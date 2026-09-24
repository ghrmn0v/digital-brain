"""Brain Events (Phase 6): emit structured Developer Mode Brain Events.

Pure data only. The emitter serializes reasoning/proposals; the pipeline wires
reasoning → planning → events for the demo flow. No execution surface exists.
"""

from __future__ import annotations

from .emitter import BrainEventEmitter
from .pipeline import DevModePipeline, DevOutcome

__all__ = [
    "BrainEventEmitter",
    "DevModePipeline",
    "DevOutcome",
]