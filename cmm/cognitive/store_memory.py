"""Phase 8.5 – In-Memory Knowledge Store implementation.

Thread-safe, deterministic, defensive copy in-memory implementation of KnowledgeStoreProtocol.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from threading import RLock
from typing import Any

from cmm.cognitive.enums import (
    ContradictionSeverity,
    ContradictionStatus,
    KnowledgeKind,
    KnowledgeRelationKind,
    KnowledgeStatus,
    SensitivityLevel,
)
from cmm.cognitive.errors import (
    KnowledgeStoreConflictError,
    KnowledgeStoreError,
    KnowledgeStoreNotFoundError,
)
from cmm.cognitive.knowledge import (
    Contradiction,
    Evidence,
    KnowledgeBundle,
    KnowledgeItem,
    KnowledgeRelation,
)
from cmm.cognitive.store_contracts import validate_store_id


class _Record:
    __slots__ = ("created_at_iso", "id", "payload", "record_type")

    def __init__(
        self,
        record_id: str,
        record_type: str,
        payload: dict[str, Any],
        created_at_iso: str,
    ) -> None:
        self.id = record_id
        self.record_type = record_type
        self.payload = payload
        self.created_at_iso = created_at_iso


class InMemoryKnowledgeStore:
    """In-memory implementation of KnowledgeStoreProtocol."""

    def __init__(self) -> None:
        self._records: dict[str, _Record] = {}
        self._lock = RLock()

    @contextmanager
    def transaction(self) -> Iterator[InMemoryKnowledgeStore]:
        """Provide atomic transaction boundary with snapshot rollback capability."""
        with self._lock:
            snapshot = {
                k: _Record(
                    r.id,
                    r.record_type,
                    dict(r.payload),
                    r.created_at_iso,
                )
                for k, r in self._records.items()
            }
            try:
                yield self
            except Exception:
                self._records = snapshot
                raise

    def _check_record_type(self, record_id: str, expected_type: str) -> None:
        rec = self._records.get(record_id)
        if rec is not None and rec.record_type != expected_type:
            raise KnowledgeStoreConflictError(
                f"ID '{record_id}' is already registered as a '{rec.record_type}'"
            )

    # ── KnowledgeItem ────────────────────────────────────────────────────────

    def save_item(self, item: KnowledgeItem) -> KnowledgeItem:
        if not isinstance(item, KnowledgeItem):
            raise KnowledgeStoreError(
                f"Expected KnowledgeItem, got {type(item).__name__}"
            )
        validate_store_id(item.id, "item_id")
        serialized = item.serialize()
        with self._lock:
            self._check_record_type(item.id, "item")
            self._records[item.id] = _Record(
                record_id=item.id,
                record_type="item",
                payload=serialized,
                created_at_iso=item.created_at.isoformat(),
            )
        return KnowledgeItem.from_mapping(serialized)

    def get_item(self, item_id: str) -> KnowledgeItem:
        validate_store_id(item_id, "item_id")
        with self._lock:
            rec = self._records.get(item_id)
            if rec is None or rec.record_type != "item":
                raise KnowledgeStoreNotFoundError(
                    f"KnowledgeItem not found: '{item_id}'"
                )
            return KnowledgeItem.from_mapping(rec.payload)

    def contains_item(self, item_id: str) -> bool:
        if not isinstance(item_id, str) or not item_id.strip():
            return False
        with self._lock:
            rec = self._records.get(item_id)
            return rec is not None and rec.record_type == "item"

    def delete_item(self, item_id: str) -> None:
        validate_store_id(item_id, "item_id")
        with self._lock:
            rec = self._records.get(item_id)
            if rec is None or rec.record_type != "item":
                raise KnowledgeStoreNotFoundError(
                    f"KnowledgeItem not found: '{item_id}'"
                )
            del self._records[item_id]

    def list_items(
        self,
        kind: KnowledgeKind | str | None = None,
        status: KnowledgeStatus | str | None = None,
        resource_id: str | None = None,
        actor_id: str | None = None,
        sensitivity: SensitivityLevel | str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[KnowledgeItem, ...]:
        kind_str = kind.value if isinstance(kind, KnowledgeKind) else kind
        status_str = status.value if isinstance(status, KnowledgeStatus) else status
        sens_str = (
            sensitivity.value
            if isinstance(sensitivity, SensitivityLevel)
            else sensitivity
        )

        with self._lock:
            item_records = [
                r for r in self._records.values() if r.record_type == "item"
            ]

        matching: list[dict[str, Any]] = []
        for r in item_records:
            p = r.payload
            if kind_str is not None and p.get("kind") != kind_str:
                continue
            if status_str is not None and p.get("status") != status_str:
                continue
            if resource_id is not None and p.get("resource_id") != resource_id:
                continue
            if actor_id is not None and p.get("actor_id") != actor_id:
                continue
            if sens_str is not None and p.get("sensitivity") != sens_str:
                continue
            matching.append(p)

        matching.sort(key=lambda p: (p["created_at"], p["id"]))

        if offset > 0:
            matching = matching[offset:]
        if limit is not None:
            matching = matching[:limit]

        return tuple(KnowledgeItem.from_mapping(p) for p in matching)

    def count_items(
        self,
        kind: KnowledgeKind | str | None = None,
        status: KnowledgeStatus | str | None = None,
        resource_id: str | None = None,
        actor_id: str | None = None,
        sensitivity: SensitivityLevel | str | None = None,
    ) -> int:
        return len(
            self.list_items(
                kind=kind,
                status=status,
                resource_id=resource_id,
                actor_id=actor_id,
                sensitivity=sensitivity,
            )
        )

    # ── Evidence ─────────────────────────────────────────────────────────────

    def save_evidence(self, evidence: Evidence) -> Evidence:
        if not isinstance(evidence, Evidence):
            raise KnowledgeStoreError(
                f"Expected Evidence, got {type(evidence).__name__}"
            )
        validate_store_id(evidence.id, "evidence_id")
        serialized = evidence.serialize()
        with self._lock:
            self._check_record_type(evidence.id, "evidence")
            self._records[evidence.id] = _Record(
                record_id=evidence.id,
                record_type="evidence",
                payload=serialized,
                created_at_iso=evidence.observed_at.isoformat(),
            )
        return Evidence.from_mapping(serialized)

    def get_evidence(self, evidence_id: str) -> Evidence:
        validate_store_id(evidence_id, "evidence_id")
        with self._lock:
            rec = self._records.get(evidence_id)
            if rec is None or rec.record_type != "evidence":
                raise KnowledgeStoreNotFoundError(
                    f"Evidence not found: '{evidence_id}'"
                )
            return Evidence.from_mapping(rec.payload)

    def contains_evidence(self, evidence_id: str) -> bool:
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            return False
        with self._lock:
            rec = self._records.get(evidence_id)
            return rec is not None and rec.record_type == "evidence"

    def delete_evidence(self, evidence_id: str) -> None:
        validate_store_id(evidence_id, "evidence_id")
        with self._lock:
            rec = self._records.get(evidence_id)
            if rec is None or rec.record_type != "evidence":
                raise KnowledgeStoreNotFoundError(
                    f"Evidence not found: '{evidence_id}'"
                )
            del self._records[evidence_id]

    def list_evidence(
        self,
        source_id: str | None = None,
        resource_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[Evidence, ...]:
        with self._lock:
            ev_records = [
                r for r in self._records.values() if r.record_type == "evidence"
            ]

        matching: list[dict[str, Any]] = []
        for r in ev_records:
            p = r.payload
            if source_id is not None and p.get("source_id") != source_id:
                continue
            if resource_id is not None and p.get("resource_id") != resource_id:
                continue
            matching.append(p)

        matching.sort(key=lambda p: (p["created_at"], p["id"]))

        if offset > 0:
            matching = matching[offset:]
        if limit is not None:
            matching = matching[:limit]

        return tuple(Evidence.from_mapping(p) for p in matching)

    # ── KnowledgeRelation ─────────────────────────────────────────────────────

    def save_relation(self, relation: KnowledgeRelation) -> KnowledgeRelation:
        if not isinstance(relation, KnowledgeRelation):
            raise KnowledgeStoreError(
                f"Expected KnowledgeRelation, got {type(relation).__name__}"
            )
        validate_store_id(relation.id, "relation_id")
        serialized = relation.serialize()
        with self._lock:
            self._check_record_type(relation.id, "relation")
            self._records[relation.id] = _Record(
                record_id=relation.id,
                record_type="relation",
                payload=serialized,
                created_at_iso=relation.created_at.isoformat(),
            )
        return KnowledgeRelation.from_mapping(serialized)

    def get_relation(self, relation_id: str) -> KnowledgeRelation:
        validate_store_id(relation_id, "relation_id")
        with self._lock:
            rec = self._records.get(relation_id)
            if rec is None or rec.record_type != "relation":
                raise KnowledgeStoreNotFoundError(
                    f"KnowledgeRelation not found: '{relation_id}'"
                )
            return KnowledgeRelation.from_mapping(rec.payload)

    def contains_relation(self, relation_id: str) -> bool:
        if not isinstance(relation_id, str) or not relation_id.strip():
            return False
        with self._lock:
            rec = self._records.get(relation_id)
            return rec is not None and rec.record_type == "relation"

    def delete_relation(self, relation_id: str) -> None:
        validate_store_id(relation_id, "relation_id")
        with self._lock:
            rec = self._records.get(relation_id)
            if rec is None or rec.record_type != "relation":
                raise KnowledgeStoreNotFoundError(
                    f"KnowledgeRelation not found: '{relation_id}'"
                )
            del self._records[relation_id]

    def list_relations(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        kind: KnowledgeRelationKind | str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[KnowledgeRelation, ...]:
        kind_str = kind.value if isinstance(kind, KnowledgeRelationKind) else kind

        with self._lock:
            rel_records = [
                r for r in self._records.values() if r.record_type == "relation"
            ]

        matching: list[dict[str, Any]] = []
        for r in rel_records:
            p = r.payload
            if source_id is not None and p.get("source_id") != source_id:
                continue
            if target_id is not None and p.get("target_id") != target_id:
                continue
            if kind_str is not None and p.get("kind") != kind_str:
                continue
            matching.append(p)

        matching.sort(key=lambda p: (p["created_at"], p["id"]))

        if offset > 0:
            matching = matching[offset:]
        if limit is not None:
            matching = matching[:limit]

        return tuple(KnowledgeRelation.from_mapping(p) for p in matching)

    # ── Contradiction ─────────────────────────────────────────────────────────

    def save_contradiction(self, contradiction: Contradiction) -> Contradiction:
        if not isinstance(contradiction, Contradiction):
            raise KnowledgeStoreError(
                f"Expected Contradiction, got {type(contradiction).__name__}"
            )
        validate_store_id(contradiction.id, "contradiction_id")
        serialized = contradiction.serialize()
        with self._lock:
            self._check_record_type(contradiction.id, "contradiction")
            self._records[contradiction.id] = _Record(
                record_id=contradiction.id,
                record_type="contradiction",
                payload=serialized,
                created_at_iso=contradiction.created_at.isoformat(),
            )
        return Contradiction.from_mapping(serialized)

    def get_contradiction(self, contradiction_id: str) -> Contradiction:
        validate_store_id(contradiction_id, "contradiction_id")
        with self._lock:
            rec = self._records.get(contradiction_id)
            if rec is None or rec.record_type != "contradiction":
                raise KnowledgeStoreNotFoundError(
                    f"Contradiction not found: '{contradiction_id}'"
                )
            return Contradiction.from_mapping(rec.payload)

    def contains_contradiction(self, contradiction_id: str) -> bool:
        if not isinstance(contradiction_id, str) or not contradiction_id.strip():
            return False
        with self._lock:
            rec = self._records.get(contradiction_id)
            return rec is not None and rec.record_type == "contradiction"

    def delete_contradiction(self, contradiction_id: str) -> None:
        validate_store_id(contradiction_id, "contradiction_id")
        with self._lock:
            rec = self._records.get(contradiction_id)
            if rec is None or rec.record_type != "contradiction":
                raise KnowledgeStoreNotFoundError(
                    f"Contradiction not found: '{contradiction_id}'"
                )
            del self._records[contradiction_id]

    def list_contradictions(
        self,
        status: ContradictionStatus | str | None = None,
        severity: ContradictionSeverity | str | None = None,
        item_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[Contradiction, ...]:
        status_str = status.value if isinstance(status, ContradictionStatus) else status
        sev_str = (
            severity.value if isinstance(severity, ContradictionSeverity) else severity
        )

        with self._lock:
            con_records = [
                r for r in self._records.values() if r.record_type == "contradiction"
            ]

        matching: list[dict[str, Any]] = []
        for r in con_records:
            p = r.payload
            if status_str is not None and p.get("status") != status_str:
                continue
            if sev_str is not None and p.get("severity") != sev_str:
                continue
            if (
                item_id is not None
                and p.get("item_a_id") != item_id
                and p.get("item_b_id") != item_id
            ):
                continue
            matching.append(p)

        matching.sort(key=lambda p: (p["created_at"], p["id"]))

        if offset > 0:
            matching = matching[offset:]
        if limit is not None:
            matching = matching[:limit]

        return tuple(Contradiction.from_mapping(p) for p in matching)

    # ── KnowledgeBundle ───────────────────────────────────────────────────────

    def save_bundle(self, bundle: KnowledgeBundle) -> KnowledgeBundle:
        if not isinstance(bundle, KnowledgeBundle):
            raise KnowledgeStoreError(
                f"Expected KnowledgeBundle, got {type(bundle).__name__}"
            )
        validate_store_id(bundle.id, "bundle_id")
        serialized = bundle.serialize()

        with self._lock:
            self._check_record_type(bundle.id, "bundle")
            # Strategy B: save all internal entities atomically
            for item in bundle.items:
                self.save_item(item)
            for evidence in bundle.evidence:
                self.save_evidence(evidence)
            for relation in bundle.relations:
                self.save_relation(relation)
            for contradiction in bundle.contradictions:
                self.save_contradiction(contradiction)

            self._records[bundle.id] = _Record(
                record_id=bundle.id,
                record_type="bundle",
                payload=serialized,
                created_at_iso=bundle.created_at.isoformat(),
            )
        return KnowledgeBundle.from_mapping(serialized)

    def get_bundle(self, bundle_id: str) -> KnowledgeBundle:
        validate_store_id(bundle_id, "bundle_id")
        with self._lock:
            rec = self._records.get(bundle_id)
            if rec is None or rec.record_type != "bundle":
                raise KnowledgeStoreNotFoundError(
                    f"KnowledgeBundle not found: '{bundle_id}'"
                )
            return KnowledgeBundle.from_mapping(rec.payload)

    def contains_bundle(self, bundle_id: str) -> bool:
        if not isinstance(bundle_id, str) or not bundle_id.strip():
            return False
        with self._lock:
            rec = self._records.get(bundle_id)
            return rec is not None and rec.record_type == "bundle"

    def delete_bundle(self, bundle_id: str) -> None:
        validate_store_id(bundle_id, "bundle_id")
        with self._lock:
            rec = self._records.get(bundle_id)
            if rec is None or rec.record_type != "bundle":
                raise KnowledgeStoreNotFoundError(
                    f"KnowledgeBundle not found: '{bundle_id}'"
                )
            del self._records[bundle_id]

    def list_bundles(
        self,
        status: str | None = None,
        actor_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[KnowledgeBundle, ...]:
        with self._lock:
            bundle_records = [
                r for r in self._records.values() if r.record_type == "bundle"
            ]

        matching: list[dict[str, Any]] = []
        for r in bundle_records:
            p = r.payload
            if status is not None and p.get("status") != status:
                continue
            if actor_id is not None and p.get("actor_id") != actor_id:
                continue
            matching.append(p)

        matching.sort(key=lambda p: (p["created_at"], p["id"]))

        if offset > 0:
            matching = matching[offset:]
        if limit is not None:
            matching = matching[:limit]

        return tuple(KnowledgeBundle.from_mapping(p) for p in matching)
