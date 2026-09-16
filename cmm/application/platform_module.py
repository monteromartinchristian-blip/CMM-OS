"""Phase 11.3 — Phase 11.1 composition contribution.

``build_application_composition_module`` returns a side-effect-free
``StaticCompositionModule`` contribution containing the one public application
service binding: ``application.gateway``.  Phase 11.1 remains the composition
core: this module adds a new service binding, changes no Phase 11.1 semantics,
and ``cmm.platform`` never imports ``cmm.application``.

The module constructs nothing.  The gateway is an already-built object supplied
by the composition root, and every binding declares an enforceable runtime
contract — the concrete :class:`~cmm.application.gateway.ApplicationGateway` —
so an unrelated object can never claim the public application identity, not even
through a hand-built binding.

``application-public-gateway`` is the only authority claimed here.  No provider,
domain, agent, workflow, execution, validation, memory, knowledge or
orchestration authority is claimed, claimed twice or re-declared, and the one
declared dependency (the Phase 11.2 ``orchestration.orchestrator``) is a real
graph edge: composing the application module without the orchestration
contribution fails closed instead of reaching ``READY``.

See ``docs/reference/phase-11-application-backend.md``.
"""

from __future__ import annotations

from typing import Any

from cmm.application.gateway import ApplicationGateway
from cmm.platform.contracts import (
    ContractMetadata,
    ServiceBinding,
    ServiceDependency,
    ServiceDescriptor,
    ServiceMode,
)
from cmm.platform.modules import StaticCompositionModule

__all__ = [
    "APPLICATION_AUTHORITY",
    "APPLICATION_CONTRACT_VERSION",
    "APPLICATION_MODULE_ID",
    "APPLICATION_OWNER",
    "APPLICATION_SCHEMA_VERSION",
    "APPLICATION_SERVICE_ID",
    "ORCHESTRATOR_CONTRACT_VERSION",
    "ORCHESTRATOR_DEPENDENCY_ID",
    "ORCHESTRATOR_OWNER",
    "ORCHESTRATOR_SCHEMA_VERSION",
    "build_application_composition_module",
]

APPLICATION_MODULE_ID = "application"
APPLICATION_SERVICE_ID = "application.gateway"
APPLICATION_OWNER = "cmm.application"
APPLICATION_CONTRACT_VERSION = "1.0.0"
APPLICATION_SCHEMA_VERSION = "1"

#: The one exclusive authority the application layer owns.
APPLICATION_AUTHORITY = "application-public-gateway"

#: The canonical Phase 11.2 service the public gateway depends on.
ORCHESTRATOR_DEPENDENCY_ID = "orchestration.orchestrator"
ORCHESTRATOR_OWNER = "cmm.orchestration"

#: The Phase 11.2 boundary the gateway is built against.  Phase 11.1
#: compatibility is exact, so these mirror the orchestration boundary; the
#: composition gate test fails loudly if that boundary ever moves.
ORCHESTRATOR_CONTRACT_VERSION = "1.0.0"
ORCHESTRATOR_SCHEMA_VERSION = "1"


def _boundary_contract(service_id: str) -> ContractMetadata:
    return ContractMetadata(
        contract_name=service_id,
        contract_version=APPLICATION_CONTRACT_VERSION,
        schema_version=APPLICATION_SCHEMA_VERSION,
        owner=APPLICATION_OWNER,
    )


def _orchestrator_contract() -> ContractMetadata:
    return ContractMetadata(
        contract_name=ORCHESTRATOR_DEPENDENCY_ID,
        contract_version=ORCHESTRATOR_CONTRACT_VERSION,
        schema_version=ORCHESTRATOR_SCHEMA_VERSION,
        owner=ORCHESTRATOR_OWNER,
    )


def _implementation_id(implementation: Any) -> str:
    implementation_type = type(implementation)
    return f"{implementation_type.__module__}.{implementation_type.__qualname__}"


def build_application_composition_module(*, gateway: Any) -> StaticCompositionModule:
    """Return the Phase 11.1 contribution for the public application gateway.

    The builder constructs no subsystem: the gateway is an already-constructed
    object supplied by the composition root, and anything that is not the
    concrete Phase 11.3 gateway fails closed.
    """

    if not isinstance(gateway, ApplicationGateway):
        raise TypeError(
            "gateway must be the concrete Phase 11.3 ApplicationGateway, "
            f"not {type(gateway).__name__}"
        )

    binding = ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id=APPLICATION_SERVICE_ID,
            contract=_boundary_contract(APPLICATION_SERVICE_ID),
            implementation_id=_implementation_id(gateway),
            dependencies=(
                ServiceDependency(
                    service_id=ORCHESTRATOR_DEPENDENCY_ID,
                    contract=_orchestrator_contract(),
                ),
            ),
            mode=ServiceMode.LOCAL,
            authority=APPLICATION_AUTHORITY,
        ),
        implementation=gateway,
        runtime_contract=ApplicationGateway,
    )

    return StaticCompositionModule(APPLICATION_MODULE_ID, (binding,))
