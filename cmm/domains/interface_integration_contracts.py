"""Phase 10.45 - immutable, interface-neutral Domain interface integration contracts.

The contracts in this module are the single deterministic projection seam through
which future interfaces consume canonical Domain Intelligence state and submit
tightly controlled Domain Selector intents. They are reference-oriented, frozen,
slotted, JSON-serializable, and free of mutable nested authority payloads.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from cmm.domains.errors import (
    DomainInterfaceContractError,
    DomainInterfaceSerializationError,
)

__all__ = [
    "ConversationalDomainView",
    "CrossDomainInterfaceView",
    "DomainCenterDomainView",
    "DomainCenterView",
    "DomainInterfaceIntent",
    "DomainInterfaceIntentKind",
    "DomainInterfaceIntentResult",
    "DomainInterfaceProjection",
    "DomainInterfaceProjectionRequest",
    "DomainInterfaceReference",
    "DomainInterfaceStatus",
    "DomainInterfaceViewKind",
    "DomainReviewCenterView",
    "DomainReviewItemView",
    "DomainSelectorView",
]

_HEX64_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _require_non_blank_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainInterfaceContractError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_hex64(value: Any, field_name: str) -> str:
    val = _require_non_blank_str(value, field_name)
    if not _HEX64_PATTERN.match(val):
        raise DomainInterfaceContractError(
            f"{field_name} must be a 64-character lowercase hex digest"
        )
    return val


def _normalize_refs(values: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise DomainInterfaceContractError(
            f"{field_name} must be a sequence of non-empty strings"
        )
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        ref = _require_non_blank_str(value, field_name)
        if ref not in seen:
            seen.add(ref)
            normalized.append(ref)
    return tuple(normalized)


def _coerce_enum(value: Any, enum_type: type[Enum], field_name: str) -> Enum:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except (ValueError, TypeError):
        raise DomainInterfaceContractError(
            f"{field_name} must be a valid {enum_type.__name__} value"
        ) from None


def _validate_confidence(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DomainInterfaceContractError(
            f"{field_name} must be a float in the closed interval [0.0, 1.0]"
        )
    confidence = float(value)
    if not (0.0 <= confidence <= 1.0):
        raise DomainInterfaceContractError(
            f"{field_name} must be in the closed interval [0.0, 1.0]"
        )
    return confidence


def _thaw_json_value(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return {key: _thaw_json_value(val) for key, val in sorted(obj.items())}
    if isinstance(obj, (tuple, list, set, frozenset)):
        return [_thaw_json_value(val) for val in obj]
    if hasattr(obj, "to_dict"):
        return _thaw_json_value(obj.to_dict())
    if isinstance(obj, Enum):
        return _thaw_json_value(obj.value)
    return obj


def _canonical_json(data: Any) -> str:
    return json.dumps(
        _thaw_json_value(data), sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _sha256_digest(data: Any) -> str:
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


class DomainInterfaceViewKind(str, Enum):
    CONVERSATIONAL = "conversational"
    SELECTOR = "selector"
    DOMAIN_CENTER = "domain_center"
    CROSS_DOMAIN = "cross_domain"
    REVIEW_CENTER = "review_center"


class DomainInterfaceIntentKind(str, Enum):
    SELECT_PRIMARY = "select_primary"
    AUTO_RESOLVE = "auto_resolve"
    ADD_SUPPORTING = "add_supporting"
    WITHDRAW_SUPPORTING = "withdraw_supporting"
    EXPLAIN_SELECTION = "explain_selection"
    REQUEST_POLICY_CHANGE = "request_policy_change"


class DomainInterfaceStatus(str, Enum):
    READY = "ready"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class DomainInterfaceReference:
    """Validated interface-neutral reference to one canonical object."""

    reference_id: str
    category: str
    domain_id: str | None = None

    def __post_init__(self) -> None:
        ref_id = _require_non_blank_str(self.reference_id, "reference_id")
        category = _require_non_blank_str(self.category, "category")
        domain_id = self.domain_id
        if domain_id is not None:
            domain_id = _require_non_blank_str(domain_id, "domain_id")
        object.__setattr__(self, "reference_id", ref_id)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "domain_id", domain_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_id": self.reference_id,
            "category": self.category,
            "domain_id": self.domain_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainInterfaceReference:
        try:
            return cls(
                reference_id=data["reference_id"],
                category=data["category"],
                domain_id=data.get("domain_id"),
            )
        except KeyError as exc:
            raise DomainInterfaceSerializationError(
                f"Missing required field in reference: {exc}"
            ) from exc
        except DomainInterfaceContractError as exc:
            raise DomainInterfaceSerializationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class ConversationalDomainView:
    """Authorized references for conversational Domain Intelligence context."""

    primary_domain: str
    supporting_domains: tuple[str, ...]
    workflow_refs: tuple[str, ...]
    question_refs: tuple[str, ...]
    approval_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    contradiction_refs: tuple[str, ...]
    result_refs: tuple[str, ...]
    memory_proposal_refs: tuple[str, ...]
    confidence: float | None
    warning_refs: tuple[str, ...]
    status: DomainInterfaceStatus

    def __post_init__(self) -> None:
        primary_domain = _require_non_blank_str(self.primary_domain, "primary_domain")
        supporting_domains = _normalize_refs(
            self.supporting_domains, "supporting_domains"
        )
        workflow_refs = _normalize_refs(self.workflow_refs, "workflow_refs")
        question_refs = _normalize_refs(self.question_refs, "question_refs")
        approval_refs = _normalize_refs(self.approval_refs, "approval_refs")
        source_refs = _normalize_refs(self.source_refs, "source_refs")
        contradiction_refs = _normalize_refs(
            self.contradiction_refs, "contradiction_refs"
        )
        result_refs = _normalize_refs(self.result_refs, "result_refs")
        memory_proposal_refs = _normalize_refs(
            self.memory_proposal_refs, "memory_proposal_refs"
        )
        warning_refs = _normalize_refs(self.warning_refs, "warning_refs")
        confidence = _validate_confidence(self.confidence, "confidence")
        status = _coerce_enum(self.status, DomainInterfaceStatus, "status")
        if primary_domain in supporting_domains:
            raise DomainInterfaceContractError(
                "primary_domain must not also appear in supporting_domains"
            )
        object.__setattr__(self, "primary_domain", primary_domain)
        object.__setattr__(self, "supporting_domains", supporting_domains)
        object.__setattr__(self, "workflow_refs", workflow_refs)
        object.__setattr__(self, "question_refs", question_refs)
        object.__setattr__(self, "approval_refs", approval_refs)
        object.__setattr__(self, "source_refs", source_refs)
        object.__setattr__(self, "contradiction_refs", contradiction_refs)
        object.__setattr__(self, "result_refs", result_refs)
        object.__setattr__(self, "memory_proposal_refs", memory_proposal_refs)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "warning_refs", warning_refs)
        object.__setattr__(self, "status", status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_domain": self.primary_domain,
            "supporting_domains": list(self.supporting_domains),
            "workflow_refs": list(self.workflow_refs),
            "question_refs": list(self.question_refs),
            "approval_refs": list(self.approval_refs),
            "source_refs": list(self.source_refs),
            "contradiction_refs": list(self.contradiction_refs),
            "result_refs": list(self.result_refs),
            "memory_proposal_refs": list(self.memory_proposal_refs),
            "confidence": self.confidence,
            "warning_refs": list(self.warning_refs),
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ConversationalDomainView:
        try:
            return cls(
                primary_domain=data["primary_domain"],
                supporting_domains=tuple(data.get("supporting_domains", ())),
                workflow_refs=tuple(data.get("workflow_refs", ())),
                question_refs=tuple(data.get("question_refs", ())),
                approval_refs=tuple(data.get("approval_refs", ())),
                source_refs=tuple(data.get("source_refs", ())),
                contradiction_refs=tuple(data.get("contradiction_refs", ())),
                result_refs=tuple(data.get("result_refs", ())),
                memory_proposal_refs=tuple(data.get("memory_proposal_refs", ())),
                confidence=data["confidence"],
                warning_refs=tuple(data.get("warning_refs", ())),
                status=DomainInterfaceStatus(data["status"]),
            )
        except KeyError as exc:
            raise DomainInterfaceSerializationError(
                f"Missing required field in conversational view: {exc}"
            ) from exc
        except (DomainInterfaceContractError, ValueError) as exc:
            raise DomainInterfaceSerializationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class DomainSelectorView:
    """Authorized canonical selection state for the Domain Selector."""

    primary_domain: str
    supporting_domains: tuple[str, ...]
    rejected_domains: tuple[str, ...]
    ambiguous_domains: tuple[str, ...]
    reason_refs: tuple[str, ...]
    requires_clarification: bool
    status: DomainInterfaceStatus

    def __post_init__(self) -> None:
        primary_domain = _require_non_blank_str(self.primary_domain, "primary_domain")
        supporting_domains = _normalize_refs(
            self.supporting_domains, "supporting_domains"
        )
        rejected_domains = _normalize_refs(self.rejected_domains, "rejected_domains")
        ambiguous_domains = _normalize_refs(self.ambiguous_domains, "ambiguous_domains")
        reason_refs = _normalize_refs(self.reason_refs, "reason_refs")
        status = _coerce_enum(self.status, DomainInterfaceStatus, "status")
        object.__setattr__(self, "primary_domain", primary_domain)
        object.__setattr__(self, "supporting_domains", supporting_domains)
        object.__setattr__(self, "rejected_domains", rejected_domains)
        object.__setattr__(self, "ambiguous_domains", ambiguous_domains)
        object.__setattr__(self, "reason_refs", reason_refs)
        object.__setattr__(
            self, "requires_clarification", bool(self.requires_clarification)
        )
        object.__setattr__(self, "status", status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_domain": self.primary_domain,
            "supporting_domains": list(self.supporting_domains),
            "rejected_domains": list(self.rejected_domains),
            "ambiguous_domains": list(self.ambiguous_domains),
            "reason_refs": list(self.reason_refs),
            "requires_clarification": self.requires_clarification,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainSelectorView:
        try:
            return cls(
                primary_domain=data["primary_domain"],
                supporting_domains=tuple(data.get("supporting_domains", ())),
                rejected_domains=tuple(data.get("rejected_domains", ())),
                ambiguous_domains=tuple(data.get("ambiguous_domains", ())),
                reason_refs=tuple(data.get("reason_refs", ())),
                requires_clarification=bool(data["requires_clarification"]),
                status=DomainInterfaceStatus(data["status"]),
            )
        except KeyError as exc:
            raise DomainInterfaceSerializationError(
                f"Missing required field in selector view: {exc}"
            ) from exc
        except (DomainInterfaceContractError, ValueError) as exc:
            raise DomainInterfaceSerializationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class DomainCenterDomainView:
    """One installed domain entry in the deterministic Domain Center projection."""

    domain_id: str
    status: str
    enabled: bool
    version: str
    capability_refs: tuple[str, ...] = ()
    permission_refs: tuple[str, ...] = ()
    operation_refs: tuple[str, ...] = ()
    workflow_refs: tuple[str, ...] = ()
    metric_refs: tuple[str, ...] = ()
    error_refs: tuple[str, ...] = ()
    update_status: str = "unknown"

    def __post_init__(self) -> None:
        domain_id = _require_non_blank_str(self.domain_id, "domain_id")
        status = _require_non_blank_str(self.status, "status")
        version = _require_non_blank_str(self.version, "version")
        capability_refs = _normalize_refs(self.capability_refs, "capability_refs")
        permission_refs = _normalize_refs(self.permission_refs, "permission_refs")
        operation_refs = _normalize_refs(self.operation_refs, "operation_refs")
        workflow_refs = _normalize_refs(self.workflow_refs, "workflow_refs")
        metric_refs = _normalize_refs(self.metric_refs, "metric_refs")
        error_refs = _normalize_refs(self.error_refs, "error_refs")
        update_status = _require_non_blank_str(self.update_status, "update_status")
        object.__setattr__(self, "domain_id", domain_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "enabled", bool(self.enabled))
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "capability_refs", capability_refs)
        object.__setattr__(self, "permission_refs", permission_refs)
        object.__setattr__(self, "operation_refs", operation_refs)
        object.__setattr__(self, "workflow_refs", workflow_refs)
        object.__setattr__(self, "metric_refs", metric_refs)
        object.__setattr__(self, "error_refs", error_refs)
        object.__setattr__(self, "update_status", update_status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "status": self.status,
            "enabled": self.enabled,
            "version": self.version,
            "capability_refs": list(self.capability_refs),
            "permission_refs": list(self.permission_refs),
            "operation_refs": list(self.operation_refs),
            "workflow_refs": list(self.workflow_refs),
            "metric_refs": list(self.metric_refs),
            "error_refs": list(self.error_refs),
            "update_status": self.update_status,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainCenterDomainView:
        try:
            return cls(
                domain_id=data["domain_id"],
                status=data["status"],
                enabled=bool(data["enabled"]),
                version=data["version"],
                capability_refs=tuple(data.get("capability_refs", ())),
                permission_refs=tuple(data.get("permission_refs", ())),
                operation_refs=tuple(data.get("operation_refs", ())),
                workflow_refs=tuple(data.get("workflow_refs", ())),
                metric_refs=tuple(data.get("metric_refs", ())),
                error_refs=tuple(data.get("error_refs", ())),
                update_status=data.get("update_status", "unknown"),
            )
        except KeyError as exc:
            raise DomainInterfaceSerializationError(
                f"Missing required field in domain center domain view: {exc}"
            ) from exc
        except DomainInterfaceContractError as exc:
            raise DomainInterfaceSerializationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class DomainCenterView:
    """Deterministic projection of canonical domain lifecycle state."""

    domains: tuple[DomainCenterDomainView, ...]

    def __post_init__(self) -> None:
        if isinstance(self.domains, str) or not isinstance(self.domains, Sequence):
            raise DomainInterfaceContractError(
                "domains must be a sequence of DomainCenterDomainView entries"
            )
        entries = list(self.domains)
        for entry in entries:
            if type(entry) is not DomainCenterDomainView:
                raise DomainInterfaceContractError(
                    "domains must contain only canonical DomainCenterDomainView entries"
                )
        entries.sort(key=lambda entry: entry.domain_id)
        object.__setattr__(self, "domains", tuple(entries))

    def to_dict(self) -> dict[str, Any]:
        return {"domains": [entry.to_dict() for entry in self.domains]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainCenterView:
        try:
            return cls(
                domains=tuple(
                    DomainCenterDomainView.from_dict(entry)
                    for entry in data.get("domains", ())
                )
            )
        except (DomainInterfaceContractError, DomainInterfaceSerializationError) as exc:
            if isinstance(exc, DomainInterfaceContractError):
                raise DomainInterfaceSerializationError(str(exc)) from exc
            raise


@dataclass(frozen=True, slots=True)
class CrossDomainInterfaceView:
    """Authorized canonical cross-domain state for interface projection."""

    primary_domain: str
    supporting_domains: tuple[str, ...]
    transfer_refs: tuple[str, ...]
    dependency_refs: tuple[str, ...]
    conflict_refs: tuple[str, ...]
    consolidated_result_ref: str | None
    status: DomainInterfaceStatus

    def __post_init__(self) -> None:
        primary_domain = _require_non_blank_str(self.primary_domain, "primary_domain")
        supporting_domains = _normalize_refs(
            self.supporting_domains, "supporting_domains"
        )
        transfer_refs = _normalize_refs(self.transfer_refs, "transfer_refs")
        dependency_refs = _normalize_refs(self.dependency_refs, "dependency_refs")
        conflict_refs = _normalize_refs(self.conflict_refs, "conflict_refs")
        consolidated_result_ref = self.consolidated_result_ref
        if consolidated_result_ref is not None:
            consolidated_result_ref = _require_non_blank_str(
                consolidated_result_ref, "consolidated_result_ref"
            )
        status = _coerce_enum(self.status, DomainInterfaceStatus, "status")
        object.__setattr__(self, "primary_domain", primary_domain)
        object.__setattr__(self, "supporting_domains", supporting_domains)
        object.__setattr__(self, "transfer_refs", transfer_refs)
        object.__setattr__(self, "dependency_refs", dependency_refs)
        object.__setattr__(self, "conflict_refs", conflict_refs)
        object.__setattr__(self, "consolidated_result_ref", consolidated_result_ref)
        object.__setattr__(self, "status", status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_domain": self.primary_domain,
            "supporting_domains": list(self.supporting_domains),
            "transfer_refs": list(self.transfer_refs),
            "dependency_refs": list(self.dependency_refs),
            "conflict_refs": list(self.conflict_refs),
            "consolidated_result_ref": self.consolidated_result_ref,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CrossDomainInterfaceView:
        try:
            return cls(
                primary_domain=data["primary_domain"],
                supporting_domains=tuple(data.get("supporting_domains", ())),
                transfer_refs=tuple(data.get("transfer_refs", ())),
                dependency_refs=tuple(data.get("dependency_refs", ())),
                conflict_refs=tuple(data.get("conflict_refs", ())),
                consolidated_result_ref=data.get("consolidated_result_ref"),
                status=DomainInterfaceStatus(data["status"]),
            )
        except KeyError as exc:
            raise DomainInterfaceSerializationError(
                f"Missing required field in cross-domain view: {exc}"
            ) from exc
        except (DomainInterfaceContractError, ValueError) as exc:
            raise DomainInterfaceSerializationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class DomainReviewItemView:
    """One review-required canonical reference in the Review Center view."""

    review_ref: str
    category: str
    state: str
    domain_id: str | None = None
    operation_ref: str | None = None
    workflow_ref: str | None = None
    session_ref: str | None = None
    reason_ref: str | None = None

    def __post_init__(self) -> None:
        review_ref = _require_non_blank_str(self.review_ref, "review_ref")
        category = _require_non_blank_str(self.category, "category")
        state = _require_non_blank_str(self.state, "state")
        domain_id = _optional_required_str(self.domain_id, "domain_id")
        operation_ref = _optional_required_str(self.operation_ref, "operation_ref")
        workflow_ref = _optional_required_str(self.workflow_ref, "workflow_ref")
        session_ref = _optional_required_str(self.session_ref, "session_ref")
        reason_ref = _optional_required_str(self.reason_ref, "reason_ref")
        object.__setattr__(self, "review_ref", review_ref)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "domain_id", domain_id)
        object.__setattr__(self, "operation_ref", operation_ref)
        object.__setattr__(self, "workflow_ref", workflow_ref)
        object.__setattr__(self, "session_ref", session_ref)
        object.__setattr__(self, "reason_ref", reason_ref)

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_ref": self.review_ref,
            "category": self.category,
            "state": self.state,
            "domain_id": self.domain_id,
            "operation_ref": self.operation_ref,
            "workflow_ref": self.workflow_ref,
            "session_ref": self.session_ref,
            "reason_ref": self.reason_ref,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainReviewItemView:
        try:
            return cls(
                review_ref=data["review_ref"],
                category=data["category"],
                state=data["state"],
                domain_id=data.get("domain_id"),
                operation_ref=data.get("operation_ref"),
                workflow_ref=data.get("workflow_ref"),
                session_ref=data.get("session_ref"),
                reason_ref=data.get("reason_ref"),
            )
        except KeyError as exc:
            raise DomainInterfaceSerializationError(
                f"Missing required field in review item view: {exc}"
            ) from exc
        except DomainInterfaceContractError as exc:
            raise DomainInterfaceSerializationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class DomainReviewCenterView:
    """Aggregate read projection over canonical review-required references."""

    items: tuple[DomainReviewItemView, ...]

    def __post_init__(self) -> None:
        if isinstance(self.items, str) or not isinstance(self.items, Sequence):
            raise DomainInterfaceContractError(
                "items must be a sequence of DomainReviewItemView entries"
            )
        entries = list(self.items)
        for entry in entries:
            if type(entry) is not DomainReviewItemView:
                raise DomainInterfaceContractError(
                    "items must contain only canonical DomainReviewItemView entries"
                )
        entries.sort(key=lambda entry: entry.review_ref)
        object.__setattr__(self, "items", tuple(entries))

    def to_dict(self) -> dict[str, Any]:
        return {"items": [item.to_dict() for item in self.items]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainReviewCenterView:
        try:
            return cls(
                items=tuple(
                    DomainReviewItemView.from_dict(item)
                    for item in data.get("items", ())
                )
            )
        except DomainInterfaceContractError as exc:
            raise DomainInterfaceSerializationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class DomainInterfaceProjectionRequest:
    """Explicit, typed request for one interface projection of canonical authority."""

    request_id: str
    resolution_reference_id: str
    composition_reference_id: str
    session_reference_id: str | None = None
    requested_views: tuple[DomainInterfaceViewKind, ...] = (
        DomainInterfaceViewKind.CONVERSATIONAL,
        DomainInterfaceViewKind.SELECTOR,
        DomainInterfaceViewKind.DOMAIN_CENTER,
        DomainInterfaceViewKind.CROSS_DOMAIN,
        DomainInterfaceViewKind.REVIEW_CENTER,
    )

    def __post_init__(self) -> None:
        request_id = _require_non_blank_str(self.request_id, "request_id")
        resolution_reference_id = _require_non_blank_str(
            self.resolution_reference_id, "resolution_reference_id"
        )
        composition_reference_id = _require_non_blank_str(
            self.composition_reference_id, "composition_reference_id"
        )
        session_reference_id = self.session_reference_id
        if session_reference_id is not None:
            session_reference_id = _require_non_blank_str(
                session_reference_id, "session_reference_id"
            )
        if isinstance(self.requested_views, str) or not isinstance(
            self.requested_views, Sequence
        ):
            raise DomainInterfaceContractError(
                "requested_views must be a sequence of DomainInterfaceViewKind"
            )
        requested_views: list[DomainInterfaceViewKind] = []
        seen: set[DomainInterfaceViewKind] = set()
        for value in self.requested_views:
            kind = _coerce_enum(value, DomainInterfaceViewKind, "requested_views")
            assert isinstance(kind, DomainInterfaceViewKind)
            if kind not in seen:
                seen.add(kind)
                requested_views.append(kind)
        if not requested_views:
            raise DomainInterfaceContractError("requested_views must not be empty")
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "resolution_reference_id", resolution_reference_id)
        object.__setattr__(self, "composition_reference_id", composition_reference_id)
        object.__setattr__(self, "session_reference_id", session_reference_id)
        object.__setattr__(self, "requested_views", tuple(requested_views))

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "resolution_reference_id": self.resolution_reference_id,
            "composition_reference_id": self.composition_reference_id,
            "session_reference_id": self.session_reference_id,
            "requested_views": [kind.value for kind in self.requested_views],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainInterfaceProjectionRequest:
        try:
            return cls(
                request_id=data["request_id"],
                resolution_reference_id=data["resolution_reference_id"],
                composition_reference_id=data["composition_reference_id"],
                session_reference_id=data.get("session_reference_id"),
                requested_views=tuple(data.get("requested_views", ())),
            )
        except KeyError as exc:
            raise DomainInterfaceSerializationError(
                f"Missing required field in projection request: {exc}"
            ) from exc
        except (DomainInterfaceContractError, ValueError) as exc:
            raise DomainInterfaceSerializationError(str(exc)) from exc


def _optional_required_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_blank_str(value, field_name)


@dataclass(frozen=True, slots=True)
class DomainInterfaceProjection:
    """Immutable, content-bound interface projection of canonical Domain authority."""

    projection_id: str
    request_id: str
    resolution_reference_id: str
    composition_reference_id: str
    session_reference_id: str | None
    conversational: ConversationalDomainView | None
    selector: DomainSelectorView | None
    domain_center: DomainCenterView | None
    cross_domain: CrossDomainInterfaceView | None
    review_center: DomainReviewCenterView | None
    content_digest: str = ""

    def __post_init__(self) -> None:
        projection_id = _require_non_blank_str(self.projection_id, "projection_id")
        request_id = _require_non_blank_str(self.request_id, "request_id")
        resolution_reference_id = _require_non_blank_str(
            self.resolution_reference_id, "resolution_reference_id"
        )
        composition_reference_id = _require_non_blank_str(
            self.composition_reference_id, "composition_reference_id"
        )
        session_reference_id = self.session_reference_id
        if session_reference_id is not None:
            session_reference_id = _require_non_blank_str(
                session_reference_id, "session_reference_id"
            )
        expected_digest = self._content_digest()
        if self.content_digest and self.content_digest != expected_digest:
            raise DomainInterfaceContractError(
                "content_digest does not match projection content"
            )
        content_digest = (
            _require_hex64(self.content_digest, "content_digest")
            if self.content_digest
            else expected_digest
        )
        object.__setattr__(self, "projection_id", projection_id)
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "resolution_reference_id", resolution_reference_id)
        object.__setattr__(self, "composition_reference_id", composition_reference_id)
        object.__setattr__(self, "session_reference_id", session_reference_id)
        object.__setattr__(self, "content_digest", content_digest)

    def _content_digest(self) -> str:
        payload = {
            "resolution_reference_id": self.resolution_reference_id,
            "composition_reference_id": self.composition_reference_id,
            "session_reference_id": self.session_reference_id,
            "conversational": self.conversational.to_dict()
            if self.conversational is not None
            else None,
            "selector": self.selector.to_dict() if self.selector is not None else None,
            "domain_center": self.domain_center.to_dict()
            if self.domain_center is not None
            else None,
            "cross_domain": self.cross_domain.to_dict()
            if self.cross_domain is not None
            else None,
            "review_center": self.review_center.to_dict()
            if self.review_center is not None
            else None,
        }
        return _sha256_digest(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection_id": self.projection_id,
            "request_id": self.request_id,
            "resolution_reference_id": self.resolution_reference_id,
            "composition_reference_id": self.composition_reference_id,
            "session_reference_id": self.session_reference_id,
            "conversational": self.conversational.to_dict()
            if self.conversational is not None
            else None,
            "selector": self.selector.to_dict() if self.selector is not None else None,
            "domain_center": self.domain_center.to_dict()
            if self.domain_center is not None
            else None,
            "cross_domain": self.cross_domain.to_dict()
            if self.cross_domain is not None
            else None,
            "review_center": self.review_center.to_dict()
            if self.review_center is not None
            else None,
            "content_digest": self.content_digest,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainInterfaceProjection:
        try:
            conversational = data.get("conversational")
            selector = data.get("selector")
            domain_center = data.get("domain_center")
            cross_domain = data.get("cross_domain")
            review_center = data.get("review_center")
            return cls(
                projection_id=data["projection_id"],
                request_id=data["request_id"],
                resolution_reference_id=data["resolution_reference_id"],
                composition_reference_id=data["composition_reference_id"],
                session_reference_id=data.get("session_reference_id"),
                conversational=ConversationalDomainView.from_dict(conversational)
                if conversational is not None
                else None,
                selector=DomainSelectorView.from_dict(selector)
                if selector is not None
                else None,
                domain_center=DomainCenterView.from_dict(domain_center)
                if domain_center is not None
                else None,
                cross_domain=CrossDomainInterfaceView.from_dict(cross_domain)
                if cross_domain is not None
                else None,
                review_center=DomainReviewCenterView.from_dict(review_center)
                if review_center is not None
                else None,
                content_digest=data.get("content_digest", ""),
            )
        except KeyError as exc:
            raise DomainInterfaceSerializationError(
                f"Missing required field in projection: {exc}"
            ) from exc
        except DomainInterfaceContractError as exc:
            raise DomainInterfaceSerializationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class DomainInterfaceIntent:
    """Typed interface-originated Domain Selector intent bound to canonical authority."""

    intent_id: str
    kind: DomainInterfaceIntentKind
    resolution_reference_id: str
    composition_reference_id: str
    target_domain: str | None = None
    session_reference_id: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        intent_id = _require_non_blank_str(self.intent_id, "intent_id")
        kind = _coerce_enum(self.kind, DomainInterfaceIntentKind, "kind")
        resolution_reference_id = _require_non_blank_str(
            self.resolution_reference_id, "resolution_reference_id"
        )
        composition_reference_id = _require_non_blank_str(
            self.composition_reference_id, "composition_reference_id"
        )
        target_domain = _optional_required_str(self.target_domain, "target_domain")
        session_reference_id = _optional_required_str(
            self.session_reference_id, "session_reference_id"
        )
        reason = _optional_required_str(self.reason, "reason")
        if (
            kind
            in (
                DomainInterfaceIntentKind.SELECT_PRIMARY,
                DomainInterfaceIntentKind.ADD_SUPPORTING,
                DomainInterfaceIntentKind.WITHDRAW_SUPPORTING,
            )
            and target_domain is None
        ):
            raise DomainInterfaceContractError(
                f"{kind.value} intent requires a target_domain"
            )
        object.__setattr__(self, "intent_id", intent_id)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "resolution_reference_id", resolution_reference_id)
        object.__setattr__(self, "composition_reference_id", composition_reference_id)
        object.__setattr__(self, "target_domain", target_domain)
        object.__setattr__(self, "session_reference_id", session_reference_id)
        object.__setattr__(self, "reason", reason)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "kind": self.kind.value,
            "resolution_reference_id": self.resolution_reference_id,
            "composition_reference_id": self.composition_reference_id,
            "target_domain": self.target_domain,
            "session_reference_id": self.session_reference_id,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainInterfaceIntent:
        try:
            return cls(
                intent_id=data["intent_id"],
                kind=DomainInterfaceIntentKind(data["kind"]),
                resolution_reference_id=data["resolution_reference_id"],
                composition_reference_id=data["composition_reference_id"],
                target_domain=data.get("target_domain"),
                session_reference_id=data.get("session_reference_id"),
                reason=data.get("reason"),
            )
        except KeyError as exc:
            raise DomainInterfaceSerializationError(
                f"Missing required field in intent: {exc}"
            ) from exc
        except (DomainInterfaceContractError, ValueError) as exc:
            raise DomainInterfaceSerializationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class DomainInterfaceIntentResult:
    """Reference-bound outcome of one delegated Domain Selector intent."""

    intent_id: str
    accepted: bool
    status: DomainInterfaceStatus
    resolution_reference_id: str
    composition_reference_id: str
    reason_code: str

    def __post_init__(self) -> None:
        intent_id = _require_non_blank_str(self.intent_id, "intent_id")
        resolution_reference_id = _require_non_blank_str(
            self.resolution_reference_id, "resolution_reference_id"
        )
        composition_reference_id = _require_non_blank_str(
            self.composition_reference_id, "composition_reference_id"
        )
        reason_code = _require_non_blank_str(self.reason_code, "reason_code")
        status = _coerce_enum(self.status, DomainInterfaceStatus, "status")
        object.__setattr__(self, "intent_id", intent_id)
        object.__setattr__(self, "accepted", bool(self.accepted))
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "resolution_reference_id", resolution_reference_id)
        object.__setattr__(self, "composition_reference_id", composition_reference_id)
        object.__setattr__(self, "reason_code", reason_code)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "accepted": self.accepted,
            "status": self.status.value,
            "resolution_reference_id": self.resolution_reference_id,
            "composition_reference_id": self.composition_reference_id,
            "reason_code": self.reason_code,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainInterfaceIntentResult:
        try:
            return cls(
                intent_id=data["intent_id"],
                accepted=bool(data["accepted"]),
                status=DomainInterfaceStatus(data["status"]),
                resolution_reference_id=data["resolution_reference_id"],
                composition_reference_id=data["composition_reference_id"],
                reason_code=data["reason_code"],
            )
        except KeyError as exc:
            raise DomainInterfaceSerializationError(
                f"Missing required field in intent result: {exc}"
            ) from exc
        except (DomainInterfaceContractError, ValueError) as exc:
            raise DomainInterfaceSerializationError(str(exc)) from exc
