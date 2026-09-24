"""Deterministic source checks shared by BugDetector and CodeReviewer.

Every check is honest: it flags a *potential* issue with an explicit low
confidence and "possible ..." language. Findings are never certainty claims.
Checks are pattern-based and may produce false positives — that is why each one
carries a bounded confidence and a `check` name for traceability.

Specialised project-level checks (e.g. missing test coverage) live in the
CodeReviewer, not here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import ReviewCategory, Severity

_ASSIGN_FROM_CALL = re.compile(
    r"\b([A-Za-z_]\w*)\s*=\s*(?:await\s+)?(?:[\w.]+\s*\.\s*)?"
    r"(get_\w+|fetch[\w]*|find[\w]*|load[\w]*|pop\s*\(|read[\w]*|parse[\w]*|input\s*\()"
)
_VAR_DEREF = re.compile(r"\b([A-Za-z_]\w*)\s*[\.\[]")
_SLASH_DIV = re.compile(r"(?<![:/])/(?![/=])")
_DIVISOR = re.compile(r"/\s*(?:\(?\s*)?([A-Za-z_]\w*)")
_FOR_LINE = re.compile(r"^\s*for\s+\w+\s+in\b")
_STR_APPEND = re.compile(r"\w+\s*\+=\s*[\"']")
_BARE_EXCEPT = re.compile(r"^\s*except\s*:\s*(?:#.*)?$")
_SECRET = re.compile(
    r"\b(api[_-]?key|password|passwd|secret|access[_-]?token|auth[_-]?token"
    r"|app_secret)\b\s*[:=]\s*[\"'][^\"']{3,}[\"']"
)
_TODO = re.compile(r"^\s*#+\s*(TODO|FIXME|HACK)\b", re.IGNORECASE)
_TODO_C = re.compile(r"^\s*(//|/\*|\*)\s*(TODO|FIXME|HACK)\b", re.IGNORECASE)


def _language_of(language: str | None) -> str:
    return (language or "").lower()


@dataclass(frozen=True)
class FoundIssue:
    """One deterministic finding from a source check."""

    path: str
    line: int
    category: ReviewCategory
    severity: Severity
    title: str
    message: str
    confidence: float
    check: str
    suggestion: str | None = None


def _null_guards(var: str) -> list[re.Pattern[str]]:
    return [
        re.compile(r"\bis\s+None\b"),
        re.compile(r"\bis\s+not\s+None\b"),
        re.compile(rf"\bif\s+(not\s+)?{var}\b"),
        re.compile(rf"\b{var}\s+(or\b|==\s+None|!=None)\b"),
        re.compile(rf"\bassert\s+{var}\b"),
    ]


def _zero_guard(var: str) -> re.Pattern[str]:
    return re.compile(
        rf"\bif\s+(not\s+)?[\(]?\s*{var}\s*(==|!=|<=|<|>=|>)\s*0|"
        rf"\b{var}\s*(==|!=)\s*0\b"
    )


def _scan_null_deref(lines: list[str]) -> list[FoundIssue]:
    issues: list[FoundIssue] = []
    assigned: dict[str, int] = {}
    for index, raw in enumerate(lines):
        line_no = index + 1
        stripped = raw.strip()
        if re.match(r"^\s*(async\s+def|def|class)\s", raw):
            assigned.clear()
        for match in _ASSIGN_FROM_CALL.finditer(raw):
            assigned[match.group(1)] = line_no
        for var_match in _VAR_DEREF.finditer(raw):
            var = var_match.group(1)
            assign_line = assigned.get(var)
            if assign_line is None:
                continue
            if line_no - assign_line > 8:
                continue
            guarded = False
            for probe in lines[assign_line:index]:
                guards = _null_guards(var)
                if any(guard.search(probe) for guard in guards):
                    guarded = True
                    break
            if guarded:
                continue
            issues.append(
                FoundIssue(
                    path="", line=line_no, category=ReviewCategory.BUG,
                    severity=Severity.HIGH,
                    title=f"Possible null reference on `{var}`",
                    message=(
                        f"`{var}` was assigned from a maybe-empty call on line "
                        f"{assign_line} and is dereferenced here without a "
                        f"null check. If the call returns None this can throw "
                        f"at runtime."
                    ),
                    confidence=0.4,
                    check="null_deref_check",
                    suggestion=(
                        f"Add a guard before using `{var}`, for example "
                        f"`if {var} is not None: ...`."
                    ),
                )
            )
            # one finding per assignment-deref pair is enough
            assigned[var] = line_no
    return issues


def _scan_division_by_zero(lines: list[str]) -> list[FoundIssue]:
    issues: list[FoundIssue] = []
    for index, raw in enumerate(lines):
        line_no = index + 1
        stripped = raw.strip()
        if not _SLASH_DIV.search(raw):
            continue
        if stripped.startswith(("#", "//", "*")):
            continue
        if "://" in raw or '"""' in raw or "'''" in raw:
            continue
        divisor = _DIVISOR.search(raw)
        if not divisor:
            continue
        token = divisor.group(1)
        if token in ("len", "abs", "int", "float"):
            continue
        window = lines[max(0, index - 8): index + 8]
        guarded = any(
            _zero_guard(token).search(probe) for probe in window
        )
        if guarded:
            continue
        issues.append(
            FoundIssue(
                path="", line=line_no, category=ReviewCategory.BUG,
                severity=Severity.HIGH,
                title=f"Potential division by zero on `{token}`",
                message=(
                    f"This expression divides by `{token}`, which is not an "
                    f"obvious non-zero literal and is not guarded against 0 "
                    f"nearby. It may raise ZeroDivisionError / an exception "
                    f"at runtime."
                ),
                confidence=0.3,
                check="division_zero_check",
                suggestion=(
                    f"Guard the division, e.g. `if {token} == 0: return ...`."
                ),
            )
        )
    return issues


def _scan_secrets(lines: list[str]) -> list[FoundIssue]:
    issues: list[FoundIssue] = []
    for index, raw in enumerate(lines):
        line_no = index + 1
        if _SECRET.search(raw):
            issues.append(
                FoundIssue(
                    path="", line=line_no, category=ReviewCategory.SECURITY_CONCERN,
                    severity=Severity.HIGH,
                    title="Possible secret hardcoded in source",
                    message=(
                        "A value that looks like an API key / password / token "
                        "is assigned literally in source. Committing it risks "
                        "exposure in history."
                    ),
                    confidence=0.8,
                    check="secret_literal_check",
                    suggestion="Move the value to an environment variable or a "
                    "secrets store and read it at runtime.",
                )
            )
    return issues


def _scan_bare_except(lines: list[str]) -> list[FoundIssue]:
    issues: list[FoundIssue] = []
    for index, raw in enumerate(lines):
        if _BARE_EXCEPT.search(raw):
            issues.append(
                FoundIssue(
                    path="", line=index + 1,
                    category=ReviewCategory.MAINTAINABILITY,
                    severity=Severity.INFO,
                    title="Bare except",
                    message="A bare `except:` swallows every error including "
                    "interrupts and programming errors.",
                    confidence=0.6,
                    check="bare_except_check",
                    suggestion="Catch an explicit exception type instead.",
                )
            )
    return issues


def _scan_todo_markers(lines: list[str]) -> list[FoundIssue]:
    issues: list[FoundIssue] = []
    for index, raw in enumerate(lines):
        if _TODO.search(raw) or _TODO_C.search(raw):
            issues.append(
                FoundIssue(
                    path="", line=index + 1,
                    category=ReviewCategory.MAINTAINABILITY,
                    severity=Severity.INFO,
                    title="TODO / FIXME marker in changed code",
                    message="An unfinished-work marker is present in reviewed "
                    "lines; verify it is tracked and not an oversight.",
                    confidence=0.9,
                    check="todo_marker_check",
                    suggestion="Resolve it or link the tracked issue id.",
                )
            )
    return issues


def _scan_loop_concat(lines: list[str]) -> list[FoundIssue]:
    issues: list[FoundIssue] = []
    last_for_indent: int | None = None
    for index, raw in enumerate(lines):
        if re.match(r"^\s*(def|class) ", raw) and last_for_indent is not None:
            last_for_indent = None
        for_match = _FOR_LINE.match(raw)
        if for_match:
            indent = len(raw) - len(raw.lstrip())
            last_for_indent = indent
            continue
        if _STR_APPEND.search(raw) and last_for_indent is not None:
            indent = len(raw) - len(raw.lstrip())
            if indent > last_for_indent:
                issues.append(
                    FoundIssue(
                        path="", line=index + 1,
                        category=ReviewCategory.PERFORMANCE_CONCERN,
                        severity=Severity.INFO,
                        title="String concatenation inside a loop",
                        message="Repeated `+=` string concatenation in a loop "
                        "is O(n^2) in Python; prefer building a list and "
                        "joining.",
                        confidence=0.3,
                        check="loop_concat_check",
                        suggestion="Collect parts in a list and `''.join(...)` "
                        "after the loop.",
                    )
                )
                last_for_indent = None
    return issues


def scan_file(
    path: str,
    content: str,
    *,
    language: str | None = None,
) -> list[FoundIssue]:
    """Deterministic source scan of one file.

    Returns bounded per-file checks (bugs + review categories). Specialised
    project-level checks are NOT here.
    """
    if not content or not content.strip():
        return []
    lines = content.splitlines()
    lang = _language_of(language)
    issues: list[FoundIssue] = []
    issues.extend(_scan_null_deref(lines))
    issues.extend(_scan_division_by_zero(lines))
    if lang in ("python", "py"):
        issues.extend(_scan_bare_except(lines))
        issues.extend(_scan_loop_concat(lines))
    issues.extend(_scan_secrets(lines))
    issues.extend(_scan_todo_markers(lines))
    return issues