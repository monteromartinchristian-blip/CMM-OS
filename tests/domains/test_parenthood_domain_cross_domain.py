"""Phase 10.27 — Cross-Domain Boundary and Sibling Workspace Invariance Suite."""

from __future__ import annotations

import pytest

from cmm.cognitive.enums import ReasoningRuleResultStatus, ReasoningSeverity
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.identifiers import DomainId
from cmm.domains.parenthood.bootstrap import build_standard_parenthood_domain_bootstrap
from cmm.domains.parenthood.rules import (
    DevelopmentalContextRule,
    HealthBoundaryRule,
    MinorPrivacyRule,
    SiblingIdentityIsolationRule,
)
from cmm.domains.parenthood.workspaces import (
    select_journey_transfer_candidates,
)


def _ctx(
    active_domains: tuple[str, ...] = ("domain:parenthood",),
    metadata: dict | None = None,
) -> ReasoningRuleContext:
    from datetime import datetime, timezone

    return ReasoningRuleContext(
        reasoning_id="cross-domain-test",
        timestamp=datetime.now(timezone.utc),
        active_domains=active_domains,
        primary_domain=active_domains[0],
        metadata=metadata or {},
    )


def test_coexistence_with_standard_registries() -> None:
    """Verify Parenthood and General coexist without collision."""
    bootstrap = build_standard_parenthood_domain_bootstrap()

    # Domains registered
    assert bootstrap.domain_registry.get("domain:general") is not None
    assert bootstrap.domain_registry.get("domain:parenthood") is not None

    # Profiles registered
    assert bootstrap.profile_registry.get_by_domain(DomainId("general")) is not None
    assert bootstrap.profile_registry.get_by_domain(DomainId("parenthood")) is not None


def test_cross_domain_sibling_isolation_invariance() -> None:
    """Verify cross-domain reasoning preserves sibling isolation strictly."""
    rule = SiblingIdentityIsolationRule()

    # Context mixes Sibling 1 and Sibling 2 data
    ctx = _ctx(
        active_domains=("domain:parenthood", "domain:health", "domain:education"),
        metadata={
            "active_child_id": "child:001",
            "context_records": [
                {
                    "child_id": "child:001",
                    "type": "routine",
                    "bedtime": "20:00",
                    "is_shared": False,
                },
                {
                    "child_id": "child:002",
                    "type": "pediatric_note",
                    "allergy": "penicillin",
                    "is_shared": False,
                },
            ],
        },
    )
    result = rule.evaluate(ctx)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    findings = [f for f in result.findings if f.code == "SIBLING_CONTAMINATION_BLOCKED"]
    assert len(findings) == 1
    assert "child:002" in findings[0].message
    assert findings[0].severity is ReasoningSeverity.CRITICAL


def test_cross_domain_health_boundary_invariance() -> None:
    """Verify health boundary prevents clinical diagnosis in parenthood workflows."""
    dev_rule = DevelopmentalContextRule()
    health_rule = HealthBoundaryRule()

    # Proposed psychiatric diagnosis for minor
    ctx = _ctx(
        active_domains=("domain:parenthood", "domain:health"),
        metadata={
            "child_observations": [
                {
                    "behavior": "restlessness in seat",
                    "stage": "school_age",
                    "proposed_diagnosis": "ADHD_combined_type",
                },
            ]
        },
    )
    res_dev = dev_rule.evaluate(ctx)
    res_health = health_rule.evaluate(ctx)

    assert any(f.code == "PATHOLOGY_LABEL_REJECTED" for f in res_dev.findings)
    assert any(f.code == "HEALTH_BOUNDARY_ENFORCED" for f in res_health.findings)


def test_cross_domain_minor_privacy_fail_closed() -> None:
    """Verify minor privacy rule blocks external actions across domains."""
    rule = MinorPrivacyRule()

    ctx = _ctx(
        active_domains=("domain:parenthood", "domain:finance", "domain:legal"),
        metadata={
            "child_id": "child:001",
            "action_proposed": "external_api_export_child_records",
        },
    )
    result = rule.evaluate(ctx)
    assert any(f.code == "MINOR_PRIVACY_RESTRICTION" for f in result.findings)


def test_journey_to_child_selective_transfer_invariance() -> None:
    """Verify pre-parenthood journey records are never bulk-copied into a child workspace."""
    journey_dossier = {
        "doc-1": {
            "topic": "surrogacy_contract",
            "category": "legal_contract",
            "is_child_facing": False,
        },
        "doc-2": {
            "topic": "clinic_medical_history",
            "category": "medical_history",
            "is_child_facing": False,
        },
        "doc-3": {
            "topic": "selected_pediatrician",
            "category": "pediatric_contact",
            "is_child_facing": True,
        },
        "doc-4": {
            "topic": "family_origin_story",
            "category": "narrative",
            "is_child_facing": True,
        },
    }

    # Bulk copy without selection raises ValueError
    with pytest.raises(ValueError, match="bulk copy prohibited"):
        select_journey_transfer_candidates(
            journey_context=journey_dossier,
            selected_keys=None,
            allow_bulk_transfer=True,
        )

    # Explicit selective transfer only selects specified keys
    transfers = select_journey_transfer_candidates(
        journey_context=journey_dossier,
        selected_keys=("doc-3", "doc-4"),
        target_child_id="child:001",
    )

    transfer_keys = [t["key"] for t in transfers]
    assert "doc-3" in transfer_keys
    assert "doc-4" in transfer_keys
    assert "doc-1" not in transfer_keys
    assert "doc-2" not in transfer_keys
