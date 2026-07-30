"""Phase 10.7 – Domain Resolver.

Deterministic resolver that selects a primary domain, supporting domains,
rejected domains, ambiguous domains, global confidence, and structured
reasons from a ``DomainResolutionContext``.

Pure function of the context; no live registry, no stores, no filesystem,
no mutable shared state, no LLM calls.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from typing_extensions import Protocol

from cmm.domains.enums import DomainResolutionStatus, DomainStatus
from cmm.domains.errors import (
    DomainResolverConfigurationError,
    DomainResolverExecutionError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resolver_contracts import (
    DomainCandidateScore,
    DomainResolutionReason,
    DomainResolutionResult,
    DomainScoringPolicy,
)
from cmm.domains.resolver_scoring import DomainCandidateScorer

# ── Protocol ──────────────────────────────────────────────────────────────────


class DomainResolver(Protocol):
    """Protocol for domain resolution.

    Implementations take a ``DomainResolutionContext`` and return a
    ``DomainResolutionResult``.
    """

    def resolve(
        self,
        context: DomainResolutionContext,
    ) -> DomainResolutionResult: ...


# ── Default implementation ────────────────────────────────────────────────────


class DefaultDomainResolver:
    """Deterministic domain resolver using structured evidence only.

    The resolver is pure with respect to the context: same context
    (with fixed clock/id factories) produces same result every time.
    """

    def __init__(
        self,
        *,
        scorer: DomainCandidateScorer | None = None,
        scoring_policy: DomainScoringPolicy | None = None,
        fallback_domain: DomainId | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if (
            scorer is not None
            and scoring_policy is not None
            and scorer.policy is not scoring_policy
        ):
            raise DomainResolverConfigurationError(
                "scorer.policy and scoring_policy are different objects. "
                "Provide one or the other, or ensure they are the same instance.",
                field="scoring_policy",
            )
        if scoring_policy is not None:
            self._scorer = DomainCandidateScorer(policy=scoring_policy)
        elif scorer is not None:
            self._scorer = scorer
        else:
            self._scorer = DomainCandidateScorer()

        self._policy: DomainScoringPolicy = self._scorer.policy
        self._fallback_domain: DomainId | None = fallback_domain
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: uuid4().hex)

        if self._fallback_domain is not None and not isinstance(
            self._fallback_domain, DomainId
        ):
            raise DomainResolverConfigurationError(
                "fallback_domain must be a DomainId or None",
                field="fallback_domain",
            )

    @property
    def scoring_policy(self) -> DomainScoringPolicy:
        """The scoring policy in use (immutable)."""
        return self._policy

    @property
    def fallback_domain(self) -> DomainId | None:
        """The configured fallback domain, if any."""
        return self._fallback_domain

    # ── Public API ────────────────────────────────────────────────────────────

    def resolve(
        self,
        context: DomainResolutionContext,
    ) -> DomainResolutionResult:
        """Resolve domains from a context."""
        if not isinstance(context, DomainResolutionContext):
            raise TypeError(
                f"context must be a DomainResolutionContext, got {type(context).__name__}"
            )

        return self._resolve_impl(context)

    def _resolve_impl(
        self,
        context: DomainResolutionContext,
    ) -> DomainResolutionResult:
        """Core resolution logic."""
        system_policy = context.system_policy

        available = context.available_domains
        if not available:
            return self._build_result(
                context=context,
                status=DomainResolutionStatus.UNSUPPORTED,
                primary=None,
                candidate_scores=(),
                reasons=(
                    DomainResolutionReason(
                        code="DOMAIN_NO_ELIGIBLE_CANDIDATE",
                        message="No available domains in context",
                    ),
                ),
            )

        candidates, _rejected_scores, all_reasons = self._filter_and_score(
            context, available
        )

        eligible_scores = [
            c
            for c in candidates
            if c.eligible
            and not c.rejected
            and c.score >= self._policy.minimum_resolution_score
        ]
        rejected_list = [c for c in candidates if c.rejected]

        rejected_domains: tuple[DomainId, ...] = tuple(
            sorted((c.domain_id for c in rejected_list), key=lambda d: d.slug)
        )

        explicit_eligible = self._get_explicit_eligible(context, eligible_scores)

        required_slugs: set[str] = set()
        if system_policy is not None:
            required_slugs = {d.slug for d in system_policy.required_domains}

        required_blocked = [
            c for c in rejected_list if c.domain_id.slug in required_slugs
        ]
        if required_blocked:
            blocking_reasons: list[DomainResolutionReason] = []
            for rc in required_blocked:
                for r in rc.reasons:
                    if r.blocking:
                        blocking_reasons.append(r)
                if not any(r.blocking for r in rc.reasons):
                    blocking_reasons.append(
                        DomainResolutionReason(
                            code="DOMAIN_POLICY_DENIED",
                            message=f"Required domain {rc.domain_id} is rejected",
                            domain_id=rc.domain_id,
                            blocking=True,
                        )
                    )
            return self._build_result(
                context=context,
                status=DomainResolutionStatus.BLOCKED,
                primary=None,
                rejected_domains=rejected_domains,
                candidate_scores=tuple(candidates),
                reasons=tuple(blocking_reasons) if blocking_reasons else all_reasons,
            )

        if not eligible_scores:
            fallback_result = self._try_fallback(
                context, candidates, eligible_scores, rejected_list
            )
            if fallback_result is not None:
                return fallback_result
            return self._build_result(
                context=context,
                status=DomainResolutionStatus.UNSUPPORTED,
                primary=None,
                rejected_domains=rejected_domains,
                candidate_scores=tuple(candidates),
                reasons=all_reasons
                + (
                    DomainResolutionReason(
                        code="DOMAIN_NO_ELIGIBLE_CANDIDATE",
                        message="No eligible domain candidate found",
                    ),
                ),
                confidence=0.0,
            )

        eligible_scores = self._sort_eligible(eligible_scores)

        ambiguity_check = self._check_ambiguity(
            context,
            eligible_scores,
            explicit_eligible,
            candidates,
            rejected_domains,
            all_reasons,
        )
        if ambiguity_check is not None:
            return ambiguity_check

        high_impact_check = self._check_high_impact(
            context,
            eligible_scores,
            candidates,
            rejected_domains,
            all_reasons,
        )
        if high_impact_check is not None:
            return high_impact_check

        primary_score = eligible_scores[0]
        primary = primary_score.domain_id

        supporting = self._select_supporting(
            eligible_scores, primary, primary_score, context, candidates
        )

        # Build result reasons: primary + supporting + blocking rejected + global
        resolved_reasons = self._build_resolved_reasons(
            eligible_scores=eligible_scores,
            primary=primary,
            supporting_ids={s.slug for s in supporting},
            rejected_list=rejected_list,
            global_reasons=all_reasons,
            context=context,
        )

        return self._build_result(
            context=context,
            status=DomainResolutionStatus.RESOLVED,
            primary=primary,
            supporting_domains=supporting,
            rejected_domains=rejected_domains,
            candidate_scores=tuple(candidates),
            reasons=resolved_reasons,
            confidence=primary_score.confidence,
        )

    # ── Filter & Score ────────────────────────────────────────────────────────

    def _filter_and_score(
        self,
        context: DomainResolutionContext,
        available: tuple[DomainId, ...],
    ) -> tuple[
        list[DomainCandidateScore],
        list[DomainCandidateScore],
        tuple[DomainResolutionReason, ...],
    ]:
        system_policy = context.system_policy
        all_candidates: list[DomainCandidateScore] = []
        rejected: list[DomainCandidateScore] = []
        global_reasons: list[DomainResolutionReason] = []

        require_auth = True
        if system_policy is not None:
            require_auth = system_policy.require_authorization

        authorized_slugs = {d.slug for d in context.authorized_domains}
        denied_slugs: set[str] = set()
        allowed_slugs: set[str] | None = None

        # Status evidence from builder metadata
        registry_versions: dict[str, list[dict[str, str]]] = {}
        raw_meta = dict(context.metadata)
        if "_resolution_registry_versions" in raw_meta:
            registry_versions = raw_meta["_resolution_registry_versions"]

        allow_disabled = False
        allow_degraded = True
        if system_policy is not None:
            denied_slugs = {d.slug for d in system_policy.denied_domains}
            allow_disabled = system_policy.allow_disabled
            allow_degraded = system_policy.allow_degraded
            if system_policy.allowed_domains:
                allowed_slugs = {d.slug for d in system_policy.allowed_domains}

        for domain_id in available:
            slug = domain_id.slug
            rejection_codes: list[str] = []
            rejection_reasons: list[DomainResolutionReason] = []

            # ── Allowed domains policy ─────────────────────────────────
            if allowed_slugs is not None and slug not in allowed_slugs:
                rejection_codes.append("DOMAIN_POLICY_NOT_ALLOWED")
                rejection_reasons.append(
                    DomainResolutionReason(
                        code="DOMAIN_POLICY_NOT_ALLOWED",
                        message=f"Domain {domain_id} is not in the allowed list",
                        domain_id=domain_id,
                        blocking=True,
                    )
                )

            # ── Denied domains ──────────────────────────────────────────
            if slug in denied_slugs:
                rejection_codes.append("DOMAIN_POLICY_DENIED")
                rejection_reasons.append(
                    DomainResolutionReason(
                        code="DOMAIN_POLICY_DENIED",
                        message=f"Domain {domain_id} is denied by policy",
                        domain_id=domain_id,
                        blocking=True,
                    )
                )

            # ── Authorization (fail-closed) ─────────────────────────────
            if (
                require_auth
                and slug not in authorized_slugs
                and slug not in denied_slugs
            ):
                rejection_codes.append("DOMAIN_UNAUTHORIZED_REJECTED")
                rejection_reasons.append(
                    DomainResolutionReason(
                        code="DOMAIN_UNAUTHORIZED_REJECTED",
                        message=f"Domain {domain_id} is not authorized",
                        domain_id=domain_id,
                        blocking=True,
                    )
                )

            # ── Status: disabled / degraded ────────────────────────────
            domain_statuses = self._get_domain_statuses(slug, registry_versions)
            if DomainStatus.DISABLED.value in domain_statuses and not allow_disabled:
                rejection_codes.append("DOMAIN_DISABLED_REJECTED")
                rejection_reasons.append(
                    DomainResolutionReason(
                        code="DOMAIN_DISABLED_REJECTED",
                        message=f"Domain {domain_id} is disabled",
                        domain_id=domain_id,
                        blocking=True,
                    )
                )
            if DomainStatus.DEGRADED.value in domain_statuses and not allow_degraded:
                rejection_codes.append("DOMAIN_DEGRADED_REJECTED")
                rejection_reasons.append(
                    DomainResolutionReason(
                        code="DOMAIN_DEGRADED_REJECTED",
                        message=f"Domain {domain_id} is degraded and policy disallows degraded",
                        domain_id=domain_id,
                        blocking=True,
                    )
                )

            scored = self._scorer.score(context, domain_id)

            if rejection_codes:
                # Apply degraded penalty if degraded and allowed
                effective_score = scored.score
                effective_confidence = scored.confidence
                if (
                    DomainStatus.DEGRADED.value in domain_statuses
                    and allow_degraded
                    and "DOMAIN_DEGRADED_REJECTED" not in rejection_codes
                ):
                    effective_score = max(
                        0.0, effective_score - self._policy.degraded_penalty
                    )
                    rejection_reasons.append(
                        DomainResolutionReason(
                            code="DOMAIN_DEGRADED_PENALTY_APPLIED",
                            message=f"Degraded penalty applied to {domain_id}",
                            domain_id=domain_id,
                            signal_kind="system_policy",
                            contribution=-self._policy.degraded_penalty,
                        )
                    )

                all_reasons = list(rejection_reasons) + list(scored.reasons)
                rejected_score = DomainCandidateScore(
                    domain_id=domain_id,
                    score=effective_score,
                    confidence=effective_confidence,
                    eligible=False,
                    rejected=True,
                    rejection_codes=tuple(rejection_codes),
                    reasons=tuple(all_reasons),
                    matched_signal_kinds=scored.matched_signal_kinds,
                )
                rejected.append(rejected_score)
                all_candidates.append(rejected_score)
            else:
                # Apply degraded penalty for non-rejected degraded domains
                if DomainStatus.DEGRADED.value in domain_statuses and allow_degraded:
                    degraded_score = max(
                        0.0, scored.score - self._policy.degraded_penalty
                    )
                    degraded_confidence = scored.confidence
                    degraded_reasons = tuple(scored.reasons) + (
                        DomainResolutionReason(
                            code="DOMAIN_DEGRADED_PENALTY_APPLIED",
                            message=f"Degraded penalty applied to {domain_id}",
                            domain_id=domain_id,
                            signal_kind="system_policy",
                            contribution=-self._policy.degraded_penalty,
                        ),
                    )
                    degraded_candidate = DomainCandidateScore(
                        domain_id=domain_id,
                        score=degraded_score,
                        confidence=degraded_confidence,
                        eligible=scored.eligible,
                        rejected=False,
                        reasons=degraded_reasons,
                        matched_signal_kinds=scored.matched_signal_kinds,
                    )
                    all_candidates.append(degraded_candidate)
                else:
                    all_candidates.append(scored)

        all_candidates = self._sort_candidates(all_candidates)
        global_reasons.extend(r for c in rejected for r in c.reasons if r.blocking)

        return all_candidates, rejected, tuple(global_reasons)

    @staticmethod
    def _get_domain_statuses(
        slug: str, registry_versions: dict[str, list[dict[str, str]]]
    ) -> set[str]:
        """Extract status values from builder's version metadata."""
        entries = registry_versions.get(slug, [])
        return {entry["status"] for entry in entries if "status" in entry}

    # ── Explicit precedence ───────────────────────────────────────────────────

    def _get_explicit_eligible(
        self,
        context: DomainResolutionContext,
        eligible_scores: list[DomainCandidateScore],
    ) -> list[DomainCandidateScore]:
        explicit_slugs = {d.slug for d in context.explicit_domains}
        return [c for c in eligible_scores if c.domain_id.slug in explicit_slugs]

    # ── Ambiguity detection ───────────────────────────────────────────────────

    def _check_ambiguity(
        self,
        context: DomainResolutionContext,
        eligible: list[DomainCandidateScore],
        explicit_eligible: list[DomainCandidateScore],
        candidates: list[DomainCandidateScore],
        rejected_domains: tuple[DomainId, ...],
        global_blocking_reasons: tuple[DomainResolutionReason, ...],
    ) -> DomainResolutionResult | None:
        if len(eligible) < 2:
            return None

        p = self._policy

        if len(explicit_eligible) >= 2:
            top = explicit_eligible[0]
            second = explicit_eligible[1]
            if abs(top.score - second.score) <= p.ambiguity_margin:
                ambiguous_slugs = sorted({top.domain_id.slug, second.domain_id.slug})
                ambiguous_domains = tuple(
                    sorted([top.domain_id, second.domain_id], key=lambda d: d.slug)
                )
                question = self._build_ambiguity_question(ambiguous_domains)
                fallback_primary = None
                fallback_used = False
                if self._fallback_domain is not None:
                    fb_candidate = self._is_fallback_eligible(context, candidates)
                    if (
                        fb_candidate is not None
                        and fb_candidate.domain_id.slug not in ambiguous_slugs
                    ):
                        fallback_primary = fb_candidate.domain_id
                        fallback_used = True

                reasons = (
                    DomainResolutionReason(
                        code="DOMAIN_AMBIGUOUS_SCORE",
                        message=f"Ambiguous: {top.domain_id} vs {second.domain_id}",
                        blocking=False,
                    ),
                ) + global_blocking_reasons

                return self._build_result(
                    context=context,
                    status=DomainResolutionStatus.AMBIGUOUS,
                    primary=fallback_primary,
                    ambiguous_domains=ambiguous_domains,
                    confidence=min(top.confidence, second.confidence),
                    reasons=reasons,
                    requires_clarification=True,
                    recommended_question=question,
                    fallback_used=fallback_used,
                    candidate_scores=tuple(candidates),
                    rejected_domains=rejected_domains,
                )

        top = eligible[0]
        second = eligible[1]
        if (
            abs(top.score - second.score) <= p.ambiguity_margin
            and top.score >= p.minimum_resolution_score
            and second.score >= p.minimum_resolution_score
        ):
            explicit_slugs = {c.domain_id.slug for c in explicit_eligible}
            if (
                top.domain_id.slug not in explicit_slugs
                or second.domain_id.slug in explicit_slugs
            ):
                ambiguous_domains = tuple(
                    sorted([top.domain_id, second.domain_id], key=lambda d: d.slug)
                )
                ambiguous_slugs = {d.slug for d in ambiguous_domains}
                question = self._build_ambiguity_question(ambiguous_domains)
                fallback_primary = None
                fallback_used = False
                if self._fallback_domain is not None:
                    fb_candidate = self._is_fallback_eligible(context, candidates)
                    if (
                        fb_candidate is not None
                        and fb_candidate.domain_id.slug not in ambiguous_slugs
                    ):
                        fallback_primary = fb_candidate.domain_id
                        fallback_used = True

                reasons = (
                    DomainResolutionReason(
                        code="DOMAIN_AMBIGUOUS_SCORE",
                        message=f"Ambiguous: {top.domain_id} vs {second.domain_id}",
                        blocking=False,
                    ),
                ) + global_blocking_reasons

                return self._build_result(
                    context=context,
                    status=DomainResolutionStatus.AMBIGUOUS,
                    primary=fallback_primary,
                    ambiguous_domains=ambiguous_domains,
                    confidence=min(top.confidence, second.confidence),
                    reasons=reasons,
                    requires_clarification=True,
                    recommended_question=question,
                    fallback_used=fallback_used,
                    candidate_scores=tuple(candidates),
                    rejected_domains=rejected_domains,
                )

        return None

    def _build_ambiguity_question(self, domains: tuple[DomainId, ...]) -> str:
        names = [str(d) for d in domains]
        if len(names) == 2:
            return f"Which domain should take priority: {names[0]} or {names[1]}?"
        return f"Which domain should take priority among: {', '.join(names)}?"

    # ── High-impact protection ────────────────────────────────────────────────

    def _check_high_impact(
        self,
        context: DomainResolutionContext,
        eligible: list[DomainCandidateScore],
        candidates: list[DomainCandidateScore],
        rejected_domains: tuple[DomainId, ...],
        global_blocking_reasons: tuple[DomainResolutionReason, ...],
    ) -> DomainResolutionResult | None:
        system_policy = context.system_policy
        if system_policy is None:
            return None

        high_impact_slugs = {d.slug for d in system_policy.high_impact_domains}
        if not high_impact_slugs:
            return None

        min_conf = (
            system_policy.minimum_confidence
            or self._policy.high_impact_minimum_confidence
        )

        if eligible and high_impact_slugs:
            top = eligible[0]
            if top.domain_id.slug in high_impact_slugs and top.confidence < min_conf:
                second = eligible[1] if len(eligible) > 1 else None
                if second:
                    ambiguous_domains = tuple(
                        sorted([top.domain_id, second.domain_id], key=lambda d: d.slug)
                    )
                    reasons = global_blocking_reasons + (
                        DomainResolutionReason(
                            code="DOMAIN_HIGH_IMPACT_LOW_CONFIDENCE",
                            message=(
                                f"High-impact domain {top.domain_id} has "
                                f"low confidence ({top.confidence:.2f} < {min_conf:.2f})"
                            ),
                            domain_id=top.domain_id,
                            blocking=False,
                        ),
                    )
                    return self._build_result(
                        context=context,
                        status=DomainResolutionStatus.AMBIGUOUS,
                        ambiguous_domains=ambiguous_domains,
                        confidence=top.confidence,
                        reasons=reasons,
                        requires_clarification=True,
                        recommended_question=(
                            f"The domain {top.domain_id} is high-impact but has "
                            f"low confidence. Do you want to proceed?"
                        ),
                        candidate_scores=tuple(candidates),
                        rejected_domains=rejected_domains,
                    )
                else:
                    # No second candidate — try fallback
                    fallback_primary = None
                    fallback_used = False
                    fb_candidate = self._is_fallback_eligible(context, candidates)
                    if fb_candidate is not None:
                        fallback_primary = fb_candidate.domain_id
                        fallback_used = True

                    reasons = global_blocking_reasons + (
                        DomainResolutionReason(
                            code="DOMAIN_HIGH_IMPACT_LOW_CONFIDENCE",
                            message=(
                                f"High-impact domain {top.domain_id} has "
                                f"low confidence ({top.confidence:.2f} < {min_conf:.2f})"
                            ),
                            domain_id=top.domain_id,
                            blocking=False,
                        ),
                    )
                    return self._build_result(
                        context=context,
                        status=DomainResolutionStatus.INSUFFICIENT_INFORMATION,
                        primary=fallback_primary,
                        confidence=top.confidence,
                        reasons=reasons,
                        requires_clarification=True,
                        recommended_question=(
                            f"The domain {top.domain_id} is high-impact but has "
                            f"low confidence. Do you want to proceed?"
                        ),
                        fallback_used=fallback_used,
                        candidate_scores=tuple(candidates),
                        rejected_domains=rejected_domains,
                    )

        return None

    # ── Fallback ──────────────────────────────────────────────────────────────

    def _is_fallback_eligible(
        self,
        context: DomainResolutionContext,
        candidates: list[DomainCandidateScore],
    ) -> DomainCandidateScore | None:
        """Return the candidate score for the fallback domain if eligible, or None."""
        if self._fallback_domain is None:
            return None

        fb_slug = self._fallback_domain.slug

        # Must be present in available_domains
        available_slugs = {d.slug for d in context.available_domains}
        if fb_slug not in available_slugs:
            return None

        # Find the candidate
        fb_candidate = None
        for c in candidates:
            if c.domain_id.slug == fb_slug:
                fb_candidate = c
                break

        if fb_candidate is None:
            # Create a fresh score
            fb_candidate = self._scorer.score(context, self._fallback_domain)

        # Must be eligible
        if not fb_candidate.eligible:
            return None
        # Must not be rejected
        if fb_candidate.rejected:
            return None
        # Must be authorized
        authorized_slugs = {d.slug for d in context.authorized_domains}
        require_auth = True
        if context.system_policy is not None:
            require_auth = context.system_policy.require_authorization
        if require_auth and fb_slug not in authorized_slugs:
            return None
        # Must not be denied
        denied_slugs: set[str] = set()
        if context.system_policy is not None:
            denied_slugs = {d.slug for d in context.system_policy.denied_domains}
        if fb_slug in denied_slugs:
            return None
        # Must be allowed by policy if allowed_domains is set
        if context.system_policy is not None and context.system_policy.allowed_domains:
            allowed_slugs = {d.slug for d in context.system_policy.allowed_domains}
            if fb_slug not in allowed_slugs:
                return None
        # Must pass status checks
        if not self._check_status_allowed(context, fb_slug):
            return None

        return fb_candidate

    def _check_status_allowed(
        self, context: DomainResolutionContext, slug: str
    ) -> bool:
        """Check if a domain's status is allowed by policy."""
        registry_versions: dict[str, list[dict[str, str]]] = {}
        raw_meta = dict(context.metadata)
        if "_resolution_registry_versions" in raw_meta:
            registry_versions = raw_meta["_resolution_registry_versions"]

        domain_statuses = self._get_domain_statuses(slug, registry_versions)

        allow_disabled = False
        allow_degraded = True
        if context.system_policy is not None:
            allow_disabled = context.system_policy.allow_disabled
            allow_degraded = context.system_policy.allow_degraded

        return not (
            DomainStatus.DISABLED.value in domain_statuses
            and not allow_disabled
            or DomainStatus.DEGRADED.value in domain_statuses
            and not allow_degraded
        )

    def _try_fallback(
        self,
        context: DomainResolutionContext,
        candidates: list[DomainCandidateScore],
        eligible_scores: list[DomainCandidateScore],
        rejected_list: list[DomainCandidateScore],
    ) -> DomainResolutionResult | None:
        fb_candidate = self._is_fallback_eligible(context, candidates)
        if fb_candidate is None:
            return None

        return self._build_result(
            context=context,
            status=DomainResolutionStatus.INSUFFICIENT_INFORMATION,
            primary=fb_candidate.domain_id,
            rejected_domains=tuple(
                sorted((c.domain_id for c in rejected_list), key=lambda d: d.slug)
            ),
            reasons=(
                DomainResolutionReason(
                    code="DOMAIN_FALLBACK_SELECTED",
                    message=f"No specialized domain found; using fallback {fb_candidate.domain_id}",
                    domain_id=fb_candidate.domain_id,
                    contribution=0.0,
                ),
            ),
            confidence=fb_candidate.confidence,
            fallback_used=True,
            candidate_scores=tuple(candidates),
        )

    # ── Supporting domains ────────────────────────────────────────────────────

    def _select_supporting(
        self,
        eligible: list[DomainCandidateScore],
        primary: DomainId,
        primary_score: DomainCandidateScore,
        context: DomainResolutionContext,
        candidates: list[DomainCandidateScore],
    ) -> tuple[DomainId, ...]:
        p = self._policy
        max_supporting = p.max_supporting_domains

        # Determine required domains from policy
        required_slugs: set[str] = set()
        if context.system_policy is not None:
            required_slugs = {d.slug for d in context.system_policy.required_domains}

        # Collect all eligible supporting candidates
        optional_candidates: list[DomainCandidateScore] = []
        for c in eligible:
            if c.domain_id.slug == primary.slug:
                continue
            if c.rejected:
                continue
            optional_candidates.append(c)

        optional_candidates.sort(
            key=lambda c: (-c.score, -c.confidence, c.domain_id.slug)
        )

        result: list[DomainId] = []
        seen: set[str] = {primary.slug}

        # First, include all required domains (if eligible and not primary)
        required_eligible: list[DomainCandidateScore] = []
        for c in optional_candidates:
            if c.domain_id.slug in required_slugs:
                required_eligible.append(c)

        # Required domains always included (regardless of score/margin)
        for c in required_eligible:
            if c.domain_id.slug not in seen:
                seen.add(c.domain_id.slug)
                result.append(c.domain_id)

        # Choose policy for required overflow: increase supporting to fit all
        effective_max_for_optional = max(0, max_supporting - len(result))

        # Now fill remaining with optional candidates respecting limits
        for c in optional_candidates:
            if c.domain_id.slug in required_slugs:
                continue  # Already included above
            if len(result) >= max_supporting and effective_max_for_optional <= 0:
                break
            if c.score < p.minimum_resolution_score:
                continue
            if abs(c.score - primary_score.score) > p.supporting_margin:
                continue
            if c.domain_id.slug not in seen:
                seen.add(c.domain_id.slug)
                result.append(c.domain_id)
                if len(result) >= max_supporting:
                    break

        return tuple(result)

    # ── Reasons builder ────────────────────────────────────────────────────────

    def _build_resolved_reasons(
        self,
        *,
        eligible_scores: list[DomainCandidateScore],
        primary: DomainId,
        supporting_ids: set[str],
        rejected_list: list[DomainCandidateScore],
        global_reasons: tuple[DomainResolutionReason, ...],
        context: DomainResolutionContext,
    ) -> tuple[DomainResolutionReason, ...]:
        """Build ordered, deduplicated reasons for a RESOLVED result."""
        seen: set[tuple[str, str, str]] = set()
        result_reasons: list[DomainResolutionReason] = []

        def add(r: DomainResolutionReason) -> None:
            key = (
                r.code,
                str(r.domain_id) if r.domain_id else "",
                r.signal_kind or "",
            )
            if key not in seen:
                seen.add(key)
                result_reasons.append(r)

        # Blocking rejected reasons first
        for rc in rejected_list:
            for rr in rc.reasons:
                if rr.blocking:
                    add(rr)

        # Primary reasons
        for cs in eligible_scores:
            if cs.domain_id.slug == primary.slug:
                for rr in cs.reasons:
                    add(rr)
                break

        # Supporting reasons
        for cs in eligible_scores:
            if cs.domain_id.slug in supporting_ids:
                for rr in cs.reasons:
                    add(rr)

        # Global blocking reasons (not already covered)
        for gr in global_reasons:
            add(gr)

        # Sort: blocking desc, domain slug, code, signal_kind, message
        result_reasons.sort(
            key=lambda r: (
                not r.blocking,
                str(r.domain_id) if r.domain_id else "",
                r.code,
                r.signal_kind or "",
                r.message,
            )
        )

        return tuple(result_reasons)

    # ── Result construction ───────────────────────────────────────────────────

    def _build_result(
        self,
        *,
        context: DomainResolutionContext,
        status: DomainResolutionStatus,
        primary: DomainId | None = None,
        supporting_domains: tuple[DomainId, ...] = (),
        rejected_domains: tuple[DomainId, ...] = (),
        ambiguous_domains: tuple[DomainId, ...] = (),
        candidate_scores: tuple[DomainCandidateScore, ...] = (),
        reasons: tuple[DomainResolutionReason, ...] = (),
        confidence: float = 0.0,
        requires_clarification: bool = False,
        recommended_question: str | None = None,
        fallback_used: bool = False,
    ) -> DomainResolutionResult:
        # Validate clock and id_factory before constructing any result
        try:
            result_id = self._id_factory()
        except Exception as exc:
            raise DomainResolverExecutionError(
                "Domain resolution execution failed",
                details={"error_code": "ID_FACTORY_FAILED"},
            ) from exc
        if not isinstance(result_id, str) or not result_id:
            raise DomainResolverExecutionError(
                "Domain resolution execution failed",
                details={"error_code": "INVALID_ID_FACTORY_RETURN"},
            )

        try:
            resolved_time = self._clock()
        except Exception as exc:
            raise DomainResolverExecutionError(
                "Domain resolution execution failed",
                details={"error_code": "CLOCK_FAILED"},
            ) from exc
        if not isinstance(resolved_time, datetime):
            raise DomainResolverExecutionError(
                "Domain resolution execution failed",
                details={"error_code": "INVALID_CLOCK_RETURN_TYPE"},
            )
        if resolved_time.tzinfo is None:
            raise DomainResolverExecutionError(
                "Domain resolution execution failed",
                details={"error_code": "NAIVE_CLOCK_RETURN"},
            )

        requires_clar = requires_clarification
        rec_question = recommended_question

        if (
            status == DomainResolutionStatus.INSUFFICIENT_INFORMATION
            and not fallback_used
        ):
            requires_clar = True

        return DomainResolutionResult(
            id=result_id,
            context_id=context.id,
            status=status,
            primary_domain=primary,
            supporting_domains=supporting_domains,
            rejected_domains=rejected_domains,
            ambiguous_domains=ambiguous_domains,
            confidence=confidence,
            reasons=reasons,
            candidate_scores=candidate_scores,
            requires_clarification=requires_clar,
            recommended_question=rec_question,
            fallback_used=fallback_used,
            resolved_at=resolved_time,
        )

    # ── Sorting helpers ───────────────────────────────────────────────────────

    def _sort_candidates(
        self, candidates: list[DomainCandidateScore]
    ) -> list[DomainCandidateScore]:
        candidates.sort(
            key=lambda c: (
                0 if c.eligible else 1,
                -c.score if c.score == c.score else 0,
                -c.confidence if c.confidence == c.confidence else 0,
                c.domain_id.slug,
            )
        )
        return candidates

    def _sort_eligible(
        self, candidates: list[DomainCandidateScore]
    ) -> list[DomainCandidateScore]:
        candidates.sort(
            key=lambda c: (
                -c.score if c.score == c.score else 0,
                -c.confidence if c.confidence == c.confidence else 0,
                c.domain_id.slug,
            )
        )
        return candidates


__all__ = [
    "DefaultDomainResolver",
    "DomainResolver",
]
