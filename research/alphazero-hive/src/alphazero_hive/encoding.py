"""Base-Hive observations and injective legal-action maps.

Slots follow the author's moving-tile order Q, A1..3, G1..3, S1..2, B1..2.
Opponent reference slots run in reverse order. Relative actions flatten
(reference, direction, moving tile); direction 6 means on top (also the
otherwise impossible self-reference used for the first placement).
"""
from dataclasses import dataclass
from typing import Protocol

import numpy as np

SIZE = 26
DIRECTIONS = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))
SLOTS = {"queen": (0, 1), "ant": (1, 3), "grasshopper": (4, 3),
         "spider": (7, 2), "beetle": (9, 2)}
TYPES = tuple(SLOTS)
CHANNELS = {"original": 1, "symmetric": 1, "simple": 1, "binary": 10,
            "hybrid": 4, "identity": 23}


class Position(Protocol):
    board: list
    current_player: str

    def legal_actions(self) -> list: ...


def other(color):
    return "black" if color == "white" else "white"


def tile_slot(piece):
    try:
        start, count = SLOTS[piece["piece"]]
        ordinal = piece["ordinal"]
    except KeyError as error:
        raise ValueError("Only the eleven base-Hive pieces are supported") from error
    if not isinstance(ordinal, int) or not 0 <= ordinal < count:
        raise ValueError("Piece ordinal outside the base inventory")
    return start + ordinal


def transform_hex(hexagon, symmetry=0):
    if not 0 <= symmetry < 12:
        raise ValueError("Symmetry must be in [0, 12)")
    q, r = hexagon
    if symmetry >= 6:
        q, r = r, q
    for _ in range(symmetry % 6):
        q, r = -r, q + r
    return q, r


def transform_action(action, symmetry):
    result = dict(action)
    for field in ("from", "to"):
        if field in result:
            result[field] = transform_hex(result[field], symmetry)
    return result


def snapshot(position, symmetry=0):
    result = []
    seen = set()
    for cell in position.board:
        q, r = transform_hex((cell["q"], cell["r"]), symmetry)
        for piece in cell["stack"]:
            identity = (piece["color"], tile_slot(piece))
            if identity in seen:
                raise ValueError("Duplicate piece identity in position")
            seen.add(identity)
        result.append({"q": q, "r": r, "stack": cell["stack"]})
    return result


@dataclass(frozen=True)
class Frame:
    """Center the occupied skew-grid bounding box; reserve room for destinations."""
    x_offset: int
    y_offset: int

    @classmethod
    def from_cells(cls, cells):
        xs = [c["q"] + c["r"] for c in cells] or [0]
        ys = [c["r"] for c in cells] or [0]
        if max(xs) - min(xs) > 21 or max(ys) - min(ys) > 21:
            raise ValueError("Position exceeds the connected 22-tile base-Hive board")
        return cls((SIZE - (max(xs) - min(xs) + 1)) // 2 - min(xs),
                   (SIZE - (max(ys) - min(ys) + 1)) // 2 - min(ys))

    def index(self, at):
        q, r = at
        row, col = r + self.y_offset, q + r + self.x_offset
        if not (0 <= row < SIZE and 0 <= col < SIZE):
            raise ValueError("Destination outside observation frame")
        return row, col


def encode_observation(position, representation="hybrid", symmetry=0, perspective=None):
    """Paper-inspired top-view encodings; identity retains all stack levels.

    The native position/history, never this tensor, controls rules and MCTS keys.
    In identity, a piece plane holds its stack level (ground=1), preserving order.
    """
    if representation not in CHANNELS:
        raise ValueError(f"Unknown observation: {representation}")
    perspective = perspective or position.current_player
    cells = snapshot(position, symmetry)
    frame = Frame.from_cells(cells)
    result = np.zeros((CHANNELS[representation], SIZE, SIZE), dtype=np.float32)
    for cell in cells:
        row, col = frame.index((cell["q"], cell["r"]))
        top = cell["stack"][-1]
        enemy = int(top["color"] != perspective)
        kind = top["piece"]
        # Paper codes: own A,G,B,S,Q = 1..5; opponent Q,S,B,G,A = 6..10.
        rank = {"ant": 1, "grasshopper": 2, "beetle": 3, "spider": 4, "queen": 5}
        if representation == "identity":
            for level, piece in enumerate(cell["stack"], 1):
                plane = 11 * int(piece["color"] != perspective) + tile_slot(piece)
                result[plane, row, col] = level
        elif representation == "hybrid":
            plane = enemy if kind == "queen" else enemy + 2
            result[plane, row, col] = 1 if kind == "queen" else rank[kind]
        elif representation == "binary":
            result[enemy * 5 + rank[kind] - 1, row, col] = 1
        elif representation == "symmetric":
            result[0, row, col] = rank[kind] * (-1 if enemy else 1)
        elif representation == "simple":
            result[0, row, col] = (10 if kind == "queen" else 1) * (-1 if enemy else 1)
        else:
            digits = [str(rank[p["piece"]] if p["color"] == perspective else
                          11 - rank[p["piece"]]) for p in cell["stack"]]
            result[0, row, col] = int("".join(digits))
    if representation == "identity":
        result[22].fill(1 if perspective == "white" else -1)
    return result


def action_key(action):
    return tuple(sorted((key, tuple(value) if isinstance(value, (list, tuple)) else value)
                        for key, value in action.items()))


class ActionCodec:
    def __init__(self, encoding="relative"):
        if encoding not in ("relative", "absolute"):
            raise ValueError("Action encoding must be relative or absolute")
        self.encoding = encoding
        self.pass_index = 22 * 7 * 11 if encoding == "relative" else 11 * SIZE * SIZE
        self.size = self.pass_index + 1

    def _encode(self, cells, frame, player, action):
        if action["kind"] == "pass":
            return self.pass_index
        if action["kind"] not in ("place", "move"):
            raise ValueError("Only base-Hive actions are supported")
        by_hex = {(c["q"], c["r"]): c["stack"] for c in cells}
        source = tuple(action["from"]) if "from" in action else None
        moving = by_hex[source][-1] if source is not None else action
        slot = tile_slot(moving)
        if source is not None and moving["color"] != player:
            raise ValueError("Moving an opponent piece")
        destination = tuple(action["to"])
        if self.encoding == "absolute":
            row, col = frame.index(destination)
            return (slot * SIZE + row) * SIZE + col
        if not cells:
            # Self-reference + on-top is impossible for any normal move.
            return (slot * 7 + 6) * 11 + slot
        references = []
        for at, stack in by_hex.items():
            for level, piece in enumerate(stack):
                if at == source and level == len(stack) - 1:
                    continue
                delta = (destination[0] - at[0], destination[1] - at[1])
                if delta != (0, 0) and delta not in DIRECTIONS:
                    continue
                reference = tile_slot(piece) if piece["color"] == player else 21 - tile_slot(piece)
                direction = 6 if delta == (0, 0) else DIRECTIONS.index(delta)
                references.append((reference, direction))
        if not references:
            raise ValueError("Action destination has no stationary reference tile")
        reference, direction = min(references)
        return (reference * 7 + direction) * 11 + slot

    def legal_map(self, position, symmetry=0):
        """Return policy ID -> original native DTO; reject any collisions."""
        cells = snapshot(position, symmetry)
        frame = Frame.from_cells(cells)
        result = {}
        for action in position.legal_actions():
            transformed = transform_action(action, symmetry)
            index = self._encode(cells, frame, position.current_player, transformed)
            if index in result:
                raise ValueError(f"Policy collision at {index}: {result[index]} / {action}")
            if not 0 <= index < self.size:
                raise ValueError("Policy ID out of range")
            result[index] = action
        return result

    def encode(self, position, action):
        key = action_key(action)
        for index, legal in self.legal_map(position).items():
            if action_key(legal) == key:
                return index
        raise ValueError("Cannot encode an illegal action")

    def decode(self, position, index):
        if not isinstance(index, (int, np.integer)):
            raise ValueError("Policy index must be an integer")
        try:
            return dict(self.legal_map(position)[int(index)])
        except KeyError as error:
            raise ValueError(f"Policy index {index} is not legal in this state") from error

    def mask(self, position, symmetry=0):
        mask = np.zeros(self.size, dtype=np.float32)
        mask[list(self.legal_map(position, symmetry))] = 1
        return mask

    def transform_policy(self, position, policy, symmetry):
        policy = np.asarray(policy, dtype=np.float32)
        if policy.shape != (self.size,) or not np.all(np.isfinite(policy)) or np.any(policy < 0):
            raise ValueError("Policy must be a finite nonnegative vector of action_size")
        original = self.legal_map(position)
        if np.any(policy[self.mask(position) == 0] != 0):
            raise ValueError("Symmetry targets must have zero mass on illegal actions")
        rotated = {action_key(a): i for i, a in self.legal_map(position, symmetry).items()}
        result = np.zeros_like(policy)
        for index, action in original.items():
            result[rotated[action_key(action)]] = policy[index]
        return result
