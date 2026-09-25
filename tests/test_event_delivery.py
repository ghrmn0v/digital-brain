"""Phase 8 Slice 4B — consumer-side event delivery contract.

Verifies the semantics documented in ``docs/event-delivery.md``:

- stable event identity (delivery dedup key = ``event.id``, minted once);
- same emission redelivered => recognised as a duplicate; distinct emissions
  stay distinct even with identical content;
- correlation_id / user_id are envelope-stable and never rewritten;
- per-operation ordering (delivery order == emission order); no global
  ordering claim (no sequence numbers, timestamps may tie);
- at-most-once best-effort delivery (no retry / replay / durability);
- the EventSink port is the transport-independent consumer boundary
  (no HTTP / WebSocket / Redics / Kafka / DB imports in the event infra);
- existing EventSink and developer-pipeline behavior is unchanged.

No transports, no network and no new production machinery: the tests only pin
down existing behavior.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from contracts.brain_events.events import BrainEvent, BrainEventType
from contracts.common.types import Source
from contracts.feedback.feedback import (
    Feedback,
    FeedbackKind,
    FeedbackSource,
    FeedbackTarget,
)

from core import (
    BrainEventDispatcher,
    BrainEventEmitter,
    CollectingEventSink,
    DevModePipeline,
    EventSink,
    NullEventSink,
    build_brain_service,
)

from .ingestion_support import make_event as make_source_event
from .test_brain_events import _sample_finding
from .test_reasoning import make_context


_FIXED_NOW = datetime(2026, 9, 25, 10, 0, 0, tzinfo=timezone.utc)


def _synthetic(
    event_type: BrainEventType = BrainEventType.DECISION_CREATED,
    *,
    user_id: str = "usr_a",
    correlation_id: str | None = None,
    **payload: object,
) -> BrainEvent:
    """A minimal but fully contract-valid BrainEvent (test fixture)."""
    return BrainEvent(
        id="evt_test",
        type=event_type,
        timestamp=_FIXED_NOW,
        user_id=user_id,
        source=Source(provider="core", component="test"),
        related_ids=[],
        payload={"correlation_id": correlation_id, **payload},
    )


class DedupConsumer:
    """Minimal consumer demonstrating the duplicate rule (test helper).

    A plain object with only ``emit(event)`` — exactly what the EventSink
    consumer port requires. It records which deliveries were duplicates.
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self.accepted: list[BrainEvent] = []
        self.duplicates: list[BrainEvent] = []

    def emit(self, event: BrainEvent) -> None:
        if event.id in self._seen:
            self.duplicates.append(event)
            return
        self._seen.add(event.id)
        self.accepted.append(event)


class EventIdentityTests(unittest.TestCase):
    def setUp(self):
        self.emitter = BrainEventEmitter()

    def test_ids_are_minted_once_per_emission_and_stable(self):
        e1 = self.emitter.bug_detected(_sample_finding(), correlation_id="c")
        e2 = self.emitter.bug_detected(_sample_finding(), correlation_id="c")
        self.assertNotEqual(e1.id, e2.id)
        for event in (e1, e2):
            self.assertTrue(event.id.startswith("evt_"), event.id)
            self.assertGreater(len(event.id), 8)
        # redelivering the SAME emission keeps the SAME identity
        self.assertEqual(e1.id, e1.id)
        self.assertEqual(e1.model_copy().id, e1.id)

    def test_identity_survives_wire_round_trip(self):
        event = self.emitter.bug_detected(_sample_finding(), correlation_id="c")
        rebuilt = BrainEvent.model_validate_json(event.model_dump_json())
        self.assertEqual(rebuilt.id, event.id)
        self.assertEqual(rebuilt.user_id, event.user_id)
        self.assertEqual(rebuilt.payload, event.payload)

    def test_identical_content_distinct_emissions_are_distinct_events(self):
        same = _sample_finding()
        e1 = self.emitter.bug_detected(same, correlation_id="c")
        e2 = self.emitter.bug_detected(same, correlation_id="c")
        self.assertEqual(e1.payload, e2.payload)
        self.assertEqual(e1.payload["finding_id"], e2.payload["finding_id"])
        self.assertNotEqual(e1.id, e2.id)


class DuplicateDeliveryTests(unittest.TestCase):
    def test_same_emission_delivered_twice_is_recognised_as_duplicate(self):
        consumer = DedupConsumer()
        event = BrainEventEmitter().bug_detected(
            _sample_finding(), correlation_id="c"
        )
        consumer.emit(event)
        consumer.emit(event)
        self.assertEqual(consumer.accepted, [event])
        self.assertEqual(consumer.duplicates, [event])

    def test_distinct_emissions_are_never_duplicates(self):
        consumer = DedupConsumer()
        emitter = BrainEventEmitter()
        consumer.emit(emitter.bug_detected(_sample_finding(), correlation_id="c"))
        consumer.emit(emitter.bug_detected(_sample_finding(), correlation_id="c"))
        consumer.emit(emitter.bug_detected(_sample_finding(), correlation_id="c"))
        self.assertEqual(len(consumer.accepted), 3)
        self.assertEqual(consumer.duplicates, [])


class CorrelationTests(unittest.TestCase):
    def test_correlation_is_stable_across_deliveries(self):
        emitter = BrainEventEmitter()
        event = emitter.bug_detected(_sample_finding(), correlation_id="corr_x")
        rebuilt = BrainEvent.model_validate_json(event.model_dump_json())
        self.assertEqual(event.payload["correlation_id"], "corr_x")
        self.assertEqual(rebuilt.payload["correlation_id"], "corr_x")

    def test_correlation_key_always_present_null_when_absent(self):
        event = _synthetic(correlation_id=None)
        self.assertIn("correlation_id", event.payload)
        self.assertIsNone(event.payload["correlation_id"])

    def test_all_events_of_one_operation_share_correlation(self):
        service = build_brain_service(":memory:", sink=CollectingEventSink())
        self.addCleanup(service.close)
        outcome = service.analyze_developer(
            make_context(
                [
                    {
                        "path": "core/auth/login.py",
                        "language": "python",
                        "content": (
                            "def get_user():\n    return None\n\n"
                            "def render():\n    user = get_user()\n"
                            "    return user.email\n"
                        ),
                    }
                ],
                task="bug in login render",
                changed_files=["core/auth/login.py"],
                test_results=[
                    {"name": "login", "status": "failed", "message": "boom"}
                ],
            ),
            correlation_id="corr_op",
        )
        emitted = service.sink.emitted
        self.assertGreater(len(emitted), 0)
        for event in emitted:
            self.assertEqual(event.payload["correlation_id"], "corr_op")
            self.assertEqual(event.payload["correlation_id"], outcome.correlation_id)


class UserOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.sink = CollectingEventSink()
        self.service = build_brain_service(":memory:", sink=self.sink)
        self.addCleanup(self.service.close)

    def test_user_id_is_stable_across_deliveries(self):
        event = BrainEventEmitter().bug_detected(
            _sample_finding(user_id="usr_a"), correlation_id="c"
        )
        rebuilt = BrainEvent.model_validate_json(event.model_dump_json())
        self.assertEqual(event.user_id, "usr_a")
        self.assertEqual(rebuilt.user_id, "usr_a")

    def test_consumer_partitions_events_by_user(self):
        self.service.ingest(
            make_source_event(
                event_id="evt_src_a",
                user_id="usr_a",
                event_type="source.linkedin.profile_updated",
                payload={"full_name": "Ana", "section": "experience"},
                correlation_id="corr_a",
            )
        )
        self.service.ingest(
            make_source_event(
                event_id="evt_src_b",
                user_id="usr_b",
                event_type="source.linkedin.profile_updated",
                payload={"full_name": "Bob", "section": "experience"},
                correlation_id="corr_b",
            )
        )
        events = self.sink.emitted
        self.assertGreater(len(events), 0)
        for event in events:
            self.assertIn(event.user_id, {"usr_a", "usr_b"})

        for_a = self.sink.by_user("usr_a")
        for_b = self.sink.by_user("usr_b")
        self.assertTrue(for_a)
        self.assertTrue(for_b)
        # a consumer filtered by user never sees another user's events
        self.assertTrue(all(e.user_id == "usr_a" for e in for_a))
        self.assertTrue(all(e.user_id == "usr_b" for e in for_b))
        id_a = {e.id for e in for_a}
        id_b = {e.id for e in for_b}
        self.assertTrue(id_a.isdisjoint(id_b))
        # correlation chains stay per-user
        self.assertTrue(
            all(e.payload["correlation_id"] == "corr_a" for e in for_a)
        )
        self.assertTrue(
            all(e.payload["correlation_id"] == "corr_b" for e in for_b)
        )


class OrderingTests(unittest.TestCase):
    def test_analyze_developer_delivery_matches_emission_order(self):
        sink = CollectingEventSink()
        service = build_brain_service(":memory:", sink=sink)
        self.addCleanup(service.close)
        outcome = service.analyze_developer(
            make_context(
                [
                    {
                        "path": "core/auth/login.py",
                        "language": "python",
                        "content": (
                            "def get_user():\n    return None\n\n"
                            "def render():\n    user = get_user()\n"
                            "    return user.email\n"
                        ),
                    }
                ],
                task="bug in login render",
                changed_files=["core/auth/login.py"],
                test_results=[
                    {"name": "login", "status": "failed", "message": "boom"}
                ],
            ),
            correlation_id="corr_order",
        )

        emitted = sink.emitted
        self.assertEqual(emitted, outcome.events)

        developer_count = len(outcome.events) - 1 - len(
            outcome.plan.proposed_actions
        )
        self.assertTrue(developer_count > 0)
        self.assertTrue(
            all(
                event.type.value.startswith("developer.")
                for event in emitted[:developer_count]
            )
        )

        decision_types = [e.type for e in emitted[developer_count:]]
        self.assertEqual(
            decision_types,
            [BrainEventType.DECISION_CREATED]
            + [
                BrainEventType.ACTION_PROPOSED
                for _ in outcome.plan.proposed_actions
            ],
        )

        # 3) every event preserves correlation + ownership.
        for event in emitted:
            self.assertEqual(event.payload["correlation_id"], "corr_order")
            self.assertEqual(event.user_id, outcome.user_id)

        # 4) no developer event arrives after the plan decision.
        developer_ids = [
            i
            for i, e in enumerate(emitted)
            if e.type.value.startswith("developer.")
        ]
        decision_index = next(
            i
            for i, e in enumerate(emitted)
            if e.type == BrainEventType.DECISION_CREATED
        )
        self.assertTrue(
            all(i < decision_index for i in developer_ids)
        )

    def test_ordering_is_delivery_order_not_timestamp(self):
        # A fixed clock mints IDENTICAL timestamps for every event of a run;
        # ordering still comes from sequential emit calls, never timestamps.
        sink = CollectingEventSink()
        pipeline = DevModePipeline(
            emitter=BrainEventEmitter(now=lambda: _FIXED_NOW),
            sink=sink,
        )
        outcome = pipeline.run(
            make_context(
                [
                    {
                        "path": "core/auth/login.py",
                        "language": "python",
                        "content": (
                            "def get_user():\n    return None\n\n"
                            "def render():\n    user = get_user()\n"
                            "    return user.email\n"
                        ),
                    }
                ],
                task="bug in login render",
                changed_files=["core/auth/login.py"],
            )
        )
        self.assertGreater(len(outcome.events), 1)
        stamps = {e.timestamp for e in sink.emitted}
        self.assertEqual(len(stamps), 1)  # timestamps tie ...
        self.assertEqual(sink.emitted, outcome.events)  # ... but order holds

    def test_no_global_sequence_field_on_events(self):
        brain_schema = BrainEvent.model_json_schema()
        for banned in ("sequence", "seq", "order", "global_order", "position"):
            self.assertNotIn(banned, brain_schema["properties"])

    def test_missing_feedback_signal_precedes_preference_within_one_call(self):
        sink = CollectingEventSink()
        service = build_brain_service(":memory:", sink=sink)
        self.addCleanup(service.close)

        outcome = service.analyze_developer(
            make_context(
                [
                    {
                        "path": "core/auth/login.py",
                        "language": "python",
                        "content": (
                            "def get_user():\n    return None\n\n"
                            "def render():\n    user = get_user()\n"
                            "    return user.email\n"
                        ),
                    }
                ],
                task="bug in login render",
                changed_files=["core/auth/login.py"],
                test_results=[
                    {"name": "login", "status": "failed", "message": "boom"}
                ],
            )
        )
        decision = outcome.plan.decision
        fix_action = next(
            a
            for a in outcome.plan.proposed_actions
            if a.action_type.value == "code.fix"
        )

        sink.clear()
        saw_preference = False
        for _ in range(8):
            service.record_feedback(
                Feedback(
                    feedback_id=f"fb_order_loop",
                    user_id=outcome.user_id,
                    source=FeedbackSource.PRODUCT,
                    kind=FeedbackKind.EXPLICIT,
                    target=FeedbackTarget(
                        decision_id=decision.decision_id,
                        action_id=fix_action.action_id,
                    ),
                    label="rejected",
                    value=-1.0,
                    note="wrong target",
                    created_at=_FIXED_NOW,
                    correlation_id="corr_fb",
                    metadata={"action_type": "code.fix"},
                ),
                correlation_id="corr_fb",
            )
            call_events = sink.emitted
            types = [e.type for e in call_events]
            self.assertEqual(types[:1], [BrainEventType.LEARNING_SIGNAL_DETECTED])
            if BrainEventType.PREFERENCE_UPDATED in types:
                # within one operation: signal first, preference after it,
                # both owning the same user + correlation.
                self.assertEqual(types[-1], BrainEventType.PREFERENCE_UPDATED)
                for event in call_events:
                    self.assertEqual(event.user_id, outcome.user_id)
                    self.assertEqual(
                        event.payload["correlation_id"], "corr_fb"
                    )
                saw_preference = True
                break
            sink.clear()
        self.assertTrue(saw_preference, "feedback loop never wrote a preference")


class DeliverySemanticsTests(unittest.TestCase):
    def test_delivery_is_synchronous_emit_no_retry_on_failure(self):
        class FailingSink:
            def __init__(self):
                self.attempts = 0

            def emit(self, event):
                self.attempts += 1
                raise RuntimeError("no transport here")

        failing = FailingSink()
        pipeline = DevModePipeline(
            sink=failing,  # type: ignore[arg-type]
        )
        with self.assertRaises(RuntimeError):
            pipeline.run(
                make_context(
                    [
                        {
                            "path": "core/auth/login.py",
                            "language": "python",
                            "content": (
                                "def get_user():\n    return None\n\n"
                                "def render():\n    user = get_user()\n"
                                "    return user.email\n"
                            ),
                        }
                    ],
                    task="bug in login render",
                    changed_files=["core/auth/login.py"],
                )
            )
        # the failure propagated and NOTHING was retried or spooled.
        self.assertEqual(failing.attempts, 1)

    def test_sink_delivery_is_inline_without_background_queue(self):
        class InlineSink:
            def __init__(self):
                self.calls = 0
                self.in_emit = False
                self.events = []

            def emit(self, event):
                self.calls += 1
                self.in_emit = True
                self.events.append(event)
                self.in_emit = False

        sink = InlineSink()
        service = build_brain_service(":memory:", sink=sink)
        self.addCleanup(service.close)
        service.ingest(
            make_source_event(
                event_id="evt_inline",
                event_type="source.linkedin.profile_updated",
                user_id="usr_a",
                payload={"full_name": "Inline"},
            )
        )
        self.assertEqual(sink.calls, 1)
        self.assertFalse(sink.in_emit)
        self.assertEqual(len(sink.events), 1)

    def test_idempotent_operation_emits_no_duplicate_events(self):
        sink = CollectingEventSink()
        service = build_brain_service(":memory:", sink=sink)
        self.addCleanup(service.close)

        source = make_source_event(
            event_id="evt_once",
            user_id="usr_a",
            event_type="source.linkedin.profile_updated",
            payload={"full_name": "Once", "section": "experience"},
        )
        first = service.ingest(source, correlation_id="corr_once")
        self.assertEqual(first.outcome.value, "accepted")
        self.assertEqual(len(sink.emitted), 1)
        events_before = len(sink.emitted)

        # the exact same logical event again: receipted as duplicate, no
        # transition => no new event, no duplicate delivery.
        again = service.ingest(source, correlation_id="corr_once")
        self.assertEqual(again.outcome.value, "duplicate")
        self.assertEqual(len(sink.emitted), events_before)


class EventSinkCompatibilityTests(unittest.TestCase):
    def test_existing_sink_behavior_still_compatible(self):
        # NullEventSink validates and discards; rejects non-contracts.
        null_sink = NullEventSink()
        null_sink.emit(_synthetic())
        with self.assertRaises(TypeError):
            null_sink.emit(object())  # type: ignore[arg-type]

        # port is runtime-checkable; bundled sinks implement it.
        self.assertIsInstance(NullEventSink(), EventSink)
        self.assertIsInstance(CollectingEventSink(), EventSink)
        self.assertIsInstance(DedupConsumer(), EventSink)

        # CollectingEventSink snapshot isolation / views / clear.
        sink = CollectingEventSink()
        sink.emit(_synthetic(correlation_id="c1"))
        sink.emit(_synthetic(BrainEventType.ACTION_PROPOSED, correlation_id="c2"))
        self.assertEqual(len(sink.emitted), 2)
        snapshot = sink.emitted
        snapshot.clear()
        self.assertEqual(len(sink.emitted), 2)
        self.assertEqual(
            len(sink.by_type(BrainEventType.DECISION_CREATED)), 1
        )
        sink.clear()
        self.assertEqual(sink.emitted, [])

    def test_plain_consumer_class_works_as_service_sink(self):
        consumer = DedupConsumer()
        service = build_brain_service(":memory:", sink=consumer)
        self.addCleanup(service.close)
        service.ingest(
            make_source_event(
                event_id="evt_cons",
                user_id="usr_a",
                event_type="source.linkedin.profile_updated",
                payload={"full_name": "Cora", "section": "experience"},
            ),
            correlation_id="corr_cons",
        )
        self.assertEqual(len(consumer.accepted), 1)
        self.assertEqual(consumer.accepted[0].user_id, "usr_a")
        self.assertEqual(consumer.accepted[0].payload["correlation_id"], "corr_cons")
        self.assertEqual(consumer.duplicates, [])


class DeveloperPipelineUnchangedTests(unittest.TestCase):
    def _demo_context(self):
        return make_context(
            [
                {
                    "path": "core/auth/login.py",
                    "language": "python",
                    "content": (
                        "def get_user():\n    return None\n\n"
                        "def render():\n    user = get_user()\n"
                        "    return user.email\n"
                    ),
                }
            ],
            task="bug in login render",
            changed_files=["core/auth/login.py"],
            test_results=[
                {"name": "login", "status": "failed", "message": "boom"}
            ],
        )

    def test_sink_attachment_changes_no_pipeline_outcome(self):
        collect = CollectingEventSink()
        piped = DevModePipeline(sink=collect)
        outcome = piped.run(self._demo_context(), correlation_id="corr_d")
        # the returned events and the delivered events are the same objects
        self.assertEqual(outcome.events, collect.emitted)
        for event in outcome.events:
            self.assertEqual(event.payload["correlation_id"], "corr_d")
            self.assertEqual(event.user_id, "usr_a")

        # a Null sink delivers nothing but must not change the outcome shape
        null_pipe = DevModePipeline(sink=NullEventSink())
        outcome_null = null_pipe.run(self._demo_context(), correlation_id="corr_d")
        self.assertEqual(
            [e.type for e in outcome.events],
            [e.type for e in outcome_null.events],
        )
        # identical shapes, correlation and ownership (minted ids differ by
        # design — ids are minted, never faked), proving the sink changes
        # nothing about what the pipeline produces.
        self.assertEqual(
            [sorted(e.payload) for e in outcome.events],
            [sorted(e.payload) for e in outcome_null.events],
        )
        self.assertEqual(
            [e.payload["correlation_id"] for e in outcome.events],
            [e.payload["correlation_id"] for e in outcome_null.events],
        )
        self.assertEqual(
            [e.user_id for e in outcome.events],
            [e.user_id for e in outcome_null.events],
        )

    def test_repeated_runs_are_distinct_emissions_not_duplicates(self):
        consumer = DedupConsumer()
        piped = DevModePipeline(sink=consumer)  # type: ignore[arg-type]
        piped.run(self._demo_context())
        piped.run(self._demo_context())
        self.assertEqual(consumer.duplicates, [])
        # every emitted event has a distinct identity
        ids = {e.id for e in consumer.accepted}
        self.assertEqual(len(ids), len(consumer.accepted))


class TransportIndependenceGuardTests(unittest.TestCase):
    FORBIDDEN = (
        "http",
        "websocket",
        "socket",
        "redis",
        "kafka",
        "sqlite",
        "grpc",
        "nats",
        "aerospike",
        "rabbitmq",
        "transport",
        "service",
        "mobile",
        "sdk",
        "stdio",
        "jsonlines",
        "aiohttp",
        "flask",
    )

    def _source_files(self):
        from pathlib import Path

        base = Path(__file__).resolve().parents[1]
        files = sorted((base / "core" / "brain_events").glob("*.py"))
        files.append(base / "contracts" / "brain_events" / "events.py")
        return files

    def test_event_infra_never_imports_transport_infrastructure(self):
        for path in self._source_files():
            with self.subTest(path=path.name):
                for lineno, line in enumerate(path.read_text().splitlines(), 1):
                    stripped = line.strip()
                    if not (
                        stripped.startswith("import ")
                        or stripped.startswith("from ")
                    ):
                        continue
                    low = line.lower()
                    for token in self.FORBIDDEN:
                        self.assertNotIn(
                            token,
                            low,
                            f"{path.name}:{lineno}: forbidden import token "
                            f"{token!r} in {line!r}",
                        )

    def test_event_infra_never_imports_core_service_or_transports(self):
        for path in self._source_files():
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                stripped = line.strip()
                if not (
                    stripped.startswith("import ")
                    or stripped.startswith("from ")
                ):
                    continue
                low = line.lower()
                self.assertNotIn("core.transport", low, path.name)
                self.assertNotIn("core.service", low, path.name)


if __name__ == "__main__":
    unittest.main()