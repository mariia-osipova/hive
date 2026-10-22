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

## Mac runner

The intended remote machine is `hutter-mac`, reached through Tailscale. This is a
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
The `Hutter Mac runner` workflow selects `[self-hosted, macOS, hutter-mac]`, verifies
the actual host and pinned author source, and runs on pushes to the reproduction
branch. There is no pull-request trigger. Registration is complete only after
GitHub reports the runner online and this workflow succeeds.

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

Full training and new tournaments are still pending. Do not describe the earlier
small pilot or analysis of published data as completion of these experiments.
