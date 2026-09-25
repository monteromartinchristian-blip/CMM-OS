"""Phase 11.21 — safe fallback mechanics tests.

Phase 11.21 executes an already-authorized fallback sequence; it never invents
routing policy.  Only a retryable transport-level primary failure may lead to a
fallback, every candidate must still satisfy capabilities, reasoning effort,
modalities, tools, structured output, context and canonical privacy before its
adapter may run, and a candidate may never relax a failed requirement.
"""

from __future__ import annotations

import hashlib

import pytest

from cmm.agent_runtime.model_egress_privacy_adapter import CanonicalPrivacyEgressGate
from cmm.agent_runtime.model_fallback_contracts import ModelFallbackPolicy
from cmm.agent_runtime.model_fallback_gateway_adapter import (
    ModelGatewayFallbackPlanner,
)
from cmm.cognitive.privacy import PrivacyMetadata, PrivacyPolicy
from kernel.llm.capabilities import ModelCapabilities, ReasoningEffort
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_gateway_contracts import (
    ModelGatewayRequest,
    ModelGatewayRetryPolicy,
    ModelInputPart,
    ModelToolDefinition,
    ModelUsage,
    StructuredOutputRequirement,
)
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.model_provider_adapter import InMemoryModelProviderAdapter
from kernel.llm.model_streaming import ModelCallCancellation
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec
from tests.llm.model_gateway_support import (
    MULTIMODAL,
    PNG_BYTES,
    CanonicalGraph,
    build_runtime,
)

LOCAL_ONLY = PrivacyMetadata(policy=PrivacyPolicy.LOCAL_ONLY)


def _planner(**overrides: object) -> ModelGatewayFallbackPlanner:
    return ModelGatewayFallbackPlanner(**overrides)  # type: ignore[arg-type]


class _FallbackRuntime:
    """A gateway with a primary model and an authorized fallback chain."""

    def __init__(
        self,
        *,
        primary_capabilities: ModelCapabilities,
        fallback_capabilities: ModelCapabilities,
        second_fallback_capabilities: ModelCapabilities | None = None,
        fallback_provider_type: str = "local",
        privacy_gate: object | None = None,
        include_planner: bool = True,
        policy: ModelFallbackPolicy | None = None,
        reasoning_effort_map: dict[ReasoningEffort, str] | None = None,
    ) -> None:
        providers = ProviderRegistry()
        providers.register(
            ProviderSpec(
                id="local",
                provider_type="local",
                api_style="chat_completions",
                availability="available",
            )
        )
        providers.register(
            ProviderSpec(
                id="fallback-a",
                provider_type=fallback_provider_type,  # type: ignore[arg-type]
                api_style="chat_completions",
                base_url="https://fallback-a.example/v1",
                availability="available",
            )
        )
        providers.register(
            ProviderSpec(
                id="fallback-b",
                provider_type="local",
                api_style="chat_completions",
                availability="available",
            )
        )
        graph = CanonicalGraph(providers=providers, models=ModelCatalog(providers))
        graph.models.register(
            ModelSpec(
                id="primary",
                provider_id="local",
                context_window=32768,
                capabilities=primary_capabilities,
                availability="available",
            )
        )
        graph.models.register(
            ModelSpec(
                id="secondary",
                provider_id="fallback-a",
                context_window=32768,
                capabilities=fallback_capabilities,
                availability="available",
            )
        )
        self.adapters = {
            "local": InMemoryModelProviderAdapter(
                "local", reasoning_effort_map=reasoning_effort_map
            ),
            "fallback-a": InMemoryModelProviderAdapter(
                "fallback-a", reasoning_effort_map=reasoning_effort_map
            ),
        }
        if second_fallback_capabilities is not None:
            graph.models.register(
                ModelSpec(
                    id="tertiary",
                    provider_id="fallback-b",
                    context_window=32768,
                    capabilities=second_fallback_capabilities,
                    availability="available",
                )
            )
            self.adapters["fallback-b"] = InMemoryModelProviderAdapter(
                "fallback-b", reasoning_effort_map=reasoning_effort_map
            )
        self.runtime = build_runtime(
            graph=graph,
            register_model=False,
            provider_id="local",
            adapters=tuple(self.adapters.values()),
            privacy_gate=privacy_gate,
            fallback_planner=_planner(policy=policy) if include_planner else None,
        )

    @property
    def gateway(self):
        return self.runtime.gateway

    @property
    def sink(self):
        return self.runtime.sink

    def adapter(self, provider_id: str) -> InMemoryModelProviderAdapter:
        return self.adapters[provider_id]


def _request(**overrides: object) -> ModelGatewayRequest:
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "model_id": "local:primary",
        "input_parts": (ModelInputPart.text_part("answer"),),
        "fallback_model_ids": ("fallback-a:secondary",),
    }
    values.update(overrides)
    return ModelGatewayRequest(**values)  # type: ignore[arg-type]


def _transient(adapter: InMemoryModelProviderAdapter) -> None:
    adapter.add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE,
        "transient upstream error",
        retryable=True,
    )


# ── Successful authorized fallback ──────────────────────────────────────────


def test_transient_primary_failure_falls_back_to_an_authorized_candidate() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL, fallback_capabilities=MULTIMODAL
    )
    _transient(runtime.adapter("local"))
    runtime.adapter("fallback-a").add_response(content="fallback answer")

    response = runtime.gateway.execute(_request())

    assert response.content == "fallback answer"
    assert response.provider_id == "fallback-a"
    assert response.model_id == "secondary"
    assert runtime.adapter("local").call_count == 1
    assert runtime.adapter("fallback-a").call_count == 1
    assert response.facts is not None
    assert response.facts.fallback_used is True
    assert response.facts.fallback_index == 1
    assert response.facts.success is True


def test_the_fallback_preserves_every_request_requirement() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL,
        fallback_capabilities=MULTIMODAL,
        reasoning_effort_map={ReasoningEffort.HIGH: "thinking_budget_high"},
    )
    _transient(runtime.adapter("local"))
    runtime.adapter("fallback-a").add_response(
        structured_output={"answer": "a"},
        tool_calls=(),
    )
    requirement = StructuredOutputRequirement(schema={"type": "object"})
    tool = ModelToolDefinition(tool_id="t1")

    runtime.gateway.execute(
        _request(
            reasoning_effort=ReasoningEffort.HIGH,
            required_capabilities=("vision", "tool_calling"),
            tools=(tool,),
            structured_output=requirement,
            input_parts=(
                ModelInputPart.text_part("describe"),
                ModelInputPart.image_part(PNG_BYTES, "image/png"),
            ),
        )
    )

    primary = runtime.adapter("local").requests[0]
    fallback = runtime.adapter("fallback-a").requests[0]
    assert fallback.reasoning_effort is ReasoningEffort.HIGH
    assert fallback.tools == primary.tools
    assert fallback.structured_output == primary.structured_output
    assert [part.content_digest for part in fallback.input_parts] == [
        part.content_digest for part in primary.input_parts
    ]
    assert fallback.input_parts[1].content == PNG_BYTES


def test_the_fallback_receives_real_attachment_content() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL, fallback_capabilities=MULTIMODAL
    )
    _transient(runtime.adapter("local"))
    runtime.adapter("fallback-a").add_response(content="ok")

    runtime.gateway.execute(
        _request(
            input_parts=(
                ModelInputPart.text_part("classify"),
                ModelInputPart.image_part(PNG_BYTES, "image/png"),
            )
        )
    )

    fingerprints = runtime.adapter("fallback-a").received_input_fingerprints[0]
    assert fingerprints[1] == (
        "image",
        len(PNG_BYTES),
        hashlib.sha256(PNG_BYTES).hexdigest(),
    )


def test_fallback_skipped_candidates_are_recorded_safely() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL, fallback_capabilities=MULTIMODAL
    )
    _transient(runtime.adapter("local"))
    runtime.adapter("fallback-a").add_response(content="ok")

    response = runtime.gateway.execute(
        _request(fallback_model_ids=("fallback-z:missing", "fallback-a:secondary"))
    )

    assert response.facts is not None
    assert any("missing" in entry for entry in response.facts.fallback_skipped)


# ── Incompatible fallbacks never execute ────────────────────────────────────


def test_an_incompatible_fallback_is_not_executed() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=ModelCapabilities(vision=True),
        fallback_capabilities=ModelCapabilities(),
    )
    _transient(runtime.adapter("local"))

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(
                input_parts=(
                    ModelInputPart.text_part("classify"),
                    ModelInputPart.image_part(PNG_BYTES, "image/png"),
                )
            )
        )

    assert error.value.code is ModelGatewayErrorCode.FALLBACK_EXHAUSTED
    assert runtime.adapter("fallback-a").call_count == 0


def test_a_fallback_lacking_the_requested_effort_is_rejected() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=ModelCapabilities(
            reasoning=True, reasoning_efforts=(ReasoningEffort.HIGH,)
        ),
        fallback_capabilities=ModelCapabilities(reasoning=True),
        reasoning_effort_map={ReasoningEffort.HIGH: "thinking_budget_high"},
    )
    _transient(runtime.adapter("local"))

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(reasoning_effort=ReasoningEffort.HIGH))

    assert error.value.code is ModelGatewayErrorCode.FALLBACK_EXHAUSTED
    assert runtime.adapter("fallback-a").call_count == 0


def test_a_fallback_missing_structured_output_support_is_rejected() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=ModelCapabilities(structured_output=True),
        fallback_capabilities=ModelCapabilities(),
    )
    _transient(runtime.adapter("local"))

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(structured_output=StructuredOutputRequirement())
        )

    assert error.value.code is ModelGatewayErrorCode.FALLBACK_EXHAUSTED
    assert runtime.adapter("fallback-a").call_count == 0


def test_a_remote_fallback_is_blocked_under_local_only() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL,
        fallback_capabilities=MULTIMODAL,
        fallback_provider_type="remote",
        privacy_gate=CanonicalPrivacyEgressGate(),
    )
    _transient(runtime.adapter("local"))
    runtime.adapter("fallback-a").add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(privacy=LOCAL_ONLY))

    assert error.value.code is ModelGatewayErrorCode.FALLBACK_EXHAUSTED
    assert runtime.adapter("local").call_count == 1
    assert runtime.adapter("fallback-a").call_count == 0


def test_an_unregistered_fallback_entry_exhausts_the_sequence() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL, fallback_capabilities=MULTIMODAL
    )
    _transient(runtime.adapter("local"))

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(fallback_model_ids=("local:nope",)))

    assert error.value.code is ModelGatewayErrorCode.FALLBACK_EXHAUSTED
    assert error.value.retryable is False
    assert runtime.adapter("local").call_count == 1


def test_a_failing_fallback_chain_exhausts_within_the_bound() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL,
        fallback_capabilities=MULTIMODAL,
        second_fallback_capabilities=MULTIMODAL,
        policy=ModelFallbackPolicy(maximum_attempts=3, maximum_attempts_per_model=1),
    )
    _transient(runtime.adapter("local"))
    _transient(runtime.adapter("fallback-a"))
    _transient(runtime.adapter("fallback-b"))

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(
                fallback_model_ids=("fallback-a:secondary", "fallback-b:tertiary"),
            )
        )

    assert error.value.code is ModelGatewayErrorCode.FALLBACK_EXHAUSTED
    assert runtime.adapter("local").call_count == 1
    assert runtime.adapter("fallback-a").call_count == 1
    assert runtime.adapter("fallback-b").call_count == 1


def test_a_permanent_fallback_failure_stops_the_sequence() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL,
        fallback_capabilities=MULTIMODAL,
        second_fallback_capabilities=MULTIMODAL,
    )
    _transient(runtime.adapter("local"))
    runtime.adapter("fallback-a").add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE,
        "permanent auth failure",
        retryable=False,
    )

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(fallback_model_ids=("fallback-a:secondary", "fallback-b:tertiary"))
        )

    assert error.value.code is ModelGatewayErrorCode.FALLBACK_EXHAUSTED
    assert runtime.adapter("fallback-b").call_count == 0


# ── Fallback never widens authority ─────────────────────────────────────────


def test_no_authorized_candidate_keeps_the_primary_error() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL, fallback_capabilities=MULTIMODAL
    )
    _transient(runtime.adapter("local"))

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(fallback_model_ids=()))

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_FAILURE
    assert runtime.adapter("fallback-a").call_count == 0


def test_a_non_retryable_primary_failure_never_falls_back() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL, fallback_capabilities=MULTIMODAL
    )
    runtime.adapter("local").add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE,
        "permanent upstream failure",
        retryable=False,
    )

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request())

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_FAILURE
    assert runtime.adapter("fallback-a").call_count == 0


def test_a_privacy_denial_never_falls_back() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL,
        fallback_capabilities=MULTIMODAL,
        fallback_provider_type="remote",
        privacy_gate=CanonicalPrivacyEgressGate(),
    )
    runtime.adapter("local").add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(privacy=LOCAL_ONLY, model_id="fallback-a:secondary")
        )

    assert error.value.code is ModelGatewayErrorCode.PRIVACY_DENIED
    assert runtime.adapter("local").call_count == 0
    assert runtime.adapter("fallback-a").call_count == 0


def test_authorization_without_a_canonical_planner_never_substitutes() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL,
        fallback_capabilities=MULTIMODAL,
        include_planner=False,
    )
    _transient(runtime.adapter("local"))

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request())

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_FAILURE
    assert runtime.adapter("fallback-a").call_count == 0


def test_gateway_rejects_a_foreign_fallback_planner() -> None:
    with pytest.raises(TypeError):
        build_runtime(fallback_planner=object())


def test_fallback_usage_is_reported_from_the_executing_provider() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL, fallback_capabilities=MULTIMODAL
    )
    _transient(runtime.adapter("local"))
    runtime.adapter("fallback-a").add_response(
        content="ok", usage=ModelUsage(input_tokens=9, output_tokens=4)
    )

    response = runtime.gateway.execute(_request())

    assert response.usage.input_tokens == 9
    assert response.usage.output_tokens == 4


# ── Remediation V1 MAJOR-02 — one cancellation token belongs to the whole call.
#
# The exact caller token must stay authoritative across primary execution,
# transport retry, retry backoff, fallback planning, fallback candidate
# preflight and fallback execution.  Cancellation beats every recovery path, so
# a cancelled call ends with MODEL_CALL_CANCELLED and performs no later provider
# I/O.


class _RecordingAdapter:
    """Delegate to a real in-memory adapter while recording the token identity."""

    def __init__(self, delegate: InMemoryModelProviderAdapter) -> None:
        self._delegate = delegate
        self.seen: list[object | None] = []

    @property
    def provider_id(self) -> str:
        return self._delegate.provider_id

    @property
    def supports_streaming(self) -> bool:
        return False

    def execute(self, request, *, cancellation: object | None = None):
        self.seen.append(cancellation)
        return self._delegate.execute(request, cancellation=cancellation)

    def stream(self, request, *, cancellation: object | None = None):
        raise AssertionError("streaming is not used by these tests")


def _composed_runtime(
    *,
    primary_adapter,
    cancellation: ModelCallCancellation | None = None,
    retry_policy: ModelGatewayRetryPolicy | None = None,
    planner: object | None = None,
) -> _FallbackRuntime:
    """Compose the fallback runtime around an instrumented primary adapter."""

    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL,
        fallback_capabilities=MULTIMODAL,
    )
    runtime.adapters["local"] = primary_adapter  # type: ignore[assignment]
    runtime.runtime = build_runtime(
        graph=runtime.runtime.graph,
        register_model=False,
        provider_id="local",
        adapters=tuple(runtime.adapters.values()),
        fallback_planner=planner if planner is not None else _planner(),
        **(
            {"retry_policy": retry_policy}
            if retry_policy is not None
            else {}
        ),  # type: ignore[arg-type]
    )
    return runtime


class _CancellingAdapter(_RecordingAdapter):
    """Cancel the shared token, then fail retryably (or delegate a response)."""

    def __init__(
        self,
        delegate: InMemoryModelProviderAdapter,
        *,
        cancel: ModelCallCancellation,
        failure_code: ModelGatewayErrorCode | None,
        retryable: bool,
    ) -> None:
        super().__init__(delegate)
        self._cancel = cancel
        self._failure_code = failure_code
        self._retryable = retryable

    def execute(self, request, *, cancellation: object | None = None):
        self.seen.append(cancellation)
        self._cancel.cancel("primary cancelled the call")
        if self._failure_code is not None:
            raise ModelGatewayError(
                self._failure_code,
                "primary failed after cancelling",
                details={"provider_id": self.provider_id},
                retryable=self._retryable,
            )
        return self._delegate.execute(request, cancellation=cancellation)


def test_a_cancelled_primary_never_executes_an_authorized_fallback() -> None:
    cancellation = ModelCallCancellation()
    delegate = InMemoryModelProviderAdapter("local")
    primary = _CancellingAdapter(
        delegate,
        cancel=cancellation,
        failure_code=ModelGatewayErrorCode.PROVIDER_FAILURE,
        retryable=True,
    )
    runtime = _composed_runtime(primary_adapter=primary)
    runtime.adapter("fallback-a").add_response(content="must never run")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(), cancellation=cancellation)

    assert error.value.code is ModelGatewayErrorCode.MODEL_CALL_CANCELLED
    assert error.value.retryable is False
    assert cancellation.is_cancelled is True
    assert runtime.adapter("fallback-a").call_count == 0
    assert delegate.call_count == 1
    assert primary.seen == [cancellation]


def test_cancellation_during_retry_backoff_stops_the_next_attempt() -> None:
    cancellation = ModelCallCancellation()
    delegate = InMemoryModelProviderAdapter("local")
    primary = _CancellingAdapter(
        delegate,
        cancel=cancellation,
        failure_code=ModelGatewayErrorCode.PROVIDER_FAILURE,
        retryable=True,
    )
    runtime = _composed_runtime(
        primary_adapter=primary,
        retry_policy=ModelGatewayRetryPolicy(max_attempts=3, backoff_seconds=0.0),
    )

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(), cancellation=cancellation)

    assert error.value.code is ModelGatewayErrorCode.MODEL_CALL_CANCELLED
    # Exactly one primary attempt: cancellation observed after the retryable
    # failure prevents both the retry and the fallback.
    assert delegate.call_count == 1
    assert primary.seen == [cancellation]
    assert runtime.adapter("fallback-a").call_count == 0


def test_cancellation_before_fallback_preflight_stops_fallback_io() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL,
        fallback_capabilities=MULTIMODAL,
    )
    cancellation = ModelCallCancellation()
    _transient(runtime.adapter("local"))
    cancellation.cancel("user cancelled before fallback planning")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(), cancellation=cancellation)

    assert error.value.code is ModelGatewayErrorCode.MODEL_CALL_CANCELLED
    assert runtime.adapter("local").call_count == 0
    assert runtime.adapter("fallback-a").call_count == 0


def test_a_cancelled_request_never_reaches_primary_provider_io() -> None:
    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL,
        fallback_capabilities=MULTIMODAL,
    )
    cancellation = ModelCallCancellation()
    _transient(runtime.adapter("local"))
    cancellation.cancel("stop before primary")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(), cancellation=cancellation)

    assert error.value.code is ModelGatewayErrorCode.MODEL_CALL_CANCELLED
    assert runtime.adapter("local").call_count == 0
    assert runtime.adapter("fallback-a").call_count == 0


def test_cancellation_during_fallback_planning_stops_before_invocation() -> None:
    """Cancellation observed while planning still blocks fallback adapter I/O."""

    cancellation = ModelCallCancellation()
    delegate = InMemoryModelProviderAdapter("local")
    _transient(delegate)

    class _CancellingPlanner:
        """Cancel the shared token while the canonical planner is deciding."""

        def __init__(self, delegate: object) -> None:
            self._delegate = delegate

        def next_selection(self, **kwargs: object):
            decision = self._delegate.next_selection(**kwargs)  # type: ignore[attr-defined]
            cancellation.cancel("cancelled during fallback planning")
            return decision

    runtime = _composed_runtime(
        primary_adapter=delegate,
        planner=_CancellingPlanner(_planner()),
    )
    runtime.adapter("fallback-a").add_response(content="must never run")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(), cancellation=cancellation)

    assert error.value.code is ModelGatewayErrorCode.MODEL_CALL_CANCELLED
    assert runtime.adapter("fallback-a").call_count == 0


def test_the_fallback_plumbing_receives_the_exact_cancellation_object() -> None:
    """The same token object reaches every attempt, never ``None`` or a copy."""

    runtime = _FallbackRuntime(
        primary_capabilities=MULTIMODAL,
        fallback_capabilities=MULTIMODAL,
    )
    cancellation = ModelCallCancellation()
    _transient(runtime.adapter("local"))
    primary = _RecordingAdapter(runtime.adapter("local"))
    secondary = _RecordingAdapter(runtime.adapter("fallback-a"))
    runtime.adapters["local"] = primary  # type: ignore[assignment]
    runtime.adapters["fallback-a"] = secondary  # type: ignore[assignment]
    secondary._delegate.add_response(content="fallback answer")
    runtime.runtime = build_runtime(
        graph=runtime.runtime.graph,
        register_model=False,
        provider_id="local",
        adapters=tuple(runtime.adapters.values()),
        fallback_planner=_planner(),
    )

    response = runtime.gateway.execute(_request(), cancellation=cancellation)

    assert response.content == "fallback answer"
    assert primary.seen == [cancellation]
    assert secondary.seen == [cancellation]
