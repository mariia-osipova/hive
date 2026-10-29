"""Independently replay every saved live move against the verified original engine."""
import argparse
import importlib
import json
import os
import sys
from pathlib import Path

from verify_source import ROOT, verify_worktree, verify_build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", nargs="+", type=Path)
    args = parser.parse_args()
    directories = [path.resolve() for path in args.result]
    lock = verify_worktree()
    verify_build(lock)
    engine = ROOT / "work/author/hive-engine"
    os.chdir(engine)
    sys.path.insert(0, str(engine))
    import numpy as np
    np.str = str
    hive = importlib.import_module("hive.HiveGame")
    game = hive.HiveGame()
    for directory in directories:
        report = json.loads((directory / "summary.json").read_text())
        rows = [json.loads(line) for line in (directory / "moves.jsonl").read_text().splitlines()]
        if report["status"] != "passed" or report["training_performed"]:
            raise RuntimeError("Evidence is not a successful no-training live run")
        if len(report["completed_games"]) != report["planned_games"]:
            raise RuntimeError("Missing games in live evidence")
        checked = 0
        for match in report["completed_games"]:
            moves = [r for r in rows if r["game"] == match["game"]]
            board, player = game.getInitBoard(), 1
            for row in moves:
                if game.getGameEnded(board, player):
                    raise RuntimeError("Move follows a terminal position")
                valids = game.getValidMoves(board, player)
                if row["legal_actions"] != np.flatnonzero(valids).tolist() or not valids[row["action"]]:
                    raise RuntimeError("Saved action/legality does not match native replay")
                if row["ply"] != board[0].node.contents.board.contents.turn:
                    raise RuntimeError("Saved ply does not match native replay")
                board, player = game.getNextState(board, player, row["action"])
                if board[1].tolist() != row["board_after"]:
                    raise RuntimeError("Saved board differs from native replay")
                checked += 1
            if len(moves) != match["moves"] or int(board[0].finished()) != match["native_result"]:
                raise RuntimeError("Saved final result differs from native replay")
        if checked != len(rows) or checked != report["legal_moves_checked"]:
            raise RuntimeError("Unaccounted live move records")
        print(json.dumps(dict(result=directory.name, replayed_games=len(report["completed_games"]),
                              checked_moves=checked, status="passed")))


if __name__ == "__main__":
    main()
