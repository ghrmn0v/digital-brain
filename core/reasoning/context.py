"""ReasoningContext adapter (Phase 8 Slice 2).

The ContextEngine stays independent from Reasoning: it produces
``core.context.Context``, and this adapter distills — never dumps — the bounded
parts Reasoning actually consumes into the typed
:class:`~core.reasoning.models.ReasoningContext`.

One-way dependency: Reasoning only reads Context *models*, never constructs or
owns the engine, so no cycle exists (core.context never imports core.reasoning).

Distillation rules:

- only deterministic, bounded fields are copied;
- memory content is truncated and the list is capped;
- reference-id lists are deduplicated, sorted and capped;
- nothing is inferred: absent data stays absent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.context.models import Context

from .exceptions import ReasoningValidationError
from .models import ReasoningContext, RelevantMemory

_WORD_RE = re.compile(r"[a-z0-9_]{3,}")

_NOISE_WORDS: frozenset[str] = frozenset(
    {
        "def", "return", "if", "elif", "else", "for", "while", "self", "import",
        "from", "class", "pass", "none", "true", "false", "and", "or", "not",
        "null", "print", "int", "str", "bool", "list", "dict", "the", "this",
        "that", "with", "were", "been", "have", "has", "are", "was", "into",
    }
)


@dataclass(frozen=True)
class ContextDistillationLimits:
    """Deterministic bounds for the Context -> ReasoningContext distillation."""

    max_memories: int = 8
    content_chars: int = 2000
    max_reference_ids: int = 8
    max_keywords: int = 10

    def validate(self) -> "ContextDistillationLimits":
        if self.max_memories < 0 or self.max_reference_ids < 0:
            raise ReasoningValidationError(
                "distillation limits must be >= 0"
            )
        if self.content_chars < 1 or self.max_keywords < 1:
            raise ReasoningValidationError(
                "distillation limits must be >= 1"
            )
        return self


def build_reasoning_context(
    context: Context,
    *,
    limits: ContextDistillationLimits | None = None,
) -> ReasoningContext:
    """Distill a built ``Context`` into a bounded ``ReasoningContext``.

    Raises ``ReasoningValidationError`` for a non-Context input or invalid
    limits. The output is deterministic for the same input.
    """
    if not isinstance(context, Context):
        raise ReasoningValidationError(
            "context must be a core.context.Context"
        )
    try:
        limits = (
            limits if limits is not None else ContextDistillationLimits()
        ).validate()
    except ReasoningValidationError as exc:
        raise ReasoningValidationError(str(exc)) from exc

    memories: list[RelevantMemory] = [
        RelevantMemory(
            memory_id=item.memory.memory_id,
            source_type=item.memory.type.value,
            content=item.memory.content[: limits.content_chars],
            importance=item.memory.importance,
            confidence=item.memory.confidence,
            score=item.score,
        )
        for item in sorted(
            context.relevant_memories,
            key=lambda item: (-item.score, item.memory.memory_id),
        )[: limits.max_memories]
    ]

    return ReasoningContext(
        context_id=context.context_id,
        user_id=context.user_id,
        status=context.status.value,
        repository=context.repository
        or (
            context.developer_context.repository
            if context.developer_context is not None
            else None
        ),
        current_file=context.current_file,
        current_task=context.current_task,
        relevant_memories=memories,
        previous_bug_findings=sorted(set(context.previous_bug_findings))[
            : limits.max_reference_ids
        ],
        previous_decisions=sorted(set(context.previous_decisions))[
            : limits.max_reference_ids
        ],
        developer_preferences=sorted(set(context.developer_preferences))[
            : limits.max_reference_ids
        ],
        relevant_people=sorted(set(context.relevant_people))[
            : limits.max_reference_ids
        ],
    )


def context_keywords(
    reasoning_context: ReasoningContext,
    *,
    max_keywords: int | None = None,
) -> list[str]:
    """Distinctive lexical keyword candidates from distilled memories.

    Deterministic, bounded and explicit (no ML): tokens are only suggested when
    they occur in at least two distinct memories, which filters incidental noise
    without inventing meaning. The result is ordered by (frequency, token).
    """
    if reasoning_context is None:
        return []
    if max_keywords is None:
        max_keywords = ContextDistillationLimits().max_keywords
    counts: dict[str, int] = {}
    for memory in reasoning_context.relevant_memories:
        seen: set[str] = set()
        for token in _WORD_RE.findall(memory.content.lower()):
            if token in _NOISE_WORDS or token in seen:
                continue
            seen.add(token)
            counts[token] = counts.get(token, 0) + 1
    candidates = sorted(
        (token for token, count in counts.items() if count >= 2),
        key=lambda token: (-counts[token], token),
    )
    return candidates[: max_keywords]