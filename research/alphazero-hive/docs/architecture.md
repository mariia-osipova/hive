# Архитектура

```text
resolved config + seed
        ↓
Python runner → manifest / metrics / replay / RNG / checkpoints
        ↓
A0G Coach.executeEpisode ← HiveCoach + HiveMCTS → A0G MCTS.search
        ↕                                   ↕
HiveGame                               HiveNet / PyTorch
        ↓                                   ↑
pybind11 → C++ Hive core              observation + policy targets
             ↑
        optional SFML GUI
```

## Правила и состояние

Единственный тренировочный источник правил — C++ `Game`. Он владеет фигурами, глубоко клонирует доску, хранит turn, инвентарь, статус и историю повторов. Native `state_key()` различает идентичности action-слотов, релевантную историю, deadline ферзя и оставшийся бюджет cap. Python не реализует вторую проверку легальности.

`HiveState` хранит native object и цвет перспективы. Canonicalization меняет перспективу, сохраняя абсолютные цвета и историю в core. `getNextState` всегда клонирует родителя. `stringRepresentation` включает перспективу и полный native key; observation никогда не используется как MCTS key.

Для A0G незавершённая игра возвращает 0, ничья — sentinel `1e-8`, который обучение переводит в настоящий reward 0. Победа/поражение возвращают ±1 относительно запрошенного игрока. Экспериментальные caps задаются правилами, а не скрытым обрезанием self-play. Runner требует cap 1–256 plies; API движка по-прежнему позволяет партии без cap.

## Представления

Доска кодируется в 26×26 skew grid: `x=q+r, y=r`, occupied bounding box центрируется. Для connected base Hive достаточно места с padding для соседних legal destinations. При нарушении границ encoder вызывает ошибку и не обрезает данные.

Observation: `original`, `symmetric`, `simple`, `binary` (10 плоскостей), `hybrid` (4), `identity` (23). Hybrid показывает верхние фигуры; identity хранит все экземпляры и высоту каждой фигуры. Ни один из этих входов не содержит полной истории повторов, поэтому value-сеть не получает всего марковского состояния; правила и поиск получают его из native object.

Relative policy: `(reference=22, direction=7, moving_piece=11)` плюс Pass, всего 1695. Own slots: Q,A1–3,G1–3,S1–2,B1–2; enemy reference slots имеют обратный порядок. Шесть axial directions и on-top. Выбирается минимальный stationary reference ID, чтобы несколько соседей одного destination не создавали разные представления одного легального хода. Пустой дебют использует иначе невозможный self-reference/on-top. Стек не теряет экземпляры фигур. Absolute policy: `(11,26,26)` плюс Pass, всего 7437.

Decode проверяет индекс против legal map текущего состояния. Маска строится тем же codec. Для симметрии координаты преобразуются до построения observation и policy; таблица соответствий legal DTO обеспечивает сохранение policy mass. Augmentation не меняет native state/history.

## Обучение

A0G закреплён по commit; vendor изменяет только два абсолютных импорта на относительные. `HiveMCTS` использует исходный `MCTS.search`, добавляя optional root noise и безопасное извлечение вероятностей только по legal actions. Требуется не менее двух simulations, чтобы после раскрытия корня был посещён хотя бы один edge. `HiveCoach` наследует неизменённый self-play episode из A0G.

CNN повторяет активные слои авторского кода: первые две свёртки с padding, остальные без, BatchNorm/ReLU, shared dense и policy/value outputs. Маленький smoke-конфиг использует те же операции с меньшими размерами. Optimizer сохраняется между итерациями, включая resume. CPU-тест сравнивает продолженный и непрерывный запуск побитово по весам и RNG.

Runner отвечает за очередь примеров, обучение кандидата, цветосбалансированную арену, promotion, random baseline и checkpoint. Seed оценки изолирован от RNG обучения. `latest.pt` записывается атомарно и является источником истины для resume; CSV восстанавливаются из него. Артефакты незаконченной итерации могут существовать, но resume их не использует. Long-run checkpoints содержат replay и могут быть крупными.

## Границы

Браузерная игра в корне не используется для self-play. Beekeeper — ограниченный локальный справочник; полная differential parity не заявляется. Точный upstream behavior и результаты статьи требуют отдельного согласования из-за противоречий paper/code, описанных в `paper-audit.md`.
