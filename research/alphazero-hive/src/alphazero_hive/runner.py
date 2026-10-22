"""Reproducible self-play, training, promotion and iteration-boundary resume."""
import argparse
import csv
import hashlib
import json
import platform
import random
import subprocess
import sys
import time
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from .coach import HiveCoach
from .evaluation import NetworkAgent, RandomAgent, arena
from .game import HiveGame
from .network import HiveNet
from .encoding import CHANNELS

PROJECT = Path(__file__).resolve().parents[2]
METRIC_FIELDS = ("iteration", "accepted", "examples", "self_play_seconds", "training_seconds",
                 "arena_seconds", "iteration_seconds", "policy_loss", "value_loss",
                 "candidate_wins", "previous_wins", "draws", "random_win_rate")


def seed_everything(seed, threads=1):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(threads)
    torch.use_deterministic_algorithms(True)


def load_config(path):
    path = Path(path).resolve()
    config = json.loads(path.read_text())
    for name in ("rules", "representation"):
        key = name + "_config"
        if key in config:
            config[name] = json.loads((path.parent / config.pop(key)).read_text())
    validate_config(config)
    return config


def validate_config(config):
    required = {"schema_version", "name", "seed", "rules", "representation", "search",
                "network", "training", "runtime", "symmetries"}
    if set(config) != required or config["schema_version"] != 1:
        raise ValueError(f"Expected config fields {sorted(required)}")
    if not isinstance(config["seed"], int) or not 0 <= config["seed"] < 2**32:
        raise ValueError("Seed must be a uint32 integer")
    if not isinstance(config["symmetries"], bool):
        raise ValueError("symmetries must be boolean")
    training = config["training"]
    for field in ("iterations", "self_play_games", "temperature_threshold", "replay_iterations", "max_examples"):
        if not isinstance(training[field], int) or training[field] < 1:
            raise ValueError(f"training.{field} must be a positive integer")
    for field in ("arena_games", "random_games"):
        if training[field] < 2 or training[field] % 2:
            raise ValueError(f"training.{field} must be even and >= 2")
    if not 0 <= training["promotion_threshold"] <= 1 or training["max_seconds"] < 0:
        raise ValueError("Invalid promotion threshold or time budget")
    # Finite experiments use an explicit capped ruleset, never silently truncate.
    options = config["rules"].get("options", {})
    if not 1 <= options.get("max_plies", 0) <= 256:
        raise ValueError("Training requires an explicit rules.options.max_plies in [1,256]")
    if config["runtime"]["threads"] < 1:
        raise ValueError("runtime.threads must be positive")
    network = config["network"]
    for field in ("layers", "channels", "batch_size", "epochs"):
        if not isinstance(network[field], int):
            raise ValueError(f"network.{field} must be an integer")
    if (network["layers"] not in (4, 6, 8) or network["channels"] < 1 or
            len(network["hidden"]) != 2 or min(network["hidden"]) < 1 or
            network["batch_size"] < 2 or network["epochs"] < 1 or
            network["learning_rate"] <= 0 or not 0 <= network["dropout"] < 1):
        raise ValueError("Invalid network hyperparameters")
    from .search import HiveMCTS
    game = make_game(config)
    representation = config["representation"]
    if representation["observation"] not in CHANNELS:
        raise ValueError("Unknown observation representation")
    expected = {"input_shape": [CHANNELS[game.representation], 26, 26],
                "action_size": game.codec.size, "pass_index": game.codec.pass_index}
    for name, value in expected.items():
        if name in representation and representation[name] != value:
            raise ValueError(f"Representation metadata {name} does not match the encoder")
    game.getInitBoard()  # native rules validation
    HiveMCTS(game, None, config["search"])


def make_game(config):
    representation = config["representation"]
    game = HiveGame(config["rules"], representation["observation"],
                    representation["action_encoding"], config["symmetries"])
    game.network_config = config["network"]
    return game


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def command_output(command):
    result = subprocess.run(command, cwd=PROJECT, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def provenance():
    digest = hashlib.sha256()
    for folder in ("src", "engine/team-cpp/src", "engine/team-cpp/include", "bindings/python"):
        for file in sorted((PROJECT / folder).rglob("*")):
            if file.is_file() and file.suffix in (".py", ".cpp", ".h", ".toml"):
                digest.update(str(file.relative_to(PROJECT)).encode())
                # Git can normalize CRLF in the copied C++ snapshot on checkout.
                digest.update(file.read_text().encode())
    upstream = json.loads((PROJECT / "src/alphazero_hive/_vendor/alpha_zero_general/UPSTREAM.json").read_text())
    return {"git_commit": command_output(["git", "rev-parse", "HEAD"]),
            "git_dirty": bool(command_output(["git", "status", "--porcelain", "--", "."])),
            "source_sha256": digest.hexdigest(), "alpha_zero_general_commit": upstream["commit"],
            "python": sys.version, "torch": str(torch.__version__), "numpy": np.__version__,
            "platform": platform.platform(), "machine": platform.machine(),
            "compiler": command_output(["c++", "--version"]),
            "build": "C++17, scikit-build-core Release, SFML disabled",
            "accelerator": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU/MPS host"}


def rng_payload():
    name, keys, position, gaussian, cached = np.random.get_state()
    return {"python": random.getstate(), "torch": torch.get_rng_state(),
            "numpy": [name, keys.tolist(), position, gaussian, cached],
            "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []}


def restore_rng(payload):
    random.setstate(payload["python"])
    torch.set_rng_state(payload["torch"].cpu())
    name, keys, position, gaussian, cached = payload["numpy"]
    np.random.set_state((name, np.asarray(keys, dtype=np.uint32), position, gaussian, cached))
    if payload["cuda"]:
        torch.cuda.set_rng_state_all(payload["cuda"])


def write_metrics(run_dir, rows, epoch_rows):
    for name, data, fields in (("metrics.csv", rows, METRIC_FIELDS),
                                ("epochs.csv", epoch_rows, ("iteration", "epoch", "policy_loss", "value_loss"))):
        destination = run_dir / name
        temporary = destination.with_suffix(".csv.tmp")
        with temporary.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)
        temporary.replace(destination)


def run(config, run_dir, resume=False, stop_after=None):
    validate_config(config)
    run_dir = Path(run_dir)
    seed_everything(config["seed"], config["runtime"]["threads"])
    game = make_game(config)
    network = HiveNet(game)
    previous = HiveNet(game)
    checkpoint_dir = run_dir / "checkpoints"
    if resume:
        manifest = json.loads((run_dir / "manifest.json").read_text())
        if manifest["config"] != config:
            raise ValueError("Resume requires exactly the saved resolved configuration")
        if manifest["provenance"]["source_sha256"] != provenance()["source_sha256"]:
            raise ValueError("Resume requires the same engine and training source files")
        saved = torch.load(checkpoint_dir / "latest.pt", map_location="cpu", weights_only=True)
        if saved["config"] != config:
            raise ValueError("Resume checkpoint/config mismatch")
        network.restore(saved["network"])
        network.save_checkpoint(checkpoint_dir, "best.pt")
        history = [deque(((x.numpy(), p.numpy(), v) for x, p, v in batch),
                         maxlen=config["training"]["max_examples"]) for batch in saved["history"]]
        rows, epoch_rows = saved["metrics"], saved["epochs"]
        completed = saved["iteration"]
        restore_rng(saved["rng"])
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
        checkpoint_dir.mkdir()
        (run_dir / "logs").mkdir()
        manifest = {"format_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
                    "status": "running", "config": deepcopy(config), "provenance": provenance(),
                    "resume_granularity": "completed iteration; interrupted iteration is replayed"}
        atomic_json(run_dir / "manifest.json", manifest)
        network.save_checkpoint(checkpoint_dir, "initial.pt")
        network.save_checkpoint(checkpoint_dir, "best.pt")
        history, rows, epoch_rows, completed = [], [], [], 0
        # A crash in the very first iteration can also resume from an atomic boundary.
        initial = {"format_version": 1, "config": config, "iteration": 0,
                   "network": network.payload(), "rng": rng_payload(), "metrics": [], "epochs": [], "history": []}
        temporary = checkpoint_dir / "latest.pt.tmp"
        torch.save(initial, temporary)
        temporary.replace(checkpoint_dir / "latest.pt")
    # After a crash, metrics are reconstructed from the atomic latest checkpoint.
    write_metrics(run_dir, rows, epoch_rows)
    manifest["status"] = "running"
    manifest.pop("error", None)
    atomic_json(run_dir / "manifest.json", manifest)
    coach = HiveCoach(game, network, config)
    started = time.perf_counter()
    prior_seconds = sum(row["iteration_seconds"] for row in rows)
    try:
        for iteration in range(completed + 1, config["training"]["iterations"] + 1):
            if stop_after is not None and iteration > stop_after:
                break
            max_seconds = config["training"]["max_seconds"]
            if max_seconds and prior_seconds + time.perf_counter() - started >= max_seconds:
                break
            iteration_start = time.perf_counter()
            print(f"iteration {iteration}: self-play", flush=True)
            batch = deque(maxlen=config["training"]["max_examples"])
            for _ in range(config["training"]["self_play_games"]):
                batch.extend(coach.executeEpisode())
            self_play_seconds = time.perf_counter() - iteration_start
            history.append(batch)
            history = history[-config["training"]["replay_iterations"]:]
            examples = [example for batch in history for example in batch]
            previous.restore(deepcopy(network.payload()))
            training_start = time.perf_counter()
            network.train(examples)
            training_seconds = time.perf_counter() - training_start
            epoch_rows.extend({"iteration": iteration, **metrics} for metrics in network.last_metrics)
            # Keep candidate weights even when promotion rejects them.
            network.save_checkpoint(checkpoint_dir, f"candidate-{iteration:04d}.pt")
            arena_start = time.perf_counter()
            evaluation_rng = rng_payload()
            result = arena(game, NetworkAgent(game, network, config["search"]),
                           NetworkAgent(game, previous, config["search"]),
                           config["training"]["arena_games"], config["seed"] + 10000)
            decisive = result["wins"] + result["losses"]
            accepted = decisive > 0 and result["wins"] / decisive >= config["training"]["promotion_threshold"]
            if not accepted:
                network.restore(previous.payload())
            baseline = arena(game, NetworkAgent(game, network, config["search"]), RandomAgent(game),
                             config["training"]["random_games"], config["seed"] + 20000)
            restore_rng(evaluation_rng)
            arena_seconds = time.perf_counter() - arena_start
            atomic_json(run_dir / "logs" / f"arena-{iteration:04d}.json",
                        {"candidate_vs_previous": result, "selected_vs_random": baseline})
            row = {"iteration": iteration, "accepted": accepted, "examples": len(examples),
                   "self_play_seconds": self_play_seconds, "training_seconds": training_seconds,
                   "arena_seconds": arena_seconds, "iteration_seconds": time.perf_counter() - iteration_start,
                   "policy_loss": network.last_metrics[-1]["policy_loss"],
                   "value_loss": network.last_metrics[-1]["value_loss"],
                   "candidate_wins": result["wins"], "previous_wins": result["losses"],
                   "draws": result["draws"], "random_win_rate": baseline["win_rate"]}
            rows.append(row)
            snapshot = {"format_version": 1, "config": config, "iteration": iteration,
                        "network": network.payload(), "rng": rng_payload(), "metrics": rows, "epochs": epoch_rows,
                        "history": [[(torch.from_numpy(x), torch.from_numpy(p), float(v))
                                     for x, p, v in batch] for batch in history]}
            temporary = checkpoint_dir / "latest.pt.tmp"
            torch.save(snapshot, temporary)
            temporary.replace(checkpoint_dir / "latest.pt")
            network.save_checkpoint(checkpoint_dir, "best.pt")
            write_metrics(run_dir, rows, epoch_rows)
            completed = iteration
            print(json.dumps(row), flush=True)
        manifest["status"] = "complete" if completed == config["training"]["iterations"] else "budget_or_stop_limit"
        manifest["completed_iterations"] = completed
        atomic_json(run_dir / "manifest.json", manifest)
    except BaseException as error:
        manifest["status"] = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
        manifest["error"] = f"{type(error).__name__}: {error}"
        atomic_json(run_dir / "manifest.json", manifest)
        raise
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after", type=int, help="Stop after this iteration; config stays unchanged")
    args = parser.parse_args(argv)
    if args.stop_after is not None and args.stop_after < 1:
        parser.error("--stop-after must be positive")
    if args.resume and args.config is None:
        config = json.loads((args.run_dir / "manifest.json").read_text())["config"]
    elif args.config:
        config = load_config(args.config)
    else:
        parser.error("--config is required for a new run")
    run(config, args.run_dir, args.resume, args.stop_after)


if __name__ == "__main__":
    main()
