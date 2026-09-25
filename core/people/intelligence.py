"""Brain-owned People Intelligence (Phase 5).

Aggregates people/relationship/preference knowledge out of the Memory Engine.
People Intelligence owns no storage: it reads through a memory port and writes
preferences through the same Memory Engine lifecycle (candidate -> classify ->
score -> persist -> conflict resolution).

Deterministic by design — no LLM, no machine learning. Everything returned is
traceable back to the memory ids that produced it.
"""

from __future__ import annotations

from typing import Any, Iterable

from contracts.common.ids import PersonId, UserId
from contracts.common.types import Source
from contracts.memory.memory import Memory, MemoryType

from core.memory.candidate import MemoryCandidate
from core.memory.filters import MemoryQuery, MemoryStatusFilter

from .exceptions import PeopleValidationError
from .identification import (
    collect_aliases,
    identify,
    mint_person_id,
    resolve_exact,
)
from .models import (
    DeveloperPreferences,
    InteractionReference,
    PeopleLimits,
    PeopleSummary,
    PersonFact,
    PersonFactDurability,
    PersonProfile,
    PersonResolution,
    PersonSourceTrace,
    PersonSummary,
    PersonTimeline,
    PersonTimelineEntry,
    Preference,
    PreferenceDomain,
    RelationshipFact,
)
from .ports import PeopleMemory, PeopleMemoryWriter
_DEV_DOMAINS = tuple(domain for domain in PreferenceDomain)


IDENTITY_KIND = "person_identity"

_DEV_DOMAINS = tuple(domain for domain in PreferenceDomain)

_CLASSIFY_ORDER = (
    PreferenceDomain.LANGUAGE,
    PreferenceDomain.TESTING,
    PreferenceDomain.EXPLANATION_DETAIL,
    PreferenceDomain.COMMIT_STYLE,
    PreferenceDomain.DEPLOYMENT,
    PreferenceDomain.CODING_STYLE,
)

_DOMAIN_KEYWORDS: dict[PreferenceDomain, frozenset[str]] = {
    PreferenceDomain.LANGUAGE: frozenset(
        {"language", "languages", "python", "javascript", "typescript", "rust",
         "golang", "java", "kotlin", "swift", "ruby", "php", "cpp", "csharp"}
    ),
    PreferenceDomain.CODING_STYLE: frozenset(
        {"style", "formatting", "formatter", "lint", "naming", "convention"}
    ),
    PreferenceDomain.TESTING: frozenset(
        {"test", "testing", "pytest", "unittest", "coverage", "spec"}
    ),
    PreferenceDomain.EXPLANATION_DETAIL: frozenset(
        {"explain", "explanation", "concise", "terse", "verbose", "detail",
         "bullet", "summary"}
    ),
    PreferenceDomain.COMMIT_STYLE: frozenset(
        {"commit", "commits", "conventional commits", "commit message"}
    ),
    PreferenceDomain.DEPLOYMENT: frozenset(
        {"deploy", "deployment", "ci", "cd", "release", "rollout"}
    ),
}

_DURABLE_TOPICS = frozenset(
    {
        "employment",
        "employer",
        "job",
        "company",
        "career",
        "work",
        "relationship",
        "role",
        "responsibility",
        "organization",
        "location",
        "current_location",
        "residence",
        "city",
        "address",
    }
)

_EVIDENCE_KEYS = (
    "topic",
    "event_type",
    "provider",
    "source_event_timestamp",
    "occurred_at",
    "explicit",
    "inferred",
    "temporary",
    "durable",
    "durability",
    "conflict_key",
    "person_name",
    "person_aliases",
    "source_event_id",
    "correlation_id",
)

_DURABILITY_VALUES = {
    value.value for value in PersonFactDurability
}


def classify_person_fact_durability(
    memory: Memory,
) -> PersonFactDurability:
    """Classify durability from explicit metadata, type, and topic only.

    Natural-language inference is deliberately not attempted. A memory remains
    ``unspecified`` when the available structured evidence is insufficient.
    """
    metadata = memory.metadata or {}
    explicit = metadata.get("durability")
    if isinstance(explicit, str) and explicit in _DURABILITY_VALUES:
        return PersonFactDurability(explicit)
    if metadata.get("temporary") is True:
        return PersonFactDurability.TEMPORARY
    if metadata.get("durable") is True:
        return PersonFactDurability.DURABLE
    topic = metadata.get("topic")
    if isinstance(topic, str) and topic.lower() in _DURABLE_TOPICS:
        return PersonFactDurability.DURABLE
    if memory.type in (MemoryType.INTERACTION, MemoryType.OBSERVATION):
        return PersonFactDurability.TEMPORARY
    if memory.type == MemoryType.RELATIONSHIP:
        return PersonFactDurability.DURABLE
    if metadata.get("explicit") is True and memory.type in (
        MemoryType.FACT,
        MemoryType.EVENT,
    ):
        return PersonFactDurability.DURABLE
    return PersonFactDurability.UNSPECIFIED


def _bounded_evidence(metadata: dict[str, Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    for key in _EVIDENCE_KEYS:
        if key not in metadata:
            continue
        value = metadata[key]
        if isinstance(value, str):
            evidence[key] = value[:512]
        elif isinstance(value, (bool, int, float)) or value is None:
            evidence[key] = value
        elif isinstance(value, (list, tuple)):
            evidence[key] = [
                item[:120] if isinstance(item, str) else item
                for item in value[:20]
                if isinstance(item, (str, bool, int, float))
            ]
    return evidence


def _source_trace(memory: Memory) -> PersonSourceTrace:
    metadata = memory.metadata or {}
    raw_source_event_id = metadata.get("source_event_id")
    source_event_id = None
    source_event_id_truncated = False
    if isinstance(raw_source_event_id, str) and raw_source_event_id.strip():
        source_event_id = raw_source_event_id[:512]
        source_event_id_truncated = len(raw_source_event_id) > 512
    raw_correlation_id = metadata.get("correlation_id")
    correlation_id = None
    correlation_id_truncated = False
    if isinstance(raw_correlation_id, str) and raw_correlation_id.strip():
        correlation_id = raw_correlation_id[:256]
        correlation_id_truncated = len(raw_correlation_id) > 256
    return PersonSourceTrace(
        source=memory.source,
        source_event_id=source_event_id,
        correlation_id=correlation_id,
        source_event_id_truncated=source_event_id_truncated,
        correlation_id_truncated=correlation_id_truncated,
        related_event_ids=list(memory.related_events[:32]),
        evidence=_bounded_evidence(metadata),
    )


def _timeline_entry(
    memory: Memory,
    person_id: PersonId,
) -> PersonTimelineEntry:
    statement = memory.content.strip()
    return PersonTimelineEntry(
        person_id=person_id,
        memory_id=memory.memory_id,
        memory_type=memory.type,
        status=memory.status,
        statement=statement[:2000],
        statement_truncated=len(statement) > 2000,
        occurred_at=memory.valid_from,
        created_at=memory.created_at,
        valid_until=memory.valid_until,
        durability=classify_person_fact_durability(memory),
        confidence=memory.confidence,
        importance=memory.importance,
        provenance=_source_trace(memory),
    )


def classify_preference_domain(
    name: str,
    content: str,
    metadata: dict[str, Any],
) -> PreferenceDomain | None:
    """Deterministic preference domain detection.

    Explicit ``metadata["domain"]`` wins; otherwise a keyword table decides.
    Returns None for a general (non-developer) preference.
    """
    explicit = metadata.get("domain")
    if isinstance(explicit, str):
        for domain in _DEV_DOMAINS:
            if explicit == domain.value:
                return domain
    haystack = f"{name} {content}".lower()
    for domain in _CLASSIFY_ORDER:
        if any(word in haystack for word in _DOMAIN_KEYWORDS[domain]):
            return domain
    return None


def _slug(value: str) -> str:
    return "_".join(value.strip().lower().split())[:80] or "preference"


class PeopleIntelligence:
    """People identification, relationships, interactions and preferences."""

    def __init__(
        self,
        memory: PeopleMemory,
        *,
        writer: PeopleMemoryWriter | None = None,
        limits: PeopleLimits | None = None,
    ) -> None:
        if not isinstance(memory, PeopleMemory):
            raise PeopleValidationError("memory must implement PeopleMemory")
        self._memory = memory
        if writer is not None and not isinstance(writer, PeopleMemoryWriter):
            raise PeopleValidationError("writer must implement PeopleMemoryWriter")
        self._writer = writer
        self._limits = limits or PeopleLimits()

    # -- people identification -------------------------------------------------
    def identify_people(self, text: str, *, user_id: UserId) -> list[PersonId]:
        """Identify people by name/alias tokens found in ``text``."""
        self._validate_ids(user_id)
        if not text or not text.strip():
            return []
        memories = self._scan(user_id)
        index = collect_aliases(memories)
        return identify(text, index)

    # -- aggregation -----------------------------------------------------------
    def profile(
        self, user_id: UserId, person_id: PersonId
    ) -> PersonProfile:
        """Aggregate everything known about one person."""
        self._validate_ids(user_id, person_id)
        memories = self._referencing(user_id, person_id)
        memories.sort(
            key=lambda m: (-m.importance, -m.updated_at.timestamp(), m.memory_id)
        )
        names = collect_aliases(memories).get(person_id) or frozenset()
        name = next(iter(sorted(names)), None)

        facts: list[PersonFact] = []
        for memory in memories:
            if memory.type in (MemoryType.RELATIONSHIP, MemoryType.INTERACTION):
                continue
            if len(facts) >= self._limits.max_facts:
                break
            facts.append(
                PersonFact(
                    memory_id=memory.memory_id,
                    statement=memory.content,
                    confidence=memory.confidence,
                    importance=memory.importance,
                )
            )

        relationships = self._relationship_facts(memories)
        interactions = self._interaction_refs(memories)

        last_seen = None if not memories else max(
            m.created_at or m.valid_from for m in memories
        )
        return PersonProfile(
            user_id=user_id,
            person_id=person_id,
            name=name,
            aliases=sorted(names) if names else [],
            relationship_facts=relationships,
            interactions=interactions,
            facts=facts,
            mention_count=len(memories),
            last_seen=last_seen,
            memory_ids=sorted({m.memory_id for m in memories}),
        )

    def timeline(
        self,
        user_id: UserId,
        person_id: PersonId,
        *,
        limit: int | None = None,
    ) -> PersonTimeline:
        """Return the bounded, chronological, source-traceable person timeline.

        Both active and historical memories are read so supersessions and
        expired facts remain inspectable. No memory is deleted or rewritten.
        """
        self._validate_ids(user_id, person_id)
        if limit is not None and (
            isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
        ):
            raise PeopleValidationError("limit must be a positive integer")
        maximum = min(
            limit or self._limits.max_timeline_entries,
            self._limits.max_timeline_entries,
        )
        memories = self._memory.list_memories(
            MemoryQuery(
                user_id=user_id,
                person_id=person_id,
                status=MemoryStatusFilter.ANY,
                limit=self._limits.scan_limit,
            )
        )
        memories.sort(
            key=lambda memory: (
                memory.valid_from,
                memory.created_at,
                memory.memory_id,
            )
        )
        entries = [
            _timeline_entry(memory, person_id)
            for memory in memories[:maximum]
        ]
        return PersonTimeline(
            user_id=user_id,
            person_id=person_id,
            entries=entries,
            total_entries=len(memories),
            truncated=len(memories) > len(entries),
            scan_truncated=len(memories) >= self._limits.scan_limit,
            person_known=bool(memories),
        )

    def relationships(
        self, user_id: UserId, *, person_id: PersonId | None = None
    ) -> list[RelationshipFact]:
        """Relationship facts for a person (or for everyone the user knows)."""
        self._validate_ids(user_id, person_id)
        memories = self._memory.list_memories(
            MemoryQuery(
                user_id=user_id,
                memory_type=MemoryType.RELATIONSHIP,
                person_id=person_id,
                status=MemoryStatusFilter.ACTIVE,
                limit=None,
            )
        )
        memories.sort(
            key=lambda m: (-m.importance, -m.updated_at.timestamp(), m.memory_id)
        )
        return self._relationship_facts(memories)

    def interactions(
        self, user_id: UserId, *, person_id: PersonId | None = None
    ) -> list[InteractionReference]:
        """Interaction-history references for a person (or all)."""
        self._validate_ids(user_id, person_id)
        memories = self._memory.list_memories(
            MemoryQuery(
                user_id=user_id,
                memory_type=MemoryType.INTERACTION,
                person_id=person_id,
                status=MemoryStatusFilter.ACTIVE,
                limit=None,
            )
        )
        memories.sort(
            key=lambda m: (-m.updated_at.timestamp(), m.memory_id)
        )
        return self._interaction_refs(memories)

    def people_summary(self, user_id: UserId) -> PeopleSummary:
        """Everyone known to the user, ranked by mention count.

        The identity record written by :meth:`resolve_person` is not a mention,
        so it never inflates a person's count.
        """
        self._validate_ids(user_id)
        memories = self._scan(user_id)
        counts: dict[PersonId, int] = {}
        for memory in memories:
            is_identity = memory.metadata.get("kind") == IDENTITY_KIND
            for person_id in memory.related_people:
                if person_id not in counts:
                    counts[person_id] = 0
                if not is_identity:
                    counts[person_id] += 1
        names = collect_aliases(memories)
        rows: list[PersonSummary] = []
        for person_id, count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        ):
            aliases = names.get(person_id) or frozenset()
            rows.append(
                PersonSummary(
                    person_id=person_id,
                    name=next(iter(sorted(aliases)), None),
                    mention_count=count,
                )
            )
            if len(rows) >= self._limits.max_people:
                break
        return PeopleSummary(user_id=user_id, people=rows)

    # -- preferences ------------------------------------------------------------
    def preferences(self, user_id: UserId) -> list[Preference]:
        """All preference memories for the user (developer + general)."""
        self._validate_ids(user_id)
        memories = self._memory.list_memories(
            MemoryQuery(
                user_id=user_id,
                memory_type=MemoryType.PREFERENCE,
                status=MemoryStatusFilter.ACTIVE,
                limit=None,
            )
        )
        preferences = [
            self._as_preference(memory) for memory in memories
        ]
        preferences.sort(
            key=lambda p: (
                0 if p.domain is None else list(PreferenceDomain).index(p.domain),
                -p.importance,
                p.memory_id,
            )
        )
        return preferences

    def developer_preferences(
        self, user_id: UserId
    ) -> DeveloperPreferences:
        """Developer-workflow preferences, bucketed by domain."""
        all_preferences = self.preferences(user_id)
        buckets: dict[PreferenceDomain, list[Preference]] = {
            domain: [] for domain in _DEV_DOMAINS
        }
        for preference in all_preferences:
            if preference.domain is None:
                continue
            bucket = buckets[preference.domain]
            if len(bucket) < self._limits.max_preferences_per_domain:
                bucket.append(preference)
        return DeveloperPreferences(
            user_id=user_id,
            languages=buckets[PreferenceDomain.LANGUAGE],
            coding_style=buckets[PreferenceDomain.CODING_STYLE],
            testing=buckets[PreferenceDomain.TESTING],
            explanation_detail=buckets[PreferenceDomain.EXPLANATION_DETAIL],
            commit_style=buckets[PreferenceDomain.COMMIT_STYLE],
            deployment=buckets[PreferenceDomain.DEPLOYMENT],
        )

    def record_preference(
        self,
        user_id: UserId,
        *,
        name: str,
        value: str,
        domain: PreferenceDomain | None = None,
        confidence: float | None = None,
        importance: float | None = None,
        source: Source | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Preference:
        """Persist a preference through the Memory Engine.

        Uses ``metadata["preference"]`` as the conflict key
        (``<domain>:<name>``), so re-recording the same preference supersedes
        the previous record instead of accumulating dead facts.
        """
        if self._writer is None:
            raise PeopleValidationError(
                "record_preference requires a PeopleMemoryWriter (provide MemoryService)"
            )
        self._validate_ids(user_id)
        name = name.strip()
        value = value.strip()
        if not name:
            raise PeopleValidationError("preference name must be non-empty")
        if not value:
            raise PeopleValidationError("preference value must be non-empty")

        meta = dict(metadata or {})
        meta["kind"] = "preference"
        meta["preference_name"] = name
        meta["preference"] = (
            f"{domain.value}:{name}" if domain else f"pref:{name}"
        )
        if domain is not None:
            meta["domain"] = domain.value
        else:
            meta["user_preference"] = True

        created = self._writer.create_memory(
            MemoryCandidate(
                content=value,
                user_id=user_id,
                source=source or Source(provider="people"),
                confidence=confidence,
                importance=importance,
                metadata=meta,
            )
        )
        return Preference(
            memory_id=created.memory_id,
            domain=domain,
            name=name,
            value=value,
            confidence=created.confidence,
            importance=created.importance,
        )

    # -- identity resolution ----------------------------------------------------
    def resolve_person(
        self,
        user_id: UserId,
        name: str,
        *,
        aliases: Iterable[str] = (),
        source: Source | None = None,
    ) -> PersonResolution:
        """Resolve one person name to a stable person id for this user.

        Only an exact, normalized name/alias match reuses an existing person.
        Two people already known under the same name are reported as ambiguous
        and are **never** merged. An unknown name gets a deterministic id and
        one traceable identity memory, so the same name always converges on the
        same person instead of forking a new one.
        """
        if self._writer is None:
            raise PeopleValidationError(
                "resolve_person requires a PeopleMemoryWriter (provide MemoryService)"
            )
        self._validate_ids(user_id)
        clean = name.strip() if isinstance(name, str) else ""
        if not clean:
            raise PeopleValidationError("person name must be non-empty")
        if len(clean) > self._limits.max_person_name_length:
            raise PeopleValidationError(
                f"person name must be at most {self._limits.max_person_name_length} characters"
            )
        extra = self._clean_aliases(aliases)

        matches = resolve_exact(clean, collect_aliases(self._scan(user_id)))
        if len(matches) > 1:
            return PersonResolution(
                user_id=user_id,
                name=clean,
                person_id=None,
                ambiguous=True,
                candidates=matches[: self._limits.max_person_aliases],
            )
        if len(matches) == 1:
            person_id = matches[0]
            if person_id is None:  # pragma: no cover - sorted() never yields None
                raise PeopleValidationError("resolved person id is invalid")
            return PersonResolution(
                user_id=user_id,
                name=clean,
                person_id=person_id,
                aliases=extra,
                created=False,
            )

        person_id = mint_person_id(user_id, clean)
        created = self._writer.create_memory(
            self._identity_candidate(
                user_id=user_id,
                person_id=person_id,
                name=clean,
                aliases=extra,
                source=source,
            )
        )
        return PersonResolution(
            user_id=user_id,
            name=clean,
            person_id=person_id,
            aliases=extra,
            created=True,
            memory_id=created.memory_id,
        )

    def _clean_aliases(self, aliases: Iterable[str]) -> list[str]:
        cleaned: list[str] = []
        for alias in aliases:
            if not isinstance(alias, str):
                continue
            value = alias.strip()
            if not value or len(value) > self._limits.max_person_name_length:
                continue
            if value not in cleaned:
                cleaned.append(value)
            if len(cleaned) >= self._limits.max_person_aliases:
                break
        return cleaned

    def _identity_candidate(
        self,
        *,
        user_id: UserId,
        person_id: PersonId,
        name: str,
        aliases: list[str],
        source: Source | None,
    ) -> MemoryCandidate:
        metadata: dict[str, Any] = {
            "kind": IDENTITY_KIND,
            "person_name": name,
            "person_key": f"person:{person_id}:identity",
            "durability": PersonFactDurability.DURABLE.value,
        }
        if aliases:
            metadata["person_aliases"] = list(aliases)
        return MemoryCandidate(
            content=f"Person known as {name}",
            user_id=user_id,
            type=MemoryType.FACT,
            source=source or Source(provider="people"),
            related_people=[person_id],
            metadata=metadata,
        )

    # -- internals --------------------------------------------------------------
    def _scan(self, user_id: UserId) -> list[Memory]:
        return self._memory.list_memories(
            MemoryQuery(
                user_id=user_id,
                status=MemoryStatusFilter.ACTIVE,
                limit=self._limits.scan_limit,
            )
        )

    def _referencing(self, user_id: UserId, person_id: PersonId) -> list[Memory]:
        return self._memory.list_memories(
            MemoryQuery(
                user_id=user_id,
                person_id=person_id,
                status=MemoryStatusFilter.ACTIVE,
                limit=None,
            )
        )

    def _relationship_facts(
        self, memories: Iterable[Memory]
    ) -> list[RelationshipFact]:
        facts: list[RelationshipFact] = []
        order = sorted(memories, key=lambda m: (-m.importance, m.memory_id))
        for memory in order:
            if memory.type != MemoryType.RELATIONSHIP:
                continue
            for person_id in memory.related_people:
                if len(facts) >= self._limits.max_relationships:
                    return facts
                facts.append(
                    RelationshipFact(
                        person_id=person_id,
                        memory_id=memory.memory_id,
                        statement=memory.content,
                        confidence=memory.confidence,
                        importance=memory.importance,
                    )
                )
        return facts

    def _interaction_refs(
        self, memories: Iterable[Memory]
    ) -> list[InteractionReference]:
        refs: list[InteractionReference] = []
        order = sorted(
            memories, key=lambda m: (-m.updated_at.timestamp(), m.memory_id)
        )
        for memory in order:
            if memory.type != MemoryType.INTERACTION:
                continue
            for person_id in memory.related_people:
                if len(refs) >= self._limits.max_interactions:
                    return refs
                refs.append(
                    InteractionReference(
                        person_id=person_id,
                        memory_id=memory.memory_id,
                        occurred_at=memory.valid_from or memory.created_at,
                        summary=memory.content,
                        source_event_id=memory.metadata.get("source_event_id"),
                    )
                )
        return refs

    def _as_preference(self, memory: Memory) -> Preference:
        metadata = memory.metadata or {}
        raw_name = metadata.get("preference_name")
        if isinstance(raw_name, str) and raw_name.strip():
            name = raw_name.strip()
        else:
            key = metadata.get("preference")
            name = _slug(memory.content)
            if isinstance(key, str):
                if ":" in key:
                    name = key.split(":", 1)[1]
                elif key:
                    name = key
        domain = classify_preference_domain(
            name, memory.content, metadata
        )
        value = memory.content.strip()
        return Preference(
            memory_id=memory.memory_id,
            domain=domain,
            name=name,
            value=value,
            confidence=memory.confidence,
            importance=memory.importance,
        )

    @staticmethod
    def _validate_ids(user_id: UserId, person_id: PersonId | None = None) -> None:
        if (
            not user_id
            or not str(user_id).strip()
            or len(str(user_id)) > 512
        ):
            raise PeopleValidationError("user_id must be a bounded non-empty string")
        if person_id is not None and (
            not str(person_id).strip() or len(str(person_id)) > 512
        ):
            raise PeopleValidationError(
                "person_id must be a bounded non-empty string"
            )