"""Phase 9.28 – Existing System Integration completeness gate.

Verifies structural/documentation completeness of the 9.28 wiring: the
roadmap → test matrix is real and complete, no forbidden duplicate
subsystems were introduced, the composition root's new dependencies are
genuinely optional and protocol-backed, and backward compatibility of the
relaxed contract holds.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

import pytest

from cmm.agent_runtime.agent_runtime_integration_contracts import (
    IntegratedAgentExecutionRequest,
)
from cmm.agent_runtime.agent_runtime_integration_service import (
    AgentRuntimeIntegrationService,
)
from cmm.agent_runtime.agent_security_contracts import AgentPermissionContext
from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "docs/architecture/phase-9-28-existing-system-integration.md"
SERVICE_PATH = REPO_ROOT / "cmm/agent_runtime/agent_runtime_integration_service.py"
TEST_MODULE_PATH = REPO_ROOT / "tests/agent_runtime/test_existing_system_integration.py"
COMPLETENESS_PATH = REPO_ROOT / (
    "tests/agent_runtime/test_existing_system_integration_completeness.py"
)

UTC = __import__("datetime").timezone.utc
UTC_NOW = __import__("datetime").datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


# ── Matrix ↔ test existence ─────────────────────────────────────────────────


def _matrix_test_names() -> list[str]:
    """Extract every ``test_*`` identifier referenced in the doc's matrix table."""

    text = DOC_PATH.read_text()
    table_start = text.index("## Requirement matrix")
    table_end = text.index("## Residual risks")
    table = text[table_start:table_end]
    names = re.findall(r"`(test_[a-zA-Z0-9_]+)`", table)
    assert names, "matrix table must reference at least one test function"
    return names


def _defined_test_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }


def test_roadmap_matrix_is_complete() -> None:
    """Every test function named in the architecture doc's matrix exists,
    in either the behavior suite or this completeness suite."""

    matrix_names = set(_matrix_test_names())
    defined = _defined_test_functions(TEST_MODULE_PATH) | _defined_test_functions(
        COMPLETENESS_PATH
    )
    missing = matrix_names - defined
    assert not missing, f"matrix references undefined tests: {sorted(missing)}"


def test_matrix_covers_all_required_subsystems() -> None:
    text = DOC_PATH.read_text()
    table_start = text.index("## Requirement matrix")
    table_end = text.index("## Residual risks")
    table = text[table_start:table_end]
    for subsystem in (
        "Kernel",
        "Cognitive Layer",
        "Planner",
        "Execution Engine",
        "Validation System",
        "Workflow System",
        "Semantic Engine",
        "Future Domain Intelligence",
    ):
        assert subsystem in table, f"matrix missing subsystem row: {subsystem}"


def test_matrix_has_no_open_status() -> None:
    text = DOC_PATH.read_text()
    table_start = text.index("## Requirement matrix")
    table_end = text.index("## Residual risks")
    table = text[table_start:table_end]
    rows = [
        line
        for line in table.splitlines()
        if line.startswith("|")
        and "---" not in line
        and "Estado" not in line
        and "Status" not in line
    ]
    assert rows, "matrix must contain data rows"
    for row in rows:
        assert "TODO" not in row
        assert "Pending" not in row
        assert "Not started" not in row


# ── No skipped/xfail/TODO tests ─────────────────────────────────────────────


_FORBIDDEN_MARKER_PATTERNS = (
    re.compile(r"@pytest\.mark\.xfail"),
    re.compile(r"@pytest\.mark\.skip"),
    re.compile(r"pytest\.skip\("),
    re.compile(r"pytest\.xfail\("),
    re.compile(r"\bassert False\b"),
    re.compile(r"#\s*TODO\b"),
    re.compile(r"#\s*FIXME\b"),
)


def _assert_no_forbidden_markers(path: Path) -> None:
    text = path.read_text()
    for pattern in _FORBIDDEN_MARKER_PATTERNS:
        assert not pattern.search(text), (
            f"{path.name} contains forbidden marker: {pattern.pattern}"
        )


def test_no_xfail_skip_or_todo_in_test_suite() -> None:
    _assert_no_forbidden_markers(TEST_MODULE_PATH)
    _assert_no_forbidden_markers(COMPLETENESS_PATH)


def test_all_test_functions_have_at_least_one_assertion() -> None:
    source = TEST_MODULE_PATH.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            has_assert = any(isinstance(stmt, ast.Assert) for stmt in ast.walk(node))
            segment = ast.get_source_segment(source, node) or ""
            has_pytest_raises = "pytest.raises" in segment
            assert has_assert or has_pytest_raises, (
                f"{node.name} has no assertion and no pytest.raises"
            )


# ── Composition root: optional, protocol-backed dependencies ───────────────


def test_new_dependencies_are_optional_keyword_only() -> None:
    signature = inspect.signature(AgentRuntimeIntegrationService.__init__)
    for name in (
        "cognitive_service",
        "planning_service",
        "validation_service",
        "validation_policy_service",
    ):
        assert name in signature.parameters, f"missing constructor parameter: {name}"
        param = signature.parameters[name]
        assert param.default is None, f"{name} must default to None (optional)"
        assert param.kind is inspect.Parameter.KEYWORD_ONLY, (
            f"{name} must be keyword-only"
        )


def test_new_dependencies_are_not_typed_as_concrete_implementations() -> None:
    """The constructor must not import/require concrete adapter classes as types."""

    source = SERVICE_PATH.read_text()
    tree = ast.parse(source)
    init = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            init = node
            break
    assert init is not None
    forbidden_types = (
        "DefaultCognitiveRuntimeAdapter",
        "AgentCognitiveService",
        "DefaultWorkflowPlannerAdapter",
        "AgentPlanningService",
        "AgentValidationAdapter",
        "AgentValidationPolicyAdapter",
    )
    for arg in init.args.kwonlyargs:
        if arg.arg in (
            "cognitive_service",
            "planning_service",
            "validation_service",
            "validation_policy_service",
        ):
            annotation = ast.dump(arg.annotation) if arg.annotation else ""
            for forbidden in forbidden_types:
                assert forbidden not in annotation, (
                    f"{arg.arg} annotation must not hard-require {forbidden}"
                )


def test_service_keeps_no_parallel_mutable_state_for_new_deps() -> None:
    """The service stores each dependency verbatim; it does not wrap it in a
    second cache/store of its own (state stays in AgentRuntimeIntegrationStore
    and the injected services' own stores)."""

    source = SERVICE_PATH.read_text()
    forbidden_attrs = (
        "_cognitive_cache",
        "_plan_cache",
        "_validation_cache",
        "_cognitive_store",
        "_plan_store",
        "_validation_store",
    )
    for attr in forbidden_attrs:
        assert attr not in source, f"found forbidden parallel state attribute: {attr}"


# ── No duplicate runtime/planner/cognitive/kernel modules ──────────────────


def test_no_kernel_module_exists() -> None:
    kernel_path = REPO_ROOT / "cmm/agent_runtime/kernel.py"
    assert not kernel_path.exists(), "a monolithic kernel.py must not be introduced"


def test_no_duplicate_runtime_loop_or_planner_or_cognitive_classes() -> None:
    """Only one class per canonical subsystem concept exists under agent_runtime."""

    agent_runtime_dir = REPO_ROOT / "cmm/agent_runtime"
    class_names: dict[str, list[str]] = {}
    for path in agent_runtime_dir.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_names.setdefault(node.name, []).append(path.name)

    for canonical in (
        "AgentRuntimeLoop",
        "AgentPlanningService",
        "AgentCognitiveService",
        "AgentValidationAdapter",
        "AgentValidationPolicyAdapter",
        "AgentRuntimeIntegrationService",
        "AgentRuntimeIntegrationStore",
    ):
        files = class_names.get(canonical, [])
        assert len(files) == 1, f"{canonical} defined in more than one file: {files}"


# ── Backward compatibility of the relaxed contract ──────────────────────────


def _permission_context() -> AgentPermissionContext:
    return AgentPermissionContext(
        id="perm-ctx-completeness",
        agent_id="agent-1",
        agent_run_id="run-1",
        goal_id="goal-1",
        actor_id="actor-1",
        owner_actor_id="actor-1",
        allowed_domains=("documents",),
        allowed_resources=("doc-1",),
        allowed_operations=("documents.read",),
        allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
        maximum_autonomy_level=2,
        created_at=UTC_NOW,
    )


def _operation() -> AgentOperationRequest:
    return AgentOperationRequest(
        id="op-1",
        agent_run_id="run-1",
        workflow_id="workflow-1",
        task_id="task-1",
        operation_name="documents.read",
        idempotency_key="idem-1",
        created_at=UTC_NOW.isoformat(),
    )


def test_existing_operations_only_requests_still_round_trip() -> None:
    """Pre-9.28 payload shape (operations present) round-trips unchanged."""

    request = IntegratedAgentExecutionRequest(
        execution_id="exec-1",
        request_id="req-1",
        goal_id="goal-1",
        actor_id="actor-1",
        owner_actor_id="actor-1",
        operations=(_operation(),),
        permission_context=_permission_context(),
        created_at=UTC_NOW,
    )
    payload = request.to_dict()
    restored = IntegratedAgentExecutionRequest.from_dict(payload)
    assert restored.to_dict() == payload


def test_operations_and_workflow_together_still_rejected() -> None:
    from cmm.agent_runtime.workflow_planner_contracts import AgentWorkflowPlan

    workflow = AgentWorkflowPlan(
        id="plan-1",
        goal_id="goal-1",
        agent_run_id="run-1",
        workflow_id="workflow-1",
    )
    with pytest.raises(ValueError, match="not both"):
        IntegratedAgentExecutionRequest(
            execution_id="exec-1",
            request_id="req-1",
            goal_id="goal-1",
            actor_id="actor-1",
            owner_actor_id="actor-1",
            operations=(_operation(),),
            workflow=workflow,
            created_at=UTC_NOW,
        )


def test_neither_operations_nor_workflow_now_accepted_at_contract_level() -> None:
    """The 9.28 relaxation: planning-required requests are contract-valid.

    ``AgentRuntimeIntegrationService.validate()`` (tested in the main 9.28
    suite) still fails closed when no ``planning_service`` is configured —
    this test only verifies the *contract* accepts the shape.
    """

    request = IntegratedAgentExecutionRequest(
        execution_id="exec-1",
        request_id="req-1",
        goal_id="goal-1",
        actor_id="actor-1",
        owner_actor_id="actor-1",
        operations=(),
        workflow=None,
        created_at=UTC_NOW,
    )
    assert request.operations == ()
    assert request.workflow is None
    payload = request.to_dict()
    assert IntegratedAgentExecutionRequest.from_dict(payload).to_dict() == payload


# ── Documentation completeness ──────────────────────────────────────────────


def test_architecture_doc_exists_and_documents_seams() -> None:
    assert DOC_PATH.exists()
    text = DOC_PATH.read_text()
    for heading in (
        "## Composition root changes",
        "## Cognitive wiring",
        "## Planner wiring",
        "## Validation wiring",
        "## Workflow lifecycle",
        "## Kernel boundary",
        "## Semantic Engine seam (optional)",
        "## Future Domain Intelligence",
        "## Requirement matrix",
        "## Residual risks",
    ):
        assert heading in text, f"architecture doc missing section: {heading}"
