"""CMMChat Wave E0 — the canonical CMM OS model execution seam.

``cmm.model_execution`` makes one real model inference reachable from a
canonical conversational request without introducing any parallel authority.  It
imports the canonical Phase 11.2 decision contract and the canonical
``kernel.llm`` provider machinery, and nothing else owns model execution.

Public surface:

* :class:`~cmm.model_execution.executor.CanonicalModelExecutor` — the seam;
* :mod:`cmm.model_execution.composition` — the canonical CMMChat Router provider
  registration and the seam's composition builders;
* :mod:`cmm.model_execution.turn` — the canonical turn sequencing
  (conversation → canonical decision → seam);
* :mod:`cmm.model_execution.canary` — the live E0 canary entry point.

See ``docs/reference/phase-11-model-execution-canary.md``.
"""

from __future__ import annotations

from cmm.model_execution.contracts import (
    ModelExecutionErrorCode,
    ModelExecutionFailure,
    ModelExecutionParameters,
    ModelExecutionRequest,
    ModelExecutionResult,
    ModelExecutionStatus,
)
from cmm.model_execution.errors import ModelExecutionError
from cmm.model_execution.executor import CanonicalModelExecutor

__all__ = [
    "CanonicalModelExecutor",
    "ModelExecutionError",
    "ModelExecutionErrorCode",
    "ModelExecutionFailure",
    "ModelExecutionParameters",
    "ModelExecutionRequest",
    "ModelExecutionResult",
    "ModelExecutionStatus",
]
