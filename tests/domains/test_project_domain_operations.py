"""Phase 10.30 — Project Domain Operations Tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.domains.enums import DomainOperationStatus
from cmm.domains.errors import DomainOperationRegistryError
from cmm.domains.operation_availability import (
    DomainOperationAvailabilityContext,
    DomainOperationAvailabilityResolver,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.project.catalog import CANONICAL_PROJECT_OPERATION_IDS
from cmm.domains.project.operations import (
    build_prepare_commit_readiness_result,
    build_project_operation_definitions,
    create_project_overview_result,
    generate_project_progress_summary_result,
    plan_project_milestones_result,
    review_project_dependencies_result,
    review_project_resources_result,
    review_project_risks_result,
    review_project_status_result,
)


def test_build_project_operation_definitions_inventory() -> None:
    ops = build_project_operation_definitions()
    assert len(ops) == 20
    assert tuple(op.operation_id for op in ops) == CANONICAL_PROJECT_OPERATION_IDS
    assert all(op.domain_id == "domain:project" for op in ops)

    # Legacy operation is not canonical
    assert "project.review_change" in [op.operation_id for op in ops]
    assert "project.prepare_change_review" not in [op.operation_id for op in ops]


def test_modify_code_declares_real_file_modify_capability_only() -> None:
    operations = {op.operation_id: op for op in build_project_operation_definitions()}

    modify = operations["project.modify_code"]
    assert modify.required_permissions == (PermissionCapability.FILE_MODIFY.value,)

    all_permissions = {
        permission
        for operation in operations.values()
        for permission in operation.required_permissions
    }
    assert "permission.file.modify" not in all_permissions
    assert "domain-permission:project:1.0.0" not in all_permissions

    for op_id, op in operations.items():
        if op_id != "project.modify_code":
            assert PermissionCapability.FILE_MODIFY.value not in op.required_permissions


def test_operations_unavailable_without_implementation() -> None:
    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    ops = build_project_operation_definitions()

    for op in ops:
        # Register without implementation
        registry.register(op, implementation=None)
        with pytest.raises(
            DomainOperationRegistryError,
            match="has no implementation and is UNAVAILABLE",
        ):
            registry.get_implementation(op.operation_id, op.version)
        # Common descriptor is disabled when registered with implementation=None
        desc = common.resolve(op.operation_id, op.version)
        assert desc.enabled is False

    resolver = DomainOperationAvailabilityResolver()
    context = DomainOperationAvailabilityContext(
        primary_domain_id="domain:project",
        granted_permissions=(
            "domain-permission:project:1.0.0",
            PermissionCapability.FILE_MODIFY.value,
            "resource.read",
            "memory.read",
        ),
        available_resources=(),
    )
    for op in ops:
        # Resolving disabled definition returns UNAVAILABLE
        disabled_op = replace(op, enabled=False)
        availability = resolver.resolve(disabled_op, context)
        assert availability.status is DomainOperationStatus.UNAVAILABLE

        # Resolving with missing resources also returns UNAVAILABLE
        res_availability = resolver.resolve(op, context)
        assert res_availability.status is DomainOperationStatus.UNAVAILABLE


def test_generic_result_builders_proposals() -> None:
    overview = create_project_overview_result(
        project_id="proj:1",
        title="Test Project",
        objective="Build system",
        scope={"deliverables": ["core"]},
    )
    assert overview["is_proposal"] is True
    assert overview["project_id"] == "proj:1"

    status_res = review_project_status_result(
        project_id="proj:1",
        status="active",
        milestones=[{"id": "m1", "status": "active"}],
    )
    assert status_res["status"] == "active"
    assert status_res["is_proposal"] is True

    plan_res = plan_project_milestones_result(
        project_id="proj:1",
        proposed_milestones=[{"id": "m1", "title": "M1"}],
    )
    assert plan_res["is_proposal"] is True
    assert len(plan_res["proposed_milestones"]) == 1

    dep_res = review_project_dependencies_result(
        dependencies=[{"source": "m1", "target": "m2"}],
    )
    assert dep_res["valid"] is True
    assert dep_res["is_proposal"] is True

    res_res = review_project_resources_result(
        resources=[{"kind": "devs", "available": 2}],
        requirements=[{"kind": "devs", "required": 1}],
    )
    assert res_res["feasible"] is True
    assert res_res["is_proposal"] is True

    risk_res = review_project_risks_result(
        risks=[{"id": "r1", "severity": "medium", "description": "delay"}],
    )
    assert risk_res["is_proposal"] is True
    assert len(risk_res["risks"]) == 1

    prog_res = generate_project_progress_summary_result(
        project_id="proj:1",
        progress_claims=[{"id": "c1", "deliverable": "core"}],
        evidence=[{"deliverable": "core", "status": "verified"}],
    )
    assert prog_res["supported"] is True
    assert prog_res["is_proposal"] is True


def test_prepare_commit_readiness_semantics() -> None:
    # Failed validation
    failed = build_prepare_commit_readiness_result(
        change_id="change:1",
        validation_passed=False,
        validation_reference="validation:1",
        commit_gate_allowed=False,
        approval_reference=None,
        authoritative_commit_reference=None,
    )
    assert failed["ready_for_approved_commit"] is False
    assert failed["committed"] is False
    assert "commit_hash" not in failed

    # Validation passed but no approval
    unapproved = build_prepare_commit_readiness_result(
        change_id="change:1",
        validation_passed=True,
        validation_reference="validation:1",
        commit_gate_allowed=True,
        approval_reference=None,
        authoritative_commit_reference=None,
    )
    assert unapproved["ready_for_approved_commit"] is False
    assert unapproved["committed"] is False

    # Validation passed + approval -> ready for commit, but NOT committed
    ready = build_prepare_commit_readiness_result(
        change_id="change:1",
        validation_passed=True,
        validation_reference="validation:1",
        commit_gate_allowed=True,
        approval_reference="approval:1",
        authoritative_commit_reference=None,
    )
    assert ready["ready_for_approved_commit"] is True
    assert ready["committed"] is False
    assert "commit_hash" not in ready

    # External caller-provided reference NEVER produces committed=True
    caller_ref = build_prepare_commit_readiness_result(
        change_id="change:1",
        validation_passed=True,
        validation_reference="validation:1",
        commit_gate_allowed=True,
        approval_reference="approval:1",
        authoritative_commit_reference="git:commit:abcdef123456",
    )
    assert caller_ref["ready_for_approved_commit"] is True
    assert caller_ref["committed"] is False

    # Fake reference with failed validation / gate / approval never commits
    fake_failed = build_prepare_commit_readiness_result(
        change_id="change:1",
        validation_passed=False,
        validation_reference=None,
        commit_gate_allowed=False,
        approval_reference=None,
        authoritative_commit_reference="caller:fake",
    )
    assert fake_failed["ready_for_approved_commit"] is False
    assert fake_failed["committed"] is False


def test_prepare_commit_does_not_mutate_git_head(tmp_path: Path) -> None:
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "file.py").write_text("print('hello')\n")
    subprocess.run(["git", "add", "file.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True
    )

    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    result = build_prepare_commit_readiness_result(
        change_id="change:repo:1",
        validation_passed=True,
        validation_reference="validation:p7",
        commit_gate_allowed=True,
        approval_reference="appr:1",
        authoritative_commit_reference="caller:fake",
    )
    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert head_after == head_before
    assert result["ready_for_approved_commit"] is True
    assert result["committed"] is False


def test_no_direct_execution_in_operations_source() -> None:
    source = Path("cmm/domains/project/operations.py").read_text()
    forbidden = (
        "subprocess",
        "os.system",
        "shell=True",
        "git commit",
        "FilesystemExecutor",
        "GitExecutor",
        "SemanticRuntime",
    )
    for token in forbidden:
        assert token not in source, f"Found forbidden token {token!r} in operations.py"
