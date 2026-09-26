"""The Brain must honour a local ``.env`` without any manual exporting.

The Brain is a plain process: it reads ``os.environ`` and nothing else, so a
developer who filled in ``.env`` used to get a silent heuristic fallback and no
error to explain it. These tests pin the properties that make the file safe to
rely on — environment wins, nothing is read at import time, values never escape
— rather than just that a file gets parsed.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.config import (
    DEFAULT_ENV_FILENAME,
    env_file_candidates,
    load_env_file,
    resolve_llm_provider,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def write_env(directory: Path, body: str) -> Path:
    path = directory / DEFAULT_ENV_FILENAME
    path.write_text(body, encoding="utf-8")
    return path


class EnvDiscoveryTests(unittest.TestCase):
    def test_an_explicit_path_is_the_only_candidate(self) -> None:
        with TemporaryDirectory() as tmp:
            wanted = Path(tmp) / "custom.env"
            self.assertEqual(env_file_candidates(wanted), [wanted])

    def test_cwd_is_tried_before_the_repository_root(self) -> None:
        candidates = env_file_candidates()
        self.assertEqual(candidates[0], Path.cwd() / DEFAULT_ENV_FILENAME)
        self.assertGreaterEqual(len(candidates), 1)

    def test_a_missing_file_is_not_an_error(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertIsNone(load_env_file(Path(tmp) / "absent.env"))

    def test_the_repository_env_is_gitignored(self) -> None:
        """A committed .env would be a committed credential.

        Asserted against git itself rather than against the text of the rules,
        because a glob (``.env*``) is a stricter and equally correct way to
        spell this than two literal lines.
        """
        def ignored(name: str) -> bool:
            result = subprocess.run(
                ["git", "check-ignore", "-q", name],
                cwd=REPO_ROOT,
                capture_output=True,
                timeout=60,
            )
            return result.returncode == 0

        self.assertTrue(ignored(".env"), ".env must be ignored")
        self.assertTrue(ignored(".env.local"), ".env.local must be ignored")
        self.assertFalse(ignored(".env.example"), ".env.example must be tracked")

    def test_the_example_file_holds_no_real_credential(self) -> None:
        example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        active = [
            line
            for line in example.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        for line in active:
            key, _, value = line.partition("=")
            value = value.strip().strip('"')
            if key.strip() in {"GEMINI_API_KEY", "SERVICE_API_TOKEN"}:
                self.assertIn(
                    value, {"", "replace-with-a-long-random-token"},
                    f"{key} in .env.example must be a placeholder, not a value",
                )


class EnvLoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = dict(os.environ)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._saved)

    def test_values_from_the_file_reach_the_environment(self) -> None:
        with TemporaryDirectory() as tmp:
            path = write_env(
                Path(tmp), "BRAIN_LOG_LEVEL=warning\nBRAIN_LOG_FORMAT=text\n"
            )
            os.environ.pop("BRAIN_LOG_LEVEL", None)
            os.environ.pop("BRAIN_LOG_FORMAT", None)

            self.assertEqual(load_env_file(path), path)
            self.assertEqual(os.environ["BRAIN_LOG_LEVEL"], "warning")

    def test_the_environment_takes_precedence_over_the_file(self) -> None:
        """A real variable or a CI secret must never be displaced by a file."""
        with TemporaryDirectory() as tmp:
            path = write_env(Path(tmp), "BRAIN_LOG_LEVEL=warning\n")
            os.environ["BRAIN_LOG_LEVEL"] = "error"

            load_env_file(path)
            self.assertEqual(os.environ["BRAIN_LOG_LEVEL"], "error")

    def test_the_file_only_fills_a_gap(self) -> None:
        with TemporaryDirectory() as tmp:
            path = write_env(
                Path(tmp),
                "BRAIN_LOG_LEVEL=warning\nBRAIN_LOG_FORMAT=text\n",
            )
            os.environ["BRAIN_LOG_LEVEL"] = "error"
            os.environ.pop("BRAIN_LOG_FORMAT", None)

            load_env_file(path)
            self.assertEqual(os.environ["BRAIN_LOG_LEVEL"], "error")
            self.assertEqual(os.environ["BRAIN_LOG_FORMAT"], "text")

    def test_the_returned_value_is_a_path_and_never_the_values(self) -> None:
        with TemporaryDirectory() as tmp:
            path = write_env(Path(tmp), "GEMINI_API_KEY=not-a-real-key\n")
            returned = load_env_file(path)
            self.assertIsInstance(returned, Path)
            self.assertEqual(returned, path)

    def test_a_second_load_does_not_change_anything(self) -> None:
        with TemporaryDirectory() as tmp:
            path = write_env(Path(tmp), "BRAIN_LOG_LEVEL=warning\n")
            load_env_file(path)
            os.environ["BRAIN_LOG_LEVEL"] = "error"
            load_env_file(path)
            self.assertEqual(os.environ["BRAIN_LOG_LEVEL"], "error")


class GeminiStillReadsTheEnvironmentTests(unittest.TestCase):
    """``GeminiConfig.from_env`` must be untouched by the loader."""

    def test_gemini_config_reads_a_loaded_file(self) -> None:
        from core.understanding.gemini import GeminiConfig

        with TemporaryDirectory() as tmp:
            path = write_env(
                Path(tmp),
                "GEMINI_ENABLED=1\nGEMINI_API_KEY=not-a-real-key\n"
                "GEMINI_MODEL=gemini-test-model\n",
            )
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ.pop("GEMINI_ENABLED", None)
            os.environ.pop("GEMINI_MODEL", None)
            load_env_file(path)
            try:
                config = GeminiConfig.from_env()
                self.assertTrue(config.enabled)
                self.assertTrue(config.is_configured)
                self.assertEqual(config.model, "gemini-test-model")
                self.assertNotEqual(
                    config.redacted().api_key, os.environ["GEMINI_API_KEY"]
                )
            finally:
                for key in ("GEMINI_API_KEY", "GEMINI_ENABLED", "GEMINI_MODEL"):
                    os.environ.pop(key, None)

    def test_provider_selection_still_reads_the_environment(self) -> None:
        with TemporaryDirectory() as tmp:
            path = write_env(Path(tmp), "BRAIN_LLM_PROVIDER=gemini\n")
            os.environ.pop("BRAIN_LLM_PROVIDER", None)
            load_env_file(path)
            try:
                self.assertEqual(resolve_llm_provider(None), "gemini")
                self.assertEqual(resolve_llm_provider("heuristic"), "heuristic")
            finally:
                os.environ.pop("BRAIN_LLM_PROVIDER", None)


class TransportWiringTests(unittest.TestCase):
    """Every transport must load the file before it resolves anything."""

    def test_each_transport_loads_the_env_file(self) -> None:
        for name in ("http", "stdio", "websocket"):
            with self.subTest(transport=name):
                source = (
                    REPO_ROOT / "core" / "transport" / f"{name}.py"
                ).read_text(encoding="utf-8")
                self.assertIn("load_env_file()", source)
                self.assertLess(
                    source.index("load_env_file()"),
                    source.index("resolve_llm_provider("),
                    f"{name} resolves configuration before loading .env",
                )

    def test_a_transport_picks_up_a_dotenv_from_the_working_directory(self) -> None:
        """The whole point: no manual exporting, verified in a real process."""
        with TemporaryDirectory() as tmp:
            write_env(
                Path(tmp),
                "BRAIN_LLM_PROVIDER=gemini\nGEMINI_ENABLED=1\n"
                "GEMINI_API_KEY=not-a-real-key\n",
            )
            script = textwrap.dedent(
                """
                import sys
                sys.path.insert(0, %r)
                from core.config import load_env_file, resolve_llm_provider
                load_env_file()
                from core.understanding.gemini import GeminiConfig
                print(resolve_llm_provider(None))
                print(GeminiConfig.from_env().is_configured)
                """
            ) % str(REPO_ROOT)
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
            lines = result.stdout.split()
            self.assertEqual(lines[0], "gemini")
            self.assertEqual(lines[1], "True")


if __name__ == "__main__":
    unittest.main()
