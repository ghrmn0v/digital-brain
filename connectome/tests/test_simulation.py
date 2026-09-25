import unittest

from connectome.event_processor import normalize_event
from connectome.loader import load_wiring
from connectome.model import Brain
from connectome.reward import map_feedback
from connectome.simulate import run_simulation


class TestLearning(unittest.TestCase):
    def _rewarded_brain(self, event_payload, feedback):
        brain = Brain(load_wiring())
        event = normalize_event(event_payload)
        from connectome.simulate import inject_event
        inject_event(brain, event)
        for _ in range(40):
            brain.step()
        reward = map_feedback(feedback)
        brain.deliver_reward(reward.value)
        for _ in range(3):
            brain.step()
        return brain

    def test_positive_feedback_potentiates_kc_mbon_synapses(self):
        brains = [self._rewarded_brain({"event": "important_message", "priority": 0.9}, "marked_useful") for _ in range(5)]
        weights = [b.synapse_weight("KC", "MBON_gamma") for b in brains]
        for w in weights:
            self.assertGreater(w, brains[0].initial_weights[("KC", "MBON_gamma")])

    def test_negative_feedback_depresses_kc_mbon_synapses(self):
        brain = self._rewarded_brain({"event": "important_message", "priority": 0.9}, "marked_unnecessary")
        self.assertLess(brain.synapse_weight("KC", "MBON_gamma"), brain.initial_weights[("KC", "MBON_gamma")])

    def test_weight_decay_pulls_synapses_back_toward_wiring_prior(self):
        brain = self._rewarded_brain({"event": "important_message", "priority": 0.9}, "marked_useful")
        key = ("KC", "MBON_gamma")
        self.assertGreater(brain.synapse_weight(*key), brain.initial_weights[key])
        for _ in range(4000):
            brain.step()
        self.assertAlmostEqual(brain.synapse_weight(*key), brain.initial_weights[key], places=1)

    def test_end_to_end_simulation_returns_fly_state(self):
        result = run_simulation(
            {"event": "important_message", "source": "whatsapp", "priority": 0.9},
            feedback="marked_useful",
        )
        self.assertIn("fly_state", result)
        self.assertIn("brain_state", result)
        self.assertIn("activity", result)
        self.assertIn("feedback", result)
        self.assertEqual(result["feedback"]["reward_value"], 1.0)
        self.assertTrue(result["feedback"]["synapse_delta"])

    def test_malformed_event_does_not_crash_simulation(self):
        result = run_simulation({"event": "garbage", "priority": "nan"})
        self.assertIn(result["fly_state"], {"IDLE", "BACKGROUND"})


if __name__ == "__main__":
    unittest.main()