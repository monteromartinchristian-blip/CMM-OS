"""CMMChat Wave E0 — the canonical model execution seam.

``CanonicalModelExecutor`` is the one place where a canonical conversational
request becomes a real model inference.  It is execution glue and owns no
authority of its own:

* it makes **no** routing decision — the canonical
  :class:`~kernel.llm.model_router.ModelRouter` evaluates the canonical
  ``ModelRequirements`` and returns the auditable ``RoutingDecision``;
* it builds **no** provider — the canonical
  :class:`~kernel.llm.provider_factory.ProviderFactory` materializes the
  canonical ``OpenAICompatibleProvider`` from that decision, resolving the
  provider's own configured credential and base URL;
* it implements **no** provider protocol and no transport — the inference runs
  through the canonical :class:`~kernel.llm.provider.LLMProvider`, whose
  transport is the canonical ``OpenAICompatibleClient``;
* it holds no catalog, no registry, no policy, no state and no session: the
  canonical ``ProviderRegistry`` and ``ModelCatalog`` instances are injected, and
  the catalog must be bound to the injected registry.

The seam is therefore composition/execution glue: it maps one canonical request
onto the canonical ``LLMRequest``, invokes the canonical provider once, and
normalizes the canonical ``LLMResponse`` back into a canonical result.

Failure semantics: every provider, transport and response defect becomes a
normalized, secret-free :class:`ModelExecutionResult` failure.  No provider
message, response body, credential or traceback can reach a result, and only the
canonical route ``DIRECT_RESPONSE`` may reach a model at all.
"""

from __future__ import annotations

from typing import Any

from cmm.model_execution.contracts import (
    ModelExecutionErrorCode,
    ModelExecutionFailure,
    ModelExecutionRequest,
    ModelExecutionResult,
)
from cmm.orchestration.contracts import ExecutionRoute
from kernel.llm.model_catalog import ModelCatalog
from kernel.llm.model_router import ModelRouter, RoutingDecision
from kernel.llm.models import LLMRequest, LLMResponse
from kernel.llm.provider import LLMProvider
from kernel.llm.provider_factory import ProviderFactory
from kernel.llm.provider_registry import ProviderRegistry

__all__ = ["CanonicalModelExecutor"]

#: The one canonical execution route a model inference may serve.
EXECUTABLE_ROUTE = ExecutionRoute.DIRECT_RESPONSE

#: The public length bound of the assistant text the seam reports.  A provider
#: answer longer than this is refused rather than silently truncated, so the
#: normalized result is never a partial answer presented as a complete one.
MAX_ASSISTANT_TEXT_LENGTH = 1_000_000

#: Application-owned safe failure messages.  They are constants, so no upstream
#: text can be interpolated into a public failure.
ROUTE_NOT_EXECUTABLE_MESSAGE = (
    "The canonical route selected for this request is not a model inference"
)
MODEL_UNAVAILABLE_MESSAGE = "No canonical model satisfies the request"
PROVIDER_UNAVAILABLE_MESSAGE = "The canonical model provider is not available"
PROVIDER_FAILURE_MESSAGE = "The model provider failed to complete the request"
PROVIDER_RESPONSE_INVALID_MESSAGE = "The model provider returned an unusable response"


def _require_canonical_role(name: str, implementation: object, contract: type) -> None:
    """Fail closed unless *implementation* is the canonical *contract*.

    Every collaborator is validated at construction, so a cross-wired graph
    fails before any request is executed — including a hand-built executor that
    never passed through the canonical composition.  The message names the role
    and the offending type only; no collaborator state is interpolated.
    """

    if not isinstance(implementation, contract):
        raise TypeError(
            f"{name} must hold the canonical {contract.__name__} role, "
            f"got {type(implementation).__name__}"
        )


class CanonicalModelExecutor:
    """Executes one canonical model execution request through the canonical stack."""

    def __init__(
        self,
        *,
        model_router: ModelRouter,
        provider_factory: ProviderFactory,
        provider_registry: ProviderRegistry,
        model_catalog: ModelCatalog,
        client: Any | None = None,
    ) -> None:
        _require_canonical_role("model_router", model_router, ModelRouter)
        _require_canonical_role("provider_factory", provider_factory, ProviderFactory)
        _require_canonical_role(
            "provider_registry", provider_registry, ProviderRegistry
        )
        _require_canonical_role("model_catalog", model_catalog, ModelCatalog)
        if model_catalog.provider_registry is not provider_registry:
            raise TypeError(
                "model_catalog must be bound to the supplied canonical "
                "provider_registry"
            )

        self._model_router = model_router
        self._provider_factory = provider_factory
        self._provider_registry = provider_registry
        self._model_catalog = model_catalog
        # The canonical factory's own documented injection point: production
        # passes ``None``, so the factory resolves the provider's configured
        # credential and base URL from the canonical ProviderSpec.
        self._client = client

    # ── Public API ───────────────────────────────────────────────────────────

    def execute(self, request: ModelExecutionRequest) -> ModelExecutionResult:
        """Execute one canonical request, or fail closed with a safe result.

        A non-``ModelExecutionRequest`` is a caller defect at the direct Python
        boundary and raises ``TypeError``; every other defect becomes a
        normalized failure, so no exception and no upstream text escapes.
        """

        if not isinstance(request, ModelExecutionRequest):
            raise TypeError(
                f"request must be a ModelExecutionRequest, got {type(request).__name__}"
            )

        if request.route is not EXECUTABLE_ROUTE:
            return self._failed(
                request,
                ModelExecutionErrorCode.ROUTE_NOT_EXECUTABLE,
                ROUTE_NOT_EXECUTABLE_MESSAGE,
                retryable=False,
                details={"route": request.route.value},
            )

        decision = self._routing_decision(request)
        if isinstance(decision, ModelExecutionResult):
            return decision

        selected_provider_id = decision.selected_provider_id
        selected_model_id = decision.selected_model_id
        if selected_provider_id is None or selected_model_id is None:
            # A decision that claims a selection but names no model is
            # malformed: it is refused rather than completed with empty
            # metadata.
            return self._failed(
                request,
                ModelExecutionErrorCode.MODEL_UNAVAILABLE,
                MODEL_UNAVAILABLE_MESSAGE,
                retryable=False,
            )

        provider = self._materialized_provider(request, decision)
        if isinstance(provider, ModelExecutionResult):
            return provider

        response = self._generated_response(request, decision, provider)
        if isinstance(response, ModelExecutionResult):
            return response

        return ModelExecutionResult.succeeded(
            request_id=request.request_id,
            decision_id=request.decision_id,
            text=response.content.strip(),
            provider_id=selected_provider_id,
            model_id=response.model or selected_model_id,
            routing_decision_id=decision.id,
            usage_prompt_tokens=response.usage_prompt_tokens,
            usage_completion_tokens=response.usage_completion_tokens,
            finish_reason=response.finish_reason,
        )

    # ── Canonical delegation ─────────────────────────────────────────────────

    def _routing_decision(
        self, request: ModelExecutionRequest
    ) -> RoutingDecision | ModelExecutionResult:
        """Delegate model selection to the canonical ``ModelRouter``."""

        try:
            decision = self._model_router.decide(request.requirements)
        except Exception:  # noqa: BLE001 - every defect becomes a safe failure
            return self._failed(
                request,
                ModelExecutionErrorCode.MODEL_UNAVAILABLE,
                MODEL_UNAVAILABLE_MESSAGE,
                retryable=False,
            )

        if not isinstance(decision, RoutingDecision) or decision.status != "selected":
            return self._failed(
                request,
                ModelExecutionErrorCode.MODEL_UNAVAILABLE,
                MODEL_UNAVAILABLE_MESSAGE,
                retryable=False,
            )
        return decision

    def _materialized_provider(
        self, request: ModelExecutionRequest, decision: RoutingDecision
    ) -> LLMProvider | ModelExecutionResult:
        """Delegate provider construction to the canonical ``ProviderFactory``."""

        try:
            provider = self._provider_factory.create_from_decision(
                decision,
                provider_registry=self._provider_registry,
                model_catalog=self._model_catalog,
                client=self._client,
            )
        except Exception:  # noqa: BLE001 - every defect becomes a safe failure
            return self._failed(
                request,
                ModelExecutionErrorCode.PROVIDER_UNAVAILABLE,
                PROVIDER_UNAVAILABLE_MESSAGE,
                retryable=True,
                details=self._decision_details(decision),
                routing_decision_id=decision.id,
            )

        if not isinstance(provider, LLMProvider):
            return self._failed(
                request,
                ModelExecutionErrorCode.PROVIDER_UNAVAILABLE,
                PROVIDER_UNAVAILABLE_MESSAGE,
                retryable=True,
                details=self._decision_details(decision),
                routing_decision_id=decision.id,
            )
        return provider

    def _generated_response(
        self,
        request: ModelExecutionRequest,
        decision: RoutingDecision,
        provider: LLMProvider,
    ) -> LLMResponse | ModelExecutionResult:
        """Invoke the canonical provider once and validate its canonical answer."""

        try:
            response = provider.generate(self._llm_request(request))
        except Exception:  # noqa: BLE001 - every defect becomes a safe failure
            return self._failed(
                request,
                ModelExecutionErrorCode.PROVIDER_FAILURE,
                PROVIDER_FAILURE_MESSAGE,
                retryable=True,
                details=self._decision_details(decision),
                routing_decision_id=decision.id,
            )

        if (
            not isinstance(response, LLMResponse)
            or not isinstance(response.content, str)
            or not response.content.strip()
            or len(response.content) > MAX_ASSISTANT_TEXT_LENGTH
        ):
            return self._failed(
                request,
                ModelExecutionErrorCode.PROVIDER_RESPONSE_INVALID,
                PROVIDER_RESPONSE_INVALID_MESSAGE,
                retryable=False,
                details=self._decision_details(decision),
                routing_decision_id=decision.id,
            )
        return response

    # ── Mapping ──────────────────────────────────────────────────────────────

    @staticmethod
    def _llm_request(request: ModelExecutionRequest) -> LLMRequest:
        """Map one canonical request onto the canonical ``LLMRequest``.

        E0 is plain text inference: the conversational text is the prompt, no
        system prompt is invented, and the only metadata forwarded is the
        canonical ``max_tokens`` the existing provider already reads.
        """

        metadata: dict[str, Any] = {}
        if request.parameters.max_tokens is not None:
            metadata["max_tokens"] = request.parameters.max_tokens
        return LLMRequest(
            prompt=request.prompt,
            temperature=request.parameters.temperature,
            metadata=metadata,
        )

    @staticmethod
    def _decision_details(decision: RoutingDecision) -> dict[str, str]:
        """Return the safe identifier details of one routing decision."""

        details: dict[str, str] = {}
        if decision.selected_provider_id:
            details["provider_id"] = decision.selected_provider_id
        if decision.selected_model_id:
            details["model_id"] = decision.selected_model_id
        return details

    def _failed(
        self,
        request: ModelExecutionRequest,
        code: ModelExecutionErrorCode,
        message: str,
        *,
        retryable: bool,
        details: dict[str, str] | None = None,
        routing_decision_id: str | None = None,
    ) -> ModelExecutionResult:
        """Return one normalized, secret-free failed result."""

        return ModelExecutionResult.failed(
            request_id=request.request_id,
            decision_id=request.decision_id,
            error=ModelExecutionFailure(
                code=code,
                message=message,
                retryable=retryable,
                details=details or {},
            ),
            routing_decision_id=routing_decision_id,
        )
