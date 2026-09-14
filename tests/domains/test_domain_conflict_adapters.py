"""Phase 10.32 — Domain Conflict Adapters tests."""

from __future__ import annotations

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
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictSeverity,
    DomainConflictSourceKind,
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


def test_permission_adapter_is_fail_closed_and_does_not_copy_source_lists() -> None:
    source = DomainPermissionConflict(
        action=PermissionCapability.DOMAIN_CROSS_ACCESS,
        allowing_sources=("primary:project:1.0.0",),
        denying_sources=("supporting:general:1.0.0",),
        resolution=PermissionOutcome.DENY,
        reason_code="allow_deny_conflict",
    )

    ref, domains = adapt_permission_conflict(
        source,
        source_id="perm-1",
        domain_id=DomainId(slug="project"),
    )

    assert ref.source_kind is DomainConflictSourceKind.PERMISSION_CONFLICT
    assert ref.authority_kind is DomainConflictAuthority.PERMISSION
    assert ref.blocking is True
    assert ref.severity is DomainConflictSeverity.BLOCKING
    assert domains == (DomainId(slug="project"),)
    assert "allowing_sources" not in ref.metadata
    assert "denying_sources" not in ref.metadata
    assert ref.metadata["action"] == "domain.cross_access"
    assert ref.metadata["resolution"] == "deny"


def test_composition_adapter_preserves_all_domain_participation() -> None:
    conflict = DomainCompositionConflict(
        code="TEST_CONFLICT",
        category="declared_conflicts",
        domains=(DomainId(slug="project"), DomainId(slug="general")),
        severity="blocking",
        message="incompatible",
        blocking=True,
    )

    ref, domains = adapt_composition_conflict(
        conflict,
        source_id="composition-1",
    )

    assert ref.source_kind is DomainConflictSourceKind.COMPOSITION_CONFLICT
    assert ref.blocking is True
    assert ref.severity is DomainConflictSeverity.BLOCKING
    assert domains == (
        DomainId(slug="project"),
        DomainId(slug="general"),
    )
    assert ref.metadata["code"] == "TEST_CONFLICT"
    assert ref.metadata["category"] == "declared_conflicts"
    assert "message" not in ref.metadata


def test_declared_conflict_adapter() -> None:
    conflict = DomainConflict(
        domain_id=DomainId(slug="legacy"),
        reason="incompatible API",
        severity="blocking",
    )
    ref, domains = adapt_declared_domain_conflict(
        conflict,
        source_id="decl-1",
        owner_domain_id=DomainId(slug="project"),
    )
    assert ref.source_kind is DomainConflictSourceKind.DECLARED_DOMAIN_CONFLICT
    assert ref.blocking is True
    assert ref.severity is DomainConflictSeverity.BLOCKING
    assert domains == (DomainId(slug="project"), DomainId(slug="legacy"))
    assert "reason" not in ref.metadata
    assert ref.metadata["declared_severity"] == "blocking"


def test_profile_conflict_adapter_preserves_blocking_and_metadata() -> None:
    conflict = DomainProfileConflict(
        code="CONF_OVERLAP",
        field="settings.theme",
        severity=DomainProfileConflictSeverity.BLOCKING,
        sources=(
            DomainProfileSource.PRIMARY_DOMAIN,
            DomainProfileSource.SUPPORTING_DOMAIN,
        ),
        description="Conflicting theme setting",
        blocking=True,
    )
    ref, domains = adapt_profile_conflict(
        conflict,
        source_id="prof-1",
        domain_id=DomainId(slug="project"),
    )
    assert ref.source_kind is DomainConflictSourceKind.PROFILE_CONFLICT
    assert ref.blocking is True
    assert ref.severity is DomainConflictSeverity.BLOCKING
    assert domains == (DomainId(slug="project"),)
    assert ref.metadata["code"] == "CONF_OVERLAP"
    assert ref.metadata["field"] == "settings.theme"
    assert "description" not in ref.metadata


def test_rule_selection_conflict_adapter() -> None:
    conflict = DomainRuleSelectionConflict(
        code="RULE_CONFLICT",
        rule_id="security.require_auth",
        message="Conflicting rule selection",
        severity=DomainRuleConflictSeverity.BLOCKING,
    )
    ref, domains = adapt_rule_selection_conflict(
        conflict,
        source_id="rule-1",
        domain_id=DomainId(slug="project"),
        authority_kind=DomainConflictAuthority.MANDATORY_RULE,
    )
    assert ref.source_kind is DomainConflictSourceKind.RULE_SELECTION_CONFLICT
    assert ref.authority_kind is DomainConflictAuthority.MANDATORY_RULE
    assert ref.blocking is True
    assert ref.severity is DomainConflictSeverity.BLOCKING
    assert domains == (DomainId(slug="project"),)
    assert ref.metadata["code"] == "RULE_CONFLICT"
    assert ref.metadata["rule_id"] == "security.require_auth"
    assert "message" not in ref.metadata


def test_presentation_conflict_adapter() -> None:
    conflict = DomainPresentationConflict(
        code=DomainPresentationConflictCode.TERMINOLOGY_INCOMPATIBLE,
        related_ids=("term-1", "term-2"),
    )
    ref, domains = adapt_presentation_conflict(
        conflict,
        source_id="pres-1",
        domain_id=DomainId(slug="project"),
    )
    assert ref.source_kind is DomainConflictSourceKind.PRESENTATION_CONFLICT
    assert ref.blocking is False
    assert ref.severity is DomainConflictSeverity.MATERIAL
    assert domains == (DomainId(slug="project"),)
    assert ref.metadata["code"] == "TERMINOLOGY_INCOMPATIBLE"
    assert tuple(ref.metadata["related_ids"]) == ("term-1", "term-2")


def test_cross_domain_contradiction_adapter() -> None:
    contra = CrossDomainContradiction(
        id="cdc-1",
        domains=(DomainId(slug="domain-a"), DomainId(slug="domain-b")),
        subject="data_retention",
        statements=("store forever", "purge after 30 days"),
        severity=CrossDomainSeverity.HIGH,
        provenance=("prov-1",),
        resolved=False,
        requires_review=True,
    )
    ref, domains = adapt_cross_domain_contradiction(contra)
    assert ref.source_kind is DomainConflictSourceKind.CROSS_DOMAIN_CONTRADICTION
    assert ref.source_id == "cdc-1"
    assert ref.blocking is True
    assert ref.severity is DomainConflictSeverity.BLOCKING
    assert domains == (DomainId(slug="domain-a"), DomainId(slug="domain-b"))
    assert ref.metadata["resolved_upstream"] is False
    assert ref.metadata["requires_review"] is True
    assert "statements" not in ref.metadata
    assert "subject" not in ref.metadata


def test_knowledge_contradiction_adapter() -> None:
    contra = Contradiction(
        id="cog-contra-1",
        item_a_id="item-1",
        item_b_id="item-2",
        severity=ContradictionSeverity.HIGH,
        status=ContradictionStatus.UNRESOLVED,
        preferred_id="item-1",
        preference_reason="more recent evidence",
    )
    ref, domains = adapt_knowledge_contradiction(
        contra,
        domain_ids=(DomainId(slug="project"),),
    )
    assert ref.source_kind is DomainConflictSourceKind.KNOWLEDGE_CONTRADICTION
    assert ref.source_id == "cog-contra-1"
    assert ref.blocking is True
    assert ref.severity is DomainConflictSeverity.BLOCKING
    assert domains == (DomainId(slug="project"),)
    assert ref.metadata["status"] == "unresolved"
    assert ref.metadata["preferred_id"] == "item-1"
    assert "explanation" not in ref.metadata
    assert "preference_reason" not in ref.metadata


def test_selection_adapter_only_accepts_real_ambiguity() -> None:
    ambiguous = DomainResolutionResult(
        id="res-amb-1",
        context_id="ctx-1",
        status=DomainResolutionStatus.AMBIGUOUS,
        ambiguous_domains=(DomainId(slug="project"), DomainId(slug="general")),
        requires_clarification=True,
        recommended_question="Which domain should take precedence?",
    )
    ref, domains = adapt_selection_conflict(ambiguous)
    assert ref.source_kind is DomainConflictSourceKind.SELECTION_CONFLICT
    assert ref.source_id == "res-amb-1"
    assert ref.blocking is False
    assert ref.severity is DomainConflictSeverity.MATERIAL
    assert domains == (DomainId(slug="project"), DomainId(slug="general"))
    assert "candidate_scores" not in ref.metadata

    resolved = DomainResolutionResult(
        id="res-ok-1",
        context_id="ctx-1",
        status=DomainResolutionStatus.RESOLVED,
        primary_domain=DomainId(slug="project"),
    )
    with pytest.raises(DomainConflictResolutionContractError):
        adapt_selection_conflict(resolved)


def test_adapters_do_not_mutate_sources() -> None:
    perm = DomainPermissionConflict(
        action=PermissionCapability.DOMAIN_CROSS_ACCESS,
        allowing_sources=("primary:project:1.0.0",),
        denying_sources=("supporting:general:1.0.0",),
        resolution=PermissionOutcome.DENY,
        reason_code="allow_deny_conflict",
    )
    perm_dict_before = perm.to_dict()
    adapt_permission_conflict(perm, source_id="p1")
    assert perm.to_dict() == perm_dict_before

    comp = DomainCompositionConflict(
        code="TEST",
        category="category",
        domains=(DomainId(slug="project"),),
        severity="blocking",
        message="msg",
        blocking=True,
    )
    comp_dict_before = comp.to_dict()
    adapt_composition_conflict(comp, source_id="c1")
    assert comp.to_dict() == comp_dict_before

    decl = DomainConflict(
        domain_id=DomainId(slug="legacy"),
        reason="incompatible",
        severity="blocking",
    )
    decl_dict_before = decl.to_dict()
    adapt_declared_domain_conflict(decl, source_id="d1")
    assert decl.to_dict() == decl_dict_before


def test_adapters_reject_invalid_source_types() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        adapt_permission_conflict("not a permission conflict", source_id="p1")  # type: ignore[arg-type]

    with pytest.raises(DomainConflictResolutionContractError):
        adapt_composition_conflict("not a composition conflict", source_id="c1")  # type: ignore[arg-type]

    with pytest.raises(DomainConflictResolutionContractError):
        adapt_declared_domain_conflict("not a declared conflict", source_id="d1")  # type: ignore[arg-type]

    with pytest.raises(DomainConflictResolutionContractError):
        adapt_profile_conflict("not a profile conflict", source_id="pr1")  # type: ignore[arg-type]

    with pytest.raises(DomainConflictResolutionContractError):
        adapt_rule_selection_conflict("not a rule conflict", source_id="r1")  # type: ignore[arg-type]

    with pytest.raises(DomainConflictResolutionContractError):
        adapt_presentation_conflict("not a presentation conflict", source_id="ps1")  # type: ignore[arg-type]

    with pytest.raises(DomainConflictResolutionContractError):
        adapt_cross_domain_contradiction("not a cross domain contradiction")  # type: ignore[arg-type]

    with pytest.raises(DomainConflictResolutionContractError):
        adapt_knowledge_contradiction("not a knowledge contradiction")  # type: ignore[arg-type]

    with pytest.raises(DomainConflictResolutionContractError):
        adapt_selection_conflict("not a resolution result")  # type: ignore[arg-type]
