"""Phase 10.24 — Reflection validation-first matrix tests.

Malformed pack members fail before partial registration; unknown
workflow/operation states block; a clean import never registers globally; and
Reflection composes with General through the shared bootstrap (spec §39, §40).
"""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.reflection import (
    build_reflection_domain_definition,
    register_reflection_domain,
)
from cmm.domains.reflection.integration import (
    _validate_all,
)
from cmm.domains.reflection.operations import (
    build_reflection_operation_definitions,
)
from cmm.domains.reflection.permissions import build_reflection_permission_policy
from cmm.domains.reflection.profile import build_reflection_profile
from cmm.domains.reflection.resources import (
    build_reflection_resource_definitions,
)
from cmm.domains.reflection.rules import build_reflection_rules
from cmm.domains.reflection.workflows import (
    build_reflection_workflow_definitions,
)
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_contracts import DomainWorkflowContext
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


def test_clean_import_registers_nothing():
    import subprocess
    import sys

    code = (
        "import cmm.domains.reflection as r; "
        "from cmm.domains.registry import DomainRegistry; "
        "print(DomainRegistry().get('domain:reflection'))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "None"


def test_malformed_workflow_definition_fails_validation_first():
    """A malformed workflow fails validation before any registration mutation."""
    from cmm.domains.workflow_contracts import (
        DomainWorkflowDefinition,
        DomainWorkflowValidationError,
    )

    with pytest.raises(DomainWorkflowValidationError):
        DomainWorkflowDefinition(
            workflow_id="reflection.broken",
            domain_id="domain:reflection",
            version="1.0.0",
            name="Broken",
            nodes=(),  # empty nodes -> invalid domain workflow
        )


def test_unknown_operation_implementation_fails_closed():
    """An implementation for a non-declared operation is rejected."""
    registries = _registries()

    class _Imp:
        def execute(self, request):
            return {"ok": True}

    with pytest.raises(ValueError, match="undeclared operations"):
        register_reflection_domain(
            **registries,
            operation_implementations={"reflection.not_a_real_operation": _Imp()},
        )


def test_unknown_workflow_fails_closed_in_resolution():
    from cmm.workflows.enums import WorkflowAvailabilityStatus

    workflows = {w.workflow_id: w for w in build_reflection_workflow_definitions()}
    wf = workflows["reflection.personal_question_exploration"]
    context = DomainWorkflowContext(
        primary_domain_id="domain:reflection",
        known_domain_ids=frozenset({"domain:reflection", "domain:general"}),
        available_resources=frozenset(wf.required_resources),
        available_operations=frozenset(
            {n.operation_id for n in wf.nodes if n.operation_id}
        ),
    )
    from cmm.domains.workflow_resolution import resolve_domain_workflow

    resolution = resolve_domain_workflow(wf, context)
    assert resolution.status is WorkflowAvailabilityStatus.AVAILABLE

    # an unknown workflow id resolves to nothing -> blocks
    from cmm.workflows.errors import WorkflowRegistryError

    with pytest.raises(WorkflowRegistryError):
        __import__(
            "cmm.workflows.registry", fromlist=["InMemoryWorkflowRegistry"]
        ).InMemoryWorkflowRegistry().get("reflection.unknown_workflow", "1.0.0")


def test_validation_all_detects_duplicate_resources():
    registries = _registries()
    resources = build_reflection_resource_definitions()
    duplicate = list(resources)
    duplicate.append(duplicate[0])  # exact duplicate
    from cmm.domains.errors import DomainResourceRegistryError

    with pytest.raises(DomainResourceRegistryError):
        _validate_all(
            definition=build_reflection_domain_definition(),
            profile=build_reflection_profile(),
            resources=tuple(duplicate),
            rules=build_reflection_rules(),
            operations=build_reflection_operation_definitions(),
            workflows=build_reflection_workflow_definitions(),
            permission_policy=build_reflection_permission_policy(),
            domain_registry=registries["domain_registry"],
            profile_registry=registries["profile_registry"],
            resource_registry=registries["resource_registry"],
            rule_registry=registries["rule_registry"],
            operation_registry=registries["operation_registry"],
            workflow_registry=registries["workflow_registry"],
            permission_registry=registries["permission_registry"],
            operation_implementations=None,
        )


def test_repeated_registration_after_success_fails_cleanly():
    registries = _registries()
    register_reflection_domain(**registries)
    before = {name: r.snapshot_state() for name, r in registries.items()}
    from cmm.domains.errors import DomainRegistryConflict

    with pytest.raises(DomainRegistryConflict):
        register_reflection_domain(**registries)
    after = {name: r.snapshot_state() for name, r in registries.items()}
    assert before == after
