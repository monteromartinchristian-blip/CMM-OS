"""CMMChat Wave E0 — the canonical model execution contracts.

One canonical model execution is described by a request derived from the
Phase 11.2 ``OrchestrationDecisionRecord`` the canonical orchestrator persisted,
and its outcome is one normalized, secret-free result.

The contracts are deliberately small and closed:

* :class:`ModelExecutionParameters` carries only the generation parameters the
  canonical LLM contracts already understand (``temperature`` and
  ``max_tokens``); it invents no product parameter surface.
* :class:`ModelExecutionRequest` carries the canonical request identity, the
  canonical decision identity, the canonical ``ExecutionRoute`` the orchestrator
  selected, the conversational text to infer on and the canonical
  ``ModelRequirements``.  It is the seam's complete input: the seam resolves no
  session, no domain and no routing fact of its own.
* :class:`ModelExecutionResult` carries either the normalized assistant text
  with the resolved model metadata, or one normalized
  :class:`ModelExecutionFailure` whose message is an application-owned constant.
  No provider text, response body, credential, path or traceback can reach it.

Every contract is immutable by construction (``frozen``, ``slots``, tuples and
``MappingProxyType``), so a caller can neither mutate a value in place nor share
mutable state with the seam.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Literal

from cmm.orchestration.contracts import ExecutionRoute, OrchestrationDecisionRecord
from kernel.llm.model_catalog import ModelSpec
from kernel.llm.model_selection import ModelRequirements
from kernel.llm.provider_registry import ProviderSpec

__all__ = [
    "MAX_EXECUTION_TEMPERATURE",
    "MIN_EXECUTION_TEMPERATURE",
    "ModelExecutionErrorCode",
    "ModelExecutionFailure",
    "ModelExecutionParameters",
    "ModelExecutionRequest",
    "ModelExecutionResult",
    "ModelExecutionStatus",
    "NormalizedModel",
    "ResolvedChatModel",
]

#: The canonical temperature band the seam accepts.  It mirrors the range the
#: canonical OpenAI-compatible contracts document; a value outside it is a
#: configuration defect and fails closed at construction.
MIN_EXECUTION_TEMPERATURE = 0.0
MAX_EXECUTION_TEMPERATURE = 2.0


def _non_empty_text(value: object, *, label: str) -> str:
    """Return a non-empty stripped text value or fail closed."""

    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must be non-empty")
    return normalized


def _optional_reference(value: object, *, label: str) -> str | None:
    """Return a normalized optional identifier or fail closed."""

    if value is None:
        return None
    return _non_empty_text(value, label=label)


class ModelExecutionStatus(str, Enum):
    """Terminal status of one canonical model execution."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ModelExecutionErrorCode(str, Enum):
    """Normalized, safe failure codes of the model execution seam.

    The vocabulary is closed and categorical: it names *what* failed, never an
    upstream message, a status line or a response fragment.
    """

    #: The canonical orchestration route the decision selected is not a model
    #: inference route, so no model may be called.
    ROUTE_NOT_EXECUTABLE = "ROUTE_NOT_EXECUTABLE"
    #: No canonical model satisfied the canonical requirements.
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    #: The canonical provider authority refused to materialize the provider.
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    #: The provider was reached and the invocation itself failed.
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    #: The provider answered with something that is not a usable completion.
    PROVIDER_RESPONSE_INVALID = "PROVIDER_RESPONSE_INVALID"


@dataclass(frozen=True, slots=True)
class ModelExecutionParameters:
    """Safe normalized generation parameters of one model execution."""

    temperature: float = 0.0
    max_tokens: int | None = None

    def __post_init__(self) -> None:
        temperature = self.temperature
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
            raise TypeError("temperature must be a number")
        resolved = float(temperature)
        if (
            math.isnan(resolved)
            or math.isinf(resolved)
            or resolved < MIN_EXECUTION_TEMPERATURE
            or resolved > MAX_EXECUTION_TEMPERATURE
        ):
            raise ValueError(
                "temperature must be within "
                f"{MIN_EXECUTION_TEMPERATURE} and {MAX_EXECUTION_TEMPERATURE}"
            )
        object.__setattr__(self, "temperature", resolved)

        max_tokens = self.max_tokens
        if max_tokens is None:
            return
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int):
            raise TypeError("max_tokens must be an integer")
        if max_tokens <= 0:
            raise ValueError("max_tokens must be greater than zero")


@dataclass(frozen=True, slots=True)
class ModelExecutionRequest:
    """One canonical model execution request.

    ``route`` is the canonical ``ExecutionRoute`` the orchestrator selected; the
    seam never re-derives it.  ``requirements`` are the canonical
    ``ModelRequirements`` the canonical ``ModelRouter`` evaluates, and
    ``parameters`` are the only generation parameters the seam forwards.
    """

    request_id: str
    decision_id: str
    route: ExecutionRoute
    prompt: str
    requirements: ModelRequirements = field(default_factory=ModelRequirements)
    parameters: ModelExecutionParameters = field(
        default_factory=ModelExecutionParameters
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _non_empty_text(self.request_id, label="request_id")
        )
        object.__setattr__(
            self, "decision_id", _non_empty_text(self.decision_id, label="decision_id")
        )
        if not isinstance(self.route, ExecutionRoute):
            raise TypeError("route must be an ExecutionRoute")
        object.__setattr__(self, "prompt", _non_empty_text(self.prompt, label="prompt"))
        if not isinstance(self.requirements, ModelRequirements):
            raise TypeError("requirements must be ModelRequirements")
        if not isinstance(self.parameters, ModelExecutionParameters):
            raise TypeError("parameters must be ModelExecutionParameters")

    @classmethod
    def from_decision(
        cls,
        record: OrchestrationDecisionRecord,
        *,
        prompt: str,
        requirements: ModelRequirements | None = None,
        parameters: ModelExecutionParameters | None = None,
    ) -> ModelExecutionRequest:
        """Map one canonical decision record onto one execution request.

        The mapping is faithful and total: the identity, the decision identity
        and the selected route are copied from the canonical record, and the
        text, the requirements and the parameters are supplied explicitly.  A
        non-executable route is copied unchanged — refusing it is the executor's
        decision, not the mapping's.
        """

        if not isinstance(record, OrchestrationDecisionRecord):
            raise TypeError("record must be an OrchestrationDecisionRecord")
        return cls(
            request_id=record.request_id,
            decision_id=record.decision_id,
            route=record.execution_route,
            prompt=prompt,
            requirements=(
                requirements if requirements is not None else ModelRequirements()
            ),
            parameters=(
                parameters if parameters is not None else ModelExecutionParameters()
            ),
        )


@dataclass(frozen=True, slots=True)
class ModelExecutionFailure:
    """One normalized, safe model execution failure."""

    code: ModelExecutionErrorCode
    message: str
    retryable: bool = False
    details: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.code, ModelExecutionErrorCode):
            raise TypeError("code must be a ModelExecutionErrorCode")
        object.__setattr__(
            self, "message", _non_empty_text(self.message, label="message")
        )
        if not isinstance(self.retryable, bool):
            raise TypeError("retryable must be a bool")

        raw_details = self.details
        if not isinstance(raw_details, Mapping):
            raise TypeError("details must be a mapping of strings")
        frozen: dict[str, str] = {}
        for key, value in raw_details.items():
            frozen[_non_empty_text(key, label="detail key")] = _non_empty_text(
                value, label="detail value"
            )
        object.__setattr__(self, "details", MappingProxyType(frozen))

    def to_dict(self) -> dict[str, Any]:
        """Return the safe representation of this failure."""

        return {
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class ModelExecutionResult:
    """The normalized outcome of one canonical model execution."""

    status: ModelExecutionStatus
    request_id: str
    decision_id: str
    text: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    routing_decision_id: str | None = None
    usage_prompt_tokens: int = 0
    usage_completion_tokens: int = 0
    finish_reason: str | None = None
    error: ModelExecutionFailure | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ModelExecutionStatus):
            raise TypeError("status must be a ModelExecutionStatus")
        object.__setattr__(
            self, "request_id", _non_empty_text(self.request_id, label="request_id")
        )
        object.__setattr__(
            self, "decision_id", _non_empty_text(self.decision_id, label="decision_id")
        )
        for name in ("provider_id", "model_id", "routing_decision_id", "finish_reason"):
            object.__setattr__(
                self, name, _optional_reference(getattr(self, name), label=name)
            )

        if self.status is ModelExecutionStatus.SUCCEEDED:
            if self.error is not None:
                raise ValueError("a successful result cannot carry a failure")
            text = self.text
            if not isinstance(text, str) or not text.strip():
                raise ValueError(
                    "a successful result must carry a non-empty assistant text"
                )
            return

        if not isinstance(self.error, ModelExecutionFailure):
            raise TypeError("a failed result must carry a normalized failure")
        if self.text is not None:
            raise ValueError("a failed result cannot carry assistant text")

    @property
    def is_successful(self) -> bool:
        """Return whether the execution produced a canonical assistant text."""

        return self.status is ModelExecutionStatus.SUCCEEDED

    @property
    def total_tokens(self) -> int:
        """Return the total token usage reported by the provider."""

        return self.usage_prompt_tokens + self.usage_completion_tokens

    @classmethod
    def succeeded(
        cls,
        *,
        request_id: str,
        decision_id: str,
        text: str,
        provider_id: str,
        model_id: str,
        routing_decision_id: str,
        usage_prompt_tokens: int = 0,
        usage_completion_tokens: int = 0,
        finish_reason: str | None = None,
    ) -> ModelExecutionResult:
        """Return one normalized successful result carrying the assistant text."""
        return cls(
            status=ModelExecutionStatus.SUCCEEDED,
            request_id=request_id,
            decision_id=decision_id,
            text=text,
            provider_id=provider_id,
            model_id=model_id,
            routing_decision_id=routing_decision_id,
            usage_prompt_tokens=usage_prompt_tokens,
            usage_completion_tokens=usage_completion_tokens,
            finish_reason=finish_reason,
        )

    @classmethod
    def failed(
        cls,
        *,
        request_id: str,
        decision_id: str,
        error: ModelExecutionFailure,
        routing_decision_id: str | None = None,
    ) -> ModelExecutionResult:
        """Return one normalized failed result."""

        return cls(
            status=ModelExecutionStatus.FAILED,
            request_id=request_id,
            decision_id=decision_id,
            routing_decision_id=routing_decision_id,
            error=error,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the safe representation of this result."""

        return {
            "status": self.status.value,
            "request_id": self.request_id,
            "decision_id": self.decision_id,
            "text": self.text,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "routing_decision_id": self.routing_decision_id,
            "usage_prompt_tokens": self.usage_prompt_tokens,
            "usage_completion_tokens": self.usage_completion_tokens,
            "finish_reason": self.finish_reason,
            "error": None if self.error is None else self.error.to_dict(),
        }


#: The normalized availability a catalog entry reports to CMMChat.  A model is
#: *available* exactly when it is routable right now; the vocabulary is closed so
#: no provider-specific availability string can reach a client.
ModelAvailability = Literal["available", "unavailable"]


@dataclass(frozen=True, slots=True)
class NormalizedModel:
    """One CMM OS model projected for the CMMChat selector.

    This is a product-neutral, provider-free view of a canonical ``ModelSpec``
    and its ``ProviderSpec``.  ``model_id`` is the stable selection identity the
    client sends back; ``display_name`` is a human label derived from it; no
    field may carry a provider implementation detail.
    """

    model_id: str
    display_name: str
    provider_id: str
    locality: str  # "local" | "cloud"
    availability: ModelAvailability = "available"
    capabilities: Mapping[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "model_id", _non_empty_text(self.model_id, label="model_id")
        )
        object.__setattr__(
            self,
            "display_name",
            _non_empty_text(self.display_name, label="display_name"),
        )
        object.__setattr__(
            self, "provider_id", _non_empty_text(self.provider_id, label="provider_id")
        )
        if self.locality not in {"local", "cloud"}:
            raise ValueError("locality must be 'local' or 'cloud'")
        if self.availability not in ("available", "unavailable"):
            raise ValueError("availability must be 'available' or 'unavailable'")
        object.__setattr__(
            self, "capabilities", MappingProxyType(dict(self.capabilities))
        )


@dataclass(frozen=True, slots=True)
class ResolvedChatModel:
    """One model selection resolved against the canonical authorities.

    ``policy`` is ``"cmm-auto"`` when the canonical ``ModelRouter`` chose the
    model or ``"explicit"`` when the caller named it.  ``spec`` and ``provider``
    are the canonical, immutable catalog and registry entries the seam resolved;
    they are opaque to callers and are the only handle the seam needs to
    materialize a provider for streaming.
    """

    model: NormalizedModel
    policy: str
    spec: ModelSpec
    provider: ProviderSpec

    def __post_init__(self) -> None:
        if not isinstance(self.model, NormalizedModel):
            raise TypeError("model must be a NormalizedModel")
        if self.policy not in {"cmm-auto", "explicit"}:
            raise ValueError("policy must be 'cmm-auto' or 'explicit'")
        if not isinstance(self.spec, ModelSpec):
            raise TypeError("spec must be a canonical ModelSpec")
        if not isinstance(self.provider, ProviderSpec):
            raise TypeError("provider must be a canonical ProviderSpec")
