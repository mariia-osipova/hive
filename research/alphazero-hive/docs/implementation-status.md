# Implementation status

## Implemented

- SFML-free C++ core, legacy/base profiles, stable actions, deep clone, repetition-aware key and Python binding.
- Explicit configurable surround threshold, ply cap, cap adjudication and tie handling; base defaults remain unchanged.
- Height-aware Beetle gate check, including climbing and elevated descent.
- Six observation encodings, absolute and relative action maps with Pass, masks and 12 symmetry transforms.
- AlphaZero General Game/NeuralNet interfaces, pinned MIT scaffold, MCTS/self-play integration and configurable CNN.
- Training, candidate/previous arena, promotion, random baseline, manifests, epoch/iteration CSV, atomic checkpoints and iteration-boundary resume with optimizer/replay/RNG.
- Color-balanced tournament, local minimax and rollout MCTS baselines, regularized logistic Elo, move timings, experiment suite generation and measured-power CSV integration.

## Validation

Python tests cover action injectivity and round trips, stacks, first placement, Pass/terminal masks, all observation shapes, symmetry policy mass and native move-set equivariance over legal playouts. Training tests check player perspective, terminal signs, four-neighbor rules, checkpoint compatibility, weight updates and deterministic CPU resume.

C++ tests include movement fixtures for every piece, one-hive/sliding/stacking, queen status, Pass/repetition, cap/clone behavior and the Beetle gate regression. A short real self-play/training/arena run is recorded in `experiments/pipeline-smoke-2026-10-22.md`.

## First CPU pilot

The first compact CPU pilot is complete: six iterations / 60 self-play games, 347.41 s wall time, 723,075,072-byte peak RSS. None of six candidates passed promotion, so the selected network remains the exact initialization. In 300 held-out matches with seeds separate from training, both initial and selected models scored 72/100 against random and 50:50 head to head. No playing-strength gain was established. Results, plots and model fingerprints: [`cpu-pilot-2026-10-22`](../experiments/cpu-pilot-2026-10-22/README.md).

## Still required for a complete paper reproduction

- Resolve the paper/code differences in board dimensions, cap semantics, tie adjudication and representation transforms; see `paper-audit.md`.
- Full independent movement parity against a rules-compatible reference. Existing Beekeeper differential evidence covers only one opening; symmetry properties and hand fixtures are not a complete oracle.
- Run the long repeated experiment suites, reproduce loss/strength/speed plots, and evaluate 4h/24h models against the original opponents under matched search budgets.
- Use the original BayesElo evaluation if numerical comparison to the paper's Elo is needed. Local logistic Elo is labeled separately.
- Record actual CPU/GPU energy samples on the training hardware and integrate them; no energy result is inferred from wall time.

The implementation is an executable, tested adaptation. Smoke results do not establish playing strength, paper parity or completed long experiments.
