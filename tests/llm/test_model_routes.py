
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


# --- Review round 1 (Task 2): store-side normalization, ValueError taxonomy,
# aware-datetime enforcement, dataclasses.replace, deterministic ordering ---


def test_padded_mixed_case_route_id_round_trips_through_get_and_marks() -> None:
    """Storage normalizes ids; raw lookups normalize too (finding 1)."""
    catalog = ModelRouteCatalog()
    registered = catalog.register(ModelRoute(
        route_id="  OpenAI:GPT-4o  ",
        connection_id="  OpenAI:Main  ",
        provider_model_id="gpt-4o",
        canonical_model_id="gpt-4o",
    ))

    assert registered.route_id == "openai:gpt-4o"
    assert registered.connection_id == "openai:main"

    fetched = catalog.get("OPENAI:GPT-4o")
    assert fetched is not None
    assert fetched.route_id == "openai:gpt-4o"

    seen = catalog.mark_seen("  OpenAI:GPT-4o ", T1)
    assert seen.last_seen_at == T1
    assert seen.route_id == "openai:gpt-4o"

    unavailable = catalog.mark_unavailable("OPENAI:gpt-4o")
    assert unavailable.available is False
    assert catalog.get("openai:gpt-4o").available is False


def test_provider_model_id_case_is_preserved_by_normalization() -> None:
    """Only route/connection ids are lowered; model ids stay case-sensitive."""
    catalog = ModelRouteCatalog()
    registered = catalog.register(ModelRoute(
        route_id="openai:gpt-4o",
        connection_id="openai:main",
        provider_model_id="GPT-4o-20260801",
        canonical_model_id="GPT-4o",
    ))

    assert registered.provider_model_id == "GPT-4o-20260801"
    assert registered.canonical_model_id == "GPT-4o"


@pytest.mark.parametrize(
    "field,bad_value,label",
    [
        ("route_id", "   ", "Route id"),
        ("connection_id", "", "Connection id"),
        ("provider_model_id", "  ", "Provider model id"),
        ("canonical_model_id", "", "Canonical model id"),
    ],
)
def test_blank_identity_fields_rejected_on_construction(
    field: str, bad_value: str, label: str
) -> None:
    values = {
        "route_id": "openai:gpt-4",
        "connection_id": "openai:main",
        "provider_model_id": "gpt-4",
        "canonical_model_id": "gpt-4",
    }
    values[field] = bad_value

    with pytest.raises(ValueError, match=f"{label} cannot be empty"):
        ModelRoute(**values)


def test_mark_seen_unknown_route_id_raises_value_error() -> None:
    """Mutators raise; get() returns None (findings 1/2 taxonomy)."""
    catalog = ModelRouteCatalog()

    with pytest.raises(ValueError, match="unknown route_id: ghost:model"):
        catalog.mark_seen("ghost:model")


def test_mark_unavailable_unknown_route_id_raises_value_error() -> None:
    catalog = ModelRouteCatalog()

    with pytest.raises(ValueError, match="unknown route_id: ghost:model"):
        catalog.mark_unavailable("ghost:model")


def test_mark_seen_blank_route_id_raises_value_error() -> None:
    catalog = ModelRouteCatalog()

    with pytest.raises(ValueError, match="unknown route_id"):
        catalog.mark_seen("   ")


def test_mark_unavailable_blank_route_id_raises_value_error() -> None:
    catalog = ModelRouteCatalog()

    with pytest.raises(ValueError, match="unknown route_id"):
        catalog.mark_unavailable("")


def test_case_variant_route_id_rejected_as_duplicate() -> None:
    """Normalized keys make duplicate detection case-insensitive (finding 3)."""
    catalog = ModelRouteCatalog()
    catalog.register(ModelRoute(
        route_id="A:b",
        connection_id="a:main",
        provider_model_id="b",
        canonical_model_id="b",
    ))

    with pytest.raises(ValueError, match="duplicate route_id"):
        catalog.register(ModelRoute(
            route_id="a:b",
            connection_id="a:backup",
            provider_model_id="b",
            canonical_model_id="b",
        ))


def test_register_rejects_naive_first_seen_at() -> None:
    """Naive timestamps are a correctness trap (finding 4)."""
    catalog = ModelRouteCatalog()
    naive = datetime(2026, 9, 13, 10, 0)  # noqa: DTZ001

    with pytest.raises(ValueError, match="must be timezone-aware"):
        catalog.register(ModelRoute(
            route_id="naive:model",
            connection_id="naive:main",
            provider_model_id="naive",
            canonical_model_id="naive",
            first_seen_at=naive,
        ))


def test_mark_seen_rejects_naive_timestamp() -> None:
    catalog = ModelRouteCatalog()
    registered = catalog.register(ModelRoute(
        route_id="openai:gpt-4",
        connection_id="openai:main",
        provider_model_id="gpt-4",
        canonical_model_id="gpt-4",
    ))

    naive_at = datetime(2026, 9, 13, 11, 0)  # noqa: DTZ001
    with pytest.raises(ValueError, match="must be timezone-aware"):
        catalog.mark_seen(registered.route_id, naive_at)

    assert catalog.get(registered.route_id).last_seen_at == registered.last_seen_at


def test_routes_for_canonical_model_sorted_by_route_id() -> None:
    """Deterministic ordering for consumers (finding 7)."""
    catalog = ModelRouteCatalog()
    for route_id in ("zeta:model", "alpha:model", "mid:model"):
        catalog.register(ModelRoute(
            route_id=route_id,
            connection_id=f"{route_id.split(':')[0]}:main",
            provider_model_id="shared",
            canonical_model_id="shared",
        ))

    routes = catalog.routes_for_canonical_model("shared")
    assert [route.route_id for route in routes] == [
        "alpha:model",
        "mid:model",
        "zeta:model",
    ]


def test_register_pins_available_true_for_seen_now_semantics() -> None:
    """register() means 'seen now', so availability is forced True (finding 6)."""
    catalog = ModelRouteCatalog()
    registered = catalog.register(ModelRoute(
        route_id="pinned:model",
        connection_id="pinned:main",
        provider_model_id="pinned",
        canonical_model_id="pinned",
        available=False,
    ))

    assert registered.available is True
    assert catalog.get("pinned:model").available is True


def test_filter_accepts_discovered_confidence_when_supported() -> None:
    """Pinned policy: only UNKNOWN confidence fails; DISCOVERED passes."""
    catalog = ModelRouteCatalog()
    catalog.register(ModelRoute(
        route_id="discovered:model",
        connection_id="discovered:main",
        provider_model_id="discovered",
        canonical_model_id="discovered",
        capabilities=(
            RouteCapabilityState(
                name="tools",
                supported=True,
                confidence=CapabilityConfidence.DISCOVERED,
            ),
        ),
    ))

    filtered = catalog.filter_required_capabilities(("tools",))
    assert [route.route_id for route in filtered] == ["discovered:model"]
