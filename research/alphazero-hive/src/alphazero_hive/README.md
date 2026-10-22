# Python package

`alphazero_hive._hive_cpp` supplies native rules, stable DTOs, independent clone, board stacks, terminal result and history-aware keys. `Game()` selects base Hive; legacy expansions require `Game("legacy-expanded")`.

`encoding.py` implements six observation representations and two policy encodings; `game.py` implements the AlphaZero General Game contract. `search.py` and `coach.py` adapt the pinned MIT scaffold without replacing its recursive search or self-play episode procedure. `network.py` implements the CNN and NeuralNet contract. `runner.py` provides training, promotion and deterministic iteration-boundary resume. `evaluation.py` and `experiments.py` provide evaluation and experiment suites.

See the project README for installation and commands; see `docs/paper-audit.md` for explicit reproduction limitations.
