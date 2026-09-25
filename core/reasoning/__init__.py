"""Reasoning (Phase 6): intent understanding, bug detection, lightweight code
review, test-result interpretation.

Core Brain REASONS here (what is happening, what is relevant, what could be
wrong). It PROPOSES (never executes) — proposals live in ``core/actions/``.
All passes are deterministic; findings carry honest, bounded confidence.
"""

from __future__ import annotations

from .bug_detection import BugDetector
from .checks import scan_file
from .context import (
    ContextDistillationLimits,
    build_reasoning_context,
    context_keywords,
)
from .exceptions import (
    IntentAnalysisError,
    ReasoningError,
    ReasoningValidationError,
)
from .intent import IntentAnalyzer
from .models import (
    BugFinding,
    IntentKind,
    IntentUnderstanding,
    LearnedAffinity,
    LearningInfluence,
    ReasoningContext,
    ReasoningLimits,
    ReasoningResult,
    RelevantMemory,
    ReviewCategory,
    ReviewFinding,
    Severity,
    TestFailure,
    TestResultInterpretation,
)
from .ports import LearningProfilePort
from .profiles import build_learning_influence
from .reasoning import ReasoningEngine
from .review import CodeReviewer
from .test_interpretation import TestResultInterpreter

__all__ = [
    "BugDetector",
    "BugFinding",
    "CodeReviewer",
    "ContextDistillationLimits",
    "IntentAnalysisError",
    "IntentAnalyzer",
    "IntentKind",
    "IntentUnderstanding",
    "LearnedAffinity",
    "LearningInfluence",
    "LearningProfilePort",
    "ReasoningContext",
    "ReasoningEngine",
    "ReasoningError",
    "ReasoningLimits",
    "ReasoningResult",
    "ReasoningValidationError",
    "RelevantMemory",
    "ReviewCategory",
    "ReviewFinding",
    "Severity",
    "TestFailure",
    "TestResultInterpreter",
    "TestResultInterpretation",
    "build_learning_influence",
    "build_reasoning_context",
    "context_keywords",
    "scan_file",
]