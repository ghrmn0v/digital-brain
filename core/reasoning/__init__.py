"""Reasoning (Phase 6): intent understanding, bug detection, lightweight code
review, test-result interpretation.

Core Brain REASONS here (what is happening, what is relevant, what could be
wrong). It PROPOSES (never executes) — proposals live in ``core/actions/``.
All passes are deterministic; findings carry honest, bounded confidence.
"""

from __future__ import annotations

from .bug_detection import BugDetector
from .checks import scan_file
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
    ReasoningLimits,
    ReasoningResult,
    ReviewCategory,
    ReviewFinding,
    Severity,
    TestFailure,
    TestResultInterpretation,
)
from .reasoning import ReasoningEngine
from .review import CodeReviewer
from .test_interpretation import TestResultInterpreter

__all__ = [
    "BugDetector",
    "BugFinding",
    "CodeReviewer",
    "IntentAnalysisError",
    "IntentAnalyzer",
    "IntentKind",
    "IntentUnderstanding",
    "ReasoningEngine",
    "ReasoningError",
    "ReasoningLimits",
    "ReasoningResult",
    "ReasoningValidationError",
    "ReviewCategory",
    "ReviewFinding",
    "Severity",
    "TestFailure",
    "TestResultInterpreter",
    "TestResultInterpretation",
    "scan_file",
]