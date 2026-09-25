"""Phase 11.21 — usage, latency and cost accounting tests.

Accounting is factual.  Missing provider metrics stay unknown (``None``) and are
never fabricated as zeros, provider-reported cost wins over any derived value,
and a catalog-derived cost appears only when canonical pricing metadata can
price the call deterministically.  No budget, ledger, dashboard or alerting is
introduced.
"""

from __future__ import annotations

import json
from decimal import Decimal

from kernel.llm.model_catalog import ModelSpec
from kernel.llm.model_gateway import derive_model_call_cost
from kernel.llm.model_gateway_contracts import (
    ModelGatewayRequest,
    ModelInputPart,
    ModelUsage,
)
from tests.llm.model_gateway_support import TEXT_CAPABLE, build_runtime


def _request(**overrides: object) -> ModelGatewayRequest:
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "model_id": "local:model-1",
        "input_parts": (ModelInputPart.text_part("account for this"),),
    }
    values.update(overrides)
    return ModelGatewayRequest(**values)  # type: ignore[arg-type]


def _runtime(**overrides: object):
    overrides.setdefault("capabilities", TEXT_CAPABLE)
    return build_runtime(**overrides)  # type: ignore[arg-type]


def _priced_runtime(**overrides: object):
    from tests.llm.model_gateway_support import build_canonical_graph

    graph = build_canonical_graph()
    graph.models.register(
        ModelSpec(
            id="model-1",
            provider_id="local",
            context_window=32768,
            capabilities=TEXT_CAPABLE,
            availability="available",
            input_cost_per_million=Decimal("1.50"),
            output_cost_per_million=Decimal("6.00"),
            cached_input_cost_per_million=Decimal("0.15"),
        )
    )
    return build_runtime(
        graph=graph,
        register_model=False,
        **overrides,  # type: ignore[arg-type]
    )


# ── Provider-reported facts ─────────────────────────────────────────────────


def test_provider_reported_usage_is_normalized() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(
        content="ok",
        usage=ModelUsage(input_tokens=120, output_tokens=34, cached_tokens=20),
        finish_reason="length",
    )

    response = runtime.gateway.execute(_request())

    assert response.usage.input_tokens == 120
    assert response.usage.output_tokens == 34
    assert response.usage.cached_tokens == 20
    assert response.usage.total_tokens == 154
    assert response.finish_reason == "length"
    assert response.facts is not None
    assert response.facts.usage == response.usage
    assert response.facts.latency_ms is not None


def test_missing_provider_metrics_remain_unknown_not_zero() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(content="ok")

    response = runtime.gateway.execute(_request())

    assert response.usage.input_tokens is None
    assert response.usage.output_tokens is None
    assert response.usage.cached_tokens is None
    assert response.usage.cost is None
    assert response.usage.cost_source is None
    assert response.usage.total_tokens is None
    payload = response.to_dict()["usage"]
    assert payload["input_tokens"] is None
    assert payload["output_tokens"] is None
    assert payload["total_tokens"] is None


def test_partial_usage_stays_partial() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(usage=ModelUsage(input_tokens=10))

    response = runtime.gateway.execute(_request())

    assert response.usage.input_tokens == 10
    assert response.usage.output_tokens is None
    assert response.usage.total_tokens is None


def test_a_provider_reported_zero_is_preserved_as_zero() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(usage=ModelUsage(cached_tokens=0))

    response = runtime.gateway.execute(_request())

    assert response.usage.cached_tokens == 0


def test_a_cancelled_stream_still_records_elapsed_latency() -> None:
    from kernel.llm.capabilities import ModelCapabilities
    from kernel.llm.model_streaming import ModelCallCancellation

    runtime = _runtime(capabilities=ModelCapabilities(streaming=True))
    runtime.adapter().add_stream(("a",))
    cancellation = ModelCallCancellation()
    cancellation.cancel("stop")

    list(runtime.gateway.stream(_request(), cancellation=cancellation))

    facts = runtime.sink.records[0]
    assert facts.cancelled is True
    assert facts.latency_ms is not None
    assert facts.latency_ms >= 0


# ── Provider-reported cost ──────────────────────────────────────────────────


def test_provider_reported_cost_wins_over_any_derived_value() -> None:
    runtime = _priced_runtime()
    runtime.adapter().add_response(
        usage=ModelUsage(
            input_tokens=1000000,
            output_tokens=1000000,
            cost=Decimal("0.01000000"),
            cost_source="provider_reported",
        )
    )

    response = runtime.gateway.execute(_request())

    assert response.usage.cost == Decimal("0.01000000")
    assert response.usage.cost_source == "provider_reported"


def test_catalog_derived_cost_is_deterministic() -> None:
    runtime = _priced_runtime()
    runtime.adapter().add_response(
        usage=ModelUsage(input_tokens=1000000, output_tokens=500000)
    )

    response = runtime.gateway.execute(_request())

    assert response.usage.cost_source == "catalog_derived"
    assert response.usage.cost == Decimal("4.50000000")


def test_cached_tokens_are_priced_at_the_cached_rate_without_double_billing() -> None:
    runtime = _priced_runtime()
    runtime.adapter().add_response(
        usage=ModelUsage(input_tokens=1000000, cached_tokens=1000000)
    )

    response = runtime.gateway.execute(_request())

    assert response.usage.cost == Decimal("0.15000000")


def test_cached_tokens_fall_back_to_the_input_rate_when_unpriced() -> None:
    from tests.llm.model_gateway_support import build_canonical_graph

    graph = build_canonical_graph()
    graph.models.register(
        ModelSpec(
            id="model-1",
            provider_id="local",
            context_window=32768,
            capabilities=TEXT_CAPABLE,
            availability="available",
            input_cost_per_million=Decimal("2.00"),
            output_cost_per_million=Decimal("4.00"),
        )
    )
    runtime = build_runtime(graph=graph, register_model=False)
    runtime.adapter().add_response(
        usage=ModelUsage(input_tokens=1000000, cached_tokens=500000)
    )

    response = runtime.gateway.execute(_request())

    assert response.usage.cost == Decimal("2.00000000")


def test_no_price_metadata_means_unknown_cost() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(
        usage=ModelUsage(input_tokens=1000, output_tokens=10)
    )

    response = runtime.gateway.execute(_request())

    assert response.usage.cost is None
    assert response.usage.cost_source is None


# ── Pure derivation helper ──────────────────────────────────────────────────


def test_derivation_returns_none_without_token_counts() -> None:
    assert (
        derive_model_call_cost(
            input_tokens=None,
            output_tokens=None,
            cached_tokens=None,
            input_cost_per_million=Decimal("1.00"),
            output_cost_per_million=Decimal("1.00"),
            cached_input_cost_per_million=None,
        )
        is None
    )


def test_derivation_returns_none_when_a_known_count_is_unpriced() -> None:
    assert (
        derive_model_call_cost(
            input_tokens=100,
            output_tokens=10,
            cached_tokens=None,
            input_cost_per_million=Decimal("1.00"),
            output_cost_per_million=None,
            cached_input_cost_per_million=None,
        )
        is None
    )
    assert (
        derive_model_call_cost(
            input_tokens=100,
            output_tokens=None,
            cached_tokens=None,
            input_cost_per_million=None,
            output_cost_per_million=Decimal("1.00"),
            cached_input_cost_per_million=None,
        )
        is None
    )


def test_derivation_never_returns_a_fabricated_zero() -> None:
    assert derive_model_call_cost(
        input_tokens=0,
        output_tokens=0,
        cached_tokens=None,
        input_cost_per_million=Decimal("1.00"),
        output_cost_per_million=Decimal("1.00"),
        cached_input_cost_per_million=None,
    ) == Decimal("0E-8")


def test_derivation_is_pure_and_deterministic() -> None:
    arguments = {
        "input_tokens": 12345,
        "output_tokens": 678,
        "cached_tokens": 45,
        "input_cost_per_million": Decimal("2.50"),
        "output_cost_per_million": Decimal("10.00"),
        "cached_input_cost_per_million": Decimal("0.25"),
    }

    first = derive_model_call_cost(**arguments)  # type: ignore[arg-type]
    second = derive_model_call_cost(**arguments)  # type: ignore[arg-type]

    assert first == second
    assert first == Decimal("0.03754125")


def test_cost_is_serialized_as_a_string_with_its_source() -> None:
    runtime = _priced_runtime()
    runtime.adapter().add_response(
        usage=ModelUsage(input_tokens=1000000, output_tokens=1000000)
    )

    payload = json.loads(json.dumps(runtime.gateway.execute(_request()).to_dict()))

    assert payload["usage"]["cost"] == "7.50000000"
    assert payload["usage"]["cost_source"] == "catalog_derived"


def test_accounting_introduces_no_budget_or_dashboard_surface() -> None:
    runtime = _runtime()

    for forbidden in (
        "budget",
        "spend",
        "ledger",
        "dashboard",
        "monthly_cost",
        "alert_threshold",
    ):
        assert not hasattr(runtime.gateway, forbidden)
