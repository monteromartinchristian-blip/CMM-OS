"""Phase 10.43 — Workflow and cross-domain validation composition (Task 5)."""

from __future__ import annotations

import pytest

from cmm.domains.validation_integration import (
    DomainValidationIntegrationError,
    compose_effective_validation_ids,
    is_ignored_caller_validation_metadata,
    require_canonical_validation_success,
)
from cmm.domains.validation_policy_bindings import (
    build_cross_domain_execution_policy,
    build_domain_workflow_policy,
    compose_required_validation_ids,
)
from cmm.validation import ValidationResult, ValidationStatus
from cmm.validation.steps import ValidationStepResult


def _step(name: str) -> ValidationStepResult:
    return ValidationStepResult(name=name, status=ValidationStatus.PASSED)


def _result(result_id: str, steps: tuple) -> ValidationResult:
    return ValidationResult(id=result_id, status=ValidationStatus.PASSED, steps=steps)


class TestWorkflowObligationPreservation:
    def test_workflow_policy_preserves_required_ids(self) -> None:
        policy = build_domain_workflow_policy(
            required_validation_ids=("parent.validation", "child.validation")
        )
        assert set(policy.required_steps) == {
            "parent.validation",
            "child.validation",
        }

    def test_phase_1042_operation_semantics_preserve_validation(self) -> None:
        # Phase 10.42 remains canonical owner: required_validations carry the
        # operation validation_policy_id into planning without 10.43 replanning.
        from cmm.agent_runtime.enums import PolicyRiskLevel
        from cmm.domains.enums import DomainOperationType
        from cmm.domains.operation_contracts import DomainOperationDefinition
        from cmm.domains.planner_workflow_integration import _operation_semantics

        definition = DomainOperationDefinition(
            operation_id="test.op",
            domain_id="domain:test",
            version="1.0.0",
            name="op",
            description="test",
            operation_type=DomainOperationType.READ,
            risk_level=PolicyRiskLevel.LOW,
            reversible=True,
            requires_approval=False,
            validation_policy_id="parent.validation",
            rollback_policy_id="rollback.test.op",
            enabled=True,
            metadata={},
        )
        semantics = _operation_semantics(definition, ())
        assert semantics["required_validations"] == ["parent.validation"]

    def test_ineligible_optional_branch_invents_nothing(self) -> None:
        # An empty/optional workflow contributes no obligations.
        policy = build_domain_workflow_policy(required_validation_ids=())
        assert policy.required_steps == ()
        assert compose_effective_validation_ids(workflow_required=()) == ()


class TestCrossDomainComposition:
    def test_deterministic_restrictive_union(self) -> None:
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
        # Deterministic: same inputs in different call order yield same output.
        reordered = compose_effective_validation_ids(
            workflow_required=("workflow.result.validation",),
            operation_required=("operation.output.validation",),
            supporting_required=("health.safety.validation", "domain.permissions"),
            primary_required=("domain.permissions", "domain.contracts"),
        )
        assert reordered == effective

    def test_supporting_cannot_weaken_primary(self) -> None:
        effective = compose_effective_validation_ids(
            primary_required=("domain.contracts", "domain.permissions"),
            supporting_required=("domain.permissions",),
        )
        assert "domain.contracts" in effective
        assert "domain.permissions" in effective

    def test_policy_builder_composes_monotonically(self) -> None:
        policy = build_cross_domain_execution_policy(
            primary_required=("domain.contracts", "domain.permissions"),
            supporting_required=("domain.permissions", "health.safety.validation"),
            operation_required=("operation.output.validation",),
            workflow_required=("workflow.result.validation",),
        )
        assert tuple(policy.required_steps) == (
            "domain.contracts",
            "domain.permissions",
            "health.safety.validation",
            "operation.output.validation",
            "workflow.result.validation",
        )

    def test_caller_metadata_cannot_remove_obligations(self) -> None:
        for key in (
            "required_validation_ids",
            "skip_validation",
            "validation_passed",
            "trust",
            "approval",
        ):
            assert is_ignored_caller_validation_metadata(key) is True
        # Host-derived composition never consults caller metadata: even when
        # caller claims empty/skipped, effective obligations remain.
        host_effective = compose_effective_validation_ids(
            primary_required=("domain.contracts",),
            operation_required=("operation.output.validation",),
        )
        assert host_effective == ("domain.contracts", "operation.output.validation")
        # A caller-supplied empty set is not an input to the composer at all;
        # composing with no groups yields empty, but composing with host
        # groups always preserves them (monotonic).
        assert set(host_effective) <= set(
            compose_required_validation_ids(host_effective, ("domain.contracts",))
        )

    def test_unknown_mandatory_id_fails_closed(self) -> None:
        effective = compose_effective_validation_ids(
            primary_required=("unknown.required.validation",),
        )
        assert effective == ("unknown.required.validation",)
        # The unknown ID is preserved (not silently dropped) and validation
        # fails closed for lack of evidence.
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=effective,
                canonical_results=(),
            )

    def test_duplicate_declarations_create_single_truth(self) -> None:
        effective = compose_effective_validation_ids(
            primary_required=("domain.contracts",),
            supporting_required=("domain.contracts",),
            operation_required=("domain.contracts",),
            workflow_required=("domain.contracts",),
        )
        assert effective == ("domain.contracts",)
        canonical = _result("vr-1", steps=(_step("domain.contracts"),))
        refs = require_canonical_validation_success(
            required_validation_ids=effective,
            canonical_results=(canonical,),
        )
        # One effective ID → one canonical execution reference, no Domain-level
        # copied duplicate truth.
        assert refs == ("vr-1",)

    def test_full_seven_group_union(self) -> None:
        effective = compose_effective_validation_ids(
            global_required=("global.mandatory",),
            primary_required=("domain.contracts",),
            supporting_required=("domain.permissions",),
            operation_required=("operation.output.validation",),
            workflow_required=("workflow.result.validation",),
            dependency_required=("dependency.validation",),
            project_required=("project.validation",),
        )
        assert effective == (
            "dependency.validation",
            "domain.contracts",
            "domain.permissions",
            "global.mandatory",
            "operation.output.validation",
            "project.validation",
            "workflow.result.validation",
        )


def _cross_test_operation(
    operation_id: str,
    domain_id: str,
    validation_policy_id: str | None,
    declared_ids: tuple[str, ...] = (),
):
    from cmm.agent_runtime.enums import PolicyRiskLevel
    from cmm.domains.enums import DomainOperationType
    from cmm.domains.operation_contracts import DomainOperationDefinition

    return DomainOperationDefinition(
        operation_id=operation_id,
        domain_id=domain_id,
        version="1.0.0",
        name="op",
        description="cross-domain test operation",
        operation_type=DomainOperationType.READ,
        required_permissions=(),
        risk_level=PolicyRiskLevel.LOW,
        reversible=False,
        requires_approval=False,
        validation_policy_id=validation_policy_id,
        rollback_policy_id=None,
        enabled=True,
        metadata=(
            {"domain_validation_requirement_ids": list(declared_ids)}
            if declared_ids
            else {}
        ),
    )


def _cross_port(tmp_path, project_dir):
    from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
    from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
    from cmm.agent_runtime.validation_execution_adapter import AgentValidationAdapter
    from cmm.domains.operation_execution import (
        DefaultDomainOperationOrchestrator,
        DomainOperationExecutionDelegate,
        OrchestratedCrossDomainOperationPort,
    )
    from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
    from cmm.domains.validation_integration import (
        resolve_domain_operation_validation_requirements as _resolver,
    )

    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)

    class Impl:
        def __init__(self, definition) -> None:
            self.definition = definition

        def execute(self, request) -> dict:
            return {"success": True, "output": {"status": "ok"}}

    alpha = _cross_test_operation("alpha.op", "domain:alpha", None)
    beta = _cross_test_operation(
        "beta.op", "domain:beta", "validation.beta.op", ("syntax_validator",)
    )
    registry.register(alpha, Impl(alpha))
    registry.register(beta, Impl(beta))
    adapter = AgentExecutionAdapter(
        registry=common,
        execution_delegate=DomainOperationExecutionDelegate(registry),
        validation_adapter=AgentValidationAdapter(),
    )
    orchestrator = DefaultDomainOperationOrchestrator(
        registry, adapter, operation_validation_provider=_resolver
    )
    port = OrchestratedCrossDomainOperationPort(
        orchestrator=orchestrator,
        operation_registry=registry,
        capabilities=("execute", "validation"),
        metadata={"validation_project_root": str(project_dir)},
    )
    return port


class TestRealCrossDomainEnforcement:
    def test_real_cross_domain_execution_uses_restrictive_validation_union(
        self, tmp_path
    ) -> None:
        from datetime import datetime, timezone

        from cmm.domains.composition_contracts import (
            DomainComposition,
            DomainCompositionItem,
        )
        from cmm.domains.cross_domain_contracts import (
            CrossDomainDomainResult,
            CrossDomainRequest,
        )
        from cmm.domains.cross_domain_engine import DefaultCrossDomainEngine
        from cmm.domains.enums import (
            CrossDomainStatus,
            DomainCompositionStatus,
            DomainResolutionStatus,
        )
        from cmm.domains.identifiers import DomainId
        from cmm.domains.resolver_contracts import DomainResolutionResult

        def _now():
            return datetime.now(timezone.utc)

        class Agent:
            def coordinate(self, *, domain_id, plan, context):
                return CrossDomainDomainResult(
                    domain_id=domain_id,
                    status="completed",
                    findings=(),
                    recommendations=(),
                    confidence=0.9,
                )

        project_dir = tmp_path / "xproj"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "main.py").write_text("def broken(:\n", encoding="utf-8")
        port = _cross_port(tmp_path, project_dir)

        class Resolver:
            def resolve(self, request):
                return DomainResolutionResult(
                    id="res-x",
                    context_id="ctx-x",
                    status=DomainResolutionStatus.RESOLVED,
                    primary_domain=DomainId(slug="alpha"),
                    supporting_domains=(DomainId(slug="beta"),),
                    resolved_at=_now(),
                )

        class Composer:
            def compose(self, resolution):
                return DomainComposition(
                    id="comp-x",
                    resolution_id="res-x",
                    status=DomainCompositionStatus.COMPOSED,
                    primary_domain=DomainId(slug="alpha"),
                    supporting_domains=(DomainId(slug="beta"),),
                    operations=(
                        DomainCompositionItem(
                            category="operations",
                            identifier="alpha.op",
                            contributing_domains=(DomainId(slug="alpha"),),
                            primary_contributor=DomainId(slug="alpha"),
                            precedence=0,
                        ),
                        DomainCompositionItem(
                            category="operations",
                            identifier="beta.op",
                            contributing_domains=(DomainId(slug="beta"),),
                            primary_contributor=DomainId(slug="beta"),
                            precedence=1,
                        ),
                    ),
                    composed_at=_now(),
                )

        engine = DefaultCrossDomainEngine(
            resolver=Resolver(), composer=Composer(), operation=port, agent=Agent()
        )
        captured: dict = {}
        raw_coordinate = port.coordinate_operations

        def _capture(**kwargs):
            outcome = raw_coordinate(**kwargs)
            captured["result"] = outcome
            return outcome

        port.coordinate_operations = _capture  # type: ignore[method-assign]
        engine.execute(
            CrossDomainRequest(id="r-x", objective="o", primary_domain="domain:alpha")
        )
        # alpha.op carries no validation of its own, but the restrictive
        # cross-domain union (beta's syntax obligation) blocks it on the
        # broken tree through the real runtime path.
        port_result = captured["result"]
        assert port_result.status is not CrossDomainStatus.COMPLETED
        assert port.calls != []
        executed = {call for call, _ in port.calls}
        assert {"alpha.op", "beta.op"} <= executed
        blocked_ids = {finding.identifier for finding in port_result.findings}
        assert "alpha.op.validation_blocked" in blocked_ids
        assert port_result.metadata["cross_domain_validation_policy"] == (
            "CrossDomainExecutionPolicy"
        )
        assert "syntax_validator" in port_result.metadata["effective_validation_ids"]

        # Correcting the tree lets the same union pass: obligations are
        # enforced, not merely recorded.
        (project_dir / "main.py").write_text("x = 1\n", encoding="utf-8")
        port2 = _cross_port(tmp_path, project_dir)
        engine2 = DefaultCrossDomainEngine(
            resolver=Resolver(), composer=Composer(), operation=port2, agent=Agent()
        )
        captured2: dict = {}
        raw_coordinate2 = port2.coordinate_operations

        def _capture2(**kwargs):
            outcome = raw_coordinate2(**kwargs)
            captured2["result"] = outcome
            return outcome

        port2.coordinate_operations = _capture2  # type: ignore[method-assign]
        result2 = engine2.execute(
            CrossDomainRequest(id="r-x2", objective="o", primary_domain="domain:alpha")
        )
        assert captured2["result"].status is CrossDomainStatus.COMPLETED
        assert result2.status is CrossDomainStatus.COMPLETED

    def test_caller_metadata_cannot_remove_cross_domain_required_validation(
        self,
    ) -> None:
        # Hostile per-request metadata cannot weaken host-derived obligations:
        # the definition-derived requirement still fails closed.
        from cmm.agent_runtime.errors import ValidationAdapterError
        from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
        from cmm.agent_runtime.validation_execution_adapter import (
            AgentValidationAdapter,
        )
        from cmm.domains.operation_contracts import DomainOperationRequest
        from cmm.domains.operation_execution import DefaultDomainOperationOrchestrator
        from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
        from cmm.domains.validation_integration import (
            resolve_domain_operation_validation_requirements as _resolver,
        )

        adapter = AgentExecutionAdapter(
            execution_delegate=lambda req: {"success": True, "output": {}},
            validation_adapter=AgentValidationAdapter(),
        )
        registry = InMemoryDomainOperationRegistry(adapter.registry)
        definition = _cross_test_operation(
            "alpha.op", "domain:alpha", "validation.alpha.op"
        )

        class Impl:
            def __init__(self) -> None:
                self.definition = definition

            def execute(self, request) -> dict:
                return {"success": True, "output": {}}  # pragma: no cover

        registry.register(definition, Impl())
        orchestrator = DefaultDomainOperationOrchestrator(
            registry, adapter, operation_validation_provider=_resolver
        )
        request = DomainOperationRequest(
            request_id="req-hostile-1",
            operation_id="alpha.op",
            operation_version="1.0.0",
            inputs={},
            agent_run_id="run-1",
            workflow_id="wf-1",
            task_id="task-1",
            primary_domain_id="domain:alpha",
            idempotency_key="idem-hostile-1",
            capabilities=("execute", "validation"),
            metadata={
                "required_validation_ids": (),
                "skip_validation": True,
                "validation_passed": True,
            },
        )
        with pytest.raises(ValidationAdapterError):
            orchestrator.execute(request)

    def test_duplicate_cross_domain_requirement_executes_as_one_obligation(
        self, tmp_path
    ) -> None:
        # The same requirement declared by several sources executes once.
        from datetime import datetime, timezone

        from cmm.agent_runtime.enums import (
            AgentValidationStage,
            OperationEffectType,
            OperationEnvironment,
            ValidationRequirementKind,
        )
        from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
        from cmm.agent_runtime.operation_execution_contracts import (
            AgentOperationRequest,
            OperationDescriptor,
        )
        from cmm.agent_runtime.validation_execution_adapter import (
            AgentValidationAdapter,
        )
        from cmm.agent_runtime.validation_integration_contracts import (
            ValidationRequirement,
        )

        target = tmp_path / "dup.py"
        target.write_text("x = 1\n", encoding="utf-8")
        adapter = AgentExecutionAdapter(
            execution_delegate=lambda req: {"success": True},
            validation_adapter=AgentValidationAdapter(),
        )
        adapter.register_operation(
            OperationDescriptor(
                name="dup.op",
                version="1",
                description="t",
                input_schema={"type": "object"},
                effects=(OperationEffectType.READ,),
                reversible=True,
                compatible_environments=(OperationEnvironment.LOCAL,),
            )
        )

        def _req(suffix: str) -> ValidationRequirement:
            return ValidationRequirement(
                requirement_id=f"req-dup-{suffix}",
                validation_kind=ValidationRequirementKind.SYNTAX,
                stage=AgentValidationStage.POST_EXECUTION,
                required=True,
                blocking=True,
                validator_ids=("syntax_validator",),
            )

        request = AgentOperationRequest(
            id="req-dup-1",
            agent_run_id="run-1",
            workflow_id="wf-1",
            task_id="task-1",
            operation_name="dup.op",
            operation_version="1",
            parameters={},
            idempotency_key="idem-dup-1",
            created_at=datetime.now(timezone.utc).isoformat(),
            validation_requirements=(_req("a"), _req("b"), _req("c")),
            validation_project_root=str(tmp_path),
        )
        result = adapter.execute(request)
        assert result.success is True
        validation_adapter = adapter.validation_adapter
        assert validation_adapter is not None
        stored = validation_adapter.repository.get_result(
            result.validation_result_ids[-1]
        )
        steps = stored.validation_report.get("steps", [])
        syntax_steps = [s for s in steps if s.get("name") == "syntax"]
        assert len(syntax_steps) == 1
