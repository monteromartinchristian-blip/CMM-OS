"""Tests for Phase 10.18 DomainMemoryIntegrationValidator."""

from cmm.domains.memory_contracts import (
    _DIGEST_PREFIX_LENGTH,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryProposalBinding,
    DomainMemoryProposalSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemorySelectionDecision,
    DomainMemorySelectionDecisionCode,
    DomainMemoryTraceSnapshot,
    DomainMemoryValidationCode,
    DomainMemoryView,
    DomainMemoryViewRequest,
    DomainMemoryViewSnapshot,
    _sha256_digest,
)
from cmm.domains.memory_validation import (
    DefaultDomainMemoryIntegrationValidator,
    DomainMemoryIntegrationValidator,
)

_VIEW_DIGEST_1 = _sha256_digest(
    {"fixture_id": "view:req:1"}
)
_VID1 = (
    "view:req:1:"
    f"{_VIEW_DIGEST_1[:_DIGEST_PREFIX_LENGTH]}"
)

def _make_binding_id(
    *,
    domain_id: str = "domain:health",
    trace_id: str = "trace:1",
    view_id: str = _VID1,
    view_digest: str = _VIEW_DIGEST_1,
    memory_proposal_ids: tuple[str, ...] = (),
    agent_knowledge_proposal_ids: tuple[str, ...] = (),
    affected_reference_ids: tuple[str, ...] = (),
    permission_decision_ids: tuple[str, ...] = (),
    approval_request_ids: tuple[str, ...] = (),
    approval_decision_ids: tuple[str, ...] = (),
) -> str:
    content_digest = _sha256_digest(
        {
            "domain_id": domain_id,
            "trace_id": trace_id,
            "view_id": view_id,
            "view_digest": view_digest,
            "memory_proposal_ids": sorted(set(memory_proposal_ids)),
            "agent_knowledge_proposal_ids": sorted(
                set(agent_knowledge_proposal_ids)
            ),
            "affected_reference_ids": sorted(set(affected_reference_ids)),
            "permission_decision_ids": sorted(set(permission_decision_ids)),
            "approval_request_ids": sorted(set(approval_request_ids)),
            "approval_decision_ids": sorted(set(approval_decision_ids)),
        }
    )
    return (
        f"binding:{domain_id}:{trace_id}:{view_id}:"
        f"{content_digest[:_DIGEST_PREFIX_LENGTH]}"
    )


def test_validator_protocol_conformance() -> None:
    validator = DefaultDomainMemoryIntegrationValidator()
    assert isinstance(validator, DomainMemoryIntegrationValidator)


def _make_ref(
    ref_id: str = "ref:1",
    canonical_id: str = "item:1",
    kind: DomainMemoryReferenceKind = DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
) -> DomainMemoryReference:
    return DomainMemoryReference(
        reference_id=ref_id,
        kind=kind,
        canonical_id=canonical_id,
        domain_id="domain:health",
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )


def _make_view_id(
    *,
    request_id: str,
    primary_domain: str,
    selection_decisions: tuple[DomainMemorySelectionDecision, ...],
    selected_references: tuple[DomainMemoryReference, ...],
    request_digest: str | None = None,
    trace_id: str | None = None,
    temporal_reference: str | None = None,
) -> str:
    payload = {
        "request_id": request_id,
        "primary_domain": primary_domain,
        "selection_decisions": [
            decision.to_dict()
            for decision in selection_decisions
        ],
        "selected_references": [
            reference.to_dict()
            for reference in selected_references
        ],
    }
    if request_digest is not None:
        payload["request_digest"] = request_digest
    if trace_id is not None:
        payload["trace_id"] = trace_id
    if temporal_reference is not None:
        payload["temporal_reference"] = temporal_reference

    digest = _sha256_digest(payload)
    return (
        f"view:{request_id}:"
        f"{digest[:_DIGEST_PREFIX_LENGTH]}"
    )


def test_validate_view_valid() -> None:
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    ref = _make_ref()
    req = DomainMemoryViewRequest(
        request_id="req:1",
        primary_domain="domain:health",
        permission_decision_ids=("perm:1",),
        candidates=(ref,),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:1",
                allowed=True,
                capabilities=("READ",),
                target_domain_id="domain:health",
            ),
        ),
    )

    resolver = DefaultDomainMemoryViewResolver()
    view = resolver.resolve(req, inventory)

    validator = DefaultDomainMemoryIntegrationValidator()
    result = validator.validate_view(view, req, inventory)

    assert result.is_valid is True
    assert result.code == DomainMemoryValidationCode.VALID


def test_validate_view_mismatch_request_id() -> None:
    ref = _make_ref()
    req = DomainMemoryViewRequest(
        request_id="req:1",
        primary_domain="domain:health",
        candidates=(ref,),
    )
    dec = DomainMemorySelectionDecision(
        reference_id="ref:1",
        code=DomainMemorySelectionDecisionCode.SELECTED,
    )
    req2 = DomainMemoryViewRequest(
        request_id="req:2",
        primary_domain="domain:health",
    )
    view = DomainMemoryView(
        view_id=_make_view_id(
            request_id="req:2",
            primary_domain="domain:health",
            request_digest=req2.digest,
            selection_decisions=(dec,),
            selected_references=(ref,),
        ),
        request_id="req:2",
        primary_domain="domain:health",
        request_digest=req2.digest,
        selection_decisions=(dec,),
        selected_references=(ref,),
    )
    inventory = DomainMemoryReferenceInventory(references=(ref,))

    validator = DefaultDomainMemoryIntegrationValidator()
    result = validator.validate_view(view, req, inventory)

    assert result.is_valid is False
    assert result.code == DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH


def test_validate_view_substituted_reference_kind_rejected() -> None:
    ref_cand = _make_ref()
    ref_sub = _make_ref(kind=DomainMemoryReferenceKind.RESOURCE)
    req = DomainMemoryViewRequest(
        request_id="req:1",
        primary_domain="domain:health",
        permission_decision_ids=("perm:1",),
        candidates=(ref_cand,),
    )
    dec = DomainMemorySelectionDecision(
        reference_id="ref:1",
        code=DomainMemorySelectionDecisionCode.SELECTED,
        permission_decision_ids=("perm:1",),
    )
    view = DomainMemoryView(
        view_id=_make_view_id(
            request_id="req:1",
            primary_domain="domain:health",
            request_digest=req.digest,
            selection_decisions=(dec,),
            selected_references=(ref_sub,),
        ),
        request_id="req:1",
        primary_domain="domain:health",
        request_digest=req.digest,
        selection_decisions=(dec,),
        selected_references=(ref_sub,),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(ref_cand,),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:1",
                allowed=True,
                capabilities=("READ",),
                target_domain_id="domain:health",
            ),
        ),
    )

    validator = DefaultDomainMemoryIntegrationValidator()
    result = validator.validate_view(view, req, inventory)

    assert result.is_valid is False
    assert result.code == DomainMemoryValidationCode.INVALID_REFERENCE_INTEGRITY


def test_validate_view_arbitrary_view_id_rejected() -> None:
    ref = _make_ref()
    req = DomainMemoryViewRequest(
        request_id="req:1",
        primary_domain="domain:health",
        candidates=(ref,),
    )
    dec = DomainMemorySelectionDecision(
        reference_id="ref:1",
        code=DomainMemorySelectionDecisionCode.SELECTED,
    )
    view = object.__new__(DomainMemoryView)
    object.__setattr__(view, "view_id", "view:fake_id")
    object.__setattr__(view, "request_id", "req:1")
    object.__setattr__(view, "primary_domain", ref.domain_id)
    object.__setattr__(view, "request_digest", req.digest)
    object.__setattr__(view, "selection_decisions", (dec,))
    object.__setattr__(view, "selected_references", (ref,))

    inventory = DomainMemoryReferenceInventory(references=(ref,))

    validator = DefaultDomainMemoryIntegrationValidator()
    result = validator.validate_view(view, req, inventory)

    assert result.is_valid is False
    assert result.code == DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED


def test_validate_binding_proposal_coverage_mismatch() -> None:
    binding_id = _make_binding_id(
        memory_proposal_ids=("prop:mem:1",),
        affected_reference_ids=("ref:1", "ref:extra"),
        permission_decision_ids=("perm:write:1",),
    )
    binding = DomainMemoryProposalBinding(
        binding_id=binding_id,
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=_VID1,
        view_digest=_VIEW_DIGEST_1,
        memory_proposal_ids=("prop:mem:1",),
        affected_reference_ids=("ref:1", "ref:extra"),
        permission_decision_ids=("perm:write:1",),
    )
    inventory = DomainMemoryReferenceInventory(
        proposals=(
            DomainMemoryProposalSnapshot(
                proposal_id="prop:mem:1",
                proposal_kind="memory_update",
                affected_reference_ids=("ref:1",),
                required_capabilities=("PROPOSE",),
            ),
        ),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:write:1",
                allowed=True,
                capabilities=("PROPOSE",),
                target_domain_id="domain:health",
            ),
        ),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id="trace:1", primary_domain="domain:health"
            ),
        ),
        views=(
            DomainMemoryViewSnapshot(
                view_id=_VID1,
                request_id="req:1",
                primary_domain="domain:health",
                trace_id="trace:1",
                view_digest=_VIEW_DIGEST_1,
            ),
        ),
    )

    validator = DefaultDomainMemoryIntegrationValidator()
    result = validator.validate_binding(binding, inventory)

    assert result.is_valid is False
    assert result.code == DomainMemoryValidationCode.INVALID_PROPOSAL_COVERAGE


def test_validate_binding_missing_trace_rejected() -> None:
    binding_id = _make_binding_id(
        trace_id="trace:missing",
        memory_proposal_ids=("prop:mem:1",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:write:1",),
    )
    binding = DomainMemoryProposalBinding(
        binding_id=binding_id,
        domain_id="domain:health",
        trace_id="trace:missing",
        view_id=_VID1,
        view_digest=_VIEW_DIGEST_1,
        memory_proposal_ids=("prop:mem:1",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:write:1",),
    )
    inventory = DomainMemoryReferenceInventory(
        proposals=(
            DomainMemoryProposalSnapshot(
                proposal_id="prop:mem:1",
                proposal_kind="memory_update",
                affected_reference_ids=("ref:1",),
                required_capabilities=("PROPOSE",),
            ),
        ),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:write:1",
                allowed=True,
                capabilities=("PROPOSE",),
                target_domain_id="domain:health",
            ),
        ),
        views=(
            DomainMemoryViewSnapshot(
                view_id=_VID1,
                request_id="req:1",
                primary_domain="domain:health",
                trace_id="trace:missing",
                view_digest=_VIEW_DIGEST_1,
            ),
        ),
        traces=(),
    )

    validator = DefaultDomainMemoryIntegrationValidator()
    result = validator.validate_binding(binding, inventory)

    assert result.is_valid is False
    assert result.code == DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH


def test_validate_binding_missing_approval_rejected() -> None:
    binding_id = _make_binding_id(
        memory_proposal_ids=("prop:mem:1",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:write:1",),
    )
    binding = DomainMemoryProposalBinding(
        binding_id=binding_id,
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=_VID1,
        view_digest=_VIEW_DIGEST_1,
        memory_proposal_ids=("prop:mem:1",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:write:1",),
    )
    inventory = DomainMemoryReferenceInventory(
        proposals=(
            DomainMemoryProposalSnapshot(
                proposal_id="prop:mem:1",
                proposal_kind="memory_update",
                affected_reference_ids=("ref:1",),
                required_capabilities=("PROPOSE",),
                requires_confirmation=True,
            ),
        ),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:write:1",
                allowed=True,
                capabilities=("PROPOSE",),
                target_domain_id="domain:health",
            ),
        ),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id="trace:1", primary_domain="domain:health"
            ),
        ),
        views=(
            DomainMemoryViewSnapshot(
                view_id=_VID1,
                request_id="req:1",
                primary_domain="domain:health",
                trace_id="trace:1",
                view_digest=_VIEW_DIGEST_1,
            ),
        ),
    )

    validator = DefaultDomainMemoryIntegrationValidator()
    result = validator.validate_binding(binding, inventory)

    assert result.is_valid is False
    assert result.code == DomainMemoryValidationCode.INVALID_APPROVAL_REQUIRED

def test_validate_view_rejects_declared_unknown_permission_id() -> None:
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    ref = _make_ref()
    request = DomainMemoryViewRequest(
        request_id="req:unknown-permission",
        primary_domain="domain:health",
        permission_decision_ids=("perm:known", "perm:unknown"),
        candidates=(ref,),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:known",
                allowed=True,
                capabilities=("READ",),
                target_domain_id="domain:health",
            ),
        ),
    )

    view = DefaultDomainMemoryViewResolver().resolve(request, inventory)
    result = DefaultDomainMemoryIntegrationValidator().validate_view(
        view,
        request,
        inventory,
    )

    assert result.is_valid is False
    assert result.code == DomainMemoryValidationCode.INVALID_PERMISSION_DENIED


def test_validate_binding_rejects_declared_unknown_permission_id() -> None:
    permission_ids = ("perm:write:known", "perm:write:unknown")
    binding = DomainMemoryProposalBinding(
        binding_id=_make_binding_id(
            memory_proposal_ids=("prop:mem:unknown-permission",),
            affected_reference_ids=("ref:1",),
            permission_decision_ids=permission_ids,
        ),
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=_VID1,
        view_digest=_VIEW_DIGEST_1,
        memory_proposal_ids=("prop:mem:unknown-permission",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=permission_ids,
    )
    inventory = DomainMemoryReferenceInventory(
        proposals=(
            DomainMemoryProposalSnapshot(
                proposal_id="prop:mem:unknown-permission",
                proposal_kind="memory_update",
                affected_reference_ids=("ref:1",),
                required_capabilities=("PROPOSE",),
            ),
        ),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:write:known",
                allowed=True,
                capabilities=("PROPOSE",),
                target_domain_id="domain:health",
            ),
        ),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id="trace:1",
                primary_domain="domain:health",
            ),
        ),
        views=(
            DomainMemoryViewSnapshot(
                view_id=_VID1,
                request_id="req:1",
                primary_domain="domain:health",
                trace_id="trace:1",
                view_digest=_VIEW_DIGEST_1,
            ),
        ),
    )

    result = DefaultDomainMemoryIntegrationValidator().validate_binding(
        binding,
        inventory,
    )

    assert result.is_valid is False
    assert result.code == DomainMemoryValidationCode.INVALID_PERMISSION_DENIED
    assert result.affected_object_ids == ("perm:write:unknown",)


def test_validate_binding_rejects_mismatched_full_view_digest() -> None:
    tampered_view_digest = (
        _VIEW_DIGEST_1[:_DIGEST_PREFIX_LENGTH]
        + ("f" * (64 - _DIGEST_PREFIX_LENGTH))
    )
    assert tampered_view_digest != _VIEW_DIGEST_1

    binding = DomainMemoryProposalBinding(
        binding_id=_make_binding_id(
            view_digest=tampered_view_digest,
            memory_proposal_ids=("prop:mem:view-digest",),
            affected_reference_ids=("ref:1",),
            permission_decision_ids=("perm:write:view-digest",),
        ),
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=_VID1,
        view_digest=tampered_view_digest,
        memory_proposal_ids=("prop:mem:view-digest",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:write:view-digest",),
    )
    inventory = DomainMemoryReferenceInventory(
        proposals=(
            DomainMemoryProposalSnapshot(
                proposal_id="prop:mem:view-digest",
                proposal_kind="memory_update",
                affected_reference_ids=("ref:1",),
                required_capabilities=("PROPOSE",),
            ),
        ),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:write:view-digest",
                allowed=True,
                capabilities=("PROPOSE",),
                target_domain_id="domain:health",
            ),
        ),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id="trace:1",
                primary_domain="domain:health",
            ),
        ),
        views=(
            DomainMemoryViewSnapshot(
                view_id=_VID1,
                request_id="req:1",
                primary_domain="domain:health",
                trace_id="trace:1",
                view_digest=_VIEW_DIGEST_1,
            ),
        ),
    )

    result = DefaultDomainMemoryIntegrationValidator().validate_binding(
        binding,
        inventory,
    )

    assert result.is_valid is False
    assert result.code == DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED


def test_validate_view_rejects_post_construction_tampering_trace_id() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemoryReference,
        DomainMemoryReferenceInventory,
        DomainMemoryReferenceKind,
        DomainMemoryTraceSnapshot,
        DomainMemoryViewRequest,
    )
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    ref = DomainMemoryReference(
        reference_id="ref:tamper:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:1",
        domain_id="domain:health",
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    req = DomainMemoryViewRequest(
        request_id="req:tamper:1",
        primary_domain="domain:health",
        candidates=(ref,),
        permission_decision_ids=("perm:tamper:1",),
        trace_id="trace:1",
    )
    inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:tamper:1",
                allowed=True,
                capabilities=("READ",),
                target_domain_id="domain:health",
            ),
        ),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id="trace:1",
                primary_domain="domain:health",
            ),
            DomainMemoryTraceSnapshot(
                trace_id="trace:tampered",
                primary_domain="domain:health",
            ),
        ),
    )
    view = DefaultDomainMemoryViewResolver().resolve(req, inventory)

    # Validate before tampering
    validator = DefaultDomainMemoryIntegrationValidator()
    assert validator.validate_view(view, req, inventory).is_valid is True

    # Tamper trace_id via object.__setattr__
    object.__setattr__(view, "trace_id", "trace:tampered")
    res = validator.validate_view(view, req, inventory)
    assert res.is_valid is False
    assert res.code in (
        DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED,
        DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,
        DomainMemoryValidationCode.INVALID_REFERENCE_INTEGRITY,
    )


def test_validate_view_rejects_post_construction_tampering_temporal_reference() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemoryReference,
        DomainMemoryReferenceInventory,
        DomainMemoryReferenceKind,
        DomainMemoryViewRequest,
    )
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    ref = DomainMemoryReference(
        reference_id="ref:tamper:2",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:2",
        domain_id="domain:health",
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    req = DomainMemoryViewRequest(
        request_id="req:tamper:2",
        primary_domain="domain:health",
        candidates=(ref,),
        permission_decision_ids=("perm:tamper:2",),
        temporal_reference="2026-01-01T00:00:00+00:00",
    )
    inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:tamper:2",
                allowed=True,
                capabilities=("READ",),
                target_domain_id="domain:health",
            ),
        ),
    )
    view = DefaultDomainMemoryViewResolver().resolve(req, inventory)

    validator = DefaultDomainMemoryIntegrationValidator()
    assert validator.validate_view(view, req, inventory).is_valid is True

    # Tamper temporal_reference via object.__setattr__
    object.__setattr__(view, "temporal_reference", "2026-06-01T00:00:00+00:00")
    res = validator.validate_view(view, req, inventory)
    assert res.is_valid is False
    assert res.code in (
        DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED,
        DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,
        DomainMemoryValidationCode.INVALID_REFERENCE_INTEGRITY,
    )


def test_validate_view_rejects_post_construction_tampering_selection_decisions() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemoryReference,
        DomainMemoryReferenceInventory,
        DomainMemoryReferenceKind,
        DomainMemorySelectionDecision,
        DomainMemorySelectionDecisionCode,
        DomainMemoryViewRequest,
    )
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    ref = DomainMemoryReference(
        reference_id="ref:tamper:3",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:3",
        domain_id="domain:health",
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    req = DomainMemoryViewRequest(
        request_id="req:tamper:3",
        primary_domain="domain:health",
        candidates=(ref,),
        permission_decision_ids=("perm:tamper:3",),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:tamper:3",
                allowed=True,
                capabilities=("READ",),
                target_domain_id="domain:health",
            ),
        ),
    )
    view = DefaultDomainMemoryViewResolver().resolve(req, inventory)

    validator = DefaultDomainMemoryIntegrationValidator()
    assert validator.validate_view(view, req, inventory).is_valid is True

    # Tamper selection_decisions via object.__setattr__
    tampered_dec = DomainMemorySelectionDecision(
        reference_id="ref:tamper:3",
        code=DomainMemorySelectionDecisionCode.EXCLUDED_PERMISSION_DENIED,
    )
    object.__setattr__(view, "selection_decisions", (tampered_dec,))
    res = validator.validate_view(view, req, inventory)
    assert res.is_valid is False
    assert res.code in (
        DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED,
        DomainMemoryValidationCode.INVALID_REFERENCE_INTEGRITY,
        DomainMemoryValidationCode.INVALID_PERMISSION_DENIED,
    )


def test_validate_binding_rejects_post_construction_tampering_fields() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemoryProposalBinding,
        DomainMemoryProposalSnapshot,
        DomainMemoryReferenceInventory,
        DomainMemoryTraceSnapshot,
        DomainMemoryViewSnapshot,
    )

    binding = DomainMemoryProposalBinding(
        binding_id=_make_binding_id(
            memory_proposal_ids=("prop:mem:1",),
            affected_reference_ids=("ref:1",),
            permission_decision_ids=("perm:write:1",),
        ),
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=_VID1,
        view_digest=_VIEW_DIGEST_1,
        memory_proposal_ids=("prop:mem:1",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:write:1",),
    )
    inventory = DomainMemoryReferenceInventory(
        proposals=(
            DomainMemoryProposalSnapshot(
                proposal_id="prop:mem:1",
                proposal_kind="memory_update",
                affected_reference_ids=("ref:1",),
                required_capabilities=("PROPOSE",),
            ),
            DomainMemoryProposalSnapshot(
                proposal_id="prop:mem:2",
                proposal_kind="memory_update",
                affected_reference_ids=("ref:2",),
                required_capabilities=("PROPOSE",),
            ),
        ),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:write:1",
                allowed=True,
                capabilities=("PROPOSE",),
                target_domain_id="domain:health",
            ),
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:write:2",
                allowed=True,
                capabilities=("PROPOSE",),
                target_domain_id="domain:health",
            ),
        ),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id="trace:1",
                primary_domain="domain:health",
            ),
        ),
        views=(
            DomainMemoryViewSnapshot(
                view_id=_VID1,
                request_id="req:1",
                primary_domain="domain:health",
                trace_id="trace:1",
                view_digest=_VIEW_DIGEST_1,
            ),
        ),
    )

    validator = DefaultDomainMemoryIntegrationValidator()
    assert validator.validate_binding(binding, inventory).is_valid is True

    # 1. Tamper permission_decision_ids (with known IDs in inventory)
    object.__setattr__(binding, "permission_decision_ids", ("perm:write:1", "perm:write:2"))
    res_perm = validator.validate_binding(binding, inventory)
    assert res_perm.is_valid is False
    assert res_perm.code == DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED

    # Restore binding
    object.__setattr__(binding, "permission_decision_ids", ("perm:write:1",))

    # 2. Tamper affected_reference_ids
    object.__setattr__(binding, "affected_reference_ids", ("ref:1", "ref:2"))
    res_aff = validator.validate_binding(binding, inventory)
    assert res_aff.is_valid is False
    assert res_aff.code == DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED

    # Restore binding
    object.__setattr__(binding, "affected_reference_ids", ("ref:1",))

    # 3. Tamper proposal IDs set
    object.__setattr__(binding, "memory_proposal_ids", ("prop:mem:1", "prop:mem:2"))
    res_prop = validator.validate_binding(binding, inventory)
    assert res_prop.is_valid is False
    assert res_prop.code == DomainMemoryValidationCode.INVALID_DIGEST_TAMPERED
