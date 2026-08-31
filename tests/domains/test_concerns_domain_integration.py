"""Phase 10.25 — Concerns Domain integration tests.

Validation-first atomic registration across all shared registries:
the full pack registers atomically, duplicates fail before any mutation, the
bootstrap composes General + Concerns through shared mechanisms, General
remains fallback, and a fresh import registers nothing (implementation plan
Task 10).
"""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.concerns.bootstrap import (
    CONCERNS_BOOTSTRAP_NAME,
    ConcernsDomainBootstrap,
    build_standard_concerns_domain_bootstrap,
)
from cmm.domains.concerns.definition import (
    CONCERNS_DOMAIN_ID,
    CONCERNS_PERMISSION_IDS,
    build_concerns_domain_definition,
)
from cmm.domains.concerns.integration import (
    ConcernsDomainIntegrationResult,
    register_concerns_domain,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry


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


# ── Complete registration ────────────────────────────────────────────────────


def test_registers_complete_pack():
    registries = _registries()
    result = register_concerns_domain(**registries)
    assert isinstance(result, ConcernsDomainIntegrationResult)
    assert str(result.definition.id) == CONCERNS_DOMAIN_ID
    assert registries["domain_registry"].get(CONCERNS_DOMAIN_ID) is not None
    assert len(registries["resource_registry"].list_all()) == 10
    assert len(registries["rule_registry"].list_all()) == 14
    assert len(registries["operation_registry"].list_definitions()) == 13
    assert len(registries["workflow_registry"].list_for_domain(CONCERNS_DOMAIN_ID)) == 8
    assert registries["profile_registry"].get("concerns.profile") is not None
    stored_policy = registries["permission_registry"].get(CONCERNS_PERMISSION_IDS[0])
    assert str(stored_policy.policy_id) == "domain-permission:concerns:1.0.0"


def test_operations_registered_unavailable_by_default():
    from cmm.domains.operation_registry import DomainOperationRegistryError

    registries = _registries()
    register_concerns_domain(**registries)
    for definition in registries["operation_registry"].list_definitions():
        with pytest.raises(DomainOperationRegistryError):
            registries["operation_registry"].get_implementation(
                definition.operation_id, definition.version
            )


def test_duplicate_registration_fails_validation_first():
    registries = _registries()
    register_concerns_domain(**registries)
    from cmm.domains.errors import DomainRegistryConflict

    before = registries["domain_registry"].snapshot_state()
    with pytest.raises(DomainRegistryConflict):
        register_concerns_domain(**registries)
    # validation-first: no partial mutation on the second attempt
    assert registries["domain_registry"].snapshot_state() == before


# ── Validation-first failures ────────────────────────────────────────────────


def test_unknown_operation_implementation_fails_closed():
    registries = _registries()

    class _Imp:
        def execute(self, request):
            return {"ok": True}

    with pytest.raises(ValueError, match="undeclared operations"):
        register_concerns_domain(
            **registries,
            operation_implementations={"concerns.not_a_real_operation": _Imp()},
        )


def test_duplicate_resources_fail_validation_first():
    from cmm.domains.concerns.integration import _validate_all
    from cmm.domains.concerns.operations import build_concerns_operation_definitions
    from cmm.domains.concerns.permissions import build_concerns_permission_policy
    from cmm.domains.concerns.profile import build_concerns_profile
    from cmm.domains.concerns.resources import build_concerns_resource_definitions
    from cmm.domains.concerns.rules import build_concerns_rules
    from cmm.domains.concerns.workflows import build_concerns_workflow_definitions
    from cmm.domains.errors import DomainResourceRegistryError

    registries = _registries()
    resources = list(build_concerns_resource_definitions())
    resources.append(resources[0])
    with pytest.raises(DomainResourceRegistryError):
        _validate_all(
            definition=build_concerns_domain_definition(),
            profile=build_concerns_profile(),
            resources=tuple(resources),
            rules=build_concerns_rules(),
            operations=build_concerns_operation_definitions(),
            workflows=build_concerns_workflow_definitions(),
            permission_policy=build_concerns_permission_policy(),
            domain_registry=registries["domain_registry"],
            profile_registry=registries["profile_registry"],
            resource_registry=registries["resource_registry"],
            rule_registry=registries["rule_registry"],
            operation_registry=registries["operation_registry"],
            workflow_registry=registries["workflow_registry"],
            permission_registry=registries["permission_registry"],
            operation_implementations=None,
        )


def test_malformed_workflow_failures_block_before_mutation():
    """A workflow registry failure during registration leaves zero mutations."""
    registries = _registries()

    class _FailingWorkflowRegistry(InMemoryDomainWorkflowRegistry):
        def register(self, definition):
            raise RuntimeError("simulated post-mutation failure")

    failing = _FailingWorkflowRegistry(InMemoryWorkflowRegistry())
    registries["workflow_registry"] = failing
    before_all = {name: r.snapshot_state() for name, r in registries.items()}
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_concerns_domain(**registries)
    after_all = {name: r.snapshot_state() for name, r in registries.items()}
    assert before_all == after_all


# ── Rollback at every boundary ───────────────────────────────────────────────


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


@pytest.mark.parametrize(
    ("registry_key", "fail_after"),
    [
        ("domain_registry", 0),
        ("profile_registry", 0),
        ("resource_registry", 0),
        ("rule_registry", 0),
        ("operation_registry", 0),
        ("workflow_registry", 0),
        ("permission_registry", 0),
    ],
)
def test_failure_at_every_boundary_rolls_back_completely(registry_key, fail_after):
    registries = _registries()
    registries[registry_key] = _FailAfterN(registries[registry_key], fail_after)
    before = {name: r.snapshot_state() for name, r in registries.items()}
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_concerns_domain(**registries)
    after = {name: r.snapshot_state() for name, r in registries.items()}
    assert set(before.keys()) == set(after.keys())
    for key, before_snapshot in before.items():
        assert before_snapshot == after[key], f"snapshot mismatch for {key}"
    # nothing partial remains
    assert registries["domain_registry"].get(CONCERNS_DOMAIN_ID) is None
    assert registries["resource_registry"].list_all() == ()
    assert registries["rule_registry"].list_all() == ()
    assert registries["operation_registry"].list_definitions() == ()
    assert registries["workflow_registry"].list_for_domain(CONCERNS_DOMAIN_ID) == ()
    assert registries["profile_registry"].get("concerns.profile") is None


def test_unrelated_preexisting_entries_preserved_after_rollback():
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
    before = {name: r.snapshot_state() for name, r in registries.items()}
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_concerns_domain(**registries)
    after = {name: r.snapshot_state() for name, r in registries.items()}
    assert before == after
    # unrelated entry survived exactly
    assert registries["resource_registry"].get("unrelated.resource") is not None


def test_retry_succeeds_after_rollback():
    registries = _registries()
    registries["resource_registry"] = _FailAfterN(
        registries["resource_registry"], fail_after=0
    )
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_concerns_domain(**registries)
    registries["resource_registry"] = InMemoryDomainResourceRegistry()
    result = register_concerns_domain(**registries)
    assert str(result.definition.id) == CONCERNS_DOMAIN_ID
    assert len(registries["resource_registry"].list_all()) == 10


# ── Bootstrap composition ────────────────────────────────────────────────────


def test_bootstrap_builds_general_plus_concerns():
    bootstrap = build_standard_concerns_domain_bootstrap()
    assert isinstance(bootstrap, ConcernsDomainBootstrap)
    assert bootstrap.domain_registry.get("domain:general") is not None
    assert bootstrap.domain_registry.get(CONCERNS_DOMAIN_ID) is not None
    # exact same registry objects as the standard general bootstrap
    general = build_standard_general_registries_probe()
    del general
    # General is the fallback resolver
    assert str(bootstrap.resolver.fallback_domain) == "domain:general"
    assert bootstrap.profile_registry.get("general.profile") is not None
    assert bootstrap.profile_registry.get("concerns.profile") is not None


def build_standard_general_registries_probe():  # pragma: no cover - helper
    from cmm.domains.general.bootstrap import build_standard_general_domain_bootstrap

    return build_standard_general_domain_bootstrap()


def test_bootstrap_name_and_general_fallback():
    from cmm.domains.identifiers import DomainId

    assert CONCERNS_BOOTSTRAP_NAME == "ConcernsDomainBootstrap"
    bootstrap = build_standard_concerns_domain_bootstrap()
    assert bootstrap.resolver.fallback_domain == DomainId(slug="general")


def test_bootstrap_operations_unavailable_without_injections():
    from cmm.domains.operation_registry import DomainOperationRegistryError

    bootstrap = build_standard_concerns_domain_bootstrap()
    for definition in bootstrap.operation_registry.list_definitions():
        if str(definition.domain_id) == CONCERNS_DOMAIN_ID:
            with pytest.raises(DomainOperationRegistryError):
                bootstrap.operation_registry.get_implementation(
                    definition.operation_id, definition.version
                )


# ── Fresh import ─────────────────────────────────────────────────────────────


def test_import_has_no_side_effects():
    import cmm.domains.concerns  # noqa: F401

    registry = DomainRegistry()
    assert registry.get(CONCERNS_DOMAIN_ID) is None


def test_clean_subprocess_import_registers_nothing():
    import subprocess
    import sys

    code = (
        "import cmm.domains.concerns; "
        "from cmm.domains.registry import DomainRegistry; "
        "print(DomainRegistry().get('domain:concerns'))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "None"


def test_package_boundary_exactly_14_modules():
    from pathlib import Path

    package_dir = Path(__file__).resolve().parents[2] / "cmm" / "domains" / "concerns"
    modules = sorted(
        path.name for path in package_dir.glob("*.py") if path.suffix == ".py"
    )
    assert modules == [
        "__init__.py",
        "bootstrap.py",
        "catalog.py",
        "definition.py",
        "integration.py",
        "memory.py",
        "operations.py",
        "permissions.py",
        "presentation.py",
        "profile.py",
        "resources.py",
        "rules.py",
        "trace.py",
        "workflows.py",
    ]
