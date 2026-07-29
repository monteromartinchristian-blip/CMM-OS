"""Phase 9.8 – Policy Engine Tests.

Tests contracts, enums, repository, versioning, condition evaluation, safe path resolution,
combining algorithms, obligations, restrictions, violations, fail-safe fallbacks,
domain adapters, initial policies, and end-to-end flows.
"""

from __future__ import annotations

import pytest

from cmm.agent_runtime import (
    AgentCognitiveResult,
    AgentWorkflowOperation,
    AgentWorkflowPlan,
    AgentWorkflowPlanValidation,
    DefaultPolicyEvaluator,
    DuplicatePolicyError,
    DuplicatePolicySetError,
    InformationAcquisitionDecision,
    InvalidPolicyContractError,
    Policy,
    PolicyAction,
    PolicyCombiningAlgorithm,
    PolicyCombiningError,
    PolicyCondition,
    PolicyConditionOperator,
    PolicyDecision,
    PolicyEffect,
    PolicyEngine,
    PolicyEnvironment,
    PolicyEvaluationContext,
    PolicyEvaluationRequest,
    PolicyEvaluationResult,
    PolicyEvaluationStatus,
    PolicyFailureMode,
    PolicyNotFoundError,
    PolicyObligationKind,
    PolicyRepository,
    PolicyResource,
    PolicyResourceKind,
    PolicyRiskLevel,
    PolicyRule,
    PolicySet,
    PolicySetNotFoundError,
    PolicySubject,
    PolicySubjectKind,
    PolicyVersionError,
    create_request_from_acquisition_decision,
    create_request_from_cognitive_result,
    create_request_from_workflow_operation,
    create_request_from_workflow_plan,
    evaluate_condition,
    resolve_field_value,
)
from cmm.transformations import OperationRegistry, TransformationOperation


# Helper mock operation for OperationRegistry integration test
class MockTransformationOperation(TransformationOperation):
    """Mock operation for registry testing."""

    @property
    def name(self) -> str:
        return "mock_op"

    def describe(self) -> str:
        return "Mock operation description"

    def metadata(self) -> dict[str, object]:
        return {"name": "mock_op"}


# ── 1. Contract Invariant & Serialization Tests ────────────────────────────────


def test_policy_subject_invariants_and_serialization() -> None:
    subject = PolicySubject(
        id="agent-123",
        kind=PolicySubjectKind.AGENT,
        roles=("admin", "developer"),
        permissions=("read_code", "write_code"),
    )
    assert subject.id == "agent-123"
    assert subject.kind == PolicySubjectKind.AGENT
    assert subject.roles == ("admin", "developer")

    serialized = subject.serialize()
    deserialized = PolicySubject.from_mapping(serialized)
    assert deserialized == subject

    with pytest.raises(InvalidPolicyContractError):
        PolicySubject(id="")


def test_policy_resource_invariants_and_serialization() -> None:
    res = PolicyResource(
        id="file-src-main",
        kind=PolicyResourceKind.FILE,
        sensitivity="restricted",
        path="src/main.py",
    )
    assert res.id == "file-src-main"
    assert res.sensitivity == "restricted"

    serialized = res.serialize()
    deserialized = PolicyResource.from_mapping(serialized)
    assert deserialized == res

    with pytest.raises(InvalidPolicyContractError):
        PolicyResource(id="  ")


def test_policy_condition_security_invariants() -> None:
    # Valid condition
    cond = PolicyCondition(
        field="subject.id",
        operator=PolicyConditionOperator.EQUALS,
        value="agent-1",
    )
    assert cond.field == "subject.id"

    # Reject private attribute path
    with pytest.raises(InvalidPolicyContractError):
        PolicyCondition(
            field="subject._private",
            operator=PolicyConditionOperator.EQUALS,
            value="secret",
        )

    # Reject method invocation path
    with pytest.raises(InvalidPolicyContractError):
        PolicyCondition(
            field="subject.get_secret()",
            operator=PolicyConditionOperator.EQUALS,
            value="secret",
        )

    # Reject path with spaces or code execution attempts
    with pytest.raises(InvalidPolicyContractError):
        PolicyCondition(
            field="subject.id + 'evil'",
            operator=PolicyConditionOperator.EQUALS,
            value="evil",
        )


def test_policy_invariants_and_rule_uniqueness() -> None:
    rule1 = PolicyRule(
        id="rule-1",
        policy_id="pol-1",
        description="Rule 1",
        conditions=(),
        effect=PolicyEffect.PERMIT,
        decision=PolicyDecision.ALLOW,
    )
    rule2 = PolicyRule(
        id="rule-2",
        policy_id="pol-1",
        description="Rule 2",
        conditions=(),
        effect=PolicyEffect.DENY,
        decision=PolicyDecision.DENY,
    )
    policy = Policy(
        id="pol-1",
        name="Test Policy",
        description="Description",
        version=1,
        priority=10,
        rules=(rule1, rule2),
    )
    assert len(policy.rules) == 2

    # Negative priority check
    with pytest.raises(InvalidPolicyContractError):
        Policy(id="pol-2", name="Bad Policy", description="", priority=-1)

    # Version <= 0 check
    with pytest.raises(PolicyVersionError):
        Policy(id="pol-3", name="Bad Version", description="", version=0)

    # Duplicate rule ID inside policy check
    rule_dup = PolicyRule(
        id="rule-1",
        policy_id="pol-dup",
        description="Duplicate Rule ID",
    )
    with pytest.raises(InvalidPolicyContractError):
        Policy(
            id="pol-dup",
            name="Dup Policy",
            description="",
            rules=(rule1, rule_dup),
        )

    # Invalid dates check (valid_from > valid_until)
    with pytest.raises(InvalidPolicyContractError):
        Policy(
            id="pol-dates",
            name="Dates Policy",
            description="",
            valid_from="2026-08-01T00:00:00Z",
            valid_until="2026-07-01T00:00:00Z",
        )


def test_policy_evaluation_result_confidence_bounds() -> None:
    with pytest.raises(InvalidPolicyContractError):
        PolicyEvaluationResult(
            id="res-bad",
            request_id="req-1",
            status=PolicyEvaluationStatus.COMPLETED,
            decision=PolicyDecision.ALLOW,
            allowed=True,
            denied=False,
            requires_approval=False,
            requires_validation=False,
            requires_information=False,
            paused=False,
            confidence=1.5,
        )


# ── 2. Repository & Store Tests ────────────────────────────────────────────────


def test_policy_repository_crud_and_versioning() -> None:
    repo = PolicyRepository()

    p1_v1 = Policy(
        id="pol-security",
        name="Security Policy",
        description="v1",
        version=1,
        priority=10,
    )
    p1_v2 = Policy(
        id="pol-security",
        name="Security Policy",
        description="v2",
        version=2,
        priority=20,
    )

    repo.add_policy(p1_v1)
    repo.add_policy(p1_v2)

    # Duplicate add check
    with pytest.raises(DuplicatePolicyError):
        repo.add_policy(p1_v1)

    # Latest version retrieval
    latest = repo.get_policy("pol-security")
    assert latest is not None
    assert latest.version == 2
    assert latest.priority == 20

    # Specific version retrieval
    v1_retrieved = repo.get_policy("pol-security", version=1)
    assert v1_retrieved is not None
    assert v1_retrieved.version == 1

    # Latest version number
    assert repo.get_latest_policy_version("pol-security") == 2

    # Disable policy
    repo.disable_policy("pol-security", version=2)
    assert repo.get_policy("pol-security", version=2).enabled is False

    # Policy Set CRUD
    pset = PolicySet(
        id="pset-1",
        name="Policy Set 1",
        description="Description",
        policy_ids=("pol-security",),
    )
    repo.add_policy_set(pset)

    with pytest.raises(DuplicatePolicySetError):
        repo.add_policy_set(pset)

    assert repo.get_policy_set("pset-1") == pset

    with pytest.raises(PolicyNotFoundError):
        repo.require_policy("nonexistent")

    with pytest.raises(PolicySetNotFoundError):
        repo.require_policy_set("nonexistent")


# ── 3. Field Resolution & Condition Evaluation Tests ──────────────────────────


def test_resolve_field_value_and_condition_operators() -> None:
    req = PolicyEvaluationRequest(
        id="req-test",
        subject=PolicySubject(id="agent-1", permissions=("read", "write")),
        resource=PolicyResource(id="res-1", sensitivity="internal"),
        action=PolicyAction(
            name="edit",
            parameters={"path": "src/app.py", "count": 5},
            is_mutation=True,
        ),
        environment=PolicyEnvironment(name="development", is_production=False),
        permissions=("read", "write"),
        risk=PolicyRiskLevel.LOW,
    )

    context = PolicyEvaluationContext(
        actor=req.subject,
        agent_id="agent-1",
        goal="goal-1",
        agent_run="run-1",
        subject=req.subject,
        resource=req.resource,
        action=req.action,
        environment=req.environment,
        permissions=req.permissions,
        sensitivity=req.sensitivity,
        risk=req.risk,
    )

    # Path resolution
    assert resolve_field_value("subject.id", context) == "agent-1"
    assert resolve_field_value("action.parameters.path", context) == "src/app.py"
    assert resolve_field_value("environment.is_production", context) is False

    # Condition evaluation checks
    c_equals = PolicyCondition(
        field="subject.id",
        operator=PolicyConditionOperator.EQUALS,
        value="agent-1",
    )
    assert evaluate_condition(c_equals, context) is True

    c_in = PolicyCondition(
        field="action.parameters.path",
        operator=PolicyConditionOperator.STARTS_WITH,
        value="src/",
    )
    assert evaluate_condition(c_in, context) is True

    c_num = PolicyCondition(
        field="action.parameters.count",
        operator=PolicyConditionOperator.GREATER_THAN,
        value=3,
    )
    assert evaluate_condition(c_num, context) is True

    c_exists = PolicyCondition(
        field="subject.id",
        operator=PolicyConditionOperator.EXISTS,
        value=True,
    )
    assert evaluate_condition(c_exists, context) is True

    c_not_exists = PolicyCondition(
        field="nonexistent.field",
        operator=PolicyConditionOperator.NOT_EXISTS,
        value=True,
    )
    assert evaluate_condition(c_not_exists, context) is True

    c_contains = PolicyCondition(
        field="permissions",
        operator=PolicyConditionOperator.CONTAINS,
        value="write",
    )
    assert evaluate_condition(c_contains, context) is True


# ── 4. Combining Algorithms Tests ─────────────────────────────────────────────


def test_combining_algorithms_behavior() -> None:
    evaluator = DefaultPolicyEvaluator()

    p_allow = Policy(
        id="p-allow",
        name="Allow Policy",
        description="",
        priority=10,
        rules=(
            PolicyRule(
                id="r-allow",
                policy_id="p-allow",
                description="Allow rule",
                effect=PolicyEffect.PERMIT,
                decision=PolicyDecision.ALLOW,
            ),
        ),
    )
    p_deny = Policy(
        id="p-deny",
        name="Deny Policy",
        description="",
        priority=20,
        rules=(
            PolicyRule(
                id="r-deny",
                policy_id="p-deny",
                description="Deny rule",
                effect=PolicyEffect.DENY,
                decision=PolicyDecision.DENY,
                reason_code="access_denied",
            ),
        ),
    )

    req = PolicyEvaluationRequest(
        id="req-comb",
        subject=PolicySubject(id="agent"),
        resource=PolicyResource(id="res"),
        action=PolicyAction(name="test"),
        environment=PolicyEnvironment(name="test"),
    )

    # 1. Deny overrides (Default)
    res_deny_overrides = evaluator.evaluate(
        request=req,
        policies=[p_allow, p_deny],
        policy_sets=[
            PolicySet(
                id="ps-1",
                name="Deny Overrides Set",
                description="",
                combining_algorithm=PolicyCombiningAlgorithm.DENY_OVERRIDES,
            )
        ],
    )
    assert res_deny_overrides.decision == PolicyDecision.DENY
    assert res_deny_overrides.denied is True

    # 2. Permit overrides
    res_permit_overrides = evaluator.evaluate(
        request=req,
        policies=[p_allow, p_deny],
        policy_sets=[
            PolicySet(
                id="ps-2",
                name="Permit Overrides Set",
                description="",
                combining_algorithm=PolicyCombiningAlgorithm.PERMIT_OVERRIDES,
            )
        ],
    )
    assert res_permit_overrides.decision == PolicyDecision.ALLOW
    assert res_permit_overrides.allowed is True

    # 3. First applicable (p_deny has higher priority 20 vs 10)
    res_first_app = evaluator.evaluate(
        request=req,
        policies=[p_allow, p_deny],
        policy_sets=[
            PolicySet(
                id="ps-3",
                name="First Applicable Set",
                description="",
                combining_algorithm=PolicyCombiningAlgorithm.FIRST_APPLICABLE,
            )
        ],
    )
    assert res_first_app.decision == PolicyDecision.DENY

    # 4. Only one applicable (fails when 2 match)
    with pytest.raises(PolicyCombiningError):
        evaluator.evaluate(
            request=req,
            policies=[p_allow, p_deny],
            policy_sets=[
                PolicySet(
                    id="ps-4",
                    name="Only One Applicable Set",
                    description="",
                    combining_algorithm=PolicyCombiningAlgorithm.ONLY_ONE_APPLICABLE,
                )
            ],
        )


# ── 5. Default System Policies & E2E Flows ─────────────────────────────────────


def test_policy_engine_operational_safety_unregistered_op() -> None:
    engine = PolicyEngine()  # Loads initial system policies

    req = PolicyEvaluationRequest(
        id="req-unregistered",
        subject=PolicySubject(id="agent-1"),
        resource=PolicyResource(id="op-1", kind=PolicyResourceKind.OPERATION),
        action=PolicyAction(
            name="execute_operation",
            parameters={"is_registered": False},
        ),
        environment=PolicyEnvironment(name="development"),
    )

    res = engine.evaluate(req)
    assert res.decision == PolicyDecision.DENY
    assert res.denied is True
    assert "unregistered_operation" in res.reason_codes


def test_policy_engine_critical_risk_requires_approval() -> None:
    engine = PolicyEngine()

    req = PolicyEvaluationRequest(
        id="req-critical-risk",
        subject=PolicySubject(id="agent-1"),
        resource=PolicyResource(id="db-prod", kind=PolicyResourceKind.SYSTEM),
        action=PolicyAction(
            name="execute_operation",
            parameters={"is_registered": True},
            is_mutation=True,
            is_reversible=False,
        ),
        environment=PolicyEnvironment(name="production", is_production=True),
        risk=PolicyRiskLevel.CRITICAL,
    )

    res = engine.evaluate(req)
    assert res.decision == PolicyDecision.REQUIRE_APPROVAL
    assert res.requires_approval is True
    assert any(o.kind == PolicyObligationKind.REQUIRE_APPROVAL for o in res.obligations)


def test_policy_engine_reversible_mutation_mandatory_rollback() -> None:
    engine = PolicyEngine()

    req = PolicyEvaluationRequest(
        id="req-reversible-mut",
        subject=PolicySubject(id="agent-1"),
        resource=PolicyResource(id="file-1", kind=PolicyResourceKind.FILE),
        action=PolicyAction(
            name="modify_file",
            parameters={"is_registered": True},
            is_mutation=True,
            is_reversible=True,
        ),
        environment=PolicyEnvironment(name="development"),
        risk=PolicyRiskLevel.LOW,
    )

    res = engine.evaluate(req)
    assert res.decision == PolicyDecision.ALLOW_WITH_RESTRICTIONS
    assert res.allowed is True
    assert any(o.kind == PolicyObligationKind.ENFORCE_ROLLBACK for o in res.obligations)


def test_policy_engine_data_sensitivity_restricted_external_search() -> None:
    engine = PolicyEngine()

    req = PolicyEvaluationRequest(
        id="req-restricted-search",
        subject=PolicySubject(id="agent-1"),
        resource=PolicyResource(id="doc-confidential", sensitivity="restricted"),
        action=PolicyAction(name="search_external_source"),
        environment=PolicyEnvironment(name="development"),
        permissions=("external_search",),
    )

    res = engine.evaluate(req)
    assert res.decision == PolicyDecision.DENY
    assert res.denied is True
    assert "external_transmission_restricted" in res.reason_codes


def test_policy_engine_info_acquisition_ask_secrets_denied() -> None:
    engine = PolicyEngine()

    req = PolicyEvaluationRequest(
        id="req-ask-secret",
        subject=PolicySubject(id="agent-1"),
        resource=PolicyResource(
            id="gap-secret", kind=PolicyResourceKind.ACQUISITION_STRATEGY
        ),
        action=PolicyAction(
            name="ask_user",
            parameters={"requests_secret": True},
        ),
        environment=PolicyEnvironment(name="development"),
    )

    res = engine.evaluate(req)
    assert res.decision == PolicyDecision.DENY
    assert res.denied is True
    assert "prohibit_asking_for_secrets" in res.reason_codes


def test_policy_engine_fallback_restrict_when_no_policy_matches() -> None:
    repo = PolicyRepository()
    engine = PolicyEngine(
        repository=repo,
        fallback_mode=PolicyFailureMode.DENY,
        load_initial_policies=False,
    )

    req = PolicyEvaluationRequest(
        id="req-no-policy",
        subject=PolicySubject(id="agent-1"),
        resource=PolicyResource(id="res-1"),
        action=PolicyAction(name="uncovered_action"),
        environment=PolicyEnvironment(name="development"),
    )

    res = engine.evaluate(req)
    assert res.decision == PolicyDecision.DENY
    assert res.denied is True
    assert "fallback_policy_applied" in res.reason_codes


# ── 6. Domain Adapters Integration Tests ───────────────────────────────────────


from cmm.agent_runtime import (
    AgentCognitiveDecision,
    AgentCognitiveStatus,
    InformationAcquisitionCost,
    InformationAcquisitionDecisionType,
    InformationAcquisitionStrategy,
    WorkflowPlanValidationStatus,
)


def test_workflow_plan_adapter_integration() -> None:
    engine = PolicyEngine()

    plan = AgentWorkflowPlan(
        id="plan-123",
        goal_id="goal-1",
        agent_run_id="run-1",
        workflow_id="wf-1",
        version=1,
        tasks=(),
        dependencies=(),
        operations=(),
        validation_nodes=(),
        approval_nodes=(),
        validation=AgentWorkflowPlanValidation(
            status=WorkflowPlanValidationStatus.FAILED,
            is_valid=False,
        ),
    )

    req = create_request_from_workflow_plan(plan)
    res = engine.evaluate(req)

    assert res.decision == PolicyDecision.DENY
    assert res.denied is True
    assert "invalid_workflow_plan" in res.reason_codes


def test_workflow_operation_adapter_integration() -> None:
    engine = PolicyEngine()

    op = AgentWorkflowOperation(
        id="op-shell",
        task_id="task-1",
        operation_name="shell",
        parameters={"command": "rm -rf /"},
        reversible=False,
    )

    req = create_request_from_workflow_operation(operation=op, permissions=("read",))
    res = engine.evaluate(req)

    assert res.decision == PolicyDecision.DENY
    assert res.denied is True
    assert "unauthorized_shell" in res.reason_codes


def test_acquisition_decision_adapter_integration() -> None:
    engine = PolicyEngine()

    dec = InformationAcquisitionDecision(
        id="acq-1",
        request_id="req-1",
        gap_id="gap-1",
        decision=InformationAcquisitionDecisionType.SELECT_STRATEGY,
        strategy=InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE,
        expected_cost=InformationAcquisitionCost(),
    )

    req = create_request_from_acquisition_decision(dec)
    res = engine.evaluate(req)

    assert res.decision == PolicyDecision.DENY
    assert res.denied is True


def test_cognitive_result_adapter_integration() -> None:
    engine = PolicyEngine()

    cog_res = AgentCognitiveResult(
        id="cog-res-1",
        request_id="req-1",
        agent_run_id="run-1",
        goal_id="goal-1",
        status=AgentCognitiveStatus.COMPLETED,
        reasoning_result_id="rr-1",
        recommended_decision=AgentCognitiveDecision.PLAN,
        confidence=0.9,
    )

    req = create_request_from_cognitive_result(cog_res)
    res = engine.evaluate(req)

    assert res.status == PolicyEvaluationStatus.COMPLETED
    assert res.allowed is True or res.decision in (
        PolicyDecision.ALLOW,
        PolicyDecision.ALLOW_WITH_RESTRICTIONS,
    )


def test_operation_registry_integration() -> None:
    registry = OperationRegistry()
    mock_op = MockTransformationOperation()
    registry.register(mock_op)

    # Verify operation is resolved in registry
    resolved = registry.resolve("mock_op")
    assert resolved.name == "mock_op"

    engine = PolicyEngine()
    req = PolicyEvaluationRequest(
        id="req-reg-op",
        subject=PolicySubject(id="agent-1"),
        resource=PolicyResource(id="op-mock", kind=PolicyResourceKind.OPERATION),
        action=PolicyAction(
            name="execute_operation",
            operation_name="mock_op",
            parameters={"is_registered": True},
        ),
        environment=PolicyEnvironment(name="development"),
    )

    res = engine.evaluate(req)
    assert res.allowed is True
