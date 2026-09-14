"""Phase 10.34 – Domain Knowledge Authority Contracts.

Defines native authority interfaces and verdicts for evaluating domain knowledge
freshness, validity, and provenance during domain session resumption.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from typing_extensions import Protocol, runtime_checkable

from cmm.cognitive.enums import KnowledgeStatus, TemporalScopeKind
from cmm.cognitive.knowledge import KnowledgeItem
from cmm.cognitive.store_contracts import KnowledgeStoreProtocol
from cmm.domains.resource_contracts import _deep_freeze
from cmm.domains.session_contracts import DomainSessionCheckStatus


@dataclass(frozen=True, slots=True)
class DomainKnowledgeCurrentVerdict:
    """Authoritative verdict for a domain knowledge reference."""

    knowledge_id: str
    status: DomainSessionCheckStatus
    message: str = ""
    is_blocking: bool = False
    details: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not self.knowledge_id or not isinstance(self.knowledge_id, str):
            raise ValueError("knowledge_id must be a non-empty string")
        if not isinstance(self.status, DomainSessionCheckStatus):
            raise TypeError("status must be a DomainSessionCheckStatus")
        object.__setattr__(self, "details", _deep_freeze(self.details))


@runtime_checkable
class DomainKnowledgeAuthority(Protocol):
    """Protocol for authoritative resolution of domain knowledge freshness and validity."""

    def resolve_knowledge_freshness(
        self,
        knowledge_id: str,
        *,
        domain: str | None = None,
        at: datetime | None = None,
    ) -> DomainKnowledgeCurrentVerdict:
        """Resolve the authoritative current freshness verdict for a knowledge reference."""
        ...


class DefaultDomainKnowledgeAuthority:
    """Default repository-native knowledge authority."""

    def __init__(
        self,
        valid_knowledge: Mapping[str, Any] | None = None,
        *,
        store: KnowledgeStoreProtocol | None = None,
    ) -> None:
        self._store = store
        self._valid_knowledge: dict[str, Any] = (
            dict(valid_knowledge) if valid_knowledge is not None else {}
        )

    def register_knowledge(self, knowledge_id: str, metadata: Any = None) -> None:
        self._valid_knowledge[knowledge_id] = metadata

    def resolve_knowledge_freshness(
        self,
        knowledge_id: str,
        *,
        domain: str | None = None,
        at: datetime | None = None,
    ) -> DomainKnowledgeCurrentVerdict:
        found, value = self._resolve_value(knowledge_id)
        if not found:
            return DomainKnowledgeCurrentVerdict(
                knowledge_id=knowledge_id,
                status=DomainSessionCheckStatus.BLOCKING,
                message=f"Knowledge '{knowledge_id}' not found in authoritative knowledge registry",
                is_blocking=True,
                details={
                    "knowledge_id": knowledge_id,
                    "domain": domain,
                    "reason": "NOT_FOUND",
                },
            )

        if isinstance(value, KnowledgeItem):
            return self._evaluate_item(value, knowledge_id, domain=domain, at=at)

        val = value
        if isinstance(val, str):
            val_u = val.upper().strip()
            if val_u in ("MISSING", "INVALIDATED", "EXPIRED"):
                return DomainKnowledgeCurrentVerdict(
                    knowledge_id=knowledge_id,
                    status=DomainSessionCheckStatus.BLOCKING,
                    message=f"Knowledge '{knowledge_id}' is {val_u.lower()}",
                    is_blocking=True,
                    details={
                        "knowledge_id": knowledge_id,
                        "domain": domain,
                        "status": val_u,
                    },
                )
            if val_u in ("STALE", "DRIFT", "CHANGED") or "drift" in val.lower():
                return DomainKnowledgeCurrentVerdict(
                    knowledge_id=knowledge_id,
                    status=DomainSessionCheckStatus.DRIFT,
                    message=f"Knowledge '{knowledge_id}' has drifted/is stale",
                    is_blocking=False,
                    details={
                        "knowledge_id": knowledge_id,
                        "domain": domain,
                        "status": val_u,
                    },
                )

            return DomainKnowledgeCurrentVerdict(
                knowledge_id=knowledge_id,
                status=DomainSessionCheckStatus.PASS,
                message=f"Knowledge '{knowledge_id}' is current",
                is_blocking=False,
                details={
                    "knowledge_id": knowledge_id,
                    "domain": domain,
                    "source": "legacy_mapping_adapter",
                },
            )

        if isinstance(val, Mapping):
            return DomainKnowledgeCurrentVerdict(
                knowledge_id=knowledge_id,
                status=DomainSessionCheckStatus.PASS,
                message=f"Knowledge '{knowledge_id}' is current",
                is_blocking=False,
                details={
                    "knowledge_id": knowledge_id,
                    "domain": domain,
                    "source": "legacy_mapping_adapter",
                },
            )

        return self._conservative_verdict(
            knowledge_id,
            domain=domain,
            reason="UNKNOWN_AUTHORITY_OBJECT",
            message=f"Knowledge '{knowledge_id}' has an unknown authority object",
        )

    def _resolve_value(self, knowledge_id: str) -> tuple[bool, Any]:
        if self._store is not None:
            try:
                if not self._store.contains_item(knowledge_id):
                    return False, None
                return True, self._store.get_item(knowledge_id)
            except Exception:  # noqa: BLE001 - authority failures must fail closed
                return False, None
        if knowledge_id not in self._valid_knowledge:
            return False, None
        return True, self._valid_knowledge[knowledge_id]

    def _evaluate_item(
        self,
        item: KnowledgeItem,
        knowledge_id: str,
        *,
        domain: str | None,
        at: datetime | None,
    ) -> DomainKnowledgeCurrentVerdict:
        if item.id != knowledge_id:
            return self._conservative_verdict(
                knowledge_id,
                domain=domain,
                reason="ID_MISMATCH",
                message=(
                    f"Knowledge authority returned '{item.id}' for requested "
                    f"ID '{knowledge_id}'"
                ),
            )

        status_details = {
            "knowledge_id": knowledge_id,
            "domain": domain,
            "status": item.status.value,
            "version": item.version,
            "superseded_by_id": item.superseded_by_id,
            "invalidated_at": (
                item.invalidated_at.isoformat()
                if item.invalidated_at is not None
                else None
            ),
            "invalidation_reason": item.invalidation_reason,
            "temporal_scope": item.temporal_scope.serialize(),
            "source": "canonical_knowledge_item",
        }
        if item.status in {
            KnowledgeStatus.INVALIDATED,
            KnowledgeStatus.SUPERSEDED,
            KnowledgeStatus.UNVERIFIED,
            KnowledgeStatus.DISPUTED,
        }:
            return DomainKnowledgeCurrentVerdict(
                knowledge_id=knowledge_id,
                status=DomainSessionCheckStatus.BLOCKING,
                message=(
                    f"Knowledge '{knowledge_id}' has conservative canonical "
                    f"status {item.status.value}"
                ),
                is_blocking=True,
                details=status_details,
            )

        if item.status is not KnowledgeStatus.ACTIVE:
            return self._conservative_verdict(
                knowledge_id,
                domain=domain,
                reason="UNKNOWN_KNOWLEDGE_STATUS",
                message=f"Knowledge '{knowledge_id}' has an unknown status",
            )

        now = at if at is not None else datetime.now(timezone.utc)
        scope = item.temporal_scope
        temporally_valid = scope.kind is TemporalScopeKind.TIMELESS or (
            scope.kind is not TemporalScopeKind.UNKNOWN
            and scope.is_valid_at(now)
            and (scope.expires_at is None or now <= scope.expires_at)
        )
        if not temporally_valid:
            return DomainKnowledgeCurrentVerdict(
                knowledge_id=knowledge_id,
                status=DomainSessionCheckStatus.BLOCKING,
                message=f"Knowledge '{knowledge_id}' is not temporally current",
                is_blocking=True,
                details={**status_details, "reason": "TEMPORALLY_INVALID"},
            )

        return DomainKnowledgeCurrentVerdict(
            knowledge_id=knowledge_id,
            status=DomainSessionCheckStatus.PASS,
            message=f"Knowledge '{knowledge_id}' is current",
            is_blocking=False,
            details=status_details,
        )

    @staticmethod
    def _conservative_verdict(
        knowledge_id: str,
        *,
        domain: str | None,
        reason: str,
        message: str,
    ) -> DomainKnowledgeCurrentVerdict:
        return DomainKnowledgeCurrentVerdict(
            knowledge_id=knowledge_id,
            status=DomainSessionCheckStatus.BLOCKING,
            message=message,
            is_blocking=True,
            details={
                "knowledge_id": knowledge_id,
                "domain": domain,
                "reason": reason,
            },
        )


__all__ = [
    "DefaultDomainKnowledgeAuthority",
    "DomainKnowledgeAuthority",
    "DomainKnowledgeCurrentVerdict",
]
