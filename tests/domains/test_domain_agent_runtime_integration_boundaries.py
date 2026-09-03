"""Phase 10.41 — Task 1 boundary characterization tests.

These tests lock the existing Domain ↔ Agent Runtime boundary BEFORE any
Phase 10.41 production code exists:

- the permanent ``cmm.agent_runtime → cmm.domains`` reverse-import gate;
- the exact Phase 9 request seam used by the Domain integration boundary;
- the canonical Agent Runtime service call shape;
- the canonical Action Budget decrease/restriction path and the forbidden
  increase paths;
- Agent permission context immutability and narrowing behavior;
- anti-fragmentation ownership names for the Phase 10.41 surface.

This task is characterization only: it locks existing repository behavior.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
from dataclasses import fields, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import get_type_hints

import pytest

from cmm.agent_runtime.action_budget_service import ActionBudgetService
from cmm.agent_runtime.agent_runtime_integration_contracts import (
    IntegratedAgentExecutionRequest,
)
from cmm.agent_runtime.agent_runtime_integration_service import (
    AgentRuntimeIntegrationService,
)
from cmm.agent_runtime.agent_security_contracts import AgentPermissionContext
from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest
from cmm.agent_runtime.workflow_planner_contracts import AgentWorkflowPlan
from cmm.domains.validation_fragmentation import analyze_fragmentation

ROOT = Path(__file__).resolve().parents[2]
PHASE_1041_PRODUCTION_FILES = (
    ROOT / "cmm" / "domains" / "agent_runtime_integration_contracts.py",
    ROOT / "cmm" / "domains" / "agent_runtime_integration.py",
)

FORBIDDEN_OWNER_NAMES = frozenset(
    {
        "DomainAgentRuntime",
        "DomainAgentRuntimeService",
        "DomainRuntimeLoop",
        "DomainRuntimeStateMachine",
        "DomainRuntimeStore",
        "DomainAgentPlanner",
        "DomainAgentWorkflowEngine",
        "DomainAgentApprovalService",
        "DomainAgentBudgetService",
        "DomainAgentExecutionEngine",
        "DomainAgentValidationEngine",
        "DomainAgentMemoryStore",
        "DomainAgentKnowledgeStore",
        "DomainAgentTraceStore",
        "DomainAgentEventBus",
        "DomainCognitiveEngine",
    }
)
INTEGRATION_OWNER_NAME = "DefaultDomainAgentRuntimeIntegrator"

# A metadata key that Phase 9 rejects as secret-bearing (value is irrelevant).
SECRET_LIKE_METADATA_KEY = "api_key"


# ── Helpers ───────────────────────────────────────────────────────────────────


def imports_prefix(root: Path, prefix: str) -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == prefix or alias.name.startswith(prefix + "."):
                        found.append((path, f"import {alias.name}"))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == prefix or module.startswith(prefix + "."):
                    found.append((path, f"from {module} import ..."))
    return found


def _phase_1041_owner_definitions(path: Path) -> list[str]:
    if not path.exists():
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in FORBIDDEN_OWNER_NAMES
        ):
            names.append(node.name)
    return names


def _permission_context(**overrides: object) -> AgentPermissionContext:
    values: dict[str, object] = {
        "id": "perm-ctx-1041",
        "agent_id": "agent-1",
        "agent_run_id": "run-1",
        "goal_id": "goal-1",
        "actor_id": "actor-1",
        "owner_actor_id": "actor-1",
        "allowed_domains": ("documents",),
        "allowed_resources": ("doc-1",),
        "allowed_operations": ("documents.read",),
        "allowed_sensitivity_levels": (SensitivityLevel.INTERNAL,),
        "maximum_autonomy_level": 2,
        "created_at": datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return AgentPermissionContext(**values)


def _operation_request(**overrides: object) -> AgentOperationRequest:
    values: dict[str, object] = {
        "id": "op-1",
        "agent_run_id": "run-1",
        "workflow_id": "workflow-1",
        "task_id": "task-1",
        "operation_name": "documents.read",
        "idempotency_key": "idem-1",
        "parameters": {"document": {"id": "doc-1"}},
        "created_at": "2026-09-03T12:00:00+00:00",
    }
    values.update(overrides)
    return AgentOperationRequest(**values)


def _integrated_request(**overrides: object) -> IntegratedAgentExecutionRequest:
    values: dict[str, object] = {
        "execution_id": "exec-1041",
        "request_id": "req-1041",
        "goal_id": "goal-1",
        "actor_id": "actor-1",
        "owner_actor_id": "actor-1",
        "operations": (_operation_request(),),
        "max_autonomy_level": 2,
        "budget_id": "budget-1041",
        "trace_id": "trace-1041",
        "correlation_id": "corr-1041",
        "causation_id": "cause-1041",
        "created_at": datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return IntegratedAgentExecutionRequest(**values)


# ── Permanent reverse-import gate ─────────────────────────────────────────────


def test_agent_runtime_has_zero_reverse_imports_from_domains() -> None:
    assert imports_prefix(ROOT / "cmm" / "agent_runtime", "cmm.domains") == []


# ── Phase 9 request seam ──────────────────────────────────────────────────────


def test_integrated_request_exposes_locked_seam_fields() -> None:
    required_fields = {
        "execution_id",
        "request_id",
        "goal_id",
        "actor_id",
        "owner_actor_id",
        "operations",
        "workflow",
        "cognitive_context",
        "permission_context",
        "max_autonomy_level",
        "budget_id",
        "budget_allocations",
        "trace_id",
        "correlation_id",
        "causation_id",
        "metadata",
    }
    assert required_fields <= {
        field.name for field in fields(IntegratedAgentExecutionRequest)
    }


def test_integrated_request_round_trips_through_dict_api() -> None:
    request = _integrated_request()
    restored = IntegratedAgentExecutionRequest.from_dict(request.to_dict())
    assert restored == request


def test_integrated_request_rejects_operations_with_workflow() -> None:
    workflow = AgentWorkflowPlan(
        id="plan-1",
        goal_id="goal-1",
        agent_run_id="run-1",
        workflow_id="workflow-1",
        created_at="2026-09-03T12:00:00+00:00",
        updated_at="2026-09-03T12:00:00+00:00",
    )
    with pytest.raises(ValueError, match="operations or workflow"):
        _integrated_request(workflow=workflow)


# ── Canonical runtime service call ────────────────────────────────────────────


def test_runtime_service_execute_takes_single_request_and_returns_result() -> None:
    signature = inspect.signature(AgentRuntimeIntegrationService.execute)
    assert list(signature.parameters) == ["self", "request"]
    hints = get_type_hints(AgentRuntimeIntegrationService.execute)
    assert hints["request"] is IntegratedAgentExecutionRequest
    assert hints["return"].__name__ == "IntegratedAgentExecutionResult"


# ── Canonical budget restriction path ─────────────────────────────────────────


def test_decrease_budget_signature_is_locked() -> None:
    signature = inspect.signature(ActionBudgetService.decrease_budget)
    parameter_names = list(signature.parameters)
    assert parameter_names[:2] == ["self", "budget_id"]
    assert "resource_type" in parameter_names
    assert "new_limit" in parameter_names


def test_budget_service_keeps_distinct_increase_paths() -> None:
    assert hasattr(ActionBudgetService, "increase_budget")
    assert hasattr(ActionBudgetService, "request_increase")
    assert (
        ActionBudgetService.increase_budget is not ActionBudgetService.decrease_budget
    )
    assert (
        ActionBudgetService.request_increase is not ActionBudgetService.decrease_budget
    )


# ── Agent permission immutability ─────────────────────────────────────────────


def test_agent_permission_context_is_frozen_slotted_dataclass() -> None:
    assert dataclasses.is_dataclass(AgentPermissionContext)
    params = AgentPermissionContext.__dataclass_params__
    assert params.frozen is True
    assert params.slots is True


def test_agent_permission_context_serialization_round_trip() -> None:
    context = _permission_context()
    restored = AgentPermissionContext.from_mapping(context.to_dict())
    assert restored.id == context.id
    assert restored.allowed_operations == context.allowed_operations
    assert restored.allowed_domains == context.allowed_domains
    assert restored.allowed_sensitivity_levels == context.allowed_sensitivity_levels
    assert restored.maximum_autonomy_level == context.maximum_autonomy_level
    assert restored.created_at == context.created_at


def test_agent_permission_context_rejects_secret_metadata() -> None:
    with pytest.raises(Exception, match="forbidden key"):
        _permission_context(metadata={SECRET_LIKE_METADATA_KEY: "value-1041"})


def test_agent_permission_context_narrows_without_mutation() -> None:
    context = _permission_context()
    narrowed = replace(context, allowed_operations=("other.read",))
    assert context.allowed_operations == ("documents.read",)
    assert narrowed.allowed_operations == ("other.read",)
    assert narrowed.maximum_autonomy_level == context.maximum_autonomy_level


# ── Anti-fragmentation ownership names ────────────────────────────────────────


def test_phase_1041_production_files_define_no_forbidden_owners() -> None:
    offenders = {
        path.relative_to(ROOT).as_posix(): _phase_1041_owner_definitions(path)
        for path in PHASE_1041_PRODUCTION_FILES
        if path.exists() and _phase_1041_owner_definitions(path)
    }
    assert offenders == {}


def test_integration_owner_name_is_not_a_forbidden_owner() -> None:
    assert INTEGRATION_OWNER_NAME not in FORBIDDEN_OWNER_NAMES


def test_fragmentation_guard_blocks_duplicate_runtime_owner() -> None:
    findings = analyze_fragmentation(
        "class DomainAgentRuntime:\n    pass\n",
        "phase1041_owner.py",
    )
    assert "DOMAIN_FRAGMENTATION_AGENT_RUNTIME_DUPLICATION" in {
        str(finding["code"]) for finding in findings
    }
