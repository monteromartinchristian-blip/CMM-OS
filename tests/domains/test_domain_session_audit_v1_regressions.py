"""Phase 10.34 — Audit V1 Regression Suite.

Adversarial tests specifically reproducing and guarding against all findings
from Independent Audit V1:
- BLOCKER-01: Stale auth fail-open
- BLOCKER-02: Nominal recomposition / re-resolution
- BLOCKER-03: Missing shared session persistence integration
- MAJOR-01: Session ID mismatch / transplantation
- MAJOR-02: False-pass revalidation / unknown states
- MAJOR-03: Permissive serialization / JSON-unsafe objects
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.errors import (
    DomainSessionContractError,
    DomainSessionResumeError,
    DomainSessionSerializationError,
)
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.session_codec import DomainSessionCodec
from cmm.domains.session_contracts import (
    DomainSessionCheck,
    DomainSessionCheckStatus,
    DomainSessionContext,
    DomainSessionResumeRequest,
    DomainSessionResumeResult,
    DomainSessionResumeStatus,
)
from cmm.domains.session_resumer import DomainSessionResumer
from cmm.domains.session_revalidation import (
    revalidate_resource_and_knowledge_drift,
    revalidate_temporal,
    revalidate_workflows,
)
from tests.domains.domain_session_test_support import (
    failing_shared_session_adapter,
    shared_session_adapter,
)


def _now() -> datetime:
    return datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


def _make_def(
    slug: str,
    version: str = "1.0.0",
    operations: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
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


def _build_test_registry() -> DomainRegistry:
    reg = DomainRegistry()
    d_health = _make_def(
        "health",
        "1.0.0",
        operations=("op:health_read", "op:health_write", "op:delete_all"),
        permissions=("perm:health_read", "perm:health_write", "perm:admin"),
        rules=("rule:health_1",),
    )
    d_fitness = _make_def(
        "fitness",
        "1.2.0",
        operations=("op:fitness_log",),
        permissions=("perm:fitness_write",),
        rules=("rule:fitness_1",),
    )
    d_general = _make_def(
        "general",
        "1.0.0",
        operations=("op:gen_query",),
        permissions=("perm:gen_read",),
        rules=("rule:general_1",),
    )
    for d in (d_health, d_fitness, d_general):
        reg.register(d)
        reg.restore_record(
            DomainRegistryRecord(
                definition=d,
                status=DomainStatus.ACTIVE,
                registered_at=_now(),
                updated_at=_now(),
            )
        )
    return reg


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCKER-01: Stale auth fail-open tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_resume_without_current_permission_authority_fails_closed():
    """Resuming without current permission authority must fail closed and never resume."""
    ctx = DomainSessionContext(
        session_id="s-auth-1",
        primary_domain="domain:health",
        effective_permission_refs=("perm:admin",),
        available_operation_ids=("op:delete_all",),
        updated_at=_now(),
    )
    req = DomainSessionResumeRequest(session_id="s-auth-1")
    reg = _build_test_registry()

    # Resumer with NO permission evaluator and NO operation authority
    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=None,
        operation_filter=None,
        shared_session_adapter=shared_session_adapter(),
    )
    result = resumer.resume(req, ctx)

    # Must fail closed: not RESUMED, and cannot retain stale permissions
    assert result.status in (
        DomainSessionResumeStatus.FAILED,
        DomainSessionResumeStatus.BLOCKED,
    )
    assert result.context is None or result.context.effective_permission_refs != (
        "perm:admin",
    )
    assert result.recorded_resumption is False


def test_resume_without_current_operation_authority_fails_closed():
    """Resuming without current operation authority must fail closed."""
    ctx = DomainSessionContext(
        session_id="s-auth-2",
        primary_domain="domain:health",
        effective_permission_refs=("perm:health_read",),
        available_operation_ids=("op:delete_all",),
        updated_at=_now(),
    )
    req = DomainSessionResumeRequest(session_id="s-auth-2")
    reg = _build_test_registry()

    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: ("perm:health_read",),
        operation_filter=None,
        shared_session_adapter=shared_session_adapter(),
    )
    result = resumer.resume(req, ctx)

    assert result.status in (
        DomainSessionResumeStatus.FAILED,
        DomainSessionResumeStatus.BLOCKED,
    )
    assert (
        result.context is None
        or "op:delete_all" not in result.context.available_operation_ids
    )
    assert result.recorded_resumption is False


def test_resume_without_current_domain_registry_fails_closed():
    """Resuming without domain registry authority must fail closed."""
    ctx = DomainSessionContext(
        session_id="s-auth-3",
        primary_domain="domain:health",
        updated_at=_now(),
    )
    req = DomainSessionResumeRequest(session_id="s-auth-3")
    resumer = DomainSessionResumer(
        registry=None,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    result = resumer.resume(req, ctx)

    assert result.status in (
        DomainSessionResumeStatus.FAILED,
        DomainSessionResumeStatus.BLOCKED,
    )
    assert result.context is None
    assert any(c.blocking for c in result.checks)
    assert result.recorded_resumption is False


def test_stale_permission_snapshot_never_becomes_current_permission():
    """Historical perm:admin in persisted snapshot must be stripped by current permission evaluator."""
    reg = _build_test_registry()
    ctx = DomainSessionContext(
        session_id="s-auth-4",
        primary_domain="domain:health",
        effective_permission_refs=("perm:admin", "perm:health_read"),
        available_operation_ids=("op:delete_all", "op:health_read"),
        updated_at=_now(),
    )
    req = DomainSessionResumeRequest(session_id="s-auth-4", actor="standard_user")
    # Current authority only grants read
    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda actor, perms: ("perm:health_read",),
        operation_filter=lambda perms, ops: ("op:health_read",),
        shared_session_adapter=shared_session_adapter(),
    )
    result = resumer.resume(req, ctx)
    assert result.status is DomainSessionResumeStatus.RESUMED
    assert result.context is not None
    assert result.context.effective_permission_refs == ("perm:health_read",)
    assert "perm:admin" not in result.context.effective_permission_refs


def test_stale_operation_snapshot_never_becomes_current_availability():
    """Historical op:delete_all must not become available when current filter denies it."""
    reg = _build_test_registry()
    ctx = DomainSessionContext(
        session_id="s-auth-5",
        primary_domain="domain:health",
        effective_permission_refs=("perm:health_read",),
        available_operation_ids=("op:delete_all",),
        updated_at=_now(),
    )
    req = DomainSessionResumeRequest(session_id="s-auth-5")
    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda actor, perms: ("perm:health_read",),
        operation_filter=lambda perms, ops: ("op:health_read",),
        shared_session_adapter=shared_session_adapter(),
    )
    result = resumer.resume(req, ctx)
    assert result.status is DomainSessionResumeStatus.RESUMED
    assert result.context is not None
    assert result.context.available_operation_ids == ("op:health_read",)
    assert "op:delete_all" not in result.context.available_operation_ids


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCKER-02: Real Recomposition and Re-resolution tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_recomposed_status_requires_composer_invocation():
    """Returning RECOMPOSED must invoke the composer."""
    reg = _build_test_registry()
    # Disable supporting domain
    d_fitness = _make_def("fitness", "1.2.0")
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_fitness,
            status=DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )

    ctx = DomainSessionContext(
        session_id="s-comp-1",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        composition_id="comp:OLD",
        effective_profile="profile:OLD",
        effective_rule_ids=("rule:OLD",),
        effective_permission_refs=("perm:OLD",),
        available_operation_ids=("op:OLD",),
        updated_at=_now(),
    )

    mock_composer = MagicMock()
    mock_composition = MagicMock()
    mock_composition.id = "comp:NEW_RECOMPOSED"
    mock_composition.effective_profile = "profile:NEW"
    mock_composition.rules = ("rule:health_1",)
    mock_composition.permissions = ("perm:health_read",)
    mock_composition.operations = ("op:health_read",)
    mock_composer.compose.return_value = mock_composition

    resumer = DomainSessionResumer(
        registry=reg,
        composer=mock_composer,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="s-comp-1")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.RECOMPOSED
    assert mock_composer.compose.called
    assert result.context is not None
    assert result.context.composition_id == "comp:NEW_RECOMPOSED"
    assert result.context.effective_profile == "profile:NEW"
    assert result.context.effective_rule_ids == ("rule:health_1",)


def test_supporting_domain_removal_rebuilds_composition():
    """When a supporting domain is disabled, the composition is rebuilt using real composer."""
    reg = _build_test_registry()
    d_fitness = _make_def("fitness", "1.2.0")
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_fitness,
            status=DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    ctx = DomainSessionContext(
        session_id="s-comp-2",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        composition_id="comp:OLD",
        updated_at=_now(),
    )
    real_composer = DefaultDomainComposer()
    resumer = DomainSessionResumer(
        registry=reg,
        composer=real_composer,
        permission_evaluator=lambda a, p: ("perm:health_read",),
        operation_filter=lambda p, o: ("op:health_read",),
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="s-comp-2")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.RECOMPOSED
    assert result.context is not None
    assert result.context.composition_id != "comp:OLD"
    assert result.context.composition_id.startswith("domain-composition-")
    assert result.context.supporting_domains == ()


def test_material_domain_change_recomputes_profile():
    """Material domain change must recompute effective profile."""
    reg = _build_test_registry()
    d_fitness = _make_def("fitness", "1.2.0")
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_fitness,
            status=DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    ctx = DomainSessionContext(
        session_id="s-comp-3",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        effective_profile="old_joint_profile",
        updated_at=_now(),
    )
    real_composer = DefaultDomainComposer()
    resumer = DomainSessionResumer(
        registry=reg,
        composer=real_composer,
        permission_evaluator=lambda a, p: ("perm:health_read",),
        operation_filter=lambda p, o: ("op:health_read",),
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="s-comp-3")
    result = resumer.resume(req, ctx)
    assert result.status is DomainSessionResumeStatus.RECOMPOSED
    assert result.context is not None
    assert result.context.effective_profile != "old_joint_profile"


def test_material_domain_change_recomputes_rules():
    """Material domain change must recompute effective rules."""
    reg = _build_test_registry()
    d_fitness = _make_def("fitness", "1.2.0")
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_fitness,
            status=DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    ctx = DomainSessionContext(
        session_id="s-comp-4",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        effective_rule_ids=("rule:health_1", "rule:fitness_1"),
        updated_at=_now(),
    )
    real_composer = DefaultDomainComposer()
    resumer = DomainSessionResumer(
        registry=reg,
        composer=real_composer,
        permission_evaluator=lambda a, p: ("perm:health_read",),
        operation_filter=lambda p, o: ("op:health_read",),
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="s-comp-4")
    result = resumer.resume(req, ctx)
    assert result.status is DomainSessionResumeStatus.RECOMPOSED
    assert result.context is not None
    assert "rule:fitness_1" not in result.context.effective_rule_ids
    assert "rule:health_1" in result.context.effective_rule_ids


def test_material_domain_change_recomputes_permissions():
    """Material domain change must recompute permissions."""
    reg = _build_test_registry()
    d_fitness = _make_def("fitness", "1.2.0")
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_fitness,
            status=DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    ctx = DomainSessionContext(
        session_id="s-comp-5",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        effective_permission_refs=("perm:health_read", "perm:fitness_write"),
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        composer=DefaultDomainComposer(),
        permission_evaluator=lambda a, p: tuple(x for x in p if "fitness" not in x),
        operation_filter=lambda p, o: ("op:health_read",),
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="s-comp-5")
    result = resumer.resume(req, ctx)
    assert result.status is DomainSessionResumeStatus.RECOMPOSED
    assert result.context is not None
    assert "perm:fitness_write" not in result.context.effective_permission_refs


def test_material_domain_change_recomputes_operations():
    """Material domain change must recompute available operations."""
    reg = _build_test_registry()
    d_fitness = _make_def("fitness", "1.2.0")
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_fitness,
            status=DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    ctx = DomainSessionContext(
        session_id="s-comp-6",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        available_operation_ids=("op:health_read", "op:fitness_log"),
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        composer=DefaultDomainComposer(),
        permission_evaluator=lambda a, p: ("perm:health_read",),
        operation_filter=lambda p, o: ("op:health_read",),
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="s-comp-6")
    result = resumer.resume(req, ctx)
    assert result.status is DomainSessionResumeStatus.RECOMPOSED
    assert result.context is not None
    assert "op:fitness_log" not in result.context.available_operation_ids


def test_material_domain_change_reevaluates_questions():
    """Material domain change triggers question reevaluation."""
    reg = _build_test_registry()
    d_fitness = _make_def("fitness", "1.2.0")
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_fitness,
            status=DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    ctx = DomainSessionContext(
        session_id="s-comp-7",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        pending_domain_question_refs=("q:health_symptom", "q:fitness_intensity"),
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        composer=DefaultDomainComposer(),
        permission_evaluator=lambda a, p: ("perm:health_read",),
        operation_filter=lambda p, o: ("op:health_read",),
        question_evaluator=lambda q_refs: (
            ("q:health_symptom",),
            ("q:fitness_intensity",),
        ),
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="s-comp-7")
    result = resumer.resume(req, ctx)
    assert result.status is DomainSessionResumeStatus.WAITING_FOR_USER
    assert result.context is not None
    assert result.context.pending_domain_question_refs == ("q:health_symptom",)
    assert any("Dropped 1" in w for w in result.warnings)


def test_material_domain_change_reconstructs_next_step():
    """Material domain change reconstructs next step."""
    reg = _build_test_registry()
    d_fitness = _make_def("fitness", "1.2.0")
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_fitness,
            status=DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    ctx = DomainSessionContext(
        session_id="s-comp-8",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        next_recommended_step="step:log_workout_intensity",
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        composer=DefaultDomainComposer(),
        permission_evaluator=lambda a, p: ("perm:health_read",),
        operation_filter=lambda p, o: ("op:health_read",),
        next_step_reconstructor=lambda c, st: "step:recalculated_health_step",
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="s-comp-8")
    result = resumer.resume(req, ctx)
    assert result.status is DomainSessionResumeStatus.RECOMPOSED
    assert result.context is not None
    assert result.context.next_recommended_step == "step:recalculated_health_step"


def test_reresolved_status_requires_real_resolution():
    """RE_RESOLVED status must use real resolver / fallback."""
    reg = _build_test_registry()
    # Disable primary domain health
    d_health = _make_def("health", "1.0.0")
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_health,
            status=DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    ctx = DomainSessionContext(
        session_id="s-resolv-1",
        primary_domain="domain:health",
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        fallback_resolver=lambda prim, sup: "domain:general",
        permission_evaluator=lambda a, p: ("perm:gen_read",),
        operation_filter=lambda p, o: ("op:gen_query",),
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="s-resolv-1")
    result = resumer.resume(req, ctx)
    assert result.status is DomainSessionResumeStatus.RE_RESOLVED
    assert result.context is not None
    assert result.context.primary_domain == "domain:general"


def test_composer_and_resolver_doubles_must_be_invoked():
    """Unused composer double that raises error when expected proves it is wired."""
    reg = _build_test_registry()
    d_fitness = _make_def("fitness", "1.2.0")
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_fitness,
            status=DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    ctx = DomainSessionContext(
        session_id="s-trap-1",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        updated_at=_now(),
    )

    class TrappingComposer:
        def compose(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("TrappingComposer invoked successfully")

    resumer = DomainSessionResumer(
        registry=reg,
        composer=TrappingComposer(),
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="s-trap-1")
    with pytest.raises(RuntimeError, match="TrappingComposer invoked successfully"):
        resumer.resume(req, ctx)


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCKER-03: Shared session persistence integration tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_resume_requires_authoritative_shared_session():
    """Resume requires authoritative session context."""
    req = DomainSessionResumeRequest(session_id="s-persist-1")
    resumer = DomainSessionResumer(
        registry=_build_test_registry(),
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    with pytest.raises(DomainSessionResumeError, match="session context is missing"):
        resumer.resume(req, session_context=None)


def test_resume_loads_domain_state_from_shared_session():
    """Domain state is extracted and resumed from a shared session envelope."""
    reg = _build_test_registry()
    codec = DomainSessionCodec()
    ctx = DomainSessionContext(
        session_id="s-persist-2",
        primary_domain="domain:health",
        updated_at=_now(),
    )
    envelope = {"session_id": "s-persist-2", "metadata": {}}
    attached = codec.attach_to_session(envelope, ctx)

    resumer = DomainSessionResumer(
        registry=reg,
        codec=codec,
        permission_evaluator=lambda a, p: ("perm:health_read",),
        operation_filter=lambda p, o: ("op:health_read",),
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="s-persist-2")
    result = resumer.resume(req, attached)

    assert result.status is DomainSessionResumeStatus.RESUMED
    assert result.context is not None
    assert result.context.session_id == "s-persist-2"


def test_resume_records_revision_only_after_shared_persistence_commit():
    """Resumption revision increment is only recorded after persistence commit."""
    reg = _build_test_registry()
    ctx = DomainSessionContext(
        session_id="s-persist-3",
        primary_domain="domain:health",
        revision=3,
        updated_at=_now(),
    )
    adapter = shared_session_adapter()

    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: ("perm:health_read",),
        operation_filter=lambda p, o: ("op:health_read",),
        shared_session_adapter=adapter,
    )
    req = DomainSessionResumeRequest(session_id="s-persist-3")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.RESUMED
    assert result.recorded_resumption is True
    assert result.previous_revision == 3
    assert result.resumed_revision == 4
    persisted = adapter.load_domain_session("s-persist-3")
    assert persisted is not None
    assert persisted.revision == 4


def test_resume_without_persistence_authority_cannot_claim_recorded():
    """Resume without persistence authority must fail closed and cannot claim recorded_resumption=True."""
    reg = _build_test_registry()
    ctx = DomainSessionContext(
        session_id="s-persist-4",
        primary_domain="domain:health",
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: ("perm:health_read",),
        operation_filter=lambda p, o: ("op:health_read",),
    )
    req = DomainSessionResumeRequest(session_id="s-persist-4")
    result = resumer.resume(req, ctx)

    assert result.recorded_resumption is False
    assert result.status in (
        DomainSessionResumeStatus.FAILED,
        DomainSessionResumeStatus.BLOCKED,
    )
    assert result.context is None


def test_persistence_failure_keeps_previous_revision_recoverable():
    """Persistence failure must return FAILED status, context=None, recorded_resumption=False."""
    reg = _build_test_registry()
    ctx = DomainSessionContext(
        session_id="s-persist-5",
        primary_domain="domain:health",
        revision=2,
        updated_at=_now(),
    )

    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: ("perm:health_read",),
        operation_filter=lambda p, o: ("op:health_read",),
        shared_session_adapter=failing_shared_session_adapter(
            OSError("Disk write failed / database lock")
        ),
    )
    req = DomainSessionResumeRequest(session_id="s-persist-5")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.FAILED
    assert result.recorded_resumption is False
    assert result.previous_revision == 2
    assert result.resumed_revision == 2
    assert result.context is None
    assert any(
        "Shared session persistence failure" in f for f in result.blocking_findings
    )


def test_persistence_failure_does_not_emit_committed_transition_event():
    """When persistence fails, no committed lifecycle event may be published."""
    reg = _build_test_registry()
    # Supporting domain disabled -> triggers recomposition
    d_fitness = _make_def("fitness", "1.2.0")
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_fitness,
            status=DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    ctx = DomainSessionContext(
        session_id="s-persist-6",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        updated_at=_now(),
    )
    mock_publisher = MagicMock()

    resumer = DomainSessionResumer(
        registry=reg,
        composer=DefaultDomainComposer(),
        permission_evaluator=lambda a, p: ("perm:health_read",),
        operation_filter=lambda p, o: ("op:health_read",),
        shared_session_adapter=failing_shared_session_adapter(
            RuntimeError("Persistence commit aborted")
        ),
        event_publisher=mock_publisher,
    )
    req = DomainSessionResumeRequest(session_id="s-persist-6")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.FAILED
    assert not mock_publisher.publish.called


def test_shared_session_core_does_not_import_cmm_domains():
    """The cognitive / shared session core must never import cmm.domains."""
    from pathlib import Path

    cog_dir = Path("cmm/cognitive")
    for py_file in cog_dir.glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        assert "cmm.domains" not in text, f"Illegal import of cmm.domains in {py_file}"


# ═══════════════════════════════════════════════════════════════════════════════
# MAJOR-01: Session ID binding tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_request_context_session_id_mismatch_fails_closed():
    """Mismatched session ID between request and domain context fails closed."""
    reg = _build_test_registry()
    ctx = DomainSessionContext(
        session_id="session-A",
        primary_domain="domain:health",
        updated_at=_now(),
    )
    req = DomainSessionResumeRequest(session_id="session-B")
    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: ("perm:health_read",),
        operation_filter=lambda p, o: ("op:health_read",),
        shared_session_adapter=shared_session_adapter(),
    )
    with pytest.raises(
        (
            DomainSessionContractError,
            DomainSessionResumeError,
            DomainSessionSerializationError,
        )
    ):
        resumer.resume(req, ctx)


def test_context_shared_session_id_mismatch_fails_closed():
    """Mismatched session ID between domain context and outer shared envelope fails closed."""
    reg = _build_test_registry()
    codec = DomainSessionCodec()
    ctx = DomainSessionContext(
        session_id="session-A",
        primary_domain="domain:health",
        updated_at=_now(),
    )
    envelope = {"session_id": "session-B", "domain_session": ctx.to_dict()}
    resumer = DomainSessionResumer(
        registry=reg,
        codec=codec,
        permission_evaluator=lambda a, p: ("perm:health_read",),
        operation_filter=lambda p, o: ("op:health_read",),
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-B")
    with pytest.raises(
        (
            DomainSessionContractError,
            DomainSessionResumeError,
            DomainSessionSerializationError,
        )
    ):
        resumer.resume(req, envelope)


def test_request_shared_session_id_mismatch_fails_closed():
    """Mismatched session ID between request and shared envelope fails closed."""
    reg = _build_test_registry()
    codec = DomainSessionCodec()
    ctx = DomainSessionContext(
        session_id="session-A",
        primary_domain="domain:health",
        updated_at=_now(),
    )
    envelope = {"session_id": "session-A", "domain_session": ctx.to_dict()}
    resumer = DomainSessionResumer(
        registry=reg,
        codec=codec,
        permission_evaluator=lambda a, p: ("perm:health_read",),
        operation_filter=lambda p, o: ("op:health_read",),
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-B")
    with pytest.raises(
        (
            DomainSessionContractError,
            DomainSessionResumeError,
            DomainSessionSerializationError,
        )
    ):
        resumer.resume(req, envelope)


def test_codec_refuses_domain_context_for_different_session():
    """DomainSessionCodec refuses to attach a DomainSessionContext to an envelope with a different session_id."""
    codec = DomainSessionCodec()
    ctx = DomainSessionContext(
        session_id="session-ALPHA",
        primary_domain="domain:health",
        updated_at=_now(),
    )
    envelope = {"session_id": "session-BETA", "metadata": {}}
    with pytest.raises((DomainSessionContractError, DomainSessionSerializationError)):
        codec.attach_to_session(envelope, ctx)


# ═══════════════════════════════════════════════════════════════════════════════
# MAJOR-02: Real Revalidation; UNKNOWN is not PASS tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_unknown_resource_state_is_not_pass():
    """Referenced resource with unknown/unverified current version must not be PASS."""
    ctx = DomainSessionContext(
        session_id="s-drift-1",
        primary_domain="domain:health",
        domain_resource_refs={"domain:health": ("res:ehr_1",)},
        updated_at=_now(),
    )
    # Request provides NO resource versions
    req = DomainSessionResumeRequest(session_id="s-drift-1")
    checks = revalidate_resource_and_knowledge_drift(ctx, req)
    res_checks = [c for c in checks if "res:ehr_1" in c.name]
    assert len(res_checks) == 1
    assert res_checks[0].status != DomainSessionCheckStatus.PASS
    assert res_checks[0].status in (
        DomainSessionCheckStatus.WARNING,
        DomainSessionCheckStatus.DRIFT,
    )


def test_unknown_knowledge_state_is_not_pass():
    """Referenced knowledge with unknown current version must not be PASS."""
    ctx = DomainSessionContext(
        session_id="s-drift-2",
        primary_domain="domain:health",
        domain_knowledge_refs={"domain:health": ("know:doc_1",)},
        updated_at=_now(),
    )
    req = DomainSessionResumeRequest(session_id="s-drift-2")
    checks = revalidate_resource_and_knowledge_drift(ctx, req)
    know_checks = [c for c in checks if "know:doc_1" in c.name]
    assert len(know_checks) == 1
    assert know_checks[0].status != DomainSessionCheckStatus.PASS
    assert know_checks[0].status in (
        DomainSessionCheckStatus.WARNING,
        DomainSessionCheckStatus.DRIFT,
    )


def test_missing_temporal_authority_is_not_pass():
    """Missing temporal reference in request must produce WARNING, never fabricated PASS."""
    ctx = DomainSessionContext(
        session_id="s-drift-3",
        primary_domain="domain:health",
        updated_at=_now(),
    )
    req = DomainSessionResumeRequest(session_id="s-drift-3", temporal_reference=None)
    checks = revalidate_temporal(ctx, req)
    temp_check = next(c for c in checks if c.name == "temporal_validity")
    assert temp_check.status != DomainSessionCheckStatus.PASS
    assert temp_check.status == DomainSessionCheckStatus.WARNING


def test_malformed_workflow_status_fails_closed():
    """Unrecognized workflow status must fail closed and not default to CURRENT."""
    ctx = DomainSessionContext(
        session_id="s-wf-1",
        primary_domain="domain:health",
        active_workflow_refs=("wf:critical_step",),
        updated_at=_now(),
    )
    checks, _active_refs, overall_status = revalidate_workflows(
        ctx,
        workflow_statuses={"wf:critical_step": "GARBAGE_UNRECOGNIZED_STATUS"},
    )
    assert overall_status in (
        DomainSessionResumeStatus.INCOMPATIBLE,
        DomainSessionResumeStatus.BLOCKED,
        DomainSessionResumeStatus.REPLAN_REQUIRED,
    )
    assert any(
        c.status
        in (
            DomainSessionCheckStatus.INCOMPATIBLE,
            DomainSessionCheckStatus.BLOCKING,
            DomainSessionCheckStatus.WARNING,
        )
        for c in checks
    )


def test_unknown_required_workflow_cannot_resume_as_current():
    """Unknown workflow status cannot be resumed as CURRENT."""
    ctx = DomainSessionContext(
        session_id="s-wf-2",
        primary_domain="domain:health",
        active_workflow_refs=("wf:unknown_job",),
        updated_at=_now(),
    )
    checks, _active_refs, overall_status = revalidate_workflows(
        ctx,
        workflow_statuses={"wf:unknown_job": "MISSING"},
    )
    assert overall_status is DomainSessionResumeStatus.INCOMPATIBLE
    assert any(c.blocking for c in checks)


def test_high_impact_unknown_dependency_can_block_resume():
    """High-impact resource with MISSING/INVALIDATED status blocks resumption."""
    ctx = DomainSessionContext(
        session_id="s-drift-4",
        primary_domain="domain:health",
        domain_resource_refs={"domain:health": ("res:critical_vitals",)},
        updated_at=_now(),
    )
    req = DomainSessionResumeRequest(
        session_id="s-drift-4",
        current_resource_versions={"res:critical_vitals": "INVALIDATED"},
    )
    checks = revalidate_resource_and_knowledge_drift(ctx, req)
    blocking_checks = [c for c in checks if c.blocking]
    assert len(blocking_checks) >= 1
    assert blocking_checks[0].status == DomainSessionCheckStatus.BLOCKING


# ═══════════════════════════════════════════════════════════════════════════════
# MAJOR-03: Strict JSON-Safe Serialization tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_string_false_is_rejected_for_blocking():
    """String 'false' for blocking field in DomainSessionCheck.from_dict must be rejected."""
    data = {
        "name": "check_test",
        "status": "PASS",
        "message": "test message",
        "blocking": "false",  # invalid bool type
    }
    with pytest.raises(DomainSessionSerializationError):
        DomainSessionCheck.from_dict(data)


def test_string_false_is_rejected_for_recorded_resumption():
    """String 'false' for recorded_resumption in DomainSessionResumeResult.from_dict must be rejected."""
    data = {
        "status": "RESUMED",
        "session_id": "session-1",
        "previous_revision": 1,
        "resumed_revision": 2,
        "recorded_resumption": "false",  # invalid bool type
    }
    with pytest.raises(DomainSessionSerializationError):
        DomainSessionResumeResult.from_dict(data)


def test_string_revision_is_rejected():
    """String '1' for revision fields must be rejected."""
    data = {
        "status": "RESUMED",
        "session_id": "session-1",
        "previous_revision": "1",  # string not allowed
        "resumed_revision": 2,
    }
    with pytest.raises(DomainSessionSerializationError):
        DomainSessionResumeResult.from_dict(data)


def test_boolean_revision_is_rejected():
    """Boolean True for revision fields must be rejected."""
    data = {
        "status": "RESUMED",
        "session_id": "session-1",
        "previous_revision": True,  # boolean not allowed as int
        "resumed_revision": 2,
    }
    with pytest.raises(DomainSessionSerializationError):
        DomainSessionResumeResult.from_dict(data)


def test_arbitrary_actor_object_is_rejected():
    """Arbitrary Python object for actor that cannot serialize to JSON must be rejected."""

    class CustomNonSerializableObject:
        pass

    with pytest.raises((DomainSessionContractError, DomainSessionSerializationError)):
        DomainSessionResumeRequest(
            session_id="session-1",
            actor=CustomNonSerializableObject(),
        )


def test_request_is_json_safe():
    """DomainSessionResumeRequest must be strictly JSON round-trippable."""
    req = DomainSessionResumeRequest(
        session_id="session-json-1",
        actor="standard_actor",
        temporal_reference=_now(),
        current_resource_versions={"res:1": "v1"},
        current_knowledge_versions={"know:1": "v1"},
        metadata={"key": "val"},
    )
    d = req.to_dict()
    json_str = json.dumps(d, allow_nan=False)
    loaded = json.loads(json_str)
    reconstructed = DomainSessionResumeRequest.from_dict(loaded)
    assert reconstructed.session_id == req.session_id
    assert reconstructed.actor == req.actor
    assert reconstructed.temporal_reference == req.temporal_reference


def test_resume_result_is_json_safe():
    """DomainSessionResumeResult must be strictly JSON round-trippable."""
    res = DomainSessionResumeResult(
        status=DomainSessionResumeStatus.RESUMED,
        session_id="session-json-2",
        previous_revision=1,
        resumed_revision=2,
        context=DomainSessionContext(
            session_id="session-json-2",
            primary_domain="domain:health",
            updated_at=_now(),
        ),
        checks=(
            DomainSessionCheck(
                name="c1",
                status=DomainSessionCheckStatus.PASS,
                message="m1",
                blocking=False,
            ),
        ),
        warnings=("w1",),
        blocking_findings=(),
        recovered_question_refs=("q1",),
        recovered_approval_refs=("a1",),
        next_recommended_step="step:1",
        recorded_resumption=True,
    )
    d = res.to_dict()
    json_str = json.dumps(d, allow_nan=False)
    loaded = json.loads(json_str)
    reconstructed = DomainSessionResumeResult.from_dict(loaded)
    assert reconstructed.status == res.status
    assert reconstructed.session_id == res.session_id
    assert reconstructed.previous_revision == res.previous_revision
    assert reconstructed.resumed_revision == res.resumed_revision
    assert reconstructed.recorded_resumption == res.recorded_resumption


def test_unknown_serialized_fields_fail_closed():
    """Unknown fields in serialized payloads must be rejected across all contract from_dict methods."""
    with pytest.raises(DomainSessionSerializationError):
        DomainSessionResumeRequest.from_dict({"session_id": "s1", "unknown_field": 123})

    with pytest.raises(DomainSessionSerializationError):
        DomainSessionResumeResult.from_dict(
            {
                "status": "RESUMED",
                "session_id": "s1",
                "previous_revision": 1,
                "resumed_revision": 2,
                "rogue_field": "injected",
            }
        )

    with pytest.raises(DomainSessionSerializationError):
        DomainSessionCheck.from_dict(
            {
                "name": "c",
                "status": "PASS",
                "message": "m",
                "extra": 1,
            }
        )
