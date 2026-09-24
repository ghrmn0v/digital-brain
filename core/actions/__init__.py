"""Action Proposals (Phase 6).

Core Brain PROPOSES, Product EXECUTES after permission. This package only
builds pure-data proposals on the existing Phase 0 contracts; there is no
execution surface anywhere here.
"""

from __future__ import annotations

from .exceptions import ActionPlanningError, ActionValidationError
from .models import ActionPlan
from .planner import ActionPlanner

__all__ = [
    "ActionPlan",
    "ActionPlanner",
    "ActionPlanningError",
    "ActionValidationError",
]