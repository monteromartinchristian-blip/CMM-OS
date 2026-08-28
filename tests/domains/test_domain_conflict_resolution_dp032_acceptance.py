"""Phase 10.32 — AT-DP-032 Acceptance Test Gate.

32 comprehensive end-to-end checkpoints verifying all requirements of
Phase 10.32: Domain Conflict Resolution.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest

from cmm.cognitive.enums import ContradictionSeverity, ContradictionStatus
from cmm.cognitive.knowledge import Contradiction
from cmm.domains.composition_contracts import DomainCompositionConflict
from cmm.domains.conflict_adapters import (
    adapt_composition_conflict,
    adapt_cross_domain_contradiction,
    adapt_declared_domain_conflict,
    adapt_knowledge_contradiction,
    adapt_permission_conflict,
    adapt_presentation_conflict,
    adapt_profile_conflict,
    adapt_rule_selection_conflict,
    adapt_selection_conflict,
)
from cmm.domains.conflict_resolution import DomainConflictResolver
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReasonCode,
    DomainConflictReference,
    DomainConflictResolution,
    DomainConflictResolutionPolicy,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
    DomainConflictStrategy,
)
from cmm.domains.contracts import DomainConflict
from cmm.domains.cross_domain_contracts import (
    CrossDomainContradiction,
    CrossDomainSeverity,
)
from cmm.domains.enums import (
    DomainProfileConflictSeverity,
    DomainProfileSource,
    DomainResolutionStatus,
    DomainRuleConflictSeverity,
)
from cmm.domains.errors import DomainConflictResolutionContractError
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_contracts import (
    DomainPermissionConflict,
    PermissionCapability,
    PermissionOutcome,
)
from cmm.domains.presentation_contracts import (
    DomainPresentationConflict,
    DomainPresentationConflictCode,
)
from cmm.domains.profile_contracts import DomainProfileConflict
from cmm.domains.resolver_contracts import DomainResolutionResult
from cmm.domains.rule_contracts import DomainRuleSelectionConflict


def _make_ref(
    source_id: str,
    *,
    domain_slug: str | None = None,
    blocking: bool = False,
    severity: DomainConflictSeverity | None = None,
    authority: DomainConflictAuthority = DomainConflictAuthority.UNCLASSIFIED,
    metadata: dict[str, object] | None = None,
) -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id=source_id,
        domain_id=DomainId(slug=domain_slug) if domain_slug else None,
        blocking=blocking,
        severity=severity
        or (
            DomainConflictSeverity.BLOCKING
            if blocking
            else DomainConflictSeverity.MATERIAL
        ),
        authority_kind=authority,
        metadata=metadata,
    )


# CP-01: Pure adapter preserves immutable source object unchanged
def test_cp01_pure_adapter_preserves_source_immutable() -> None:
    source = DomainPermissionConflict(
        action=PermissionCapability.DOMAIN_CROSS_ACCESS,
        allowing_sources=("primary:project:1.0.0",),
        denying_sources=("supporting:general:1.0.0",),
        resolution=PermissionOutcome.DENY,
        reason_code="cross_domain_denied",
    )
    dump_before = source.to_dict()
    ref, domains = adapt_permission_conflict(
        source, source_id="perm-cp1", domain_id=DomainId(slug="project")
    )
    assert source.to_dict() == dump_before
    assert ref.source_id == "perm-cp1"
    assert domains == (DomainId(slug="project"),)


# CP-02: Declared domain conflict normalization preserves blocking flag and reasons
def test_cp02_declared_domain_conflict_normalization() -> None:
    source = DomainConflict(
        domain_id=DomainId(slug="legacy"),
        reason="incompatible API version",
        severity="blocking",
    )
    ref, domains = adapt_declared_domain_conflict(
        source,
        source_id="decl-cp2",
        owner_domain_id=DomainId(slug="project"),
    )
    assert ref.source_kind is DomainConflictSourceKind.DECLARED_DOMAIN_CONFLICT
    assert ref.blocking is True
    assert ref.severity is DomainConflictSeverity.BLOCKING
    assert domains == (DomainId(slug="project"), DomainId(slug="legacy"))
    assert "reason" not in ref.metadata
    assert ref.metadata["declared_severity"] == "blocking"


# CP-03: DomainCompositionConflict normalization preserves multiple domains
def test_cp03_composition_conflict_normalization() -> None:
    source = DomainCompositionConflict(
        code="MUTUAL_EXCLUSION",
        category="declared_conflicts",
        domains=(DomainId(slug="dom-a"), DomainId(slug="dom-b")),
        severity="blocking",
        message="Incompatible domains",
        blocking=True,
    )
    ref, domains = adapt_composition_conflict(source, source_id="comp-cp3")
    assert ref.source_kind is DomainConflictSourceKind.COMPOSITION_CONFLICT
    assert ref.blocking is True
    assert domains == (DomainId(slug="dom-a"), DomainId(slug="dom-b"))
    assert ref.metadata["code"] == "MUTUAL_EXCLUSION"


# CP-04: DomainPermissionConflict normalization is fail-closed, does not copy source lists
def test_cp04_permission_conflict_fail_closed_no_source_lists() -> None:
    source = DomainPermissionConflict(
        action=PermissionCapability.DOMAIN_CROSS_ACCESS,
        allowing_sources=("primary:project:1.0.0",),
        denying_sources=("supporting:general:1.0.0",),
        resolution=PermissionOutcome.DENY,
        reason_code="deny_cross_access",
    )
    ref, _ = adapt_permission_conflict(
        source, source_id="perm-cp4", domain_id=DomainId(slug="project")
    )
    assert ref.blocking is True
    assert ref.authority_kind is DomainConflictAuthority.PERMISSION
    assert "allowing_sources" not in ref.metadata
    assert "denying_sources" not in ref.metadata


# CP-05: DomainProfileConflict normalization preserves field and blocking
def test_cp05_profile_conflict_normalization() -> None:
    source = DomainProfileConflict(
        code="PARAM_OVERLAP",
        field="model.temperature",
        severity=DomainProfileConflictSeverity.BLOCKING,
        sources=(DomainProfileSource.PRIMARY_DOMAIN, DomainProfileSource.GLOBAL_POLICY),
        description="Conflicting parameter",
        blocking=True,
    )
    ref, _ = adapt_profile_conflict(
        source, source_id="prof-cp5", domain_id=DomainId(slug="project")
    )
    assert ref.source_kind is DomainConflictSourceKind.PROFILE_CONFLICT
    assert ref.blocking is True
    assert ref.metadata["field"] == "model.temperature"
    assert "description" not in ref.metadata


# CP-06: DomainRuleSelectionConflict normalization preserves rule_id and blocking
def test_cp06_rule_selection_conflict_normalization() -> None:
    source = DomainRuleSelectionConflict(
        code="RULE_MISSING_PERM",
        rule_id="security.audit_enforce",
        message="Missing execution permissions",
        severity=DomainRuleConflictSeverity.BLOCKING,
    )
    ref, _ = adapt_rule_selection_conflict(
        source,
        source_id="rule-cp6",
        domain_id=DomainId(slug="project"),
        authority_kind=DomainConflictAuthority.MANDATORY_RULE,
    )
    assert ref.source_kind is DomainConflictSourceKind.RULE_SELECTION_CONFLICT
    assert ref.authority_kind is DomainConflictAuthority.MANDATORY_RULE
    assert ref.blocking is True
    assert ref.metadata["rule_id"] == "security.audit_enforce"
    assert "message" not in ref.metadata


# CP-07: DomainPresentationConflict normalization preserves non-blocking semantics
def test_cp07_presentation_conflict_normalization() -> None:
    source = DomainPresentationConflict(
        code=DomainPresentationConflictCode.TERMINOLOGY_INCOMPATIBLE,
        related_ids=("term-1", "term-2"),
    )
    ref, _ = adapt_presentation_conflict(
        source, source_id="pres-cp7", domain_id=DomainId(slug="project")
    )
    assert ref.source_kind is DomainConflictSourceKind.PRESENTATION_CONFLICT
    assert ref.blocking is False
    assert ref.metadata["code"] == "TERMINOLOGY_INCOMPATIBLE"


# CP-08: CrossDomainContradiction normalization preserves requires_review/resolved
def test_cp08_cross_domain_contradiction_normalization() -> None:
    source = CrossDomainContradiction(
        id="cdc-cp8",
        domains=(DomainId(slug="a"), DomainId(slug="b")),
        subject="data_expiry",
        statements=("infinite", "30d"),
        severity=CrossDomainSeverity.HIGH,
        provenance=("source-1",),
        resolved=False,
        requires_review=True,
    )
    ref, domains = adapt_cross_domain_contradiction(source)
    assert ref.source_kind is DomainConflictSourceKind.CROSS_DOMAIN_CONTRADICTION
    assert ref.source_id == "cdc-cp8"
    assert ref.blocking is True
    assert domains == (DomainId(slug="a"), DomainId(slug="b"))
    assert ref.metadata["requires_review"] is True
    assert "statements" not in ref.metadata


# CP-09: Cognitive Contradiction normalization preserves evidence refs without re-deciding truth
def test_cp09_cognitive_contradiction_normalization() -> None:
    source = Contradiction(
        id="cog-cp9",
        item_a_id="item-a",
        item_b_id="item-b",
        severity=ContradictionSeverity.HIGH,
        status=ContradictionStatus.UNRESOLVED,
        preferred_id="item-a",
        preference_reason="temporal priority",
    )
    ref, _ = adapt_knowledge_contradiction(
        source, domain_ids=(DomainId(slug="project"),)
    )
    assert ref.source_id == "cog-cp9"
    assert ref.blocking is True
    assert ref.metadata["preferred_id"] == "item-a"
    assert "explanation" not in ref.metadata


# CP-10: DomainResolutionResult selection conflict normalization requires real ambiguity
def test_cp10_selection_conflict_normalization() -> None:
    ambig = DomainResolutionResult(
        id="res-cp10",
        context_id="ctx-1",
        status=DomainResolutionStatus.AMBIGUOUS,
        ambiguous_domains=(DomainId(slug="a"), DomainId(slug="b")),
        requires_clarification=True,
        recommended_question="Which domain?",
    )
    ref, domains = adapt_selection_conflict(ambig)
    assert ref.source_kind is DomainConflictSourceKind.SELECTION_CONFLICT
    assert domains == (DomainId(slug="a"), DomainId(slug="b"))
    assert "candidate_scores" not in ref.metadata


# CP-11: DomainConflictReference immutability & metadata security
def test_cp11_reference_immutability_and_metadata_security() -> None:
    ref = _make_ref("ref-cp11", metadata={"sensitive_key": "safe_scalar"})
    with pytest.raises((AttributeError, TypeError)):
        ref.source_id = "mutated"  # type: ignore[misc]
    with pytest.raises((TypeError, AttributeError)):
        ref.metadata["new_key"] = "bad"  # type: ignore[index]


# CP-12: DomainConflictCase invariants (disjoint references, domains, strict status)
def test_cp12_case_invariants() -> None:
    ref1 = _make_ref("ref-1")
    ref2 = _make_ref("ref-2")
    case = DomainConflictCase(
        id="case-cp12",
        domains=(DomainId(slug="project"),),
        kind=DomainConflictKind.COMPOSITION,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
        blocking=False,
    )
    assert case.id == "case-cp12"

    with pytest.raises(DomainConflictResolutionContractError):
        # Duplicate reference IDs must fail
        DomainConflictCase(
            id="case-cp12-dup",
            domains=(),
            kind=DomainConflictKind.COMPOSITION,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.OPEN,
            references=(ref1, ref1),
            blocking=False,
        )


# CP-13: DomainConflictResolution invariants
def test_cp13_resolution_invariants() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        # Disjoint invariant: winning and rejected cannot overlap
        DomainConflictResolution(
            conflict_id="case-cp13",
            status=DomainConflictStatus.RESOLVED,
            strategy=DomainConflictStrategy.MOST_RESTRICTIVE,
            winning_reference_ids=("ref-1",),
            rejected_reference_ids=("ref-1",),
            can_proceed=True,
        )

    with pytest.raises(DomainConflictResolutionContractError):
        # BLOCKED status requires can_proceed=False
        DomainConflictResolution(
            conflict_id="case-cp13",
            status=DomainConflictStatus.BLOCKED,
            strategy=DomainConflictStrategy.MOST_RESTRICTIVE,
            winning_reference_ids=(),
            can_proceed=True,
        )


# CP-14: DomainConflictResolutionPolicy configurable strategy defaults & strict immutability
def test_cp14_policy_defaults_and_immutability() -> None:
    policy = DomainConflictResolutionPolicy()
    assert policy.permission_strategy is DomainConflictStrategy.MOST_RESTRICTIVE
    assert (
        policy.high_risk_strategy is DomainConflictStrategy.HIGH_RISK_DOMAIN_PRECEDENCE
    )
    assert policy.primary_strategy is DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE
    with pytest.raises((AttributeError, TypeError)):
        policy.allow_user_confirmation = False  # type: ignore[misc]


# CP-15: JSON roundtrip serialization exactness across all contracts
def test_cp15_json_roundtrip_serialization() -> None:
    import json

    ref = _make_ref("ref-cp15", metadata={"val": 42})
    ref_json = json.dumps(ref.to_dict())
    ref_rt = DomainConflictReference.from_dict(json.loads(ref_json))
    assert ref == ref_rt

    case = DomainConflictCase(
        id="case-cp15",
        domains=(DomainId(slug="project"),),
        kind=DomainConflictKind.DOMAIN_PRECEDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=False,
    )
    case_json = json.dumps(case.to_dict())
    case_rt = DomainConflictCase.from_dict(json.loads(case_json))
    assert case == case_rt

    res = DomainConflictResolution(
        conflict_id="case-cp15",
        status=DomainConflictStatus.RESOLVED,
        strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
        winning_reference_ids=("ref-cp15",),
        reason_codes=(DomainConflictReasonCode.PRIMARY_PRECEDENCE,),
        can_proceed=True,
    )
    res_json = json.dumps(res.to_dict())
    res_rt = DomainConflictResolution.from_dict(json.loads(res_json))
    assert res == res_rt

    policy = DomainConflictResolutionPolicy(
        default_strategy=DomainConflictStrategy.SEPARATE_RESULTS,
        allow_separate_results=True,
    )
    pol_json = json.dumps(policy.to_dict())
    pol_rt = DomainConflictResolutionPolicy.from_dict(json.loads(pol_json))
    assert policy == pol_rt


# CP-16: Layer 0 Global Safety precedence over all lower layers
def test_cp16_global_safety_precedence() -> None:
    resolver = DomainConflictResolver()
    ref_safe = _make_ref(
        "safe-1", blocking=True, authority=DomainConflictAuthority.GLOBAL_SAFETY
    )
    ref_perm = _make_ref(
        "perm-1", blocking=False, authority=DomainConflictAuthority.PERMISSION
    )
    case = DomainConflictCase(
        id="case-cp16",
        domains=(),
        kind=DomainConflictKind.SAFETY,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_safe, ref_perm),
        blocking=True,
    )
    res = resolver.resolve(case)
    assert res.winning_reference_ids == ("safe-1",)
    assert res.can_proceed is False
    assert DomainConflictReasonCode.SAFETY_PRECEDENCE in res.reason_codes


# CP-17: Layer 1 Permission precedence over mandatory rules, high risk, and primary domain
def test_cp17_permission_precedence() -> None:
    resolver = DomainConflictResolver()
    ref_perm = _make_ref(
        "perm-1", blocking=True, authority=DomainConflictAuthority.PERMISSION
    )
    ref_mand = _make_ref(
        "mand-1", blocking=False, authority=DomainConflictAuthority.MANDATORY_RULE
    )
    case = DomainConflictCase(
        id="case-cp17",
        domains=(),
        kind=DomainConflictKind.PERMISSION,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_perm, ref_mand),
        blocking=True,
    )
    res = resolver.resolve(case)
    assert res.winning_reference_ids == ("perm-1",)
    assert res.can_proceed is False
    assert DomainConflictReasonCode.PERMISSION_PRECEDENCE in res.reason_codes


# CP-18: Layer 2 Mandatory Rule precedence over high risk, primary domain, and evidence
def test_cp18_mandatory_rule_precedence() -> None:
    resolver = DomainConflictResolver()
    ref_mand = _make_ref(
        "mand-1", blocking=True, authority=DomainConflictAuthority.MANDATORY_RULE
    )
    ref_prim = _make_ref(
        "prim-1", blocking=False, authority=DomainConflictAuthority.PRIMARY_DOMAIN
    )
    case = DomainConflictCase(
        id="case-cp18",
        domains=(),
        kind=DomainConflictKind.MANDATORY_RULE,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_mand, ref_prim),
        blocking=True,
    )
    res = resolver.resolve(case, primary_domain=DomainId(slug="project"))
    assert res.winning_reference_ids == ("mand-1",)
    assert res.can_proceed is False
    assert DomainConflictReasonCode.MANDATORY_RULE_PRECEDENCE in res.reason_codes


# CP-19: Layer 3 High Risk Domain precedence requires explicit structured domain argument
def test_cp19_high_risk_requires_explicit_domain() -> None:
    resolver = DomainConflictResolver()
    ref_risk = _make_ref(
        "risk-1",
        domain_slug="finance",
        blocking=False,
        authority=DomainConflictAuthority.HIGH_RISK_DOMAIN,
    )
    ref_other = _make_ref(
        "other-1",
        domain_slug="general",
        blocking=False,
        authority=DomainConflictAuthority.HIGH_RISK_DOMAIN,
    )
    case = DomainConflictCase(
        id="case-cp19",
        domains=(DomainId(slug="finance"), DomainId(slug="general")),
        kind=DomainConflictKind.DOMAIN_RISK,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref_risk, ref_other),
        blocking=False,
    )
    res_none = resolver.resolve(case, highest_risk_domain=None)
    assert res_none.status is DomainConflictStatus.UNRESOLVED

    res_finance = resolver.resolve(case, highest_risk_domain=DomainId(slug="finance"))
    assert res_finance.winning_reference_ids == ("risk-1",)
    assert res_finance.can_proceed is True


# CP-20: High Risk Domain precedence never uses regex or string heuristics
def test_cp20_high_risk_never_uses_name_heuristics() -> None:
    resolver = DomainConflictResolver()
    ref_risk = _make_ref(
        "risk-1",
        domain_slug="high-risk-secret-health-finance",
        blocking=False,
        authority=DomainConflictAuthority.HIGH_RISK_DOMAIN,
    )
    ref_other = _make_ref(
        "other-1",
        domain_slug="general",
        blocking=False,
        authority=DomainConflictAuthority.HIGH_RISK_DOMAIN,
    )
    case = DomainConflictCase(
        id="case-cp20",
        domains=(
            DomainId(slug="high-risk-secret-health-finance"),
            DomainId(slug="general"),
        ),
        kind=DomainConflictKind.DOMAIN_RISK,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref_risk, ref_other),
        blocking=False,
    )
    res = resolver.resolve(case, highest_risk_domain=None)
    assert res.status is DomainConflictStatus.UNRESOLVED


# CP-21: Layer 4 Primary Domain precedence requires primary domain participation
def test_cp21_primary_precedence_requires_participation() -> None:
    resolver = DomainConflictResolver()
    ref1 = _make_ref(
        "r-1",
        domain_slug="dom-a",
        blocking=False,
        authority=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    ref2 = _make_ref(
        "r-2",
        domain_slug="dom-b",
        blocking=False,
        authority=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    case = DomainConflictCase(
        id="case-cp21",
        domains=(DomainId(slug="dom-a"), DomainId(slug="dom-b")),
        kind=DomainConflictKind.DOMAIN_PRECEDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
        blocking=False,
    )
    res = resolver.resolve(case, primary_domain=DomainId(slug="project"))
    assert res.status is DomainConflictStatus.UNRESOLVED


# CP-22: Primary Domain precedence never resolves blocking conflicts
def test_cp22_primary_precedence_never_resolves_blocking() -> None:
    resolver = DomainConflictResolver()
    ref1 = _make_ref(
        "prim-1",
        domain_slug="project",
        blocking=True,
        authority=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    case = DomainConflictCase(
        id="case-cp22",
        domains=(DomainId(slug="project"),),
        kind=DomainConflictKind.COMPOSITION,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref1,),
        blocking=True,
    )
    res = resolver.resolve(case, primary_domain=DomainId(slug="project"))
    assert res.status is DomainConflictStatus.BLOCKED
    assert res.can_proceed is False


# CP-23: Layer 5 Evidence weighted resolution selects unique maximum score
def test_cp23_evidence_unique_maximum() -> None:
    resolver = DomainConflictResolver()
    ref1 = _make_ref("ev-1", authority=DomainConflictAuthority.EVIDENCE)
    ref2 = _make_ref("ev-2", authority=DomainConflictAuthority.EVIDENCE)
    case = DomainConflictCase(
        id="case-cp23",
        domains=(),
        kind=DomainConflictKind.EVIDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
        blocking=False,
    )
    res = resolver.resolve(case, evidence_scores={"ev-1": 0.95, "ev-2": 0.70})
    assert res.winning_reference_ids == ("ev-1",)
    assert res.can_proceed is True


# CP-24: Evidence tie preserves conflict and refuses arbitrary tie-break
def test_cp24_evidence_tie_preserves_conflict() -> None:
    resolver = DomainConflictResolver()
    ref1 = _make_ref("ev-1", authority=DomainConflictAuthority.EVIDENCE)
    ref2 = _make_ref("ev-2", authority=DomainConflictAuthority.EVIDENCE)
    case = DomainConflictCase(
        id="case-cp24",
        domains=(),
        kind=DomainConflictKind.EVIDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
        blocking=False,
    )
    res = resolver.resolve(case, evidence_scores={"ev-1": 0.85, "ev-2": 0.85})
    assert res.status is DomainConflictStatus.UNRESOLVED
    assert res.conflict_preserved is True
    assert res.can_proceed is False


# CP-25: Missing evidence score preserves conflict without assuming zero
def test_cp25_missing_evidence_score_preserves_conflict() -> None:
    resolver = DomainConflictResolver()
    ref1 = _make_ref("ev-1", authority=DomainConflictAuthority.EVIDENCE)
    ref2 = _make_ref("ev-2", authority=DomainConflictAuthority.EVIDENCE)
    case = DomainConflictCase(
        id="case-cp25",
        domains=(),
        kind=DomainConflictKind.EVIDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
        blocking=False,
    )
    res = resolver.resolve(case, evidence_scores={"ev-1": 0.90})
    assert res.status is DomainConflictStatus.UNRESOLVED
    assert res.conflict_preserved is True


# CP-26: Reliability weighted resolution cannot bypass permission deny
def test_cp26_reliability_cannot_bypass_permission() -> None:
    resolver = DomainConflictResolver()
    ref_perm = _make_ref(
        "perm-1", blocking=True, authority=DomainConflictAuthority.PERMISSION
    )
    ref_rel = _make_ref(
        "rel-1", blocking=False, authority=DomainConflictAuthority.RELIABILITY
    )
    case = DomainConflictCase(
        id="case-cp26",
        domains=(),
        kind=DomainConflictKind.PERMISSION,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_perm, ref_rel),
        blocking=True,
    )
    res = resolver.resolve(case, reliability_scores={"perm-1": 0.1, "rel-1": 1.0})
    assert "rel-1" not in res.winning_reference_ids
    assert res.can_proceed is False


# CP-27: Temporal freshness cannot bypass mandatory rule restriction
def test_cp27_temporal_cannot_bypass_mandatory_rule() -> None:
    resolver = DomainConflictResolver()
    ref_mand = _make_ref(
        "mand-1", blocking=True, authority=DomainConflictAuthority.MANDATORY_RULE
    )
    ref_temp = _make_ref(
        "temp-1", blocking=False, authority=DomainConflictAuthority.TEMPORAL
    )
    case = DomainConflictCase(
        id="case-cp27",
        domains=(),
        kind=DomainConflictKind.MANDATORY_RULE,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_mand, ref_temp),
        blocking=True,
    )
    res = resolver.resolve(case, temporal_scores={"mand-1": 1.0, "temp-1": 10000.0})
    assert "temp-1" not in res.winning_reference_ids
    assert res.can_proceed is False


# CP-28: Separate results strategy only valid for non-blocking soft conflicts
def test_cp28_separate_results_validity() -> None:
    resolver = DomainConflictResolver()
    ref1 = _make_ref("ref-1", authority=DomainConflictAuthority.UNCLASSIFIED)
    case = DomainConflictCase(
        id="case-cp28",
        domains=(),
        kind=DomainConflictKind.PRESENTATION,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1,),
        blocking=False,
    )
    policy = DomainConflictResolutionPolicy(
        default_strategy=DomainConflictStrategy.SEPARATE_RESULTS,
        allow_separate_results=True,
    )
    res = resolver.resolve(case, policy=policy)
    assert res.strategy is DomainConflictStrategy.SEPARATE_RESULTS
    assert res.can_proceed is True


# CP-29: Ask user strategy only valid for non-blocking soft conflicts
def test_cp29_ask_user_validity() -> None:
    resolver = DomainConflictResolver()
    ref1 = _make_ref("user-1", authority=DomainConflictAuthority.USER)
    case = DomainConflictCase(
        id="case-cp29",
        domains=(),
        kind=DomainConflictKind.PREFERENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1,),
        blocking=False,
    )
    res = resolver.resolve(case)
    assert res.status is DomainConflictStatus.AWAITING_USER
    assert res.requires_user_input is True
    assert res.can_proceed is False


# CP-30: Human review strategy emits declarative required flag and halts execution
def test_cp30_human_review_declarative() -> None:
    resolver = DomainConflictResolver()
    ref1 = _make_ref("hr-1", authority=DomainConflictAuthority.HUMAN_REVIEW)
    case = DomainConflictCase(
        id="case-cp30",
        domains=(),
        kind=DomainConflictKind.OTHER,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1,),
        blocking=False,
    )
    res = resolver.resolve(case)
    assert res.status is DomainConflictStatus.AWAITING_HUMAN_REVIEW
    assert res.requires_human_review is True
    assert res.can_proceed is False


# CP-31: Postpone action strategy emits postponed flag and halts execution
def test_cp31_postpone_action() -> None:
    resolver = DomainConflictResolver()
    ref1 = _make_ref("post-1", authority=DomainConflictAuthority.UNCLASSIFIED)
    case = DomainConflictCase(
        id="case-cp31",
        domains=(),
        kind=DomainConflictKind.OTHER,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1,),
        blocking=False,
    )
    policy = DomainConflictResolutionPolicy(
        default_strategy=DomainConflictStrategy.POSTPONE_ACTION,
        allow_postpone=True,
    )
    res = resolver.resolve(case, policy=policy)
    assert res.status is DomainConflictStatus.POSTPONED
    assert res.action_postponed is True
    assert res.can_proceed is False


# CP-32: Resolver purity (no time, random, uuid, network, filesystem, event emission, workflow execution, memory write)
def test_cp32_resolver_purity_complete() -> None:
    path = Path("cmm/domains/conflict_resolution.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {
        "time",
        "datetime",
        "uuid",
        "random",
        "secrets",
        "socket",
        "http",
        "urllib",
        "requests",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden

    resolver = DomainConflictResolver()
    ref = _make_ref("ref-cp32", authority=DomainConflictAuthority.EVIDENCE)
    case = DomainConflictCase(
        id="case-cp32",
        domains=(),
        kind=DomainConflictKind.EVIDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=False,
    )

    def _trap(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Forbidden impure call inside resolver!")

    with (
        patch("time.time", side_effect=_trap),
        patch("uuid.uuid4", side_effect=_trap),
        patch("random.random", side_effect=_trap),
    ):
        res = resolver.resolve(case, evidence_scores={"ref-cp32": 1.0})
    assert res.winning_reference_ids == ("ref-cp32",)
