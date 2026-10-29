# Replication audit — 2026-10-29

**The requested deliverable is a verified setup with algorithms exercised live;
training is left for the user to run manually.** The original code also passes
a bounded training integration check. Full-paper experimental replication is
not claimed and is outside the clarified setup request.

References: [ICPE 2022 paper](https://research.spec.org/icpe_proceedings/2022/proceedings/p145.pdf),
DOI 10.1145/3489525.3511685, and [preserved author commit](https://github.com/ddgoede/alphazero-hive/tree/17e45e6b27db7591f64f11f2af83c3b59c3c126b).

## Checked evidence

| Check | Result | Interpretation |
| --- | --- | --- |
| Archive and independent GitHub tree | All 647 Git blobs match | Author source/data identity |
| Extracted files | All 646 match; shipped Linux `.so` explicitly replaced by recorded Mac build | Source/config/CSV/PGN integrity |
| Native rebuild | Identical library SHA256 | Repeatable local build |
| Encoding/architecture coverage | All 16 full-size inference checks pass | Both action encodings, all five representations, 4/6/8 layers, augmentation settings |
| Original training integration | One MCTS episode yields 348 augmented examples; first 64 train for 10 original epochs/optimizer steps | Original self-play and optimizer execute, full 120,883,872 parameters; value-head weights change |
| Checkpoint | Corrupt in-memory weights, reload, recover identical policy/value predictions | Weight serialization works |
| Arena | Two games finish, one win each against random | Integration only; no strength inference |
| Native opponents | Minimax and rollout MCTS return legal actions at plies 8 and 9 | Execution for both player parities |
| Live algorithm suite | Eight complete games, 168 checked legal moves; minimax, rollout MCTS, neural MCTS and policy each face random in both colors | Every automated algorithm exercised without training |
| Saved checkpoint live play | Two further neural MCTS vs policy games; 18 legal moves | Provided-checkpoint mode works without optimization |
| State screen | 48 games, 974 states, 147 tactical cases; all replay/codec/geometry checks pass | Deterministic local rule checks |
| Published data | Ten representation series and both candidate loss series recomputed; independent aggregation matches author plotting functions | Reanalysis only |
| Published Elo | Default advantage matches six rounded ratings; zero advantage differs | Calculation only, no fresh tournament |

Evidence is in `results/verification-2026-10-29/`,
`results/live-algorithms-2026-10-29/`,
`results/native-opponents-2026-10-29.json`, `results/published-data-audit.json`,
`results/upstream-tree-2026-10-29.json` and
`../hive-paper-lab/results/screen-2026-10-29/`.
Integration weights remain local; SHA256 and size are exported.

## Discrepancies

The following findings preserve the original code:

- Move-limit ties go to black in the paper but white in C `finished_board`.
  Two replayable trajectories show equal queen-neighbor counts at ply 29.
  Example: seed 20261022, episode 8, state SHA256
  `7cfd9b48984a6833ace5d77ac0c24dd53231889efcd0166ddbfce5d871b4440a`.
- Figure 6 matches BayesElo's default 32.8 advantage; zero as specified differs.
- The PGN encodes 1,500 synthetic games from aggregate outcomes, 500 per engine;
  the text states 400. Actual game moves cannot be recovered from that artifact.
- Author `results_comparison.txt` gives `4h - MCTS: 27 - 100`; the generator and
  PGN consistently encode 27 wins and 73 losses.
- `plots_policy_value_loss()` defaults to ten-plane input; section 5.1 describes
  hybrid input. Both candidate series are exported; figure identity is unresolved.
- 54 published baseline rows contain fewer than 50 decisive results. Author plots
  divide wins by wins+losses, excluding outcomes not recorded in those two columns.
- The printed cost expression gives 198,360,000 minutes, or 377.40 365-day
  node-years before rounding. The energy integrals sum to 6.65 MJ. Multiplying
  324,000 runs by the rounded 6.6 MJ gives 594 MWh; the reported 602.78 MWh is not
  recovered from those inputs. These are arithmetic checks, not measurements.

## Missing experiments

| Study | Fresh evidence still required |
| --- | --- |
| Loss evolution | Five independent hybrid/tile-relative runs, ten iterations each |
| Representation comparison | Two encodings × five representations × five repetitions; timed training and baseline evaluation |
| Architecture/augmentation | Repeated training for 4/6/8 layers with/without symmetries |
| Six-engine tournament | Trained 4h/24h policies, untrained/random/native opponents, 100 games per pair |
| Playing speed | Fixed-hardware measurements across MCTS budgets |
| Energy | CPU/GPU measurements on reference hardware or a clearly labeled different platform |

A fresh original Coach run was stopped following the user's clarification that
training should be manual. It completed no optimization epochs. Its preserved
status is in `results/local-cpu-2026-10-29/`. The separate bounded training
integration check finished before that clarification. No training remains active.
Future manual training uses the complete published JSON: 20 iterations,
100 self-play games each, 25 simulations, 10 epochs, batch 64, 40 comparisons.
Timed reference GPU runs differ from a fixed-iteration Mac run.

Original random seeds and reference trained weights are absent from the pinned
archive. The Mac has no NVIDIA GPU for the reference energy measurements. The
original Coach does not save optimizer/RNG/self-play history for exact resumption.
Source identity does not establish numerical equivalence.

## Recheck

```sh
python3 research/az-hive-exact/scripts/bootstrap.py
research/az-hive-exact/.venv/bin/python research/az-hive-exact/scripts/test_fidelity.py
python3 research/az-hive-exact/scripts/reanalyse_published_data.py
python3 research/az-hive-exact/scripts/reanalyse_published_elo.py
# Must reject a running/incomplete experiment:
python3 research/az-hive-exact/scripts/export_run.py \
  --run research/az-hive-exact/runs/original-symmetric-4layer-2026-10-29 \
  --output research/az-hive-exact/results/local-cpu-2026-10-29 \
  --require-complete
```
