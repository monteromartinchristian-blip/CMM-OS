"""Phase 11.50 — Phase 11.1 composition contribution.

``build_client_backend_composition_module`` returns a side-effect-free
``StaticCompositionModule`` contribution containing the one Phase 11.50
top-layer service binding: ``client.backend``.  Phase 11.1 remains the
composition core: this module adds one service binding, changes no Phase 11.1
semantics, and ``cmm.platform`` never imports ``cmm.client_backend``.

The module constructs nothing.  The facade is an already-built object supplied by
the composition root, and the binding declares an enforceable runtime contract —
the exact concrete :class:`~cmm.client_backend.interface.ClientBackend` type — so
an unrelated object, and equally a *subclass* of the facade, can never claim the
public client-backend identity, not even through a hand-built binding.

``client-backend-public-facade`` is the only authority claimed here, and it is
deliberately a *facade* authority: the layer owns no session, conversation,
routing, model, provider, privacy, approval, validation or storage authority.  No
second container, registry or resolver is created.

The two declared dependencies are the existing canonical services the facade
actually delegates to — ``application.gateway`` and ``conversation.service`` —
so both edges point *downward* at the closed owners.  The Phase 11.21
``model.gateway`` is deliberately **not** a declared dependency: the client must
never acquire model execution authority through composition.  Model-boundary
capability facts travel as read-only declarations supplied to the facade by the
composition root instead.

See ``docs/superpowers/specs/2026-09-25-phase-11.50-reusable-backend-interfaces-design.md``
(sections 39 and 40) and ``docs/reference/phase-11-reusable-backend-interfaces.md``.
"""

from __future__ import annotations

from typing import Any

from cmm.client_backend.contracts import (
    CLIENT_BACKEND_MODULE_ID,
    CLIENT_BACKEND_SERVICE_ID,
)
from cmm.client_backend.interface import ClientBackend
from cmm.platform.contracts import (
    ContractMetadata,
    ServiceBinding,
    ServiceDependency,
    ServiceDescriptor,
    ServiceMode,
)
from cmm.platform.modules import StaticCompositionModule

__all__ = [
    "APPLICATION_GATEWAY_CONTRACT_VERSION",
    "APPLICATION_GATEWAY_DEPENDENCY_ID",
    "APPLICATION_GATEWAY_OWNER",
    "APPLICATION_GATEWAY_SCHEMA_VERSION",
    "CLIENT_BACKEND_AUTHORITY",
    "CLIENT_BACKEND_CONTRACT_VERSION",
    "CLIENT_BACKEND_OWNER",
    "CLIENT_BACKEND_SCHEMA_VERSION",
    "CONVERSATION_CONTRACT_VERSION",
    "CONVERSATION_DEPENDENCY_ID",
    "CONVERSATION_OWNER",
    "CONVERSATION_SCHEMA_VERSION",
    "build_client_backend_composition_module",
]

CLIENT_BACKEND_OWNER = "cmm.client_backend"
CLIENT_BACKEND_CONTRACT_VERSION = "1.0.0"
CLIENT_BACKEND_SCHEMA_VERSION = "1"

#: The one authority the reusable client backend claims: a public facade.  It is
#: not an execution, session, conversation or model authority.
CLIENT_BACKEND_AUTHORITY = "client-backend-public-facade"

#: The canonical Phase 11.3 service the facade delegates session and message
#: operations to.
APPLICATION_GATEWAY_DEPENDENCY_ID = "application.gateway"
APPLICATION_GATEWAY_OWNER = "cmm.application"
APPLICATION_GATEWAY_CONTRACT_VERSION = "1.0.0"
APPLICATION_GATEWAY_SCHEMA_VERSION = "1"

#: The canonical Phase 11.5 service the facade delegates conversation operations
#: to.
CONVERSATION_DEPENDENCY_ID = "conversation.service"
CONVERSATION_OWNER = "cmm.conversation"
CONVERSATION_CONTRACT_VERSION = "1.0.0"
CONVERSATION_SCHEMA_VERSION = "1"


def _boundary_contract(service_id: str) -> ContractMetadata:
    return ContractMetadata(
        contract_name=service_id,
        contract_version=CLIENT_BACKEND_CONTRACT_VERSION,
        schema_version=CLIENT_BACKEND_SCHEMA_VERSION,
        owner=CLIENT_BACKEND_OWNER,
    )


def _application_gateway_contract() -> ContractMetadata:
    return ContractMetadata(
        contract_name=APPLICATION_GATEWAY_DEPENDENCY_ID,
        contract_version=APPLICATION_GATEWAY_CONTRACT_VERSION,
        schema_version=APPLICATION_GATEWAY_SCHEMA_VERSION,
        owner=APPLICATION_GATEWAY_OWNER,
    )


def _conversation_contract() -> ContractMetadata:
    return ContractMetadata(
        contract_name=CONVERSATION_DEPENDENCY_ID,
        contract_version=CONVERSATION_CONTRACT_VERSION,
        schema_version=CONVERSATION_SCHEMA_VERSION,
        owner=CONVERSATION_OWNER,
    )


def _implementation_id(implementation: Any) -> str:
    implementation_type = type(implementation)
    return f"{implementation_type.__module__}.{implementation_type.__qualname__}"


def build_client_backend_composition_module(
    *, service: ClientBackend
) -> StaticCompositionModule:
    """Return the Phase 11.1 contribution for the reusable client backend.

    The builder constructs no subsystem: the facade is an already-constructed
    object supplied by the composition root, and anything that is not the exact
    concrete Phase 11.50 facade type fails closed — a facade subclass may
    override authority-bearing behaviour, so ``isinstance(...)`` is deliberately
    not the gate here (Audit V1 MAJOR-02).
    """

    if type(service) is not ClientBackend:
        raise TypeError(
            "service must be the exact concrete Phase 11.50 ClientBackend, "
            f"not {type(service).__name__}"
        )

    binding = ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id=CLIENT_BACKEND_SERVICE_ID,
            contract=_boundary_contract(CLIENT_BACKEND_SERVICE_ID),
            implementation_id=_implementation_id(service),
            dependencies=(
                ServiceDependency(
                    service_id=APPLICATION_GATEWAY_DEPENDENCY_ID,
                    contract=_application_gateway_contract(),
                ),
                ServiceDependency(
                    service_id=CONVERSATION_DEPENDENCY_ID,
                    contract=_conversation_contract(),
                ),
            ),
            mode=ServiceMode.LOCAL,
            authority=CLIENT_BACKEND_AUTHORITY,
        ),
        implementation=service,
        runtime_contract=ClientBackend,
    )

    return StaticCompositionModule(CLIENT_BACKEND_MODULE_ID, (binding,))
