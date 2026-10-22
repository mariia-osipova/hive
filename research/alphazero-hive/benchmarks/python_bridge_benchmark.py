"""Measure Python/native call costs; this is a bridge microbenchmark, not MCTS."""

import argparse
import json
import time

from alphazero_hive import Game


def time_per_call(iterations, operation):
    start = time.perf_counter()
    for index in range(iterations):
        operation(index)
    return (time.perf_counter() - start) * 1e9 / iterations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=10000)
    args = parser.parse_args()

    game = Game()
    plies = 0
    for _ in range(28):
        if game.status != "ongoing":
            break
        available = game.legal_actions()
        if not available:
            break
        game.apply_action(available[0])
        plies += 1

    sink = [0]

    legal_ns = time_per_call(args.iterations, lambda _: sink.__setitem__(
        0, sink[0] + len(game.legal_actions())))

    def clone_apply(index):
        child = game.clone()
        available = child.legal_actions()
        child.apply_action(available[index % len(available)])
        sink[0] += child.turn_number

    clone_apply_ns = time_per_call(args.iterations, clone_apply)
    digest = 14695981039346656037
    for byte in game.state_key().encode("utf-8"):
        digest ^= byte
        digest = (digest * 1099511628211) & ((1 << 64) - 1)
    print(json.dumps({
        "benchmark": "python-pybind-bridge",
        "ruleset": game.ruleset_id,
        "position_plies": plies,
        "state_key_fnv1a64": f"{digest:016x}",
        "iterations": args.iterations,
        "legal_actions_ns": legal_ns,
        "clone_apply_ns": clone_apply_ns,
        "sink": sink[0],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
