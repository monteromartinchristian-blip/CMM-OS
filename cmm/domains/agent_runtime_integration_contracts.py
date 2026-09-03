"""Strict immutable contracts at the Domain Intelligence/Agent Runtime boundary.

Phase 10.41 value objects only.  No services, stores, registries, loaders,
executors, planners, or state machines live in this module.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.agent_runtime_integration_contracts import (
    IntegratedAgentExecutionRequest,
    IntegratedAgentExecutionResult,
)
from cmm.domains.cognitive_integration_contracts import (
    DomainCognitiveIntegrationResult,
    DomainCognitiveResourceInput,
)
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.contracts import _deep_freeze, _deep_unfreeze
from cmm.domains.errors import (
    DomainAgentRuntimeIntegrationContractError,
    DomainContractValidationError,
)
from cmm.domains.profile_contracts import ResolvedDomainProfile
from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resolver_contracts import DomainResolutionResult

# Secret-bearing metadata key semantics aligned with the canonical Phase 9
# request contracts (normalized matching on exact keys, prefixes, suffixes).
_SECRET_KEYS = frozenset(
    {
        "password",
        "passwords",
        "passwd",
        "secret",
        "secrets",
        "token",
        "tokens",
        "api_key",
        "api_keys",
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "private_key",
        "access_key",
        "refresh_token",
        "bearer",
    }
)
_SECRET_KEY_PREFIXES = (
    "secret_",
    "password_",
    "passwd_",
    "api_key_",
    "apikey_",
    "private_key_",
    "access_key_",
    "refresh_token_",
    "authorization_",
    "bearer_",
)
_SECRET_KEY_SUFFIXES = (
    "_secret",
    "_password",
    "_passwd",
    "_token",
    "_api_key",
    "_apikey",
    "_credential",
    "_credentials",
    "_private_key",
    "_access_key",
)
_HIDDEN_REASONING_KEYS = frozenset(
    {
        "chain_of_thought",
        "reasoning_text",
        "internal_reasoning",
        "scratchpad",
        "hidden_trace",
    }
)


def _is_secret_key(key: str) -> bool:
    camel_separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", camel_separated).strip("_").casefold()
    return (
        normalized in _SECRET_KEYS
        or normalized.startswith(_SECRET_KEY_PREFIXES)
        or normalized.endswith(_SECRET_KEY_SUFFIXES)
    )


def _is_hidden_reasoning_key(key: str) -> bool:
    camel_separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", camel_separated).strip("_").casefold()
    return normalized in _HIDDEN_REASONING_KEYS


def _non_blank(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainAgentRuntimeIntegrationContractError(
            f"{field_name} must be a non-blank string", field=field_name
        )
    return value.strip()


def _optional_non_blank(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _non_blank(value, field_name)


def _unique_non_blank_strings(value: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise DomainAgentRuntimeIntegrationContractError(
            f"{field_name} must be a sequence of strings", field=field_name
        )
    values = tuple(_non_blank(item, field_name) for item in value)
    if len(set(values)) != len(values):
        raise DomainAgentRuntimeIntegrationContractError(
            f"{field_name} must not contain duplicates", field=field_name
        )
    return values


def _tuple_of_instances(
    value: Any, expected_type: type, field_name: str
) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise DomainAgentRuntimeIntegrationContractError(
            f"{field_name} must be a sequence", field=field_name
        )
    values = tuple(value)
    for index, item in enumerate(values):
        if type(item) is not expected_type:
            raise DomainAgentRuntimeIntegrationContractError(
                f"{field_name}[{index}] must be a {expected_type.__name__}",
                field=field_name,
            )
    return values


def _freeze_metadata(
    value: Any,
    field_name: str,
    *,
    reject_hidden_reasoning: bool = False,
) -> MappingProxyType[str, Any]:
    if not isinstance(value, Mapping):
        raise DomainAgentRuntimeIntegrationContractError(
            f"{field_name} must be a mapping", field=field_name
        )
    for key in value:
        if not isinstance(key, str):
            raise DomainAgentRuntimeIntegrationContractError(
                f"{field_name} keys must be strings", field=field_name
            )
        if _is_secret_key(key):
            raise DomainAgentRuntimeIntegrationContractError(
                f"{field_name} contains secret-like key {key!r}", field=field_name
            )
        if reject_hidden_reasoning and _is_hidden_reasoning_key(key):
            raise DomainAgentRuntimeIntegrationContractError(
                f"{field_name} contains hidden-reasoning key {key!r}",
                field=field_name,
            )
    try:
        return _deep_freeze(value)
    except DomainContractValidationError as exc:
        raise DomainAgentRuntimeIntegrationContractError(
            exc.message, field="metadata", details=dict(exc.details)
        ) from exc


def _exact_type(value: Any, expected_type: type, field_name: str) -> None:
    if type(value) is not expected_type:
        raise DomainAgentRuntimeIntegrationContractError(
            f"{field_name} must be a {expected_type.__name__}", field=field_name
        )


def _exact_bool(value: Any, field_name: str) -> None:
    if not isinstance(value, bool):
        raise DomainAgentRuntimeIntegrationContractError(
            f"{field_name} must be a bool", field=field_name
        )


class DomainAgentRuntimeDecisionCode(str, Enum):
    """Structured, safe decision codes for Domain-side runtime integration."""

    DOMAIN_RESOLVED = "DOMAIN_RESOLVED"
    DOMAIN_REEVALUATED = "DOMAIN_REEVALUATED"
    PRIMARY_DOMAIN_CHANGED = "PRIMARY_DOMAIN_CHANGED"
    SUPPORTING_DOMAIN_ADDED = "SUPPORTING_DOMAIN_ADDED"
    DOMAIN_COMPOSED = "DOMAIN_COMPOSED"
    PROFILE_RESOLVED = "PROFILE_RESOLVED"
    DOMAIN_PERMISSION_RESTRICTED = "DOMAIN_PERMISSION_RESTRICTED"
    DOMAIN_APPROVAL_REQUIRED = "DOMAIN_APPROVAL_REQUIRED"
    DOMAIN_AUTONOMY_RESTRICTED = "DOMAIN_AUTONOMY_RESTRICTED"
    DOMAIN_BUDGET_RESTRICTED = "DOMAIN_BUDGET_RESTRICTED"
    DOMAIN_OPERATION_SELECTED = "DOMAIN_OPERATION_SELECTED"
    DOMAIN_WORKFLOW_BOUND = "DOMAIN_WORKFLOW_BOUND"
    DOMAIN_COGNITIVE_BOUND = "DOMAIN_COGNITIVE_BOUND"
    DOMAIN_RUNTIME_BLOCKED = "DOMAIN_RUNTIME_BLOCKED"
    DOMAIN_RUNTIME_COMPLETED = "DOMAIN_RUNTIME_COMPLETED"


@dataclass(frozen=True, slots=True)
class DomainActionBudget:
    """Immutable Domain-side budget ceiling; never a mutable budget owner.

    Consumed/reserved state remains exclusively inside the canonical Phase 9
    ``ActionBudget`` / ``ActionBudgetService``.
    """

    domain_id: str
    maximum_operations: int | None = None
    maximum_iterations: int | None = None
    maximum_questions: int | None = None
    maximum_external_calls: int | None = None
    maximum_duration_seconds: int | None = None
    maximum_cost: Decimal | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "domain_id", _non_blank(self.domain_id, "domain_id"))
        for field_name in (
            "maximum_operations",
            "maximum_iterations",
            "maximum_questions",
            "maximum_external_calls",
            "maximum_duration_seconds",
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                raise DomainAgentRuntimeIntegrationContractError(
                    f"{field_name} must be an integer or None", field=field_name
                )
            if value < 0:
                raise DomainAgentRuntimeIntegrationContractError(
                    f"{field_name} must be non-negative", field=field_name
                )
        cost = self.maximum_cost
        if cost is not None:
            if isinstance(cost, bool) or not isinstance(cost, Decimal):
                raise DomainAgentRuntimeIntegrationContractError(
                    "maximum_cost must be a Decimal or None", field="maximum_cost"
                )
            if not cost.is_finite():
                raise DomainAgentRuntimeIntegrationContractError(
                    "maximum_cost must be finite", field="maximum_cost"
                )
            if cost < 0:
                raise DomainAgentRuntimeIntegrationContractError(
                    "maximum_cost must be non-negative", field="maximum_cost"
                )
        object.__setattr__(
            self, "metadata", _freeze_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "maximum_operations": self.maximum_operations,
            "maximum_iterations": self.maximum_iterations,
            "maximum_questions": self.maximum_questions,
            "maximum_external_calls": self.maximum_external_calls,
            "maximum_duration_seconds": self.maximum_duration_seconds,
            "maximum_cost": (
                str(self.maximum_cost) if self.maximum_cost is not None else None
            ),
            "metadata": _deep_unfreeze(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class DomainAgentRuntimeDecision:
    """Immutable structured record of one Domain integration decision."""

    code: DomainAgentRuntimeDecisionCode
    subject_id: str
    reason_codes: tuple[str, ...] = ()
    related_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.code, DomainAgentRuntimeDecisionCode):
            raise DomainAgentRuntimeIntegrationContractError(
                "code must be a DomainAgentRuntimeDecisionCode", field="code"
            )
        object.__setattr__(
            self, "subject_id", _non_blank(self.subject_id, "subject_id")
        )
        object.__setattr__(
            self,
            "reason_codes",
            _unique_non_blank_strings(self.reason_codes, "reason_codes"),
        )
        object.__setattr__(
            self,
            "related_ids",
            _unique_non_blank_strings(self.related_ids, "related_ids"),
        )
        object.__setattr__(
            self,
            "metadata",
            _freeze_metadata(self.metadata, "metadata", reject_hidden_reasoning=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "subject_id": self.subject_id,
            "reason_codes": list(self.reason_codes),
            "related_ids": list(self.related_ids),
            "metadata": _deep_unfreeze(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class DomainAgentRuntimeIntegrationRequest:
    """Immutable wrapper binding canonical Domain and Phase 9 requests.

    The wrapper binds canonical objects rather than cloning their contents.
    """

    request_id: str
    resolution_context: DomainResolutionContext
    agent_request: IntegratedAgentExecutionRequest
    cognitive_resources: tuple[DomainCognitiveResourceInput, ...] = ()
    domain_budget: DomainActionBudget | None = None
    force_domain_reevaluation: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _non_blank(self.request_id, "request_id")
        )
        _exact_type(
            self.resolution_context, DomainResolutionContext, "resolution_context"
        )
        _exact_type(
            self.agent_request,
            IntegratedAgentExecutionRequest,
            "agent_request",
        )
        resources = _tuple_of_instances(
            self.cognitive_resources,
            DomainCognitiveResourceInput,
            "cognitive_resources",
        )
        binding_ids = [resource.binding.id for resource in resources]
        if len(set(binding_ids)) != len(binding_ids):
            raise DomainAgentRuntimeIntegrationContractError(
                "cognitive_resources must not duplicate binding IDs",
                field="cognitive_resources",
            )
        object.__setattr__(self, "cognitive_resources", resources)
        if self.domain_budget is not None:
            _exact_type(self.domain_budget, DomainActionBudget, "domain_budget")
        _exact_bool(self.force_domain_reevaluation, "force_domain_reevaluation")
        context = self.resolution_context
        if (
            context.goal_id is not None
            and context.goal_id != self.agent_request.goal_id
        ):
            raise DomainAgentRuntimeIntegrationContractError(
                "resolution_context.goal_id must match agent_request.goal_id",
                field="resolution_context.goal_id",
            )
        if (
            context.actor not in ("", "system")
            and context.actor != self.agent_request.actor_id
        ):
            raise DomainAgentRuntimeIntegrationContractError(
                "resolution_context.actor must match agent_request.actor_id",
                field="resolution_context.actor",
            )
        object.__setattr__(
            self, "metadata", _freeze_metadata(self.metadata, "metadata")
        )


@dataclass(frozen=True, slots=True)
class DomainAgentRuntimeIntegrationResult:
    """Immutable integration aggregate binding canonical results by reference.

    It is not a replacement for ``DomainResolutionResult`` or
    ``IntegratedAgentExecutionResult``; canonical objects are preserved
    rather than translated into private duplicates.
    """

    request_id: str
    resolution: DomainResolutionResult
    composition: DomainComposition
    profile: ResolvedDomainProfile
    cognitive_result: DomainCognitiveIntegrationResult | None
    agent_result: IntegratedAgentExecutionResult | None
    decisions: tuple[DomainAgentRuntimeDecision, ...]
    domain_trace_id: str | None
    agent_trace_id: str | None
    memory_binding_ids: tuple[str, ...] = ()
    blocked: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _non_blank(self.request_id, "request_id")
        )
        _exact_type(self.resolution, DomainResolutionResult, "resolution")
        _exact_type(self.composition, DomainComposition, "composition")
        _exact_type(self.profile, ResolvedDomainProfile, "profile")
        if self.composition.resolution_id != self.resolution.id:
            raise DomainAgentRuntimeIntegrationContractError(
                "composition.resolution_id must match resolution.id",
                field="composition",
            )
        if (
            self.profile.primary_domain != self.composition.primary_domain
            or self.profile.supporting_domains != self.composition.supporting_domains
        ):
            raise DomainAgentRuntimeIntegrationContractError(
                "profile active domains must match composition", field="profile"
            )
        if self.cognitive_result is not None:
            _exact_type(
                self.cognitive_result,
                DomainCognitiveIntegrationResult,
                "cognitive_result",
            )
        if self.agent_result is not None:
            _exact_type(
                self.agent_result,
                IntegratedAgentExecutionResult,
                "agent_result",
            )
        _exact_bool(self.blocked, "blocked")
        if not self.blocked and self.agent_result is None:
            raise DomainAgentRuntimeIntegrationContractError(
                "agent_result is required when the result is not blocked",
                field="agent_result",
            )
        decisions = _tuple_of_instances(
            self.decisions, DomainAgentRuntimeDecision, "decisions"
        )
        decision_keys = [
            (
                decision.code.value,
                decision.subject_id,
                decision.reason_codes,
                decision.related_ids,
            )
            for decision in decisions
        ]
        if len(set(decision_keys)) != len(decision_keys):
            raise DomainAgentRuntimeIntegrationContractError(
                "decisions must not contain duplicates", field="decisions"
            )
        object.__setattr__(self, "decisions", decisions)
        object.__setattr__(
            self,
            "domain_trace_id",
            _optional_non_blank(self.domain_trace_id, "domain_trace_id"),
        )
        object.__setattr__(
            self,
            "agent_trace_id",
            _optional_non_blank(self.agent_trace_id, "agent_trace_id"),
        )
        object.__setattr__(
            self,
            "memory_binding_ids",
            _unique_non_blank_strings(self.memory_binding_ids, "memory_binding_ids"),
        )
        object.__setattr__(
            self, "metadata", _freeze_metadata(self.metadata, "metadata")
        )


__all__ = [
    "DomainActionBudget",
    "DomainAgentRuntimeDecision",
    "DomainAgentRuntimeDecisionCode",
    "DomainAgentRuntimeIntegrationRequest",
    "DomainAgentRuntimeIntegrationResult",
]
