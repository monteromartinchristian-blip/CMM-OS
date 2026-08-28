"""Phase 10.32 — Domain Conflict Adapters.

Pure, deterministic normalization adapters mapping upstream conflict contracts
to DomainConflictReference without modifying source objects or copying
sensitive payloads.
"""

from __future__ import annotations

from cmm.cognitive.enums import ContradictionSeverity, ContradictionStatus
from cmm.cognitive.knowledge import Contradiction
from cmm.domains.composition_contracts import (
    DomainCompositionConflict,
    DomainCompositionPolicy,
)
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictReference,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    _validate_non_empty_str,
)
from cmm.domains.contracts import DomainConflict
from cmm.domains.cross_domain_contracts import (
    CrossDomainContradiction,
    CrossDomainSeverity,
)
from cmm.domains.enums import (
    DomainProfileConflictSeverity,
    DomainResolutionStatus,
    DomainRuleConflictSeverity,
)
from cmm.domains.errors import DomainConflictResolutionContractError
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_contracts import DomainPermissionConflict
from cmm.domains.presentation_contracts import DomainPresentationConflict
from cmm.domains.profile_contracts import DomainProfileConflict
from cmm.domains.resolver_contracts import DomainResolutionResult
from cmm.domains.rule_contracts import DomainRuleSelectionConflict


def adapt_declared_domain_conflict(
    conflict: DomainConflict,
    *,
    source_id: str,
    owner_domain_id: DomainId | None = None,
    authority_kind: DomainConflictAuthority | None = None,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]:
    """Normalize a declared DomainConflict."""
    if not isinstance(conflict, DomainConflict):
        raise DomainConflictResolutionContractError(
            f"Expected DomainConflict, got {type(conflict).__name__}",
            field="conflict",
        )
    sid = _validate_non_empty_str(source_id, "source_id")
    declared_severity = conflict.severity.strip().lower()
    blocking_severities = frozenset(
        value.strip().lower() for value in DomainCompositionPolicy().blocking_severities
    )
    is_blocking = declared_severity in blocking_severities
    if is_blocking:
        sev = DomainConflictSeverity.BLOCKING
    elif declared_severity in ("advisory", "warning"):
        sev = DomainConflictSeverity.ADVISORY
    else:
        sev = DomainConflictSeverity.MATERIAL

    domains = (
        (owner_domain_id, conflict.domain_id)
        if owner_domain_id and owner_domain_id != conflict.domain_id
        else (conflict.domain_id,)
    )

    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DECLARED_DOMAIN_CONFLICT,
        source_id=sid,
        domain_id=conflict.domain_id,
        blocking=is_blocking,
        severity=sev,
        authority_kind=authority_kind,
        metadata={
            "declared_severity": conflict.severity,
        },
    )
    return ref, domains


def adapt_composition_conflict(
    conflict: DomainCompositionConflict,
    *,
    source_id: str,
    authority_kind: DomainConflictAuthority | None = None,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]:
    """Normalize a DomainCompositionConflict."""
    if not isinstance(conflict, DomainCompositionConflict):
        raise DomainConflictResolutionContractError(
            f"Expected DomainCompositionConflict, got {type(conflict).__name__}",
            field="conflict",
        )
    sid = _validate_non_empty_str(source_id, "source_id")
    is_blocking = bool(conflict.blocking)
    if is_blocking:
        sev = DomainConflictSeverity.BLOCKING
    elif conflict.severity.strip().lower() in ("advisory", "warning"):
        sev = DomainConflictSeverity.ADVISORY
    else:
        sev = DomainConflictSeverity.MATERIAL

    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.COMPOSITION_CONFLICT,
        source_id=sid,
        domain_id=conflict.domains[0] if len(conflict.domains) == 1 else None,
        blocking=is_blocking,
        severity=sev,
        authority_kind=authority_kind,
        metadata={
            "code": conflict.code,
            "category": conflict.category,
            "resolved_upstream": conflict.resolved,
        },
    )
    return ref, conflict.domains


def adapt_permission_conflict(
    conflict: DomainPermissionConflict,
    *,
    source_id: str,
    domain_id: DomainId | None = None,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]:
    """Normalize a DomainPermissionConflict fail-closed without copying source lists."""
    if not isinstance(conflict, DomainPermissionConflict):
        raise DomainConflictResolutionContractError(
            f"Expected DomainPermissionConflict, got {type(conflict).__name__}",
            field="conflict",
        )
    sid = _validate_non_empty_str(source_id, "source_id")
    domains = (domain_id,) if domain_id is not None else ()

    action_val = (
        conflict.action.value
        if hasattr(conflict.action, "value")
        else str(conflict.action)
    )
    res_val = (
        conflict.resolution.value
        if hasattr(conflict.resolution, "value")
        else str(conflict.resolution)
    )

    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.PERMISSION_CONFLICT,
        source_id=sid,
        domain_id=domain_id,
        blocking=True,
        severity=DomainConflictSeverity.BLOCKING,
        authority_kind=DomainConflictAuthority.PERMISSION,
        metadata={
            "action": action_val,
            "resolution": res_val,
            "reason_code": conflict.reason_code,
        },
    )
    return ref, domains


def adapt_profile_conflict(
    conflict: DomainProfileConflict,
    *,
    source_id: str,
    domain_id: DomainId | None = None,
    authority_kind: DomainConflictAuthority | None = None,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]:
    """Normalize a DomainProfileConflict."""
    if not isinstance(conflict, DomainProfileConflict):
        raise DomainConflictResolutionContractError(
            f"Expected DomainProfileConflict, got {type(conflict).__name__}",
            field="conflict",
        )
    sid = _validate_non_empty_str(source_id, "source_id")
    is_blocking = conflict.blocking or (
        conflict.severity == DomainProfileConflictSeverity.BLOCKING
    )
    if is_blocking:
        sev = DomainConflictSeverity.BLOCKING
    elif conflict.severity == DomainProfileConflictSeverity.WARNING:
        sev = DomainConflictSeverity.ADVISORY
    else:
        sev = DomainConflictSeverity.MATERIAL

    domains = (domain_id,) if domain_id is not None else ()

    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.PROFILE_CONFLICT,
        source_id=sid,
        domain_id=domain_id,
        blocking=is_blocking,
        severity=sev,
        authority_kind=authority_kind,
        metadata={
            "code": conflict.code,
            "field": conflict.field,
        },
    )
    return ref, domains


def adapt_rule_selection_conflict(
    conflict: DomainRuleSelectionConflict,
    *,
    source_id: str,
    domain_id: DomainId | None = None,
    authority_kind: DomainConflictAuthority | None = None,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]:
    """Normalize a DomainRuleSelectionConflict."""
    if not isinstance(conflict, DomainRuleSelectionConflict):
        raise DomainConflictResolutionContractError(
            f"Expected DomainRuleSelectionConflict, got {type(conflict).__name__}",
            field="conflict",
        )
    sid = _validate_non_empty_str(source_id, "source_id")
    is_blocking = conflict.blocking or (
        conflict.severity == DomainRuleConflictSeverity.BLOCKING
    )
    if is_blocking:
        sev = DomainConflictSeverity.BLOCKING
    elif conflict.severity == DomainRuleConflictSeverity.WARNING:
        sev = DomainConflictSeverity.ADVISORY
    else:
        sev = DomainConflictSeverity.MATERIAL

    domains = (domain_id,) if domain_id is not None else ()

    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.RULE_SELECTION_CONFLICT,
        source_id=sid,
        domain_id=domain_id,
        blocking=is_blocking,
        severity=sev,
        authority_kind=authority_kind,
        metadata={
            "code": conflict.code,
            "rule_id": conflict.rule_id,
        },
    )
    return ref, domains


def adapt_presentation_conflict(
    conflict: DomainPresentationConflict,
    *,
    source_id: str,
    domain_id: DomainId | None = None,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]:
    """Normalize a DomainPresentationConflict."""
    if not isinstance(conflict, DomainPresentationConflict):
        raise DomainConflictResolutionContractError(
            f"Expected DomainPresentationConflict, got {type(conflict).__name__}",
            field="conflict",
        )
    sid = _validate_non_empty_str(source_id, "source_id")
    domains = (domain_id,) if domain_id is not None else ()

    code_val = (
        conflict.code.value if hasattr(conflict.code, "value") else str(conflict.code)
    )

    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.PRESENTATION_CONFLICT,
        source_id=sid,
        domain_id=domain_id,
        blocking=False,
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=None,
        metadata={
            "code": code_val,
            "related_ids": list(conflict.related_ids),
        },
    )
    return ref, domains


def adapt_cross_domain_contradiction(
    contradiction: CrossDomainContradiction,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]:
    """Normalize a CrossDomainContradiction."""
    if not isinstance(contradiction, CrossDomainContradiction):
        raise DomainConflictResolutionContractError(
            f"Expected CrossDomainContradiction, got {type(contradiction).__name__}",
            field="contradiction",
        )
    is_blocking = (
        contradiction.requires_review
        or contradiction.severity
        in (CrossDomainSeverity.HIGH, CrossDomainSeverity.CRITICAL)
    ) and not contradiction.resolved

    if is_blocking:
        sev = DomainConflictSeverity.BLOCKING
    elif contradiction.severity == CrossDomainSeverity.LOW:
        sev = DomainConflictSeverity.ADVISORY
    else:
        sev = DomainConflictSeverity.MATERIAL

    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.CROSS_DOMAIN_CONTRADICTION,
        source_id=contradiction.id,
        domain_id=None,
        blocking=is_blocking,
        severity=sev,
        authority_kind=None,
        metadata={
            "resolved_upstream": contradiction.resolved,
            "requires_review": contradiction.requires_review,
        },
    )
    return ref, contradiction.domains


def adapt_knowledge_contradiction(
    contradiction: Contradiction,
    *,
    domain_ids: tuple[DomainId, ...] = (),
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]:
    """Normalize a Cognitive Contradiction reference."""
    if not isinstance(contradiction, Contradiction):
        raise DomainConflictResolutionContractError(
            f"Expected Contradiction, got {type(contradiction).__name__}",
            field="contradiction",
        )

    is_blocking = (
        contradiction.status is ContradictionStatus.UNRESOLVED
        and contradiction.severity
        in (ContradictionSeverity.HIGH, ContradictionSeverity.CRITICAL)
    )
    if is_blocking:
        sev = DomainConflictSeverity.BLOCKING
    elif contradiction.severity is ContradictionSeverity.LOW:
        sev = DomainConflictSeverity.ADVISORY
    else:
        sev = DomainConflictSeverity.MATERIAL

    evidence_refs: list[str] = []
    if (
        hasattr(contradiction, "supporting_evidence")
        and contradiction.supporting_evidence
    ):
        for ev in contradiction.supporting_evidence:
            if hasattr(ev, "id") and isinstance(ev.id, str) and ev.id.strip():
                evidence_refs.append(ev.id.strip())

    status_val = (
        contradiction.status.value
        if hasattr(contradiction.status, "value")
        else str(contradiction.status)
    )

    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.KNOWLEDGE_CONTRADICTION,
        source_id=contradiction.id,
        domain_id=domain_ids[0] if len(domain_ids) == 1 else None,
        blocking=is_blocking,
        severity=sev,
        authority_kind=None,
        evidence_refs=tuple(evidence_refs),
        metadata={
            "status": status_val,
            "preferred_id": contradiction.preferred_id,
        },
    )
    return ref, domain_ids


def adapt_selection_conflict(
    result: DomainResolutionResult,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]:
    """Normalize a DomainResolutionResult with AMBIGUOUS status."""
    if not isinstance(result, DomainResolutionResult):
        raise DomainConflictResolutionContractError(
            f"Expected DomainResolutionResult, got {type(result).__name__}",
            field="result",
        )
    if (
        result.status is not DomainResolutionStatus.AMBIGUOUS
        or len(result.ambiguous_domains) < 2
    ):
        raise DomainConflictResolutionContractError(
            "DomainResolutionResult must have status=AMBIGUOUS and >=2 ambiguous domains to adapt as selection conflict",
            field="status",
        )

    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.SELECTION_CONFLICT,
        source_id=result.id,
        domain_id=None,
        blocking=False,
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=None,
        metadata={
            "requires_clarification": result.requires_clarification,
        },
    )
    return ref, result.ambiguous_domains
