# 🛡️ Phase 9.8 — Policy Engine Architecture

## Overview

The **Policy Engine** is the generic, deterministic authorization, compliance, safety, and governance component of the Phase 9 Autonomous Agent Runtime in CMM OS.

It evaluates whether a given goal, strategy, workflow plan, task, operation, information acquisition request, or cognitive decision is permitted under an explicit, versioned, prioritized set of security and governance policies.

```text
Actor + Agent + Goal + AgentRun + Request (Plan / Task / Operation / Acquisition)
+ Permissions + Environment + Risk + Sensitivity + Policy Sets
                                ↓
                        Policy Engine
                                ↓
    Policy Evaluation (Combining Algorithm: Deny-Overrides)
                                ↓
Allow / Deny / Require Approval / Require Validation / Pause / Restrict
```

---

## Key Principles & Boundaries

1. **Standalone & Deterministic**: Evaluation relies on structured attributes and condition trees (`PolicyCondition`). It does not use `eval`, dynamic Python execution, or unconstrained LLM heuristics.
2. **Non-Executing**: The Policy Engine only evaluates requests. It does not execute operations, grant permissions, raise autonomy levels, persist state changes, consume action budgets, or alter workflow plans.
3. **Fail-Safe Restricted Fallback**: If no policy matches, or if an evaluation error/indeterminate state occurs, the system defaults to a configurable fail-safe mode (`deny`, `pause`, or `require_approval`). It **never** defaults to `allow`.
4. **No Code Duplication**: Reuses existing `OperationRegistry` and `ValidationPolicy` names without duplicating authorization or approval mechanics.
5. **Decoupled Architecture**: Domain objects (`AgentWorkflowPlan`, `AgentWorkflowOperation`, `InformationAcquisitionDecision`, `AgentCognitiveResult`) are translated into `PolicyEvaluationRequest` via pure adapters without modifying domain models.

---

## Core Component Contracts

### 1. Data Models & Entities
* `PolicySubject`: Represents the actor/agent under check (`id`, `kind`, `roles`, `permissions`).
* `PolicyResource`: Target entity (`id`, `kind`, `sensitivity`, `path`, `owner_id`).
* `PolicyAction`: Operation being attempted (`name`, `operation_name`, `parameters`, `is_mutation`, `is_reversible`).
* `PolicyEnvironment`: Runtime environment context (`name`, `is_production`, `ip_address`, `timestamp`).
* `PolicyCondition`: Safe comparison predicate (`field`, `operator`, `value`, `case_sensitive`, `negate`).

### 2. Policy Structure
* `Policy`: Immutable policy definition (`id`, `name`, `version`, `enabled`, `priority`, `scope`, `target`, `rules`, `obligations`, `restrictions`, `failure_mode`).
* `PolicyRule`: Rule contained within a policy (`id`, `policy_id`, `conditions`, `effect`, `decision`, `priority`, `reason_code`, `obligations`, `restrictions`).
* `PolicySet`: Group of policies combined via a `PolicyCombiningAlgorithm`.

### 3. Evaluation Requests & Results
* `PolicyEvaluationRequest`: Standardized input payload.
* `PolicyEvaluationContext`: Structured evaluation context preserving actor, agent, goal, run, subject, resource, action, environment, permissions, sensitivity, and risk.
* `PolicyEvaluationResult`: Comprehensive result containing `decision`, `allowed`, `denied`, `requires_approval`, `requires_validation`, `applicable_policy_ids`, `matched_rule_ids`, `rule_evaluations`, `obligations`, `restrictions`, `advice`, `violations`, `warnings`, `errors`, and `policy_trace_id`.

---

## Combining Algorithms

* **`deny_overrides`** *(Default)*: Any matching `DENY` decision immediately overrides `ALLOW` decisions.
* **`permit_overrides`**: Any matching `ALLOW` overrides `DENY`.
* **`first_applicable`**: Returns the decision of the first policy/rule matching the target.
* **`only_one_applicable`**: Expects exactly one applicable rule; fails if multiple match.
* **`ordered_deny_overrides`**: Evaluates in strict priority order, stopping at the first `DENY`.
* **`ordered_permit_overrides`**: Evaluates in strict priority order, stopping at the first `ALLOW`.

---

## Security & Path Resolution

Property resolution is strictly controlled:
*Dotted attribute paths* (e.g. `subject.kind`, `action.parameters.path`, `context.risk`) are resolved using `resolve_field_value`.
Paths containing underscores at part boundaries (e.g., `_private`), method invocations (`()`), or dynamic code patterns are rejected immediately with `InvalidPolicyContractError`.

---

## Domain Adapters

* `create_request_from_workflow_plan(plan)`: Adapts an `AgentWorkflowPlan` into a policy check covering structural validation, risks, pending approvals, and rollback availability.
* `create_request_from_workflow_operation(operation)`: Adapts an `AgentWorkflowOperation` checking operation name, parameters, mutation status, reversibility, and registered status.
* `create_request_from_acquisition_decision(decision)`: Adapts an `InformationAcquisitionDecision` checking external search permissions, sensitivity, and user secret requests.
* `create_request_from_cognitive_result(result)`: Adapts an `AgentCognitiveResult` checking cognitive recommendations and blocking gaps.

---

## Code Example

```python
from cmm.agent_runtime import (
    PolicyEngine,
    PolicyEvaluationRequest,
    PolicySubject,
    PolicySubjectKind,
    PolicyResource,
    PolicyResourceKind,
    PolicyAction,
    PolicyEnvironment,
    PolicyRiskLevel,
    PolicyDecision,
)

# 1. Initialize Policy Engine (loads default initial system policies)
engine = PolicyEngine()

# 2. Build PolicyEvaluationRequest
request = PolicyEvaluationRequest(
    id="policy-req-001",
    subject=PolicySubject(id="agent-maintenance", kind=PolicySubjectKind.AGENT),
    resource=PolicyResource(id="src/service.py", kind=PolicyResourceKind.FILE, sensitivity="internal"),
    action=PolicyAction(
        name="execute_operation",
        operation_name="refactor_code",
        parameters={"is_registered": True},
        is_mutation=True,
        is_reversible=True,
    ),
    environment=PolicyEnvironment(name="development"),
    permissions=("write_code",),
    risk=PolicyRiskLevel.LOW,
)

# 3. Evaluate request
result = engine.evaluate(request)

if result.allowed:
    print(f"Decision allowed ({result.decision.value}) with obligations: {len(result.obligations)}")
else:
    print(f"Decision denied ({result.decision.value}) reason: {result.reason_codes}")
```

---

## Relationship with Subsequent Subphases

* **Phase 9.9 — Autonomy Levels**: Policy Engine provides compatible target fields and fallback decisions when autonomy levels are insufficient or undefined.
* **Phase 9.10 — Human Approval System**: Emits `require_approval` decisions and `REQUIRE_APPROVAL` obligations to trigger approval requests without executing actions itself.
* **Phase 9.11 — Action Budget**: Enforces cost/timeout restrictions without directly tracking budget consumption.
* **Phase 9.12 - 9.14 — Runtime Loop, Execution Adapter & Recovery**: Queries Policy Engine before each workflow task/operation step to ensure safety compliance.
