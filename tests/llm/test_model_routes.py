
from kernel.llm.model_routes import (
    CapabilityConfidence,
    ModelRoute,
    ModelRouteCatalog,
    RouteCapabilityState,
)


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
