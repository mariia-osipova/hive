# AZ-Hive replication verification

Apply the installed autoresearch skill and keep author code immutable. The TP3
benchmark repository and Make targets are absent here.

Fixed baseline: author commit `17e45e6b27db7591f64f11f2af83c3b59c3c126b`,
647 archive blobs, Mac arm64, GNU GCC 15, Python 3.12, CPU, four Torch threads.
The October 22 original run completed zero training iterations. The adapted
pilot is not original-code evidence.

Address one fidelity problem per change. Rerun the affected fixed checks and
keep the change only when correctness is preserved. No speed claim without
before/after measurements. Never silently reduce a paper budget.

1. Verify archive SHA256, independent GitHub tree, extracted files and native
   build hash. Only the shipped Linux shared library is deliberately rebuilt.
2. Check all 16 encoding/representation/architecture choices in fresh processes.
3. Check original MCTS self-play, real full-size-network optimizer steps, finite
   losses, changed weights, checkpoint restoration and completed arena games.
4. Check native minimax/rollout-MCTS moves for both player parities.
5. Replay 48 fixed seeded trajectories; check geometry, symmetries and codecs.
6. Recompute published data separately from collecting new experimental data.
   Preserve discrepancies; do not modify algorithms to conceal them.
7. Export full-run evidence with `export_run.py --require-complete`. Missing
   epochs, comparisons or final weights, or changed parameters, must fail.
8. Push reviewed code and small evidence, fetch, and verify the remote SHA.

Full-paper replication additionally requires the repeated training, timed
representation studies, trained tournament, speed study and energy measurements
in `REPLICATION_STATUS.md`. Passing checks or starting a job cannot satisfy that
claim. Record hardware differences and unpublished reference seeds/checkpoints.
