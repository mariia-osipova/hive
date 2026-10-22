# Python binding

The package builds the same `hive_core` used by the C++ tests and GUI. It does
not contain a second rules implementation.

From this directory, install an editable development package with:

```sh
python -m pip install -e .
```

```python
from alphazero_hive import Game

game = Game()  # base Hive profile, no expansions
actions = game.legal_actions()
child = game.clone()
assert child.apply_action(actions[0])
assert child.state_key() != game.state_key()
```

`Game(profile="legacy-expanded")` exists only to keep the copied SFML GUI
engine compatible. Experiments should name the base profile explicitly in their
manifest. The binding exposes action dictionaries and a history-aware state key.

The AlphaZero policy encoder remains a separate draft: the paper's tile-relative
action map is not yet audited, so this package intentionally does not claim paper
reproduction or expose a training-ready fixed action space.
