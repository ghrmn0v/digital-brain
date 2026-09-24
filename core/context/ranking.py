"""Deterministic, explainable relevance ranking (Phase 4).

No embeddings, no ML, no opaque AI: each factor is a documented rule in [0, 1]
and the final score is a weighted, normalized sum. ``ranking_reason`` records
every factor so a score can always be explained and reproduced.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Mapping

from contracts.memory.memory import Memory, MemoryStatus

from .fields import is_bug_finding, is_decision, memory_file, memory_repository, normalize_repository
from .models import ScoredMemory, SearchQuery

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> frozenset[str]:
    """Lowercase alphanumeric token set (deterministic; underscores kept)."""
    if not text:
        return frozenset()
    return frozenset(_TOKEN_RE.findall(text.lower()))


def dice(left: frozenset[str], right: frozenset[str]) -> float:
    """Dice coefficient in [0, 1]; 0 when either side is empty."""
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    return (2.0 * overlap) / (len(left) + len(right))


_REPOSITORY_SCORE = {
    "exact": 1.0,
    "related": 0.8,
    "other": 0.1,
    "unknown": 0.6,
    "none": 1.0,
}

_FILE_SCORE = {
    "exact": 1.0,
    "same_name": 0.8,
    "other": 0.3,
    "unknown": 0.7,
    "none": 1.0,
}

_HISTORICAL_STATUS_SCORE = 0.3


@dataclass(frozen=True)
class RankConfig:
    """Factor weights (sum need not be 1; it is normalized for you)."""

    w_lexical: float = 0.35
    w_repository: float = 0.20
    w_file: float = 0.15
    w_importance: float = 0.12
    w_recency: float = 0.10
    w_status: float = 0.04
    w_type: float = 0.04
    recency_half_life_days: float = 30.0
    min_score: float = 0.05
    type_weights: Mapping[str, float] = field(default_factory=dict)

    def factors(self) -> tuple[tuple[str, float], ...]:
        return (
            ("lexical", self.w_lexical),
            ("repository", self.w_repository),
            ("file", self.w_file),
            ("importance", self.w_importance),
            ("recency", self.w_recency),
            ("status", self.w_status),
            ("type", self.w_type),
        )


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


class Ranker:
    """Scores memories against a :class:`SearchQuery` deterministically."""

    def __init__(
        self,
        config: RankConfig | None = None,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        weights = config or RankConfig()
        if any(weight < 0 for _, weight in weights.factors()):
            raise ValueError("all ranking weights must be >= 0")
        if weights.recency_half_life_days <= 0:
            raise ValueError("recency_half_life_days must be > 0")
        self._config = weights
        self._now = now or (lambda: datetime.now(timezone.utc))

    def rank(
        self,
        query: SearchQuery,
        memories: list[Memory],
    ) -> list[ScoredMemory]:
        """Rank memories for a query; irrelevant memories are excluded."""
        query_text = " ".join(
            part
            for part in (query.text, *query.keywords)
            if isinstance(part, str) and part.strip()
        )
        query_tokens = tokenize(query_text)

        target_repo = (
            normalize_repository(query.repository)
            if query.repository
            else None
        )
        target_file = query.current_file or None

        results = [self._score(memory, query, query_tokens, target_repo, target_file) for memory in memories]
        results = [result for result in results if result is not None]
        results.sort(key=lambda r: (-r.score, r.memory.memory_id))
        return results

    def _score(
        self,
        memory: Memory,
        query: SearchQuery,
        query_tokens: frozenset[str],
        target_repo: str | None,
        target_file: str | None,
    ) -> ScoredMemory | None:
        content_tokens = tokenize(memory.content)
        lexical = dice(query_tokens, content_tokens)

        repo_score, repo_match = self._repo_factor(target_repo, memory)
        file_score, file_match = self._file_factor(target_file, memory)

        importance = float(memory.importance)
        recency = self._recency(memory)
        status_score = 1.0 if memory.status == MemoryStatus.ACTIVE else _HISTORICAL_STATUS_SCORE
        type_score = float(self._config.type_weights.get(memory.type.value, 1.0))

        matched = (
            lexical > 0.0
            or repo_match in {"exact", "related"}
            or file_match in {"exact", "same_name"}
        )
        if not matched:
            return None

        factors = {
            "lexical": lexical,
            "repository": repo_score,
            "file": file_score,
            "importance": importance,
            "recency": recency,
            "status": status_score,
            "type": type_score,
        }
        weights = dict(self._config.factors())
        total = sum(weights.values())
        if total <= 0.0:
            total = 1.0
        score = sum(weights[name] / total * factor for name, factor in factors.items())
        if score < self._config.min_score:
            return None

        matched_fields = self._matched_fields(
            lexical, repo_match, file_match, memory
        )
        reason = (
            f"lex={lexical:.2f} repo={repo_score:.2f}({repo_match}) "
            f"file={file_score:.2f}({file_match}) imp={importance:.2f} "
            f"rec={recency:.2f} st={status_score:.2f} type={type_score:.2f} "
            f"=> {score:.3f}"
        )
        return ScoredMemory(
            memory=memory,
            score=round(score, 6),
            matched_fields=matched_fields,
            ranking_reason=reason,
            repository_match=repo_match,
            file_match=file_match,
        )

    @staticmethod
    def _repo_factor(
        target_repo: str | None, memory: Memory
    ) -> tuple[float, str]:
        stored = memory_repository(memory)
        if not target_repo:
            return _REPOSITORY_SCORE["none"], "none"
        if stored is None:
            return _REPOSITORY_SCORE["unknown"], "unknown"
        norm = normalize_repository(stored)
        if norm == target_repo:
            return _REPOSITORY_SCORE["exact"], "exact"
        if norm in target_repo or target_repo in norm:
            return _REPOSITORY_SCORE["related"], "related"
        return _REPOSITORY_SCORE["other"], "other"

    @staticmethod
    def _file_factor(target_file: str | None, memory: Memory) -> tuple[float, str]:
        stored = memory_file(memory)
        if not target_file:
            return _FILE_SCORE["none"], "none"
        if stored is None:
            return _FILE_SCORE["unknown"], "unknown"
        if target_file == stored:
            return _FILE_SCORE["exact"], "exact"
        if _basename(target_file) == _basename(stored):
            return _FILE_SCORE["same_name"], "same_name"
        return _FILE_SCORE["other"], "other"

    def _recency(self, memory: Memory) -> float:
        age_seconds = max(0.0, (self._now() - memory.updated_at).total_seconds())
        age_days = age_seconds / 86400.0
        half_life = self._config.recency_half_life_days
        return math.exp(-age_days / half_life)

    @staticmethod
    def _matched_fields(
        lexical: float, repo_match: str, file_match: str, memory: Memory
    ) -> list[str]:
        fields: list[str] = []
        if lexical > 0.0:
            fields.append("content")
        if repo_match in {"exact", "related"}:
            fields.append("repository")
        if file_match in {"exact", "same_name"}:
            fields.append("file")
        if is_bug_finding(memory) or is_decision(memory):
            fields.append("category")
        return fields