"""Phase 10.45 MAJOR-03 — Canonical Domain Selection Transition contracts.

Immutable, deterministic and JSON-serializable contracts for the Domain
Selection Transition Coordinator (Audit V1 MAJOR-03 remediation).  The
coordinator translates an interface-originated, permission-validated
membership delta intent (ADD_SUPPORTING | WITHDRAW_SUPPORTING) into exactly
one canonical session revision through the canonical resolution, composition,
transition and session-persistence chain.

These contracts carry command and outcome data only.  No module in this file
performs resolution, registry access, permission evaluation, persistence,
coordination or projection.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from cmm.domains.errors import (
    DomainSelectionTransitionContractError,
    DomainSelectionTransitionSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_contracts import CrossDomainPermissionRequest
from cmm.domains.selection_contracts import DomainSelectionTransition


def _require_non_blank_str(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise DomainSelectionTransitionContractError(
            f"{name} must be a non-blank string",
            field=name,
        )
    normalized = value.strip()
    if not normalized:
        raise DomainSelectionTransitionContractError(
            f"{name} must be a non-blank string",
            field=name,
        )
    return normalized


def _normalize_optional_text(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _require_non_blank_str(value, name)


def _coerce_command_kind(
    value: Any,
) -> DomainSelectionTransitionCommandKind:
    if isinstance(value, DomainSelectionTransitionCommandKind):
        return value
    if isinstance(value, str):
        try:
            return DomainSelectionTransitionCommandKind(value)
        except ValueError:
            pass
    raise DomainSelectionTransitionContractError(
        "kind must be a DomainSelectionTransitionCommandKind member "
        "or one of its canonical string values",
        field="kind",
        details={
            "supported": [
                member.value for member in DomainSelectionTransitionCommandKind
            ]
        },
    )


def _coerce_target_domain(value: Any) -> DomainId:
    if isinstance(value, DomainId):
        return value
    if isinstance(value, str):
        try:
            return DomainId.from_str(value)
        except Exception as exc:
            raise DomainSelectionTransitionContractError(
                f"target_domain must be a canonical domain:<slug> reference, got {value!r}",
                field="target_domain",
            ) from exc
    raise DomainSelectionTransitionContractError(
        "target_domain must be a DomainId or a canonical domain:<slug> string",
        field="target_domain",
    )


def _coerce_status(value: Any) -> DomainSelectionTransitionStatus:
    if isinstance(value, DomainSelectionTransitionStatus):
        return value
    if isinstance(value, str):
        try:
            return DomainSelectionTransitionStatus(value)
        except ValueError:
            pass
    raise DomainSelectionTransitionContractError(
        "status must be a DomainSelectionTransitionStatus member "
        "or one of its canonical string values",
        field="status",
        details={
            "supported": [member.value for member in DomainSelectionTransitionStatus]
        },
    )


def _coerce_permission_evidence(value: Any) -> CrossDomainPermissionRequest:
    if not isinstance(value, CrossDomainPermissionRequest):
        raise DomainSelectionTransitionContractError(
            "permission_request must be a canonical CrossDomainPermissionRequest",
            field="permission_request",
        )
    return value


class DomainSelectionTransitionCommandKind(str, Enum):
    """Canonical membership-delta commands accepted by the coordinator."""

    ADD_SUPPORTING = "add_supporting"
    WITHDRAW_SUPPORTING = "withdraw_supporting"


class DomainSelectionTransitionStatus(str, Enum):
    """Canonical outcome status of a selection transition request."""

    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class DomainSelectionTransitionRequest:
    """Typed membership-delta request submitted to the transition coordinator.

    ``ADD_SUPPORTING`` always carries canonical cross-domain permission
    evidence for the target domain; ``WITHDRAW_SUPPORTING`` never does,
    because withdrawing retracts membership the session already holds.
    """

    request_id: str
    kind: DomainSelectionTransitionCommandKind
    target_domain: DomainId
    session_reference_id: str
    resolution_reference_id: str
    composition_reference_id: str
    reason: str | None = None
    permission_request: CrossDomainPermissionRequest | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _require_non_blank_str(self.request_id, "request_id")
        )
        object.__setattr__(self, "kind", _coerce_command_kind(self.kind))
        object.__setattr__(
            self, "target_domain", _coerce_target_domain(self.target_domain)
        )
        object.__setattr__(
            self,
            "session_reference_id",
            _require_non_blank_str(self.session_reference_id, "session_reference_id"),
        )
        object.__setattr__(
            self,
            "resolution_reference_id",
            _require_non_blank_str(
                self.resolution_reference_id, "resolution_reference_id"
            ),
        )
        object.__setattr__(
            self,
            "composition_reference_id",
            _require_non_blank_str(
                self.composition_reference_id, "composition_reference_id"
            ),
        )
        object.__setattr__(
            self, "reason", _normalize_optional_text(self.reason, "reason")
        )
        if self.kind is DomainSelectionTransitionCommandKind.ADD_SUPPORTING:
            if self.permission_request is None:
                raise DomainSelectionTransitionContractError(
                    "permission_request is required for ADD_SUPPORTING",
                    field="permission_request",
                )
            object.__setattr__(
                self,
                "permission_request",
                _coerce_permission_evidence(self.permission_request),
            )
        else:
            if self.permission_request is not None:
                raise DomainSelectionTransitionContractError(
                    "permission_request must be None for WITHDRAW_SUPPORTING",
                    field="permission_request",
                )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the request to a JSON-safe dictionary."""
        return {
            "request_id": self.request_id,
            "kind": self.kind.value,
            "target_domain": str(self.target_domain),
            "session_reference_id": self.session_reference_id,
            "resolution_reference_id": self.resolution_reference_id,
            "composition_reference_id": self.composition_reference_id,
            "reason": self.reason,
            "permission_request": (
                None
                if self.permission_request is None
                else self.permission_request.to_dict()
            ),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainSelectionTransitionRequest:
        """Deserialize a request from a strict mapping."""
        if not isinstance(data, Mapping):
            raise DomainSelectionTransitionSerializationError(
                "DomainSelectionTransitionRequest.from_dict requires a mapping",
                field="data",
            )
        try:
            permission_raw = data.get("permission_request")
            if permission_raw is not None and not isinstance(permission_raw, Mapping):
                raise DomainSelectionTransitionSerializationError(
                    "permission_request must be a mapping",
                    field="permission_request",
                )
            permission_request = (
                None
                if permission_raw is None
                else CrossDomainPermissionRequest.from_dict(permission_raw)
            )
            return cls(
                request_id=data["request_id"],
                kind=data["kind"],
                target_domain=data["target_domain"],
                session_reference_id=data["session_reference_id"],
                resolution_reference_id=data["resolution_reference_id"],
                composition_reference_id=data["composition_reference_id"],
                reason=data.get("reason"),
                permission_request=permission_request,
            )
        except KeyError as exc:
            raise DomainSelectionTransitionSerializationError(
                f"Missing required field in domain selection transition request: {exc}",
                field=str(exc),
            ) from exc
        except DomainSelectionTransitionContractError as exc:
            raise DomainSelectionTransitionSerializationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class DomainSelectionTransitionResult:
    """Typed outcome of a selection transition request.

    ``ACCEPTED`` outcomes always carry the canonical ``DomainSelectionTransition``
    produced by ``build_domain_selection_transition``; ``BLOCKED`` and
    ``PENDING`` outcomes never persist anything and therefore carry no
    transition.
    """

    request_id: str
    kind: DomainSelectionTransitionCommandKind
    status: DomainSelectionTransitionStatus
    reason_code: str | None = None
    transition: DomainSelectionTransition | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _require_non_blank_str(self.request_id, "request_id")
        )
        object.__setattr__(self, "kind", _coerce_command_kind(self.kind))
        object.__setattr__(self, "status", _coerce_status(self.status))
        object.__setattr__(
            self,
            "reason_code",
            _normalize_optional_text(self.reason_code, "reason_code"),
        )
        if self.status is DomainSelectionTransitionStatus.ACCEPTED:
            if not isinstance(self.transition, DomainSelectionTransition):
                raise DomainSelectionTransitionContractError(
                    "transition is required for an ACCEPTED outcome",
                    field="transition",
                )
        elif self.transition is not None:
            raise DomainSelectionTransitionContractError(
                "transition must be None for non-ACCEPTED outcomes",
                field="transition",
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result to a JSON-safe dictionary."""
        return {
            "request_id": self.request_id,
            "kind": self.kind.value,
            "status": self.status.value,
            "reason_code": self.reason_code,
            "transition": None
            if self.transition is None
            else self.transition.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainSelectionTransitionResult:
        """Deserialize a result from a strict mapping."""
        if not isinstance(data, Mapping):
            raise DomainSelectionTransitionSerializationError(
                "DomainSelectionTransitionResult.from_dict requires a mapping",
                field="data",
            )
        try:
            transition_raw = data.get("transition")
            if transition_raw is not None and not isinstance(transition_raw, Mapping):
                raise DomainSelectionTransitionSerializationError(
                    "transition must be a mapping",
                    field="transition",
                )
            transition = (
                None
                if transition_raw is None
                else DomainSelectionTransition.from_dict(transition_raw)
            )
            return cls(
                request_id=data["request_id"],
                kind=data["kind"],
                status=data["status"],
                reason_code=data.get("reason_code"),
                transition=transition,
            )
        except KeyError as exc:
            raise DomainSelectionTransitionSerializationError(
                f"Missing required field in domain selection transition result: {exc}",
                field=str(exc),
            ) from exc
        except DomainSelectionTransitionContractError as exc:
            raise DomainSelectionTransitionSerializationError(str(exc)) from exc


@runtime_checkable
class DomainSelectionTransitionCoordinator(Protocol):
    """Protocol of the canonical Domain Selection Transition Coordinator.

    Implementations translate an interface-originated, permission-validated
    membership delta request into exactly one canonical ``DomainSessionContext``
    revision through the canonical resolution, composition, transition and
    session-persistence chain — or fail closed leaving every canonical object
    and store untouched.
    """

    def apply(
        self,
        request,
        session,
        resolution,
        composition,
        resolution_context,
    ) -> DomainSelectionTransitionResult: ...


__all__ = [
    "DomainSelectionTransitionCommandKind",
    "DomainSelectionTransitionCoordinator",
    "DomainSelectionTransitionRequest",
    "DomainSelectionTransitionResult",
    "DomainSelectionTransitionStatus",
]
