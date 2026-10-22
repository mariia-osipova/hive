"""Color-balanced arena, transparent baselines, tournament ratings and move timings."""
import argparse
import hashlib
import json
import math
import time
from itertools import combinations
from pathlib import Path

import numpy as np

from .encoding import DIRECTIONS
from .game import HiveGame
from .search import HiveMCTS


def queen_pressure(native, color):
    occupied = {(c["q"], c["r"]) for c in native.board}
    for cell in native.board:
        if any(p["color"] == color and p["piece"] == "queen" for p in cell["stack"]):
            return sum((cell["q"] + dq, cell["r"] + dr) in occupied for dq, dr in DIRECTIONS)
    return 0


class RandomAgent:
    def __init__(self, game):
        self.game = game

    def __call__(self, board):
        return int(np.random.choice(np.flatnonzero(self.game.getValidMoves(board, 1))))


class NetworkAgent:
    def __init__(self, game, network, search):
        self.game, self.network, self.config = game, network, search
        self.startGame()

    def startGame(self):
        self.search = HiveMCTS(self.game, self.network, self.config)

    def __call__(self, board):
        return int(np.argmax(self.search.getActionProb(board, temp=0)))


class MinimaxAgent:
    """Local depth-limited baseline, not the paper's Beekeeper implementation."""
    def __init__(self, game, depth=2):
        if depth < 1:
            raise ValueError("Minimax depth must be positive")
        self.game, self.depth = game, depth

    def score(self, board, depth, alpha=-float("inf"), beta=float("inf")):
        result = self.game.getGameEnded(board, 1)
        if result:
            return 0 if abs(result) < 1e-7 else 100 * result
        if depth == 0:
            color = board.native.current_player
            enemy = "black" if color == "white" else "white"
            return queen_pressure(board.native, enemy) - queen_pressure(board.native, color)
        best = -float("inf")
        for action in self.game.codec.legal_map(board.native):
            child, player = self.game.getNextState(board, 1, action)
            child = self.game.getCanonicalForm(child, player)
            best = max(best, -self.score(child, depth - 1, -beta, -alpha))
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best

    def __call__(self, board):
        best = -float("inf")
        chosen = None
        for action in self.game.codec.legal_map(board.native):
            child, player = self.game.getNextState(board, 1, action)
            score = -self.score(self.game.getCanonicalForm(child, player), self.depth - 1)
            if score > best:
                best, chosen = score, action
        return chosen


class RolloutMCTSAgent:
    """UCT with random terminal rollouts; shares only the native game rules."""
    def __init__(self, game, simulations=25, exploration=math.sqrt(2)):
        if simulations < 1:
            raise ValueError("Rollout simulations must be positive")
        self.game, self.simulations, self.exploration = game, simulations, exploration

    def __call__(self, board):
        root = {"state": board, "visits": 0, "value": 0.0, "children": {},
                "untried": list(self.game.codec.legal_map(board.native))}
        for _ in range(self.simulations):
            node, path = root, [root]
            while not self.game.getGameEnded(node["state"], 1):
                if node["untried"]:
                    index = np.random.randint(len(node["untried"]))
                    action = node["untried"].pop(index)
                    child, player = self.game.getNextState(node["state"], 1, action)
                    state = self.game.getCanonicalForm(child, player)
                    child = {"state": state, "visits": 0, "value": 0.0, "children": {},
                             "untried": list(self.game.codec.legal_map(state.native))}
                    node["children"][action] = child
                    node = child
                    path.append(node)
                    break
                node = max(node["children"].values(), key=lambda child:
                           -child["value"] / child["visits"] + self.exploration *
                           math.sqrt(math.log(max(1, node["visits"])) / child["visits"]))
                path.append(node)
            state = node["state"]
            while not self.game.getGameEnded(state, 1):
                action = int(np.random.choice(list(self.game.codec.legal_map(state.native))))
                child, player = self.game.getNextState(state, 1, action)
                state = self.game.getCanonicalForm(child, player)
            outcome = state.native.terminal_result()
            for ancestor in path:
                ancestor["visits"] += 1
                ancestor["value"] += outcome * (1 if ancestor["state"].native.current_player == "white" else -1)
        return max(root["children"], key=lambda action: root["children"][action]["visits"])


def arena(game, first, second, games, seed=1):
    if games < 2 or games % 2:
        raise ValueError("Arena games must be a positive even number >= 2")
    outcomes, timings = [], []
    for match in range(games):
        # Common random numbers across a color-swapped pair of games.
        np.random.seed(seed + match // 2)
        for agent in (first, second):
            if hasattr(agent, "startGame"):
                agent.startGame()
        players = (first, second) if match % 2 == 0 else (second, first)
        board, player, plies = game.getInitBoard(), 1, 0
        while not game.getGameEnded(board, player):
            canonical = game.getCanonicalForm(board, player)
            started = time.perf_counter()
            action = players[0 if player == 1 else 1](canonical)
            timings.append({"match": match, "ply": plies, "agent":
                            "first" if players[0 if player == 1 else 1] is first else "second",
                            "seconds": time.perf_counter() - started})
            board, player = game.getNextState(board, player, action)
            plies += 1
        result = board.native.terminal_result() * (1 if match % 2 == 0 else -1)
        outcomes.append({"match": match, "first_color": "white" if match % 2 == 0 else "black",
                         "result": result, "plies": plies})
    wins = sum(m["result"] == 1 for m in outcomes)
    losses = sum(m["result"] == -1 for m in outcomes)
    draws = games - wins - losses
    # Wilson interval for the binary win indicator; draws count as nonwins.
    p, z = wins / games, 1.96
    center = (p + z * z / (2 * games)) / (1 + z * z / games)
    radius = z * math.sqrt(p * (1 - p) / games + z * z / (4 * games * games)) / (1 + z * z / games)
    return {"wins": wins, "losses": losses, "draws": draws, "win_rate": p,
            "win_rate_95ci": [center - radius, center + radius],
            "score_rate": (wins + 0.5 * draws) / games,
            "matches": outcomes, "move_timings": timings}


def elo_ratings(names, pair_results):
    """Regularized logistic fit, draw=half point, mean Elo=1000 (not BayesElo)."""
    strength = np.zeros(len(names))
    index = {name: i for i, name in enumerate(names)}
    for _ in range(2000):
        gradient = -0.01 * strength
        for pair in pair_results:
            i, j = index[pair["first"]], index[pair["second"]]
            result = pair["result"]
            n = result["wins"] + result["losses"] + result["draws"]
            expected = 1 / (1 + np.exp(np.clip(strength[j] - strength[i], -30, 30)))
            difference = result["wins"] + 0.5 * result["draws"] - n * expected
            gradient[i] += difference
            gradient[j] -= difference
        strength += 0.01 * gradient / max(1, len(pair_results))
        strength -= strength.mean()
    return {name: float(1000 + strength[i] * 400 / np.log(10)) for i, name in enumerate(names)}


def benchmark_speed(game, network, search_config, simulations, positions=3, repeats=3, seed=1):
    """Fresh-tree search timing on reproducible positions, including inference."""
    if positions < 1 or repeats < 1 or any(n < 2 for n in simulations):
        raise ValueError("Speed benchmark needs positive samples and simulations >= 2")
    generator = np.random.default_rng(seed)
    state, player = game.getInitBoard(), 1
    sequence, samples = [], []
    for position in range(positions):
        if position:
            for _ in range(6):
                if game.getGameEnded(state, player):
                    state, player, sequence = game.getInitBoard(), 1, []
                action = int(generator.choice(list(game.codec.legal_map(state.native))))
                sequence.append(game.codec.decode(state.native, action))
                state, player = game.getNextState(state, player, action)
        if game.getGameEnded(state, player):
            state, player, sequence = game.getInitBoard(), 1, []
        canonical = game.getCanonicalForm(state, player)
        network.predict(canonical)  # initialize kernels before measuring
        for count in simulations:
            for repeat in range(repeats):
                search = HiveMCTS(game, network, {**search_config, "simulations": count})
                started = time.perf_counter()
                search.getActionProb(canonical, temp=0)
                seconds = time.perf_counter() - started
                samples.append({"position": position, "repeat": repeat, "simulations": count,
                                "seconds_per_move": seconds, "simulations_per_second": count / seconds,
                                "position_key_sha256": hashlib.sha256(state.native.state_key().encode()).hexdigest(),
                                "native_actions_from_start": list(sequence)})
    return samples


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--checkpoint", default="best.pt")
    parser.add_argument("--games", type=int, default=50)
    parser.add_argument("--seed", type=int, default=1001)
    parser.add_argument("--baselines", nargs="+", choices=("random", "minimax", "rollout"), default=["random"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--speed-simulations", nargs="+", type=int)
    parser.add_argument("--speed-positions", type=int, default=3)
    parser.add_argument("--speed-repeats", type=int, default=3)
    parser.add_argument("--speed-only", action="store_true")
    args = parser.parse_args(argv)
    from .network import HiveNet
    from .runner import make_game, provenance, seed_everything
    config = json.loads((args.run / "manifest.json").read_text())["config"]
    seed_everything(args.seed, config["runtime"]["threads"])
    game = make_game(config)
    trained = HiveNet(game)
    trained.load_checkpoint(args.run / "checkpoints", args.checkpoint)
    if args.speed_only and not args.speed_simulations:
        parser.error("--speed-only requires --speed-simulations")
    agents = {}
    if not args.speed_only:
        untrained = HiveNet(game)
        # Compare to the exact initialization of this training run, not a new
        # random network drawn from the evaluation seed.
        untrained.load_checkpoint(args.run / "checkpoints", "initial.pt")
        agents = {"trained": NetworkAgent(game, trained, config["search"]),
                  "initial": NetworkAgent(game, untrained, config["search"])}
    constructors = {"random": lambda: RandomAgent(game), "minimax": lambda: MinimaxAgent(game),
                    "rollout": lambda: RolloutMCTSAgent(game, config["search"]["simulations"])}
    if not args.speed_only:
        agents.update({name: constructors[name]() for name in args.baselines})
    pairs = []
    for first, second in combinations(agents, 2):
        pairs.append({"first": first, "second": second,
                      "result": arena(game, agents[first], agents[second], args.games, args.seed)})
    report = {"seed": args.seed, "games_per_pair": args.games, "config": config,
              "evaluation_provenance": provenance(),
              "checkpoint": args.checkpoint, "pairs": pairs,
              "elo_method": "regularized logistic fit, draws=half-point, centered at 1000; not BayesElo",
              "baseline_provenance": "Local minimax and rollout MCTS; not the paper's Beekeeper agents",
              "elo": elo_ratings(list(agents), pairs)}
    report["checkpoints"] = {
        name: {"filename": filename,
               "sha256": hashlib.sha256((args.run / "checkpoints" / filename).read_bytes()).hexdigest()}
        for name, filename in (("trained", args.checkpoint), ("initial", "initial.pt"))
        if name == "trained" or not args.speed_only}
    if args.speed_simulations:
        report["speed_samples"] = benchmark_speed(game, trained, config["search"], args.speed_simulations,
                                                  args.speed_positions, args.speed_repeats, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(args.output), "elo": report["elo"]}))


if __name__ == "__main__":
    main()
