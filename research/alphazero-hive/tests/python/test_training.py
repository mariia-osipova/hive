import json
from copy import deepcopy

import numpy as np
import pytest
import torch

from alphazero_hive import Game
from alphazero_hive.evaluation import (MinimaxAgent, RandomAgent, RolloutMCTSAgent,
                                       arena, benchmark_speed, elo_ratings)
from alphazero_hive.experiments import configurations, integrate_energy
from alphazero_hive.game import HiveGame, HiveState
from alphazero_hive.network import HiveNet
from alphazero_hive.runner import PROJECT, load_config, make_game, run, seed_everything, validate_config
from alphazero_hive.search import HiveMCTS
from alphazero_hive.coach import HiveCoach


@pytest.fixture
def config():
    result = load_config(PROJECT / "configs/experiments/smoke.json")
    result["rules"]["options"]["max_plies"] = 8
    result["training"]["promotion_threshold"] = 0.0
    return result


def test_canonical_transition_matches_absolute_transition_and_keeps_parent():
    game = HiveGame()
    state = game.getInitBoard()
    first = next(iter(game.codec.legal_map(state.native)))
    state, player = game.getNextState(state, 1, first)
    canonical = game.getCanonicalForm(state, player)
    key = game.stringRepresentation(state)
    action = next(iter(game.codec.legal_map(state.native)))
    absolute_child, absolute_next = game.getNextState(state, player, action)
    relative_child, relative_next = game.getNextState(canonical, 1, action)
    assert absolute_child.native.state_key() == relative_child.native.state_key()
    assert absolute_next == 1 and relative_next == -1
    assert game.stringRepresentation(state) == key
    np.testing.assert_array_equal(game.observation(game.getCanonicalForm(absolute_child, absolute_next)),
                                  game.observation(game.getCanonicalForm(relative_child, relative_next)))
    with pytest.raises(ValueError):
        game.getNextState(state, 1, action)


def test_capped_terminal_perspectives_draw_and_invalid_rules():
    for ties in (True, False):
        game = HiveGame({"profile": "base", "options": {"max_plies": 2, "black_wins_ties": ties}})
        state, player = game.getInitBoard(), 1
        for _ in range(2):
            state, player = game.getNextState(state, player, next(iter(game.codec.legal_map(state.native))))
        assert state.native.status == ("black_wins" if ties else "draw")
        assert game.getGameEnded(state, 1) == (-1 if ties else 1e-8)
        assert game.getGameEnded(state, -1) == (1 if ties else 1e-8)
    with pytest.raises(ValueError):
        Game("base", {"unknown": 1})
    with pytest.raises(ValueError):
        Game("base", {"queen_surround_count": 7})


def test_mcts_returns_only_legal_probabilities(config):
    seed_everything(1)
    game = make_game(config)
    network = HiveNet(game)
    state = game.getInitBoard()
    search = HiveMCTS(game, network, config["search"], noise=True)
    policy = search.getActionProb(state)
    assert np.isclose(policy.sum(), 1)
    assert np.all(policy[game.getValidMoves(state, 1) == 0] == 0)
    assert np.isfinite(search.getActionProb(state, temp=0.00001)).all()
    with pytest.raises(ValueError):
        HiveMCTS(game, network, {**config["search"], "simulations": 1})


def test_four_neighbor_variant_ends_before_standard_surround():
    moves = [("ant", (0, 0)), ("ant", (1, 0)),
             ("queen", (-1, 0)), ("queen", (2, 0)),
             ("spider", (-1, 1)), ("spider", (3, 0)),
             ("spider", (-2, 1)), ("ant", (3, 1)),
             ("beetle", (-2, 0))]
    base = Game()
    modified = Game("base", {"queen_surround_count": 4})
    for piece, destination in moves:
        for game in (base, modified):
            assert game.apply_action({"kind": "place", "piece": piece, "to": destination})
    assert base.status == "ongoing"
    assert modified.status == "black_wins"


def test_network_training_updates_weights_and_checkpoint_roundtrips(config, tmp_path):
    seed_everything(17)
    game = make_game(config)
    network = HiveNet(game)
    state = game.getInitBoard()
    before, _ = network.predict(state)
    policy = game.getValidMoves(state, 1)
    policy /= policy.sum()
    network.train([(game.observation(state), policy, 1.0)] * 4)
    after, value = network.predict(state)
    assert not np.array_equal(before, after)
    assert -1 <= value <= 1
    network.save_checkpoint(tmp_path, "weights.pt")
    restored = HiveNet(game)
    restored.load_checkpoint(tmp_path, "weights.pt")
    np.testing.assert_array_equal(after, restored.predict(state)[0])
    mismatch = HiveNet(game, {**config["network"], "dropout": 0.1})
    with pytest.raises(ValueError):
        mismatch.load_checkpoint(tmp_path, "weights.pt")


def test_resume_matches_uninterrupted_cpu_training(config, tmp_path):
    whole, split = tmp_path / "whole", tmp_path / "split"
    run(config, whole)
    run(config, split, stop_after=1)
    assert json.loads((split / "manifest.json").read_text())["completed_iterations"] == 1
    run(config, split, resume=True)
    first = torch.load(whole / "checkpoints/latest.pt", weights_only=True)
    second = torch.load(split / "checkpoints/latest.pt", weights_only=True)
    assert first["iteration"] == second["iteration"] == 2
    for name, tensor in first["network"]["model"].items():
        assert torch.equal(tensor, second["network"]["model"][name]), name
    assert first["rng"]["numpy"] == second["rng"]["numpy"]
    assert torch.equal(first["rng"]["torch"], second["rng"]["torch"])
    assert len(first["history"]) == len(second["history"]) == 2
    assert len((split / "metrics.csv").read_text().splitlines()) == 3
    changed = deepcopy(config)
    changed["seed"] += 1
    with pytest.raises(ValueError):
        run(changed, split, resume=True)
    with pytest.raises(FileExistsError):
        run(config, whole)


def test_resume_restarts_a_failed_first_iteration(config, tmp_path, monkeypatch):
    execute = HiveCoach.executeEpisode
    def fail_episode(self):
        raise RuntimeError("simulated interruption before any iteration completed")
    monkeypatch.setattr(HiveCoach, "executeEpisode", fail_episode)
    destination = tmp_path / "interrupted"
    with pytest.raises(RuntimeError, match="simulated interruption"):
        run(config, destination)
    assert json.loads((destination / "manifest.json").read_text())["status"] == "failed"
    checkpoint = torch.load(destination / "checkpoints/latest.pt", weights_only=True)
    assert checkpoint["iteration"] == 0
    monkeypatch.setattr(HiveCoach, "executeEpisode", execute)
    run(config, destination, resume=True, stop_after=1)
    manifest = json.loads((destination / "manifest.json").read_text())
    assert manifest["completed_iterations"] == 1


@pytest.mark.parametrize("observation", ["hybrid", "binary", "identity"])
@pytest.mark.parametrize("layers", [4, 6, 8])
def test_cnn_accepts_each_multiplane_representation_and_depth(config, observation, layers):
    seed_everything(1)
    config["representation"] = {"observation": observation, "action_encoding": "absolute"}
    config["network"]["layers"] = layers
    game = make_game(config)
    policy, value = HiveNet(game).predict(game.getInitBoard())
    assert policy.shape == (7437,)
    assert np.isclose(policy.sum(), 1)
    assert -1 <= value <= 1


def test_balanced_arena_baselines_and_ratings(config):
    game = make_game(config)
    random = RandomAgent(game)
    result = arena(game, random, MinimaxAgent(game, depth=1), 2, seed=7)
    assert result["wins"] + result["losses"] + result["draws"] == 2
    assert [m["first_color"] for m in result["matches"]] == ["white", "black"]
    assert all(t["seconds"] >= 0 for t in result["move_timings"])
    state = game.getInitBoard()
    action = RolloutMCTSAgent(game, simulations=2)(state)
    assert game.getValidMoves(state, 1)[action]
    ratings = elo_ratings(["winner", "loser"], [{"first": "winner", "second": "loser",
                                                 "result": {"wins": 2, "losses": 0, "draws": 0}}])
    assert ratings["winner"] > ratings["loser"]
    with pytest.raises(ValueError):
        arena(game, random, random, 3)


def test_experiment_matrix_and_measured_energy(config, tmp_path):
    configs = list(configurations(config, "representations", repeats=5))
    assert len(configs) == 50
    assert len({c["name"] for c in configs}) == 50
    for generated in configs:
        validate_config(generated)
    assert len(list(configurations(config, "architectures", repeats=5))) == 30
    power = tmp_path / "power.csv"
    power.write_text("seconds,cpu_watts,gpu_watts\n0,10,20\n10,10,20\n")
    assert integrate_energy(power)["joules"] == 300
    power.write_text("seconds,cpu_watts,gpu_watts\n1,10,20\n0,10,20\n")
    with pytest.raises(ValueError):
        integrate_energy(power)


def test_search_speed_samples_preserve_reproducible_positions(config):
    seed_everything(1)
    game = make_game(config)
    samples = benchmark_speed(game, HiveNet(game), config["search"], [2, 4], positions=2, repeats=1)
    assert len(samples) == 4
    assert samples[0]["position_key_sha256"] == samples[1]["position_key_sha256"]
    assert samples[2]["position_key_sha256"] == samples[3]["position_key_sha256"]
    assert samples[0]["position_key_sha256"] != samples[2]["position_key_sha256"]
    assert all(sample["seconds_per_move"] > 0 for sample in samples)
