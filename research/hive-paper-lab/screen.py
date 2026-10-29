"""Deterministic, engine-checked screening experiments; no model training."""
import argparse
import collections
import hashlib
import importlib
import json
import os
import platform
import random
import sys
import time
import zlib
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
EXACT = ROOT.parent / "az-hive-exact"
KINDS = {1: "ant", 2: "grasshopper", 3: "beetle", 4: "spider", 5: "queen"}
LETTERS = {"ant": "A", "grasshopper": "G", "beetle": "B", "spider": "S", "queen": "Q"}
NEIGHBORS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)]
RESERVES = ["ant", "grasshopper", "beetle", "spider", "queen"]
RESERVE_FIELDS = ["ants_left", "grasshoppers_left", "beetles_left", "spiders_left", "queens_left"]


def stable(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(stable(value).encode()).hexdigest()


def piece(raw, x, y, z):
    color = "black" if raw & 32 else "white"
    kind = KINDS[raw & 31]
    return {"id": color[0] + LETTERS[kind] + str(raw >> 6), "color": color,
            "kind": kind, "x": x, "y": y, "z": z}


def snapshot(board):
    c = board[0].node.contents.board.contents
    stacks = collections.defaultdict(list)
    for item in c.stack:
        if item.location >= 0:
            stacks[int(item.location)].append((int(item.z), int(item.type)))
    pieces = []
    for y, row in enumerate(c.tiles):
        for x, item in enumerate(row):
            if not item.type:
                continue
            hidden = sorted(stacks.get(y * 26 + x, []))
            for z, raw in hidden:
                pieces.append(piece(raw, x, y, z))
            pieces.append(piece(int(item.type), x, y, len(hidden)))
    reserve = {color: {name: int(getattr(c.players[i], field)) for name, field in zip(RESERVES, RESERVE_FIELDS)}
               for i, color in enumerate(["white", "black"])}
    return {"ply": int(c.turn), "to_move": "white" if c.turn % 2 == 0 else "black",
            "reserve": reserve, "pieces": sorted(pieces, key=lambda p: p["id"])}


def queen_counts(state):
    occupied = {(p["x"], p["y"]) for p in state["pieces"]}
    counts = {}
    for color in ["white", "black"]:
        queens = [p for p in state["pieces"] if p["color"] == color and p["kind"] == "queen"]
        counts[color] = None if not queens else sum((queens[0]["x"] + dx, queens[0]["y"] + dy) in occupied
                                                   for dx, dy in NEIGHBORS)
    return counts


def terminal_from_state(state):
    counts = queen_counts(state)
    if state["ply"] == 29:
        if None in counts.values():
            raise ValueError("Missing queen at the native time limit")
        # Match the actual native source: white wins equal surrounding counts.
        return 2 if counts["white"] > counts["black"] else 1
    white_lost = counts["white"] is not None and counts["white"] >= 4
    black_lost = counts["black"] is not None and counts["black"] >= 4
    return 3 if white_lost and black_lost else 2 if white_lost else 1 if black_lost else 0


def rotate(state):
    state = json.loads(stable(state))
    for p in state["pieces"]:
        p["x"], p["y"] = p["y"], p["y"] - p["x"]
    return state


def reflect(state):
    state = json.loads(stable(state))
    for p in state["pieces"]:
        p["x"], p["y"] = p["y"], p["x"]
    return state


def encode_compact(state):
    columns = collections.defaultdict(list)
    for p in state["pieces"]:
        columns[(p["x"], p["y"])].append((p["z"], p["id"]))
    return {"ply": state["ply"], "reserve": [[state["reserve"][c][k] for k in RESERVES] for c in ["white", "black"]],
            "columns": [[x, y, [identifier for z, identifier in sorted(items)]] for (x, y), items in sorted(columns.items())]}


def decode_compact(encoded):
    pieces = []
    by_letter = {value: key for key, value in LETTERS.items()}
    for x, y, column in encoded["columns"]:
        for z, identifier in enumerate(column):
            pieces.append({"id": identifier, "color": "white" if identifier[0] == "w" else "black",
                           "kind": by_letter[identifier[1]], "x": x, "y": y, "z": z})
    return {"ply": encoded["ply"], "to_move": "white" if encoded["ply"] % 2 == 0 else "black",
            "reserve": {c: dict(zip(RESERVES, encoded["reserve"][i])) for i, c in enumerate(["white", "black"])},
            "pieces": sorted(pieces, key=lambda p: p["id"])}


def load_native():
    sys.path.insert(0, str(EXACT / "scripts"))
    from verify_source import verify_worktree, verify_build
    lock = verify_worktree()
    verify_build(lock)
    author = EXACT / "work/author"
    os.chdir(author / "hive-engine")
    sys.path.insert(0, str(author / "hive-engine"))
    import numpy as np
    np.str = str
    return importlib.import_module("hive.HiveGame"), lock


def winning_task(hive, board, state, rng):
    if state["ply"] < 8 or state["ply"] >= 28:
        return None
    current_result = 1 if state["to_move"] == "white" else 2
    candidates = [(child, int(hive.lib.finished_board(child.contents.board))) for child in board[0].children]
    winners = [item for item in candidates if item[1] == current_result]
    others = [item for item in candidates if item[1] != current_result]
    if not winners or len(others) < 3:
        return None
    chosen = [rng.choice(winners), *rng.sample(others, 3)]
    rng.shuffle(chosen)
    options, answer = [], None
    for index, (child, result) in enumerate(chosen):
        next_state = snapshot((SimpleNamespace(node=child), None))
        if terminal_from_state(next_state) != result:
            raise RuntimeError("Candidate native terminal oracle mismatch")
        move = child.contents.move
        origin = int(move.previous_location)
        destination = int(move.location)
        candidate = {"action": int(hive.move_encoding_general(child)), "native_result": result,
                     "move": {"kind": "pass" if destination < 0 else "place" if origin < 0 else "move",
                              "piece_kind": KINDS.get(int(move.tile) & 31),
                              "from": None if origin < 0 else [origin % 26, origin // 26],
                              "to": None if destination < 0 else [destination % 26, destination // 26]}}
        options.append(candidate)
        if result == current_result:
            answer = index
    return {"type": "immediate_win_among_four_legal_candidates", "options": options, "answer_index": answer}


def collect(hive, seeds, games):
    game = hive.HiveGame()
    records, trajectories, synthetic = [], [], []
    for seed in seeds:
        rng = random.Random(seed)
        task_rng = random.Random(seed + 100000)
        for episode in range(games):
            board = game.getInitBoard()
            actions, hashes = [], []
            for _ in range(30):
                state = snapshot(board)
                native = int(board[0].finished())
                expected = terminal_from_state(state)
                if native != expected:
                    raise RuntimeError(f"Independent terminal oracle mismatch: {native} != {expected}")
                hashes.append(digest(state))
                record = {"seed": seed, "episode": episode, "state": state, "native_terminal": native,
                          "queen_neighbors": queen_counts(state), "state_sha256": hashes[-1]}
                records.append(record)
                if native == 0:
                    task = winning_task(hive, board, state, task_rng)
                    if task:
                        record["winning_task"] = task
                if not synthetic and native == 0 and state["ply"] >= 9 and state["ply"] % 2 == 1:
                    c = board[0].node.contents.board.contents
                    before = game.stringRepresentation(board)
                    original_ply = int(c.turn)
                    try:
                        c.turn = 29
                        synthetic.append({"kind": "synthetic_clock_intervention_not_reachability_certified",
                                          "source_state": state, "source_actions": list(actions),
                                          "source_terminal": native, "changed_ply": 29,
                                          "changed_terminal": int(board[0].finished()),
                                          "author_key_collides": before == game.stringRepresentation(board),
                                          "turn_aware_key_collides": (before, original_ply) == (game.stringRepresentation(board), 29)})
                    finally:
                        c.turn = original_ply
                if native:
                    break
                valids = game.getValidMoves(board, 1)
                legal = [i for i, value in enumerate(valids) if value]
                if not legal:
                    raise RuntimeError("No legal move or Pass in ongoing state")
                action = rng.choice(legal)
                board, _ = game.getNextState(board, 1, action)
                actions.append(action)
            else:
                raise RuntimeError("Native trajectory exceeded original horizon")
            trajectories.append({"seed": seed, "episode": episode, "actions": actions, "state_hashes": hashes})
        print(stable({"event": "seed_collected", "seed": seed, "states": len(records)}), flush=True)
    # Replay all legal trajectories against the unmodified API.
    for trajectory in trajectories:
        board = game.getInitBoard()
        if digest(snapshot(board)) != trajectory["state_hashes"][0]:
            raise RuntimeError("Initial replay mismatch")
        for step, action in enumerate(trajectory["actions"]):
            if not game.getValidMoves(board, 1)[action]:
                raise RuntimeError("Illegal replay action")
            board, _ = game.getNextState(board, 1, action)
            if digest(snapshot(board)) != trajectory["state_hashes"][step + 1]:
                raise RuntimeError("Native trajectory replay mismatch")
    return records, trajectories, synthetic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games-per-seed", type=int, default=16)
    parser.add_argument("--output", type=Path, default=ROOT / "results/screen-2026-10-22")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    hive, lock = load_native()
    records, trajectories, synthetic = collect(hive, [20261022, 20261023, 20261024], args.games_per_seed)
    sizes = collections.Counter()
    with (output / "states.jsonl").open("w") as stream:
        for record in records:
            state = record["state"]
            compact = encode_compact(state)
            if decode_compact(compact) != state:
                raise RuntimeError("Compact codec lost logical state information")
            rotated = state
            for _ in range(6):
                rotated = rotate(rotated)
                if queen_counts(rotated) != record["queen_neighbors"] or terminal_from_state(rotated) != record["native_terminal"]:
                    raise RuntimeError("Rotation changed the geometric oracle")
            if rotated != state or reflect(reflect(state)) != state:
                raise RuntimeError("Symmetry inverse failed")
            if queen_counts(reflect(state)) != record["queen_neighbors"]:
                raise RuntimeError("Reflection changed the geometric oracle")
            raw = stable(state).encode()
            encoded = stable(compact).encode()
            compressed = zlib.compress(raw)
            if zlib.decompress(compressed) != raw:
                raise RuntimeError("Byte compressor round-trip failed")
            sizes.update(verbose_bytes=len(raw), compact_bytes=len(encoded), zlib_bytes=len(compressed))
            stream.write(stable(record) + "\n")
    (output / "trajectories.json").write_text(json.dumps(trajectories, indent=2) + "\n")
    (output / "clock-intervention.json").write_text(json.dumps(synthetic, indent=2) + "\n")
    report = {"status": "screen_passed", "author_commit": lock["commit"], "source_files_verified": len(lock["files"]),
              "platform": platform.platform(), "python": sys.version, "seeds": [20261022, 20261023, 20261024],
              "games": len(trajectories), "states": len(records), "all_trajectories_replayed": True,
              "one_ply_tactical_cases": sum("winning_task" in r for r in records),
              "independent_terminal_oracle_matches": len(records), "codec_round_trips": len(records),
              "rotation_checks": 6 * len(records), "reflection_checks": len(records),
              "sizes": dict(sizes), "verbose_to_compact_byte_ratio": sizes["verbose_bytes"] / sizes["compact_bytes"],
              "verbose_to_zlib_byte_ratio": sizes["verbose_bytes"] / sizes["zlib_bytes"],
              "synthetic_clock_key_collision": bool(synthetic and synthetic[0]["author_key_collides"]),
              "elapsed_seconds": time.perf_counter() - start,
              "limits": ["Modified author rules, not standard full Hive", "Byte savings are not token savings or reasoning gains",
                         "Clock intervention is synthetic, not a reachable-history proof", "No trained policy or LLM results in this report"]}
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
