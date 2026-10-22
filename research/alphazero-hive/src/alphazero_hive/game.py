"""AlphaZero General interface with complete native state and explicit viewpoint."""
from dataclasses import dataclass

from . import Game as NativeGame
from ._vendor.alpha_zero_general.Game import Game as GameInterface
from .encoding import ActionCodec, encode_observation, other


@dataclass(frozen=True)
class HiveState:
    native: NativeGame
    perspective: str = "white"


class HiveGame(GameInterface):
    def __init__(self, rules=None, representation="hybrid", action_encoding="relative", symmetries=True):
        self.rules = rules or {"profile": "base"}
        self.representation = representation
        self.codec = ActionCodec(action_encoding)
        self.symmetries = symmetries

    def getInitBoard(self):
        return HiveState(NativeGame(self.rules.get("profile", "base"), self.rules.get("options", {})))

    def getBoardSize(self):
        return 26, 26

    def getActionSize(self):
        return self.codec.size

    @staticmethod
    def _color(board, player):
        if player not in (-1, 1):
            raise ValueError("AlphaZero player must be -1 or 1")
        return board.perspective if player == 1 else other(board.perspective)

    def getNextState(self, board, player, action):
        if self._color(board, player) != board.native.current_player:
            raise ValueError("Player does not match native side to move")
        dto = self.codec.decode(board.native, action)
        child = board.native.clone()
        if not child.apply_action(dto):
            raise RuntimeError("Native engine rejected an encoded legal action")
        return HiveState(child, board.perspective), -player

    def getValidMoves(self, board, player):
        if self._color(board, player) != board.native.current_player:
            raise ValueError("Player does not match native side to move")
        return self.codec.mask(board.native)

    def getGameEnded(self, board, player):
        result = board.native.terminal_result()
        if result is None:
            return 0
        # A0G reserves zero for an unfinished game. Training maps this sentinel to 0.
        if result == 0:
            return 1e-8
        return result if self._color(board, player) == "white" else -result

    def getCanonicalForm(self, board, player):
        return HiveState(board.native, self._color(board, player))

    def observation(self, board, symmetry=0):
        return encode_observation(board.native, self.representation, symmetry, board.perspective)

    def getSymmetries(self, board, pi):
        return [(self.observation(board, symmetry),
                 self.codec.transform_policy(board.native, pi, symmetry))
                for symmetry in range(12 if self.symmetries else 1)]

    def stringRepresentation(self, board):
        return board.perspective + "|" + board.native.state_key()
