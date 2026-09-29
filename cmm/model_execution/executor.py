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

The Wave E chat surface lives on this same seam — a normalized catalog
projection, AUTO/explicit chat-model resolution through the canonical router and
catalog, and token streaming through the canonical provider abstraction.  It
adds no parallel authority: the same injected ``ModelRouter``,
``ProviderRegistry``, ``ModelCatalog`` and ``ProviderFactory`` answer for it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from threading import Event
from typing import Any

from cmm.model_execution.contracts import (
    ChatStreamFacts,
    ModelExecutionErrorCode,
    ModelExecutionFailure,
    ModelExecutionParameters,
    ModelExecutionRequest,
    ModelExecutionResult,
    NormalizedModel,
    ResolvedChatModel,
)
from cmm.model_execution.errors import ModelExecutionError
from cmm.model_execution.lanes import lane_locality
from cmm.orchestration.contracts import ExecutionRoute
from kernel.llm.capabilities import ReasoningEffort
from kernel.llm.exceptions import ProviderError, ProviderTimeoutError
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_router import ModelRouter, RoutingDecision
from kernel.llm.model_selection import ModelRequirements
from kernel.llm.models import ChatTurn, ImageInput, LLMRequest, LLMResponse
from kernel.llm.provider import LLMProvider
from kernel.llm.provider_factory import ProviderFactory
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

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
NO_MODELS_AVAILABLE_MESSAGE = "No canonical model is currently available"
CHAT_PROMPT_INVALID_MESSAGE = "A chat request requires a non-empty prompt"

#: Safe normalized codes of the chat surface's fail-closed defects.  They extend
#: the :class:`ModelExecutionErrorCode` vocabulary only for conditions the
#: result-shaped error enum does not describe (chat resolution raises, it does
#: not return a result).
NO_MODELS_AVAILABLE_CODE = "NO_MODELS_AVAILABLE"
CHAT_PROMPT_INVALID_CODE = "CHAT_PROMPT_INVALID"

UNSUPPORTED_REASONING_EFFORT_MESSAGE = (
    "The selected model does not support that reasoning effort"
)
UNSUPPORTED_REASONING_EFFORT_CODE = "UNSUPPORTED_REASONING_EFFORT"

PROVIDER_TIMEOUT_MESSAGE = "The model runtime took too long to answer."
PROVIDER_TIMEOUT_CODE = "PROVIDER_TIMEOUT"


def _normalized_effort(effort: ReasoningEffort | str) -> ReasoningEffort:
    """Return the canonical effort level, refusing invented values."""

    try:
        return ReasoningEffort(effort)
    except ValueError as error:
        raise ModelExecutionError(
            UNSUPPORTED_REASONING_EFFORT_MESSAGE,
            code=UNSUPPORTED_REASONING_EFFORT_CODE,
        ) from error

#: The selection values that mean "let the canonical router choose".
AUTO_SELECTION_VALUES = frozenset({"", "cmm-auto", "auto"})
AUTO_POLICY = "cmm-auto"
EXPLICIT_POLICY = "explicit"

#: Catalog and registry states that make a model unroutable right now.  The
#: sets mirror the canonical router's own rejection conditions.
UNAVAILABLE_MODEL_STATES = frozenset({"unavailable", "disabled"})
UNAVAILABLE_PROVIDER_STATES = frozenset({"unavailable", "disabled"})

#: The capability flags projected for a chat model selector, provider-free.
CHAT_CAPABILITY_FIELDS = ("reasoning", "vision", "tool_calling", "structured_output")


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


def model_status(spec: ModelSpec, provider: ProviderSpec, available: bool) -> str:
    """Why a model is in the state it is in.

    ``availability`` is the coarse answer a client gates selection on; this is
    the reason behind it.  A model whose runtime is temporarily down must not
    be indistinguishable from one that was never discovered, and neither may be
    silently presented as usable — the distinction is what lets a selector keep
    a local model visible across a restart without claiming it works.
    """

    if not available:
        if spec.availability == "disabled" or provider.availability == "disabled":
            return "disabled"
        if spec.availability == "unavailable" or provider.availability == "unavailable":
            return "offline"
        if spec.availability == "degraded" or provider.availability == "degraded":
            return "degraded"
        return "unavailable"
    if spec.availability == "unknown" and provider.availability == "unknown":
        # Nothing has ever probed this lane, so "available" is an assumption
        # rather than an observation.  Say so instead of asserting health.
        return "starting"
    return "available"


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

    # ── Chat surface: catalog / resolution / streaming ───────────────────────

    def catalog(self) -> tuple[NormalizedModel, ...]:
        """Project the canonical catalog as provider-free, selectable models.

        A model is listed exactly when its current canonical provider is
        registered and enabled; a model whose catalog or provider state makes it
        unroutable right now is reported as *unavailable* instead of being
        hidden, so a selector can show it honestly.
        """

        projected: list[NormalizedModel] = []
        for spec in self._model_catalog.list():
            provider = self._current_provider(spec.provider_id)
            if provider is None or not provider.enabled:
                continue
            projected.append(self._normalized_model(spec, provider))
        return tuple(projected)

    def resolve_chat(self, selection: str | None = None) -> ResolvedChatModel:
        """Resolve one chat-model selection against the canonical authorities.

        ``None``, ``"cmm-auto"`` and ``"auto"`` delegate to the canonical
        ``ModelRouter``; any other value is an explicit selection resolved by
        qualified id, alias or bare model id through the canonical
        ``ModelCatalog``.  A failure is a :class:`ModelExecutionError` whose
        message is a constant — the selection text never reaches it.
        """

        normalized = (selection or "").strip().lower()
        if normalized in AUTO_SELECTION_VALUES:
            return self._resolve_auto()
        return self._resolve_explicit(normalized)

    def stream(
        self,
        resolved: ResolvedChatModel,
        *,
        prompt: str,
        system: str | None = None,
        history: Sequence[tuple[str, str]] = (),
        images: Sequence[ImageInput] = (),
        cancel_event: Event | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        reasoning_effort: ReasoningEffort | str = ReasoningEffort.DEFAULT,
        facts_sink: Callable[[ChatStreamFacts], None] | None = None,
    ) -> Iterator[str]:
        """Stream normalized content deltas for one resolved chat model.

        Caller defects (a bad ``ResolvedChatModel``, blank prompt or malformed
        history) raise at call time; every provider and transport defect is
        normalized to a secret-free :class:`ModelExecutionError`.  A reasoning
        effort the model does not declare, or the provider cannot put on the
        wire, is refused before any provider call — never silently dropped.
        """

        if not isinstance(resolved, ResolvedChatModel):
            raise TypeError(
                f"resolved must be a ResolvedChatModel, got {type(resolved).__name__}"
            )
        if not isinstance(prompt, str) or not prompt.strip():
            raise ModelExecutionError(
                CHAT_PROMPT_INVALID_MESSAGE, code=CHAT_PROMPT_INVALID_CODE
            )
        effort = _normalized_effort(reasoning_effort)
        if not resolved.spec.capabilities.supports_reasoning_effort(effort):
            raise ModelExecutionError(
                UNSUPPORTED_REASONING_EFFORT_MESSAGE,
                code=UNSUPPORTED_REASONING_EFFORT_CODE,
            )

        parameters = ModelExecutionParameters(
            temperature=temperature, max_tokens=max_tokens
        )
        transcript_history = tuple(
            ChatTurn(role=role, content=content) for role, content in history
        )
        transcript_images = tuple(images)

        if transcript_images and not resolved.spec.capabilities.vision:
            raise ModelExecutionError(
                CHAT_PROMPT_INVALID_MESSAGE,
                code=CHAT_PROMPT_INVALID_CODE,
            )

        provider = self._chat_provider(resolved)

        wire_supports = getattr(provider, "supports_reasoning_effort", None)
        if callable(wire_supports) and not wire_supports(effort):
            raise ModelExecutionError(
                UNSUPPORTED_REASONING_EFFORT_MESSAGE,
                code=UNSUPPORTED_REASONING_EFFORT_CODE,
            )

        metadata: dict[str, Any] = {}
        if parameters.max_tokens is not None:
            metadata["max_tokens"] = parameters.max_tokens
        request = LLMRequest(
            prompt=prompt,
            system_prompt=system,
            temperature=parameters.temperature,
            metadata=metadata,
            history=transcript_history,
            images=transcript_images,
            reasoning_effort=effort,
        )
        if facts_sink is not None:
            # These runtimes never echo the effort they applied, so the honest
            # effective value is "unknown", never an echo of the request.
            facts_sink(
                ChatStreamFacts(
                    requested_reasoning_effort=effort.value,
                    effective_reasoning_effort=None,
                )
            )
        return self._stream_deltas(provider, request, cancel_event)

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

    def _resolve_auto(self) -> ResolvedChatModel:
        """Let the canonical router pick the chat model, or fail closed."""

        try:
            decision = self._model_router.decide(ModelRequirements())
        except Exception:  # noqa: BLE001 - a routing defect is an unavailable model
            raise ModelExecutionError(
                NO_MODELS_AVAILABLE_MESSAGE, code=NO_MODELS_AVAILABLE_CODE
            ) from None

        if (
            not isinstance(decision, RoutingDecision)
            or decision.status != "selected"
            or decision.selected_provider_id is None
            or decision.selected_model_id is None
        ):
            raise ModelExecutionError(
                NO_MODELS_AVAILABLE_MESSAGE, code=NO_MODELS_AVAILABLE_CODE
            )

        try:
            spec = self._model_catalog.get(
                decision.selected_model_id,
                provider_id=decision.selected_provider_id,
            )
            provider = self._provider_registry.get(decision.selected_provider_id)
        except ProviderError:
            raise ModelExecutionError(
                NO_MODELS_AVAILABLE_MESSAGE, code=NO_MODELS_AVAILABLE_CODE
            ) from None

        return ResolvedChatModel(
            model=self._normalized_model(spec, provider),
            policy=AUTO_POLICY,
            spec=spec,
            provider=provider,
        )

    def _resolve_explicit(self, normalized_id: str) -> ResolvedChatModel:
        """Resolve one named chat model through the canonical catalog.

        The canonical catalog resolves qualified ids and aliases; a bare model
        id is found by scanning the same canonical listing, so no second
        lookup table exists.  Unknown, unavailable and disabled everything all
        report the same constant message.
        """

        try:
            spec = self._model_catalog.get(normalized_id)
        except ProviderError:
            spec = next(
                (
                    model
                    for model in self._model_catalog.list()
                    if model.id == normalized_id
                ),
                None,
            )
        if spec is None:
            raise ModelExecutionError(
                MODEL_UNAVAILABLE_MESSAGE,
                code=ModelExecutionErrorCode.MODEL_UNAVAILABLE.value,
            )

        provider = self._current_provider(spec.provider_id)
        if (
            provider is None
            or not provider.enabled
            or provider.availability in UNAVAILABLE_PROVIDER_STATES
            or spec.availability in UNAVAILABLE_MODEL_STATES
        ):
            raise ModelExecutionError(
                MODEL_UNAVAILABLE_MESSAGE,
                code=ModelExecutionErrorCode.MODEL_UNAVAILABLE.value,
            )

        return ResolvedChatModel(
            model=self._normalized_model(spec, provider),
            policy=EXPLICIT_POLICY,
            spec=spec,
            provider=provider,
        )

    def _chat_provider(self, resolved: ResolvedChatModel) -> LLMProvider:
        """Materialize the provider for one resolved chat model.

        The canonical factory re-applies the provider and model gates, so a
        disabled or unavailable provider is refused at the stream boundary
        even for a hand-built ``ResolvedChatModel``.
        """

        try:
            provider = self._provider_factory.create(
                provider=resolved.provider,
                model=resolved.spec,
                client=self._client,
            )
        except Exception:  # noqa: BLE001 - every defect becomes a safe failure
            raise ModelExecutionError(
                PROVIDER_UNAVAILABLE_MESSAGE,
                code=ModelExecutionErrorCode.PROVIDER_UNAVAILABLE.value,
            ) from None

        if not isinstance(provider, LLMProvider):
            raise ModelExecutionError(
                PROVIDER_UNAVAILABLE_MESSAGE,
                code=ModelExecutionErrorCode.PROVIDER_UNAVAILABLE.value,
            )
        return provider

    @staticmethod
    def _stream_deltas(
        provider: LLMProvider, request: LLMRequest, cancel_event: Event | None
    ) -> Iterator[str]:
        """Yield the provider's content deltas, normalizing every failure."""

        try:
            yield from provider.stream(request, cancel_event=cancel_event)
        except ProviderTimeoutError:
            # A budget decision, not a provider verdict: the product must be
            # able to say "too slow" apart from "failed".
            raise ModelExecutionError(
                PROVIDER_TIMEOUT_MESSAGE, code=PROVIDER_TIMEOUT_CODE
            ) from None
        except Exception:  # noqa: BLE001 - every defect becomes a safe failure
            raise ModelExecutionError(
                PROVIDER_FAILURE_MESSAGE,
                code=ModelExecutionErrorCode.PROVIDER_FAILURE.value,
            ) from None

    def _current_provider(self, provider_id: str) -> ProviderSpec | None:
        """Return the provider the canonical registry resolves *now*, if any."""

        try:
            return self._provider_registry.get(provider_id)
        except ProviderError:
            return None

    @staticmethod
    def _normalized_model(spec: ModelSpec, provider: ProviderSpec) -> NormalizedModel:
        """Project one canonical catalog entry into a chat selector's view."""

        model_id = spec.id
        capabilities = {
            name: bool(getattr(spec.capabilities, name, False))
            for name in CHAT_CAPABILITY_FIELDS
        }
        available = (
            spec.availability not in UNAVAILABLE_MODEL_STATES
            and provider.availability not in UNAVAILABLE_PROVIDER_STATES
        )
        return NormalizedModel(
            model_id=model_id,
            # The display name the serving authority published, verbatim.  It
            # used to be re-derived by slicing the id, which threw away
            # everything the upstream knew -- a bare alias came out as "sonnet"
            # instead of the real label, and a rolling route was presented as if
            # it named a specific variant.  Falling back to the id is a
            # last resort for an authority that published no name at all, not
            # the normal path.
            display_name=(spec.display_name or model_id.rsplit("/", 1)[-1]),
            provider_id=provider.id,
            # Per-model egress truth when the authority stated it; the lane
            # answer is the fallback for a model that declared nothing.
            locality=spec.locality or lane_locality(provider.id),
            availability="available" if available else "unavailable",
            vendor=spec.vendor,
            capabilities=capabilities,
            reasoning_efforts=tuple(
                effort.value for effort in spec.capabilities.reasoning_efforts
            ),
            document_media_types=tuple(spec.capabilities.document_media_types),
            context_window=spec.context_window,
            streaming=bool(spec.capabilities.streaming),
            version=spec.version,
            status=model_status(spec, provider, available),
        )

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
