"""Phase 10.53 — Neurodivergence Domain registration tests.

The DomainDefinition is canonical, and registration is atomic: all inputs are
validated before the first mutation, and any failure after a mutation restores
every touched registry to its exact pre-call state.  No new registry is
introduced and no global mutable state is modified.
"""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind
from cmm.domains.neurodivergence.definition import (
    NEURODIVERGENCE_DOMAIN_ID,
    NEURODIVERGENCE_DOMAIN_VERSION,
    NEURODIVERGENCE_MANIFEST_ID,
    build_neurodivergence_domain_definition,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry

PROFILE_ID = "neurodivergence.profile"


class _FakeImplementation:
    def __init__(self, definition):
        self.definition = definition

    def execute(self, request, memory_view=None):
        return {"success": True, "output": {}, "effects": ()}


class _FailAfterN:
    """Wrapper that allows N successful registrations, then raises."""

    def __init__(self, inner, fail_after: int):
        self._inner = inner
        self._fail_after = fail_after
        self._count = 0

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def register(self, *args, **kwargs):
        if self._count >= self._fail_after:
            raise RuntimeError("simulated post-mutation failure")
        self._count += 1
        return self._inner.register(*args, **kwargs)


def _registries():
    return {
        "domain_registry": DomainRegistry(),
        "profile_registry": InMemoryDomainProfileRegistry(),
        "resource_registry": InMemoryDomainResourceRegistry(),
        "rule_registry": InMemoryReasoningRuleRegistry(),
        "operation_registry": InMemoryDomainOperationRegistry(
            InMemoryAgentOperationRegistry()
        ),
        "workflow_registry": InMemoryDomainWorkflowRegistry(InMemoryWorkflowRegistry()),
        "permission_registry": DomainPermissionRegistry(),
    }


def _snapshot_all(registries):
    return {name: registry.snapshot_state() for name, registry in registries.items()}


def _assert_snapshots_equal(before, after):
    assert set(before.keys()) == set(after.keys())
    for key in before:
        assert before[key] == after[key], f"snapshot mismatch for {key}"


def _assert_no_neurodivergence_entries(registries):
    assert registries["domain_registry"].get(NEURODIVERGENCE_DOMAIN_ID) is None
    assert registries["profile_registry"].get(PROFILE_ID) is None
    assert registries["resource_registry"].list_all() == ()
    assert registries["rule_registry"].list_all() == ()
    assert registries["operation_registry"].list_definitions() == ()
    assert (
        registries["workflow_registry"].list_for_domain(NEURODIVERGENCE_DOMAIN_ID) == ()
    )
    assert (
        registries["permission_registry"].active_for_domain(NEURODIVERGENCE_DOMAIN_ID)
        is None
    )


# ── Definition ───────────────────────────────────────────────────────────────


def test_definition_identity_and_metadata():
    definition = build_neurodivergence_domain_definition()

    assert isinstance(definition, DomainDefinition)
    assert str(definition.id) == "domain:neurodivergence"
    assert definition.kind is DomainKind.PERSONAL
    assert definition.version == NEURODIVERGENCE_DOMAIN_VERSION
    assert definition.version == "1.0.0"
    assert definition.manifest_id == NEURODIVERGENCE_MANIFEST_ID
    assert definition.enabled is True
    assert definition.metadata is not None
    assert "neurodivergence" in definition.metadata.tags


def test_definition_attaches_every_approved_surface():
    definition = build_neurodivergence_domain_definition()

    assert definition.reasoning_profile == "NeurodivergenceProfile"
    assert tuple(definition.resources) == _resource_ids()
    assert tuple(definition.rules) == _rule_ids()
    assert len(definition.operations) == 8
    assert len(definition.workflows) == 8
    assert definition.permissions == ("domain-permission:neurodivergence:1.0.0",)
    assert definition.validators == ()
    assert definition.benchmark_suites
    assert definition.quality_metrics
    assert definition.knowledge_package_schema is not None
    assert definition.privacy_policy is not None
    assert definition.model_policy is not None
    assert definition.presentation_policy


def _resource_ids():
    from cmm.domains.neurodivergence.catalog import NEURODIVERGENCE_RESOURCE_IDS

    return NEURODIVERGENCE_RESOURCE_IDS


def _rule_ids():
    from cmm.domains.neurodivergence.catalog import NEURODIVERGENCE_RULE_IDS

    return NEURODIVERGENCE_RULE_IDS


def test_definition_model_policy_is_provider_agnostic():
    definition = build_neurodivergence_domain_definition()
    serialized = str(definition.model_policy.to_dict()).casefold()

    assert "provider_id" not in serialized
    assert "model_id" not in serialized
    assert "openai" not in serialized
    assert "anthropic" not in serialized


def test_definition_declares_no_sibling_implementation_dependency():
    """Cross-domain support is registry/permission-driven, never an import."""
    definition = build_neurodivergence_domain_definition()

    for sibling in (
        "domain:health",
        "domain:mental-health",
        "domain:university",
        "domain:relationships",
    ):
        assert sibling not in definition.dependencies
        assert sibling not in definition.optional_dependencies
    assert definition.dependencies == ()
    assert definition.optional_dependencies == ()
    assert definition.conflicts == ()


def test_definition_offers_its_own_reasoning_capabilities():
    definition = build_neurodivergence_domain_definition()
    names = {capability.name for capability in definition.capabilities}

    for capability in (
        "exploratory_neurodevelopmental_reasoning",
        "developmental_history_review",
        "assessment_evidence_organization",
        "differential_overlap_reasoning",
        "functional_impact_review",
        "professional_assessment_preparation",
    ):
        assert capability in names, capability
    assert all(
        str(capability.provided_by) == NEURODIVERGENCE_DOMAIN_ID
        for capability in definition.capabilities
    )


def test_definition_serialization_is_deterministic():
    first = build_neurodivergence_domain_definition()
    second = build_neurodivergence_domain_definition()

    assert first.to_dict() == second.to_dict()
    assert DomainDefinition.from_dict(first.to_dict()) == first


def test_package_export_surface_is_side_effect_free():
    import cmm.domains.neurodivergence as package

    for name in (
        "NEURODIVERGENCE_DOMAIN_ID",
        "NEURODIVERGENCE_PROFILE_NAME",
        "build_neurodivergence_domain_definition",
        "register_neurodivergence_domain",
    ):
        assert hasattr(package, name), name
    # No global registration side effect on import.
    assert DomainRegistry().list() == ()


# ── Registration ─────────────────────────────────────────────────────────────


def test_registration_registers_all_components():
    from cmm.domains.neurodivergence.integration import register_neurodivergence_domain

    registries = _registries()
    result = register_neurodivergence_domain(**registries)

    assert result.definition.id == NEURODIVERGENCE_DOMAIN_ID
    assert registries["domain_registry"].get(NEURODIVERGENCE_DOMAIN_ID) is not None
    assert registries["profile_registry"].get(PROFILE_ID) is not None
    assert len(registries["resource_registry"].list_all()) == 10
    assert len(registries["rule_registry"].list_all()) == 14
    assert len(registries["operation_registry"].list_definitions()) == 8
    assert (
        len(registries["workflow_registry"].list_for_domain(NEURODIVERGENCE_DOMAIN_ID))
        == 8
    )
    assert (
        registries["permission_registry"].active_for_domain(NEURODIVERGENCE_DOMAIN_ID)
        is not None
    )


def test_registration_leaves_operations_unavailable_by_default():
    from cmm.domains.neurodivergence.integration import register_neurodivergence_domain

    registries = _registries()
    register_neurodivergence_domain(**registries)

    definitions = registries["operation_registry"].list_definitions()
    assert definitions
    for operation in definitions:
        assert operation.enabled is False


def test_registration_accepts_injected_implementations():
    from cmm.domains.neurodivergence.integration import register_neurodivergence_domain
    from cmm.domains.neurodivergence.operations import (
        build_neurodivergence_operation_definitions,
    )

    registries = _registries()
    implementations = {
        operation.operation_id: _FakeImplementation(operation)
        for operation in build_neurodivergence_operation_definitions()
    }
    register_neurodivergence_domain(
        **registries, operation_implementations=implementations
    )

    for operation in registries["operation_registry"].list_definitions():
        assert operation.enabled is True


def test_duplicate_registration_is_rejected_before_mutation():
    from cmm.domains.errors import DomainError
    from cmm.domains.neurodivergence.integration import register_neurodivergence_domain

    registries = _registries()
    register_neurodivergence_domain(**registries)
    before = _snapshot_all(registries)

    with pytest.raises(DomainError):
        register_neurodivergence_domain(**registries)

    _assert_snapshots_equal(before, _snapshot_all(registries))


@pytest.mark.parametrize(
    "fail_registry",
    ("domain_registry", "resource_registry", "rule_registry", "permission_registry"),
)
def test_post_mutation_failure_restores_every_registry(fail_registry):
    from cmm.domains.neurodivergence.integration import register_neurodivergence_domain

    registries = _registries()
    plain_snapshots = _snapshot_all(registries)
    registries[fail_registry] = _FailAfterN(registries[fail_registry], fail_after=0)

    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_neurodivergence_domain(**registries)

    _assert_snapshots_equal(plain_snapshots, _snapshot_all(registries))
    _assert_no_neurodivergence_entries(registries)


def test_partial_failure_after_earlier_registrations_restores_them():
    from cmm.domains.neurodivergence.integration import register_neurodivergence_domain

    registries = _registries()
    plain_snapshots = _snapshot_all(registries)
    # Allow the Domain, profile, resources and rules to register, then fail.
    registries["permission_registry"] = _FailAfterN(
        registries["permission_registry"], fail_after=0
    )

    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_neurodivergence_domain(**registries)

    _assert_snapshots_equal(plain_snapshots, _snapshot_all(registries))
    _assert_no_neurodivergence_entries(registries)


def test_registration_rejects_undeclared_operation_implementations_before_mutation():
    from cmm.domains.neurodivergence.integration import register_neurodivergence_domain

    registries = _registries()
    before = _snapshot_all(registries)

    with pytest.raises(ValueError, match="undeclared operations"):
        register_neurodivergence_domain(
            **registries,
            operation_implementations={"neurodivergence.not_an_operation": object()},
        )

    _assert_snapshots_equal(before, _snapshot_all(registries))
    _assert_no_neurodivergence_entries(registries)


def test_registration_touches_only_the_supplied_registries():
    from cmm.domains.neurodivergence.integration import register_neurodivergence_domain

    registries = _registries()
    result = register_neurodivergence_domain(
        domain_registry=registries["domain_registry"]
    )

    assert result.definition.id == NEURODIVERGENCE_DOMAIN_ID
    assert registries["domain_registry"].get(NEURODIVERGENCE_DOMAIN_ID) is not None
    # Skipped registries stay untouched.
    assert registries["resource_registry"].list_all() == ()
    assert registries["rule_registry"].list_all() == ()
