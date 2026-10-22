# Original AZ-Hive reproduction

This workspace uses the original [AZ-Hive implementation](https://github.com/ddgoede/alphazero-hive/tree/17e45e6b27db7591f64f11f2af83c3b59c3c126b)
for [the ICPE 2022 paper](https://research.spec.org/icpe_proceedings/2022/proceedings/p145.pdf).
The earlier `research/alphazero-hive-reproduction` branch contains an adaptation and a small pilot;
those results do **not** reproduce the paper.

`upstream/author-source.tar.gz` is the unmodified author archive. Its SHA256 and all
647 original Git blob hashes are recorded in `upstream/author.lock.json`. The GPL-3.0
license is retained. Verify it with:

```sh
python3 research/az-hive-exact/scripts/verify_source.py
```

The original Python code includes its own MCTS, Coach, network, and ctypes wrapper;
the original C Beekeeper source includes the minimax and rollout MCTS opponents.
The network wrapper crops the native 26×26 board to 14×14 before inference and
training. This is original behavior, not an unresolved dimension mismatch.

## Local Mac execution

The active target is the user's own Mac. Remote runner setup was stopped at the
user's request; its queued check was cancelled, and no remote runner was registered.

```sh
python3 research/az-hive-exact/scripts/bootstrap.py
python3 -m venv research/az-hive-exact/.venv
research/az-hive-exact/.venv/bin/python -m pip install -r research/az-hive-exact/requirements-macos.lock.txt
research/az-hive-exact/.venv/bin/python -u research/az-hive-exact/scripts/run_original.py \
  --config nn_architecture/symmetries/4-layers/1 \
  --output research/az-hive-exact/runs/NEW-RUN
```

The full network has **120,883,872 parameters** including the original unused
convolution layers. The selected published JSON uses 20 iterations, 100 self-play
games per iteration, 25 MCTS simulations, 10 epochs, batch size 64, 40 comparison
games, a 0.5 acceptance threshold, and five iterations of training-data history.
Rotation/reflection augmentation is enabled. The original Coach first evaluates
50 games against random before starting self-play and optimization.

Original Python/C source files are verified before every run. The harness changes
only the selected published configuration's module globals, output paths, CUDA
availability, and a recorded new seed. It restores `numpy.str = str`, the alias
used by the author's old NumPy, without editing the original source. Modern GCC
requires `-fcommon`; signed-char behavior is set explicitly. The native library is
built from the author's original nine translation units. Build flags and hashes
are saved in `work/build.json`; environment, parameters, source identity and status
are saved in each run's `run.json`. Source identity does not imply identical
floating-point behavior across platforms.

The unmodified Coach does not save training-example history during `learn()`.
Its checkpoints preserve model weights, not an exact resumable training state.
Do not claim a restarted run continues the same experiment.

## Optional remote runner preparation

The previously considered remote machine was `hutter-mac`, reached through Tailscale. This is a
separate machine from the developer's local Mac. Register it only after obtaining
its actual macOS SSH username:

```sh
python3 scripts/register-mac-runner.py --tailscale --ssh USER@hutter-mac
```

This requires the existing authenticated `gh` session to have repository admin
access, and an authorized SSH login on the selected Mac. A Tailscale account email
does not identify the macOS login. The installer checks the operating system and
architecture, downloads the official GitHub runner release, verifies its SHA256,
registers it for `mariia-osipova/hive` with `hutter-mac` and `az-hive` labels, and
installs/starts its standard macOS user service. Registration credentials are sent
over SSH stdin and are not saved in the repository.

The runner uses `~/.local/share/github-actions/mariia-osipova-hive-hutter-mac`.
The draft workflow was removed when the user selected local execution. No remote
jobs or installation are part of the active run.

## Fidelity and remaining work

The goal is to run the original source with the published experiment JSON files,
including full network widths, self-play counts, epochs, and native opponents.
macOS/CPU and a modern Python/PyTorch environment differ from the original
Linux/NVIDIA setup. Runtime, energy consumption, and numerical results must be
reported as local results with those differences recorded. Identical source alone
does not establish identical experimental outcomes.

The published `results/traditional_comparison/tournament.pgn` contains aggregate
outcomes encoded as PGN by the authors' generator. Reanalysing it with BayesElo
checks the published Elo calculation; it is not a fresh tournament.

The local original-code run was stopped at the user's request during self-play
of iteration 1. Its initial, untrained model won 28/50 games against random;
no optimization epochs or complete training iterations finished. The saved partial
results are in `results/local-cpu-2026-10-22/`. Model weights remain local; their
hash and size are recorded with the exported results. The earlier pilot and
published-data reanalysis do not establish completion of the experiments.

Recompute the published Elo analysis after bootstrap with:

```sh
python3 research/az-hive-exact/scripts/reanalyse_published_elo.py
```

The explicitly specified zero first-move advantage gives ratings differing by
1–2 points from Figure 6. BayesElo's default advantage (32.8) reproduces its rounded
ratings. Both outputs are retained; this discrepancy remains unresolved.
