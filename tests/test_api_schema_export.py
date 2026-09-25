"""Tests for canonical Brain API v1 registry and schema distribution."""

from __future__ import annotations

import io
import json
import re
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from contracts.api import (
    API_CONTRACT_VERSION,
    API_METHOD_REGISTRY,
    API_METHOD_SPECS,
    ApiMethod,
    ResponseEnvelope,
    api_method_names,
    describe_api_methods,
    get_api_method_spec,
)
from contracts.api.frames import EventEnvelope
from contracts.api.schema import (
    BRAIN_API_SCHEMA_ID,
    DEFAULT_SCHEMA_PATH,
    JSON_SCHEMA_DIALECT,
    brain_api_schema_is_current,
    build_brain_api_schema,
    dumps_brain_api_schema,
    main,
)
from core import BrainApi, build_brain_service
from core.service.api import _HANDLERS


class RegistryTests(unittest.TestCase):
    def test_registry_exactly_matches_v1_method_enum_in_order(self):
        self.assertEqual(api_method_names(), [method.value for method in ApiMethod])
        self.assertEqual(len(API_METHOD_SPECS), len(ApiMethod))
        self.assertEqual(
            [spec.method for spec in API_METHOD_SPECS],
            list(ApiMethod),
        )
        self.assertEqual(set(API_METHOD_REGISTRY), set(ApiMethod))

    def test_every_method_binds_typed_models(self):
        for spec in API_METHOD_SPECS:
            with self.subTest(method=spec.method.value):
                self.assertTrue(issubclass(spec.params_model, BaseModel))
                self.assertTrue(issubclass(spec.result_model, BaseModel))
                self.assertIs(get_api_method_spec(spec.method), spec)
                self.assertIs(get_api_method_spec(spec.method.value), spec)

    def test_public_registry_mapping_is_immutable(self):
        with self.assertRaises(TypeError):
            API_METHOD_REGISTRY[ApiMethod.PING] = API_METHOD_SPECS[0]

    def test_runtime_handlers_cover_exact_public_registry(self):
        self.assertEqual(set(_HANDLERS), set(API_METHOD_REGISTRY))

    def test_describe_helper_is_deterministic_and_complete(self):
        first = describe_api_methods()
        second = describe_api_methods()
        self.assertEqual(first, second)
        self.assertEqual(list(first), api_method_names())
        for method in api_method_names():
            with self.subTest(method=method):
                self.assertEqual(set(first[method]), {"params", "result"})


class SchemaBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = build_brain_api_schema()
        cls.text = dumps_brain_api_schema()

    def test_bundle_metadata_and_method_order_are_v1(self):
        self.assertEqual(self.bundle["$schema"], JSON_SCHEMA_DIALECT)
        self.assertEqual(self.bundle["$id"], BRAIN_API_SCHEMA_ID)
        self.assertEqual(
            self.bundle["x-brain-api-version"],
            API_CONTRACT_VERSION,
        )
        self.assertEqual(
            [entry["method"] for entry in self.bundle["x-methods"]],
            api_method_names(),
        )

    def test_root_schema_validates_the_catalog_shape(self):
        self.assertEqual(self.bundle["type"], "object")
        self.assertFalse(self.bundle["additionalProperties"])
        self.assertEqual(
            set(self.bundle["required"]),
            set(self.bundle["properties"]),
        )
        self.assertEqual(set(self.bundle), set(self.bundle["properties"]))
        self.assertEqual(
            self.bundle["properties"]["x-brain-api-version"],
            {"const": API_CONTRACT_VERSION},
        )
        self.assertIn("JsonSchema", self.bundle["$defs"])
        self.assertIn("JsonSchemaValue", self.bundle["$defs"])

    def test_bundle_exposes_envelope_event_and_frame_contracts(self):
        expected = {
            "ApiRequest",
            "ApiResponse",
            "ApiError",
            "ApiErrorCode",
            "ApiMethod",
            "BrainEvent",
            "ResponseEnvelope",
            "EventEnvelope",
        }
        self.assertEqual(set(self.bundle["x-contracts"]), expected)
        response = self.bundle["$defs"]["ResponseEnvelope"]
        event = self.bundle["$defs"]["EventEnvelope"]
        self.assertEqual(response["properties"]["kind"]["const"], "response")
        self.assertEqual(event["properties"]["kind"]["const"], "event")
        self.assertFalse(response["additionalProperties"])
        self.assertFalse(event["additionalProperties"])

    def test_every_local_reference_resolves(self):
        definitions = self.bundle["$defs"]
        missing: list[str] = []
        pending = [self.bundle]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                reference = value.get("$ref")
                if isinstance(reference, str):
                    if not reference.startswith("#/$defs/"):
                        missing.append(reference)
                    elif reference.removeprefix("#/$defs/") not in definitions:
                        missing.append(reference)
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
        self.assertEqual(missing, [])
        pattern = self.bundle["properties"]["x-methods"]["items"]["properties"][
            "params"
        ]["pattern"]
        for reference in self.bundle["x-contracts"].values():
            self.assertIsNotNone(re.fullmatch(pattern, reference))

    def test_method_references_match_each_contract_model(self):
        entries = {
            entry["method"]: entry
            for entry in self.bundle["x-methods"]
        }
        for spec in API_METHOD_SPECS:
            entry = entries[spec.method.value]
            for field, model in (
                ("params", spec.params_model),
                ("result", spec.result_model),
            ):
                with self.subTest(method=spec.method.value, field=field):
                    name = entry[field].removeprefix("#/$defs/")
                    individual = model.model_json_schema()
                    reference = individual.get("$ref")
                    if isinstance(reference, str):
                        expected = individual["$defs"][
                            reference.removeprefix("#/$defs/")
                        ]
                    else:
                        expected = {
                            key: value
                            for key, value in individual.items()
                            if key != "$defs"
                        }
                    self.assertEqual(self.bundle["$defs"][name], expected)

    def test_serialization_is_valid_deterministic_and_data_free(self):
        self.assertEqual(self.text, dumps_brain_api_schema())
        parsed = json.loads(self.text)
        self.assertEqual(parsed, self.bundle)
        self.assertTrue(self.text.endswith("\n"))
        for forbidden in ("usr_a", "usr_b", "evt_api", "secret-token"):
            self.assertNotIn(forbidden, self.text)

    def test_checked_in_artifact_is_current(self):
        artifact = DEFAULT_SCHEMA_PATH
        self.assertEqual(
            artifact,
            Path(__file__).resolve().parent.parent
            / "contracts"
            / "schemas"
            / "brain-api.v1.json",
        )
        self.assertTrue(brain_api_schema_is_current(artifact))
        self.assertEqual(
            artifact.read_bytes(),
            dumps_brain_api_schema().encode("utf-8"),
        )
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--check"]), 0)

    def test_exporter_writes_and_check_detects_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested" / "brain-api.v1.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--output", str(target)]), 0)
            self.assertTrue(brain_api_schema_is_current(target))
            target.write_bytes(b"{}\n")
            errors = io.StringIO()
            with redirect_stderr(errors), redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--check", "--output", str(target)]), 1)
            self.assertIn("stale", errors.getvalue())
            target.unlink()
            self.assertFalse(brain_api_schema_is_current(target))

    def test_runtime_describe_uses_the_public_contract_registry(self):
        service = build_brain_service(":memory:")
        self.addCleanup(service.close)
        described = BrainApi(service).describe()
        self.assertEqual(described.methods, api_method_names())
        self.assertEqual(described.schemas, describe_api_methods())


class SchemaArchitectureTests(unittest.TestCase):
    def test_packaging_includes_canonical_schema_artifact(self):
        project = Path(__file__).resolve().parent.parent
        config = tomllib.loads(
            (project / "pyproject.toml").read_text(encoding="utf-8")
        )
        self.assertIn("contracts*", config["tool"]["setuptools"]["packages"]["find"]["include"])
        self.assertEqual(
            config["tool"]["setuptools"]["package-data"]["contracts.schemas"],
            ["*.json"],
        )
        self.assertTrue(DEFAULT_SCHEMA_PATH.is_file())
        self.assertEqual(DEFAULT_SCHEMA_PATH.parent.name, "schemas")
        self.assertEqual(DEFAULT_SCHEMA_PATH.name, "brain-api.v1.json")

    def test_contract_schema_layer_imports_no_core_or_transport(self):
        package = Path(__file__).resolve().parent.parent / "contracts" / "api"
        forbidden = (
            "core",
            "transport",
            "socket",
            "asyncio",
            "http",
            "websocket",
            "mobile",
            "react",
        )
        offenders: list[str] = []
        for path in package.glob("*.py"):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if not (stripped.startswith("import ") or stripped.startswith("from ")):
                    continue
                lowered = stripped.lower()
                if any(token in lowered for token in forbidden):
                    offenders.append(f"{path.name}: {stripped}")
        self.assertEqual(offenders, [])

    def test_canonical_frame_models_remain_wire_compatible(self):
        response = ResponseEnvelope.model_validate(
            {
                "kind": "response",
                "payload": {
                    "id": "r",
                    "method": "ping",
                    "version": "v1",
                    "ok": True,
                    "result": {
                        "service": "digital-brain",
                        "api_version": "v1",
                    },
                    "error": None,
                },
            }
        )
        self.assertEqual(response.kind, "response")
        self.assertTrue(response.payload.ok)
        with self.assertRaises(ValueError):
            EventEnvelope.model_validate(
                {
                    "kind": "response",
                    "payload": {},
                }
            )


if __name__ == "__main__":
    unittest.main()
