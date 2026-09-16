"""Phase 11.2 — authorized context resolution.

``ContextResolver`` determines which authorized context references are relevant
to the current request.  It owns no context source: the canonical session
authority stays ``cmm.runtime.sessions.SessionStore`` and every additional
collaborator is an explicit, constructor-injected read-only seam.  No context
registry, loader registry, cache or store is introduced here.

The resolver is two-stage on purpose.  Domain-specific context is only safe
once the canonical Domain Router has selected a domain, so:

``resolve_base``
    projects the caller's allowlisted references, the canonical shared session
    and any injected read-only reference seams;
``resolve_domain_context``
    extends that projection with the selected domain references and the
    canonical permission references carried by the domain route decision.

Only the minimum authorized projection is forwarded.  Source objects are never
copied into a public orchestration contract, non-allowlisted caller context is
withheld rather than forwarded, and missing context is reported rather than
invented.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from cmm.orchestration.contracts import (
    DomainRouteDecision,
    OrchestrationRequest,
    ResolvedContext,
)
from cmm.orchestration.errors import ContextResolutionError

if TYPE_CHECKING:
    from cmm.runtime.sessions import SessionStore

__all__ = [
    "ContextReferenceReader",
    "ContextResolver",
    "DefaultContextResolver",
]

#: The caller context keys Phase 11.2 forwards.  Every other key is withheld.
ALLOWED_CALLER_CONTEXT_KEYS = frozenset({"context_refs"})

#: Deterministic prefix for each projected reference source.
CALLER_REFERENCE_PREFIX = "caller"
SESSION_REFERENCE_PREFIX = "session"
GOAL_REFERENCE_PREFIX = "goal"
WORKFLOW_REFERENCE_PREFIX = "workflow"
MEMORY_REFERENCE_PREFIX = "memory"
KNOWLEDGE_REFERENCE_PREFIX = "knowledge"
EVENT_REFERENCE_PREFIX = "event"


@runtime_checkable
class ContextReferenceReader(Protocol):
    """Read-only seam for one non-session context source.

    A reader returns plain reference strings only.  It is not a registry, keeps
    no authoritative state, and is never asked to rank or transform data.
    """

    def list_references(self, *, request: OrchestrationRequest) -> tuple[str, ...]: ...


@runtime_checkable
class ContextResolver(Protocol):
    """Two-stage authorized context resolution boundary."""

    def resolve_base(self, request: OrchestrationRequest) -> ResolvedContext: ...

    def resolve_domain_context(
        self,
        request: OrchestrationRequest,
        base_context: ResolvedContext,
        domain_route: DomainRouteDecision,
    ) -> ResolvedContext: ...


def _references(value: object, field_name: str) -> tuple[str, ...]:
    """Normalize a sequence of non-empty reference strings, failing closed."""

    if isinstance(value, (str, bytes | bytearray)) or not isinstance(value, Sequence):
        raise ContextResolutionError(
            f"{field_name} must be a sequence of references",
            details={"field": field_name},
        )

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ContextResolutionError(
                f"{field_name} must contain non-empty references",
                details={"field": field_name},
            )
        normalized.append(item.strip())
    return tuple(normalized)


class DefaultContextResolver:
    """Read-only coordinator over canonical context sources."""

    def __init__(
        self,
        *,
        session_store: SessionStore | None,
        goal_reader: ContextReferenceReader | None = None,
        workflow_reader: ContextReferenceReader | None = None,
        memory_reader: ContextReferenceReader | None = None,
        knowledge_reader: ContextReferenceReader | None = None,
        recent_event_reader: ContextReferenceReader | None = None,
    ) -> None:
        self._session_store = session_store
        self._readers: tuple[tuple[str, ContextReferenceReader | None], ...] = (
            (GOAL_REFERENCE_PREFIX, goal_reader),
            (WORKFLOW_REFERENCE_PREFIX, workflow_reader),
            (MEMORY_REFERENCE_PREFIX, memory_reader),
            (KNOWLEDGE_REFERENCE_PREFIX, knowledge_reader),
            (EVENT_REFERENCE_PREFIX, recent_event_reader),
        )

    # ── Stage 1: base context ────────────────────────────────────────────────

    def resolve_base(self, request: OrchestrationRequest) -> ResolvedContext:
        """Return the base context projection for *request*."""

        if not isinstance(request, OrchestrationRequest):
            raise TypeError(
                f"request must be an OrchestrationRequest, got {type(request).__name__}"
            )

        reason_codes: list[str] = []
        missing_refs: list[str] = []
        references: list[str] = []

        session_ref, session_status, session_revision, session_reason = (
            self._resolve_session(request)
        )
        if session_ref is not None:
            references.append(f"{SESSION_REFERENCE_PREFIX}:{session_ref}")
        elif request.session_id is not None:
            missing_refs.append(f"{SESSION_REFERENCE_PREFIX}:{request.session_id}")
        if session_reason is not None:
            reason_codes.append(session_reason)

        for prefix, reader in self._readers:
            for reference in self._read_reader(reader, prefix, request):
                references.append(f"{prefix}:{reference}")

        caller_refs, withheld, caller_reason = self._resolve_caller_context(request)
        references.extend(f"{CALLER_REFERENCE_PREFIX}:{ref}" for ref in caller_refs)
        if caller_reason is not None:
            reason_codes.append(caller_reason)

        return ResolvedContext(
            request_id=request.request_id,
            stage="base",
            session_ref=session_ref,
            session_status=session_status,
            session_revision=session_revision,
            context_refs=tuple(references),
            missing_refs=tuple(missing_refs),
            withheld_field_count=withheld,
            reason_codes=tuple(reason_codes),
        )

    # ── Stage 2: authorized domain context ───────────────────────────────────

    def resolve_domain_context(
        self,
        request: OrchestrationRequest,
        base_context: ResolvedContext,
        domain_route: DomainRouteDecision,
    ) -> ResolvedContext:
        """Extend *base_context* with the selected domain's authorized refs.

        The domain stage cannot run before the canonical Domain Router has
        selected a primary domain, so this method requires a real
        :class:`DomainRouteDecision` carrying one.
        """

        if not isinstance(domain_route, DomainRouteDecision):
            raise TypeError(
                "domain_route must be a DomainRouteDecision, "
                f"got {type(domain_route).__name__}"
            )
        if not isinstance(base_context, ResolvedContext):
            raise TypeError(
                "base_context must be a ResolvedContext, "
                f"got {type(base_context).__name__}"
            )
        if domain_route.primary_domain is None:
            raise ContextResolutionError(
                "Authorized domain context requires a selected primary domain",
                details={"request_id": request.request_id},
            )

        # Canonical domain references are already fully qualified
        # (``domain:<slug>``), so they are projected verbatim.
        domain_refs = (
            domain_route.primary_domain,
            *domain_route.supporting_domains,
        )

        return ResolvedContext(
            request_id=base_context.request_id,
            stage="domain",
            session_ref=base_context.session_ref,
            session_status=base_context.session_status,
            session_revision=base_context.session_revision,
            context_refs=base_context.context_refs,
            domain_refs=domain_refs,
            permission_refs=domain_route.permission_refs,
            missing_refs=base_context.missing_refs,
            withheld_field_count=base_context.withheld_field_count,
            reason_codes=base_context.reason_codes,
        )

    # ── Collaborators ────────────────────────────────────────────────────────

    def _resolve_session(
        self, request: OrchestrationRequest
    ) -> tuple[str | None, str | None, int | None, str | None]:
        """Load the canonical shared session, if one was referenced."""

        if request.session_id is None:
            return None, None, None, None

        if self._session_store is None:
            raise ContextResolutionError(
                "A session was referenced but no canonical session store is composed",
                details={"request_id": request.request_id},
            )

        try:
            state = self._session_store.load(request.session_id)
        except Exception as error:
            raise ContextResolutionError(
                "Canonical session lookup failed",
                details={"request_id": request.request_id},
            ) from error

        if state is None:
            return None, None, None, "CONTEXT_SESSION_NOT_FOUND"

        return state.session_id, state.status, state.revision, "CONTEXT_SESSION_LOADED"

    def _read_reader(
        self,
        reader: ContextReferenceReader | None,
        prefix: str,
        request: OrchestrationRequest,
    ) -> tuple[str, ...]:
        if reader is None:
            return ()
        if not isinstance(reader, ContextReferenceReader):
            raise ContextResolutionError(
                "Injected context reader does not implement the read seam",
                details={"request_id": request.request_id, "source": prefix},
            )
        try:
            references = reader.list_references(request=request)
        except Exception as error:
            raise ContextResolutionError(
                "Injected context reader failed",
                details={"request_id": request.request_id, "source": prefix},
            ) from error
        return _references(references, prefix)

    def _resolve_caller_context(
        self, request: OrchestrationRequest
    ) -> tuple[tuple[str, ...], int, str | None]:
        """Return the allowlisted caller references and the withheld count."""

        caller_context: Mapping[str, object] = request.context
        withheld = sum(
            1 for key in caller_context if key not in ALLOWED_CALLER_CONTEXT_KEYS
        )
        if "context_refs" not in caller_context:
            return (), withheld, None

        references = _references(caller_context["context_refs"], "context_refs")
        reason = "CONTEXT_CALLER_REFERENCES_WITHHELD" if withheld else None
        return references, withheld, reason
