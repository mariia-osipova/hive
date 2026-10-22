from types import SimpleNamespace

import numpy as np
import pytest

from alphazero_hive import Game
from alphazero_hive.encoding import (ActionCodec, CHANNELS, Frame, action_key,
                                      encode_observation, transform_action, transform_hex)


def fixture(cells, actions, player="white"):
    return SimpleNamespace(board=cells, current_player=player, legal_actions=lambda: actions)


def cell(q, r, *pieces):
    return {"q": q, "r": r, "stack": [
        {"color": color, "piece": kind, "ordinal": ordinal} for color, kind, ordinal in pieces]}


@pytest.mark.parametrize("encoding", ["relative", "absolute"])
def test_empty_opening_pass_and_terminal_have_distinct_legal_slots(encoding):
    codec = ActionCodec(encoding)
    game = Game()
    mapping = codec.legal_map(game)
    assert len(mapping) == 4
    assert codec.pass_index not in mapping
    for index, action in mapping.items():
        assert codec.encode(game, codec.decode(game, index)) == index
        assert action_key(codec.decode(game, index)) == action_key(action)
    passing = fixture([], [{"kind": "pass"}])
    assert codec.legal_map(passing) == {codec.pass_index: {"kind": "pass"}}
    for symmetry in range(12):
        assert codec.mask(passing, symmetry).sum() == 1
        np.testing.assert_array_equal(codec.transform_policy(passing, codec.mask(passing), symmetry), codec.mask(passing))
    assert codec.mask(fixture([], [])).sum() == 0
    with pytest.raises(ValueError):
        codec.decode(game, codec.pass_index)
    with pytest.raises(ValueError):
        codec.decode(game, -1)


def test_stack_order_and_hidden_queens_are_retained_in_identity_observation():
    position = fixture([cell(100, -60, ("white", "queen", 0), ("black", "beetle", 0),
                             ("white", "beetle", 1))], [])
    observation = encode_observation(position, "identity")
    row, col = Frame.from_cells(position.board).index((100, -60))
    assert observation[0, row, col] == 1
    assert observation[20, row, col] == 2
    assert observation[10, row, col] == 3
    assert np.all(observation[22] == 1)
    translated = fixture([cell(0, 0, ("white", "queen", 0), ("black", "beetle", 0),
                              ("white", "beetle", 1))], [])
    np.testing.assert_array_equal(observation, encode_observation(translated, "identity"))


@pytest.mark.parametrize("encoding", ["relative", "absolute"])
def test_stacked_beetle_destinations_do_not_alias(encoding):
    actions = [{"kind": "move", "from": (0, 0), "to": at} for at in ((1, 0), (0, 1), (1, -1))]
    position = fixture([cell(0, 0, ("white", "queen", 0), ("white", "beetle", 1)),
                        cell(1, 0, ("black", "queen", 0))], actions)
    codec = ActionCodec(encoding)
    assert len(codec.legal_map(position)) == len(actions)
    for symmetry in range(12):
        assert codec.mask(position, symmetry).sum() == len(actions)
        policy = codec.mask(position) / len(actions)
        assert np.isclose(codec.transform_policy(position, policy, symmetry).sum(), 1)


def test_hex_symmetries_form_twelve_unique_isometries():
    transforms = {tuple(transform_hex(h, s) for h in ((2, 1), (1, 3))) for s in range(12)}
    assert len(transforms) == 12
    for symmetry in range(12):
        q, r = transform_hex((2, -1), symmetry)
        assert (abs(q) + abs(r) + abs(q + r)) // 2 == 2
        assert transform_action({"kind": "pass"}, symmetry) == {"kind": "pass"}


@pytest.mark.parametrize("encoding", ["relative", "absolute"])
def test_native_playouts_have_injective_maps_and_equivariant_targets(encoding):
    random = np.random.default_rng(120)
    codec = ActionCodec(encoding)
    saw_movement = saw_stack = False
    for _ in range(3):
        game = Game("base", {"max_plies": 100})
        for ply in range(100):
            mapping = codec.legal_map(game)
            actions = game.legal_actions()
            assert len(mapping) == len(actions)
            assert codec.mask(game).sum() == len(actions)
            if not actions:
                break
            if ply % 8 == 0:
                weights = random.random(len(mapping))
                weights /= weights.sum()
                policy = np.zeros(codec.size, dtype=np.float32)
                policy[list(mapping)] = weights
                for symmetry in range(12):
                    transformed = codec.transform_policy(game, policy, symmetry)
                    assert np.isclose(transformed.sum(), 1)
                    assert np.all(transformed[codec.mask(game, symmetry) == 0] == 0)
                    for name, channels in CHANNELS.items():
                        observation = encode_observation(game, name, symmetry)
                        assert observation.shape == (channels, 26, 26)
                        assert np.all(np.isfinite(observation))
            action = actions[random.integers(len(actions))]
            saw_movement |= action["kind"] == "move"
            parent_key = game.state_key()
            child = game.clone()
            index = codec.encode(game, action)
            assert codec.decode(game, index) == action
            assert child.apply_action(codec.decode(game, index))
            assert game.state_key() == parent_key
            game = child
            saw_stack |= any(len(c["stack"]) > 1 for c in game.board)
    assert saw_movement
    assert saw_stack


def test_all_symmetries_preserve_native_legal_move_sets():
    random = np.random.default_rng(88)
    base = Game()
    images = [Game() for _ in range(12)]
    for ply in range(70):
        actions = base.legal_actions()
        for symmetry, image in enumerate(images):
            transformed = {action_key(transform_action(a, symmetry)) for a in actions}
            assert transformed == {action_key(a) for a in image.legal_actions()}
        if not actions:
            break
        action = actions[random.integers(len(actions))]
        assert base.apply_action(action)
        for symmetry, image in enumerate(images):
            assert image.apply_action(transform_action(action, symmetry))


def test_invalid_targets_and_expansion_pieces_are_rejected():
    codec = ActionCodec()
    policy = np.ones(codec.size)
    with pytest.raises(ValueError):
        codec.transform_policy(Game(), policy, 1)
    with pytest.raises(ValueError):
        codec.legal_map(Game("legacy"))
