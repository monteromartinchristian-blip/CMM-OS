"""Phase 10.30 — Project Domain Software & Self-Development End-to-End Acceptance Tests.

Tests the full authoritative software-project and self-development lifecycle:
- isolated temporary Git/Python repository
- real ProjectAnalyzer repository analysis producing genuine ProjectContext
- grounded software capability activation via real ProjectContext
- all 10 software reasoning rules actively evaluate code quality, contracts, and debt
- real shared planning contract producing DevelopmentPlan via DeterministicPlanningProvider
- DomainPermissionGate enforcing approval on FILE_MODIFY (project.modify_code)
- canonical ApprovalService grant creation and one-time consumption
- injected project.modify_code execution through DefaultDomainOperationOrchestrator and AgentExecutionAdapter
- shared TransactionManager with forced downstream failure and real rollback restoring file state without manual file writes
- actual Phase 7 ValidationPipeline execution (failing case -> not ready; passing case -> ready)
- CommitGateEvaluator and prepare_commit readiness evaluation preserving HEAD unchanged
- memory proposals and trace assembly bound to actual runtime outputs
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.checkpoint_manager import CheckpointManager
from cmm.agent_runtime.checkpoint_repository import InMemoryCheckpointRepository
from cmm.agent_runtime.checkpoint_restoration import CheckpointRestorationManager
from cmm.agent_runtime.checkpoint_rollback_executor import (
    CheckpointRestorationRollbackExecutor,
)
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionOutcome,
)
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.agent_runtime.transaction_manager import TransactionManager
from cmm.agent_runtime.validation_execution_adapter import AgentValidationAdapter
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningRuleContext,
    ReasoningRuleResultStatus,
)
from cmm.development.analyzer import ProjectAnalyzer
from cmm.development.models import DevelopmentPlan
from cmm.development.providers import DeterministicPlanningProvider
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.identifiers import DomainId
from cmm.domains.memory_contracts import sha256_digest
from cmm.domains.operation_contracts import (
    DomainOperationDefinition,
    DomainOperationRequest,
    DomainOperationStatus,
)
from cmm.domains.operation_execution import (
    DefaultDomainOperationOrchestrator,
    DomainOperationExecutionDelegate,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_adapters import evaluate_domain_operation
from cmm.domains.permission_gate import DomainPermissionGate
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


class RepoResourceVersionProvider:
    """Resource version provider that captures file snapshots in repo_dir and restores them."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path
        self._snapshots: dict[str, dict[Path, bytes]] = {}

    def capture_version(self, resource_key: str) -> str:
        files_state = {}
        for p in self.repo_path.rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                files_state[p] = p.read_bytes()
        digest_content = "".join(
            f"{p.relative_to(self.repo_path)}:{hashlib.sha256(b).hexdigest()};"
            for p, b in sorted(files_state.items(), key=lambda x: str(x[0]))
        )
        digest = hashlib.sha256(digest_content.encode("utf-8")).hexdigest()
        self._snapshots[digest] = files_state
        return digest

    def verify_version(self, resource_key: str, expected_version: str) -> bool:
        current = self.capture_version(resource_key)
        return current == expected_version

    def restore_version(self, resource_key: str, target_version: str) -> bool:
        if target_version not in self._snapshots:
            return False
        snapshot = self._snapshots[target_version]
        current_files = {
            p
            for p in self.repo_path.rglob("*")
            if p.is_file() and ".git" not in p.parts
        }
        for p in current_files - set(snapshot.keys()):
            p.unlink()
        for path, data in snapshot.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return True


class ProjectModifyCodeImplementation:
    """Injected operation delegate executing semantic Python code modification."""

    def __init__(
        self,
        definition: DomainOperationDefinition,
        runtime: SemanticRuntime | None = None,
        *,
        fail_after_mutation: bool = False,
    ) -> None:
        self.definition = definition
        self.runtime = runtime or Runtime()
        self.fail_after_mutation = fail_after_mutation
        self.execution_count = 0

    def execute(self, request: AgentOperationRequest) -> dict[str, Any]:
        self.execution_count += 1
        runtime_action = request.parameters["runtime_action"]
        run_res = self.runtime.run(runtime_action)
        if self.fail_after_mutation or request.parameters.get("force_failure"):
            return {
                "success": False,
                "error": {
                    "code": "OPERATION_EXECUTION_FAILED",
                    "message": "Forced failure after mutation to test rollback",
                    "details": {},
                },
                "output": {
                    "status": "failed",
                    "result": {
                        "modified_files": list(
                            request.parameters.get("modified_files", ())
                        )
                    },
                },
                "modified_files": request.parameters.get("modified_files", ()),
                "execution_count": self.execution_count,
            }
        return {
            "success": run_res.success,
            "output": {
                "status": "completed" if run_res.success else "failed",
                "result": {
                    "modified_files": list(request.parameters.get("modified_files", ()))
                },
            },
            "modified_files": request.parameters.get("modified_files", ()),
            "execution_count": self.execution_count,
        }


def _approve_operation_requirements(
    *,
    definition: DomainOperationDefinition,
    proto_request: DomainOperationRequest,
    resolver: DomainPermissionResolver,
    approval_service: ApprovalService,
    requested_by: str,
    approver_actor_id: str = "human:tech_lead",
) -> tuple[str, dict[str, str], tuple[PermissionApprovalRequirement, ...]]:
    actor_id = str(proto_request.metadata.get("actor_id", proto_request.agent_run_id))
    session_id = proto_request.session_id or proto_request.agent_run_id
    decision = evaluate_domain_operation(
        definition,
        resolver,
        request_id=proto_request.request_id,
        actor_id=actor_id,
        session_id=session_id,
    )
    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    approval_request_ids: dict[str, str] = {}
    operation_execute_approval_id: str | None = None
    for req in decision.approval_requirements:
        bridged = to_approval_requirement(
            req,
            agent_run_id=proto_request.agent_run_id,
        )
        app_req = approval_service.create_request_from_requirement(
            bridged,
            requested_by=requested_by,
            metadata_override={
                "domain_request_fingerprint": proto_request.calculate_fingerprint(),
            },
        )
        approval_service.approve(
            app_req.id,
            actor_id=approver_actor_id,
            comment=f"Approved requirement {req.requirement_id}",
        )
        approval_request_ids[req.requirement_id] = app_req.id
        if req.action is PermissionCapability.OPERATION_EXECUTE:
            operation_execute_approval_id = app_req.id

    assert operation_execute_approval_id is not None
    return (
        operation_execute_approval_id,
        approval_request_ids,
        decision.approval_requirements,
    )


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
    # 7. Permission Gate, Transaction Manager & Rollback Setup
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

    resource_provider = RepoResourceVersionProvider(repo_dir)
    cp_repo = InMemoryCheckpointRepository()
    cp_mgr = CheckpointManager(repository=cp_repo, resource_provider=resource_provider)
    tx_manager = TransactionManager(cp_mgr)
    rest_manager = CheckpointRestorationManager(
        repository=cp_repo, resource_provider=resource_provider
    )
    rollback_executor = CheckpointRestorationRollbackExecutor(
        transaction_manager=tx_manager, restoration_manager=rest_manager
    )

    modify_impl = ProjectModifyCodeImplementation(modify_op)
    common_registry = InMemoryAgentOperationRegistry()
    operation_registry = InMemoryDomainOperationRegistry(common_registry)
    operation_registry.register(modify_op, modify_impl)

    val_adapter = AgentValidationAdapter()
    execution_adapter = AgentExecutionAdapter(
        registry=common_registry,
        execution_delegate=DomainOperationExecutionDelegate(operation_registry),
        validation_adapter=val_adapter,
    )

    orchestrator = DefaultDomainOperationOrchestrator(
        operation_registry,
        execution_adapter,
        approval_service=approval_svc,
        permission_gate=gate,
        transaction_manager=tx_manager,
        rollback_executor=rollback_executor,
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # 8. Unapproved Mutation Blocked by Orchestrator
    # ═══════════════════════════════════════════════════════════════════════════
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

    unapproved_req = DomainOperationRequest(
        request_id="req:op:unapproved:1",
        operation_id=modify_op.operation_id,
        operation_version=modify_op.version,
        inputs={
            "runtime_action": runtime_action,
            "modified_files": ["auth_service.py"],
        },
        agent_run_id="run:dev:1",
        workflow_id="project.self_development",
        task_id="task:dev:1",
        session_id="session:1",
        primary_domain_id=PROJECT_DOMAIN_ID,
        idempotency_key="idem:unapproved:1",
        granted_permissions=modify_op.required_permissions,
        available_resources=modify_op.required_resources,
        capabilities=("execute", "transaction", "rollback", "validation"),
        metadata={"actor_id": "actor:dev"},
    )
    unapproved_result = orchestrator.execute(unapproved_req)
    assert unapproved_result.status in (
        DomainOperationStatus.WAITING_FOR_APPROVAL,
        DomainOperationStatus.BLOCKED,
    )
    assert modify_impl.execution_count == 0
    assert init_file.read_bytes() == initial_bytes

    # ═══════════════════════════════════════════════════════════════════════════
    # 9. Forced Downstream Failure & Real Rollback via Orchestrator
    # ═══════════════════════════════════════════════════════════════════════════
    trial_impl = ProjectModifyCodeImplementation(modify_op, fail_after_mutation=True)
    trial_common = InMemoryAgentOperationRegistry()
    trial_op_reg = InMemoryDomainOperationRegistry(trial_common)
    trial_op_reg.register(modify_op, trial_impl)
    trial_adapter = AgentExecutionAdapter(
        registry=trial_common,
        execution_delegate=DomainOperationExecutionDelegate(trial_op_reg),
        validation_adapter=val_adapter,
    )
    trial_orchestrator = DefaultDomainOperationOrchestrator(
        trial_op_reg,
        trial_adapter,
        approval_service=approval_svc,
        permission_gate=gate,
        transaction_manager=tx_manager,
        rollback_executor=rollback_executor,
    )

    trial_action = {
        "version": 1,
        "actions": [
            {
                "tool": "python",
                "action": "insert_method",
                "path": str(init_file),
                "class_name": "AuthService",
                "position": "end",
                "code": (
                    "def trial_corrupt(self) -> None:\n"
                    '    """Corrupted trial method."""\n'
                    "    pass\n"
                ),
            }
        ],
    }
    trial_op_req_proto = DomainOperationRequest(
        request_id="req:op:trial:1",
        operation_id=modify_op.operation_id,
        operation_version=modify_op.version,
        inputs={
            "runtime_action": trial_action,
            "modified_files": ["auth_service.py"],
        },
        agent_run_id="run:dev:1",
        workflow_id="project.self_development",
        task_id="task:trial:1",
        session_id="session:1",
        primary_domain_id=PROJECT_DOMAIN_ID,
        idempotency_key="idem:trial:1",
        granted_permissions=modify_op.required_permissions,
        available_resources=modify_op.required_resources,
        capabilities=("execute", "transaction", "rollback", "validation"),
        metadata={"actor_id": "actor:dev"},
    )
    (
        trial_op_exec_id,
        trial_approval_ids,
        _trial_approval_requirements,
    ) = _approve_operation_requirements(
        definition=modify_op,
        proto_request=trial_op_req_proto,
        resolver=resolver,
        approval_service=approval_svc,
        requested_by="agent:self_dev",
        approver_actor_id="human:tech_lead",
    )
    trial_op_req = DomainOperationRequest(
        request_id=trial_op_req_proto.request_id,
        operation_id=trial_op_req_proto.operation_id,
        operation_version=trial_op_req_proto.operation_version,
        inputs=trial_op_req_proto.inputs,
        agent_run_id=trial_op_req_proto.agent_run_id,
        workflow_id=trial_op_req_proto.workflow_id,
        task_id=trial_op_req_proto.task_id,
        session_id=trial_op_req_proto.session_id,
        primary_domain_id=trial_op_req_proto.primary_domain_id,
        idempotency_key=trial_op_req_proto.idempotency_key,
        granted_permissions=trial_op_req_proto.granted_permissions,
        available_resources=trial_op_req_proto.available_resources,
        capabilities=trial_op_req_proto.capabilities,
        approval_request_id=trial_op_exec_id,
        metadata={
            "actor_id": "actor:dev",
            "approval_request_ids": trial_approval_ids,
        },
    )

    trial_result = trial_orchestrator.execute(trial_op_req)
    assert trial_result.status is DomainOperationStatus.ROLLED_BACK
    assert trial_result.rollback_result is not None
    assert trial_result.rollback_result.attempted is True
    assert trial_result.rollback_result.succeeded is True
    assert trial_impl.execution_count == 1
    assert init_file.read_bytes() == initial_bytes

    diff_after_rollback = subprocess.run(
        ["git", "diff", "--stat"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert diff_after_rollback == ""

    # ═══════════════════════════════════════════════════════════════════════════
    # 10. Approved Mutation Executed via Authoritative Orchestrator Path
    # ═══════════════════════════════════════════════════════════════════════════
    positive_op_req_proto = DomainOperationRequest(
        request_id="req:op:modify:1",
        operation_id=modify_op.operation_id,
        operation_version=modify_op.version,
        inputs={
            "runtime_action": runtime_action,
            "modified_files": ["auth_service.py"],
        },
        agent_run_id="run:dev:1",
        workflow_id="project.self_development",
        task_id="task:dev:1",
        session_id="session:1",
        primary_domain_id=PROJECT_DOMAIN_ID,
        idempotency_key="idem:mod:1",
        granted_permissions=modify_op.required_permissions,
        available_resources=modify_op.required_resources,
        capabilities=("execute", "transaction", "rollback", "validation"),
        metadata={"actor_id": "actor:dev"},
    )
    (
        operation_execute_approval_id,
        approval_request_ids,
        approval_requirements,
    ) = _approve_operation_requirements(
        definition=modify_op,
        proto_request=positive_op_req_proto,
        resolver=resolver,
        approval_service=approval_svc,
        requested_by="agent:self_dev",
        approver_actor_id="human:tech_lead",
    )
    app_request = approval_repo.get_request(operation_execute_approval_id)
    assert any(
        req.action is PermissionCapability.FILE_MODIFY for req in approval_requirements
    )
    assert any(
        req.action is PermissionCapability.OPERATION_EXECUTE
        for req in approval_requirements
    )

    approved_op_req = DomainOperationRequest(
        request_id=positive_op_req_proto.request_id,
        operation_id=positive_op_req_proto.operation_id,
        operation_version=positive_op_req_proto.operation_version,
        inputs=positive_op_req_proto.inputs,
        agent_run_id=positive_op_req_proto.agent_run_id,
        workflow_id=positive_op_req_proto.workflow_id,
        task_id=positive_op_req_proto.task_id,
        session_id=positive_op_req_proto.session_id,
        primary_domain_id=positive_op_req_proto.primary_domain_id,
        idempotency_key=positive_op_req_proto.idempotency_key,
        granted_permissions=positive_op_req_proto.granted_permissions,
        available_resources=positive_op_req_proto.available_resources,
        capabilities=positive_op_req_proto.capabilities,
        approval_request_id=operation_execute_approval_id,
        metadata={
            "actor_id": "actor:dev",
            "approval_request_ids": approval_request_ids,
        },
    )

    op_result = orchestrator.execute(approved_op_req)
    assert op_result.status is DomainOperationStatus.COMPLETED
    assert modify_impl.execution_count == 1
    assert op_result.transaction_id is not None
    for approval_id in approval_request_ids.values():
        assert approval_repo.is_consumed(approval_id) is True

    modified_source = init_file.read_text(encoding="utf-8")
    assert "def validate_token" in modified_source

    # ═══════════════════════════════════════════════════════════════════════════
    # 11. Real Phase 7 Validation Pipeline Execution
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
        change_id="change:auth_method:001",
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
    # 12. Prepare Commit Readiness Semantics (HEAD Unchanged)
    # ═══════════════════════════════════════════════════════════════════════════
    readiness_ready = build_prepare_commit_readiness_result(
        change_id="change:auth_method:001",
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
    # 13. Memory Integration & Proposal Binding Real Runtime Outputs
    # ═══════════════════════════════════════════════════════════════════════════
    project_context_ref = "project-context:sha256:" + sha256_digest(
        project_context.serialize()
    )
    development_plan_ref = "development-plan:sha256:" + sha256_digest(
        dev_plan.serialize()
    )
    assert trial_result.rollback_result is not None
    rollback_ref = "rollback-result:sha256:" + sha256_digest(
        trial_result.rollback_result.to_dict()
    )
    readiness_ref = "prepare-commit-readiness:sha256:" + sha256_digest(readiness_ready)

    # Prove artifact identity sensitivity: mutating data changes the digest
    modified_plan_data = dict(dev_plan.serialize())
    modified_plan_data["goal"] = "Altered Plan Goal for Sensitivity Test"
    assert (
        "development-plan:sha256:" + sha256_digest(modified_plan_data)
        != development_plan_ref
    )

    modified_ctx_data = dict(project_context.serialize())
    modified_ctx_data["summary"] = "Altered Project Context Summary"
    assert (
        "project-context:sha256:" + sha256_digest(modified_ctx_data)
        != project_context_ref
    )

    affected_reference_ids = (
        project_context_ref,
        development_plan_ref,
        app_request.id,
        str(op_result.result_id),
        str(op_result.transaction_id),
        rollback_ref,
        str(pass_res.id),
        readiness_ref,
    )

    proposal_content = {
        "kind": "architecture_document",
        "status": "decision",
        "is_confirmed": True,
        "summary": "Added token validation method to AuthService",
        "project_context_reference": project_context_ref,
        "plan_reference": development_plan_ref,
        "approval_reference": app_request.id,
        "operation_result_reference": str(op_result.result_id),
        "transaction_reference": str(op_result.transaction_id),
        "rollback_reference": rollback_ref,
        "validation_reference": str(pass_res.id),
        "readiness_reference": readiness_ref,
    }
    assert (
        validate_project_memory_proposal_content(proposal_content)["is_valid"] is True
    )

    mem_proposal = build_project_memory_proposal(
        proposal_id="prop:arch:001",
        affected_reference_ids=affected_reference_ids,
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
        approval_request_ids=(app_request.id,),
    )
    assert binding.trace_id == "trace:software:e2e:1"
    assert binding.affected_reference_ids == tuple(sorted(set(affected_reference_ids)))

    # ═══════════════════════════════════════════════════════════════════════════
    # 14. Trace Assembly & Independent Inventory Binding Real Runtime Outputs
    # ═══════════════════════════════════════════════════════════════════════════
    now = datetime.now(timezone.utc)
    ref_ctx = build_project_trace_reference(
        ref_id=project_context_ref,
        kind=DomainTraceReferenceKind.RESOURCE_RESOLUTION,
    )
    ref_plan = build_project_trace_reference(
        ref_id=development_plan_ref,
        kind=DomainTraceReferenceKind.RULE_PLAN,
    )
    ref_app_req = build_project_trace_reference(
        ref_id=app_request.id,
        kind=DomainTraceReferenceKind.APPROVAL_REQUEST,
    )
    ref_op_mutation = build_project_trace_reference(
        ref_id=str(op_result.result_id),
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    ref_tx = build_project_trace_reference(
        ref_id=str(op_result.transaction_id),
        kind=DomainTraceReferenceKind.EVIDENCE,
    )
    ref_rollback = build_project_trace_reference(
        ref_id=rollback_ref,
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    ref_val = build_project_trace_reference(
        ref_id=str(pass_res.id),
        kind=DomainTraceReferenceKind.EVIDENCE,
    )
    ref_readiness = build_project_trace_reference(
        ref_id=readiness_ref,
        kind=DomainTraceReferenceKind.OPERATION_RESULT,
    )
    ref_rule = build_project_trace_reference(
        ref_id="rule:project.scope_consistency:1.0.0",
        kind=DomainTraceReferenceKind.RULE_RESULT,
    )

    all_trace_refs = (
        ref_ctx,
        ref_plan,
        ref_app_req,
        ref_op_mutation,
        ref_tx,
        ref_rollback,
        ref_val,
        ref_readiness,
        ref_rule,
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
                references=all_trace_refs,
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
            *all_trace_refs,
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
        references=all_trace_refs,
    )
    assert trace.id == predicted_identity.trace_id
    assert trace.primary_domain == DomainId.from_str(PROJECT_DOMAIN_ID)
    assert trace.status == DomainTraceStatus.COMPLETED

    trace_val = validate_project_trace(trace=trace, inventory=inventory)
    assert trace_val.valid is True

    # ═══════════════════════════════════════════════════════════════════════════
    # 15. Presentation Projection
    # ═══════════════════════════════════════════════════════════════════════════
    presented = present_project_result(readiness_ready)
    assert presented["domain_display_name"] == "Project"
    assert presented["ready_for_approved_commit"] is True
    assert presented["committed"] is False


def test_generic_operation_approval_alone_cannot_modify_code(tmp_path: Path) -> None:
    repo_dir = tmp_path / "neg_repo"
    repo_dir.mkdir()
    target_file = repo_dir / "target.py"
    initial_bytes = b"class Target:\n    pass\n"
    target_file.write_bytes(initial_bytes)

    # Prohibit FILE_MODIFY while OPERATION_EXECUTE remains allowed
    canonical_policy = build_project_permission_policy()
    prohibited_file_modify_policy = replace(
        canonical_policy,
        policy_id="policy:project:no_file_modify",
        prohibited_capabilities=(
            *canonical_policy.prohibited_capabilities,
            PermissionCapability.FILE_MODIFY,
        ),
        allowed_capabilities=tuple(
            cap
            for cap in canonical_policy.allowed_capabilities
            if cap is not PermissionCapability.FILE_MODIFY
        ),
    )

    registry = DomainPermissionRegistry()
    registry.register(prohibited_file_modify_policy)
    resolver = DomainPermissionResolver(registry)

    approval_repo = InMemoryApprovalRepository()
    approval_svc = ApprovalService(approval_repo)
    gate = DomainPermissionGate(resolver, approval_service=approval_svc)

    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    modify_op = ops["project.modify_code"]

    modify_impl = ProjectModifyCodeImplementation(modify_op)
    common_registry = InMemoryAgentOperationRegistry()
    domain_registry = InMemoryDomainOperationRegistry(common_registry)
    domain_registry.register(modify_op, modify_impl)

    resource_provider = RepoResourceVersionProvider(repo_dir)
    cp_repo = InMemoryCheckpointRepository()
    cp_mgr = CheckpointManager(repository=cp_repo, resource_provider=resource_provider)
    tx_manager = TransactionManager(cp_mgr)
    rest_manager = CheckpointRestorationManager(
        repository=cp_repo, resource_provider=resource_provider
    )
    rollback_executor = CheckpointRestorationRollbackExecutor(
        transaction_manager=tx_manager, restoration_manager=rest_manager
    )

    adapter = AgentExecutionAdapter(
        registry=common_registry,
        execution_delegate=DomainOperationExecutionDelegate(domain_registry),
        validation_adapter=AgentValidationAdapter(),
    )
    orchestrator = DefaultDomainOperationOrchestrator(
        domain_registry,
        adapter,
        approval_service=approval_svc,
        permission_gate=gate,
        transaction_manager=tx_manager,
        rollback_executor=rollback_executor,
    )

    proto_request = DomainOperationRequest(
        request_id="req:neg:1",
        operation_id=modify_op.operation_id,
        operation_version=modify_op.version,
        inputs={
            "runtime_action": {
                "version": 1,
                "actions": [
                    {
                        "tool": "python",
                        "action": "insert_method",
                        "path": str(target_file),
                        "class_name": "Target",
                        "position": "end",
                        "code": "def injected(self) -> None:\n    pass\n",
                    }
                ],
            },
            "modified_files": ["target.py"],
        },
        agent_run_id="run:neg:1",
        workflow_id="project.self_development",
        task_id="task:neg:1",
        session_id="session:neg",
        primary_domain_id=PROJECT_DOMAIN_ID,
        idempotency_key="idem:neg:1",
        granted_permissions=modify_op.required_permissions,
        available_resources=modify_op.required_resources,
        capabilities=("execute", "transaction", "rollback", "validation"),
        metadata={"actor_id": "actor:dev"},
    )

    # Create and approve a generic OPERATION_EXECUTE approval only
    generic_req = PermissionApprovalRequirement(
        requirement_id=f"operation:project.modify_code:1.0.0:{proto_request.request_id}:operation_requires_approval",
        action=PermissionCapability.OPERATION_EXECUTE,
        actor_id="actor:dev",
        session_id="session:neg",
        domain_id=PROJECT_DOMAIN_ID,
        operation_id="project.modify_code",
        operation_version="1.0.0",
        fingerprint=f"{proto_request.request_id}:project.modify_code:1.0.0:actor:dev:session:neg:operation_requires_approval",
        scope="operation",
        reason_code="operation_requires_approval",
        risk="high",
    )
    bridged = to_approval_requirement(generic_req, agent_run_id="run:neg:1")
    app_req = approval_svc.create_request_from_requirement(
        bridged,
        requested_by="agent:neg",
        metadata_override={
            "domain_request_fingerprint": proto_request.calculate_fingerprint(),
        },
    )
    approval_svc.approve(
        app_req.id, actor_id="lead", comment="Approved operation execute only"
    )

    request_with_generic_approval = DomainOperationRequest(
        request_id=proto_request.request_id,
        operation_id=proto_request.operation_id,
        operation_version=proto_request.operation_version,
        inputs=proto_request.inputs,
        agent_run_id=proto_request.agent_run_id,
        workflow_id=proto_request.workflow_id,
        task_id=proto_request.task_id,
        session_id=proto_request.session_id,
        primary_domain_id=proto_request.primary_domain_id,
        idempotency_key=proto_request.idempotency_key,
        granted_permissions=proto_request.granted_permissions,
        available_resources=proto_request.available_resources,
        capabilities=proto_request.capabilities,
        approval_request_id=app_req.id,
        metadata={
            "actor_id": "actor:dev",
            "approval_request_ids": {generic_req.requirement_id: app_req.id},
        },
    )

    result = orchestrator.execute(request_with_generic_approval)
    assert result.status is DomainOperationStatus.BLOCKED
    assert modify_impl.execution_count == 0
    assert target_file.read_bytes() == initial_bytes
