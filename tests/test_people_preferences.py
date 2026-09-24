"""Tests for People Intelligence preferences (Phase 5): domain mapping,
record/write lifecycle and per-domain bounds."""

from __future__ import annotations

import unittest

from core.memory import MemoryCandidate
from core.people import (
    PeopleIntelligence,
    PeopleLimits,
    PeopleValidationError,
    Preference,
    PreferenceDomain,
)

from tests.memory_support import make_service


def make_intelligence(**kwargs):
    service = make_service()
    return service, PeopleIntelligence(service, writer=service, **kwargs)


def seed_preference(
    service,
    content,
    *,
    user_id="usr_a",
    name=None,
    domain=None,
    metadata=None,
    importance=None,
):
    meta = dict(metadata or {})
    meta["kind"] = "preference"
    if name is not None:
        meta["preference_name"] = name
    if domain is not None:
        meta["preference"] = f"{domain}:{name}"
        meta["domain"] = domain.value if isinstance(domain, PreferenceDomain) else domain
    else:
        meta["preference"] = f"pref:{name}"
    return service.create_memory(
        MemoryCandidate(
            content=content,
            user_id=user_id,
            importance=importance,
            metadata=meta,
        )
    )


class DomainClassificationTests(unittest.TestCase):
    def test_explicit_metadata_wins(self):
        svc, pi = make_intelligence()
        mem = seed_preference(
            svc, "write tests first", name="tdd", domain="testing"
        )
        prefs = pi.preferences("usr_a")
        self.assertEqual(prefs[0].domain, PreferenceDomain.TESTING)
        self.assertEqual(prefs[0].name, "tdd")
        self.assertEqual(prefs[0].value, "write tests first")
        self.assertIn(mem.memory_id, {p.memory_id for p in prefs})

    def test_keyword_mapping_for_all_domains(self):
        svc, pi = make_intelligence()
        cases = {
            "prefers python for backend": ("language", PreferenceDomain.LANGUAGE),
            "likes strict formatting rules": ("coding_style", PreferenceDomain.CODING_STYLE),
            "always writes pytest": ("testing", PreferenceDomain.TESTING),
            "wants concise explanations": ("explanation_detail", PreferenceDomain.EXPLANATION_DETAIL),
            "uses conventional commits": ("commit_style", PreferenceDomain.COMMIT_STYLE),
            "prefers automated deploy via CI": ("deployment", PreferenceDomain.DEPLOYMENT),
        }
        for content, (name, domain) in cases.items():
            seed_preference(svc, content, name=name)
        dev = pi.developer_preferences("usr_a")
        self.assertEqual({p.value for p in dev.languages}, {"prefers python for backend"})
        self.assertEqual({p.value for p in dev.coding_style}, {"likes strict formatting rules"})
        self.assertEqual({p.value for p in dev.testing}, {"always writes pytest"})
        self.assertEqual({p.value for p in dev.explanation_detail}, {"wants concise explanations"})
        self.assertEqual({p.value for p in dev.commit_style}, {"uses conventional commits"})
        self.assertEqual({p.value for p in dev.deployment}, {"prefers automated deploy via CI"})

    def test_general_preference_has_no_developer_domain(self):
        svc, pi = make_intelligence()
        seed_preference(svc, "likes dark mode ui", name="dark_mode")
        prefs = pi.preferences("usr_a")
        self.assertEqual(len(prefs), 1)
        self.assertIsNone(prefs[0].domain)
        dev = pi.developer_preferences("usr_a")
        for bucket in (
            dev.languages, dev.coding_style, dev.testing,
            dev.explanation_detail, dev.commit_style, dev.deployment,
        ):
            self.assertEqual(bucket, [])


class RecordPreferenceTests(unittest.TestCase):
    def test_record_preference_persists_and_reads(self):
        svc, pi = make_intelligence()
        recorded = pi.record_preference(
            "usr_a",
            name="explanation_detail",
            value="concise bullets",
            domain=PreferenceDomain.EXPLANATION_DETAIL,
            importance=0.8,
        )
        self.assertIsInstance(recorded, Preference)
        self.assertEqual(recorded.domain, PreferenceDomain.EXPLANATION_DETAIL)
        self.assertEqual(recorded.value, "concise bullets")
        read = pi.preferences("usr_a")
        self.assertEqual([p.memory_id for p in read], [recorded.memory_id])
        self.assertEqual(read[0].name, "explanation_detail")
        self.assertEqual(read[0].importance, 0.8)

    def test_record_general_preference(self):
        svc, pi = make_intelligence()
        pi.record_preference("usr_a", name="theme", value="dark")
        prefs = pi.preferences("usr_a")
        self.assertIsNone(prefs[0].domain)
        self.assertEqual(prefs[0].value, "dark")

    def test_record_again_supersedes_previous(self):
        svc, pi = make_intelligence()
        pi.record_preference(
            "usr_a", name="testing", value="pytest",
            domain=PreferenceDomain.TESTING,
        )
        pi.record_preference(
            "usr_a", name="testing", value="pytest",
            domain=PreferenceDomain.TESTING,
        )
        prefs = pi.preferences("usr_a")
        self.assertEqual(len(prefs), 1)
        self.assertEqual(prefs[0].value, "pytest")
        self.assertEqual(prefs[0].domain, PreferenceDomain.TESTING)

    def test_record_uses_distinct_conflict_keys_for_distinct_domains(self):
        svc, pi = make_intelligence()
        pi.record_preference(
            "usr_a", name="fast", value="pytest", domain=PreferenceDomain.TESTING
        )
        pi.record_preference(
            "usr_a", name="fast", value="hot reload", domain=PreferenceDomain.CODING_STYLE
        )
        self.assertEqual(len(pi.preferences("usr_a")), 2)

    def test_record_requires_writer(self):
        service = make_service()
        pi = PeopleIntelligence(service)
        with self.assertRaises(PeopleValidationError):
            pi.record_preference(
                "usr_a", name="x", value="y",
                domain=PreferenceDomain.TESTING,
            )

    def test_record_validates_inputs(self):
        svc, pi = make_intelligence()
        with self.assertRaises(PeopleValidationError):
            pi.record_preference("usr_a", name="", value="y")
        with self.assertRaises(PeopleValidationError):
            pi.record_preference("usr_a", name="x", value="  ")
        with self.assertRaises(PeopleValidationError):
            pi.record_preference("", name="x", value="y")


class BoundedPreferencesTests(unittest.TestCase):
    def test_per_domain_bounded(self):
        svc, pi = make_intelligence(
            limits=PeopleLimits(max_preferences_per_domain=3)
        )
        for i in range(5):
            seed_preference(
                svc, f"testing pref {i}", name=f"t{i}", domain="testing",
                importance=0.1 * (i + 1),
            )
        dev = pi.developer_preferences("usr_a")
        self.assertEqual(len(dev.testing), 3)
        self.assertEqual(
            [p.value for p in dev.testing],
            ["testing pref 4", "testing pref 3", "testing pref 2"],
        )


class PreferenceIsolationTests(unittest.TestCase):
    def test_preferences_are_user_scoped(self):
        svc, pi = make_intelligence()
        seed_preference(
            svc, "a likes python", user_id="usr_a", name="lang", domain="language"
        )
        seed_preference(
            svc, "b likes rust", user_id="usr_b", name="lang", domain="language"
        )
        self.assertEqual([p.value for p in pi.preferences("usr_a")], ["a likes python"])
        self.assertEqual([p.value for p in pi.preferences("usr_b")], ["b likes rust"])
        self.assertEqual(
            [p.value for p in pi.developer_preferences("usr_a").languages],
            ["a likes python"],
        )


if __name__ == "__main__":
    unittest.main()