"""Import regression for the route-aware provider registry contracts."""

from __future__ import annotations

from kernel import llm
from kernel.llm import (
    BillingClass,
    CapabilityConfidence,
    ConnectionStatus,
    ModelRoute,
    ModelRouteCatalog,
    ProviderConnection,
    ProviderConnectionRegistry,
    RouteCapabilityState,
)

REGISTRY_CONTRACTS = {
    "BillingClass": BillingClass,
    "ConnectionStatus": ConnectionStatus,
    "ProviderConnection": ProviderConnection,
    "ProviderConnectionRegistry": ProviderConnectionRegistry,
    "CapabilityConfidence": CapabilityConfidence,
    "RouteCapabilityState": RouteCapabilityState,
    "ModelRoute": ModelRoute,
    "ModelRouteCatalog": ModelRouteCatalog,
}


def test_registry_contracts_are_importable() -> None:
    for name in REGISTRY_CONTRACTS:
        assert getattr(llm, name) is not None


def test_registry_contracts_are_public() -> None:
    expected = set(REGISTRY_CONTRACTS)

    assert expected <= set(llm.__all__)
