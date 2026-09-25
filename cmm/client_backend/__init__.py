"""Phase 11.50 — the reusable first-party client backend public boundary.

This package is the smallest stable backend seam a first-party client (for
example CMMChat) consumes.  It is a **facade and capability projection only**:
it adapts the already-closed Phase 11.3 ``ApplicationGateway`` and Phase 11.5
``ConversationService`` and owns no execution authority of its own.  It creates
no second application gateway, conversation service, orchestrator, model
gateway, provider registry, model catalog, session store, conversation store,
router, runtime, engine, registry, repository, resolver, service locator, HTTP
server or event bus.

```text
first-party client
      ↓
cmm.client_backend
      ↓
ConversationService
      ↓
ApplicationGateway
      ↓
Orchestrator / existing canonical owners
```

The public surface is deliberately small and closed.  A first-party client needs
one import path — ``from cmm.client_backend import ...`` — and no internal module.

Capability truth is reported honestly: a Phase 11.21 model-boundary fact is
reported as ``boundary_only`` and never as end-to-end availability, a
response-event stream is never relabelled as token streaming, attachments stay
``reference_only`` and document upload stays ``unavailable``.

See ``docs/superpowers/specs/2026-09-25-phase-11.50-reusable-backend-interfaces-design.md``
and ``docs/reference/phase-11-reusable-backend-interfaces.md``.
"""

from __future__ import annotations

from cmm.application.contracts import APPLICATION_API_VERSION
from cmm.client_backend.capabilities import (
    ClientBackendCapabilities,
    ClientBackendCapabilityStatus,
)
from cmm.client_backend.contracts import (
    CLIENT_BACKEND_ERROR_MESSAGES,
    CLIENT_BACKEND_INTERFACE_VERSION,
    CLIENT_BACKEND_MODULE_ID,
    CLIENT_BACKEND_SERVICE_ID,
    ClientBackendError,
    ClientBackendErrorCode,
    ClientBackendRequest,
    ClientBackendResult,
    ClientOperation,
)
from cmm.client_backend.interface import ClientBackend
from cmm.client_backend.platform_module import build_client_backend_composition_module

__all__ = [
    "APPLICATION_API_VERSION",
    "CLIENT_BACKEND_ERROR_MESSAGES",
    "CLIENT_BACKEND_INTERFACE_VERSION",
    "CLIENT_BACKEND_MODULE_ID",
    "CLIENT_BACKEND_SERVICE_ID",
    "ClientBackend",
    "ClientBackendCapabilities",
    "ClientBackendCapabilityStatus",
    "ClientBackendError",
    "ClientBackendErrorCode",
    "ClientBackendRequest",
    "ClientBackendResult",
    "ClientOperation",
    "build_client_backend_composition_module",
]
