from decimal import Decimal

import pytest

from kernel.llm.exceptions import ProviderError
from kernel.llm.model_catalog import (
    ModelSpec,
    get_model_spec,
    has_model,
    list_model_specs,
    register_model,
)
from kernel.llm.provider_capabilities import ProviderCapabilities


def test_registers_and_resolves_model_by_qualified_id() -> None:
    register_model(
        ModelSpec(
            id="catalog-test-model",
            provider="groq",
            context_window=32_768,
        ),
        replace=True,
    )

    spec = get_model_spec("groq:catalog-test-model")

    assert spec.id == "catalog-test-model"
    assert spec.provider == "groq"
    assert spec.qualified_id == "groq:catalog-test-model"
    assert spec.context_window == 32_768


def test_resolves_model_by_alias() -> None:
    register_model(
        ModelSpec(
            id="aliased-test-model",
            provider="openrouter",
            context_window=65_536,
            aliases=("fast-test", " FAST-TEST-SECONDARY "),
        ),
        replace=True,
    )

    assert get_model_spec("fast-test").id == "aliased-test-model"
    assert get_model_spec("fast-test-secondary").provider == "openrouter"


def test_preserves_model_capabilities_and_pricing() -> None:
    capabilities = ProviderCapabilities(
        reasoning=True,
        vision=True,
        max_context_tokens=131_072,
    )

    register_model(
        ModelSpec(
            id="priced-test-model",
            provider="together",
            context_window=131_072,
            capabilities=capabilities,
            input_cost_per_million=Decimal("0.50"),
            output_cost_per_million=Decimal("1.25"),
        ),
        replace=True,
    )

    spec = get_model_spec("priced-test-model", provider="together")

    assert spec.capabilities == capabilities
    assert spec.input_cost_per_million == Decimal("0.50")
    assert spec.output_cost_per_million == Decimal("1.25")


def test_rejects_unknown_provider() -> None:
    with pytest.raises(
        ProviderError,
        match="Unknown registered provider",
    ):
        register_model(
            ModelSpec(
                id="unknown-provider-model",
                provider="missing-provider",
                context_window=8_192,
            )
        )


@pytest.mark.parametrize(
    ("context_window", "input_cost", "expected_message"),
    [
        (0, None, "context window"),
        (-1, None, "context window"),
        (8_192, Decimal("-0.01"), "cost cannot be negative"),
    ],
)
def test_rejects_invalid_model_metadata(
    context_window: int,
    input_cost: Decimal | None,
    expected_message: str,
) -> None:
    with pytest.raises(ProviderError, match=expected_message):
        register_model(
            ModelSpec(
                id=f"invalid-model-{context_window}",
                provider="groq",
                context_window=context_window,
                input_cost_per_million=input_cost,
            )
        )


def test_lists_models_filtered_by_provider() -> None:
    register_model(
        ModelSpec(
            id="list-test-groq",
            provider="groq",
            context_window=8_192,
        ),
        replace=True,
    )
    register_model(
        ModelSpec(
            id="list-test-openrouter",
            provider="openrouter",
            context_window=8_192,
        ),
        replace=True,
    )

    groq_models = list_model_specs(provider="groq")

    assert any(spec.id == "list-test-groq" for spec in groq_models)
    assert all(spec.provider == "groq" for spec in groq_models)
    assert has_model("list-test-groq", provider="groq")
    assert not has_model("list-test-groq", provider="openrouter")
