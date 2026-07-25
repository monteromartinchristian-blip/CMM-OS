"""Phase 8.4 – Knowledge Materializer.

Pure, stateless conversion layer that promotes Phase 8.3 extraction
contracts into Phase 8.4 Knowledge Model contracts.

No persistence, no reasoning, no automatic fact promotion.
All provenance, confidence, actor, and timestamps are preserved verbatim.

Public surface
--------------
materialise_candidate(candidate, *, actor_id, resource_provenance_id) -> KnowledgeItem
materialise_evidence(extraction_evidence, fragment, confidence) -> Evidence
materialise_result(extraction_result, *, actor_id) -> KnowledgeBundle
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cmm.cognitive.contracts import Confidence
from cmm.cognitive.enums import (
    CandidateKind,
    ContradictionStatus,
    EvidenceKind,
    EvidencePolarityKind,
    KnowledgeKind,
    KnowledgeStatus,
    TemporalScopeKind,
)
from cmm.cognitive.extraction import (
    ExtractionCandidate,
    ExtractionEvidence,
    KnowledgeExtractionResult,
)
from cmm.cognitive.knowledge import (
    Evidence,
    KnowledgeBundle,
    KnowledgeItem,
    TemporalScope,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ── CandidateKind → KnowledgeKind mapping ─────────────────────────────────────

_CANDIDATE_TO_KNOWLEDGE_KIND: dict[CandidateKind, KnowledgeKind] = {
    CandidateKind.STATEMENT: KnowledgeKind.FACT,
    CandidateKind.ENTITY_MENTION: KnowledgeKind.OBSERVATION,
    CandidateKind.RELATIONSHIP_MENTION: KnowledgeKind.INFERENCE,
    CandidateKind.TEMPORAL_REFERENCE: KnowledgeKind.OBSERVATION,
    CandidateKind.QUANTITY: KnowledgeKind.OBSERVATION,
    CandidateKind.KEYWORD: KnowledgeKind.OBSERVATION,
    CandidateKind.QUESTION: KnowledgeKind.QUESTION,
    CandidateKind.UNKNOWN: KnowledgeKind.HYPOTHESIS,
}


def _candidate_kind_to_knowledge_kind(kind: CandidateKind) -> KnowledgeKind:
    """Map an extraction CandidateKind to a KnowledgeKind.

    STATEMENT candidates become FACT; QUESTION becomes QUESTION.
    All others default to OBSERVATION or INFERENCE, never FACT, to
    avoid auto-promotion of unverified content.
    """
    return _CANDIDATE_TO_KNOWLEDGE_KIND.get(kind, KnowledgeKind.HYPOTHESIS)


# ── Evidence materialisation ──────────────────────────────────────────────────


def materialise_evidence(
    extraction_evidence: ExtractionEvidence,
    *,
    confidence: Confidence,
    actor_id: str | None = None,
    extraction_candidate_id: str | None = None,
    resource_provenance_id: str | None = None,
    observed_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> Evidence:
    """Convert an :class:`ExtractionEvidence` into a Knowledge Model :class:`Evidence`.

    Preserves all localisation fields (start/end, section, page) and adds
    traceability links back to the extraction candidate and resource provenance.
    """
    return Evidence(
        resource_id=extraction_evidence.resource_id,
        fragment=extraction_evidence.fragment
        if extraction_evidence.fragment.strip()
        else "(extracted)",
        confidence=confidence,
        kind=EvidenceKind.EXTRACTION_CANDIDATE,
        polarity=EvidencePolarityKind.SUPPORTING,
        locator=extraction_evidence.selector,
        section=extraction_evidence.section,
        page=extraction_evidence.page,
        char_start=extraction_evidence.start,
        char_end=extraction_evidence.end,
        actor_id=actor_id,
        extraction_candidate_id=extraction_candidate_id,
        resource_provenance_id=resource_provenance_id,
        observed_at=observed_at or _utc_now(),
        metadata=dict(metadata or {}),
    )


# ── Candidate materialisation ─────────────────────────────────────────────────


def materialise_candidate(
    candidate: ExtractionCandidate,
    *,
    actor_id: str | None = None,
    resource_provenance_id: str | None = None,
    observed_at: datetime | None = None,
) -> KnowledgeItem:
    """Promote an :class:`ExtractionCandidate` to a :class:`KnowledgeItem`.

    The resulting item is always UNVERIFIED: no automatic fact promotion.
    Confidence, actor, resource_id, and candidate id are preserved verbatim.
    """
    ts = observed_at or _utc_now()

    ev = materialise_evidence(
        candidate.evidence,
        confidence=candidate.confidence,
        actor_id=actor_id or candidate.extractor_name,
        extraction_candidate_id=candidate.id,
        resource_provenance_id=resource_provenance_id,
        observed_at=ts,
        metadata=dict(candidate.metadata),
    )

    # Value may be a string, number, or mapping — serialise to str for statement
    statement = (
        str(candidate.value).strip()
        if candidate.value is not None
        else "(no statement)"
    )
    if not statement:
        statement = "(empty value)"

    return KnowledgeItem(
        statement=statement,
        kind=_candidate_kind_to_knowledge_kind(candidate.kind),
        confidence=candidate.confidence,
        status=KnowledgeStatus.UNVERIFIED,
        evidence=(ev,),
        temporal_scope=TemporalScope(kind=TemporalScopeKind.UNKNOWN),
        actor_id=actor_id or candidate.extractor_name,
        resource_id=candidate.resource_id,
        created_at=ts,
        updated_at=ts,
        metadata={
            "extractor_name": candidate.extractor_name,
            "candidate_id": candidate.id,
            "labels": list(candidate.labels),
            **dict(candidate.metadata),
        },
    )


# ── Result materialisation ────────────────────────────────────────────────────


def materialise_result(
    extraction_result: KnowledgeExtractionResult,
    *,
    actor_id: str | None = None,
    resource_provenance_id: str | None = None,
) -> KnowledgeBundle:
    """Convert a full :class:`KnowledgeExtractionResult` into a :class:`KnowledgeBundle`.

    Each candidate becomes a KnowledgeItem (UNVERIFIED).
    Open questions (QUESTION candidates) are surfaced as open_questions strings.
    Extraction warnings become findings.
    No contradictions are inferred automatically.
    """
    observed_at = extraction_result.created_at

    items: list[KnowledgeItem] = []
    open_questions: list[str] = []

    for candidate in extraction_result.candidates:
        item = materialise_candidate(
            candidate,
            actor_id=actor_id,
            resource_provenance_id=resource_provenance_id,
            observed_at=observed_at,
        )
        items.append(item)
        if candidate.kind is CandidateKind.QUESTION:
            open_questions.append(str(candidate.value))

    findings = list(extraction_result.warnings)
    if extraction_result.errors:
        findings.extend(f"[error] {e}" for e in extraction_result.errors)

    bundle_status = extraction_result.status.value

    return KnowledgeBundle(
        items=tuple(items),
        open_questions=tuple(open_questions),
        findings=tuple(findings),
        actor_id=actor_id,
        status=bundle_status,
        created_at=observed_at,
        metadata={
            "extraction_result_id": extraction_result.id,
            "extractor_name": extraction_result.extractor_name,
            "extractor_version": extraction_result.extractor_version,
            "resource_id": extraction_result.resource_id,
            "extraction_status": extraction_result.status.value,
            "candidate_count": extraction_result.candidate_count,
            "truncated": extraction_result.truncated,
        },
    )
