"""Refresh the small, MIT-licensed AlphaZero General scaffold at a pinned commit."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

COMMIT = "f1a78e0505c614205f8c60eaa82cd644a07a84b3"
DEST = Path(__file__).resolve().parents[1] / "src/alphazero_hive/_vendor/alpha_zero_general"


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    checksums = {}
    for name in ("Game.py", "NeuralNet.py", "MCTS.py", "Coach.py", "Arena.py", "utils.py", "LICENSE"):
        url = f"https://raw.githubusercontent.com/suragnair/alpha-zero-general/{COMMIT}/{name}"
        with urlopen(url, timeout=30) as response:
            raw = response.read()
        checksums[name] = hashlib.sha256(raw).hexdigest()
        source = raw.decode()
        for module in ("Arena", "MCTS", "utils"):
            source = source.replace(f"from {module} import", f"from .{module} import")
        (DEST / name).write_text(source)
    (DEST / "__init__.py").write_text('"""Pinned AlphaZero General; see UPSTREAM.json and LICENSE."""\n')
    (DEST / "UPSTREAM.json").write_text(json.dumps({
        "repository": "https://github.com/suragnair/alpha-zero-general",
        "commit": COMMIT,
        "changes": "Only package-relative imports in Coach.py and Arena.py.",
        "upstream_sha256": checksums,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
