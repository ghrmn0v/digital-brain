"""Packaged Digital Brain API schema artifacts."""

from __future__ import annotations

from pathlib import Path

SCHEMA_FILENAME = "brain-api.v1.json"
SCHEMA_PATH = Path(__file__).resolve().with_name(SCHEMA_FILENAME)


def read_schema_bytes() -> bytes:
    """Read the packaged Brain API v1 schema without newline translation."""
    return SCHEMA_PATH.read_bytes()


__all__ = [
    "SCHEMA_FILENAME",
    "SCHEMA_PATH",
    "read_schema_bytes",
]
