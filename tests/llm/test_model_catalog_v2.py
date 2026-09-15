from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.exceptions import ProviderError
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_routes import ModelRoute, ModelRouteCatalog
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
    ProviderConnectionRegistry,
)
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec


def _route_catalog_for(*provider_ids: str) -> ModelRouteCatalog:
    """Build a route catalog whose providers/connections exist canonically."""
    providers = ProviderRegistry()
    connections = ProviderConnectionRegistry(providers)
    for provider_id in provider_ids:
        providers.register(
            ProviderSpec(
                id=provider_id,
                provider_type="remote",
                api_style="chat_completions",
                base_url="https://example.test/v1",
            )
        )
        connections.register(
            ProviderConnection(
                connection_id=f"{provider_id}:main",
                provider_id=provider_id,
                display_name=provider_id,
                billing_class=BillingClass.API,
                credential_ref=None,
                endpoint="https://example.test/v1",
                isolation_profile_ref=None,
                status=ConnectionStatus.CONNECTED,
            )
        )
    return ModelRouteCatalog(connections)


@pytest.fixture
def registry() -> ProviderRegistry:
    provider_registry = ProviderRegistry()
    provider_registry.register(
        ProviderSpec(
            id="test-provider",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://example.test/v1",
        )
    )
    return provider_registry


@pytest.fixture
def catalog(registry: ProviderRegistry) -> ModelCatalog:
    return ModelCatalog(registry)


def test_model_catalog_exposes_bound_provider_registry() -> None:
    """The catalog publishes the one authority it resolves providers through."""
    providers = ProviderRegistry()
    catalog = ModelCatalog(providers)

    assert catalog.provider_registry is providers


def test_catalog_is_instance_scoped(
    catalog: ModelCatalog,
    registry: ProviderRegistry,
) -> None:
    other = ModelCatalog(registry)
    catalog.register(
        ModelSpec(
            id="model-a",
            provider_id="test-provider",
        )
    )

    assert catalog.has("model-a", provider_id="test-provider")
    assert not other.has("model-a", provider_id="test-provider")


def test_catalog_rejects_unknown_provider(catalog: ModelCatalog) -> None:
    with pytest.raises(ProviderError, match="Unknown registered provider"):
        catalog.register(
            ModelSpec(
                id="model-a",
                provider_id="missing",
            )
        )


def test_catalog_resolves_qualified_id_and_alias(
    catalog: ModelCatalog,
) -> None:
    registered = catalog.register(
        ModelSpec(
            id="MODEL-A",
            provider_id="TEST-PROVIDER",
            aliases=("fast", " FAST "),
            context_window=32_768,
            capabilities=ModelCapabilities(
                reasoning=True,
                structured_output=True,
            ),
        )
    )

    assert registered.qualified_id == "test-provider:model-a"
    assert catalog.get("test-provider:model-a") == registered
    assert catalog.get("fast") == registered
    assert registered.aliases == ("fast",)


def test_catalog_preserves_pricing_and_version(
    catalog: ModelCatalog,
) -> None:
    registered = catalog.register(
        ModelSpec(
            id="priced",
            provider_id="test-provider",
            input_cost_per_million=Decimal("0.50"),
            output_cost_per_million=Decimal("1.25"),
            cached_input_cost_per_million=Decimal("0.10"),
            version="2026-07",
        )
    )

    assert registered.input_cost_per_million == Decimal("0.50")
    assert registered.output_cost_per_million == Decimal("1.25")
    assert registered.cached_input_cost_per_million == Decimal("0.10")
    assert registered.version == "2026-07"


@pytest.mark.parametrize(
    ("context_window", "cost", "message"),
    [
        (0, None, "context window"),
        (-1, None, "context window"),
        (8_192, Decimal("-0.01"), "cannot be negative"),
    ],
)
def test_catalog_rejects_invalid_model_metadata(
    context_window: int,
    cost: Decimal | None,
    message: str,
    catalog: ModelCatalog,
) -> None:
    with pytest.raises(ProviderError, match=message):
        catalog.register(
            ModelSpec(
                id="invalid",
                provider_id="test-provider",
                context_window=context_window,
                input_cost_per_million=cost,
            )
        )


def test_catalog_rejects_alias_collision(catalog: ModelCatalog) -> None:
    catalog.register(
        ModelSpec(
            id="first",
            provider_id="test-provider",
            aliases=("shared",),
        )
    )

    with pytest.raises(ProviderError, match="alias is already registered"):
        catalog.register(
            ModelSpec(
                id="second",
                provider_id="test-provider",
                aliases=("shared",),
            )
        )


def test_catalog_lists_filters_and_removes_models(
    catalog: ModelCatalog,
) -> None:
    catalog.register(ModelSpec(id="zeta", provider_id="test-provider"))
    catalog.register(ModelSpec(id="alpha", provider_id="test-provider"))

    assert [spec.id for spec in catalog.list()] == ["alpha", "zeta"]
    assert catalog.remove("alpha", provider_id="test-provider").id == "alpha"
    assert not catalog.has("alpha", provider_id="test-provider")


def test_registering_model_route_does_not_mutate_model_catalog(
    catalog: ModelCatalog,
) -> None:
    catalog.register(ModelSpec(id="model-a", provider_id="test-provider"))
    route_catalog = _route_catalog_for("test-provider")
    route_catalog.register(
        ModelRoute(
            route_id="test-provider:main:model-a",
            connection_id="test-provider:main",
            provider_model_id="model-a",
            canonical_model_id="model-a",
        )
    )

    assert [spec.id for spec in catalog.list()] == ["model-a"]
    assert not catalog.has("test-provider:main:model-a")
    with pytest.raises(ProviderError, match="Unknown registered model"):
        catalog.get("test-provider:main:model-a")
    assert route_catalog.get("test-provider:main:model-a") is not None


def test_model_spec_provider_id_ownership_unchanged_with_route_inventory(
    catalog: ModelCatalog,
) -> None:
    route_catalog = _route_catalog_for("test-provider", "missing")
    route_catalog.register(
        ModelRoute(
            route_id="missing:model-a",
            connection_id="missing:main",
            provider_model_id="model-a",
            canonical_model_id="model-a",
        )
    )

    catalog.register(ModelSpec(id="model-a", provider_id="test-provider"))
    with pytest.raises(ProviderError, match="Unknown registered provider"):
        catalog.register(ModelSpec(id="model-b", provider_id="missing"))


def test_model_spec_fields_untouched_by_route_types() -> None:
    field_names = {f.name for f in dataclasses.fields(ModelSpec)}

    assert "route_id" not in field_names
    assert "connection_id" not in field_names
    assert "canonical_model_id" not in field_names
    assert "available" not in field_names
