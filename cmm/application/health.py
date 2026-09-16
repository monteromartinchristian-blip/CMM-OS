"""Phase 11.3 — the health application service.

``HealthApplicationService`` projects the readiness of the application
composition into the safe public :class:`~cmm.application.contracts.ApplicationHealth`
value.  It owns no health state: Phase 11.1 already owns composition readiness,
and duplicating it here would create a second readiness authority.

Two boundaries are deliberate:

- the constructor accepts only a real
  :class:`~cmm.platform.container.ApplicationContainer`, never a structurally
  similar object that merely exposes ``state`` and ``snapshot``;
- ``get_health()`` reads ``container.state`` first and only then the ready
  composition snapshot, and it never resolves a service.  A not-ready
  composition reports ``degraded`` with ``platform_ready=False`` and no service
  list, so the raw container failure — a path, a stack trace or an internal
  reason — can never cross the public boundary.

Only the allowlisted service identifiers of the Phase 11.1 snapshot are
projected.  Implementation identities, contract owners, bound implementations
and descriptor metadata are never exposed, so health stays a readiness
projection rather than an inspection or metrics surface.

See ``docs/reference/phase-11-application-backend.md``.
"""

from __future__ import annotations

from cmm.application.contracts import APPLICATION_API_VERSION, ApplicationHealth
from cmm.platform.container import ApplicationContainer
from cmm.platform.contracts import ContainerState

__all__ = [
    "HEALTH_STATUS_DEGRADED",
    "HEALTH_STATUS_OK",
    "HealthApplicationService",
]

#: Public health status of a ready composition.
HEALTH_STATUS_OK = "ok"

#: Public health status of a composition that is not ready.
HEALTH_STATUS_DEGRADED = "degraded"


class HealthApplicationService:
    """Public-safe readiness projection over the Phase 11.1 composition."""

    def __init__(self, container: ApplicationContainer) -> None:
        if not isinstance(container, ApplicationContainer):
            raise TypeError(
                "container must be a Phase 11.1 ApplicationContainer, "
                f"not {type(container).__name__}"
            )
        self._container = container

    def get_health(self) -> ApplicationHealth:
        """Return the safe public readiness of the application composition."""

        if self._container.state is not ContainerState.READY:
            # Not ready means there is nothing safe to project: the snapshot is
            # unavailable and the recorded failure stays inside the platform.
            return ApplicationHealth(
                status=HEALTH_STATUS_DEGRADED,
                api_version=APPLICATION_API_VERSION,
                platform_ready=False,
                services=(),
            )

        snapshot = self._container.snapshot()
        return ApplicationHealth(
            status=HEALTH_STATUS_OK,
            api_version=APPLICATION_API_VERSION,
            platform_ready=True,
            services=tuple(service.service_id for service in snapshot.services),
        )
