"""Phase 10.7 – Domain Candidate Scorer.

Stateless, deterministic scoring of domain candidates from a
``DomainResolutionContext``.  No live registry, no LLM, no network,
no filesystem.

The scorer consumes only structured evidence already present in the
context — never scans free text or metadata for keyword matches.
"""

from __future__ import annotations

import json
import math

from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
)
from cmm.domains.resolver_contracts import (
    DomainCandidateScore,
    DomainResolutionReason,
    DomainScoringPolicy,
)

# ── Signal kind → policy weight mapping ─────────────────────────────────────────

_SIGNAL_KIND_WEIGHT_MAP: dict[str, str] = {
    "explicit": "explicit_weight",
    "resource": "resource_weight",
    "entity": "entity_weight",
    "intent": "intent_weight",
    "objective": "objective_weight",
    "operation": "operation_weight",
    "workflow": "workflow_weight",
    "session": "session_weight",
    "goal": "goal_weight",
    "profile": "profile_weight",
    "knowledge": "knowledge_weight",
    "history": "history_weight",
    "event": "event_weight",
    "user_preference": "user_preference_weight",
    "system_policy": "system_policy_weight",
}

# ── Code templates per evidence category ────────────────────────────────────────

_SIGNAL_CODE_MAP: dict[str, str] = {
    "explicit": "DOMAIN_EXPLICIT_MATCH",
    "resource": "DOMAIN_RESOURCE_MATCH",
    "entity": "DOMAIN_ENTITY_MATCH",
    "intent": "DOMAIN_INTENT_MATCH",
    "objective": "DOMAIN_OBJECTIVE_MATCH",
    "operation": "DOMAIN_OPERATION_MATCH",
    "workflow": "DOMAIN_WORKFLOW_MATCH",
    "session": "DOMAIN_SESSION_MATCH",
    "goal": "DOMAIN_GOAL_MATCH",
    "profile": "DOMAIN_PROFILE_MATCH",
    "knowledge": "DOMAIN_KNOWLEDGE_MATCH",
    "history": "DOMAIN_HISTORY_MATCH",
    "event": "DOMAIN_EVENT_MATCH",
    "user_preference": "DOMAIN_USER_PREFERENCE_MATCH",
    "system_policy": "DOMAIN_SYSTEM_POLICY_MATCH",
}

# ── Stable JSON canonical helpers ───────────────────────────────────────────────


def _json_canonical(value: object) -> str:
    """Produce a stable, canonical JSON representation for deduplication."""
    if isinstance(value, (str, int, float)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, bool):
        return json.dumps(value)
    if value is None:
        return "null"
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return repr(value)


def _provenance_canonical(provenance: object) -> str:
    """Produce a stable representation of provenance metadata."""
    if provenance is None:
        return "null"
    try:
        if hasattr(provenance, "items"):
            return json.dumps(dict(provenance), sort_keys=True, separators=(",", ":"))
        return json.dumps(provenance, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return repr(provenance)


class DomainCandidateScorer:
    """Stateless scorer that evaluates a single candidate domain against the context.

    Only uses structured evidence present in the context.  Never scans free
    text, never accesses the registry, never mutates state.
    """

    def __init__(
        self,
        *,
        policy: DomainScoringPolicy | None = None,
    ) -> None:
        self._policy: DomainScoringPolicy = policy or DomainScoringPolicy()

    @property
    def policy(self) -> DomainScoringPolicy:
        """The scoring policy in use (immutable)."""
        return self._policy

    def score(
        self,
        context: DomainResolutionContext,
        domain_id: DomainId,
    ) -> DomainCandidateScore:
        """Produce a ``DomainCandidateScore`` for a single candidate.

        Args:
            context: The resolution context (immutable snapshot).
            domain_id: The candidate domain to score.

        Returns:
            A complete ``DomainCandidateScore`` with score, confidence,
            eligibility, reasons, and matched signal kinds.

        Raises:
            TypeError: If ``context`` is not a ``DomainResolutionContext``.
        """
        if not isinstance(context, DomainResolutionContext):
            raise TypeError(
                f"context must be a DomainResolutionContext, got {type(context).__name__}"
            )

        domain_slug = domain_id.slug
        reasons: list[DomainResolutionReason] = []
        total_score: float = 0.0
        matched_kinds: list[str] = []

        # ── 1. Explicit domains (highest weight) ──────────────────────────────
        explicit_score = self._score_explicit(context, domain_id)
        if explicit_score is not None:
            total_score += explicit_score
            matched_kinds.append("explicit")
            reasons.append(
                DomainResolutionReason(
                    code="DOMAIN_EXPLICIT_MATCH",
                    message=f"Domain {domain_id} explicitly requested",
                    domain_id=domain_id,
                    signal_kind="explicit",
                    contribution=explicit_score,
                )
            )

        # ── 2. Resources ──────────────────────────────────────────────────────
        resource_contrib = self._score_resources(context, domain_id)
        if resource_contrib > 0:
            total_score += resource_contrib
            matched_kinds.append("resource")
            reasons.append(
                DomainResolutionReason(
                    code="DOMAIN_RESOURCE_MATCH",
                    message=f"Resource evidence for {domain_id}",
                    domain_id=domain_id,
                    signal_kind="resource",
                    contribution=resource_contrib,
                )
            )

        # ── 3. Entities ───────────────────────────────────────────────────────
        entity_contrib = self._score_entities(context, domain_id)
        if entity_contrib > 0:
            total_score += entity_contrib
            matched_kinds.append("entity")
            reasons.append(
                DomainResolutionReason(
                    code="DOMAIN_ENTITY_MATCH",
                    message=f"Entity evidence for {domain_id}",
                    domain_id=domain_id,
                    signal_kind="entity",
                    contribution=entity_contrib,
                )
            )

        # ── 4. Knowledge items ────────────────────────────────────────────────
        knowledge_contrib = self._score_knowledge(context, domain_id)
        if knowledge_contrib > 0:
            total_score += knowledge_contrib
            matched_kinds.append("knowledge")
            reasons.append(
                DomainResolutionReason(
                    code="DOMAIN_KNOWLEDGE_MATCH",
                    message=f"Knowledge evidence for {domain_id}",
                    domain_id=domain_id,
                    signal_kind="knowledge",
                    contribution=knowledge_contrib,
                )
            )

        # ── 5. Generic signals ────────────────────────────────────────────────
        signal_contrib = self._score_signals(context, domain_id, reasons)
        if signal_contrib > 0:
            total_score += signal_contrib

        # ── 6. Active bonus ───────────────────────────────────────────────────
        if domain_slug in {d.slug for d in context.active_domains}:
            total_score += self._policy.active_bonus
            reasons.append(
                DomainResolutionReason(
                    code="DOMAIN_ACTIVE_BONUS",
                    message=f"Domain {domain_id} is currently active",
                    domain_id=domain_id,
                    signal_kind="session",
                    contribution=self._policy.active_bonus,
                )
            )

        # ── 7. History match ──────────────────────────────────────────────────
        history_contrib = self._score_history(context, domain_id)
        if history_contrib > 0:
            total_score += history_contrib
            matched_kinds.append("history")
            reasons.append(
                DomainResolutionReason(
                    code="DOMAIN_HISTORY_MATCH",
                    message=f"Recent history evidence for {domain_id}",
                    domain_id=domain_id,
                    signal_kind="history",
                    contribution=history_contrib,
                )
            )

        # ── 8. Compute confidence ─────────────────────────────────────────────
        confidence = self._compute_confidence(total_score)

        # ── 9. Build result ─────────────────────────────────────────────────
        all_kinds: list[str] = []
        seen_kinds: set[str] = set()
        for r in reasons:
            if r.signal_kind and r.signal_kind not in seen_kinds:
                seen_kinds.add(r.signal_kind)
                all_kinds.append(r.signal_kind)
        for mk in matched_kinds:
            if mk not in seen_kinds:
                seen_kinds.add(mk)
                all_kinds.append(mk)

        return DomainCandidateScore(
            domain_id=domain_id,
            score=total_score,
            confidence=confidence,
            eligible=True,
            rejected=False,
            reasons=tuple(reasons),
            matched_signal_kinds=tuple(all_kinds),
        )

    # ── Evidence scoring methods ───────────────────────────────────────────────

    def _score_explicit(
        self, context: DomainResolutionContext, domain_id: DomainId
    ) -> float | None:
        """Return explicit match score or None if not explicit."""
        domain_slug = domain_id.slug
        for ed in context.explicit_domains:
            if ed.slug == domain_slug:
                return self._policy.explicit_weight
        return None

    def _score_resources(
        self, context: DomainResolutionContext, domain_id: DomainId
    ) -> float:
        """Score from resource domain_ids references.

        Semantic deduplication key: (id, resource_type, source, domain).
        """
        domain_slug = domain_id.slug
        contrib = 0.0
        seen: set[tuple[str, str, str, str]] = set()
        for resource in context.resources:
            for rd in resource.domain_ids:
                if rd.slug == domain_slug:
                    dedup_key = (
                        resource.id,
                        resource.resource_type,
                        resource.source,
                        domain_slug,
                    )
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)
                    contrib += self._policy.resource_weight
        return contrib

    def _score_entities(
        self, context: DomainResolutionContext, domain_id: DomainId
    ) -> float:
        """Score from entity domain_ids and confidence.

        Semantic deduplication key: (id, entity_type, source, domain).
        """
        domain_slug = domain_id.slug
        contrib = 0.0
        seen: set[tuple[str, str, str, str]] = set()
        for entity in context.entities:
            for ed in entity.domain_ids:
                if ed.slug == domain_slug:
                    dedup_key = (
                        entity.id,
                        entity.entity_type,
                        entity.source,
                        domain_slug,
                    )
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)
                    factor = entity.confidence if entity.confidence is not None else 1.0
                    contrib += self._policy.entity_weight * factor
        return contrib

    def _score_knowledge(
        self, context: DomainResolutionContext, domain_id: DomainId
    ) -> float:
        """Score from knowledge item domain_ids and relevance.

        Semantic deduplication key: (id, knowledge_type, source, domain).
        """
        domain_slug = domain_id.slug
        contrib = 0.0
        seen: set[tuple[str, str, str, str]] = set()
        for ki in context.knowledge_items:
            for kd in ki.domain_ids:
                if kd.slug == domain_slug:
                    dedup_key = (
                        ki.id,
                        ki.knowledge_type,
                        ki.source,
                        domain_slug,
                    )
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)
                    factor = ki.relevance if ki.relevance is not None else 1.0
                    contrib += self._policy.knowledge_weight * factor
        return contrib

    def _score_history(
        self, context: DomainResolutionContext, domain_id: DomainId
    ) -> float:
        """Score from recent history domain_ids.

        Semantic deduplication key: (id, item_type, timestamp, domain).
        """
        domain_slug = domain_id.slug
        contrib = 0.0
        seen: set[tuple[str, str, str, str]] = set()
        for hi in context.recent_history:
            for hd in hi.domain_ids:
                if hd.slug == domain_slug:
                    ts_str = hi.timestamp.isoformat() if hi.timestamp else ""
                    dedup_key = (
                        hi.id,
                        hi.item_type,
                        ts_str,
                        domain_slug,
                    )
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)
                    contrib += self._policy.history_weight
        return contrib

    def _score_signals(
        self,
        context: DomainResolutionContext,
        domain_id: DomainId,
        reasons: list[DomainResolutionReason],
    ) -> float:
        """Score from generic ``DomainResolutionSignal`` entries.

        Semantic deduplication key includes:
            kind, source, domain, value canonical JSON, confidence,
            weight, observed_at, provenance canonical.
        """
        domain_slug = domain_id.slug
        contrib = 0.0
        seen_evidence: set[tuple[str, str, str, str, str, str, str, str]] = set()
        for signal in context.signals:
            for sd in signal.domain_ids:
                if sd.slug != domain_slug:
                    continue

                value_canon = _json_canonical(signal.value)
                confidence_str = (
                    _json_canonical(signal.confidence)
                    if signal.confidence is not None
                    else "null"
                )
                weight_str = (
                    _json_canonical(signal.weight)
                    if signal.weight is not None
                    else "null"
                )
                observed_str = (
                    signal.observed_at.isoformat()
                    if signal.observed_at is not None
                    else "null"
                )
                prov_canon = _provenance_canonical(signal.provenance)

                evidence_key = (
                    signal.kind,
                    signal.source,
                    domain_slug,
                    value_canon,
                    confidence_str,
                    weight_str,
                    observed_str,
                    prov_canon,
                )
                if evidence_key in seen_evidence:
                    continue
                seen_evidence.add(evidence_key)

                weight_attr = _SIGNAL_KIND_WEIGHT_MAP.get(signal.kind)
                if weight_attr is None:
                    continue
                category_weight = getattr(self._policy, weight_attr, 0.0)
                signal_conf = (
                    signal.confidence if signal.confidence is not None else 1.0
                )
                signal_weight = signal.weight if signal.weight is not None else 1.0
                signal_weight = min(signal_weight, 100.0)
                signal_contrib = category_weight * signal_conf * signal_weight
                signal_contrib = min(signal_contrib, category_weight * 10.0)
                contrib += signal_contrib
                code = _SIGNAL_CODE_MAP.get(
                    signal.kind, f"DOMAIN_{signal.kind.upper()}_MATCH"
                )
                reasons.append(
                    DomainResolutionReason(
                        code=code,
                        message=f"Signal {signal.kind} from {signal.source} matched {domain_id}",
                        domain_id=domain_id,
                        signal_kind=signal.kind,
                        contribution=signal_contrib,
                    )
                )
                break  # One reason per signal

        return contrib

    # ── Confidence calculation ─────────────────────────────────────────────────

    def _compute_confidence(self, score: float) -> float:
        """Compute confidence from score using a monotonic saturated function.

        Uses::
            confidence = 1.0 - exp(-max(score, 0.0) / scale)

        This ensures confidence is always in [0, 1] and increases
        monotonically with score, saturating asymptotically at 1.0.
        """
        effective = max(score, 0.0)
        scale = self._policy.confidence_scale
        if scale <= 0.0:
            scale = 1.0
        return 1.0 - math.exp(-effective / scale)


__all__ = [
    "DomainCandidateScorer",
]
