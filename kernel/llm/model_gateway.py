"""Canonical provider-independent Model Gateway (Phase 11.21).

The Model Gateway is the single model-call execution boundary of CMM OS.  It
owns normalization and execution only:

* canonical model/provider lookup through the exact canonical
  :class:`~kernel.llm.provider_registry.ProviderRegistry` and
  :class:`~kernel.llm.model_catalog.ModelCatalog` instances it was constructed
  with (never a copy, snapshot or second authority);
* preflight capability, reasoning-effort and modality validation before any
  provider I/O;
* canonical privacy enforcement before any remote egress;
* provider request translation through an injected provider adapter;
* normalized responses, streams, cancellation, timeout, bounded transport
  retry, authorized fallback mechanics and usage/latency/cost facts.

It owns none of: provider identity, model inventory, routing policy, user
preferences, conversation state, persistence, memory, domain logic, agent
planning, tool execution, permissions, approval, validation or events.  A
provider tool call grants the gateway no authority, and a provider being
available never implies permission to transmit.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass

from kernel.llm.capabilities import ReasoningEffort
from kernel.llm.exceptions import ProviderError
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_gateway_contracts import (
    InputPartKind,
    ModelCapabilityProjection,
    ModelExecutionEvidenceSink,
    ModelExecutionFacts,
    ModelGatewayRequest,
    ModelGatewayResponse,
    ModelUsage,
    PrivacyEgressDecision,
    PrivacyEgressGate,
)
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.model_provider_adapter import (
    ModelProviderAdapter,
    ModelProviderAdapterRegistry,
    ProviderModelRequest,
    ProviderModelResponse,
)
from kernel.llm.model_streaming import ModelCallCancellation, ModelCallHandle
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

__all__ = ["ModelGateway"]

_UNAVAILABLE_AVAILABILITY = frozenset({"unavailable", "disabled"})

#: A canonical requirement name maps to the declared capability field that must
#: be true.  ``document`` is validated against declared document media types.
_CAPABILITY_FIELD_NAMES = {
    "reasoning": "reasoning",
    "tool_calling": "tool_calling",
    "structured_output": "structured_output",
    "json_mode": "json_mode",
    "json_schema": "json_schema",
    "vision": "vision",
    "streaming": "streaming",
    "audio_input": "audio_input",
    "audio_output": "audio_output",
    "embeddings": "embeddings",
}

_DEFAULT_MAX_TIMEOUT_SECONDS = 300.0
_DEFAULT_MAX_ATTEMPTS = 1


@dataclass(frozen=True, slots=True)
class _ExecutionPlan:
    """The validated execution decision for one explicit model call."""

    model: ModelSpec
    provider: ProviderSpec
    adapter: ModelProviderAdapter
    capability_decision: str
    privacy_decision: str


class ModelGateway:
    """The canonical model-call execution boundary.

    Construction requires the exact canonical provider registry and the
    canonical model catalog bound to that registry.  The gateway stores those
    references and exposes them read-only so a composition boundary can prove
    exact object identity.
    """

    __slots__ = (
        "_adapter_registry",
        "_clock",
        "_evidence_sink",
        "_max_attempts",
        "_max_timeout_seconds",
        "_model_catalog",
        "_privacy_gate",
        "_provider_registry",
    )

    def __init__(
        self,
        *,
        provider_registry: ProviderRegistry,
        model_catalog: ModelCatalog,
        adapters: ModelProviderAdapterRegistry
        | Iterable[ModelProviderAdapter]
        | None = None,
        privacy_gate: PrivacyEgressGate | None = None,
        evidence_sink: ModelExecutionEvidenceSink | None = None,
        max_timeout_seconds: float = _DEFAULT_MAX_TIMEOUT_SECONDS,
        clock: object | None = None,
    ) -> None:
        if not isinstance(provider_registry, ProviderRegistry):
            raise TypeError("provider_registry must be a ProviderRegistry")
        if not isinstance(model_catalog, ModelCatalog):
            raise TypeError("model_catalog must be a ModelCatalog")
        if model_catalog.provider_registry is not provider_registry:
            raise ValueError(
                "model_catalog must be bound to the supplied provider_registry"
            )
        if not isinstance(max_timeout_seconds, (int, float)) or isinstance(
            max_timeout_seconds, bool
        ):
            raise TypeError("max_timeout_seconds must be a number")
        if not float(max_timeout_seconds) > 0:
            raise ValueError("max_timeout_seconds must be positive")

        self._provider_registry = provider_registry
        self._model_catalog = model_catalog
        self._adapter_registry = self._normalize_adapters(adapters)
        self._privacy_gate = self._normalize_privacy_gate(privacy_gate)
        self._evidence_sink = self._normalize_evidence_sink(evidence_sink)
        self._max_timeout_seconds = float(max_timeout_seconds)
        self._max_attempts = _DEFAULT_MAX_ATTEMPTS
        self._clock = clock if callable(clock) else time.perf_counter

    # ── Read-only authority accessors ────────────────────────────────────────

    @property
    def provider_registry(self) -> ProviderRegistry:
        """Return the exact canonical provider authority (read-only)."""

        return self._provider_registry

    @property
    def model_catalog(self) -> ModelCatalog:
        """Return the exact canonical model catalog (read-only)."""

        return self._model_catalog

    @property
    def adapter_registry(self) -> ModelProviderAdapterRegistry:
        """Return the execution-only adapter registry (read-only)."""

        return self._adapter_registry

    # ── Explicit model execution ─────────────────────────────────────────────

    def open_call(self, request: ModelGatewayRequest) -> ModelCallHandle:
        """Open a narrow, cancellable handle for one model call."""

        if not isinstance(request, ModelGatewayRequest):
            raise TypeError("request must be a ModelGatewayRequest")
        return ModelCallHandle(request_id=request.request_id)

    def execute(
        self,
        request: ModelGatewayRequest,
        *,
        cancellation: ModelCallCancellation | None = None,
    ) -> ModelGatewayResponse:
        """Execute one validated model request and return a normalized response."""

        if not isinstance(request, ModelGatewayRequest):
            raise TypeError("request must be a ModelGatewayRequest")

        started = self._clock()
        plan = self._preflight(request)

        attempt = 0
        last_error: ModelGatewayError | None = None
        while attempt < self._max_attempts:
            attempt += 1
            try:
                provider_response = self._execute_adapter(
                    plan,
                    self._provider_request(request, plan),
                    request,
                    cancellation,
                )
            except ModelGatewayError as error:
                last_error = error
                if not error.retryable or attempt >= self._max_attempts:
                    break
                continue
            return self._succeed(
                request,
                plan,
                provider_response,
                started=started,
                attempt=attempt,
            )

        raise self._failed(
            request,
            plan,
            last_error,
            started=started,
            attempt=attempt,
        )

    # ── Read-only capability projection ──────────────────────────────────────

    def model_capabilities(
        self,
        model_id: str,
        *,
        provider_id: str | None = None,
    ) -> ModelCapabilityProjection:
        """Return the canonical capability projection for one model.

        The projection is derived only from canonical registry/catalog state, so
        an unknown model fails closed with ``MODEL_NOT_FOUND`` and an unknown
        capability stays unknown rather than being guessed.
        """

        try:
            model = self._model_catalog.get(model_id, provider_id=provider_id)
        except ProviderError as error:
            raise ModelGatewayError(
                ModelGatewayErrorCode.MODEL_NOT_FOUND,
                "requested model is not registered",
                details={"model_id": str(model_id)},
            ) from error
        return self._project(model, self._resolve_provider(model))

    def list_model_capabilities(
        self,
        *,
        provider_id: str | None = None,
    ) -> tuple[ModelCapabilityProjection, ...]:
        """Return the capability projection for every canonical model, sorted."""

        return tuple(
            self._project(model, self._resolve_provider(model))
            for model in self._model_catalog.list(provider_id=provider_id)
        )

    # ── Construction helpers ─────────────────────────────────────────────────

    @staticmethod
    def _normalize_adapters(
        adapters: ModelProviderAdapterRegistry | Iterable[ModelProviderAdapter] | None,
    ) -> ModelProviderAdapterRegistry:
        if adapters is None:
            return ModelProviderAdapterRegistry()
        if isinstance(adapters, ModelProviderAdapterRegistry):
            return adapters
        return ModelProviderAdapterRegistry(adapters)

    @staticmethod
    def _normalize_privacy_gate(
        privacy_gate: PrivacyEgressGate | None,
    ) -> PrivacyEgressGate | None:
        if privacy_gate is None:
            return None
        if not callable(getattr(privacy_gate, "evaluate_egress", None)):
            raise TypeError("privacy_gate must implement evaluate_egress()")
        return privacy_gate

    @staticmethod
    def _normalize_evidence_sink(
        evidence_sink: ModelExecutionEvidenceSink | None,
    ) -> ModelExecutionEvidenceSink | None:
        if evidence_sink is None:
            return None
        if not callable(getattr(evidence_sink, "record", None)):
            raise TypeError("evidence_sink must implement record()")
        return evidence_sink

    # ── Preflight ────────────────────────────────────────────────────────────

    def _preflight(self, request: ModelGatewayRequest) -> _ExecutionPlan:
        if request.timeout_seconds > self._max_timeout_seconds:
            raise ModelGatewayError(
                ModelGatewayErrorCode.PROVIDER_REQUEST_INVALID,
                "requested timeout exceeds the gateway timeout ceiling",
                details={
                    "timeout_seconds": request.timeout_seconds,
                    "max_timeout_seconds": self._max_timeout_seconds,
                },
                retryable=False,
            )

        model = self._resolve_model(request)
        provider = self._resolve_provider(model)
        if provider is None:
            raise ModelGatewayError(
                ModelGatewayErrorCode.PROVIDER_NOT_AVAILABLE,
                "the model's provider is not registered",
                details={"provider_id": model.provider_id},
                retryable=False,
            )
        if not provider.enabled or provider.availability in _UNAVAILABLE_AVAILABILITY:
            raise ModelGatewayError(
                ModelGatewayErrorCode.PROVIDER_NOT_AVAILABLE,
                "the provider is not available for execution",
                details={"provider_id": provider.id},
                retryable=False,
            )
        if model.availability in _UNAVAILABLE_AVAILABILITY:
            raise ModelGatewayError(
                ModelGatewayErrorCode.MODEL_UNAVAILABLE,
                "the model is not available for execution",
                details={"model_id": model.qualified_id},
                retryable=False,
            )

        capability_decision = self._validate_capabilities(request, model)
        self._validate_modalities(request, model)
        privacy_decision = self._privacy_decision(request, provider)
        adapter = self._adapter_registry.get(model.provider_id)

        return _ExecutionPlan(
            model=model,
            provider=provider,
            adapter=adapter,
            capability_decision=capability_decision,
            privacy_decision=privacy_decision,
        )

    def _resolve_model(self, request: ModelGatewayRequest) -> ModelSpec:
        selection_mode = request.selection_mode
        if request.model_id is not None:
            try:
                model = self._model_catalog.get(
                    request.model_id,
                    provider_id=request.provider_id,
                )
            except ProviderError as error:
                raise ModelGatewayError(
                    ModelGatewayErrorCode.MODEL_NOT_FOUND,
                    "the requested model is not registered",
                    details={"model_id": request.model_id},
                ) from error
            if not self._model_catalog.is_bound_to_current_provider(model):
                raise ModelGatewayError(
                    ModelGatewayErrorCode.MODEL_UNAVAILABLE,
                    "the model is bound to a stale or missing provider authority",
                    details={"model_id": model.qualified_id},
                    retryable=False,
                )
            return model
        raise ModelGatewayError(
            ModelGatewayErrorCode.MODEL_NOT_FOUND,
            f"{selection_mode.value} model selection is not resolvable",
            retryable=False,
        )

    def _resolve_provider(self, model: ModelSpec) -> ProviderSpec | None:
        """Resolve a model's canonical provider, or ``None`` when it is gone."""

        try:
            return self._provider_registry.get(model.provider_id)
        except ProviderError:
            return None

    @staticmethod
    def _validate_capabilities(
        request: ModelGatewayRequest,
        model: ModelSpec,
    ) -> str:
        capabilities = model.capabilities
        effort = request.reasoning_effort
        if effort is not ReasoningEffort.DEFAULT and (
            not capabilities.supports_reasoning_effort(effort)
        ):
            raise ModelGatewayError(
                ModelGatewayErrorCode.UNSUPPORTED_REASONING_EFFORT,
                "the model does not declare the requested reasoning effort",
                details={"effort": effort.value, "model_id": model.qualified_id},
                retryable=False,
            )
        if request.tools and not capabilities.tool_calling:
            raise ModelGatewayError(
                ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED,
                "the model does not declare tool-calling support",
                details={"model_id": model.qualified_id},
                retryable=False,
            )
        if request.structured_output is not None:
            if not capabilities.structured_output:
                raise ModelGatewayError(
                    ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED,
                    "the model does not declare structured-output support",
                    details={"model_id": model.qualified_id},
                    retryable=False,
                )
            if (
                request.structured_output.schema is not None
                and not capabilities.json_schema
            ):
                raise ModelGatewayError(
                    ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED,
                    "the model does not declare JSON-schema support",
                    details={"model_id": model.qualified_id},
                    retryable=False,
                )
        for name in request.required_capabilities:
            if name == "document":
                if not capabilities.document_media_types:
                    raise ModelGatewayError(
                        ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED,
                        "the model does not declare document input support",
                        details={"capability": name, "model_id": model.qualified_id},
                        retryable=False,
                    )
                continue
            if not getattr(capabilities, _CAPABILITY_FIELD_NAMES[name]):
                raise ModelGatewayError(
                    ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED,
                    "the model does not support a required capability",
                    details={"capability": name, "model_id": model.qualified_id},
                    retryable=False,
                )
        return "verified"

    @staticmethod
    def _validate_modalities(
        request: ModelGatewayRequest,
        model: ModelSpec,
    ) -> None:
        """Fail closed before provider I/O when a model cannot take an input part.

        The declared canonical capabilities are the only authority: image input
        requires declared vision, and a document part requires the model to
        declare that exact media type.  Nothing is inferred and nothing is
        silently degraded (a PDF is never converted to extracted text here).
        """

        capabilities = model.capabilities
        for part in request.input_parts:
            if part.kind is InputPartKind.IMAGE and not capabilities.vision:
                raise ModelGatewayError(
                    ModelGatewayErrorCode.INPUT_MODALITY_UNSUPPORTED,
                    "the model does not declare image input support",
                    details={
                        "kind": part.kind.value,
                        "media_type": part.media_type,
                        "model_id": model.qualified_id,
                    },
                    retryable=False,
                )
            if part.kind is InputPartKind.DOCUMENT and not (
                capabilities.supports_document_media_type(part.media_type or "")
            ):
                raise ModelGatewayError(
                    ModelGatewayErrorCode.INPUT_MODALITY_UNSUPPORTED,
                    "the model does not declare this document media type",
                    details={
                        "kind": part.kind.value,
                        "media_type": part.media_type,
                        "model_id": model.qualified_id,
                    },
                    retryable=False,
                )

    # ── Privacy before egress ────────────────────────────────────────────────

    def _privacy_decision(
        self,
        request: ModelGatewayRequest,
        provider: ProviderSpec,
    ) -> str:
        is_remote = provider.provider_type == "remote"
        if not is_remote:
            if request.privacy is None or self._privacy_gate is None:
                return "not_required"
            decision = self._evaluate_egress(request, provider, is_remote=False)
            if not decision.allowed:
                raise self._privacy_denied(decision, provider)
            return decision.reason_code

        if request.privacy is None:
            raise ModelGatewayError(
                ModelGatewayErrorCode.PRIVACY_DENIED,
                "remote transmission requires canonical privacy metadata",
                details={"provider_id": provider.id},
                retryable=False,
            )
        if self._privacy_gate is None:
            raise ModelGatewayError(
                ModelGatewayErrorCode.PRIVACY_DENIED,
                "no canonical privacy authority is configured for remote egress",
                details={"provider_id": provider.id},
                retryable=False,
            )
        decision = self._evaluate_egress(request, provider, is_remote=True)
        if not decision.allowed:
            raise self._privacy_denied(decision, provider)
        return decision.reason_code

    def _evaluate_egress(
        self,
        request: ModelGatewayRequest,
        provider: ProviderSpec,
        *,
        is_remote: bool,
    ) -> PrivacyEgressDecision:
        try:
            decision = self._privacy_gate.evaluate_egress(  # type: ignore[union-attr]
                privacy=request.privacy,
                provider_id=provider.id,
                is_remote=is_remote,
            )
        except ModelGatewayError:
            raise
        except Exception as error:
            raise ModelGatewayError(
                ModelGatewayErrorCode.PRIVACY_DENIED,
                "canonical privacy evaluation failed",
                details={"provider_id": provider.id},
                retryable=False,
            ) from error
        if not isinstance(decision, PrivacyEgressDecision):
            raise ModelGatewayError(
                ModelGatewayErrorCode.PRIVACY_DENIED,
                "canonical privacy authority returned an unusable decision",
                details={"provider_id": provider.id},
                retryable=False,
            )
        return decision

    @staticmethod
    def _privacy_denied(
        decision: PrivacyEgressDecision,
        provider: ProviderSpec,
    ) -> ModelGatewayError:
        return ModelGatewayError(
            ModelGatewayErrorCode.PRIVACY_DENIED,
            "canonical privacy policy denied provider egress",
            details={
                "provider_id": provider.id,
                "reason_code": decision.reason_code,
            },
            retryable=False,
        )

    # ── Adapter invocation ───────────────────────────────────────────────────

    @staticmethod
    def _provider_request(
        request: ModelGatewayRequest,
        plan: _ExecutionPlan,
    ) -> ProviderModelRequest:
        return ProviderModelRequest(
            request_id=request.request_id,
            provider_id=plan.provider.id,
            model_id=plan.model.id,
            input_parts=request.input_parts,
            reasoning_effort=request.reasoning_effort,
            tools=request.tools,
            structured_output=request.structured_output,
            timeout_seconds=request.timeout_seconds,
        )

    def _execute_adapter(
        self,
        plan: _ExecutionPlan,
        provider_request: ProviderModelRequest,
        request: ModelGatewayRequest,
        cancellation: ModelCallCancellation | None,
    ) -> ProviderModelResponse:
        if cancellation is not None and cancellation.is_cancelled:
            raise ModelGatewayError(
                ModelGatewayErrorCode.MODEL_CALL_CANCELLED,
                "model call was cancelled before provider execution",
                retryable=False,
            )

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(
            plan.adapter.execute,
            provider_request,
            cancellation=cancellation,
        )
        try:
            provider_response = future.result(timeout=request.timeout_seconds)
        except FuturesTimeoutError as error:
            if cancellation is not None:
                cancellation.cancel("model call timed out")
            raise ModelGatewayError(
                ModelGatewayErrorCode.PROVIDER_TIMEOUT,
                "model call exceeded its timeout",
                details={
                    "provider_id": plan.provider.id,
                    "timeout_seconds": request.timeout_seconds,
                },
                retryable=True,
            ) from error
        except ModelGatewayError:
            raise
        except Exception as error:
            raise ModelGatewayError(
                ModelGatewayErrorCode.PROVIDER_FAILURE,
                "provider execution failed",
                details={"provider_id": plan.provider.id},
                retryable=True,
            ) from error
        finally:
            executor.shutdown(wait=False)

        if (
            request.structured_output is not None
            and request.structured_output.required
            and provider_response.structured_output is None
        ):
            raise ModelGatewayError(
                ModelGatewayErrorCode.STRUCTURED_OUTPUT_INVALID,
                "provider returned no structured output for a required requirement",
                details={"provider_id": plan.provider.id},
                retryable=False,
            )
        if provider_response.tool_calls and not request.tools:
            raise ModelGatewayError(
                ModelGatewayErrorCode.TOOL_CALL_INVALID,
                "provider returned a tool call that the request never declared",
                details={"provider_id": plan.provider.id},
                retryable=False,
            )
        if provider_response.effective_reasoning_effort is not request.reasoning_effort:
            raise ModelGatewayError(
                ModelGatewayErrorCode.PROVIDER_FAILURE,
                "provider adapter changed the requested reasoning effort",
                details={
                    "provider_id": plan.provider.id,
                    "requested_effort": request.reasoning_effort.value,
                    "effective_effort": provider_response.effective_reasoning_effort.value,
                },
                retryable=False,
            )
        return provider_response

    # ── Result normalization ─────────────────────────────────────────────────

    def _succeed(
        self,
        request: ModelGatewayRequest,
        plan: _ExecutionPlan,
        provider_response: ProviderModelResponse,
        *,
        started: float,
        attempt: int,
    ) -> ModelGatewayResponse:
        facts = self._facts(
            request,
            plan,
            started=started,
            attempt=attempt,
            success=True,
            error_code=None,
            finish_reason=provider_response.finish_reason,
            usage=provider_response.usage,
            reasoning_used=provider_response.reasoning_used,
            effective_reasoning_effort=provider_response.effective_reasoning_effort,
        )
        self._emit(facts)
        return ModelGatewayResponse(
            request_id=request.request_id,
            provider_id=plan.provider.id,
            model_id=plan.model.id,
            selection_mode=request.selection_mode,
            content=provider_response.content,
            structured_output=provider_response.structured_output,
            tool_calls=provider_response.tool_calls,
            usage=provider_response.usage,
            facts=facts,
            finish_reason=provider_response.finish_reason,
            cancelled=False,
            error_code=None,
            reasoning_used=provider_response.reasoning_used,
            effective_reasoning_effort=provider_response.effective_reasoning_effort,
        )

    def _failed(
        self,
        request: ModelGatewayRequest,
        plan: _ExecutionPlan,
        error: ModelGatewayError | None,
        *,
        started: float,
        attempt: int,
    ) -> ModelGatewayError:
        failure = error or ModelGatewayError(
            ModelGatewayErrorCode.PROVIDER_FAILURE,
            "model call failed",
            retryable=False,
        )
        facts = self._facts(
            request,
            plan,
            started=started,
            attempt=attempt,
            success=False,
            error_code=failure.code.value,
            finish_reason=None,
            usage=None,
            reasoning_used=False,
            effective_reasoning_effort=request.reasoning_effort,
        )
        self._emit(facts)
        return failure

    def _facts(
        self,
        request: ModelGatewayRequest,
        plan: _ExecutionPlan,
        *,
        started: float,
        attempt: int,
        success: bool,
        error_code: str | None,
        finish_reason: str | None,
        usage: ModelUsage | None,
        reasoning_used: bool,
        effective_reasoning_effort: ReasoningEffort,
    ) -> ModelExecutionFacts:
        latency_ms = max(int((self._clock() - started) * 1000), 0)
        return ModelExecutionFacts(
            request_id=request.request_id,
            provider_id=plan.provider.id,
            model_id=plan.model.id,
            selection_mode=request.selection_mode,
            success=success,
            capability_decision=plan.capability_decision,
            privacy_decision=plan.privacy_decision,
            requested_reasoning_effort=request.reasoning_effort,
            effective_reasoning_effort=effective_reasoning_effort,
            reasoning_used=reasoning_used,
            input_modalities=request.input_modalities,
            tool_use=bool(request.tools),
            structured_output_use=request.structured_output is not None,
            streamed=False,
            cancelled=error_code == ModelGatewayErrorCode.MODEL_CALL_CANCELLED.value,
            timed_out=error_code == ModelGatewayErrorCode.PROVIDER_TIMEOUT.value,
            retry_count=max(attempt - 1, 0),
            usage=usage if usage is not None else ModelUsage(),
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            error_code=error_code,
        )

    def _emit(self, facts: ModelExecutionFacts) -> None:
        if self._evidence_sink is not None:
            self._evidence_sink.record(facts)

    # ── Capability projection helpers ────────────────────────────────────────

    def _project(
        self,
        model: ModelSpec,
        provider: ProviderSpec | None,
    ) -> ModelCapabilityProjection:
        """Build one truthful, read-only capability projection."""

        authority_current = self._model_catalog.is_bound_to_current_provider(model)
        capabilities = model.capabilities

        if provider is None:
            provider_type = "unknown"
            provider_available = False
        else:
            provider_type = provider.provider_type
            provider_available = (
                authority_current
                and provider.enabled
                and provider.availability not in _UNAVAILABLE_AVAILABILITY
            )

        return ModelCapabilityProjection(
            model_id=model.id,
            provider_id=model.provider_id,
            qualified_id=model.qualified_id,
            provider_type=provider_type,
            is_local=provider_type == "local",
            provider_available=provider_available,
            model_available=model.availability not in _UNAVAILABLE_AVAILABILITY,
            authority_current=authority_current,
            context_window=model.context_window,
            reasoning=capabilities.reasoning,
            reasoning_efforts=capabilities.reasoning_efforts,
            tool_calling=capabilities.tool_calling,
            structured_output=capabilities.structured_output,
            json_mode=capabilities.json_mode,
            json_schema=capabilities.json_schema,
            vision=capabilities.vision,
            document_media_types=capabilities.document_media_types,
            streaming=capabilities.streaming,
            audio_input=capabilities.audio_input,
            audio_output=capabilities.audio_output,
            embeddings=capabilities.embeddings,
            aliases=model.aliases,
            version=model.version,
            input_cost_per_million=model.input_cost_per_million,
            output_cost_per_million=model.output_cost_per_million,
            cached_input_cost_per_million=model.cached_input_cost_per_million,
        )
