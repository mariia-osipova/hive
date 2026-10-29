"""Check original minimax/rollout-MCTS actions on legal mid-game states."""
import argparse
import importlib
import json
import os
import random
import sys
import time
from pathlib import Path

from verify_source import ROOT, verify_worktree, verify_build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    lock = verify_worktree()
    build = verify_build(lock)
    engine = ROOT / "work/author/hive-engine"
    os.chdir(engine)
    sys.path.insert(0, str(engine))
    import numpy as np
    np.str = str
    hive = importlib.import_module("hive.HiveGame")
    game = hive.HiveGame()
    cases = []
    for method in ["minimax", "mcts"]:
        for ply in [8, 9]:
            board = game.getInitBoard()
            rng = random.Random(20261029)
            actions = []
            for _ in range(ply):
                legal = np.flatnonzero(game.getValidMoves(board, 1))
                action = int(rng.choice(legal))
                actions.append(action)
                board, _ = game.getNextState(board, 1, action)
            if game.getGameEnded(board, 1):
                raise RuntimeError("Probe state ended early")
            legal_before = game.getValidMoves(board, 1).copy()
            start = time.perf_counter()
            action = int(getattr(board[0], method)())
            seconds = time.perf_counter() - start
            if not 0 <= action < len(legal_before) or not legal_before[action]:
                raise RuntimeError(f"{method} returned an illegal action")
            next_board, _ = game.getNextState(board, 1, action)
            if next_board[0].node.contents.board.contents.turn != ply + 1:
                raise RuntimeError("Native opponent action failed to advance the board")
            cases.append(dict(method=method, ply=ply, prefix_actions=actions,
                              selected_action=action, legal=True, seconds=seconds))
    report = dict(status="passed", scope="four action checks, not a tournament or strength result",
                  author_commit=lock["commit"], native_build=build, cases=cases)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
