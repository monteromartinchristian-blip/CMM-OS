"""Phase 10.20 — Health Domain validation-first adversarial matrix.

Proves that ``register_health_domain`` is genuinely **validation-first**: every
adversarial input is rejected *before the first mutation*.  The proof is a
counting spy on the domain registry asserting ``register_calls == 0`` — not a
rollback-style after-the-fact restoration.  The spy counts ``register()`` calls
on the *first* registry the integration would mutate, so a non-zero count would
mean the integration mutated before validating.

The matrix covers all 13 validation paths that can reject a Health Domain
registration, plus the permission prevalidation guarantee that an unrelated
error is never broadly swallowed as "already registered".
"""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.errors import (
    DomainOperationRegistryError,
    DomainPermissionRegistryError,
    DomainProfileRegistryError,
    DomainRegistryConflict,
    DomainResourceRegistryError,
)
from cmm.domains.health import (
    HEALTH_DOMAIN_ID,
    build_health_operation_definitions,
    build_health_resource_definitions,
    build_health_rules,
    build_health_workflow_definitions,
    register_health_domain,
)
from cmm.domains.health.permissions import build_health_permission_policy
from cmm.domains.health.profile import build_health_profile
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
    """Test-local spy that counts register() calls without touching production.

    This is the *first* registry mutated by ``register_health_domain``, so a
    ``register_calls == 0`` result is a direct proof of validation-first.
    """

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
        "workflow_registry": InMemoryDomainWorkflowRegistry(InMemoryWorkflowRegistry()),
        "permission_registry": DomainPermissionRegistry(),
    }


def _implementations():
    return {
        op.operation_id: _FakeImplementation(op)
        for op in build_health_operation_definitions()
    }


def _spy_registries():
    """Return registries with a counting domain spy, ready for a failing call."""
    registries = _registries()
    counting = _CountingDomainRegistry()
    registries["domain_registry"] = counting
    return registries, counting


def _baseline(registries):
    """Return the registry sizes *before* a call so an untouched registry can be
    verified unchanged afterward (validation-first proof)."""
    return {
        "profile": len(registries["profile_registry"].list_all()),
        "resource": len(registries["resource_registry"].list_all()),
        "rule": len(registries["rule_registry"].list_all()),
        "operation": len(registries["operation_registry"].list_definitions()),
        "workflow": len(
            registries["workflow_registry"].list_for_domain(HEALTH_DOMAIN_ID)
        ),
        "permission": len(registries["permission_registry"].list_policies()),
    }


def _assert_unchanged(registries, counting, baseline):
    """Assert validation-first: the domain-register spy was never called and no
    other registry gained entries relative to the pre-call baseline."""
    assert counting.register_calls == 0
    assert len(registries["profile_registry"].list_all()) == baseline["profile"]
    assert len(registries["resource_registry"].list_all()) == baseline["resource"]
    assert len(registries["rule_registry"].list_all()) == baseline["rule"]
    assert (
        len(registries["operation_registry"].list_definitions())
        == baseline["operation"]
    )
    assert (
        len(registries["workflow_registry"].list_for_domain(HEALTH_DOMAIN_ID))
        == baseline["workflow"]
    )
    assert (
        len(registries["permission_registry"].list_policies()) == baseline["permission"]
    )


# ── 1–13: every validation path rejects before the first mutation ────────────


def test_1_duplicate_domain_rejected_before_mutation():
    registries, counting = _spy_registries()
    register_health_domain(**registries, operation_implementations=_implementations())
    # The successful first call legitimately increments the spy; reset it so the
    # second (rejected) call must leave it at zero — the validation-first proof.
    counting.register_calls = 0

    baseline = _baseline(registries)
    with pytest.raises(DomainRegistryConflict):
        register_health_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_unchanged(registries, counting, baseline)


def test_2_duplicate_profile_id_rejected_before_mutation():
    registries, counting = _spy_registries()
    registries["profile_registry"].register(build_health_profile())

    baseline = _baseline(registries)
    with pytest.raises(DomainProfileRegistryError):
        register_health_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_unchanged(registries, counting, baseline)


def test_3_existing_profile_for_health_domain_rejected_before_mutation():
    """A profile already present for the health domain (different id) must fail
    via the domain collision, not via the profile id."""
    from cmm.domains.profile_contracts import DomainProfileDefinition

    registries, counting = _spy_registries()
    registries["profile_registry"].register(
        DomainProfileDefinition(
            id="other.health.profile",
            domain_id=HEALTH_DOMAIN_ID,
            profile_name="OtherHealth",
        )
    )

    baseline = _baseline(registries)
    with pytest.raises(DomainProfileRegistryError):
        register_health_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_unchanged(registries, counting, baseline)


def test_4_duplicate_resource_rejected_before_mutation():
    registries, counting = _spy_registries()
    registries["resource_registry"].register(build_health_resource_definitions()[0])

    baseline = _baseline(registries)
    with pytest.raises(DomainResourceRegistryError):
        register_health_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_unchanged(registries, counting, baseline)


def test_5_duplicate_rule_rejected_before_mutation():
    from cmm.cognitive.errors import ReasoningRuleRegistryError

    registries, counting = _spy_registries()
    registries["rule_registry"].register(build_health_rules()[0])

    baseline = _baseline(registries)
    with pytest.raises(ReasoningRuleRegistryError):
        register_health_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_unchanged(registries, counting, baseline)


def test_6_unknown_operation_implementation_rejected_before_mutation():
    registries, counting = _spy_registries()

    baseline = _baseline(registries)
    with pytest.raises(ValueError):
        register_health_domain(
            **registries,
            operation_implementations={"health.not_an_operation": object()},
        )
    _assert_unchanged(registries, counting, baseline)


def test_7_mismatched_operation_implementation_rejected_before_mutation():
    """An implementation whose definition mismatches its declared operation must
    fail before the first mutation."""
    registries, counting = _spy_registries()
    ops = build_health_operation_definitions()
    declared, other = ops[0], ops[1]

    baseline = _baseline(registries)
    with pytest.raises(DomainOperationRegistryError):
        register_health_domain(
            **registries,
            operation_implementations={
                declared.operation_id: _FakeImplementation(other)
            },
        )
    _assert_unchanged(registries, counting, baseline)


def test_8_invalid_operation_execute_signature_rejected_before_mutation():
    """An implementation with a correct definition but an invalid execute
    signature must fail before the first mutation."""
    registries, counting = _spy_registries()
    declared = build_health_operation_definitions()[0]

    class _InvalidSignatureImplementation:
        def __init__(self, definition):
            self.definition = definition

        def execute(self, request, *args):  # invalid: *args
            return {}

    baseline = _baseline(registries)
    with pytest.raises(DomainOperationRegistryError):
        register_health_domain(
            **registries,
            operation_implementations={
                declared.operation_id: _InvalidSignatureImplementation(declared)
            },
        )
    _assert_unchanged(registries, counting, baseline)


def test_9_duplicate_health_operation_rejected_before_mutation():
    registries, counting = _spy_registries()
    op_registry = registries["operation_registry"]
    op_registry.register(build_health_operation_definitions()[0])

    baseline = _baseline(registries)
    with pytest.raises(DomainOperationRegistryError):
        register_health_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_unchanged(registries, counting, baseline)


def test_10_common_operation_collision_rejected_before_mutation():
    """A key already present in the nested common operation registry (without a
    corresponding Domain definition) must fail before the first mutation."""
    registries, counting = _spy_registries()
    op_registry = registries["operation_registry"]
    operation = build_health_operation_definitions()[0]

    # Pre-register DIRECTLY in the common registry, bypassing the Domain
    # operation registry entirely.
    op_registry.common_registry.register(operation.to_operation_descriptor())
    assert op_registry.list_definitions() == ()

    baseline = _baseline(registries)
    with pytest.raises(DomainOperationRegistryError):
        register_health_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_unchanged(registries, counting, baseline)


def test_11_duplicate_health_workflow_rejected_before_mutation():
    registries, counting = _spy_registries()
    registries["workflow_registry"].register(build_health_workflow_definitions()[0])

    baseline = _baseline(registries)
    with pytest.raises(WorkflowRegistryError):
        register_health_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_unchanged(registries, counting, baseline)


def test_12_common_workflow_collision_rejected_before_mutation():
    """A key already present in the nested common workflow registry (without a
    corresponding Domain workflow definition) must fail before the first
    mutation."""
    registries, counting = _spy_registries()
    workflow_registry = registries["workflow_registry"]
    workflow = build_health_workflow_definitions()[0]

    workflow_registry.common_registry.register(workflow.to_common())
    assert workflow_registry.list_for_domain(HEALTH_DOMAIN_ID) == ()

    baseline = _baseline(registries)
    with pytest.raises(WorkflowRegistryError):
        register_health_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_unchanged(registries, counting, baseline)


def test_13_pre_registered_permission_policy_rejected_before_mutation():
    registries, counting = _spy_registries()
    registries["permission_registry"].register(build_health_permission_policy())

    baseline = _baseline(registries)
    with pytest.raises(DomainPermissionRegistryError):
        register_health_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_unchanged(registries, counting, baseline)


# ── Permission prevalidation: no broad swallow ───────────────────────────────


def test_permission_prevalidation_never_swallows_unrelated_error():
    """The permission prevalidation ``get`` call must not broadly swallow
    errors: an unrelated (non-not-found) error raised by the permission
    registry's ``get`` must propagate, not be treated as safe to proceed."""
    registries, counting = _spy_registries()

    class _ExplodingPermissionRegistry(DomainPermissionRegistry):
        def get(self, policy_id, version=None):
            raise RuntimeError("permission store unreachable")

    registries["permission_registry"] = _ExplodingPermissionRegistry()

    baseline = _baseline(registries)
    with pytest.raises(RuntimeError, match="permission store unreachable"):
        register_health_domain(
            **registries, operation_implementations=_implementations()
        )
    # Even on the unrelated error the integration must not have mutated.
    _assert_unchanged(registries, counting, baseline)


def test_permission_prevalidation_only_swallows_not_found():
    """When the permission registry genuinely reports "not found" the
    validation proceeds (the only legal swallow), and registration succeeds."""
    registries, counting = _spy_registries()
    result = register_health_domain(
        **registries, operation_implementations=_implementations()
    )
    assert str(result.definition.id) == HEALTH_DOMAIN_ID
    assert counting.register_calls == 1
    assert (
        registries["permission_registry"].get("domain-permission:health:1.0.0")
        is not None
    )
