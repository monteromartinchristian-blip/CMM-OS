"""Phase 10.42 — architecture and anti-fragmentation boundary tests.

DP-042 — Domain-specialized Planner and Workflow Engine integration.

Static gates proving the integration adds no parallel owners and no
reverse imports:

- AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
- WORKFLOWS_TO_DOMAIN_IMPORTS=0
- NO_PARALLEL_PLANNER / WORKFLOW_ENGINE / PLAN_STORE / WORKFLOW_STORE /
  PERMISSION_SYSTEM / APPROVAL_SYSTEM / VALIDATION_SYSTEM / RUNTIME /
  EVENT_BUS / STATE_MACHINE = YES
"""

from __future__ import annotations

import ast
from pathlib import Path

from cmm.domains import (
    DefaultDomainPlannerWorkflowIntegrator,
    DomainPlannerWorkflowIntegrationRequest,
    DomainPlannerWorkflowIntegrationResult,
    DomainPlannerWorkflowIntegrator,
    DomainPlanningCapabilityView,
)
from cmm.domains.validation_fragmentation import analyze_fragmentation

ROOT = Path(__file__).resolve().parents[2]
PHASE_1042_PRODUCTION_FILES = (
    ROOT / "cmm" / "domains" / "planner_workflow_integration_contracts.py",
    ROOT / "cmm" / "domains" / "planner_workflow_integration.py",
)

ALLOWED_DEFINITION_NAMES = frozenset(
    {
        "DomainPlanningCapabilityView",
        "DomainPlannerWorkflowIntegrationRequest",
        "DomainPlannerWorkflowIntegrationResult",
        "DomainPlannerWorkflowIntegrator",
        "DefaultDomainPlannerWorkflowIntegrator",
        "_PlanningAttempt",
    }
)

FORBIDDEN_OWNER_TOKENS = (
    "PlanningEngine",
    "WorkflowEngine",
    "WorkflowRuntime",
    "WorkflowStore",
    "PlanStore",
    "PermissionSystem",
    "ApprovalService",
    "ValidationService",
    "EventBus",
    "StateMachine",
    "Planner",
    "Runtime",
    "Registry",
)

FORBIDDEN_INSTANTIATION_SUFFIXES = (
    "Store",
    "Registry",
    "Engine",
    "EventBus",
    "StateMachine",
    "Service",
)


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


def _defined_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]


# ── Reverse-import gates ──────────────────────────────────────────────────


def test_agent_runtime_has_zero_domain_imports() -> None:
    hits = imports_prefix(ROOT / "cmm" / "agent_runtime", "cmm.domains")
    assert hits == [], hits


def test_workflows_have_zero_domain_imports() -> None:
    hits = imports_prefix(ROOT / "cmm" / "workflows", "cmm.domains")
    assert hits == [], hits


# ── Frozen public surface ─────────────────────────────────────────────────


def test_phase_1042_public_surface_is_complete() -> None:
    assert DefaultDomainPlannerWorkflowIntegrator is not None
    assert DomainPlannerWorkflowIntegrationRequest is not None
    assert DomainPlannerWorkflowIntegrationResult is not None
    assert DomainPlannerWorkflowIntegrator is not None
    assert DomainPlanningCapabilityView is not None


def test_phase_1042_production_files_exist() -> None:
    for path in PHASE_1042_PRODUCTION_FILES:
        assert path.exists(), path


# ── Parallel-owner scan ───────────────────────────────────────────────────


def test_no_parallel_owner_definitions() -> None:
    offenders: list[str] = []
    for path in PHASE_1042_PRODUCTION_FILES:
        for name in _defined_names(path):
            if name in ALLOWED_DEFINITION_NAMES or name.startswith("_"):
                if name in ALLOWED_DEFINITION_NAMES:
                    continue
                if name.startswith(
                    ("_build_", "_prepare_", "_planned_", "_stable_", "_clean_")
                ):
                    continue
            if name in ALLOWED_DEFINITION_NAMES:
                continue
            for token in FORBIDDEN_OWNER_TOKENS:
                if token in name:
                    offenders.append(f"{path.name}:{name}")
                    break
    assert offenders == [], offenders


def test_integrator_creates_no_stateful_infrastructure() -> None:
    path = ROOT / "cmm" / "domains" / "planner_workflow_integration.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            called = func.id
        elif isinstance(func, ast.Attribute):
            called = func.attr
        else:
            continue
        if called in ALLOWED_DEFINITION_NAMES:
            continue
        if called.endswith(FORBIDDEN_INSTANTIATION_SUFFIXES):
            offenders.append(f"{path.name}:{called}")
    assert offenders == [], offenders


def test_integrator_holds_no_store_or_engine_state() -> None:
    for attr in vars(DefaultDomainPlannerWorkflowIntegrator):
        lowered = attr.lower()
        assert "store" not in lowered, attr
        assert "engine" not in lowered, attr
        assert "registry" not in lowered or attr == "__doc__", attr


# ── Fragmentation validator ───────────────────────────────────────────────


def test_fragmentation_guard_still_flags_duplicate_planner() -> None:
    findings = analyze_fragmentation(
        "class DomainPlanner:\n    pass\n",
        "phase1042_owner.py",
    )
    assert "DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION" in {
        str(finding["code"]) for finding in findings
    }


def test_fragmentation_guard_flags_duplicate_workflow_engine() -> None:
    findings = analyze_fragmentation(
        "class DomainWorkflowEngine:\n    pass\n",
        "phase1042_owner.py",
    )
    assert "DOMAIN_FRAGMENTATION_WORKFLOW_ENGINE_DUPLICATION" in {
        str(finding["code"]) for finding in findings
    }


def test_phase_1042_modules_raise_no_planner_or_engine_findings() -> None:
    forbidden_codes = {
        "DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION",
        "DOMAIN_FRAGMENTATION_WORKFLOW_ENGINE_DUPLICATION",
        "DOMAIN_FRAGMENTATION_AGENT_RUNTIME_DUPLICATION",
        "DOMAIN_FRAGMENTATION_PERMISSION_SYSTEM_DUPLICATION",
        "DOMAIN_FRAGMENTATION_REGISTRY_DUPLICATION",
    }
    offenders: list[str] = []
    for path in PHASE_1042_PRODUCTION_FILES:
        findings = analyze_fragmentation(path.read_text(encoding="utf-8"), path.name)
        for finding in findings:
            if str(finding["code"]) in forbidden_codes:
                offenders.append(f"{path.name}:{finding['code']}")
    assert offenders == [], offenders
