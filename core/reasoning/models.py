"""Reasoning models (Phase 6): intent understanding, bug findings, review
findings, test interpretation and the aggregated ReasoningResult."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from contracts.common.ids import UserId
from contracts.common.types import Confidence, UtcDateTime


class Severity(str, Enum):
    """Honest severity ladder for findings (info < warning < high < critical)."""

    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class IntentKind(str, Enum):
    """What the developer is asking for / what is happening (open-additive)."""

    BUG_DETECTION = "bug_detection"
    FIX = "fix"
    EXPLAIN = "explain"
    TEST = "test"
    REVIEW = "review"
    DEPLOY = "deploy"
    DEVELOPMENT = "development"


class ReviewCategory(str, Enum):
    """Categories for lightweight code-review findings (open-additive)."""

    BUG = "bug"
    MAINTAINABILITY = "maintainability"
    TEST_COVERAGE = "test_coverage"
    SECURITY_CONCERN = "security_concern"
    PERFORMANCE_CONCERN = "performance_concern"


class IntentUnderstanding(BaseModel):
    """Corpus-free understanding of what is requested / happening."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    query: str = Field(default="", max_length=4096)
    intent_kind: IntentKind
    confidence: Confidence
    keywords: list[str] = Field(default_factory=list)
    repository: str | None = None
    target_file: str | None = None
    target_line: int | None = Field(default=None, ge=1)
    fallback_used: bool = False


class BugFinding(BaseModel):
    """A potential bug detected by Core Brain (never a certainty claim)."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    user_id: UserId
    repository: str
    file: str
    line: int = Field(ge=1)
    column: int | None = Field(default=None, ge=1)
    title: str = Field(max_length=200)
    message: str = Field(max_length=2000)
    severity: Severity
    confidence: Confidence
    check: str
    suggested_fix: str | None = None


class ReviewFinding(BaseModel):
    """A lightweight review finding with an explicit category."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    user_id: UserId
    repository: str
    file: str
    line: int = Field(ge=1)
    category: ReviewCategory
    severity: Severity
    explanation: str = Field(max_length=2000)
    confidence: Confidence
    suggestion: str | None = None


class TestFailure(BaseModel):
    """One failing/erroring test exactly as reported (never fabricated)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    file: str | None = None
    message: str | None = Field(default=None, max_length=4096)


class TestResultInterpretation(BaseModel):
    """Core Brain's summary of supplied test results."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    repository: str
    provided: bool
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    summary: str = ""
    reason: str | None = None
    failures: list[TestFailure] = Field(default_factory=list)
    confidence: Confidence


class ReasoningResult(BaseModel):
    """Everything Core Brain determined about one developer context."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    repository: str
    created_at: datetime
    intent: IntentUnderstanding
    bugs: list[BugFinding] = Field(default_factory=list)
    review_findings: list[ReviewFinding] = Field(default_factory=list)
    tests: TestResultInterpretation
    files_scanned: int = 0
    total_changed: int = 0


@dataclass(frozen=True)
class ReasoningLimits:
    """Deterministic bounds for reasoning passes (all zero-safe)."""

    max_findings: int = 40
    max_review_findings: int = 30
    max_failed_detail: int = 5