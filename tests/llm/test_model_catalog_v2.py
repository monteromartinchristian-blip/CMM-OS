from __future__ import annotations

from decimal import Decimal

import pytest

from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.exceptions import ProviderError
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec


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
    catalog.register(
        ModelSpec(id="zeta", provider_id="test-provider")
    )
    catalog.register(
        ModelSpec(id="alpha", provider_id="test-provider")
    )

    assert [spec.id for spec in catalog.list()] == ["alpha", "zeta"]
    assert catalog.remove("alpha", provider_id="test-provider").id == "alpha"
    assert not catalog.has("alpha", provider_id="test-provider")
