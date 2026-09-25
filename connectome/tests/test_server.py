import unittest

from connectome.server import FlyBrainService


class TestServer(unittest.TestCase):
    def setUp(self):
        self.service = FlyBrainService(steps=20)

    def test_health(self):
        health = self.service.health()
        self.assertEqual(health["status"], "ok")
        self.assertGreater(health["neurons"], 0)

    def test_behavior_returns_decision(self):
        result = self.service.behavior(
            {"event": "important_message", "source": "whatsapp", "priority": 0.9}
        )
        self.assertEqual(result["event"], "important_message")
        self.assertIn("fetch", result)
        self.assertEqual(result["fetch"], "IMPORTANT")
        self.assertIn("activity", result)

    def test_malformed_behavior_does_not_crash(self):
        result = self.service.behavior({"priority": "nan"})
        self.assertIn(result["fetch"], {"IDLE", "BACKGROUND"})

    def test_feedback_returns_synapse_delta(self):
        self.service.behavior({"event": "important_message", "priority": 0.9})
        result = self.service.feedback(
            {"behavior_id": "b1", "feedback": "marked_unnecessary"}
        )
        self.assertEqual(result["behavior_id"], "b1")
        self.assertEqual(result["reward_value"], -1.0)
        self.assertTrue(result["synapse_delta"])

    def test_reset_clears_brain_state(self):
        self.service.behavior({"event": "important_message", "priority": 0.9})
        result = self.service.reset()
        self.assertEqual(result["status"], "reset")

    def test_flight_mode_defaults_on(self):
        self.assertTrue(self.service.flight)
        self.assertEqual(self.service.health()["flight_mode"], "on")

    def test_flight_off_excludes_flight_states(self):
        self.service.set_flight({"flight": False})
        result = self.service.behavior(
            {"event": "process_completed", "source": "app", "priority": 0.92}
        )
        self.assertNotIn(result["fetch"], ("TAKEOFF", "FLYING", "LANDING"))
        self.assertEqual(self.service.health()["flight_mode"], "off")


if __name__ == "__main__":
    unittest.main()