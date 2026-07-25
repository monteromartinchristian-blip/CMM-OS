"""Phase 8.8 – Knowledge Contradiction Detection Service.

Implements deterministic, auditable, rule-based contradiction detection across KnowledgeItems.
Does NOT resolve contradictions, select true statements, or modify KnowledgeItems.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

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

OPPOSITION_PAIRS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("activo",), ("inactivo",)),
    (("válido",), ("inválido",)),
    (("verdadero",), ("falso",)),
    (("permitido",), ("prohibido",)),
    (("presente",), ("ausente",)),
    (("existe",), ("no", "existe")),
)

NEGATION_TOKENS: set[str] = {"no", "nunca", "jamás", "sin"}

NEGATION_EXCLUSIONS: set[tuple[str, ...]] = {
    ("no", "solo"),
    ("no", "obstante"),
    ("sin", "embargo"),
}

MIN_CONTRADICTION_CONTEXT: float = 0.75

WORD_REGEX: re.Pattern[str] = re.compile(r"\b[\wáéíóúüñ]+\b", re.UNICODE)

QUANTITY_REGEX: re.Pattern[str] = re.compile(
    r"(?P<value>-?\d+(?:[\.,]\d+)?)\s*(?P<unit>%|[a-zA-Záéíóúüñ]+)?"
)


@dataclass(frozen=True, slots=True)
class _ExtractedQuantity:
    value: float
    unit: str
    prefix_tokens: tuple[str, ...]
    statement_mask: tuple[str, ...]


def _tokenize(text: str) -> tuple[str, ...]:
    """Extract normalized word tokens from text."""
    normalized = normalize_statement(text)
    return tuple(WORD_REGEX.findall(normalized))


def _contains_token_sequence(
    tokens: tuple[str, ...],
    sequence: tuple[str, ...],
) -> bool:
    """Check if a sequence of tokens appears as a contiguous subsequence within tokens."""
    if not sequence or len(sequence) > len(tokens):
        return False
    seq_len = len(sequence)
    for i in range(len(tokens) - seq_len + 1):
        if tokens[i : i + seq_len] == sequence:
            return True
    return False


def _substitute_token_sequence(
    tokens: tuple[str, ...],
    target: tuple[str, ...],
    replacement: tuple[str, ...],
) -> tuple[str, ...] | None:
    """Replace target token sequence with replacement sequence if present."""
    if not _contains_token_sequence(tokens, target):
        return None
    seq_len = len(target)
    for i in range(len(tokens) - seq_len + 1):
        if tokens[i : i + seq_len] == target:
            return tokens[:i] + replacement + tokens[i + seq_len :]
    return None


def _context_compatibility(item_a: KnowledgeItem, item_b: KnowledgeItem) -> float:
    """Calculate discrete context compatibility score between 0.0 and 1.0."""
    stmt_a = normalize_statement(item_a.statement)
    stmt_b = normalize_statement(item_b.statement)

    if stmt_a == stmt_b or knowledge_fingerprint(item_a) == knowledge_fingerprint(
        item_b
    ):
        return 1.0

    tokens_a = set(_tokenize(item_a.statement))
    tokens_b = set(_tokenize(item_b.statement))

    score = 0.0
    if item_a.kind == item_b.kind:
        score += 0.25

    if item_a.resource_id == item_b.resource_id:
        score += 0.25

    if item_a.actor_id == item_b.actor_id:
        score += 0.25

    common_tokens = (tokens_a.intersection(tokens_b)) - NEGATION_TOKENS
    min_tokens_len = max(1, min(len(tokens_a), len(tokens_b)))
    overlap_ratio = len(common_tokens) / min_tokens_len

    if overlap_ratio >= 0.70:
        score += 0.50
    elif overlap_ratio >= 0.40:
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


def _extract_quantities(statement: str) -> list[_ExtractedQuantity]:
    """Extract contextual quantities from a statement."""
    tokens = _tokenize(statement)
    results: list[_ExtractedQuantity] = []

    for match in QUANTITY_REGEX.finditer(statement):
        val_str = match.group("value").replace(",", ".")
        try:
            val = float(val_str)
        except ValueError:
            continue
        unit = (match.group("unit") or "").strip().casefold()

        raw_num = match.group("value").casefold()
        idx = -1
        for i, t in enumerate(tokens):
            if t == raw_num or t.replace(",", ".") == val_str:
                idx = i
                break

        prefix = tokens[max(0, idx - 3) : idx] if idx >= 0 else ()
        mask = list(tokens)
        if idx >= 0:
            mask[idx] = "<quantity>"
            if idx + 1 < len(mask) and mask[idx + 1] == unit:
                mask.pop(idx + 1)

        results.append(
            _ExtractedQuantity(
                value=val,
                unit=unit,
                prefix_tokens=prefix,
                statement_mask=tuple(mask),
            )
        )
    return results


def _temporal_scopes_conflict(
    scope_a: TemporalScope,
    scope_b: TemporalScope,
    item_a: KnowledgeItem,
    item_b: KnowledgeItem,
) -> tuple[bool, str]:
    """Evaluate whether two temporal scopes conflict for compatible statements."""
    if scope_a.kind in (
        TemporalScopeKind.UNKNOWN,
        TemporalScopeKind.TIMELESS,
    ) or scope_b.kind in (TemporalScopeKind.UNKNOWN, TemporalScopeKind.TIMELESS):
        return False, ""

    if (
        scope_a.kind == TemporalScopeKind.POINT_IN_TIME
        and scope_b.kind == TemporalScopeKind.POINT_IN_TIME
        and scope_a.observed_at is not None
        and scope_a.observed_at == scope_b.observed_at
        and (
            scope_a.validity_status != scope_b.validity_status
            or item_a.status != item_b.status
        )
    ):
        return (
            True,
            f"Identical point in time ({scope_a.observed_at.isoformat()}) has conflicting status",
        )

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


def _merge_detection_evidence(
    item_a: KnowledgeItem | None,
    item_b: KnowledgeItem | None,
) -> tuple[Evidence, ...]:
    """Merge evidence from item_a and item_b, checking for evidence payload conflicts."""
    ev_map: dict[str, Evidence] = {}
    items = [it for it in (item_a, item_b) if it is not None]

    for item in items:
        for ev in item.evidence:
            if ev.id in ev_map:
                existing = ev_map[ev.id]
                if existing.serialize() != ev.serialize():
                    raise KnowledgeContradictionConflictError(
                        f"Conflicting Evidence payload for evidence_id '{ev.id}'"
                    )
            else:
                ev_map[ev.id] = ev

    return tuple(sorted(ev_map.values(), key=lambda e: e.id))


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

        tokens_first = _tokenize(first.statement)
        tokens_second = _tokenize(second.statement)

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

        # ── 2. Direct contradiction (Token-sequence matching) ─────────────────
        for seq1, seq2 in OPPOSITION_PAIRS:
            match_forward = _contains_token_sequence(
                tokens_first, seq1
            ) and _contains_token_sequence(tokens_second, seq2)
            match_reverse = _contains_token_sequence(
                tokens_first, seq2
            ) and _contains_token_sequence(tokens_second, seq1)

            if match_forward:
                subst = _substitute_token_sequence(tokens_first, seq1, seq2)
                if (
                    subst is not None and subst == tokens_second
                ) or ctx_score >= MIN_CONTRADICTION_CONTEXT:
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
                            reason=f"Explicit token opposition sequence ({' '.join(seq1)}, {' '.join(seq2)}) in statements",
                        )
                    )
                    break
            elif match_reverse:
                subst = _substitute_token_sequence(tokens_first, seq2, seq1)
                if (
                    subst is not None and subst == tokens_second
                ) or ctx_score >= MIN_CONTRADICTION_CONTEXT:
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
                            reason=f"Explicit token opposition sequence ({' '.join(seq2)}, {' '.join(seq1)}) in statements",
                        )
                    )
                    break

        # ── 3. Structural negation (Token-level with exclusions) ──────────────
        if abs(len(tokens_first) - len(tokens_second)) == 1:
            shorter_tokens, longer_tokens = (
                (tokens_first, tokens_second)
                if len(tokens_first) < len(tokens_second)
                else (tokens_second, tokens_first)
            )

            for i in range(len(longer_tokens)):
                token = longer_tokens[i]
                if token in NEGATION_TOKENS:
                    # Check exclusions
                    is_excluded = False
                    if (
                        i + 1 < len(longer_tokens)
                        and (
                            token,
                            longer_tokens[i + 1],
                        )
                        in NEGATION_EXCLUSIONS
                    ) or (
                        i > 0
                        and (
                            longer_tokens[i - 1],
                            token,
                        )
                        in NEGATION_EXCLUSIONS
                    ):
                        is_excluded = True

                    if not is_excluded:
                        reconstructed = longer_tokens[:i] + longer_tokens[i + 1 :]
                        if reconstructed == shorter_tokens:
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
                                    reason=f"Structural negation via token '{token}'",
                                )
                            )
                            break

        # ── 4. Quantitative contradiction (Context-aware) ─────────────────────
        q_first = _extract_quantities(first.statement)
        q_second = _extract_quantities(second.statement)
        if q_first and q_second:
            for q1 in q_first:
                for q2 in q_second:
                    if q1.unit == q2.unit and q1.value != q2.value:
                        matching_context = (
                            q1.statement_mask == q2.statement_mask
                            or q1.prefix_tokens == q2.prefix_tokens
                        )
                        if matching_context and ctx_score >= MIN_CONTRADICTION_CONTEXT:
                            signals.append(
                                ContradictionSignal(
                                    kind=ContradictionKind.QUANTITATIVE,
                                    field="statement",
                                    value_a=f"{q1.value} {q1.unit}".strip(),
                                    value_b=f"{q2.value} {q2.unit}".strip(),
                                    strength=0.90,
                                    reason=f"Quantitative conflict for unit '{q1.unit}': {q1.value} vs {q2.value}",
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
            tokens_first == tokens_second or ctx_score >= MIN_CONTRADICTION_CONTEXT
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

        # Sort signals deterministically by kind, field, and reason
        signals.sort(key=lambda s: (s.kind.value, s.field, s.reason))

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
        elif any(s.kind == ContradictionKind.TEMPORAL for s in signals):
            overall_kind = ContradictionKind.TEMPORAL
        elif any(s.kind == ContradictionKind.STATUS for s in signals):
            overall_kind = ContradictionKind.STATUS
        elif any(s.kind == ContradictionKind.RELATIONAL for s in signals):
            overall_kind = ContradictionKind.RELATIONAL
        elif any(s.kind == ContradictionKind.QUANTITATIVE for s in signals):
            overall_kind = ContradictionKind.QUANTITATIVE

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
        allow_possible: bool = False,
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

        if detection.kind == ContradictionKind.POSSIBLE and not allow_possible:
            raise InvalidContradictionDetectionError(
                "Cannot register a POSSIBLE contradiction"
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
        item_a = (
            self._store.get_item(detection.item_a_id)
            if self._store.contains_item(detection.item_a_id)
            else None
        )
        item_b = (
            self._store.get_item(detection.item_b_id)
            if self._store.contains_item(detection.item_b_id)
            else None
        )
        dedup_evidence = _merge_detection_evidence(item_a, item_b)

        contradiction = Contradiction(
            id=contradiction_id,
            item_a_id=detection.item_a_id,
            item_b_id=detection.item_b_id,
            severity=detection.severity,
            status=ContradictionStatus.UNRESOLVED,
            supporting_evidence=dedup_evidence,
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
            registered.append(
                self.register(det, actor_id=actor_id, allow_possible=include_possible)
            )

        return tuple(registered)
