"""Static parity between the Java client and the canonical contract.

This environment cannot compile or run Java (JRE only, no ``javac``, no
``jdk.compiler`` module), so this test does **not** claim the Java client
builds. It proves the narrower, mechanically checkable property: the Java
sources name the same methods, paths and error codes that the Core publishes,
and they do not reference anything the contract no longer has.

Compilation and behaviour remain unverified; see ``clients/java/README.md``.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from contracts.api import ApiErrorCode
from contracts.api.methods import ApiMethod
from contracts.api.params import ResolvePersonParams, UserParams
from contracts.api.params import PeopleTimelineParams
from contracts.api.results import PersonResolutionWire

REPO_ROOT = Path(__file__).resolve().parents[1]
JAVA_ROOT = REPO_ROOT / "clients" / "java"
JAVA_SOURCES = sorted(
    path
    for path in (JAVA_ROOT / "src" / "main" / "java").rglob("*.java")
)


def java_sources() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in JAVA_SOURCES)


def java_method_table() -> list[str]:
    """The method names the Java client advertises, in order."""
    block = re.search(
        r"public static List<String> knownMethods\(\).*?Collections\.addAll\("
        r"\s*methods,\s*(.*?)\);",
        java_sources(),
        re.DOTALL,
    )
    if block is None:
        raise AssertionError("could not find the Java method table")
    return re.findall(r'"([^"]+)"', block.group(1))


class JavaClientParityTests(unittest.TestCase):
    def test_client_sources_exist(self) -> None:
        self.assertTrue(JAVA_SOURCES, "no Java sources found under clients/java")
        names = {path.name for path in JAVA_SOURCES}
        self.assertEqual(
            names,
            {
                "Json.java",
                "BrainApiException.java",
                "BrainRequests.java",
                "BrainHttpClient.java",
                "BrainWebSocketClient.java",
                "BrainClient.java",
                "SelfCheck.java",
            },
        )

    def test_every_api_method_is_listed_in_the_java_client(self) -> None:
        listed = java_method_table()
        for method in ApiMethod:
            with self.subTest(method=method.value):
                self.assertIn(method.value, listed)

    def test_the_java_method_table_matches_the_registry_exactly(self) -> None:
        self.assertEqual(java_method_table(), [method.value for method in ApiMethod])

    def test_the_java_method_count_is_17(self) -> None:
        self.assertEqual(len(java_method_table()), 17)
        self.assertEqual(len(set(java_method_table())), 17)

    def test_the_endpoint_paths_match_the_core_transports(self) -> None:
        source = java_sources()
        self.assertIn('API_PATH = "/v1/brain"', source)
        self.assertIn('"/health"', source)
        self.assertIn('API_VERSION = "v1"', source)
        self.assertIn("user_id=", source)

    def test_canonical_error_codes_are_used(self) -> None:
        # The client branches on the two caller-side codes; every literal error
        # code it mentions must exist in the canonical vocabulary.
        source = java_sources()
        for code in ("validation_error", "bad_request"):
            with self.subTest(code=code):
                found = [
                    path.name
                    for path in JAVA_SOURCES
                    if f'"{code}"' in path.read_text(encoding="utf-8")
                ]
                self.assertTrue(found, f"{code} is not used by the client")
        mentioned = set(re.findall(r'"([a-z_]+_error|[a-z_]+_method)"', source))
        self.assertTrue(mentioned.issubset(set(ApiErrorCode)), mentioned)

    def test_no_java_source_references_a_method_outside_the_registry(self) -> None:
        known = {method.value for method in ApiMethod}
        # Method-ish literals in the client must be real API methods.
        for path in JAVA_SOURCES:
            source = path.read_text(encoding="utf-8")
            for literal in re.findall(r'call\("([a-z_]+)"', source):
                with self.subTest(path=path.name, method=literal):
                    self.assertIn(literal, known)

    def test_resolve_person_params_and_result_shape_are_covered(self) -> None:
        source = java_sources()
        self.assertIn("resolve_person", source)
        params = set(ResolvePersonParams.model_fields)
        self.assertEqual({"user_id", "name", "aliases", "correlation_id"}, params)
        result = set(PersonResolutionWire.model_fields)
        self.assertEqual(
            {
                "user_id",
                "name",
                "person_id",
                "aliases",
                "created",
                "ambiguous",
                "candidates",
                "memory_id",
            },
            result,
        )
        self.assertEqual({"user_id", "person_id", "limit"}, set(PeopleTimelineParams.model_fields))
        self.assertEqual({"user_id"}, set(UserParams.model_fields))

    def test_the_client_has_no_third_party_imports(self) -> None:
        for path in JAVA_SOURCES:
            source = path.read_text(encoding="utf-8")
            for imported in re.findall(r"^import\s+([\w.]+);", source, re.MULTILINE):
                with self.subTest(path=path.name, imported=imported):
                    self.assertTrue(
                        imported.startswith("java.")
                        or imported.startswith("dev.digitalbrain.client"),
                        f"{path.name} imports {imported}",
                    )

    def test_pom_declares_no_dependencies(self) -> None:
        pom = (JAVA_ROOT / "pom.xml").read_text(encoding="utf-8")
        self.assertIn("<dependencies/>", pom)
        self.assertNotIn("<dependency>", pom)

    def test_java_readme_states_the_verification_limit(self) -> None:
        readme = (JAVA_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("NOT been compiled", readme)


class JavaClientAndSchemaTests(unittest.TestCase):
    def test_java_known_methods_equal_the_schema_bundle(self) -> None:
        listed = java_method_table()
        schema = json.loads(
            (REPO_ROOT / "contracts" / "schemas" / "brain-api.v1.json").read_text(
                encoding="utf-8"
            )
        )
        from_schema = [entry["method"] for entry in schema["x-methods"]]
        self.assertEqual(listed, from_schema)


if __name__ == "__main__":
    unittest.main()
