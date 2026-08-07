"""Tests for General Domain integration with catalogs and registries."""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.errors import (
    DomainOperationRegistryError,
    DomainProfileRegistryError,
    DomainRegistryConflict,
    DomainResourceRegistryError,
)
from cmm.domains.general import (
    GENERAL_DOMAIN_ID,
    GENERAL_RESOURCE_IDS,
    GENERAL_RULE_IDS,
    GENERAL_WORKFLOW_IDS,
    build_general_operation_definitions,
    build_general_workflow_definitions,
    register_general_domain,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.errors import WorkflowRegistryError
from cmm.workflows.registry import InMemoryWorkflowRegistry


class _FakeImplementation:
    def __init__(self, definition):
        self.definition = definition

    def execute(self, request):
        return {"success": True, "output": {}, "effects": ()}


class _CountingDomainRegistry(DomainRegistry):
    """Test-local spy that counts register() calls without touching production."""

    def __init__(self):
        super().__init__()
        self.register_calls = 0

    def register(self, definition):
        self.register_calls += 1
        return super().register(definition)


def _registries():
    return {
        "domain_registry": DomainRegistry(),
        "profile_registry": InMemoryDomainProfileRegistry(),
        "resource_registry": InMemoryDomainResourceRegistry(),
        "rule_registry": InMemoryReasoningRuleRegistry(),
        "operation_registry": InMemoryDomainOperationRegistry(
            InMemoryAgentOperationRegistry()
        ),
        "workflow_registry": InMemoryDomainWorkflowRegistry(
            InMemoryWorkflowRegistry()
        ),
        "permission_registry": DomainPermissionRegistry(),
    }


def _implementations():
    return {
        op.operation_id: _FakeImplementation(op)
        for op in build_general_operation_definitions()
    }


def test_complete_registration():
    registries = _registries()
    operation_registry = registries.pop("operation_registry")
    implementations = _implementations()
    result = register_general_domain(
        **registries,
        operation_registry=operation_registry,
        operation_implementations=implementations,
    )
    assert result.definition.id.slug == "general"
    assert registries["domain_registry"].get(GENERAL_DOMAIN_ID) is not None
    assert len(registries["resource_registry"].list_all()) == 9
    assert len(registries["rule_registry"].list_all()) == 6
    assert len(operation_registry.list_definitions()) == 8
    assert len(registries["workflow_registry"].list_for_domain(GENERAL_DOMAIN_ID)) == 4
    assert registries["permission_registry"].get(
        "domain-permission:general:1.0.0"
    ) is not None


def test_duplicate_registration_raises():
    registries = _registries()
    registries.pop("operation_registry")
    register_general_domain(**registries)
    with pytest.raises(DomainRegistryConflict):
        register_general_domain(**registries)


def test_partial_registration_failure():
    registries = _registries()
    registries.pop("operation_registry")
    # Register domain first, then try to register again with a duplicate
    register_general_domain(**registries)
    with pytest.raises(DomainRegistryConflict):
        register_general_domain(**registries)


def test_exact_catalog_contents():
    registries = _registries()
    registries.pop("operation_registry")
    register_general_domain(**registries)
    resource_ids = {r.id for r in registries["resource_registry"].list_all()}
    assert resource_ids == set(GENERAL_RESOURCE_IDS)
    rule_ids = {r.definition.id for r in registries["rule_registry"].list_all()}
    assert rule_ids == set(GENERAL_RULE_IDS)
    wf_ids = {
        w.workflow_id
        for w in registries["workflow_registry"].list_for_domain(GENERAL_DOMAIN_ID)
    }
    assert wf_ids == set(GENERAL_WORKFLOW_IDS)


def test_deterministic_ordering():
    registries = _registries()
    registries.pop("operation_registry")
    register_general_domain(**registries)
    resources = registries["resource_registry"].list_all()
    assert [r.id for r in resources] == sorted(r.id for r in resources)


def test_no_import_time_registration():
    import sys

    import cmm.domains.general  # noqa: F401

    after = set(sys.modules)
    assert "cmm.domains.general" in after
    # No global registries should be modified by import
    assert "cmm.domains.general" in after


# ── Atomicity tests ───────────────────────────────────────────────────────────


def test_missing_operation_implementation_is_atomic():
    """Missing implementation registers operations as UNAVAILABLE (fail-closed)."""
    from cmm.domains.enums import DomainOperationStatus
    from cmm.domains.operation_availability import (
        DomainOperationAvailabilityContext,
        DomainOperationAvailabilityResolver,
    )

    registries = _registries()
    operation_registry = registries.pop("operation_registry")
    # Provide implementations for only some operations
    ops = build_general_operation_definitions()
    partial = {ops[0].operation_id: _FakeImplementation(ops[0])}

    result = register_general_domain(
        **registries,
        operation_registry=operation_registry,
        operation_implementations=partial,
    )
    assert result.definition.id.slug == "general"

    # All 8 operations are registered; the 7 without implementations are UNAVAILABLE
    assert len(operation_registry.list_definitions()) == 8
    resolver = DomainOperationAvailabilityResolver()
    context = DomainOperationAvailabilityContext(
        primary_domain_id="domain:general",
        granted_permissions=("resource.read", "memory.read"),
        available_resources=("general.user_message",),
    )
    for op in operation_registry.list_definitions():
        availability = resolver.resolve(op, context)
        if op.operation_id == ops[0].operation_id:
            # The injected implementation is available
            assert availability.status is DomainOperationStatus.AVAILABLE
        else:
            assert availability.status is DomainOperationStatus.UNAVAILABLE
            assert "availability.disabled" in availability.reason_codes


def test_duplicate_domain_id_is_atomic():
    """Duplicate domain ID must fail before any mutation."""
    registries = _registries()
    registries.pop("operation_registry")
    from cmm.domains.general.definition import build_general_domain_definition

    # Pre-register the domain definition
    registries["domain_registry"].register(build_general_domain_definition())

    with pytest.raises(DomainRegistryConflict):
        register_general_domain(**registries)

    # No other registry should have been mutated
    assert registries["profile_registry"].get("general.profile") is None
    assert registries["resource_registry"].list_all() == ()
    assert registries["rule_registry"].list_all() == ()


def test_duplicate_resource_id_is_atomic():
    """Duplicate resource ID must fail before any mutation."""
    registries = _registries()
    registries.pop("operation_registry")
    from cmm.domains.general.resources import build_general_resource_definitions

    # Pre-register just one resource
    resources = build_general_resource_definitions()
    registries["resource_registry"].register(resources[0])

    with pytest.raises(DomainResourceRegistryError):
        register_general_domain(**registries)

    # No other registry should have been mutated
    assert registries["domain_registry"].get(GENERAL_DOMAIN_ID) is None
    assert registries["profile_registry"].get("general.profile") is None
    assert registries["rule_registry"].list_all() == ()


def test_duplicate_operation_id_is_atomic():
    """Duplicate operation ID must fail before any mutation."""
    registries = _registries()
    operation_registry = registries.pop("operation_registry")
    ops = build_general_operation_definitions()

    # Pre-register just one operation
    operation_registry.register(ops[0], _FakeImplementation(ops[0]))

    with pytest.raises(DomainOperationRegistryError):
        register_general_domain(
            **registries,
            operation_registry=operation_registry,
            operation_implementations=_implementations(),
        )

    # No other registry should have been mutated
    assert registries["domain_registry"].get(GENERAL_DOMAIN_ID) is None
    assert registries["profile_registry"].get("general.profile") is None
    assert registries["resource_registry"].list_all() == ()
    assert registries["rule_registry"].list_all() == ()


def test_retry_succeeds_after_fix():
    """After a failed registration, fixing the issue allows full registration."""
    registries = _registries()
    operation_registry = registries.pop("operation_registry")

    # First attempt registers operations as UNAVAILABLE (no implementations)
    result = register_general_domain(
        **registries,
        operation_registry=operation_registry,
    )
    assert result.definition.id.slug == "general"
    assert len(operation_registry.list_definitions()) == 8

    # A second registration with the same domain ID fails (duplicate)
    with pytest.raises(DomainRegistryConflict):
        register_general_domain(
            **registries,
            operation_registry=operation_registry,
            operation_implementations=_implementations(),
        )


def test_preexisting_entries_conserved():
    """Pre-existing entries in registries must survive validation failures."""
    registries = _registries()
    registries.pop("operation_registry")

    # Pre-register an unrelated resource
    from cmm.domains.general.resources import build_general_resource_definitions

    resources = build_general_resource_definitions()

    # Use a different resource first
    from cmm.cognitive.enums import SensitivityLevel
    from cmm.domains.resource_contracts import (
        DomainResourceDefinition,
        DomainResourceTemporalPolicy,
    )

    unrelated = DomainResourceDefinition(
        id="unrelated.resource",
        kind="unrelated",
        domain_id="domain:unrelated",
        adapter="cognitive.unrelated",
        entity_types=("unrelated",),
        default_sensitivity=SensitivityLevel.INTERNAL,
        default_reliability=0.5,
        temporal_policy=DomainResourceTemporalPolicy(
            effective_date_required=False,
            expiration_required=False,
            historical_allowed=True,
        ),
        metadata={"phase": "test"},
    )
    registries["resource_registry"].register(unrelated)

    # Now try to register general domain with a duplicate resource
    registries["resource_registry"].register(resources[0])

    with pytest.raises(DomainResourceRegistryError):
        register_general_domain(**registries)

    # The unrelated resource must still exist
    assert registries["resource_registry"].get("unrelated.resource") is not None
    # But the general domain entries must not exist
    assert registries["domain_registry"].get(GENERAL_DOMAIN_ID) is None
    assert registries["profile_registry"].get("general.profile") is None


def test_deterministic_atomic_failure():
    """The same failure reproduces deterministically."""
    registries = _registries()
    operation_registry = registries.pop("operation_registry")

    # First registration succeeds with operations UNAVAILABLE
    register_general_domain(
        **registries,
        operation_registry=operation_registry,
    )
    assert registries["domain_registry"].get(GENERAL_DOMAIN_ID) is not None

    # A second registration with the same domain ID fails deterministically
    with pytest.raises(DomainRegistryConflict):
        register_general_domain(
            **registries,
            operation_registry=operation_registry,
        )
    with pytest.raises(DomainRegistryConflict):
        register_general_domain(
            **registries,
            operation_registry=operation_registry,
        )
# ── Validation-first: operation implementation mismatch ──────────────────────


def test_mismatched_operation_implementation_fails_before_any_mutation():
    """An implementation whose definition mismatches its declared operation must
    fail before the first mutation (domain registry must never be touched)."""
    registries = _registries()
    operation_registry = registries.pop("operation_registry")
    counting_domain = _CountingDomainRegistry()
    registries["domain_registry"] = counting_domain

    ops = build_general_operation_definitions()
    declared, other = ops[0], ops[1]
    assert other != declared
    # Correct operation_id, but the implementation claims a *different* valid
    # DomainOperationDefinition.
    mismatched = {declared.operation_id: _FakeImplementation(other)}

    with pytest.raises(DomainOperationRegistryError):
        register_general_domain(
            **registries,
            operation_registry=operation_registry,
            operation_implementations=mismatched,
        )

    assert counting_domain.register_calls == 0
    assert registries["profile_registry"].get("general.profile") is None
    assert registries["resource_registry"].list_all() == ()
    assert registries["rule_registry"].list_all() == ()


def test_invalid_operation_execute_signature_fails_before_any_mutation():
    """An implementation with a correct definition but an invalid execute
    signature must fail before the first mutation."""
    registries = _registries()
    operation_registry = registries.pop("operation_registry")
    counting_domain = _CountingDomainRegistry()
    registries["domain_registry"] = counting_domain

    ops = build_general_operation_definitions()
    declared = ops[0]

    class _InvalidSignatureImplementation:
        def __init__(self, definition):
            self.definition = definition

        def execute(self, request, *args):  # invalid: *args
            return {}

    with pytest.raises(DomainOperationRegistryError):
        register_general_domain(
            **registries,
            operation_registry=operation_registry,
            operation_implementations={
                declared.operation_id: _InvalidSignatureImplementation(declared)
            },
        )

    assert counting_domain.register_calls == 0
    assert registries["profile_registry"].get("general.profile") is None
    assert registries["resource_registry"].list_all() == ()
    assert registries["rule_registry"].list_all() == ()


# ── Validation-first: profile domain collision ───────────────────────────────


def test_existing_profile_for_general_domain_fails_before_any_mutation():
    """A profile already present for the general domain (different id) must fail
    before any mutation via the domain collision, not via the profile id."""
    from cmm.domains.profile_contracts import DomainProfileDefinition

    registries = _registries()
    registries.pop("operation_registry")
    counting_domain = _CountingDomainRegistry()
    registries["domain_registry"] = counting_domain

    # Different id, same domain -> isolates the domain collision.
    existing = DomainProfileDefinition(
        id="other.general.profile",
        domain_id=GENERAL_DOMAIN_ID,
        profile_name="OtherGeneral",
    )
    registries["profile_registry"].register(existing)

    with pytest.raises(DomainProfileRegistryError):
        register_general_domain(**registries)

    assert counting_domain.register_calls == 0
    assert registries["profile_registry"].get("other.general.profile") is not None
    assert registries["resource_registry"].list_all() == ()
    assert registries["rule_registry"].list_all() == ()
# ── Validation-first: nested common registry collisions ──────────────────────


def test_common_operation_collision_fails_before_any_mutation():
    """A key already present in the nested common operation registry (without a
    corresponding Domain definition) must fail before the first mutation."""
    registries = _registries()
    operation_registry = registries.pop("operation_registry")
    counting_domain = _CountingDomainRegistry()
    registries["domain_registry"] = counting_domain

    operation = build_general_operation_definitions()[0]

    # Pre-register DIRECTLY in the common registry, bypassing the Domain
    # operation registry entirely.
    operation_registry.common_registry.register(
        operation.to_operation_descriptor()
    )

    # Precondition: the Domain registry is untouched, so the current Phase 1
    # Domain-duplicate validation cannot see this collision.
    assert operation_registry.list_definitions() == ()

    with pytest.raises(DomainOperationRegistryError):
        register_general_domain(
            **registries,
            operation_registry=operation_registry,
            operation_implementations=_implementations(),
        )

    # The collision must be detected BEFORE the first mutation.
    assert counting_domain.register_calls == 0
    assert registries["profile_registry"].get("general.profile") is None
    assert registries["resource_registry"].list_all() == ()
    assert registries["rule_registry"].list_all() == ()


def test_common_workflow_collision_fails_before_any_mutation():
    """A key already present in the nested common workflow registry (without a
    corresponding Domain workflow definition) must fail before the first
    mutation."""
    registries = _registries()
    # Isolate the workflow case: omit the operation registry, but keep the
    # workflow registry.
    registries.pop("operation_registry")
    workflow_registry = registries["workflow_registry"]
    counting_domain = _CountingDomainRegistry()
    registries["domain_registry"] = counting_domain

    workflow = build_general_workflow_definitions()[0]

    # Pre-register DIRECTLY in the common workflow registry.
    workflow_registry.common_registry.register(workflow.to_common())

    # Precondition: no Domain workflow definition exists locally, so the
    # current Phase 1 Domain-duplicate validation cannot see this collision.
    assert workflow_registry.list_for_domain(GENERAL_DOMAIN_ID) == ()

    with pytest.raises(WorkflowRegistryError):
        register_general_domain(**registries)

    # The collision must be detected BEFORE the first mutation.
    assert counting_domain.register_calls == 0
    assert registries["profile_registry"].get("general.profile") is None
    assert registries["resource_registry"].list_all() == ()
    assert registries["rule_registry"].list_all() == ()
