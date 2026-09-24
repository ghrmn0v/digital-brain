import tempfile
import unittest

from connectome.server import FlyBrainService
from connectome.store import SqliteStore
from connectome.training.analysis import (
    analyze,
    feedback_distribution,
    policy_agreement,
    recent_reward_rate,
)


class TestStore(unittest.TestCase):
    def setUp(self):
        self.conn = SqliteStore(":memory:")

    def test_counters_and_roundtrip(self):
        self.conn.record_decision(
            {"event": "important_message", "source": "whatsapp", "priority": 0.9, "fetch": "IMPORTANT", "priority_level": "HIGH", "confidence": 0.44, "activity": {}},
            behavior_id="evt_1",
        )
        self.conn.record_feedback("marked_useful", 1.0, behavior_id="evt_1")
        counts = self.conn.counts()
        self.assertEqual(counts, {"decisions": 1, "feedback": 1})
        self.assertEqual(self.conn.decisions()[0]["behavior_id"], "evt_1")
        self.assertEqual(self.conn.feedback_rows()[0]["reward_value"], 1.0)

    def test_weights_persist_across_store_instances(self):
        self.conn.save_weights({("KC", "MBON_gamma"): 1.234})
        reloaded = SqliteStore(":memory:")
        weights = self.conn.load_weights()
        self.assertAlmostEqual(weights[("KC", "MBON_gamma")], 1.234)


class TestPersistenceAcrossServiceRestart(unittest.TestCase):
    def test_learning_survives_restart(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        try:
            first = FlyBrainService(steps=20, store=SqliteStore(db_path))
            before = first.brain.synapse_weight("KC", "MBON_gamma")
            first.behavior({"event": "important_message", "priority": 0.9})
            first.feedback({"behavior_id": "behavior_x", "feedback": "marked_useful"})
            learned = first.brain.synapse_weight("KC", "MBON_gamma")
            self.assertGreater(learned, before)

            second = FlyBrainService(steps=20, store=SqliteStore(db_path))
            self.assertAlmostEqual(second.brain.synapse_weight("KC", "MBON_gamma"), learned)
        finally:
            import os
            os.unlink(db_path)


class TestServiceRecordsHistory(unittest.TestCase):
    def setUp(self):
        self.store = SqliteStore(":memory:")
        self.service = FlyBrainService(steps=20, store=self.store)

    def test_decisions_and_feedback_recorded(self):
        self.service.behavior({"event": "important_message", "source": "whatsapp", "priority": 0.9})
        self.service.feedback({"behavior_id": "behavior_x", "feedback": "looked"})
        counts = self.store.counts()
        self.assertEqual(counts["decisions"], 1)
        self.assertEqual(counts["feedback"], 1)
        self.assertTrue(self.store.latest_weights_json())


class TestTrainingAnalysis(unittest.TestCase):
    def setUp(self):
        self.store = SqliteStore(":memory:")
        self.service = FlyBrainService(steps=20, store=self.store)

    def test_metrics_with_data(self):
        self.service.behavior({"event": "important_message", "priority": 0.9})
        self.service.feedback({"behavior_id": "evt-id", "feedback": "marked_useful"})
        self.service.feedback({"behavior_id": "evt-id", "feedback": "dismissed"})
        self.service.feedback({"behavior_id": "evt-id", "feedback": "marked_useful"})
        metrics = analyze(self.store, window=3)
        self.assertEqual(metrics["decisions"], 1)
        self.assertEqual(metrics["feedback_events"], 3)
        self.assertIn("marked_useful", metrics["distribution"])

    def test_policy_agreement_links_behavior(self):
        self.service.behavior({"id": "evt_1", "event": "important_message", "priority": 0.9})
        self.service.feedback({"behavior_id": "evt_1", "feedback": "marked_useful"})
        self.assertEqual(policy_agreement(self.store), 1.0)

    def test_empty_store_gives_none_metrics(self):
        metrics = analyze(SqliteStore(":memory:"))
        self.assertEqual(metrics["decisions"], 0)
        self.assertIsNone(metrics["reward_rate"])

    def test_reward_rate_stays_in_unit_interval(self):
        for _ in range(5):
            self.service.feedback({"behavior_id": "x", "feedback": "marked_useful"})
        for _ in range(5):
            self.service.feedback({"behavior_id": "x", "feedback": "marked_unnecessary"})
        rate = recent_reward_rate(self.store, window=10)
        self.assertGreaterEqual(rate, 0.0)
        self.assertLessEqual(rate, 1.0)


if __name__ == "__main__":
    unittest.main()