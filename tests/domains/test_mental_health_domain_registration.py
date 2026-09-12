"""Phase 10.52 — Mental Health Domain registration tests.

The DomainDefinition is canonical, and registration is atomic: all inputs are
validated before the first mutation, and any failure after a mutation restores
every touched registry to its exact pre-call state.
"""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind
from cmm.domains.mental_health.definition import (
    MENTAL_HEALTH_DOMAIN_ID,
    MENTAL_HEALTH_DOMAIN_VERSION,
    MENTAL_HEALTH_MANIFEST_ID,
    build_mental_health_domain_definition,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry

PROFILE_ID = "mental-health.profile"


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


def _assert_no_mental_health_entries(registries):
    assert registries["domain_registry"].get(MENTAL_HEALTH_DOMAIN_ID) is None
    assert registries["profile_registry"].get(PROFILE_ID) is None
    assert registries["resource_registry"].list_all() == ()
    assert registries["rule_registry"].list_all() == ()
    assert registries["operation_registry"].list_definitions() == ()
    assert (
        registries["workflow_registry"].list_for_domain(MENTAL_HEALTH_DOMAIN_ID) == ()
    )
    assert (
        registries["permission_registry"].active_for_domain(MENTAL_HEALTH_DOMAIN_ID)
        is None
    )


# ── Definition ───────────────────────────────────────────────────────────────


def test_definition_identity_and_metadata():
    definition = build_mental_health_domain_definition()
    assert isinstance(definition, DomainDefinition)
    assert str(definition.id) == "domain:mental-health"
    assert definition.kind is DomainKind.PERSONAL
    assert definition.version == MENTAL_HEALTH_DOMAIN_VERSION
    assert definition.manifest_id == MENTAL_HEALTH_MANIFEST_ID
    assert definition.enabled is True


def test_definition_attaches_every_approved_surface():
    definition = build_mental_health_domain_definition()
    assert definition.reasoning_profile == "MentalHealthProfile"
    assert definition.resources
    assert definition.rules
    assert len(definition.operations) == 8
    assert len(definition.workflows) == 8
    assert definition.benchmark_suites
    assert definition.quality_metrics
    assert definition.knowledge_package_schema is not None
    assert definition.privacy_policy is not None
    assert definition.model_policy is not None
    # Provider/model agnostic: no concrete identifiers are embedded.
    serialized = str(definition.model_policy.to_dict())
    assert "provider" not in serialized
    assert "model_id" not in serialized


def test_definition_has_no_neurodivergence_dependency():
    definition = build_mental_health_domain_definition()
    assert "domain:neurodivergence" not in definition.dependencies
    assert "domain:neurodivergence" not in definition.optional_dependencies
    assert not any(
        capability.name.startswith("neurodivergence")
        for capability in definition.capabilities
    )


def test_definition_serialization_is_deterministic():
    first = build_mental_health_domain_definition()
    second = build_mental_health_domain_definition()
    assert first.to_dict() == second.to_dict()
    assert DomainDefinition.from_dict(first.to_dict()) == first


# ── Registration ─────────────────────────────────────────────────────────────


def test_registration_registers_all_components():
    from cmm.domains.mental_health.integration import register_mental_health_domain

    registries = _registries()
    result = register_mental_health_domain(**registries)

    assert result.definition.id == MENTAL_HEALTH_DOMAIN_ID
    assert registries["domain_registry"].get(MENTAL_HEALTH_DOMAIN_ID) is not None
    assert registries["profile_registry"].get(PROFILE_ID) is not None
    assert len(registries["resource_registry"].list_all()) == 10
    assert len(registries["rule_registry"].list_all()) == 13
    assert len(registries["operation_registry"].list_definitions()) == 8
    assert (
        len(registries["workflow_registry"].list_for_domain(MENTAL_HEALTH_DOMAIN_ID))
        == 8
    )
    assert (
        registries["permission_registry"].active_for_domain(MENTAL_HEALTH_DOMAIN_ID)
        is not None
    )


def test_registration_leaves_operations_unavailable_by_default():
    from cmm.domains.mental_health.integration import register_mental_health_domain

    registries = _registries()
    register_mental_health_domain(**registries)
    for operation in registries["operation_registry"].list_definitions():
        assert operation.enabled is False


def test_registration_accepts_injected_implementations():
    from cmm.domains.mental_health.integration import register_mental_health_domain
    from cmm.domains.mental_health.operations import (
        build_mental_health_operation_definitions,
    )

    registries = _registries()
    implementations = {
        operation.operation_id: _FakeImplementation(operation)
        for operation in build_mental_health_operation_definitions()
    }
    register_mental_health_domain(
        **registries, operation_implementations=implementations
    )
    for operation in registries["operation_registry"].list_definitions():
        assert operation.enabled is True


def test_duplicate_registration_is_rejected_before_mutation():
    from cmm.domains.errors import DomainError
    from cmm.domains.mental_health.integration import register_mental_health_domain

    registries = _registries()
    register_mental_health_domain(**registries)
    before = _snapshot_all(registries)
    with pytest.raises(DomainError):
        register_mental_health_domain(**registries)
    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)


@pytest.mark.parametrize(
    "fail_registry",
    ("domain_registry", "resource_registry", "rule_registry", "permission_registry"),
)
def test_post_mutation_failure_restores_every_registry(fail_registry):
    from cmm.domains.mental_health.integration import register_mental_health_domain

    registries = _registries()
    plain_snapshots = _snapshot_all(registries)
    registries[fail_registry] = _FailAfterN(registries[fail_registry], fail_after=0)

    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_mental_health_domain(**registries)

    # Every registry (including the failing one) equals its pre-call state.
    _assert_snapshots_equal(plain_snapshots, _snapshot_all(registries))
    _assert_no_mental_health_entries(registries)


def test_partial_failure_after_earlier_registrations_restores_them():
    from cmm.domains.mental_health.integration import register_mental_health_domain

    registries = _registries()
    plain_snapshots = _snapshot_all(registries)
    # Allow the Domain, profile, resources and rules to register, then fail.
    registries["permission_registry"] = _FailAfterN(
        registries["permission_registry"], fail_after=0
    )

    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_mental_health_domain(**registries)

    _assert_snapshots_equal(plain_snapshots, _snapshot_all(registries))
    _assert_no_mental_health_entries(registries)
