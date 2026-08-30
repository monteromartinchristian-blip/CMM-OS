"""Phase 10.34 — Domain Session Contracts.

Immutable, type-safe, JSON-serializable contracts for Domain Intelligence Session state.
All dataclasses are ``frozen=True``, use ``slots=True``, and never expose mutable state.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import (
    _deep_freeze,
    _ensure_tz_aware,
)
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSessionContractError,
)


def _validate_non_empty(val: Any, field_name: str) -> str:
    """Validate that val is a non-empty string."""
    if not isinstance(val, str) or not val.strip():
        raise DomainSessionContractError(
            f"{field_name} must be a non-empty string", field=field_name
        )
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
                f"{field_name} items must be non-empty strings", field=field_name
            )
        cleaned = item.strip()
        if cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return tuple(result)


def _validate_revision(val: Any) -> int:
    """Validate that revision is a positive integer >= 1."""
    if isinstance(val, bool) or not isinstance(val, int) or val < 1:
        raise DomainSessionContractError(
            f"revision must be an integer >= 1, got {val!r}", field="revision"
        )
    return val


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
        if not isinstance(v, (list, tuple, set, frozenset)):
            raise DomainSessionContractError(
                f"{field_name}[{k!r}] must be a sequence of strings", field=field_name
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
        if not isinstance(v, str) or not v.strip():
            raise DomainSessionContractError(
                f"{field_name}[{k!r}] must be a non-empty string", field=field_name
            )
        frozen[k.strip()] = v.strip()
    return MappingProxyType(frozen)


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
                f"blocking must be a bool, got {self.blocking!r}", field="blocking"
            )
        object.__setattr__(self, "details", _deep_freeze(dict(self.details)))


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
            self, "reason_code", _validate_non_empty(self.reason_code, "reason_code")
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

        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


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
            self, "session_id", _validate_non_empty(self.session_id, "session_id")
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
                self.pending_domain_question_refs, "pending_domain_question_refs"
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
        # Check transitions
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

        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


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
            self, "session_id", _validate_non_empty(self.session_id, "session_id")
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
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


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
            self, "session_id", _validate_non_empty(self.session_id, "session_id")
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
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


__all__ = [
    "DomainSessionCheck",
    "DomainSessionCheckStatus",
    "DomainSessionContext",
    "DomainSessionResumeRequest",
    "DomainSessionResumeResult",
    "DomainSessionResumeStatus",
    "DomainSessionTransition",
]
