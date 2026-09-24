"""Action planning models (Phase 6).

The Brain ONLY proposes. ``ActionPlan`` wraps the existing contract
``BrainDecision`` (whose ``proposed_actions`` are pure-data ``ProposedAction``
records) plus a lightweight trace so reasoning→action provenance is preserved.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from contracts.common.ids import UserId
from contracts.decisions.decisions import BrainDecision, ProposedAction
from contracts.common.types import UtcDateTime


class ActionPlan(BaseModel):
    """A bounded set of proposals for one developer context."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    correlation_id: str
    decision: BrainDecision
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    created_at: UtcDateTime