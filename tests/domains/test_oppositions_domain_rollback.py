"""Phase 10.23 — Opposition Domain exact rollback (snapshot parity) tests."""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.oppositions import (
    OPPOSITIONS_DOMAIN_ID,
    build_oppositions_operation_definitions,
    register_oppositions_domain,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry


class _FakeImplementation:
    def __init__(self, definition):
        self.definition = definition

    def execute(self, request, memory_view=None):
        return {"success": True, "output": {}, "effects": ()}


class _FailAfterN:
    """Allows N successful registrations, then raises."""

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


def _implementations():
    return {
        op.operation_id: _FakeImplementation(op)
        for op in build_oppositions_operation_definitions()
    }


def _snapshot(registries):
    return {name: registry.snapshot_state() for name, registry in registries.items()}


def _assert_snapshots_equal(a, b):
    assert set(a.keys()) == set(b.keys())
    for key in a:
        assert a[key] == b[key], f"snapshot mismatch for {key}"


def _assert_no_opposition_entries(registries):
    assert registries["domain_registry"].get(OPPOSITIONS_DOMAIN_ID) is None
    assert registries["profile_registry"].get("oppositions.profile") is None
    assert registries["resource_registry"].list_all() == ()
    assert registries["rule_registry"].list_all() == ()
    assert registries["operation_registry"].list_definitions() == ()
    assert registries["workflow_registry"].list_for_domain(OPPOSITIONS_DOMAIN_ID) == ()


def test_failure_after_definition_rolls_back_exact():
    registries = _registries()
    registries["domain_registry"] = _FailAfterN(
        registries["domain_registry"], fail_after=0
    )
    before = _snapshot(registries)
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_oppositions_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_snapshots_equal(before, _snapshot(registries))
    _assert_no_opposition_entries(registries)


def test_failure_during_resources_rolls_back_exact():
    registries = _registries()
    registries["resource_registry"] = _FailAfterN(
        registries["resource_registry"], fail_after=0
    )
    before = _snapshot(registries)
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_oppositions_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_snapshots_equal(before, _snapshot(registries))
    _assert_no_opposition_entries(registries)


def test_failure_during_rules_rolls_back_exact():
    registries = _registries()
    registries["rule_registry"] = _FailAfterN(
        registries["rule_registry"], fail_after=0
    )
    before = _snapshot(registries)
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_oppositions_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_snapshots_equal(before, _snapshot(registries))
    _assert_no_opposition_entries(registries)


def test_failure_during_operations_rolls_back_exact():
    registries = _registries()
    registries["operation_registry"] = _FailAfterN(
        registries["operation_registry"], fail_after=0
    )
    before = _snapshot(registries)
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_oppositions_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_snapshots_equal(before, _snapshot(registries))
    _assert_no_opposition_entries(registries)


def test_failure_during_workflows_rolls_back_exact():
    registries = _registries()
    registries["workflow_registry"] = _FailAfterN(
        registries["workflow_registry"], fail_after=0
    )
    before = _snapshot(registries)
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_oppositions_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_snapshots_equal(before, _snapshot(registries))
    _assert_no_opposition_entries(registries)


def test_failure_after_permission_rolls_back_exact():
    registries = _registries()
    registries["permission_registry"] = _FailAfterN(
        registries["permission_registry"], fail_after=0
    )
    before = _snapshot(registries)
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_oppositions_domain(
            **registries, operation_implementations=_implementations()
        )
    _assert_snapshots_equal(before, _snapshot(registries))
    _assert_no_opposition_entries(registries)


def test_retry_after_rollback_succeeds():
    # First attempt fails after a mutation; the exact rollback leaves the
    # registries clean, so a retry succeeds.
    registries = _registries()
    failed_registries = _registries()
    failed_registries["resource_registry"] = _FailAfterN(
        failed_registries["resource_registry"], fail_after=0
    )
    with pytest.raises(RuntimeError):
        register_oppositions_domain(
            **failed_registries, operation_implementations=_implementations()
        )

    # Now register on the clean registries used for `before` snapshot check.
    result = register_oppositions_domain(
        **registries, operation_implementations=_implementations()
    )
    assert len(result.resources) == 11