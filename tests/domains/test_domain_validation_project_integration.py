"""Phase 10.43 — Project Domain mandatory Phase 7 validation (Task 6)."""

from __future__ import annotations

import pytest

from cmm.domains.project.operations import build_project_operation_definitions
from cmm.domains.validation_integration import (
    DomainValidationIntegrationError,
    is_project_domain_code_mutation,
    project_change_requires_validation,
    require_canonical_validation_success,
)
from cmm.domains.validation_policy_bindings import (
    PROJECT_DOMAIN_CHANGE_POLICY_NAME,
    build_project_domain_change_policy,
)
from cmm.validation import (
    CommitGateEvaluator,
    ValidationFinding,
    ValidationPolicy,
    ValidationResult,
    ValidationSeverity,
    ValidationStatus,
)
from cmm.validation.steps import ValidationStepResult


def _ops() -> dict:
    return {op.operation_id: op for op in build_project_operation_definitions()}


def _step(name: str, status=ValidationStatus.PASSED) -> ValidationStepResult:
    return ValidationStepResult(name=name, status=status)


def _validation_result(
    result_id: str = "vr-1",
    status=ValidationStatus.PASSED,
    steps: tuple = (),
    policy: str | None = "small_change",
) -> ValidationResult:
    return ValidationResult(
        id=result_id, status=status, policy=policy, steps=tuple(steps)
    )


class TestProjectDeclarationBinding:
    def test_project_modify_code_requires_project_domain_change_policy(self) -> None:
        ops = _ops()
        definition = ops["project.modify_code"]
        # Existing canonical declaration preserved: every Project operation
        # carries a validation policy ID, and modify_code specifically does.
        assert definition.validation_policy_id is not None
        assert definition.validation_policy_id == "validation.project.modify_code"
        # Phase 10.43 Project policy covers that declaration: building the
        # canonical ProjectDomainChangePolicy with the operation's ID yields
        # a canonical ValidationPolicy requiring it.
        policy = build_project_domain_change_policy(
            required_validation_ids=(definition.validation_policy_id,),
        )
        assert isinstance(policy, ValidationPolicy)
        assert policy.metadata["domain_policy_family"] == (
            PROJECT_DOMAIN_CHANGE_POLICY_NAME
        )
        assert definition.validation_policy_id in policy.required_steps

    def test_is_project_code_mutation_semantic(self) -> None:
        assert is_project_domain_code_mutation("project.modify_code") is True
        assert is_project_domain_code_mutation("project.run_validation") is False
        assert is_project_domain_code_mutation("project.prepare_commit") is False
        assert is_project_domain_code_mutation("") is False
        assert is_project_domain_code_mutation(None) is False

    def test_project_change_requires_validation(self) -> None:
        assert project_change_requires_validation("project.modify_code") is True
        # run_validation availability never exempts a later mutation.
        assert project_change_requires_validation("project.run_validation") is False


class TestProjectMutationValidation:
    def test_mutation_without_evidence_blocked(self) -> None:
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("syntax",),
                canonical_results=(),
            )

    def test_failing_affected_test_blocks_acceptance(self) -> None:
        failing = _validation_result(
            "vr-fail",
            status=ValidationStatus.FAILED,
            steps=(_step("syntax", ValidationStatus.FAILED),),
        )
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("syntax",),
                canonical_results=(failing,),
            )

    def test_corrected_regression_passes(self) -> None:
        passing = _validation_result(
            "vr-pass",
            status=ValidationStatus.PASSED,
            steps=(_step("syntax"), _step("ast")),
        )
        refs = require_canonical_validation_success(
            required_validation_ids=("syntax", "ast"),
            canonical_results=(passing,),
        )
        assert refs == ("vr-pass",)

    def test_run_validation_does_not_exempt_modify_code(self) -> None:
        # Historic/explicit validation operation availability is not
        # equivalent to post-change validation success: a new mutation still
        # carries its current required obligation.
        assert project_change_requires_validation("project.modify_code") is True
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("syntax",),
                canonical_results=(),
            )


class TestPrepareCommitGate:
    def test_blocking_finding_denies_commit_authorization(self) -> None:
        finding = ValidationFinding(
            code="TEST_FAIL",
            message="failing test",
            severity=ValidationSeverity.ERROR,
            source="pytest",
            blocking=True,
        )
        result = ValidationResult(
            id="vr-block",
            status=ValidationStatus.FAILED,
            policy="small_change",
            steps=(_step("syntax", ValidationStatus.FAILED),),
            blocking_findings=(finding,),
        )
        policy = build_project_domain_change_policy()
        gate = CommitGateEvaluator.evaluate(result, policy)
        assert gate.allowed is False

    def test_passing_validation_defers_to_gate(self) -> None:
        from cmm.validation.policy import DEFAULT_VALIDATION_POLICIES

        policy = DEFAULT_VALIDATION_POLICIES["small_change"]
        result = _validation_result(
            "vr-ok",
            status=ValidationStatus.PASSED,
            steps=(
                _step("formatter_check"),
                _step("syntax"),
                _step("ast"),
                _step("affected_tests"),
            ),
            policy="small_change",
        )
        gate = CommitGateEvaluator.evaluate(result, policy)
        # Existing gate decides eligibility; Domain code never issues its own
        # commit authorization (no Domain commit-gate symbol exists).
        assert gate.validation_result_id == "vr-ok"

    def test_domain_layer_has_no_commit_gate(self) -> None:
        import cmm.domains.validation_integration as mod

        assert not hasattr(mod, "DomainValidationCommitGate")
        assert not hasattr(mod, "issue_commit_authorization")


class TestImpactEscalation:
    def test_small_change_uses_lower_impact_set(self) -> None:
        policy = build_project_domain_change_policy(impact="small")
        assert policy.require_full_suite is False
        assert "syntax" in policy.required_steps

    def test_structural_change_includes_broader_checks(self) -> None:
        small = build_project_domain_change_policy(impact="small")
        structural = build_project_domain_change_policy(impact="structural")
        assert set(small.required_steps) <= set(structural.required_steps)
        assert len(structural.required_steps) > len(small.required_steps)

    def test_broad_change_escalates_to_full_suite(self) -> None:
        broad = build_project_domain_change_policy(impact="broad")
        assert broad.require_full_suite is True


class TestRealProjectMutationValidation:
    def test_real_project_modify_code_requires_current_phase7_validation(
        self, tmp_path
    ) -> None:
        from cmm.domains.enums import DomainOperationStatus
        from tests.domains.test_domain_validation_runtime_integration import (
            _modify_code_stack,
        )

        # Baseline: valid tree validates and the mutation is accepted.
        orchestrator, request, _, project_dir = _modify_code_stack(
            tmp_path, break_tree=False, break_on_execute=False
        )
        assert orchestrator.execute(request).status is DomainOperationStatus.COMPLETED

        # The mutation itself introduces a regression: current canonical
        # validation fails and accepted success becomes impossible.
        breaking_orch, breaking_request, _, _ = _modify_code_stack(
            tmp_path, break_tree=False, break_on_execute=True
        )
        breaking = breaking_orch.execute(breaking_request)
        assert breaking.status is not DomainOperationStatus.COMPLETED

        # Correcting the regression restores acceptance: validation is
        # re-executed against current state, never reused from history.
        (project_dir / "main.py").write_text("x = 1\n", encoding="utf-8")
        fixed_orch, fixed_request, _, _ = _modify_code_stack(
            tmp_path, break_tree=False, break_on_execute=False
        )
        assert (
            fixed_orch.execute(fixed_request).status is DomainOperationStatus.COMPLETED
        )

    def test_historic_project_run_validation_does_not_exempt_new_mutation(
        self, tmp_path
    ) -> None:
        from cmm.domains.enums import DomainOperationStatus
        from cmm.domains.operation_availability import (
            DomainOperationAvailabilityContext,
            DomainOperationAvailabilityResolver,
        )
        from cmm.domains.project.operations import build_project_operation_definitions
        from tests.domains.test_domain_validation_runtime_integration import (
            _modify_code_stack,
        )

        ops = {op.operation_id: op for op in build_project_operation_definitions()}
        run_validation = ops["project.run_validation"]
        # run_validation is registered and available: availability is not
        # evidence, and it never exempts a later mutation.
        resolver = DomainOperationAvailabilityResolver()
        availability = resolver.resolve(
            run_validation,
            DomainOperationAvailabilityContext(
                primary_domain_id=run_validation.domain_id,
                supporting_domain_ids=(),
                granted_permissions=(),
                denied_permissions=(),
                available_resources=run_validation.required_resources,
                capabilities=("execute", "transaction", "rollback", "validation"),
                available_validation_policy_ids=(
                    (run_validation.validation_policy_id,)
                    if run_validation.validation_policy_id
                    else ()
                ),
                available_rollback_policy_ids=(
                    (run_validation.rollback_policy_id,)
                    if run_validation.rollback_policy_id
                    else ()
                ),
                approval_status=None,
                approval_fingerprint=None,
                request_fingerprint="fp",
                metadata={},
            ),
        )
        assert availability.status is DomainOperationStatus.AVAILABLE

        orchestrator, request, _, _ = _modify_code_stack(
            tmp_path, break_tree=True, break_on_execute=False
        )
        blocked = orchestrator.execute(request)
        assert blocked.status is not DomainOperationStatus.COMPLETED
        assert blocked.metadata.get("validation_result_ids") != ()

    def test_project_prepare_commit_remains_owned_by_phase7_commit_gate(
        self, tmp_path
    ) -> None:
        from pathlib import Path

        from cmm.domains.validation_integration import (
            DomainValidationIntegrationError,
            require_canonical_validation_success,
        )
        from cmm.validation import (
            ValidationContext,
            build_default_validation_pipeline,
        )
        from cmm.validation.catalog import ast_step, syntax_step

        project_dir = tmp_path / "commitproj"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "main.py").write_text("def broken(:\n", encoding="utf-8")

        def _canonical_result():
            pipeline = build_default_validation_pipeline()
            context = ValidationContext(project_root=Path(project_dir))
            return pipeline.run(context, (syntax_step(), ast_step()))

        # Real canonical failure: no evidence to project, gate denies.
        failing = _canonical_result()
        assert failing.status.value == "failed"
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("syntax",),
                canonical_results=(failing,),
            )
        policy = build_project_domain_change_policy(impact="small")
        assert CommitGateEvaluator.evaluate(failing, policy).allowed is False

        # Corrected tree: real canonical evidence, existing gate decides.
        (project_dir / "main.py").write_text("x = 1\n", encoding="utf-8")
        passing = _canonical_result()
        assert passing.status.value == "passed"
        refs = require_canonical_validation_success(
            required_validation_ids=("syntax", "ast"),
            canonical_results=(passing,),
        )
        assert refs == (passing.id,)
        gate = CommitGateEvaluator.evaluate(passing, policy)
        assert gate.validation_result_id == passing.id


# ── V2→V3 remediation: BLOCKER-V2-02 Project change policy in real runtime ─────


def _affected_test_stack(
    tmp_path,
    *,
    break_test: bool = False,
    custom_mutation=None,
    validation_impact="small",
    validation_changed_files=None,
    suffix: str | None = None,
):
    """Real orchestrator stack for project.modify_code with an affected test.

    The temp project carries ``main.py`` with a valid function and
    ``tests/test_main.py`` asserting its behavior. When ``break_test`` is True
    the implementation rewrites ``main.py`` to a semantically broken but
    syntactically valid version (also unformatted, so the canonical
    ``small_change`` formatter gate -- part of the new Project policy --
    rejects it), proving the real ``project.modify_code`` path no longer
    accepts valid-syntax regressions under the old fixed syntax+AST mapping.
    """
    import dataclasses
    from datetime import datetime, timezone

    from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
    from cmm.agent_runtime.approval_service import ApprovalService
    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
    from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
    from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
    from cmm.agent_runtime.validation_execution_adapter import AgentValidationAdapter
    from cmm.domains.approval_bridge import to_approval_requirement
    from cmm.domains.operation_contracts import DomainOperationRequest
    from cmm.domains.operation_execution import (
        DefaultDomainOperationOrchestrator,
        DomainOperationExecutionDelegate,
    )
    from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
    from cmm.domains.permission_adapters import evaluate_domain_operation
    from cmm.domains.permission_gate import DomainPermissionGate
    from cmm.domains.permission_registry import DomainPermissionRegistry
    from cmm.domains.permission_resolution import DomainPermissionResolver
    from cmm.domains.project.permissions import build_project_permission_policy
    from cmm.domains.validation_integration import (
        resolve_domain_operation_validation_requirements,
    )

    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    definition = ops["project.modify_code"]

    project_dir = tmp_path / "affproj"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "main.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    tests_dir = project_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "test_main.py").write_text(
        "from main import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    import shutil

    for pycache in project_dir.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)

    class Implementation:
        def __init__(self) -> None:
            self.definition = definition

        def execute(self, request) -> dict:
            import shutil

            if custom_mutation is not None:
                custom_mutation(project_dir)
            elif break_test:
                # Formatter-clean and lint-clean code where only affected pytest test fails
                (project_dir / "main.py").write_text(
                    "def add(a, b):\n    return a - b\n", encoding="utf-8"
                )
            for pycache in project_dir.rglob("__pycache__"):
                shutil.rmtree(pycache, ignore_errors=True)
            return {"success": True, "output": {"status": "ok"}}

    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    registry.register(definition, Implementation())

    perm_registry = DomainPermissionRegistry()
    perm_registry.register(build_project_permission_policy())
    resolver = DomainPermissionResolver(perm_registry)
    service = ApprovalService(InMemoryApprovalRepository())

    eff_suffix = suffix or ("break" if break_test else "pass")
    effective_files = (
        () if validation_changed_files is None else tuple(validation_changed_files)
    )
    request = DomainOperationRequest(
        request_id=f"req:aff:{eff_suffix}",
        operation_id="project.modify_code",
        operation_version=definition.version,
        inputs={},
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="task-1",
        session_id="sess-1",
        primary_domain_id=definition.domain_id,
        idempotency_key=f"idem-aff-{eff_suffix}",
        granted_permissions=definition.required_permissions,
        available_resources=definition.required_resources,
        capabilities=("execute", "transaction", "rollback", "validation"),
        metadata={
            "actor_id": "actor-1",
            "validation_project_root": str(project_dir),
        },
        validation_impact=validation_impact,
        validation_changed_files=effective_files,
    )
    decision = evaluate_domain_operation(
        definition,
        resolver,
        request_id=request.request_id,
        actor_id="actor-1",
        session_id="sess-1",
    )
    approval_request_ids: dict = {}
    op_exec_approval_id = None
    for req in decision.approval_requirements:
        bridged = to_approval_requirement(req, agent_run_id="run-1")
        app_req = service.create_request_from_requirement(
            bridged,
            requested_by="agent:dev",
            metadata_override={
                "domain_request_fingerprint": request.calculate_fingerprint(),
            },
        )
        service.approve(app_req.id, actor_id="lead")
        approval_request_ids[req.requirement_id] = app_req.id
        if req.action is PermissionCapability.OPERATION_EXECUTE:
            op_exec_approval_id = app_req.id

    class Boundary:
        id = "transaction:1"

    class TransactionManagerSpy:
        def start_transaction(self, **kwargs):
            return Boundary(), "checkpoint:1"

        def register_operation(self, **kwargs) -> None:
            return None

        def commit(self, transaction_id: str) -> None:
            return None

        def mark_rollback_started(self, transaction_id: str) -> None:
            return None

        def mark_rolled_back(self, transaction_id: str) -> None:
            return None

        def mark_failed(self, transaction_id: str) -> None:
            return None

    adapter = AgentExecutionAdapter(
        registry=common,
        execution_delegate=DomainOperationExecutionDelegate(registry),
        validation_adapter=AgentValidationAdapter(),
    )
    _now = datetime.now(timezone.utc)
    gate = DomainPermissionGate(resolver, service, clock=lambda: _now)

    class RollbackSpy:
        def __init__(self) -> None:
            self.calls = 0

        def rollback(self, transaction_id, checkpoint_id=None) -> bool:
            self.calls += 1
            return True

    orchestrator = DefaultDomainOperationOrchestrator(
        registry,
        adapter,
        approval_service=service,
        permission_gate=gate,
        transaction_manager=TransactionManagerSpy(),
        rollback_executor=RollbackSpy(),
        operation_validation_provider=(
            resolve_domain_operation_validation_requirements
        ),
    )
    approved_request = dataclasses.replace(
        request,
        approval_request_id=op_exec_approval_id,
        metadata={
            "actor_id": "actor-1",
            "approval_request_ids": approval_request_ids,
            "validation_project_root": str(project_dir),
            "validation_impact": validation_impact,
            "validation_changed_files": effective_files,
        },
        validation_impact=validation_impact,
        validation_changed_files=effective_files,
    )
    return orchestrator, approved_request, project_dir


class TestV2Blocker02ProjectChangePolicy:
    """The real project.modify_code runtime must derive its validation
    requirements from the canonical Project/Phase 7 change policy
    (impact-sensitive), not the old fixed syntax+AST mapping."""

    def test_resolver_routes_modify_code_through_canonical_small_policy(
        self,
    ) -> None:
        from cmm.domains.validation_integration import (
            resolve_project_domain_change_validation_ids,
        )

        ops = {op.operation_id: op for op in build_project_operation_definitions()}
        definition = ops["project.modify_code"]
        ids = resolve_project_domain_change_validation_ids(definition)
        # Canonical small_change set: formatter_check, lint, syntax, ast,
        # affected_tests -- NOT the old fixed syntax+ast pair.
        assert "formatter_check" in ids
        assert "lint" in ids
        assert "syntax_validator" in ids
        assert "ast_validator" in ids
        assert "affected_tests_step" in ids

    def test_project_modify_code_uses_canonical_small_change_requirements(
        self, tmp_path
    ) -> None:
        from cmm.agent_runtime.validation_integration_contracts import (
            ValidationRequirement,
        )
        from cmm.domains.validation_integration import (
            resolve_domain_operation_validation_requirements,
        )

        project_dir = tmp_path / "reqproj"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "main.py").write_text("x = 1\n", encoding="utf-8")

        ops = {op.operation_id: op for op in build_project_operation_definitions()}
        definition = ops["project.modify_code"]

        requirements = resolve_domain_operation_validation_requirements(
            definition,
            impact="small",
            changed_files=("main.py",),
        )
        assert requirements
        assert all(
            isinstance(r, ValidationRequirement) and r.required and r.blocking
            for r in requirements
        )
        validator_ids = sorted(vid for r in requirements for vid in r.validator_ids)
        assert "formatter_check" in validator_ids
        assert "lint" in validator_ids
        assert "syntax_validator" in validator_ids
        assert "ast_validator" in validator_ids
        assert "affected_tests_step" in validator_ids
        # changed_files propagated to requirement resource scope.
        assert requirements[0].resource_scope == ("main.py",)

    def test_project_structural_change_uses_stronger_canonical_policy(
        self,
    ) -> None:
        from cmm.domains.validation_integration import (
            DomainValidationIntegrationError,
            resolve_project_domain_change_validation_ids,
        )

        ops = {op.operation_id: op for op in build_project_operation_definitions()}
        definition = ops["project.modify_code"]
        small = resolve_project_domain_change_validation_ids(definition, impact="small")
        # structural demands custom validators the runtime cannot execute, so
        # it fails closed -- proving escalation is never silently downgraded
        # to the weaker small policy.
        with pytest.raises(DomainValidationIntegrationError):
            resolve_project_domain_change_validation_ids(
                definition, impact="structural"
            )
        # public/broad/high/full escalate to stronger policies and also fail
        # closed on unmappable mandatory steps.
        with pytest.raises(DomainValidationIntegrationError):
            resolve_project_domain_change_validation_ids(definition, impact="public")
        with pytest.raises(DomainValidationIntegrationError):
            resolve_project_domain_change_validation_ids(definition, impact="broad")
        with pytest.raises(DomainValidationIntegrationError):
            resolve_project_domain_change_validation_ids(definition, impact="full")
        with pytest.raises(DomainValidationIntegrationError):
            resolve_project_domain_change_validation_ids(definition, impact="high")
        assert set(small) <= {
            "formatter_check",
            "lint",
            "syntax_validator",
            "ast_validator",
            "affected_tests_step",
        }

    def test_project_modify_code_blocks_valid_syntax_when_affected_test_fails(
        self, tmp_path
    ) -> None:
        import ast
        import subprocess
        import sys

        from cmm.domains.enums import DomainOperationStatus

        # Valid syntax + a passing affected test: accepted.
        orchestrator, request, _ = _affected_test_stack(tmp_path, break_test=False)
        assert orchestrator.execute(request).status is DomainOperationStatus.COMPLETED

        # Introduce a regression that breaks the affected test while keeping
        # syntax and AST valid; the mutation must be blocked by the real
        # project.modify_code path under the canonical small_change policy.
        breaking_orch, breaking_request, _ = _affected_test_stack(
            tmp_path, break_test=True
        )
        breaking = breaking_orch.execute(breaking_request)
        assert breaking.status is not DomainOperationStatus.COMPLETED

        # The broken tree is syntactically valid Python with a valid AST.
        broken_text = (tmp_path / "affproj" / "main.py").read_text(encoding="utf-8")
        compile(broken_text, "main.py", "exec")
        ast.parse(broken_text)

        # Direct affected-test evidence: pytest fails on the broken tree.
        probe = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "-q",
                "tests/test_main.py",
            ],
            cwd=(tmp_path / "affproj"),
            capture_output=True,
            text=True,
            check=False,
        )
        assert probe.returncode != 0

        # Repair restores acceptance only after current validation passes.
        (tmp_path / "affproj" / "main.py").write_text(
            "def add(a, b):\n    return a + b\n", encoding="utf-8"
        )
        fixed_orch, fixed_request, _ = _affected_test_stack(
            tmp_path, break_test=False, suffix="repair"
        )
        assert (
            fixed_orch.execute(fixed_request).status is DomainOperationStatus.COMPLETED
        )

    def test_caller_cannot_downgrade_project_impact(self) -> None:
        from cmm.domains.validation_integration import combine_validation_impacts

        # Host detects structural or public impact; caller specifies small hint.
        # Stronger host impact must govern and cannot be downgraded.
        assert combine_validation_impacts("structural", "small") == "structural"
        assert combine_validation_impacts("public", "small") == "public"
        assert combine_validation_impacts("full", "small") == "full"
        # Caller can escalate severity, but never downgrade host truth.
        assert combine_validation_impacts("small", "full") == "full"

    def test_project_modify_code_derives_changed_files_when_request_omits_them(
        self, tmp_path
    ) -> None:
        from cmm.domains.enums import DomainOperationStatus

        # Caller request omits validation_changed_files (empty tuple / None).
        orch_fail, req_fail, _ = _affected_test_stack(
            tmp_path / "case1",
            break_test=True,
            validation_changed_files=(),
        )
        # Even without caller-provided files, the host derives main.py from the
        # mutation and runs affected tests on main.py, which fails and blocks acceptance.
        res_fail = orch_fail.execute(req_fail)
        assert res_fail.status is not DomainOperationStatus.COMPLETED

        # Valid mutation also derives main.py and passes affected tests.
        orch_pass, req_pass, _ = _affected_test_stack(
            tmp_path / "case2",
            break_test=False,
            validation_changed_files=(),
        )
        res_pass = orch_pass.execute(req_pass)
        assert res_pass.status is DomainOperationStatus.COMPLETED

    def test_project_changed_file_hint_cannot_remove_host_changed_file(
        self, tmp_path
    ) -> None:
        from cmm.domains.enums import DomainOperationStatus

        # Host mutation modifies main.py (broken test).
        # Caller supplies validation_changed_files=("other.py",) in an attempt to hide main.py.
        hint_dir = tmp_path / "hint_proj"
        orch, req, _ = _affected_test_stack(
            hint_dir,
            break_test=True,
            validation_changed_files=("other.py",),
        )
        (hint_dir / "affproj" / "other.py").write_text("y = 2\n", encoding="utf-8")
        res = orch.execute(req)
        # Caller hint cannot remove main.py from the effective validation scope.
        # Affected tests still execute against main.py and fail.
        assert res.status is not DomainOperationStatus.COMPLETED

    def test_host_structural_or_public_impact_overrides_caller_small_hint(
        self, tmp_path
    ) -> None:
        from cmm.domains.enums import DomainOperationStatus

        # Host mutation introduces structural change (function signature change).
        def structural_mutation(project_dir) -> None:
            (project_dir / "main.py").write_text(
                "def add(a, b, c=0):\n    return a + b + c\n",
                encoding="utf-8",
            )

        orch, req, _ = _affected_test_stack(
            tmp_path / "struct_proj",
            custom_mutation=structural_mutation,
            validation_impact="small",
        )
        res = orch.execute(req)
        # Host structural impact overrides caller's small hint.
        # Stronger canonical policy fails closed on unmappable steps rather than downgrading.
        assert res.status is not DomainOperationStatus.COMPLETED

    def test_project_runtime_derives_impact_when_request_omits_validation_impact(
        self, tmp_path
    ) -> None:
        from cmm.domains.enums import DomainOperationStatus

        # Caller omits validation_impact entirely (validation_impact=None).
        # For a structural change, the host derives structural and refuses to default to small.
        def structural_mutation(project_dir) -> None:
            (project_dir / "main.py").write_text(
                "def add(a, b, c=0):\n    return a + b + c\n",
                encoding="utf-8",
            )

        orch, req, _ = _affected_test_stack(
            tmp_path / "no_impact_proj",
            custom_mutation=structural_mutation,
            validation_impact=None,
        )
        res = orch.execute(req)
        # Runtime derives structural impact and fails closed (does not silently default to small).
        assert res.status is not DomainOperationStatus.COMPLETED

    def test_unknown_mandatory_policy_step_fails_closed(self) -> None:
        from cmm.domains.validation_integration import (
            DomainValidationIntegrationError,
            resolve_project_domain_change_validation_ids,
        )

        ops = {op.operation_id: op for op in build_project_operation_definitions()}
        definition = ops["project.modify_code"]
        # Any mandatory Phase 7 step without an executable mapping fails
        # closed instead of being silently omitted.
        with pytest.raises(DomainValidationIntegrationError) as excinfo:
            resolve_project_domain_change_validation_ids(
                definition, impact="structural"
            )
        assert excinfo.value.details.get("reason") == "unmapped_mandatory_policy_step"
