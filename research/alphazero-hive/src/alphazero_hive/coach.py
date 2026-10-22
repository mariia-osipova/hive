"""Reuse A0G's self-play episode procedure with Hive's validated search adapter."""
from types import SimpleNamespace

from ._vendor.alpha_zero_general.Coach import Coach
from .search import HiveMCTS


class HiveCoach(Coach):
    def __init__(self, game, network, config):
        # The upstream learn() loop is replaced by the resumable runner; the
        # episode procedure and value-backup convention are inherited unchanged.
        self.game = game
        self.nnet = network
        self.config = config
        self.args = SimpleNamespace(tempThreshold=config["training"]["temperature_threshold"])

    def executeEpisode(self):
        self.mcts = HiveMCTS(self.game, self.nnet, self.config["search"], noise=True)
        return super().executeEpisode()
