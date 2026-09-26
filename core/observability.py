"""Structured, secret-safe observability for Core Brain.

The Brain had no diagnostics at all: a caller could not tell whether an event
produced a memory, whether learning ran, or whether a provider or the
heuristic fallback produced an answer. This module adds that, with three rules
that are enforced here rather than left to call sites.

**Bounded records.** A record carries identifiers, counts, decisions and
reasons. It never carries memory content, a payload, a note, a statement or a
query — only whether one was involved and how large it was. Full user history
is reachable through the canonical API, under the caller's ``user_id``, and is
never duplicated into a log stream that may be shipped somewhere else.

**Redaction.** Secret-shaped keys are replaced with ``***`` at emission time,
and any registered secret value is scrubbed from the rendered text, so a
credential cannot escape through a provider error message.

**Off by default.** A library must not write to a host's stderr uninvited, so
records are discarded unless the Brain is explicitly enabled. That also keeps
the default hot path free of formatting cost.

Use :func:`get_logger` from Brain modules and :func:`configure` from a process
entry point. Nothing here changes behaviour: a Brain with logging disabled is
byte-for-byte the Brain that existed before.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from typing import Any, Mapping, TextIO

from core.config import LogSettings, log_settings

__all__ = [
    "BrainLogger",
    "configure",
    "get_logger",
    "redact_secrets",
    "register_secret",
]

LOGGER_NAME = "digital_brain"

#: Key names whose values are never emitted, whatever the nesting.
_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "bearer",
        "cookie",
        "credential",
        "credentials",
        "password",
        "passwd",
        "private_key",
        "secret",
        "session",
        "token",
        "x-api-key",
    }
)

_REDACTED = "***"
_MAX_VALUE_CHARS = 200
_MAX_DEPTH = 4
_MAX_ITEMS = 24

# Registered secret values are scrubbed from rendered text as a second line of
# defence: a provider error can echo a credential inside a free-text message.
_SECRETS: set[str] = set()


def register_secret(value: str | None) -> None:
    """Register a value that must never appear in output.

    The Brain registers the Gemini API key when it reads its configuration.
    Values shorter than eight characters are ignored, because scrubbing a short
    string would corrupt unrelated text.
    """
    if value and len(value.strip()) >= 8:
        _SECRETS.add(value.strip())


def redact_secrets(text: str) -> str:
    """Replace every registered secret value found in ``text``."""
    for secret in _SECRETS:
        if secret in text:
            text = text.replace(secret, _REDACTED)
    return text


def _scrub(value: Any, depth: int = 0) -> Any:
    """Reduce a value to something safe to log.

    Secret-shaped keys are redacted, strings are length-capped and
    secret-scrubbed, containers are bounded in both width and depth.
    """
    if isinstance(value, str):
        capped = value[:_MAX_VALUE_CHARS]
        if len(value) > _MAX_VALUE_CHARS:
            capped = f"{capped}…(+{len(value) - _MAX_VALUE_CHARS} chars)"
        return redact_secrets(capped)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Mapping):
        if depth >= _MAX_DEPTH:
            return "…"
        out: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _MAX_ITEMS:
                out["…"] = f"+{len(value) - _MAX_ITEMS} more"
                break
            name = str(key)
            out[name] = (
                _REDACTED
                if name.strip().lower() in _SECRET_KEYS
                else _scrub(item, depth + 1)
            )
        return out
    if isinstance(value, (list, tuple, set, frozenset)):
        if depth >= _MAX_DEPTH:
            return "…"
        items = list(value)
        scrubbed = [_scrub(item, depth + 1) for item in items[:_MAX_ITEMS]]
        if len(items) > _MAX_ITEMS:
            scrubbed.append(f"+{len(items) - _MAX_ITEMS} more")
        return scrubbed
    return _scrub(str(value), depth + 1)


class _JsonFormatter(logging.Formatter):
    """One JSON object per record, with the scrubbed payload attached."""

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "brain_event", {})
        body: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        fields = _scrub(event) if isinstance(event, Mapping) else {}
        if isinstance(fields, Mapping) and fields:
            body.update(fields)
        if record.exc_info:
            # The exception type only: a provider traceback can quote a request
            # body, and the message text is already scrubbed above.
            body["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return redact_secrets(json.dumps(body, ensure_ascii=False, sort_keys=True))


class _TextFormatter(logging.Formatter):
    """One readable line per record, still scrubbed."""

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "brain_event", {})
        fields = _scrub(event) if isinstance(event, Mapping) else {}
        suffix = ""
        if isinstance(fields, Mapping) and fields:
            suffix = " " + " ".join(f"{k}={v}" for k, v in fields.items())
        base = (
            f"{self.formatTime(record, '%H:%M:%S')} "
            f"{record.levelname:<7} {record.getMessage()}{suffix}"
        )
        if record.exc_info and record.exc_info[0] is not None:
            base = f"{base} error_type={record.exc_info[0].__name__}"
        return redact_secrets(base)


@dataclass
class BrainLogger:
    """A thin, dependency-free recorder for one Brain subsystem.

    Every method is a no-op when the Brain is not enabled, so call sites can log
    unconditionally without a guard and without paying for formatting.
    """

    name: str
    _logger: logging.Logger = field(repr=False, default=None)  # type: ignore[assignment]
    enabled: bool = False
    json_format: bool = True

    @classmethod
    def get(cls, name: str) -> "BrainLogger":
        # configure() is idempotent, so a host that already configured logging
        # keeps its settings and an unconfigured host still gets env-driven
        # defaults.
        settings = configure()
        return cls(
            name=f"{LOGGER_NAME}.{name}",
            _logger=logging.getLogger(f"{LOGGER_NAME}.{name}"),
            enabled=settings.enabled,
            json_format=settings.json_format,
        )

    # -- internals ---------------------------------------------------------------
    def _live_enabled(self) -> bool:
        """Whether records should flow *right now*.

        Deliberately not the ``enabled`` field: Brain modules create their
        logger at import time, which is almost always before a host calls
        ``configure()``. Caching the flag at construction would leave every
        module-level logger permanently silent, so the live package state is
        consulted instead.
        """
        return not logging.getLogger(LOGGER_NAME).disabled

    def _emit(self, level: int, event: str, fields: Mapping[str, Any]) -> None:
        if not self._live_enabled():
            return
        # A handler-less package logger would emit through lastResort at WARNING.
        if not logging.getLogger(LOGGER_NAME).handlers:
            return
        self._logger.log(level, event, extra={"brain_event": dict(fields)})

    # -- public surface ----------------------------------------------------------
    def debug(self, event: str, /, **fields: Any) -> None:
        self._emit(logging.DEBUG, event, fields)

    def info(self, event: str, /, **fields: Any) -> None:
        self._emit(logging.INFO, event, fields)

    def warning(self, event: str, /, **fields: Any) -> None:
        self._emit(logging.WARNING, event, fields)

    def error(self, event: str, /, **fields: Any) -> None:
        self._emit(logging.ERROR, event, fields)

    def exception(self, event: str, /, **fields: Any) -> None:
        """Log an error with the current exception's *type* only."""
        if not self._live_enabled():
            return
        self._logger.error(
            event,
            exc_info=True,
            extra={"brain_event": dict(fields)},
        )


_configured = False
_settings: LogSettings | None = None
_stream: TextIO | None = None


def configure(
    settings: LogSettings | None = None,
    *,
    stream: TextIO | None = None,
) -> LogSettings:
    """Attach the Brain's handler and return the resolved settings.

    Idempotent, and the resolved settings are remembered: a later call with no
    argument reuses them instead of re-reading the environment, so a host that
    configures logging programmatically is not silently overridden by ambient
    environment variables.

    Naming an explicit ``stream`` always takes effect, even after a first call.
    Silently ignoring it would send a caller's records to stderr while they
    believed they were being captured, which is the worst possible failure for
    an observability API.
    """
    global _configured, _settings, _stream
    resolved = settings or _settings or log_settings()
    _settings = resolved
    package = logging.getLogger(LOGGER_NAME)
    package.setLevel(getattr(logging, resolved.level_name, logging.INFO))
    # The Brain owns its own output: never propagate into a host application's
    # root handlers, which would duplicate or misroute records.
    package.propagate = False

    retarget = stream is not None and stream is not _stream
    if not _configured or retarget:
        if retarget:
            package.handlers.clear()
        handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
        handler.setFormatter(
            _JsonFormatter() if resolved.json_format else _TextFormatter()
        )
        package.addHandler(handler)
        _configured = True
        _stream = stream if stream is not None else sys.stderr
    package.disabled = not resolved.enabled
    return resolved


def get_logger(name: str) -> BrainLogger:
    """Return the recorder for one Brain subsystem (e.g. ``"ingestion"``)."""
    return BrainLogger.get(name)
