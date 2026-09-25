"""Client-facing ``resolve_person`` (Phase 8, additive method 17).

Covers the contract bindings, the adapter, the service transition with its
single ``person.created`` emission site, the WebSocket ownership boundary and
the identity invariants that must not drift: exact match reuses, unknown mints
deterministically, ambiguous never writes, token overlap is not proof, and the
identity memory stays traceable.
"""

from __future__ import annotations

import json
import unittest

from contracts.api import ApiErrorCode, ApiMethod
from contracts.api import params as P
from contracts.api import results as R
from contracts.api.registry import (
    API_METHOD_REGISTRY,
    api_method_names,
    describe_api_methods,
    get_api_method_spec,
)
from contracts.brain_events.events import BrainEventType
from contracts.common.types import Source
from contracts.memory.memory import MemoryType

from core import BrainApi, build_brain_service
from core.memory.candidate import MemoryCandidate
from core.memory.filters import MemoryQuery
from core.people import mint_person_id
from core.transport.websocket import API_PATH, WebSocketBrainTransport

from tests.memory_support import make_service


def _build_api() -> BrainApi:
    return BrainApi(build_brain_service(":memory:"))


class ResolvePersonContractTests(unittest.TestCase):
    def test_method_is_declared_last_and_keeps_previous_indices(self) -> None:
        names = api_method_names()
        self.assertEqual(names[-1], ApiMethod.RESOLVE_PERSON.value)
        self.assertEqual(len(names), 17)
        self.assertEqual(names[:16], names[:16])
        self.assertIn(ApiMethod.RESOLVE_PERSON, list(ApiMethod))

    def test_registry_binds_the_typed_models(self) -> None:
        spec = get_api_method_spec(ApiMethod.RESOLVE_PERSON)
        self.assertIs(spec.params_model, P.ResolvePersonParams)
        self.assertIs(spec.result_model, R.PersonResolutionWire)
        self.assertIn(ApiMethod.RESOLVE_PERSON, API_METHOD_REGISTRY)

    def test_describe_exposes_the_new_method(self) -> None:
        described = describe_api_methods()
        self.assertIn(ApiMethod.RESOLVE_PERSON.value, described)
        schema = described[ApiMethod.RESOLVE_PERSON.value]
        self.assertIn("name", schema["params"]["properties"])
        self.assertIn("user_id", schema["params"]["required"])
        self.assertIn("person_id", schema["result"]["properties"])

    def test_params_require_a_name_and_forbid_extras(self) -> None:
        params = P.ResolvePersonParams(user_id="usr_a", name="Ali")
        self.assertEqual(params.aliases, [])
        with self.assertRaises(Exception):
            P.ResolvePersonParams(user_id="usr_a")
        with self.assertRaises(Exception):
            P.ResolvePersonParams(user_id="usr_a", name="x" * 500)
        with self.assertRaises(Exception):
            P.ResolvePersonParams(user_id="usr_a", name="Ali", unknown=1)
        with self.assertRaises(Exception):
            P.ResolvePersonParams(user_id="usr_a", name="Ali", aliases=["a"] * 20)

    def test_result_wire_keeps_the_ambiguity_shape(self) -> None:
        wire = R.PersonResolutionWire(
            user_id="usr_a",
            name="Ali",
            person_id=None,
            ambiguous=True,
            candidates=["per_1", "per_2"],
        )
        self.assertIsNone(wire.person_id)
        self.assertEqual(len(wire.candidates), 2)
        self.assertFalse(wire.created)


class ResolvePersonApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = build_brain_service(":memory:")
        self.addCleanup(self.service.close)
        self.api = BrainApi(self.service)

    def _memories(self, user_id: str):
        return self.service._memory.list_memories(
            MemoryQuery(user_id=user_id, limit=None)
        )

    def resolve(self, request_id: str, **params):
        return self.api.handle(
            {
                "id": request_id,
                "method": ApiMethod.RESOLVE_PERSON.value,
                "version": "v1",
                "params": params,
            }
        )

    def test_unknown_name_creates_the_person_once(self) -> None:
        first = self.resolve("1", user_id="usr_a", name="Ali Ahmadov")
        self.assertTrue(first.ok, first.error)
        self.assertIsInstance(first.result, R.PersonResolutionWire)
        self.assertTrue(first.result.created)
        self.assertFalse(first.result.ambiguous)
        self.assertIsNotNone(first.result.person_id)
        self.assertIsNotNone(first.result.memory_id)
        self.assertEqual(
            first.result.person_id, mint_person_id("usr_a", "Ali Ahmadov")
        )

        again = self.resolve("2", user_id="usr_a", name="  ali   ahmadov ")
        self.assertTrue(again.result.person_id == first.result.person_id)
        self.assertFalse(again.result.created)
        self.assertIsNone(again.result.memory_id)

    def test_person_created_is_emitted_only_for_a_new_person(self) -> None:
        self.resolve("1", user_id="usr_a", name="Ali")
        self.resolve("2", user_id="usr_a", name="Ali")
        self.resolve("3", user_id="usr_a", name="Bəkir")
        created = [
            event
            for event in self.service.emitted
            if event.type == BrainEventType.PERSON_CREATED
        ]
        self.assertEqual([event.payload["name"] for event in created], ["Ali", "Bəkir"])
        self.assertTrue(all(event.user_id == "usr_a" for event in created))
        self.assertTrue(all("person_id" in event.payload for event in created))

    def test_correlation_id_reaches_the_event(self) -> None:
        self.resolve("1", user_id="usr_a", name="Ali", correlation_id="corr_1")
        created = [
            event
            for event in self.service.emitted
            if event.type == BrainEventType.PERSON_CREATED
        ][0]
        self.assertEqual(created.payload.get("correlation_id"), "corr_1")

    def test_ambiguous_name_is_reported_without_writing(self) -> None:
        self.resolve("1", user_id="usr_a", name="Ali")
        self.service._memory.create_memory(
            MemoryCandidate(
                content="Ali (the other one)",
                user_id="usr_a",
                type=MemoryType.FACT,
                source=Source(provider="linkedin"),
                related_people=["per_connector_ali"],
                metadata={"person_name": "Ali"},
            )
        )
        before = len(self._memories("usr_a"))

        response = self.resolve("2", user_id="usr_a", name="Ali")
        self.assertTrue(response.ok, response.error)
        self.assertTrue(response.result.ambiguous)
        self.assertIsNone(response.result.person_id)
        self.assertGreaterEqual(len(response.result.candidates), 2)
        self.assertFalse(response.result.created)
        self.assertEqual(len(self._memories("usr_a")), before)
        self.assertNotIn(
            BrainEventType.PERSON_CREATED,
            [event.type for event in self.service.emitted[1:]],
        )

    def test_token_overlap_does_not_resolve_to_one_person(self) -> None:
        first = self.resolve("1", user_id="usr_a", name="Ali Ahmadov")
        second = self.resolve("2", user_id="usr_a", name="Ali Karimov")
        self.assertNotEqual(first.result.person_id, second.result.person_id)
        self.assertTrue(second.result.created)

    def test_aliases_are_recorded_and_resolve(self) -> None:
        first = self.resolve("1", user_id="usr_a", name="Ali", aliases=["Aly", "Ali A."])
        self.assertEqual(first.result.aliases, ["Aly", "Ali A."])
        by_alias = self.resolve("2", user_id="usr_a", name="Aly")
        self.assertEqual(by_alias.result.person_id, first.result.person_id)
        self.assertFalse(by_alias.result.created)

    def test_identity_memory_stays_traceable(self) -> None:
        response = self.resolve("1", user_id="usr_a", name="Ali")
        memory = self.service._memory.get_memory("usr_a", response.result.memory_id)
        self.assertEqual(memory.related_people, [response.result.person_id])
        self.assertEqual(memory.metadata["kind"], "person_identity")
        self.assertEqual(memory.metadata["person_name"], "Ali")
        self.assertEqual(memory.metadata["durability"], "durable")
        self.assertEqual(
            memory.metadata["person_key"],
            f"person:{response.result.person_id}:identity",
        )
        self.assertEqual(memory.source.provider, "people")

    def test_user_isolation(self) -> None:
        ali = self.resolve("1", user_id="usr_a", name="Ali")
        other = self.resolve("2", user_id="usr_b", name="Ali")
        self.assertNotEqual(ali.result.person_id, other.result.person_id)
        self.assertNotIn(
            other.result.person_id,
            [
                person.person_id
                for person in self.service.people_summary("usr_a").people
            ],
        )

    def test_invalid_params_return_a_typed_validation_error(self) -> None:
        for params in (
            {"user_id": "usr_a"},
            {"user_id": "usr_a", "name": "   "},
            {"user_id": "usr_a", "name": "x" * 500},
        ):
            with self.subTest(params=params):
                response = self.api.handle(
                    {
                        "id": "1",
                        "method": ApiMethod.RESOLVE_PERSON.value,
                        "version": "v1",
                        "params": params,
                    }
                )
                self.assertFalse(response.ok)
                self.assertEqual(response.error.code, ApiErrorCode.VALIDATION_ERROR)

    def test_resolved_person_is_usable_in_the_people_views(self) -> None:
        resolution = self.resolve("1", user_id="usr_a", name="Ali Ahmadov")
        person_id = resolution.result.person_id
        self.api.handle(
            {
                "id": "2",
                "method": ApiMethod.INGEST.value,
                "version": "v1",
                "params": {
                    "event": {
                        "id": "evt_1",
                        "type": "source.whatsapp.message_received",
                        "timestamp": "2026-09-25T10:00:00Z",
                        "occurred_at": "2026-09-25T10:00:00Z",
                        "user_id": "usr_a",
                        "source": {"provider": "whatsapp"},
                        "subject": {"person_name": "Ali Ahmadov"},
                        "payload": {"text": "see you"},
                    }
                },
            }
        )
        summary = self.api.handle(
            {
                "id": "3",
                "method": ApiMethod.PEOPLE_SUMMARY.value,
                "version": "v1",
                "params": {"user_id": "usr_a"},
            }
        )
        row = summary.result.people[0]
        self.assertEqual(row.person_id, person_id)
        self.assertEqual(row.name, "Ali Ahmadov")
        self.assertEqual(row.mention_count, 1)

        timeline = self.api.handle(
            {
                "id": "4",
                "method": ApiMethod.PEOPLE_TIMELINE.value,
                "version": "v1",
                "params": {"user_id": "usr_a", "person_id": person_id},
            }
        )
        self.assertTrue(timeline.result.person_known)
        self.assertGreaterEqual(timeline.result.total_entries, 1)


class ResolvePersonTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = build_brain_service(":memory:")
        self.addCleanup(self.service.close)
        self.transport = WebSocketBrainTransport(BrainApi(self.service))

    def test_websocket_ownership_boundary_covers_the_new_method(self) -> None:
        response = self.transport.handle_message(
            json.dumps(
                {
                    "id": "cross",
                    "method": ApiMethod.RESOLVE_PERSON.value,
                    "params": {"user_id": "usr_b", "name": "Ali"},
                }
            ),
            "usr_a",
        )
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code.value, "bad_request")
        self.assertIn("does not match", response.error.message)

    def test_matching_identity_reaches_the_api(self) -> None:
        response = self.transport.handle_message(
            json.dumps(
                {
                    "id": "same",
                    "method": ApiMethod.RESOLVE_PERSON.value,
                    "params": {"user_id": "usr_a", "name": "Ali"},
                }
            ),
            "usr_a",
        )
        self.assertTrue(response.ok)
        self.assertTrue(response.result.created)

    def test_connection_path_admission_is_unchanged(self) -> None:
        self.assertEqual(
            self.transport.user_id_from_path(f"{API_PATH}?user_id=usr_a"), "usr_a"
        )


class ResolvePersonServiceTests(unittest.TestCase):
    def test_service_requires_people(self) -> None:
        from core.service.brain_service import BrainService

        service = BrainService(memory=make_service())
        self.addCleanup(service.close)
        with self.assertRaises(Exception):
            service.resolve_person("usr_a", "Ali")


if __name__ == "__main__":
    unittest.main()
