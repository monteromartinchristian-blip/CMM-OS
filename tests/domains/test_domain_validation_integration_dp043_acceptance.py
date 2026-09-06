"""Phase 10.43 — AT-DP-043 connected acceptance (Task 8).

DP-043: Domain Intelligence expresses specialized validation policies and
obligations while all authoritative execution remains owned by canonical
Phase 7 (and Phase 9 bridge for agentic runtime). Uses real canonical
components or official in-memory implementations throughout.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.enums import (
    AgentValidationDecision,
    AgentValidationStage,
    AgentValidationStatus,
    OperationEffectType,
    OperationEnvironment,
    PolicyRiskLevel,
)
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_execution_contracts import (
    AgentOperationRequest,
    OperationDescriptor,
)
from cmm.agent_runtime.validation_execution_adapter import AgentValidationAdapter
from cmm.agent_runtime.validation_integration_contracts import (
    AgentValidationRequest,
    AgentValidationResult,
)
from cmm.agent_runtime.validation_integration_repository import (
    InMemoryAgentValidationRepository,
)
from cmm.domains.enums import DomainOperationType, DomainValidationStatus
from cmm.domains.errors import DomainValidationBlocked
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.project.operations import build_project_operation_definitions
from cmm.domains.validation import (
    PipelineDomainValidator,
    ensure_domain_validation_allows_install,
)
from cmm.domains.validation_contracts import (
    DomainValidationRequest,
    DomainValidationResult,
)
from cmm.domains.validation_integration import (
    DomainValidationIntegrationError,
    build_operation_validation_requirements,
    compose_effective_validation_ids,
    require_canonical_validation_success,
    validate_domain_specialized_result,
)
from cmm.domains.validation_policy_bindings import (
    DOMAIN_PACK_BASE_VALIDATION_IDS,
    PROJECT_DOMAIN_CHANGE_POLICY_NAME,
    build_cross_domain_execution_policy,
    build_domain_operation_policy,
    build_domain_pack_installation_policy,
    build_domain_pack_update_policy,
    build_domain_workflow_policy,
    build_project_domain_change_policy,
    compose_required_validation_ids,
)
from cmm.validation import (
    CommitGateEvaluator,
    ValidationResult,
    ValidationStatus,
)
from cmm.validation.steps import ValidationStepResult
from tests.domains._loader_helpers import make_pack


def _pack_request(tmp_path, slug: str = "accept-domain") -> DomainValidationRequest:
    domain_dir = tmp_path / slug
    domain_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"id": slug, "version": "1.0.0", "author": "t", "license": "MIT"}
    (domain_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (domain_dir / "probe.py").write_text("x = 1\n", encoding="utf-8")
    pack = make_pack(slug, "1.0.0", root_path=str(domain_dir))
    return DomainValidationRequest(
        pack=pack, root_path=str(domain_dir), strict=False, run_tests=False
    )


def _phase7_step(name: str, status=ValidationStatus.PASSED) -> ValidationStepResult:
    return ValidationStepResult(name=name, status=status)


def _phase7_result(
    result_id: str = "vr-1",
    status=ValidationStatus.PASSED,
    steps: tuple = (),
    policy: str | None = None,
) -> ValidationResult:
    return ValidationResult(
        id=result_id, status=status, policy=policy, steps=tuple(steps)
    )


class _FixedDecisionAdapter(AgentValidationAdapter):
    def __init__(self, decision, status) -> None:
        self._decision = decision
        self._status = status
        self._repository = InMemoryAgentValidationRepository()

    @property
    def repository(self):  # type: ignore[override]
        return self._repository

    def validate(self, request, exec_context=None):  # type: ignore[override]
        return AgentValidationResult(
            request_id=request.id,
            run_id=request.run_id,
            iteration_id=request.iteration_id,
            operation_request_id=request.operation_request_id,
            stage=request.stage,
            status=self._status,
            decision=self._decision,
        )


def _agent_request(**overrides) -> AgentOperationRequest:
    defaults = {
        "id": "req-at",
        "agent_run_id": "run-at",
        "workflow_id": "wf-at",
        "task_id": "task-at",
        "operation_name": "accept.op",
        "operation_version": "1",
        "parameters": {},
        "idempotency_key": "idem-at",
        "environment": "local",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    defaults.update(overrides)
    return AgentOperationRequest(**defaults)


def _register_accept_operation(adapter: AgentExecutionAdapter) -> None:
    desc = OperationDescriptor(
        name="accept.op",
        version="1",
        description="acceptance",
        input_schema={"type": "object"},
        effects=(OperationEffectType.READ,),
        reversible=True,
        compatible_environments=(OperationEnvironment.LOCAL,),
    )
    adapter.register_operation(desc)


# ── A. Domain Pack installation ─────────────────────────────────────────────


class TestAcceptancePackInstallation:
    def test_blocking_prevents_install_corrected_passes(self, tmp_path) -> None:
        request = _pack_request(tmp_path)
        policy = build_domain_pack_installation_policy()
        validator = PipelineDomainValidator()
        result = validator.validate(request, policy=policy)
        # Real Phase 7 pipeline executed with canonical checks.
        executed = {sr.name for sr in result.step_results}
        assert set(DOMAIN_PACK_BASE_VALIDATION_IDS) <= executed
        # Blocking finding prevents installation.
        from cmm.validation import ValidationFinding, ValidationSeverity

        blocking = DomainValidationResult(
            domain_id=result.domain_id,
            version=result.version,
            status=DomainValidationStatus.FAILED,
            manifest_valid=False,
            compatibility_valid=False,
            dependencies_valid=False,
            contracts_valid=False,
            permissions_valid=False,
            operations_valid=False,
            workflows_valid=False,
            security_valid=False,
            fragmentation_valid=False,
            tests_valid=False,
            findings=(
                ValidationFinding(
                    code="AT_BLOCK",
                    message="blocking",
                    severity=ValidationSeverity.ERROR,
                    source="domain.manifest",
                    blocking=True,
                ),
            ),
            metadata={"strict": False, "tests_evaluated": True},
        )
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(blocking)
        # Corrected fixture passes the gate (strict=False pack passes).
        ensure_domain_validation_allows_install(result)

    def test_installed_distinct_from_enabled_authorized(self, tmp_path) -> None:
        request = _pack_request(tmp_path)
        result = PipelineDomainValidator().validate(
            request, policy=build_domain_pack_installation_policy()
        )
        assert result.is_install_allowed is True
        # VALIDATED != AUTHORIZED, INSTALLED != ENABLED, TRUSTED != PERMITTED:
        # the result carries no enablement, trust, permission, or approval.
        assert not hasattr(result, "enabled")
        assert not hasattr(result, "authorized")
        assert not hasattr(result, "trusted")


# ── B. Domain operation ─────────────────────────────────────────────────────


class TestAcceptanceDomainOperation:
    def test_projection_adapter_pre_post_and_references(self) -> None:
        definition = DomainOperationDefinition(
            operation_id="accept.op",
            domain_id="domain:accept",
            version="1.0.0",
            name="op",
            description="acceptance operation",
            operation_type=DomainOperationType.READ,
            risk_level=PolicyRiskLevel.LOW,
            reversible=True,
            requires_approval=False,
            validation_policy_id="validation.accept.op",
            rollback_policy_id="rollback.accept.op",
            enabled=True,
            metadata={},
        )
        # Phase 10.42 projection preserves the obligation.
        from cmm.domains.planner_workflow_integration import _operation_semantics

        semantics = _operation_semantics(definition, ())
        assert semantics["required_validations"] == ["validation.accept.op"]

        # Agent Runtime plan obligation via operation policy helper.
        policy = build_domain_operation_policy(
            required_validation_ids=("validation.accept.op",)
        )
        assert "validation.accept.op" in policy.required_steps

        # Official operation adapter with real validation adapter seam:
        # missing adapter fails closed (existing Phase 9 behavior).
        from cmm.agent_runtime.errors import ValidationAdapterError

        adapter = AgentExecutionAdapter(
            execution_delegate=lambda req: {"success": True}
        )
        _register_accept_operation(adapter)
        with pytest.raises(ValidationAdapterError):
            adapter.execute(_agent_request(metadata={"requires_validation": True}))

        # PRE failure prevents execution (existing decision semantics).
        calls: list = []
        pre_block = AgentExecutionAdapter(
            execution_delegate=lambda req: calls.append(req) or {"success": True},
            validation_adapter=_FixedDecisionAdapter(
                AgentValidationDecision.BLOCK, AgentValidationStatus.FAILED
            ),
        )
        _register_accept_operation(pre_block)
        pre_result = pre_block.execute(_agent_request())
        assert pre_result.success is False
        assert calls == []

        # POST failure prevents accepted success.
        class _PostFail(_FixedDecisionAdapter):
            def validate(self, request, exec_context=None):
                if request.stage == AgentValidationStage.PRE_EXECUTION:
                    return AgentValidationResult(
                        request_id=request.id,
                        run_id=request.run_id,
                        iteration_id=request.iteration_id,
                        operation_request_id=request.operation_request_id,
                        stage=request.stage,
                        status=AgentValidationStatus.PASSED,
                        decision=AgentValidationDecision.CONTINUE,
                    )
                return AgentValidationResult(
                    request_id=request.id,
                    run_id=request.run_id,
                    iteration_id=request.iteration_id,
                    operation_request_id=request.operation_request_id,
                    stage=request.stage,
                    status=AgentValidationStatus.FAILED,
                    decision=AgentValidationDecision.BLOCK,
                )

        post_fail = AgentExecutionAdapter(
            execution_delegate=lambda req: {"success": True},
            validation_adapter=_PostFail(
                AgentValidationDecision.BLOCK, AgentValidationStatus.FAILED
            ),
        )
        _register_accept_operation(post_fail)
        post_result = post_fail.execute(_agent_request())
        assert post_result.success is False

        # Passing run retains canonical validation references.
        passing = AgentExecutionAdapter(
            execution_delegate=lambda req: {"success": True},
            validation_adapter=_FixedDecisionAdapter(
                AgentValidationDecision.CONTINUE, AgentValidationStatus.PASSED
            ),
        )
        _register_accept_operation(passing)
        ok_result = passing.execute(_agent_request())
        assert ok_result.success is True
        assert len(ok_result.validation_result_ids) == 2

    def test_agent_adapter_runs_canonical_phase7(self, tmp_path) -> None:
        good = tmp_path / "good.py"
        good.write_text("x = 1\n", encoding="utf-8")
        adapter = AgentValidationAdapter()
        reqs = build_operation_validation_requirements(
            required_validation_ids=("syntax_validator",),
            stage="post_execution",
            operation_name="accept.op",
        )
        from cmm.agent_runtime.validation_integration_contracts import (
            ValidationExecutionContext,
        )

        request = AgentValidationRequest(
            id="val-at-good",
            run_id="run-at",
            iteration_id="task-at",
            operation_request_id="req-at",
            stage=AgentValidationStage.POST_EXECUTION,
            requirements=reqs,
            context_data={"project_root": str(tmp_path)},
        )
        exec_ctx = ValidationExecutionContext(
            run_id="run-at",
            iteration_id="task-at",
            operation_name="accept.op",
            resource_scope=(str(good),),
        )
        result = adapter.validate(request, exec_context=exec_ctx)
        assert result.status == AgentValidationStatus.PASSED
        assert result.decision == AgentValidationDecision.CONTINUE
        assert result.validation_report != {}


# ── C. Domain workflow ──────────────────────────────────────────────────────


class TestAcceptanceWorkflow:
    def test_dependency_closure_preserves_obligations(self) -> None:
        parent = build_domain_workflow_policy(
            required_validation_ids=("parent.validation",)
        )
        child = build_domain_workflow_policy(
            required_validation_ids=("child.validation",)
        )
        # Required subworkflow closure: union preserves both.
        effective = compose_required_validation_ids(
            parent.required_steps, child.required_steps
        )
        assert set(effective) == {"parent.validation", "child.validation"}
        # Canonical validation nodes would carry the union (planner seam
        # pattern: operation validations union plan-wide validations).
        task_ids = sorted({"parent.validation"} | set(effective))
        assert task_ids == ["child.validation", "parent.validation"]

    def test_workflow_failure_blocks_via_canonical_evidence(self) -> None:
        effective = ("parent.validation", "child.validation")
        failing = _phase7_result(
            "vr-wf-fail",
            status=ValidationStatus.FAILED,
            steps=(_phase7_step("parent.validation", ValidationStatus.FAILED),),
        )
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=effective,
                canonical_results=(failing,),
            )
        passing_parent = _phase7_result(
            "vr-p", steps=(_phase7_step("parent.validation"),)
        )
        passing_child = _phase7_result(
            "vr-c", steps=(_phase7_step("child.validation"),)
        )
        refs = require_canonical_validation_success(
            required_validation_ids=effective,
            canonical_results=(passing_parent, passing_child),
        )
        assert refs == ("vr-c", "vr-p")


# ── D. Cross-domain ─────────────────────────────────────────────────────────


class TestAcceptanceCrossDomain:
    def test_restrictive_union_metadata_ignored_single_truth(self) -> None:
        effective = compose_effective_validation_ids(
            primary_required=("domain.contracts", "domain.permissions"),
            supporting_required=("domain.permissions", "health.safety.validation"),
            operation_required=("operation.output.validation",),
            workflow_required=("workflow.result.validation",),
        )
        assert effective == (
            "domain.contracts",
            "domain.permissions",
            "health.safety.validation",
            "operation.output.validation",
            "workflow.result.validation",
        )
        # Caller metadata cannot remove an obligation (composer takes no
        # metadata input; host sets only).
        assert "domain.contracts" in compose_effective_validation_ids(
            primary_required=("domain.contracts",),
        )
        # Duplicate declarations collapse to one truth.
        dup = compose_effective_validation_ids(
            primary_required=("domain.contracts",),
            supporting_required=("domain.contracts",),
            operation_required=("domain.contracts",),
            workflow_required=("domain.contracts",),
        )
        assert dup == ("domain.contracts",)
        canonical = _phase7_result("vr-x", steps=(_phase7_step("domain.contracts"),))
        assert require_canonical_validation_success(
            required_validation_ids=dup, canonical_results=(canonical,)
        ) == ("vr-x",)
        # Policy builder agrees.
        policy = build_cross_domain_execution_policy(
            primary_required=("domain.contracts", "domain.permissions"),
            supporting_required=("domain.permissions", "health.safety.validation"),
        )
        assert set(policy.required_steps) == {
            "domain.contracts",
            "domain.permissions",
            "health.safety.validation",
        }


# ── E. Project Domain ───────────────────────────────────────────────────────


class TestAcceptanceProjectDomain:
    def test_mutation_requires_validation_regression_blocks_correction_passes(
        self,
    ) -> None:
        ops = {op.operation_id: op for op in build_project_operation_definitions()}
        modify = ops["project.modify_code"]
        assert modify.validation_policy_id is not None
        policy = build_project_domain_change_policy(
            required_validation_ids=(modify.validation_policy_id,)
        )
        assert modify.validation_policy_id in policy.required_steps
        # Regression blocks acceptance.
        failing = _phase7_result(
            "vr-regress",
            status=ValidationStatus.FAILED,
            steps=(_phase7_step("syntax", ValidationStatus.FAILED),),
        )
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("syntax",),
                canonical_results=(failing,),
            )
        # Corrected regression passes.
        passing = _phase7_result(
            "vr-fixed", steps=(_phase7_step("syntax"), _phase7_step("ast"))
        )
        refs = require_canonical_validation_success(
            required_validation_ids=("syntax", "ast"),
            canonical_results=(passing,),
        )
        assert refs == ("vr-fixed",)
        # Commit authorization remains owned by Phase 7 commit gate.
        gate_denied = CommitGateEvaluator.evaluate(failing, policy)
        assert gate_denied.allowed is False

    def test_run_validation_does_not_exempt_mutation(self) -> None:
        from cmm.domains.validation_integration import (
            project_change_requires_validation,
        )

        assert project_change_requires_validation("project.modify_code") is True
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("syntax",),
                canonical_results=(),
            )


# ── F. Architectural proof ──────────────────────────────────────────────────


class TestAcceptanceArchitecture:
    def test_no_parallel_validation_subsystem(self) -> None:
        import pathlib

        prohibited = (
            "DomainValidationEngine",
            "DomainValidationRuntime",
            "DomainValidationStore",
            "DomainValidationRepository",
            "DomainValidationEventBus",
            "DomainValidationHistory",
            "DomainValidationCommitGate",
            "DomainValidationPolicyRegistry",
            "DomainValidationExecutor",
        )
        offenders = []
        for path in sorted(pathlib.Path("cmm/domains").glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for symbol in prohibited:
                if symbol in text:
                    offenders.append(f"{path.name}:{symbol}")
        assert offenders == []

    def test_domain_state_derives_from_canonical_phase7(self, tmp_path) -> None:
        request = _pack_request(tmp_path)
        domain_result = PipelineDomainValidator().validate(
            request, policy=build_domain_pack_installation_policy()
        )
        # Domain flags derive from canonical step results, not invented.
        names = {sr.name for sr in domain_result.step_results}
        assert set(DOMAIN_PACK_BASE_VALIDATION_IDS) <= names
        assert domain_result.status in (
            DomainValidationStatus.PASSED,
            DomainValidationStatus.WARNING,
        )

    def test_validation_grants_no_authority(self) -> None:
        definition = DomainOperationDefinition(
            operation_id="accept.op",
            domain_id="domain:accept",
            version="1.0.0",
            name="op",
            description="acceptance",
            operation_type=DomainOperationType.READ,
            required_permissions=("file.modify",),
            risk_level=PolicyRiskLevel.LOW,
            reversible=True,
            requires_approval=False,
            validation_policy_id="validation.accept.op",
            rollback_policy_id="rollback.accept.op",
            enabled=True,
            metadata={},
        )
        real = _phase7_result("vr-1", steps=(_phase7_step("syntax"),))
        refs = validate_domain_specialized_result(
            result={
                "domain_id": "domain:accept",
                "operation_id": "accept.op",
                "status": "success",
                "validation_result_ids": ["vr-1"],
            },
            expected_domain_id="domain:accept",
            expected_operation_id="accept.op",
            required_validation_ids=("syntax",),
            canonical_validation_results=(real,),
        )
        assert refs == ("vr-1",)
        assert definition.required_permissions == ("file.modify",)
        assert definition.enabled is True

    def test_public_contracts_serialize_deterministically(self) -> None:
        policy = build_domain_pack_installation_policy()
        assert policy.serialize() == policy.serialize()
        effective = compose_effective_validation_ids(
            primary_required=("domain.contracts",),
            supporting_required=("domain.permissions",),
        )
        assert effective == ("domain.contracts", "domain.permissions")
        assert (
            build_project_domain_change_policy().metadata["domain_policy_family"]
            == PROJECT_DOMAIN_CHANGE_POLICY_NAME
        )
        assert (
            build_domain_pack_update_policy().metadata["domain_policy_family"]
            == "DomainPackUpdatePolicy"
        )
