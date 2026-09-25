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
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal

from kernel.llm.capabilities import ReasoningEffort
from kernel.llm.exceptions import ProviderError
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_gateway_contracts import (
    InputPartKind,
    ModelCapabilityProjection,
    ModelExecutionEvidenceSink,
    ModelExecutionFacts,
    ModelFallbackAttempt,
    ModelFallbackPlanner,
    ModelGatewayRequest,
    ModelGatewayResponse,
    ModelGatewayRetryPolicy,
    ModelStreamEvent,
    ModelStreamEventType,
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
from kernel.llm.model_router import RoutingCandidate
from kernel.llm.model_selection import ModelRequirements, find_matching_models
from kernel.llm.model_streaming import (
    ModelCallCancellation,
    ModelCallHandle,
    ModelStreamNormalizer,
)
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

__all__ = ["ModelGateway", "derive_model_call_cost"]

#: Deterministic cost precision for catalog-derived pricing.
_COST_QUANTUM = Decimal("0.00000001")
_PER_MILLION = Decimal(1000000)


def derive_model_call_cost(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_tokens: int | None,
    input_cost_per_million: Decimal | None,
    output_cost_per_million: Decimal | None,
    cached_input_cost_per_million: Decimal | None,
) -> Decimal | None:
    """Derive a per-call cost from canonical pricing metadata, or ``None``.

    Returns ``None`` — never zero — whenever the available metadata cannot price
    the call deterministically: an unknown token count, or a missing price for a
    token count that *is* known.  Cached tokens are billed at the cached price
    when one is published and at the input price otherwise, and are never billed
    twice.
    """

    if input_tokens is None and output_tokens is None:
        return None
    if input_tokens is not None and input_cost_per_million is None:
        return None
    if output_tokens is not None and output_cost_per_million is None:
        return None

    total = Decimal(0)
    if input_tokens is not None:
        cached = min(cached_tokens or 0, input_tokens)
        billed_input = input_tokens - cached
        total += Decimal(billed_input) * input_cost_per_million  # type: ignore[operator]
        cached_price = (
            cached_input_cost_per_million
            if cached_input_cost_per_million is not None
            else input_cost_per_million
        )
        total += Decimal(cached) * cached_price  # type: ignore[operator]
    if output_tokens is not None:
        total += Decimal(output_tokens) * output_cost_per_million  # type: ignore[operator]
    return (total / _PER_MILLION).quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP)


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

#: The canonical ``ModelFallbackAction.NEXT_ROUTING_CANDIDATE`` value.  The
#: gateway never imports the fallback authority's types; it reads the injected
#: planner's decision through this one documented value.
_NEXT_CANDIDATE_ACTION = "next_routing_candidate"


@dataclass(frozen=True, slots=True)
class _ExecutionPlan:
    """The validated execution decision for one explicit model call."""

    model: ModelSpec
    provider: ProviderSpec
    adapter: ModelProviderAdapter
    capability_decision: str
    privacy_decision: str


class _CandidateHardGateFailure(Exception):
    """One candidate failed a candidate-local hard execution gate.

    A candidate-local failure never aborts AUTO selection: the gateway records
    the safe canonical failure code, skips that candidate and evaluates the next
    one in the canonical order.  A malformed or request-level failure is raised
    as its own :class:`ModelGatewayError` instead, which stays terminal and must
    never be skipped.

    For an explicit-model request the original gate error is carried so the
    caller receives exactly the error the gate produced, with its own message
    and details.  A gate modelled without an explicit error (provider/model
    availability) carries a bare canonical code.
    """

    __slots__ = ("code", "error")

    def __init__(
        self,
        code: ModelGatewayErrorCode,
        error: ModelGatewayError | None = None,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.error = error


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
        "_fallback_planner",
        "_max_timeout_seconds",
        "_model_catalog",
        "_privacy_gate",
        "_provider_registry",
        "_retry_policy",
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
        retry_policy: ModelGatewayRetryPolicy | None = None,
        fallback_planner: ModelFallbackPlanner | None = None,
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
        if retry_policy is not None and not isinstance(
            retry_policy, ModelGatewayRetryPolicy
        ):
            raise TypeError("retry_policy must be a ModelGatewayRetryPolicy or None")
        if fallback_planner is not None and not callable(
            getattr(fallback_planner, "next_selection", None)
        ):
            raise TypeError("fallback_planner must implement next_selection()")
        self._retry_policy = retry_policy or ModelGatewayRetryPolicy()
        self._fallback_planner = fallback_planner
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
        """Execute one validated model request and return a normalized response.

        One cancellation token belongs to the whole model call, so it stays
        authoritative across the primary attempt, transport retry, retry backoff,
        fallback planning, fallback preflight and fallback execution.
        Cancellation beats every recovery path: a cancelled call ends with
        ``MODEL_CALL_CANCELLED`` and performs no later provider I/O.
        """

        if not isinstance(request, ModelGatewayRequest):
            raise TypeError("request must be a ModelGatewayRequest")
        if cancellation is not None and not isinstance(
            cancellation, ModelCallCancellation
        ):
            raise TypeError("cancellation must be a ModelCallCancellation or None")
        if request.stream:
            raise ModelGatewayError(
                ModelGatewayErrorCode.PROVIDER_REQUEST_INVALID,
                "a streaming request must be executed through stream()",
                retryable=False,
            )

        started = self._clock()
        plan = self._preflight(request)
        self._raise_if_call_cancelled(cancellation)

        policy = self._retry_policy
        attempt = 0
        last_error: ModelGatewayError | None = None
        while attempt < policy.max_attempts:
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
                self._raise_if_call_cancelled(cancellation)
                if not error.retryable or attempt >= policy.max_attempts:
                    break
                if policy.backoff_seconds:
                    time.sleep(policy.backoff_seconds)
                self._raise_if_call_cancelled(cancellation)
                continue
            self._raise_if_call_cancelled(cancellation)
            return self._succeed(
                request,
                plan,
                provider_response,
                started=started,
                attempt=attempt,
            )

        self._raise_if_call_cancelled(cancellation)
        if (
            last_error is not None
            and last_error.retryable
            and request.fallback_model_ids
            and self._fallback_planner is not None
        ):
            return self._execute_authorized_fallback(
                request,
                plan,
                last_error,
                started=started,
                attempt=attempt,
                cancellation=cancellation,
            )

        raise self._failed(
            request,
            plan,
            last_error,
            started=started,
            attempt=attempt,
        )

    # ── Canonical provider-token streaming ───────────────────────────────────

    def stream(
        self,
        request: ModelGatewayRequest,
        *,
        cancellation: ModelCallCancellation | None = None,
    ) -> Iterator[ModelStreamEvent]:
        """Stream one validated model call as canonical, ordered events.

        The returned stream always begins with exactly one ``STARTED`` event and
        ends with exactly one terminal event.  Nothing is emitted after a
        terminal event, and no raw provider object or hidden reasoning ever
        appears.  Streaming is intentionally not retried: once any content was
        emitted, re-attempting would duplicate it.
        """

        if not isinstance(request, ModelGatewayRequest):
            raise TypeError("request must be a ModelGatewayRequest")

        started = self._clock()
        plan = self._preflight(request, require_streaming=True)
        normalizer = ModelStreamNormalizer(
            request_id=request.request_id,
            provider_id=plan.provider.id,
            model_id=plan.model.id,
        )
        started_event = normalizer.started_event(
            effective_reasoning_effort=request.reasoning_effort,
            reasoning_used=False,
        )
        if started_event is not None:
            yield started_event

        provider_request = self._provider_request(request, plan)
        try:
            adapter_events: Iterator[object] = iter(
                plan.adapter.stream(provider_request, cancellation=cancellation)
            )
        except ModelGatewayError as error:
            yield self._stream_failure(
                request, plan, normalizer, error, started=started
            )
            return
        except Exception:  # noqa: BLE001 - normalize any provider failure
            yield self._stream_failure(
                request,
                plan,
                normalizer,
                ModelGatewayError(
                    ModelGatewayErrorCode.PROVIDER_FAILURE,
                    "provider stream could not be opened",
                    details={"provider_id": plan.provider.id},
                    retryable=False,
                ),
                started=started,
            )
            return

        deadline = started + request.timeout_seconds
        accumulated: list[str] = []
        latest_usage = None
        saw_tool_call = False

        while True:
            if cancellation is not None and cancellation.is_cancelled:
                yield self._stream_cancelled(request, plan, normalizer, started=started)
                return
            if self._clock() > deadline:
                if cancellation is not None:
                    cancellation.cancel("model stream timed out")
                yield self._stream_failure(
                    request,
                    plan,
                    normalizer,
                    ModelGatewayError(
                        ModelGatewayErrorCode.PROVIDER_TIMEOUT,
                        "model stream exceeded its timeout",
                        details={
                            "provider_id": plan.provider.id,
                            "timeout_seconds": request.timeout_seconds,
                        },
                        retryable=True,
                    ),
                    started=started,
                )
                return
            try:
                adapter_event = next(adapter_events)
            except StopIteration:
                break
            except ModelGatewayError as error:
                yield self._stream_failure(
                    request, plan, normalizer, error, started=started
                )
                return
            except Exception:  # noqa: BLE001 - normalize any provider failure
                yield self._stream_failure(
                    request,
                    plan,
                    normalizer,
                    ModelGatewayError(
                        ModelGatewayErrorCode.PROVIDER_FAILURE,
                        "provider stream failed",
                        details={"provider_id": plan.provider.id},
                        retryable=False,
                    ),
                    started=started,
                )
                return

            event_type = getattr(adapter_event, "event_type", None)
            if event_type is ModelStreamEventType.STARTED:
                continue
            if event_type is ModelStreamEventType.CONTENT_DELTA:
                delta = getattr(adapter_event, "content_delta", None)
                if not delta:
                    yield self._stream_failure(
                        request,
                        plan,
                        normalizer,
                        ModelGatewayError(
                            ModelGatewayErrorCode.STREAM_FAILURE,
                            "provider stream emitted an empty content delta",
                            details={"provider_id": plan.provider.id},
                            retryable=False,
                        ),
                        started=started,
                    )
                    return
                accumulated.append(delta)
                normalized = normalizer.content_event(delta)
                if normalized is not None:
                    yield normalized
                continue
            if event_type is ModelStreamEventType.TOOL_CALL_DELTA:
                tool_call = getattr(adapter_event, "tool_call", None)
                if tool_call is None:
                    yield self._stream_failure(
                        request,
                        plan,
                        normalizer,
                        ModelGatewayError(
                            ModelGatewayErrorCode.STREAM_FAILURE,
                            "provider stream emitted an unnormalized tool call",
                            details={"provider_id": plan.provider.id},
                            retryable=False,
                        ),
                        started=started,
                    )
                    return
                saw_tool_call = True
                normalized = normalizer.tool_call_event(tool_call)
                if normalized is not None:
                    yield normalized
                continue
            if event_type is ModelStreamEventType.USAGE:
                usage = getattr(adapter_event, "usage", None)
                if usage is None:
                    yield self._stream_failure(
                        request,
                        plan,
                        normalizer,
                        ModelGatewayError(
                            ModelGatewayErrorCode.STREAM_FAILURE,
                            "provider stream emitted an empty usage event",
                            details={"provider_id": plan.provider.id},
                            retryable=False,
                        ),
                        started=started,
                    )
                    return
                latest_usage = usage
                normalized = normalizer.usage_event(usage)
                if normalized is not None:
                    yield normalized
                continue
            if event_type is ModelStreamEventType.CANCELLED:
                yield self._stream_cancelled(request, plan, normalizer, started=started)
                return
            if event_type is ModelStreamEventType.ERROR:
                error_code = getattr(adapter_event, "error_code", None) or (
                    ModelGatewayErrorCode.STREAM_FAILURE.value
                )
                failure_text = getattr(adapter_event, "failure", None) or (
                    "provider stream failed"
                )
                try:
                    code = ModelGatewayErrorCode(error_code)
                except ValueError:
                    code = ModelGatewayErrorCode.STREAM_FAILURE
                yield self._stream_failure(
                    request,
                    plan,
                    normalizer,
                    ModelGatewayError(
                        code,
                        str(failure_text),
                        details={"provider_id": plan.provider.id},
                        retryable=False,
                    ),
                    started=started,
                )
                return
            if event_type is ModelStreamEventType.COMPLETED:
                provider_response = getattr(adapter_event, "response", None)
                if provider_response is None:
                    yield self._stream_failure(
                        request,
                        plan,
                        normalizer,
                        ModelGatewayError(
                            ModelGatewayErrorCode.STREAM_FAILURE,
                            "provider stream completed without a response",
                            details={"provider_id": plan.provider.id},
                            retryable=False,
                        ),
                        started=started,
                    )
                    return
                try:
                    self._validate_stream_result(
                        request, plan, provider_response, saw_tool_call=saw_tool_call
                    )
                except ModelGatewayError as error:
                    yield self._stream_failure(
                        request, plan, normalizer, error, started=started
                    )
                    return
                response = self._stream_response(
                    request,
                    plan,
                    provider_response,
                    accumulated=accumulated,
                    usage=latest_usage,
                    started=started,
                )
                self._emit(response.facts)  # type: ignore[arg-type]
                terminal = normalizer.completed_event(response)
                if terminal is not None:
                    yield terminal
                return
            # An unknown adapter event type is a boundary failure, never ignored.
            yield self._stream_failure(
                request,
                plan,
                normalizer,
                ModelGatewayError(
                    ModelGatewayErrorCode.STREAM_FAILURE,
                    "provider stream emitted an unknown event type",
                    details={"provider_id": plan.provider.id},
                    retryable=False,
                ),
                started=started,
            )
            return

        yield self._stream_failure(
            request,
            plan,
            normalizer,
            ModelGatewayError(
                ModelGatewayErrorCode.STREAM_FAILURE,
                "provider stream ended without a terminal event",
                details={"provider_id": plan.provider.id},
                retryable=False,
            ),
            started=started,
        )

    def _validate_stream_result(
        self,
        request: ModelGatewayRequest,
        plan: _ExecutionPlan,
        provider_response: ProviderModelResponse,
        *,
        saw_tool_call: bool,
    ) -> None:
        if provider_response.effective_reasoning_effort is not request.reasoning_effort:
            raise ModelGatewayError(
                ModelGatewayErrorCode.PROVIDER_FAILURE,
                "provider adapter changed the requested reasoning effort",
                details={"provider_id": plan.provider.id},
                retryable=False,
            )
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
        if (provider_response.tool_calls or saw_tool_call) and not request.tools:
            raise ModelGatewayError(
                ModelGatewayErrorCode.TOOL_CALL_INVALID,
                "provider returned a tool call that the request never declared",
                details={"provider_id": plan.provider.id},
                retryable=False,
            )

    def _stream_response(
        self,
        request: ModelGatewayRequest,
        plan: _ExecutionPlan,
        provider_response: ProviderModelResponse,
        *,
        accumulated: list[str],
        usage: object | None,
        started: float,
    ) -> ModelGatewayResponse:
        content = provider_response.content
        if not content and accumulated:
            content = "".join(accumulated)
        resolved_usage = self._resolve_usage(
            plan.model,
            usage if usage is not None else provider_response.usage,
        )
        facts = self._facts(
            request,
            plan,
            started=started,
            attempt=1,
            success=True,
            error_code=None,
            finish_reason=provider_response.finish_reason,
            usage=resolved_usage,  # type: ignore[arg-type]
            reasoning_used=provider_response.reasoning_used,
            effective_reasoning_effort=provider_response.effective_reasoning_effort,
            streamed=True,
        )
        return ModelGatewayResponse(
            request_id=request.request_id,
            provider_id=plan.provider.id,
            model_id=plan.model.id,
            selection_mode=request.selection_mode,
            content=content,
            structured_output=provider_response.structured_output,
            tool_calls=provider_response.tool_calls,
            usage=resolved_usage,  # type: ignore[arg-type]
            facts=facts,
            finish_reason=provider_response.finish_reason,
            cancelled=False,
            error_code=None,
            reasoning_used=provider_response.reasoning_used,
            effective_reasoning_effort=provider_response.effective_reasoning_effort,
        )

    def _stream_failure(
        self,
        request: ModelGatewayRequest,
        plan: _ExecutionPlan,
        normalizer: ModelStreamNormalizer,
        error: ModelGatewayError,
        *,
        started: float,
    ) -> ModelStreamEvent:
        facts = self._facts(
            request,
            plan,
            started=started,
            attempt=1,
            success=False,
            error_code=error.code.value,
            finish_reason=None,
            usage=None,
            reasoning_used=False,
            effective_reasoning_effort=request.reasoning_effort,
            streamed=True,
            cancelled=error.code is ModelGatewayErrorCode.MODEL_CALL_CANCELLED,
        )
        self._emit(facts)
        event = normalizer.error_event(error)
        if event is None:
            raise ModelGatewayError(
                ModelGatewayErrorCode.STREAM_FAILURE,
                "stream already reported a terminal event",
                retryable=False,
            )
        return event

    def _stream_cancelled(
        self,
        request: ModelGatewayRequest,
        plan: _ExecutionPlan,
        normalizer: ModelStreamNormalizer,
        *,
        started: float,
    ) -> ModelStreamEvent:
        facts = self._facts(
            request,
            plan,
            started=started,
            attempt=1,
            success=False,
            error_code=None,
            finish_reason=None,
            usage=None,
            reasoning_used=False,
            effective_reasoning_effort=request.reasoning_effort,
            streamed=True,
            cancelled=True,
        )
        self._emit(facts)
        event = normalizer.cancelled_event()
        if event is None:
            raise ModelGatewayError(
                ModelGatewayErrorCode.STREAM_FAILURE,
                "stream already reported a terminal event",
                retryable=False,
            )
        return event

    # ── Authorized fallback mechanics ────────────────────────────────────────

    def _execute_authorized_fallback(
        self,
        request: ModelGatewayRequest,
        plan: _ExecutionPlan,
        primary_error: ModelGatewayError,
        *,
        started: float,
        attempt: int,
        cancellation: ModelCallCancellation | None = None,
    ) -> ModelGatewayResponse:
        """Execute only an explicitly authorized, requirement-preserving fallback.

        Only a retryable transport-level primary failure may lead here; a
        privacy denial, an invalid request, an unsupported capability, a
        cancellation or an incompatible explicit model never falls back.

        Candidate order is exactly the caller's authorized sequence: the
        canonical fallback authority decides *whether* another candidate may be
        attempted and which one, and every candidate must still satisfy
        capabilities, reasoning effort, modalities, tools, structured output,
        context and canonical privacy before its adapter may run.

        A fallback is a continuation of the same model call, never a new one:
        the caller's exact cancellation object stays authoritative across
        planning, preflight, invocation and the returned success, so a cancelled
        call performs no later provider I/O and never reports success.
        """

        self._raise_if_call_cancelled(cancellation)
        requirements = self._requirements(request)
        routing_candidates, unresolved = self._authorized_candidates(request)
        skipped = list(unresolved)
        history: list[ModelFallbackAttempt] = [
            ModelFallbackAttempt(
                attempt_index=1,
                model_id=plan.model.id,
                provider_id=plan.provider.id,
                success=False,
                error_code=primary_error.code.value,
                retryable=primary_error.retryable,
                latency_ms=self._latency_ms(started),
            )
        ]
        last_error = primary_error
        fallback_index = 0

        while routing_candidates:
            self._raise_if_call_cancelled(cancellation)
            try:
                decision = self._fallback_planner.next_selection(  # type: ignore[union-attr]
                    candidates=routing_candidates,
                    attempts=tuple(history),
                    error=last_error,
                    requirements=requirements,
                )
            except Exception as error:
                raise self._failed(
                    request,
                    plan,
                    ModelGatewayError(
                        ModelGatewayErrorCode.FALLBACK_EXHAUSTED,
                        "the authorized fallback sequence could not be planned",
                        details={"provider_id": plan.provider.id},
                        retryable=False,
                    ),
                    started=started,
                    attempt=attempt,
                ) from error

            self._raise_if_call_cancelled(cancellation)
            skipped.extend(
                str(entry)
                for entry in getattr(decision, "skipped_candidates", ()) or ()
            )
            if not self._is_next_candidate_decision(decision):
                break
            selected_model_id = getattr(decision, "selected_model_id", None)
            selected_provider_id = getattr(decision, "selected_provider_id", None)
            if not selected_model_id or not selected_provider_id:
                break

            fallback_index += 1
            self._raise_if_call_cancelled(cancellation)
            try:
                candidate_plan = self._preflight_candidate(
                    request,
                    provider_id=str(selected_provider_id),
                    model_id=str(selected_model_id),
                )
            except ModelGatewayError as error:
                skipped.append(
                    f"{selected_provider_id}:{selected_model_id}:{error.code.value}"
                )
                history.append(
                    ModelFallbackAttempt(
                        attempt_index=len(history) + 1,
                        model_id=str(selected_model_id),
                        provider_id=str(selected_provider_id),
                        success=False,
                        error_code=error.code.value,
                        retryable=error.retryable,
                    )
                )
                last_error = error
                continue

            self._raise_if_call_cancelled(cancellation)
            try:
                provider_response = self._execute_adapter(
                    candidate_plan,
                    self._provider_request(request, candidate_plan),
                    request,
                    cancellation,
                )
            except ModelGatewayError as error:
                last_error = error
                history.append(
                    ModelFallbackAttempt(
                        attempt_index=len(history) + 1,
                        model_id=str(selected_model_id),
                        provider_id=str(selected_provider_id),
                        success=False,
                        error_code=error.code.value,
                        retryable=error.retryable,
                        latency_ms=self._latency_ms(started),
                    )
                )
                self._raise_if_call_cancelled(cancellation)
                if not error.retryable:
                    break
                continue

            self._raise_if_call_cancelled(cancellation)
            return self._succeed(
                request,
                candidate_plan,
                provider_response,
                started=started,
                attempt=1,
                fallback_index=fallback_index,
                fallback_used=True,
                fallback_skipped=tuple(skipped),
            )

        raise self._failed(
            request,
            plan,
            ModelGatewayError(
                ModelGatewayErrorCode.FALLBACK_EXHAUSTED,
                "no authorized fallback candidate could be executed",
                details={
                    "provider_id": plan.provider.id,
                    "last_error_code": last_error.code.value,
                },
                retryable=False,
            ),
            started=started,
            attempt=attempt,
        )

    def _authorized_candidates(
        self,
        request: ModelGatewayRequest,
    ) -> tuple[tuple[RoutingCandidate, ...], tuple[str, ...]]:
        """Resolve the caller's authorized sequence into canonical candidates."""

        candidates: list[RoutingCandidate] = []
        unresolved: list[str] = []
        rank = 1
        for entry in request.fallback_model_ids:
            try:
                model = self._model_catalog.get(entry)
            except ProviderError:
                unresolved.append(f"{entry}:MODEL_NOT_FOUND")
                continue
            candidates.append(
                RoutingCandidate(
                    rank=rank,
                    qualified_model_id=model.qualified_id,
                    provider_id=model.provider_id,
                    model_id=model.id,
                    input_cost_per_million=model.input_cost_per_million,
                    output_cost_per_million=model.output_cost_per_million,
                    context_window=model.context_window,
                )
            )
            rank += 1
        return tuple(candidates), tuple(unresolved)

    @staticmethod
    def _requirements(request: ModelGatewayRequest) -> ModelRequirements:
        """Describe the caller's hard requirements for canonical fallback planning.

        Real egress permission is enforced per candidate by the canonical
        privacy gate, so this never asserts a routing privacy preference the
        gateway does not own.
        """

        effort = request.reasoning_effort
        return ModelRequirements(
            tool_calling=bool(request.tools),
            structured_output=request.structured_output is not None,
            json_schema=(
                request.structured_output is not None
                and request.structured_output.schema is not None
            ),
            vision=request.has_image_input,
            reasoning=effort not in (ReasoningEffort.DEFAULT, ReasoningEffort.NONE),
        )

    @staticmethod
    def _is_next_candidate_decision(decision: object) -> bool:
        action = getattr(decision, "action", None)
        return str(getattr(action, "value", action)) == _NEXT_CANDIDATE_ACTION

    def _latency_ms(self, started: float) -> int:
        return max(int((self._clock() - started) * 1000), 0)

    @staticmethod
    def _raise_if_call_cancelled(
        cancellation: ModelCallCancellation | None,
    ) -> None:
        """Fail with the canonical cancellation outcome when the call is cancelled.

        This is the one cancellation checkpoint used across the whole call
        lifecycle.  It never substitutes, copies or discards the caller's token,
        so cancellation always wins over retry, backoff and fallback recovery.
        """

        if cancellation is not None and cancellation.is_cancelled:
            raise ModelGatewayError(
                ModelGatewayErrorCode.MODEL_CALL_CANCELLED,
                "model call was cancelled",
                retryable=False,
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

    def _preflight(
        self,
        request: ModelGatewayRequest,
        *,
        require_streaming: bool = False,
    ) -> _ExecutionPlan:
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
        return self._plan(request, require_streaming=require_streaming)

    def _preflight_candidate(
        self,
        request: ModelGatewayRequest,
        *,
        provider_id: str,
        model_id: str,
    ) -> _ExecutionPlan:
        """Validate one authorized fallback candidate before its adapter runs."""

        try:
            model = self._model_catalog.get(model_id, provider_id=provider_id)
        except ProviderError as error:
            raise ModelGatewayError(
                ModelGatewayErrorCode.MODEL_NOT_FOUND,
                "the authorized fallback model is not registered",
                details={"model_id": f"{provider_id}:{model_id}"},
                retryable=False,
            ) from error
        return self._plan(request, model)

    def _plan(
        self,
        request: ModelGatewayRequest,
        model: ModelSpec | None = None,
        *,
        require_streaming: bool = False,
    ) -> _ExecutionPlan:
        """Validate one model against the canonical authorities before I/O.

        An explicit model request resolves exactly one canonical model and must
        satisfy every hard gate; an AUTO request resolves through
        :meth:`_resolve_auto_model`, which has already evaluated every hard gate
        for the candidate it selected.
        """

        if model is None:
            return self._resolve_model(request, require_streaming=require_streaming)

        try:
            provider, capability_decision, privacy_decision, adapter = (
                self._candidate_gate(
                    model, request, require_streaming=require_streaming
                )
            )
        except _CandidateHardGateFailure as failure:
            if failure.error is not None:
                raise failure.error
            raise self._availability_gate_error(model, failure.code) from None
        return _ExecutionPlan(
            model=model,
            provider=provider,
            adapter=adapter,
            capability_decision=capability_decision,
            privacy_decision=privacy_decision,
        )

    def _candidate_gate(
        self,
        model: ModelSpec,
        request: ModelGatewayRequest,
        *,
        require_streaming: bool = False,
    ) -> tuple[ProviderSpec, str, str, ModelProviderAdapter]:
        """Evaluate every gateway-owned hard execution gate for one candidate.

        The gates are evaluated in canonical order — provider authority,
        provider/model execution availability, requested reasoning effort,
        required capabilities, input modalities, the streaming requirement,
        adapter availability and finally the canonical privacy decision for this
        candidate's own provider — so a candidate is never selected without an
        executable adapter and a real egress decision.

        A candidate-local failure raises :class:`_CandidateHardGateFailure`.
        Anything else (a malformed request-level failure, an internal invariant
        violation or an unusable privacy authority) propagates unchanged and
        stays terminal.
        """

        if not self._model_catalog.is_bound_to_current_provider(model):
            raise _CandidateHardGateFailure(ModelGatewayErrorCode.MODEL_UNAVAILABLE)
        provider = self._resolve_provider(model)
        if provider is None:
            raise _CandidateHardGateFailure(
                ModelGatewayErrorCode.PROVIDER_NOT_AVAILABLE
            )
        if not provider.enabled or provider.availability in _UNAVAILABLE_AVAILABILITY:
            raise _CandidateHardGateFailure(
                ModelGatewayErrorCode.PROVIDER_NOT_AVAILABLE
            )
        if model.availability in _UNAVAILABLE_AVAILABILITY:
            raise _CandidateHardGateFailure(ModelGatewayErrorCode.MODEL_UNAVAILABLE)

        try:
            capability_decision = self._validate_capabilities(request, model)
            if require_streaming and not model.capabilities.streaming:
                raise ModelGatewayError(
                    ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED,
                    "the model does not declare provider token streaming support",
                    details={"model_id": model.qualified_id},
                    retryable=False,
                )
            self._validate_modalities(request, model)
        except ModelGatewayError as error:
            raise _CandidateHardGateFailure(error.code, error) from None

        if not self._adapter_registry.has(model.provider_id):
            raise _CandidateHardGateFailure(
                ModelGatewayErrorCode.PROVIDER_NOT_AVAILABLE
            )
        adapter = self._adapter_registry.get(model.provider_id)

        try:
            privacy_decision = self._privacy_decision(request, provider)
        except ModelGatewayError as error:
            if error.code is not ModelGatewayErrorCode.PRIVACY_DENIED:
                raise
            # The call-level egress prerequisites are enforced once for the whole
            # candidate set (``_require_egress_authority``), so a denial here is
            # this candidate's own canonical privacy policy refusing egress: it
            # is candidate-local and never terminal, and AUTO may continue.
            raise _CandidateHardGateFailure(error.code, error) from None
        return provider, capability_decision, privacy_decision, adapter

    @staticmethod
    def _availability_gate_error(
        model: ModelSpec,
        code: ModelGatewayErrorCode,
    ) -> ModelGatewayError:
        """Build the safe terminal error for a provider/model availability gate.

        These two gates are modelled without an explicit error object, so the
        explicit-model wording they must keep is reconstructed here.  Every other
        gate carries and re-raises its own original error unchanged.
        """

        if code is ModelGatewayErrorCode.MODEL_UNAVAILABLE:
            return ModelGatewayError(
                code,
                "the model is not available for execution",
                details={"model_id": model.qualified_id},
                retryable=False,
            )
        return ModelGatewayError(
            code,
            "the provider is not available for execution",
            details={"provider_id": model.provider_id},
            retryable=False,
        )

    def _resolve_model(
        self,
        request: ModelGatewayRequest,
        *,
        require_streaming: bool = False,
    ) -> _ExecutionPlan:
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
            return self._plan(request, model, require_streaming=require_streaming)
        return self._resolve_auto_model(request, require_streaming=require_streaming)

    def _resolve_auto_model(
        self,
        request: ModelGatewayRequest,
        *,
        require_streaming: bool = False,
    ) -> _ExecutionPlan:
        """Resolve an AUTO request through the canonical selection path only.

        Candidate ordering is exactly the canonical model-selection ranking; the
        gateway adds no scoring, cost optimization, preference learning or
        provider ranking of its own.  It evaluates each canonical candidate in
        order against its own hard execution gates — reasoning effort,
        capabilities, modalities, streaming, provider/model availability,
        adapter availability and canonical privacy for that candidate's provider
        — returns the first executable candidate, and continues to the next
        canonical candidate when one fails locally.  It fails closed, with the
        most specific safe canonical error, when nothing is executable.
        """

        matches = find_matching_models(
            self._model_catalog,
            self._provider_registry,
            self._requirements(request),
        )
        self._require_egress_authority(matches, request)
        failure_codes: list[ModelGatewayErrorCode] = []
        for model in matches:
            try:
                provider, capability_decision, privacy_decision, adapter = (
                    self._candidate_gate(
                        model, request, require_streaming=require_streaming
                    )
                )
            except _CandidateHardGateFailure as failure:
                failure_codes.append(failure.code)
                continue
            return _ExecutionPlan(
                model=model,
                provider=provider,
                adapter=adapter,
                capability_decision=capability_decision,
                privacy_decision=privacy_decision,
            )
        raise self._auto_exhausted(request, matches, failure_codes)

    def _require_egress_authority(
        self,
        matches: tuple[ModelSpec, ...],
        request: ModelGatewayRequest,
    ) -> None:
        """Fail a request-level egress-prerequisite failure before AUTO iteration.

        A candidate that a *policy* denies is candidate-local and is skipped, but
        a call that has no canonical privacy authority at all is a malformed
        request-level failure: it is terminal and must not be answered by
        silently evaluating a later candidate.  Applying the same prerequisites
        up front also preserves the explicit-model error semantics for an AUTO
        request whose only candidates are remote.
        """

        references_remote = any(
            (provider := self._resolve_provider(model)) is not None
            and provider.provider_type == "remote"
            for model in matches
        )
        if not references_remote:
            return
        if self._privacy_gate is None:
            raise ModelGatewayError(
                ModelGatewayErrorCode.PRIVACY_DENIED,
                "no canonical privacy authority is configured for remote egress",
                details={"selection_mode": request.selection_mode.value},
                retryable=False,
            )
        if request.privacy is None:
            raise ModelGatewayError(
                ModelGatewayErrorCode.PRIVACY_DENIED,
                "remote transmission requires canonical privacy metadata",
                details={"selection_mode": request.selection_mode.value},
                retryable=False,
            )

    @staticmethod
    def _auto_exhausted(
        request: ModelGatewayRequest,
        matches: tuple[ModelSpec, ...],
        failure_codes: Iterable[ModelGatewayErrorCode],
    ) -> ModelGatewayError:
        """Return the deterministic, safe failure for an exhausted AUTO search.

        Nothing sensitive is exposed: only canonical candidate count and the
        most specific safe failure code the gateway produced while iterating.
        """

        codes = tuple(failure_codes)
        for candidate_code in (
            ModelGatewayErrorCode.UNSUPPORTED_REASONING_EFFORT,
            ModelGatewayErrorCode.INPUT_MODALITY_UNSUPPORTED,
            ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED,
            ModelGatewayErrorCode.PRIVACY_DENIED,
        ):
            if candidate_code in codes:
                code = candidate_code
                break
        else:
            code = ModelGatewayErrorCode.MODEL_NOT_FOUND
        return ModelGatewayError(
            code,
            "no canonical model satisfies the requested requirements",
            details={
                "selection_mode": request.selection_mode.value,
                "candidates_considered": len(matches),
            },
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

    @staticmethod
    def _resolve_usage(model: ModelSpec, usage: ModelUsage) -> ModelUsage:
        """Add a deterministic catalog-derived cost when no cost was reported."""

        if usage.cost is not None or usage.cost_source is not None:
            return usage
        derived = derive_model_call_cost(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_tokens=usage.cached_tokens,
            input_cost_per_million=model.input_cost_per_million,
            output_cost_per_million=model.output_cost_per_million,
            cached_input_cost_per_million=model.cached_input_cost_per_million,
        )
        if derived is None:
            return usage
        return replace(usage, cost=derived, cost_source="catalog_derived")

    def _succeed(
        self,
        request: ModelGatewayRequest,
        plan: _ExecutionPlan,
        provider_response: ProviderModelResponse,
        *,
        started: float,
        attempt: int,
        fallback_index: int = 0,
        fallback_used: bool = False,
        fallback_skipped: tuple[str, ...] = (),
    ) -> ModelGatewayResponse:
        usage = self._resolve_usage(plan.model, provider_response.usage)
        facts = self._facts(
            request,
            plan,
            started=started,
            attempt=attempt,
            success=True,
            fallback_index=fallback_index,
            fallback_used=fallback_used,
            fallback_skipped=fallback_skipped,
            error_code=None,
            finish_reason=provider_response.finish_reason,
            usage=usage,
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
            usage=usage,
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
        streamed: bool = False,
        cancelled: bool | None = None,
        fallback_index: int = 0,
        fallback_used: bool = False,
        fallback_skipped: tuple[str, ...] = (),
    ) -> ModelExecutionFacts:
        latency_ms = self._latency_ms(started)
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
            streamed=streamed,
            cancelled=(
                error_code == ModelGatewayErrorCode.MODEL_CALL_CANCELLED.value
                if cancelled is None
                else cancelled
            ),
            timed_out=error_code == ModelGatewayErrorCode.PROVIDER_TIMEOUT.value,
            retry_count=max(attempt - 1, 0),
            fallback_index=fallback_index,
            fallback_used=fallback_used,
            fallback_skipped=fallback_skipped,
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
