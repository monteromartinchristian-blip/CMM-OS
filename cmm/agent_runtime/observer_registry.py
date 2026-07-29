"""Phase 9.4 – Observer Registry.

Manages registration, lifecycle status, resolution, and availability checking of Observers.
Does not execute observations.
"""

from __future__ import annotations

from cmm.agent_runtime.enums import ObserverStatus
from cmm.agent_runtime.errors import (
    DuplicateObserverError,
    InvalidObservationContractError,
    ObserverNotFoundError,
)
from cmm.agent_runtime.observation_contracts import ObservationRequest
from cmm.agent_runtime.observer_protocol import Observer


class ObserverRegistry:
    """Central registry for discovering, enabling, disabling, and resolving Observers."""

    def __init__(self) -> None:
        self._observers: dict[str, Observer] = {}
        self._statuses: dict[str, ObserverStatus] = {}

    def register(self, observer: Observer) -> None:
        """Register an observer.

        Raises:
            DuplicateObserverError: If an observer with the same name is already registered.
            InvalidObservationContractError: If the observer does not satisfy the Observer protocol.
        """
        if not isinstance(observer, Observer) and not (
            hasattr(observer, "name")
            and hasattr(observer, "version")
            and hasattr(observer, "supports")
            and hasattr(observer, "observe")
        ):
            raise InvalidObservationContractError(
                f"Object {observer!r} does not satisfy the Observer protocol"
            )

        name = getattr(observer, "name", None)
        if not name or not isinstance(name, str) or not name.strip():
            raise InvalidObservationContractError(
                "Observer name must be a non-empty string"
            )

        if name in self._observers:
            raise DuplicateObserverError(
                f"Observer with name '{name}' is already registered"
            )

        status = getattr(observer, "status", ObserverStatus.AVAILABLE)
        if not isinstance(status, ObserverStatus):
            status = ObserverStatus.AVAILABLE

        self._observers[name] = observer
        self._statuses[name] = status

    def get(self, name: str) -> Observer | None:
        """Retrieve a registered observer by name."""
        return self._observers.get(name)

    def list_all(self) -> list[Observer]:
        """List all registered observers."""
        return list(self._observers.values())

    def enable(self, name: str) -> None:
        """Enable a registered observer."""
        if name not in self._observers:
            raise ObserverNotFoundError(f"Observer '{name}' not found in registry")
        self._statuses[name] = ObserverStatus.AVAILABLE

    def disable(self, name: str) -> None:
        """Disable a registered observer."""
        if name not in self._observers:
            raise ObserverNotFoundError(f"Observer '{name}' not found in registry")
        self._statuses[name] = ObserverStatus.DISABLED

    def is_available(self, name: str) -> bool:
        """Check if an observer is registered and available (not disabled or unavailable)."""
        if name not in self._observers:
            return False
        status = self._statuses.get(name)
        return status in (ObserverStatus.AVAILABLE, ObserverStatus.REGISTERED)

    def get_status(self, name: str) -> ObserverStatus:
        """Get the current operational status of an observer."""
        if name not in self._observers:
            raise ObserverNotFoundError(f"Observer '{name}' not found in registry")
        return self._statuses[name]

    def resolve_observers(self, request: ObservationRequest) -> list[Observer]:
        """Resolve all registered and enabled observers that support the given request.

        If request.observer_names is specified, filters to those requested observers.
        """
        target_names = (
            set(request.observer_names)
            if request.observer_names
            else set(self._observers.keys())
        )
        resolved: list[Observer] = []

        for name in sorted(self._observers.keys()):
            if name in target_names and self.is_available(name):
                obs = self._observers[name]
                if obs.supports(request):
                    resolved.append(obs)

        return resolved
