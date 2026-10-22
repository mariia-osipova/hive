"""Generate auditable experiment suites; execute only when explicitly selected."""
import argparse
import csv
import json
from copy import deepcopy
from pathlib import Path

import numpy as np

from .runner import atomic_json, load_config, run


def configurations(base, suite, repeats=5):
    variants = []
    if suite == "representations":
        for actions in ("absolute", "relative"):
            for observation in ("original", "symmetric", "simple", "binary", "hybrid"):
                variants.append((f"{actions}-{observation}", {"observation": observation,
                                  "action_encoding": actions}, 4, False))
    elif suite == "architectures":
        for layers in (4, 6, 8):
            for symmetry in (False, True):
                variants.append((f"hybrid-relative-{layers}-symmetry-{symmetry}",
                                 {"observation": "hybrid", "action_encoding": "relative"}, layers, symmetry))
    elif suite == "loss":
        variants.append(("hybrid-relative-loss", {"observation": "hybrid", "action_encoding": "relative"}, 4, False))
    elif suite == "strength":
        for hours in (4, 24):
            variants.append((f"hybrid-relative-{hours}h", {"observation": "hybrid", "action_encoding": "relative"}, 4, True))
    else:
        raise ValueError(f"Unknown suite {suite}")
    for name, representation, layers, symmetry in variants:
        for seed in range(1, repeats + 1):
            config = deepcopy(base)
            config["name"] = f"{name}-seed-{seed}"
            config["seed"], config["symmetries"] = seed, symmetry
            config["representation"] = representation
            config["network"]["layers"] = layers
            if suite == "loss":
                config["training"]["iterations"] = 10
                config["training"]["max_seconds"] = 0
            elif suite == "strength":
                hours = 24 if "24h" in name else 4
                config["training"]["iterations"] = 10000
                config["training"]["max_seconds"] = hours * 3600
            yield config


def integrate_energy(path):
    """CSV columns: seconds,cpu_watts,gpu_watts; integrate sampled device power."""
    with Path(path).open() as stream:
        rows = list(csv.DictReader(stream))
    samples = np.array([[float(row[name]) for name in ("seconds", "cpu_watts", "gpu_watts")]
                        for row in rows])
    if (len(samples) < 2 or not np.all(np.isfinite(samples)) or
            np.any(samples[:, 1:] < 0) or np.any(np.diff(samples[:, 0]) <= 0)):
        raise ValueError("Energy samples need increasing timestamps and finite nonnegative power")
    power = samples[:, 1:].sum(axis=1)
    joules = np.sum((power[1:] + power[:-1]) * np.diff(samples[:, 0]) / 2)
    return {"sampled_seconds": float(samples[-1, 0] - samples[0, 0]), "joules": float(joules),
            "kwh": float(joules / 3_600_000), "method": "trapezoidal integration of sampled CPU+GPU power"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--suite", choices=("representations", "architectures", "loss", "strength"))
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--energy-csv", type=Path)
    args = parser.parse_args(argv)
    if args.energy_csv:
        atomic_json(args.output, integrate_energy(args.energy_csv))
        return
    if not args.base or not args.suite or args.repeats < 1:
        parser.error("--base, --suite and positive --repeats are required")
    args.output.mkdir(parents=True, exist_ok=False)
    configs = list(configurations(load_config(args.base), args.suite, args.repeats))
    for config in configs:
        atomic_json(args.output / (config["name"] + ".json"), config)
    atomic_json(args.output / "suite.json", {
        "suite": args.suite, "runs": len(configs), "repeats": args.repeats,
        "status": "planned", "planned_max_training_seconds": sum(c["training"]["max_seconds"] for c in configs),
        "note": "These are adaptations; see docs/paper-audit.md. No training occurs without --execute."})
    print(json.dumps({"configs": len(configs), "destination": str(args.output)}))
    if args.execute:
        for config in configs:
            run(config, args.output / config["name"])


if __name__ == "__main__":
    main()
