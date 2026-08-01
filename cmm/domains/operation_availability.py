"""Pure availability resolution for registered domain operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.enums import ApprovalRequestStatus, PolicyRiskLevel
from cmm.domains.enums import DomainOperationStatus, DomainOperationType
from cmm.domains.errors import (
    DomainOperationContractError,
    DomainOperationSerializationError,
)
from cmm.domains.operation_contracts import (
    DomainOperationDefinition,
    DomainOperationTraceEntry,
    _enum,
    _json_mapping,
    _non_empty,
    _optional_text,
    _reject_unknown,
    _strict_bool,
    _string_tuple,
    _thaw,
)

_AVAILABILITY_CONTEXT_FIELDS = frozenset(
    {
        "primary_domain_id",
        "supporting_domain_ids",
        "granted_permissions",
        "denied_permissions",
        "available_resources",
        "capabilities",
        "available_validation_policy_ids",
        "available_rollback_policy_ids",
        "approval_status",
        "approval_fingerprint",
        "request_fingerprint",
        "metadata",
    }
)

_AVAILABILITY_FIELDS = frozenset(
    {
        "operation_id",
        "operation_version",
        "domain_id",
        "status",
        "reason_codes",
        "required_permissions",
        "granted_permissions",
        "denied_permissions",
        "available_resources",
        "missing_resources",
        "approval_required",
        "validation_policy_id",
        "rollback_policy_id",
        "risk_level",
        "reversible",
        "trace_entries",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainOperationAvailabilityContext:
    primary_domain_id: str
    supporting_domain_ids: tuple[str, ...] = ()
    granted_permissions: tuple[str, ...] = ()
    denied_permissions: tuple[str, ...] = ()
    available_resources: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    available_validation_policy_ids: tuple[str, ...] = ()
    available_rollback_policy_ids: tuple[str, ...] = ()
    approval_status: ApprovalRequestStatus | None = None
    approval_fingerprint: str | None = None
    request_fingerprint: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "primary_domain_id",
            _non_empty(self.primary_domain_id, "primary_domain_id"),
        )
        for attr in (
            "supporting_domain_ids",
            "granted_permissions",
            "denied_permissions",
            "available_resources",
            "capabilities",
            "available_validation_policy_ids",
            "available_rollback_policy_ids",
        ):
            object.__setattr__(self, attr, _string_tuple(getattr(self, attr), attr))
        if self.approval_status is not None:
            object.__setattr__(
                self,
                "approval_status",
                _enum(
                    self.approval_status,
                    ApprovalRequestStatus,
                    "approval_status",
                ),
            )
        object.__setattr__(
            self,
            "approval_fingerprint",
            _optional_text(self.approval_fingerprint, "approval_fingerprint"),
        )
        if not isinstance(self.request_fingerprint, str):
            raise DomainOperationContractError(
                "request_fingerprint must be a string", field="request_fingerprint"
            )
        object.__setattr__(self, "metadata", _json_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_domain_id": self.primary_domain_id,
            "supporting_domain_ids": list(self.supporting_domain_ids),
            "granted_permissions": list(self.granted_permissions),
            "denied_permissions": list(self.denied_permissions),
            "available_resources": list(self.available_resources),
            "capabilities": list(self.capabilities),
            "available_validation_policy_ids": list(
                self.available_validation_policy_ids
            ),
            "available_rollback_policy_ids": list(self.available_rollback_policy_ids),
            "approval_status": self.approval_status.value
            if self.approval_status
            else None,
            "approval_fingerprint": self.approval_fingerprint,
            "request_fingerprint": self.request_fingerprint,
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainOperationAvailabilityContext:
        if not isinstance(data, Mapping):
            raise DomainOperationSerializationError(
                "DomainOperationAvailabilityContext.from_dict requires a mapping"
            )
        _reject_unknown(
            data, _AVAILABILITY_CONTEXT_FIELDS, "DomainOperationAvailabilityContext"
        )
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class DomainOperationAvailability:
    operation_id: str
    operation_version: str
    domain_id: str
    status: DomainOperationStatus
    reason_codes: tuple[str, ...]
    required_permissions: tuple[str, ...]
    granted_permissions: tuple[str, ...]
    denied_permissions: tuple[str, ...]
    available_resources: tuple[str, ...]
    missing_resources: tuple[str, ...]
    approval_required: bool
    validation_policy_id: str | None
    rollback_policy_id: str | None
    risk_level: PolicyRiskLevel
    reversible: bool
    trace_entries: tuple[DomainOperationTraceEntry, ...]
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        for attr in ("operation_id", "operation_version", "domain_id"):
            object.__setattr__(self, attr, _non_empty(getattr(self, attr), attr))
        object.__setattr__(
            self, "status", _enum(self.status, DomainOperationStatus, "status")
        )
        for attr in (
            "reason_codes",
            "required_permissions",
            "granted_permissions",
            "denied_permissions",
            "available_resources",
            "missing_resources",
        ):
            object.__setattr__(self, attr, _string_tuple(getattr(self, attr), attr))
        object.__setattr__(
            self,
            "approval_required",
            _strict_bool(self.approval_required, "approval_required"),
        )
        object.__setattr__(
            self,
            "validation_policy_id",
            _optional_text(self.validation_policy_id, "validation_policy_id"),
        )
        object.__setattr__(
            self,
            "rollback_policy_id",
            _optional_text(self.rollback_policy_id, "rollback_policy_id"),
        )
        object.__setattr__(
            self,
            "risk_level",
            _enum(self.risk_level, PolicyRiskLevel, "risk_level"),
        )
        object.__setattr__(
            self, "reversible", _strict_bool(self.reversible, "reversible")
        )
        if not isinstance(self.trace_entries, (tuple, list)) or not all(
            isinstance(item, DomainOperationTraceEntry) for item in self.trace_entries
        ):
            raise DomainOperationContractError(
                "trace_entries must contain DomainOperationTraceEntry values",
                field="trace_entries",
            )
        object.__setattr__(self, "trace_entries", tuple(self.trace_entries))
        object.__setattr__(self, "metadata", _json_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "operation_version": self.operation_version,
            "domain_id": self.domain_id,
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),
            "required_permissions": list(self.required_permissions),
            "granted_permissions": list(self.granted_permissions),
            "denied_permissions": list(self.denied_permissions),
            "available_resources": list(self.available_resources),
            "missing_resources": list(self.missing_resources),
            "approval_required": self.approval_required,
            "validation_policy_id": self.validation_policy_id,
            "rollback_policy_id": self.rollback_policy_id,
            "risk_level": self.risk_level.value,
            "reversible": self.reversible,
            "trace_entries": [item.to_dict() for item in self.trace_entries],
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainOperationAvailability:
        if not isinstance(data, Mapping):
            raise DomainOperationSerializationError(
                "DomainOperationAvailability.from_dict requires a mapping"
            )
        _reject_unknown(data, _AVAILABILITY_FIELDS, "DomainOperationAvailability")
        values = dict(data)
        values["trace_entries"] = tuple(
            DomainOperationTraceEntry.from_dict(item)
            for item in values.get("trace_entries", ())
        )
        return cls(**values)


class DomainOperationAvailabilityResolver:
    def resolve(
        self,
        definition: DomainOperationDefinition,
        context: DomainOperationAvailabilityContext,
        *,
        now: datetime | None = None,
    ) -> DomainOperationAvailability:
        timestamp = now or datetime.now(timezone.utc)
        reasons: list[str] = []
        status = DomainOperationStatus.AVAILABLE
        required = definition.required_permissions
        denied = tuple(item for item in required if item in context.denied_permissions)
        granted = tuple(
            item
            for item in required
            if item in context.granted_permissions and item not in denied
        )
        missing_permissions = tuple(
            item for item in required if item not in context.granted_permissions
        )
        missing_resources = tuple(
            item
            for item in definition.required_resources
            if item not in context.available_resources
        )

        if not definition.enabled:
            status = DomainOperationStatus.UNAVAILABLE
            reasons.append("availability.disabled")
        elif definition.domain_id not in (
            context.primary_domain_id,
            *context.supporting_domain_ids,
        ):
            status = DomainOperationStatus.BLOCKED
            reasons.append("availability.domain_incompatible")
        elif denied:
            status = DomainOperationStatus.BLOCKED
            reasons.append("availability.permission_denied")
        elif missing_permissions:
            status = DomainOperationStatus.BLOCKED
            reasons.append("availability.permission_missing")
        elif missing_resources:
            status = DomainOperationStatus.UNAVAILABLE
            reasons.append("availability.resource_missing")
        elif (
            definition.operation_type is DomainOperationType.EXTERNAL
            and "external" not in context.capabilities
        ):
            status = DomainOperationStatus.UNAVAILABLE
            reasons.append("availability.external_capability_missing")
        elif (
            definition.validation_policy_id
            and definition.validation_policy_id
            not in context.available_validation_policy_ids
        ):
            status = DomainOperationStatus.UNAVAILABLE
            reasons.append("availability.validation_policy_missing")
        elif (
            definition.reversible
            and definition.rollback_policy_id
            and definition.rollback_policy_id
            not in context.available_rollback_policy_ids
        ):
            status = DomainOperationStatus.BLOCKED
            reasons.append("availability.rollback_policy_missing")
        elif definition.reversible and "transaction" not in context.capabilities:
            status = DomainOperationStatus.UNAVAILABLE
            reasons.append("availability.transaction_capability_missing")
        else:
            approval_required = (
                definition.requires_approval
                or definition.operation_type is DomainOperationType.DESTRUCTIVE
            )
            if approval_required:
                if context.approval_status is None or context.approval_status in (
                    ApprovalRequestStatus.PENDING,
                    ApprovalRequestStatus.POSTPONED,
                ):
                    status = DomainOperationStatus.WAITING_FOR_APPROVAL
                    reasons.append("availability.approval_pending")
                elif context.approval_status is not ApprovalRequestStatus.APPROVED:
                    status = DomainOperationStatus.BLOCKED
                    reasons.append("availability.approval_denied")
                elif (
                    not context.request_fingerprint
                    or context.approval_fingerprint != context.request_fingerprint
                ):
                    status = DomainOperationStatus.BLOCKED
                    reasons.append("availability.approval_mismatch")
        if status is DomainOperationStatus.AVAILABLE:
            reasons.append("availability.available")
        trace = tuple(
            DomainOperationTraceEntry(
                code=f"availability:{index}",
                status=status,
                occurred_at=timestamp,
                reason_code=reason,
            )
            for index, reason in enumerate(reasons)
        )
        return DomainOperationAvailability(
            operation_id=definition.operation_id,
            operation_version=definition.version,
            domain_id=definition.domain_id,
            status=status,
            reason_codes=tuple(reasons),
            required_permissions=required,
            granted_permissions=granted,
            denied_permissions=denied,
            available_resources=context.available_resources,
            missing_resources=missing_resources,
            approval_required=definition.requires_approval
            or definition.operation_type is DomainOperationType.DESTRUCTIVE,
            validation_policy_id=definition.validation_policy_id,
            rollback_policy_id=definition.rollback_policy_id,
            risk_level=definition.risk_level,
            reversible=definition.reversible,
            trace_entries=trace,
            metadata=_json_mapping(context.metadata, "metadata"),
        )


__all__ = [
    "DomainOperationAvailability",
    "DomainOperationAvailabilityContext",
    "DomainOperationAvailabilityResolver",
]
