"""Phase 11.5 — Phase 11.1 composition contribution.

``build_conversation_composition_module`` returns a side-effect-free
``StaticCompositionModule`` contribution containing the one public
conversational service binding: ``conversation.service``.  Phase 11.1 remains
the composition core: this module adds a new service binding, changes no Phase
11.1 semantics, and ``cmm.platform`` never imports ``cmm.conversation``.

The module constructs nothing.  The service is an already-built object supplied
by the composition root, and the binding declares an enforceable runtime
contract — the concrete :class:`~cmm.conversation.service.ConversationService` —
so an unrelated object can never claim the public conversational identity, not
even through a hand-built binding.

``conversation-public-interface`` is the only authority claimed here.  No
session, application, orchestration, provider, domain, agent, workflow,
execution, validation, memory, knowledge or bot authority is claimed, claimed
twice or re-declared, and the one declared dependency (the Phase 11.3
``application.gateway``) is a real graph edge that points toward the application
boundary — never backwards toward a client, UI or CMMChat surface.  Composing
the conversation contribution without the application contribution fails closed
instead of reaching ``READY``.

This module imports the platform composition contracts and its own package
only.  It never imports ``cmm.application``, ``cmm.orchestration``, the HTTP
adapter or any UI framework, and it defines no ``ConversationRuntime``, no
registry, no container and no module-level service singleton.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``
(sections 6, 24, 25 and 26).
"""

from __future__ import annotations

from typing import Any

from cmm.conversation.service import ConversationService
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
    "CONVERSATION_AUTHORITY",
    "CONVERSATION_CONTRACT_VERSION",
    "CONVERSATION_MODULE_ID",
    "CONVERSATION_OWNER",
    "CONVERSATION_SCHEMA_VERSION",
    "CONVERSATION_SERVICE_ID",
    "build_conversation_composition_module",
]

CONVERSATION_MODULE_ID = "phase11.conversation"
CONVERSATION_SERVICE_ID = "conversation.service"
CONVERSATION_OWNER = "cmm.conversation"
CONVERSATION_CONTRACT_VERSION = "1.0.0"
CONVERSATION_SCHEMA_VERSION = "1"

#: The one exclusive authority the conversational layer owns.
CONVERSATION_AUTHORITY = "conversation-public-interface"

#: The canonical Phase 11.3 service the public conversational service depends on.
APPLICATION_GATEWAY_DEPENDENCY_ID = "application.gateway"
APPLICATION_GATEWAY_OWNER = "cmm.application"

#: The Phase 11.3 boundary the service is built against.  Phase 11.1
#: compatibility is exact, so these mirror ``cmm/application/platform_module.py``'s
#: own metadata; the mirror test fails loudly if that boundary ever moves.
APPLICATION_GATEWAY_CONTRACT_VERSION = "1.0.0"
APPLICATION_GATEWAY_SCHEMA_VERSION = "1"


def _boundary_contract(service_id: str) -> ContractMetadata:
    return ContractMetadata(
        contract_name=service_id,
        contract_version=CONVERSATION_CONTRACT_VERSION,
        schema_version=CONVERSATION_SCHEMA_VERSION,
        owner=CONVERSATION_OWNER,
    )


def _application_gateway_contract() -> ContractMetadata:
    return ContractMetadata(
        contract_name=APPLICATION_GATEWAY_DEPENDENCY_ID,
        contract_version=APPLICATION_GATEWAY_CONTRACT_VERSION,
        schema_version=APPLICATION_GATEWAY_SCHEMA_VERSION,
        owner=APPLICATION_GATEWAY_OWNER,
    )


def _implementation_id(implementation: Any) -> str:
    implementation_type = type(implementation)
    return f"{implementation_type.__module__}.{implementation_type.__qualname__}"


def build_conversation_composition_module(
    *, service: ConversationService
) -> StaticCompositionModule:
    """Return the Phase 11.1 contribution for the conversational service.

    The builder constructs no subsystem: the service is an already-constructed
    object supplied by the composition root, and anything that is not the
    concrete Phase 11.5 conversational service fails closed.
    """

    if not isinstance(service, ConversationService):
        raise TypeError(
            "service must be the concrete Phase 11.5 ConversationService, "
            f"not {type(service).__name__}"
        )

    binding = ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id=CONVERSATION_SERVICE_ID,
            contract=_boundary_contract(CONVERSATION_SERVICE_ID),
            implementation_id=_implementation_id(service),
            dependencies=(
                ServiceDependency(
                    service_id=APPLICATION_GATEWAY_DEPENDENCY_ID,
                    contract=_application_gateway_contract(),
                ),
            ),
            mode=ServiceMode.LOCAL,
            authority=CONVERSATION_AUTHORITY,
        ),
        implementation=service,
        runtime_contract=ConversationService,
    )

    return StaticCompositionModule(CONVERSATION_MODULE_ID, (binding,))
