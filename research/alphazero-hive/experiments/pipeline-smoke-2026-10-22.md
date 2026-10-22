# Pipeline smoke: 2026-10-22

This validates the implementation, not paper strength, hardware-matched speed or energy results.

Environment: macOS arm64, Python 3.12.6, PyTorch 2.11.0, NumPy 2.3.2, CPU with one thread; native core built Release without SFML.

Configuration: `configs/experiments/smoke.json`; four-layer CNN with four channels and dense widths 32/16, two MCTS simulations, one self-play game per iteration, twelve symmetries, two iterations, explicit 29-ply modified rules.

| Iteration | Replay examples | Policy loss | Value loss | Promotion |
|---|---:|---:|---:|---|
| 1 | 348 | 7.340269 | 1.098693 | True |
| 2 | 696 | 7.129966 | 0.783533 | True |

The CLI stopped after iteration 1 and resumed to iteration 2. Both completed successfully. The test suite independently compares resumed and uninterrupted CPU model tensors and RNG states exactly, and checks restart after failure in the first iteration.

Validation: **33 Python tests passed; 169 C++ tests passed and 10 pre-existing TODO placeholders were skipped.** Tests include state/action contracts, all twelve native move-set symmetries, relative/absolute maps, stacks/Pass, all CNN depths and multiplane inputs, model checkpoint round trips, modified surround rules, and deterministic resume.

An earlier smoke run with the same config and weights completed a color-balanced tournament among trained/untrained networks and local random/minimax/rollout MCTS agents: ten pairs, two games per pair. Fresh-tree timing at two and four simulations was also exercised. These tiny samples establish execution only; no strength or comparative speed conclusion is drawn. Provenance for that run is stored separately in the JSON report.

The representation suite generator created 50 resolved configs. Long suites were planned, not executed. Energy was not measured; the integration routine is tested with a known 300 J sample.

Reproduce from `research/alphazero-hive`:

```sh
python -m pytest tests/python -q
cmake --build build --target hive_tests -j 4
ctest --test-dir build --output-on-failure
python -m alphazero_hive.runner --config configs/experiments/smoke.json --run-dir runs/reviewed-smoke --stop-after 1
python -m alphazero_hive.runner --run-dir runs/reviewed-smoke --resume
python -m alphazero_hive.evaluation --run runs/reviewed-smoke --games 2 --baselines random minimax rollout --speed-simulations 2 4 --speed-positions 2 --speed-repeats 1 --output runs/reviewed-smoke/tournament.json
```

The compact [JSON report](pipeline-smoke-2026-10-22.json) preserves resolved configuration, version/source provenance, iteration metrics and tournament smoke summaries. Local model/replay artifacts remain in ignored `runs/` directories.
