"""Wave F — the macOS Computer Use capability of CMM OS.

Structured Accessibility-first observation, a normalized action vocabulary,
one approval policy authority, and a bounded cancellable execution loop. The
macOS runtime (pyobjc) is imported lazily so tests and other platforms use
fake runtimes; nothing here talks to model providers directly — planning is
injected through the canonical model-execution seam.
"""

from cmm.computer.contracts import (
    Action,
    ActionResult,
    ApprovalProposal,
    ComputerTaskOutcome,
    ComputerUseLimits,
    ElementInfo,
    Observation,
    PermissionState,
    WindowInfo,
)
from cmm.computer.bridge import BridgeClient, BridgeUnavailable
from cmm.computer.errors import COMPUTER_ERROR_CODES, ComputerUseError
from cmm.computer.loop import ApprovalGate, ComputerUseService
from cmm.computer.runtime_bridge import BridgeComputerRuntime
from cmm.computer.policy import PolicyDecision, classify_action

__all__ = [
    "BridgeClient",
    "BridgeComputerRuntime",
    "BridgeUnavailable",
    "COMPUTER_ERROR_CODES",
    "Action",
    "ActionResult",
    "ApprovalGate",
    "ApprovalProposal",
    "ComputerTaskOutcome",
    "ComputerUseError",
    "ComputerUseLimits",
    "ComputerUseService",
    "ElementInfo",
    "Observation",
    "PermissionState",
    "PolicyDecision",
    "WindowInfo",
    "classify_action",
]
