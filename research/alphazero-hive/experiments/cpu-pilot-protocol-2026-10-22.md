# CPU pilot protocol — fixed before training

Purpose: establish resource feasibility and test whether one compact AlphaZero Hive run shows improved playing strength. This is not a paper-scale reproduction.

The [preceding CI run](https://github.com/mariia-osipova/hive/actions/runs/39826593002) completed successfully at commit `5aefc071f65abe3b8a25c88fd73cd0b9907bd89f`.

## Resource decision

The host has 16 GiB RAM and eight logical CPUs. The paper configuration has 521,174,688 parameters: 2.08 GB of float32 weights; accounting for two models, two Adam states and gradients gives 14.59 GB. The runner's temporary deep copy can raise parameter-state storage to approximately 20.85 GB, excluding activations/replay/framework. These are meta-device parameter estimates, not measured full-model RSS. The full model is not allocated for this pilot.

The selected four-layer compact network has 4,246,816 parameters, channels 32, dense widths 256/128 and dropout 0.3. A CPU probe measured one-thread median inference at 0.605 ms, opening MCTS at 21.7 ms for 25 simulations, and process peak RSS at 499 MB after two training batches. Two/four threads slowed single-position inference, so the run uses one thread. Probe batches are synthetic; real training costs are recorded separately.

## Fixed training configuration

`configs/experiments/cpu-pilot.json`: seed 1, hybrid observation, relative policy, twelve symmetries, 25 simulations, cpuct 0.8, Dirichlet alpha 0.3/fraction 0.25, six iterations × ten self-play games, three epochs, batch size 64, Adam LR 0.001, replay history three iterations. Promotion uses 40 color-balanced games, threshold 0.55; per-iteration random monitoring uses 20 games. The 1,800-second training budget is checked between iterations. The unmodified native rule contract is the explicit four-neighbor/29-ply adaptation in `configs/rules/paper-modified.json`.

No configuration or checkpoint is chosen by looking at the final holdout results. The selected final model is `best.pt` from the existing promotion procedure. All candidates, initial weights and resumable checkpoints are preserved locally.

## Fixed final evaluation

`configs/evaluations/cpu-pilot.json`: seed 300001, 100 games per pair among the selected model, its exact saved initialization, and random. Both neural agents use 25 simulations and the same rules, with root noise disabled. Each agent plays 50 games with each color per opponent. Evaluation compares to `initial.pt`, not a freshly sampled random network. Checkpoint SHA256 digests are recorded.

Training promotion and random-monitor seeds are disjoint from the final evaluation seeds. Confidence intervals resample the 50 color-swapped game pairs as blocks, with 10,000 samples and RNG seed 90210. Report the trained-vs-initial win rate, each model's win rate against random, the paired difference against random, and color splits.

The pilot's positive-signal criterion is fixed in advance: the trained-vs-initial 95% interval must lie above 50%, and the trained-minus-initial random win-rate interval must lie above zero. Otherwise the pilot does not establish improvement. One training seed does not establish robustness across seeds.

Deliverables: resolved configs, resource measurements, epoch/iteration metrics, 300 holdout match outcomes with move timings, checkpoint identities, and plots of loss, win rate and elapsed training time. Long paper experiments and energy measurements are outside this pilot.
