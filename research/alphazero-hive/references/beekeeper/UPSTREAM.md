# Beekeeper local reference snapshot

- Repository: <https://github.com/Fjf/Beekeeper>
- Commit: `07b14993b3ef6255b68a3c4c53c51ac22e6e9d58`
- Retrieved: 2026-10-12
- Snapshot path: local `references/beekeeper/`; source files are excluded from git.
- No `LICENSE`, `COPYING` or `NOTICE` file was present in this snapshot.
- Python Hive wrapper: `python/package/games/hive/hive.py`; it loads a C shared
  library. Prebuilt `.so` files were excluded.
- Separate C++ implementation: `cpp/`; build depends on PyTorch, CUDA and Python
  development libraries.

Known issues in the C backend are summarized in
[`../../docs/sources.md`](../../docs/sources.md). This snapshot is retained for
local study; do not redistribute it before its licensing status is clarified.
