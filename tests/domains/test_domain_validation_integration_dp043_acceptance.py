"""Phase 10.43 — AT-DP-043 connected acceptance (V2).

DP-043: Domain Intelligence expresses specialized validation policies and
obligations while all authoritative validation execution remains owned by
canonical Phase 7 (and the Phase 9 bridge for agentic runtime).

Every section below exercises real canonical components or official
in-memory implementations end to end. No fixed-decision adapter doubles,
no manual validation unions in place of execution, and no synthetic
``ValidationResult`` objects appear on architectural paths.
"""

from __future__ import annotations

import json

import pytest

from cmm.agent_runtime.errors import ValidationAdapterError
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.validation_execution_adapter import AgentValidationAdapter
from cmm.domains.enums import (
    CrossDomainStatus,
    DomainLoadStatus,
    DomainOperationStatus,
    DomainStatus,
    DomainValidationStatus,
)
from cmm.domains.errors import DomainSourceUntrusted
from cmm.domains.operation_execution import (
    build_domain_workflow_operation_adapter,
)
from cmm.domains.validation import PipelineDomainValidator
from cmm.domains.validation_integration import (
    compose_effective_validation_ids,
    project_change_requires_validation,
)
from cmm.domains.validation_policy_bindings import (
    DOMAIN_PACK_BASE_VALIDATION_IDS,
    PROJECT_DOMAIN_CHANGE_POLICY_NAME,
    build_domain_pack_installation_policy,
    build_domain_pack_update_policy,
    build_project_domain_change_policy,
)
from cmm.domains.workflow_contracts import (
    DomainWorkflowContext,
    DomainWorkflowDefinition,
)
from cmm.validation import CommitGateEvaluator, ValidationContext
from cmm.validation.catalog import ast_step, syntax_step
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType, WorkflowRunStatus
from tests.domains._loader_helpers import make_candidate, write_domain_dir
from tests.domains.test_domain_api_lifecycle import _make_api
from tests.domains.test_domain_validation_cross_domain import _cross_port
from tests.domains.test_domain_validation_runtime_integration import (
    _modify_code_stack,
    _specialized_stack,
    _validating_operation,
    _validating_stack,
)


def _breaking_manifest(slug: str, version: str) -> dict:
    return {
        "id": slug,
        "version": version,
        "author": "tester",
        "license": "MIT",
        "minimum_cmm_version": "99.0.0",
    }


# ── A. Domain Pack installation/update through the real lifecycle ─────────────


class TestAcceptancePackInstallation:
    def test_real_install_applies_policy_before_registration(self, tmp_path) -> None:
        api, registry = _make_api()
        domain_dir = write_domain_dir(tmp_path / "good", "greeter", "1.0.0")
        loaded = api.install_domain(make_candidate(domain_dir, "greeter", "1.0.0"))
        assert loaded.status == DomainLoadStatus.LOADED
        # Phase 7 pipeline executed the mandatory Domain set under the
        # installation policy (direct evidence on the same path).
        validator = PipelineDomainValidator()
        direct = validator.validate(
            _request_for(domain_dir, "greeter"),
            policy=build_domain_pack_installation_policy(),
        )
        executed = {sr.name for sr in direct.step_results}
        assert set(DOMAIN_PACK_BASE_VALIDATION_IDS) <= executed

        # A pack violating a mandatory check is blocked before registration.
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        breaking = write_domain_dir(bad_dir, "breaker", "1.0.0")
        (breaking / "manifest.json").write_text(
            json.dumps(_breaking_manifest("breaker", "1.0.0")), encoding="utf-8"
        )
        blocked = api.install_domain(make_candidate(breaking, "breaker", "1.0.0"))
        assert blocked.status == DomainLoadStatus.FAILED
        assert blocked.errors != ()
        assert registry.contains("breaker") is False

    def test_real_reload_applies_update_policy_atomically(self, tmp_path) -> None:
        from cmm.domains.loader import DeclarativeDomainLoader
        from cmm.domains.manifest_reader import JsonDomainManifestReader
        from cmm.domains.registry import DomainRegistry

        registry = DomainRegistry()
        loader = DeclarativeDomainLoader(
            manifest_reader=JsonDomainManifestReader(), registry=registry
        )
        dir_a = write_domain_dir(tmp_path / "packs", "keeper", "1.0.0")
        assert (
            loader.load(make_candidate(dir_a, "keeper", "1.0.0")).status
            == DomainLoadStatus.LOADED
        )
        dir_b = write_domain_dir(tmp_path / "packs_b", "keeper", "2.0.0")
        (dir_b / "manifest.json").write_text(
            json.dumps(_breaking_manifest("keeper", "2.0.0")), encoding="utf-8"
        )
        failed = loader.reload(make_candidate(dir_b, "keeper", "2.0.0"))
        assert failed.status == DomainLoadStatus.FAILED
        assert registry.get("keeper", "1.0.0") is not None
        assert registry.get("keeper", "2.0.0") is None

        (dir_b / "manifest.json").write_text(
            json.dumps(
                {
                    "id": "keeper",
                    "version": "2.0.0",
                    "author": "tester",
                    "license": "MIT",
                }
            ),
            encoding="utf-8",
        )
        fixed = loader.reload(make_candidate(dir_b, "keeper", "2.0.0"))
        assert fixed.status == DomainLoadStatus.LOADED
        assert registry.get("keeper", "2.0.0") is not None

    def test_install_does_not_enable_or_authorize(self, tmp_path) -> None:
        api, registry = _make_api()
        domain_dir = write_domain_dir(tmp_path / "good", "solo", "1.0.0")
        result = api.install_domain(make_candidate(domain_dir, "solo", "1.0.0"))
        assert result.status == DomainLoadStatus.LOADED
        record = registry.get_record("solo", "1.0.0")
        assert record.status == DomainStatus.REGISTERED
        assert record.definition.enabled is False

    def test_untrusted_install_stays_fail_closed(self, tmp_path) -> None:
        api, registry = _make_api()
        domain_dir = write_domain_dir(tmp_path / "good", "shady", "1.0.0")
        candidate = make_candidate(domain_dir, "shady", "1.0.0", trusted=False)
        with pytest.raises(DomainSourceUntrusted):
            api.install_domain(candidate)
        assert registry.contains("shady") is False


def _request_for(domain_dir, slug: str):
    from cmm.domains.manifest_reader import JsonDomainManifestReader
    from cmm.domains.pack import DomainPack, ParsedDomainPack
    from cmm.domains.validation_contracts import DomainValidationRequest

    manifest_doc = JsonDomainManifestReader().read_document(
        domain_dir / "manifest.json"
    )
    parsed = ParsedDomainPack.from_declarative_dict(manifest_doc.data)
    pack = DomainPack(
        definition=parsed.definition,
        manifest=parsed.manifest,
        root_path=str(domain_dir),
    )
    return DomainValidationRequest(
        pack=pack,
        root_path=str(domain_dir),
        strict=False,
        run_tests=False,
    )


# ── B. Real Domain operation through orchestrator → adapter → Phase 7 ────────


class TestAcceptanceDomainOperation:
    def test_missing_adapter_fails_closed(self) -> None:
        from cmm.agent_runtime.operation_execution_contracts import OperationDescriptor

        adapter = AgentExecutionAdapter(
            execution_delegate=lambda req: {"success": True}
        )
        adapter.register_operation(
            OperationDescriptor(
                name="accept.op",
                version="1",
                description="acceptance",
                input_schema={"type": "object"},
            )
        )
        from datetime import datetime, timezone

        from cmm.agent_runtime.operation_execution_contracts import (
            AgentOperationRequest,
        )

        request = AgentOperationRequest(
            id="req-at",
            agent_run_id="run-at",
            workflow_id="wf-at",
            task_id="task-at",
            operation_name="accept.op",
            operation_version="1",
            parameters={},
            idempotency_key="idem-at",
            environment="local",
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata={"requires_validation": True},
        )
        with pytest.raises(ValidationAdapterError):
            adapter.execute(request)

    def test_real_pre_failure_prevents_execution(self, tmp_path) -> None:
        orchestrator, request, calls, _ = _modify_code_stack(
            tmp_path, break_tree=True, break_on_execute=False
        )
        result = orchestrator.execute(request)
        assert calls == []
        assert result.status is not DomainOperationStatus.COMPLETED
        assert result.metadata.get("validation_result_ids") != ()

    def test_real_post_failure_prevents_accepted_success(self, tmp_path) -> None:
        orchestrator, request, calls, _ = _modify_code_stack(
            tmp_path, break_tree=False, break_on_execute=True
        )
        result = orchestrator.execute(request)
        assert calls != []
        assert result.status is not DomainOperationStatus.COMPLETED
        assert result.metadata.get("validation_result_ids") != ()

    def test_real_operation_fix_passes_with_evidence_retained(self, tmp_path) -> None:
        orchestrator, request, _, _ = _modify_code_stack(
            tmp_path, break_tree=False, break_on_execute=False
        )
        result = orchestrator.execute(request)
        assert result.status is DomainOperationStatus.COMPLETED
        assert result.metadata.get("validation_result_ids") != ()

    def test_unknown_required_validator_fails_closed(self, tmp_path) -> None:
        import pytest

        from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
        from cmm.domains.operation_contracts import DomainOperationRequest
        from cmm.domains.operation_execution import DefaultDomainOperationOrchestrator
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
                return {"success": True, "output": {}}  # pragma: no cover

        import dataclasses

        from tests.domains.test_domain_validation_runtime_integration import (
            _domain_operation,
        )

        definition = dataclasses.replace(
            _domain_operation(), reversible=False, rollback_policy_id=None
        )
        registry.register(definition, Impl(definition))
        adapter = AgentExecutionAdapter(
            registry=common,
            execution_delegate=lambda req: {"success": True, "output": {}},
            validation_adapter=AgentValidationAdapter(),
        )
        orchestrator = DefaultDomainOperationOrchestrator(
            registry, adapter, operation_validation_provider=_resolver
        )
        request = DomainOperationRequest(
            request_id="req-at-unk",
            operation_id="test.op",
            operation_version="1.0.0",
            inputs={},
            agent_run_id="run-1",
            workflow_id="wf-1",
            task_id="task-1",
            primary_domain_id="domain:test",
            idempotency_key="idem-at-unk",
            capabilities=("execute", "validation"),
        )
        with pytest.raises(ValidationAdapterError):
            orchestrator.execute(request)


# ── C. Real workflow through canonical runtime nodes ─────────────────────────


class TestAcceptanceWorkflow:
    def test_real_workflow_executes_required_validation_nodes(self, tmp_path) -> None:
        project_dir = tmp_path / "flowproj"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "main.py").write_text("x = 1\n", encoding="utf-8")
        executor, _, calls = _validating_stack(tmp_path, str(project_dir))
        definition = DomainWorkflowDefinition(
            workflow_id="flow.main",
            domain_id="domain:flow",
            version="1.0.0",
            name="main",
            nodes=(
                WorkflowNode(
                    node_id="first",
                    node_type=WorkflowNodeType.EXECUTE_OPERATION,
                    name="first",
                    operation_id="flow.first",
                    operation_version="1.0.0",
                ),
                WorkflowNode(
                    node_id="second",
                    node_type=WorkflowNodeType.EXECUTE_OPERATION,
                    name="second",
                    dependencies=("first",),
                    operation_id="flow.second",
                    operation_version="1.0.0",
                ),
            ),
        )
        context = DomainWorkflowContext(
            "domain:flow",
            available_operations=frozenset({"flow.first", "flow.second"}),
        )
        run = executor.execute(definition, context, {})
        assert run.common_run.status is WorkflowRunStatus.COMPLETED
        assert calls == ["flow.first", "flow.second"]

        (project_dir / "main.py").write_text("def broken(:\n", encoding="utf-8")
        executor2, _, calls2 = _validating_stack(tmp_path, str(project_dir))
        run2 = executor2.execute(definition, context, {})
        assert run2.common_run.status is WorkflowRunStatus.FAILED
        assert calls2 == []

    def test_required_subworkflow_validation_survives_execution(self, tmp_path) -> None:
        import itertools

        from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
        from cmm.domains.operation_execution import (
            DefaultDomainOperationOrchestrator,
            DomainOperationExecutionDelegate,
        )
        from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
        from cmm.domains.validation_integration import (
            compose_effective_validation_ids,
        )
        from cmm.domains.validation_integration import (
            resolve_domain_operation_validation_requirements as _resolver,
        )
        from cmm.domains.workflow_execution import DomainWorkflowExecutor

        project_dir = tmp_path / "subproj"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "main.py").write_text("x = 1\n", encoding="utf-8")
        closure = compose_effective_validation_ids(
            workflow_required=("syntax_validator",),
            dependency_required=("syntax_validator",),
        )
        assert closure == ("syntax_validator",)

        common = InMemoryAgentOperationRegistry()
        registry = InMemoryDomainOperationRegistry(common)
        calls: list = []

        class Impl:
            def __init__(self, definition) -> None:
                self.definition = definition

            def execute(self, request) -> dict:
                calls.append(getattr(request, "operation_name", None))
                return {"success": True, "output": {"status": "ok"}}

        for op_id in ("flow.parent", "flow.child"):
            definition = _validating_operation(operation_id=op_id)
            registry.register(definition, Impl(definition))
        adapter = AgentExecutionAdapter(
            registry=common,
            execution_delegate=DomainOperationExecutionDelegate(registry),
            validation_adapter=AgentValidationAdapter(),
        )
        orchestrator = DefaultDomainOperationOrchestrator(
            registry, adapter, operation_validation_provider=_resolver
        )
        child_definition = DomainWorkflowDefinition(
            workflow_id="flow.child",
            domain_id="domain:flow",
            version="1.0.0",
            name="child",
            nodes=(
                WorkflowNode(
                    node_id="child-op",
                    node_type=WorkflowNodeType.EXECUTE_OPERATION,
                    name="child-op",
                    operation_id="flow.child",
                    operation_version="1.0.0",
                ),
            ),
        )
        ids = itertools.count()
        node_adapter = build_domain_workflow_operation_adapter(
            orchestrator,
            primary_domain_id="domain:flow",
            capabilities=("execute", "validation"),
            metadata={"validation_project_root": str(project_dir)},
            additional_validation_ids=closure,
            workflow_definitions={("flow.child", "1.0.0"): child_definition},
            available_operations=("flow.parent", "flow.child"),
            id_factory=lambda: f"at-sub-{next(ids)}",
        )
        run_ids = itertools.count()
        executor = DomainWorkflowExecutor(
            id_factory=lambda: f"at-run-{next(run_ids)}",
            operation_adapter=node_adapter,
        )
        parent = DomainWorkflowDefinition(
            workflow_id="flow.parent",
            domain_id="domain:flow",
            version="1.0.0",
            name="parent",
            nodes=(
                WorkflowNode(
                    node_id="parent-op",
                    node_type=WorkflowNodeType.EXECUTE_OPERATION,
                    name="parent-op",
                    operation_id="flow.parent",
                    operation_version="1.0.0",
                ),
                WorkflowNode(
                    node_id="child-flow",
                    node_type=WorkflowNodeType.INVOKE_SUBWORKFLOW,
                    name="child-flow",
                    dependencies=("parent-op",),
                    subworkflow_id="flow.child",
                    subworkflow_version="1.0.0",
                ),
            ),
        )
        context = DomainWorkflowContext(
            "domain:flow", available_operations=frozenset({"flow.parent"})
        )
        run = executor.execute(parent, context, {})
        assert run.common_run.status is WorkflowRunStatus.COMPLETED
        assert calls == ["flow.parent", "flow.child"]

        (project_dir / "main.py").write_text("def broken(:\n", encoding="utf-8")
        run2 = executor.execute(parent, context, {})
        assert run2.common_run.status is WorkflowRunStatus.FAILED


# ── D. Real cross-domain restrictive union ────────────────────────────────────


class TestAcceptanceCrossDomain:
    def test_real_cross_domain_union_enforced_in_runtime(self, tmp_path) -> None:
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
            DomainCompositionStatus,
            DomainResolutionStatus,
        )
        from cmm.domains.identifiers import DomainId
        from cmm.domains.resolver_contracts import DomainResolutionResult

        def _now():
            return datetime.now(timezone.utc)

        project_dir = tmp_path / "xproj"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "main.py").write_text("def broken(:\n", encoding="utf-8")

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

        class Agent:
            def coordinate(self, *, domain_id, plan, context):
                return CrossDomainDomainResult(
                    domain_id=domain_id,
                    status="completed",
                    findings=(),
                    recommendations=(),
                    confidence=0.9,
                )

        port = _cross_port(tmp_path, project_dir)
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
        port_result = captured["result"]
        assert port_result.status is not CrossDomainStatus.COMPLETED
        blocked = {finding.identifier for finding in port_result.findings}
        assert "alpha.op.validation_blocked" in blocked
        assert (
            port_result.metadata["cross_domain_validation_policy"]
            == "CrossDomainExecutionPolicy"
        )
        assert "syntax_validator" in port_result.metadata["effective_validation_ids"]

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
        engine2.execute(
            CrossDomainRequest(id="r-x2", objective="o", primary_domain="domain:alpha")
        )
        assert captured2["result"].status is CrossDomainStatus.COMPLETED


# ── E. Real Project Domain boundary ───────────────────────────────────────────


class TestAcceptanceProjectDomain:
    def test_project_mutation_fail_fix_pass_through_real_path(self, tmp_path) -> None:
        orchestrator, request, _, _ = _modify_code_stack(
            tmp_path, break_tree=False, break_on_execute=False
        )
        assert orchestrator.execute(request).status is DomainOperationStatus.COMPLETED

        breaking_orch, breaking_request, _, _ = _modify_code_stack(
            tmp_path, break_tree=False, break_on_execute=True
        )
        assert (
            breaking_orch.execute(breaking_request).status
            is not DomainOperationStatus.COMPLETED
        )

    def test_run_validation_availability_does_not_exempt_mutation(
        self, tmp_path
    ) -> None:
        assert project_change_requires_validation("project.modify_code") is True
        assert project_change_requires_validation("project.run_validation") is False
        orchestrator, request, _, _ = _modify_code_stack(
            tmp_path, break_tree=True, break_on_execute=False
        )
        blocked = orchestrator.execute(request)
        assert blocked.status is not DomainOperationStatus.COMPLETED
        assert blocked.metadata.get("validation_result_ids") != ()

    def test_commit_authorization_stays_with_phase7_gate(self, tmp_path) -> None:
        from pathlib import Path

        project_dir = tmp_path / "commitproj"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "main.py").write_text("def broken(:\n", encoding="utf-8")
        from cmm.validation import build_default_validation_pipeline

        engine = build_default_validation_pipeline()

        def _canonical():
            return engine.run(
                ValidationContext(project_root=Path(project_dir)),
                (syntax_step(), ast_step()),
            )

        failing = _canonical()
        assert failing.status.value == "failed"
        policy = build_project_domain_change_policy(impact="small")
        assert policy.metadata["domain_policy_family"] == (
            PROJECT_DOMAIN_CHANGE_POLICY_NAME
        )
        assert CommitGateEvaluator.evaluate(failing, policy).allowed is False

        (project_dir / "main.py").write_text("x = 1\n", encoding="utf-8")
        passing = _canonical()
        assert passing.status.value == "passed"
        gate = CommitGateEvaluator.evaluate(passing, policy)
        assert gate.validation_result_id == passing.id


# ── F. Specialized result acceptance at the real boundary ─────────────────────


class TestAcceptanceSpecializedResult:
    def test_invalid_specialized_result_rejected_at_acceptance(self) -> None:
        orchestrator, request = _specialized_stack(
            {
                "domain_id": "domain:other",
                "operation_id": "flow.special",
                "status": "ok",
            }
        )
        assert (
            orchestrator.execute(request).status is not DomainOperationStatus.COMPLETED
        )

    def test_coherent_specialized_result_accepted(self) -> None:
        orchestrator, request = _specialized_stack(
            {
                "domain_id": "domain:flow",
                "operation_id": "flow.special",
                "status": "ok",
            }
        )
        assert orchestrator.execute(request).status is DomainOperationStatus.COMPLETED


# ── G. Architectural ownership ────────────────────────────────────────────────


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

    def test_phase7_is_result_truth_phase9_is_bridge(self, tmp_path) -> None:
        from cmm.agent_runtime.validation_execution_adapter import (
            AgentValidationAdapter as Phase9Adapter,
        )
        from cmm.domains.planner_workflow_integration import _operation_semantics
        from cmm.validation import ValidationPipeline
        from tests.domains.test_domain_validation_runtime_integration import (
            _domain_operation,
        )

        assert Phase9Adapter is AgentValidationAdapter
        assert ValidationPipeline.__module__ == "cmm.validation.pipeline"
        # Phase 10.42 still owns the planning projection (obligation, not proof).
        semantics = _operation_semantics(_domain_operation(), ())
        assert semantics["required_validations"] == ["validation.test.op"]
        # Domain pack truth derives from canonical Phase 7 step execution.
        domain_dir = tmp_path / "truth"
        domain_dir.mkdir(parents=True, exist_ok=True)
        (domain_dir / "manifest.json").write_text(
            json.dumps(
                {"id": "truth", "version": "1.0.0", "author": "t", "license": "MIT"}
            ),
            encoding="utf-8",
        )
        (domain_dir / "probe.py").write_text("x = 1\n", encoding="utf-8")
        result = PipelineDomainValidator().validate(
            _request_for(domain_dir, "truth"),
            policy=build_domain_pack_installation_policy(),
        )
        names = {sr.name for sr in result.step_results}
        assert set(DOMAIN_PACK_BASE_VALIDATION_IDS) <= names
        assert result.status in (
            DomainValidationStatus.PASSED,
            DomainValidationStatus.WARNING,
        )

    def test_validation_grants_no_authority(self, tmp_path) -> None:
        api, registry = _make_api()
        domain_dir = write_domain_dir(tmp_path / "good", "plain", "1.0.0")
        loaded = api.install_domain(make_candidate(domain_dir, "plain", "1.0.0"))
        assert loaded.status == DomainLoadStatus.LOADED
        record = registry.get_record("plain", "1.0.0")
        assert record.definition.enabled is False

        orchestrator, request, _, _ = _modify_code_stack(
            tmp_path, break_tree=False, break_on_execute=False
        )
        result = orchestrator.execute(request)
        assert result.status is DomainOperationStatus.COMPLETED
        # Success carries validation references, never permissions/approvals.
        assert result.metadata.get("validation_result_ids") != ()

    def test_update_policy_record_and_public_contracts(self) -> None:
        assert (
            build_domain_pack_update_policy().metadata["domain_policy_family"]
            == "DomainPackUpdatePolicy"
        )
        assert compose_effective_validation_ids(
            primary_required=("domain.contracts",),
            supporting_required=("domain.permissions",),
        ) == ("domain.contracts", "domain.permissions")


# ── H. V2→V3 remediation: BLOCKER-V2-03 connected fail-closed invariants ──────


class TestAcceptanceV3FailClosedInvariants:
    """Connected DP-043 closure: provider omission, empty requirements,
    unconditional specialized gate, Project affected-test, and impact
    escalation through the real runtime path."""

    def test_provider_omission_fails_closed_with_adapter_present(self) -> None:
        from cmm.agent_runtime.operation_registry import (
            InMemoryAgentOperationRegistry,
        )
        from cmm.domains.operation_contracts import DomainOperationRequest
        from cmm.domains.operation_execution import (
            DefaultDomainOperationOrchestrator,
            DomainOperationExecutionDelegate,
        )
        from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
        from cmm.domains.validation_integration import (
            DomainValidationIntegrationError,
        )
        from tests.domains.test_domain_validation_runtime_integration import (
            _validating_operation,
        )

        common = InMemoryAgentOperationRegistry()
        registry = InMemoryDomainOperationRegistry(common)
        definition = _validating_operation(
            operation_id="flow.v3-required",
            validation_policy_id="validation.flow.v3-required",
            declared_ids=(),
        )

        class Impl:
            def __init__(self) -> None:
                self.definition = definition

            def execute(self, request) -> dict:  # pragma: no cover
                raise AssertionError("must not execute without provider")

        registry.register(definition, Impl())
        adapter = AgentExecutionAdapter(
            registry=common,
            execution_delegate=DomainOperationExecutionDelegate(registry),
            validation_adapter=AgentValidationAdapter(),
        )
        orchestrator = DefaultDomainOperationOrchestrator(registry, adapter)
        request = DomainOperationRequest(
            request_id="req-v3-provider-omitted",
            operation_id="flow.v3-required",
            operation_version="1.0.0",
            inputs={},
            agent_run_id="run-1",
            workflow_id="wf-1",
            task_id="task-1",
            primary_domain_id="domain:flow",
            idempotency_key="idem-v3-provider-omitted",
            capabilities=("execute", "validation"),
        )
        with pytest.raises(DomainValidationIntegrationError):
            orchestrator.execute(request)

    def test_empty_requirements_fail_closed_for_mandated_operation(self) -> None:
        from datetime import datetime, timezone

        from cmm.agent_runtime.operation_execution_adapter import (
            AgentExecutionAdapter as ExecAdapter,
        )
        from cmm.agent_runtime.operation_execution_contracts import (
            AgentOperationRequest,
            OperationDescriptor,
        )

        adapter = ExecAdapter(
            execution_delegate=lambda req: {"success": True, "output": {}},
            validation_adapter=AgentValidationAdapter(),
        )
        adapter.register_operation(
            OperationDescriptor(
                name="accept.v3empty",
                version="1",
                description="v3 empty requirements",
                input_schema={"type": "object"},
            )
        )
        request = AgentOperationRequest(
            id="req-v3-empty",
            agent_run_id="run-v3",
            workflow_id="wf-v3",
            task_id="task-v3",
            operation_name="accept.v3empty",
            operation_version="1",
            parameters={},
            idempotency_key="idem-v3-empty",
            environment="local",
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata={"requires_validation": True},
            validation_requirements=(),
        )
        with pytest.raises(ValidationAdapterError):
            adapter.execute(request)

    def test_specialized_result_gate_without_provider(self) -> None:
        from cmm.agent_runtime.operation_registry import (
            InMemoryAgentOperationRegistry,
        )
        from cmm.domains.operation_contracts import DomainOperationRequest
        from cmm.domains.operation_execution import (
            DefaultDomainOperationOrchestrator,
            DomainOperationExecutionDelegate,
        )
        from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
        from tests.domains.test_domain_validation_runtime_integration import (
            _validating_operation,
        )

        common = InMemoryAgentOperationRegistry()
        registry = InMemoryDomainOperationRegistry(common)
        definition = _validating_operation(
            operation_id="flow.v3-special",
            validation_policy_id=None,
            declared_ids=(),
        )

        class Impl:
            def __init__(self) -> None:
                self.definition = definition

            def execute(self, request) -> dict:
                return {
                    "success": True,
                    "output": {
                        "domain_id": "domain:other",
                        "operation_id": "flow.v3-special",
                        "status": "ok",
                    },
                }

        registry.register(definition, Impl())
        adapter = AgentExecutionAdapter(
            registry=common,
            execution_delegate=DomainOperationExecutionDelegate(registry),
            validation_adapter=AgentValidationAdapter(),
        )
        orchestrator = DefaultDomainOperationOrchestrator(registry, adapter)
        request = DomainOperationRequest(
            request_id="req-v3-special",
            operation_id="flow.v3-special",
            operation_version="1.0.0",
            inputs={},
            agent_run_id="run-1",
            workflow_id="wf-1",
            task_id="task-1",
            primary_domain_id="domain:flow",
            idempotency_key="idem-v3-special",
            capabilities=("execute", "validation"),
        )
        assert (
            orchestrator.execute(request).status is not DomainOperationStatus.COMPLETED
        )

    def test_project_affected_test_failure_via_real_path(self, tmp_path) -> None:
        import ast
        import subprocess
        import sys

        from tests.domains.test_domain_validation_project_integration import (
            _affected_test_stack,
        )

        orchestrator, request, _ = _affected_test_stack(tmp_path, break_test=False)
        assert orchestrator.execute(request).status is DomainOperationStatus.COMPLETED

        breaking_orch, breaking_request, _ = _affected_test_stack(
            tmp_path, break_test=True
        )
        breaking = breaking_orch.execute(breaking_request)
        assert breaking.status is not DomainOperationStatus.COMPLETED

        broken_text = (tmp_path / "affproj" / "main.py").read_text(encoding="utf-8")
        compile(broken_text, "main.py", "exec")
        ast.parse(broken_text)
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

        (tmp_path / "affproj" / "main.py").write_text(
            "def add(a, b):\n    return a + b\n", encoding="utf-8"
        )
        fixed_orch, fixed_request, _ = _affected_test_stack(tmp_path, break_test=False)
        assert (
            fixed_orch.execute(fixed_request).status is DomainOperationStatus.COMPLETED
        )

    def test_project_impact_escalation_via_real_runtime(self) -> None:
        from cmm.domains.project.operations import (
            build_project_operation_definitions,
        )
        from cmm.domains.validation_integration import (
            DomainValidationIntegrationError,
            resolve_domain_operation_validation_requirements,
            resolve_project_domain_change_validation_ids,
        )

        ops = {op.operation_id: op for op in build_project_operation_definitions()}
        definition = ops["project.modify_code"]
        small = resolve_project_domain_change_validation_ids(definition, impact="small")
        assert set(small) == {
            "formatter_check",
            "lint",
            "syntax_validator",
            "ast_validator",
            "affected_tests_step",
        }
        with pytest.raises(DomainValidationIntegrationError):
            resolve_project_domain_change_validation_ids(
                definition, impact="structural"
            )
        with pytest.raises(DomainValidationIntegrationError):
            resolve_domain_operation_validation_requirements(
                definition, impact="structural", changed_files=("main.py",)
            )
        with pytest.raises(DomainValidationIntegrationError):
            resolve_project_domain_change_validation_ids(definition, impact="public")
        with pytest.raises(DomainValidationIntegrationError):
            resolve_domain_operation_validation_requirements(
                definition, impact="full", changed_files=("main.py",)
            )
