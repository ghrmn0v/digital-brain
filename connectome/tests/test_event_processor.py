import unittest

from connectome.event_processor import is_feedback, normalize_event, normalize_feedback


class TestEventProcessor(unittest.TestCase):
    def test_normalize_valid_event(self):
        raw = {
            "event": "important_message",
            "source": "whatsapp",
            "priority": 0.85,
            "person": {"id": "person_123"},
            "context": {"topic": "job", "urgency": "high"},
            "timestamp": 123.4,
        }
        event = normalize_event(raw)
        self.assertEqual(event.name, "important_message")
        self.assertEqual(event.source, "whatsapp")
        self.assertAlmostEqual(event.priority, 0.85)
        self.assertEqual(event.person, {"id": "person_123"})
        self.assertEqual(event.context["topic"], "job")

    def test_priority_clamped_to_unit_interval(self):
        high = normalize_event({"event": "notification", "priority": 5.0})
        low = normalize_event({"event": "notification", "priority": -1.0})
        self.assertEqual(high.priority, 1.0)
        self.assertEqual(low.priority, 0.0)

    def test_malformed_priority_does_not_raise(self):
        event = normalize_event({"event": "x", "priority": "not-a-number"})
        self.assertEqual(event.priority, 0.0)

    def test_unknown_event_and_source_fall_back_safely(self):
        event = normalize_event({"event": "alien_event", "source": "mars"})
        self.assertEqual(event.name, "unknown")
        self.assertEqual(event.source, "unknown")

    def test_missing_fields_get_defaults(self):
        event = normalize_event({})
        self.assertTrue(event.id)
        self.assertEqual(event.name, "unknown")
        self.assertEqual(event.context["urgency"], "unknown")

    def test_feedback_detection(self):
        self.assertTrue(is_feedback({"event": "fly_feedback"}))
        self.assertFalse(is_feedback({"event": "important_message"}))

    def test_normalize_feedback_falls_back(self):
        fb = normalize_feedback({"event": "fly_feedback", "behavior_id": "b1", "feedback": "nonsense"})
        self.assertEqual(fb.feedback, "ignored")
        self.assertEqual(fb.behavior_id, "b1")


if __name__ == "__main__":
    unittest.main()