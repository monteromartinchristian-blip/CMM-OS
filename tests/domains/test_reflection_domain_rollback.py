"""Phase 10.24 — Reflection Domain rollback tests.

Registration is atomic: snapshots are captured before the first mutation and
every registration boundary failure restores the exact prior state with no
partial registration (spec §39, §40; hardened General rollback pattern).
"""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.reflection import REFLECTION_DOMAIN_ID, register_reflection_domain
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry


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
        "workflow_registry": InMemoryDomainWorkflowRegistry(
            InMemoryWorkflowRegistry()
        ),
        "permission_registry": DomainPermissionRegistry(),
    }


def _snapshot_all(registries):
    return {name: registry.snapshot_state() for name, registry in registries.items()}


def _assert_snapshots_equal(a, b):
    assert set(a.keys()) == set(b.keys())
    for key in a:
        assert a[key] == b[key], f"snapshot mismatch for {key}"


def _assert_no_reflection_entries(registries):
    assert registries["domain_registry"].get(REFLECTION_DOMAIN_ID) is None
    assert registries["profile_registry"].get("reflection.profile") is None
    assert registries["resource_registry"].list_all() == ()
    assert registries["rule_registry"].list_all() == ()
    assert registries["operation_registry"].list_definitions() == ()
    assert registries["workflow_registry"].list_for_domain(REFLECTION_DOMAIN_ID) == ()


def test_failure_after_definition_rolls_back():
    registries = _registries()
    registries["domain_registry"] = _FailAfterN(
        registries["domain_registry"], fail_after=0
    )
    before = _snapshot_all(registries)
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_reflection_domain(**registries)
    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)
    _assert_no_reflection_entries(registries)


def test_failure_during_resources_rolls_back():
    registries = _registries()
    registries["resource_registry"] = _FailAfterN(
        registries["resource_registry"], fail_after=0
    )
    before = _snapshot_all(registries)
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_reflection_domain(**registries)
    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)
    _assert_no_reflection_entries(registries)


def test_failure_during_rules_rolls_back():
    registries = _registries()
    registries["rule_registry"] = _FailAfterN(
        registries["rule_registry"], fail_after=0
    )
    before = _snapshot_all(registries)
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_reflection_domain(**registries)
    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)
    _assert_no_reflection_entries(registries)


def test_failure_during_operations_rolls_back():
    registries = _registries()
    registries["operation_registry"] = _FailAfterN(
        registries["operation_registry"], fail_after=0
    )
    before = _snapshot_all(registries)
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_reflection_domain(**registries)
    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)
    _assert_no_reflection_entries(registries)


def test_failure_during_workflows_rolls_back():
    registries = _registries()
    registries["workflow_registry"] = _FailAfterN(
        registries["workflow_registry"], fail_after=0
    )
    before = _snapshot_all(registries)
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_reflection_domain(**registries)
    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)
    _assert_no_reflection_entries(registries)


def test_failure_during_permission_rolls_back():
    registries = _registries()
    registries["permission_registry"] = _FailAfterN(
        registries["permission_registry"], fail_after=0
    )
    before = _snapshot_all(registries)
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_reflection_domain(**registries)
    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)
    _assert_no_reflection_entries(registries)


def test_preexisting_entries_preserved_after_rollback():
    from cmm.cognitive.enums import SensitivityLevel
    from cmm.domains.resource_contracts import (
        DomainResourceDefinition,
        DomainResourceTemporalPolicy,
    )

    registries = _registries()
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
    registries["resource_registry"] = _FailAfterN(
        registries["resource_registry"], fail_after=0
    )
    before = _snapshot_all(registries)
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_reflection_domain(**registries)
    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)
    assert registries["resource_registry"].get("unrelated.resource") is not None


def test_retry_succeeds_after_rollback():
    registries = _registries()
    registries["resource_registry"] = _FailAfterN(
        registries["resource_registry"], fail_after=0
    )
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_reflection_domain(**registries)
    registries["resource_registry"] = InMemoryDomainResourceRegistry()
    result = register_reflection_domain(**registries)
    assert str(result.definition.id) == REFLECTION_DOMAIN_ID
    assert len(registries["resource_registry"].list_all()) == 9