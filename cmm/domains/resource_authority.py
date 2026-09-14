"""Phase 10.34 – Domain Resource Authority Contracts.

Defines native authority interfaces and verdicts for evaluating domain resource
freshness, temporal policies, and provenance during domain session resumption.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from typing_extensions import Protocol, runtime_checkable

from cmm.domains.resource_contracts import (
    DomainResourceContext,
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
    _deep_freeze,
)
from cmm.domains.resource_resolver import _evaluate_temporal_policy
from cmm.domains.session_contracts import DomainSessionCheckStatus


@dataclass(frozen=True, slots=True)
class DomainResourceCurrentVerdict:
    """Authoritative verdict for a domain resource reference."""

    resource_id: str
    status: DomainSessionCheckStatus
    message: str = ""
    is_blocking: bool = False
    context: DomainResourceContext | None = None
    definition: DomainResourceDefinition | None = None
    temporal_policy: DomainResourceTemporalPolicy | None = None
    details: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not self.resource_id or not isinstance(self.resource_id, str):
            raise ValueError("resource_id must be a non-empty string")
        if not isinstance(self.status, DomainSessionCheckStatus):
            raise TypeError("status must be a DomainSessionCheckStatus")
        object.__setattr__(self, "details", _deep_freeze(self.details))


@runtime_checkable
class DomainResourceAuthority(Protocol):
    """Protocol for authoritative resolution of domain resource freshness and temporal policy."""

    def resolve_resource_freshness(
        self,
        resource_id: str,
        *,
        domain: str | None = None,
        at: datetime | None = None,
    ) -> DomainResourceCurrentVerdict:
        """Resolve the authoritative current freshness verdict for a resource reference."""
        ...


class DefaultDomainResourceAuthority:
    """Default repository-native resource authority.

    Evaluates registered DomainResourceContext and DomainResourceDefinition instances
    using the repository-native temporal policy engine.
    """

    def __init__(
        self,
        resources: Mapping[str, DomainResourceContext] | None = None,
        definitions: Mapping[str, DomainResourceDefinition] | None = None,
    ) -> None:
        self._resources: dict[str, DomainResourceContext] = (
            dict(resources) if resources is not None else {}
        )
        self._definitions: dict[str, DomainResourceDefinition] = (
            dict(definitions) if definitions is not None else {}
        )

    def register_resource(
        self,
        context: DomainResourceContext,
        definition: DomainResourceDefinition | None = None,
    ) -> None:
        self._resources[context.resource_id] = context
        if definition is not None:
            self._definitions[context.resource_id] = definition

    def resolve_resource_freshness(
        self,
        resource_id: str,
        *,
        domain: str | None = None,
        at: datetime | None = None,
    ) -> DomainResourceCurrentVerdict:
        if resource_id not in self._resources:
            return DomainResourceCurrentVerdict(
                resource_id=resource_id,
                status=DomainSessionCheckStatus.BLOCKING,
                message=f"Resource '{resource_id}' not found in authoritative resource registry",
                is_blocking=True,
                details={
                    "resource_id": resource_id,
                    "domain": domain,
                    "reason": "NOT_FOUND",
                },
            )

        ctx = self._resources[resource_id]
        defn = self._definitions.get(resource_id)
        now = at if at is not None else datetime.now(timezone.utc)

        if defn is not None:
            is_valid, reason = _evaluate_temporal_policy(
                context=ctx,
                definition=defn,
                now=now,
            )
            if not is_valid:
                is_stale_window = "stale relative to the validity window" in reason
                status = (
                    DomainSessionCheckStatus.DRIFT
                    if is_stale_window
                    else DomainSessionCheckStatus.BLOCKING
                )
                return DomainResourceCurrentVerdict(
                    resource_id=resource_id,
                    status=status,
                    message=f"Resource '{resource_id}' temporal policy violation: {reason}",
                    is_blocking=not is_stale_window,
                    context=ctx,
                    definition=defn,
                    temporal_policy=defn.temporal_policy,
                    details={
                        "resource_id": resource_id,
                        "domain": domain,
                        "reason": reason,
                        "is_stale_window": is_stale_window,
                    },
                )

        # A registered native definition owns temporal semantics. Only use the
        # narrow valid_until fallback when no native policy is available.
        valid_until = ctx.temporal_scope.get("valid_until")
        if defn is None and valid_until is not None and valid_until < now:
            return DomainResourceCurrentVerdict(
                resource_id=resource_id,
                status=DomainSessionCheckStatus.BLOCKING,
                message=f"Resource '{resource_id}' is expired (valid_until={valid_until.isoformat()} < now={now.isoformat()})",
                is_blocking=True,
                context=ctx,
                definition=defn,
                details={
                    "resource_id": resource_id,
                    "domain": domain,
                    "reason": "EXPIRED",
                },
            )

        return DomainResourceCurrentVerdict(
            resource_id=resource_id,
            status=DomainSessionCheckStatus.PASS,
            message=f"Resource '{resource_id}' is current",
            is_blocking=False,
            context=ctx,
            definition=defn,
            details={"resource_id": resource_id, "domain": domain},
        )


__all__ = [
    "DefaultDomainResourceAuthority",
    "DomainResourceAuthority",
    "DomainResourceCurrentVerdict",
]
