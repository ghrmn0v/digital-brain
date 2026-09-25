"""Public error mapping for Core module input errors (Phase 8 hardening).

Core modules own the detailed input rules (bounded non-empty ids, known
preference domains, usable person names). A caller that breaks one of those
rules must receive a typed ``validation_error`` — never an opaque
``internal_error`` that hides the real reason.
"""

from __future__ import annotations

import unittest

from contracts.api import ApiErrorCode

from core import BrainApi, build_brain_service


class PublicValidationErrorMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = build_brain_service(":memory:")
        self.addCleanup(self.service.close)
        self.api = BrainApi(self.service)

    def call(self, method: str, params: dict, request_id: str = "1"):
        return self.api.handle(
            {"id": request_id, "method": method, "version": "v1", "params": params}
        )

    def test_blank_user_id_is_a_validation_error_not_an_internal_one(self) -> None:
        cases = (
            ("preferences", {"user_id": "   "}),
            ("developer_preferences", {"user_id": "   "}),
            ("people_summary", {"user_id": "   "}),
            ("learning_status", {"user_id": "   "}),
            ("feedback_history", {"user_id": "   "}),
            ("personalization_profile", {"user_id": "   "}),
            ("record_preference", {"user_id": "   ", "name": "n", "value": "v"}),
            ("people_timeline", {"user_id": "   ", "person_id": "per_ali"}),
            ("resolve_person", {"user_id": "   ", "name": "Ali"}),
        )
        for method, params in cases:
            with self.subTest(method=method):
                response = self.call(method, params)
                self.assertFalse(response.ok)
                self.assertEqual(response.error.code, ApiErrorCode.VALIDATION_ERROR)
                self.assertNotEqual(response.error.code, ApiErrorCode.INTERNAL_ERROR)
                self.assertNotIn("internal failure", response.error.message)

    def test_blank_preference_name_and_value_are_validation_errors(self) -> None:
        for params in (
            {"user_id": "usr_a", "name": "   ", "value": "v"},
            {"user_id": "usr_a", "name": "n", "value": "   "},
        ):
            with self.subTest(params=params):
                response = self.call("record_preference", params)
                self.assertFalse(response.ok)
                self.assertEqual(response.error.code, ApiErrorCode.VALIDATION_ERROR)

    def test_blank_person_id_is_a_validation_error(self) -> None:
        response = self.call("people_timeline", {"user_id": "usr_a", "person_id": "   "})
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.VALIDATION_ERROR)

    def test_oversized_user_id_is_a_validation_error(self) -> None:
        response = self.call("people_summary", {"user_id": "u" * 513})
        # The typed contract rejects the length before the service is reached.
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.VALIDATION_ERROR)

    def test_valid_requests_still_succeed_after_the_mapping_change(self) -> None:
        self.assertTrue(self.call("preferences", {"user_id": "usr_a"}).ok)
        self.assertTrue(self.call("people_summary", {"user_id": "usr_a"}).ok)
        self.assertTrue(
            self.call("learning_status", {"user_id": "usr_a"}).ok
        )
        self.assertTrue(
            self.call(
                "record_preference",
                {"user_id": "usr_a", "name": "language", "value": "Python"},
            ).ok
        )

    def test_unknown_method_still_reports_unknown_method(self) -> None:
        response = self.call("definitely_not_a_method", {})
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.UNKNOWN_METHOD)


if __name__ == "__main__":
    unittest.main()
