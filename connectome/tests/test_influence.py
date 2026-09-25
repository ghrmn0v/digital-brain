import json
import tempfile
import unittest
from pathlib import Path

from connectome.event_processor import Event
from connectome.influence import (
    CANDIDATE_VERDICT,
    ProductionInfluence,
    resolve_case,
)
from connectome.server import FlyBrainService

SNAPSHOT_ROWS = [
    {"case": "text", "rl_behavior": "frontflip"},
    {"case": "image", "rl_behavior": "normal"},
    {"case": "audio", "rl_behavior": "face_user"},
    {"case": "sticker", "rl_behavior": "backflip"},
    {"case": "video", "rl_behavior": "frontflip"},
]

SNAPSHOT = {"evaluation": {"rows": SNAPSHOT_ROWS}}


def event(name, media_type=None, priority=0.5, source="whatsapp"):
    context = {"urgency": "high" if priority >= 0.7 else "medium"}
    if media_type:
        context["media_type"] = media_type
    return Event(
        id="influence_test",
        name=name,
        source=source,
        priority=priority,
        person=None,
        context=context,
        timestamp=0.0,
    )


class TempArtifacts:
    def __init__(self, verdict=CANDIDATE_VERDICT, snapshot=SNAPSHOT):
        self.dir = tempfile.TemporaryDirectory()
        self.snapshot = Path(self.dir.name) / "snapshot.json"
        self.evaluation = Path(self.dir.name) / "eval.json"
        self.snapshot.write_text(json.dumps(snapshot))
        self.evaluation.write_text(json.dumps({"verdict": verdict}))

    def close(self):
        self.dir.cleanup()

    def influence(self, mode="on"):
        return ProductionInfluence(
            mode=mode, snapshot_path=self.snapshot, evaluation_path=self.evaluation
        )


class TestResolveCase(unittest.TestCase):
    def test_user_message_maps_to_text(self):
        self.assertEqual(resolve_case(event("user_message")), "text")

    def test_notification_uses_media_type(self):
        self.assertEqual(resolve_case(event("notification", media_type="video")), "video")
        self.assertEqual(resolve_case(event("notification", media_type="audio")), "audio")
        self.assertEqual(resolve_case(event("notification", media_type="sticker")), "sticker")

    def test_notification_without_media_type_falls_back_to_image(self):
        self.assertEqual(resolve_case(event("notification")), "image")
        self.assertEqual(resolve_case(event("notification", media_type="weird")), "image")

    def test_uncovered_event_maps_to_none(self):
        self.assertIsNone(resolve_case(event("important_message")))
        self.assertIsNone(resolve_case(event("process_completed")))


class TestProductionInfluence(unittest.TestCase):
    def setUp(self):
        self.artifacts = TempArtifacts()

    def tearDown(self):
        self.artifacts.close()

    def test_off_mode_never_applies_even_with_allowing_verdict(self):
        gate = self.artifacts.influence(mode="off")
        state, status = gate.apply(event("user_message"), "LISTENING")
        self.assertEqual(state, "LISTENING")
        self.assertFalse(status["applied"])
        self.assertEqual(status["mode"], "off")

    def test_on_mode_applies_learned_state(self):
        gate = self.artifacts.influence(mode="on")
        state, status = gate.apply(event("user_message"), "LISTENING")
        self.assertEqual(state, "IMPORTANT")
        self.assertTrue(status["applied"])
        self.assertEqual(status["source"], "rl")
        self.assertEqual(status["case"], "text")
        self.assertEqual(status["reaction"], "frontflip")
        self.assertEqual(status["from_state"], "LISTENING")
        self.assertEqual(status["to_state"], "IMPORTANT")

    def test_auto_mode_requires_candidate_verdict(self):
        gate = self.artifacts.influence(mode="auto")
        state, status = gate.apply(event("user_message"), "LISTENING")
        self.assertEqual(state, "IMPORTANT")
        self.assertTrue(status["applied"])

        self.artifacts.evaluation.write_text(json.dumps({"verdict": "COLLECT_MORE_DATA"}))
        state, status = gate.apply(event("user_message"), "LISTENING")
        self.assertEqual(state, "LISTENING")
        self.assertFalse(status["applied"])

        self.artifacts.evaluation.write_text(json.dumps({"verdict": "KEEP_BASELINE"}))
        state, _ = gate.apply(event("user_message"), "LISTENING")
        self.assertEqual(state, "LISTENING")

    def test_same_state_is_not_reapplied(self):
        gate = self.artifacts.influence(mode="on")
        state, status = gate.apply(event("user_message"), "IMPORTANT")
        self.assertEqual(state, "IMPORTANT")
        self.assertFalse(status["applied"])

    def test_missing_snapshot_falls_back_to_baseline(self):
        gate = ProductionInfluence(
            mode="on",
            snapshot_path=Path(self.artifacts.dir.name) / "missing.json",
            evaluation_path=self.artifacts.evaluation,
        )
        state, status = gate.apply(event("user_message"), "LISTENING")
        self.assertEqual(state, "LISTENING")
        self.assertFalse(status["applied"])

    def test_missing_evaluation_blocks_auto_mode(self):
        gate = ProductionInfluence(
            mode="auto",
            snapshot_path=self.artifacts.snapshot,
            evaluation_path=Path(self.artifacts.dir.name) / "missing.json",
        )
        state, status = gate.apply(event("user_message"), "LISTENING")
        self.assertEqual(state, "LISTENING")
        self.assertIsNone(status["verdict"])

    def test_uncovered_event_is_never_influenced(self):
        gate = self.artifacts.influence(mode="on")
        state, status = gate.apply(event("important_message"), "IMPORTANT")
        self.assertEqual(state, "IMPORTANT")
        self.assertFalse(status["applied"])

    def test_unknown_mode_string_sanitizes_to_off(self):
        gate = ProductionInfluence(
            mode="bananas",
            snapshot_path=self.artifacts.snapshot,
            evaluation_path=self.artifacts.evaluation,
        )
        self.assertEqual(gate.mode, "off")
        state, status = gate.apply(event("user_message"), "LISTENING")
        self.assertEqual(state, "LISTENING")
        self.assertFalse(status["applied"])

    def test_summary_reports_gate_state(self):
        gate = self.artifacts.influence(mode="auto")
        summary = gate.summary()
        self.assertEqual(summary["mode"], "auto")
        self.assertEqual(summary["verdict"], CANDIDATE_VERDICT)
        self.assertTrue(summary["permitted"])
        self.assertIn("text", summary["covered_cases"])


class TestServerIntegration(unittest.TestCase):
    def test_default_server_uses_baseline_and_reports_influence(self):
        artifacts = TempArtifacts()
        try:
            service = FlyBrainService(steps=20)
            health = service.health()
            self.assertIn("learned_influence", health)
            self.assertEqual(health["learned_influence"]["mode"], "off")

            result = service.behavior(
                {"event": "user_message", "source": "whatsapp", "context": {"media_type": "text"}, "priority": 0.4}
            )
            self.assertEqual(result["fetch"], "LISTENING")
            self.assertFalse(result["influence"]["applied"])
        finally:
            artifacts.close()

    def test_server_influence_mode_on_overrides_state(self):
        artifacts = TempArtifacts()
        try:
            service = FlyBrainService(
                steps=20,
                influence=artifacts.influence(mode="on"),
            )
            result = service.behavior(
                {"event": "user_message", "source": "whatsapp", "priority": 0.4}
            )
            self.assertEqual(result["fetch"], "IMPORTANT")
            self.assertTrue(result["influence"]["applied"])
            self.assertEqual(result["influence"]["source"], "rl")
            # recorded decision column reflects the influenced state
            self.assertEqual(
                service.store.decisions(limit=1)[0]["state"], "IMPORTANT"
            )
        finally:
            artifacts.close()


if __name__ == "__main__":
    unittest.main()