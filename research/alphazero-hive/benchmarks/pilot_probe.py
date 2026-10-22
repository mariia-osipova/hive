"""Measure pilot CPU costs and estimate the paper model without allocating it."""
import argparse
import json
import resource
import statistics
import sys
import time
from copy import deepcopy
from pathlib import Path

import numpy as np
import torch

from alphazero_hive.encoding import CHANNELS
from alphazero_hive.network import HiveCNN, HiveNet
from alphazero_hive.runner import load_config, make_game, provenance, seed_everything
from alphazero_hive.search import HiveMCTS


def architecture(config):
    game = make_game(config)
    with torch.device("meta"):
        model = HiveCNN(CHANNELS[game.representation], game.getActionSize(), config["network"])
    parameters = sum(p.numel() for p in model.parameters())
    return {"parameters": parameters, "float32_weights_bytes": parameters * 4,
            "two_models_two_adam_states_and_gradient_bytes": parameters * 28,
            "estimated_parameter_peak_with_runner_deepcopy_bytes": parameters * 40,
            "estimate_excludes": "activations, replay, Python/framework, serialization, allocator overhead",
            "method": "meta-device parameter count; float32 parameter/optimizer accounting, not measured RSS"}


def probe(config, threads):
    config = deepcopy(config)
    config["runtime"]["threads"] = threads
    seed_everything(config["seed"], threads)
    game = make_game(config)
    network = HiveNet(game)
    board = game.getInitBoard()
    network.predict(board)
    timings = []
    for _ in range(12):
        started = time.perf_counter()
        network.predict(board)
        timings.append(time.perf_counter() - started)
    search_times = []
    for _ in range(3):
        search = HiveMCTS(game, network, config["search"])
        started = time.perf_counter()
        search.getActionProb(board, temp=0)
        search_times.append(time.perf_counter() - started)
    policy = game.codec.mask(board.native)
    policy /= policy.sum()
    example = (game.observation(board), policy, 1.0)
    batch = config["network"]["batch_size"]
    original_epochs = network.config["epochs"]
    network.config["epochs"] = 1
    started = time.perf_counter()
    network.train([example] * (2 * batch))
    train_seconds = time.perf_counter() - started
    network.config["epochs"] = original_epochs
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {"threads": threads, "inference_median_seconds": statistics.median(timings),
            "mcts_simulations": config["search"]["simulations"],
            "opening_move_median_seconds": statistics.median(search_times),
            "two_training_batches_seconds": train_seconds, "batch_size": batch,
            "process_peak_rss_bytes": rss if sys.platform == "darwin" else rss * 1024,
            "note": "Opening search and repeated synthetic batch; pilot run measures real positions and replay"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--paper", type=Path, required=True)
    parser.add_argument("--threads", type=int, nargs="+", default=[1, 2, 4])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pilot, paper = load_config(args.pilot), load_config(args.paper)
    report = {"provenance": provenance(), "paper_architecture": architecture(paper),
              "pilot_architecture": architecture(pilot), "measurements": []}
    for threads in args.threads:
        measurement = probe(pilot, threads)
        report["measurements"].append(measurement)
        print(json.dumps(measurement), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
