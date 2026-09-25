"""Phase 11.21 — canonical capability binding and projection tests.

These tests prove the gateway consumes the *exact* canonical Phase 11.34
provider registry and the canonical model catalog, that capability truth comes
only from declared canonical metadata (never from a model name), that the
additive reasoning-effort/document/streaming capability seam is backwards
compatible, and that the read-only capability projection answers client
questions truthfully — unknown stays unknown.
"""

from __future__ import annotations

import dataclasses

import pytest

from kernel.llm.capabilities import ModelCapabilities, ReasoningEffort
from kernel.llm.model_catalog import ModelSpec
from kernel.llm.model_gateway import ModelGateway
from kernel.llm.model_gateway_contracts import ModelCapabilityProjection
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec
from tests.llm.model_gateway_support import CanonicalGraph, build_canonical_graph

CANONICAL_DOCUMENTS = ("application/pdf", "text/plain", "text/markdown")


def _gateway(graph: CanonicalGraph) -> ModelGateway:
    return ModelGateway(provider_registry=graph.providers, model_catalog=graph.models)


# ── Additive capability seam ─────────────────────────────────────────────────


def test_model_capabilities_new_fields_are_additive_and_defaulted() -> None:
    capabilities = ModelCapabilities()

    assert capabilities.reasoning is False
    assert capabilities.tool_calling is False
    assert capabilities.structured_output is False
    assert capabilities.json_mode is False
    assert capabilities.json_schema is False
    assert capabilities.vision is False
    assert capabilities.audio_input is False
    assert capabilities.audio_output is False
    assert capabilities.embeddings is False
    assert capabilities.reasoning_efforts == ()
    assert capabilities.document_media_types == ()
    assert capabilities.streaming is False


def test_existing_keyword_construction_still_works() -> None:
    capabilities = ModelCapabilities(reasoning=True, vision=True)
    assert capabilities.reasoning is True
    assert capabilities.vision is True
    assert capabilities.reasoning_efforts == ()


def test_reasoning_efforts_are_a_closed_typed_set() -> None:
    capabilities = ModelCapabilities(
        reasoning=True,
        reasoning_efforts=(
            ReasoningEffort.LOW,
            ReasoningEffort.HIGH,
            "medium",
        ),
    )
    assert capabilities.reasoning_efforts == (
        ReasoningEffort.LOW,
        ReasoningEffort.HIGH,
        ReasoningEffort.MEDIUM,
    )

    with pytest.raises(ValueError):
        ModelCapabilities(reasoning_efforts=("minimal",))
    with pytest.raises(ValueError):
        ModelCapabilities(reasoning_efforts=("high", "high"))


def test_document_media_types_are_explicit_and_normalized() -> None:
    capabilities = ModelCapabilities(
        document_media_types=("Application/PDF", "text/plain", "text/plain"),
    )
    assert capabilities.document_media_types == ("application/pdf", "text/plain")

    with pytest.raises(ValueError):
        ModelCapabilities(document_media_types=("  ",))
    with pytest.raises(TypeError):
        ModelCapabilities(document_media_types=(b"application/pdf",))


def test_capability_support_helpers_fail_closed() -> None:
    unknown = ModelCapabilities()
    assert unknown.supports_reasoning_effort(ReasoningEffort.DEFAULT) is True
    assert unknown.supports_reasoning_effort(ReasoningEffort.HIGH) is False
    assert unknown.supports_document_media_type("application/pdf") is False

    declared = ModelCapabilities(
        reasoning=True,
        reasoning_efforts=(ReasoningEffort.HIGH,),
        document_media_types=("application/pdf",),
    )
    assert declared.supports_reasoning_effort(ReasoningEffort.HIGH) is True
    assert declared.supports_reasoning_effort(ReasoningEffort.EXTRA_HIGH) is False
    assert declared.supports_document_media_type("application/pdf") is True


def test_default_effort_is_always_acceptable_without_declaring_it() -> None:
    for capabilities in (
        ModelCapabilities(),
        ModelCapabilities(reasoning=True),
        ModelCapabilities(reasoning=True, reasoning_efforts=(ReasoningEffort.NONE,)),
    ):
        assert capabilities.supports_reasoning_effort(ReasoningEffort.DEFAULT) is True
        assert ReasoningEffort.DEFAULT not in capabilities.reasoning_efforts


# ── Canonical authority binding ──────────────────────────────────────────────


def test_gateway_requires_the_exact_canonical_authorities() -> None:
    graph = build_canonical_graph()
    gateway = _gateway(graph)

    assert gateway.provider_registry is graph.providers
    assert gateway.model_catalog is graph.models
    assert gateway.model_catalog.provider_registry is graph.providers


def test_gateway_rejects_wrong_authority_types() -> None:
    graph = build_canonical_graph()
    with pytest.raises(TypeError):
        ModelGateway(provider_registry=object(), model_catalog=graph.models)
    with pytest.raises(TypeError):
        ModelGateway(provider_registry=graph.providers, model_catalog=object())


def test_gateway_rejects_a_catalog_bound_to_a_different_provider_registry() -> None:
    graph = build_canonical_graph()
    foreign = ProviderRegistry()

    with pytest.raises(ValueError):
        ModelGateway(provider_registry=foreign, model_catalog=graph.models)


def test_gateway_owns_no_model_inventory_mutation() -> None:
    gateway = _gateway(build_canonical_graph())

    for forbidden in (
        "register",
        "register_model",
        "add_model",
        "remove",
        "remove_model",
        "replace",
    ):
        assert not hasattr(gateway, forbidden), forbidden


# ── Capability projection ────────────────────────────────────────────────────


def test_capability_projection_derives_from_the_canonical_catalog() -> None:
    graph = build_canonical_graph()
    graph.register_local_model(
        "reasoner",
        context_window=200000,
        capabilities=ModelCapabilities(
            reasoning=True,
            tool_calling=True,
            structured_output=True,
            json_schema=True,
            vision=True,
            streaming=True,
            reasoning_efforts=(
                ReasoningEffort.LOW,
                ReasoningEffort.MEDIUM,
                ReasoningEffort.HIGH,
            ),
            document_media_types=("application/pdf", "text/markdown"),
        ),
        aliases=("reasoner-alias",),
    )
    gateway = _gateway(graph)

    projection = gateway.model_capabilities("local:reasoner")

    assert isinstance(projection, ModelCapabilityProjection)
    assert projection.model_id == "reasoner"
    assert projection.provider_id == "local"
    assert projection.qualified_id == "local:reasoner"
    assert projection.context_window == 200000
    assert projection.provider_type == "local"
    assert projection.is_local is True
    assert projection.provider_available is True
    assert projection.model_available is True
    assert projection.authority_current is True
    assert projection.reasoning is True
    assert projection.reasoning_efforts == (
        ReasoningEffort.LOW,
        ReasoningEffort.MEDIUM,
        ReasoningEffort.HIGH,
    )
    assert projection.tool_calling is True
    assert projection.structured_output is True
    assert projection.json_schema is True
    assert projection.vision is True
    assert projection.streaming is True
    assert projection.document_media_types == ("application/pdf", "text/markdown")
    assert projection.aliases == ("reasoner-alias",)


def test_capability_projection_resolves_by_provider_qualified_id() -> None:
    graph = build_canonical_graph()
    graph.register_local_model("reasoner")
    gateway = _gateway(graph)

    assert (
        gateway.model_capabilities("reasoner", provider_id="local").qualified_id
        == "local:reasoner"
    )


def test_capabilities_are_never_inferred_from_a_model_name() -> None:
    graph = build_canonical_graph()
    graph.register_local_model("gpt-4-vision-preview-ultra")
    graph.register_local_model("claude-3-opus-thinking")
    graph.register_local_model("llama3.2-vision-document")
    graph.register_local_model(
        "plain-model",
        capabilities=ModelCapabilities(
            vision=True,
            document_media_types=("application/pdf",),
            reasoning=True,
            reasoning_efforts=(ReasoningEffort.HIGH,),
        ),
    )
    gateway = _gateway(graph)

    for suggestive in (
        "local:gpt-4-vision-preview-ultra",
        "local:claude-3-opus-thinking",
        "local:llama3.2-vision-document",
    ):
        projection = gateway.model_capabilities(suggestive)
        assert projection.vision is False, suggestive
        assert projection.document_media_types == (), suggestive
        assert projection.reasoning_efforts == (), suggestive

    plain = gateway.model_capabilities("local:plain-model")
    assert plain.vision is True
    assert plain.document_media_types == ("application/pdf",)
    assert plain.reasoning_efforts == (ReasoningEffort.HIGH,)


def test_unknown_capability_stays_unknown_not_guessed() -> None:
    graph = build_canonical_graph()
    graph.register_local_model("opaque-model", context_window=None)
    gateway = _gateway(graph)

    projection = gateway.model_capabilities("local:opaque-model")

    assert projection.context_window is None
    assert projection.reasoning_efforts == ()
    assert projection.document_media_types == ()
    assert projection.supports_reasoning_effort(ReasoningEffort.HIGH) is False


def test_unknown_model_fails_model_not_found() -> None:
    gateway = _gateway(build_canonical_graph())

    with pytest.raises(ModelGatewayError) as error:
        gateway.model_capabilities("missing-model")

    assert error.value.code is ModelGatewayErrorCode.MODEL_NOT_FOUND


def test_projection_reports_provider_and_model_availability_truthfully() -> None:
    graph = build_canonical_graph()
    graph.providers.register(
        ProviderSpec(
            id="disabled-provider",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://disabled.example/v1",
            availability="unavailable",
            enabled=False,
        )
    )
    graph.models.register(
        ModelSpec(
            id="disabled-model",
            provider_id="disabled-provider",
            context_window=1000,
        )
    )
    graph.register_local_model("withdrawn-model", availability="disabled")
    gateway = _gateway(graph)

    disabled = gateway.model_capabilities("disabled-provider:disabled-model")
    assert disabled.provider_available is False
    assert disabled.model_available is True

    withdrawn = gateway.model_capabilities("local:withdrawn-model")
    assert withdrawn.provider_available is True
    assert withdrawn.model_available is False


def test_projection_marks_a_stale_provider_authority() -> None:
    graph = build_canonical_graph()
    graph.register_local_model("stale-model")
    graph.providers.register(
        ProviderSpec(
            id="local",
            provider_type="local",
            api_style="chat_completions",
            availability="available",
        ),
        replace_existing=True,
    )
    gateway = _gateway(graph)

    projection = gateway.model_capabilities("local:stale-model")

    assert projection.authority_current is False
    assert projection.provider_available is False


def test_projection_distinguishes_remote_models() -> None:
    graph = build_canonical_graph()
    graph.models.register(
        ModelSpec(
            id="remote-reasoner",
            provider_id="remote-a",
            context_window=128000,
            capabilities=ModelCapabilities(streaming=True),
        )
    )
    gateway = _gateway(graph)

    projection = gateway.model_capabilities("remote-a:remote-reasoner")

    assert projection.provider_type == "remote"
    assert projection.is_local is False
    assert projection.streaming is True


def test_capability_projection_serialization_is_safe_and_complete() -> None:
    graph = build_canonical_graph()
    graph.register_local_model(
        "reasoner",
        capabilities=ModelCapabilities(
            reasoning=True,
            reasoning_efforts=(ReasoningEffort.HIGH,),
            document_media_types=("application/pdf",),
        ),
    )
    gateway = _gateway(graph)

    payload = gateway.model_capabilities("local:reasoner").to_dict()

    assert payload["reasoning_efforts"] == ["high"]
    assert payload["document_media_types"] == ["application/pdf"]
    assert payload["is_local"] is True
    for forbidden in ("api_key", "secret", "credential", "prompt", "payload"):
        assert forbidden not in payload


def test_list_model_capabilities_is_sorted_and_filterable() -> None:
    graph = build_canonical_graph()
    graph.register_local_model("zeta")
    graph.register_local_model("alpha")
    graph.models.register(
        ModelSpec(id="beta", provider_id="remote-a", context_window=8)
    )
    gateway = _gateway(graph)

    all_models = gateway.list_model_capabilities()
    assert [item.qualified_id for item in all_models] == [
        "local:alpha",
        "local:zeta",
        "remote-a:beta",
    ]

    local_only = gateway.list_model_capabilities(provider_id="local")
    assert [item.qualified_id for item in local_only] == ["local:alpha", "local:zeta"]


def test_projection_is_immutable() -> None:
    graph = build_canonical_graph()
    graph.register_local_model("reasoner")
    gateway = _gateway(graph)

    projection = gateway.model_capabilities("local:reasoner")

    with pytest.raises(dataclasses.FrozenInstanceError):
        projection.vision = True  # type: ignore[misc]
