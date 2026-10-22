# Paper audit and reproduction boundary

The DOI previously labeled “AlphaZero for Hive” in this workspace belongs to **The Cost of Reinforcement Learning for Game Engines: The AZ-Hive Case-study**, de Goede, Kampert and Varbanescu, ICPE 2022.

Primary references inspected:

- [Proceedings PDF](https://research.spec.org/icpe_proceedings/2022/proceedings/p145.pdf), especially sections 4.3, 5 and 6.
- [Author repository](https://github.com/ddgoede/alphazero-hive/tree/17e45e6b27db7591f64f11f2af83c3b59c3c126b), pinned at `17e45e6b27db7591f64f11f2af83c3b59c3c126b`.
- `hive-engine/hive/HiveGame.py`, `hive-engine/hive/pytorch/{HiveNNet,NNet}.py`, `beekeeper/c/engine/{board.c,board.h}` at that commit.
- Published `results/tile_relative/regular/spatial_planes_4/1/{training-parameters,nn-parameters}.json`.

The author repository was read as a reference; its GPL training implementation is not vendored here. The generic MIT AlphaZero General files are pinned independently at `f1a78e0505c614205f8c60eaa82cd644a07a84b3`, with their license and original-file checksums in `_vendor/alpha_zero_general/`.

## Corrections to the initial draft

| Component | Paper / inspected source | This implementation |
|---|---|---|
| Hybrid observation | Four planes: two queens and two integer nonqueen planes | Four top-view planes, relative to side to move; our plane order is own queen, enemy queen, own other, enemy other |
| Binary observation | Ten color/type planes | Ten top-view planes; plane order is documented by `encoding.py` |
| Old 23-plane draft | Not the paper hybrid | Retained only as separate `identity` option: 22 piece slots with stack levels plus absolute perspective plane |
| Tile-relative action size | Source shape `(22,7,11)` plus Pass | 1695, not the earlier 1771 candidate |
| Absolute action size | `(11,26,26)` plus Pass | 7437 |
| Opening action | Source uses the otherwise unused self-reference | Self-reference/on-top, with no extra empty-tile reference plane |
| Symmetries | Six rotations times two reflections | Transform native coordinates before encoding, recenter, remap each legal action; test mass and move-set preservation |
| CNN | Author code: padded first two convs, remaining unpadded, shared dense 4096/2048, policy/value outputs | Same active layer topology; only active conv blocks are constructed; smoke uses smaller channels/dense widths |

Our relative reference is the smallest stable identity among stationary pieces adjacent to or under the destination. It is deterministic under geometric symmetries and gives one ID per native legal DTO. Direction numbering is native axial order, not the author's Beekeeper permutation. These changes require new checkpoints; published weights are not compatible.

The paper's five observations are implemented as explicit adaptations (`original`, `symmetric`, `simple`, `binary`, `hybrid`). Native piece/stack fields are encoded directly rather than reproducing the author's decimal-modulo transforms. The top-view variants intentionally omit buried pieces; `identity` preserves their stack order. Original decimal concatenation remains a lossy/awkward float32 input for some large stack values. Full repetition history stays in the native game and search key, not the network observation.

## Contradictions that prevent claiming exact parity

1. **Board size:** paper section 4.3 describes 26×26; the inspected `HiveGame` defaults to `n=14`, while `NNet.py` allocates 14×14 spatial planes and the native board wrapper uses width 26. We use 26×26 consistently and center the occupied bounding box.
2. **Cap:** paper describes 30 moves. The backend default is `MAX_TURNS=30`, starts at `turn=0`, and adjudicates at `turn==MAX_TURNS-1`. The explicit adaptation therefore uses **29 plies**, where a ply is one player's action. This is the inspected default behavior, not proof of the flags compiled for every published experiment.
3. **Cap ties:** paper and the backend comment say black wins; the inspected C expression returns white on equal queen-neighbor counts. Our adaptation awards ties to black, following the prose. Terminal surround takes priority over cap adjudication here; the snapshot's cap branch overrides the earlier surround result.
4. **Simultaneous surrounds:** the C backend returns a draw, and the Python wrapper uses a small negative terminal value. The paper describes draw-free modified rules. Our modified profile explicitly awards simultaneous surrounds to black; base Hive retains draws.
5. **Rules:** the original backend has incomplete repetition and known stacked-Beetle caveats. We use our tested C++ core, including a height-aware gate fix. The one checked Beekeeper opening is not evidence of full movement parity.
6. **Training:** we use persistent Adam state, shuffled passes including the last partial batch, exact zero draw targets, per-iteration checkpoints and isolated evaluation RNG. The inspected wrapper recreates Adam inside `train()` and uses its own batch sampling. Dirichlet noise is off in the paper-inspired config and explicitly on in smoke.
7. **Evaluation:** our minimax and rollout MCTS are local baselines with their own search budgets. They are not the original Beekeeper agents. Our Elo is a regularized logistic fit with draw half-points and mean 1000, not the paper's BayesElo. These ratings cannot be compared numerically to its Figure 6.

## Experiment coverage

`paper-inspired.json` transcribes the published selected run's scalar parameters: 20 iterations, 100 self-play games per iteration, temperature threshold 15, 25 simulations, cpuct 0.8, 40 promotion games, threshold 0.5, replay history 20, max iteration queue 200000, Adam LR 0.001, dropout 0.3, 10 epochs, batch size 64, 256 channels and four conv layers. The implementation runs on CPU by default; choose a device explicitly for long runs. The configured four-hour budget is checked at iteration boundaries.

The suite generator covers 10 action/observation combinations, 4/6/8-layer and symmetry comparisons, ten-iteration loss runs and 4h/24h strength runs, with configurable repeated seeds. It generates plans unless `--execute` is supplied. Run evaluation against the desired checkpoints with the same arena configuration. `hive-evaluate --speed-simulations ...` measures neural MCTS thinking time on fixed saved-run positions independently from the arena. CPU/GPU energy is accepted only as measured timestamp/power samples through `--energy-csv`; no synthetic energy measurement is supplied.

**No long suite, paper strength result, hardware-matched throughput result or measured energy result has been reproduced yet.** The committed smoke report establishes that the implementation executes and resumes correctly. Exact paper replication still requires resolving the above contracts and matching original opponents, hardware and experiment artifacts.
