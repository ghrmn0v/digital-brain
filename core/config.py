"""Brain-owned runtime configuration.

This is the single place the Brain reads its own environment. Nothing here is
evaluated at import time: every accessor takes the mapping it should read, so a
host process (or a test) stays in control of what the Brain believes.

Precedence is always explicit argument, then environment, then built-in default.
A missing or empty environment never disables a subsystem silently — the
heuristic provider and the null log sink keep the Brain fully functional.

Environment variables the Brain reads
-------------------------------------
Provider selection
    ``BRAIN_LLM_PROVIDER``       Provider name for :func:`create_provider`
                                  (default ``heuristic``). ``gemini`` is only
                                  usable when it is also enabled and keyed.
Observability
    ``BRAIN_LOG_ENABLED``        ``1``/``true``/``yes``/``on`` to emit records
                                  to stderr. Default off: a library must not
                                  write to a host's stderr uninvited.
    ``BRAIN_LOG_LEVEL``          ``debug``/``info``/``warning``/``error``.
                                  Default ``info``.
    ``BRAIN_LOG_FORMAT``         ``json`` for one JSON object per record,
                                  ``text`` for a human line. Default ``json``.
Gemini provider (see :mod:`core.understanding.gemini`)
    ``GEMINI_API_KEY``           Credential. Never logged, never echoed.
    ``GEMINI_ENABLED``           Explicit opt-in. Default off.
    ``GEMINI_MODEL``             Default ``gemini-3.8-flash``.
    ``GEMINI_API_BASE``          Default the Google endpoint.
    ``GEMINI_TIMEOUT_SECONDS``   Default ``30``.
    ``GEMINI_TEMPERATURE``       Default ``0.2``.
    ``GEMINI_MAX_OUTPUT_TOKENS`` Default ``2048``.

Transport bind address, port and database path are command-line flags
(``--host``/``--port``/``--db``), deliberately not environment variables, so a
deployed Brain always states where it listens.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

# Gemini provider variable names live here, not in the provider module, so this
# module stays the bottom of the dependency graph: the provider imports these
# names, never the other way round.
ENV_GEMINI_API_KEY = "GEMINI_API_KEY"
ENV_GEMINI_ENABLED = "GEMINI_ENABLED"
ENV_GEMINI_MODEL = "GEMINI_MODEL"
ENV_GEMINI_API_BASE = "GEMINI_API_BASE"
ENV_GEMINI_TIMEOUT = "GEMINI_TIMEOUT_SECONDS"
ENV_GEMINI_TEMPERATURE = "GEMINI_TEMPERATURE"
ENV_GEMINI_MAX_OUTPUT_TOKENS = "GEMINI_MAX_OUTPUT_TOKENS"

__all__ = [
    "DEFAULT_LOG_FORMAT",
    "DEFAULT_ENV_FILENAME",
    "ENV_FILE_POINTER",
    "DEFAULT_LOG_LEVEL",
    "DEFAULT_PROVIDER",
    "ENV_LLM_PROVIDER",
    "ENV_LOG_ENABLED",
    "ENV_LOG_FORMAT",
    "ENV_LOG_LEVEL",
    "GEMINI_ENV_VARS",
    "LogSettings",
    "brain_env_var_names",
    "env_file_candidates",
    "load_env_file",
    "log_settings",
    "resolve_llm_provider",
]

ENV_LLM_PROVIDER = "BRAIN_LLM_PROVIDER"
ENV_LOG_ENABLED = "BRAIN_LOG_ENABLED"
ENV_LOG_FORMAT = "BRAIN_LOG_FORMAT"
ENV_LOG_LEVEL = "BRAIN_LOG_LEVEL"

DEFAULT_PROVIDER = "heuristic"
DEFAULT_LOG_LEVEL = "info"
DEFAULT_LOG_FORMAT = "json"

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_LOG_LEVELS = ("debug", "info", "warning", "error")
_LOG_FORMATS = ("json", "text")

#: Every environment variable the Gemini provider reads, in documentation order.
GEMINI_ENV_VARS: tuple[str, ...] = (
    ENV_GEMINI_API_KEY,
    ENV_GEMINI_ENABLED,
    ENV_GEMINI_MODEL,
    ENV_GEMINI_API_BASE,
    ENV_GEMINI_TIMEOUT,
    ENV_GEMINI_TEMPERATURE,
    ENV_GEMINI_MAX_OUTPUT_TOKENS,
)


def brain_env_var_names() -> tuple[str, ...]:
    """Every environment variable the Brain reads, for docs and diagnostics."""
    return (ENV_LLM_PROVIDER, ENV_LOG_ENABLED, ENV_LOG_LEVEL, ENV_LOG_FORMAT) + (
        GEMINI_ENV_VARS
    )


def resolve_llm_provider(
    explicit: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> str:
    """Resolve which LLM provider the Brain should use.

    An explicit argument (a ``--provider`` flag) always wins, then
    ``BRAIN_LLM_PROVIDER``, then the deterministic default. An explicitly empty
    value is treated as absent so a blank environment variable cannot select a
    provider named ``""``.

    The name is returned, not instantiated: an unknown name still fails loudly
    at :func:`create_provider` rather than being silently downgraded here.
    """
    source = os.environ if env is None else env
    for candidate in (explicit, source.get(ENV_LLM_PROVIDER)):
        if candidate is not None and candidate.strip():
            return candidate.strip()
    return DEFAULT_PROVIDER


@dataclass(frozen=True)
class LogSettings:
    """Resolved observability settings."""

    enabled: bool = False
    level: str = DEFAULT_LOG_LEVEL
    json_format: bool = True

    @property
    def level_name(self) -> str:
        return self.level.upper()


def log_settings(
    *,
    enabled: bool | None = None,
    level: str | None = None,
    log_format: str | None = None,
    env: Mapping[str, str] | None = None,
) -> LogSettings:
    """Resolve observability settings from arguments then environment.

    An unrecognised level or format falls back to the default instead of
    raising: bad observability configuration must never stop the Brain from
    serving requests.
    """
    source = os.environ if env is None else env

    if enabled is None:
        enabled = (source.get(ENV_LOG_ENABLED) or "").strip().lower() in _TRUTHY

    resolved_level = (level or source.get(ENV_LOG_LEVEL) or "").strip().lower()
    if resolved_level not in _LOG_LEVELS:
        resolved_level = DEFAULT_LOG_LEVEL

    resolved_format = (
        (log_format or source.get(ENV_LOG_FORMAT) or "").strip().lower()
    )
    if resolved_format not in _LOG_FORMATS:
        resolved_format = DEFAULT_LOG_FORMAT

    return LogSettings(
        enabled=enabled,
        level=resolved_level,
        json_format=resolved_format == "json",
    )


DEFAULT_ENV_FILENAME = ".env"
ENV_FILE_POINTER = "BRAIN_ENV_FILE"


def env_file_candidates(
    explicit: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> list[Path]:
    """Where a local ``.env`` may live, most specific first.

    Precedence: an explicit argument, then ``BRAIN_ENV_FILE``, then the working
    directory, then the repository root. The first two are single candidates, so
    naming one file means nothing else is read.

    ``BRAIN_ENV_FILE`` exists for the case where a checkout keeps its
    credentials in another worktree's ``.env``: a demo runner can point every
    service at one file without copying or printing it.
    """
    if explicit is not None:
        return [Path(explicit)]
    source = os.environ if env is None else env
    pointer = (source.get(ENV_FILE_POINTER) or "").strip()
    if pointer:
        return [Path(pointer)]
    candidates = [Path.cwd() / DEFAULT_ENV_FILENAME]
    # core/config.py -> core/ -> repository root
    repo_root = Path(__file__).resolve().parents[1]
    root_env = repo_root / DEFAULT_ENV_FILENAME
    if root_env not in candidates:
        candidates.append(root_env)
    return candidates


def load_env_file(
    explicit: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path | None:
    """Load a local ``.env`` into the process environment. Returns its path.

    The point of this is that the Brain is a plain process: it reads
    ``os.environ`` and nothing else, so a developer who filled in ``.env`` would
    otherwise still get a silent heuristic fallback. Precedence is
    **environment over file**, so an exported variable or a CI secret always
    wins and a ``.env`` can only fill gaps.

    Values are never returned, logged or echoed — only the path is, and only the
    path is returned. ``override`` stays false for that same reason: a file must
    never be able to displace a real environment variable.

    If ``python-dotenv`` is not installed the Brain keeps working from the
    environment alone, and the caller is told no file was loaded rather than
    being handed a broken configuration.
    """
    target_env = os.environ if env is None else env
    del target_env  # documented precedence; the real work is done by dotenv

    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - exercised only without the extra
        return None

    for candidate in env_file_candidates(explicit, env=env):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return candidate
    return None
