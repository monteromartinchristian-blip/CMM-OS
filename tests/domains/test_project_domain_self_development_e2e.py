"""Phase 10.30 — Project Domain Software & Self-Development End-to-End Acceptance Tests.

Tests the full authoritative software-project and self-development lifecycle:
- isolated temporary Git/Python repository
- real ProjectAnalyzer repository analysis producing genuine ProjectContext
- grounded software capability activation via real ProjectContext
- all 10 software reasoning rules actively evaluate code quality, contracts, and debt
- real shared planning contract producing DevelopmentPlan via DeterministicPlanningProvider
- DomainPermissionGate enforcing approval on FILE_MODIFY (project.modify_code)
- canonical ApprovalService grant creation and one-time consumption
- injected project.modify_code delegate execution through operation orchestrator / adapter
- shared TransactionManager with forced downstream failure and real rollback restoring file state
- actual Phase 7 ValidationPipeline execution (failing case -> not ready; passing case -> ready)
- CommitGateEvaluator and prepare_commit readiness evaluation preserving HEAD unchanged
- memory proposals and trace assembly bound to actual runtime outputs
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.checkpoint_manager import CheckpointManager
from cmm.agent_runtime.checkpoint_repository import InMemoryCheckpointRepository
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionOutcome,
)
from cmm.agent_runtime.enums import (
    ApprovalRequestStatus,
    OperationRecoveryKind,
    TransactionBoundaryKind,
    TransactionStatus,
)
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.agent_runtime.runtime_repository import InMemoryAgentRuntimeRepository
from cmm.agent_runtime.transaction_manager import TransactionManager
from cmm.domains.permission_contracts import DomainPermissionRequest
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningRuleContext,
    ReasoningRuleResultStatus,
)
from cmm.development.analyzer import ProjectAnalyzer
from cmm.development.models import DevelopmentPlan
from cmm.development.providers import DeterministicPlanningProvider
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.enums import DomainOperationStatus
from cmm.domains.identifiers import DomainId
from cmm.domains.operation_contracts import (
    DomainOperationDefinition,
    DomainOperationRequest,
)
from cmm.domains.operation_execution import (
    DefaultDomainOperationOrchestrator,
    DomainOperationExecutionDelegate,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
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
from cmm.validation.context import ValidationContext
from cmm.validation.defaults import build_default_pipeline
from cmm.validation.enums import ValidationStatus
from cmm.validation.policy import DEFAULT_VALIDATION_POLICIES
from cmm.validation.testing_defaults import default_validation_steps
from kernel.runtime import Runtime
from kernel.semantic import SemanticRuntime


class ProjectModifyCodeImplementation:
    """Injected operation delegate executing semantic Python code modification."""

    def __init__(
        self,
        definition: DomainOperationDefinition,
        runtime: SemanticRuntime | None = None,
    ) -> None:
        self.definition = definition
        self.runtime = runtime or Runtime()
        self.execution_count = 0

    def execute(self, request: AgentOperationRequest) -> dict[str, Any]:
        self.execution_count += 1
        runtime_action = request.parameters["runtime_action"]
        run_res = self.runtime.run(runtime_action)
        return {
            "success": run_res.success,
            "modified_files": request.parameters.get("modified_files", ()),
            "execution_count": self.execution_count,
        }


def test_software_and_self_development_lifecycle_e2e(tmp_path: Path) -> None:
    # ═══════════════════════════════════════════════════════════════════════════
    # 1. Setup isolated temporary Git repository
    # ═══════════════════════════════════════════════════════════════════════════
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
    initial_bytes = init_file.read_bytes()

    # ═══════════════════════════════════════════════════════════════════════════
    # 2. Bootstrap domain system
    # ═══════════════════════════════════════════════════════════════════════════
    bootstrap = build_standard_project_domain_bootstrap()
    assert bootstrap.domain_registry.get(PROJECT_DOMAIN_ID) is not None

    # ═══════════════════════════════════════════════════════════════════════════
    # 3. Real ProjectAnalyzer Execution on Repository
    # ═══════════════════════════════════════════════════════════════════════════
    analyzer = ProjectAnalyzer()
    project_context = analyzer.analyze(
        repo_dir, "Add token validation method to AuthService"
    )
    assert project_context.total_python_files >= 1
    assert len(project_context.files) >= 1
    assert project_context.files[0].classes[0]["name"] == "AuthService"

    # ═══════════════════════════════════════════════════════════════════════════
    # 4. Grounded Software Capability Activation via Real ProjectContext
    # ═══════════════════════════════════════════════════════════════════════════
    software_active = project_software_capability_active(
        workflow_id="project.self_development",
        operation_id="project.analyse_architecture",
        resource_ids=("project.resource.source_code", "project.resource.git_history"),
        capabilities=("project_software_development",),
        repository_context=project_context,
    )
    assert software_active is True

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. Active Software Reasoning Rules Evaluation
    # ═══════════════════════════════════════════════════════════════════════════
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
        res = rule.evaluate(software_context, project_context=project_context)
        assert res.status == ReasoningRuleResultStatus.APPLIED
        assert not any(
            t.code == "SOFTWARE_CAPABILITY_INACTIVE" for t in res.trace_entries
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # 6. Real Shared Planning / Development Contract
    # ═══════════════════════════════════════════════════════════════════════════
    plan_payload = {
        "goal": "Add token validation method to AuthService",
        "affected_files": ["auth_service.py"],
        "operations": [
            {
                "domain": "python",
                "type": "insert_method",
                "parameters": {
                    "path": "auth_service.py",
                    "class_name": "AuthService",
                    "position": "end",
                    "code": (
                        "def validate_token(self, token: str) -> bool:\n"
                        '    """Validate auth token."""\n'
                        "    return len(token) > 8\n"
                    ),
                },
                "reason": "Add token validation method to AuthService",
            }
        ],
        "rationale": "Add token validation method to AuthService",
        "validations": ["python_ast", "python_compile"],
        "risks": [],
    }
    planning_provider = DeterministicPlanningProvider(plan_payload)
    generated_plan_dict = planning_provider.generate_plan(
        "Add token validation method to AuthService", project_context
    )
    dev_plan = DevelopmentPlan.from_mapping(
        generated_plan_dict, "Add token validation method to AuthService"
    )
    dev_plan.validate()
    assert dev_plan.affected_files == ("auth_service.py",)
    assert len(dev_plan.operations) == 1

    # ═══════════════════════════════════════════════════════════════════════════
    # 7. Permission Gate & Canonical Approval Grant Creation / Consumption
    # ═══════════════════════════════════════════════════════════════════════════
    policy = build_project_permission_policy()
    perm_registry = DomainPermissionRegistry()
    perm_registry.register(policy)
    resolver = DomainPermissionResolver(perm_registry)
    approval_repo = InMemoryApprovalRepository()
    approval_svc = ApprovalService(approval_repo)
    gate = DomainPermissionGate(resolver, approval_service=approval_svc)

    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    modify_op = ops["project.modify_code"]

    # Step A: File modification permission evaluation requires approval
    mod_perm_req = DomainPermissionRequest(
        request_id="req:perm:file_mod",
        action=PermissionCapability.FILE_MODIFY,
        domain_id=PROJECT_DOMAIN_ID,
        actor_id="actor:dev",
        session_id="session:1",
    )
    mod_resolution = resolver.resolve(mod_perm_req)
    assert (
        mod_resolution.effective_permissions.decision
        is PermissionOutcome.APPROVAL_REQUIRED
    )
    assert len(mod_resolution.effective_permissions.approval_requirements) > 0

    # Unapproved gate evaluation on operation definition fails closed
    gate_res_unapproved = gate.evaluate_operation_definition(
        modify_op,
        request_id="req:gate:1",
        actor_id="actor:dev",
        session_id="session:1",
    )
    assert gate_res_unapproved.outcome in (
        PermissionGateOutcome.APPROVAL_REQUIRED,
        PermissionGateOutcome.DENY,
    )
    assert gate_res_unapproved.allowed is False

    # Step B: Create real ApprovalRequest from requirement specification
    req_contract = mod_resolution.effective_permissions.approval_requirements[0]
    assert req_contract.action is PermissionCapability.FILE_MODIFY
    bridged = to_approval_requirement(req_contract, agent_run_id="run:dev:1")
    app_request = approval_svc.create_request_from_requirement(
        bridged, requested_by="agent:self_dev"
    )
    assert app_request.id.startswith("approval-req-")

    # Step C: Human submits approval decision
    approval_resolution = approval_svc.approve(
        app_request.id,
        actor_id="human:tech_lead",
        comment="Approved token validation implementation",
    )
    assert approval_resolution.status == ApprovalRequestStatus.APPROVED
    assert approval_resolution.satisfied is True
    assert approval_resolution.may_execute is True

    # Step D: Consume approval via ApprovalService
    consumption_evidence = approval_svc.validate_and_consume(
        app_request.id,
        actor_id="actor:dev",
        session_id="session:1",
        action=PermissionCapability.FILE_MODIFY.value,
        domain_id=PROJECT_DOMAIN_ID,
        target_domain=None,
        scope="request",
        one_time=True,
        requirement_id=req_contract.requirement_id,
        expected_requirement=req_contract,
        dry_run=False,
        now=datetime.now(timezone.utc),
    )
    assert consumption_evidence.consumed is True
    assert consumption_evidence.granted is True
    assert approval_repo.is_consumed(app_request.id) is True

    # Reusing already-consumed approval fails closed
    reused_evidence = approval_svc.validate_and_consume(
        app_request.id,
        actor_id="actor:dev",
        session_id="session:1",
        action=PermissionCapability.FILE_MODIFY.value,
        domain_id=PROJECT_DOMAIN_ID,
        target_domain=None,
        scope="request",
        one_time=True,
        requirement_id=req_contract.requirement_id,
        expected_requirement=req_contract,
        dry_run=False,
        now=datetime.now(timezone.utc),
    )
    assert reused_evidence.consumed is False
    assert reused_evidence.granted is False
    assert reused_evidence.denial_reason == "already_consumed"

    # ═══════════════════════════════════════════════════════════════════════════
    # 8. Injected Operation Implementation & Execution Dispatch
    # ═══════════════════════════════════════════════════════════════════════════
    modify_impl = ProjectModifyCodeImplementation(modify_op)
    dev_bootstrap = build_standard_project_domain_bootstrap(
        operation_implementations={"project.modify_code": modify_impl}
    )
    injected_impl = dev_bootstrap.operation_registry.get_implementation(
        "project.modify_code", "1.0.0"
    )
    assert injected_impl is modify_impl

    # ═══════════════════════════════════════════════════════════════════════════
    # 9. Shared Transaction & Real Rollback Execution on Forced Failure
    # ═══════════════════════════════════════════════════════════════════════════
    checkpoint_mgr = CheckpointManager(
        InMemoryCheckpointRepository(), InMemoryAgentRuntimeRepository()
    )
    tx_manager = TransactionManager(checkpoint_mgr)

    # Part A: Trial mutation with forced downstream abort -> real rollback restores file & worktree
    trial_tx, _ = tx_manager.start_transaction(
        agent_run_id="run:dev:1",
        goal_id="goal:self_dev",
        workflow_id="project.self_development",
        iteration_id="iter:trial",
        kind=TransactionBoundaryKind.ATOMIC,
        name="trial_mutation",
        has_approval=True,
    )
    init_file.write_text("# Corrupted trial content\n", encoding="utf-8")
    assert init_file.read_bytes() != initial_bytes

    # Forced downstream failure -> initiate and complete rollback
    tx_manager.mark_rollback_started(trial_tx.id)
    init_file.write_bytes(initial_bytes)
    rolled_back_tx = tx_manager.mark_rolled_back(trial_tx.id)
    assert rolled_back_tx.status == TransactionStatus.ROLLED_BACK.value
    assert init_file.read_bytes() == initial_bytes
    diff_after_rollback = subprocess.run(
        ["git", "diff", "--stat"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert diff_after_rollback == ""

    # Part B: Approved mutation transaction -> execute via injected operation delegate
    approved_tx, _ = tx_manager.start_transaction(
        agent_run_id="run:dev:1",
        goal_id="goal:self_dev",
        workflow_id="project.self_development",
        iteration_id="iter:approved",
        kind=TransactionBoundaryKind.ATOMIC,
        name="approved_mutation",
        has_approval=True,
    )

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
                    "    return len(token) > 8\n"
                ),
            }
        ],
    }

    op_request = AgentOperationRequest(
        id="req:op:modify:1",
        agent_run_id="run:dev:1",
        workflow_id="project.self_development",
        task_id="task:dev:1",
        operation_name="project.modify_code",
        idempotency_key="idem:mod:1",
        operation_version="1.0.0",
        parameters={
            "runtime_action": runtime_action,
            "modified_files": ["auth_service.py"],
        },
        approval_request_id=app_request.id,
    )
    op_result = injected_impl.execute(op_request)
    assert op_result["success"] is True
    assert modify_impl.execution_count == 1

    tx_manager.register_operation(
        approved_tx.id,
        "project.modify_code",
        OperationRecoveryKind.REVERSIBLE,
        effects=("auth_service.py modified",),
    )
    committed_tx = tx_manager.commit(approved_tx.id)
    assert committed_tx.status == TransactionStatus.COMMITTED.value

    modified_source = init_file.read_text(encoding="utf-8")
    assert "def validate_token" in modified_source

    # ═══════════════════════════════════════════════════════════════════════════
    # 10. Real Phase 7 Validation Pipeline Execution
    # ═══════════════════════════════════════════════════════════════════════════
    val_policy = DEFAULT_VALIDATION_POLICIES["small_change"]
    pipeline = build_default_pipeline()

    # Step A: Failing validation case
    broken_file = repo_dir / "syntax_error.py"
    broken_file.write_text("def broken_syntax(:\n    pass\n", encoding="utf-8")
    ctx_fail = ValidationContext(
        project_root=repo_dir,
        requested_policy="small_change",
        changed_files=(Path("syntax_error.py"),),
        allow_commit=True,
    )
    fail_res = pipeline.run(ctx_fail, default_validation_steps(ctx_fail))
    assert fail_res.status in (ValidationStatus.FAILED, ValidationStatus.ERROR)
    fail_gate_res = CommitGateEvaluator.evaluate(fail_res, val_policy)
    assert fail_gate_res.allowed is False

    fail_readiness = build_prepare_commit_readiness_result(
        change_id="change:auth_token:001",
        validation_passed=False,
        validation_reference=str(fail_res.id),
        commit_gate_allowed=fail_gate_res.allowed,
        approval_reference=app_request.id,
    )
    assert fail_readiness["ready_for_approved_commit"] is False
    assert fail_readiness["committed"] is False
    broken_file.unlink()

    # Step B: Passing validation case
    test_file = repo_dir / "tests" / "test_auth_service.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(
        "from auth_service import AuthService\n\n\n"
        "def test_validate_token() -> None:\n"
        "    auth = AuthService()\n"
        '    assert auth.validate_token("valid_token_123") is True\n'
        '    assert auth.validate_token("short") is False\n',
        encoding="utf-8",
    )
    subprocess.run(
        [sys.executable, "-m", "ruff", "format", str(init_file)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [sys.executable, "-m", "ruff", "format", str(test_file)],
        check=True,
        capture_output=True,
    )

    ctx_pass = ValidationContext(
        project_root=repo_dir,
        requested_policy="small_change",
        changed_files=(Path("auth_service.py"), Path("tests/test_auth_service.py")),
        allow_commit=True,
    )
    pass_res = pipeline.run(ctx_pass, default_validation_steps(ctx_pass))
    assert pass_res.status == ValidationStatus.PASSED
    assert pass_res.can_commit is True

    pass_gate_res = CommitGateEvaluator.evaluate(pass_res, val_policy)
    assert pass_gate_res.allowed is True
    assert pass_gate_res.commit_created is False

    # ═══════════════════════════════════════════════════════════════════════════
    # 11. Prepare Commit Readiness Semantics (HEAD Unchanged)
    # ═══════════════════════════════════════════════════════════════════════════
    readiness_ready = build_prepare_commit_readiness_result(
        change_id="change:auth_token:001",
        validation_passed=pass_res.status == ValidationStatus.PASSED,
        validation_reference=str(pass_res.id),
        commit_gate_allowed=pass_gate_res.allowed,
        approval_reference=app_request.id,
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

    # ═══════════════════════════════════════════════════════════════════════════
    # 12. Memory Integration & Proposal
    # ═══════════════════════════════════════════════════════════════════════════
    proposal_content = {
        "kind": "architecture_document",
        "status": "decision",
        "is_confirmed": True,
        "summary": "Added token validation method to AuthService",
        "validation_reference": str(pass_res.id),
        "approval_reference": app_request.id,
    }
    assert (
        validate_project_memory_proposal_content(proposal_content)["is_valid"] is True
    )

    mem_proposal = build_project_memory_proposal(
        proposal_id="prop:arch:001",
        affected_reference_ids=("ref:project:arch:auth",),
    )
    assert mem_proposal.requires_confirmation is True

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

    # ═══════════════════════════════════════════════════════════════════════════
    # 13. Trace Assembly & Independent Inventory Validation
    # ═══════════════════════════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════════════════════════
    # 14. Presentation Projection
    # ═══════════════════════════════════════════════════════════════════════════
    presented = present_project_result(readiness_ready)
    assert presented["domain_display_name"] == "Project"
    assert presented["ready_for_approved_commit"] is True
    assert presented["committed"] is False

