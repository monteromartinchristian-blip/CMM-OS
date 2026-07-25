"""Phase 8.5 – Knowledge Store contracts and protocol.

Defines the explicit, typed interface for local Knowledge Store implementations.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol, runtime_checkable

from cmm.cognitive.enums import (
    ContradictionSeverity,
    ContradictionStatus,
    KnowledgeKind,
    KnowledgeRelationKind,
    KnowledgeStatus,
    SensitivityLevel,
)
from cmm.cognitive.errors import KnowledgeStoreError
from cmm.cognitive.knowledge import (
    Contradiction,
    Evidence,
    KnowledgeBundle,
    KnowledgeItem,
    KnowledgeRelation,
)

KNOWLEDGE_STORE_SCHEMA_VERSION: int = 1


def validate_store_id(id_value: Any, param_name: str = "id") -> str:
    """Validate that an ID parameter is a non-empty string."""
    if not isinstance(id_value, str):
        raise KnowledgeStoreError(
            f"Invalid {param_name}: expected string, got {type(id_value).__name__}"
        )
    stripped = id_value.strip()
    if not stripped:
        raise KnowledgeStoreError(
            f"Invalid {param_name}: must not be empty or whitespace"
        )
    return id_value


@runtime_checkable
class KnowledgeStoreProtocol(Protocol):
    """Protocol for local deterministic Knowledge Store implementations."""

    def transaction(self) -> AbstractContextManager[KnowledgeStoreProtocol]: ...

    # ── KnowledgeItem ────────────────────────────────────────────────────────

    def save_item(self, item: KnowledgeItem) -> KnowledgeItem: ...

    def get_item(self, item_id: str) -> KnowledgeItem: ...

    def contains_item(self, item_id: str) -> bool: ...

    def delete_item(self, item_id: str) -> None: ...

    def list_items(
        self,
        kind: KnowledgeKind | str | None = None,
        status: KnowledgeStatus | str | None = None,
        resource_id: str | None = None,
        actor_id: str | None = None,
        sensitivity: SensitivityLevel | str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[KnowledgeItem, ...]: ...

    def count_items(
        self,
        kind: KnowledgeKind | str | None = None,
        status: KnowledgeStatus | str | None = None,
        resource_id: str | None = None,
        actor_id: str | None = None,
        sensitivity: SensitivityLevel | str | None = None,
    ) -> int: ...

    # ── Evidence ─────────────────────────────────────────────────────────────

    def save_evidence(self, evidence: Evidence) -> Evidence: ...

    def get_evidence(self, evidence_id: str) -> Evidence: ...

    def contains_evidence(self, evidence_id: str) -> bool: ...

    def delete_evidence(self, evidence_id: str) -> None: ...

    def list_evidence(
        self,
        source_id: str | None = None,
        resource_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[Evidence, ...]: ...

    # ── KnowledgeRelation ─────────────────────────────────────────────────────

    def save_relation(self, relation: KnowledgeRelation) -> KnowledgeRelation: ...

    def get_relation(self, relation_id: str) -> KnowledgeRelation: ...

    def contains_relation(self, relation_id: str) -> bool: ...

    def delete_relation(self, relation_id: str) -> None: ...

    def list_relations(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        kind: KnowledgeRelationKind | str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[KnowledgeRelation, ...]: ...

    # ── Contradiction ─────────────────────────────────────────────────────────

    def save_contradiction(self, contradiction: Contradiction) -> Contradiction: ...

    def get_contradiction(self, contradiction_id: str) -> Contradiction: ...

    def contains_contradiction(self, contradiction_id: str) -> bool: ...

    def delete_contradiction(self, contradiction_id: str) -> None: ...

    def list_contradictions(
        self,
        status: ContradictionStatus | str | None = None,
        severity: ContradictionSeverity | str | None = None,
        item_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[Contradiction, ...]: ...

    # ── KnowledgeBundle ───────────────────────────────────────────────────────

    def save_bundle(self, bundle: KnowledgeBundle) -> KnowledgeBundle: ...

    def get_bundle(self, bundle_id: str) -> KnowledgeBundle: ...

    def contains_bundle(self, bundle_id: str) -> bool: ...

    def delete_bundle(self, bundle_id: str) -> None: ...

    def list_bundles(
        self,
        status: str | None = None,
        actor_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[KnowledgeBundle, ...]: ...
