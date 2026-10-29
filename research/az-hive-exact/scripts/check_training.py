"""Bounded integration check of the original full CNN, MCTS, optimizer and I/O.

This is deliberately NOT a paper experiment: one self-play episode, its first
64 augmented examples, ten original optimization epochs and two arena games.
No algorithm source, width, batch size, epoch count or MCTS budget is changed.
"""
import argparse
import csv
import hashlib
import importlib
import json
import os
import platform
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from verify_source import ROOT, verify_worktree, verify_build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261029)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    lock = verify_worktree()
    build = verify_build(lock)
    config = "nn_architecture/symmetries/4-layers/1"
    author = ROOT / "work/author"
    source = author / "results" / config
    training = json.loads((source / "training-parameters.json").read_text())
    network = json.loads((source / "nn-parameters.json").read_text())
    os.chdir(author / "hive-engine")
    sys.path.insert(0, str(author / "hive-engine"))
    import numpy as np
    import torch
    np.str = str
    torch.set_num_threads(4)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    hive = importlib.import_module("hive.HiveGame")
    module = importlib.import_module("hive.pytorch.NNet")
    module.args.update(dict(network, cuda=False, results=str(output)))
    from utils import dotdict
    from Coach import Coach
    from MCTS import MCTS
    from Arena import Arena
    game = hive.HiveGame()
    nnet = module.NNetWrapper(game)
    coach = Coach(game, nnet, dotdict(dict(training, results=str(output))))
    report = {
        "status": "running", "scope": "bounded_original_code_integration_check",
        "paper_replication": False, "author_commit": lock["commit"],
        "source_files_verified": len(lock["files"]), "native_build": build,
        "started_utc": datetime.now(timezone.utc).isoformat(), "seed": args.seed,
        "platform": platform.platform(), "python": sys.version, "torch": torch.__version__,
        "numpy": np.__version__, "threads": torch.get_num_threads(), "device": "cpu",
        "published_config": config, "published_training": training, "published_network": network,
        "parameters": sum(p.numel() for p in nnet.nnet.parameters()),
        "algorithm_source_edits": [], "compatibility_shims": {"numpy.str": "builtin str"},
        "deviations": ["one self-play episode instead of 100 per iteration",
                       "train on first 64 augmented examples only",
                       "two trained-versus-random games; no Coach.learn acceptance loop",
                       "macOS arm64 CPU and modern Python/PyTorch/NumPy"],
    }
    start = time.perf_counter()
    def save():
        (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    save()
    try:
        examples = coach.executeEpisode()
        if len(examples) < network["batch_size"]:
            raise RuntimeError("Episode yielded too few examples for a real optimizer step")
        report["self_play_examples"] = len(examples)
        report["self_play_seconds"] = time.perf_counter() - start
        batch = examples[:network["batch_size"]]
        before = nnet.nnet.fc4.weight.detach().clone()
        nnet.train(batch)
        if torch.equal(before, nnet.nnet.fc4.weight.detach()):
            raise RuntimeError("Value-head weights did not change during training")
        losses = np.array(list(csv.reader((output / "stage2.csv").open())), dtype=float)
        if losses.shape != (network["epochs"], 2) or not np.isfinite(losses).all():
            raise RuntimeError("Missing epochs or nonfinite policy/value losses")
        report.update(optimization_epochs=len(losses), optimizer_steps=len(losses),
                      training_examples=len(batch), value_head_weights_changed=True,
                      policy_value_losses=losses.tolist())
        board = game.getInitBoard()
        policy, value = nnet.predict(board[1])
        if (len(policy) != game.getActionSize() or not np.isfinite(policy).all()
                or not np.isfinite(value).all() or abs(float(policy.sum()) - 1) > 1e-5):
            raise RuntimeError("Invalid trained-model inference")
        nnet.save_checkpoint(folder=str(output), filename="integration.pth.tar")
        # Corrupt one parameter in memory so loading must restore actual weights.
        with torch.no_grad():
            nnet.nnet.fc4.weight.add_(1)
        nnet.load_checkpoint(folder=str(output), filename="integration.pth.tar")
        restored_policy, restored_value = nnet.predict(board[1])
        if not np.array_equal(policy, restored_policy) or not np.array_equal(value, restored_value):
            raise RuntimeError("Checkpoint failed to restore trained predictions")
        checkpoint = output / "integration.pth.tar"
        report["checkpoint"] = {"bytes": checkpoint.stat().st_size,
            "sha256": hashlib.file_digest(checkpoint.open("rb"), "sha256").hexdigest(),
            "prediction_round_trip_exact": True, "uploaded": False}
        mcts = MCTS(game, nnet, coach.args)
        probs = mcts.getActionProb(board, temp=0)
        if not game.getValidMoves(board, 1)[int(np.argmax(probs))]:
            raise RuntimeError("Trained MCTS chose an illegal move")
        arena = Arena(coach.random_move_baseline,
                      lambda b: np.argmax(mcts.getActionProb(b, temp=0)), game)
        random_wins, trained_wins, draws = arena.playGames(2)
        if random_wins + trained_wins + draws != 2:
            raise RuntimeError("Arena did not complete both games")
        report["arena"] = dict(games=2, random_wins=random_wins, trained_wins=trained_wins, draws=draws)
        verify_worktree()
        report["status"] = "passed"
    except BaseException as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        report["elapsed_seconds"] = time.perf_counter() - start
        save()
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
