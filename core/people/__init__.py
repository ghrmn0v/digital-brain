"""People Intelligence (Phase 5).

Brain-owned people/relationship/preference intelligence. Identity comes from
the unified Phase 0 ``Person`` contract (``PersonId``); facts, relationships,
interactions, timelines and preferences are derived from Memory Engine records.
No second database, no LLM — deterministic and traceable.
"""

from __future__ import annotations

from .exceptions import PeopleError, PeopleValidationError
from .identification import collect_aliases, identify, tokenize
from .intelligence import (
    PeopleIntelligence,
    classify_person_fact_durability,
    classify_preference_domain,
)
from .models import (
    DeveloperPreferences,
    InteractionReference,
    PeopleLimits,
    PeopleSummary,
    PersonFact,
    PersonFactDurability,
    PersonProfile,
    PersonSourceTrace,
    PersonSummary,
    PersonTimeline,
    PersonTimelineEntry,
    Preference,
    PreferenceDomain,
    RelationshipFact,
)
from .ports import PeopleMemory, PeopleMemoryWriter

__all__ = [
    "PeopleIntelligence",
    "classify_person_fact_durability",
    "classify_preference_domain",
    "collect_aliases",
    "identify",
    "tokenize",
    "DeveloperPreferences",
    "InteractionReference",
    "PeopleLimits",
    "PeopleSummary",
    "PersonFact",
    "PersonFactDurability",
    "PersonProfile",
    "PersonSourceTrace",
    "PersonSummary",
    "PersonTimeline",
    "PersonTimelineEntry",
    "Preference",
    "PreferenceDomain",
    "RelationshipFact",
    "PeopleError",
    "PeopleValidationError",
    "PeopleMemory",
    "PeopleMemoryWriter",
]