"""Phase 11.2 — orchestration boundary contracts.

This module defines the immutable Phase 11.2 orchestration values.  It
deliberately does not redefine any canonical subsystem contract: roadmap
contract names that already have a canonical production owner (domains,
agents, workflows, operations, sessions, validation, approval, error results)
stay owned by that subsystem and are referenced, never cloned.

Every public value here is frozen, validated at construction, defensive against
caller mutation, recursively frozen for mappings and sequences, deterministically
serializable through ``to_dict()``, and refuses opaque runtime objects.

No public orchestration value carries model reasoning.  The roadmap's
conceptual ``reasoning_trace`` field is represented only by safe
``trace_refs``/``reason_codes`` references, and the roadmap's conceptual
``memory_updates`` payload is not implemented because Phase 11.2 has no memory
authority.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.platform.contracts import ErrorResult

__all__ = [
    "AgentRouteDecision",
    "DomainRouteDecision",
    "ExecutionRoute",
    "IntentKind",
    "IntentResolution",
    "OrchestrationChannel",
    "OrchestrationDecisionRecord",
    "OrchestrationPolicyDecision",
    "OrchestrationRequest",
    "OrchestrationResult",
    "OrchestrationStatus",
    "PolicyDisposition",
    "ResolvedContext",
]


# ── Safe immutable value helpers ─────────────────────────────────────────────
#
# These helpers are orchestration-local on purpose: Phase 11.1 keeps its
# equivalent helpers private, and importing private platform helpers would
# couple this package to an implementation detail instead of a contract.


def _non_empty(value: object, field_name: str) -> str:
    """Return the normalized string or fail closed on blank input."""

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _optional_reference(value: object, field_name: str) -> str | None:
    """Normalize an optional opaque reference.

    An absent or blank reference is normalized to ``None``; the canonical
    repository convention is that an empty optional reference means "not
    supplied" and must never be stored as an empty identifier.
    """

    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None")
    normalized = value.strip()
    return normalized or None


def _freeze_value(value: object, field_name: str) -> Any:
    """Return a recursively immutable, JSON-safe representation of *value*.

    Only descriptive values are accepted: ``None``, ``bool``, ``int``,
    ``float``, ``str``, mappings of those values and sequences of them.
    Binary data and every other object are rejected, so a live client,
    repository, provider object or credential can never enter a public
    orchestration contract.
    """

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} must not contain a non-finite float")
        return value
    if isinstance(value, bytes | bytearray):
        raise TypeError(f"{field_name} must not carry binary data")
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{field_name} keys must be strings")
            frozen[key] = _freeze_value(item, field_name)
        return MappingProxyType(frozen)
    if isinstance(value, Sequence):
        return tuple(_freeze_value(item, field_name) for item in value)

    raise TypeError(
        f"{field_name} must be a descriptive immutable value, "
        f"not {type(value).__name__}"
    )


def _freeze_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    """Freeze a mapping field, rejecting anything that is not a mapping."""

    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    frozen = _freeze_value(value, field_name)
    assert isinstance(frozen, Mapping)
    return frozen


def _freeze_reference_tuple(value: object, field_name: str) -> tuple[str, ...]:
    """Freeze a sequence of non-empty references, deduplicating in order."""

    if value is None:
        return ()
    if isinstance(value, (str, bytes | bytearray)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of strings")

    seen: set[str] = set()
    normalized: list[str] = []
    for item in value:
        reference = _non_empty(item, field_name)
        if reference in seen:
            continue
        seen.add(reference)
        normalized.append(reference)
    return tuple(normalized)


def _enum_value(value: object, enum_type: type[Enum], field_name: str) -> Any:
    """Require a real enum member; never silently coerce a raw string."""

    if not isinstance(value, enum_type):
        raise TypeError(f"{field_name} must be a {enum_type.__name__}")
    return value


def _enum_value_opt(
    value: object, enum_type: type[Enum], field_name: str
) -> Any | None:
    if value is None:
        return None
    return _enum_value(value, enum_type, field_name)


def _aware(value: object, field_name: str) -> datetime:
    """Require a timezone-aware datetime."""

    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _not_naive(value: object, field_name: str) -> datetime:
    return _aware(value, field_name)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ────────────────────────────────────────────────────────────────────


class IntentKind(str, Enum):
    """Deterministic request classification owned by Phase 11.2."""

    QUESTION = "question"
    REFLECTION = "reflection"
    COMMAND = "command"
    GOAL = "goal"
    WORKFLOW_REQUEST = "workflow_request"
    INFORMATION_UPDATE = "information_update"
    APPROVAL_RESPONSE = "approval_response"
    CONTINUATION = "continuation"
    CANCELLATION = "cancellation"
    CONFIGURATION_CHANGE = "configuration_change"
    UNKNOWN = "unknown"


class OrchestrationChannel(str, Enum):
    """Origin channel of an orchestration request.

    ``API`` is an origin identifier only.  Phase 11.2 implements no API.
    """

    CONVERSATION = "conversation"
    CLI = "cli"
    INTERNAL = "internal"
    API = "api"


class ExecutionRoute(str, Enum):
    """The bounded execution path selected for a request."""

    DIRECT_RESPONSE = "direct_response"
    OPERATION = "operation"
    WORKFLOW = "workflow"
    AUTONOMOUS_AGENT = "autonomous_agent"
    HUMAN_ESCALATION = "human_escalation"
    NONE = "none"


class OrchestrationStatus(str, Enum):
    """Terminal status of one orchestration attempt.

    ``COMPLETED`` is deliberately absent: Phase 11.2 decides and delegates and
    never executes the downstream vertical.
    """

    ROUTED = "routed"
    NEEDS_CLARIFICATION = "needs_clarification"
    BLOCKED = "blocked"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PolicyDisposition(str, Enum):
    """Restrictive disposition of the orchestration policy.

    A disposition may only preserve or narrow canonical authority.
    """

    ALLOW_ROUTE = "allow_route"
    REQUIRE_APPROVAL = "require_approval"
    ESCALATE = "escalate"
    DENY = "deny"


# ── Intent resolution ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IntentResolution:
    """Categorical outcome of deterministic intent resolution."""

    intent: IntentKind = IntentKind.UNKNOWN
    needs_clarification: bool = True
    source_kind: str = "intent_hint"
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "intent", _enum_value(self.intent, IntentKind, "intent")
        )
        object.__setattr__(
            self, "source_kind", _non_empty(self.source_kind, "source_kind")
        )
        if not isinstance(self.needs_clarification, bool):
            raise TypeError("needs_clarification must be a bool")
        object.__setattr__(
            self,
            "reason_codes",
            _freeze_reference_tuple(self.reason_codes, "reason_codes"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.value,
            "needs_clarification": self.needs_clarification,
            "source_kind": self.source_kind,
            "reason_codes": list(self.reason_codes),
        }


# ── Context ──────────────────────────────────────────────────────────────────

_CONTEXT_STAGES = ("base", "domain")


@dataclass(frozen=True, slots=True)
class ResolvedContext:
    """Minimum authorized context projection for one orchestration stage.

    Only safe references and categorical facts are carried.  Source objects are
    never copied into this value, and unauthorized or unrelated caller context
    is withheld rather than forwarded.
    """

    request_id: str
    stage: str
    session_ref: str | None = None
    session_status: str | None = None
    session_revision: int | None = None
    context_refs: tuple[str, ...] = ()
    domain_refs: tuple[str, ...] = ()
    permission_refs: tuple[str, ...] = ()
    missing_refs: tuple[str, ...] = ()
    withheld_field_count: int = 0
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _non_empty(self.request_id, "request_id")
        )
        stage = _non_empty(self.stage, "stage")
        if stage not in _CONTEXT_STAGES:
            raise ValueError(f"stage must be one of {_CONTEXT_STAGES}")
        object.__setattr__(self, "stage", stage)
        object.__setattr__(
            self,
            "session_ref",
            _optional_reference(self.session_ref, "session_ref"),
        )
        object.__setattr__(
            self,
            "session_status",
            _optional_reference(self.session_status, "session_status"),
        )
        if self.session_revision is not None and (
            isinstance(self.session_revision, bool)
            or not isinstance(self.session_revision, int)
            or self.session_revision < 0
        ):
            raise ValueError("session_revision must be a non-negative int or None")
        for name in (
            "context_refs",
            "domain_refs",
            "permission_refs",
            "missing_refs",
            "reason_codes",
        ):
            object.__setattr__(
                self, name, _freeze_reference_tuple(getattr(self, name), name)
            )
        if isinstance(self.withheld_field_count, bool) or not isinstance(
            self.withheld_field_count, int
        ):
            raise TypeError("withheld_field_count must be an int")
        if self.withheld_field_count < 0:
            raise ValueError("withheld_field_count must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "stage": self.stage,
            "session_ref": self.session_ref,
            "session_status": self.session_status,
            "session_revision": self.session_revision,
            "context_refs": list(self.context_refs),
            "domain_refs": list(self.domain_refs),
            "permission_refs": list(self.permission_refs),
            "missing_refs": list(self.missing_refs),
            "withheld_field_count": self.withheld_field_count,
            "reason_codes": list(self.reason_codes),
        }


# ── Domain route ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DomainRouteDecision:
    """Orchestration projection of canonical Domain Intelligence evidence.

    It references canonical outcomes; it never reimplements domain scoring,
    fallback, ambiguity detection or permission semantics.
    """

    status: str
    primary_domain: str | None = None
    supporting_domains: tuple[str, ...] = ()
    rejected_domains: tuple[str, ...] = ()
    ambiguous_domains: tuple[str, ...] = ()
    profile_id: str | None = None
    permission_disposition: str | None = None
    permission_refs: tuple[str, ...] = ()
    approval_refs: tuple[str, ...] = ()
    trace_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    needs_clarification: bool = False
    fallback_used: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _non_empty(self.status, "status"))
        object.__setattr__(
            self,
            "primary_domain",
            _optional_reference(self.primary_domain, "primary_domain"),
        )
        object.__setattr__(
            self,
            "profile_id",
            _optional_reference(self.profile_id, "profile_id"),
        )
        object.__setattr__(
            self,
            "permission_disposition",
            _optional_reference(self.permission_disposition, "permission_disposition"),
        )
        for name in (
            "supporting_domains",
            "rejected_domains",
            "ambiguous_domains",
            "permission_refs",
            "approval_refs",
            "trace_refs",
            "reason_codes",
        ):
            object.__setattr__(
                self, name, _freeze_reference_tuple(getattr(self, name), name)
            )
        for name in ("needs_clarification", "fallback_used"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        if self.primary_domain is not None and self.primary_domain in (
            self.supporting_domains
        ):
            raise ValueError("primary domain must not also be a supporting domain")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "primary_domain": self.primary_domain,
            "supporting_domains": list(self.supporting_domains),
            "rejected_domains": list(self.rejected_domains),
            "ambiguous_domains": list(self.ambiguous_domains),
            "profile_id": self.profile_id,
            "permission_disposition": self.permission_disposition,
            "permission_refs": list(self.permission_refs),
            "approval_refs": list(self.approval_refs),
            "trace_refs": list(self.trace_refs),
            "reason_codes": list(self.reason_codes),
            "needs_clarification": self.needs_clarification,
            "fallback_used": self.fallback_used,
        }


# ── Agent / execution-path route ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AgentRouteDecision:
    """The selected bounded execution path and its safe references."""

    route: ExecutionRoute = ExecutionRoute.NONE
    agent_id: str | None = None
    agent_version: str | None = None
    workflow_id: str | None = None
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        route = _enum_value(self.route, ExecutionRoute, "route")
        object.__setattr__(self, "route", route)
        object.__setattr__(
            self, "agent_id", _optional_reference(self.agent_id, "agent_id")
        )
        object.__setattr__(
            self,
            "agent_version",
            _optional_reference(self.agent_version, "agent_version"),
        )
        object.__setattr__(
            self, "workflow_id", _optional_reference(self.workflow_id, "workflow_id")
        )
        object.__setattr__(
            self,
            "reason_codes",
            _freeze_reference_tuple(self.reason_codes, "reason_codes"),
        )

        if route is ExecutionRoute.AUTONOMOUS_AGENT:
            if self.agent_id is None:
                raise ValueError("an autonomous route requires a canonical agent ID")
        elif self.agent_id is not None:
            raise ValueError(
                f"route {route.value} must not carry an agent ID",
            )
        if self.agent_version is not None and self.agent_id is None:
            raise ValueError("agent_version requires an agent_id")
        if (
            route not in (ExecutionRoute.WORKFLOW, ExecutionRoute.AUTONOMOUS_AGENT)
            and self.workflow_id is not None
        ):
            raise ValueError(f"route {route.value} must not carry a workflow ID")

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route.value,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "workflow_id": self.workflow_id,
            "reason_codes": list(self.reason_codes),
        }


# ── Policy ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class OrchestrationPolicyDecision:
    """Restrictive policy outcome over canonical evidence."""

    disposition: PolicyDisposition = PolicyDisposition.DENY
    approval_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        disposition = _enum_value(self.disposition, PolicyDisposition, "disposition")
        object.__setattr__(self, "disposition", disposition)
        object.__setattr__(
            self,
            "approval_refs",
            _freeze_reference_tuple(self.approval_refs, "approval_refs"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            _freeze_reference_tuple(self.reason_codes, "reason_codes"),
        )
        if disposition is not PolicyDisposition.REQUIRE_APPROVAL and self.approval_refs:
            raise ValueError(
                "approval references are only meaningful for REQUIRE_APPROVAL"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition.value,
            "approval_refs": list(self.approval_refs),
            "reason_codes": list(self.reason_codes),
        }


# ── Request ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class OrchestrationRequest:
    """Immutable, serializable request to the global Orchestration Layer.

    ``channel`` is declared immediately after the two required identities so
    that every remaining field can carry a safe default; the field names and
    semantics are exactly the frozen Phase 11.2 set.

    ``bot_id`` is an opaque reference only.  Phase 11.2 implements no Bot
    identity, Bot repository or Bot runtime authority.
    """

    request_id: str
    user_id: str
    channel: OrchestrationChannel = OrchestrationChannel.INTERNAL
    session_id: str | None = None
    bot_id: str | None = None
    input: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    context: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    requested_capabilities: tuple[str, ...] = ()
    intent_hint: IntentKind | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _non_empty(self.request_id, "request_id")
        )
        object.__setattr__(self, "user_id", _non_empty(self.user_id, "user_id"))
        object.__setattr__(
            self, "channel", _enum_value(self.channel, OrchestrationChannel, "channel")
        )
        object.__setattr__(
            self, "session_id", _optional_reference(self.session_id, "session_id")
        )
        object.__setattr__(self, "bot_id", _optional_reference(self.bot_id, "bot_id"))
        object.__setattr__(self, "input", _freeze_mapping(self.input, "input"))
        object.__setattr__(self, "context", _freeze_mapping(self.context, "context"))
        object.__setattr__(
            self,
            "requested_capabilities",
            _freeze_reference_tuple(
                self.requested_capabilities, "requested_capabilities"
            ),
        )
        object.__setattr__(
            self,
            "intent_hint",
            _enum_value_opt(self.intent_hint, IntentKind, "intent_hint"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "channel": self.channel.value,
            "session_id": self.session_id,
            "bot_id": self.bot_id,
            "input": _thaw(self.input),
            "context": _thaw(self.context),
            "requested_capabilities": list(self.requested_capabilities),
            "intent_hint": self.intent_hint.value if self.intent_hint else None,
        }


def _thaw(value: object) -> Any:
    """Return a JSON-native representation of a frozen orchestration value."""

    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


# ── Decision record ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class OrchestrationDecisionRecord:
    """Safe categorical record of one terminal orchestration decision.

    The record never stores raw request text, prompts, hidden reasoning,
    credentials, provider payloads or copied sensitive domain content.
    """

    decision_id: str
    request_id: str
    channel: OrchestrationChannel
    intent: IntentKind
    execution_route: ExecutionRoute
    policy_disposition: PolicyDisposition
    session_id: str | None = None
    primary_domain: str | None = None
    supporting_domains: tuple[str, ...] = ()
    selected_agent_id: str | None = None
    workflow_id: str | None = None
    approval_refs: tuple[str, ...] = ()
    trace_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    occurred_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "decision_id", _non_empty(self.decision_id, "decision_id")
        )
        object.__setattr__(
            self, "request_id", _non_empty(self.request_id, "request_id")
        )
        object.__setattr__(
            self, "channel", _enum_value(self.channel, OrchestrationChannel, "channel")
        )
        object.__setattr__(
            self, "intent", _enum_value(self.intent, IntentKind, "intent")
        )
        object.__setattr__(
            self,
            "execution_route",
            _enum_value(self.execution_route, ExecutionRoute, "execution_route"),
        )
        object.__setattr__(
            self,
            "policy_disposition",
            _enum_value(
                self.policy_disposition, PolicyDisposition, "policy_disposition"
            ),
        )
        for name in (
            "session_id",
            "primary_domain",
            "selected_agent_id",
            "workflow_id",
        ):
            object.__setattr__(
                self, name, _optional_reference(getattr(self, name), name)
            )
        for name in (
            "supporting_domains",
            "approval_refs",
            "trace_refs",
            "reason_codes",
        ):
            object.__setattr__(
                self, name, _freeze_reference_tuple(getattr(self, name), name)
            )
        object.__setattr__(
            self, "occurred_at", _not_naive(self.occurred_at, "occurred_at")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "channel": self.channel.value,
            "intent": self.intent.value,
            "primary_domain": self.primary_domain,
            "supporting_domains": list(self.supporting_domains),
            "execution_route": self.execution_route.value,
            "policy_disposition": self.policy_disposition.value,
            "selected_agent_id": self.selected_agent_id,
            "workflow_id": self.workflow_id,
            "approval_refs": list(self.approval_refs),
            "reason_codes": list(self.reason_codes),
            "trace_refs": list(self.trace_refs),
            "occurred_at": self.occurred_at.astimezone(timezone.utc).isoformat(),
        }

    def identity_payload(self) -> dict[str, Any]:
        """Return the deterministic decision facts used for duplicate checks."""

        payload = self.to_dict()
        payload.pop("occurred_at")
        return payload


# ── Result ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    """Immutable, serializable outcome of one orchestration attempt.

    The result describes the orchestration decision, never hidden model
    reasoning.  It carries identifiers and categorical facts produced by
    canonical owners; it never copies canonical internal state.
    """

    request_id: str
    status: OrchestrationStatus = OrchestrationStatus.FAILED
    intent: IntentKind = IntentKind.UNKNOWN
    primary_domain: str | None = None
    supporting_domains: tuple[str, ...] = ()
    profile_id: str | None = None
    route: ExecutionRoute = ExecutionRoute.NONE
    agent_id: str | None = None
    workflow_id: str | None = None
    approval_refs: tuple[str, ...] = ()
    decision_id: str | None = None
    trace_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    error: ErrorResult | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _non_empty(self.request_id, "request_id")
        )
        object.__setattr__(
            self, "status", _enum_value(self.status, OrchestrationStatus, "status")
        )
        object.__setattr__(
            self, "intent", _enum_value(self.intent, IntentKind, "intent")
        )
        object.__setattr__(
            self, "route", _enum_value(self.route, ExecutionRoute, "route")
        )
        for name in (
            "primary_domain",
            "profile_id",
            "agent_id",
            "workflow_id",
            "decision_id",
        ):
            object.__setattr__(
                self, name, _optional_reference(getattr(self, name), name)
            )
        for name in (
            "supporting_domains",
            "approval_refs",
            "trace_refs",
            "reason_codes",
        ):
            object.__setattr__(
                self, name, _freeze_reference_tuple(getattr(self, name), name)
            )
        if self.error is not None and not isinstance(self.error, ErrorResult):
            raise TypeError("error must be a cmm.platform.contracts.ErrorResult")

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "intent": self.intent.value,
            "primary_domain": self.primary_domain,
            "supporting_domains": list(self.supporting_domains),
            "profile_id": self.profile_id,
            "route": self.route.value,
            "agent_id": self.agent_id,
            "workflow_id": self.workflow_id,
            "approval_refs": list(self.approval_refs),
            "decision_id": self.decision_id,
            "trace_refs": list(self.trace_refs),
            "reason_codes": list(self.reason_codes),
            "error": None if self.error is None else _error_to_dict(self.error),
        }


def _error_to_dict(error: ErrorResult) -> dict[str, Any]:
    return {
        "code": error.code,
        "message": error.message,
        "category": error.category,
        "details": dict(error.details),
    }
