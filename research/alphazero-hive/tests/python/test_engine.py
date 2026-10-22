import unittest

from alphazero_hive import Game


class NativeEngineTest(unittest.TestCase):
    def test_default_profile_is_base_hive_without_extensions(self):
        game = Game()

        self.assertEqual(game.ruleset_id, "base-hive-paper-profile")
        self.assertEqual(game.remaining("white", "mosquito"), 0)
        self.assertEqual(game.remaining("white", "ladybug"), 0)
        self.assertEqual(game.remaining("white", "pillbug"), 0)
        actions = game.legal_actions()
        self.assertEqual(len(actions), 4)
        self.assertTrue(all(action["kind"] == "place" for action in actions))
        self.assertTrue(all(action["piece"] != "queen" for action in actions))
        self.assertTrue(all(action["ordinal"] == 0 for action in actions))

    def test_clone_apply_and_history_key_are_independent(self):
        game = Game()
        action = game.legal_actions()[0]
        child = game.clone()

        self.assertEqual(child.state_key(), game.state_key())
        self.assertTrue(child.apply_action(action))
        self.assertNotEqual(child.state_key(), game.state_key())
        self.assertEqual(len(game.board), 0)
        self.assertEqual(len(child.board), 1)
        self.assertEqual(game.current_player, "white")
        self.assertEqual(child.current_player, "black")

    def test_rejecting_an_illegal_action_does_not_mutate_state(self):
        game = Game()
        before = game.state_key()

        self.assertFalse(
            game.apply_action({"kind": "place", "piece": "queen", "to": (5, 5)})
        )
        self.assertEqual(game.state_key(), before)
        self.assertEqual(game.status, "ongoing")
        self.assertIsNone(game.terminal_result())

    def test_legacy_profile_is_explicit_and_unchanged_for_gui_compatibility(self):
        game = Game("legacy-expanded")

        self.assertEqual(game.remaining("white", "mosquito"), 1)
        self.assertEqual(len(game.legal_actions()), 8)
        self.assertTrue(any(action["piece"] == "queen" for action in game.legal_actions()))


if __name__ == "__main__":
    unittest.main()
