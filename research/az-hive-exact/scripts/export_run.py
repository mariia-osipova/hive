"""Export small, independently checked run evidence; never upload model weights."""
import argparse
import csv
import hashlib
import json
import math
import shutil
from pathlib import Path

from verify_source import ROOT, verify_worktree


def inspect_run(run):
    lock = verify_worktree()
    metadata = json.loads((run / "run.json").read_text())
    config = (ROOT / "work/author/results" / metadata["published_config"]).resolve()
    if not config.is_relative_to((ROOT / "work/author/results").resolve()):
        raise RuntimeError("Run config escapes published results")
    training = json.loads((config / "training-parameters.json").read_text())
    network = json.loads((config / "nn-parameters.json").read_text())
    if metadata["author_commit"] != lock["commit"] or metadata["algorithm_source_edits"]:
        raise RuntimeError("Run has a different source identity")
    if metadata["published_training"] != training or metadata["published_network"] != network:
        raise RuntimeError("Recorded configuration differs from the pinned author configuration")
    effective_training = {k: v for k, v in metadata["effective_training"].items() if k not in {"results", "checkpoint"}}
    effective_network = {k: v for k, v in metadata["effective_network"].items() if k not in {"results", "cuda"}}
    if effective_training != {k: v for k, v in training.items() if k not in {"results", "checkpoint"}}:
        raise RuntimeError("Training budget/hyperparameters were changed")
    if effective_network != {k: v for k, v in network.items() if k not in {"results", "cuda"}}:
        raise RuntimeError("Network/training parameters were changed")
    counts = {}
    for name in ["stage2.csv", "stage3.csv", "random_baseline.csv"]:
        path = run / name
        values = list(csv.reader(path.open())) if path.exists() else []
        if any(not math.isfinite(float(v)) for row in values for v in row):
            raise RuntimeError(f"Nonfinite run evidence: {name}")
        counts[name] = len(values)
    complete = (metadata["status"] == "completed"
                and counts["stage2.csv"] == training["numIters"] * network["epochs"]
                and counts["stage3.csv"] == training["numIters"]
                and counts["random_baseline.csv"] >= 1
                and (run / "final.pth.tar").is_file())
    if metadata["status"] == "completed" and not complete:
        raise RuntimeError("Run claims completion but lacks all epochs, comparisons, or final weights")
    checkpoints = []
    for path in sorted(run.rglob("*.pth.tar")):
        with path.open("rb") as stream:
            sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        checkpoints.append(dict(filename=str(path.relative_to(run)), bytes=path.stat().st_size,
                                sha256=sha256, uploaded=False))
    return dict(status="completed_local_configuration" if complete else "incomplete",
                published_config=metadata["published_config"], original_run_status=metadata["status"],
                completed_training_iterations=counts["stage3.csv"], recorded_optimization_epochs=counts["stage2.csv"],
                full_paper_replication=False, checkpoint_files=checkpoints,
                limitations=["One local configuration cannot reproduce the full multi-run study",
                             "No fresh six-engine tournament or energy measurement in this export",
                             "Checkpoints do not preserve optimizer, RNG or self-play history"],
                metadata=metadata)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    run, output = args.run.resolve(), args.output.resolve()
    if output == run or output.is_relative_to(run) or run.is_relative_to(output):
        raise RuntimeError("Export must be separate from the run directory")
    report = inspect_run(run)
    output.mkdir(parents=True, exist_ok=True)
    for name in ["run.json", "training-parameters.json", "nn-parameters.json", "stage2.csv", "stage3.csv", "random_baseline.csv", "console.log"]:
        if (run / name).is_file():
            shutil.copyfile(run / name, output / name)
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "metadata"}, indent=2))
    if args.require_complete and report["status"] != "completed_local_configuration":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
