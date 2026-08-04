"""Tests for Phase 10.18 DefaultDomainMemoryViewResolver."""

from cmm.domains.memory_contracts import (
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemorySelectionDecisionCode,
    DomainMemoryViewRequest,
)
from cmm.domains.memory_validation import DefaultDomainMemoryIntegrationValidator
from cmm.domains.memory_view import (
    DefaultDomainMemoryViewResolver,
    DomainMemoryViewResolver,
)


def test_resolver_protocol_conformance() -> None:
    resolver = DefaultDomainMemoryViewResolver()
    assert isinstance(resolver, DomainMemoryViewResolver)


def test_resolve_primary_domain_candidate_selected() -> None:
    ref = DomainMemoryReference(
        reference_id="ref:knowledge:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:100",
        domain_id="domain:health",
        applicable_domains=("domain:health",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
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

    assert len(view.selected_references) == 1
    assert view.selected_references[0].reference_id == "ref:knowledge:1"
    assert len(view.excluded_decisions) == 0

    validator = DefaultDomainMemoryIntegrationValidator()
    val_res = validator.validate_view(view, req, inventory)
    assert val_res.is_valid is True


def test_resolve_inapplicable_domain_excluded() -> None:
    ref = DomainMemoryReference(
        reference_id="ref:knowledge:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:100",
        domain_id="domain:finance",
        applicable_domains=("domain:finance",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
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

    assert len(view.selected_references) == 0
    assert len(view.excluded_decisions) == 1
    assert (
        view.excluded_decisions[0].code
        == DomainMemorySelectionDecisionCode.EXCLUDED_DOMAIN_INAPPLICABLE
    )


def test_resolve_supporting_domain_requires_permission() -> None:
    ref = DomainMemoryReference(
        reference_id="ref:knowledge:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:100",
        domain_id="domain:fitness",
        applicable_domains=("domain:fitness",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    req_no_perm = DomainMemoryViewRequest(
        request_id="req:1",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        candidates=(ref,),
    )
    inventory_no_perm = DomainMemoryReferenceInventory(references=(ref,))
    resolver = DefaultDomainMemoryViewResolver()
    view_no_perm = resolver.resolve(req_no_perm, inventory_no_perm)

    assert len(view_no_perm.selected_references) == 0
    assert (
        view_no_perm.excluded_decisions[0].code
        == DomainMemorySelectionDecisionCode.EXCLUDED_PERMISSION_DENIED
    )

    req_with_perm = DomainMemoryViewRequest(
        request_id="req:2",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        permission_decision_ids=("perm:cross:1",),
        candidates=(ref,),
    )
    inventory_with_perm = DomainMemoryReferenceInventory(
        references=(ref,),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:cross:1",
                allowed=True,
                capabilities=("READ",),
                source_domain_id="domain:fitness",
                target_domain_id="domain:health",
            ),
        ),
    )
    view_with_perm = resolver.resolve(req_with_perm, inventory_with_perm)
    assert len(view_with_perm.selected_references) == 1

    validator = DefaultDomainMemoryIntegrationValidator()
    val_res = validator.validate_view(
        view_with_perm, req_with_perm, inventory_with_perm
    )
    assert val_res.is_valid is True


def test_resolve_arbitrary_permission_id_denied() -> None:
    ref = DomainMemoryReference(
        reference_id="ref:knowledge:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:100",
        domain_id="domain:fitness",
        applicable_domains=("domain:fitness",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    req = DomainMemoryViewRequest(
        request_id="req:1",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        permission_decision_ids=("perm:fake",),
        candidates=(ref,),
    )
    inventory = DomainMemoryReferenceInventory(references=(ref,))
    resolver = DefaultDomainMemoryViewResolver()
    view = resolver.resolve(req, inventory)

    assert len(view.selected_references) == 0
    assert (
        view.excluded_decisions[0].code
        == DomainMemorySelectionDecisionCode.EXCLUDED_PERMISSION_DENIED
    )


def test_resolve_wrong_capability_permission_denied() -> None:
    ref = DomainMemoryReference(
        reference_id="ref:knowledge:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:100",
        domain_id="domain:fitness",
        applicable_domains=("domain:fitness",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    req = DomainMemoryViewRequest(
        request_id="req:1",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        permission_decision_ids=("perm:write_only",),
        candidates=(ref,),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:write_only",
                allowed=True,
                capabilities=("PROPOSE",),
                source_domain_id="domain:fitness",
                target_domain_id="domain:health",
            ),
        ),
    )
    resolver = DefaultDomainMemoryViewResolver()
    view = resolver.resolve(req, inventory)

    assert len(view.selected_references) == 0
    assert (
        view.excluded_decisions[0].code
        == DomainMemorySelectionDecisionCode.EXCLUDED_PERMISSION_DENIED
    )


def test_resolve_superseded_and_conflict_handling() -> None:
    superseded_ref = DomainMemoryReference(
        reference_id="ref:knowledge:old",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:old",
        domain_id="domain:health",
        superseded_by_id="ref:knowledge:new",
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    conflict_ref = DomainMemoryReference(
        reference_id="ref:knowledge:conflict",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:conflict",
        domain_id="domain:health",
        has_unresolved_conflict=True,
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    req = DomainMemoryViewRequest(
        request_id="req:1",
        primary_domain="domain:health",
        permission_decision_ids=("perm:1",),
        candidates=(superseded_ref, conflict_ref),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(superseded_ref, conflict_ref),
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

    decisions = {d.reference_id: d.code for d in view.excluded_decisions}
    assert (
        decisions["ref:knowledge:old"]
        == DomainMemorySelectionDecisionCode.EXCLUDED_SUPERSEDED
    )
    assert (
        decisions["ref:knowledge:conflict"]
        == DomainMemorySelectionDecisionCode.EXCLUDED_PRESERVED_CONFLICT
    )


def test_resolve_exact_coverage_and_disjointness() -> None:
    r1 = DomainMemoryReference(
        reference_id="ref:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:1",
        domain_id="domain:health",
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    r2 = DomainMemoryReference(
        reference_id="ref:2",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:2",
        domain_id="domain:fitness",
    )
    req = DomainMemoryViewRequest(
        request_id="req:1",
        primary_domain="domain:health",
        permission_decision_ids=("perm:1",),
        candidates=(r1, r2),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(r1, r2),
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

    selected_ids = {r.reference_id for r in view.selected_references}
    excluded_ids = {d.reference_id for d in view.excluded_decisions}

    assert selected_ids.isdisjoint(excluded_ids)
    assert selected_ids | excluded_ids == {"ref:1", "ref:2"}


def test_resolver_view_id_suffix_matches_content_digest() -> None:
    ref = DomainMemoryReference(
        reference_id="ref:knowledge:digest",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:digest",
        domain_id="domain:health",
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    request = DomainMemoryViewRequest(
        request_id="req:digest",
        primary_domain="domain:health",
        candidates=(ref,),
    )
    inventory = DomainMemoryReferenceInventory(references=(ref,))

    view = DefaultDomainMemoryViewResolver().resolve(request, inventory)

    assert view.view_id.rsplit(":", 1)[-1] == view.content_digest[:12]


def test_same_request_id_different_trace_produces_different_view_id() -> None:
    ref = DomainMemoryReference(
        reference_id="ref:knowledge:identity",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:identity",
        domain_id="domain:health",
    )
    inventory = DomainMemoryReferenceInventory(references=(ref,))
    resolver = DefaultDomainMemoryViewResolver()

    first = resolver.resolve(
        DomainMemoryViewRequest(
            request_id="req:identity",
            primary_domain="domain:health",
            trace_id="trace:first",
            candidates=(ref,),
        ),
        inventory,
    )
    second = resolver.resolve(
        DomainMemoryViewRequest(
            request_id="req:identity",
            primary_domain="domain:health",
            trace_id="trace:second",
            candidates=(ref,),
        ),
        inventory,
    )

    assert first.view_id != second.view_id


def test_same_request_id_different_temporal_reference_produces_different_view_id(
) -> None:
    ref = DomainMemoryReference(
        reference_id="ref:knowledge:temporal-identity",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:temporal-identity",
        domain_id="domain:health",
    )
    inventory = DomainMemoryReferenceInventory(references=(ref,))
    resolver = DefaultDomainMemoryViewResolver()

    first = resolver.resolve(
        DomainMemoryViewRequest(
            request_id="req:temporal-identity",
            primary_domain="domain:health",
            temporal_reference="2026-01-01T00:00:00+00:00",
            candidates=(ref,),
        ),
        inventory,
    )
    second = resolver.resolve(
        DomainMemoryViewRequest(
            request_id="req:temporal-identity",
            primary_domain="domain:health",
            temporal_reference="2026-02-01T00:00:00+00:00",
            candidates=(ref,),
        ),
        inventory,
    )

    assert first.view_id != second.view_id


def test_same_request_id_different_supporting_domains_produces_different_view_id() -> None:
    ref = DomainMemoryReference(
        reference_id="ref:knowledge:supp-id",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:supp-id",
        domain_id="domain:health",
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    inventory = DomainMemoryReferenceInventory(references=(ref,))
    resolver = DefaultDomainMemoryViewResolver()

    first = resolver.resolve(
        DomainMemoryViewRequest(
            request_id="req:supp-id",
            primary_domain="domain:health",
            supporting_domains=(),
            candidates=(ref,),
        ),
        inventory,
    )
    second = resolver.resolve(
        DomainMemoryViewRequest(
            request_id="req:supp-id",
            primary_domain="domain:health",
            supporting_domains=("domain:nutrition",),
            candidates=(ref,),
        ),
        inventory,
    )

    assert first.selected_references == second.selected_references
    assert first.selection_decisions == second.selection_decisions
    assert first.view_id != second.view_id


def test_same_request_id_different_resolution_reference_id_produces_different_view_id() -> None:
    ref = DomainMemoryReference(
        reference_id="ref:knowledge:res-id",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:res-id",
        domain_id="domain:health",
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    inventory = DomainMemoryReferenceInventory(references=(ref,))
    resolver = DefaultDomainMemoryViewResolver()

    first = resolver.resolve(
        DomainMemoryViewRequest(
            request_id="req:res-id",
            primary_domain="domain:health",
            resolution_reference_id=None,
            candidates=(ref,),
        ),
        inventory,
    )
    second = resolver.resolve(
        DomainMemoryViewRequest(
            request_id="req:res-id",
            primary_domain="domain:health",
            resolution_reference_id="ref:knowledge:res-id",
            candidates=(ref,),
        ),
        inventory,
    )

    assert first.selected_references == second.selected_references
    assert first.selection_decisions == second.selection_decisions
    assert first.view_id != second.view_id


def test_same_request_id_different_requested_kinds_produces_different_view_id() -> None:
    ref = DomainMemoryReference(
        reference_id="ref:knowledge:kind-id",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:kind-id",
        domain_id="domain:health",
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )
    inventory = DomainMemoryReferenceInventory(references=(ref,))
    resolver = DefaultDomainMemoryViewResolver()

    first = resolver.resolve(
        DomainMemoryViewRequest(
            request_id="req:kind-id",
            primary_domain="domain:health",
            requested_kinds=(),
            candidates=(ref,),
        ),
        inventory,
    )
    second = resolver.resolve(
        DomainMemoryViewRequest(
            request_id="req:kind-id",
            primary_domain="domain:health",
            requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
            candidates=(ref,),
        ),
        inventory,
    )

    assert first.selected_references == second.selected_references
    assert first.selection_decisions == second.selection_decisions
    assert first.view_id != second.view_id


def test_same_request_id_different_permission_decision_ids_produces_different_view_id() -> None:
    from cmm.domains.memory_contracts import DomainMemoryPermissionDecisionSnapshot

    ref = DomainMemoryReference(
        reference_id="ref:knowledge:perm-id",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:perm-id",
        domain_id="domain:health",
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
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
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:2",
                allowed=True,
                capabilities=("READ",),
                target_domain_id="domain:health",
            ),
        ),
    )
    resolver = DefaultDomainMemoryViewResolver()

    first = resolver.resolve(
        DomainMemoryViewRequest(
            request_id="req:perm-id",
            primary_domain="domain:health",
            permission_decision_ids=("perm:1",),
            candidates=(ref,),
        ),
        inventory,
    )
    second = resolver.resolve(
        DomainMemoryViewRequest(
            request_id="req:perm-id",
            primary_domain="domain:health",
            permission_decision_ids=("perm:1", "perm:2"),
            candidates=(ref,),
        ),
        inventory,
    )

    assert first.selected_references == second.selected_references
    assert first.view_id != second.view_id


def test_timeless_with_expires_at_without_temporal_reference_is_excluded() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemorySelectionDecisionCode,
        DomainMemoryTemporalKind,
        DomainMemoryTemporalSnapshot,
    )

    view = _resolve_temporal_reference(
        DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.TIMELESS,
            expires_at="2020-12-31T23:59:59+00:00",
        ),
        temporal_reference=None,
    )

    assert view.selected_references == ()
    assert view.selection_decisions[0].code == DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_INVALID


def _resolve_temporal_reference(
    temporal: object,
    *,
    temporal_reference: str | None = None,
):
    from cmm.domains.memory_contracts import (
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemoryReference,
        DomainMemoryReferenceInventory,
        DomainMemoryReferenceKind,
        DomainMemoryViewRequest,
    )
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    reference = DomainMemoryReference(
        reference_id="ref:knowledge:temporal",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:temporal",
        domain_id="domain:health",
        evidence_ids=("ev:temporal",),
        resource_ids=("res:temporal",),
        temporal=temporal,
    )
    request = DomainMemoryViewRequest(
        request_id="req:temporal",
        primary_domain="domain:health",
        candidates=(reference,),
        permission_decision_ids=("perm:read:temporal",),
        temporal_reference=temporal_reference,
    )
    inventory = DomainMemoryReferenceInventory(
        references=(reference,),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:read:temporal",
                allowed=True,
                capabilities=("READ",),
                target_domain_id="domain:health",
            ),
        ),
    )
    return DefaultDomainMemoryViewResolver().resolve(request, inventory)


def test_interval_without_temporal_reference_is_not_selected() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemorySelectionDecisionCode,
        DomainMemoryTemporalKind,
        DomainMemoryTemporalSnapshot,
    )

    view = _resolve_temporal_reference(
        DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.INTERVAL,
            valid_from="2020-01-01T00:00:00+00:00",
            valid_to="2020-12-31T23:59:59+00:00",
        )
    )

    assert view.selected_references == ()
    assert view.selection_decisions[0].code == DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_INVALID


def test_expired_timeless_reference_is_not_selected() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemorySelectionDecisionCode,
        DomainMemoryTemporalKind,
        DomainMemoryTemporalSnapshot,
    )

    view = _resolve_temporal_reference(
        DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.TIMELESS,
            expires_at="2020-12-31T23:59:59+00:00",
        ),
        temporal_reference="2026-01-01T00:00:00+00:00",
    )

    assert view.selected_references == ()
    assert view.selection_decisions[0].code == DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_EXPIRED


def test_unknown_temporal_scope_without_reference_is_not_selected() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemorySelectionDecisionCode,
        DomainMemoryTemporalKind,
        DomainMemoryTemporalSnapshot,
    )

    view = _resolve_temporal_reference(
        DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.UNKNOWN,
        )
    )

    assert view.selected_references == ()
    assert view.selection_decisions[0].code == DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_UNKNOWN


def test_timeless_without_expiration_and_without_temporal_reference_is_selected() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemorySelectionDecisionCode,
        DomainMemoryTemporalKind,
        DomainMemoryTemporalSnapshot,
    )

    view = _resolve_temporal_reference(
        DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.TIMELESS,
        )
    )

    assert len(view.selected_references) == 1
    assert view.selection_decisions[0].code == DomainMemorySelectionDecisionCode.SELECTED


def test_resolver_rejects_unknown_permission_decision_ids() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemoryReference,
        DomainMemoryReferenceInventory,
        DomainMemoryReferenceKind,
        DomainMemorySelectionDecisionCode,
        DomainMemoryViewRequest,
    )
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    reference = DomainMemoryReference(
        reference_id="ref:knowledge:perm_test",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:perm_test",
        domain_id="domain:health",
        evidence_ids=("ev:perm",),
        resource_ids=("res:perm",),
    )
    request = DomainMemoryViewRequest(
        request_id="req:perm_test",
        primary_domain="domain:health",
        candidates=(reference,),
        permission_decision_ids=("perm:known", "perm:unknown"),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(reference,),
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

    assert view.selected_references == ()
    assert len(view.selection_decisions) == 1
    assert view.selection_decisions[0].code == DomainMemorySelectionDecisionCode.EXCLUDED_PERMISSION_DENIED


def test_unknown_temporal_with_temporal_reference_is_excluded_unknown() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemoryReference,
        DomainMemoryReferenceInventory,
        DomainMemoryReferenceKind,
        DomainMemorySelectionDecisionCode,
        DomainMemoryTemporalKind,
        DomainMemoryTemporalSnapshot,
        DomainMemoryViewRequest,
    )
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    ref = DomainMemoryReference(
        reference_id="ref:knowledge:unknown_temp",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:unknown_temp",
        domain_id="domain:health",
        applicable_domains=("domain:health",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
        temporal=DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.UNKNOWN,
        ),
    )
    req = DomainMemoryViewRequest(
        request_id="req:unknown_temp",
        primary_domain="domain:health",
        permission_decision_ids=("perm:1",),
        temporal_reference="2026-08-03T12:00:00Z",
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

    view = DefaultDomainMemoryViewResolver().resolve(req, inventory)

    assert view.selected_references == ()
    assert len(view.selection_decisions) == 1
    assert view.selection_decisions[0].code == DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_UNKNOWN


def test_safety_temporal_kind_is_excluded_invalid() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemoryReference,
        DomainMemoryReferenceInventory,
        DomainMemoryReferenceKind,
        DomainMemorySelectionDecisionCode,
        DomainMemoryTemporalKind,
        DomainMemoryTemporalSnapshot,
        DomainMemoryViewRequest,
    )
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    ref = DomainMemoryReference(
        reference_id="ref:knowledge:safety_temp",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:safety_temp",
        domain_id="domain:health",
        applicable_domains=("domain:health",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
        temporal=DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.SAFETY,
        ),
    )
    req = DomainMemoryViewRequest(
        request_id="req:safety_temp",
        primary_domain="domain:health",
        permission_decision_ids=("perm:1",),
        temporal_reference="2026-08-03T12:00:00Z",
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

    view = DefaultDomainMemoryViewResolver().resolve(req, inventory)

    assert view.selected_references == ()
    assert len(view.selection_decisions) == 1
    assert view.selection_decisions[0].code == DomainMemorySelectionDecisionCode.EXCLUDED_TEMPORAL_INVALID
