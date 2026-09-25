"""Reasoning ports (Phase 8 Slice 2).

Reasoning must never touch a learning-state database. It depends on this
read-only port; ``core.learning.LearningEngine`` satisfies it unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from contracts.common.ids import UserId

if TYPE_CHECKING:
    from core.learning.models import AssistanceProfile


@runtime_checkable
class LearningProfilePort(Protocol):
    """Read-only access to a user's explicitly learned personalization.

    Only explicit learned information is exposed; absent data stays absent.
    Implementations never infer or invent preferences.
    """

    def personalization_profile(self, user_id: UserId) -> "AssistanceProfile": ...