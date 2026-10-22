# Источники кода и статьи

## Командный C++-проект

- Upstream: <https://github.com/Paradigmas-UDESA/grupo-1-tp1-hive-group-4>
- Локальный источник при копировании:
  `/Users/maria/CLionProjects/grupo-1-tp1-hive-group-4`
- Snapshot tracked-файлов локального `HEAD` сохранён в `engine/team-cpp/`.
- Исключены `.git`, IDE-настройки, build output и скомпилированные бинарники.
- Выбранный профиль явно запрещает ставить ферзя первым ходом. В других
  изданиях или casual ruleset этот параметр может отличаться; поэтому он
  хранится в конфиге, а не зашит в encoding.
- Rulebook PDF:
  <https://cdn.1j1ju.com/medias/96/cb/a5-hive-rulebook.pdf>

## Beekeeper, локальная справочная копия

- Upstream: <https://github.com/Fjf/Beekeeper>
- Snapshot commit: `07b14993b3ef6255b68a3c4c53c51ac22e6e9d58`
- Локальный путь: `references/beekeeper/`; код игнорируется git до выяснения
  лицензии. В git остаётся только файл `UPSTREAM.md` с происхождением.
- В snapshot не найден `LICENSE`/`COPYING`.

Проверенные ограничения C backend:

- repetition detection в `finished_board()` закомментирован, несмотря на
  хранящийся `hash_history`;
- генератор ходов применяет tournament rule: запрещает ставить ферзя первым
  ходом;
- `MAX_TURNS` задаётся при компиляции; по достижении лимита движок выбирает
  победителя по числу соседей вокруг ферзей;
- upstream `c/readme.md` описывает незавершённую проверку `fits` для некоторых
  положений с многоуровневыми жуками.
- Python wrapper требует отдельного аудита action map: Pass проходит через
  обычный tile encoder с пустым tile index, а относительная кодировка задаёт
  семь направлений, хотя код использует отдельное значение 7 для попадания на
  занятую клетку. Проверить диапазон и уникальность индексов до reuse.

## AlphaZero и статья

- Статья: de Goede, Kampert, Varbanescu, “The Cost of Reinforcement Learning for Game Engines: The AZ-Hive Case-study”, ICPE 2022:
  <https://dl.acm.org/doi/10.1145/3489525.3511685>
- Реализация для Hive: <https://github.com/ddgoede/alphazero-hive>
- Проверенный author commit: `17e45e6b27db7591f64f11f2af83c3b59c3c126b`.
- Полный текст: <https://research.spec.org/icpe_proceedings/2022/proceedings/p145.pdf>.
- Общий training scaffold: <https://github.com/suragnair/alpha-zero-general>
- AlphaZero Hive repository declares GPL-3.0; его код здесь не копировался.
- AlphaZero General закреплён на `f1a78e0505c614205f8c60eaa82cd644a07a84b3`;
  MIT scaffold лежит в `src/alphazero_hive/_vendor/alpha_zero_general/` вместе с
  лицензией и SHA256 исходников. Изменены только package-relative imports.
- Аудит расхождений paper/code и границы воспроизведения: [`paper-audit.md`](paper-audit.md).
- AlphaZero General Game interface:
  <https://github.com/suragnair/alpha-zero-general/blob/master/Game.py>
- Classic Hive rules PDF mirror:
  <https://cdn.1j1ju.com/medias/96/cb/a5-hive-rulebook.pdf>

Статья полезна как ориентир для кодировок, MCTS и обучения; детали её
экспериментальных rulesets нужно сверять с конкретным описанием эксперимента,
а не смешивать с официальным базовым Hive.
