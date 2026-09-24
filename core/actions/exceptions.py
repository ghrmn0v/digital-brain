"""Action planning errors (Phase 6)."""

from __future__ import annotations


class ActionPlanningError(Exception):
    """Base class for all Action Planning errors."""


class ActionValidationError(ActionPlanningError):
    """Invalid input to the Action Planner."""