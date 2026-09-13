
from datetime import datetime, timezone

import pytest

from kernel.llm.model_routes import (
    CapabilityConfidence,
    ModelRoute,
    ModelRouteCatalog,
    RouteCapabilityState,
)

T0 = datetime(2026, 9, 13, 10, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def test_capability_filter_accepts_verified_support() -> None:
    catalog = ModelRouteCatalog()
    catalog.register(ModelRoute(
        route_id="openai:gpt-4",
        connection_id="openai:main",
        provider_model_id="gpt-4",
        canonical_model_id="gpt-4",
        capabilities=(
            RouteCapabilityState(
                name="tools",
                supported=True,
                confidence=CapabilityConfidence.VERIFIED,
            ),
            RouteCapabilityState(
                name="structured_output",
                supported=True,
                confidence=CapabilityConfidence.VERIFIED,
            ),
        ),
    ))
    filtered = catalog.filter_required_capabilities(("tools", "structured_output"))
    assert len(filtered) == 1
    assert filtered[0].route_id == "openai:gpt-4"

def test_capability_filter_rejects_missing_capability() -> None:
    catalog = ModelRouteCatalog()
    catalog.register(ModelRoute(
        route_id="basic:model",
        connection_id="basic:main",
        provider_model_id="basic",
        canonical_model_id="basic",
        capabilities=(
            RouteCapabilityState(
                name="tools",
                supported=True,
                confidence=CapabilityConfidence.VERIFIED,
            ),
        ),
    ))
    filtered = catalog.filter_required_capabilities(("tools", "structured_output"))
    assert len(filtered) == 0

def test_capability_filter_rejects_unsupported_capability() -> None:
    catalog = ModelRouteCatalog()
    catalog.register(ModelRoute(
        route_id="weak:model",
        connection_id="weak:main",
        provider_model_id="weak",
        canonical_model_id="weak",
        capabilities=(
            RouteCapabilityState(
                name="tools",
                supported=False,
                confidence=CapabilityConfidence.DISCOVERED,
            ),
        ),
    ))
    filtered = catalog.filter_required_capabilities(("tools",))
    assert len(filtered) == 0

def test_capability_filter_rejects_unknown_confidence() -> None:
    catalog = ModelRouteCatalog()
    catalog.register(ModelRoute(
        route_id="unknown:model",
        connection_id="unknown:main",
        provider_model_id="unknown",
        canonical_model_id="unknown",
        capabilities=(
            RouteCapabilityState(
                name="tools",
                supported=True,
                confidence=CapabilityConfidence.UNKNOWN,
            ),
        ),
    ))
    filtered = catalog.filter_required_capabilities(("tools",))
    assert len(filtered) == 0

def test_capability_filter_accepts_declared_support_for_automation() -> None:
    catalog = ModelRouteCatalog()
    catalog.register(ModelRoute(
        route_id="declared:model",
        connection_id="declared:main",
        provider_model_id="declared",
        canonical_model_id="declared",
        capabilities=(
            RouteCapabilityState(
                name="chat",
                supported=True,
                confidence=CapabilityConfidence.DECLARED,
            ),
        ),
    ))
    filtered = catalog.filter_required_capabilities(("chat",))
    assert len(filtered) == 1


# --- Step 1 (plan): route identity and lifecycle tests, verbatim from
# docs/superpowers/plans/2026-09-13-cmm-provider-registry-core.md Task 2 ---


def test_same_model_can_have_multiple_provider_routes() -> None:
    catalog = ModelRouteCatalog()
    catalog.register(ModelRoute(
        route_id="qwen-token-plan:qwen3.8-max",
        connection_id="qwen-token-plan:main",
        provider_model_id="qwen3.8-max",
        canonical_model_id="qwen3.8-max",
    ))
    catalog.register(ModelRoute(
        route_id="qwen-cloud:qwen3.8-max",
        connection_id="qwen-cloud:main",
        provider_model_id="qwen3.8-max",
        canonical_model_id="qwen3.8-max",
    ))

    routes = catalog.routes_for_canonical_model("qwen3.8-max")
    assert {route.connection_id for route in routes} == {
        "qwen-token-plan:main",
        "qwen-cloud:main",
    }

def test_missing_route_becomes_unavailable_not_deleted() -> None:
    catalog = ModelRouteCatalog()
    route = catalog.register(ModelRoute(
        route_id="kira:glm-5.3-free",
        connection_id="kira:main",
        provider_model_id="glm-5.3-free",
        canonical_model_id="glm-5.3",
    ))

    catalog.mark_unavailable(route.route_id)

    assert catalog.get(route.route_id) is not None
    assert catalog.get(route.route_id).available is False


# --- Task 2 spec-gap closure: identity defaults and lifecycle pinning ---


def test_register_sets_seen_timestamps_when_none() -> None:
    catalog = ModelRouteCatalog()
    registered = catalog.register(ModelRoute(
        route_id="deepseek:deepseek-chat",
        connection_id="deepseek:main",
        provider_model_id="deepseek-chat",
        canonical_model_id="deepseek-chat",
    ))

    assert registered.first_seen_at is not None
    assert registered.last_seen_at is not None
    assert registered.first_seen_at.tzinfo is not None
    assert registered.available is True


def test_register_preserves_explicit_first_seen_at() -> None:
    catalog = ModelRouteCatalog()
    registered = catalog.register(ModelRoute(
        route_id="moonshot:kimi-k2",
        connection_id="moonshot:main",
        provider_model_id="kimi-k2",
        canonical_model_id="kimi-k2",
        first_seen_at=T0,
    ))

    assert registered.first_seen_at == T0
    assert registered.last_seen_at is not None


def test_mark_seen_refreshes_last_seen_and_restores_availability() -> None:
    catalog = ModelRouteCatalog()
    registered = catalog.register(ModelRoute(
        route_id="zhipu:glm-5.3",
        connection_id="zhipu:main",
        provider_model_id="glm-5.3",
        canonical_model_id="glm-5.3",
        first_seen_at=T0,
        last_seen_at=T0,
    ))
    catalog.mark_unavailable(registered.route_id)

    seen = catalog.mark_seen(registered.route_id, at=T1)

    assert seen.last_seen_at == T1
    assert seen.available is True
    assert seen.first_seen_at == T0  # historical identity preserved
    stored = catalog.get(registered.route_id)
    assert stored == seen


def test_mark_seen_positional_at_matches_plan_interface() -> None:
    """Plan interface is mark_seen(route_id, at) — 'at' must be positional."""
    catalog = ModelRouteCatalog()
    registered = catalog.register(ModelRoute(
        route_id="openrouter:meta-llama",
        connection_id="openrouter:main",
        provider_model_id="meta-llama/llama-3",
        canonical_model_id="llama-3",
    ))

    seen = catalog.mark_seen(registered.route_id, T1)

    assert seen.last_seen_at == T1
    assert seen.available is True


def test_mark_unavailable_retains_identity_and_blocks_re_register() -> None:
    catalog = ModelRouteCatalog()
    registered = catalog.register(ModelRoute(
        route_id="groq:llama-guard",
        connection_id="groq:main",
        provider_model_id="llama-guard",
        canonical_model_id="llama-guard",
    ))
    catalog.mark_unavailable(registered.route_id)

    assert catalog.get(registered.route_id) is not None
    assert catalog.routes_for_canonical_model("llama-guard")  # history kept

    with pytest.raises(ValueError, match="duplicate route_id"):
        catalog.register(ModelRoute(
            route_id="groq:llama-guard",
            connection_id="groq:main",
            provider_model_id="llama-guard",
            canonical_model_id="llama-guard",
        ))


def test_duplicate_route_id_rejected() -> None:
    catalog = ModelRouteCatalog()
    route = ModelRoute(
        route_id="anthropic:claude-opus",
        connection_id="anthropic:main",
        provider_model_id="claude-opus",
        canonical_model_id="claude-opus",
    )
    catalog.register(route)

    with pytest.raises(ValueError, match="duplicate route_id"):
        catalog.register(ModelRoute(
            route_id="anthropic:claude-opus",
            connection_id="anthropic:backup",
            provider_model_id="claude-opus",
            canonical_model_id="claude-opus",
        ))
