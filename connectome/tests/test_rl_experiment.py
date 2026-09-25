import unittest

from connectome.training.rl import rl_brain
from connectome.training.rl.offline_exp import MESSAGE_CASES, evaluate


class _StubBaselineModel:
    """Pretends the RL policy learned exactly the baseline (best case)."""

    @staticmethod
    def predict_behavior(type_code, text_len, cur_x, cur_y, goal_x, goal_y):
        return rl_brain.baseline_behavior(type_code)


class _StubAlwaysFaceUser:
    """Degenerate policy that always picks face_user (worst case)."""

    @staticmethod
    def predict_behavior(type_code, text_len, cur_x, cur_y, goal_x, goal_y):
        return 3


class _StubRandom:
    def __init__(self, labels):
        self.labels = list(labels)

    def predict_behavior(self, type_code, text_len, cur_x, cur_y, goal_x, goal_y):
        return self.labels.pop(0)


class RlExperimentTest(unittest.TestCase):
    def test_message_cases_cover_whatsapp_types(self):
        names = {name for name, _, _ in MESSAGE_CASES}
        self.assertEqual(names, {"text", "image", "audio", "sticker", "video"})

    def test_baseline_behavior_mapping(self):
        self.assertEqual(rl_brain.baseline_behavior(1.0), 1)
        self.assertEqual(rl_brain.baseline_behavior(3.0), 2)
        self.assertEqual(rl_brain.baseline_behavior(0.0), 3)
        self.assertEqual(rl_brain.baseline_behavior(2.0), 3)

    def test_type_code_mapping(self):
        self.assertEqual(rl_brain.type_code_of("image"), 1.0)
        self.assertEqual(rl_brain.type_code_of("ptt"), 2.0)
        self.assertEqual(rl_brain.type_code_of("sticker"), 3.0)
        self.assertEqual(rl_brain.type_code_of("chat"), 0.0)

    def test_evaluate_perfect_agreement(self):
        metrics = evaluate(_StubBaselineModel())
        self.assertEqual(metrics["policy_agreement"], 1.0)
        self.assertTrue(all(row["agree"] for row in metrics["rows"]))

    def test_evaluate_zero_agreement_when_degenerate(self):
        metrics = evaluate(_StubAlwaysFaceUser())
        # face_user is correct for text/audio but wrong for image/sticker/video
        self.assertEqual(metrics["policy_agreement"], 0.4)
        self.assertEqual(metrics["agreed_cases"], 2)

    def test_evaluate_partial_agreement(self):
        # labels: text->1(x), image->1(v), audio->0(x), sticker->0(x), video->1(v)
        metrics = evaluate(_StubRandom([1, 1, 0, 0, 1]))
        self.assertEqual(metrics["evaluated_cases"], 5)
        self.assertEqual(metrics["agreed_cases"], 2)

    def test_sample_goal_stays_in_bounds(self):
        gx, gy = rl_brain.sample_goal_for_type(1.0, 10, 0.5, 0.5)
        self.assertTrue(0.02 <= gx <= 0.98)
        self.assertTrue(0.02 <= gy <= 0.98)


if __name__ == "__main__":
    unittest.main()