"""Fresh-process inference checks for all published encoding/architecture choices."""
import argparse
import itertools
import json
import subprocess
import sys
from pathlib import Path

from verify_source import ROOT, verify_worktree


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    verify_worktree()
    configs = [f"{enc}/regular/{rep}/1" for enc, rep in itertools.product(
        ["absolute_coord", "tile_relative"],
        ["original", "symmetric", "simple", "spatial_planes", "spatial_planes_4"])]
    configs += [f"nn_architecture/{sym}/{depth}-layers/1" for sym, depth in
                itertools.product(["regular", "symmetries"], [4, 6, 8])]
    reports = []
    for index, config in enumerate(configs):
        child = output / str(index)
        run = subprocess.run([sys.executable, str(ROOT / "scripts/run_original.py"),
                              "--config", config, "--check-only", "--output", str(child)],
                             text=True, capture_output=True, timeout=180)
        (output / f"{index}.log").write_text(run.stdout + run.stderr)
        metadata = json.loads((child / "run.json").read_text()) if (child / "run.json").exists() else {}
        reports.append(dict(config=config, returncode=run.returncode,
                            status=metadata.get("status", "failed_before_metadata"),
                            parameters=metadata.get("parameters"), action_size=metadata.get("action_size"),
                            use_symmetries=metadata.get("use_symmetries")))
        passed = all(r["returncode"] == 0 and r["status"] == "inference_check_passed" for r in reports)
        status = "failed" if not passed else "passed" if len(reports) == len(configs) else "running"
        (output / "summary.json").write_text(json.dumps(dict(status=status,
            scope="inference only; no training or strength claim", configurations=reports,
            tested=len(reports), planned=len(configs), complete=len(reports) == len(configs)), indent=2) + "\n")
        print(json.dumps(reports[-1]), flush=True)
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
