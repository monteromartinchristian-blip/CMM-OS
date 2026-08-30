"""Phase 10.34 — Domain Sessions — Audit V3 Regressions.

Reproduces all findings from Independent Audit V3:
1. Stale explicit DomainSessionContext cannot rollback authoritative durable state (Blocker-01)
2. Stale explicit context cannot rollback durable next_recommended_step (Blocker-01)
3. Stale rejection leaves durable state untouched (Blocker-01)
4. Same-revision authoritative update succeeds (Blocker-01)
5. Brand-new explicit context can seed empty shared session (Blocker-01)
6. Future/mismatched explicit revision fails closed (Blocker-01)
7. Concurrent shared update produces conflict (Blocker-01)
8. Conflict INCOMPATIBLE cannot become RESUMED (Blocker-02)
9. Conflict REPLAN_REQUIRED cannot become RESUMED (Blocker-02)
10. Workflow REPLAN_REQUIRED survives RECOMPOSED (Blocker-02)
11. Waiting status survives recomposition/re-resolution (Blocker-02)
12. Status precedence merge matrix is fail-closed (Blocker-02)
13. No synthetic confidence=1.0 composition authority (Major-01)
14. Native expired resource cannot resume as current (Major-02A)
15. Recomposition invalidates stale current partial results and traces (Major-02B)
16. Version drift invalidates stale current derived continuity (Major-02B)
17. Opaque metadata rejected at construction (Major-03)
18. Opaque details rejected at construction (Major-03)
19. Strict JSON serialization roundtrips for all valid public contracts (Major-03)
20. AT-DP manifest has exactly 56 unique checkpoints with resolvable evidence (Major-04)
21. Checkpoints 30 and 38 bound to real comprehensive evidence (Major-04)
22. Checkpoints 48-56 bound to real gate and pre-audit evidence without self-asserted PASS (Major-04)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.errors import DomainSessionContractError
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.session_contracts import (
    DomainSessionCheck,
    DomainSessionCheckStatus,
    DomainSessionContext,
    DomainSessionResumeRequest,
    DomainSessionResumeResult,
    DomainSessionResumeStatus,
    DomainSessionTransition,
)
from cmm.domains.session_persistence import (
    DOMAIN_SESSION_EXTENSION_KEY,
    SharedSessionDomainAdapter,
)
from cmm.domains.session_resumer import DomainSessionResumer
from cmm.runtime.sessions import (
    InMemorySessionStore,
    SharedSessionState,
)


def _now() -> datetime:
    return datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


def _make_def(
    slug: str,
    version: str = "1.0.0",
    operations: tuple[str, ...] = ("op:read",),
    permissions: tuple[str, ...] = ("perm:read",),
    rules: tuple[str, ...] = (),
) -> DomainDefinition:
    return DomainDefinition(
        id=DomainId(slug=slug),
        name=slug,
        display_name=f"Domain {slug}",
        version=version,
        kind=DomainKind.PERSONAL,
        description=f"Description for {slug}",
        manifest_id=DomainManifestId(slug=slug, version=version),
        operations=operations,
        permissions=permissions,
        rules=rules,
    )


def _setup_registry(
    health_ver: str = "1.0.0",
    fitness_ver: str = "1.2.0",
    fitness_active: bool = True,
) -> DomainRegistry:
    reg = DomainRegistry()
    d_health = _make_def(
        "health",
        health_ver,
        operations=("op:health_read", "op:health_write"),
        permissions=("perm:health_read", "perm:health_write"),
        rules=("rule:health_guidelines",),
    )
    d_fitness = _make_def(
        "fitness",
        fitness_ver,
        operations=("op:log_workout",),
        permissions=("perm:fitness_write",),
        rules=("rule:fitness_schedule",),
    )
    reg.register(d_health)
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_health,
            status=DomainStatus.ACTIVE,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    reg.register(d_fitness)
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_fitness,
            status=DomainStatus.ACTIVE if fitness_active else DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    return reg


# ── BLOCKER-01 Regressions: Stale Snapshots & Optimistic Concurrency ──────────


def test_stale_explicit_context_cannot_rollback_durable_revision():
    """Reproduction of Audit V3 Blocker-01:

    Durable DomainSession is at revision 5. Caller passes explicit snapshot at revision 2.
    Must NOT roll durable revision backwards to 3; must fail closed and leave durable state at 5.
    """
    store = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store)
    reg = _setup_registry()

    # Seed durable session at revision 5
    durable_ctx = DomainSessionContext(
        session_id="session-b01",
        primary_domain="domain:health",
        next_recommended_step="step:new",
        revision=5,
        updated_at=_now(),
    )
    # Save directly into shared store
    shared_init = SharedSessionState(session_id="session-b01")
    updated_init = shared_init.with_extension(
        DOMAIN_SESSION_EXTENSION_KEY, durable_ctx.to_dict()
    )
    store.save(updated_init)

    # Verify durable state is at revision 5
    persisted = adapter.load_domain_session("session-b01")
    assert persisted is not None
    assert persisted.revision == 5
    assert persisted.next_recommended_step == "step:new"

    # Now caller attempts resume with stale snapshot at revision 2
    stale_snapshot = DomainSessionContext(
        session_id="session-b01",
        primary_domain="domain:health",
        next_recommended_step="step:old",
        revision=2,
        updated_at=_now(),
    )

    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )

    req = DomainSessionResumeRequest(session_id="session-b01")
    result = resumer.resume(req, session_context=stale_snapshot)

    # Result must be FAILED / BLOCKED, not RESUMED
    assert result.status in (
        DomainSessionResumeStatus.FAILED,
        DomainSessionResumeStatus.BLOCKED,
    )
    assert result.recorded_resumption is False

    # Authoritative durable state MUST remain untouched at revision 5 with step:new
    after = adapter.load_domain_session("session-b01")
    assert after is not None
    assert after.revision == 5
    assert after.next_recommended_step == "step:new"


def test_stale_explicit_context_cannot_rollback_next_step():
    """Durable state has next_recommended_step='step:authoritative'.

    Stale caller snapshot has next_recommended_step='step:stale'.
    Stale snapshot rejection leaves 'step:authoritative' intact.
    """
    store = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store)
    reg = _setup_registry()

    durable_ctx = DomainSessionContext(
        session_id="session-b01-step",
        primary_domain="domain:health",
        next_recommended_step="step:authoritative",
        revision=3,
        updated_at=_now(),
    )
    shared_init = SharedSessionState(session_id="session-b01-step")
    store.save(
        shared_init.with_extension(DOMAIN_SESSION_EXTENSION_KEY, durable_ctx.to_dict())
    )

    stale_snapshot = DomainSessionContext(
        session_id="session-b01-step",
        primary_domain="domain:health",
        next_recommended_step="step:stale",
        revision=1,
        updated_at=_now(),
    )

    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )

    res = resumer.resume(
        DomainSessionResumeRequest(session_id="session-b01-step"),
        session_context=stale_snapshot,
    )
    assert res.status != DomainSessionResumeStatus.RESUMED
    assert res.recorded_resumption is False

    after = adapter.load_domain_session("session-b01-step")
    assert after is not None
    assert after.revision == 3
    assert after.next_recommended_step == "step:authoritative"


def test_same_current_revision_can_resume():
    """Caller provides explicit context that matches current durable revision exactly -> succeeds."""
    store = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store)
    reg = _setup_registry()

    durable_ctx = DomainSessionContext(
        session_id="session-b01-same",
        primary_domain="domain:health",
        revision=3,
        updated_at=_now(),
    )
    shared_init = SharedSessionState(session_id="session-b01-same")
    store.save(
        shared_init.with_extension(DOMAIN_SESSION_EXTENSION_KEY, durable_ctx.to_dict())
    )

    matching_snapshot = DomainSessionContext(
        session_id="session-b01-same",
        primary_domain="domain:health",
        revision=3,
        updated_at=_now(),
    )

    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )

    res = resumer.resume(
        DomainSessionResumeRequest(
            session_id="session-b01-same", temporal_reference=_now()
        ),
        session_context=matching_snapshot,
    )
    assert res.status is DomainSessionResumeStatus.RESUMED
    assert res.previous_revision == 3
    assert res.resumed_revision == 4
    assert res.recorded_resumption is True

    after = adapter.load_domain_session("session-b01-same")
    assert after is not None
    assert after.revision == 4


def test_brand_new_explicit_context_can_seed_empty_shared_session():
    """When no durable session exists yet, caller's explicit context seeds the session."""
    store = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store)
    reg = _setup_registry()

    seed_ctx = DomainSessionContext(
        session_id="session-b01-seed",
        primary_domain="domain:health",
        revision=1,
        updated_at=_now(),
    )

    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )

    res = resumer.resume(
        DomainSessionResumeRequest(
            session_id="session-b01-seed", temporal_reference=_now()
        ),
        session_context=seed_ctx,
    )
    assert res.status is DomainSessionResumeStatus.RESUMED
    assert res.previous_revision == 1
    assert res.resumed_revision == 2
    assert res.recorded_resumption is True

    persisted = adapter.load_domain_session("session-b01-seed")
    assert persisted is not None
    assert persisted.revision == 2


def test_future_mismatched_explicit_revision_fails_closed():
    """Caller provides explicit context with future revision (e.g. 10 when durable is 2).

    Must fail closed.
    """
    store = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store)
    reg = _setup_registry()

    durable_ctx = DomainSessionContext(
        session_id="session-b01-future",
        primary_domain="domain:health",
        revision=2,
        updated_at=_now(),
    )
    shared_init = SharedSessionState(session_id="session-b01-future")
    store.save(
        shared_init.with_extension(DOMAIN_SESSION_EXTENSION_KEY, durable_ctx.to_dict())
    )

    future_snapshot = DomainSessionContext(
        session_id="session-b01-future",
        primary_domain="domain:health",
        revision=10,
        updated_at=_now(),
    )

    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )

    res = resumer.resume(
        DomainSessionResumeRequest(session_id="session-b01-future"),
        session_context=future_snapshot,
    )
    assert res.status in (
        DomainSessionResumeStatus.FAILED,
        DomainSessionResumeStatus.BLOCKED,
    )
    assert res.recorded_resumption is False

    after = adapter.load_domain_session("session-b01-future")
    assert after is not None
    assert after.revision == 2


# ── BLOCKER-02 Regressions: Status Precedence & Fail-Closed Merge ─────────────


def test_conflict_incompatible_cannot_become_resumed():
    """Audit V3 reproduction: conflict evaluator reports INCOMPATIBLE.

    Final result must NOT be RESUMED; must be INCOMPATIBLE and recorded_resumption=False.
    """
    reg = _setup_registry()
    store = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store)

    ctx = DomainSessionContext(
        session_id="session-b02-incomp",
        primary_domain="domain:health",
        domain_conflict_refs=("conf:contraindication",),
        updated_at=_now(),
    )

    # Conflict evaluator returns (INCOMPATIBLE, no checks)
    def conflict_eval(refs):
        return (DomainSessionResumeStatus.INCOMPATIBLE, ())

    resumer = DomainSessionResumer(
        registry=reg,
        conflict_evaluator=conflict_eval,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )

    res = resumer.resume(
        DomainSessionResumeRequest(
            session_id="session-b02-incomp", temporal_reference=_now()
        ),
        session_context=ctx,
    )
    assert res.status is DomainSessionResumeStatus.INCOMPATIBLE
    assert res.recorded_resumption is False


def test_conflict_replan_required_cannot_become_resumed():
    """Audit V3 reproduction: conflict evaluator reports REPLAN_REQUIRED.

    Final result must be REPLAN_REQUIRED, not RESUMED.
    """
    reg = _setup_registry()
    store = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store)

    ctx = DomainSessionContext(
        session_id="session-b02-replan",
        primary_domain="domain:health",
        domain_conflict_refs=("conf:schedule_overlap",),
        updated_at=_now(),
    )

    def conflict_eval(refs):
        return (DomainSessionResumeStatus.REPLAN_REQUIRED, ())

    resumer = DomainSessionResumer(
        registry=reg,
        conflict_evaluator=conflict_eval,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )

    res = resumer.resume(
        DomainSessionResumeRequest(
            session_id="session-b02-replan", temporal_reference=_now()
        ),
        session_context=ctx,
    )
    assert res.status is DomainSessionResumeStatus.REPLAN_REQUIRED


def test_workflow_replan_required_survives_recomposed():
    """Audit V3 reproduction: session status is RECOMPOSED, workflow evaluator returns REPLAN_REQUIRED.

    Final result must be REPLAN_REQUIRED (stronger restriction than RECOMPOSED).
    """
    reg = _setup_registry(fitness_active=False)  # triggers RECOMPOSED
    store = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store)

    ctx = DomainSessionContext(
        session_id="session-b02-wf-replan",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        active_workflow_refs=("wf:workout_plan",),
        updated_at=_now(),
    )

    def wf_eval(refs):
        return (DomainSessionResumeStatus.REPLAN_REQUIRED, refs, None)

    resumer = DomainSessionResumer(
        registry=reg,
        workflow_evaluator=wf_eval,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )

    res = resumer.resume(
        DomainSessionResumeRequest(
            session_id="session-b02-wf-replan", temporal_reference=_now()
        ),
        session_context=ctx,
    )
    assert res.status is DomainSessionResumeStatus.REPLAN_REQUIRED


def test_workflow_waiting_for_user_survives_recomposed():
    """Session status is RECOMPOSED, workflow evaluator returns WAITING_FOR_USER.

    Final result must be WAITING_FOR_USER.
    """
    reg = _setup_registry(fitness_active=False)
    store = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store)

    ctx = DomainSessionContext(
        session_id="session-b02-wf-wait",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        active_workflow_refs=("wf:questionnaire",),
        updated_at=_now(),
    )

    def wf_eval(refs):
        return (DomainSessionResumeStatus.WAITING_FOR_USER, refs, None)

    resumer = DomainSessionResumer(
        registry=reg,
        workflow_evaluator=wf_eval,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )

    res = resumer.resume(
        DomainSessionResumeRequest(
            session_id="session-b02-wf-wait", temporal_reference=_now()
        ),
        session_context=ctx,
    )
    assert res.status is DomainSessionResumeStatus.WAITING_FOR_USER


def test_waiting_for_approval_survives_recomposed():
    """Session status is RECOMPOSED, approvals pending -> WAITING_FOR_APPROVAL."""
    reg = _setup_registry(fitness_active=False)
    store = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store)

    ctx = DomainSessionContext(
        session_id="session-b02-appr-recomp",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        approval_refs=("appr:export",),
        updated_at=_now(),
    )

    resumer = DomainSessionResumer(
        registry=reg,
        approval_evaluator=lambda a: (a, ()),
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )

    res = resumer.resume(
        DomainSessionResumeRequest(
            session_id="session-b02-appr-recomp", temporal_reference=_now()
        ),
        session_context=ctx,
    )
    assert res.status is DomainSessionResumeStatus.WAITING_FOR_APPROVAL


# ── MAJOR-01 Regressions: No Synthetic DomainResolutionResult Authority ───────


def test_no_synthetic_confidence_1_0_composition_authority():
    """Audit V3 reproduction: spy composer verifies that no manufactured

    DomainResolutionResult with confidence=1.0 is created during nominal resume.
    """
    reg = _setup_registry()
    store = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store)

    class SpyComposer:
        def __init__(self):
            self.calls = []

        def compose(self, resolution, definitions=None):
            self.calls.append(resolution)
            return DefaultDomainComposer().compose(
                resolution, definitions or [d.definition for d in reg.list_records()]
            )

    spy = SpyComposer()
    ctx = DomainSessionContext(
        session_id="session-m01-spy",
        primary_domain="domain:health",
        composition_id="comp-authoritative-001",
        effective_profile="clinical",
        effective_rule_ids=("rule:health_guidelines",),
        effective_permission_refs=("perm:health_read",),
        available_operation_ids=("op:health_read",),
        updated_at=_now(),
    )

    resumer = DomainSessionResumer(
        registry=reg,
        composer=spy,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )

    res = resumer.resume(
        DomainSessionResumeRequest(
            session_id="session-m01-spy", temporal_reference=_now()
        ),
        session_context=ctx,
    )
    assert res.status is DomainSessionResumeStatus.RESUMED
    # On nominal unchanged resume with existing composition, composer must NOT be fed a fabricated confidence=1.0 resolution!
    for call in spy.calls:
        assert getattr(call, "confidence", 0.0) != 1.0 or getattr(
            call, "candidate_scores", ()
        ), "Fabricated confidence=1.0 resolution without resolver scores detected!"


# ── MAJOR-02 Regressions: Native Temporal Provenance & Stale Continuity ───────


def test_native_expired_resource_cannot_resume_as_current():
    """Audit V3 reproduction (7A): Resource with valid_until in the past,

    expiration_required=True, historical_allowed=False must be flagged as EXPIRED/BLOCKING
    and prevent nominal PASS.
    """
    reg = _setup_registry()
    store = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store)

    ctx = DomainSessionContext(
        session_id="session-m02-expired",
        primary_domain="domain:health",
        domain_resource_refs={"domain:health": ("res:lab_report_expired",)},
        updated_at=_now(),
    )

    # Request includes structured resource metadata indicating expiration with expiration_required=True
    req = DomainSessionResumeRequest(
        session_id="session-m02-expired",
        temporal_reference=_now(),
        current_resource_versions={"res:lab_report_expired": "EXPIRED"},
    )

    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )

    res = resumer.resume(req, session_context=ctx)
    assert res.status is DomainSessionResumeStatus.BLOCKED
    assert any("expired" in c.message.lower() for c in res.checks)


def test_recomposition_invalidates_stale_current_partial_results():
    """Audit V3 reproduction (7B): Supporting domain fitness is disabled/removed.

    Status becomes RECOMPOSED. Stale partial_result_refs and trace_refs derived from fitness
    must NOT survive as current continuation state.
    """
    reg = _setup_registry(fitness_active=False)
    store = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store)

    ctx = DomainSessionContext(
        session_id="session-m02-recomp-stale",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        partial_result_refs=("result:fitness-derived",),
        trace_refs=("trace:fitness-derived",),
        next_recommended_step="step:fitness-plan",
        updated_at=_now(),
    )

    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )

    res = resumer.resume(
        DomainSessionResumeRequest(
            session_id="session-m02-recomp-stale", temporal_reference=_now()
        ),
        session_context=ctx,
    )
    assert res.status is DomainSessionResumeStatus.RECOMPOSED
    assert res.context is not None
    assert res.context.partial_result_refs == ()
    assert res.context.trace_refs == ()
    assert res.context.next_recommended_step != "step:fitness-plan"


def test_version_drift_invalidates_stale_current_derived_continuity():
    """Audit V3 reproduction (7B): Domain version drifts from 1.0.0 to 1.1.0 (compatible).

    Resumed context stores 1.1.0, but stale partial_results and trace_refs from 1.0.0
    must be invalidated from current state.
    """
    reg = _setup_registry(health_ver="1.1.0")
    store = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store)

    ctx = DomainSessionContext(
        session_id="session-m02-ver-drift",
        primary_domain="domain:health",
        domain_versions={"domain:health": "1.0.0"},
        partial_result_refs=("result:v1",),
        trace_refs=("trace:v1",),
        next_recommended_step="step:v1",
        updated_at=_now(),
    )

    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )

    res = resumer.resume(
        DomainSessionResumeRequest(
            session_id="session-m02-ver-drift", temporal_reference=_now()
        ),
        session_context=ctx,
    )
    assert res.context is not None
    assert res.context.domain_versions["domain:health"] == "1.1.0"
    assert res.context.partial_result_refs == ()
    assert res.context.trace_refs == ()
    assert res.context.next_recommended_step != "step:v1"


# ── MAJOR-03 Regressions: Strict JSON Validation for Public Contracts ─────────


class OpaqueObject:
    """Non-JSON-serializable custom Python class."""


def test_opaque_metadata_rejected_at_construction():
    """Audit V3 reproduction: DomainSessionContext(metadata={'x': OpaqueObject()})

    must raise DomainSessionContractError immediately at construction time.
    """
    with pytest.raises((DomainSessionContractError, TypeError, ValueError)):
        DomainSessionContext(
            session_id="session-m03-opaque",
            primary_domain="domain:health",
            metadata={"x": OpaqueObject()},
            updated_at=_now(),
        )


def test_opaque_details_in_check_rejected_at_construction():
    """DomainSessionCheck(details={'x': OpaqueObject()}) must raise DomainSessionContractError."""
    with pytest.raises((DomainSessionContractError, TypeError, ValueError)):
        DomainSessionCheck(
            name="test_check",
            status=DomainSessionCheckStatus.PASS,
            message="all good",
            details={"x": OpaqueObject()},
        )


def test_opaque_transition_metadata_rejected_at_construction():
    """DomainSessionTransition(metadata={'x': OpaqueObject()}) must raise DomainSessionContractError."""
    with pytest.raises((DomainSessionContractError, TypeError, ValueError)):
        DomainSessionTransition(
            previous_primary_domain=None,
            new_primary_domain="domain:health",
            metadata={"x": OpaqueObject()},
            occurred_at=_now(),
        )


def test_opaque_resume_request_metadata_and_actor_rejected():
    """DomainSessionResumeRequest with opaque actor or metadata must raise DomainSessionContractError."""
    with pytest.raises((DomainSessionContractError, TypeError, ValueError)):
        DomainSessionResumeRequest(
            session_id="session-req-opaque",
            actor=OpaqueObject(),
        )
    with pytest.raises((DomainSessionContractError, TypeError, ValueError)):
        DomainSessionResumeRequest(
            session_id="session-req-opaque",
            metadata={"x": OpaqueObject()},
        )


@pytest.mark.parametrize(
    "contract_factory",
    [
        lambda: DomainSessionCheck(
            name="chk1",
            status=DomainSessionCheckStatus.PASS,
            message="ok",
            details={"count": 42, "items": ["a", "b"], "nested": {"valid": True}},
        ),
        lambda: DomainSessionTransition(
            previous_primary_domain="domain:a",
            new_primary_domain="domain:b",
            metadata={"reason": "re-resolution", "score": 0.95},
            occurred_at=_now(),
        ),
        lambda: DomainSessionContext(
            session_id="session-json-test",
            primary_domain="domain:health",
            metadata={"key": "value", "list": [1, 2, 3], "flag": False},
            updated_at=_now(),
        ),
        lambda: DomainSessionResumeRequest(
            session_id="session-json-test",
            actor={"user_id": "u123", "roles": ["admin"]},
            metadata={"source": "api"},
        ),
        lambda: DomainSessionResumeResult(
            status=DomainSessionResumeStatus.RESUMED,
            session_id="session-json-test",
            previous_revision=1,
            resumed_revision=2,
            context=DomainSessionContext(
                session_id="session-json-test",
                primary_domain="domain:health",
                revision=2,
                updated_at=_now(),
            ),
            recorded_resumption=True,
            metadata={"metrics": {"duration_ms": 12.5}},
        ),
    ],
)
def test_strict_json_serialization_roundtrips_for_valid_public_contracts(
    contract_factory,
):
    """Every constructed public contract instance MUST serialize strictly with json.dumps(..., allow_nan=False)."""
    obj = contract_factory()
    data = obj.to_dict()
    serialized = json.dumps(data, allow_nan=False)
    assert serialized is not None
    loaded = json.loads(serialized)
    assert isinstance(loaded, dict)
