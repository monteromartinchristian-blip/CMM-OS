"""Phase 10.34 — Domain Session Contracts.

Immutable, type-safe, JSON-serializable contracts for Domain Intelligence Session state.
All dataclasses are ``frozen=True``, use ``slots=True``, and never expose mutable state.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import (
    _deep_freeze,
    _deep_unfreeze,
    _ensure_tz_aware,
)
from cmm.domains.credential_policy import contains_high_confidence_credential
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSessionContractError,
    DomainSessionSecurityError,
    DomainSessionSerializationError,
)

# ── Schema Version ────────────────────────────────────────────────────────────

DOMAIN_SESSION_SCHEMA_VERSION: int = 1


# ── Internal Validation & Parsing Helpers ─────────────────────────────────────


def _validate_no_credentials(value: Any, field_name: str) -> None:
    """Recursively validate that value contains no high-confidence credentials."""
    if isinstance(value, str):
        if contains_high_confidence_credential(value):
            raise DomainSessionSecurityError(
                f"High-confidence credential detected in {field_name}",
                field=field_name,
                details={"security_violation": "credential_detected"},
            )
    elif isinstance(value, Mapping):
        for k, v in value.items():
            if isinstance(k, str) and contains_high_confidence_credential(k):
                raise DomainSessionSecurityError(
                    f"High-confidence credential detected in {field_name} key",
                    field=field_name,
                    details={"security_violation": "credential_detected"},
                )
            _validate_no_credentials(
                v, f"{field_name}.{k}" if isinstance(k, str) else field_name
            )
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _validate_no_credentials(item, field_name)


def _reject_unknown_fields(
    data: Mapping[str, Any], known: frozenset[str], cls_name: str
) -> None:
    """Raise DomainSessionSerializationError if data contains unknown fields."""
    unknown = set(data.keys()) - known
    if unknown:
        raise DomainSessionSerializationError(
            f"{cls_name}.from_dict got unknown fields: {sorted(unknown)}",
            field="data",
            details={"unknown_fields": sorted(unknown)},
        )


def _validate_non_empty(val: Any, field_name: str) -> str:
    """Validate that val is a non-empty string."""
    if not isinstance(val, str) or not val.strip():
        raise DomainSessionContractError(
            f"{field_name} must be a non-empty string", field=field_name
        )
    _validate_no_credentials(val, field_name)
    return val.strip()


def _validate_non_empty_serialization(val: Any, field_name: str) -> str:
    """Validate non-empty string for deserialization context."""
    if not isinstance(val, str) or not val.strip():
        raise DomainSessionSerializationError(
            f"{field_name} must be a non-empty string, got {val!r}",
            field=field_name,
        )
    _validate_no_credentials(val, field_name)
    return val.strip()


def _dedupe_tuple(items: Iterable[Any] | None, field_name: str) -> tuple[str, ...]:
    """Deduplicate strings preserving first appearance order."""
    if items is None:
        return ()
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise DomainSessionContractError(
                f"{field_name} items must be non-empty strings",
                field=field_name,
            )
        _validate_no_credentials(item, field_name)
        cleaned = item.strip()
        if cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return tuple(result)


def _validate_bool(val: Any, field_name: str) -> bool:
    """Validate that val is a boolean."""
    if not isinstance(val, bool):
        raise DomainSessionContractError(
            f"{field_name} must be a bool, got {val!r}", field=field_name
        )
    return val


def _validate_bool_serialization(val: Any, field_name: str) -> bool:
    """Validate boolean for deserialization."""
    if not isinstance(val, bool):
        raise DomainSessionSerializationError(
            f"{field_name} must be a boolean, got {val!r}", field=field_name
        )
    return val


def _validate_revision(val: Any) -> int:
    """Validate that revision is a positive integer >= 1."""
    if isinstance(val, bool) or not isinstance(val, int) or val < 1:
        raise DomainSessionContractError(
            f"revision must be an integer >= 1, got {val!r}", field="revision"
        )
    return val


def _validate_revision_serialization(val: Any) -> int:
    """Validate revision for deserialization."""
    if isinstance(val, bool) or not isinstance(val, int) or val < 1:
        raise DomainSessionSerializationError(
            f"revision must be an integer >= 1, got {val!r}", field="revision"
        )
    return val


def _validate_revision_opt_serialization(val: Any, field_name: str = "revision") -> int:
    """Validate non-negative integer revision for deserialization."""
    if isinstance(val, bool) or not isinstance(val, int) or val < 0:
        raise DomainSessionSerializationError(
            f"{field_name} must be an integer >= 0, got {val!r}", field=field_name
        )
    return val


def _validate_actor(val: Any, field_name: str = "actor") -> Any:
    """Validate that actor is JSON-safe and contains no credentials."""
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        _validate_no_credentials(val, field_name)
        return val
    if isinstance(val, Mapping):
        _validate_no_credentials(val, field_name)
        try:
            json.dumps(dict(val), allow_nan=False)
        except Exception as exc:
            raise DomainSessionContractError(
                f"{field_name} must be JSON-serializable, got error: {exc}",
                field=field_name,
            ) from exc
        return _deep_freeze(dict(val))
    if isinstance(val, (list, tuple)):
        _validate_no_credentials(val, field_name)
        try:
            json.dumps(list(val), allow_nan=False)
        except Exception as exc:
            raise DomainSessionContractError(
                f"{field_name} must be JSON-serializable, got error: {exc}",
                field=field_name,
            ) from exc
        return tuple(val)
    raise DomainSessionContractError(
        f"{field_name} must be a JSON-serializable scalar or mapping, got {type(val).__name__}",
        field=field_name,
    )


def _validate_actor_serialization(val: Any, field_name: str = "actor") -> Any:
    """Validate actor during deserialization."""
    if val is None:
        return None
    try:
        return _validate_actor(val, field_name)
    except DomainSessionContractError as exc:
        raise DomainSessionSerializationError(
            exc.message, field=exc.field, details=dict(exc.details)
        ) from exc


def _freeze_nested_refs_map(
    val: Mapping[str, Sequence[str]] | None, field_name: str
) -> MappingProxyType[str, tuple[str, ...]]:
    """Validate and deeply freeze a mapping from domain to tuple of ref strings."""
    if val is None:
        return MappingProxyType({})
    if not isinstance(val, Mapping):
        raise DomainSessionContractError(
            f"{field_name} must be a mapping", field=field_name
        )
    frozen: dict[str, tuple[str, ...]] = {}
    for k, v in val.items():
        if not isinstance(k, str) or not k.strip():
            raise DomainSessionContractError(
                f"{field_name} keys must be non-empty strings", field=field_name
            )
        _validate_no_credentials(k, f"{field_name}_key")
        if not isinstance(v, (list, tuple, set, frozenset)):
            raise DomainSessionContractError(
                f"{field_name}[{k!r}] must be a sequence of strings",
                field=field_name,
            )
        frozen[k.strip()] = _dedupe_tuple(v, f"{field_name}[{k!r}]")
    return MappingProxyType(frozen)


def _freeze_str_str_map(
    val: Mapping[str, str] | None, field_name: str
) -> MappingProxyType[str, str]:
    """Validate and freeze a mapping of string to string."""
    if val is None:
        return MappingProxyType({})
    if not isinstance(val, Mapping):
        raise DomainSessionContractError(
            f"{field_name} must be a mapping", field=field_name
        )
    frozen: dict[str, str] = {}
    for k, v in val.items():
        if not isinstance(k, str) or not k.strip():
            raise DomainSessionContractError(
                f"{field_name} keys must be non-empty strings", field=field_name
            )
        _validate_no_credentials(k, f"{field_name}_key")
        if not isinstance(v, str) or not v.strip():
            raise DomainSessionContractError(
                f"{field_name}[{k!r}] must be a non-empty string",
                field=field_name,
            )
        _validate_no_credentials(v, f"{field_name}[{k!r}]")
        frozen[k.strip()] = v.strip()
    return MappingProxyType(frozen)


def _parse_tz_aware_iso(val: Any, field_name: str) -> datetime:
    """Parse ISO formatted string to a timezone-aware datetime."""
    if not isinstance(val, str) or not val.strip():
        raise DomainSessionSerializationError(
            f"{field_name} must be an ISO 8601 string", field=field_name
        )
    try:
        dt = datetime.fromisoformat(val.strip())
    except Exception as exc:
        raise DomainSessionSerializationError(
            f"{field_name} has invalid ISO format: {val!r}", field=field_name
        ) from exc
    if dt.tzinfo is None:
        raise DomainSessionSerializationError(
            f"{field_name} must be timezone-aware (contain timezone offset)",
            field=field_name,
        )
    return dt


# ── Enums ─────────────────────────────────────────────────────────────────────


class DomainSessionResumeStatus(str, Enum):
    """Canonical status returned after a Domain Session resume attempt."""

    RESUMED = "RESUMED"
    RE_RESOLVED = "RE_RESOLVED"
    RECOMPOSED = "RECOMPOSED"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    BLOCKED = "BLOCKED"
    INCOMPATIBLE = "INCOMPATIBLE"
    FAILED = "FAILED"


class DomainSessionCheckStatus(str, Enum):
    """Status of an individual validation/drift check during resumption."""

    PASS = "PASS"
    CHANGED = "CHANGED"
    DRIFT = "DRIFT"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"
    INCOMPATIBLE = "INCOMPATIBLE"
    FAILED = "FAILED"


# ── Contracts ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DomainSessionCheck:
    """Individual verification/drift check result for Domain Session resumption."""

    name: str
    status: DomainSessionCheckStatus
    message: str
    blocking: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _validate_non_empty(self.name, "name"))
        if not isinstance(self.status, DomainSessionCheckStatus):
            raise DomainSessionContractError(
                f"status must be a DomainSessionCheckStatus, got {self.status!r}",
                field="status",
            )
        object.__setattr__(
            self, "message", _validate_non_empty(self.message, "message")
        )
        if not isinstance(self.blocking, bool):
            raise DomainSessionContractError(
                f"blocking must be a bool, got {self.blocking!r}",
                field="blocking",
            )
        _validate_no_credentials(self.details, "details")
        object.__setattr__(self, "details", _deep_freeze(dict(self.details)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "blocking": self.blocking,
            "details": _deep_unfreeze(self.details),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainSessionCheck:
        if not isinstance(data, Mapping):
            raise DomainSessionSerializationError(
                "DomainSessionCheck.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(
            data,
            frozenset({"name", "status", "message", "blocking", "details"}),
            "DomainSessionCheck",
        )
        for req in ("name", "status", "message"):
            if req not in data:
                raise DomainSessionSerializationError(
                    f"DomainSessionCheck.from_dict missing required field {req!r}",
                    field=req,
                )
        raw_status = data["status"]
        try:
            status = DomainSessionCheckStatus(raw_status)
        except Exception as exc:
            raise DomainSessionSerializationError(
                f"Invalid check status: {raw_status!r}", field="status"
            ) from exc

        return cls(
            name=_validate_non_empty_serialization(data["name"], "name"),
            status=status,
            message=_validate_non_empty_serialization(data["message"], "message"),
            blocking=_validate_bool_serialization(
                data.get("blocking", False), "blocking"
            ),
            details=dict(data.get("details", {})),
        )


@dataclass(frozen=True, slots=True)
class DomainSessionTransition:
    """Immutable audit record of a primary or supporting domain transition."""

    previous_primary_domain: str | None
    new_primary_domain: str
    previous_supporting_domains: tuple[str, ...] = ()
    new_supporting_domains: tuple[str, ...] = ()
    reason_code: str = "INITIAL_RESOLUTION"
    resolution_id: str | None = None
    composition_id: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.previous_primary_domain is not None:
            object.__setattr__(
                self,
                "previous_primary_domain",
                _validate_non_empty(
                    self.previous_primary_domain, "previous_primary_domain"
                ),
            )
        object.__setattr__(
            self,
            "new_primary_domain",
            _validate_non_empty(self.new_primary_domain, "new_primary_domain"),
        )
        object.__setattr__(
            self,
            "previous_supporting_domains",
            _dedupe_tuple(
                self.previous_supporting_domains, "previous_supporting_domains"
            ),
        )
        object.__setattr__(
            self,
            "new_supporting_domains",
            _dedupe_tuple(self.new_supporting_domains, "new_supporting_domains"),
        )
        object.__setattr__(
            self,
            "reason_code",
            _validate_non_empty(self.reason_code, "reason_code"),
        )
        if self.resolution_id is not None:
            object.__setattr__(
                self,
                "resolution_id",
                _validate_non_empty(self.resolution_id, "resolution_id"),
            )
        if self.composition_id is not None:
            object.__setattr__(
                self,
                "composition_id",
                _validate_non_empty(self.composition_id, "composition_id"),
            )
        try:
            _ensure_tz_aware(self.occurred_at, "occurred_at")
        except DomainContractValidationError as exc:
            raise DomainSessionContractError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc

        _validate_no_credentials(self.metadata, "metadata")
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous_primary_domain": self.previous_primary_domain,
            "new_primary_domain": self.new_primary_domain,
            "previous_supporting_domains": list(self.previous_supporting_domains),
            "new_supporting_domains": list(self.new_supporting_domains),
            "reason_code": self.reason_code,
            "resolution_id": self.resolution_id,
            "composition_id": self.composition_id,
            "occurred_at": self.occurred_at.isoformat(),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainSessionTransition:
        if not isinstance(data, Mapping):
            raise DomainSessionSerializationError(
                "DomainSessionTransition.from_dict requires a mapping",
                field="data",
            )
        _reject_unknown_fields(
            data,
            frozenset(
                {
                    "previous_primary_domain",
                    "new_primary_domain",
                    "previous_supporting_domains",
                    "new_supporting_domains",
                    "reason_code",
                    "resolution_id",
                    "composition_id",
                    "occurred_at",
                    "metadata",
                }
            ),
            "DomainSessionTransition",
        )
        for req in ("new_primary_domain", "reason_code", "occurred_at"):
            if req not in data:
                raise DomainSessionSerializationError(
                    f"DomainSessionTransition.from_dict missing required field {req!r}",
                    field=req,
                )
        return cls(
            previous_primary_domain=data.get("previous_primary_domain"),
            new_primary_domain=_validate_non_empty_serialization(
                data["new_primary_domain"], "new_primary_domain"
            ),
            previous_supporting_domains=tuple(
                data.get("previous_supporting_domains", ())
            ),
            new_supporting_domains=tuple(data.get("new_supporting_domains", ())),
            reason_code=_validate_non_empty_serialization(
                data["reason_code"], "reason_code"
            ),
            resolution_id=data.get("resolution_id"),
            composition_id=data.get("composition_id"),
            occurred_at=_parse_tz_aware_iso(data["occurred_at"], "occurred_at"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class DomainSessionContext:
    """Immutable, slotted, reference-first Domain Intelligence Session Context."""

    session_id: str
    primary_domain: str
    supporting_domains: tuple[str, ...] = ()
    domain_versions: Mapping[str, str] = field(default_factory=dict)
    composition_id: str | None = None
    effective_profile: str | None = None
    effective_rule_ids: tuple[str, ...] = ()
    effective_permission_refs: tuple[str, ...] = ()
    active_workflow_refs: tuple[str, ...] = ()
    available_operation_ids: tuple[str, ...] = ()
    domain_resource_refs: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    domain_knowledge_refs: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    pending_domain_question_refs: tuple[str, ...] = ()
    domain_conflict_refs: tuple[str, ...] = ()
    approval_refs: tuple[str, ...] = ()
    partial_result_refs: tuple[str, ...] = ()
    trace_refs: tuple[str, ...] = ()
    domain_transitions: tuple[DomainSessionTransition, ...] = ()
    last_resolution_id: str | None = None
    next_recommended_step: str | None = None
    revision: int = 1
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "session_id",
            _validate_non_empty(self.session_id, "session_id"),
        )
        object.__setattr__(
            self,
            "primary_domain",
            _validate_non_empty(self.primary_domain, "primary_domain"),
        )
        object.__setattr__(
            self,
            "supporting_domains",
            _dedupe_tuple(self.supporting_domains, "supporting_domains"),
        )
        object.__setattr__(
            self,
            "domain_versions",
            _freeze_str_str_map(self.domain_versions, "domain_versions"),
        )
        if self.composition_id is not None:
            object.__setattr__(
                self,
                "composition_id",
                _validate_non_empty(self.composition_id, "composition_id"),
            )
        if self.effective_profile is not None:
            object.__setattr__(
                self,
                "effective_profile",
                _validate_non_empty(self.effective_profile, "effective_profile"),
            )
        object.__setattr__(
            self,
            "effective_rule_ids",
            _dedupe_tuple(self.effective_rule_ids, "effective_rule_ids"),
        )
        object.__setattr__(
            self,
            "effective_permission_refs",
            _dedupe_tuple(self.effective_permission_refs, "effective_permission_refs"),
        )
        object.__setattr__(
            self,
            "active_workflow_refs",
            _dedupe_tuple(self.active_workflow_refs, "active_workflow_refs"),
        )
        object.__setattr__(
            self,
            "available_operation_ids",
            _dedupe_tuple(self.available_operation_ids, "available_operation_ids"),
        )
        object.__setattr__(
            self,
            "domain_resource_refs",
            _freeze_nested_refs_map(self.domain_resource_refs, "domain_resource_refs"),
        )
        object.__setattr__(
            self,
            "domain_knowledge_refs",
            _freeze_nested_refs_map(
                self.domain_knowledge_refs, "domain_knowledge_refs"
            ),
        )
        object.__setattr__(
            self,
            "pending_domain_question_refs",
            _dedupe_tuple(
                self.pending_domain_question_refs,
                "pending_domain_question_refs",
            ),
        )
        object.__setattr__(
            self,
            "domain_conflict_refs",
            _dedupe_tuple(self.domain_conflict_refs, "domain_conflict_refs"),
        )
        object.__setattr__(
            self,
            "approval_refs",
            _dedupe_tuple(self.approval_refs, "approval_refs"),
        )
        object.__setattr__(
            self,
            "partial_result_refs",
            _dedupe_tuple(self.partial_result_refs, "partial_result_refs"),
        )
        object.__setattr__(
            self,
            "trace_refs",
            _dedupe_tuple(self.trace_refs, "trace_refs"),
        )
        for i, tr in enumerate(self.domain_transitions):
            if not isinstance(tr, DomainSessionTransition):
                raise DomainSessionContractError(
                    f"domain_transitions[{i}] must be DomainSessionTransition",
                    field="domain_transitions",
                )
        object.__setattr__(self, "domain_transitions", tuple(self.domain_transitions))
        if self.last_resolution_id is not None:
            object.__setattr__(
                self,
                "last_resolution_id",
                _validate_non_empty(self.last_resolution_id, "last_resolution_id"),
            )
        if self.next_recommended_step is not None:
            object.__setattr__(
                self,
                "next_recommended_step",
                _validate_non_empty(
                    self.next_recommended_step, "next_recommended_step"
                ),
            )
        object.__setattr__(self, "revision", _validate_revision(self.revision))
        try:
            _ensure_tz_aware(self.updated_at, "updated_at")
        except DomainContractValidationError as exc:
            raise DomainSessionContractError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc

        _validate_no_credentials(self.metadata, "metadata")
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        """Serialize context to strict dictionary representation."""
        return {
            "schema_version": DOMAIN_SESSION_SCHEMA_VERSION,
            "session_id": self.session_id,
            "primary_domain": self.primary_domain,
            "supporting_domains": list(self.supporting_domains),
            "domain_versions": dict(self.domain_versions),
            "composition_id": self.composition_id,
            "effective_profile": self.effective_profile,
            "effective_rule_ids": list(self.effective_rule_ids),
            "effective_permission_refs": list(self.effective_permission_refs),
            "active_workflow_refs": list(self.active_workflow_refs),
            "available_operation_ids": list(self.available_operation_ids),
            "domain_resource_refs": {
                k: list(v) for k, v in self.domain_resource_refs.items()
            },
            "domain_knowledge_refs": {
                k: list(v) for k, v in self.domain_knowledge_refs.items()
            },
            "pending_domain_question_refs": list(self.pending_domain_question_refs),
            "domain_conflict_refs": list(self.domain_conflict_refs),
            "approval_refs": list(self.approval_refs),
            "partial_result_refs": list(self.partial_result_refs),
            "trace_refs": list(self.trace_refs),
            "domain_transitions": [tr.to_dict() for tr in self.domain_transitions],
            "last_resolution_id": self.last_resolution_id,
            "next_recommended_step": self.next_recommended_step,
            "revision": self.revision,
            "updated_at": self.updated_at.isoformat(),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainSessionContext:
        """Deserialize context strictly from a dictionary."""
        if not isinstance(data, Mapping):
            raise DomainSessionSerializationError(
                "DomainSessionContext.from_dict requires a mapping",
                field="data",
            )
        _reject_unknown_fields(
            data,
            frozenset(
                {
                    "schema_version",
                    "session_id",
                    "primary_domain",
                    "supporting_domains",
                    "domain_versions",
                    "composition_id",
                    "effective_profile",
                    "effective_rule_ids",
                    "effective_permission_refs",
                    "active_workflow_refs",
                    "available_operation_ids",
                    "domain_resource_refs",
                    "domain_knowledge_refs",
                    "pending_domain_question_refs",
                    "domain_conflict_refs",
                    "approval_refs",
                    "partial_result_refs",
                    "trace_refs",
                    "domain_transitions",
                    "last_resolution_id",
                    "next_recommended_step",
                    "revision",
                    "updated_at",
                    "metadata",
                }
            ),
            "DomainSessionContext",
        )
        schema_version = data.get("schema_version")
        if schema_version != DOMAIN_SESSION_SCHEMA_VERSION:
            raise DomainSessionSerializationError(
                f"Unsupported schema_version: {schema_version!r} (expected {DOMAIN_SESSION_SCHEMA_VERSION})",
                field="schema_version",
            )
        for req in ("session_id", "primary_domain", "updated_at"):
            if req not in data:
                raise DomainSessionSerializationError(
                    f"DomainSessionContext.from_dict missing required field {req!r}",
                    field=req,
                )

        raw_transitions = data.get("domain_transitions", ())
        transitions: list[DomainSessionTransition] = []
        for item in raw_transitions:
            if isinstance(item, DomainSessionTransition):
                transitions.append(item)
            elif isinstance(item, Mapping):
                transitions.append(DomainSessionTransition.from_dict(item))
            else:
                raise DomainSessionSerializationError(
                    f"Invalid domain transition entry: {item!r}",
                    field="domain_transitions",
                )

        return cls(
            session_id=_validate_non_empty_serialization(
                data["session_id"], "session_id"
            ),
            primary_domain=_validate_non_empty_serialization(
                data["primary_domain"], "primary_domain"
            ),
            supporting_domains=tuple(data.get("supporting_domains", ())),
            domain_versions=dict(data.get("domain_versions", {})),
            composition_id=data.get("composition_id"),
            effective_profile=data.get("effective_profile"),
            effective_rule_ids=tuple(data.get("effective_rule_ids", ())),
            effective_permission_refs=tuple(data.get("effective_permission_refs", ())),
            active_workflow_refs=tuple(data.get("active_workflow_refs", ())),
            available_operation_ids=tuple(data.get("available_operation_ids", ())),
            domain_resource_refs=dict(data.get("domain_resource_refs", {})),
            domain_knowledge_refs=dict(data.get("domain_knowledge_refs", {})),
            pending_domain_question_refs=tuple(
                data.get("pending_domain_question_refs", ())
            ),
            domain_conflict_refs=tuple(data.get("domain_conflict_refs", ())),
            approval_refs=tuple(data.get("approval_refs", ())),
            partial_result_refs=tuple(data.get("partial_result_refs", ())),
            trace_refs=tuple(data.get("trace_refs", ())),
            domain_transitions=tuple(transitions),
            last_resolution_id=data.get("last_resolution_id"),
            next_recommended_step=data.get("next_recommended_step"),
            revision=_validate_revision_serialization(data.get("revision", 1)),
            updated_at=_parse_tz_aware_iso(data["updated_at"], "updated_at"),
            metadata=dict(data.get("metadata", {})),
        )

    def to_json(self) -> str:
        """Serialize context to strict JSON string without NaN."""
        return json.dumps(self.to_dict(), allow_nan=False, sort_keys=True)

    @classmethod
    def from_json(cls, json_str: str) -> DomainSessionContext:
        """Deserialize context from JSON string."""
        if not isinstance(json_str, str) or not json_str.strip():
            raise DomainSessionSerializationError(
                "DomainSessionContext.from_json requires a non-empty string",
                field="json_str",
            )
        try:
            data = json.loads(json_str)
        except Exception as exc:
            raise DomainSessionSerializationError(
                f"Malformed JSON: {exc}", field="json_str"
            ) from exc
        return cls.from_dict(data)


@dataclass(frozen=True, slots=True)
class DomainSessionResumeRequest:
    """Request payload for attempting Domain Session resumption."""

    session_id: str
    actor: Any | None = None
    temporal_reference: datetime | None = None
    current_resource_versions: Mapping[str, str] = field(default_factory=dict)
    current_knowledge_versions: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "session_id",
            _validate_non_empty(self.session_id, "session_id"),
        )
        object.__setattr__(
            self,
            "actor",
            _validate_actor(self.actor, "actor"),
        )
        if self.temporal_reference is not None:
            try:
                _ensure_tz_aware(self.temporal_reference, "temporal_reference")
            except DomainContractValidationError as exc:
                raise DomainSessionContractError(
                    exc.message, field=exc.field, details=dict(exc.details)
                ) from exc
        object.__setattr__(
            self,
            "current_resource_versions",
            _freeze_str_str_map(
                self.current_resource_versions, "current_resource_versions"
            ),
        )
        object.__setattr__(
            self,
            "current_knowledge_versions",
            _freeze_str_str_map(
                self.current_knowledge_versions, "current_knowledge_versions"
            ),
        )
        _validate_no_credentials(self.metadata, "metadata")
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        actor_out = (
            _deep_unfreeze(self.actor)
            if isinstance(self.actor, MappingProxyType)
            else self.actor
        )
        return {
            "session_id": self.session_id,
            "actor": actor_out,
            "temporal_reference": self.temporal_reference.isoformat()
            if self.temporal_reference is not None
            else None,
            "current_resource_versions": dict(self.current_resource_versions),
            "current_knowledge_versions": dict(self.current_knowledge_versions),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainSessionResumeRequest:
        if not isinstance(data, Mapping):
            raise DomainSessionSerializationError(
                "DomainSessionResumeRequest.from_dict requires a mapping",
                field="data",
            )
        _reject_unknown_fields(
            data,
            frozenset(
                {
                    "session_id",
                    "actor",
                    "temporal_reference",
                    "current_resource_versions",
                    "current_knowledge_versions",
                    "metadata",
                }
            ),
            "DomainSessionResumeRequest",
        )
        if "session_id" not in data:
            raise DomainSessionSerializationError(
                "DomainSessionResumeRequest.from_dict missing 'session_id'",
                field="session_id",
            )
        temporal_ref = data.get("temporal_reference")
        temporal_dt = (
            _parse_tz_aware_iso(temporal_ref, "temporal_reference")
            if temporal_ref is not None
            else None
        )
        return cls(
            session_id=_validate_non_empty_serialization(
                data["session_id"], "session_id"
            ),
            actor=_validate_actor_serialization(data.get("actor"), "actor"),
            temporal_reference=temporal_dt,
            current_resource_versions=dict(data.get("current_resource_versions", {})),
            current_knowledge_versions=dict(data.get("current_knowledge_versions", {})),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class DomainSessionResumeResult:
    """Structured, side-effect bounded result of a Domain Session resumption."""

    status: DomainSessionResumeStatus
    session_id: str
    previous_revision: int
    resumed_revision: int
    context: DomainSessionContext | None = None
    checks: tuple[DomainSessionCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_findings: tuple[str, ...] = ()
    recovered_question_refs: tuple[str, ...] = ()
    recovered_approval_refs: tuple[str, ...] = ()
    next_recommended_step: str | None = None
    recorded_resumption: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.status, DomainSessionResumeStatus):
            raise DomainSessionContractError(
                f"status must be a DomainSessionResumeStatus, got {self.status!r}",
                field="status",
            )
        object.__setattr__(
            self,
            "session_id",
            _validate_non_empty(self.session_id, "session_id"),
        )
        if self.context is not None and not isinstance(
            self.context, DomainSessionContext
        ):
            raise DomainSessionContractError(
                "context must be a DomainSessionContext or None", field="context"
            )
        for i, chk in enumerate(self.checks):
            if not isinstance(chk, DomainSessionCheck):
                raise DomainSessionContractError(
                    f"checks[{i}] must be DomainSessionCheck", field="checks"
                )
        object.__setattr__(self, "checks", tuple(self.checks))
        object.__setattr__(self, "warnings", _dedupe_tuple(self.warnings, "warnings"))
        object.__setattr__(
            self,
            "blocking_findings",
            _dedupe_tuple(self.blocking_findings, "blocking_findings"),
        )
        object.__setattr__(
            self,
            "recovered_question_refs",
            _dedupe_tuple(self.recovered_question_refs, "recovered_question_refs"),
        )
        object.__setattr__(
            self,
            "recovered_approval_refs",
            _dedupe_tuple(self.recovered_approval_refs, "recovered_approval_refs"),
        )
        if self.next_recommended_step is not None:
            object.__setattr__(
                self,
                "next_recommended_step",
                _validate_non_empty(
                    self.next_recommended_step, "next_recommended_step"
                ),
            )
        if not isinstance(self.recorded_resumption, bool):
            raise DomainSessionContractError(
                f"recorded_resumption must be a bool, got {self.recorded_resumption!r}",
                field="recorded_resumption",
            )
        _validate_no_credentials(self.metadata, "metadata")
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "session_id": self.session_id,
            "previous_revision": self.previous_revision,
            "resumed_revision": self.resumed_revision,
            "context": self.context.to_dict() if self.context is not None else None,
            "checks": [chk.to_dict() for chk in self.checks],
            "warnings": list(self.warnings),
            "blocking_findings": list(self.blocking_findings),
            "recovered_question_refs": list(self.recovered_question_refs),
            "recovered_approval_refs": list(self.recovered_approval_refs),
            "next_recommended_step": self.next_recommended_step,
            "recorded_resumption": self.recorded_resumption,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainSessionResumeResult:
        if not isinstance(data, Mapping):
            raise DomainSessionSerializationError(
                "DomainSessionResumeResult.from_dict requires a mapping",
                field="data",
            )
        _reject_unknown_fields(
            data,
            frozenset(
                {
                    "status",
                    "session_id",
                    "previous_revision",
                    "resumed_revision",
                    "context",
                    "checks",
                    "warnings",
                    "blocking_findings",
                    "recovered_question_refs",
                    "recovered_approval_refs",
                    "next_recommended_step",
                    "recorded_resumption",
                    "metadata",
                }
            ),
            "DomainSessionResumeResult",
        )
        for req in (
            "status",
            "session_id",
            "previous_revision",
            "resumed_revision",
        ):
            if req not in data:
                raise DomainSessionSerializationError(
                    f"DomainSessionResumeResult.from_dict missing required field {req!r}",
                    field=req,
                )
        raw_status = data["status"]
        try:
            status = DomainSessionResumeStatus(raw_status)
        except Exception as exc:
            raise DomainSessionSerializationError(
                f"Invalid resume status: {raw_status!r}", field="status"
            ) from exc

        raw_ctx = data.get("context")
        ctx = None
        if raw_ctx is not None:
            if isinstance(raw_ctx, DomainSessionContext):
                ctx = raw_ctx
            elif isinstance(raw_ctx, Mapping):
                ctx = DomainSessionContext.from_dict(raw_ctx)
            else:
                raise DomainSessionSerializationError(
                    f"Invalid context in resume result: {raw_ctx!r}",
                    field="context",
                )

        checks: list[DomainSessionCheck] = []
        for chk in data.get("checks", ()):
            if isinstance(chk, DomainSessionCheck):
                checks.append(chk)
            elif isinstance(chk, Mapping):
                checks.append(DomainSessionCheck.from_dict(chk))
            else:
                raise DomainSessionSerializationError(
                    f"Invalid check entry: {chk!r}", field="checks"
                )

        return cls(
            status=status,
            session_id=_validate_non_empty_serialization(
                data["session_id"], "session_id"
            ),
            previous_revision=_validate_revision_opt_serialization(
                data["previous_revision"], "previous_revision"
            ),
            resumed_revision=_validate_revision_opt_serialization(
                data["resumed_revision"], "resumed_revision"
            ),
            context=ctx,
            checks=tuple(checks),
            warnings=tuple(data.get("warnings", ())),
            blocking_findings=tuple(data.get("blocking_findings", ())),
            recovered_question_refs=tuple(data.get("recovered_question_refs", ())),
            recovered_approval_refs=tuple(data.get("recovered_approval_refs", ())),
            next_recommended_step=data.get("next_recommended_step"),
            recorded_resumption=_validate_bool_serialization(
                data.get("recorded_resumption", False), "recorded_resumption"
            ),
            metadata=dict(data.get("metadata", {})),
        )


__all__ = [
    "DOMAIN_SESSION_SCHEMA_VERSION",
    "DomainSessionCheck",
    "DomainSessionCheckStatus",
    "DomainSessionContext",
    "DomainSessionResumeRequest",
    "DomainSessionResumeResult",
    "DomainSessionResumeStatus",
    "DomainSessionTransition",
]
