"""Tests for Phase 10.8 – Composition Public API exports."""

from __future__ import annotations

from cmm import domains


def test_expected_exports_present():
    expected = [
        "DomainCompositionStatus",
        "DomainConflictPolicy",
        "DomainCompositionPolicy",
        "DomainCompositionItem",
        "DomainCompositionDecision",
        "DomainCompositionConflict",
        "EffectiveReasoningProfile",
        "PermissionComposition",
        "PresentationComposition",
        "DomainComposition",
        "DomainComposer",
        "DefaultDomainComposer",
        "DomainCompositionError",
        "DomainCompositionContractError",
        "DomainCompositionSerializationError",
        "DomainCompositionConfigurationError",
        "DomainCompositionExecutionError",
    ]
    for name in expected:
        assert hasattr(domains, name), f"Missing export: {name}"


def test_forbidden_exports_absent():
    forbidden = [
        "CrossDomainEngine",
        "DomainCompositionExecutor",
        "RegistryDomainComposer",
        "WorkflowExecutor",
        "CognitiveDomainEngine",
    ]
    for name in forbidden:
        assert not hasattr(domains, name), f"Forbidden export present: {name}"


def test_all_contains_phase10_8_exports():
    assert "DomainCompositionStatus" in domains.__all__
    assert "DomainConflictPolicy" in domains.__all__
    assert "DomainCompositionPolicy" in domains.__all__
    assert "DomainComposition" in domains.__all__
    assert "DomainComposer" in domains.__all__
    assert "DefaultDomainComposer" in domains.__all__
    assert "DomainCompositionError" in domains.__all__
    assert "EffectiveReasoningProfile" in domains.__all__
    assert "PermissionComposition" in domains.__all__
    assert "PresentationComposition" in domains.__all__


def test_previous_phase_apis_remain():
    """Ensure Phase 10.7 and earlier APIs are still accessible."""
    assert hasattr(domains, "DomainResolutionResult")
    assert hasattr(domains, "DomainResolver")
    assert hasattr(domains, "DefaultDomainResolver")
    assert hasattr(domains, "DomainDefinition")
    assert hasattr(domains, "DomainId")
    assert hasattr(domains, "DomainKind")


def test_no_runtime_imports():
    """Assert source/import boundaries: no agent_runtime, cognitive imports."""

    # Check that composition modules don't import from forbidden packages
    forbidden_modules = [
        "cmm.agent_runtime",
        "cmm.cognitive",
    ]

    composition_modules = [
        "cmm.domains.composer",
        "cmm.domains.composition_contracts",
        "cmm.domains.composition_items",
        "cmm.domains.composition_permissions",
        "cmm.domains.composition_conflicts",
    ]

    for mod_name in composition_modules:
        mod = __import__(mod_name, fromlist=["__name__"])
        mod_source = str(vars(mod))
        for forbidden in forbidden_modules:
            assert forbidden not in mod_source, (
                f"{mod_name} imports forbidden package {forbidden}"
            )


def test_composition_contracts_importable():
    from cmm.domains.composition_contracts import (
        DomainComposition,
        DomainCompositionPolicy,
    )

    assert DomainComposition is not None
    assert DomainCompositionPolicy is not None


def test_composer_importable():
    from cmm.domains.composer import DefaultDomainComposer, DomainComposer

    assert DefaultDomainComposer is not None
    assert DomainComposer is not None
