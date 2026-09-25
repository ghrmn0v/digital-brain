"""Personalized, bounded Brain context for LLM requests.

The Brain — not the model — decides what the model is allowed to see. This
module assembles the smallest slice of the user's own state that is relevant to
one request, so a provider receives context instead of a database dump:

    user input
        -> identify the user
        -> relevant memories        (existing SemanticSearch, user-scoped)
        -> relevant preferences     (People Intelligence)
        -> relevant people          (People Intelligence, mention-based)
        -> learned evidence         (Learning Engine status)
        -> bounded context + prompt

Design rules:

* **Bounded.** Every list is capped by explicit limits; every text field is
  truncated. There is no code path that can serialize the whole store.
* **User-scoped.** Every read is filtered by the request's ``user_id``; nothing
  crosses users.
* **Relevance-filtered.** Unrelated memories, people and topics are not
  included just because they exist.
* **Provenance-labelled.** Explicit user statements, learned evidence and
  uncertain inferences are labelled, so a model cannot present a weak signal
  as a fact.
* **No persistence.** Nothing here writes memory; the model cannot store a fact
  by answering.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from contracts.common.ids import PersonId, UserId
from core.people.models import PeopleSummary, Preference

from .ports import SemanticSearch
from .models import SearchQuery

#: Hard caps so a single prompt can never grow with the user's history.
DEFAULT_MEMORY_LIMIT = 8
DEFAULT_PREFERENCE_LIMIT = 10
DEFAULT_PEOPLE_LIMIT = 5
DEFAULT_EVIDENCE_LIMIT = 5
STATEMENT_LIMIT = 300

_SYSTEM_PREAMBLE = (
    "You are the reasoning model inside Digital Brain.\n"
    "You do not own persistent memory. Digital Brain supplies the user context "
    "below.\n"
    "Rules:\n"
    "- Use the provided context when it is relevant; ignore it otherwise.\n"
    "- Never invent user facts that are not present in the context.\n"
    "- Never claim to remember anything by yourself.\n"
    "- Treat explicitly stated facts as stronger than learned preferences, and "
    "learned preferences as stronger than your own inference.\n"
    "- If the context does not answer the question, say what is missing."
)


@runtime_checkable
class PeopleReader(Protocol):
    """Read-only People Intelligence surface used for personalization.

    ``PeopleIntelligence`` satisfies this protocol unchanged.
    """

    def preferences(self, user_id: UserId) -> list[Preference]: ...

    def people_summary(self, user_id: UserId) -> PeopleSummary: ...

    def identify_people(
        self, text: str, *, user_id: UserId
    ) -> list[PersonId]: ...


@runtime_checkable
class LearningReader(Protocol):
    """Read-only Learning Engine surface used for personalization.

    ``LearningEngine`` satisfies this protocol unchanged.
    """

    def learning_status(self, user_id: UserId) -> object: ...


class ContextFact(BaseModel):
    """One bounded, labelled piece of user context."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1, max_length=32)
    text: str = Field(min_length=1, max_length=STATEMENT_LIMIT)
    source: str = Field(default="unknown", max_length=32)
    memory_id: str | None = None
    person_id: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class PersonalContext(BaseModel):
    """Everything the Brain chose to show the model for one request."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    request: str = Field(min_length=1, max_length=4096)
    memories: list[ContextFact] = Field(default_factory=list, max_length=32)
    preferences: list[ContextFact] = Field(default_factory=list, max_length=32)
    people: list[ContextFact] = Field(default_factory=list, max_length=32)
    learned: list[ContextFact] = Field(default_factory=list, max_length=32)

    @property
    def is_empty(self) -> bool:
        return not (
            self.memories or self.preferences or self.people or self.learned
        )


class PersonalContextBuilder:
    """Assembles a :class:`PersonalContext` from existing Brain subsystems."""

    def __init__(
        self,
        search: SemanticSearch,
        *,
        people: PeopleReader | None = None,
        learning: LearningReader | None = None,
        memory_limit: int = DEFAULT_MEMORY_LIMIT,
        preference_limit: int = DEFAULT_PREFERENCE_LIMIT,
        people_limit: int = DEFAULT_PEOPLE_LIMIT,
        evidence_limit: int = DEFAULT_EVIDENCE_LIMIT,
    ) -> None:
        if not isinstance(search, SemanticSearch):
            raise TypeError("search must implement SemanticSearch")
        self._search = search
        self._people = people
        self._learning = learning
        self._memory_limit = max(1, memory_limit)
        self._preference_limit = max(1, preference_limit)
        self._people_limit = max(1, people_limit)
        self._evidence_limit = max(1, evidence_limit)

    def build(
        self,
        user_id: UserId,
        request: str,
        *,
        repository: str | None = None,
    ) -> PersonalContext:
        text = (request or "").strip()
        if not text:
            raise ValueError("request text must not be empty")
        return PersonalContext(
            user_id=user_id,
            request=text[:4096],
            memories=self._memories(user_id, text, repository),
            preferences=self._preferences(user_id),
            people=self._people_facts(user_id, text),
            learned=self._learned(user_id),
        )

    # -- individual slices -------------------------------------------------
    def _memories(
        self, user_id: UserId, text: str, repository: str | None
    ) -> list[ContextFact]:
        results = self._search.search(
            SearchQuery(
                user_id=user_id,
                text=text[:4096],
                repository=repository,
                top_k=self._memory_limit,
            )
        )
        facts: list[ContextFact] = []
        for scored in results[: self._memory_limit]:
            memory = scored.memory
            facts.append(
                ContextFact(
                    kind="memory",
                    text=_truncate(memory.content),
                    source=_memory_source(memory),
                    memory_id=memory.memory_id,
                    person_id=memory.related_people[0] if memory.related_people else None,
                    confidence=round(scored.score, 4)
                    if getattr(scored, "score", None) is not None
                    else None,
                )
            )
        return facts

    def _preferences(self, user_id: UserId) -> list[ContextFact]:
        if self._people is None:
            return []
        facts: list[ContextFact] = []
        for preference in self._people.preferences(user_id)[
            : self._preference_limit
        ]:
            # An explicit user statement is labelled as such so the model can
            # prefer it over anything weaker.
            learned_flag = _metadata_flag(preference, "learned")
            facts.append(
                ContextFact(
                    kind="preference",
                    text=(
                        f"{preference.name} = {preference.value}"
                        f"{f' ({_domain_value(preference.domain)})' if preference.domain else ''}"
                    )[:STATEMENT_LIMIT],
                    source="learned" if learned_flag else "explicit",
                    memory_id=preference.memory_id,
                    confidence=preference.confidence,
                )
            )
        return facts

    def _people_facts(self, user_id: UserId, text: str) -> list[ContextFact]:
        if self._people is None:
            return []
        mentioned = self._people.identify_people(text, user_id=user_id)
        if not mentioned:
            return []
        summary = self._people.people_summary(user_id)
        by_id = {row.person_id: row for row in summary.people}
        facts: list[ContextFact] = []
        for person_id in mentioned[: self._people_limit]:
            row = by_id.get(person_id)
            label = (row.name if row is not None else None) or person_id
            facts.append(
                ContextFact(
                    kind="person",
                    text=f"{label} (mentioned in this request)",
                    source="memory" if row is not None else "unknown",
                    person_id=person_id,
                )
            )
        return facts

    def _learned(self, user_id: UserId) -> list[ContextFact]:
        if self._learning is None:
            return []
        status = self._learning.learning_status(user_id)
        evidence = getattr(status, "preference_evidence", None) or []
        facts: list[ContextFact] = []
        for entry in evidence[: self._evidence_limit]:
            rate = entry.positive_rate
            facts.append(
                ContextFact(
                    kind="learned_evidence",
                    text=(
                        f"{entry.name}: {entry.positive} positive / "
                        f"{entry.negative} negative"
                        + (f", positive rate {rate:.2f}" if rate is not None else "")
                    )[:STATEMENT_LIMIT],
                    source="learned",
                    confidence=entry.weight,
                )
            )
        return facts


def render_personal_context(context: PersonalContext) -> str:
    """Render the bounded context as the user part of a provider request.

    Sections are explicit and empty sections are omitted, so a model is never
    told about data that does not exist.
    """
    lines: list[str] = []
    if context.memories:
        lines.append("RELEVANT MEMORIES (from this user's own memory):")
        lines.extend(
            f"- [{fact.source}] {fact.text}" for fact in context.memories
        )
    if context.preferences:
        lines.append("PREFERENCES (explicit = the user stated it directly):")
        lines.extend(
            f"- [{fact.source}] {fact.text}" for fact in context.preferences
        )
    if context.people:
        lines.append("PEOPLE MENTIONED:")
        lines.extend(f"- {fact.text}" for fact in context.people)
    if context.learned:
        lines.append("LEARNED EVIDENCE (weak signals, not facts):")
        lines.extend(f"- {fact.text}" for fact in context.learned)
    return "\n".join(lines)


def personal_system_prompt() -> str:
    """The system side of a personalized request."""
    return _SYSTEM_PREAMBLE


def personalized_user_prompt(
    context: PersonalContext,
    *,
    instruction: str | None = None,
) -> str:
    """System-free user text: context first, then the current request."""
    rendered = render_personal_context(context)
    request = f"CURRENT REQUEST:\n{context.request}"
    if not rendered:
        return (
            "USER CONTEXT:\n(none stored yet)\n\n" + request
        )
    return f"USER CONTEXT:\n{rendered}\n\n{request}" + (
        f"\n\nTASK:\n{instruction}" if instruction else ""
    )


def _truncate(text: str) -> str:
    collapsed = " ".join((text or "").split())
    return (collapsed[:STATEMENT_LIMIT] or "(empty)")[:STATEMENT_LIMIT]


def _memory_source(memory: object) -> str:
    metadata = getattr(memory, "metadata", None) or {}
    if metadata.get("kind") == "person_identity":
        return "identity"
    if metadata.get("learned") is True:
        return "learned"
    if metadata.get("explicit") is True:
        return "explicit"
    provider = getattr(getattr(memory, "source", None), "provider", None)
    if isinstance(provider, str) and provider:
        return provider[:32]
    return "memory"


def _domain_value(domain: object) -> str:
    """Render a preference domain as its stored value, not an enum repr."""
    value = getattr(domain, "value", domain)
    return str(value) if value is not None else ""


def _metadata_flag(preference: object, key: str) -> bool:
    # Preference objects are Brain models without raw metadata; the learning
    # source provider is the honest signal available here.
    source = getattr(preference, "source", None)
    provider = getattr(source, "provider", None)
    return key == "learned" and provider == "learning"
