"""Recompute published CSV aggregates and cost equations; no new training."""
import ast
import csv
import itertools
import json
import math
import re
from collections import Counter
from statistics import mean, pstdev

from verify_source import ROOT, verify_worktree


def rows(path):
    with path.open() as stream:
        return [[float(v) for v in row] for row in csv.reader(stream)]


def main():
    lock = verify_worktree()
    author = ROOT / "work/author"
    results = author / "results"
    series = {}
    fewer_than_50 = []
    for encoding, representation in itertools.product(
            ["absolute_coord", "tile_relative"],
            ["original", "symmetric", "simple", "spatial_planes", "spatial_planes_4"]):
        name = f"{encoding}/regular/{representation}"
        runs = [rows(results / name / str(i) / "random_baseline.csv") for i in range(1, 6)]
        for run_index, run in enumerate(runs, 1):
            if any(not 0 < w + l <= 50 or w < 0 or l < 0 for _, w, l in run):
                raise RuntimeError(f"Invalid random-baseline game counts: {name}")
            fewer_than_50.extend(dict(config=name, run=run_index, model_iteration=i, wins=w, losses=l)
                                 for i, w, l in run if w + l < 50)
        points = []
        for index in range(max(map(len, runs))):
            rates = [round(run[index][1] / (run[index][1] + run[index][2]), 2)
                     for run in runs if index < len(run)]
            points.append(dict(model_iteration=index + 1, contributing_runs=len(rates),
                               mean_win_rate=round(mean(rates), 2), std=round(pstdev(rates), 2)))
        series[name] = points
    losses = {}
    # Paper section 5.1 says hybrid; author's plotting function defaults to ten planes.
    for representation in ["spatial_planes", "spatial_planes_4"]:
        runs = [rows(results / f"tile_relative/regular/{representation}/{i}/stage2.csv")[:100]
                for i in range(1, 6)]
        if any(len(run) != 100 or any(not math.isfinite(v) for row in run for v in row) for run in runs):
            raise RuntimeError("Insufficient or nonfinite published loss data")
        losses[representation] = [dict(epoch=i + 1, policy_mean=mean(r[i][0] for r in runs),
                                      value_mean=mean(r[i][1] for r in runs)) for i in range(100)]
    text = (results / "traditional_comparison/tournament.pgn").read_text()
    matches = re.findall(r'\[White "([^"]+)"\]\[Black "([^"]+)"\]\[Result "([^"]+)"\]', text)
    games, wins, pairs = Counter(), Counter(), Counter()
    for white, black, outcome in matches:
        if outcome not in {"1-0", "0-1"}:
            raise RuntimeError("Unexpected published PGN result")
        games.update([white, black])
        wins[white if outcome == "1-0" else black] += 1
        pairs[tuple(sorted([white, black]))] += 1
    generator = ast.parse((results / "traditional_comparison/generate_pgn.py").read_text())
    expected = next(ast.literal_eval(node.value) for node in generator.body
                    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "results" for t in node.targets))
    for a, b, w in expected:
        actual = sum((white == a and black == b and outcome == "1-0") or
                     (white == b and black == a and outcome == "0-1") for white, black, outcome in matches)
        if actual != w:
            raise RuntimeError(f"PGN differs from author aggregate: {a}/{b}")
    if len(matches) != 1500 or set(games.values()) != {500} or set(pairs.values()) != {100}:
        raise RuntimeError("Unexpected published tournament size")
    minutes = 100 * 120 * sum(3 * 20 * (5 * e / 100 * m / 25 + 10 + 3 * m / 25)
                             for e, m in itertools.product([50, 100, 200], [25, 50, 100]))
    # Integrals printed in equations (2) and (3), evaluated exactly as written.
    gpu_j = 1e5 * (0.55 / 2 * (5**2 - 1**2) + 0.2 * 4 + 3.0 * 15)
    cpu_j = 1e4 * (0.9 / 2 * (5**2 - 1**2) + 3.3 * 4 + 7.8 * 15)
    report = {
        "status": "reanalysis_completed", "paper_replication": False,
        "scope": "author aggregate data and printed equations only; no new experiments",
        "author_commit": lock["commit"], "figures_4_5": series, "figure_3_candidates": losses,
        "baseline_rows_with_fewer_than_50_decisive_games": fewer_than_50,
        "tournament": {"games": len(matches), "games_per_engine": dict(games), "wins": dict(wins),
                       "all_15_pairs_match_generator": True},
        "cost_equations": {"equation_1_minutes": minutes, "node_years_365_days": minutes / (365 * 24 * 60),
            "gpu_integral_j": gpu_j, "cpu_integral_j": cpu_j,
            "total_integral_j": gpu_j + cpu_j,
            "exploration_mwh_using_paper_rounded_6_6MJ": 100 * 120 * 27 * 6.6e6 / 3.6e9,
            "measurement_status": "arithmetic only; local CPU/GPU energy not measured"},
        "discrepancies": [
            "Some random-baseline rows contain fewer than 50 decisive results; author plot divides wins by wins+losses, excluding unrecorded outcomes.",
            "Paper states 400 games per engine; six engines and 100 games per opponent imply 500, as PGN confirms.",
            "Author results_comparison.txt gives 4h vs MCTS as 27-100; generator and PGN encode 27-73.",
            "Paper section 5.1 specifies hybrid input; plots_policy_value_loss defaults to spatial_planes (10 planes). Both series retained; figure identity unresolved.",
            "Printed integral equations give 6.65 MJ combined, versus rounded 6.6 MJ in prose.",
            "Equation (1) gives 198,360,000 minutes = 377.40 365-day node-years; the paper rounds to about 200 million minutes and reports 381 node-years.",
            "324,000 runs times the paper's rounded 6.6 MJ gives 594 MWh; the paper reports 602.78 MWh. The arithmetic inputs behind that value remain unresolved.",
        ]}
    destination = ROOT / "results/published-data-audit.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in {"figures_4_5", "figure_3_candidates"}}, indent=2))


if __name__ == "__main__":
    main()
