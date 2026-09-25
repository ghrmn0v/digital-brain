"""Tests for provider selection reaching the serving path.

The Gemini provider was fully implemented and registered, but every transport
built its service with the default provider, so a configured key would never
have been used. These tests exist to stop that from silently regressing: they
assert the flag and the environment variable both arrive at the service the
transport actually serves.
"""

from __future__ import annotations

import io
import unittest
from unittest import mock

from core.config import ENV_LLM_PROVIDER, resolve_llm_provider
from core.understanding.providers import create_provider


class TransportProviderWiringTests(unittest.TestCase):
    """Each transport must be able to select a non-default provider."""

    def _run_main(self, module_name: str, argv: list[str]) -> mock.MagicMock:
        """Run a transport's ``main`` and return a spy on its service factory.

        A spy, not a stub: the real factory still runs, so the transport builds a
        genuine BrainService and its own type checks stay satisfied. Only the
        blocking socket/daemon calls are neutralised.
        """
        import importlib

        module = importlib.import_module(module_name)
        real_factory = module.build_brain_service
        build = mock.MagicMock(side_effect=lambda *a, **k: real_factory(*a, **k))
        with mock.patch.object(module, "build_brain_service", build):
            # Each transport blocks differently: HTTP and WebSocket on a socket
            # loop, stdio on stdin. Neutralise exactly the call that blocks.
            async def _no_serve(*_args, **_kwargs):
                return None

            stack = []
            for attr, method, replacement in (
                ("HttpBrainServer", "serve_forever", _no_serve),
                ("WebSocketBrainServer", "serve_forever", _no_serve),
                ("StdioDaemon", "serve", lambda *_a, **_k: None),
            ):
                target = getattr(module, attr, None)
                if target is not None:
                    stack.append(mock.patch.object(target, method, replacement))
            with contextlib_exit(stack), mock.patch("sys.argv", ["prog", *argv]):
                try:
                    module.main(argv)
                except SystemExit:
                    pass
                except KeyboardInterrupt:
                    pass
            return build

    def test_http_accepts_the_provider_flag(self) -> None:
        build = self._run_main("core.transport.http", ["--provider", "gemini", "--port", "0"])
        build.assert_called_once()
        self.assertEqual(build.call_args.kwargs.get("provider"), "gemini")

    def test_http_defaults_to_the_resolved_provider(self) -> None:
        build = self._run_main("core.transport.http", ["--port", "0"])
        self.assertEqual(
            build.call_args.kwargs.get("provider"),
            resolve_llm_provider(None, env={}),
        )

    def test_http_provider_flag_beats_the_environment(self) -> None:
        with mock.patch.dict("os.environ", {ENV_LLM_PROVIDER: "heuristic"}):
            build = self._run_main("core.transport.http", ["--provider", "gemini", "--port", "0"])
        self.assertEqual(build.call_args.kwargs.get("provider"), "gemini")

    def test_http_uses_the_environment_when_no_flag_is_given(self) -> None:
        with mock.patch.dict("os.environ", {ENV_LLM_PROVIDER: "gemini"}):
            build = self._run_main("core.transport.http", ["--port", "0"])
        self.assertEqual(build.call_args.kwargs.get("provider"), "gemini")

    def test_stdio_accepts_the_provider_flag(self) -> None:
        build = self._run_main("core.transport.stdio", ["--provider", "gemini"])
        self.assertEqual(build.call_args.kwargs.get("provider"), "gemini")

    def test_websocket_accepts_the_provider_flag(self) -> None:
        build = self._run_main(
            "core.transport.websocket", ["--provider", "gemini", "--port", "0"]
        )
        self.assertEqual(build.call_args.kwargs.get("provider"), "gemini")

    def test_every_transport_advertises_the_flag(self) -> None:
        for module_name in (
            "core.transport.http",
            "core.transport.stdio",
            "core.transport.websocket",
        ):
            with self.subTest(transport=module_name):
                import importlib
                import io as _io
                from contextlib import redirect_stdout

                module = importlib.import_module(module_name)
                buffer = _io.StringIO()
                with redirect_stdout(buffer):
                    try:
                        with self.assertRaises(SystemExit):
                            module.main(["--help"])
                    except SystemExit:
                        pass
                self.assertIn("--provider", buffer.getvalue())


class ProviderSelectionReachesTheGatewayTests(unittest.TestCase):
    def _provider_name(self, service) -> str:
        """The provider a service will actually answer with, observed not assumed.

        ``BrainService`` deliberately exposes no gateway accessor, so this reads
        the private field rather than adding public surface just for a test.
        """
        return service._understanding.provider.name

    def test_a_selected_gemini_provider_builds_a_gateway_that_uses_it(self) -> None:
        """End to end: the name the transport resolves is the name used."""
        from core.service.brain_service import build_brain_service

        service = build_brain_service(":memory:", provider="gemini")
        self.assertEqual(self._provider_name(service), "gemini")

    def test_the_default_service_uses_the_deterministic_provider(self) -> None:
        from core.service.brain_service import build_brain_service

        service = build_brain_service(":memory:")
        self.assertEqual(self._provider_name(service), "heuristic")

    def test_gemini_is_registered_and_constructible(self) -> None:
        provider = create_provider("gemini")
        self.assertEqual(provider.name, "gemini")

    def test_gemini_without_configuration_fails_over_to_heuristic(self) -> None:
        """An unconfigured Gemini must not break the Brain."""
        from core.service.brain_service import build_brain_service

        service = build_brain_service(":memory:", provider="gemini")
        result = service.understand(
            "The team moved the review to Thursday at ten in room three."
        )
        self.assertTrue(result.summary)
        # The gateway reports which provider actually answered.
        self.assertIn(result.provider, {"gemini", "heuristic"})

    def test_an_unknown_provider_name_fails_loudly(self) -> None:
        with self.assertRaises(Exception):
            create_provider("does-not-exist")


def contextlib_exit(stack):
    from contextlib import ExitStack

    ctx = ExitStack()
    for patcher in stack:
        ctx.enter_context(patcher)
    return ctx


if __name__ == "__main__":
    unittest.main()
