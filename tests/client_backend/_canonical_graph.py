"""Phase 11.50 — the real canonical graph behind the client-backend tests.

Every Phase 11.50 test that needs a connected graph builds it here, from the
repository's own official composition root and canonical classes:

```text
build_local_application_runtime()   (cmm.application — the Phase 11.4 composition root)
  → official InMemorySessionStore + SessionApplicationService + ApplicationGateway
  → real Phase 11.2 Orchestrator
→ canonical SharedSessionConversationAdapter over the very same session store
→ canonical ConversationService
→ canonical ClientBackend
```

Nothing is mocked, subclassed or replaced.  ``_ObservedGatewayHandle`` wraps the
real gateway's bound ``handle`` method (the class itself is never touched) so a
test can count how many times the canonical application boundary was actually
entered — the traversal evidence for "zero downstream calls" and "exactly one
canonical path" assertions.

This helper is deliberately *not* a production seam: it lives in the test tree
and constructs nothing the production packages do not already compose.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cmm.application.capabilities import (
    CapabilityApplicationService,
    build_default_capabilities,
)
from cmm.application.contracts import ApplicationRequest, ApplicationResponse
from cmm.application.gateway import ApplicationGateway
from cmm.application.local_runtime import build_local_application_runtime
from cmm.client_backend.interface import ClientBackend
from cmm.conversation.capabilities import ConversationCapabilityResolver
from cmm.conversation.projection import ConversationResponseProjector
from cmm.conversation.service import ConversationService
from cmm.conversation.state import SharedSessionConversationAdapter
from cmm.runtime.sessions import InMemorySessionStore

__all__ = ["ClientBackendGraph", "build_client_backend_graph"]


class ObservedGatewayHandle:
    """Recording delegate in front of the real gateway's ``handle``.

    The delegate wraps the real bound method; the canonical
    ``ApplicationGateway`` class is never subclassed or replaced, so every
    observed call still lands on the one canonical gateway instance.
    """

    def __init__(self, gateway: ApplicationGateway) -> None:
        self.calls: list[tuple[ApplicationRequest, ApplicationResponse]] = []
        self._handle = gateway.handle
        gateway.handle = self  # type: ignore[method-assign]

    def __call__(self, request: ApplicationRequest) -> ApplicationResponse:
        response = self._handle(request)
        self.calls.append((request, response))
        return response

    def count(self) -> int:
        """Return the number of canonical gateway traversals observed."""

        return len(self.calls)


@dataclass(slots=True)
class ClientBackendGraph:
    """One connected canonical graph with the reusable client backend on top."""

    store: InMemorySessionStore
    gateway: ApplicationGateway
    conversation: ConversationService
    client: ClientBackend
    handle: ObservedGatewayHandle
    runtime: object
    observed_calls: list[tuple[ApplicationRequest, ApplicationResponse]] = field(
        default_factory=list
    )

    def canonical_gateway_calls(self) -> int:
        """Return how many times the canonical application boundary was entered."""

        return self.handle.count()

    def session_gateway_calls(self) -> int:
        """Return how many canonical traversals were session operations.

        Session create/get legitimately enter the one public gateway entrypoint
        (Phase 11.50 delegates session operations to the official Phase 11.3
        boundary through ``handle``), so a conversational assertion counts only
        the non-session traversals.
        """

        session_operations = {
            "sessions.create",
            "sessions.get",
        }
        return sum(
            1
            for request, _response in self.handle.calls
            if request.operation.value in session_operations
        )

    def conversation_gateway_calls(self) -> int:
        """Return how many canonical traversals were conversational operations."""

        return self.canonical_gateway_calls() - self.session_gateway_calls()


def build_client_backend_graph(
    *,
    model_boundary_capabilities: tuple[object, ...] = (),
    with_capability_declarations: bool = True,
) -> ClientBackendGraph:
    """Compose the real canonical graph and the facade over it.

    ``with_capability_declarations`` supplies the canonical Phase 11.3 public
    capability declarations to the facade through the canonical factory, which is
    what a composition root does; turning it off exercises the honest "no
    declaration supplied" path where every application-level row is unavailable.
    """

    runtime = build_local_application_runtime()
    handle = ObservedGatewayHandle(runtime.gateway)

    adapter = SharedSessionConversationAdapter(runtime.session_store)
    conversation = ConversationService(
        gateway=runtime.gateway,
        state=adapter,
        capabilities=ConversationCapabilityResolver(),
        projector=ConversationResponseProjector(),
    )

    # The canonical Phase 11.3 declaration set the composed runtime's own gateway
    # was built with, obtained from the official application service rather than
    # by reaching into the gateway.
    declarations = (
        CapabilityApplicationService(build_default_capabilities()).list_capabilities()
        if with_capability_declarations
        else ()
    )

    client = ClientBackend.from_capability_declarations(
        gateway=runtime.gateway,
        conversation=conversation,
        capability_declarations=declarations,  # type: ignore[arg-type]
        model_boundary_capabilities=model_boundary_capabilities,  # type: ignore[arg-type]
    )

    return ClientBackendGraph(
        store=runtime.session_store,
        gateway=runtime.gateway,
        conversation=conversation,
        client=client,
        handle=handle,
        runtime=runtime,
    )
