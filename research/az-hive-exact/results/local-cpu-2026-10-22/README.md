# Partial local original-code run — 2026-10-22

Stopped at the user's request. This is not a completed reproduction or a trained-model result.

- Original author C Beekeeper, Python MCTS/Coach and full 120,883,872-parameter network.
- Published configuration: `nn_architecture/symmetries/4-layers/1`.
- Initial **untrained** model vs random: **28 wins, 22 losses, 0 draws (50 games)**.
- Iteration 1 self-play: **47/100 completed games** before interruption.
- Completed optimization epochs: **0**. Completed training iterations: **0**.
- Runtime: macOS arm64, CPU, Python 3.12 / modern PyTorch, not the paper's Linux/CUDA environment.

`console.log` is the raw terminal log, including carriage-return progress output
and the expected KeyboardInterrupt from the requested stop. `run.json` records
parameters, seed, dependencies, compatibility shim and stopped status. The initial
checkpoint remains local; `summary.json` records its SHA256 and byte size. The
original Coach did not persist self-play history, so this is not an exact resumable
training checkpoint. The new seed was recorded; author seeds were not published.

The nearby `cpu-batch-timing.json` measures three synthetic full-size batches only.
It is a rough runtime measurement, not optimization of the experiment's model.
Published Elo reanalysis is stored separately and contains no new tournament games.
