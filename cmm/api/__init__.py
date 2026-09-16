"""Phase 11.3 — HTTP/OpenAPI/SSE adapter for the public application boundary.

This package is an adapter and owns no business, domain, agent, workflow,
operation, execution, validation, session or provider authority.  It adapts HTTP
transport concerns — path/method, transport DTO parsing, application service
invocation, public response serialization, HTTP status mapping and SSE
adaptation — onto ``cmm.application``.

It must never import canonical internal owners directly; it reaches the platform
only through the application layer.

See ``docs/reference/phase-11-application-backend.md``.
"""
