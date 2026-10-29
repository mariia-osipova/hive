"""Recompute Elo from published aggregate outcomes, not from newly played games."""
import hashlib
import json
import subprocess
import tarfile

from verify_source import ROOT, verify_worktree


def main():
    verify_worktree()
    lock = json.loads((ROOT / "upstream/bayeselo.lock.json").read_text())
    archive = ROOT / "upstream" / lock["archive"]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != lock["sha256"]:
        raise RuntimeError("BayesElo archive hash mismatch")
    work = ROOT / "work/bayeselo"
    work.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as source:
        source.extractall(work, filter="data")
    source_dir = work / "BayesElo"
    subprocess.run(lock["build"], cwd=source_dir, check=True)
    binary = source_dir / "bayeselo"
    pgn = ROOT / "work/author/results/traditional_comparison/tournament.pgn"
    expected = {"mm": 1355, "mcts": 1181, "nn": 1063, "4h": 919, "random": 778, "untrained": 704}
    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    reports = {}
    for name, advantage in [("paper-zero-advantage", "advantage 0"), ("bayeselo-default-advantage", "advantage")]:
        commands = f"readpgn {pgn}\nelo\n{advantage}\nmm\nexactdist\noffset 1000\nratings\nx\nx\n"
        run = subprocess.run([str(binary)], input=commands, text=True, capture_output=True, check=True)
        (results / f"{name}.txt").write_text(run.stdout + "\n" + run.stderr)
        ratings = {}
        for line in run.stdout.splitlines():
            fields = line.split()
            if len(fields) > 2 and fields[0].isdigit() and fields[1] in expected:
                ratings[fields[1]] = int(fields[2])
        if set(ratings) != set(expected):
            raise RuntimeError("Could not parse all six BayesElo ratings")
        reports[name] = {"ratings": ratings, "matches_published_rounded_ratings": ratings == expected,
                         "commands": commands.replace(str(pgn), "AUTHOR/results/traditional_comparison/tournament.pgn")}
    report = {"analysis": "Published aggregate PGN reanalysis; no new games or training",
              "pgn_sha256": hashlib.sha256(pgn.read_bytes()).hexdigest(), "published_figure_6": expected,
              "analyses": reports,
              "finding": "Default first-move advantage 32.8 reproduces Figure 6; explicitly setting 0 as described in the paper gives slightly different ratings. The cause is unresolved."}
    (results / "published-bayeselo.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
