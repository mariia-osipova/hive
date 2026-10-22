# ADR-0001: C++ core и Python training loop

- Статус: принято для прототипа.
- Контекст: текущая игра и GUI уже используют C++; AlphaZero General и
  нейросеть удобнее подключить из Python; Beekeeper послужил backend в статье.

## Решение

Оставить один источник игровых правил — C++ core из `engine/team-cpp/` — и
подключить его к Python через pybind11. AlphaZero General предоставляет Coach,
MCTS и generic training loop. Beekeeper хранить локально для чтения кодировок и
сверки отдельных случаев, не использовать как runtime dependency.

## Почему не Beekeeper как backend

В snapshot нет файла лицензии. Повторение позиций в C-коде фактически
отключено, compile-time turn cap завершает игру выбором победителя по эвристике,
upstream сообщает об edge case `fits` для стеков жуков, а Python action map
требует проверки на Pass и stacked Beetle. Для выбранной задачи это создаёт
правовые, rule-parity и encoder неопределённости.

## Последствия

- Нужно добавить base-only `Ruleset`, Pass, repetition history и независимое
  состояние для ветвления поиска в C++ core.
- Зафиксированный профиль запрещает ферзя первым ходом, как Beekeeper
  tournament opening rule. Если исследуется вариант, разрешающий первого
  ферзя, переключать отдельный config, не смешивая результаты.
- Python получает только устойчивый API действий/состояния; детали C++ не
  протекают в MCTS и модель.
- Первый Python MCTS может оказаться медленным из-за частых переходов через
  binding; до оптимизации измерить throughput на фиксированном benchmark.
- Beekeeper snapshot остаётся локальным и git-ignored до выяснения лицензии.
- До завершения rule fixtures и проверки копирования self-play не считается
  корректным экспериментом.
