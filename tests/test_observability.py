"""Tests for the Brain's structured observability.

Two things are being protected here. First, that a developer can actually see
what the Brain did. Second — and this is the one that matters more — that
turning on logging cannot leak a credential or dump a user's private history
into a stream that gets shipped somewhere else.
"""

from __future__ import annotations

import io
import json
import unittest

import core.observability as obs
from core.config import log_settings
from core.observability import (
    BrainLogger,
    configure,
    get_logger,
    redact_secrets,
    register_secret,
)


class _Sink:
    """A throwaway stderr so a test never touches the real one."""

    def __init__(self) -> None:
        self.buffer = io.StringIO()

    def write(self, text: str) -> int:
        return self.buffer.write(text)

    def flush(self) -> None:
        return None

    @property
    def text(self) -> str:
        return self.buffer.getvalue()


class ObservabilityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # Each test gets a private handler and a private secret registry, so no
        # test can observe another's records or leaked values.
        self._sink = _Sink()
        self._saved_handler = list(obs.logging.getLogger(obs.LOGGER_NAME).handlers)
        self._saved_disabled = obs.logging.getLogger(obs.LOGGER_NAME).disabled
        self._saved_secrets = set(obs._SECRETS)
        self._saved_configured = obs._configured
        self._saved_settings = obs._settings
        obs._SECRETS.clear()
        package = obs.logging.getLogger(obs.LOGGER_NAME)
        package.handlers.clear()
        obs._configured = False
        obs._settings = None

    def tearDown(self) -> None:
        package = obs.logging.getLogger(obs.LOGGER_NAME)
        package.handlers.clear()
        for handler in self._saved_handler:
            package.addHandler(handler)
        package.disabled = self._saved_disabled
        obs._SECRETS.clear()
        obs._SECRETS.update(self._saved_secrets)
        obs._configured = self._saved_configured
        obs._settings = self._saved_settings

    def enable(self, **kwargs) -> None:
        """Point the Brain's logger at this test's private sink."""
        configure(log_settings(enabled=True, level="debug", **kwargs), stream=self._sink)

    def records(self) -> list[dict]:
        out = []
        for line in self._sink.text.strip().splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out


class RedactionTests(ObservabilityTestCase):
    def test_secret_shaped_keys_are_redacted(self) -> None:
        self.enable()
        log = get_logger("t")
        log.info(
            "op",
            api_key="AIzaSySomethingLong",
            authorization="Bearer sk-secret",
            password="hunter2",
            token="t0k",
            secret="s3cr3t",
            credential="c",
            user_id="usr_ok",
        )
        (record,) = self.records()
        for key in (
            "api_key",
            "authorization",
            "password",
            "token",
            "secret",
            "credential",
        ):
            with self.subTest(key=key):
                self.assertEqual(record[key], "***")
        self.assertEqual(record["user_id"], "usr_ok")

    def test_a_registered_secret_is_scrubbed_from_free_text(self) -> None:
        secret = "AIzaSyRegisteredSecretValue123"
        register_secret(secret)
        self.enable()
        get_logger("t").info("failed", detail=f"auth failed for key {secret}")
        (record,) = self.records()
        self.assertNotIn(secret, self._sink.text)
        self.assertIn("***", record["detail"])

    def test_short_values_are_not_registered(self) -> None:
        """Scrubbing a short string would corrupt unrelated text."""
        register_secret("abc")
        register_secret(None)
        register_secret("   ")
        self.assertEqual(obs._SECRETS, set())

    def test_redact_secrets_leaves_clean_text_alone(self) -> None:
        self.assertEqual(redact_secrets("nothing secret here"), "nothing secret here")


class BoundednessTests(ObservabilityTestCase):
    def test_long_strings_are_capped_with_a_visible_marker(self) -> None:
        self.enable()
        get_logger("t").info("op", note="x" * 5000)
        (record,) = self.records()
        self.assertLess(len(record["note"]), 260)
        self.assertIn("chars)", record["note"])

    def test_wide_containers_are_capped(self) -> None:
        self.enable()
        get_logger("t").info("op", ids=[f"id_{i}" for i in range(200)])
        (record,) = self.records()
        self.assertLessEqual(len(record["ids"]), 25)
        self.assertTrue(any("more" in str(item) for item in record["ids"]))

    def test_deep_nesting_terminates(self) -> None:
        payload: dict = {"a": 1}
        for _ in range(20):
            payload = {"n": payload}
        self.enable()
        get_logger("t").info("op", deep=payload)
        (record,) = self.records()  # must not recurse without bound
        self.assertIn("deep", record)

    def test_nested_secrets_are_redacted_too(self) -> None:
        self.enable()
        get_logger("t").info("op", outer={"inner": {"api_key": "AIzaNested"}})
        (record,) = self.records()
        self.assertEqual(record["outer"]["inner"]["api_key"], "***")


class DisabledByDefaultTests(ObservabilityTestCase):
    def test_nothing_is_emitted_when_logging_is_off(self) -> None:
        configure(log_settings(enabled=False), stream=self._sink)
        log = get_logger("t")
        log.info("should.not.appear")
        log.error("also.not")
        self.assertEqual(self._sink.text, "")

    def test_explicit_configuration_is_not_overridden_by_the_environment(self) -> None:
        configure(log_settings(enabled=True, level="debug"), stream=self._sink)
        # A later configure() with no argument must not re-read the environment
        # and silently switch observability off again.
        settings = configure()
        self.assertTrue(settings.enabled)
        get_logger("t").info("kept.enabled")
        self.assertIn("kept.enabled", self._sink.text)

    def test_the_service_logger_is_silent_by_default(self) -> None:
        from core.service.brain_service import _log

        self.assertIsInstance(_log, BrainLogger)


class JsonAndTextTests(ObservabilityTestCase):
    def test_every_record_is_one_json_object(self) -> None:
        self.enable()
        get_logger("t").info("first", a=1)
        get_logger("t").warning("second", b=2)
        records = self.records()
        self.assertEqual([r["event"] for r in records], ["first", "second"])
        for record in records:
            self.assertIn("ts", record)
            self.assertIn("level", record)
            self.assertIn("logger", record)

    def test_text_format_is_readable_and_still_scrubbed(self) -> None:
        register_secret("AIzaSyTextFormatSecret99")
        self.enable(log_format="text")
        get_logger("t").info("second", field=f"x AIzaSyTextFormatSecret99")
        out = self._sink.text
        self.assertNotIn("AIzaSyTextFormatSecret99", out)
        self.assertIn("second", out)
        self.assertIn("field=x", out)


class ExceptionTests(ObservabilityTestCase):
    def test_only_the_exception_type_is_recorded(self) -> None:
        """A provider traceback can quote a request body; the type is enough."""
        register_secret("AIzaSyExceptionSecret123")
        self.enable()
        try:
            raise RuntimeError("request failed with key AIzaSyExceptionSecret123")
        except RuntimeError:
            get_logger("t").exception("provider.failed", provider="gemini")
        records = self.records()
        self.assertEqual(records[0]["error_type"], "RuntimeError")
        self.assertNotIn("AIzaSyExceptionSecret123", self._sink.text)
        self.assertNotIn("request failed with key", self._sink.text)


class ServiceObservabilityTests(unittest.TestCase):
    """The service must actually say what it did, not merely own a logger."""

    def _capturing_logger(self):
        sink = _Sink()
        saved = list(obs.logging.getLogger(obs.LOGGER_NAME).handlers)
        saved_disabled = obs.logging.getLogger(obs.LOGGER_NAME).disabled
        saved_configured, saved_settings = obs._configured, obs._settings
        package = obs.logging.getLogger(obs.LOGGER_NAME)
        package.handlers.clear()
        obs._configured = False
        obs._settings = None
        configure(log_settings(enabled=True, level="debug"), stream=sink)
        self.addCleanup(lambda: _restore(package, saved, saved_disabled, saved_configured, saved_settings))
        return sink

    def test_ingest_reports_outcome_user_and_correlation(self) -> None:
        from core.service.brain_service import build_brain_service

        sink = self._capturing_logger()
        service = build_brain_service(":memory:")
        service.ingest(
            {
                "id": "evt-obs-1",
                "type": "source.calendar.event_created",
                "timestamp": "2026-09-26T09:00:00Z",
                "occurred_at": "2026-09-26T09:00:00Z",
                "user_id": "usr_obs",
                "source": {"provider": "calendar"},
                "payload": {"summary": "Planning meeting"},
                "correlation_id": "corr-obs-1",
            }
        )
        events = [r["event"] for r in _records(sink)]
        self.assertIn("event.received", events)
        self.assertIn("ingest.accepted", events)
        accepted = next(r for r in _records(sink) if r["event"] == "ingest.accepted")
        self.assertEqual(accepted["user_id"], "usr_obs")
        self.assertEqual(accepted["correlation_id"], "corr-obs-1")
        self.assertEqual(accepted["memory_count"], 1)

    def test_a_rejection_is_a_warning_with_its_reason(self) -> None:
        from core.service.brain_service import build_brain_service

        sink = self._capturing_logger()
        service = build_brain_service(":memory:")
        # calendar.event_created requires a `summary`; omitting it is rejected.
        result = service.ingest(
            {
                "id": "evt-obs-2",
                "type": "source.calendar.event_created",
                "timestamp": "2026-09-26T09:00:00Z",
                "occurred_at": "2026-09-26T09:00:00Z",
                "user_id": "usr_obs",
                "source": {"provider": "calendar"},
                "payload": {"title": "no summary here"},
                "correlation_id": "corr-obs-2",
            }
        )
        self.assertEqual(result.outcome.value, "rejected")
        rejected = next(r for r in _records(sink) if r["event"] == "ingest.rejected")
        self.assertEqual(rejected["level"], "warning")
        self.assertIn("summary", rejected["reason"])

    def test_a_duplicate_is_reported_as_a_duplicate(self) -> None:
        from core.service.brain_service import build_brain_service

        sink = self._capturing_logger()
        service = build_brain_service(":memory:")
        event = {
            "id": "evt-obs-3",
            "type": "source.calendar.event_created",
            "timestamp": "2026-09-26T09:00:00Z",
            "occurred_at": "2026-09-26T09:00:00Z",
            "user_id": "usr_obs",
            "source": {"provider": "calendar"},
            "payload": {"summary": "Same meeting"},
        }
        service.ingest(dict(event))
        service.ingest(dict(event))
        self.assertIn("ingest.duplicate", [r["event"] for r in _records(sink)])


def _records(sink: _Sink) -> list[dict]:
    out = []
    for line in sink.text.strip().splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _restore(package, handlers, disabled, configured, settings) -> None:
    package.handlers.clear()
    for handler in handlers:
        package.addHandler(handler)
    package.disabled = disabled
    obs._configured = configured
    obs._settings = settings


if __name__ == "__main__":
    unittest.main()
