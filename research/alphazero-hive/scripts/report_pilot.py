"""Build the fixed pilot report from recorded measurements and match outcomes."""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

import numpy as np


def agent_matches(report, first, second):
    for pair in report["pairs"]:
        if {pair["first"], pair["second"]} == {first, second}:
            sign = 1 if pair["first"] == first else -1
            rows = sorted(pair["result"]["matches"], key=lambda row: row["match"])
            results = np.asarray([row["result"] * sign for row in rows])
            colors = [row["first_color"] if sign == 1 else
                      ("black" if row["first_color"] == "white" else "white") for row in rows]
            return results, colors
    raise ValueError(f"Missing match pair: {first}, {second}")


def summarize_holdout(report, bootstrap_seed=90210, resamples=10000):
    games = report["games_per_pair"]
    if games < 2 or games % 2:
        raise ValueError("Evaluation needs an even number of games")
    trained, trained_colors = agent_matches(report, "trained", "random")
    initial, initial_colors = agent_matches(report, "initial", "random")
    direct, direct_colors = agent_matches(report, "trained", "initial")
    for results, colors in ((trained, trained_colors), (initial, initial_colors), (direct, direct_colors)):
        if len(results) != games or colors != ["white", "black"] * (games // 2):
            raise ValueError("Match pairs must be complete and color balanced in recorded order")
    rng = np.random.default_rng(bootstrap_seed)
    indices = rng.integers(0, games // 2, size=(resamples, games // 2))

    def interval(values):
        pairs = values.reshape(-1, 2).mean(axis=1)
        bootstrapped = pairs[indices].mean(axis=1)
        return {"estimate": float(values.mean()),
                "ci95": np.quantile(bootstrapped, [0.025, 0.975]).tolist()}

    def result(values, colors):
        summary = interval((values == 1).astype(float))
        summary.update({"wins": int(np.sum(values == 1)), "losses": int(np.sum(values == -1)),
                        "draws": int(np.sum(values == 0)), "games": len(values),
                        "white_wins": int(sum(value == 1 and color == "white" for value, color in zip(values, colors))),
                        "black_wins": int(sum(value == 1 and color == "black" for value, color in zip(values, colors)))})
        return summary

    trained_random = result(trained, trained_colors)
    initial_random = result(initial, initial_colors)
    trained_initial = result(direct, direct_colors)
    difference = interval((trained == 1).astype(float) - (initial == 1).astype(float))
    positive = trained_initial["ci95"][0] > 0.5 and difference["ci95"][0] > 0
    return {"trained_vs_random": trained_random, "initial_vs_random": initial_random,
            "trained_vs_initial": trained_initial, "random_win_rate_difference": difference,
            "positive_signal_criterion_met": bool(positive),
            "uncertainty": "95% percentile bootstrap over color-swapped pairs, paired model-vs-random difference",
            "bootstrap_seed": bootstrap_seed, "resamples": resamples,
            "interpretation": "positive pilot signal; one training seed" if positive else
                              "pilot does not establish improved playing strength"}


def resource_measurements(path):
    raw = Path(path).read_text()
    peak = re.search(r"^\s*(\d+)\s+maximum resident set size", raw, re.MULTILINE)
    times = re.search(r"([\d.]+)\s+real\s+([\d.]+)\s+user\s+([\d.]+)\s+sys", raw)
    if not peak or not times:
        raise ValueError("Expected macOS /usr/bin/time -l resource log")
    return {"peak_process_rss_bytes": int(peak.group(1)),
            "wall_seconds": float(times.group(1)), "user_seconds": float(times.group(2)),
            "system_seconds": float(times.group(3)), "measurement": "macOS /usr/bin/time -l"}


def state_digest(state):
    digest = hashlib.sha256()
    for name, tensor in sorted(state.items()):
        values = tensor.detach().cpu().contiguous().numpy()
        digest.update(name.encode())
        digest.update(str(values.dtype).encode())
        digest.update(str(values.shape).encode())
        digest.update(values.tobytes())
    return digest.hexdigest()


def plot_report(rows, epochs, holdout, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    figure, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    promoted = any(row["accepted"] == "True" for row in rows)
    subtitle = "" if promoted else "\nNo candidates promoted; selected final model equals initialization"
    figure.suptitle("AlphaZero Hive: CPU pilot, one training seed" + subtitle, fontsize=14)
    iterations = np.asarray([int(row["iteration"]) for row in rows])
    epoch_positions = [int(row["iteration"]) - 1 + int(row["epoch"]) / 3 for row in epochs]
    for axis, field, title, color in ((axes[0, 0], "policy_loss", "Policy loss (candidate training)", "#2456a6"),
                                     (axes[0, 1], "value_loss", "Value loss (candidate training)", "#986432")):
        axis.plot(epoch_positions, [float(row[field]) for row in epochs], marker=".", color=color)
        axis.set(title=title, xlabel="Training iteration", ylabel="Loss", xticks=iterations)
        axis.grid(alpha=0.2)
    axis = axes[1, 0]
    axis.plot(iterations, [100 * float(row["random_win_rate"]) for row in rows],
              "o--", color="#999999", label="Promotion-selected model: monitoring (20 games)")
    points = ((0, holdout["initial_vs_random"]), (iterations[-1], holdout["trained_vs_random"]))
    for index, (x, result) in enumerate(points):
        value = result["estimate"] * 100
        low, high = np.asarray(result["ci95"]) * 100
        axis.errorbar(x, value, yerr=[[value - low], [high - value]], marker="s", capsize=5,
                      color="#2456a6", label="Held out (100 games, paired 95% CI)" if index == 0 else None)
    axis.axhline(50, color="#cccccc", linewidth=1)
    axis.set(title="Win rate against random", xlabel="Training iteration", ylabel="Win rate (%)",
             ylim=(0, 100), xticks=np.arange(0, iterations[-1] + 1))
    axis.legend(fontsize=7, loc="best")
    axis.grid(alpha=0.2)
    axis = axes[1, 1]
    bottom = np.zeros(len(rows))
    for field, label, color in (("self_play_seconds", "Self-play", "#2456a6"),
                                ("training_seconds", "CNN training", "#54a693"),
                                ("arena_seconds", "Promotion + monitoring", "#ba8958")):
        values = np.asarray([float(row[field]) / 60 for row in rows])
        axis.bar(iterations, values, bottom=bottom, label=label, color=color)
        bottom += values
    axis.set(title="Measured time per iteration", xlabel="Training iteration", ylabel="Minutes", xticks=iterations)
    axis.legend(fontsize=8)
    axis.grid(axis="y", alpha=0.2)
    figure.savefig(output / "pilot.png", dpi=180)
    figure.savefig(output / "pilot.svg")
    svg = output / "pilot.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    plt.close(figure)


def main():
    import torch
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python-tests-passed", type=int, help="Explicitly record an observed test result")
    parser.add_argument("--update", action="store_true", help="Regenerate an existing report directory")
    args = parser.parse_args()
    manifest = json.loads((args.run / "manifest.json").read_text())
    evaluation = json.loads(args.evaluation.read_text())
    probe = json.loads(args.probe.read_text())
    protocol_path = Path(__file__).resolve().parents[1] / "configs/evaluations/cpu-pilot.json"
    protocol = json.loads(protocol_path.read_text())
    if evaluation["seed"] != protocol["seed"] or evaluation["games_per_pair"] != protocol["games_per_pair"]:
        raise ValueError("Holdout seed/sample size differ from fixed protocol")
    if evaluation["config"] != manifest["config"]:
        raise ValueError("Evaluation and training configs do not match")
    with (args.run / "metrics.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    with (args.run / "epochs.csv").open() as stream:
        epochs = list(csv.DictReader(stream))
    holdout = summarize_holdout(evaluation)
    resources = resource_measurements(args.run.with_suffix(".resources.log"))
    fingerprints = {}
    for label, filename in (("initial", "initial.pt"), ("selected_final", "best.pt")):
        payload = torch.load(args.run / "checkpoints" / filename, map_location="cpu", weights_only=True)
        fingerprints[label] = state_digest(payload["model"])
    args.output.mkdir(parents=True, exist_ok=args.update)
    summary = {"purpose": "One-seed compact-model pilot, not paper reproduction", "manifest": manifest,
               "fixed_evaluation_protocol": protocol, "holdout": holdout, "training_resources": resources,
               "resource_probe": probe, "checkpoints": evaluation["checkpoints"],
               "network_state_sha256": fingerprints,
               "selected_model_changed": fingerprints["initial"] != fingerprints["selected_final"],
               "accepted_iterations": [int(row["iteration"]) for row in rows if row["accepted"] == "True"],
               "total_self_play_games": len(rows) * manifest["config"]["training"]["self_play_games"],
               "validation": {"local_python_tests_passed": args.python_tests_passed,
                              "training_source_ci": "https://github.com/mariia-osipova/hive/actions/runs/39827943689"},
               "report_environment": {"matplotlib": __import__("matplotlib").__version__},
               "measured_energy": None}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.output / "evaluation.json").write_text(args.evaluation.read_text())
    (args.output / "metrics.csv").write_text((args.run / "metrics.csv").read_text())
    (args.output / "epochs.csv").write_text((args.run / "epochs.csv").read_text())
    plot_report(rows, epochs, holdout, args.output)
    def percent(result):
        low, high = result["ci95"]
        return f"{100 * result['estimate']:.0f}% [{100 * low:.0f}%, {100 * high:.0f}%]"
    lines = ["# CPU pilot — 2026-10-22", "", holdout["interpretation"].capitalize() + ".", "",
             "![Loss, win rate and training time](pilot.png)", "",
             "| Held-out comparison | Wins / losses / draws | Win rate [paired 95% CI] |",
             "|---|---:|---:|"]
    for name, label in (("initial_vs_random", "Initial vs random"), ("trained_vs_random", "Selected final vs random"),
                         ("trained_vs_initial", "Selected final vs initial")):
        result = holdout[name]
        lines.append(f"| {label} | {result['wins']} / {result['losses']} / {result['draws']} | {percent(result)} |")
    delta = holdout["random_win_rate_difference"]
    delta_text = f"{100 * delta['estimate']:+.0f} pp [{100 * delta['ci95'][0]:+.0f}, {100 * delta['ci95'][1]:+.0f}]"
    lines += ["", f"Paired change against random: **{delta_text}**.", "",
              f"Training completed {manifest['completed_iterations']} iterations and {summary['total_self_play_games']} self-play games. "
              f"Accepted iterations: {summary['accepted_iterations']}. "
              f"Measured training-process wall time: {resources['wall_seconds'] / 60:.2f} min; "
              f"peak RSS: {resources['peak_process_rss_bytes'] / 2**30:.2f} GiB.", "",
              f"Selected model state differs from exact initialization: **{summary['selected_model_changed']}**. "
              "Model-state fingerprints include weights and BatchNorm buffers; file hashes alone can differ because checkpoint filenames differ.", "",
              "Both neural agents used 25 MCTS simulations, identical rules and 50 games with each color per opponent. "
              "The initial opponent is the exact saved initial.pt checkpoint. Holdout seed 300001 was fixed before training "
              "and is separate from promotion/monitoring seeds. Intervals resample color-swapped pairs, not individual games.", "",
              ("The paired difference intervals collapse because the selected and initial models are identical and were evaluated "
               "on matching seeded/color pairs. This does not remove uncertainty about future training runs."
               if not summary["selected_model_changed"] else "Intervals describe this one-seed pilot, not variation across training seeds."), "",
              "Loss curves include rejected candidate training. Monitoring and holdout win rates use separate seeds and sample sizes, "
              "as marked in the plot. A lower training loss alone does not establish stronger play.", "",
              "This compact network has 4,246,816 parameters; it is not the paper's 521,174,688-parameter model. "
              "The four-neighbor/29-ply rules are the explicit adaptation documented in ../cpu-pilot-protocol-2026-10-22.md. "
              "Only one training seed was used. Energy was not measured. Full checkpoints/replay remain in the local ignored runs directory.", "",
              "Raw match outcomes and move timings are in evaluation.json; summary.json records resolved configuration, source/version "
              "provenance, resource measurements, checkpoint hashes and the fixed evaluation protocol.", "",
              f"Recorded local Python tests passed: {args.python_tests_passed if args.python_tests_passed is not None else 'not supplied'}. Training-source CI: "
              "https://github.com/mariia-osipova/hive/actions/runs/39827943689. "
              "Report plots used Matplotlib 3.10.7. Local model/replay path: runs/cpu-pilot-2026-10-22/.", ""]
    (args.output / "README.md").write_text("\n".join(lines))
    print(json.dumps({"output": str(args.output), "holdout": holdout, "training_resources": resources}, indent=2))


if __name__ == "__main__":
    main()
