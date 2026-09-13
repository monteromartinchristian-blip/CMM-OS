"""Import regression for the route-aware provider registry contracts."""

from __future__ import annotations

from kernel import llm
from kernel.llm import (
    FIRST_WAVE_AUTH_SCHEME,
    KNOWN_API_STYLES,
    BillingClass,
    CapabilityConfidence,
    ConnectionStatus,
    DiscoverableModelClient,
    ModelDiscoveryResult,
    ModelRoute,
    ModelRouteCatalog,
    ProviderConnection,
    ProviderConnectionRegistry,
    ProviderManifest,
    ProviderManifestRegistry,
    RouteCapabilityState,
    discover_models,
    register_first_wave_manifests,
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

DISCOVERY_CONTRACTS = {
    "FIRST_WAVE_AUTH_SCHEME": FIRST_WAVE_AUTH_SCHEME,
    "KNOWN_API_STYLES": KNOWN_API_STYLES,
    "ProviderManifest": ProviderManifest,
    "ProviderManifestRegistry": ProviderManifestRegistry,
    "register_first_wave_manifests": register_first_wave_manifests,
    "DiscoverableModelClient": DiscoverableModelClient,
    "ModelDiscoveryResult": ModelDiscoveryResult,
    "discover_models": discover_models,
}


def test_registry_contracts_are_importable() -> None:
    for name in REGISTRY_CONTRACTS:
        assert getattr(llm, name) is not None


def test_registry_contracts_are_public() -> None:
    expected = set(REGISTRY_CONTRACTS)

    assert expected <= set(llm.__all__)


def test_discovery_contracts_are_importable() -> None:
    for name in DISCOVERY_CONTRACTS:
        assert getattr(llm, name) is not None


def test_discovery_contracts_are_public() -> None:
    expected = set(DISCOVERY_CONTRACTS)

    assert expected <= set(llm.__all__)
