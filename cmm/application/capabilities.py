"""Phase 11.3 — the capability application service.

``CapabilityApplicationService`` projects the public capability declarations of
the v1 application backend.  Capability discovery is **descriptive**: the set is
an explicit, frozen declaration list, so availability can never be inferred from
an import path, a module name, a route name or the mere existence of a class.

That is the whole point of the seam.  Four capability statuses are possible —
``AVAILABLE``, ``UNAVAILABLE`` and ``DEFERRED`` are the public ones — and the
initial v1 set distinguishes them honestly:

- ``AVAILABLE`` capabilities have a real public owner in this phase;
- ``request-cancellation`` is ``UNAVAILABLE``: Phase 11.3 exposes the stable
  cancellation surface but no canonical cancellable owner exists for it;
- the remaining capabilities are ``DEFERRED``: no owner exists yet, so no
  operation, route or placeholder behavior may be fabricated for them.

No capability declaration carries a class name, a module name or a runtime
object, so discovery can never leak an implementation identity or become a
second registry.  The declaration order is canonical (sorted by capability ID)
so two calls in two processes produce the same public result.

See ``docs/reference/phase-11-application-backend.md``.
"""

from __future__ import annotations

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationCapability,
    ApplicationOperation,
    CapabilityStatus,
)

__all__ = [
    "REASON_CANCELLATION_UNAVAILABLE",
    "REASON_OWNER_NOT_IMPLEMENTED",
    "CapabilityApplicationService",
    "build_default_capabilities",
]

#: The cancellation surface exists but has no canonical cancellable owner.
REASON_CANCELLATION_UNAVAILABLE = "NO_CANCELLABLE_OWNER"

#: The capability names a subsystem that Phase 11.3 does not own yet.
REASON_OWNER_NOT_IMPLEMENTED = "OWNER_NOT_IMPLEMENTED"


def _available(
    capability_id: str,
    *operations: ApplicationOperation,
) -> ApplicationCapability:
    """Declare one capability whose public owner exists in this phase."""

    return ApplicationCapability(
        capability_id=capability_id,
        status=CapabilityStatus.AVAILABLE,
        version=APPLICATION_API_VERSION,
        operations=tuple(operation.value for operation in operations),
    )


def _unavailable(
    capability_id: str,
    reason_code: str,
) -> ApplicationCapability:
    """Declare one capability whose public surface exists but has no owner."""

    return ApplicationCapability(
        capability_id=capability_id,
        status=CapabilityStatus.UNAVAILABLE,
        version=APPLICATION_API_VERSION,
        reason_code=reason_code,
    )


def _deferred(capability_id: str) -> ApplicationCapability:
    """Declare one capability that belongs to later roadmap work."""

    return ApplicationCapability(
        capability_id=capability_id,
        status=CapabilityStatus.DEFERRED,
        version=APPLICATION_API_VERSION,
        reason_code=REASON_OWNER_NOT_IMPLEMENTED,
    )


def build_default_capabilities() -> tuple[ApplicationCapability, ...]:
    """Return the frozen initial v1 capability declarations.

    The declarations are explicit constants.  Nothing here inspects imports,
    registries or live owners, so a capability can only become available by
    declaring it in this function.
    """

    declarations = (
        _available("capabilities", ApplicationOperation.CAPABILITIES_LIST),
        _available("health", ApplicationOperation.HEALTH_GET),
        _available("messages", ApplicationOperation.MESSAGE_SUBMIT),
        # Streaming is delivered by the public SSE surface.  It declares no
        # operation because the frozen public operation identity set has no
        # streaming entry; inventing one here would fabricate a public identity.
        _available("streaming"),
        _available(
            "sessions",
            ApplicationOperation.SESSION_CREATE,
            ApplicationOperation.SESSION_GET,
        ),
        _unavailable(
            "request-cancellation",
            REASON_CANCELLATION_UNAVAILABLE,
        ),
        _deferred("agents"),
        _deferred("backups"),
        _deferred("domains"),
        _deferred("metrics"),
        _deferred("model-routing"),
        _deferred("plugins"),
    )

    return tuple(sorted(declarations, key=lambda item: item.capability_id))


class CapabilityApplicationService:
    """Projects the explicit public capability declarations of the backend."""

    def __init__(self, capabilities: tuple[ApplicationCapability, ...]) -> None:
        if not isinstance(capabilities, tuple):
            raise TypeError(
                "capabilities must be an immutable tuple of ApplicationCapability "
                f"values, not {type(capabilities).__name__}"
            )
        for capability in capabilities:
            if not isinstance(capability, ApplicationCapability):
                raise TypeError(
                    "capabilities must contain ApplicationCapability values"
                )

        identifiers = [
            capability.capability_id for capability in capabilities
        ]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("capabilities must not declare a duplicate capability ID")

        self._capabilities = tuple(capabilities)

    def list_capabilities(self) -> tuple[ApplicationCapability, ...]:
        """Return the declared capabilities in canonical declaration order."""

        return self._capabilities
