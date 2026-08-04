"""Adversarial and fail-closed audit tests for Phase 10.18 Domain Memory Integration."""


import pytest

from cmm.domains.errors import (
    DomainMemoryContractError,
    DomainMemoryPrivacyError,
    DomainMemorySerializationError,
)
from cmm.domains.memory_contracts import (
    _DIGEST_PREFIX_LENGTH,
    DomainMemoryCapability,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryProposalBinding,
    DomainMemoryProposalKind,
    DomainMemoryProposalSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemoryTemporalSnapshot,
    DomainMemoryTraceSnapshot,
    DomainMemoryValidationCode,
    DomainMemoryValidationResult,
    DomainMemoryView,
    DomainMemoryViewRequest,
    DomainMemoryViewSnapshot,
    _sha256_digest,
)
from cmm.domains.memory_validation import DefaultDomainMemoryIntegrationValidator
from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

# --- 18 MANDATORY ADVERSARIAL AUDIT TESTS FOR AUDIT V4 ---


def _make_ref(
    ref_id: str = "ref:1",
    canonical_id: str = "item:1",
    domain: str = "domain:health",
    **kwargs,
) -> DomainMemoryReference:
    base = {
        "reference_id": ref_id,
        "kind": DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        "canonical_id": canonical_id,
        "domain_id": domain,
        "evidence_ids": ("ev:1",),
        "resource_ids": ("res:1",),
    }
    base.update(kwargs)
    return DomainMemoryReference(**base)


def _make_view_request(
    request_id: str = "req:1",
    primary_domain: str = "domain:health",
    candidates: tuple = (),
    permission_ids: tuple = (),
    **kwargs,
) -> DomainMemoryViewRequest:
    return DomainMemoryViewRequest(
        request_id=request_id,
        primary_domain=primary_domain,
        candidates=candidates,
        permission_decision_ids=permission_ids,
        **kwargs,
    )


def _make_view(
    req: DomainMemoryViewRequest,
    decisions,
    selected,
) -> DomainMemoryView:
    payload = {
        "request_id": req.request_id,
        "primary_domain": str(req.primary_domain),
        "request_digest": req.digest,
        "selection_decisions": [d.to_dict() for d in decisions],
        "selected_references": [r.to_dict() for r in selected],
    }
    if req.trace_id is not None:
        payload["trace_id"] = req.trace_id
    if req.temporal_reference is not None:
        payload["temporal_reference"] = req.temporal_reference
    content_digest = _sha256_digest(payload)
    return DomainMemoryView(
        view_id=f"view:{req.request_id}:{content_digest[:_DIGEST_PREFIX_LENGTH]}",
        request_id=req.request_id,
        primary_domain=req.primary_domain,
        request_digest=req.digest,
        trace_id=req.trace_id,
        temporal_reference=req.temporal_reference,
        selection_decisions=tuple(decisions),
        selected_references=tuple(selected),
    )


_VIEW_DIGEST1 = "abc123def456" + ("0" * 52)
_VID1 = (
    "view:req:1:"
    f"{_VIEW_DIGEST1[:_DIGEST_PREFIX_LENGTH]}"
)


def _make_binding_id(
    *,
    domain_id: str = "domain:health",
    trace_id: str = "trace:1",
    view_id: str = _VID1,
    view_digest: str = _VIEW_DIGEST1,
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


# 1. READ cannot authorize write
def test_audit_v4_read_cannot_authorize_write() -> None:
    with pytest.raises(DomainMemoryContractError):
        DomainMemoryProposalSnapshot(
            proposal_id="prop:1",
            proposal_kind=DomainMemoryProposalKind.MEMORY_UPDATE,
            affected_reference_ids=("ref:1",),
            required_capabilities=(DomainMemoryCapability.READ,),
        )


# 2. Empty proposal capabilities rejected
def test_audit_v4_empty_proposal_capabilities_rejected() -> None:
    with pytest.raises(DomainMemoryContractError):
        DomainMemoryProposalSnapshot(
            proposal_id="prop:1",
            proposal_kind=DomainMemoryProposalKind.MEMORY_UPDATE,
            affected_reference_ids=("ref:1",),
            required_capabilities=(),
        )


# 3. APPROVE capability separation
def test_audit_v4_approve_capability_enforced() -> None:
    assert DomainMemoryCapability.APPROVE.value == "APPROVE"

    binding_id = _make_binding_id(
        memory_proposal_ids=("prop:1",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:approve",),
    )
    binding = DomainMemoryProposalBinding(
        binding_id=binding_id,
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=_VID1,
        view_digest=_VIEW_DIGEST1,
        memory_proposal_ids=("prop:1",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:approve",),
    )
    inventory = DomainMemoryReferenceInventory(
        proposals=(
            DomainMemoryProposalSnapshot(
                proposal_id="prop:1",
                proposal_kind=DomainMemoryProposalKind.MEMORY_UPDATE,
                affected_reference_ids=("ref:1",),
                required_capabilities=(DomainMemoryCapability.APPROVE,),
            ),
        ),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:propose",
                allowed=True,
                capabilities=(DomainMemoryCapability.PROPOSE,),
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
                view_digest=_VIEW_DIGEST1,
            ),
        ),
    )
    validator = DefaultDomainMemoryIntegrationValidator()
    result = validator.validate_binding(binding, inventory)
    assert result.is_valid is False
    assert result.code in (
        DomainMemoryValidationCode.INVALID_PERMISSION_DENIED,
        DomainMemoryValidationCode.INVALID_PERMISSION_UNSCOPED,
    )


# 4. View ID collision regression
def test_audit_v4_view_id_content_bound() -> None:
    ref1 = _make_ref(
        ref_id="ref:1", canonical_id="item:1",
        domain="domain:health",
    )
    ref2 = _make_ref(
        ref_id="ref:2", canonical_id="item:2",
        domain="domain:health",
    )
    req1 = _make_view_request(candidates=(ref1,))
    req2 = _make_view_request(candidates=(ref2,))

    inv1 = DomainMemoryReferenceInventory(references=(ref1,))
    inv2 = DomainMemoryReferenceInventory(references=(ref2,))

    resolver = DefaultDomainMemoryViewResolver()
    view1 = resolver.resolve(req1, inv1)
    view2 = resolver.resolve(req2, inv2)

    assert view1.view_id != view2.view_id


# 5. Binding ID collision regression
def test_audit_v4_binding_id_content_bound() -> None:
    binding_id_1 = _make_binding_id(
        memory_proposal_ids=("prop:1",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:1",),
    )
    binding_id_2 = _make_binding_id(
        memory_proposal_ids=("prop:2",),
        affected_reference_ids=("ref:2",),
        permission_decision_ids=("perm:1",),
    )
    b1 = DomainMemoryProposalBinding(
        binding_id=binding_id_1,
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=_VID1,
        view_digest=_VIEW_DIGEST1,
        memory_proposal_ids=("prop:1",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:1",),
    )
    b2 = DomainMemoryProposalBinding(
        binding_id=binding_id_2,
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=_VID1,
        view_digest=_VIEW_DIGEST1,
        memory_proposal_ids=("prop:2",),
        affected_reference_ids=("ref:2",),
        permission_decision_ids=("perm:1",),
    )
    assert b1.binding_id != b2.binding_id


# 6. Stale/tampered view digest rejected
def test_audit_v4_stale_view_digest_rejected() -> None:
    ref = _make_ref()
    req = _make_view_request(candidates=(ref,))
    inv = DomainMemoryReferenceInventory(references=(ref,))
    resolver = DefaultDomainMemoryViewResolver()
    view = resolver.resolve(req, inv)

    # Simulate post-construction tampering of otherwise valid content.
    bad_view = view
    object.__setattr__(bad_view, "selection_decisions", ())

    validator = DefaultDomainMemoryIntegrationValidator()
    result = validator.validate_view(bad_view, req, inv)
    assert result.is_valid is False


# 7. Duplicate canonical identity rejected in request
def test_audit_v4_duplicate_canonical_id_in_request_rejected() -> None:
    ref1 = _make_ref(ref_id="ref:1", canonical_id="item:1")
    ref2 = _make_ref(ref_id="ref:2", canonical_id="item:1")  # Same canonical_id, different ref_id
    with pytest.raises(DomainMemoryContractError):
        _make_view_request(candidates=(ref1, ref2))


# 8. Duplicate canonical identity rejected in inventory
def test_audit_v4_duplicate_canonical_id_in_inventory_rejected() -> None:
    ref1 = _make_ref(ref_id="ref:1", canonical_id="item:1")
    ref2 = _make_ref(ref_id="ref:2", canonical_id="item:1")
    with pytest.raises(DomainMemoryContractError):
        DomainMemoryReferenceInventory(references=(ref1, ref2))


# 9. Multidomain single canonical identity accepted
def test_audit_v4_multidomain_single_canonical_identity() -> None:
    ref = _make_ref(
        ref_id="ref:1",
        canonical_id="item:1",
        domain="domain:health",
        applicable_domains=("domain:health", "domain:fitness"),
    )
    req = _make_view_request(
        primary_domain="domain:health",
        candidates=(ref,),
        permission_ids=("perm:1",),
    )
    inv = DomainMemoryReferenceInventory(
        references=(ref,),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:1",
                allowed=True,
                capabilities=(DomainMemoryCapability.READ,),
                target_domain_id="domain:health",
            ),
        ),
    )
    resolver = DefaultDomainMemoryViewResolver()
    view = resolver.resolve(req, inv)
    assert len(view.selected_references) == 1
    assert view.selected_references[0].reference_id == "ref:1"
    assert view.selected_references[0].canonical_id == "item:1"


# 10. PII underscore token rejected
def test_audit_v4_pii_underscore_token_rejected() -> None:
    with pytest.raises(DomainMemoryPrivacyError):
        _make_ref(metadata={"category": "christian_montero"})

    with pytest.raises(DomainMemoryPrivacyError):
        _make_ref(metadata={"category": "diagnostico_bipolar_christian"})


# 11. DNI/phone token rejected
def test_audit_v4_dni_phone_token_rejected() -> None:
    with pytest.raises(DomainMemoryPrivacyError):
        _make_ref(metadata={"category": "dni_12345678z"})

    with pytest.raises(DomainMemoryPrivacyError):
        _make_ref(metadata={"category": "telefono_600123456"})


# 12. Error does not echo rejected metadata
def test_audit_v4_error_does_not_echo_rejected_metadata() -> None:
    try:
        _make_ref(metadata={"category": "dni_12345678z"})
        assert False, "Should have raised"
    except DomainMemoryPrivacyError as exc:
        msg = str(exc)
        assert "dni_12345678z" not in msg
        assert "12345678" not in msg


# 13. Legacy diagnostics rejected
def test_audit_v4_legacy_diagnostics_rejected() -> None:
    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryValidationResult.from_dict(
            {
                "is_valid": True,
                "code": "valid",
                "diagnostics": "free_text_diagnostics",
            }
        )


# 14. Ambiguous proposal aliases rejected
def test_audit_v4_ambiguous_proposal_aliases_rejected() -> None:
    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryReferenceInventory.from_dict(
            {
                "proposals": (),
                "memory_proposals": (),
            }
        )


# 15. Temporal current/historical selection
def test_audit_v4_temporal_current_historical_selection() -> None:
    ref_current = _make_ref(
        ref_id="ref:1",
        canonical_id="item:1",
        temporal=DomainMemoryTemporalSnapshot(
            kind="interval",
            valid_from="2024-01-01T00:00:00+00:00",
            valid_to="2025-12-31T23:59:59+00:00",
        ),
    )
    ref_h = _make_ref(
        ref_id="ref:2",
        canonical_id="item:2",
        temporal=DomainMemoryTemporalSnapshot(
            kind="interval",
            valid_from="2023-01-01T00:00:00+00:00",
            valid_to="2023-12-31T23:59:59+00:00",
        ),
    )
    req = _make_view_request(
        candidates=(ref_current, ref_h),
        permission_ids=("perm:1",),
        temporal_reference="2024-06-01T00:00:00+00:00",
    )
    inv = DomainMemoryReferenceInventory(
        references=(ref_current, ref_h),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:1",
                allowed=True,
                capabilities=(DomainMemoryCapability.READ,),
                target_domain_id="domain:health",
            ),
        ),
    )
    resolver = DefaultDomainMemoryViewResolver()
    view = resolver.resolve(req, inv)
    assert len(view.selected_references) == 1
    assert view.selected_references[0].reference_id == "ref:1"


# 16. Invalidation preserved
def test_audit_v4_invalidation_preserved() -> None:
    ref_valid = _make_ref(ref_id="ref:1", canonical_id="item:1")
    ref_invalid = _make_ref(
        ref_id="ref:2",
        canonical_id="item:2",
        temporal=DomainMemoryTemporalSnapshot(
            kind="interval",
            valid_from="2024-01-01T00:00:00+00:00",
            valid_to="2024-12-31T23:59:59+00:00",
            invalidated=True,
            invalidation_reason="superseded",
        ),
    )
    req = _make_view_request(
        candidates=(ref_valid, ref_invalid),
        permission_ids=("perm:1",),
    )
    inv = DomainMemoryReferenceInventory(
        references=(ref_valid, ref_invalid),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:1",
                allowed=True,
                capabilities=(DomainMemoryCapability.READ,),
                target_domain_id="domain:health",
            ),
        ),
    )
    resolver = DefaultDomainMemoryViewResolver()
    view = resolver.resolve(req, inv)
    assert len(view.selected_references) == 1
    assert view.selected_references[0].reference_id == "ref:1"


# 17. Resolver output validates
def test_audit_v4_resolver_output_validates() -> None:
    ref = _make_ref()
    req = _make_view_request(
        candidates=(ref,),
        permission_ids=("perm:1",),
    )
    inv = DomainMemoryReferenceInventory(
        references=(ref,),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:1",
                allowed=True,
                capabilities=(DomainMemoryCapability.READ,),
                target_domain_id="domain:health",
            ),
        ),
    )
    resolver = DefaultDomainMemoryViewResolver()
    validator = DefaultDomainMemoryIntegrationValidator()
    view = resolver.resolve(req, inv)
    assert validator.validate_view(view, req, inv).is_valid is True


# 18. Manipulated instances fail closed
def test_audit_v4_manipulated_instances_fail_closed() -> None:
    corrupt_view = object.__new__(DomainMemoryView)
    object.__setattr__(corrupt_view, "view_id", "view:corrupt")
    object.__setattr__(corrupt_view, "request_id", "req:corrupt")
    object.__setattr__(corrupt_view, "primary_domain", "invalid_domain_format")
    object.__setattr__(corrupt_view, "selection_decisions", None)
    object.__setattr__(corrupt_view, "selected_references", "not_a_tuple")

    req = DomainMemoryViewRequest(
        request_id="req:corrupt",
        primary_domain="domain:health",
    )
    inventory = DomainMemoryReferenceInventory()

    validator = DefaultDomainMemoryIntegrationValidator()
    result = validator.validate_view(corrupt_view, req, inventory)

    assert result.is_valid is False
    assert result.code in (
        DomainMemoryValidationCode.INVALID_STRUCTURE,
        DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH,
    )


def test_audit_v8_doc_code_reconciliation_guards() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryReferenceKind,
        DomainMemoryTemporalKind,
        DomainMemoryValidationCode,
        DomainMemoryValidationResult,
    )

    val_res = DomainMemoryValidationResult(
        is_valid=True,
        code=DomainMemoryValidationCode.VALID,
    )
    assert val_res.codes == (DomainMemoryValidationCode.VALID,)

    expected_kinds = {
        "KNOWLEDGE_ITEM",
        "KNOWLEDGE_RELATION",
        "EVIDENCE",
        "RESOURCE",
        "CONTRADICTION",
        "VERSION",
        "RESOLUTION_MEMORY_ENTRY",
        "KNOWLEDGE_PACKAGE",
    }
    actual_kinds = {k.name for k in DomainMemoryReferenceKind}
    assert actual_kinds == expected_kinds

    expected_temporal = {"UNKNOWN", "TIMELESS", "POINT_IN_TIME", "INTERVAL", "SAFETY"}
    actual_temporal = {t.name for t in DomainMemoryTemporalKind}
    assert actual_temporal == expected_temporal