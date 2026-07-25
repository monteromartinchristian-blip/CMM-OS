"""Phase 8.5 – SQLite Knowledge Store implementation.

Local, persistent, atomic, deterministic implementation of KnowledgeStoreProtocol.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from types import TracebackType
from typing import Any

from typing_extensions import Self

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
    KnowledgeStoreCorruptionError,
    KnowledgeStoreError,
    KnowledgeStoreNotFoundError,
    KnowledgeStoreSchemaError,
)
from cmm.cognitive.knowledge import (
    Contradiction,
    Evidence,
    KnowledgeBundle,
    KnowledgeItem,
    KnowledgeRelation,
)
from cmm.cognitive.store_contracts import (
    KNOWLEDGE_STORE_SCHEMA_VERSION,
    validate_store_id,
)


def _resolve_and_validate_db_path(db_path: str | Path) -> str:
    path_str = str(db_path)
    if path_str == ":memory:":
        return ":memory:"

    path_obj = Path(db_path)
    if not path_obj.is_absolute():
        cwd = Path.cwd().resolve()
        resolved = (cwd / path_obj).resolve()
        try:
            resolved.relative_to(cwd)
        except ValueError as exc:
            raise KnowledgeStoreError(
                f"Relative database path '{db_path}' escapes project root '{cwd}'"
            ) from exc
        return str(resolved)
    return str(path_obj.resolve())


class SQLiteKnowledgeStore:
    """SQLite implementation of KnowledgeStoreProtocol."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._target_path = _resolve_and_validate_db_path(db_path)
        self._lock = RLock()
        try:
            self._conn = sqlite3.connect(self._target_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise KnowledgeStoreError(
                f"Failed to connect to SQLite database at '{db_path}': {exc}"
            ) from exc

        self._closed = False
        try:
            self._init_db()
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                try:
                    self._conn.close()
                except sqlite3.Error:
                    pass
                self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise KnowledgeStoreError("Knowledge store database is closed")

    @contextmanager
    def transaction(self) -> Iterator[SQLiteKnowledgeStore]:
        """Provide atomic transaction boundary."""
        with self._lock:
            self._ensure_open()
            if self._conn.in_transaction:
                yield self
            else:
                self._conn.execute("BEGIN TRANSACTION")
                try:
                    yield self
                except Exception:
                    self._conn.execute("ROLLBACK")
                    raise
                else:
                    self._conn.execute("COMMIT")

    @contextmanager
    def _tx_cursor(self) -> Iterator[sqlite3.Cursor]:
        """Provide cursor under active transaction context or temporary connection transaction."""
        if self._conn.in_transaction:
            yield self._conn.cursor()
        else:
            with self._conn:
                yield self._conn.cursor()

    def _init_db(self) -> None:
        with self._lock:
            self._ensure_open()
            try:
                with self._conn:
                    cursor = self._conn.cursor()
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS store_metadata (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL
                        )
                    """)
                    cursor.execute(
                        "SELECT value FROM store_metadata WHERE key = 'schema_version'"
                    )
                    row = cursor.fetchone()
                    if row is None:
                        cursor.execute(
                            "INSERT INTO store_metadata (key, value) VALUES ('schema_version', ?)",
                            (str(KNOWLEDGE_STORE_SCHEMA_VERSION),),
                        )
                    else:
                        try:
                            version = int(row["value"])
                        except ValueError as exc:
                            raise KnowledgeStoreCorruptionError(
                                f"Corrupt schema_version value in metadata: {row['value']}"
                            ) from exc
                        if version != KNOWLEDGE_STORE_SCHEMA_VERSION:
                            raise KnowledgeStoreSchemaError(
                                f"Unsupported schema version: {version} (expected {KNOWLEDGE_STORE_SCHEMA_VERSION})"
                            )

                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS knowledge_records (
                            record_id TEXT PRIMARY KEY,
                            record_type TEXT NOT NULL,
                            payload_json TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            schema_version INTEGER NOT NULL,
                            kind TEXT,
                            status TEXT,
                            resource_id TEXT,
                            actor_id TEXT,
                            sensitivity TEXT,
                            source_id TEXT,
                            target_id TEXT,
                            severity TEXT,
                            item_id_a TEXT,
                            item_id_b TEXT
                        )
                    """)
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_rec_type ON knowledge_records(record_type)"
                    )
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_rec_kind ON knowledge_records(kind)"
                    )
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_rec_status ON knowledge_records(status)"
                    )
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_rec_resource ON knowledge_records(resource_id)"
                    )
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_rec_actor ON knowledge_records(actor_id)"
                    )
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_rec_source ON knowledge_records(source_id)"
                    )
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_rec_target ON knowledge_records(target_id)"
                    )
            except sqlite3.DatabaseError as exc:
                raise KnowledgeStoreCorruptionError(
                    f"Corrupt or invalid SQLite database: {exc}"
                ) from exc
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Failed to initialize database schema: {exc}"
                ) from exc

    def _check_record_type_conflict(
        self, cursor: sqlite3.Cursor, record_id: str, expected_type: str
    ) -> None:
        cursor.execute(
            "SELECT record_type FROM knowledge_records WHERE record_id = ?",
            (record_id,),
        )
        row = cursor.fetchone()
        if row is not None and row["record_type"] != expected_type:
            raise KnowledgeStoreConflictError(
                f"ID '{record_id}' is already registered as a '{row['record_type']}'"
            )

    def _parse_payload(
        self, record_id: str, record_type: str, payload_json: str, factory: Any
    ) -> Any:
        try:
            payload = json.loads(payload_json)
        except Exception as exc:
            raise KnowledgeStoreCorruptionError(
                f"Corrupt JSON payload for record '{record_id}': {exc}"
            ) from exc

        try:
            return factory(payload)
        except Exception as exc:
            raise KnowledgeStoreCorruptionError(
                f"Failed to reconstruct {record_type} contract from record '{record_id}': {exc}"
            ) from exc

    # ── KnowledgeItem ────────────────────────────────────────────────────────

    def save_item(self, item: KnowledgeItem) -> KnowledgeItem:
        if not isinstance(item, KnowledgeItem):
            raise KnowledgeStoreError(
                f"Expected KnowledgeItem, got {type(item).__name__}"
            )
        validate_store_id(item.id, "item_id")
        serialized = item.serialize()
        payload_json = json.dumps(serialized, sort_keys=True)
        created_at_iso = item.created_at.isoformat()
        updated_at_iso = item.updated_at.isoformat()
        sens_val = item.sensitivity.value if item.sensitivity else None

        with self._lock:
            self._ensure_open()
            try:
                with self._tx_cursor() as cursor:
                    self._check_record_type_conflict(cursor, item.id, "item")
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO knowledge_records (
                            record_id, record_type, payload_json, created_at, updated_at,
                            schema_version, kind, status, resource_id, actor_id, sensitivity
                        ) VALUES (?, 'item', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item.id,
                            payload_json,
                            created_at_iso,
                            updated_at_iso,
                            KNOWLEDGE_STORE_SCHEMA_VERSION,
                            item.kind.value,
                            item.status.value,
                            item.resource_id,
                            item.actor_id,
                            sens_val,
                        ),
                    )
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error while saving KnowledgeItem '{item.id}': {exc}"
                ) from exc

        return KnowledgeItem.from_mapping(serialized)

    def get_item(self, item_id: str) -> KnowledgeItem:
        validate_store_id(item_id, "item_id")
        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT payload_json FROM knowledge_records WHERE record_id = ? AND record_type = 'item'",
                    (item_id,),
                )
                row = cursor.fetchone()
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error reading item '{item_id}': {exc}"
                ) from exc

        if row is None:
            raise KnowledgeStoreNotFoundError(f"KnowledgeItem not found: '{item_id}'")
        return self._parse_payload(
            item_id, "KnowledgeItem", row["payload_json"], KnowledgeItem.from_mapping
        )

    def contains_item(self, item_id: str) -> bool:
        if not isinstance(item_id, str) or not item_id.strip():
            return False
        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM knowledge_records WHERE record_id = ? AND record_type = 'item'",
                    (item_id,),
                )
                return cursor.fetchone() is not None
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error checking item '{item_id}': {exc}"
                ) from exc

    def delete_item(self, item_id: str) -> None:
        validate_store_id(item_id, "item_id")
        with self._lock:
            self._ensure_open()
            try:
                with self._tx_cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM knowledge_records WHERE record_id = ? AND record_type = 'item'",
                        (item_id,),
                    )
                    if cursor.rowcount == 0:
                        raise KnowledgeStoreNotFoundError(
                            f"KnowledgeItem not found: '{item_id}'"
                        )
            except KnowledgeStoreNotFoundError:
                raise
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error deleting item '{item_id}': {exc}"
                ) from exc

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

        query = "SELECT record_id, payload_json FROM knowledge_records WHERE record_type = 'item'"
        params: list[Any] = []

        if kind_str is not None:
            query += " AND kind = ?"
            params.append(kind_str)
        if status_str is not None:
            query += " AND status = ?"
            params.append(status_str)
        if resource_id is not None:
            query += " AND resource_id = ?"
            params.append(resource_id)
        if actor_id is not None:
            query += " AND actor_id = ?"
            params.append(actor_id)
        if sens_str is not None:
            query += " AND sensitivity = ?"
            params.append(sens_str)

        query += " ORDER BY created_at ASC, record_id ASC"

        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        elif offset > 0:
            query += " LIMIT -1 OFFSET ?"
            params.append(offset)

        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error querying KnowledgeItems: {exc}"
                ) from exc

        return tuple(
            self._parse_payload(
                r["record_id"],
                "KnowledgeItem",
                r["payload_json"],
                KnowledgeItem.from_mapping,
            )
            for r in rows
        )

    def count_items(
        self,
        kind: KnowledgeKind | str | None = None,
        status: KnowledgeStatus | str | None = None,
        resource_id: str | None = None,
        actor_id: str | None = None,
        sensitivity: SensitivityLevel | str | None = None,
    ) -> int:
        kind_str = kind.value if isinstance(kind, KnowledgeKind) else kind
        status_str = status.value if isinstance(status, KnowledgeStatus) else status
        sens_str = (
            sensitivity.value
            if isinstance(sensitivity, SensitivityLevel)
            else sensitivity
        )

        query = (
            "SELECT COUNT(*) as cnt FROM knowledge_records WHERE record_type = 'item'"
        )
        params: list[Any] = []

        if kind_str is not None:
            query += " AND kind = ?"
            params.append(kind_str)
        if status_str is not None:
            query += " AND status = ?"
            params.append(status_str)
        if resource_id is not None:
            query += " AND resource_id = ?"
            params.append(resource_id)
        if actor_id is not None:
            query += " AND actor_id = ?"
            params.append(actor_id)
        if sens_str is not None:
            query += " AND sensitivity = ?"
            params.append(sens_str)

        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(query, params)
                row = cursor.fetchone()
                return int(row["cnt"])
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error counting KnowledgeItems: {exc}"
                ) from exc

    # ── Evidence ─────────────────────────────────────────────────────────────

    def save_evidence(self, evidence: Evidence) -> Evidence:
        if not isinstance(evidence, Evidence):
            raise KnowledgeStoreError(
                f"Expected Evidence, got {type(evidence).__name__}"
            )
        validate_store_id(evidence.id, "evidence_id")
        serialized = evidence.serialize()
        payload_json = json.dumps(serialized, sort_keys=True)
        created_at_iso = evidence.observed_at.isoformat()

        with self._lock:
            self._ensure_open()
            try:
                with self._tx_cursor() as cursor:
                    self._check_record_type_conflict(cursor, evidence.id, "evidence")
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO knowledge_records (
                            record_id, record_type, payload_json, created_at, updated_at,
                            schema_version, source_id, resource_id
                        ) VALUES (?, 'evidence', ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            evidence.id,
                            payload_json,
                            created_at_iso,
                            created_at_iso,
                            KNOWLEDGE_STORE_SCHEMA_VERSION,
                            evidence.resource_provenance_id,
                            evidence.resource_id,
                        ),
                    )
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error while saving Evidence '{evidence.id}': {exc}"
                ) from exc

        return Evidence.from_mapping(serialized)

    def get_evidence(self, evidence_id: str) -> Evidence:
        validate_store_id(evidence_id, "evidence_id")
        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT payload_json FROM knowledge_records WHERE record_id = ? AND record_type = 'evidence'",
                    (evidence_id,),
                )
                row = cursor.fetchone()
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error reading evidence '{evidence_id}': {exc}"
                ) from exc

        if row is None:
            raise KnowledgeStoreNotFoundError(f"Evidence not found: '{evidence_id}'")
        return self._parse_payload(
            evidence_id, "Evidence", row["payload_json"], Evidence.from_mapping
        )

    def contains_evidence(self, evidence_id: str) -> bool:
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            return False
        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM knowledge_records WHERE record_id = ? AND record_type = 'evidence'",
                    (evidence_id,),
                )
                return cursor.fetchone() is not None
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error checking evidence '{evidence_id}': {exc}"
                ) from exc

    def delete_evidence(self, evidence_id: str) -> None:
        validate_store_id(evidence_id, "evidence_id")
        with self._lock:
            self._ensure_open()
            try:
                with self._tx_cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM knowledge_records WHERE record_id = ? AND record_type = 'evidence'",
                        (evidence_id,),
                    )
                    if cursor.rowcount == 0:
                        raise KnowledgeStoreNotFoundError(
                            f"Evidence not found: '{evidence_id}'"
                        )
            except KnowledgeStoreNotFoundError:
                raise
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error deleting evidence '{evidence_id}': {exc}"
                ) from exc

    def list_evidence(
        self,
        source_id: str | None = None,
        resource_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[Evidence, ...]:
        query = "SELECT record_id, payload_json FROM knowledge_records WHERE record_type = 'evidence'"
        params: list[Any] = []

        if source_id is not None:
            query += " AND source_id = ?"
            params.append(source_id)
        if resource_id is not None:
            query += " AND resource_id = ?"
            params.append(resource_id)

        query += " ORDER BY created_at ASC, record_id ASC"

        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        elif offset > 0:
            query += " LIMIT -1 OFFSET ?"
            params.append(offset)

        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error querying Evidence: {exc}"
                ) from exc

        return tuple(
            self._parse_payload(
                r["record_id"],
                "Evidence",
                r["payload_json"],
                Evidence.from_mapping,
            )
            for r in rows
        )

    # ── KnowledgeRelation ─────────────────────────────────────────────────────

    def save_relation(self, relation: KnowledgeRelation) -> KnowledgeRelation:
        if not isinstance(relation, KnowledgeRelation):
            raise KnowledgeStoreError(
                f"Expected KnowledgeRelation, got {type(relation).__name__}"
            )
        validate_store_id(relation.id, "relation_id")
        serialized = relation.serialize()
        payload_json = json.dumps(serialized, sort_keys=True)
        created_at_iso = relation.created_at.isoformat()

        with self._lock:
            self._ensure_open()
            try:
                with self._tx_cursor() as cursor:
                    self._check_record_type_conflict(cursor, relation.id, "relation")
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO knowledge_records (
                            record_id, record_type, payload_json, created_at, updated_at,
                            schema_version, source_id, target_id, kind
                        ) VALUES (?, 'relation', ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            relation.id,
                            payload_json,
                            created_at_iso,
                            created_at_iso,
                            KNOWLEDGE_STORE_SCHEMA_VERSION,
                            relation.source_id,
                            relation.target_id,
                            relation.kind.value,
                        ),
                    )
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error saving KnowledgeRelation '{relation.id}': {exc}"
                ) from exc

        return KnowledgeRelation.from_mapping(serialized)

    def get_relation(self, relation_id: str) -> KnowledgeRelation:
        validate_store_id(relation_id, "relation_id")
        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT payload_json FROM knowledge_records WHERE record_id = ? AND record_type = 'relation'",
                    (relation_id,),
                )
                row = cursor.fetchone()
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error reading relation '{relation_id}': {exc}"
                ) from exc

        if row is None:
            raise KnowledgeStoreNotFoundError(
                f"KnowledgeRelation not found: '{relation_id}'"
            )
        return self._parse_payload(
            relation_id,
            "KnowledgeRelation",
            row["payload_json"],
            KnowledgeRelation.from_mapping,
        )

    def contains_relation(self, relation_id: str) -> bool:
        if not isinstance(relation_id, str) or not relation_id.strip():
            return False
        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM knowledge_records WHERE record_id = ? AND record_type = 'relation'",
                    (relation_id,),
                )
                return cursor.fetchone() is not None
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error checking relation '{relation_id}': {exc}"
                ) from exc

    def delete_relation(self, relation_id: str) -> None:
        validate_store_id(relation_id, "relation_id")
        with self._lock:
            self._ensure_open()
            try:
                with self._tx_cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM knowledge_records WHERE record_id = ? AND record_type = 'relation'",
                        (relation_id,),
                    )
                    if cursor.rowcount == 0:
                        raise KnowledgeStoreNotFoundError(
                            f"KnowledgeRelation not found: '{relation_id}'"
                        )
            except KnowledgeStoreNotFoundError:
                raise
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error deleting relation '{relation_id}': {exc}"
                ) from exc

    def list_relations(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        kind: KnowledgeRelationKind | str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[KnowledgeRelation, ...]:
        kind_str = kind.value if isinstance(kind, KnowledgeRelationKind) else kind
        query = "SELECT record_id, payload_json FROM knowledge_records WHERE record_type = 'relation'"
        params: list[Any] = []

        if source_id is not None:
            query += " AND source_id = ?"
            params.append(source_id)
        if target_id is not None:
            query += " AND target_id = ?"
            params.append(target_id)
        if kind_str is not None:
            query += " AND kind = ?"
            params.append(kind_str)

        query += " ORDER BY created_at ASC, record_id ASC"

        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        elif offset > 0:
            query += " LIMIT -1 OFFSET ?"
            params.append(offset)

        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error querying KnowledgeRelations: {exc}"
                ) from exc

        return tuple(
            self._parse_payload(
                r["record_id"],
                "KnowledgeRelation",
                r["payload_json"],
                KnowledgeRelation.from_mapping,
            )
            for r in rows
        )

    # ── Contradiction ─────────────────────────────────────────────────────────

    def save_contradiction(self, contradiction: Contradiction) -> Contradiction:
        if not isinstance(contradiction, Contradiction):
            raise KnowledgeStoreError(
                f"Expected Contradiction, got {type(contradiction).__name__}"
            )
        validate_store_id(contradiction.id, "contradiction_id")
        serialized = contradiction.serialize()
        payload_json = json.dumps(serialized, sort_keys=True)
        created_at_iso = contradiction.created_at.isoformat()

        with self._lock:
            self._ensure_open()
            try:
                with self._tx_cursor() as cursor:
                    self._check_record_type_conflict(
                        cursor, contradiction.id, "contradiction"
                    )
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO knowledge_records (
                            record_id, record_type, payload_json, created_at, updated_at,
                            schema_version, status, severity, item_id_a, item_id_b, actor_id
                        ) VALUES (?, 'contradiction', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            contradiction.id,
                            payload_json,
                            created_at_iso,
                            created_at_iso,
                            KNOWLEDGE_STORE_SCHEMA_VERSION,
                            contradiction.status.value,
                            contradiction.severity.value,
                            contradiction.item_a_id,
                            contradiction.item_b_id,
                            contradiction.actor_id,
                        ),
                    )
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error saving Contradiction '{contradiction.id}': {exc}"
                ) from exc

        return Contradiction.from_mapping(serialized)

    def get_contradiction(self, contradiction_id: str) -> Contradiction:
        validate_store_id(contradiction_id, "contradiction_id")
        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT payload_json FROM knowledge_records WHERE record_id = ? AND record_type = 'contradiction'",
                    (contradiction_id,),
                )
                row = cursor.fetchone()
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error reading contradiction '{contradiction_id}': {exc}"
                ) from exc

        if row is None:
            raise KnowledgeStoreNotFoundError(
                f"Contradiction not found: '{contradiction_id}'"
            )
        return self._parse_payload(
            contradiction_id,
            "Contradiction",
            row["payload_json"],
            Contradiction.from_mapping,
        )

    def contains_contradiction(self, contradiction_id: str) -> bool:
        if not isinstance(contradiction_id, str) or not contradiction_id.strip():
            return False
        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM knowledge_records WHERE record_id = ? AND record_type = 'contradiction'",
                    (contradiction_id,),
                )
                return cursor.fetchone() is not None
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error checking contradiction '{contradiction_id}': {exc}"
                ) from exc

    def delete_contradiction(self, contradiction_id: str) -> None:
        validate_store_id(contradiction_id, "contradiction_id")
        with self._lock:
            self._ensure_open()
            try:
                with self._tx_cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM knowledge_records WHERE record_id = ? AND record_type = 'contradiction'",
                        (contradiction_id,),
                    )
                    if cursor.rowcount == 0:
                        raise KnowledgeStoreNotFoundError(
                            f"Contradiction not found: '{contradiction_id}'"
                        )
            except KnowledgeStoreNotFoundError:
                raise
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error deleting contradiction '{contradiction_id}': {exc}"
                ) from exc

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

        query = "SELECT record_id, payload_json FROM knowledge_records WHERE record_type = 'contradiction'"
        params: list[Any] = []

        if status_str is not None:
            query += " AND status = ?"
            params.append(status_str)
        if sev_str is not None:
            query += " AND severity = ?"
            params.append(sev_str)
        if item_id is not None:
            query += " AND (item_id_a = ? OR item_id_b = ?)"
            params.extend([item_id, item_id])

        query += " ORDER BY created_at ASC, record_id ASC"

        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        elif offset > 0:
            query += " LIMIT -1 OFFSET ?"
            params.append(offset)

        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error querying Contradictions: {exc}"
                ) from exc

        return tuple(
            self._parse_payload(
                r["record_id"],
                "Contradiction",
                r["payload_json"],
                Contradiction.from_mapping,
            )
            for r in rows
        )

    # ── KnowledgeBundle ───────────────────────────────────────────────────────

    def save_bundle(self, bundle: KnowledgeBundle) -> KnowledgeBundle:
        if not isinstance(bundle, KnowledgeBundle):
            raise KnowledgeStoreError(
                f"Expected KnowledgeBundle, got {type(bundle).__name__}"
            )
        validate_store_id(bundle.id, "bundle_id")
        serialized = bundle.serialize()
        payload_json = json.dumps(serialized, sort_keys=True)
        created_at_iso = bundle.created_at.isoformat()

        with self._lock:
            self._ensure_open()
            try:
                with self._tx_cursor() as cursor:
                    self._check_record_type_conflict(cursor, bundle.id, "bundle")

                    # Internal entities
                    for item in bundle.items:
                        validate_store_id(item.id, "item_id")
                        self._check_record_type_conflict(cursor, item.id, "item")
                        item_sens = item.sensitivity.value if item.sensitivity else None
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO knowledge_records (
                                record_id, record_type, payload_json, created_at, updated_at,
                                schema_version, kind, status, resource_id, actor_id, sensitivity
                            ) VALUES (?, 'item', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                item.id,
                                json.dumps(item.serialize(), sort_keys=True),
                                item.created_at.isoformat(),
                                item.updated_at.isoformat(),
                                KNOWLEDGE_STORE_SCHEMA_VERSION,
                                item.kind.value,
                                item.status.value,
                                item.resource_id,
                                item.actor_id,
                                item_sens,
                            ),
                        )

                    for evidence in bundle.evidence:
                        validate_store_id(evidence.id, "evidence_id")
                        self._check_record_type_conflict(
                            cursor, evidence.id, "evidence"
                        )
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO knowledge_records (
                                record_id, record_type, payload_json, created_at, updated_at,
                                schema_version, source_id, resource_id
                            ) VALUES (?, 'evidence', ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                evidence.id,
                                json.dumps(evidence.serialize(), sort_keys=True),
                                evidence.observed_at.isoformat(),
                                evidence.observed_at.isoformat(),
                                KNOWLEDGE_STORE_SCHEMA_VERSION,
                                evidence.resource_provenance_id,
                                evidence.resource_id,
                            ),
                        )

                    for relation in bundle.relations:
                        validate_store_id(relation.id, "relation_id")
                        self._check_record_type_conflict(
                            cursor, relation.id, "relation"
                        )
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO knowledge_records (
                                record_id, record_type, payload_json, created_at, updated_at,
                                schema_version, source_id, target_id, kind
                            ) VALUES (?, 'relation', ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                relation.id,
                                json.dumps(relation.serialize(), sort_keys=True),
                                relation.created_at.isoformat(),
                                relation.created_at.isoformat(),
                                KNOWLEDGE_STORE_SCHEMA_VERSION,
                                relation.source_id,
                                relation.target_id,
                                relation.kind.value,
                            ),
                        )

                    for contradiction in bundle.contradictions:
                        validate_store_id(contradiction.id, "contradiction_id")
                        self._check_record_type_conflict(
                            cursor, contradiction.id, "contradiction"
                        )
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO knowledge_records (
                                record_id, record_type, payload_json, created_at, updated_at,
                                schema_version, status, severity, item_id_a, item_id_b, actor_id
                            ) VALUES (?, 'contradiction', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                contradiction.id,
                                json.dumps(contradiction.serialize(), sort_keys=True),
                                contradiction.created_at.isoformat(),
                                contradiction.created_at.isoformat(),
                                KNOWLEDGE_STORE_SCHEMA_VERSION,
                                contradiction.status.value,
                                contradiction.severity.value,
                                contradiction.item_a_id,
                                contradiction.item_b_id,
                                contradiction.actor_id,
                            ),
                        )

                    # Bundle record itself
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO knowledge_records (
                            record_id, record_type, payload_json, created_at, updated_at,
                            schema_version, status, actor_id
                        ) VALUES (?, 'bundle', ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            bundle.id,
                            payload_json,
                            created_at_iso,
                            created_at_iso,
                            KNOWLEDGE_STORE_SCHEMA_VERSION,
                            bundle.status,
                            bundle.actor_id,
                        ),
                    )
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error saving KnowledgeBundle '{bundle.id}': {exc}"
                ) from exc

        return KnowledgeBundle.from_mapping(serialized)

    def get_bundle(self, bundle_id: str) -> KnowledgeBundle:
        validate_store_id(bundle_id, "bundle_id")
        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT payload_json FROM knowledge_records WHERE record_id = ? AND record_type = 'bundle'",
                    (bundle_id,),
                )
                row = cursor.fetchone()
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error reading bundle '{bundle_id}': {exc}"
                ) from exc

        if row is None:
            raise KnowledgeStoreNotFoundError(
                f"KnowledgeBundle not found: '{bundle_id}'"
            )
        return self._parse_payload(
            bundle_id,
            "KnowledgeBundle",
            row["payload_json"],
            KnowledgeBundle.from_mapping,
        )

    def contains_bundle(self, bundle_id: str) -> bool:
        if not isinstance(bundle_id, str) or not bundle_id.strip():
            return False
        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM knowledge_records WHERE record_id = ? AND record_type = 'bundle'",
                    (bundle_id,),
                )
                return cursor.fetchone() is not None
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error checking bundle '{bundle_id}': {exc}"
                ) from exc

    def delete_bundle(self, bundle_id: str) -> None:
        validate_store_id(bundle_id, "bundle_id")
        with self._lock:
            self._ensure_open()
            try:
                with self._tx_cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM knowledge_records WHERE record_id = ? AND record_type = 'bundle'",
                        (bundle_id,),
                    )
                    if cursor.rowcount == 0:
                        raise KnowledgeStoreNotFoundError(
                            f"KnowledgeBundle not found: '{bundle_id}'"
                        )
            except KnowledgeStoreNotFoundError:
                raise
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error deleting bundle '{bundle_id}': {exc}"
                ) from exc

    def list_bundles(
        self,
        status: str | None = None,
        actor_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[KnowledgeBundle, ...]:
        query = "SELECT record_id, payload_json FROM knowledge_records WHERE record_type = 'bundle'"
        params: list[Any] = []

        if status is not None:
            query += " AND status = ?"
            params.append(status)
        if actor_id is not None:
            query += " AND actor_id = ?"
            params.append(actor_id)

        query += " ORDER BY created_at ASC, record_id ASC"

        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        elif offset > 0:
            query += " LIMIT -1 OFFSET ?"
            params.append(offset)

        with self._lock:
            self._ensure_open()
            try:
                cursor = self._conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
            except sqlite3.Error as exc:
                raise KnowledgeStoreError(
                    f"Database error querying KnowledgeBundles: {exc}"
                ) from exc

        return tuple(
            self._parse_payload(
                r["record_id"],
                "KnowledgeBundle",
                r["payload_json"],
                KnowledgeBundle.from_mapping,
            )
            for r in rows
        )
