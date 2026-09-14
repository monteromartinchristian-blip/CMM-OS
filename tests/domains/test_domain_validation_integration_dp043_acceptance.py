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

        orchestrator, request, _ = _affected_test_stack(
            tmp_path, break_test=False, validation_changed_files=()
        )
        assert orchestrator.execute(request).status is DomainOperationStatus.COMPLETED

        breaking_orch, breaking_request, _ = _affected_test_stack(
            tmp_path, break_test=True, validation_changed_files=()
        )
        breaking = breaking_orch.execute(breaking_request)
        assert breaking.status is not DomainOperationStatus.COMPLETED

        # Verify affected_tests step status is FAILED in failure evidence and caused rejection
        val_repo = breaking_orch._execution_adapter._validation_adapter._repository
        post_results = val_repo.get_results_by_operation_request_id(
            breaking_request.request_id
        )
        assert len(post_results) >= 2
        post_val = post_results[-1]
        assert post_val.status.value == "failed"
        report = post_val.validation_report or {}
        step_statuses = {
            s.get("name"): s.get("status") for s in report.get("steps", [])
        }
        assert step_statuses.get("affected_tests") == "failed"

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
        fixed_orch, fixed_request, _ = _affected_test_stack(
            tmp_path, break_test=False, validation_changed_files=(), suffix="repair"
        )
        assert (
            fixed_orch.execute(fixed_request).status is DomainOperationStatus.COMPLETED
        )

    def test_project_impact_escalation_via_real_runtime(self, tmp_path) -> None:
        # V5 canonical path: a structural/public mutation is classified by
        # the real Phase 7 ChangeImpactAnalyzer (never Domain heuristics),
        # POST requirements fail closed on unmappable stronger policy steps,
        # and canonical rollback restores the mutated tree.
        from cmm.domains.validation_integration import (
            project_policy_impact_from_canonical_result,
        )
        from cmm.validation.impact import ChangeImpactAnalyzer, ChangeSetBuilder
        from cmm.validation.impact.snapshots import scan_project_snapshot

        # 1. Structural change: function signature change with caller hint "small"
        def structural_mutation(project_dir) -> None:
            (project_dir / "src" / "pkg" / "module.py").write_text(
                "def add(a, b, c=0):\n    return a + b + c\n",
                encoding="utf-8",
            )

        orch_struct, req_struct, struct_dir, _ = _canonical_project_stack(
            tmp_path,
            mutation=structural_mutation,
            suffix="struct",
            validation_impact="small",
        )
        original_struct = (struct_dir / "src" / "pkg" / "module.py").read_text(
            encoding="utf-8"
        )
        res_struct = orch_struct.execute(req_struct)
        assert res_struct.status is DomainOperationStatus.ROLLED_BACK
        assert res_struct.error is not None
        assert res_struct.error.get("code") == "POST_VALIDATION_FAILED"
        # Canonical rollback restored the mutated file content.
        assert (struct_dir / "src" / "pkg" / "module.py").read_text(
            encoding="utf-8"
        ) == original_struct

        # 2. Public API change: adding new exported function with caller hint "small"
        def public_mutation(project_dir) -> None:
            (project_dir / "src" / "pkg" / "module.py").write_text(
                "def add(a, b):\n"
                "    return a + b\n"
                "\n"
                "\n"
                "def multiply(a, b):\n"
                "    return a * b\n",
                encoding="utf-8",
            )

        orch_pub, req_pub, pub_dir, _ = _canonical_project_stack(
            tmp_path,
            mutation=public_mutation,
            suffix="public",
            validation_impact="small",
        )
        original_pub = (pub_dir / "src" / "pkg" / "module.py").read_text(
            encoding="utf-8"
        )
        res_pub = orch_pub.execute(req_pub)
        assert res_pub.status is DomainOperationStatus.ROLLED_BACK
        assert res_pub.error is not None
        assert res_pub.error.get("code") == "POST_VALIDATION_FAILED"
        assert (pub_dir / "src" / "pkg" / "module.py").read_text(
            encoding="utf-8"
        ) == original_pub

        # The canonical analyzer independently escalates both mutation
        # shapes: Phase 10.43 policy follows ChangeImpactResult, never the
        # caller's "small" hint.
        import shutil

        for label, mutate in (
            ("struct", structural_mutation),
            ("public", public_mutation),
        ):
            scratch = tmp_path / f"scratch-{label}"
            if scratch.exists():
                shutil.rmtree(scratch)
            shutil.copytree(
                struct_dir if label == "struct" else pub_dir,
                scratch,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            before = scan_project_snapshot(scratch, source="before")
            mutate(scratch)
            after = scan_project_snapshot(scratch, source="after")
            change_set = ChangeSetBuilder().build_from_snapshots(
                project_root=scratch,
                before=before,
                after=after,
            )
            assert project_policy_impact_from_canonical_result(
                ChangeImpactAnalyzer().analyze(change_set)
            ) in ("structural", "public", "full")


# ── I. V5 canonical Project proof: actual ChangeSet, trusted root, restoration ─


class _TreeResourceVersionProvider:
    """Canonical-storage resource provider snapshotting a whole project tree.

    Test-side storage double (the same established pattern as the
    self-development e2e ``RepoResourceVersionProvider``): capture/verify/
    restore whole-tree bytes so the canonical
    ``CheckpointRestorationRollbackExecutor`` can genuinely restore mutated
    file content through ``CheckpointManager``/``TransactionManager``.
    """

    def __init__(self, repo_path) -> None:
        import hashlib
        from pathlib import Path

        self._hashlib = hashlib
        self._Path = Path
        self.repo_path = Path(repo_path)
        self._snapshots: dict[str, dict] = {}

    def _current_state(self) -> dict:
        files_state = {}
        for path in self.repo_path.rglob("*"):
            if path.is_file() and ".git" not in path.parts:
                files_state[path] = path.read_bytes()
        return files_state

    def capture_version(self, resource_key: str) -> str:
        files_state = self._current_state()
        digest_content = "".join(
            f"{path.relative_to(self.repo_path)}:"
            f"{self._hashlib.sha256(data).hexdigest()};"
            for path, data in sorted(files_state.items(), key=lambda item: str(item[0]))
        )
        digest = self._hashlib.sha256(digest_content.encode("utf-8")).hexdigest()
        self._snapshots[digest] = files_state
        return digest

    def verify_version(self, resource_key: str, expected_version: str) -> bool:
        return self.capture_version(resource_key) == expected_version

    def restore_version(self, resource_key: str, target_version: str) -> bool:
        if target_version not in self._snapshots:
            return False
        snapshot = self._snapshots[target_version]
        current_files = {
            path
            for path in self.repo_path.rglob("*")
            if path.is_file() and ".git" not in path.parts
        }
        for path in current_files - set(snapshot.keys()):
            path.unlink()
        for path, data in snapshot.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return True


def _canonical_project_stack(
    tmp_path,
    *,
    mutation=None,
    suffix: str = "v5",
    hint: str | None = "omit",
    validation_impact: str | None = None,
):
    """Project mutation stack with canonical transaction/rollback ownership.

    Nested src-layout fixture with no top-level ``*.py`` files. The
    host-registered implementation declares ``host_project_root``; caller
    metadata carries only the requested hint (``"omit"`` sends none).
    Rollback uses the canonical ``CheckpointRestorationRollbackExecutor``
    over real ``TransactionManager``/``CheckpointManager``/
    ``CheckpointRestorationManager`` so restoration of file content (not
    just status) is proven. Returns
    ``(orchestrator, request, project_dir, adapter)``.
    """
    import dataclasses
    from datetime import datetime, timezone

    from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
    from cmm.agent_runtime.approval_service import ApprovalService
    from cmm.agent_runtime.checkpoint_manager import CheckpointManager
    from cmm.agent_runtime.checkpoint_repository import InMemoryCheckpointRepository
    from cmm.agent_runtime.checkpoint_restoration import CheckpointRestorationManager
    from cmm.agent_runtime.checkpoint_rollback_executor import (
        CheckpointRestorationRollbackExecutor,
    )
    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
    from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
    from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
    from cmm.agent_runtime.transaction_manager import TransactionManager
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
    from cmm.domains.project.operations import build_project_operation_definitions
    from cmm.domains.project.permissions import build_project_permission_policy
    from cmm.domains.validation_integration import (
        resolve_domain_operation_validation_requirements,
    )

    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    definition = ops["project.modify_code"]

    project_dir = tmp_path / f"canonproj-{suffix}"
    pkg_dir = project_dir / "src" / "pkg"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "src" / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "module.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    tests_dir = project_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "test_module.py").write_text(
        "from src.pkg.module import add\n"
        "\n"
        "\n"
        "def test_add():\n"
        "    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )

    class Implementation:
        def __init__(self) -> None:
            self.definition = definition
            self.host_project_root = str(project_dir)

        def execute(self, request) -> dict:
            if mutation is not None:
                mutation(project_dir)
            return {"success": True, "output": {"status": "ok"}}

    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    registry.register(definition, Implementation())

    perm_registry = DomainPermissionRegistry()
    perm_registry.register(build_project_permission_policy())
    resolver = DomainPermissionResolver(perm_registry)
    service = ApprovalService(InMemoryApprovalRepository())

    metadata: dict = {"actor_id": "actor-1"}
    if hint is not None and hint != "omit":
        metadata["validation_project_root"] = hint

    request = DomainOperationRequest(
        request_id=f"req:canon:{suffix}",
        operation_id="project.modify_code",
        operation_version=definition.version,
        inputs={},
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="task-1",
        session_id="sess-1",
        primary_domain_id=definition.domain_id,
        idempotency_key=f"idem-canon-{suffix}",
        granted_permissions=definition.required_permissions,
        available_resources=definition.required_resources,
        capabilities=("execute", "transaction", "rollback", "validation"),
        metadata=metadata,
        validation_impact=validation_impact,
        validation_changed_files=(),
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

    resource_provider = _TreeResourceVersionProvider(project_dir)
    checkpoint_repo = InMemoryCheckpointRepository()
    checkpoint_manager = CheckpointManager(
        repository=checkpoint_repo, resource_provider=resource_provider
    )
    transaction_manager = TransactionManager(checkpoint_manager)
    restoration_manager = CheckpointRestorationManager(
        repository=checkpoint_repo, resource_provider=resource_provider
    )
    rollback_executor = CheckpointRestorationRollbackExecutor(
        transaction_manager=transaction_manager,
        restoration_manager=restoration_manager,
    )

    validation_adapter = AgentValidationAdapter()
    adapter = AgentExecutionAdapter(
        registry=common,
        execution_delegate=DomainOperationExecutionDelegate(registry),
        validation_adapter=validation_adapter,
    )
    _now = datetime.now(timezone.utc)
    gate = DomainPermissionGate(resolver, service, clock=lambda: _now)
    orchestrator = DefaultDomainOperationOrchestrator(
        registry,
        adapter,
        approval_service=service,
        permission_gate=gate,
        transaction_manager=transaction_manager,
        rollback_executor=rollback_executor,
        operation_validation_provider=(
            resolve_domain_operation_validation_requirements
        ),
    )
    approved_request = dataclasses.replace(
        request,
        approval_request_id=op_exec_approval_id,
        metadata={**metadata, "approval_request_ids": approval_request_ids},
    )
    return orchestrator, approved_request, project_dir, adapter


class TestAcceptanceProjectDomainV5Canonical:
    """V5 Project acceptance: canonical ChangeSet, trusted root, restoration."""

    def test_nested_regression_blocked_and_rolled_back_with_restoration(
        self, tmp_path
    ) -> None:
        def break_mutation(project_dir) -> None:
            (project_dir / "src" / "pkg" / "module.py").write_text(
                "def add(a, b):\n    return a - b\n", encoding="utf-8"
            )

        orchestrator, request, project_dir, adapter = _canonical_project_stack(
            tmp_path, mutation=break_mutation, suffix="nestedbreak"
        )
        original = (project_dir / "src" / "pkg" / "module.py").read_text(
            encoding="utf-8"
        )
        result = orchestrator.execute(request)
        assert result.status is DomainOperationStatus.ROLLED_BACK
        # Canonical restoration: mutated file content is actually restored.
        assert (project_dir / "src" / "pkg" / "module.py").read_text(
            encoding="utf-8"
        ) == original

        # Canonical POST evidence: actual nested changed file fed POST
        # validation and affected_tests is the blocking step.
        repository = adapter.validation_adapter.repository
        post_result = repository.find_by_idempotency_key(
            "post-mutation-idem-canon-nestedbreak"
        )
        assert post_result is not None
        post_request = repository.get_request(post_result.request_id)
        post_scope = tuple(
            scope
            for requirement in post_request.requirements
            for scope in requirement.resource_scope
        )
        assert "src/pkg/module.py" in post_scope
        report = post_result.validation_report or {}
        step_by_name = {step["name"]: step for step in report.get("steps", ())}
        assert step_by_name.get("affected_tests", {}).get("status") == "failed"

        # The restored tree validates clean: a no-op mutation is accepted.
        clean_orch, clean_request, _, _ = _canonical_project_stack(
            tmp_path, mutation=None, suffix="nestedclean"
        )
        assert (
            clean_orch.execute(clean_request).status is DomainOperationStatus.COMPLETED
        )

    def test_post_mutation_derivation_failure_fails_closed(
        self, tmp_path, monkeypatch
    ) -> None:
        import cmm.domains.validation_integration as integration_mod

        class _BoomBuilder:
            def build_from_snapshots(self, **kwargs):
                raise RuntimeError("changeset unavailable")

        monkeypatch.setattr(integration_mod, "ChangeSetBuilder", lambda: _BoomBuilder())
        orchestrator, request, _, _ = _canonical_project_stack(
            tmp_path, mutation=None, suffix="derivefail"
        )
        result = orchestrator.execute(request)
        assert result.status is not DomainOperationStatus.COMPLETED

    def test_caller_decoy_root_cannot_redirect_validation(self, tmp_path) -> None:
        from cmm.domains.validation_integration import (
            DomainValidationIntegrationError,
        )

        decoy = tmp_path / "decoy"
        decoy.mkdir(parents=True, exist_ok=True)
        (decoy / "main.py").write_text("x = 1\n", encoding="utf-8")
        orchestrator, request, _, _ = _canonical_project_stack(
            tmp_path, mutation=None, suffix="decoy", hint=str(decoy)
        )
        with pytest.raises(DomainValidationIntegrationError):
            orchestrator.execute(request)
