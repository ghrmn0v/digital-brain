"""Client-facing Brain API methods (Phase 8 Slice 3).

A fixed, additive enum of every operation a platform-independent client may
call. Adding a new method is a backward-compatible change (a consumer that does
not know a method should treat it as unimplemented, never fatal).

Grouped by the BrainService surface they mirror:

- system:              ping, describe
- ingest:              ingest
- learning write:      record_feedback
- people write:        record_preference
- understanding:       understand
- context:             build_context
- reasoning:           analyze_developer, reason
- people reads:        preferences, developer_preferences, people_summary,
                        people_timeline
- learning reads:      learning_status, feedback_history, personalization_profile

Only contracts here — no implementation logic.
"""

from __future__ import annotations

from enum import Enum


class ApiMethod(str, Enum):
    """The method name a client sends inside an :class:`ApiRequest`."""

    # -- system ---------------------------------------------------------------
    PING = "ping"
    DESCRIBE = "describe"

    # -- ingest / learning write ---------------------------------------------
    INGEST = "ingest"
    RECORD_FEEDBACK = "record_feedback"
    RECORD_PREFERENCE = "record_preference"

    # -- understanding / context ---------------------------------------------
    UNDERSTAND = "understand"
    BUILD_CONTEXT = "build_context"

    # -- reasoning (Developer Mode) ------------------------------------------
    ANALYZE_DEVELOPER = "analyze_developer"
    REASON = "reason"

    # -- people reads ----------------------------------------------------------
    PREFERENCES = "preferences"
    DEVELOPER_PREFERENCES = "developer_preferences"
    PEOPLE_SUMMARY = "people_summary"
    PEOPLE_TIMELINE = "people_timeline"

    # -- learning reads --------------------------------------------------------
    LEARNING_STATUS = "learning_status"
    FEEDBACK_HISTORY = "feedback_history"
    PERSONALIZATION_PROFILE = "personalization_profile"