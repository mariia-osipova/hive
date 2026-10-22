# Эксперименты

Конфиги запуска ссылаются на отдельные `rules` и `representations`. Не менять
эти файлы после запуска: сохранять разрешённую конфигурацию в manifest.

Каждый запуск фиксирует:

- resolved config, commit C++ core и commit training code;
- версии Python, PyTorch, компилятора, pybind11 и build flags;
- seed, число MCTS simulations, Dirichlet noise и temperature schedule;
- число self-play партий, training step и checkpoint id;
- policy/value loss, inference/turn throughput и результаты arena;
- все отличия от предыдущего запуска.

Артефакты хранятся в `runs/<run-id>/`: `manifest.json`, `metrics.csv`, `logs/`
и `checkpoints/`. Каталог игнорируется git; в репозитории остаются конфиги и
небольшие сводные таблицы.

Сначала зафиксировать baseline, потом менять один фактор за эксперимент.
Модели сравнивать одинаковым числом arena-матчей на фиксированных seed,
меняя цвет первого игрока; записывать win/draw/loss и интервал неопределённости.
