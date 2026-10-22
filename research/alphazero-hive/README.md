# AlphaZero Hive

Изолированный исследовательский пакет: C++ правила → pybind11 → AlphaZero General MCTS/self-play → PyTorch policy/value CNN → обучение и арена.

## Быстрый запуск

Из `research/alphazero-hive`:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e 'bindings/python[train,test]'
python -m pytest tests/python -q
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DHIVE_BUILD_GUI=OFF
cmake --build build --target hive_tests -j 4
ctest --test-dir build --output-on-failure
python -m alphazero_hive.runner --config configs/experiments/smoke.json --run-dir runs/smoke --stop-after 1
python -m alphazero_hive.runner --run-dir runs/smoke --resume
```

Smoke использует маленькую CPU-сеть и проверяет весь цикл. Его две итерации не являются воспроизведением качества игры из статьи.

Проверенные прямые версии CPU-зависимостей записаны в `requirements-cpu-tested.txt`; для совпадающего окружения установите их перед пакетом. Manifest каждого запуска сохраняет фактические версии и digest исходников. Resume требует тот же resolved config и digest engine/training-кода.

## Обучение и оценка

```sh
python -m alphazero_hive.runner --config configs/experiments/paper-inspired.json --run-dir runs/hybrid-01
python -m alphazero_hive.evaluation --run runs/hybrid-01 --games 50 --baselines random minimax rollout --output runs/hybrid-01/tournament.json
python -m alphazero_hive.experiments --base configs/experiments/paper-inspired.json --suite representations --repeats 5 --output runs/representation-suite
```

Последняя команда создаёт 50 конфигов (две action-кодировки × пять observation-кодировок × пять seeds). `--execute` дополнительно запускает их последовательно. Другие suites: `architectures`, `loss`, `strength`. Параметры большой CNN соответствуют опубликованным конфигам: 256 каналов, 4/6/8 свёрток, dense 4096/2048. Полный запуск требует существенно больше памяти и вычислений, чем smoke; устройство задаётся `network.device` в конфиге.

Каждый каталог запуска содержит resolved config и provenance в `manifest.json`, метрики итераций и эпох в CSV, отчёты арены, начальную/выбранную/кандидатные модели и `latest.pt` с optimizer, replay buffer и RNG. `--resume` продолжает с последней полностью сохранённой итерации; незаконченная итерация выполняется заново. `--stop-after N` позволяет проверить resume без изменения конфига. Существующий каталог не перезаписывается новым запуском. Временной бюджет проверяется между итерациями и может быть превышен на одну итерацию.

## Первый CPU-пилот

Пилот завершил 6 итераций и 60 self-play партий за 5 мин 47 с, с пиком RSS 690 МиБ. Из шести кандидатов отбор не прошёл ни один; выбранная модель сохранила начальные веса. На независимых 300 матчах начальная и конечная модели обе выиграли у random 72/100, а между собой сыграли 50:50. Этот запуск не показал улучшения игровой силы.

Протокол зафиксирован до обучения в [cpu-pilot-protocol](experiments/cpu-pilot-protocol-2026-10-22.md). [Отчёт и графики](experiments/cpu-pilot-2026-10-22/README.md) содержат raw match outcomes, CI по цветосбалансированным парам, проверку идентичности весов, измерения ресурсов и resolved config. Сравнение в CLI теперь загружает точный `initial.pt` этого запуска.

```sh
python benchmarks/pilot_probe.py --pilot configs/experiments/cpu-pilot.json --paper configs/experiments/paper-inspired.json --output runs/local-probe.json
/usr/bin/time -l python -m alphazero_hive.runner --config configs/experiments/cpu-pilot.json --run-dir runs/local-pilot 2> runs/local-pilot.resources.log
python -m alphazero_hive.evaluation --run runs/local-pilot --games 100 --seed 300001 --baselines random --output runs/local-pilot/evaluation.json
python scripts/report_pilot.py --run runs/local-pilot --evaluation runs/local-pilot/evaluation.json --probe runs/local-probe.json --output experiments/local-pilot
```

Для графиков нужен Matplotlib; проверенная версия добавлена в `requirements-cpu-tested.txt`. Измерение `/usr/bin/time -l` и парсер отчёта рассчитаны на macOS. Пилот использует компактную сеть 4,25 млн параметров: расчётная память paper-сети с текущим runner превышает доступные 16 ГиБ. Её 521 млн параметров посчитаны на meta device без выделения памяти под веса.

## Граница воспроизведения

Это проверенная **адаптация подхода статьи**, а не заявление о воспроизведении всех её численных результатов. Отличия правил, представлений, оптимизатора, движка и оценки перечислены в [paper-audit.md](docs/paper-audit.md). Наши minimax, rollout MCTS и logistic Elo отличаются от Beekeeper и BayesElo авторов. Длинные запуски и аппаратные измерения энергии ещё не выполнены.

Базовый профиль C++ сохраняет 11 фигур, запрет первого ферзя, обязательного ферзя к четвёртому собственному ходу, Pass и ничью на третьем повторе. `configs/rules/paper-modified.json` явно включает отдельные экспериментальные правила; `base-capped.json` — отдельный вариант с cap для конечных запусков. GUI по умолчанию использует старый `legacy-expanded`.

## Код и проверки

- `engine/team-cpp/`: общий SFML-free core, тесты и опциональный GUI.
- `bindings/python/`: сборка pybind11; DTO ходов и полное состояние с историей.
- `src/alphazero_hive/encoding.py`: шесть observation-вариантов, relative/absolute policy, Pass, маски, 12 симметрий.
- `game.py`, `network.py`, `search.py`, `coach.py`, `runner.py`: адаптеры и сквозной цикл.
- `evaluation.py`, `experiments.py`: арена, локальные baseline-агенты, турниры, suites, интеграция измеренной мощности.
- `_vendor/alpha_zero_general/`: закреплённый MIT scaffold с лицензией и checksums; собственный код использует его MCTS.search и Coach.executeEpisode.
- `references/beekeeper/`: git-ignored локальная справочная копия, не тренировочный backend.

Происхождение: [sources.md](docs/sources.md). Текущее состояние: [implementation-status.md](docs/implementation-status.md). Замеры границы движка: [engine baseline](experiments/engine-baseline-2026-10-12.md).
