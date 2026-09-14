"""Phase 10.36 — AT-DP-036 connected acceptance test.

Proves the Domain API facade end-to-end through real canonical components:

discover -> validate -> install -> prove installed != enabled -> list/get ->
explicit enable -> inspect capabilities/resources/rules/operations/workflows ->
canonical resolution -> canonical operation orchestration -> canonical
workflow execution -> shared-session persistence/load -> session resume with
current-state revalidation -> pure conflict resolution -> reference-only trace
assembly -> canonical trace validation -> explicit disable.

Mocks may observe boundaries but never replace the behavior being accepted.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.domains import (
    DefaultDomainOperationOrchestrator,
    DomainOperationDefinition,
    DomainOperationExecutionDelegate,
    DomainOperationRequest,
    DomainOperationStatus,
    DomainOperationType,
    InMemoryDomainOperationRegistry,
)
from cmm.domains.api import DefaultDomainAPI, DomainAPI
from cmm.domains.conflict_resolution import DomainConflictResolver
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReference,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
)
from cmm.domains.discovery import FileSystemDomainDiscovery
from cmm.domains.discovery_contracts import DomainSource
from cmm.domains.enums import DomainLoadStatus, DomainSourceKind, DomainStatus
from cmm.domains.identifiers import DomainId
from cmm.domains.loader import DeclarativeDomainLoader
from cmm.domains.manifest_reader import JsonDomainManifestReader
from cmm.domains.pack import DomainPack, ParsedDomainPack
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.session_contracts import (
    DomainSessionContext,
    DomainSessionResumeRequest,
)
from cmm.domains.session_persistence import SharedSessionDomainAdapter
from cmm.domains.session_resumer import DomainSessionResumer
from cmm.domains.trace_assembler import DomainTraceAssembler
from cmm.domains.trace_contracts import (
    DomainResultTraceReference,
    DomainTraceAssemblyRequest,
    DomainTraceContribution,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceRole,
)
from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator
from cmm.domains.validation import PipelineDomainValidator
from cmm.domains.validation_contracts import DomainValidationRequest
from cmm.domains.workflow_contracts import (
    DomainWorkflowContext,
    DomainWorkflowDefinition,
    DomainWorkflowResult,
)
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.runtime.sessions import InMemorySessionStore
from cmm.workflows.contracts import WorkflowNode
from tests.domains._loader_helpers import make_candidate, write_domain_dir

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


class CountingSummaryImplementation:
    """Real operation implementation counting invocations at the boundary."""

    def __init__(self, definition: DomainOperationDefinition) -> None:
        self.definition = definition
        self.calls = 0

    def execute(self, request: AgentOperationRequest) -> dict[str, object]:
        self.calls += 1
        return {
            "success": True,
            "output": {"summary": request.parameters["text"].upper()},
        }


def _build_api(tmp_path):
    """Build one canonical runtime state shared across the whole acceptance."""
    # 1. Canonical registry (single instance for lifecycle/query/session).
    registry = DomainRegistry()

    # 2. Canonical discovery + loader + validator.
    discovery = FileSystemDomainDiscovery()
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )
    validator = PipelineDomainValidator()

    # 3. Canonical operation stack (real orchestrator, real delegate).
    operation_definition = DomainOperationDefinition(
        operation_id="greeter.prepare_structured_summary",
        domain_id="domain:greeter",
        version="1.0.0",
        name="Prepare summary",
        description="Prepare safe structure",
        operation_type=DomainOperationType.PREPARATION,
        reversible=False,
        input_schema={
            "type": "object",
            "required": ["text"],
            "properties": {"text": {"type": "string"}},
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
            "additionalProperties": False,
        },
    )
    common = InMemoryAgentOperationRegistry()
    operation_registry = InMemoryDomainOperationRegistry(common)
    implementation = CountingSummaryImplementation(operation_definition)
    operation_registry.register(operation_definition, implementation)
    adapter = AgentExecutionAdapter(
        registry=common,
        execution_delegate=DomainOperationExecutionDelegate(operation_registry),
    )
    orchestrator = DefaultDomainOperationOrchestrator(
        operation_registry, adapter, id_factory=lambda: "domain-result:fixed"
    )

    # 4. Canonical workflow registry + executor.
    workflow_definition = DomainWorkflowDefinition(
        workflow_id="greeter.flow",
        domain_id="domain:greeter",
        version="1.0.0",
        name="Greeter flow",
        nodes=(WorkflowNode("n", "complete", "N"),),
    )
    workflow_registry = InMemoryDomainWorkflowRegistry()
    workflow_registry.register(workflow_definition)
    workflow_executor = DomainWorkflowExecutor(id_factory=lambda: "wf-run:fixed")

    # 5. Canonical shared-session persistence + resumer.
    store = InMemorySessionStore()
    session_adapter = SharedSessionDomainAdapter(store=store)
    session_resumer = DomainSessionResumer(
        registry=registry,
        permission_evaluator=lambda a, p: tuple(p),
        operation_filter=lambda p, o: tuple(o),
        shared_session_adapter=session_adapter,
    )

    # 6. Canonical conflict + trace collaborators.
    conflict_resolver = DomainConflictResolver()
    trace_assembler = DomainTraceAssembler()
    trace_validator = DefaultDomainTraceReferenceValidator()

    api = DefaultDomainAPI(
        domain_registry=registry,
        discovery=discovery,
        validator=validator,
        loader=loader,
        resolver=DefaultDomainResolver(
            clock=lambda: NOW, id_factory=lambda: "res:fixed"
        ),
        operation_orchestrator=orchestrator,
        workflow_registry=workflow_registry,
        workflow_executor=workflow_executor,
        session_adapter=session_adapter,
        session_resumer=session_resumer,
        conflict_resolver=conflict_resolver,
        trace_assembler=trace_assembler,
        trace_validator=trace_validator,
        trust_policy_lookup=_trust_policy_lookup,
    )
    return api, registry, implementation, session_adapter


def _trust_policy_lookup(domain_id: str):
    """Phase 10.38: explicit trust policy for the acceptance's external pack."""
    from cmm.domains.enums import DomainTrustLevel
    from cmm.domains.trust_contracts import DomainTrustPolicy

    if domain_id == "domain:greeter":
        return DomainTrustPolicy(
            domain_id=domain_id,
            trust_level=DomainTrustLevel.TRUSTED,
            authorized_source_ids=("at-dp-036-source", "s1"),
            allow_code_execution=True,
        )
    return None


def _source(root) -> DomainSource:
    return DomainSource(
        source_id="at-dp-036-source",
        kind=DomainSourceKind.DIRECTORY,
        location=str(root),
        trusted=True,
        recursive=False,
    )


def _trace_request() -> DomainTraceAssemblyRequest:
    primary = DomainTraceContribution(
        domain_id="domain:greeter",
        role=DomainTraceRole.PRIMARY,
        references=(
            DomainTraceReference(
                ref_id="result:1",
                kind=DomainTraceReferenceKind.DOMAIN_RESULT,
                domain_id="domain:greeter",
            ),
        ),
    )
    return DomainTraceAssemblyRequest(
        request_id="request:1",
        goal_id="goal:1",
        primary_domain="domain:greeter",
        supporting_domains=(),
        contributions=(primary,),
        references=DomainTraceReferences(
            resolution_context_id="resolution-context:1",
            resolution_result_id="resolution-result:1",
            composition_id="composition:1",
        ),
        domain_results=(DomainResultTraceReference("result:1", "domain:greeter"),),
        started_at=NOW,
        completed_at=datetime(2026, 8, 31, 12, 0, 1, tzinfo=timezone.utc),
        metadata={"category": "at-dp-036"},
    )


def test_at_dp036_connected_acceptance(tmp_path) -> None:
    api, registry, implementation, session_adapter = _build_api(tmp_path)
    assert isinstance(api, DomainAPI)

    # 1. discover valid test Domain Pack (non-registering).
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    manifest_path = domain_dir / "manifest.json"
    manifest_doc = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(
        manifest_doc.replace(
            '"license": "MIT"}',
            '"license": "MIT",'
            ' "capabilities": [{"name": "greeter.capability",'
            ' "kind": "core", "provided_by": "domain:greeter",'
            ' "version": "1.0.0"}]}',
        ),
        encoding="utf-8",
    )
    discovery_result = api.discover_domains((_source(tmp_path),))
    assert [c.domain_id for c in discovery_result.candidates] == ["domain:greeter"]
    assert registry.contains("greeter") is False

    # 2. validate candidate (non-registering, non-installing).
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    manifest_doc = JsonDomainManifestReader().read_document(
        domain_dir / "manifest.json"
    )
    parsed = ParsedDomainPack.from_declarative_dict(manifest_doc.data)
    pack = DomainPack(
        definition=parsed.definition,
        manifest=parsed.manifest,
        root_path=str(domain_dir),
    )
    validation_result = api.validate_domain(
        DomainValidationRequest(
            pack=pack,
            root_path=str(domain_dir),
            candidate=candidate,
            strict=False,
            run_tests=False,
        )
    )
    assert validation_result.domain_id == "domain:greeter"
    assert registry.contains("greeter") is False

    # 3. install via DeclarativeDomainLoader (canonical runtime load).
    load_result = api.install_domain(candidate)
    assert load_result.status == DomainLoadStatus.LOADED
    assert registry.get("greeter", "1.0.0") is not None

    # 4. prove installed != enabled.
    record = registry.get_record("greeter", "1.0.0")
    assert record.status == DomainStatus.REGISTERED
    assert record.definition.enabled is False

    # 5. list/get through API.
    slugs = [d.id.slug for d in api.list_domains()]
    assert "greeter" in slugs
    assert api.get_domain("greeter") is registry.get("greeter")

    # 6. explicitly enable.
    enabled = api.enable_domain("greeter")
    assert enabled.enabled is True
    assert registry.get_record("greeter").status == DomainStatus.ACTIVE

    # 7-11. inspect capabilities/resources/rules/operations/workflows.
    assert [c.name for c in api.get_capabilities("greeter")] == ["greeter.capability"]
    assert api.get_resources("greeter") == registry.list_resources("greeter")
    assert api.get_rules("greeter") == registry.list_rules("greeter")
    assert api.get_operations("greeter") == registry.list_operations("greeter")
    assert api.get_workflows("greeter") == registry.list_workflows("greeter")

    # 12. resolve through canonical resolver.
    resolution = api.resolve_domain(
        DomainResolutionContext(
            id="ctx-at",
            objective="acceptance",
            explicit_domains=(DomainId(slug="greeter"),),
            available_domains=(DomainId(slug="greeter"),),
            authorized_domains=(DomainId(slug="greeter"),),
            active_domains=(DomainId(slug="greeter"),),
            created_at=NOW,
        )
    )
    assert resolution.id == "res:fixed"
    assert resolution.primary_domain == DomainId(slug="greeter")

    # 13. execute operation through canonical orchestration.
    operation_result = api.execute_operation(
        DomainOperationRequest(
            request_id="request:op",
            operation_id="greeter.prepare_structured_summary",
            operation_version="1.0.0",
            inputs={"text": "hello"},
            agent_run_id="run:1",
            task_id="task:1",
            primary_domain_id="domain:greeter",
            idempotency_key="idem:at",
            capabilities=("execute",),
        )
    )
    assert operation_result.status is DomainOperationStatus.COMPLETED
    assert operation_result.output == {"summary": "HELLO"}
    assert implementation.calls == 1

    # 14. start workflow through registry + executor.
    workflow_result = api.start_workflow(
        "greeter.flow", DomainWorkflowContext("domain:greeter"), {}
    )
    assert isinstance(workflow_result, DomainWorkflowResult)
    assert workflow_result.domain_id == "domain:greeter"
    assert workflow_result.run_id == "wf-run:fixed"

    # 15. persist and get DomainSessionContext through shared adapter.
    session_context = DomainSessionContext(
        session_id="sess-at-dp-036",
        primary_domain="domain:greeter",
        domain_versions={"domain:greeter": "1.0.0"},
        revision=1,
        updated_at=NOW,
    )
    session_adapter.save_domain_session(session_context)
    loaded = api.get_session("sess-at-dp-036")
    assert loaded is not None
    assert loaded.primary_domain == "domain:greeter"

    # 16. resume through DomainSessionResumer (current-state revalidation).
    resume_result = api.resume_session(
        DomainSessionResumeRequest(session_id="sess-at-dp-036", actor="user:chris")
    )
    assert resume_result.status.value == "RESUMED"
    assert resume_result.recorded_resumption is True

    # 17. resolve DomainConflictCase through pure resolver.
    case = DomainConflictCase(
        id="case-at",
        domains=(DomainId(slug="greeter"),),
        kind=DomainConflictKind.EVIDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(
            DomainConflictReference(
                source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
                source_id="ref-at",
                domain_id=DomainId(slug="greeter"),
                blocking=False,
                severity=DomainConflictSeverity.MATERIAL,
                authority_kind=DomainConflictAuthority.PRIMARY_DOMAIN,
            ),
        ),
    )
    case_before = case.to_dict()
    conflict_resolution = api.resolve_conflict(case)
    assert conflict_resolution == DomainConflictResolver().resolve(case)
    assert case.to_dict() == case_before

    # 18. assemble reference-only DomainTrace.
    trace = api.assemble_trace(_trace_request())
    assert trace == DomainTraceAssembler().assemble(_trace_request())
    assert trace.id.startswith("domain-trace:")

    # 19. validate trace with canonical reference inventory.
    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        domain_results=trace.domain_results,
        expected_primary_domain="domain:greeter",
        expected_supporting_domains=(),
        resolution_result_domains=DomainTraceDomainSelection(
            "resolution-result:1", "domain:greeter", ()
        ),
        composition_domains=DomainTraceDomainSelection(
            "composition:1", "domain:greeter", ()
        ),
    )
    validation = api.validate_trace(trace, inventory)
    assert validation.valid is True

    # 20. explicitly disable.
    disabled = api.disable_domain("greeter")
    assert disabled.enabled is False
    assert registry.get_record("greeter").status == DomainStatus.DISABLED


def test_at_dp036_structural_anti_fragmentation(tmp_path) -> None:
    """The facade must own no parallel infrastructure."""
    api, _, _, _ = _build_api(tmp_path)

    # No owned registry/loader/resolver/executor created by the facade.
    assert isinstance(api._domain_registry, DomainRegistry)
    assert isinstance(api._loader, DeclarativeDomainLoader)
    assert isinstance(api._resolver, DefaultDomainResolver)
    assert isinstance(api._workflow_executor, DomainWorkflowExecutor)

    # No session store, trace store, cache, or event bus owned by the facade.
    for forbidden in (
        "_session_store",
        "_trace_store",
        "_trace_cache",
        "_trace_repository",
        "_event_bus",
        "_cache",
        "_traces",
    ):
        assert not hasattr(api, forbidden)

    # No invented surface.
    for forbidden in (
        "list_all_domain_sessions",
        "search_domain_sessions",
        "get_trace",
        "get_trace_by_id",
        "list_traces",
        "uninstall_domain",
        "publish_domain",
        "install_package_archive",
        "grant_domain_permission",
    ):
        assert not hasattr(type(api), forbidden)
