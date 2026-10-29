"""Play original AZ-Hive algorithms live, with no training.

All games use the original author's modified rules, not the browser game's rules.
Without --checkpoint neural agents use explicitly untrained seeded weights.
"""
import argparse
import hashlib
import importlib
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from verify_source import ROOT, verify_worktree, verify_build

ALGORITHMS = ["random", "minimax", "mcts", "az-mcts", "policy", "human"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--white", choices=ALGORITHMS, default="human")
    parser.add_argument("--black", choices=ALGORITHMS, default="mcts")
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--simulations", type=int, default=25)
    parser.add_argument("--seed", type=int, default=20261029)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--suite", action="store_true", help="Each automated agent vs random in both colors")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    if args.games < 1 or args.simulations < 2:
        parser.error("--games must be positive; --simulations must be at least 2")
    output = args.output.resolve()
    checkpoint = args.checkpoint.resolve() if args.checkpoint else None
    output.mkdir(parents=True, exist_ok=False)
    lock = verify_worktree()
    build = verify_build(lock)
    author = ROOT / "work/author"
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
    game = hive.HiveGame()
    config = "nn_architecture/symmetries/4-layers/1"
    training = json.loads((author / "results" / config / "training-parameters.json").read_text())
    network = json.loads((author / "results" / config / "nn-parameters.json").read_text())
    matches = ([(a, b) for agent in ALGORITHMS if agent not in {"human", "random"}
                for a, b in [(agent, "random"), ("random", agent)]] if args.suite
               else [(args.white, args.black)] * args.games)
    nnet = None
    if any("az-mcts" in pair or "policy" in pair for pair in matches):
        module = importlib.import_module("hive.pytorch.NNet")
        module.args.update(dict(network, cuda=False, results=str(output)))
        nnet = module.NNetWrapper(game)
        if checkpoint:
            nnet.load_checkpoint(folder=str(checkpoint.parent), filename=checkpoint.name)
    from MCTS import MCTS
    from utils import dotdict
    report = dict(status="running", scope="fresh live games; no training or strength claim",
        author_commit=lock["commit"], native_build=build, seed=args.seed,
        started_utc=datetime.now(timezone.utc).isoformat(),
        rules="author modified Hive: four-neighbor surround and original move limit/tie behavior",
        algorithms=sorted({a for pair in matches for a in pair}),
        neural_weights="user_supplied_checkpoint" if checkpoint else "seeded_untrained",
        checkpoint_sha256=hashlib.file_digest(checkpoint.open("rb"), "sha256").hexdigest() if checkpoint else None,
        network_config=config, simulations=args.simulations, training_performed=False,
        planned_games=len(matches), completed_games=[], legal_moves_checked=0)
    def save():
        (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    save()
    print(json.dumps(dict(event="live_setup", rules=report["rules"],
                         algorithms=report["algorithms"], neural_weights=report["neural_weights"],
                         training_performed=False)), flush=True)
    try:
        for number, (white, black) in enumerate(matches, 1):
            board = game.getInitBoard()
            player = 1
            agents = [white, black]
            searches = [MCTS(game, nnet, dotdict(dict(training, numMCTSSims=args.simulations)))
                        if name == "az-mcts" else None for name in agents]
            moves = []
            while not game.getGameEnded(board, player):
                side = 0 if player == 1 else 1
                algorithm = agents[side]
                canonical = game.getCanonicalForm(board, player)
                legal = game.getValidMoves(canonical, 1)
                choices = np.flatnonzero(legal)
                start = time.perf_counter()
                if algorithm == "random":
                    action = int(np.random.choice(choices))
                elif algorithm in {"minimax", "mcts"}:
                    action = int(getattr(board[0], algorithm)())
                elif algorithm == "az-mcts":
                    action = int(np.argmax(searches[side].getActionProb(canonical, temp=0)))
                elif algorithm == "policy":
                    policy, value = nnet.predict(canonical[1])
                    if not np.isfinite(policy).all() or not np.isfinite(value).all():
                        raise RuntimeError("Nonfinite neural inference")
                    action = int(choices[np.argmax(policy[choices])])
                else:
                    hive.print_board_pretty(board[1])
                    print("Board codes: white A/G/B/S/Q = 1/2/3/4/5; black = 10/9/8/7/6.")
                    print("WHITE" if side == 0 else "BLACK", "to move. Choose an action ID:")
                    for child in board[0].children:
                        move = child.contents.move
                        origin, destination = int(move.previous_location), int(move.location)
                        tile = int(move.tile)
                        kind = {1: "ant", 2: "grasshopper", 3: "beetle", 4: "spider", 5: "queen"}.get(tile & 31, "pass")
                        name = f"{'black' if tile & 32 else 'white'} {kind} {(tile & 255) >> 6}"
                        print(hive.move_encoding_general(child), dict(piece=name,
                            origin=None if origin < 0 else [origin % 26, origin // 26],
                            destination=None if destination < 0 else [destination % 26, destination // 26]))
                    while True:
                        try:
                            action = int(input("Action: "))
                            if action in choices:
                                break
                        except ValueError:
                            pass
                        print("Choose one of the listed legal action IDs.")
                if not 0 <= action < len(legal) or not legal[action]:
                    raise RuntimeError(f"Illegal {algorithm} action {action}; refusing author fallback")
                ply = int(board[0].node.contents.board.contents.turn)
                record = dict(game=number, ply=ply, color="white" if side == 0 else "black",
                              algorithm=algorithm, action=action, seconds=time.perf_counter() - start,
                              legal_actions=[int(v) for v in choices])
                board, player = game.getNextState(board, player, action)
                if int(board[0].node.contents.board.contents.turn) != ply + 1:
                    raise RuntimeError("Move did not advance native board")
                record["board_after"] = board[1].tolist()
                with (output / "moves.jsonl").open("a") as stream:
                    stream.write(json.dumps(record, separators=(",", ":")) + "\n")
                moves.append(action)
                report["legal_moves_checked"] += 1
                if not args.quiet:
                    print(json.dumps({k: v for k, v in record.items() if k not in {"legal_actions", "board_after"}}), flush=True)
                if len(moves) > 29:
                    raise RuntimeError("Game exceeded the original move horizon")
            outcome = int(board[0].finished())
            result = dict(game=number, white=white, black=black, moves=len(moves),
                          native_result=outcome, winner={1: "white", 2: "black", 3: "draw"}[outcome])
            report["completed_games"].append(result)
            save()
            print(json.dumps(result), flush=True)
        verify_worktree()
        report["status"] = "passed"
    except BaseException as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        save()


if __name__ == "__main__":
    main()
