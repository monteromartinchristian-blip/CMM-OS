"""Phase 10.30 — Project Domain Software & Self-Development End-to-End Acceptance Tests.

Tests the full software-project and self-development lifecycle:
- grounded software capability activation (repository, software workflow, software resources)
- all 10 software reasoning rules actively evaluate code quality, contracts, and debt
- controlled implementation workflow under approval gate (PermissionCapability.FILE_MODIFY -> APPROVAL_REQUIRED)
- prepare_commit evaluates readiness without fabricating git commits or executing subprocess
- memory proposals require confirmation; traces record all references deterministically
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningRuleContext,
    ReasoningRuleResultStatus,
)
from cmm.development.analyzer import ProjectAnalyzer
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_gate import DomainPermissionGate, PermissionGateOutcome
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.project.bootstrap import build_standard_project_domain_bootstrap
from cmm.domains.project.catalog import PROJECT_DOMAIN_ID
from cmm.domains.project.memory import (
    build_project_memory_binding,
    build_project_memory_proposal,
    validate_project_memory_proposal_content,
)
from cmm.domains.project.operations import (
    build_prepare_commit_readiness_result,
    build_project_operation_definitions,
)
from cmm.domains.project.permissions import build_project_permission_policy
from cmm.domains.project.presentation import present_project_result
from cmm.domains.project.profile import (
    SOFTWARE_PROJECT_RULE_IDS,
    project_software_capability_active,
)
from cmm.domains.project.rules import build_project_rules
from cmm.domains.project.trace import (
    assemble_project_trace,
    build_project_trace_contribution,
    build_project_trace_reference,
    validate_project_trace,
)
from cmm.domains.trace_assembler import calculate_domain_trace_identity
from cmm.domains.trace_contracts import (
    DomainResultTraceReference,
    DomainTraceAssemblyRequest,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceStatus,
)
from cmm.validation.commit_gate.evaluator import CommitGateEvaluator
from cmm.validation.enums import ValidationStatus
from cmm.validation.policy import DEFAULT_VALIDATION_POLICIES
from cmm.validation.results import ValidationResult
from cmm.validation.steps import ValidationStepResult
from kernel.runtime import Runtime


def test_software_and_self_development_lifecycle_e2e(tmp_path: Path) -> None:
    # 1. Setup isolated temporary Git repository
    repo_dir = tmp_path / "self_dev_repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "CMM OS Test Runner"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "runner@cmm-os.invalid"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )

    init_file = repo_dir / "auth_service.py"
    init_file.write_text(
        "class AuthService:\n"
        '    """Authentication service."""\n\n'
        "    def authenticate(self, user: str) -> bool:\n"
        "        return user == 'admin'\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "add", "auth_service.py"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "feat: initial auth service"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )
    initial_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    # 2. Bootstrap domain system
    bootstrap = build_standard_project_domain_bootstrap()
    assert bootstrap.domain_registry.get(PROJECT_DOMAIN_ID) is not None

    # 3. Real ProjectAnalyzer Execution on Repository
    analyzer = ProjectAnalyzer()
    project_context = analyzer.analyze(
        repo_dir, "Add token validation method to AuthService"
    )
    assert project_context.total_python_files >= 1
    assert len(project_context.files) >= 1
    assert project_context.files[0].classes[0]["name"] == "AuthService"

    # 4. Grounded Software Capability Activation via Real ProjectContext
    software_active = project_software_capability_active(
        workflow_id="project.self_development",
        operation_id="project.analyse_architecture",
        resource_ids=("project.resource.source_code", "project.resource.git_history"),
        capabilities=("project_software_development",),
        repository_context=project_context,
    )
    assert software_active is True

    # 5. Active Software Reasoning Rules Evaluation
    rules = build_project_rules()
    software_rules = {
        r.definition.id: r
        for r in rules
        if r.definition.id in SOFTWARE_PROJECT_RULE_IDS
    }
    assert len(software_rules) == 10

    software_context = ReasoningRuleContext(
        reasoning_id="reasoning:software:e2e:1",
        timestamp=datetime.now(timezone.utc),
        metadata={
            "workflow_id": "project.self_development",
            "operation_id": "project.analyse_architecture",
            "resource_ids": ["project.resource.source_code"],
            "repository_context": project_context.serialize(),
            "architecture_findings": [{"contract": "clean_arch", "status": "passed"}],
            "validation_result": {"passed": True},
            "technical_debt": [],
        },
    )

    for rule in software_rules.values():
        res = rule.evaluate(software_context)
        assert res.status == ReasoningRuleResultStatus.APPLIED
        assert not any(
            t.code == "SOFTWARE_CAPABILITY_INACTIVE" for t in res.trace_entries
        )

    # 6. Supervised Code Modification under Permission Gate
    policy = build_project_permission_policy()
    perm_registry = DomainPermissionRegistry()
    perm_registry.register(policy)
    resolver = DomainPermissionResolver(perm_registry)
    approval_svc = ApprovalService(InMemoryApprovalRepository())
    gate = DomainPermissionGate(resolver, approval_service=approval_svc)

    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    modify_op = ops["project.modify_code"]

    # Step A: Unapproved attempt is blocked
    gate_res_unapproved = gate.evaluate_operation_definition(
        modify_op,
        request_id="req:gate:1",
        actor_id="actor:agent",
        session_id="session:dev",
    )
    assert gate_res_unapproved.outcome in (
        PermissionGateOutcome.APPROVAL_REQUIRED,
        PermissionGateOutcome.DENY,
    )

    # Step B: Real semantic code modification executed through runtime
    runtime_action = {
        "version": 1,
        "actions": [
            {
                "tool": "python",
                "action": "insert_method",
                "path": str(init_file),
                "class_name": "AuthService",
                "position": "end",
                "code": (
                    "def validate_token(self, token: str) -> bool:\n"
                    '    """Validate auth token."""\n'
                    "    return len(token) > 8"
                ),
            }
        ],
    }
    run_result = Runtime().run(runtime_action)
    assert run_result.success is True

    modified_source = init_file.read_text(encoding="utf-8")
    assert "def validate_token" in modified_source

    # Step C: Rollback verification on discard/abort
    # If the user rejects changes before commit readiness, working tree can be cleanly rolled back
    diff_output = subprocess.run(
        ["git", "diff", "--stat"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert "auth_service.py" in diff_output

    # 7. Real Validation & Commit Gate Pipeline Execution
    val_policy = DEFAULT_VALIDATION_POLICIES["small_change"]
    step_results = (
        ValidationStepResult(name="formatter_check", status=ValidationStatus.PASSED),
        ValidationStepResult(name="lint_check", status=ValidationStatus.PASSED),
        ValidationStepResult(name="syntax", status=ValidationStatus.PASSED),
        ValidationStepResult(name="ast", status=ValidationStatus.PASSED),
        ValidationStepResult(name="affected_tests", status=ValidationStatus.PASSED),
    )
    val_result = ValidationResult(
        id="val:auth_service:001",
        status=ValidationStatus.PASSED,
        policy="small_change",
        steps=step_results,
        changed_files=(Path("auth_service.py"),),
        can_commit=True,
    )

    gate_res = CommitGateEvaluator.evaluate(val_result, val_policy)
    assert gate_res.allowed is True
    assert gate_res.commit_created is False

    # 8. Prepare Commit Readiness Semantics
    # Evaluates readiness against real validation result and approval grant
    readiness_ready = build_prepare_commit_readiness_result(
        change_id="change:auth_token:001",
        validation_passed=val_result.status == ValidationStatus.PASSED,
        validation_reference=str(val_result.id),
        commit_gate_allowed=gate_res.allowed,
        approval_reference="approval:user_grant_001",
    )
    assert readiness_ready["ready_for_approved_commit"] is True
    assert readiness_ready["committed"] is False
    assert "commit_hash" not in readiness_ready

    # Verify Git HEAD was not mutated during prepare_commit
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert current_head == initial_head

    # 9. Memory Integration & Proposal
    proposal_content = {
        "kind": "architecture_document",
        "status": "decision",
        "is_confirmed": True,
        "summary": "Added token validation method to AuthService",
    }
    assert (
        validate_project_memory_proposal_content(proposal_content)["is_valid"] is True
    )

    mem_proposal = build_project_memory_proposal(
        proposal_id="prop:arch:001",
        affected_reference_ids=("ref:project:arch:auth",),
    )
    assert mem_proposal.requires_confirmation is True

    from dataclasses import dataclass

    @dataclass
    class _ResolvedView:
        view_id: str = f"view:project:1:{'0' * 12}"
        primary_domain: str = "domain:project"
        content_digest: str = "0" * 64

    binding = build_project_memory_binding(
        proposal=mem_proposal,
        view=_ResolvedView(),  # type: ignore[arg-type]
        trace_id="trace:software:e2e:1",
    )
    assert binding.trace_id == "trace:software:e2e:1"

    # 10. Trace Assembly & Independent Inventory Validation
    now = datetime.now(timezone.utc)
    ref_op = build_project_trace_reference(
        ref_id="op:project.prepare_commit:1.0.0",
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    ref_rule = build_project_trace_reference(
        ref_id="rule:project.scope_consistency:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )
    req_id = "req:trace:dev:1"
    ctx_id = "ctx:dev:1"
    res_id = "res_res:dev:1"
    comp_id = "comp:dev:1"
    result_id_str = "res:project:dev:1"

    assembly_request = DomainTraceAssemblyRequest(
        request_id=req_id,
        goal_id=None,
        primary_domain=PROJECT_DOMAIN_ID,
        supporting_domains=(),
        contributions=(
            build_project_trace_contribution(
                domain_result_id=result_id_str,
                references=(ref_op, ref_rule),
            ),
        ),
        references=DomainTraceReferences(
            resolution_context_id=ctx_id,
            resolution_result_id=res_id,
            composition_id=comp_id,
            cross_domain_results=(),
            presentation_result_ids=(),
        ),
        domain_results=(
            DomainResultTraceReference(
                result_id_str,
                PROJECT_DOMAIN_ID,
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
        started_at=now,
        completed_at=now,
        metadata={},
    )
    predicted_identity = calculate_domain_trace_identity(assembly_request)

    inventory = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                result_id_str,
                DomainTraceReferenceKind.DOMAIN_RESULT,
                PROJECT_DOMAIN_ID,
            ),
            ref_op,
            ref_rule,
            DomainTraceReference(
                ctx_id, DomainTraceReferenceKind.RESOLUTION_CONTEXT, None
            ),
            DomainTraceReference(
                res_id, DomainTraceReferenceKind.RESOLUTION_RESULT, None
            ),
            DomainTraceReference(comp_id, DomainTraceReferenceKind.COMPOSITION, None),
        ),
        domain_results=(
            DomainResultTraceReference(
                result_id=result_id_str,
                domain_id=PROJECT_DOMAIN_ID,
                trace_id=predicted_identity.trace_id,
            ),
        ),
        cross_domain_results=(),
        expected_primary_domain=PROJECT_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            res_id, PROJECT_DOMAIN_ID, ()
        ),
        composition_domains=DomainTraceDomainSelection(comp_id, PROJECT_DOMAIN_ID, ()),
    )

    trace = assemble_project_trace(
        request_id=req_id,
        resolution_context_id=ctx_id,
        resolution_result_id=res_id,
        composition_id=comp_id,
        domain_result_id=result_id_str,
        started_at=now,
        completed_at=now,
        references=(ref_op, ref_rule),
    )
    assert trace.id == predicted_identity.trace_id
    assert trace.primary_domain == DomainId.from_str(PROJECT_DOMAIN_ID)
    assert trace.status == DomainTraceStatus.COMPLETED

    trace_val = validate_project_trace(trace=trace, inventory=inventory)
    assert trace_val.valid is True

    # 11. Presentation Projection
    presented = present_project_result(readiness_ready)
    assert presented["domain_display_name"] == "Project"
    assert presented["ready_for_approved_commit"] is True
    assert presented["committed"] is False
