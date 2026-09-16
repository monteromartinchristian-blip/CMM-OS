"""Phase 11.2 — authorized context resolver tests.

The resolver determines which authorized context references are relevant to the
current request.  It owns no context source, creates no context registry, never
copies a source object into a public contract and never fabricates missing
context.
"""

from __future__ import annotations

import pytest

from cmm.orchestration.context import (
    ContextReferenceReader,
    ContextResolver,
    DefaultContextResolver,
)
from cmm.orchestration.contracts import (
    DomainRouteDecision,
    OrchestrationChannel,
    OrchestrationRequest,
    ResolvedContext,
)
from cmm.orchestration.errors import ContextResolutionError
from cmm.runtime.sessions import (
    InMemorySessionStore,
    SharedSessionState,
)


class _SpySessionStore:
    """Canonical session-store boundary with call recording for assertions."""

    def __init__(self) -> None:
        self._inner = InMemorySessionStore()
        self.loaded: list[str] = []
        self.saved: list[SharedSessionState] = []

    def load(self, session_id: str) -> SharedSessionState | None:
        self.loaded.append(session_id)
        return self._inner.load(session_id)

    def save(self, state: SharedSessionState) -> SharedSessionState:
        self.saved.append(state)
        return self._inner.save(state)


class _Reader:
    """Explicit read-only context seam returning safe references only."""

    def __init__(self, *references: str, raises: BaseException | None = None) -> None:
        self._references = references
        self._raises = raises
        self.calls = 0

    def list_references(self, *, request: OrchestrationRequest) -> tuple[str, ...]:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._references


class _NonConformingReader:
    """A collaborator that does not implement the documented read seam."""

    def fetch(self) -> tuple[str, ...]:
        return ("goal-1",)


def _request(**overrides: object) -> OrchestrationRequest:
    values: dict[str, object] = {
        "request_id": "request-1",
        "user_id": "user-1",
        "channel": OrchestrationChannel.CONVERSATION,
    }
    values.update(overrides)
    return OrchestrationRequest(**values)  # type: ignore[arg-type]


def _session(session_id: str = "session-1") -> SharedSessionState:
    return SharedSessionState(session_id=session_id, status="ACTIVE", revision=0)


def _domain_route(
    *, primary: str | None = "domain:health", supporting: tuple[str, ...] = ()
) -> DomainRouteDecision:
    return DomainRouteDecision(
        status="resolved",
        primary_domain=primary,
        supporting_domains=supporting,
    )


# ── Base stage ───────────────────────────────────────────────────────────────


def test_resolver_satisfies_its_protocol() -> None:
    assert isinstance(DefaultContextResolver(session_store=None), ContextResolver)


def test_base_stage_does_not_load_a_session_without_a_session_id() -> None:
    store = _SpySessionStore()

    context = DefaultContextResolver(session_store=store).resolve_base(_request())

    assert store.loaded == []
    assert context.session_ref is None
    assert context.stage == "base"
    assert context.domain_refs == ()


def test_base_stage_projects_the_canonical_session() -> None:
    store = _SpySessionStore()
    store.save(_session())

    context = DefaultContextResolver(session_store=store).resolve_base(
        _request(session_id="session-1")
    )

    assert store.loaded == ["session-1"]
    assert context.session_ref == "session-1"
    assert context.session_status == "ACTIVE"
    assert context.session_revision == 1
    assert "session:session-1" in context.context_refs


def test_unknown_session_is_reported_and_not_invented() -> None:
    store = _SpySessionStore()

    context = DefaultContextResolver(session_store=store).resolve_base(
        _request(session_id="session-missing")
    )

    assert context.session_ref is None
    assert context.missing_refs == ("session:session-missing",)
    assert "CONTEXT_SESSION_NOT_FOUND" in context.reason_codes


def test_missing_session_store_with_a_requested_session_fails_closed() -> None:
    resolver = DefaultContextResolver(session_store=None)

    with pytest.raises(ContextResolutionError) as captured:
        resolver.resolve_base(_request(session_id="session-1"))

    assert captured.value.category == "context"


def test_session_store_failure_fails_closed() -> None:
    class _BrokenStore:
        def load(self, session_id: str) -> SharedSessionState | None:
            raise RuntimeError("store unavailable")

        def save(self, state: SharedSessionState) -> SharedSessionState:
            raise RuntimeError("store unavailable")

    with pytest.raises(ContextResolutionError):
        DefaultContextResolver(session_store=_BrokenStore()).resolve_base(
            _request(session_id="session-1")
        )


def test_domain_stage_performs_no_additional_source_reads() -> None:
    """Base context reads the base sources; the domain stage re-reads nothing."""

    goal_reader = _Reader("goal-1")
    store = _SpySessionStore()
    store.save(_session())
    resolver = DefaultContextResolver(session_store=store, goal_reader=goal_reader)
    request = _request(session_id="session-1")

    base = resolver.resolve_base(request)
    resolver.resolve_domain_context(request, base, _domain_route())

    assert store.loaded == ["session-1"]
    assert goal_reader.calls == 1


# ── Minimization ─────────────────────────────────────────────────────────────


def test_only_allowlisted_caller_context_is_forwarded() -> None:
    request = _request(
        context={
            "context_refs": ["note-1"],
            "secret_note": "highly sensitive personal text",
            "unrelated": "value",
        }
    )

    context = DefaultContextResolver(session_store=None).resolve_base(request)

    assert context.context_refs == ("caller:note-1",)
    assert context.withheld_field_count == 2


def test_withheld_caller_context_never_reaches_the_projection() -> None:
    request = _request(
        context={"secret_note": "highly sensitive personal text", "other": "value"}
    )

    context = DefaultContextResolver(session_store=None).resolve_base(request)

    serialized = str(context.to_dict())

    assert "highly sensitive" not in serialized
    assert "secret_note" not in serialized
    assert "other" not in serialized
    assert context.withheld_field_count == 2


def test_malformed_caller_context_refs_fail_closed() -> None:
    request = _request(context={"context_refs": ["note-1", 2]})

    with pytest.raises(ContextResolutionError):
        DefaultContextResolver(session_store=None).resolve_base(request)


def test_caller_context_refs_must_be_a_sequence() -> None:
    request = _request(context={"context_refs": "note-1"})

    with pytest.raises(ContextResolutionError):
        DefaultContextResolver(session_store=None).resolve_base(request)


def test_reader_references_are_projected_with_a_safe_prefix() -> None:
    resolver = DefaultContextResolver(
        session_store=None,
        goal_reader=_Reader("goal-1"),
        workflow_reader=_Reader("workflow-1"),
        memory_reader=_Reader("memory-1"),
        knowledge_reader=_Reader("knowledge-1"),
        recent_event_reader=_Reader("event-1"),
    )

    context = resolver.resolve_base(_request())

    assert context.context_refs == (
        "goal:goal-1",
        "workflow:workflow-1",
        "memory:memory-1",
        "knowledge:knowledge-1",
        "event:event-1",
    )


def test_reader_returning_non_references_fails_closed() -> None:
    class _BadReader:
        def list_references(self, *, request: OrchestrationRequest) -> tuple[str, ...]:
            return (object(),)  # type: ignore[return-value]

    resolver = DefaultContextResolver(session_store=None, goal_reader=_BadReader())

    with pytest.raises(ContextResolutionError):
        resolver.resolve_base(_request())


def test_reader_raising_fails_closed() -> None:
    resolver = DefaultContextResolver(
        session_store=None, goal_reader=_Reader("goal-1", raises=RuntimeError("boom"))
    )

    with pytest.raises(ContextResolutionError):
        resolver.resolve_base(_request())


def test_non_conforming_reader_fails_closed() -> None:
    resolver = DefaultContextResolver(
        session_store=None, goal_reader=_NonConformingReader()
    )

    with pytest.raises(ContextResolutionError):
        resolver.resolve_base(_request())


def test_reader_protocol_matches_the_documented_seam() -> None:
    assert isinstance(_Reader("goal-1"), ContextReferenceReader)
    assert not isinstance(_NonConformingReader(), ContextReferenceReader)


def test_projection_holds_no_source_object() -> None:
    store = _SpySessionStore()
    store.save(_session())

    context = DefaultContextResolver(
        session_store=store, goal_reader=_Reader("goal-1")
    ).resolve_base(_request(session_id="session-1"))

    payload = context.to_dict()

    assert set(payload) == {
        "request_id",
        "stage",
        "session_ref",
        "session_status",
        "session_revision",
        "context_refs",
        "domain_refs",
        "permission_refs",
        "missing_refs",
        "withheld_field_count",
        "reason_codes",
    }


# ── Domain stage ─────────────────────────────────────────────────────────────


def test_domain_stage_requires_a_real_domain_route_decision() -> None:
    resolver = DefaultContextResolver(session_store=None)
    base = resolver.resolve_base(_request())

    with pytest.raises(TypeError):
        resolver.resolve_domain_context(_request(), base, None)  # type: ignore[arg-type]


def test_domain_stage_requires_a_selected_primary_domain() -> None:
    resolver = DefaultContextResolver(session_store=None)
    request = _request()
    base = resolver.resolve_base(request)

    with pytest.raises(ContextResolutionError):
        resolver.resolve_domain_context(request, base, _domain_route(primary=None))


def test_domain_stage_projects_primary_and_supporting_references() -> None:
    resolver = DefaultContextResolver(session_store=None)
    request = _request()
    base = resolver.resolve_base(request)

    context = resolver.resolve_domain_context(
        request,
        base,
        _domain_route(supporting=("domain:university",)),
    )

    assert context.stage == "domain"
    assert context.domain_refs == ("domain:health", "domain:university")


def test_domain_stage_preserves_the_base_projection() -> None:
    store = _SpySessionStore()
    store.save(_session())
    resolver = DefaultContextResolver(
        session_store=store, goal_reader=_Reader("goal-1")
    )
    request = _request(session_id="session-1", context={"context_refs": ["note-1"]})
    base = resolver.resolve_base(request)

    context = resolver.resolve_domain_context(request, base, _domain_route())

    assert context.session_ref == "session-1"
    assert context.context_refs == base.context_refs
    assert context.missing_refs == base.missing_refs


def test_domain_stage_carries_only_canonical_permission_references() -> None:
    resolver = DefaultContextResolver(session_store=None)
    request = _request()
    base = resolver.resolve_base(request)

    context = resolver.resolve_domain_context(
        request,
        base,
        DomainRouteDecision(
            status="resolved",
            primary_domain="domain:health",
            permission_refs=("permission:policy-1",),
        ),
    )

    assert context.permission_refs == ("permission:policy-1",)


def test_domain_context_is_never_loaded_before_domain_selection() -> None:
    """The two-stage ordering is explicit: the domain stage needs the route."""

    resolver = DefaultContextResolver(session_store=None)
    request = _request()

    base = resolver.resolve_base(request)

    assert isinstance(base, ResolvedContext)
    assert base.stage == "base"
    assert base.domain_refs == ()
    assert base.permission_refs == ()


def test_resolution_is_deterministic() -> None:
    resolver = DefaultContextResolver(session_store=None, goal_reader=_Reader("goal-1"))
    request = _request(context={"context_refs": ["note-1"]})

    assert resolver.resolve_base(request).to_dict() == (
        resolver.resolve_base(request).to_dict()
    )
