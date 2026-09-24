import unittest

from connectome.reward import REWARD_MAP
from connectome.training import evaluation as ev


class RewardMathTest(unittest.TestCase):
    def test_feedback_priors_sum_to_one(self):
        for name, spec in ev.SCENARIOS.items():
            with self.subTest(case=name):
                self.assertAlmostEqual(sum(spec["prior"].values()), 1.0, places=6)

    def test_expected_reward_text(self):
        # 0.30*0.8 + 0.25*0.3 + 0.35*0 + 0.10*(-0.5)
        self.assertAlmostEqual(ev.expected_reward("text"), 0.265, places=4)

    def test_penalized_reward_is_negative(self):
        self.assertLess(ev.penalized_reward("audio"), 0)

    def test_engaged_reaction_wins_full_reward(self):
        self.assertEqual(ev.graded_reward("image", "frontflip"), ev.expected_reward("image"))
        self.assertEqual(ev.graded_reward("image", "face_user"), ev.expected_reward("image"))

    def test_no_reaction_loses_reward(self):
        self.assertLess(ev.graded_reward("image", ev.NORMAL), ev.expected_reward("image"))

    def test_priors_use_only_known_feedback(self):
        for name, spec in ev.SCENARIOS.items():
            for fb in spec["prior"]:
                self.assertIn(fb, REWARD_MAP, f"{name}:{fb}")


class BaselineReactionTest(unittest.TestCase):
    def test_state_reaction_covers_all_states(self):
        from connectome.state_machine import states

        for state in states:
            self.assertIn(state, ev.STATE_REACTION, f"missing {state}")

    def test_baseline_reactions_compute_from_real_brain(self):
        reactions = ev.baseline_reactions()
        self.assertEqual(set(reactions.keys()), set(ev.SCENARIOS.keys()))
        for reaction in reactions.values():
            self.assertIn(reaction, set(ev.ENGAGED) | {ev.NORMAL})


class VerdictTest(unittest.TestCase):
    def test_identical_policy_is_candidate(self):
        baseline = {name: "face_user" for name in ev.SCENARIOS}
        result = ev.evaluate(baseline, dict(baseline))
        self.assertTrue(result["safe_to_influence_production"])
        self.assertEqual(result["verdict"], "CANDIDATE_FOR_PRODUCTION")
        self.assertEqual(result["policy_agreement"], 1.0)

    def test_divergent_but_fine_reward_needs_more_data(self):
        baseline = {name: "face_user" for name in ev.SCENARIOS}
        learned = {"text": "face_user", "image": "frontflip", "sticker": "backflip",
                   "video": "frontflip", "audio": "face_user"}
        result = ev.evaluate(baseline, learned)
        self.assertFalse(result["safe_to_influence_production"])
        self.assertEqual(result["verdict"], "COLLECT_MORE_DATA")
        self.assertGreaterEqual(result["mean_reward_delta_vs_baseline"], 0.0)

    def test_degraded_policy_keeps_baseline(self):
        baseline = {name: "face_user" for name in ev.SCENARIOS}
        learned = {name: (ev.NORMAL if name != "text" else "face_user") for name in ev.SCENARIOS}
        result = ev.evaluate(baseline, learned)
        self.assertFalse(result["safe_to_influence_production"])
        self.assertEqual(result["verdict"], "KEEP_BASELINE")
        self.assertLess(result["mean_reward_delta_vs_baseline"], 0.0)


class SnapshotTest(unittest.TestCase):
    def test_load_rl_reactions_from_phase5_snapshot(self):
        reactions = ev.load_rl_reactions(ev.DEFAULT_SNAPSHOT)
        self.assertEqual(set(reactions.keys()), set(ev.SCENARIOS.keys()))
        self.assertTrue(all(reaction in set(ev.ENGAGED) for reaction in reactions.values()))

    def test_missing_snapshot_raises(self):
        with self.assertRaises(FileNotFoundError):
            ev.load_rl_reactions(ev.REPORT_DIR / "does_not_exist.json")


if __name__ == "__main__":
    unittest.main()