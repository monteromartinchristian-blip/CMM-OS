# 🧭 Phase 9.9 — Autonomy Levels Architecture

## Overview

The **Autonomy Levels** subsystem defines the maximum operational freedom available to an agent during a specific `AgentRun`.

It introduces five canonical levels, from analysis-only behavior to policy-bounded autonomous execution. Autonomy remains an additional constraint and never replaces policy, permissions, validation, approval, rollback guarantees, or future action budgets.

```text
AgentRun + Autonomy Level + Capability + Operation Characteristics
+ Policy Decision + Approval + Validation + Rollback
                              ↓
                    Autonomy Evaluator
                              ↓
Allow / Deny / Require Approval / Require Validation
        / Require Rollback / Pause / Fail-Safe
```

Effective authorization is conjunctive:

```text
Autonomy
AND Policy
AND Permissions
AND Validation
AND Approval
AND Rollback Guarantees
```

---

## Key Principles

1. **Autonomy Is a Maximum**: It defines what an agent may potentially perform, not what it is automatically authorized to perform.

2. **Fail-Safe by Default**: Unknown capabilities, unsupported levels, ambiguous policy decisions, and inconsistent states never default to `allow`.

3. **Explicit Operation Semantics**: Mutation, reversibility, destructiveness, external effects, sensitivity, spending, and structural changes are supplied explicitly.

4. **Run-Scoped Authority**: `AgentDefinition.autonomy_level` defines the configured maximum, while `AgentRun.autonomy_level` stores the effective runtime level.

5. **Safe Reduction**: Autonomy may always be reduced without escalation authorization.

6. **Authorized Escalation**: Increasing autonomy requires explicit authorization and cannot exceed the agent definition maximum.

7. **Non-Executing**: This subsystem evaluates authority boundaries but does not execute operations, grant permissions, create approvals, or consume budgets.

---

## Canonical Levels

### Level 0 — Analyze Only

`AgentAutonomyLevel.ANALYZE_ONLY`

Allows reasoning, context inspection, information-gap detection, questions, and plan proposals. Execution is prohibited.

### Level 1 — Propose Actions

`AgentAutonomyLevel.PROPOSE_ACTIONS`

Allows structured operation and workflow proposals, but still prohibits direct execution.

### Level 2 — Reversible Execution

`AgentAutonomyLevel.REVERSIBLE_EXECUTION`

Allows read-only execution and validated reversible mutations. Rollback availability is required when mandated by the profile.

Irreversible, destructive, external, spending, permission-changing, and policy-changing operations remain prohibited.

### Level 3 — Supervised Autonomy

`AgentAutonomyLevel.SUPERVISED_AUTONOMY`

Allows broader workflow execution. High-impact actions require explicit approval, including publication, irreversible execution, destruction, spending, permission changes, and policy changes.

### Level 4 — Policy-Bounded Autonomy

`AgentAutonomyLevel.POLICY_BOUNDED_AUTONOMY`

Allows autonomous execution only when all policy, permission, validation, approval, rollback, and runtime constraints are satisfied.

Level 4 is not unrestricted autonomy.

---

## Core Contracts

### `AutonomyProfile`

Immutable definition of:

* allowed capabilities;

* approval-required capabilities;

* prohibited capabilities;

* mutation and execution restrictions;

* validation requirements;

* rollback requirements;

* external, spending, permission, and policy-change boundaries.

Canonical profiles are resolved through `get_autonomy_profile()`.

### `AutonomyEvaluationRequest`

Structured input containing:

* runtime autonomy level;

* requested capability;

* operation name;

* mutation and reversibility flags;

* destructive, external, sensitive, and spending flags;

* permission and policy changes;

* policy decision;

* approval, validation, and rollback state;

* metadata.

### `AutonomyEvaluationResult`

Deterministic result containing:

* decision;

* allowed and denied state;

* approval, validation, and rollback requirements;

* pause state;

* reason codes;

* evaluated level and capability;

* profile reference;

* timestamp and metadata.

### Transition Contracts

* `AutonomyTransitionRequest`

* `AutonomyTransitionResult`

* `AutonomyTransitionRecord`

These preserve previous, requested, and resulting levels, authorization state, actor, reason, timestamp, and audit metadata.

---

## Evaluation Rules

The `DefaultAutonomyEvaluator` applies restrictive checks in order:

1. Resolve and validate the autonomy level.

2. Classify the capability as allowed, approval-required, or prohibited.

3. Fail closed for undeclared capabilities.

4. Enforce execution and mutation restrictions.

5. Enforce irreversible, destructive, external, sensitive, spending, permission, and policy-change boundaries.

6. Require validation or rollback when configured.

7. Apply the binding policy decision.

8. Return a structured decision and reason codes.

Possible decisions include:

* `ALLOW`

* `DENY`

* `REQUIRE_APPROVAL`

* `REQUIRE_VALIDATION`

* `REQUIRE_ROLLBACK`

* `PAUSE`

* `FAILSAFE`

---

## Policy Engine Integration

`create_autonomy_request_from_policy_result()` translates a `PolicyEvaluationResult` into an `AutonomyEvaluationRequest`.

The adapter:

* validates the supplied `AgentRun`;

* validates the policy result;

* copies the effective runtime autonomy level;

* normalizes the policy decision;

* preserves explicit security flags;

* preserves approval, validation, rollback, and metadata state.

It does not reconstruct unavailable `PolicySubject`, `PolicyResource`, or `PolicyAction` instances.

It also never infers security characteristics from operation-name keywords.

---

## Autonomy Transitions

Transitions are managed through:

* `build_transition_request()`;

* `apply_autonomy_transition()`;

* `build_transition_record()`;

* `derive_new_agent_run()`.

Reductions and no-op transitions do not require escalation authorization.

Escalations:

* require explicit authorization;

* may identify the authorizing actor;

* cannot exceed the configured maximum;

* raise `AutonomyEscalationNotAuthorizedError` when unauthorized.

`derive_new_agent_run()` returns a new immutable runtime value and does not mutate the original `AgentRun`.

---

## Public API
```python
from cmm.agent_runtime import (
    AgentAutonomyLevel,
    AutonomyCapability,
    AutonomyDecision,
    AutonomyEvaluationRequest,
    AutonomyEvaluationResult,
    AutonomyProfile,
    AutonomyTransitionReason,
    AutonomyTransitionRecord,
    AutonomyTransitionRequest,
    AutonomyTransitionResult,
    AutonomyEvaluator,
    DefaultAutonomyEvaluator,
    apply_autonomy_transition,
    build_transition_record,
    build_transition_request,
    coerce_autonomy_level,
    create_autonomy_request_from_policy_result,
    derive_new_agent_run,
    get_autonomy_profile,
    list_canonical_levels,
)
```

---

## Example
```python
from cmm.agent_runtime import (
    AgentAutonomyLevel,
    AutonomyCapability,
    AutonomyEvaluationRequest,
    DefaultAutonomyEvaluator,
)
request = AutonomyEvaluationRequest(
    id="autonomy-request-001",
    agent_run_id="run-001",
    autonomy_level=AgentAutonomyLevel.REVERSIBLE_EXECUTION,
    capability=AutonomyCapability.EXECUTE_REVERSIBLE,
    operation_name="update_local_configuration",
    is_mutation=True,
    is_reversible=True,
    validation_passed=True,
    rollback_available=True,
    policy_decision="allow",
)
result = DefaultAutonomyEvaluator().evaluate(request)
```

---

## Relationship with Subsequent Subphases

* **Phase 9.10 — Human Approval System**: Satisfies and audits approval requirements.

* **Phase 9.11 — Action Budget**: Adds quantitative limits independently of autonomy.

* **Phase 9.12 — Runtime Loop**: Evaluates autonomy before each workflow step.

* **Phase 9.13 — Execution Adapter**: Supplies explicit operation characteristics and executes only after authorization.

* **Phase 9.14 — Recovery & Reflection**: May reduce autonomy during failures, rollback, uncertainty, or degraded conditions.
