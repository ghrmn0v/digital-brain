"""Core Brain Learning layer (Phase 7).

Feedback loop:  Feedback contract → deterministic signal → durable memory trace
+ bounded aggregate state → explicit preference/importance learning →
personalization profile for future reasoning and clients.
"""

from .candidates import (
    LearningCandidate,
    LearningCandidateKind,
    LearningEvidence,
    PersonalizedAnswer,
    RecordedCandidate,
    answer_instruction,
    candidate_to_feedback,
    route_candidates,
)
from .exceptions import LearningError, LearningValidationError
from .interpreter import FeedbackInterpreter
from .learning import LearningEngine
from .models import (
    AssistanceNudge,
    AssistanceProfile,
    LearningLimits,
    LearningSignal,
    LearningStatus,
    PreferenceEvidence,
    SignalKind,
    StoredFeedback,
    TopicAffinity,
)
from .personalization import PersonalizationEngine
from .ports import (
    LearnerMemory,
    LearnerMemoryUpdater,
    LearnerMemoryWriter,
    LearningStateRepository,
)
from .state import SqliteLearningStateRepository

__all__ = [
    "LearningCandidate",
    "LearningCandidateKind",
    "LearningEvidence",
    "PersonalizedAnswer",
    "RecordedCandidate",
    "answer_instruction",
    "candidate_to_feedback",
    "route_candidates",
    "AssistanceNudge",
    "AssistanceProfile",
    "FeedbackInterpreter",
    "LearnerMemory",
    "LearnerMemoryUpdater",
    "LearnerMemoryWriter",
    "LearningEngine",
    "LearningError",
    "LearningLimits",
    "LearningSignal",
    "LearningStateRepository",
    "LearningStatus",
    "LearningValidationError",
    "PersonalizationEngine",
    "PreferenceEvidence",
    "SignalKind",
    "SqliteLearningStateRepository",
    "StoredFeedback",
    "TopicAffinity",
]