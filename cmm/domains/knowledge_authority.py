"""Phase 10.34 – Domain Knowledge Authority Contracts.

Defines native authority interfaces and verdicts for evaluating domain knowledge
freshness, validity, and provenance during domain session resumption.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from typing_extensions import Protocol, runtime_checkable

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
    ) -> None:
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
        if knowledge_id not in self._valid_knowledge:
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

        val = self._valid_knowledge[knowledge_id]
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
            details={"knowledge_id": knowledge_id, "domain": domain},
        )


__all__ = [
    "DefaultDomainKnowledgeAuthority",
    "DomainKnowledgeAuthority",
    "DomainKnowledgeCurrentVerdict",
]
