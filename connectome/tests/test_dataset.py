import csv
import json
import tempfile
import unittest
from pathlib import Path

from connectome.event_processor import KNOWN_EVENTS, KNOWN_SOURCES
from connectome.policy import PRIORITY_LEVEL
from connectome.store import SqliteStore
from connectome.training import dataset as ds
from connectome.training.dataset import (  # noqa: F401  (CLI import smoke)
    LABEL_NEUTRAL, LABEL_NEGATIVE, LABEL_POSITIVE, LABEL_UNLABELED,
)

POSITIVE = ("reacted_positive", 0.8)
NEGATIVE = ("dismissed", -0.5)
NEUTRAL = ("ignored", 0.0)


def seed(store: SqliteStore) -> None:
    store.record_decision({"event": "notification", "source": "whatsapp", "priority": 0.75,
                           "fetch": "ATTENTION", "priority_level": "LOW",
                           "confidence": 0.5, "activity": {"mbON_a1": 0.1}}, behavior_id="d1")
    store.record_feedback(*POSITIVE, behavior_id="d1")
    store.record_decision({"event": "user_message", "source": "whatsapp", "priority": 0.4,
                           "fetch": "LISTENING", "priority_level": "LOW",
                           "confidence": 0.4, "activity": {}}, behavior_id="d2")
    store.record_feedback(*NEGATIVE, behavior_id="d2")
    store.record_decision({"event": "process_failed", "source": "app", "priority": 0.9,
                           "fetch": "ERROR", "priority_level": "CRITICAL",
                           "confidence": 0.9, "activity": {}}, behavior_id="d3")
    store.record_feedback(*NEUTRAL, behavior_id="d3")
    store.record_decision({"event": "app_idle", "source": "app", "priority": 0.1,
                           "fetch": "SLEEPING", "priority_level": "LOW",
                           "confidence": 0.2, "activity": {}}, behavior_id="d4")


class CodeTablesTest(unittest.TestCase):
    def test_event_unknown_is_minus_one(self):
        self.assertEqual(ds.code("not_an_event", ds.EVENT_CODES), ds.UNKNOWN)

    def test_code_tables_cover_known_members(self):
        self.assertEqual(set(ds.EVENT_CODES), set(KNOWN_EVENTS))
        self.assertEqual(set(ds.SOURCE_CODES), set(KNOWN_SOURCES))

    def test_priority_level_codes_cover_map(self):
        for level in set(ds.PRIORITY_LEVEL.values()):
            self.assertGreaterEqual(ds.code(level, ds.PRIORITY_LEVEL_CODES), 0)


class LabelTest(unittest.TestCase):
    def test_label_from_reward(self):
        self.assertEqual(ds.label_for(0.8), LABEL_POSITIVE)
        self.assertEqual(ds.label_for(-0.5), LABEL_NEGATIVE)
        self.assertEqual(ds.label_for(0.0), LABEL_NEUTRAL)
        self.assertEqual(ds.label_for(None), LABEL_UNLABELED)


class BuildDatasetTest(unittest.TestCase):
    def setUp(self):
        self.store = SqliteStore(":memory:")
        seed(self.store)

    def tearDown(self):
        self.store.close()

    def test_stats_and_linkage(self):
        dataset = ds.build_dataset(self.store)
        stats = dataset["stats"]
        self.assertEqual(stats["decisions"], 4)
        self.assertEqual(stats["labeled"], 3)
        self.assertEqual(stats["unlabeled"], 1)
        self.assertEqual(stats["positive"], 1)
        self.assertEqual(stats["negative"], 1)
        self.assertEqual(stats["neutral"], 1)

    def test_records_join_feedback_by_behavior_id(self):
        records = {r["behavior_id"]: r for r in ds.build_dataset(self.store)["records"]}
        self.assertEqual(records["d1"]["feedback"], "reacted_positive")
        self.assertEqual(records["d1"]["reward_value"], 0.8)
        self.assertEqual(records["d4"]["label"], LABEL_UNLABELED)
        self.assertIsNone(records["d4"]["reward_value"])

    def test_features_encoded(self):
        row = next(r for r in ds.build_dataset(self.store)["records"] if r["behavior_id"] == "d3")
        self.assertEqual(row["event"], "process_failed")
        self.assertGreaterEqual(row["event_code"], 0)
        self.assertEqual(row["source_code"], ds.SOURCE_CODES["app"])
        self.assertEqual(row["priority_level_code"], ds.PRIORITY_LEVEL_CODES["CRITICAL"])
        self.assertEqual(row["state_code"], ds.STATE_CODES["ERROR"])

    def test_oriented_latest_feedback_wins(self):
        self.store.record_feedback("marked_useful", 1.0, behavior_id="d3")
        row = next(r for r in ds.build_dataset(self.store)["records"] if r["behavior_id"] == "d3")
        self.assertEqual(row["feedback"], "marked_useful")
        self.assertEqual(row["reward_value"], 1.0)
        self.assertEqual(row["label"], LABEL_POSITIVE)


class WriteDatasetTest(unittest.TestCase):
    def test_writes_csv_jsonl_and_meta(self):
        store = SqliteStore(":memory:")
        seed(store)
        dataset = ds.build_dataset(store)
        store.close()
        with tempfile.TemporaryDirectory() as tmp:
            paths = ds.write_dataset(dataset, Path(tmp))
            self.assertEqual(len(paths), 3)
            with paths[0].open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 4)
            by_id = {row["behavior_id"]: row for row in rows}
            self.assertEqual(by_id["d1"]["feedback"], "reacted_positive")
            with paths[1].open() as handle:
                jsonl = [json.loads(line) for line in handle if line.strip()]
            by_id = {row["behavior_id"]: row for row in jsonl}
            self.assertEqual(by_id["d2"]["feedback"], "dismissed")
            meta = json.loads(paths[2].read_text())
            self.assertEqual(meta["stats"]["labeled"], 3)


class LegacyPrefixLinkageTest(unittest.TestCase):
    def test_feedback_with_behavior_prefix_now_links_to_stored_decision(self):
        # regression: old Spring sent "behavior_<uuid>" while python stored "<uuid>".
        store = SqliteStore(":memory:")
        store.record_decision({"event": "notification", "source": "whatsapp", "priority": 0.6,
                               "fetch": "ATTENTION", "priority_level": "LOW",
                               "confidence": 0.5, "activity": {}}, behavior_id="evt_wa_1")
        store.record_feedback("reacted_positive", 0.8, behavior_id="evt_wa_1")
        records = ds.build_dataset(store)["records"]
        store.close()
        self.assertEqual(records[0]["label"], LABEL_POSITIVE)
        self.assertEqual(records[0]["reward_value"], 0.8)


if __name__ == "__main__":
    unittest.main()