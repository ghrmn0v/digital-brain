"""Digital Brain — shared contracts (Phase 0).

Canonical, versioned data contracts exchanged between the three ownership
areas of the project:

    CORE BRAIN         (Hüseyn) — memory, people, decisions, feedback, brain events
    PRODUCT/CONNECTORS (Ayxan)  — connectors, permissions, action execution, UI
    CONNECTOME/FLY     (Fly)    — WhatsApp pipeline, Spring Boot, Python RL

See CONTRACTS.md at the repository root for ownership boundaries and the
versioning rules. NO implementation logic lives in this package.
"""

from .brain_events.events import BrainEvent, BrainEventType
from .common.envelope import EventEnvelope
from .common.ids import (
    ActionId,
    DecisionId,
    EntityId,
    EventId,
    FeedbackId,
    MemoryId,
    PersonId,
    UserId,
)
from .common.types import (
    Confidence,
    ContractVersion,
    Importance,
    ProviderName,
    Source,
    UtcDateTime,
)
from .decisions.decisions import (
    ActionType,
    BrainDecision,
    PermissionLevel,
    ProposedAction,
)
from .events.source_event import NormalizedSourceEvent, Subject
from .feedback.feedback import Feedback, FeedbackKind, FeedbackSource, FeedbackTarget
from .memory.memory import Memory, MemoryStatus, MemoryType
from .people.person import ExternalIdentity, Person

# Client-facing API contract (Phase 8 Slice 3): envelope + per-method typed
# params/results. Imported as the ``contracts.api`` package.
from . import api as api

__version__ = "0.1.0"

__all__ = [
    "ActionId",
    "ActionType",
    "BrainDecision",
    "BrainEvent",
    "BrainEventType",
    "Confidence",
    "ContractVersion",
    "DecisionId",
    "EntityId",
    "EventEnvelope",
    "EventId",
    "ExternalIdentity",
    "Feedback",
    "FeedbackId",
    "FeedbackKind",
    "FeedbackSource",
    "FeedbackTarget",
    "Importance",
    "Memory",
    "MemoryId",
    "MemoryStatus",
    "MemoryType",
    "NormalizedSourceEvent",
    "PermissionLevel",
    "Person",
    "PersonId",
    "ProposedAction",
    "ProviderName",
    "Source",
    "Subject",
    "UserId",
    "UtcDateTime",
    "__version__",
]