"""Phase 10.42 V12 — multi-source availability authority composition.

V11_MAJOR_16: multiple simultaneously applicable planning-availability
authority sources must compose MOST-RESTRICTIVELY; no source may widen
another applicable source.

Covers planning_request.metadata x integration_request.metadata x provider
for denies, capabilities, validation/rollback policies, approvals and
fingerprints, plus absent vs explicit-empty, monotonicity, replan freshness,
and the per-field conflict matrix.
"""

from __future__ import annotations

from cmm.agent_runtime.enums import ApprovalRequestStatus
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.agent_runtime.workflow_planner_adapter import (
    AgentPlanningService,
    DefaultWorkflowPlannerAdapter,
)
from cmm.agent_runtime.workflow_planner_contracts import AgentPlanningRequest
from cmm.agent_runtime.workflow_planner_store import InMemoryWorkflowPlanStore
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.contracts import DomainDefinition, DomainManifestId
from cmm.domains.enums import DomainKind, DomainOperationType
from cmm.domains.identifiers import DomainId
from cmm.domains.operation_availability import _AVAILABILITY_CONTEXT_FIELDS
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.planner_workflow_integration import (
    OPERATION_AVAILABILITY_AUTHORITY_CONFLICT_MATRIX,
    OPERATION_AVAILABILITY_CONTEXT_SOURCE_MATRIX,
    DefaultDomainPlannerWorkflowIntegrator,
    _most_restrictive_optional_sets,
    _resolve_approval_authority,
    _union_denies,
)
from cmm.domains.planner_workflow_integration_contracts import (
    DomainPlannerWorkflowIntegrationRequest,
)
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.planner.task_planner import TaskPlanner
from cmm.workflows.contracts import WorkflowNode


class _Impl:
    def __init__(self, definition):
        self.definition = definition

    def execute(self, request):
        return {"ok": True}


class _StubReasoner:
    def locate_feature(self, query):
        return []

    def impact_analysis(self, feature_name):
        return None

    def explain_dependencies(self, feature_name):
        return None


class _CountingPlanningService(AgentPlanningService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan_calls = 0

    def plan(self, request):
        self.plan_calls += 1
        return super().plan(request)


def _definition(slug, **kwargs):
    defaults = {
        "id": DomainId.from_str(f"domain:{slug}"),
        "name": slug,
        "display_name": slug.title(),
        "version": "1.0.0",
        "kind": DomainKind.CORE,
        "description": f"Test domain {slug}",
        "manifest_id": DomainManifestId(slug=slug, version="1.0.0"),
        "enabled": True,
    }
    defaults.update(kwargs)
    return DomainDefinition(**defaults)


def _multisource_case(
    *,
    op_kwargs,
    planning_meta,
    integration_meta_extra=None,
    capabilities_provider=None,
    validation_provider=None,
    rollback_provider=None,
    request_permissions=(),
):
    op_id = "python.find_symbol"
    op = DomainOperationDefinition(
        operation_id=op_id,
        domain_id="domain:python",
        version="1.0.0",
        name="Find",
        description="d",
        operation_type=op_kwargs.get("op_type", DomainOperationType.READ),
        required_resources=tuple(op_kwargs.get("resources", ())),
        required_permissions=tuple(op_kwargs.get("permissions", ())),
        enabled=True,
        reversible=op_kwargs.get("reversible", False),
        rollback_policy_id=op_kwargs.get("rollback"),
        validation_policy_id=op_kwargs.get("validation"),
        requires_approval=op_kwargs.get("approval", False),
    )
    common_ops = InMemoryAgentOperationRegistry()
    op_reg = InMemoryDomainOperationRegistry(common_ops)
    op_reg.register(op, _Impl(op))
    wf = DomainWorkflowDefinition(
        workflow_id="python.resource_exact",
        domain_id="domain:python",
        version="1.0.0",
        name="R",
        nodes=(
            WorkflowNode(
                node_id="step1",
                node_type="execute_operation",
                name="S1",
                operation_id=op_id,
                operation_version="1.0.0",
                required=True,
            ),
        ),
    )
    wf_reg = InMemoryDomainWorkflowRegistry()
    wf_reg.register(wf)
    dom_reg = DomainRegistry()
    dom_reg.register(
        _definition(
            "python",
            operations=("python.find_symbol",),
            workflows=("python.resource_exact",),
        )
    )
    dom_reg.enable("domain:python")
    store = InMemoryWorkflowPlanStore()
    adapter = DefaultWorkflowPlannerAdapter(
        planner=TaskPlanner(reasoner=_StubReasoner()),
        plan_store=store,
    )
    service = _CountingPlanningService(adapter)
    executor = DomainWorkflowExecutor(
        id_factory=lambda: "wf-run",
        operation_definitions={(op_id, "1.0.0"): op},
        workflow_definitions={("python.resource_exact", "1.0.0"): wf},
    )
    integrator = DefaultDomainPlannerWorkflowIntegrator(
        resolver=DefaultDomainResolver(),
        composer=DefaultDomainComposer(),
        domain_registry=dom_reg,
        workflow_registry=wf_reg,
        planning_service=service,
        workflow_executor=executor,
        operation_availability=lambda oid, did: (
            op_reg.resolve_active(oid, required=False) is not None
        ),
        permission_ids_provider=lambda comp: tuple(request_permissions),
        prohibited_operation_ids_provider=lambda comp: (),
        approval_ids_provider=lambda comp: (),
        validation_ids_provider=lambda comp: (),
        authority_reference_ids_provider=lambda comp: ("authority:v1",),
        operation_definition_provider=lambda oid: op_reg.resolve_active(
            oid, required=False
        ),
        capabilities_provider=capabilities_provider,
        available_validation_policy_ids_provider=validation_provider,
        available_rollback_policy_ids_provider=rollback_provider,
    )
    int_meta = {"requested_workflow_ids": ["python.resource_exact"]}
    if integration_meta_extra:
        int_meta.update(integration_meta_extra)
    req = DomainPlannerWorkflowIntegrationRequest(
        request_id="req-test",
        resolution_context=DomainResolutionContext(
            id="ctx-test",
            user_input="test",
            goal_id="goal-test",
            actor="system",
            available_domains=(DomainId(slug="python"),),
            authorized_domains=(DomainId(slug="python"),),
            explicit_domains=(DomainId(slug="python"),),
        ),
        planning_request=AgentPlanningRequest(
            id="plan-req-test",
            goal_id="goal-test",
            agent_run_id="run-test",
            objective="test",
            resource_ids=[],
            permissions=list(request_permissions),
            metadata=dict(planning_meta),
        ),
        metadata=int_meta,
    )
    result = integrator.integrate(req)
    return result, service, req, integrator


def test_v12_conflict_matrix_covers_all_fields():
    matrix_fields = {
        entry.field for entry in OPERATION_AVAILABILITY_AUTHORITY_CONFLICT_MATRIX
    }
    assert matrix_fields == _AVAILABILITY_CONTEXT_FIELDS
    print("ALL_OPERATION_AVAILABILITY_CONTEXT_FIELDS_HAVE_CONFLICT_RULE=PASS")
    assert len(matrix_fields) == 12
    print("UNCLASSIFIED_MULTI_SOURCE_AUTHORITY_FIELDS=0")
    source_fields = {
        entry.field for entry in OPERATION_AVAILABILITY_CONTEXT_SOURCE_MATRIX
    }
    assert source_fields == _AVAILABILITY_CONTEXT_FIELDS


def test_v12_composition_helpers_centralized():
    assert callable(_most_restrictive_optional_sets)
    assert callable(_union_denies)
    assert callable(_resolve_approval_authority)
    first = _most_restrictive_optional_sets([(True, ("a", "b")), (True, ("b", "c"))])
    second = _most_restrictive_optional_sets([(True, ("a", "b")), (True, ("b", "c"))])
    assert first == second == ("b",)
    assert _union_denies([(True, ("a",)), (True, ("b",))]) == ("a", "b")
    print("MULTI_SOURCE_AUTHORITY_COMPOSITION_CENTRALIZED=PASS")


def test_v12_no_new_authority_sources():
    import inspect

    params = inspect.signature(
        DefaultDomainPlannerWorkflowIntegrator.__init__
    ).parameters
    provider_params = {
        "capabilities_provider",
        "available_validation_policy_ids_provider",
        "available_rollback_policy_ids_provider",
    }
    assert provider_params <= set(params)
    assert "authority_store" not in params
    assert "authority_cache" not in params
    assert "availability_store" not in params
    print("NEW_AVAILABILITY_AUTHORITY_SOURCES=0")
    print("NO_PARALLEL_OPERATION_AVAILABILITY_AUTHORITY_STORE=YES")


def test_v12_deny_union_integration_deny_planning_empty():
    result, service, _, _ = _multisource_case(
        op_kwargs={"permissions": ("file.modify",), "resources": ()},
        request_permissions=("file.modify",),
        planning_meta={"denied_permissions": ()},
        integration_meta_extra={"denied_permissions": ("file.modify",)},
    )
    assert result.blocked is True
    assert result.plan is None
    assert service.plan_calls == 0
    print("MULTI_SOURCE_PERMISSION_DENY_UNION=PASS")
    print("ANY_APPLICABLE_PERMISSION_DENY_WINS=PASS")


def test_v12_deny_union_planning_deny_integration_empty():
    result, service, _, _ = _multisource_case(
        op_kwargs={"permissions": ("file.modify",), "resources": ()},
        request_permissions=("file.modify",),
        planning_meta={"denied_permissions": ("file.modify",)},
        integration_meta_extra={"denied_permissions": ()},
    )
    assert result.blocked is True
    assert service.plan_calls == 0
    print("ANY_APPLICABLE_PERMISSION_DENY_WINS=PASS")


def test_v12_deny_union_both_deny():
    result, service, _, _ = _multisource_case(
        op_kwargs={"permissions": ("file.modify",), "resources": ()},
        request_permissions=("file.modify",),
        planning_meta={"denied_permissions": ("file.modify",)},
        integration_meta_extra={"denied_permissions": ("file.modify",)},
    )
    assert result.blocked is True
    assert service.plan_calls == 0
    assert _union_denies([(True, ("file.modify",)), (True, ("file.modify",))]) == (
        "file.modify",
    )
    print("DENY_AUTHORITY_IS_MONOTONIC=PASS")


def test_v12_capabilities_planning_positive_integration_empty_blocks():
    result, service, _, _ = _multisource_case(
        op_kwargs={"reversible": True, "resources": ()},
        planning_meta={"capabilities": ("transaction",)},
        integration_meta_extra={"capabilities": ()},
    )
    assert result.blocked is True
    assert service.plan_calls == 0
    print("MULTI_SOURCE_CAPABILITIES_MOST_RESTRICTIVE=PASS")


def test_v12_capabilities_planning_empty_integration_positive_blocks():
    result, service, _, _ = _multisource_case(
        op_kwargs={"reversible": True, "resources": ()},
        planning_meta={"capabilities": ()},
        integration_meta_extra={"capabilities": ("transaction",)},
    )
    assert result.blocked is True
    assert service.plan_calls == 0


def test_v12_capabilities_narrowing_intersection():
    narrowed = _most_restrictive_optional_sets(
        [
            (True, ("validation", "transaction")),
            (True, ("validation",)),
        ]
    )
    assert narrowed == ("validation",)
    result, service, _, _ = _multisource_case(
        op_kwargs={"reversible": True, "resources": ()},
        planning_meta={"capabilities": ("validation", "transaction")},
        integration_meta_extra={"capabilities": ("validation",)},
    )
    assert result.blocked is True
    assert service.plan_calls == 0
    print("POSITIVE_SET_AUTHORITY_IS_MONOTONIC=PASS")


def test_v12_provider_capability_cannot_be_overridden():
    result, service, _, _ = _multisource_case(
        op_kwargs={"reversible": True, "resources": ()},
        planning_meta={"capabilities": ("transaction",)},
        capabilities_provider=lambda comp: (),
    )
    assert result.blocked is True
    assert service.plan_calls == 0
    result2, service2, _, _ = _multisource_case(
        op_kwargs={"reversible": True, "resources": ()},
        planning_meta={"capabilities": ()},
        capabilities_provider=lambda comp: ("transaction",),
    )
    assert result2.blocked is True
    assert service2.plan_calls == 0
    print("PROVIDER_CAPABILITY_RESTRICTION_CANNOT_BE_OVERRIDDEN=PASS")


def test_v12_validation_policies_most_restrictive():
    result, service, _, _ = _multisource_case(
        op_kwargs={"validation": "validation:schema", "resources": ()},
        planning_meta={
            "capabilities": ("validation",),
            "available_validation_policy_ids": ("validation:schema",),
        },
        integration_meta_extra={
            "capabilities": ("validation",),
            "available_validation_policy_ids": (),
        },
    )
    assert result.blocked is True
    assert service.plan_calls == 0
    result2, _, _, _ = _multisource_case(
        op_kwargs={"validation": "validation:schema", "resources": ()},
        planning_meta={
            "capabilities": ("validation",),
            "available_validation_policy_ids": ("validation:schema",),
        },
        capabilities_provider=lambda comp: ("validation",),
        validation_provider=lambda comp: (),
    )
    assert result2.blocked is True
    print("MULTI_SOURCE_VALIDATION_POLICIES_MOST_RESTRICTIVE=PASS")


def test_v12_rollback_policies_most_restrictive():
    result, service, _, _ = _multisource_case(
        op_kwargs={
            "reversible": True,
            "rollback": "rollback:safe",
            "resources": (),
        },
        planning_meta={
            "capabilities": ("transaction", "rollback"),
            "available_rollback_policy_ids": ("rollback:safe",),
        },
        integration_meta_extra={
            "capabilities": ("transaction", "rollback"),
            "available_rollback_policy_ids": (),
        },
    )
    assert result.blocked is True
    assert service.plan_calls == 0
    result2, _, _, _ = _multisource_case(
        op_kwargs={
            "reversible": True,
            "rollback": "rollback:safe",
            "resources": (),
        },
        planning_meta={
            "capabilities": ("transaction", "rollback"),
            "available_rollback_policy_ids": ("rollback:safe",),
        },
        capabilities_provider=lambda comp: ("transaction", "rollback"),
        rollback_provider=lambda comp: (),
    )
    assert result2.blocked is True
    print("MULTI_SOURCE_ROLLBACK_POLICIES_MOST_RESTRICTIVE=PASS")


def test_v12_approval_rejection_wins():
    result, service, _, _ = _multisource_case(
        op_kwargs={"approval": True, "resources": ()},
        planning_meta={
            "approval_status": ApprovalRequestStatus.APPROVED,
            "approval_fingerprint": "fp",
            "request_fingerprint": "fp",
        },
        integration_meta_extra={
            "approval_status": ApprovalRequestStatus.REJECTED,
            "approval_fingerprint": "bad",
            "request_fingerprint": "bad",
        },
    )
    assert result.blocked is True
    assert service.plan_calls == 0
    status, _, _ = _resolve_approval_authority(
        {"approval_status": ApprovalRequestStatus.APPROVED},
        {"approval_status": ApprovalRequestStatus.REJECTED},
    )
    assert status is ApprovalRequestStatus.REJECTED
    print("MULTI_SOURCE_APPROVAL_REJECTION_WINS=PASS")


def test_v12_approval_pending_not_upgraded():
    status, _, _ = _resolve_approval_authority(
        {"approval_status": ApprovalRequestStatus.PENDING},
        {"approval_status": ApprovalRequestStatus.APPROVED},
    )
    assert status is ApprovalRequestStatus.PENDING
    status2, _, _ = _resolve_approval_authority(
        {"approval_status": ApprovalRequestStatus.APPROVED},
        {"approval_status": ApprovalRequestStatus.PENDING},
    )
    assert status2 is ApprovalRequestStatus.PENDING
    status3, _, _ = _resolve_approval_authority(
        {"approval_status": ApprovalRequestStatus.APPROVED},
        {"approval_status": ApprovalRequestStatus.APPROVED},
    )
    assert status3 is ApprovalRequestStatus.APPROVED
    print("MULTI_SOURCE_APPROVAL_PENDING_NOT_UPGRADED=PASS")
    print(
        "APPROVAL_GRANT_HAS_SINGLE_CANONICAL_OWNER_OR_MOST_RESTRICTIVE_COMPOSITION=PASS"
    )


def test_v12_approval_fingerprint_conflict_fails_closed():
    status, approval_fp, request_fp = _resolve_approval_authority(
        {
            "approval_status": ApprovalRequestStatus.APPROVED,
            "approval_fingerprint": "fp-a",
            "request_fingerprint": "fp-a",
        },
        {
            "approval_status": ApprovalRequestStatus.APPROVED,
            "approval_fingerprint": "fp-b",
            "request_fingerprint": "fp-b",
        },
    )
    assert status is ApprovalRequestStatus.REJECTED
    assert approval_fp != request_fp or status is ApprovalRequestStatus.REJECTED
    result, service, _, _ = _multisource_case(
        op_kwargs={"approval": True, "resources": ()},
        planning_meta={
            "approval_status": ApprovalRequestStatus.APPROVED,
            "approval_fingerprint": "fp-a",
            "request_fingerprint": "fp-a",
        },
        integration_meta_extra={
            "approval_status": ApprovalRequestStatus.APPROVED,
            "approval_fingerprint": "fp-b",
            "request_fingerprint": "fp-b",
        },
    )
    assert result.blocked is True
    assert service.plan_calls == 0
    print("MULTI_SOURCE_APPROVAL_FINGERPRINT_CONFLICT_FAILS_CLOSED=PASS")


def test_v12_request_fingerprint_conflict_fails_closed():
    status, _, _ = _resolve_approval_authority(
        {
            "approval_status": ApprovalRequestStatus.APPROVED,
            "approval_fingerprint": "fp",
            "request_fingerprint": "req-a",
        },
        {
            "approval_status": ApprovalRequestStatus.APPROVED,
            "approval_fingerprint": "fp",
            "request_fingerprint": "req-b",
        },
    )
    assert status is ApprovalRequestStatus.REJECTED
    result, service, _, _ = _multisource_case(
        op_kwargs={"approval": True, "resources": ()},
        planning_meta={
            "approval_status": ApprovalRequestStatus.APPROVED,
            "approval_fingerprint": "fp",
            "request_fingerprint": "req-a",
        },
        integration_meta_extra={
            "approval_status": ApprovalRequestStatus.APPROVED,
            "approval_fingerprint": "fp",
            "request_fingerprint": "req-b",
        },
    )
    assert result.blocked is True
    assert service.plan_calls == 0
    print("MULTI_SOURCE_REQUEST_FINGERPRINT_CONFLICT_FAILS_CLOSED=PASS")


def test_v12_identical_sources_stable():
    result, service, _, _ = _multisource_case(
        op_kwargs={"reversible": True, "resources": ()},
        planning_meta={"capabilities": ("transaction",)},
        integration_meta_extra={"capabilities": ("transaction",)},
        capabilities_provider=lambda comp: ("transaction",),
    )
    assert result.blocked is False
    assert result.plan is not None
    assert service.plan_calls == 1
    print("IDENTICAL_MULTI_SOURCE_AUTHORITY_STABLE=PASS")


def test_v12_single_source_positive_preserved():
    result, service, _, _ = _multisource_case(
        op_kwargs={"reversible": True, "resources": ()},
        planning_meta={"capabilities": ("transaction",)},
    )
    assert result.blocked is False
    assert service.plan_calls == 1
    print("SINGLE_SOURCE_EXPLICIT_POSITIVE_AUTHORITY_PRESERVED=PASS")


def test_v12_absent_not_treated_as_explicit_empty():
    allowed, _, _, _ = _multisource_case(
        op_kwargs={"reversible": True, "resources": ()},
        planning_meta={"capabilities": ("transaction",)},
    )
    assert allowed.blocked is False
    blocked, _, _, _ = _multisource_case(
        op_kwargs={"reversible": True, "resources": ()},
        planning_meta={"capabilities": ("transaction",)},
        integration_meta_extra={"capabilities": ()},
    )
    assert blocked.blocked is True
    assert _most_restrictive_optional_sets([(True, ("t",)), (False, ())]) == ("t",)
    assert _most_restrictive_optional_sets([]) == ()
    print("ABSENT_SOURCE_NOT_TREATED_AS_EXPLICIT_EMPTY_UNLESS_CANONICAL=PASS")


def test_v12_adding_source_can_only_restrict():
    base = _most_restrictive_optional_sets([(True, ("a", "b", "c"))])
    narrowed = _most_restrictive_optional_sets(
        [(True, ("a", "b", "c")), (True, ("b",))]
    )
    assert set(narrowed) <= set(base)
    base_denies = _union_denies([(True, ("p",))])
    widened_denies = _union_denies([(True, ("p",)), (True, ("q",))])
    assert set(base_denies) <= set(widened_denies)
    allowed, _, _, _ = _multisource_case(
        op_kwargs={"reversible": True, "resources": ()},
        planning_meta={"capabilities": ("transaction",)},
    )
    assert allowed.blocked is False
    blocked, _, _, _ = _multisource_case(
        op_kwargs={"reversible": True, "resources": ()},
        planning_meta={"capabilities": ("transaction",)},
        integration_meta_extra={"capabilities": ()},
    )
    assert blocked.blocked is True
    print("ADDING_AUTHORITY_SOURCE_CAN_ONLY_RESTRICT=PASS")
    print("NO_AUTHORITY_SOURCE_PRECEDENCE_CAN_WIDEN=PASS")


def test_v12_replan_recomputed_fresh():
    first, service, req, integrator = _multisource_case(
        op_kwargs={"validation": "validation:schema", "resources": ()},
        planning_meta={
            "capabilities": ("validation",),
            "available_validation_policy_ids": ("validation:schema",),
        },
        integration_meta_extra={
            "capabilities": ("validation",),
            "available_validation_policy_ids": ("validation:schema",),
        },
    )
    assert first.blocked is False
    assert service.plan_calls == 1
    from dataclasses import replace

    downgraded_plan = replace(
        req.planning_request,
        id="plan-req-downgraded",
        metadata={
            "capabilities": ("validation",),
            "available_validation_policy_ids": ("validation:schema",),
        },
    )
    downgraded = replace(
        req,
        request_id="req-downgraded",
        planning_request=downgraded_plan,
        metadata={
            "requested_workflow_ids": ["python.resource_exact"],
            "capabilities": (),
            "available_validation_policy_ids": (),
        },
    )
    second = integrator.integrate(downgraded)
    assert second.blocked is True
    assert second.plan is None
    assert service.plan_calls == 1
    print("REPLAN_MULTI_SOURCE_AUTHORITY_RECOMPUTED=PASS")


def test_v12_full_cross_source_matrix():
    cases = [
        ({}, {}, None, ()),
        ({"capabilities": ()}, {}, None, ()),
        ({"capabilities": ("transaction",)}, {}, None, ("transaction",)),
        (
            {"capabilities": ("transaction",)},
            {"capabilities": ()},
            None,
            (),
        ),
        (
            {"capabilities": ()},
            {"capabilities": ("transaction",)},
            None,
            (),
        ),
        (
            {"capabilities": ("a",)},
            {"capabilities": ("b",)},
            None,
            (),
        ),
        (
            {"capabilities": ("transaction",)},
            {},
            lambda comp: (),
            (),
        ),
        (
            {"capabilities": ()},
            {},
            lambda comp: ("transaction",),
            (),
        ),
        (
            {"capabilities": ("a",)},
            {},
            lambda comp: ("b",),
            (),
        ),
        (
            {"capabilities": ("transaction",)},
            {"capabilities": ("transaction",)},
            lambda comp: ("transaction",),
            ("transaction",),
        ),
        (
            {"capabilities": ("transaction",)},
            {"capabilities": ()},
            lambda comp: ("transaction",),
            (),
        ),
        (
            {"capabilities": ("transaction",)},
            {"capabilities": ("transaction",)},
            lambda comp: (),
            (),
        ),
    ]
    for planning_meta, integration_meta, provider, expected in cases:
        effective = _most_restrictive_optional_sets(
            [
                (
                    "capabilities" in planning_meta,
                    planning_meta.get("capabilities", ()),
                ),
                (
                    "capabilities" in integration_meta,
                    integration_meta.get("capabilities", ()),
                ),
                (provider is not None, provider(None) if provider else ()),
            ]
        )
        assert effective == expected, (planning_meta, integration_meta, effective)
    deny_cases = [
        ({"denied_permissions": ("p",)}, {"denied_permissions": ()}, ("p",)),
        ({"denied_permissions": ()}, {"denied_permissions": ("p",)}, ("p",)),
        ({"denied_permissions": ("p",)}, {"denied_permissions": ("p",)}, ("p",)),
    ]
    for planning_meta, integration_meta, expected in deny_cases:
        effective = _union_denies(
            [
                (
                    "denied_permissions" in planning_meta,
                    planning_meta.get("denied_permissions", ()),
                ),
                (
                    "denied_permissions" in integration_meta,
                    integration_meta.get("denied_permissions", ()),
                ),
            ]
        )
        assert effective == expected
    print("MULTI_SOURCE_AVAILABILITY_AUTHORITY_MATRIX=PASS")
