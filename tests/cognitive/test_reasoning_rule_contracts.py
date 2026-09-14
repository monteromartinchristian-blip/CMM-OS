from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from types import MappingProxyType, SimpleNamespace

import pytest

from cmm.cognitive import (
    AuthoritativeSourceClaim,
    ContradictionStatus,
    ReasoningAuthorityContext,
    ReasoningEscalation,
    ReasoningFinding,
    ReasoningGap,
    ReasoningRecommendation,
    ReasoningRiskLevel,
    ReasoningRuleCategory,
    ReasoningRuleContext,
    ReasoningRuleContractError,
    ReasoningRuleDefinition,
    ReasoningRuleError,
    ReasoningRuleResult,
    ReasoningRuleResultStatus,
    ReasoningRuleScope,
    ReasoningRuleStatus,
    ReasoningRuleTraceEntry,
    ReasoningSeverity,
    ResourceProvenance,
    ResourceSourceKind,
)

NOW = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)


def definition(**overrides: object) -> ReasoningRuleDefinition:
    values: dict[str, object] = {
        "id": "global.preserve_provenance",
        "name": "PreserveProvenance",
        "version": "1.0.0",
        "scope": ReasoningRuleScope.GLOBAL,
        "category": ReasoningRuleCategory.EPISTEMIC,
        "status": ReasoningRuleStatus.ENABLED,
        "priority": 1000,
        "required_permissions": (),
        "risk_level": ReasoningRiskLevel.LOW,
        "deterministic": True,
        "description": "Preserve evidence provenance.",
        "metadata": {"nested": {"items": ["a"]}},
    }
    values.update(overrides)
    return ReasoningRuleDefinition(**values)  # type: ignore[arg-type]


def test_definition_is_strict_deeply_immutable_and_hashable() -> None:
    source = {"nested": {"items": ["a"]}}
    item = definition(metadata=source)
    source["nested"]["items"].append("b")  # type: ignore[index,union-attr]
    assert item.metadata["nested"]["items"] == ("a",)  # type: ignore[index]
    assert isinstance(item.metadata, MappingProxyType)
    hash(item)
    with pytest.raises(FrozenInstanceError):
        item.priority = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", ""),
        ("id", "Not Canonical"),
        ("name", " "),
        ("version", "1.10"),
        ("priority", True),
        ("priority", 10001),
        ("required_permissions", "permission.read"),
        ("required_permissions", ("permission.read", "permission.read")),
        ("deterministic", 1),
        ("metadata", {"bad": object()}),
    ],
)
def test_definition_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ReasoningRuleContractError) as caught:
        definition(**{field: value})
    assert caught.value.field is not None


def test_definition_enforces_scope_domain_invariants() -> None:
    with pytest.raises(ReasoningRuleContractError, match="domain_id"):
        definition(domain_id="domain:health")
    domain = definition(
        id="health.red_flags",
        scope="domain",
        domain_id="domain:health",
    )
    assert domain.domain_id == "domain:health"
    with pytest.raises(ReasoningRuleContractError, match="domain_id"):
        definition(id="health.red_flags", scope="domain")


def test_audit_elements_are_typed_and_preserve_sources() -> None:
    finding = ReasoningFinding(
        code="PROVENANCE_MISSING",
        message="Knowledge item has no evidence.",
        severity=ReasoningSeverity.WARNING,
        rule_id="global.preserve_provenance",
        references=("knowledge:1",),
    )
    recommendation = ReasoningRecommendation(
        code="ADD_EVIDENCE",
        message="Add an evidence reference.",
        severity="info",
        rule_id=finding.rule_id,
    )
    gap = ReasoningGap(
        code="EVIDENCE_GAP",
        message="Evidence is required.",
        severity="warning",
        rule_id=finding.rule_id,
    )
    escalation = ReasoningEscalation(
        code="HUMAN_REVIEW_RECOMMENDED",
        message="Review sensitive evidence.",
        severity="error",
        rule_id=finding.rule_id,
    )
    trace = ReasoningRuleTraceEntry(
        code="RULE_APPLIED",
        message="Rule completed.",
        rule_id=finding.rule_id,
        occurred_at=NOW,
        references=("knowledge:1",),
    )
    assert finding.severity is ReasoningSeverity.WARNING
    assert recommendation.rule_id == gap.rule_id == escalation.rule_id
    assert trace.occurred_at == NOW


def test_reasoning_severity_has_only_reasoning_values() -> None:
    assert tuple(item.value for item in ReasoningSeverity) == (
        "info",
        "warning",
        "error",
        "critical",
    )
    assert tuple(item.value for item in ContradictionStatus) == (
        "unresolved",
        "resolved",
        "deferred",
        "acknowledged",
    )


def test_context_rejects_implicit_runtime_and_naive_time() -> None:
    context = ReasoningRuleContext(
        reasoning_id="reasoning-1",
        active_domains=("domain:health", "domain:project"),
        primary_domain="domain:health",
        supporting_domains=("domain:project",),
        effective_permissions=("knowledge.health.read",),
        effective_risk="high",
        timestamp=NOW,
        metadata={"safe": [1, 2]},
    )
    assert context.active_domains == ("domain:health", "domain:project")
    assert context.metadata["safe"] == (1, 2)
    with pytest.raises(ReasoningRuleContractError, match="timezone-aware"):
        ReasoningRuleContext(reasoning_id="r", timestamp=NOW.replace(tzinfo=None))
    with pytest.raises(ReasoningRuleContractError, match="primary_domain"):
        ReasoningRuleContext(
            reasoning_id="r",
            active_domains=("domain:project",),
            primary_domain="domain:health",
            timestamp=NOW,
        )


def test_result_duration_and_confidence_are_bounded() -> None:
    result = ReasoningRuleResult(
        rule_id="global.preserve_provenance",
        rule_name="PreserveProvenance",
        rule_version="1.0.0",
        status=ReasoningRuleResultStatus.APPLIED,
        confidence_delta=0.25,
        started_at=NOW,
        completed_at=NOW,
    )
    assert result.duration_seconds == 0.0
    with pytest.raises(ReasoningRuleContractError, match="confidence_delta"):
        ReasoningRuleResult(
            rule_id=result.rule_id,
            rule_name=result.rule_name,
            rule_version=result.rule_version,
            status="applied",
            confidence_delta=float("nan"),
            started_at=NOW,
            completed_at=NOW,
        )
    with pytest.raises(ReasoningRuleContractError, match="completed_at"):
        ReasoningRuleResult(
            rule_id=result.rule_id,
            rule_name=result.rule_name,
            rule_version=result.rule_version,
            status="applied",
            started_at=NOW,
            completed_at=datetime(2026, 8, 1, 11, tzinfo=timezone.utc),
        )


def claim(**overrides: object) -> AuthoritativeSourceClaim:
    values: dict[str, object] = {
        "claim_id": "clinical_status",
        "source_domain": "domain:health",
        "purpose": "diagnostic-status-review",
        "provenance": ResourceProvenance(
            source_type=ResourceSourceKind.UPLOADED_FILE,
            source_id="clinical-record:1",
            retrieved_at=NOW,
        ),
    }
    values.update(overrides)
    return AuthoritativeSourceClaim(**values)  # type: ignore[arg-type]


def authority(**overrides: object) -> ReasoningAuthorityContext:
    values: dict[str, object] = {
        "actor_id": "actor-1",
        "session_id": "session-1",
        "source_domain": "domain:health",
        "target_domain": "domain:neurodivergence",
        "resource_ids": ("clinical_status",),
        "purpose": "diagnostic-status-review",
        "permission_decision_id": "permission-gate-decision-1",
        "permission_outcome": "approval_consumed",
        "approval_consumed": True,
        "authoritative_claims": (claim(),),
    }
    values.update(overrides)
    return ReasoningAuthorityContext(**values)  # type: ignore[arg-type]


def test_authoritative_source_claim_requires_canonical_provenance() -> None:
    item = claim()
    assert item.claim_id == "clinical_status"
    assert item.source_domain == "domain:health"
    assert item.purpose == "diagnostic-status-review"
    assert isinstance(item.provenance, ResourceProvenance)
    assert item.source_provenance_id == "clinical-record:1"
    with pytest.raises(FrozenInstanceError):
        item.claim_id = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("claim_id", ""),
        ("claim_id", "   "),
        ("claim_id", None),
        ("claim_id", 7),
        ("source_domain", "health"),
        ("source_domain", "domain:Health"),
        ("source_domain", "domain:"),
        ("purpose", ""),
        ("purpose", "  "),
        ("purpose", None),
        ("provenance", None),
        (
            "provenance",
            {"source_type": "uploaded_file", "source_id": "clinical-record:1"},
        ),
        ("provenance", SimpleNamespace(source_id="clinical-record:1")),
        ("provenance", "clinical-record:1"),
        ("provenance", object()),
    ],
)
def test_authoritative_source_claim_rejects_untrusted_values(
    field: str, value: object
) -> None:
    with pytest.raises(ReasoningRuleContractError):
        claim(**{field: value})


def test_authoritative_source_claim_rejects_provenance_substitutes() -> None:
    """Only the exact canonical provenance contract counts as provenance."""

    class _DuckProvenance:
        def __init__(self) -> None:
            self.source_id = "clinical-record:1"
            self.source_type = ResourceSourceKind.UPLOADED_FILE

    with pytest.raises(ReasoningRuleContractError):
        claim(provenance=_DuckProvenance())


def test_authoritative_source_claim_has_no_rehydration_path() -> None:
    """Shape is not provenance: there is no from_dict-style rehydration."""
    assert not hasattr(AuthoritativeSourceClaim, "from_dict")


def test_authority_context_accepts_valid_trusted_values() -> None:
    context = authority()
    assert context.source_domain == "domain:health"
    assert context.target_domain == "domain:neurodivergence"
    assert context.resource_ids == ("clinical_status",)
    assert context.permission_outcome == "approval_consumed"
    assert context.approval_consumed is True
    assert context.authoritative_claims == (claim(),)
    assert context.authoritative_claim_ids == ("clinical_status",)
    assert context.authoritative_claims[0].source_provenance_id == "clinical-record:1"
    with pytest.raises(FrozenInstanceError):
        context.approval_consumed = False  # type: ignore[misc]


def test_authority_context_naked_claim_ids_are_no_longer_constructible() -> None:
    """The core guarantee: authority cannot exist without canonical provenance."""
    with pytest.raises(TypeError):
        ReasoningAuthorityContext(
            actor_id="actor-1",
            session_id="session-1",
            source_domain="domain:health",
            target_domain="domain:neurodivergence",
            resource_ids=("clinical_status",),
            purpose="diagnostic-status-review",
            permission_decision_id="permission-gate-decision-1",
            permission_outcome="approval_consumed",
            approval_consumed=True,
            authoritative_claim_ids=("clinical_status",),
        )


def test_authority_context_allow_outcome_requires_no_approval() -> None:
    context = authority(permission_outcome="allow", approval_consumed=False)
    assert context.permission_outcome == "allow"
    assert context.approval_consumed is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("actor_id", ""),
        ("actor_id", "   "),
        ("session_id", ""),
        ("source_domain", "not-a-domain"),
        ("target_domain", "not-a-domain"),
        ("resource_ids", ()),
        ("resource_ids", ("a", "a")),
        ("purpose", ""),
        ("permission_decision_id", ""),
        ("permission_outcome", "deny"),
        ("permission_outcome", "approval_required"),
        ("approval_consumed", 1),
        ("authoritative_claims", (claim(), claim())),
        (
            "authoritative_claims",
            (
                {
                    "claim_id": "clinical_status",
                    "source_domain": "domain:health",
                    "purpose": "diagnostic-status-review",
                    "provenance": {"source_id": "clinical-record:1"},
                },
            ),
        ),
        ("authoritative_claims", (object(),)),
        ("authoritative_claims", ("clinical_status",)),
    ],
)
def test_authority_context_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ReasoningRuleContractError):
        authority(**{field: value})


def test_authority_context_rejects_claims_not_bound_to_its_domain_and_purpose() -> None:
    with pytest.raises(ReasoningRuleContractError):
        authority(authoritative_claims=(claim(source_domain="domain:mental-health"),))
    with pytest.raises(ReasoningRuleContractError):
        authority(authoritative_claims=(claim(purpose="another-purpose"),))


def test_authority_context_rejects_same_source_and_target_domain() -> None:
    with pytest.raises(ReasoningRuleContractError):
        authority(source_domain="domain:health", target_domain="domain:health")


def test_authority_context_enforces_approval_consumed_outcome_consistency() -> None:
    with pytest.raises(ReasoningRuleContractError):
        authority(permission_outcome="approval_consumed", approval_consumed=False)
    with pytest.raises(ReasoningRuleContractError):
        authority(permission_outcome="allow", approval_consumed=True)


def test_context_accepts_optional_trusted_authority_and_defaults_to_none() -> None:
    plain = ReasoningRuleContext(reasoning_id="r", timestamp=NOW)
    assert plain.authority_context is None
    trusted = ReasoningRuleContext(
        reasoning_id="r",
        timestamp=NOW,
        authority_context=authority(),
    )
    assert trusted.authority_context == authority()
    with pytest.raises(ReasoningRuleContractError):
        ReasoningRuleContext(
            reasoning_id="r",
            timestamp=NOW,
            authority_context={"actor_id": "actor-1"},  # type: ignore[arg-type]
        )


def test_reasoning_error_details_are_deeply_immutable() -> None:
    source = {"nested": {"items": ["a"]}}
    error = ReasoningRuleError("safe", details=source)
    source["nested"]["items"].append("b")  # type: ignore[index,union-attr]
    assert error.details["nested"]["items"] == ("a",)  # type: ignore[index]
    with pytest.raises(TypeError):
        error.details["nested"]["new"] = True  # type: ignore[index]
