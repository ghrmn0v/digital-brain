import unittest

from connectome.reward import REWARD_MAP, map_feedback


class TestReward(unittest.TestCase):
    def test_positive_feedback_is_reward(self):
        signal = map_feedback("marked_useful")
        self.assertTrue(signal.is_reward)
        self.assertEqual(signal.value, 1.0)

    def test_negative_feedback_is_punishment(self):
        signal = map_feedback("marked_unnecessary")
        self.assertTrue(signal.is_punishment)
        self.assertEqual(signal.value, -1.0)

    def test_ignored_is_neutral(self):
        signal = map_feedback("ignored")
        self.assertEqual(signal.value, 0.0)
        self.assertFalse(signal.is_reward)
        self.assertFalse(signal.is_punishment)

    def test_unknown_feedback_is_neutral(self):
        signal = map_feedback("something_else")
        self.assertEqual(signal.value, 0.0)

    def test_reward_map_covers_all_known_types(self):
        from connectome.event_processor import FEEDBACK_TYPES
        for fb in FEEDBACK_TYPES:
            self.assertIn(fb, REWARD_MAP)


if __name__ == "__main__":
    unittest.main()