"""Phase 10.23 — Opposition Domain presentation + trace tests."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.oppositions import (
    assemble_oppositions_trace,
    build_oppositions_presentation_policy,
    build_oppositions_trace_contribution,
    build_oppositions_trace_reference,
    validate_oppositions_trace,
)
from cmm.domains.trace_contracts import (
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
)


def test_presentation_policy_preserves_distinctions():
    policy = build_oppositions_presentation_policy()
    protected = policy.protected_terms
    assert "planning_proposal" in protected
    assert "strategy_proposal" in protected
    assert "one_mock_not_trend" in protected
    assert "official_state" in protected
    assert "strategy_state" in protected


def test_presentation_require_uncertainty_and_provenance():
    policy = build_oppositions_presentation_policy()
    assert policy.include_uncertainty is True
    assert policy.include_provenance is True


def test_presentation_never_speculates():
    policy = build_oppositions_presentation_policy()
    assert policy.allow_speculation is False
    assert policy.require_disclaimers is True


def test_trace_reference_reuses_shared_contract():
    ref = build_oppositions_trace_reference(
        ref_id="res:1", kind=DomainTraceReferenceKind.RESOURCE_RESOLUTION
    )
    assert ref.ref_id == "res:1"


def test_trace_contribution_is_reference_only():
    contribution = build_oppositions_trace_contribution(domain_result_id="result:1")
    assert contribution.references
    assert contribution.domain_id == "domain:oppositions"


def test_assemble_trace_uses_shared_assembler():
    now = datetime.now(timezone.utc)
    trace = assemble_oppositions_trace(
        request_id="req1",
        resolution_context_id="resolution-context:1",
        resolution_result_id="resolution-result:1",
        composition_id="composition:1",
        domain_result_id="domain-result:1",
        started_at=now,
        completed_at=now,
    )
    assert trace.request_id == "req1"
    assert trace.references.resolution_context_id == "resolution-context:1"


def test_validate_trace_valid_with_full_inventory():
    from cmm.domains.oppositions.definition import OPPOSITIONS_DOMAIN_ID
    from cmm.domains.trace_contracts import (
        DomainTraceDomainSelection,
    )

    now = datetime.now(timezone.utc)
    trace = assemble_oppositions_trace(
        request_id="req1",
        resolution_context_id="resolution-context:1",
        resolution_result_id="resolution-result:1",
        composition_id="composition:1",
        domain_result_id="domain-result:1",
        started_at=now,
        completed_at=now,
    )
    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        domain_results=trace.domain_results,
        cross_domain_results=trace.references.cross_domain_results,
        expected_primary_domain=OPPOSITIONS_DOMAIN_ID,
        expected_supporting_domains=(),
        resolution_result_domains=DomainTraceDomainSelection(
            "resolution-result:1", OPPOSITIONS_DOMAIN_ID
        ),
        composition_domains=DomainTraceDomainSelection(
            "composition:1", OPPOSITIONS_DOMAIN_ID
        ),
    )
    result = validate_oppositions_trace(trace=trace, inventory=inventory)
    assert result.valid is True