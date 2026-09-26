"""Tests for the Brain's own configuration surface.

The Brain reads its environment in exactly one module, and every accessor takes
the mapping it should read. These tests pin the two properties that matter:
precedence is deterministic, and bad configuration degrades instead of raising,
because configuration must never be able to stop the Brain from serving.
"""

from __future__ import annotations

import unittest

from core.config import (
    DEFAULT_PROVIDER,
    ENV_LLM_PROVIDER,
    ENV_LOG_ENABLED,
    ENV_LOG_FORMAT,
    ENV_LOG_LEVEL,
    GEMINI_ENV_VARS,
    brain_env_var_names,
    log_settings,
    resolve_llm_provider,
)


class ProviderResolutionTests(unittest.TestCase):
    def test_default_is_the_deterministic_provider(self) -> None:
        self.assertEqual(resolve_llm_provider(env={}), DEFAULT_PROVIDER)
        self.assertEqual(DEFAULT_PROVIDER, "heuristic")

    def test_explicit_argument_beats_the_environment(self) -> None:
        resolved = resolve_llm_provider("gemini", env={ENV_LLM_PROVIDER: "heuristic"})
        self.assertEqual(resolved, "gemini")

    def test_environment_is_used_when_no_argument_is_given(self) -> None:
        resolved = resolve_llm_provider(None, env={ENV_LLM_PROVIDER: "gemini"})
        self.assertEqual(resolved, "gemini")

    def test_values_are_trimmed(self) -> None:
        self.assertEqual(resolve_llm_provider("  gemini  ", env={}), "gemini")

    def test_a_blank_value_is_treated_as_absent(self) -> None:
        """A stray empty variable must not select a provider named ""."""
        for blank in ("", "   ", "\t"):
            with self.subTest(blank=blank):
                self.assertEqual(
                    resolve_llm_provider(None, env={ENV_LLM_PROVIDER: blank}),
                    DEFAULT_PROVIDER,
                )

    def test_an_unknown_name_is_not_silently_downgraded(self) -> None:
        """Resolution returns the name; failing loudly is the factory's job.

        Downgrading here would hide a typo behind a silent behaviour change.
        """
        from core.understanding.providers import create_provider

        self.assertEqual(resolve_llm_provider("nope", env={}), "nope")
        with self.assertRaises(Exception):
            create_provider("nope")


class LogSettingsTests(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        settings = log_settings(env={})
        self.assertFalse(settings.enabled)

    def test_truthy_values_enable(self) -> None:
        for value in ("1", "true", "TRUE", "yes", "on"):
            with self.subTest(value=value):
                self.assertTrue(log_settings(env={ENV_LOG_ENABLED: value}).enabled)

    def test_falsy_values_do_not_enable(self) -> None:
        for value in ("0", "false", "no", "off", "", "maybe"):
            with self.subTest(value=value):
                self.assertFalse(log_settings(env={ENV_LOG_ENABLED: value}).enabled)

    def test_level_and_format_are_read(self) -> None:
        settings = log_settings(
            env={ENV_LOG_LEVEL: "debug", ENV_LOG_FORMAT: "text"}
        )
        self.assertEqual(settings.level, "debug")
        self.assertEqual(settings.level_name, "DEBUG")
        self.assertFalse(settings.json_format)

    def test_bad_values_fall_back_instead_of_raising(self) -> None:
        """Observability misconfiguration must not stop the Brain serving."""
        settings = log_settings(
            env={ENV_LOG_LEVEL: "LOUD", ENV_LOG_FORMAT: "yaml"}
        )
        self.assertEqual(settings.level, "info")
        self.assertTrue(settings.json_format)

    def test_explicit_arguments_win(self) -> None:
        settings = log_settings(
            enabled=True,
            level="error",
            log_format="text",
            env={ENV_LOG_LEVEL: "debug", ENV_LOG_ENABLED: "0"},
        )
        self.assertTrue(settings.enabled)
        self.assertEqual(settings.level, "error")
        self.assertFalse(settings.json_format)


class EnvInventoryTests(unittest.TestCase):
    def test_gemini_vars_are_the_documented_seven(self) -> None:
        self.assertEqual(
            set(GEMINI_ENV_VARS),
            {
                "GEMINI_API_KEY",
                "GEMINI_ENABLED",
                "GEMINI_MODEL",
                "GEMINI_API_BASE",
                "GEMINI_TIMEOUT_SECONDS",
                "GEMINI_TEMPERATURE",
                "GEMINI_MAX_OUTPUT_TOKENS",
            },
        )

    def test_the_inventory_contains_no_other_services_secrets(self) -> None:
        """The Brain must not read another owner's credentials.

        Product and Fly keep their own secrets; if one of their variable names
        ever appears here, the Brain has started depending on their config.
        """
        foreign_markers = (
            "PRODUCT",
            "FLY",
            "CONNECTOME",
            "DATABASE_URL",
            "SERVICE_API_TOKEN",
            "CORE_BRAIN",
            "LINKEDIN",
            "WHATSAPP_TOKEN",
        )
        for name in brain_env_var_names():
            for marker in foreign_markers:
                with self.subTest(name=name, marker=marker):
                    self.assertNotIn(marker, name)

    def test_inventory_is_the_union_of_brain_vars(self) -> None:
        names = brain_env_var_names()
        self.assertEqual(len(names), len(set(names)))
        for expected in (ENV_LLM_PROVIDER, ENV_LOG_ENABLED, ENV_LOG_LEVEL, ENV_LOG_FORMAT):
            self.assertIn(expected, names)
        for expected in GEMINI_ENV_VARS:
            self.assertIn(expected, names)


class GeminiConfigTests(unittest.TestCase):
    def test_defaults_apply_without_any_environment(self) -> None:
        from core.understanding.gemini import GeminiConfig

        config = GeminiConfig.from_env(env={})
        self.assertEqual(config.api_key, "")
        self.assertFalse(config.enabled)
        self.assertFalse(config.is_configured)
        self.assertEqual(config.model, "gemini-3.8-flash")
        self.assertEqual(config.temperature, 0.2)
        self.assertEqual(config.max_output_tokens, 2048)

    def test_a_key_alone_does_not_enable_the_provider(self) -> None:
        """Explicit opt-in, so a stray key cannot start sending data out."""
        from core.understanding.gemini import GeminiConfig

        config = GeminiConfig.from_env(
            env={"GEMINI_API_KEY": "k" * 20, "GEMINI_ENABLED": "false"}
        )
        self.assertFalse(config.is_configured)

    def test_enabled_and_keyed_is_ready(self) -> None:
        from core.understanding.gemini import GeminiConfig

        config = GeminiConfig.from_env(
            env={"GEMINI_API_KEY": "k" * 20, "GEMINI_ENABLED": "1"}
        )
        self.assertTrue(config.is_configured)

    def test_redacted_never_shows_the_key(self) -> None:
        from core.understanding.gemini import GeminiConfig

        secret = "AIza-not-a-real-key-000000"
        config = GeminiConfig.from_env(
            env={"GEMINI_API_KEY": secret, "GEMINI_ENABLED": "1"}
        )
        self.assertNotIn(secret, config.redacted().api_key)


if __name__ == "__main__":
    unittest.main()
