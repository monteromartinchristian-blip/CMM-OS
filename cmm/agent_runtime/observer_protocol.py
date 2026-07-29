"""Phase 9.4 – Observer Protocol and Metadata.

Defines the Observer Protocol interface and declaration metadata for system state observers.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from cmm.agent_runtime.enums import ObserverStatus
from cmm.agent_runtime.observation_contracts import (
    ObservationRequest,
    ObservationResult,
)


@runtime_checkable
class Observer(Protocol):
    """Minimal protocol contract for all Observation Engine observers."""

    name: str
    version: str

    def supports(self, request: ObservationRequest) -> bool:
        """Return True if this observer can fulfill the given observation request."""
        ...

    def observe(self, request: ObservationRequest) -> ObservationResult:
        """Execute observation and return structured result without mutating the target system."""
        ...


class ObserverMetadataMixin:
    """Helper mixin / standard attribute holder for concrete Observers."""

    name: str = "BaseObserver"
    version: str = "1.0.0"
    capabilities: tuple[str, ...] = ("state_observation",)
    scope: tuple[str, ...] = ("global",)
    status: ObserverStatus = ObserverStatus.AVAILABLE
    approximate_cost: float = 0.0
    required_permissions: tuple[str, ...] = ()
    supported_sensitivity: tuple[str, ...] = ("internal", "public")
    default_timeout: float = 30.0
