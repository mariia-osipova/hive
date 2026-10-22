"""Safety and exploration adapter around the pinned, unmodified A0G tree search."""
from types import SimpleNamespace

import numpy as np

from ._vendor.alpha_zero_general.MCTS import MCTS


class HiveMCTS(MCTS):
    def __init__(self, game, network, config, noise=False):
        if (not isinstance(config["simulations"], int) or config["simulations"] < 2 or
                not np.isfinite(config["cpuct"]) or config["cpuct"] <= 0):
            raise ValueError("MCTS needs simulations >= 2 and cpuct > 0")
        super().__init__(game, network, SimpleNamespace(
            numMCTSSims=config["simulations"], cpuct=config["cpuct"]))
        self.noise = noise
        self.alpha = config.get("dirichlet_alpha", 0.3)
        self.fraction = config.get("dirichlet_fraction", 0.0)
        if not np.isfinite(self.alpha) or self.alpha <= 0 or not 0 <= self.fraction <= 1:
            raise ValueError("Invalid Dirichlet noise parameters")

    def getActionProb(self, canonicalBoard, temp=1):
        if temp < 0:
            raise ValueError("Temperature must be nonnegative")
        mask = self.game.getValidMoves(canonicalBoard, 1)
        legal = np.flatnonzero(mask)
        if not len(legal):
            raise ValueError("Cannot search a terminal position")
        key = self.game.stringRepresentation(canonicalBoard)
        first = key not in self.Ps
        if first:
            self.search(canonicalBoard)
        prior = self.Ps[key].copy()
        if self.noise and self.fraction:
            self.Ps[key][legal] = ((1 - self.fraction) * prior[legal] + self.fraction *
                                  np.random.dirichlet(np.full(len(legal), self.alpha)))
        try:
            for _ in range(self.args.numMCTSSims - int(first)):
                self.search(canonicalBoard)
        finally:
            self.Ps[key] = prior
        counts = np.array([self.Nsa.get((key, int(a)), 0) for a in legal], dtype=np.float64)
        probabilities = np.zeros(self.game.getActionSize(), dtype=np.float64)
        if temp == 0:
            probabilities[np.random.choice(legal[counts == counts.max()])] = 1
        elif counts.sum() == 0:
            probabilities[legal] = 1 / len(legal)
        else:
            # Stable for very small temperatures and large visit counts.
            weights = np.full_like(counts, -np.inf)
            positive = counts > 0
            weights[positive] = np.log(counts[positive]) / temp
            weights = np.exp(weights - np.max(weights))
            probabilities[legal] = weights / weights.sum()
        return probabilities
