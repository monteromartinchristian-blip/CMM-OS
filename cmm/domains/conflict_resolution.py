"""Phase 10.32 — Domain Conflict Resolution engine.

Pure, deterministic universal conflict orchestrator enforcing strict authority
precedence across domain conflict references without performing runtime side
effects, event emission, persistence, or duplicate truth resolution.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType

from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReasonCode,
    DomainConflictReference,
    DomainConflictResolution,
    DomainConflictResolutionPolicy,
    DomainConflictStatus,
    DomainConflictStrategy,
)
from cmm.domains.errors import DomainConflictResolutionContractError
from cmm.domains.identifiers import DomainId

_AUTHORITY_RANK: Mapping[DomainConflictAuthority, int] = MappingProxyType(
    {
        DomainConflictAuthority.GLOBAL_SAFETY: 0,
        DomainConflictAuthority.PERMISSION: 1,
        DomainConflictAuthority.MANDATORY_RULE: 2,
        DomainConflictAuthority.HIGH_RISK_DOMAIN: 3,
        DomainConflictAuthority.PRIMARY_DOMAIN: 4,
        DomainConflictAuthority.EVIDENCE: 5,
        DomainConflictAuthority.RELIABILITY: 6,
        DomainConflictAuthority.TEMPORAL: 7,
        DomainConflictAuthority.HUMAN_REVIEW: 8,
        DomainConflictAuthority.USER: 9,
        DomainConflictAuthority.UNCLASSIFIED: 10,
    }
)

_ASK_USER_ALLOWED_KINDS = frozenset(
    {
        DomainConflictKind.PREFERENCE,
        DomainConflictKind.DOMAIN_PRECEDENCE,
        DomainConflictKind.RECOMMENDATION,
        DomainConflictKind.SELECTION,
    }
)


def _validated_scores(
    raw: Mapping[str, float] | None,
    *,
    allowed_ids: frozenset[str],
    field_name: str,
) -> MappingProxyType[str, float]:
    """Validate and freeze structured numeric scores."""
    if raw is None:
        return MappingProxyType({})
    if not isinstance(raw, Mapping):
        raise DomainConflictResolutionContractError(
            f"{field_name} must be a mapping",
            field=field_name,
        )
    result: dict[str, float] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or k not in allowed_ids:
            raise DomainConflictResolutionContractError(
                f"Unknown or invalid reference ID in {field_name}: {k!r}",
                field=field_name,
            )
        if (
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
        ):
            raise DomainConflictResolutionContractError(
                f"Invalid numeric score in {field_name}[{k}]: {v!r}",
                field=field_name,
            )
        result[k] = float(v)
    return MappingProxyType(result)


def _highest_authority(
    references: tuple[DomainConflictReference, ...],
) -> DomainConflictAuthority:
    """Determine highest applicable authority among references."""
    return min(
        (
            ref.authority_kind or DomainConflictAuthority.UNCLASSIFIED
            for ref in references
        ),
        key=_AUTHORITY_RANK.__getitem__,
    )


def _preserve(
    case: DomainConflictCase,
    *,
    strategy: DomainConflictStrategy = DomainConflictStrategy.MAINTAIN_CONFLICT,
    reason_codes: tuple[DomainConflictReasonCode, ...],
) -> DomainConflictResolution:
    """Deterministic, pure helper to preserve an unresolved or blocked conflict."""
    return DomainConflictResolution(
        conflict_id=case.id,
        status=(
            DomainConflictStatus.BLOCKED
            if case.blocking
            else DomainConflictStatus.UNRESOLVED
        ),
        strategy=strategy,
        preserved_reference_ids=tuple(ref.source_id for ref in case.references),
        reason_codes=reason_codes,
        conflict_preserved=True,
        can_proceed=False,
    )


def _validate_resolution_against_case(
    case: DomainConflictCase,
    resolution: DomainConflictResolution,
) -> DomainConflictResolution:
    """Ensure all referenced IDs exist within the source case."""
    case_ids = frozenset(ref.source_id for ref in case.references)
    for ref_id in (
        resolution.winning_reference_ids
        + resolution.preserved_reference_ids
        + resolution.rejected_reference_ids
    ):
        if ref_id not in case_ids:
            raise DomainConflictResolutionContractError(
                f"Resolution references unknown reference ID not in source case: {ref_id!r}",
                field="references",
            )
    return resolution


class DomainConflictResolver:
    """Pure, deterministic domain conflict resolver orchestrating policy decisions."""

    def resolve(
        self,
        case: DomainConflictCase,
        *,
        policy: DomainConflictResolutionPolicy | None = None,
        primary_domain: DomainId | None = None,
        highest_risk_domain: DomainId | None = None,
        evidence_scores: Mapping[str, float] | None = None,
        reliability_scores: Mapping[str, float] | None = None,
        temporal_scores: Mapping[str, float] | None = None,
    ) -> DomainConflictResolution:
        """Resolve a DomainConflictCase according to strict authority precedence."""
        if not isinstance(case, DomainConflictCase):
            raise DomainConflictResolutionContractError(
                f"Expected DomainConflictCase, got {type(case).__name__}",
                field="case",
            )

        eff_policy = policy if policy is not None else DomainConflictResolutionPolicy()
        if not isinstance(eff_policy, DomainConflictResolutionPolicy):
            raise DomainConflictResolutionContractError(
                f"Expected DomainConflictResolutionPolicy, got {type(eff_policy).__name__}",
                field="policy",
            )

        case_ref_ids = frozenset(ref.source_id for ref in case.references)
        v_evidence = _validated_scores(
            evidence_scores,
            allowed_ids=case_ref_ids,
            field_name="evidence_scores",
        )
        v_reliability = _validated_scores(
            reliability_scores,
            allowed_ids=case_ref_ids,
            field_name="reliability_scores",
        )
        v_temporal = _validated_scores(
            temporal_scores,
            allowed_ids=case_ref_ids,
            field_name="temporal_scores",
        )

        authority = _highest_authority(case.references)
        decisive_refs = tuple(
            ref
            for ref in case.references
            if (ref.authority_kind or DomainConflictAuthority.UNCLASSIFIED) is authority
        )

        strategy = self._route_strategy(authority, case, eff_policy)

        if case.candidate_strategies and strategy not in case.candidate_strategies:
            res = _preserve(
                case,
                strategy=strategy,
                reason_codes=(
                    DomainConflictReasonCode.STRATEGY_NOT_APPLICABLE,
                    DomainConflictReasonCode.BLOCKING_UNRESOLVED
                    if case.blocking
                    else DomainConflictReasonCode.INSUFFICIENT_BASIS,
                ),
            )
            return _validate_resolution_against_case(case, res)

        res = self._apply_strategy(
            strategy=strategy,
            authority=authority,
            case=case,
            decisive_refs=decisive_refs,
            policy=eff_policy,
            primary_domain=primary_domain,
            highest_risk_domain=highest_risk_domain,
            evidence_scores=v_evidence,
            reliability_scores=v_reliability,
            temporal_scores=v_temporal,
        )
        return _validate_resolution_against_case(case, res)

    def _route_strategy(
        self,
        authority: DomainConflictAuthority,
        case: DomainConflictCase,
        policy: DomainConflictResolutionPolicy,
    ) -> DomainConflictStrategy:
        match authority:
            case DomainConflictAuthority.GLOBAL_SAFETY:
                return DomainConflictStrategy.MOST_RESTRICTIVE
            case DomainConflictAuthority.PERMISSION:
                return policy.permission_strategy
            case DomainConflictAuthority.MANDATORY_RULE:
                return policy.mandatory_rule_strategy
            case DomainConflictAuthority.HIGH_RISK_DOMAIN:
                return policy.high_risk_strategy
            case DomainConflictAuthority.PRIMARY_DOMAIN:
                return policy.primary_strategy
            case DomainConflictAuthority.EVIDENCE:
                return policy.evidence_strategy
            case DomainConflictAuthority.RELIABILITY:
                return DomainConflictStrategy.EVIDENCE_WEIGHTED
            case DomainConflictAuthority.TEMPORAL:
                return DomainConflictStrategy.EVIDENCE_WEIGHTED
            case DomainConflictAuthority.USER:
                if case.requires_human_review:
                    return DomainConflictStrategy.HUMAN_REVIEW
                return DomainConflictStrategy.ASK_USER
            case DomainConflictAuthority.HUMAN_REVIEW:
                return DomainConflictStrategy.HUMAN_REVIEW
            case DomainConflictAuthority.UNCLASSIFIED:
                return (
                    policy.blocking_strategy
                    if case.blocking
                    else policy.default_strategy
                )

    def _apply_strategy(
        self,
        *,
        strategy: DomainConflictStrategy,
        authority: DomainConflictAuthority,
        case: DomainConflictCase,
        decisive_refs: tuple[DomainConflictReference, ...],
        policy: DomainConflictResolutionPolicy,
        primary_domain: DomainId | None,
        highest_risk_domain: DomainId | None,
        evidence_scores: Mapping[str, float],
        reliability_scores: Mapping[str, float],
        temporal_scores: Mapping[str, float],
    ) -> DomainConflictResolution:
        match strategy:
            case DomainConflictStrategy.MOST_RESTRICTIVE:
                return self._resolve_most_restrictive(case, decisive_refs, authority)
            case DomainConflictStrategy.HIGH_RISK_DOMAIN_PRECEDENCE:
                return self._resolve_high_risk(case, decisive_refs, highest_risk_domain)
            case DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE:
                return self._resolve_primary(case, decisive_refs, primary_domain)
            case DomainConflictStrategy.EVIDENCE_WEIGHTED:
                return self._resolve_evidence_weighted(
                    case,
                    decisive_refs,
                    authority,
                    evidence_scores,
                    reliability_scores,
                    temporal_scores,
                )
            case DomainConflictStrategy.SEPARATE_RESULTS:
                return self._resolve_separate_results(case, authority, policy)
            case DomainConflictStrategy.ASK_USER:
                return self._resolve_ask_user(case, authority, policy)
            case DomainConflictStrategy.HUMAN_REVIEW:
                return self._resolve_human_review(case, policy)
            case DomainConflictStrategy.POSTPONE_ACTION:
                return self._resolve_postpone_action(case, policy)
            case DomainConflictStrategy.MAINTAIN_CONFLICT:
                return self._resolve_maintain_conflict(case)

    def _resolve_most_restrictive(
        self,
        case: DomainConflictCase,
        decisive_refs: tuple[DomainConflictReference, ...],
        authority: DomainConflictAuthority,
    ) -> DomainConflictResolution:
        if authority is DomainConflictAuthority.GLOBAL_SAFETY:
            reason = DomainConflictReasonCode.SAFETY_PRECEDENCE
        elif authority is DomainConflictAuthority.PERMISSION:
            reason = DomainConflictReasonCode.PERMISSION_PRECEDENCE
        elif authority is DomainConflictAuthority.MANDATORY_RULE:
            reason = DomainConflictReasonCode.MANDATORY_RULE_PRECEDENCE
        else:
            reason = DomainConflictReasonCode.SAFETY_PRECEDENCE

        blocking_refs = tuple(r for r in decisive_refs if r.blocking)
        if case.blocking:
            if len(blocking_refs) == 1:
                winner = blocking_refs[0]
                rejected = tuple(
                    r.source_id
                    for r in case.references
                    if r.source_id != winner.source_id
                )
                return DomainConflictResolution(
                    conflict_id=case.id,
                    status=DomainConflictStatus.RESOLVED,
                    strategy=DomainConflictStrategy.MOST_RESTRICTIVE,
                    winning_reference_ids=(winner.source_id,),
                    rejected_reference_ids=rejected,
                    reason_codes=(reason,),
                    can_proceed=False,
                )
            return _preserve(
                case,
                strategy=DomainConflictStrategy.MOST_RESTRICTIVE,
                reason_codes=(
                    reason,
                    DomainConflictReasonCode.BLOCKING_UNRESOLVED,
                ),
            )

        if len(decisive_refs) == 1:
            winner = decisive_refs[0]
            rejected = tuple(
                r.source_id for r in case.references if r.source_id != winner.source_id
            )
            return DomainConflictResolution(
                conflict_id=case.id,
                status=DomainConflictStatus.RESOLVED,
                strategy=DomainConflictStrategy.MOST_RESTRICTIVE,
                winning_reference_ids=(winner.source_id,),
                rejected_reference_ids=rejected,
                reason_codes=(reason,),
                can_proceed=True,
            )

        return _preserve(
            case,
            strategy=DomainConflictStrategy.MOST_RESTRICTIVE,
            reason_codes=(
                reason,
                DomainConflictReasonCode.INSUFFICIENT_BASIS,
            ),
        )

    def _resolve_high_risk(
        self,
        case: DomainConflictCase,
        decisive_refs: tuple[DomainConflictReference, ...],
        highest_risk_domain: DomainId | None,
    ) -> DomainConflictResolution:
        if highest_risk_domain is None or case.blocking:
            return _preserve(
                case,
                strategy=DomainConflictStrategy.HIGH_RISK_DOMAIN_PRECEDENCE,
                reason_codes=(
                    DomainConflictReasonCode.HIGH_RISK_PRECEDENCE,
                    DomainConflictReasonCode.BLOCKING_UNRESOLVED
                    if case.blocking
                    else DomainConflictReasonCode.INSUFFICIENT_BASIS,
                ),
            )

        matches = tuple(
            r
            for r in decisive_refs
            if r.domain_id is not None and r.domain_id == highest_risk_domain
        )
        if len(matches) == 1:
            winner = matches[0]
            rejected = tuple(
                r.source_id for r in case.references if r.source_id != winner.source_id
            )
            return DomainConflictResolution(
                conflict_id=case.id,
                status=DomainConflictStatus.RESOLVED,
                strategy=DomainConflictStrategy.HIGH_RISK_DOMAIN_PRECEDENCE,
                winning_reference_ids=(winner.source_id,),
                rejected_reference_ids=rejected,
                reason_codes=(DomainConflictReasonCode.HIGH_RISK_PRECEDENCE,),
                can_proceed=True,
            )

        return _preserve(
            case,
            strategy=DomainConflictStrategy.HIGH_RISK_DOMAIN_PRECEDENCE,
            reason_codes=(
                DomainConflictReasonCode.HIGH_RISK_PRECEDENCE,
                DomainConflictReasonCode.INSUFFICIENT_BASIS,
            ),
        )

    def _resolve_primary(
        self,
        case: DomainConflictCase,
        decisive_refs: tuple[DomainConflictReference, ...],
        primary_domain: DomainId | None,
    ) -> DomainConflictResolution:
        primary_eligible_kinds = frozenset(
            {
                DomainConflictKind.DOMAIN_PRECEDENCE,
                DomainConflictKind.RECOMMENDATION,
                DomainConflictKind.PRESENTATION,
                DomainConflictKind.COMPOSITION,
                DomainConflictKind.SELECTION,
            }
        )
        if case.kind not in primary_eligible_kinds:
            return _preserve(
                case,
                strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
                reason_codes=(
                    DomainConflictReasonCode.STRATEGY_NOT_APPLICABLE,
                    DomainConflictReasonCode.BLOCKING_UNRESOLVED
                    if case.blocking
                    else DomainConflictReasonCode.INSUFFICIENT_BASIS,
                ),
            )

        if primary_domain is None or case.blocking:
            return _preserve(
                case,
                strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
                reason_codes=(
                    DomainConflictReasonCode.PRIMARY_PRECEDENCE,
                    DomainConflictReasonCode.BLOCKING_UNRESOLVED
                    if case.blocking
                    else DomainConflictReasonCode.INSUFFICIENT_BASIS,
                ),
            )

        matches = tuple(
            r
            for r in decisive_refs
            if r.domain_id is not None and r.domain_id == primary_domain
        )
        if len(matches) == 1:
            winner = matches[0]
            rejected = tuple(
                r.source_id for r in case.references if r.source_id != winner.source_id
            )
            return DomainConflictResolution(
                conflict_id=case.id,
                status=DomainConflictStatus.RESOLVED,
                strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
                winning_reference_ids=(winner.source_id,),
                rejected_reference_ids=rejected,
                reason_codes=(DomainConflictReasonCode.PRIMARY_PRECEDENCE,),
                can_proceed=True,
            )

        return _preserve(
            case,
            strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
            reason_codes=(
                DomainConflictReasonCode.PRIMARY_PRECEDENCE,
                DomainConflictReasonCode.INSUFFICIENT_BASIS,
            ),
        )

    def _resolve_evidence_weighted(
        self,
        case: DomainConflictCase,
        decisive_refs: tuple[DomainConflictReference, ...],
        authority: DomainConflictAuthority,
        evidence_scores: Mapping[str, float],
        reliability_scores: Mapping[str, float],
        temporal_scores: Mapping[str, float],
    ) -> DomainConflictResolution:
        if authority is DomainConflictAuthority.RELIABILITY:
            scores = reliability_scores
            reason = DomainConflictReasonCode.RELIABILITY_PRECEDENCE
        elif authority is DomainConflictAuthority.TEMPORAL:
            scores = temporal_scores
            reason = DomainConflictReasonCode.TEMPORAL_PRECEDENCE
        else:
            scores = evidence_scores
            reason = DomainConflictReasonCode.EVIDENCE_PRECEDENCE

        if case.blocking:
            return _preserve(
                case,
                strategy=DomainConflictStrategy.EVIDENCE_WEIGHTED,
                reason_codes=(
                    reason,
                    DomainConflictReasonCode.BLOCKING_UNRESOLVED,
                ),
            )

        if not all(r.source_id in scores for r in decisive_refs):
            return _preserve(
                case,
                strategy=DomainConflictStrategy.EVIDENCE_WEIGHTED,
                reason_codes=(
                    reason,
                    DomainConflictReasonCode.INSUFFICIENT_BASIS,
                ),
            )

        max_score = max(scores[r.source_id] for r in decisive_refs)
        max_refs = [r for r in decisive_refs if scores[r.source_id] == max_score]
        if len(max_refs) == 1:
            winner = max_refs[0]
            rejected = tuple(
                r.source_id for r in case.references if r.source_id != winner.source_id
            )
            return DomainConflictResolution(
                conflict_id=case.id,
                status=DomainConflictStatus.RESOLVED,
                strategy=DomainConflictStrategy.EVIDENCE_WEIGHTED,
                winning_reference_ids=(winner.source_id,),
                rejected_reference_ids=rejected,
                reason_codes=(reason,),
                can_proceed=True,
            )

        return _preserve(
            case,
            strategy=DomainConflictStrategy.EVIDENCE_WEIGHTED,
            reason_codes=(
                reason,
                DomainConflictReasonCode.INSUFFICIENT_BASIS,
            ),
        )

    def _resolve_separate_results(
        self,
        case: DomainConflictCase,
        authority: DomainConflictAuthority,
        policy: DomainConflictResolutionPolicy,
    ) -> DomainConflictResolution:
        hard_authorities = (
            DomainConflictAuthority.GLOBAL_SAFETY,
            DomainConflictAuthority.PERMISSION,
            DomainConflictAuthority.MANDATORY_RULE,
        )
        if (
            not policy.allow_separate_results
            or case.blocking
            or authority in hard_authorities
        ):
            return _preserve(
                case,
                strategy=DomainConflictStrategy.SEPARATE_RESULTS,
                reason_codes=(
                    DomainConflictReasonCode.SEPARATE_RESULTS,
                    DomainConflictReasonCode.BLOCKING_UNRESOLVED
                    if case.blocking
                    else DomainConflictReasonCode.STRATEGY_NOT_APPLICABLE,
                ),
            )

        return DomainConflictResolution(
            conflict_id=case.id,
            status=DomainConflictStatus.UNRESOLVED,
            strategy=DomainConflictStrategy.SEPARATE_RESULTS,
            preserved_reference_ids=tuple(r.source_id for r in case.references),
            reason_codes=(DomainConflictReasonCode.SEPARATE_RESULTS,),
            conflict_preserved=True,
            can_proceed=True,
        )

    def _resolve_ask_user(
        self,
        case: DomainConflictCase,
        authority: DomainConflictAuthority,
        policy: DomainConflictResolutionPolicy,
    ) -> DomainConflictResolution:
        hard_authorities = (
            DomainConflictAuthority.GLOBAL_SAFETY,
            DomainConflictAuthority.PERMISSION,
            DomainConflictAuthority.MANDATORY_RULE,
        )
        if (
            not policy.allow_user_confirmation
            or case.blocking
            or case.requires_human_review
            or authority in hard_authorities
            or case.kind not in _ASK_USER_ALLOWED_KINDS
        ):
            return _preserve(
                case,
                strategy=DomainConflictStrategy.ASK_USER,
                reason_codes=(
                    DomainConflictReasonCode.USER_INPUT_REQUIRED,
                    DomainConflictReasonCode.BLOCKING_UNRESOLVED
                    if case.blocking
                    else DomainConflictReasonCode.STRATEGY_NOT_APPLICABLE,
                ),
            )

        return DomainConflictResolution(
            conflict_id=case.id,
            status=DomainConflictStatus.AWAITING_USER,
            strategy=DomainConflictStrategy.ASK_USER,
            preserved_reference_ids=tuple(r.source_id for r in case.references),
            reason_codes=(DomainConflictReasonCode.USER_INPUT_REQUIRED,),
            requires_user_input=True,
            conflict_preserved=True,
            can_proceed=False,
        )

    def _resolve_human_review(
        self,
        case: DomainConflictCase,
        policy: DomainConflictResolutionPolicy,
    ) -> DomainConflictResolution:
        if not policy.allow_human_review:
            return _preserve(
                case,
                strategy=DomainConflictStrategy.HUMAN_REVIEW,
                reason_codes=(
                    DomainConflictReasonCode.HUMAN_REVIEW_REQUIRED,
                    DomainConflictReasonCode.STRATEGY_NOT_APPLICABLE,
                ),
            )

        return DomainConflictResolution(
            conflict_id=case.id,
            status=DomainConflictStatus.AWAITING_HUMAN_REVIEW,
            strategy=DomainConflictStrategy.HUMAN_REVIEW,
            preserved_reference_ids=tuple(r.source_id for r in case.references),
            reason_codes=(DomainConflictReasonCode.HUMAN_REVIEW_REQUIRED,),
            requires_human_review=True,
            conflict_preserved=True,
            can_proceed=False,
        )

    def _resolve_postpone_action(
        self,
        case: DomainConflictCase,
        policy: DomainConflictResolutionPolicy,
    ) -> DomainConflictResolution:
        if not policy.allow_postpone:
            return _preserve(
                case,
                strategy=DomainConflictStrategy.POSTPONE_ACTION,
                reason_codes=(
                    DomainConflictReasonCode.ACTION_POSTPONED,
                    DomainConflictReasonCode.STRATEGY_NOT_APPLICABLE,
                ),
            )

        return DomainConflictResolution(
            conflict_id=case.id,
            status=DomainConflictStatus.POSTPONED,
            strategy=DomainConflictStrategy.POSTPONE_ACTION,
            preserved_reference_ids=tuple(r.source_id for r in case.references),
            reason_codes=(DomainConflictReasonCode.ACTION_POSTPONED,),
            action_postponed=True,
            conflict_preserved=True,
            can_proceed=False,
        )

    def _resolve_maintain_conflict(
        self,
        case: DomainConflictCase,
    ) -> DomainConflictResolution:
        return _preserve(
            case,
            strategy=DomainConflictStrategy.MAINTAIN_CONFLICT,
            reason_codes=(
                DomainConflictReasonCode.PRESERVED,
                DomainConflictReasonCode.BLOCKING_UNRESOLVED
                if case.blocking
                else DomainConflictReasonCode.INSUFFICIENT_BASIS,
            ),
        )
