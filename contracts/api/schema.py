"""Deterministic offline JSON Schema export for the Brain API v1 contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from contracts.brain_events.events import BrainEvent
from contracts.schemas import SCHEMA_PATH

from .envelope import ApiRequest, ApiResponse
from .errors import ApiError, ApiErrorCode
from .frames import EventEnvelope, ResponseEnvelope
from .methods import ApiMethod
from .registry import (
    API_CONTRACT_VERSION,
    API_METHOD_SPECS,
    api_method_names,
)

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
BRAIN_API_SCHEMA_ID = "urn:digital-brain:schema:brain-api:v1"
DEFAULT_SCHEMA_PATH = SCHEMA_PATH
REPOSITORY_SCHEMA_PATH = Path("contracts/schemas/brain-api.v1.json")


def _ordered_unique_models(models: Sequence[type[BaseModel]]) -> list[type[BaseModel]]:
    unique: list[type[BaseModel]] = []
    seen: set[type[BaseModel]] = set()
    for model in models:
        if model in seen:
            continue
        seen.add(model)
        unique.append(model)
    return unique


def _schema_reference(
    schemas: dict[tuple[type[BaseModel], str], dict[str, Any]],
    model: type[BaseModel],
) -> str:
    schema = schemas.get((model, "validation"))
    reference = schema.get("$ref") if isinstance(schema, dict) else None
    if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
        raise RuntimeError(f"schema for {model.__name__} has no stable $ref")
    return reference


def _reference_schema() -> dict[str, Any]:
    return {
        "type": "string",
        "pattern": r"^#/\$defs/[A-Za-z0-9_]+$",
    }


def _catalog_root_schema(
    contract_references: dict[str, str],
) -> dict[str, Any]:
    reference_schema = _reference_schema()
    contract_properties = {
        name: reference_schema
        for name in contract_references
    }
    properties: dict[str, Any] = {
        "$schema": {"const": JSON_SCHEMA_DIALECT},
        "$id": {"const": BRAIN_API_SCHEMA_ID},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "x-brain-api-version": {"const": API_CONTRACT_VERSION},
        "x-contracts": {
            "type": "object",
            "properties": contract_properties,
            "required": list(contract_references),
            "additionalProperties": False,
        },
        "x-methods": {
            "type": "array",
            "minItems": len(API_METHOD_SPECS),
            "maxItems": len(API_METHOD_SPECS),
            "items": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": api_method_names(),
                    },
                    "params": reference_schema,
                    "result": reference_schema,
                },
                "required": ["method", "params", "result"],
                "additionalProperties": False,
            },
        },
        "$defs": {
            "type": "object",
            "additionalProperties": {"$ref": "#/$defs/JsonSchema"},
        },
    }
    properties.update(
        {
            "type": {"const": "object"},
            "properties": {"type": "object"},
            "required": {
                "type": "array",
                "items": {"type": "string"},
            },
            "additionalProperties": {"const": False},
        }
    )
    return properties


def build_brain_api_schema() -> dict[str, Any]:
    """Build the complete, data-free v1 schema catalog."""
    contract_models: dict[str, type[BaseModel]] = {
        "ApiRequest": ApiRequest,
        "ApiResponse": ApiResponse,
        "ApiError": ApiError,
        "BrainEvent": BrainEvent,
        "ResponseEnvelope": ResponseEnvelope,
        "EventEnvelope": EventEnvelope,
    }
    method_models: list[type[BaseModel]] = []
    for spec in API_METHOD_SPECS:
        method_models.extend((spec.params_model, spec.result_model))
    models = _ordered_unique_models(
        [*contract_models.values(), *method_models]
    )
    schemas, definitions = models_json_schema(
        [(model, "validation") for model in models],
        title="Digital Brain API Schema Bundle",
        description=(
            "Canonical schema catalog for Digital Brain API v1 requests, "
            "responses, Brain events and stream frame envelopes."
        ),
        ref_template="#/$defs/{model}",
    )
    references = {
        model: _schema_reference(schemas, model)
        for model in models
    }
    contract_references = {
        name: references[model]
        for name, model in contract_models.items()
    }
    contract_references.update(
        {
            "ApiErrorCode": f"#/$defs/{ApiErrorCode.__name__}",
            "ApiMethod": f"#/$defs/{ApiMethod.__name__}",
        }
    )
    missing_contracts = sorted(
        reference.removeprefix("#/$defs/")
        for reference in contract_references.values()
        if reference.removeprefix("#/$defs/") not in definitions.get("$defs", {})
    )
    if missing_contracts:
        raise RuntimeError(
            "schema is missing contract definitions: "
            + ", ".join(missing_contracts)
        )
    method_entries = [
        {
            "method": spec.method.value,
            "params": references[spec.params_model],
            "result": references[spec.result_model],
        }
        for spec in API_METHOD_SPECS
    ]
    schema_definitions = dict(definitions.get("$defs", {}))
    schema_definitions["JsonSchema"] = {
        "anyOf": [
            {"type": "boolean"},
            {
                "type": "object",
                "additionalProperties": {
                    "$ref": "#/$defs/JsonSchemaValue",
                },
            },
        ]
    }
    schema_definitions["JsonSchemaValue"] = {
        "anyOf": [
            {"type": "null"},
            {"type": "boolean"},
            {"type": "number"},
            {"type": "string"},
            {
                "type": "array",
                "items": {"$ref": "#/$defs/JsonSchemaValue"},
            },
            {
                "type": "object",
                "additionalProperties": {"$ref": "#/$defs/JsonSchemaValue"},
            },
        ]
    }
    root_properties = _catalog_root_schema(contract_references)
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": BRAIN_API_SCHEMA_ID,
        "title": "Digital Brain API Schema Bundle",
        "description": (
            "Canonical schema catalog for Digital Brain API v1 requests, "
            "responses, Brain events and stream frame envelopes."
        ),
        "x-brain-api-version": API_CONTRACT_VERSION,
        "x-contracts": contract_references,
        "x-methods": method_entries,
        "$defs": schema_definitions,
        "type": "object",
        "properties": root_properties,
        "required": list(root_properties),
        "additionalProperties": False,
    }


def dumps_brain_api_schema() -> str:
    """Serialize the schema bundle deterministically with a final newline."""
    return (
        json.dumps(
            build_brain_api_schema(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def write_brain_api_schema(
    path: str | Path = DEFAULT_SCHEMA_PATH,
) -> Path:
    """Write the deterministic schema bundle and return its resolved path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(dumps_brain_api_schema().encode("utf-8"))
    return target.resolve()


def brain_api_schema_is_current(
    path: str | Path = DEFAULT_SCHEMA_PATH,
) -> bool:
    """Return whether a checked-in schema file matches the generator."""
    target = Path(path)
    try:
        return target.read_bytes() == dumps_brain_api_schema().encode("utf-8")
    except FileNotFoundError:
        return False


def main(argv: Sequence[str] | None = None) -> int:
    """Generate or verify the checked-in Brain API v1 schema artifact."""
    parser = argparse.ArgumentParser(
        prog="digital-brain-export-schema",
        description=(
            "Export the deterministic Digital Brain API v1 JSON Schema bundle."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that the existing file is current without rewriting it.",
    )
    args = parser.parse_args(argv)
    if args.check:
        target = args.output or DEFAULT_SCHEMA_PATH
        if not brain_api_schema_is_current(target):
            print(
                f"schema is missing or stale: {target}",
                file=sys.stderr,
            )
            return 1
        print(f"schema is current: {target}")
        return 0
    output = args.output
    if output is None:
        source_checkout = (
            Path("pyproject.toml").is_file()
            and Path("contracts/api/schema.py").is_file()
        )
        if not source_checkout:
            parser.error("--output is required outside a source checkout")
        output = REPOSITORY_SCHEMA_PATH
    target = write_brain_api_schema(output)
    print(f"wrote schema: {target}")
    return 0


__all__ = [
    "BRAIN_API_SCHEMA_ID",
    "DEFAULT_SCHEMA_PATH",
    "JSON_SCHEMA_DIALECT",
    "REPOSITORY_SCHEMA_PATH",
    "brain_api_schema_is_current",
    "build_brain_api_schema",
    "dumps_brain_api_schema",
    "main",
    "write_brain_api_schema",
]


if __name__ == "__main__":
    raise SystemExit(main())
