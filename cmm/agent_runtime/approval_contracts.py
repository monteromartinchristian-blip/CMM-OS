"""Phase 9.10 – Human Approval System Contracts.

Defines the immutable, serializable, strictly validated contracts that constitute
the formal Human Approval System of the Autonomous Agent Runtime:

* :class:`ApprovalRequirement` — specification of an approval need before request creation.
* :class:`ApprovalRequest` — explicit, auditable request for human intervention.
* :class:`ApprovalDecision` — individual, immutable human decision record.
* :class:`ApprovalResolution` — aggregated, effective resolution state of a request.

All contracts are:
* `@dataclass(frozen=True, slots=True)`
* strictly validated in ``__post_init__``;
* serializable via ``serialize()`` / ``to_dict()``;
* reconstructible from mapping via ``from_mapping()`` / ``from_dict()``;
* immutable.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from .domain_permission_contracts import PermissionApprovalRequirement
from .enums import (
    ApprovalDecisionType,
    ApprovalRequestStatus,
    ApprovalRequirementSource,
    PolicyRiskLevel,
)
from .errors import InvalidApprovalContractError

# ── Internal Helpers ──────────────────────────────────────────────────────────


def _now_utc() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def _ensure_aware_dt(val: Any, field_name: str) -> datetime:
    """Ensure ``val`` is a timezone-aware ``datetime``."""
    if not isinstance(val, datetime):
        raise InvalidApprovalContractError(
            f"{field_name} must be a datetime instance, got {type(val).__name__}"
        )
    if val.tzinfo is None:
        raise InvalidApprovalContractError(f"{field_name} must be timezone-aware")
    return val


def _parse_dt(val: Any, field_name: str) -> datetime:
    """Parse ISO string or datetime into a timezone-aware datetime."""
    if isinstance(val, datetime):
        return _ensure_aware_dt(val, field_name)
    if isinstance(val, str):
        try:
            parsed = datetime.fromisoformat(val)
        except ValueError as exc:
            raise InvalidApprovalContractError(
                f"Invalid isoformat datetime string for {field_name}: {val!r}"
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    raise InvalidApprovalContractError(
        f"{field_name} must be an ISO string or datetime instance"
    )


def _validate_non_empty_str(val: Any, field_name: str) -> str:
    """Validate that ``val`` is a non-empty string."""
    if not isinstance(val, str) or not val.strip():
        raise InvalidApprovalContractError(f"{field_name} must be a non-empty string")
    return val.strip()


def _validate_optional_str(val: Any, field_name: str) -> str | None:
    """Validate optional string."""
    if val is None:
        return None
    if not isinstance(val, str):
        raise InvalidApprovalContractError(f"{field_name} must be a string or None")
    stripped = val.strip()
    return stripped if stripped else None


def _validate_strict_int(val: Any, field_name: str, min_val: int = 1) -> int:
    """Validate strict integer, rejecting booleans."""
    if isinstance(val, bool) or not isinstance(val, int):
        raise InvalidApprovalContractError(
            f"{field_name} must be an integer, got {type(val).__name__}"
        )
    if val < min_val:
        raise InvalidApprovalContractError(
            f"{field_name} must be >= {min_val}, got {val}"
        )
    return val


def _map_risk_level(risk_val: Any) -> PolicyRiskLevel:
    """Safely map risk value to PolicyRiskLevel."""
    if isinstance(risk_val, PolicyRiskLevel):
        return risk_val
    if hasattr(risk_val, "value"):
        risk_str = str(risk_val.value).lower()
    else:
        risk_str = str(risk_val or "medium").lower()

    if risk_str in ("critical", "blocking"):
        return PolicyRiskLevel.CRITICAL
    if risk_str in ("high", "severe"):
        return PolicyRiskLevel.HIGH
    if risk_str in ("medium", "moderate"):
        return PolicyRiskLevel.MEDIUM
    if risk_str in ("low", "minor"):
        return PolicyRiskLevel.LOW
    if risk_str in ("none", "zero"):
        return PolicyRiskLevel.NONE
    raise InvalidApprovalContractError(f"Invalid PolicyRiskLevel: {risk_val!r}")


def _freeze_str_tuple(items: Any, field_name: str) -> tuple[str, ...]:
    """Validate and freeze a sequence of strings into a tuple."""
    if items is None:
        return ()
    if isinstance(items, str):
        raise InvalidApprovalContractError(
            f"{field_name} must be a sequence of strings, got single string"
        )
    if not isinstance(items, (tuple, list, set, Sequence)):
        raise InvalidApprovalContractError(
            f"{field_name} must be a sequence of strings"
        )
    res: list[str] = []
    for idx, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            raise InvalidApprovalContractError(
                f"Element at index {idx} in {field_name} must be a non-empty string"
            )
        res.append(item.strip())
    return tuple(res)


def _validate_json_serializable(val: Any, field_name: str) -> None:
    """Ensure value can be serialized to JSON."""
    try:
        json.dumps(val)
    except (TypeError, ValueError) as exc:
        raise InvalidApprovalContractError(
            f"{field_name} must contain JSON-serializable values: {exc}"
        ) from exc


def _freeze_dict(mapping: Any, field_name: str) -> MappingProxyType[str, Any]:
    """Validate and freeze a dict/mapping into a MappingProxyType."""
    if mapping is None:
        return MappingProxyType({})
    if not isinstance(mapping, Mapping):
        raise InvalidApprovalContractError(f"{field_name} must be a Mapping")
    res: dict[str, Any] = {}
    for k, v in mapping.items():
        if not isinstance(k, str):
            raise InvalidApprovalContractError(
                f"Keys in {field_name} must be strings, got {type(k).__name__}"
            )
        _validate_json_serializable(v, f"{field_name}[{k}]")
        res[k] = v
    return MappingProxyType(res)


def _compute_request_fingerprint(
    goal_id: str | None,
    workflow_id: str | None,
    operation_id: str | None,
    title: str,
    reason_codes: tuple[str, ...],
    risk_level: PolicyRiskLevel,
    expected_effects: tuple[str, ...],
    possible_side_effects: tuple[str, ...],
    requested_by: str,
    required_approvers: tuple[str, ...],
    minimum_approvals: int,
    rollback_available: bool,
    permission_requirement: PermissionApprovalRequirement | None,
    metadata: MappingProxyType[str, Any],
) -> str:
    """Compute a deterministic SHA-256 fingerprint for request uniqueness and deduplication."""
    payload = {
        "goal_id": goal_id,
        "workflow_id": workflow_id,
        "operation_id": operation_id,
        "title": title,
        "reason_codes": sorted(reason_codes),
        "risk_level": risk_level.value,
        "expected_effects": sorted(expected_effects),
        "possible_side_effects": sorted(possible_side_effects),
        "requested_by": requested_by,
        "required_approvers": sorted(required_approvers),
        "minimum_approvals": minimum_approvals,
        "rollback_available": rollback_available,
        "permission_requirement": (
            permission_requirement.to_dict()
            if permission_requirement is not None
            else None
        ),
        "scope": metadata.get("scope"),
        "operation_parameters": metadata.get("operation_parameters"),
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── Domain Contracts ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ApprovalRequirement:
    """Pre-creation requirement specification for a human approval request.

    Captures context and constraints emitted by Policy, Autonomy, or Workflow
    engines prior to formal request instantiation.
    """

    id: str
    source: ApprovalRequirementSource
    title: str
    description: str
    reason_codes: tuple[str, ...] = ()
    required_approvers: tuple[str, ...] = ()
    minimum_approvals: int = 1
    risk_level: PolicyRiskLevel = PolicyRiskLevel.MEDIUM
    scope: str = "operation"
    agent_run_id: str | None = None
    goal_id: str | None = None
    workflow_id: str | None = None
    operation_id: str | None = None
    expires_at: datetime | None = None
    allow_modifications: bool = True
    allow_postpone: bool = True
    rejection_is_final: bool = True
    allow_supersede: bool = True
    expected_effects: tuple[str, ...] = ()
    possible_side_effects: tuple[str, ...] = ()
    rollback_available: bool = False
    rollback_description: str | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    permission_requirement: PermissionApprovalRequirement | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))

        if isinstance(self.source, str):
            try:
                src_val = ApprovalRequirementSource(self.source)
            except ValueError as exc:
                raise InvalidApprovalContractError(
                    f"Invalid ApprovalRequirementSource: {self.source!r}"
                ) from exc
            object.__setattr__(self, "source", src_val)
        elif not isinstance(self.source, ApprovalRequirementSource):
            raise InvalidApprovalContractError(
                "source must be an ApprovalRequirementSource"
            )

        object.__setattr__(self, "title", _validate_non_empty_str(self.title, "title"))
        object.__setattr__(
            self,
            "description",
            _validate_non_empty_str(self.description, "description"),
        )
        object.__setattr__(
            self, "reason_codes", _freeze_str_tuple(self.reason_codes, "reason_codes")
        )
        object.__setattr__(
            self,
            "required_approvers",
            _freeze_str_tuple(self.required_approvers, "required_approvers"),
        )
        object.__setattr__(
            self,
            "minimum_approvals",
            _validate_strict_int(self.minimum_approvals, "minimum_approvals"),
        )
        object.__setattr__(self, "risk_level", _map_risk_level(self.risk_level))
        object.__setattr__(self, "scope", _validate_non_empty_str(self.scope, "scope"))
        object.__setattr__(
            self,
            "agent_run_id",
            _validate_optional_str(self.agent_run_id, "agent_run_id"),
        )
        object.__setattr__(
            self, "goal_id", _validate_optional_str(self.goal_id, "goal_id")
        )
        object.__setattr__(
            self, "workflow_id", _validate_optional_str(self.workflow_id, "workflow_id")
        )
        object.__setattr__(
            self,
            "operation_id",
            _validate_optional_str(self.operation_id, "operation_id"),
        )
        if isinstance(self.permission_requirement, Mapping):
            object.__setattr__(
                self,
                "permission_requirement",
                PermissionApprovalRequirement.from_dict(self.permission_requirement),
            )
        elif (
            self.permission_requirement is not None
            and not isinstance(
                self.permission_requirement, PermissionApprovalRequirement
            )
        ):
            raise InvalidApprovalContractError(
                "permission_requirement must be a PermissionApprovalRequirement or None"
            )

        if self.expires_at is not None:
            object.__setattr__(
                self, "expires_at", _parse_dt(self.expires_at, "expires_at")
            )

        if not isinstance(self.allow_modifications, bool):
            raise InvalidApprovalContractError("allow_modifications must be a bool")
        if not isinstance(self.allow_postpone, bool):
            raise InvalidApprovalContractError("allow_postpone must be a bool")
        if not isinstance(self.rejection_is_final, bool):
            raise InvalidApprovalContractError("rejection_is_final must be a bool")
        if not isinstance(self.allow_supersede, bool):
            raise InvalidApprovalContractError("allow_supersede must be a bool")

        object.__setattr__(
            self,
            "expected_effects",
            _freeze_str_tuple(self.expected_effects, "expected_effects"),
        )
        object.__setattr__(
            self,
            "possible_side_effects",
            _freeze_str_tuple(self.possible_side_effects, "possible_side_effects"),
        )

        if not isinstance(self.rollback_available, bool):
            raise InvalidApprovalContractError("rollback_available must be a bool")
        object.__setattr__(
            self,
            "rollback_description",
            _validate_optional_str(self.rollback_description, "rollback_description"),
        )
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        return {
            "id": self.id,
            "source": self.source.value,
            "title": self.title,
            "description": self.description,
            "reason_codes": list(self.reason_codes),
            "required_approvers": list(self.required_approvers),
            "minimum_approvals": self.minimum_approvals,
            "risk_level": self.risk_level.value,
            "scope": self.scope,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "workflow_id": self.workflow_id,
            "operation_id": self.operation_id,
            "permission_requirement": (
                self.permission_requirement.to_dict()
                if self.permission_requirement is not None
                else None
            ),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "allow_modifications": self.allow_modifications,
            "allow_postpone": self.allow_postpone,
            "rejection_is_final": self.rejection_is_final,
            "allow_supersede": self.allow_supersede,
            "expected_effects": list(self.expected_effects),
            "possible_side_effects": list(self.possible_side_effects),
            "rollback_available": self.rollback_available,
            "rollback_description": self.rollback_description,
            "metadata": dict(self.metadata),
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> ApprovalRequirement:
        """Construct an ApprovalRequirement from a dictionary/mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidApprovalContractError("mapping must be a Mapping")
        data = dict(mapping)
        return cls(
            id=data.get("id", ""),
            source=data.get("source", ApprovalRequirementSource.RUNTIME),
            title=data.get("title", ""),
            description=data.get("description", ""),
            reason_codes=data.get("reason_codes", ()),
            required_approvers=data.get("required_approvers", ()),
            minimum_approvals=data.get("minimum_approvals", 1),
            risk_level=data.get("risk_level", PolicyRiskLevel.MEDIUM),
            scope=data.get("scope", "operation"),
            agent_run_id=data.get("agent_run_id"),
            goal_id=data.get("goal_id"),
            workflow_id=data.get("workflow_id"),
            operation_id=data.get("operation_id"),
            permission_requirement=data.get("permission_requirement"),
            expires_at=data.get("expires_at"),
            allow_modifications=data.get("allow_modifications", True),
            allow_postpone=data.get("allow_postpone", True),
            rejection_is_final=data.get("rejection_is_final", True),
            allow_supersede=data.get("allow_supersede", True),
            expected_effects=data.get("expected_effects", ()),
            possible_side_effects=data.get("possible_side_effects", ()),
            rollback_available=data.get("rollback_available", False),
            rollback_description=data.get("rollback_description"),
            metadata=data.get("metadata", {}),
        )

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """Structured, persistent request for human intervention."""

    id: str
    title: str
    description: str
    requested_by: str
    agent_run_id: str | None = None
    goal_id: str | None = None
    workflow_id: str | None = None
    operation_id: str | None = None
    reason_codes: tuple[str, ...] = ()
    risk_level: PolicyRiskLevel = PolicyRiskLevel.MEDIUM
    expected_effects: tuple[str, ...] = ()
    possible_side_effects: tuple[str, ...] = ()
    rollback_available: bool = False
    rollback_description: str | None = None
    required_approvers: tuple[str, ...] = ()
    minimum_approvals: int = 1
    expires_at: datetime | None = None
    status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING
    request_fingerprint: str = ""
    superseded_by_request_id: str | None = None
    supersedes_request_id: str | None = None
    created_at: datetime = field(default_factory=_now_utc)
    updated_at: datetime = field(default_factory=_now_utc)
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    permission_requirement: PermissionApprovalRequirement | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(self, "title", _validate_non_empty_str(self.title, "title"))
        object.__setattr__(
            self,
            "description",
            _validate_non_empty_str(self.description, "description"),
        )
        object.__setattr__(
            self,
            "requested_by",
            _validate_non_empty_str(self.requested_by, "requested_by"),
        )

        object.__setattr__(
            self,
            "agent_run_id",
            _validate_optional_str(self.agent_run_id, "agent_run_id"),
        )
        object.__setattr__(
            self, "goal_id", _validate_optional_str(self.goal_id, "goal_id")
        )
        object.__setattr__(
            self, "workflow_id", _validate_optional_str(self.workflow_id, "workflow_id")
        )
        object.__setattr__(
            self,
            "operation_id",
            _validate_optional_str(self.operation_id, "operation_id"),
        )
        if isinstance(self.permission_requirement, Mapping):
            object.__setattr__(
                self,
                "permission_requirement",
                PermissionApprovalRequirement.from_dict(self.permission_requirement),
            )
        elif (
            self.permission_requirement is not None
            and not isinstance(
                self.permission_requirement, PermissionApprovalRequirement
            )
        ):
            raise InvalidApprovalContractError(
                "permission_requirement must be a PermissionApprovalRequirement or None"
            )

        object.__setattr__(
            self, "reason_codes", _freeze_str_tuple(self.reason_codes, "reason_codes")
        )
        object.__setattr__(self, "risk_level", _map_risk_level(self.risk_level))
        object.__setattr__(
            self,
            "expected_effects",
            _freeze_str_tuple(self.expected_effects, "expected_effects"),
        )
        object.__setattr__(
            self,
            "possible_side_effects",
            _freeze_str_tuple(self.possible_side_effects, "possible_side_effects"),
        )

        if not isinstance(self.rollback_available, bool):
            raise InvalidApprovalContractError("rollback_available must be a bool")
        object.__setattr__(
            self,
            "rollback_description",
            _validate_optional_str(self.rollback_description, "rollback_description"),
        )

        object.__setattr__(
            self,
            "required_approvers",
            _freeze_str_tuple(self.required_approvers, "required_approvers"),
        )
        object.__setattr__(
            self,
            "minimum_approvals",
            _validate_strict_int(self.minimum_approvals, "minimum_approvals"),
        )

        if self.expires_at is not None:
            object.__setattr__(
                self, "expires_at", _parse_dt(self.expires_at, "expires_at")
            )

        if isinstance(self.status, str):
            try:
                st_val = ApprovalRequestStatus(self.status)
            except ValueError as exc:
                raise InvalidApprovalContractError(
                    f"Invalid ApprovalRequestStatus: {self.status!r}"
                ) from exc
            object.__setattr__(self, "status", st_val)
        elif not isinstance(self.status, ApprovalRequestStatus):
            raise InvalidApprovalContractError(
                "status must be an ApprovalRequestStatus"
            )

        object.__setattr__(
            self,
            "superseded_by_request_id",
            _validate_optional_str(
                self.superseded_by_request_id, "superseded_by_request_id"
            ),
        )
        object.__setattr__(
            self,
            "supersedes_request_id",
            _validate_optional_str(self.supersedes_request_id, "supersedes_request_id"),
        )

        object.__setattr__(self, "created_at", _parse_dt(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", _parse_dt(self.updated_at, "updated_at"))
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata, "metadata"))

        # Calculate fingerprint if not explicitly supplied
        fp = self.request_fingerprint
        if not fp or not isinstance(fp, str) or not fp.strip():
            fp = _compute_request_fingerprint(
                goal_id=self.goal_id,
                workflow_id=self.workflow_id,
                operation_id=self.operation_id,
                title=self.title,
                reason_codes=self.reason_codes,
                risk_level=self.risk_level,
                expected_effects=self.expected_effects,
                possible_side_effects=self.possible_side_effects,
                requested_by=self.requested_by,
                required_approvers=self.required_approvers,
                minimum_approvals=self.minimum_approvals,
                rollback_available=self.rollback_available,
                permission_requirement=self.permission_requirement,
                metadata=self.metadata,
            )
        object.__setattr__(self, "request_fingerprint", fp.strip())

    @property
    def is_pending(self) -> bool:
        """Check if request is pending human intervention."""
        return self.status == ApprovalRequestStatus.PENDING

    @property
    def is_terminal(self) -> bool:
        """Check if request has reached a terminal status state."""
        return self.status in (
            ApprovalRequestStatus.APPROVED,
            ApprovalRequestStatus.APPROVED_WITH_CHANGES,
            ApprovalRequestStatus.REJECTED,
            ApprovalRequestStatus.EXPIRED,
            ApprovalRequestStatus.CANCELLED,
            ApprovalRequestStatus.SUPERSEDED,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "requested_by": self.requested_by,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "workflow_id": self.workflow_id,
            "operation_id": self.operation_id,
            "permission_requirement": (
                self.permission_requirement.to_dict()
                if self.permission_requirement is not None
                else None
            ),
            "reason_codes": list(self.reason_codes),
            "risk_level": self.risk_level.value,
            "expected_effects": list(self.expected_effects),
            "possible_side_effects": list(self.possible_side_effects),
            "rollback_available": self.rollback_available,
            "rollback_description": self.rollback_description,
            "required_approvers": list(self.required_approvers),
            "minimum_approvals": self.minimum_approvals,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status.value,
            "request_fingerprint": self.request_fingerprint,
            "superseded_by_request_id": self.superseded_by_request_id,
            "supersedes_request_id": self.supersedes_request_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> ApprovalRequest:
        """Construct an ApprovalRequest from a dictionary/mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidApprovalContractError("mapping must be a Mapping")
        data = dict(mapping)
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            requested_by=data.get("requested_by", ""),
            agent_run_id=data.get("agent_run_id"),
            goal_id=data.get("goal_id"),
            workflow_id=data.get("workflow_id"),
            operation_id=data.get("operation_id"),
            permission_requirement=data.get("permission_requirement"),
            reason_codes=data.get("reason_codes", ()),
            risk_level=data.get("risk_level", PolicyRiskLevel.MEDIUM),
            expected_effects=data.get("expected_effects", ()),
            possible_side_effects=data.get("possible_side_effects", ()),
            rollback_available=data.get("rollback_available", False),
            rollback_description=data.get("rollback_description"),
            required_approvers=data.get("required_approvers", ()),
            minimum_approvals=data.get("minimum_approvals", 1),
            expires_at=data.get("expires_at"),
            status=data.get("status", ApprovalRequestStatus.PENDING),
            request_fingerprint=data.get("request_fingerprint", ""),
            superseded_by_request_id=data.get("superseded_by_request_id"),
            supersedes_request_id=data.get("supersedes_request_id"),
            created_at=data.get("created_at", _now_utc()),
            updated_at=data.get("updated_at", _now_utc()),
            metadata=data.get("metadata", {}),
        )

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    """Individual, immutable decision recorded by an authorized actor."""

    id: str
    request_id: str
    decision: ApprovalDecisionType
    actor_id: str
    conditions: tuple[str, ...] = ()
    modified_parameters: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    comment: str | None = None
    created_at: datetime = field(default_factory=_now_utc)
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self, "request_id", _validate_non_empty_str(self.request_id, "request_id")
        )
        object.__setattr__(
            self, "actor_id", _validate_non_empty_str(self.actor_id, "actor_id")
        )

        if isinstance(self.decision, str):
            try:
                dec_val = ApprovalDecisionType(self.decision)
            except ValueError as exc:
                raise InvalidApprovalContractError(
                    f"Invalid ApprovalDecisionType: {self.decision!r}"
                ) from exc
            object.__setattr__(self, "decision", dec_val)
        elif not isinstance(self.decision, ApprovalDecisionType):
            raise InvalidApprovalContractError(
                "decision must be an ApprovalDecisionType"
            )

        object.__setattr__(
            self, "conditions", _freeze_str_tuple(self.conditions, "conditions")
        )
        object.__setattr__(
            self,
            "modified_parameters",
            _freeze_dict(self.modified_parameters, "modified_parameters"),
        )
        object.__setattr__(
            self, "comment", _validate_optional_str(self.comment, "comment")
        )
        object.__setattr__(self, "created_at", _parse_dt(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata, "metadata"))

        # Structural Invariant Checks
        if (
            self.decision != ApprovalDecisionType.APPROVE_WITH_CHANGES
            and self.modified_parameters
        ):
            raise InvalidApprovalContractError(
                f"modified_parameters can only be specified when decision is 'approve_with_changes', got {self.decision.value}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        return {
            "id": self.id,
            "request_id": self.request_id,
            "decision": self.decision.value,
            "actor_id": self.actor_id,
            "conditions": list(self.conditions),
            "modified_parameters": dict(self.modified_parameters),
            "comment": self.comment,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> ApprovalDecision:
        """Construct an ApprovalDecision from a dictionary/mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidApprovalContractError("mapping must be a Mapping")
        data = dict(mapping)
        return cls(
            id=data.get("id", ""),
            request_id=data.get("request_id", ""),
            decision=data.get("decision", ApprovalDecisionType.APPROVE),
            actor_id=data.get("actor_id", ""),
            conditions=data.get("conditions", ()),
            modified_parameters=data.get("modified_parameters", {}),
            comment=data.get("comment"),
            created_at=data.get("created_at", _now_utc()),
            metadata=data.get("metadata", {}),
        )

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class ApprovalResolution:
    """Aggregated, effective resolution state of an approval request."""

    request_id: str
    status: ApprovalRequestStatus
    satisfied: bool
    may_execute: bool
    approval_count: int = 0
    rejection_count: int = 0
    required_approval_count: int = 1
    approved_parameters: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    conditions: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    requires_policy_reevaluation: bool = False
    requires_validation: bool = False
    requires_budget_recalculation: bool = False
    requires_plan_update: bool = False
    resolved_at: datetime = field(default_factory=_now_utc)
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _validate_non_empty_str(self.request_id, "request_id")
        )

        if isinstance(self.status, str):
            try:
                st_val = ApprovalRequestStatus(self.status)
            except ValueError as exc:
                raise InvalidApprovalContractError(
                    f"Invalid ApprovalRequestStatus: {self.status!r}"
                ) from exc
            object.__setattr__(self, "status", st_val)
        elif not isinstance(self.status, ApprovalRequestStatus):
            raise InvalidApprovalContractError(
                "status must be an ApprovalRequestStatus"
            )

        if not isinstance(self.satisfied, bool):
            raise InvalidApprovalContractError("satisfied must be a bool")
        if not isinstance(self.may_execute, bool):
            raise InvalidApprovalContractError("may_execute must be a bool")

        object.__setattr__(
            self,
            "approval_count",
            _validate_strict_int(self.approval_count, "approval_count", min_val=0),
        )
        object.__setattr__(
            self,
            "rejection_count",
            _validate_strict_int(self.rejection_count, "rejection_count", min_val=0),
        )
        object.__setattr__(
            self,
            "required_approval_count",
            _validate_strict_int(
                self.required_approval_count, "required_approval_count", min_val=1
            ),
        )

        object.__setattr__(
            self,
            "approved_parameters",
            _freeze_dict(self.approved_parameters, "approved_parameters"),
        )
        object.__setattr__(
            self, "conditions", _freeze_str_tuple(self.conditions, "conditions")
        )
        object.__setattr__(
            self, "reason_codes", _freeze_str_tuple(self.reason_codes, "reason_codes")
        )

        if not isinstance(self.requires_policy_reevaluation, bool):
            raise InvalidApprovalContractError(
                "requires_policy_reevaluation must be a bool"
            )
        if not isinstance(self.requires_validation, bool):
            raise InvalidApprovalContractError("requires_validation must be a bool")
        if not isinstance(self.requires_budget_recalculation, bool):
            raise InvalidApprovalContractError(
                "requires_budget_recalculation must be a bool"
            )
        if not isinstance(self.requires_plan_update, bool):
            raise InvalidApprovalContractError("requires_plan_update must be a bool")

        object.__setattr__(
            self, "resolved_at", _parse_dt(self.resolved_at, "resolved_at")
        )
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata, "metadata"))

        # Invariant: If not satisfied or not approved, may_execute MUST be False
        if not self.satisfied and self.may_execute:
            raise InvalidApprovalContractError(
                "may_execute cannot be True when satisfied is False"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "satisfied": self.satisfied,
            "may_execute": self.may_execute,
            "approval_count": self.approval_count,
            "rejection_count": self.rejection_count,
            "required_approval_count": self.required_approval_count,
            "approved_parameters": dict(self.approved_parameters),
            "conditions": list(self.conditions),
            "reason_codes": list(self.reason_codes),
            "requires_policy_reevaluation": self.requires_policy_reevaluation,
            "requires_validation": self.requires_validation,
            "requires_budget_recalculation": self.requires_budget_recalculation,
            "requires_plan_update": self.requires_plan_update,
            "resolved_at": self.resolved_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    serialize = to_dict

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> ApprovalResolution:
        """Construct an ApprovalResolution from a dictionary/mapping."""
        if not isinstance(mapping, Mapping):
            raise InvalidApprovalContractError("mapping must be a Mapping")
        data = dict(mapping)
        return cls(
            request_id=data.get("request_id", ""),
            status=data.get("status", ApprovalRequestStatus.PENDING),
            satisfied=data.get("satisfied", False),
            may_execute=data.get("may_execute", False),
            approval_count=data.get("approval_count", 0),
            rejection_count=data.get("rejection_count", 0),
            required_approval_count=data.get("required_approval_count", 1),
            approved_parameters=data.get("approved_parameters", {}),
            conditions=data.get("conditions", ()),
            reason_codes=data.get("reason_codes", ()),
            requires_policy_reevaluation=data.get(
                "requires_policy_reevaluation", False
            ),
            requires_validation=data.get("requires_validation", False),
            requires_budget_recalculation=data.get(
                "requires_budget_recalculation", False
            ),
            requires_plan_update=data.get("requires_plan_update", False),
            resolved_at=data.get("resolved_at", _now_utc()),
            metadata=data.get("metadata", {}),
        )

    from_dict = from_mapping


@dataclass(frozen=True, slots=True)
class ApprovalConsumptionEvidence:
    """Structured evidence produced by validate_and_consume.

    Contains all information required for traceability (section 8)
    without storing intermediate reasoning or sensitive content by value.
    """

    request_id: str
    requirement_id: str | None = None
    actor_id: str = ""
    session_id: str = ""
    domain_id: str = ""
    target_domain: str | None = None
    action: str = ""
    scope: str = "operation"
    one_time: bool = True
    reusable: bool = False
    consumed: bool = False
    granted: bool = False
    validated_at: datetime = field(default_factory=_now_utc)
    denial_reason: str | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _validate_non_empty_str(self.request_id, "request_id")
        )
        if self.requirement_id is not None:
            object.__setattr__(
                self,
                "requirement_id",
                _validate_non_empty_str(self.requirement_id, "requirement_id"),
            )
        for name in ("actor_id", "session_id", "domain_id", "action", "scope"):
            val = getattr(self, name)
            if val:
                object.__setattr__(self, name, val.strip())
        if self.target_domain is not None:
            object.__setattr__(
                self,
                "target_domain",
                _validate_optional_str(self.target_domain, "target_domain"),
            )
        if not isinstance(self.one_time, bool):
            raise InvalidApprovalContractError("one_time must be a bool")
        if not isinstance(self.reusable, bool):
            raise InvalidApprovalContractError("reusable must be a bool")
        if not isinstance(self.consumed, bool):
            raise InvalidApprovalContractError("consumed must be a bool")
        if not isinstance(self.granted, bool):
            raise InvalidApprovalContractError("granted must be a bool")
        object.__setattr__(
            self, "validated_at", _parse_dt(self.validated_at, "validated_at")
        )
        if self.denial_reason is not None:
            object.__setattr__(
                self,
                "denial_reason",
                _validate_optional_str(self.denial_reason, "denial_reason"),
            )
        object.__setattr__(self, "metadata", _freeze_dict(self.metadata, "metadata"))

        if self.granted and self.denial_reason is not None:
            raise InvalidApprovalContractError(
                "granted evidence cannot have a denial_reason"
            )
        if not self.granted and self.denial_reason is None:
            raise InvalidApprovalContractError(
                "denied evidence must specify a denial_reason"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "requirement_id": self.requirement_id,
            "actor_id": self.actor_id,
            "session_id": self.session_id,
            "domain_id": self.domain_id,
            "target_domain": self.target_domain,
            "action": self.action,
            "scope": self.scope,
            "one_time": self.one_time,
            "reusable": self.reusable,
            "consumed": self.consumed,
            "granted": self.granted,
            "validated_at": self.validated_at.isoformat(),
            "denial_reason": self.denial_reason,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> ApprovalConsumptionEvidence:
        if not isinstance(data, Mapping):
            raise InvalidApprovalContractError(
                "ApprovalConsumptionEvidence.from_mapping requires a mapping"
            )
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise InvalidApprovalContractError(
                f"unknown ApprovalConsumptionEvidence fields: {sorted(unknown)}"
            )
        values = dict(data)
        if isinstance(values.get("validated_at"), str):
            values["validated_at"] = datetime.fromisoformat(values["validated_at"])
        return cls(**values)

    from_dict = from_mapping

    serialize = to_dict
