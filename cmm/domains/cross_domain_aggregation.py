"""Phase 10.9 – Cross-Domain Aggregation Helpers.

Pure functions that merge per-domain and per-port contributions into the
final consolidated ``CrossDomainResult`` fields, and derive confidence and
status deterministically. No I/O, no registry access, no randomness.

Deduplication never keeps only the first occurrence's provenance: whenever
two items collapse into one (same question, dependency, contradiction, gap,
or finding), their provenance and — where applicable — their source domains
are unioned deterministically, preserving first-appearance order.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from cmm.domains.cross_domain_contracts import (
    CrossDomainContradiction,
    CrossDomainDependency,
    CrossDomainDomainResult,
    CrossDomainFinding,
    CrossDomainGap,
    CrossDomainPolicy,
    CrossDomainQuestion,
    CrossDomainStatus,
)
from cmm.domains.identifiers import DomainId

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

#: Explicit precedence used when consolidating repeated results for the
#: same domain (most restrictive first). "Last write wins" is never used.
DOMAIN_STATUS_PRECEDENCE: tuple[CrossDomainStatus, ...] = (
    CrossDomainStatus.FAILED,
    CrossDomainStatus.BLOCKED,
    CrossDomainStatus.REQUIRES_REVIEW,
    CrossDomainStatus.LIMIT_REACHED,
    CrossDomainStatus.PARTIAL,
    CrossDomainStatus.COMPLETED,
)
_DOMAIN_STATUS_RANK = {s: i for i, s in enumerate(DOMAIN_STATUS_PRECEDENCE)}


def _merge_str_tuples(*groups: Iterable[str]) -> tuple[str, ...]:
    """Union of string tuples, preserving first-appearance order."""
    seen: set[str] = set()
    result: list[str] = []
    for group in groups:
        for item in group:
            if item not in seen:
                seen.add(item)
                result.append(item)
    return tuple(result)


def _merge_domain_id_tuples(*groups: Iterable[DomainId]) -> tuple[DomainId, ...]:
    """Union of DomainId tuples, preserving first-appearance order."""
    seen: set[str] = set()
    result: list[DomainId] = []
    for group in groups:
        for item in group:
            if item.slug not in seen:
                seen.add(item.slug)
                result.append(item)
    return tuple(result)


def _merge_metadata(*mappings) -> dict:
    """Shallow union merge: first value seen per key wins, nothing is dropped."""
    merged: dict = {}
    for m in mappings:
        for k, v in m.items():
            if k not in merged:
                merged[k] = v
    return merged


# ── Findings ─────────────────────────────────────────────────────────────────


def merge_two_findings(
    a: CrossDomainFinding, b: CrossDomainFinding
) -> CrossDomainFinding:
    """Merge two findings sharing the same identifier.

    Source domains and provenance are unioned; ``private``/``transferable``
    take the most restrictive value across both; the first-seen ``value``
    and metadata union are preserved.
    """
    return CrossDomainFinding(
        identifier=a.identifier,
        value=a.value,
        source_domains=_merge_domain_id_tuples(a.source_domains, b.source_domains),
        provenance=_merge_str_tuples(a.provenance, b.provenance),
        private=a.private or b.private,
        transferable=a.transferable and b.transferable,
        metadata=_merge_metadata(a.metadata, b.metadata),
    )


def merge_findings(
    *groups: Iterable[CrossDomainFinding],
) -> tuple[CrossDomainFinding, ...]:
    """Merge findings by ``identifier``, unioning source domains and provenance."""
    order: list[str] = []
    merged: dict[str, CrossDomainFinding] = {}
    for group in groups:
        for f in group:
            existing = merged.get(f.identifier)
            if existing is None:
                order.append(f.identifier)
                merged[f.identifier] = f
            else:
                merged[f.identifier] = merge_two_findings(existing, f)
    return tuple(merged[i] for i in order)


# ── Recommendations (plain strings — exact-reference dedupe) ────────────────


def merge_recommendations(*groups: Iterable[str]) -> tuple[str, ...]:
    """Exact-reference dedupe across groups, preserving first-appearance order."""
    return _merge_str_tuples(*groups)


# ── Domain results ──────────────────────────────────────────────────────────


def merge_two_domain_results(
    a: CrossDomainDomainResult, b: CrossDomainDomainResult
) -> CrossDomainDomainResult:
    """Merge two attempts for the same domain, keeping everything from both.

    The consolidated status is the most restrictive of the two per
    ``DOMAIN_STATUS_PRECEDENCE`` — never "last write wins".
    """
    if a.domain_id.slug != b.domain_id.slug:
        raise ValueError("merge_two_domain_results requires the same domain_id")
    status = (
        a.status
        if _DOMAIN_STATUS_RANK[a.status] <= _DOMAIN_STATUS_RANK[b.status]
        else b.status
    )
    confidences = [c for c in (a.confidence, b.confidence) if c is not None]
    confidence = min(confidences) if confidences else None
    return CrossDomainDomainResult(
        domain_id=a.domain_id,
        status=status,
        findings=merge_findings(a.findings, b.findings),
        questions=merge_questions(a.questions, b.questions),
        dependencies=merge_dependencies(a.dependencies, b.dependencies),
        contradictions=merge_contradictions(a.contradictions, b.contradictions),
        gaps=merge_gaps(a.gaps, b.gaps),
        recommendations=merge_recommendations(a.recommendations, b.recommendations),
        operations=_merge_str_tuples(a.operations, b.operations),
        workflow_requests=_merge_str_tuples(a.workflow_requests, b.workflow_requests),
        entities=_merge_str_tuples(a.entities, b.entities),
        timelines=_merge_str_tuples(a.timelines, b.timelines),
        confidence=confidence,
        metadata=_merge_metadata(a.metadata, b.metadata),
    )


def merge_domain_results(
    results: Sequence[CrossDomainDomainResult],
) -> tuple[CrossDomainDomainResult, ...]:
    """Consolidate repeated entries for the same domain by merging, not replacing.

    Order follows the first appearance of each domain (execution order).
    """
    order: list[str] = []
    consolidated: dict[str, CrossDomainDomainResult] = {}
    for r in results:
        slug = r.domain_id.slug
        if slug not in consolidated:
            order.append(slug)
            consolidated[slug] = r
        else:
            consolidated[slug] = merge_two_domain_results(consolidated[slug], r)
    return tuple(consolidated[slug] for slug in order)


# ── Questions ────────────────────────────────────────────────────────────────


def merge_two_questions(
    a: CrossDomainQuestion, b: CrossDomainQuestion
) -> CrossDomainQuestion:
    """Merge two questions sharing the same structural identity."""
    domains = _merge_domain_id_tuples(a.requesting_domains, b.requesting_domains)
    provenance = _merge_str_tuples(a.provenance, b.provenance)
    answered = a.answered or b.answered
    answer = a.answer if a.answered else b.answer
    return CrossDomainQuestion(
        id=a.id,
        subject=a.subject,
        requested_information=a.requested_information,
        target_entity=a.target_entity,
        time_scope=a.time_scope,
        requesting_domains=domains,
        answered=answered,
        answer=answer,
        provenance=provenance,
        metadata=_merge_metadata(a.metadata, b.metadata),
    )


def merge_questions(
    *groups: Iterable[CrossDomainQuestion],
) -> tuple[CrossDomainQuestion, ...]:
    """Structural-identity dedupe, merging requesting domains and provenance."""
    order: list[tuple] = []
    merged: dict[tuple, CrossDomainQuestion] = {}
    for group in groups:
        for q in group:
            key = q.identity_key()
            existing = merged.get(key)
            merged[key] = q if existing is None else merge_two_questions(existing, q)
            if existing is None:
                order.append(key)
    return tuple(merged[k] for k in order)


# ── Dependencies ─────────────────────────────────────────────────────────────


def merge_two_dependencies(
    a: CrossDomainDependency, b: CrossDomainDependency
) -> CrossDomainDependency:
    """Merge two dependencies sharing the same structural identity."""
    return CrossDomainDependency(
        source_domain=a.source_domain,
        target_domain=a.target_domain,
        kind=a.kind,
        description=a.description,
        blocking=a.blocking,
        satisfied=a.satisfied,
        provenance=_merge_str_tuples(a.provenance, b.provenance),
        metadata=_merge_metadata(a.metadata, b.metadata),
    )


def merge_dependencies(
    *groups: Iterable[CrossDomainDependency],
) -> tuple[CrossDomainDependency, ...]:
    """Structural-key dedupe, merging provenance (never keeping only the first)."""
    order: list[tuple] = []
    merged: dict[tuple, CrossDomainDependency] = {}
    for group in groups:
        for dep in group:
            key = dep.identity_key()
            existing = merged.get(key)
            merged[key] = (
                dep if existing is None else merge_two_dependencies(existing, dep)
            )
            if existing is None:
                order.append(key)
    return tuple(sort_dependencies(merged[k] for k in order))


def sort_dependencies(
    dependencies: Iterable[CrossDomainDependency],
) -> tuple[CrossDomainDependency, ...]:
    """Deterministic order: source slug, target slug, kind, description."""
    return tuple(
        sorted(
            dependencies,
            key=lambda d: (
                d.source_domain.slug,
                d.target_domain.slug,
                d.kind,
                d.description,
            ),
        )
    )


# ── Contradictions ───────────────────────────────────────────────────────────


def merge_two_contradictions(
    a: CrossDomainContradiction, b: CrossDomainContradiction
) -> CrossDomainContradiction:
    """Merge two contradictions sharing the same structural identity."""
    resolved = a.resolved or b.resolved
    resolution = a.resolution if a.resolved else b.resolution
    return CrossDomainContradiction(
        id=a.id,
        domains=a.domains,
        subject=a.subject,
        statements=a.statements,
        severity=a.severity,
        resolved=resolved,
        resolution=resolution,
        requires_review=a.requires_review,
        provenance=_merge_str_tuples(a.provenance, b.provenance),
        metadata=_merge_metadata(a.metadata, b.metadata),
    )


def merge_contradictions(
    *groups: Iterable[CrossDomainContradiction],
) -> tuple[CrossDomainContradiction, ...]:
    """Collapse exact duplicates (per identity_key), merging provenance."""
    order: list[tuple] = []
    merged: dict[tuple, CrossDomainContradiction] = {}
    for group in groups:
        for c in group:
            key = c.identity_key()
            existing = merged.get(key)
            merged[key] = (
                c if existing is None else merge_two_contradictions(existing, c)
            )
            if existing is None:
                order.append(key)
    return tuple(sort_contradictions(merged[k] for k in order))


def sort_contradictions(
    contradictions: Iterable[CrossDomainContradiction],
) -> tuple[CrossDomainContradiction, ...]:
    """Deterministic order: unresolved-review first, severity, domains, subject, id."""
    return tuple(
        sorted(
            contradictions,
            key=lambda c: (
                not (c.requires_review and not c.resolved),
                _SEVERITY_RANK.get(c.severity.value, len(_SEVERITY_RANK)),
                tuple(sorted(d.slug for d in c.domains)),
                c.subject,
                c.id,
            ),
        )
    )


# ── Gaps ─────────────────────────────────────────────────────────────────────


def merge_two_gaps(a: CrossDomainGap, b: CrossDomainGap) -> CrossDomainGap:
    """Merge two gaps sharing the same structural identity."""
    return CrossDomainGap(
        code=a.code,
        domain_id=a.domain_id,
        description=a.description,
        required_information=a.required_information,
        blocking=a.blocking,
        recoverable=a.recoverable,
        provenance=_merge_str_tuples(a.provenance, b.provenance),
        metadata=_merge_metadata(a.metadata, b.metadata),
    )


def merge_gaps(*groups: Iterable[CrossDomainGap]) -> tuple[CrossDomainGap, ...]:
    """Structural-key dedupe across groups, merging provenance."""
    order: list[tuple] = []
    merged: dict[tuple, CrossDomainGap] = {}
    for group in groups:
        for g in group:
            key = g.identity_key()
            existing = merged.get(key)
            merged[key] = g if existing is None else merge_two_gaps(existing, g)
            if existing is None:
                order.append(key)
    return tuple(sort_gaps(merged[k] for k in order))


def sort_gaps(gaps: Iterable[CrossDomainGap]) -> tuple[CrossDomainGap, ...]:
    """Deterministic order: blocking first, domain, code, description."""
    return tuple(
        sorted(
            gaps,
            key=lambda g: (
                not g.blocking,
                g.domain_id.slug,
                g.code,
                g.description,
            ),
        )
    )


# ── Confidence ───────────────────────────────────────────────────────────────


def derive_confidence(
    domain_results: Sequence[CrossDomainDomainResult],
    policy: CrossDomainPolicy,
    *,
    unresolved_contradiction: bool,
    unresolved_gap: bool,
    skipped_required_domain: bool,
    unavailable_required_port: bool,
    limit_reached: bool,
) -> float | None:
    """Derive overall confidence as the minimum contributing confidence minus penalties.

    Only domain results that produced at least one recommendation contribute
    evidence. No bonuses are ever applied. Returns ``None`` when there is no
    supporting evidence.
    """
    contributing = [
        r.confidence
        for r in domain_results
        if r.recommendations and r.confidence is not None
    ]
    if not contributing:
        return None

    base = min(contributing)
    penalty = 0.0
    if unresolved_contradiction:
        penalty += policy.contradiction_penalty
    if unresolved_gap:
        penalty += policy.gap_penalty
    if skipped_required_domain:
        penalty += policy.skipped_required_domain_penalty
    if unavailable_required_port:
        penalty += policy.unavailable_required_port_penalty
    if limit_reached:
        penalty += policy.limit_reached_penalty

    return max(0.0, min(1.0, base - penalty))


# ── Status derivation ────────────────────────────────────────────────────────


def derive_cross_domain_status(
    *,
    is_blocked: bool,
    limit_reached: bool,
    requires_review: bool,
    has_useful_output: bool,
    all_domains_completed: bool,
) -> CrossDomainStatus:
    """Derive the final status from mutually-observable execution conditions.

    Priority (most to least specific): BLOCKED, LIMIT_REACHED,
    REQUIRES_REVIEW, COMPLETED, PARTIAL, and finally FAILED when nothing
    useful was produced at all.
    """
    if is_blocked:
        return CrossDomainStatus.BLOCKED
    if limit_reached:
        return CrossDomainStatus.LIMIT_REACHED
    if requires_review:
        return CrossDomainStatus.REQUIRES_REVIEW
    if has_useful_output and all_domains_completed:
        return CrossDomainStatus.COMPLETED
    if has_useful_output:
        return CrossDomainStatus.PARTIAL
    return CrossDomainStatus.FAILED


__all__ = [
    "DOMAIN_STATUS_PRECEDENCE",
    "derive_confidence",
    "derive_cross_domain_status",
    "merge_contradictions",
    "merge_dependencies",
    "merge_domain_results",
    "merge_findings",
    "merge_gaps",
    "merge_questions",
    "merge_recommendations",
    "merge_two_contradictions",
    "merge_two_dependencies",
    "merge_two_domain_results",
    "merge_two_findings",
    "merge_two_gaps",
    "merge_two_questions",
    "sort_contradictions",
    "sort_dependencies",
    "sort_gaps",
]
