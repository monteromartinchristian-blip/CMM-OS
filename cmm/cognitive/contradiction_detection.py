"""Phase 8.8 – Knowledge Contradiction Detection Service.

Implements deterministic, auditable, rule-based contradiction detection across KnowledgeItems.
Does NOT resolve contradictions, select true statements, or modify KnowledgeItems.
"""

from __future__ import annotations

import hashlib
import re

from cmm.cognitive.consolidation_contracts import (
    knowledge_fingerprint,
    normalize_statement,
)
from cmm.cognitive.contradiction_detection_contracts import (
    ContradictionDetection,
    ContradictionDetectionResult,
    ContradictionKind,
    ContradictionSignal,
)
from cmm.cognitive.enums import (
    ContradictionSeverity,
    ContradictionStatus,
    KnowledgeRelationKind,
    KnowledgeStatus,
    TemporalScopeKind,
    TemporalValidityStatus,
)
from cmm.cognitive.errors import (
    InvalidContradictionDetectionError,
    KnowledgeContradictionConflictError,
    KnowledgeContradictionDetectionError,
)
from cmm.cognitive.knowledge import (
    Contradiction,
    Evidence,
    KnowledgeItem,
    TemporalScope,
)
from cmm.cognitive.query import KnowledgeQuery
from cmm.cognitive.retrieval import KnowledgeRetriever
from cmm.cognitive.store_contracts import KnowledgeStoreProtocol

OPPOSITION_PAIRS: set[tuple[str, str]] = {
    ("activo", "inactivo"),
    ("válido", "inválido"),
    ("verdadero", "falso"),
    ("permitido", "prohibido"),
    ("presente", "ausente"),
    ("existe", "no existe"),
}

NEGATION_TOKENS: set[str] = {"no", "nunca", "jamás", "sin"}

MIN_CONTRADICTION_CONTEXT: float = 0.75

QUANTITY_REGEX: re.Pattern[str] = re.compile(
    r"(?P<value>-?\d+(?:[\.,]\d+)?)\s*(?P<unit>%|[a-zA-Záéíóúñ]+)?"
)


def _context_compatibility(item_a: KnowledgeItem, item_b: KnowledgeItem) -> float:
    """Calculate discrete context compatibility score between 0.0 and 1.0."""
    stmt_a = normalize_statement(item_a.statement)
    stmt_b = normalize_statement(item_b.statement)

    if stmt_a == stmt_b or knowledge_fingerprint(item_a) == knowledge_fingerprint(
        item_b
    ):
        return 1.0

    score = 0.0
    if item_a.kind == item_b.kind:
        score += 0.25

    if item_a.resource_id is not None and item_a.resource_id == item_b.resource_id:
        score += 0.25

    if item_a.actor_id is not None and item_a.actor_id == item_b.actor_id:
        score += 0.25

    words_a = set(stmt_a.split())
    words_b = set(stmt_b.split())
    common_words = words_a.intersection(words_b) - NEGATION_TOKENS
    if common_words and len(common_words) >= min(len(words_a), len(words_b)) // 2:
        score += 0.25

    if score >= 0.875:
        return 1.0
    elif score >= 0.625:
        return 0.75
    elif score >= 0.375:
        return 0.50
    elif score >= 0.125:
        return 0.25
    return 0.0


def _extract_quantities(statement: str) -> list[tuple[float, str]]:
    """Extract (value, unit) pairs from a statement."""
    results: list[tuple[float, str]] = []
    for match in QUANTITY_REGEX.finditer(statement):
        val_str = match.group("value").replace(",", ".")
        try:
            val = float(val_str)
        except ValueError:
            continue
        unit = (match.group("unit") or "").strip().casefold()
        results.append((val, unit))
    return results


def _temporal_scopes_conflict(
    scope_a: TemporalScope,
    scope_b: TemporalScope,
    item_a: KnowledgeItem,
    item_b: KnowledgeItem,
) -> tuple[bool, str]:
    """Evaluate whether two temporal scopes conflict for compatible statements."""
    if (
        (
            scope_a.validity_status == TemporalValidityStatus.VALID
            and scope_b.validity_status == TemporalValidityStatus.EXPIRED
        )
        or (
            scope_a.validity_status == TemporalValidityStatus.EXPIRED
            and scope_b.validity_status == TemporalValidityStatus.VALID
        )
    ) and _context_compatibility(item_a, item_b) >= MIN_CONTRADICTION_CONTEXT:
        return True, "One item is marked VALID while the other is marked EXPIRED"

    if (
        scope_a.kind == TemporalScopeKind.INTERVAL
        and scope_b.kind == TemporalScopeKind.INTERVAL
        and scope_a.valid_from is not None
        and scope_b.valid_from is not None
        and scope_a.valid_until is not None
        and scope_b.valid_until is not None
    ):
        latest_start = max(scope_a.valid_from, scope_b.valid_from)
        earliest_end = min(scope_a.valid_until, scope_b.valid_until)
        if latest_start <= earliest_end and (
            scope_a.validity_status != scope_b.validity_status
            or item_a.status != item_b.status
        ):
            return (
                True,
                f"Overlapping validity interval [{latest_start.isoformat()} - {earliest_end.isoformat()}] has conflicting temporal status",
            )

    return False, ""


class KnowledgeContradictionDetector:
    """Pure, deterministic detector for contradiction identification and registration."""

    def __init__(
        self,
        store: KnowledgeStoreProtocol,
        retriever: KnowledgeRetriever | None = None,
    ) -> None:
        if not isinstance(store, KnowledgeStoreProtocol):
            raise KnowledgeContradictionDetectionError(
                f"Expected KnowledgeStoreProtocol, got {type(store).__name__}"
            )
        self._store = store
        self._retriever = (
            retriever if retriever is not None else KnowledgeRetriever(store)
        )

    def compare(
        self,
        item_a: KnowledgeItem,
        item_b: KnowledgeItem,
    ) -> ContradictionDetection:
        """Compare two KnowledgeItems deterministically and produce signals."""
        if not isinstance(item_a, KnowledgeItem):
            raise InvalidContradictionDetectionError(
                f"Expected KnowledgeItem for item_a, got {type(item_a).__name__}"
            )
        if not isinstance(item_b, KnowledgeItem):
            raise InvalidContradictionDetectionError(
                f"Expected KnowledgeItem for item_b, got {type(item_b).__name__}"
            )
        if item_a.id == item_b.id:
            raise InvalidContradictionDetectionError(
                "Cannot compare a KnowledgeItem with itself"
            )

        # Canonical ordering by ID so compare(a, b) == compare(b, a)
        if item_a.id < item_b.id:
            first, second = item_a, item_b
        else:
            first, second = item_b, item_a

        signals: list[ContradictionSignal] = []
        ctx_score = _context_compatibility(first, second)

        # ── 1. Lineage contradiction ──────────────────────────────────────────
        lineage_conflict = False
        if first.supersedes_id == second.id and second.supersedes_id == first.id:
            lineage_conflict = True
            signals.append(
                ContradictionSignal(
                    kind=ContradictionKind.LINEAGE,
                    field="supersedes_id",
                    value_a=first.supersedes_id,
                    value_b=second.supersedes_id,
                    strength=1.0,
                    reason=f"Mutual supersedes cycle between {first.id} and {second.id}",
                )
            )

        if first.superseded_by_id == second.id and second.superseded_by_id == first.id:
            lineage_conflict = True
            signals.append(
                ContradictionSignal(
                    kind=ContradictionKind.LINEAGE,
                    field="superseded_by_id",
                    value_a=first.superseded_by_id,
                    value_b=second.superseded_by_id,
                    strength=1.0,
                    reason=f"Mutual superseded_by cycle between {first.id} and {second.id}",
                )
            )

        if first.supersedes_id == second.id and first.superseded_by_id == second.id:
            lineage_conflict = True
            signals.append(
                ContradictionSignal(
                    kind=ContradictionKind.LINEAGE,
                    field="supersedes_id",
                    value_a=first.supersedes_id,
                    value_b=first.superseded_by_id,
                    strength=1.0,
                    reason=f"Item {first.id} both supersedes and is superseded by {second.id}",
                )
            )

        if first.supersedes_id == second.id and first.version <= second.version:
            signals.append(
                ContradictionSignal(
                    kind=ContradictionKind.LINEAGE,
                    field="version",
                    value_a=first.version,
                    value_b=second.version,
                    strength=0.90,
                    reason=f"Item {first.id} (v{first.version}) supersedes {second.id} (v{second.version}) but has lower or equal version",
                )
            )

        # ── 2. Direct contradiction ────────────────────────────────────────────
        stmt_first = normalize_statement(first.statement)
        stmt_second = normalize_statement(second.statement)

        # ── 2. Direct contradiction ────────────────────────────────────────────
        stmt_first = normalize_statement(first.statement)
        stmt_second = normalize_statement(second.statement)

        for p1, p2 in OPPOSITION_PAIRS:
            if p1 in stmt_first and p2 in stmt_second:
                replaced = stmt_first.replace(p1, p2)
                if replaced == stmt_second or ctx_score >= MIN_CONTRADICTION_CONTEXT:
                    kind = (
                        ContradictionKind.DIRECT
                        if ctx_score >= MIN_CONTRADICTION_CONTEXT
                        else ContradictionKind.POSSIBLE
                    )
                    signals.append(
                        ContradictionSignal(
                            kind=kind,
                            field="statement",
                            value_a=first.statement,
                            value_b=second.statement,
                            strength=0.90 if kind == ContradictionKind.DIRECT else 0.60,
                            reason=f"Explicit opposition pair ('{p1}', '{p2}') in statements",
                        )
                    )
                    break
            elif p2 in stmt_first and p1 in stmt_second:
                replaced = stmt_first.replace(p2, p1)
                if replaced == stmt_second or ctx_score >= MIN_CONTRADICTION_CONTEXT:
                    kind = (
                        ContradictionKind.DIRECT
                        if ctx_score >= MIN_CONTRADICTION_CONTEXT
                        else ContradictionKind.POSSIBLE
                    )
                    signals.append(
                        ContradictionSignal(
                            kind=kind,
                            field="statement",
                            value_a=first.statement,
                            value_b=second.statement,
                            strength=0.90 if kind == ContradictionKind.DIRECT else 0.60,
                            reason=f"Explicit opposition pair ('{p2}', '{p1}') in statements",
                        )
                    )
                    break

        # ── 3. Structural negation ─────────────────────────────────────────────
        words_first = stmt_first.split()
        words_second = stmt_second.split()

        if abs(len(words_first) - len(words_second)) == 1:
            if len(words_second) == len(words_first) + 1:
                shorter, longer = words_first, words_second
            else:
                shorter, longer = words_second, words_first

            for i in range(len(longer)):
                if longer[i] in NEGATION_TOKENS:
                    reconstructed = longer[:i] + longer[i + 1 :]
                    if reconstructed == shorter:
                        kind = (
                            ContradictionKind.NEGATION
                            if ctx_score >= MIN_CONTRADICTION_CONTEXT
                            else ContradictionKind.POSSIBLE
                        )
                        signals.append(
                            ContradictionSignal(
                                kind=kind,
                                field="statement",
                                value_a=first.statement,
                                value_b=second.statement,
                                strength=0.95
                                if kind == ContradictionKind.NEGATION
                                else 0.65,
                                reason=f"Structural negation via token '{longer[i]}'",
                            )
                        )
                        break

        # ── 4. Quantitative contradiction ─────────────────────────────────────
        q_first = _extract_quantities(first.statement)
        q_second = _extract_quantities(second.statement)
        if q_first and q_second:
            for val_a, unit_a in q_first:
                for val_b, unit_b in q_second:
                    if unit_a == unit_b and val_a != val_b:
                        kind = (
                            ContradictionKind.QUANTITATIVE
                            if ctx_score >= MIN_CONTRADICTION_CONTEXT
                            else ContradictionKind.POSSIBLE
                        )
                        signals.append(
                            ContradictionSignal(
                                kind=kind,
                                field="statement",
                                value_a=f"{val_a} {unit_a}".strip(),
                                value_b=f"{val_b} {unit_b}".strip(),
                                strength=0.90
                                if kind == ContradictionKind.QUANTITATIVE
                                else 0.60,
                                reason=f"Quantitative conflict for unit '{unit_a}': {val_a} vs {val_b}",
                            )
                        )

        # ── 5. Status contradiction ────────────────────────────────────────────
        incompatible_statuses = {
            (KnowledgeStatus.ACTIVE, KnowledgeStatus.INVALIDATED),
            (KnowledgeStatus.INVALIDATED, KnowledgeStatus.ACTIVE),
            (KnowledgeStatus.ACTIVE, KnowledgeStatus.SUPERSEDED),
            (KnowledgeStatus.SUPERSEDED, KnowledgeStatus.ACTIVE),
        }
        if (first.status, second.status) in incompatible_statuses and (
            stmt_first == stmt_second or ctx_score >= MIN_CONTRADICTION_CONTEXT
        ):
            signals.append(
                ContradictionSignal(
                    kind=ContradictionKind.STATUS,
                    field="status",
                    value_a=first.status.value,
                    value_b=second.status.value,
                    strength=0.95,
                    reason=f"Incompatible status combination ({first.status.value} vs {second.status.value}) for matching statement context",
                )
            )

        # ── 6. Temporal contradiction ──────────────────────────────────────────
        temp_conflict, temp_reason = _temporal_scopes_conflict(
            first.temporal_scope, second.temporal_scope, first, second
        )
        if temp_conflict:
            signals.append(
                ContradictionSignal(
                    kind=ContradictionKind.TEMPORAL,
                    field="temporal_scope",
                    value_a=first.temporal_scope.serialize(),
                    value_b=second.temporal_scope.serialize(),
                    strength=0.90,
                    reason=temp_reason,
                )
            )

        # ── 7. Relational contradiction ────────────────────────────────────────
        for rel_a in first.relations:
            for rel_b in second.relations:
                if (
                    rel_a.source_id == rel_b.source_id
                    and rel_a.target_id == rel_b.target_id
                    and (
                        (
                            rel_a.kind == KnowledgeRelationKind.SUPPORTS
                            and rel_b.kind == KnowledgeRelationKind.CONTRADICTS
                        )
                        or (
                            rel_a.kind == KnowledgeRelationKind.CONTRADICTS
                            and rel_b.kind == KnowledgeRelationKind.SUPPORTS
                        )
                    )
                ):
                    signals.append(
                        ContradictionSignal(
                            kind=ContradictionKind.RELATIONAL,
                            field="relations",
                            value_a=rel_a.kind.value,
                            value_b=rel_b.kind.value,
                            strength=0.90,
                            reason=f"Incompatible relation kinds for pair: {rel_a.kind.value} vs {rel_b.kind.value}",
                        )
                    )

        # ── 8. Provenance conflict ─────────────────────────────────────────────
        if (
            first.resource_id != second.resource_id
            and (first.resource_id is not None and second.resource_id is not None)
            and len(signals) > 0
        ):
            signals.append(
                ContradictionSignal(
                    kind=ContradictionKind.PROVENANCE,
                    field="resource_id",
                    value_a=first.resource_id,
                    value_b=second.resource_id,
                    strength=0.50,
                    reason=f"Conflicting knowledge originates from different resources ({first.resource_id} vs {second.resource_id})",
                )
            )

        # Determine existing contradiction in store
        existing_id: str | None = None
        existing_list = self._store.list_contradictions(item_id=first.id)
        for c in existing_list:
            if (c.item_a_id == first.id and c.item_b_id == second.id) or (
                c.item_a_id == second.id and c.item_b_id == first.id
            ):
                existing_id = c.id
                break

        shared_ev_ids = tuple(
            sorted(
                {
                    e.id
                    for e in first.evidence
                    if e.id in {ev.id for ev in second.evidence}
                }
            )
        )

        is_contradiction = len(signals) > 0
        if not is_contradiction:
            return ContradictionDetection(
                item_a_id=first.id,
                item_b_id=second.id,
                is_contradiction=False,
                kind=None,
                severity=ContradictionSeverity.LOW,
                confidence=0.0,
                signals=(),
                contradicting_fields=(),
                shared_evidence_ids=shared_ev_ids,
                reasons=(),
                warnings=(),
                existing_contradiction_id=existing_id,
            )

        # Determine overall kind
        overall_kind: ContradictionKind = ContradictionKind.POSSIBLE
        if any(s.kind == ContradictionKind.LINEAGE for s in signals):
            overall_kind = ContradictionKind.LINEAGE
        elif any(s.kind == ContradictionKind.DIRECT for s in signals):
            overall_kind = ContradictionKind.DIRECT
        elif any(s.kind == ContradictionKind.NEGATION for s in signals):
            overall_kind = ContradictionKind.NEGATION
        elif any(s.kind == ContradictionKind.STATUS for s in signals):
            overall_kind = ContradictionKind.STATUS
        elif any(s.kind == ContradictionKind.RELATIONAL for s in signals):
            overall_kind = ContradictionKind.RELATIONAL
        elif any(s.kind == ContradictionKind.QUANTITATIVE for s in signals):
            overall_kind = ContradictionKind.QUANTITATIVE
        elif any(s.kind == ContradictionKind.TEMPORAL for s in signals):
            overall_kind = ContradictionKind.TEMPORAL

        # Determine overall severity
        if overall_kind == ContradictionKind.LINEAGE and lineage_conflict:
            severity = (
                ContradictionSeverity.CRITICAL
                if any("cycle" in s.reason for s in signals)
                else ContradictionSeverity.HIGH
            )
        elif overall_kind in (
            ContradictionKind.DIRECT,
            ContradictionKind.LINEAGE,
            ContradictionKind.RELATIONAL,
            ContradictionKind.QUANTITATIVE,
        ):
            severity = (
                ContradictionSeverity.HIGH
                if ctx_score >= MIN_CONTRADICTION_CONTEXT
                else ContradictionSeverity.MEDIUM
            )
        elif overall_kind in (ContradictionKind.NEGATION, ContradictionKind.STATUS):
            severity = ContradictionSeverity.MEDIUM
        else:
            severity = ContradictionSeverity.LOW

        confidence = max(s.strength for s in signals)
        contradicting_fields = tuple(sorted({s.field for s in signals}))
        reasons = tuple(s.reason for s in signals)

        return ContradictionDetection(
            item_a_id=first.id,
            item_b_id=second.id,
            is_contradiction=True,
            kind=overall_kind,
            severity=severity,
            confidence=confidence,
            signals=tuple(signals),
            contradicting_fields=contradicting_fields,
            shared_evidence_ids=shared_ev_ids,
            reasons=reasons,
            warnings=(),
            existing_contradiction_id=existing_id,
        )

    def detect(
        self,
        query: KnowledgeQuery | None = None,
        *,
        include_possible: bool = True,
    ) -> ContradictionDetectionResult:
        """Batch detect contradictions across candidate items from query or store."""
        if query is not None:
            items = self._retriever.query(query).items
        else:
            items = self._store.list_items(limit=None)

        detections: list[ContradictionDetection] = []
        n = len(items)

        for i in range(n):
            for j in range(i + 1, n):
                det = self.compare(items[i], items[j])
                if not det.is_contradiction:
                    detections.append(det)
                elif det.kind == ContradictionKind.POSSIBLE:
                    if include_possible:
                        detections.append(det)
                else:
                    detections.append(det)

        # Sort detections deterministically by item pair
        detections.sort(key=lambda d: (d.item_a_id, d.item_b_id))

        c_count = sum(
            1
            for d in detections
            if d.is_contradiction and d.kind != ContradictionKind.POSSIBLE
        )
        p_count = sum(
            1
            for d in detections
            if d.is_contradiction and d.kind == ContradictionKind.POSSIBLE
        )
        nc_count = sum(1 for d in detections if not d.is_contradiction)
        ex_count = sum(1 for d in detections if d.existing_contradiction_id is not None)

        return ContradictionDetectionResult(
            detections=tuple(detections),
            contradiction_count=c_count,
            possible_count=p_count,
            non_contradiction_count=nc_count,
            existing_count=ex_count,
            query=query,
        )

    def register(
        self,
        detection: ContradictionDetection,
        *,
        actor_id: str | None = None,
    ) -> Contradiction:
        """Register a detected contradiction explicitly in the store."""
        if not isinstance(detection, ContradictionDetection):
            raise InvalidContradictionDetectionError(
                f"Expected ContradictionDetection, got {type(detection).__name__}"
            )
        if not detection.is_contradiction:
            raise InvalidContradictionDetectionError(
                "Cannot register a non-contradiction detection"
            )

        # Deterministic SHA-256 ID from pair, kind, and fields
        kind_str = detection.kind.value if detection.kind else "none"
        fields_str = ",".join(sorted(detection.contradicting_fields))
        payload_str = (
            f"{detection.item_a_id}:{detection.item_b_id}:{kind_str}:{fields_str}"
        )
        digest = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()[:32]
        contradiction_id = f"contradiction:{digest}"

        # Check existing in store
        existing_list = self._store.list_contradictions(item_id=detection.item_a_id)
        for ex in existing_list:
            if (
                ex.item_a_id == detection.item_a_id
                and ex.item_b_id == detection.item_b_id
            ) or (
                ex.item_a_id == detection.item_b_id
                and ex.item_b_id == detection.item_a_id
            ):
                if ex.id == contradiction_id or ex.severity == detection.severity:
                    return ex
                else:
                    raise KnowledgeContradictionConflictError(
                        f"Existing contradiction for items ({detection.item_a_id}, {detection.item_b_id}) has conflicting attributes"
                    )

        # Collect and deduplicate supporting evidence from items in store
        evidence_list: list[Evidence] = []
        if self._store.contains_item(detection.item_a_id):
            item_a = self._store.get_item(detection.item_a_id)
            evidence_list.extend(item_a.evidence)

        if self._store.contains_item(detection.item_b_id):
            item_b = self._store.get_item(detection.item_b_id)
            evidence_list.extend(item_b.evidence)

        seen_ev_ids: set[str] = set()
        dedup_evidence: list[Evidence] = []
        for ev in evidence_list:
            if ev.id not in seen_ev_ids:
                seen_ev_ids.add(ev.id)
                dedup_evidence.append(ev)

        contradiction = Contradiction(
            id=contradiction_id,
            item_a_id=detection.item_a_id,
            item_b_id=detection.item_b_id,
            severity=detection.severity,
            status=ContradictionStatus.UNRESOLVED,
            supporting_evidence=tuple(dedup_evidence),
            explanation="; ".join(detection.reasons),
            preferred_id=None,
            preference_reason=None,
            remaining_uncertainty=None,
            actor_id=actor_id,
            metadata={
                "detection_kind": kind_str,
                "detection_confidence": detection.confidence,
                "signals": [s.serialize() for s in detection.signals],
                "contradicting_fields": list(detection.contradicting_fields),
            },
        )

        return self._store.save_contradiction(contradiction)

    def detect_and_register(
        self,
        query: KnowledgeQuery | None = None,
        *,
        include_possible: bool = False,
        actor_id: str | None = None,
    ) -> tuple[Contradiction, ...]:
        """Detect and register all valid contradictions for items matching query."""
        batch_result = self.detect(query, include_possible=include_possible)
        registered: list[Contradiction] = []

        for det in batch_result.detections:
            if not det.is_contradiction:
                continue
            if det.kind == ContradictionKind.POSSIBLE and not include_possible:
                continue
            registered.append(self.register(det, actor_id=actor_id))

        return tuple(registered)
