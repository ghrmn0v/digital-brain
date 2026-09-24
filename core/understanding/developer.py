"""Developer Mode input/output structures (transport-independent).

:class:`DeveloperContext` is how the Product layer hands repository/code
context to Core Brain. It does not assume an IDE, a CLI, an editor plugin or
any transport — it is plain validated data. :class:`DeveloperAnalysis` is the
Core Brain's structured result for that context.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from contracts.common.ids import UserId
from contracts.common.types import Confidence, ContractVersion

from .models import UnderstandingResult

TestStatus = Literal["passed", "failed", "skipped", "error"]

_EXT_LANGUAGE = {
    "py": "python",
    "ts": "typescript",
    "tsx": "typescript",
    "js": "javascript",
    "jsx": "javascript",
    "go": "go",
    "rs": "rust",
    "java": "java",
    "kt": "kotlin",
    "c": "c",
    "h": "c",
    "cpp": "cpp",
    "cc": "cpp",
    "cs": "csharp",
    "rb": "ruby",
    "php": "php",
    "swift": "swift",
    "sql": "sql",
    "html": "html",
    "css": "css",
    "scss": "css",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "sh": "shell",
    "md": "markdown",
}


class GitContext(BaseModel):
    """Snapshot of repository state at analysis time."""

    model_config = ConfigDict(extra="forbid")

    branch: str | None = None
    remote: str | None = None
    dirty: bool | None = None
    recent_commits: list[str] = Field(default_factory=list)


class DeveloperFile(BaseModel):
    """One file of code context."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=1024)
    content: str = Field(default="")
    language: str | None = None


class TestResultSnapshot(BaseModel):
    """One line of a test run, exactly as reported (never fabricated)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=512)
    status: TestStatus
    file: str | None = None
    message: str | None = Field(default=None, max_length=4096)


class DeveloperContext(BaseModel):
    """Everything Core Brain knows about a developer's current code state."""

    model_config = ConfigDict(extra="forbid")

    version: ContractVersion = "v1"
    user_id: UserId
    repository: str = Field(min_length=1, max_length=512)
    root: str | None = Field(default=None, max_length=1024)
    files: list[DeveloperFile] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    current_file: str | None = Field(default=None, max_length=1024)
    current_line: int | None = Field(default=None, ge=1)
    git_context: GitContext | None = None
    test_results: list[TestResultSnapshot] = Field(default_factory=list)
    user_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Open context, e.g. role, task description, Developer Mode flag.",
    )


class DeveloperAnalysis(BaseModel):
    """Core Brain's structured understanding of a DeveloperContext."""

    model_config = ConfigDict(extra="forbid")

    version: ContractVersion = "v1"
    user_id: UserId
    repository: str
    provider: str = "unknown"
    fallback_used: bool = False
    understanding: UnderstandingResult
    files_analyzed: int = Field(default=0, ge=0)
    total_lines: int = Field(default=0, ge=0)
    languages: list[str] = Field(default_factory=list)
    focus_file: str | None = None
    focus_line: int | None = None
    confidence: Confidence


def language_of(path: str) -> str | None:
    """Best-effort language from a file extension (feeds analysis, not truth)."""
    if not path:
        return None
    stem = path.rsplit("/", 1)[-1]
    if "." not in stem:
        return None
    ext = stem.rsplit(".", 1)[-1].lower()
    return _EXT_LANGUAGE.get(ext)


def summarize_context(context: DeveloperContext) -> dict[str, Any]:
    """Trusted statistics derived directly from the context (never the LLM)."""
    lines = 0
    languages: set[str] = set()
    for file in context.files:
        lines += file.content.count("\n") + (1 if file.content else 0)
        language = file.language or language_of(file.path)
        if language:
            languages.add(language)
    focus_file = context.current_file or None
    if focus_file is None and context.files:
        focus_file = context.files[0].path
    return {
        "files_analyzed": len(context.files),
        "total_lines": lines,
        "languages": sorted(languages),
        "focus_file": focus_file,
        "focus_line": context.current_line,
    }


def context_corpus(context: DeveloperContext, limit_chars: int = 20_000) -> str:
    """Concatenated, truncated source of the changed/current files."""
    picked_paths = set(context.changed_files)
    if context.current_file:
        picked_paths.add(context.current_file)
    blocks: list[str] = []
    used = 0
    for file in context.files:
        if file.path not in picked_paths:
            continue
        body = file.content or ""
        remaining = limit_chars - used
        if remaining <= 0:
            break
        blocks.append(f"--- {file.path} ---\n{body[:remaining]}")
        used += len(body[:remaining]) + len(file.path) + 20
    if not blocks:
        for file in context.files:
            body = file.content or ""
            remaining = limit_chars - used
            if remaining <= 0:
                break
            blocks.append(f"--- {file.path} ---\n{body[:remaining]}")
            used += len(body[:remaining]) + len(file.path) + 20
    return "\n\n".join(blocks) or "<no code content supplied>"