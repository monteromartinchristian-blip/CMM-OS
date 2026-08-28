"""Phase 10.32 — Domain Conflict Resolution Adversarial and Purity tests."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

from cmm.domains.conflict_resolution import DomainConflictResolver
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReasonCode,
    DomainConflictReference,
    DomainConflictResolutionPolicy,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
    DomainConflictStrategy,
)
from cmm.domains.identifiers import DomainId


def _ref(
    source_id: str,
    *,
    domain_slug: str | None = None,
    blocking: bool = False,
    authority: DomainConflictAuthority = DomainConflictAuthority.UNCLASSIFIED,
) -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id=source_id,
        domain_id=DomainId(slug=domain_slug) if domain_slug else None,
        blocking=blocking,
        severity=(
            DomainConflictSeverity.BLOCKING
            if blocking
            else DomainConflictSeverity.MATERIAL
        ),
        authority_kind=authority,
    )


def test_resolver_has_no_forbidden_imports() -> None:
    path = Path("cmm/domains/conflict_resolution.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))

    forbidden_modules = {
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
    forbidden_prefixes = (
        "cmm.agent_runtime.approval_service",
        "cmm.agent_runtime.workflow",
        "cmm.cognitive.store",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                assert root_pkg not in forbidden_modules, (
                    f"Forbidden import: {alias.name}"
                )
                for prefix in forbidden_prefixes:
                    assert not alias.name.startswith(prefix), (
                        f"Forbidden import prefix: {alias.name}"
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            root_pkg = node.module.split(".")[0]
            assert root_pkg not in forbidden_modules, (
                f"Forbidden from-import: {node.module}"
            )
            for prefix in forbidden_prefixes:
                assert not node.module.startswith(prefix), (
                    f"Forbidden from-import prefix: {node.module}"
                )


def test_resolver_is_pure_and_does_not_call_time_or_random() -> None:
    resolver = DomainConflictResolver()
    ref1 = _ref("ref-1", authority=DomainConflictAuthority.EVIDENCE)
    ref2 = _ref("ref-2", authority=DomainConflictAuthority.EVIDENCE)
    case = DomainConflictCase(
        id="case-purity",
        domains=(),
        kind=DomainConflictKind.EVIDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
        blocking=False,
    )

    def _trap(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Forbidden impure call inside resolver!")

    with (
        patch("time.time", side_effect=_trap),
        patch("uuid.uuid4", side_effect=_trap),
        patch("random.random", side_effect=_trap),
    ):
        res1 = resolver.resolve(case, evidence_scores={"ref-1": 0.8, "ref-2": 0.2})
        res2 = resolver.resolve(case, evidence_scores={"ref-1": 0.8, "ref-2": 0.2})

    assert res1 == res2
    assert res1.to_dict() == res2.to_dict()


def test_adversarial_user_preference_cannot_override_global_safety() -> None:
    resolver = DomainConflictResolver()
    ref_safety = _ref(
        "safety-1", blocking=True, authority=DomainConflictAuthority.GLOBAL_SAFETY
    )
    ref_user = _ref(
        "user-pref-1", blocking=False, authority=DomainConflictAuthority.USER
    )

    case = DomainConflictCase(
        id="case-adv-safety",
        domains=(),
        kind=DomainConflictKind.SAFETY,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_safety, ref_user),
        blocking=True,
    )

    res = resolver.resolve(case)
    assert res.winning_reference_ids == ("safety-1",)
    assert res.can_proceed is False
    assert res.requires_user_input is False
    assert DomainConflictReasonCode.SAFETY_PRECEDENCE in res.reason_codes


def test_adversarial_temporal_freshness_cannot_convert_permission_deny() -> None:
    resolver = DomainConflictResolver()
    ref_perm = _ref(
        "perm-deny", blocking=True, authority=DomainConflictAuthority.PERMISSION
    )
    ref_temp = _ref(
        "temp-fresh", blocking=False, authority=DomainConflictAuthority.TEMPORAL
    )

    case = DomainConflictCase(
        id="case-adv-perm-temp",
        domains=(),
        kind=DomainConflictKind.PERMISSION,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_perm, ref_temp),
        blocking=True,
    )

    res = resolver.resolve(
        case, temporal_scores={"perm-deny": 1.0, "temp-fresh": 9999.0}
    )
    assert "temp-fresh" not in res.winning_reference_ids
    assert res.can_proceed is False
    assert DomainConflictReasonCode.PERMISSION_PRECEDENCE in res.reason_codes


def test_adversarial_primary_domain_cannot_defeat_mandatory_rule() -> None:
    resolver = DomainConflictResolver()
    ref_mandatory = _ref(
        "mand-1",
        domain_slug="compliance",
        blocking=True,
        authority=DomainConflictAuthority.MANDATORY_RULE,
    )
    ref_primary = _ref(
        "prim-1",
        domain_slug="project",
        blocking=False,
        authority=DomainConflictAuthority.PRIMARY_DOMAIN,
    )

    case = DomainConflictCase(
        id="case-adv-mand-prim",
        domains=(DomainId(slug="compliance"), DomainId(slug="project")),
        kind=DomainConflictKind.MANDATORY_RULE,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_mandatory, ref_primary),
        blocking=True,
    )

    res = resolver.resolve(case, primary_domain=DomainId(slug="project"))
    assert "prim-1" not in res.winning_reference_ids
    assert res.can_proceed is False
    assert DomainConflictReasonCode.MANDATORY_RULE_PRECEDENCE in res.reason_codes


def test_adversarial_separate_results_forbidden_for_safety_or_permission() -> None:
    resolver = DomainConflictResolver()
    ref_perm = _ref(
        "perm-1", blocking=True, authority=DomainConflictAuthority.PERMISSION
    )
    case = DomainConflictCase(
        id="case-adv-sep-perm",
        domains=(),
        kind=DomainConflictKind.PERMISSION,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_perm,),
        blocking=True,
    )
    policy = DomainConflictResolutionPolicy(
        permission_strategy=DomainConflictStrategy.MOST_RESTRICTIVE,
        allow_separate_results=True,
    )
    res = resolver.resolve(case, policy=policy)
    assert res.strategy is not DomainConflictStrategy.SEPARATE_RESULTS
    assert res.can_proceed is False


def test_adversarial_ask_user_forbidden_for_safety_or_permission() -> None:
    resolver = DomainConflictResolver()
    ref_safety = _ref(
        "safety-1", blocking=True, authority=DomainConflictAuthority.GLOBAL_SAFETY
    )
    case = DomainConflictCase(
        id="case-adv-ask-safety",
        domains=(),
        kind=DomainConflictKind.SAFETY,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_safety,),
        blocking=True,
    )
    res = resolver.resolve(case)
    assert res.strategy is not DomainConflictStrategy.ASK_USER
    assert res.requires_user_input is False
    assert res.can_proceed is False


# ── Connected Subsystem Integration Tests ─────────────────────────────────────

from cmm.cognitive.enums import ContradictionSeverity, ContradictionStatus
from cmm.cognitive.knowledge import Contradiction
from cmm.domains.composition_contracts import DomainCompositionConflict
from cmm.domains.conflict_adapters import (
    adapt_composition_conflict,
    adapt_cross_domain_contradiction,
    adapt_knowledge_contradiction,
    adapt_permission_conflict,
    adapt_profile_conflict,
    adapt_rule_selection_conflict,
    adapt_selection_conflict,
)
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
from cmm.domains.permission_contracts import (
    DomainPermissionConflict,
    PermissionCapability,
    PermissionOutcome,
)
from cmm.domains.profile_contracts import DomainProfileConflict
from cmm.domains.resolver_contracts import DomainResolutionResult
from cmm.domains.rule_contracts import DomainRuleSelectionConflict


def test_connected_composition_conflict_to_universal_resolution() -> None:
    comp_conflict = DomainCompositionConflict(
        code="DECLARED_INCOMPATIBILITY",
        category="declared_conflicts",
        domains=(DomainId(slug="project"), DomainId(slug="legacy")),
        severity="blocking",
        message="project is incompatible with legacy",
        blocking=True,
    )
    ref, domains = adapt_composition_conflict(comp_conflict, source_id="comp-1")
    case = DomainConflictCase(
        id="case-connected-comp",
        domains=domains,
        kind=DomainConflictKind.COMPOSITION,
        severity=ref.severity or DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=ref.blocking,
    )

    resolver = DomainConflictResolver()
    res = resolver.resolve(case, primary_domain=DomainId(slug="project"))
    assert res.status is DomainConflictStatus.BLOCKED
    assert res.can_proceed is False
    assert res.conflict_preserved is True
    assert res.preserved_reference_ids == ("comp-1",)


def test_connected_permission_conflict_fails_closed_against_all_lower_layers() -> None:
    perm_conflict = DomainPermissionConflict(
        action=PermissionCapability.DOMAIN_CROSS_ACCESS,
        allowing_sources=("primary:project:1.0.0",),
        denying_sources=("supporting:general:1.0.0",),
        resolution=PermissionOutcome.DENY,
        reason_code="cross_domain_denied",
    )
    ref, domains = adapt_permission_conflict(
        perm_conflict, source_id="perm-1", domain_id=DomainId(slug="project")
    )
    case = DomainConflictCase(
        id="case-connected-perm",
        domains=domains,
        kind=DomainConflictKind.PERMISSION,
        severity=ref.severity or DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=ref.blocking,
    )

    resolver = DomainConflictResolver()
    res = resolver.resolve(
        case,
        primary_domain=DomainId(slug="project"),
        evidence_scores={"perm-1": 0.99},
        reliability_scores={"perm-1": 1.0},
        temporal_scores={"perm-1": 1000.0},
    )
    assert res.can_proceed is False
    assert DomainConflictReasonCode.PERMISSION_PRECEDENCE in res.reason_codes


def test_connected_profile_and_rule_selection_conflicts() -> None:
    prof_conflict = DomainProfileConflict(
        code="OVERLAY_MISMATCH",
        field="inference.depth",
        severity=DomainProfileConflictSeverity.BLOCKING,
        sources=(DomainProfileSource.PRIMARY_DOMAIN, DomainProfileSource.GLOBAL_POLICY),
        description="Overlay mismatch on inference depth",
        blocking=True,
    )
    ref_prof, _ = adapt_profile_conflict(
        prof_conflict, source_id="prof-1", domain_id=DomainId(slug="project")
    )

    rule_conflict = DomainRuleSelectionConflict(
        code="MANDATORY_RULE_VIOLATION",
        rule_id="security.audit_enforce",
        message="Mandatory rule missing required permissions",
        severity=DomainRuleConflictSeverity.BLOCKING,
    )
    ref_rule, _ = adapt_rule_selection_conflict(
        rule_conflict,
        source_id="rule-1",
        domain_id=DomainId(slug="project"),
        authority_kind=DomainConflictAuthority.MANDATORY_RULE,
    )

    case = DomainConflictCase(
        id="case-prof-rule",
        domains=(DomainId(slug="project"),),
        kind=DomainConflictKind.MANDATORY_RULE,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_prof, ref_rule),
        blocking=True,
    )

    resolver = DomainConflictResolver()
    res = resolver.resolve(case, primary_domain=DomainId(slug="project"))
    assert res.can_proceed is False
    assert res.winning_reference_ids == ("rule-1",)
    assert "prof-1" in res.rejected_reference_ids


def test_connected_cross_domain_contradiction_metadata_hygiene() -> None:
    c_contra = CrossDomainContradiction(
        id="cdc-99",
        domains=(DomainId(slug="alpha"), DomainId(slug="beta")),
        subject="confidential_claim",
        statements=("secret A", "secret B"),
        severity=CrossDomainSeverity.HIGH,
        provenance=("prov-source-1",),
        resolved=False,
        requires_review=True,
    )
    ref, domains = adapt_cross_domain_contradiction(c_contra)
    assert domains == (DomainId(slug="alpha"), DomainId(slug="beta"))
    assert ref.source_id == "cdc-99"
    assert "statements" not in ref.metadata
    assert "subject" not in ref.metadata
    assert "secret" not in str(ref.metadata)


def test_connected_cognitive_contradiction_truth_unaltered() -> None:
    cog_contra = Contradiction(
        id="cog-88",
        item_a_id="k-1",
        item_b_id="k-2",
        severity=ContradictionSeverity.HIGH,
        status=ContradictionStatus.UNRESOLVED,
        preferred_id="k-1",
        preference_reason="upstream reasoning decided",
    )
    ref, _ = adapt_knowledge_contradiction(
        cog_contra, domain_ids=(DomainId(slug="project"),)
    )
    assert ref.source_id == "cog-88"
    assert ref.metadata["preferred_id"] == "k-1"
    assert "preference_reason" not in ref.metadata


def test_connected_selection_ambiguity_no_forbidden_score_tiebreak() -> None:
    ambig_result = DomainResolutionResult(
        id="res-amb-99",
        context_id="ctx-1",
        status=DomainResolutionStatus.AMBIGUOUS,
        ambiguous_domains=(DomainId(slug="domain-a"), DomainId(slug="domain-b")),
        requires_clarification=True,
        recommended_question="Which domain?",
    )
    ref, domains = adapt_selection_conflict(ambig_result)
    assert "candidate_scores" not in ref.metadata

    case = DomainConflictCase(
        id="case-selection-amb",
        domains=domains,
        kind=DomainConflictKind.SELECTION,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=False,
    )
    resolver = DomainConflictResolver()
    res = resolver.resolve(case)
    # Selection conflict without higher authority either preserves or asks user
    assert res.status in (
        DomainConflictStatus.UNRESOLVED,
        DomainConflictStatus.AWAITING_USER,
    )
    assert res.winning_reference_ids == ()
