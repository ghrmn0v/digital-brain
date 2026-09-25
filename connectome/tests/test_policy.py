import unittest

from connectome.event_processor import normalize_event
from connectome.loader import load_wiring
from connectome.model import Brain
from connectome.policy import PRIORITY_LEVEL, decide
from connectome.simulate import inject_event, run_brain


class TestPolicy(unittest.TestCase):
    def setUp(self):
        self.brain = Brain(load_wiring())

    def _decision(self, name="important_message", priority=0.85, **kwargs):
        event = normalize_event({"event": name, "source": "whatsapp", "priority": priority})
        inject_event(self.brain, event)
        for _ in range(40):
            self.brain.step()
        return decide(self.brain, event, **kwargs)

    def test_important_message_maps_to_important(self):
        decision = self._decision("important_message", 0.99)
        self.assertEqual(decision["state"], "IMPORTANT")
        self.assertEqual(decision["priority"], PRIORITY_LEVEL["IMPORTANT"])

    def test_natural_state_boost_selects_fitting_state(self):
        decision = self._decision("process_completed", 0.8, flight=False)
        self.assertEqual(decision["state"], "SUCCESS")

    def test_low_priority_unknown_event_falls_back_to_idle(self):
        decision = self._decision("unknown", 0.05)
        self.assertEqual(decision["state"], "IDLE")

    def test_priority_level_mapping_covers_all_states(self):
        from connectome.state_machine import states
        for state in states:
            self.assertIn(state, PRIORITY_LEVEL)

    def test_flight_states_are_scored(self):
        decision = self._decision("notification", 0.8)
        for state in ("TAKEOFF", "FLYING", "LANDING"):
            self.assertIn(state, decision["scores"])
            self.assertGreaterEqual(decision["scores"][state], 0.0)

    def test_flight_becomes_competitive_after_reward_training(self):
        from connectome.reward import map_feedback
        event = normalize_event({"event": "process_completed", "source": "app", "priority": 0.92})
        untrained = self._decision("process_completed", 0.92)["scores"]["FLYING"]
        for _ in range(12):
            inject_event(self.brain, event)
            for _ in range(40):
                self.brain.step()
            self.brain.deliver_reward(map_feedback("reacted_positive").value)
            for _ in range(3):
                self.brain.step()
        trained = self._decision("process_completed", 0.92)["scores"]["FLYING"]
        self.assertGreater(trained, untrained)

    def test_flight_disabled_never_picks_flight_states(self):
        from connectome.policy import FLIGHT_STATES, decide
        event = normalize_event({"event": "notification", "source": "demo", "priority": 0.9})
        inject_event(self.brain, event)
        for _ in range(40):
            self.brain.step()
        decision = decide(self.brain, event, flight=False)
        self.assertNotIn(decision["state"], FLIGHT_STATES)
        self.assertIn("FLYING", decision["scores"])

    def test_fresh_celebration_event_flies_when_flight_on(self):
        from connectome.policy import decide
        event = normalize_event({"event": "process_completed", "source": "app", "priority": 0.9})
        inject_event(self.brain, event)
        for _ in range(40):
            self.brain.step()
        on = decide(self.brain, event, flight=True)
        self.assertEqual(on["state"], "FLYING")
        off = decide(self.brain, event, flight=False)
        self.assertEqual(off["state"], "SUCCESS")

    def test_calm_low_priority_celebration_stays_grounded(self):
        from connectome.policy import FLIGHT_MIN_PRIORITY, decide
        event = normalize_event(
            {"event": "app_open", "source": "app", "priority": FLIGHT_MIN_PRIORITY - 0.1}
        )
        inject_event(self.brain, event)
        for _ in range(40):
            self.brain.step()
        decision = decide(self.brain, event, flight=True)
        self.assertNotEqual(decision["state"], "FLYING")

    def test_serious_event_never_flies(self):
        from connectome.policy import decide
        event = normalize_event({"event": "important_message", "source": "app", "priority": 0.95})
        inject_event(self.brain, event)
        for _ in range(40):
            self.brain.step()
        decision = decide(self.brain, event, flight=True)
        self.assertEqual(decision["state"], "IMPORTANT")


class TestBrainInjection(unittest.TestCase):
    def test_high_priority_drives_more_output_activation(self):
        brain_high = Brain(load_wiring())
        brain_low = Brain(load_wiring())
        for brain, priority in ((brain_high, 1.0), (brain_low, 0.0)):
            event = normalize_event({"event": "important_message", "priority": priority})
            inject_event(brain, event)
            for _ in range(40):
                brain.step()
        self.assertGreater(brain_high.activity["MBON_output"], brain_low.activity["MBON_output"])
        self.assertGreater(brain_high.activity["KC"], brain_low.activity["KC"])


if __name__ == "__main__":
    unittest.main()