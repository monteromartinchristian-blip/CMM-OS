# 🤖 Phase 9 — Autonomous Agent Runtime

## Objective

Build the common autonomous infrastructure that enables CMM OS to pursue persistent goals, observe system state, use the Cognitive Layer, plan workflows, execute operations, validate results, recover from failures, and update knowledge in a controlled way.

Phase 9 will not build a monolithic agent or an independent “brain.”

It will build a **generic goal-oriented Agent Runtime** that future agents and domains will use through different configurations, policies, profiles, and permissions.

The agent must not duplicate:

* the knowledge model;
* cognitive rules;
* reasoning profiles;
* gap analysis;
* the question engine;
* the Planner;
* the Execution Engine;
* the Validation System;
* memory;
* the event system;
* semantic operations;
* rollback mechanisms.

The Agent Runtime must coordinate these capabilities through stable contracts.

CMM OS must not be limited to executing an isolated command. It must be able to:

* maintain open goals;
* break them down into subgoals;
* observe relevant changes;
* load knowledge;
* reason about the next step;
* detect missing information;
* ask or search when appropriate;
* create executable workflows;
* request human approval;
* execute permitted operations;
* validate each result;
* evaluate whether the goal has been met;
* retry;
* replan;
* revert changes;
* pause;
* resume;
* escalate;
* update knowledge;
* preserve decisions;
* finish in a demonstrable way.

⸻

## General Architecture

Goal
↓
Goal Registration
↓
Goal Prioritization
↓
Observation
↓
Relevant Knowledge Loading
↓
Cognitive Analysis
↓
Information Gap Resolution
↓
Execution Decision
↓
Workflow Planning
↓
Policy Evaluation
↓
Approval Gates
↓
Action Budget Reservation
↓
Workflow Execution
↓
Operation Validation
↓
Outcome Evaluation
↓
Knowledge and Memory Update
↓
Continue / Retry / Replan / Rollback / Pause / Escalate / Complete

Cross-cutting components:

Agent Runtime
+
Policy Engine
+
Action Budget
+
Approval System
+
Recovery Manager
+
Runtime Event Bus
+
Persistence
+
Observability
+
Audit Trail

The Agent Runtime must be usable:

* from the conversational UI;
* from the CLI;
* from the API;
* from workflows;
* from Kernel events;
* from scheduled tasks;
* from n8n;
* from specialized domains;
* with manual execution;
* with supervised execution;
* with limited autonomy;
* with full autonomy within a policy;
* on a new goal;
* on a persistent goal;
* on goals with subgoals;
* on paused workflows;
* with local or remote models;
* without depending on a specific AI provider;
* without requiring every decision to use a language model.

⸻

# 9.1 — Agent Runtime Contracts

## Objective

Define the common contracts of the autonomous system before implementing concrete agents, policies, observers, or recovery strategies.

## Agent Identifier

Every agent or execution must have stable identifiers.

Examples:

```text
agent:project-maintenance:123
agent-run:456
goal:technical-debt:789
goal-run:321
observation:snapshot:654
workflow-plan:987
approval-request:111
runtime-decision:222
outcome-evaluation:333
```

## Agent Definition

An agent is a declarative configuration of the Agent Runtime.

```python
AgentDefinition(
    id="agent-project-maintenance",
    name="Project Maintenance Agent",
    version="1",
    description="Maintains the structural quality of the project",
    reasoning_profile="project",
    runtime_policy="project-maintenance",
    observation_profile="repository",
    autonomy_level=2,
    allowed_goal_types=[],
    allowed_operations=[],
    prohibited_operations=[],
    budget_policy="default-project-budget",
    approval_policy="project-approval",
    recovery_policy="safe-recovery",
    enabled=True,
    metadata={},
)
```

The agent will not implement cognitive logic or execution of its own.

The definition will select:

* cognitive profile;
* observers;
* policies;
* permitted operations;
* autonomy level;
* budget;
* approval criteria;
* recovery;
* events;
* persistence;
* limits.

## Agent Runtime Status

General runtime states:

```text
created
initializing
observing
reasoning
waiting_for_user
waiting_for_resource
planning
waiting_for_approval
executing
validating
evaluating
recovering
paused
blocked
completed
cancelled
failed
aborted
```

## Agent Run

```python
AgentRun(
    id="agent-run-123",
    agent_id="agent-project-maintenance",
    goal_id="goal-123",
    status="executing",
    autonomy_level=2,
    current_iteration=3,
    current_workflow_id="workflow-123",
    current_task_id="task-456",
    reasoning_session_id="session-789",
    observation_snapshot_id="observation-321",
    budget_id="budget-654",
    policy_context_id="policy-context-987",
    started_at="...",
    updated_at="...",
    paused_at=None,
    completed_at=None,
    metadata={},
)
```

## Runtime Decision

Every relevant transition must produce a structured decision.

```python
RuntimeDecision(
    id="runtime-decision-123",
    run_id="agent-run-123",
    decision="execute_workflow",
    reason_codes=[
        "sufficient_information",
        "policy_allows",
        "budget_available",
    ],
    inputs=[],
    policy_results=[],
    confidence=0.91,
    requires_approval=False,
    created_at="...",
    metadata={},
)
```

Initial decisions:

```text
observe
load_knowledge
reason
ask_user
load_resource
search
plan
execute
validate
evaluate
continue
retry
replan
rollback
pause
escalate
complete
fail
abort
```

## Agent Result

```python
AgentResult(
    id="agent-result-123",
    agent_run_id="agent-run-123",
    goal_id="goal-123",
    status="completed",
    outcome="success",
    success_criteria=[],
    completed_workflows=[],
    completed_operations=[],
    failed_operations=[],
    validations=[],
    knowledge_updates=[],
    memory_updates=[],
    side_effects=[],
    remaining_work=[],
    confidence=0.95,
    trace_id="agent-trace-123",
    started_at="...",
    completed_at="...",
    duration_ms=82000,
    metadata={},
)
```

⸻

# 9.2 — Goal System

## Objective

Represent, persist, prioritize, and manage goals as entities independent from the agent that executes them.

The system must be able to maintain goals over extended periods, split them into subgoals, and demonstrate when they are satisfied.

## Goal

```python
Goal(
    id="goal-123",
    title="Reduce project technical debt",
    description="Identify and correct priority technical debt without degrading the system",
    kind="project_improvement",
    status="active",
    priority=80,
    urgency=40,
    value=85,
    confidence=0.9,
    success_criteria=[],
    constraints=[],
    requirements=[],
    dependencies=[],
    blocked_by=[],
    parent_goal_id=None,
    child_goal_ids=[],
    source="user",
    owner_actor_id="actor-user",
    assigned_agent_id=None,
    autonomy_level=None,
    deadline=None,
    temporal_scope={},
    sensitivity="internal",
    permissions=[],
    created_at="...",
    updated_at="...",
    completed_at=None,
    metadata={},
)
```

## Goal Status

Initial states:

```text
proposed
accepted
active
planning
in_progress
waiting_for_user
waiting_for_resource
waiting_for_approval
blocked
paused
completed
partially_completed
failed
abandoned
cancelled
superseded
```

## Goal Kind

Initial types:

* information;
* analysis;
* planning;
* transformation;
* validation;
* maintenance;
* monitoring;
* research;
* documentation;
* integration;
* remediation;
* optimization;
* project_improvement;
* personal;
* domain_specific;
* recurring;
* composite.

## Goal Priority

Priority must not be represented only as a number.

```python
GoalPriority(
    score=80,
    urgency=60,
    importance=90,
    user_priority=100,
    deadline_pressure=40,
    dependency_impact=70,
    risk_reduction=80,
    estimated_cost=30,
    reasons=[],
    calculated_at="...",
    metadata={},
)
```

Initial factors:

* explicit user priority;
* urgency;
* importance;
* deadline;
* blocked goals;
* risk;
* impact;
* cost;
* expected value;
* age;
* sensitivity;
* resource availability;
* budget;
* need for human intervention.

## Success Criterion

```python
SuccessCriterion(
    id="criterion-123",
    description="The full suite remains green",
    kind="validation",
    required=True,
    measurable=True,
    evaluator="validation_result",
    expected_value="passed",
    actual_value=None,
    status="pending",
    evidence=[],
    metadata={},
)
```

Initial types:

* state;
* validation;
* metric;
* artifact;
* knowledge;
* user_confirmation;
* workflow_completion;
* operation_result;
* temporal;
* composite.

States:

```text
pending
satisfied
partially_satisfied
unsatisfied
not_evaluable
waived
```

## Goal Constraint

```python
GoalConstraint(
    id="constraint-123",
    description="Do not modify public APIs",
    kind="operation",
    severity="blocking",
    source="user",
    condition={},
    metadata={},
)
```

Types:

* time;
* cost;
* operation;
* permission;
* safety;
* domain;
* resource;
* quality;
* legal;
* privacy;
* user_defined;
* technical.

## Goal Dependency

```python
GoalDependency(
    goal_id="goal-2",
    depends_on_goal_id="goal-1",
    dependency_type="requires_completion",
    blocking=True,
    metadata={},
)
```

Initial relationships:

* requires_completion;
* requires_partial_result;
* requires_knowledge;
* requires_resource;
* conflicts_with;
* enables;
* supersedes;
* related_to.

## Goal Repository

```python
class GoalRepository:
    def add(self, goal: Goal) -> Goal:
        ...
    def get(self, goal_id: str) -> Goal | None:
        ...
    def update(self, goal: Goal) -> Goal:
        ...
    def search(self, query: GoalQuery) -> GoalSearchResult:
        ...
    def get_children(self, goal_id: str) -> list[Goal]:
        ...
    def get_dependencies(self, goal_id: str) -> list[GoalDependency]:
        ...
    def append_history(self, event: GoalHistoryEntry) -> None:
        ...
```

## Goal History

Every transition must preserve:

* previous state;
* new state;
* actor;
* reason;
* decision;
* evidence;
* timestamp;
* related run;
* applied policy.

Completion must not delete history.

## Goal Manager

Responsibilities:

* register goals;
* validate contracts;
* prioritize;
* assign agents;
* create subgoals;
* resolve dependencies;
* block;
* pause;
* resume;
* cancel;
* complete;
* evaluate success criteria;
* detect duplicate goals;
* detect incompatible goals;
* detect abandoned goals;
* preserve history;
* emit events.

Restrictions:

The Goal Manager must not:

* plan workflows;
* execute operations;
* decide sensitive actions by itself;
* convert a recommendation into a goal without authorization;
* mark a goal as completed without evaluation;
* hide unsatisfied criteria;
* remove failed goals from history.

⸻

# 9.3 — Goal Intake and Goal Normalization

## Objective

Convert requests, events, decisions, or detected needs into well-defined executable goals.

## Goal Proposal

```python
GoalProposal(
    id="goal-proposal-123",
    source="user_message",
    raw_objective="Clean up the project",
    normalized_title="Reduce priority technical debt",
    normalized_description="...",
    proposed_kind="project_improvement",
    proposed_success_criteria=[],
    proposed_constraints=[],
    ambiguities=[],
    information_gaps=[],
    requires_confirmation=True,
    confidence=0.72,
    metadata={},
)
```

## Goal Sources

* direct user request;
* workflow;
* agent;
* Kernel event;
* validation result;
* error detection;
* recurring goal;
* maintenance policy;
* periodic review;
* specialized domain;
* external integration;
* subgoal created during planning.

## Normalization

The system must try to obtain:

* title;
* description;
* desired outcome;
* scope;
* success criteria;
* constraints;
* priority;
* owner;
* deadline;
* resources;
* sensitivity;
* autonomy level;
* permissions;
* dependencies;
* risks;
* cancellation conditions.

## Ambiguous Goals

When material ambiguity exists, the system must:

* use the Cognitive Layer;
* detect gaps;
* formulate questions;
* propose success criteria;
* limit scope;
* or keep the goal as `proposed`.

It must not start impactful actions when the goal is not sufficiently defined.

## Derived Goals

An agent may propose new goals when it detects:

* technical debt;
* inconsistent documentation;
* missing tests;
* outdated knowledge;
* a recurring error;
* a blocked dependency;
* a risk;
* a contradiction;
* an optimization opportunity.

Derived goals must be distinguished as:

```text
suggested
automatically_created
user_requested
policy_required
recovery_generated
```

Automatic creation will be limited by policy.

⸻

# 9.4 — Observation Engine

## Objective

Observe the relevant state of the system and produce structured snapshots before reasoning or acting.

Observation must clearly separate:

* observed state;
* interpretation;
* detected change;
* source;
* confidence;
* validity.

## Observer

```python
class Observer:
    name: str
    version: str

    def supports(
        self,
        request: ObservationRequest,
    ) -> bool:
        ...

    def observe(
        self,
        request: ObservationRequest,
    ) -> ObservationResult:
        ...
```

## Initial Observers

* RepositoryObserver;
* FilesystemObserver;
* GitObserver;
* ValidationObserver;
* TestObserver;
* DocumentationObserver;
* MemoryObserver;
* KnowledgeObserver;
* GoalObserver;
* WorkflowObserver;
* EventObserver;
* MetricsObserver;
* SystemHealthObserver;
* DependencyObserver;
* ConfigurationObserver;
* ExternalResourceObserver.

## Observation Request

```python
ObservationRequest(
    id="observation-request-123",
    goal_id="goal-123",
    agent_run_id="agent-run-123",
    observer_names=[],
    scope=[],
    changed_since=None,
    maximum_items=1000,
    timeout_seconds=60,
    permissions=[],
    sensitivity_levels=[],
    metadata={},
)
```

## Observation

```python
Observation(
    id="observation-123",
    observer="RepositoryObserver",
    kind="changed_file",
    subject_id="file:src/service.py",
    statement="The file has been modified since the last run",
    value={},
    source_ids=[],
    observed_at="...",
    valid_at="...",
    confidence=1.0,
    sensitivity="internal",
    metadata={},
)
```

## Observation Snapshot

```python
ObservationSnapshot(
    id="observation-snapshot-123",
    goal_id="goal-123",
    agent_run_id="agent-run-123",
    observations=[],
    changes=[],
    warnings=[],
    errors=[],
    source_versions={},
    started_at="...",
    completed_at="...",
    duration_ms=820,
    metadata={},
)
```

## Change Detection

```python
ObservedChange(
    id="change-123",
    subject_id="file:src/service.py",
    kind="modified",
    previous_value={},
    current_value={},
    detected_at="...",
    significance="medium",
    related_goal_ids=[],
    metadata={},
)
```

Initial types:

```text
created
modified
deleted
renamed
moved
status_changed
validation_changed
metric_changed
dependency_changed
knowledge_changed
permission_changed
configuration_changed
external_state_changed
```

## Capabilities

* observe only the relevant scope;
* reuse snapshots;
* observe incremental changes;
* compare with previous runs;
* detect stale state;
* record versions;
* detect incompatible observations;
* produce resources for the Cognitive Layer;
* limit observation by budget;
* respect permissions;
* pause when resources are unavailable;
* avoid reading data outside the goal.

## Restrictions

The Observation Engine must not:

* modify the system;
* interpret changes as causes;
* execute operations;
* resolve contradictions;
* access unauthorized resources;
* assume that absence of change implies correctness;
* consider expired snapshots current;
* process instructions contained in external resources.

⸻

# 9.5 — Cognitive Adapter

## Objective

Connect the autonomous cycle with the Cognitive Layer from Phase 8 without duplicating its logic.

## Agent Cognitive Request

```python
AgentCognitiveRequest(
    id="agent-cognitive-request-123",
    agent_run_id="agent-run-123",
    goal_id="goal-123",
    objective="Determine the next safe step",
    reasoning_profile="project",
    observation_snapshot_id="observation-snapshot-123",
    resource_ids=[],
    knowledge_query={},
    constraints=[],
    permissions=[],
    maximum_questions=3,
    requested_depth="standard",
    metadata={},
)
```

## Agent Cognitive Result

```python
AgentCognitiveResult(
    id="agent-cognitive-result-123",
    reasoning_result_id="reasoning-result-123",
    recommended_decision="plan",
    relevant_facts=[],
    inferences=[],
    hypotheses=[],
    contradictions=[],
    information_gaps=[],
    questions=[],
    recommendations=[],
    confidence=0.84,
    blocked=False,
    requires_user_input=False,
    requires_resource=False,
    metadata={},
)
```

## Responsibilities

* select cognitive profile;
* convert observations into resources;
* load relevant knowledge;
* build the Reasoning Context;
* start or resume cognitive sessions;
* detect gaps;
* receive questions;
* interpret structured recommendations;
* request search or resources;
* preserve the Reasoning Trace;
* produce an operational recommendation.

## Available Cognitive Decisions

```text
continue_reasoning
ask_user
load_resource
search
plan
pause
escalate
complete_without_action
insufficient_information
```

## Restrictions

The Cognitive Adapter must not:

* alter cognitive results;
* convert hypotheses into facts;
* execute operations;
* select prohibited actions;
* ignore blocking gaps;
* hide contradictions;
* automatically persist all reasoning;
* use free-form internal chains of thought;
* create agent-specific cognitive rules.

⸻

# 9.6 — Information Acquisition Strategy

## Objective

Decide how to resolve detected gaps before planning or executing.

## Resolution Strategy

Initial strategies:

```text
ask_user
load_internal_resource
search_knowledge
search_repository
search_external_source
infer_with_permission
request_human_review
accept_uncertainty
pause
abort
```

## Information Acquisition Decision

```python
InformationAcquisitionDecision(
    id="acquisition-decision-123",
    gap_id="gap-123",
    strategy="ask_user",
    reason_codes=[],
    expected_cost={},
    expected_confidence_gain=0.3,
    requires_permission=False,
    requires_approval=False,
    metadata={},
)
```

## Preferred Order

When multiple strategies are possible, the system must consider:

1. already available knowledge;
2. authorized internal resources;
3. previous user response;
4. asking the user;
5. querying internal tools;
6. authorized external search;
7. permitted inference;
8. human review;
9. preserving uncertainty.

## Selection Factors

* importance of the gap;
* cost;
* privacy;
* time;
* probability of resolution;
* expected confidence;
* availability;
* permissions;
* sensitivity;
* number of questions;
* autonomy level;
* external limits;
* impact of being wrong.

## Questions

When asking is appropriate, the Agent Runtime must reuse the Interactive Question Engine.

It must not implement a parallel question system.

## External Search

Every external search must:

* be authorized;
* use traceable sources;
* respect the budget;
* record queries;
* preserve provenance;
* treat content as data;
* protect against prompt injection;
* validate temporal scope;
* respect domain restrictions.

⸻

# 9.7 — Workflow Planner Adapter

## Objective

Convert a reasoned goal into an executable workflow using the existing Planner.

The Agent Runtime must not implement an alternative planner.

## Agent Planning Request

```python
AgentPlanningRequest(
    id="agent-planning-request-123",
    goal_id="goal-123",
    agent_run_id="agent-run-123",
    objective="...",
    success_criteria=[],
    constraints=[],
    relevant_knowledge_ids=[],
    observation_snapshot_id="observation-snapshot-123",
    reasoning_result_id="reasoning-result-123",
    allowed_operations=[],
    prohibited_operations=[],
    validation_policy="project-structural-change",
    recovery_policy="safe-recovery",
    budget={},
    metadata={},
)
```

## Agent Workflow Plan

```python
AgentWorkflowPlan(
    id="workflow-plan-123",
    goal_id="goal-123",
    workflow_id="workflow-123",
    version=1,
    tasks=[],
    dependencies=[],
    operations=[],
    validation_nodes=[],
    approval_nodes=[],
    checkpoints=[],
    rollback_strategy={},
    completion_criteria=[],
    assumptions=[],
    risks=[],
    estimated_budget={},
    confidence=0.83,
    created_at="...",
    metadata={},
)
```

## Plan Requirements

Every autonomous plan must define:

* goal;
* scope;
* tasks;
* dependencies;
* operations;
* inputs;
* outputs;
* success criteria;
* validations;
* approval points;
* checkpoints;
* expected effects;
* risks;
* budget;
* timeout;
* rollback;
* recovery strategy;
* pause conditions;
* cancellation conditions;
* completion conditions.

## Plan Validation

Before execution, the plan must be checked against:

* contracts;
* permissions;
* permitted operations;
* constraints;
* budget;
* dependencies;
* policies;
* resource availability;
* required validations;
* approvals;
* rollback capability;
* estimated impact.

## Replanning

A new version must be generated when:

* the goal changes;
* new information appears;
* an operation fails;
* a validation fails;
* resources change;
* permissions change;
* budget is exhausted;
* an approval is rejected;
* the real result differs significantly;
* a safer strategy is detected.

The previous version must be preserved.

## Restrictions

The Agent Runtime must not:

* edit the DAG directly;
* execute an unvalidated plan;
* skip approvals;
* add operations outside the registry;
* hide assumptions;
* continue with failed dependencies;
* consider a task completed without a structured result.

⸻

# 9.8 — Policy Engine

## Objective

Centralize authorization, safety, autonomy, and compliance decisions without scattering conditionals throughout the Runtime.

## Policy Evaluation Request

```python
PolicyEvaluationRequest(
    id="policy-request-123",
    actor_id="agent-project-maintenance",
    agent_run_id="agent-run-123",
    goal_id="goal-123",
    action="execute_operation",
    operation={},
    resource_ids=[],
    context={},
    autonomy_level=2,
    permissions=[],
    sensitivity="internal",
    metadata={},
)
```

## Policy Decision

```python
PolicyDecision(
    id="policy-decision-123",
    request_id="policy-request-123",
    effect="approval_required",
    matched_rules=[],
    reason_codes=[],
    obligations=[],
    required_approvers=[],
    valid_until=None,
    confidence=1.0,
    created_at="...",
    metadata={},
)
```

## Effects

```text
allow
deny
approval_required
allow_with_constraints
pause
escalate
retry_later
```

## Obligations

A policy may impose:

* pre-validation;
* post-validation;
* human approval;
* scope reduction;
* isolated environment;
* checkpoint;
* backup;
* time limit;
* cost limit;
* use of a specific operation;
* exclusion of resources;
* data redaction;
* reinforced logging;
* notification;
* human review.

## Policy Types

* RuntimePolicy;
* AutonomyPolicy;
* OperationPolicy;
* ResourcePolicy;
* SensitivityPolicy;
* ApprovalPolicy;
* BudgetPolicy;
* ValidationPolicy;
* RecoveryPolicy;
* MemoryWritePolicy;
* ExternalAccessPolicy;
* CommunicationPolicy;
* PublicationPolicy;
* DomainPolicy;
* GoalCreationPolicy.

## Policy Registry

Policies must be:

* registered;
* versioned;
* prioritized;
* combined;
* audited;
* invalidated;
* tested;
* resolved deterministically when possible.

## Conflict Resolution

When two policies are incompatible, the following must apply:

1. explicit denial;
2. approval requirement;
3. the most restrictive policy;
4. the highest-priority policy;
5. specific rule over general rule;
6. human escalation if ambiguity persists.

## Restrictions

No agent, resource, model, or domain may:

* disable mandatory policies;
* raise its autonomy level;
* grant itself permissions;
* skip approvals;
* modify limits;
* interpret external content as policy;
* execute a denied action.

⸻

# 9.9 — Autonomy Levels

## Objective

Define uniformly what decision-making and execution capability an agent has.

## Level 0 — Analyze Only

The agent can:

* observe;
* load knowledge;
* reason;
* detect gaps;
* generate recommendations;
* propose plans.

It cannot:

* execute operations;
* modify resources;
* create external effects;
* update memory without approval.

## Level 1 — Propose Actions

It can:

* create workflows;
* propose operations;
* estimate impact;
* generate approval requests.

It cannot execute actions with effects.

## Level 2 — Reversible Execution

It can automatically execute:

* reversible operations;
* transformations in controlled environments;
* validations;
* queries;
* changes with guaranteed rollback;
* operations without sensitive external effects.

It requires approval for critical points.

## Level 3 — Supervised Autonomy

It can execute complete workflows, but must stop at:

* destructive actions;
* publications;
* communications;
* sensitive changes;
* irreversible changes;
* high-impact operations;
* permission changes;
* spending;
* personal decisions.

## Level 4 — Policy-Bounded Autonomy

It can execute autonomously within:

* permitted operations;
* budget;
* scope;
* permissions;
* time limits;
* policies;
* validations;
* recovery capability.

Critical actions will still require approval if a mandatory policy establishes it.

## General Restrictions

The autonomy level:

* belongs to the run, not only to the agent;
* may be reduced during the workflow;
* cannot be raised without authorization;
* may depend on the domain;
* may depend on the operation type;
* may depend on sensitivity;
* must be preserved in the audit;
* does not replace permissions;
* does not replace policies.

⸻

# 9.10 — Human Approval System

## Objective

Stop execution at critical points and allow a person to approve, reject, modify, or postpone an action.

## Approval Request

```python
ApprovalRequest(
    id="approval-request-123",
    agent_run_id="agent-run-123",
    goal_id="goal-123",
    workflow_id="workflow-123",
    operation_id="operation-456",
    title="Approve public API modification",
    description="...",
    reason_codes=[],
    risk_level="high",
    expected_effects=[],
    possible_side_effects=[],
    rollback_available=True,
    rollback_description="...",
    requested_by="agent-project-maintenance",
    required_approvers=["actor-user"],
    expires_at=None,
    status="pending",
    created_at="...",
    metadata={},
)
```

## Approval Decision

```python
ApprovalDecision(
    id="approval-decision-123",
    request_id="approval-request-123",
    decision="approved_with_changes",
    actor_id="actor-user",
    conditions=[],
    modified_parameters={},
    comment=None,
    created_at="...",
    metadata={},
)
```

## States

```text
pending
approved
approved_with_changes
rejected
expired
cancelled
superseded
```

## Actions Requiring Mandatory Approval

* data deletion;
* destructive actions;
* irreversible changes;
* publication;
* sending communications;
* creating commitments;
* permission modification;
* access to restricted data;
* use of external models with sensitive data;
* economic spending;
* contracting;
* payments;
* medical decisions;
* legal decisions;
* financial decisions;
* production modifications;
* security changes;
* sensitive memory updates;
* autonomy escalation;
* disabling validations;
* actions without rollback when relevant risk exists.

## Rejection

When an approval is rejected, the Runtime must:

* record the decision;
* not execute the action;
* determine whether it can replan;
* propose alternatives;
* pause or finish;
* not request exactly the same thing again without relevant changes.

## Approval with Changes

The system must:

* validate modified parameters;
* re-evaluate policies;
* recalculate budget;
* update the plan;
* preserve the previous version;
* execute only within the approved conditions.

⸻

# 9.11 — Action Budget

## Objective

Limit resources, time, iterations, operations, questions, and external calls during an autonomous run.

## Action Budget

```python
ActionBudget(
    id="budget-123",
    agent_run_id="agent-run-123",
    maximum_iterations=20,
    maximum_operations=50,
    maximum_workflows=5,
    maximum_replans=5,
    maximum_retries=3,
    maximum_questions=10,
    maximum_external_calls=20,
    maximum_model_calls=30,
    maximum_tokens=None,
    maximum_cost=None,
    maximum_duration_seconds=3600,
    maximum_parallel_operations=2,
    maximum_memory_writes=10,
    used={},
    reserved={},
    status="active",
    metadata={},
)
```

## Budget Status

```text
active
warning
exhausted
paused
increased
completed
cancelled
```

## Controlled Resources

* iterations;
* operations;
* workflows;
* plans;
* replans;
* retries;
* questions;
* external calls;
* model calls;
* tokens;
* cost;
* time;
* concurrency;
* storage;
* memory writes;
* observations;
* loaded resources;
* data volume.

## Budget Reservation

Before an operation, the Runtime must reserve budget.

```python
BudgetReservation(
    id="reservation-123",
    budget_id="budget-123",
    resource_type="operation",
    amount=1,
    operation_id="operation-123",
    status="reserved",
    expires_at="...",
    metadata={},
)
```

The reservation must:

* be confirmed on execution;
* be released on cancellation;
* be accounted for on failures;
* avoid race conditions;
* be preserved in the audit.

## Exhaustion

When the budget is close to exhaustion:

* emit a warning;
* reduce scope;
* prioritize critical tasks;
* avoid new searches;
* avoid low-value retries;
* propose a pause;
* request an increase when appropriate.

When it is exhausted:

* stop new operations;
* preserve state;
* evaluate partial results;
* generate a report;
* request an increase;
* pause or finish partially.

## Restrictions

An agent may not:

* increase its budget;
* hide consumption;
* split operations to avoid limits;
* restart a run to bypass restrictions;
* omit failed costs;
* continue after exhaustion without authorization.

⸻

# 9.12 — Agent Runtime Loop

## Objective

Execute the autonomous cycle through an explicit, persistent, resumable state machine.

## Operational Cycle

```text
Load Goal
↓
Validate Goal
↓
Check Dependencies
↓
Observe
↓
Load Knowledge
↓
Reason
↓
Resolve Information Gaps
↓
Decide
↓
Plan
↓
Evaluate Policies
↓
Request Approval if Required
↓
Reserve Budget
↓
Execute
↓
Validate
↓
Evaluate Outcome
↓
Update Goal
↓
Update Knowledge
↓
Continue / Recover / Complete
```

## Runtime State Machine

Initial transitions:

```text
created → initializing
initializing → observing
observing → reasoning
reasoning → waiting_for_user
reasoning → waiting_for_resource
reasoning → planning
reasoning → completed
planning → waiting_for_approval
planning → executing
executing → validating
validating → evaluating
evaluating → observing
evaluating → completed
evaluating → recovering
recovering → planning
recovering → executing
recovering → paused
recovering → failed
```

## Iteration

```python
AgentIteration(
    id="iteration-123",
    agent_run_id="agent-run-123",
    number=3,
    status="completed",
    observation_snapshot_id="observation-123",
    reasoning_result_id="reasoning-456",
    runtime_decision_id="decision-789",
    workflow_plan_id="plan-321",
    workflow_execution_id="execution-654",
    validation_result_ids=[],
    outcome_evaluation_id="evaluation-987",
    started_at="...",
    completed_at="...",
    metadata={},
)
```

## Idempotency

Resumption must not duplicate:

* completed operations;
* approvals;
* questions;
* memory updates;
* events;
* budget reservations;
* checkpoints;
* validations.

Every operation must use idempotency identifiers whenever possible.

## Locks

Locks must exist to prevent:

* two agents modifying the same incompatible resource;
* two runs of the same goal;
* unsafe concurrent writes;
* rollback while execution continues;
* simultaneous completion;
* duplicated budget consumption.

## Heartbeat

Long-running executions must record:

* last activity;
* status;
* current task;
* lock;
* budget;
* next action;
* runtime health.

Abandoned executions may be detected and recovered.

⸻

# 9.13 — Operation Selection and Execution Adapter

## Objective

Select and execute existing operations without allowing the agent to invoke arbitrary commands.

## Agent Operation Request

```python
AgentOperationRequest(
    id="agent-operation-request-123",
    agent_run_id="agent-run-123",
    workflow_id="workflow-123",
    task_id="task-123",
    operation_name="python.replace_method",
    parameters={},
    expected_effects=[],
    constraints=[],
    permissions=[],
    idempotency_key="...",
    metadata={},
)
```

## Operation Registry

The agent may only select registered operations.

Each operation must declare:

* name;
* version;
* description;
* inputs;
* outputs;
* effects;
* reversibility;
* risks;
* permissions;
* sensitivity;
* validations;
* timeout;
* cost;
* idempotency;
* rollback;
* compatible environments.

## Operation Capability

```python
OperationCapability(
    operation_name="python.replace_method",
    allowed=True,
    constraints=[],
    requires_approval=False,
    maximum_uses=5,
    metadata={},
)
```

## Execution Adapter

```python
class AgentExecutionAdapter:
    def execute(
        self,
        request: AgentOperationRequest,
    ) -> OperationResult:
        ...
```

The adapter will delegate to the existing Execution Engine.

## Before Execution

The Runtime must check:

* registered operation;
* valid parameters;
* permissions;
* autonomy;
* policies;
* approval;
* budget;
* dependencies;
* environment;
* checkpoint;
* rollback capability;
* preconditions;
* resource version;
* absence of incompatible locks.

## After Execution

It must:

* capture structured result;
* record effects;
* detect changes;
* consume budget;
* save artifacts;
* run validations;
* emit events;
* update the workflow;
* decide the next step.

## Restrictions

The agent may not:

* execute arbitrary shell unless through an explicitly authorized operation;
* build destructive commands;
* bypass the Operation Registry;
* modify parameters after approval;
* declare an operation reversible if it is not;
* hide side effects;
* execute outside the authorized environment.

# 9.14 — Validation Integration

## Objective

Systematically validate operation results through the Phase 7 Validation System.

## Validation Requirement

```python
ValidationRequirement(
    id="validation-requirement-123",
    operation_id="operation-123",
    policy="project-structural-change",
    timing="after",
    required=True,
    blocking=True,
    selected_steps=[],
    metadata={},
)
```

## Validation Moments

```text
before
after
checkpoint
workflow_end
goal_end
on_recovery
```

## Flow

```text
Operation Result
↓
Detect Changes
↓
Select Validation Policy
↓
Run Validation
↓
Interpret Structured Result
↓
Pass / Warn / Fail
↓
Continue / Retry / Replan / Rollback
```

## Rules

* blocking validations must prevent continuation;
* warnings must be preserved;
* the agent must not interpret only free-form logs;
* results must be linked to the operation;
* structural changes must use stricter policies;
* the goal cannot be completed with pending mandatory validations;
* the commit gate must be respected;
* an expired validation must be repeated if state changed.

## Validation Decision

```python
AgentValidationDecision(
    id="validation-decision-123",
    validation_result_id="validation-result-123",
    decision="rollback",
    blocking_findings=[],
    warnings=[],
    reason_codes=[],
    metadata={},
)
```

Decisions:

```text
continue
continue_with_warning
retry_operation
replan
rollback
pause
escalate
fail
```

## Restrictions

The agent may not:

* modify the validation result;
* ignore blocking errors;
* reduce the policy after a failure without authorization;
* mark a validation as passed;
* approve its own change when human review is required;
* create unsafe commits.

⸻

# 9.15 — Checkpoints and Transaction Boundaries

## Objective

Create safe recovery points before relevant operations or groups of operations.

## Checkpoint

```python
Checkpoint(
    id="checkpoint-123",
    agent_run_id="agent-run-123",
    workflow_id="workflow-123",
    name="before-public-api-change",
    resource_versions={},
    git_state={},
    storage_snapshot_id=None,
    memory_state_version=None,
    reversible_operations=[],
    created_at="...",
    status="active",
    metadata={},
)
```

## Checkpoint Status

```text
creating
active
restored
expired
invalid
deleted
failed
```

## Transaction Boundary

A workflow may group operations into:

* atomic transaction;
* compensable transaction;
* sequence with checkpoints;
* independent operations;
* irreversible operation with approval.

## Requirements

Before a risky operation, the Runtime must determine:

* which resources may change;
* whether rollback exists;
* whether a backup is needed;
* whether state can be restored;
* which external effects are not reversible;
* which validations must run;
* what authorization is required.

## Restoration

Restoration must:

* check checkpoint integrity;
* stop concurrent executions;
* revert operations;
* validate restored state;
* record differences;
* emit events;
* update the workflow;
* preserve the original failure.

⸻

# 9.16 — Recovery Manager

## Objective

Manage failures through explicit, configurable, and auditable strategies.

## Recovery Context

```python
RecoveryContext(
    id="recovery-context-123",
    agent_run_id="agent-run-123",
    goal_id="goal-123",
    workflow_id="workflow-123",
    failed_task_id="task-123",
    failed_operation_id="operation-123",
    error={},
    validation_results=[],
    retry_history=[],
    checkpoints=[],
    remaining_budget={},
    side_effects=[],
    metadata={},
)
```

## Recovery Decision

```python
RecoveryDecision(
    id="recovery-decision-123",
    strategy="replan",
    reason_codes=[],
    confidence=0.87,
    requires_approval=False,
    checkpoint_id=None,
    delay_seconds=None,
    modified_constraints=[],
    metadata={},
)
```

## Strategies

```text
retry
retry_with_modified_parameters
retry_later
reobserve
reload_resource
rerun_validation
replan
rollback
compensate
ask_user
request_approval
escalate
pause
skip_optional_task
complete_partially
abort
fail
```

## Retry Policy

```python
RetryPolicy(
    maximum_attempts=3,
    retryable_errors=[],
    non_retryable_errors=[],
    backoff_strategy="exponential",
    initial_delay_seconds=1,
    maximum_delay_seconds=60,
    jitter=True,
    require_reobservation_after=[],
    metadata={},
)
```

## Replan Policy

Replanning must consider:

* failure;
* current state;
* partial changes;
* remaining budget;
* executed operations;
* validations;
* new knowledge;
* constraints;
* approvals;
* risks;
* checkpoints.

## Rollback Policy

```python
RollbackPolicy(
    automatic_for=[],
    approval_required_for=[],
    prohibited_for=[],
    validate_after_rollback=True,
    preserve_artifacts=True,
    metadata={},
)
```

## Escalation

The system must escalate when:

* no safe strategy exists;
* permission is missing;
* rollback fails;
* potential damage exists;
* an inconsistent state is detected;
* retries are exhausted;
* budget is exhausted;
* a high-impact decision appears;
* a contradiction cannot be resolved;
* the result requires professional judgment;
* policies conflict.

## Restrictions

The Recovery Manager must not:

* retry indefinitely;
* hide failures;
* delete evidence;
* revert non-reversible external effects;
* retry non-retryable errors;
* change success criteria;
* expand scope;
* elevate permissions;
* continue from an inconsistent state.

⸻

# 9.17 — Outcome Evaluation

## Objective

Determine whether the real result satisfies the goal and its success criteria.

## Outcome Evaluation

```python
OutcomeEvaluation(
    id="outcome-evaluation-123",
    goal_id="goal-123",
    agent_run_id="agent-run-123",
    status="completed",
    outcome="partial_success",
    criterion_results=[],
    expected_state={},
    actual_state={},
    validations=[],
    evidence=[],
    side_effects=[],
    regressions=[],
    generated_debt=[],
    acquired_knowledge=[],
    remaining_gaps=[],
    remaining_tasks=[],
    confidence=0.88,
    recommended_decision="replan",
    created_at="...",
    metadata={},
)
```

## Outcome

Initial values:

```text
success
partial_success
no_change
failure
regression
inconclusive
cancelled
```

## Evaluation

The system must compare:

* goal;
* success criteria;
* previous state;
* current state;
* operation results;
* validations;
* metrics;
* side effects;
* risks;
* generated debt;
* acquired knowledge;
* pending information;
* user confirmation when necessary.

## Completion Decision

```python
GoalCompletionDecision(
    goal_id="goal-123",
    decision="continue",
    satisfied_criteria=[],
    unsatisfied_criteria=[],
    waived_criteria=[],
    evidence=[],
    confidence=0.91,
    requires_user_confirmation=False,
    metadata={},
)
```

Decisions:

```text
complete
complete_partially
continue
retry
replan
rollback
pause
escalate
fail
```

## Rules

* finishing a workflow does not imply satisfying the goal;
* a technically correct result may not satisfy the user;
* an unsatisfied mandatory criterion prevents completion;
* relevant warnings must be preserved;
* generated debt must be recorded;
* side effects must be evaluated;
* evaluation must be reproducible;
* uncertainty must be reflected.

⸻

# 9.18 — Knowledge and Memory Update

## Objective

Update knowledge and memory from autonomous results without automatically storing irrelevant, incorrect, or sensitive data.

## Agent Knowledge Update Proposal

```python
AgentKnowledgeUpdateProposal(
    id="agent-knowledge-proposal-123",
    agent_run_id="agent-run-123",
    goal_id="goal-123",
    additions=[],
    updates=[],
    invalidations=[],
    relations=[],
    operation_facts=[],
    decisions=[],
    lessons=[],
    rejected_items=[],
    requires_approval=False,
    confidence=0.9,
    reasons=[],
    metadata={},
)
```

## Knowledge Candidates

* created goal;
* completed goal;
* operation result;
* validated state;
* structural change;
* decision;
* constraint;
* explicit preference;
* reproducible error;
* failed strategy;
* successful strategy;
* dependency;
* contradiction;
* technical debt;
* generated artifact;
* new capability;
* updated resource.

## Operational Lesson

```python
OperationalLesson(
    id="lesson-123",
    statement="Operation X fails when Y",
    kind="failure_pattern",
    evidence=[],
    scope={},
    confidence=0.86,
    reusable=True,
    expiration=None,
    metadata={},
)
```

Initial types:

* success_pattern;
* failure_pattern;
* recovery_pattern;
* environment_constraint;
* tool_limitation;
* validation_requirement;
* dependency_behavior;
* user_preference;
* workflow_optimization.

## Rules

The following must not be persisted automatically:

* internal reasoning;
* trivial attempts;
* weak hypotheses;
* secrets;
* temporary data with no utility;
* unreproduced errors;
* invalidated results;
* inferred preferences;
* unconfirmed personal decisions;
* information outside permissions;
* duplicate content.

## Memory Update

Writing must pass through:

* memory policy;
* permissions;
* deduplication;
* versioning;
* confidence evaluation;
* sensitivity;
* confirmation when appropriate.

The agent will not write directly to memory tables.

⸻

# 9.19 — Agent Runtime Trace

## Objective

Produce structured traceability for autonomous execution without storing free-form internal chains of thought.

## Agent Trace

```python
AgentTrace(
    id="agent-trace-123",
    agent_run_id="agent-run-123",
    goal_id="goal-123",
    agent_id="agent-project-maintenance",
    iterations=[],
    observations=[],
    reasoning_result_ids=[],
    runtime_decisions=[],
    plans=[],
    policy_decisions=[],
    approval_requests=[],
    approval_decisions=[],
    operations=[],
    validations=[],
    recovery_decisions=[],
    outcome_evaluations=[],
    knowledge_updates=[],
    budget_events=[],
    warnings=[],
    errors=[],
    started_at="...",
    completed_at="...",
    duration_ms=82000,
    metadata={},
)
```

## Must Make It Possible to Answer

* what goal was being pursued;
* who created it;
* which agent was assigned;
* what autonomy level it had;
* what it observed;
* what knowledge it loaded;
* what cognitive profile it used;
* what information was missing;
* what questions it asked;
* what plan it created;
* what policies were applied;
* what approvals it requested;
* who approved;
* what operations it executed;
* what resources it modified;
* what validations it performed;
* what failed;
* what it retried;
* what it replanned;
* what rollback it executed;
* what budget it consumed;
* why it continued;
* why it stopped;
* whether it satisfied the goal;
* what knowledge it updated.

## Restrictions

The trace must not store:

* token-by-token chains of thought;
* private prompts;
* credentials;
* secrets;
* unnecessary sensitive content;
* data outside permissions;
* information unrelated to the goal.

⸻

# 9.20 — Runtime Event Bus

## Objective

Emit structured events to decouple the Agent Runtime from the UI, observability, n8n, other agents, and future multi-agent capabilities.

## Goal Events

```text
agent.goal.proposed
agent.goal.accepted
agent.goal.activated
agent.goal.assigned
agent.goal.blocked
agent.goal.paused
agent.goal.resumed
agent.goal.completed
agent.goal.partially_completed
agent.goal.failed
agent.goal.cancelled
agent.goal.superseded
```

## Execution Events

```text
agent.run.created
agent.run.started
agent.run.iteration.started
agent.run.iteration.completed
agent.run.paused
agent.run.resumed
agent.run.completed
agent.run.failed
agent.run.aborted
```

## Observation Events

```text
agent.observation.started
agent.observation.completed
agent.observation.change_detected
agent.observation.failed
```

## Cognitive Events

```text
agent.reasoning.started
agent.reasoning.completed
agent.gap.detected
agent.question.requested
agent.resource.requested
agent.reasoning.blocked
```

## Planning Events

```text
agent.plan.created
agent.plan.validated
agent.plan.rejected
agent.plan.revised
agent.plan.started
agent.plan.completed
```

## Policy and Approval Events

```text
agent.policy.allowed
agent.policy.denied
agent.approval.requested
agent.approval.approved
agent.approval.rejected
agent.approval.expired
```

## Execution and Validation Events

```text
agent.operation.started
agent.operation.completed
agent.operation.failed
agent.validation.started
agent.validation.passed
agent.validation.failed
```

## Recovery Events

```text
agent.recovery.started
agent.retry.started
agent.replan.started
agent.rollback.started
agent.rollback.completed
agent.escalation.requested
agent.recovery.failed
```

## Knowledge Events

```text
agent.knowledge.proposed
agent.knowledge.updated
agent.memory.proposed
agent.memory.updated
agent.lesson.created
```

## Requirements

Events must have:

* identifier;
* version;
* timestamp;
* actor;
* goal;
* run;
* structured payload;
* sensitivity;
* correlation;
* causation;
* idempotency key;
* retention policy.

Consumers must not modify Runtime state directly without using authorized commands.

⸻

# 9.21 — Persistence and Resumption

## Objective

Persist goals and executions to enable prolonged autonomous cycles, pauses, and recovery after restarts.

## Agent Run Repository

It must persist:

* AgentDefinition;
* AgentRun;
* Goal;
* GoalHistory;
* ObservationSnapshot;
* AgentIteration;
* RuntimeDecision;
* WorkflowPlan;
* PolicyDecision;
* ApprovalRequest;
* ApprovalDecision;
* ActionBudget;
* BudgetReservation;
* Checkpoint;
* RecoveryDecision;
* OutcomeEvaluation;
* AgentResult;
* AgentTrace.

## Resume Context

```python
AgentResumeContext(
    agent_run_id="agent-run-123",
    status="paused",
    goal_id="goal-123",
    last_completed_iteration=3,
    current_workflow_id="workflow-123",
    current_task_id="task-456",
    pending_questions=[],
    pending_approvals=[],
    active_reservations=[],
    active_locks=[],
    latest_checkpoint_id="checkpoint-123",
    remaining_budget={},
    next_recommended_action="resume_validation",
    metadata={},
)
```

## On Resumption

The Runtime must:

* recover the goal;
* check that it is still active;
* recover the last consistent state;
* check permissions;
* check policies;
* check approvals;
* check budget;
* check locks;
* check modified resources;
* check observation validity;
* revalidate temporal knowledge;
* detect external changes;
* invalidate obsolete plans;
* decide whether to continue, reobserve, or replan;
* avoid duplicated operations;
* record the resumption.

## Recovery After Crash

The system must be able to distinguish:

* operation not started;
* operation started without result;
* operation completed without persistence;
* pending validation;
* pending approval;
* incomplete rollback;
* orphaned budget reservation;
* orphaned lock.

⸻

# 9.22 — Scheduling and Triggering

## Objective

Allow agents and goals to be activated by commands, events, or schedules without turning the Runtime into an independent scheduler.

## Initial Triggers

* manual;
* API;
* CLI;
* Kernel event;
* schedule;
* recurring schedule;
* authorized webhook;
* validation failure;
* repository change;
* goal dependency completed;
* resource updated;
* approval received;
* user response;
* system health event.

## Agent Trigger

```python
AgentTrigger(
    id="trigger-123",
    kind="kernel_event",
    agent_id="agent-project-maintenance",
    goal_template_id="goal-template-123",
    condition={},
    cooldown_seconds=3600,
    enabled=True,
    permissions=[],
    metadata={},
)
```

## Duplicate Execution Prevention

The system must:

* group equivalent events;
* use cooldown;
* detect similar active goals;
* reuse runs;
* apply locks;
* avoid event storms;
* limit frequency;
* apply budget.

## Recurring Goals

A recurring goal must create independent runs related to a common definition.

It must not reuse the same result as if it were a new run.

⸻

# 9.23 — Agent Registry and Agent Factory

## Objective

Register agents as reusable configurations without creating incompatible implementations.

## Agent Registry

```python
class AgentRegistry:
    def register(
        self,
        definition: AgentDefinition,
    ) -> AgentDefinition:
        ...

    def get(
        self,
        agent_id: str,
    ) -> AgentDefinition | None:
        ...

    def resolve(
        self,
        request: AgentResolutionRequest,
    ) -> AgentResolutionResult:
        ...
```

## Agent Resolution

Selection may consider:

* goal type;
* domain;
* required operations;
* cognitive profile;
* autonomy level;
* sensitivity;
* permissions;
* availability;
* load;
* budget;
* required tools;
* success history.

## Agent Factory

The factory must build a run by combining:

* AgentDefinition;
* RuntimePolicy;
* ReasoningProfile;
* ObservationProfile;
* BudgetPolicy;
* ApprovalPolicy;
* RecoveryPolicy;
* OperationCapabilities;
* permissions;
* goal context.

It must not create new runtime classes per agent.

## Initial Agents

### GeneralAgent

Capabilities:

* analysis;
* planning;
* coordination;
* questions;
* limited execution.

### ProjectAgent

Capabilities:

* observe repository;
* detect debt;
* plan changes;
* execute semantic operations;
* validate;
* update documentation and knowledge.

### MaintenanceAgent

Capabilities:

* detect duplication;
* detect dead code;
* detect inconsistencies;
* propose corrections;
* execute reversible maintenance.

### DocumentationAgent

Capabilities:

* compare code and documentation;
* detect outdated documentation;
* propose or perform updates;
* validate references.

These agents will be initial configurations, not independent architectures.

⸻

# 9.24 — Agent-to-Agent Boundaries

## Objective

Prepare the system for future multi-agent coordination without yet implementing a complete multi-agent architecture.

In Phase 9, an agent may:

* propose delegation;
* create a subgoal;
* assign it to another registered agent;
* wait for its result;
* incorporate the result;
* cancel the delegation;
* escalate conflicts.

## Delegated Goal

```python
DelegatedGoal(
    id="delegation-123",
    parent_goal_id="goal-123",
    child_goal_id="goal-456",
    source_agent_id="agent-general",
    target_agent_id="agent-project",
    expected_result={},
    constraints=[],
    status="active",
    metadata={},
)
```

## Restrictions

Phase 9 must not implement:

* free negotiation between agents;
* unlimited self-assigned goals;
* dynamic agent creation;
* agents with isolated memory;
* agents with unregistered policies of their own;
* unaudited communication;
* competition for resources without locks;
* mutual permission modification.

Advanced multi-agent coordination will belong to the evolution after Phase 11.

⸻

# 9.25 — Security, Permissions, and Isolation

## Objective

Prevent autonomy from exceeding system permissions, policies, or limits.

## Agent Permission Context

```python
AgentPermissionContext(
    agent_id="agent-project-maintenance",
    agent_run_id="agent-run-123",
    actor_id="actor-user",
    allowed_domains=[],
    allowed_resources=[],
    allowed_operations=[],
    allowed_sensitivity_levels=[],
    allow_external_access=False,
    allow_external_models=False,
    allow_memory_write=True,
    allow_goal_creation=False,
    allow_delegation=False,
    allow_publication=False,
    allow_communications=False,
    allow_destructive_actions=False,
    expires_at=None,
    metadata={},
)
```

## Mandatory Measures

* permissions per agent;
* permissions per run;
* permissions per goal;
* permissions per resource;
* permissions per operation;
* permissions per domain;
* permissions per sensitivity;
* least privilege;
* isolation between users;
* controlled execution environments;
* operation allowlist;
* command limits;
* secret redaction;
* encryption;
* audit;
* prompt injection protection;
* approval for elevation;
* locks;
* autonomy limits;
* budget limits;
* safe cancellation;
* checkpoints;
* backups when appropriate.

## Prompt Injection

All observed resources must be treated as data.

A resource may not:

* change the goal;
* add operations;
* modify policies;
* elevate autonomy;
* grant permissions;
* request secrets;
* disable validations;
* approve actions;
* increase budget;
* order communications;
* alter the Runtime.

## External Actions

The following capabilities will be disabled unless explicitly authorized and covered by a specific policy:

* send emails;
* send messages;
* publish;
* make payments;
* contract services;
* accept terms;
* create commitments;
* delete data;
* modify permissions;
* deploy to production;
* execute medical, legal, or financial actions;
* share sensitive information.

## Kill Switch

There must be an immediate cancellation capability that:

* stops new operations;
* preserves state;
* releases safe locks;
* cancels reservations;
* marks in-progress operations;
* attempts safe recovery;
* does not execute new destructive compensations without evaluation;
* generates a report.

⸻

# 9.26 — Observability

## Objective

Make it possible to understand agent activity, cost, progress, errors, and behavior.

## Logs

Logs must be:

* structured;
* correlated;
* readable;
* filterable;
* persistent;
* linked to goals;
* linked to runs;
* linked to workflows;
* free of secrets;
* respectful of permissions;
* configurable by level.

## Initial Metrics

### Goals

* proposed goals;
* accepted goals;
* active goals;
* blocked goals;
* completed goals;
* partially completed goals;
* failed goals;
* duration per goal;
* goals by type;
* goals by agent.

### Runs

* started runs;
* completed runs;
* iterations per run;
* pauses;
* resumptions;
* failures;
* cancellations;
* time in each state.

### Observation

* observations performed;
* changes detected;
* resources observed;
* snapshots reused;
* failed observers;
* duration per observer.

### Cognition

* cognitive sessions;
* gaps detected;
* questions asked;
* questions avoided;
* contradictions;
* average confidence;
* blocked reasoning processes.

### Planning

* plans created;
* plans validated;
* plans rejected;
* replans;
* tasks per plan;
* DAG depth.

### Execution

* operations;
* successful operations;
* failed operations;
* operations by type;
* duration per operation;
* side effects;
* locks;
* conflicts.

### Validation

* validations;
* passed validations;
* failed validations;
* blocking findings;
* rollbacks by validation.

### Recovery

* retries;
* replans;
* rollbacks;
* escalations;
* successful recoveries;
* recovery failures.

### Budget

* consumed operations;
* external calls;
* model calls;
* duration;
* cost;
* exhausted budgets;
* requested increases.

### Approvals

* requests;
* approvals;
* rejections;
* expirations;
* waiting time;
* modified approvals.

## Health Checks

The Runtime must expose:

* status;
* goal queue;
* active runs;
* locks;
* budgets;
* pending approvals;
* recent failures;
* available observers;
* available operations;
* Planner status;
* Executor status;
* Validation System status;
* Cognitive Layer status.

⸻

# 9.27 — CLI and API

## CLI

Initial commands:

```text
cmm agent list
cmm agent inspect <agent-id>
cmm agent enable <agent-id>
cmm agent disable <agent-id>

cmm goal create
cmm goal list
cmm goal inspect <goal-id>
cmm goal activate <goal-id>
cmm goal pause <goal-id>
cmm goal resume <goal-id>
cmm goal cancel <goal-id>
cmm goal history <goal-id>
cmm goal evaluate <goal-id>

cmm agent run <agent-id> --goal <goal-id>
cmm agent run inspect <run-id>
cmm agent run pause <run-id>
cmm agent run resume <run-id>
cmm agent run cancel <run-id>
cmm agent run trace <run-id>

cmm agent observe <run-id>
cmm agent plan <run-id>
cmm agent budget <run-id>
cmm agent approvals
cmm agent approve <approval-id>
cmm agent reject <approval-id>
cmm agent checkpoints <run-id>
cmm agent rollback <run-id> --checkpoint <checkpoint-id>
cmm agent outcome <run-id>
```

## CLI Capabilities

* register goals;
* list goals;
* inspect dependencies;
* assign agents;
* start runs;
* select autonomy;
* select budget;
* observe;
* reason;
* plan;
* execute;
* pause;
* resume;
* cancel;
* approve;
* reject;
* review operations;
* review validations;
* review budget;
* inspect traces;
* inspect results;
* human-readable output;
* JSON output;
* verbose mode;
* dry-run mode;
* proposal-only mode.

## API

The API must allow:

* register agents;
* query agents;
* enable agents;
* create goals;
* query goals;
* update goals;
* activate;
* pause;
* resume;
* cancel;
* query dependencies;
* assign agents;
* start runs;
* query status;
* obtain observations;
* obtain reasoning results;
* obtain plans;
* query workflows;
* query operations;
* query validations;
* answer questions;
* approve actions;
* reject actions;
* increase budget;
* query checkpoints;
* request rollback;
* obtain evaluations;
* obtain results;
* obtain traces;
* configure policies;
* configure autonomy;
* configure permissions;
* configure triggers;
* integrate with UI and n8n.

## Contracts

The CLI and API must use the same internal contracts.

There must be no incompatible states between:

* CLI;
* API;
* UI;
* workflows;
* Kernel;
* agents;
* domains.

⸻

# 9.28 — Integration with the Existing System

## Kernel

The Agent Runtime must use the Kernel for:

* commands;
* events;
* identifiers;
* actors;
* permissions;
* timestamps;
* correlation;
* persistence;
* errors;
* cancellation.

The Kernel must not implement agent logic.

## Cognitive Layer

The agent must use it to:

* load knowledge;
* select profiles;
* reason;
* detect gaps;
* formulate questions;
* detect contradictions;
* check temporal scope;
* evaluate confidence;
* generate traceability;
* propose updates.

It must not duplicate any of these capabilities.

## Planner

The agent must use it to:

* create workflows;
* build DAG;
* resolve dependencies;
* define tasks;
* define operations;
* define validations;
* define checkpoints;
* replan.

The Runtime must decide when to plan, but not how to internally build the DAG.

## Execution Engine

The agent must use it to:

* execute operations;
* handle transactions;
* obtain structured results;
* use idempotency;
* apply rollback;
* manage effects.

## Semantic Engine

The agent may use:

* structural searches;
* references;
* impact;
* transformations;
* Python operations;
* semantic operations;
* indexes;
* symbol location.

## Validation System

The agent must use:

* policies;
* steps;
* results;
* findings;
* commit gate;
* before and after validations;
* affected validations;
* full suite when appropriate.

## Memory

The agent may:

* retrieve goals;
* retrieve decisions;
* retrieve preferences;
* retrieve sessions;
* retrieve results;
* propose updates;
* persist authorized knowledge;
* invalidate obsolete knowledge through contracts.

## Workflow System

The Runtime must:

* create runs;
* start;
* pause;
* resume;
* cancel;
* obtain results;
* detect blocked tasks;
* react to events;
* preserve versions.

## Future Domain Intelligence

Phase 10 domains must provide:

* AgentDefinition;
* ReasoningProfile;
* ObservationProfile;
* DomainOperations;
* DomainPermissions;
* RuntimePolicy;
* ApprovalPolicy;
* RecoveryPolicy;
* GoalTemplates;
* Workflows.

They must not create an independent Runtime.

⸻


# 9.29 — Model Requirements per Operation

## Status

This section defines a **post-publication extension** of Phase 9.

The original Phase 9 implementation remains complete, audited, and published. These contracts prepare the Agent Runtime for the multimodel routing, evaluation, privacy, and cost infrastructure implemented later in Phase 11.

## Objective

Allow every model-assisted operation in a workflow to declare its execution requirements without selecting or coupling itself to a concrete provider.

## Model Requirements

```python
ModelRequirements(
    capability="reasoning",
    minimum_quality="high",
    maximum_cost_eur=0.05,
    latency="normal",
    context_length="long",
    privacy="LOCAL_PREFERRED",
    structured_output=True,
    tool_calling=True,
    premium_allowed=True,
    preferred_providers=[],
    excluded_providers=[],
    required_modalities=[],
    metadata={},
)
```

## Supported Factors

* required capability;
* operation complexity;
* minimum quality;
* maximum estimated cost;
* acceptable latency;
* required context length;
* privacy policy;
* structured-output requirement;
* tool-calling requirement;
* multimodal requirements;
* premium escalation permission;
* preferred providers;
* excluded providers;
* local-processing requirement;
* model availability constraints.

## Integration

Requirements may be declared by:

* an operation;
* a workflow node;
* a workflow policy;
* a goal;
* an agent definition;
* a domain policy from Phase 10;
* a privacy policy;
* an approval decision.

The effective requirements must be resolved without weakening any inherited privacy, permission, budget, or quality constraint.

## Restrictions

An operation must not:

* select a provider directly;
* bypass the future Model Gateway;
* reduce inherited privacy requirements;
* authorize premium use by itself;
* ignore cost limits;
* declare unsupported capabilities as available.

⸻

# 9.30 — Workflow Model Fallback and Escalation Policies

## Objective

Define declarative and auditable workflow behavior when a model-assisted operation fails or produces an unacceptable result.

## Trigger Conditions

Fallback or escalation may be activated when:

* the selected model is unavailable;
* a timeout occurs;
* the response violates the required schema;
* structured output is invalid;
* tool calling is unsupported or incorrect;
* the context limit is exceeded;
* response validation fails;
* minimum quality is not reached;
* privacy policy is violated;
* the estimated or actual cost exceeds the permitted limit;
* the provider returns a retryable error.

## Fallback Policy

```python
ModelFallbackPolicy(
    id="fallback-policy-123",
    workflow_id="workflow-123",
    maximum_attempts=3,
    strategies=[
        "retry_same_model",
        "select_equivalent_model",
        "select_higher_quality_model",
        "request_premium_approval",
        "pause",
    ],
    preserve_attempt_history=True,
    require_revalidation=True,
    allow_premium_with_approval=True,
    metadata={},
)
```

## Possible Decisions

```text
retry_same_model
retry_with_reduced_context
select_equivalent_model
select_lower_cost_model
select_higher_quality_model
use_local_model
request_premium_approval
request_user_input
pause
escalate
fail
```

## Requirements

Fallback policies must be:

* declarative;
* versioned;
* auditable;
* resumable;
* bounded by the Action Budget;
* compatible with human approval;
* compatible with checkpoints;
* validated before execution;
* linked to the original operation and workflow.

Each attempt must preserve its provider, model, result, validation outcome, cost, latency, and reason for rejection.

## Restrictions

Fallback must not:

* retry indefinitely;
* bypass an explicit provider exclusion;
* reduce privacy requirements;
* exceed a hard budget;
* escalate to premium without permission;
* discard failed attempts from the audit;
* accept an invalid result merely because retries are exhausted.

⸻

# 9.31 — Economic Budgets for Goals and Workflows

## Objective

Extend the existing Action Budget with explicit economic controls for model-assisted execution.

## Economic Budget

```python
EconomicBudget(
    id="economic-budget-123",
    goal_id="goal-123",
    workflow_id="workflow-123",
    maximum_goal_cost_eur=None,
    maximum_workflow_cost_eur=1.00,
    maximum_execution_cost_eur=0.20,
    premium_reserve_eur=0.10,
    warning_threshold_percent=80,
    allow_overrun_with_approval=True,
    savings_mode=False,
    estimated_cost_eur=0.0,
    reserved_cost_eur=0.0,
    actual_cost_eur=0.0,
    status="active",
    metadata={},
)
```

## Capabilities

The Runtime must support:

* maximum cost per goal;
* maximum cost per workflow;
* maximum cost per execution;
* cost reservation before dispatch;
* accumulated estimated cost;
* accumulated actual cost;
* premium reserve;
* warning thresholds;
* hard limits;
* savings mode;
* automatic selection of lower-cost alternatives;
* approval requests for authorized overruns;
* partial completion when the budget is exhausted;
* preservation of cost history.

## Budget Decisions

```text
allow
allow_with_reservation
use_lower_cost_model
reduce_scope
enable_savings_mode
request_budget_approval
pause
complete_partially
deny
```

## Integration with Action Budget

The economic budget complements, but does not replace, limits on:

* iterations;
* operations;
* model calls;
* external calls;
* tokens;
* duration;
* retries;
* replans;
* concurrency.

A run must satisfy both operational and economic budgets.

## Restrictions

An agent or model must not:

* increase its own budget;
* hide failed-call costs;
* split calls to evade limits;
* consume the premium reserve without authorization;
* restart a run to reset accumulated cost;
* continue after a hard limit is reached.

⸻

# 9.32 — Model Execution Records

## Objective

Record every model-assisted execution in a structured form so Phase 11 can evaluate providers, calculate costs, validate routing decisions, and improve future selection.

## Model Execution Record

```python
ModelExecutionRecord(
    id="model-execution-123",
    agent_run_id="agent-run-123",
    goal_id="goal-123",
    workflow_id="workflow-123",
    task_id="task-123",
    operation_id="operation-123",
    domain=None,
    provider_id="provider-123",
    model_id="model-123",
    model_version=None,
    capability="reasoning",
    input_tokens=0,
    output_tokens=0,
    cached_tokens=0,
    estimated_cost_eur=0.0,
    actual_cost_eur=0.0,
    latency_ms=0,
    cache_used=False,
    validation_result_ids=[],
    retry_number=0,
    fallback_from=None,
    quality_evaluation=None,
    human_intervention=False,
    acceptance_status="accepted",
    created_at="...",
    metadata={},
)
```

## Required Data

Each record must preserve:

* provider;
* model;
* model version when available;
* operation;
* workflow;
* goal;
* agent run;
* domain;
* capability;
* input and output tokens;
* cached tokens;
* estimated and actual cost;
* latency;
* cache usage;
* validation results;
* retry number;
* fallback origin;
* quality assessment;
* human intervention;
* final acceptance or rejection;
* configuration and policy versions;
* correlation and trace identifiers.

## Acceptance Status

```text
pending
accepted
accepted_with_warning
rejected
repaired
regenerated
escalated
cancelled
failed
```

## Privacy

Records must preserve auditability without storing:

* secrets;
* credentials;
* unnecessary prompt contents;
* unrestricted sensitive data;
* provider responses beyond authorized retention.

Where full payload retention is prohibited, the record must preserve hashes, classifications, exclusions, and trace references instead.

## Future Use

Phase 11 will use these records for:

* provider comparison;
* routing;
* quality rankings;
* latency analysis;
* cost analysis;
* fallback evaluation;
* regression detection;
* acceptance-rate calculation;
* domain benchmark results;
* continuous provider evaluation.

⸻

# 9.33 — Implementation Order


## Block 1 — Agent Runtime Contracts

* AgentDefinition;
* AgentRun;
* AgentRuntimeStatus;
* RuntimeDecision;
* AgentResult;
* identifiers;
* serialization;
* errors;
* unit tests.

## Block 2 — Goal System

* Goal;
* GoalStatus;
* GoalKind;
* GoalPriority;
* SuccessCriterion;
* GoalConstraint;
* GoalDependency;
* GoalHistory;
* GoalRepository;
* unit tests.

## Block 3 — Goal Manager

* registration;
* normalization;
* prioritization;
* dependencies;
* subgoals;
* blocking;
* pause;
* resume;
* cancellation;
* completion;
* unit tests.

## Block 4 — Agent Registry

* AgentRegistry;
* AgentDefinition;
* AgentResolution;
* AgentFactory;
* GeneralAgent;
* ProjectAgent;
* unit tests.

## Block 5 — Observation Contracts

* ObservationRequest;
* Observation;
* ObservedChange;
* ObservationResult;
* ObservationSnapshot;
* Observer Registry;
* unit tests.

## Block 6 — Initial Observers

* RepositoryObserver;
* FilesystemObserver;
* GitObserver;
* ValidationObserver;
* MemoryObserver;
* KnowledgeObserver;
* GoalObserver;
* WorkflowObserver;
* integration tests.

## Block 7 — Cognitive Adapter

* AgentCognitiveRequest;
* AgentCognitiveResult;
* Reasoning Context creation;
* profile selection;
* resources;
* sessions;
* gap handling;
* questions;
* integration tests.

## Block 8 — Information Acquisition

* strategies;
* prioritization;
* questions;
* internal resources;
* search;
* acceptable uncertainty;
* permissions;
* unit tests.

## Block 9 — Planner Adapter

* AgentPlanningRequest;
* AgentWorkflowPlan;
* Planner integration;
* plan validation;
* versioning;
* assumptions;
* risks;
* integration tests.

## Block 10 — Policy Engine

* PolicyEvaluationRequest;
* PolicyDecision;
* Policy Registry;
* combination;
* conflicts;
* obligations;
* initial policies;
* unit tests.

## Block 11 — Autonomy Levels

* levels;
* capabilities;
* dynamic reduction;
* prohibition of elevation;
* policy integration;
* unit tests.

## Block 12 — Approval System

* ApprovalRequest;
* ApprovalDecision;
* states;
* persistence;
* approval;
* rejection;
* approval with changes;
* expiration;
* integration tests.

## Block 13 — Action Budget

* ActionBudget;
* BudgetReservation;
* consumption;
* release;
* alerts;
* exhaustion;
* increase;
* persistence;
* unit tests.

## Block 14 — Runtime State Machine

* states;
* transitions;
* AgentIteration;
* operational cycle;
* locks;
* heartbeat;
* idempotency;
* unit tests.

## Block 15 — Execution Adapter

* AgentOperationRequest;
* OperationCapability;
* Operation Registry integration;
* Executor integration;
* preconditions;
* results;
* effects;
* integration tests.

## Block 16 — Validation Integration

* ValidationRequirement;
* policy selection;
* pre-validation;
* post-validation;
* commit gate;
* decisions;
* integration tests.

## Block 17 — Checkpoints

* Checkpoint;
* creation;
* verification;
* restoration;
* transactions;
* backups;
* integration tests.

## Block 18 — Recovery Manager

* RecoveryContext;
* RecoveryDecision;
* RetryPolicy;
* ReplanPolicy;
* RollbackPolicy;
* escalation;
* pause;
* abort;
* unit tests.

## Block 19 — Outcome Evaluation

* OutcomeEvaluation;
* criterion evaluation;
* side effects;
* debt;
* completion decision;
* partial results;
* unit tests.

## Block 20 — Knowledge Update

* AgentKnowledgeUpdateProposal;
* OperationalLesson;
* Knowledge Store integration;
* memory integration;
* versioning;
* approval;
* integration tests.

## Block 21 — Runtime Events

* contracts;
* Event Bus;
* goal events;
* execution events;
* recovery events;
* correlation;
* idempotency;
* tests.

## Block 22 — Persistence and Resumption

* repositories;
* ResumeContext;
* crash recovery;
* orphaned locks;
* orphaned reservations;
* obsolete plans;
* integration tests.

## Block 23 — Triggers and Scheduling

* triggers;
* recurring goals;
* cooldown;
* deduplication;
* events;
* scheduled tasks;
* tests.

## Block 24 — Security

* permissions;
* isolation;
* Operation Registry;
* prompt injection;
* secrets;
* kill switch;
* external actions;
* limits;
* audit.

## Block 25 — Observability

* logs;
* metrics;
* health checks;
* traces;
* goals;
* runs;
* budgets;
* approvals;
* recovery.

## Block 26 — Interfaces

* CLI;
* API;
* JSON output;
* dry-run;
* proposal-only;
* approvals;
* budget;
* traces;
* results.

## Block 27 — Initial Agents

* GeneralAgent;
* ProjectAgent;
* MaintenanceAgent;
* DocumentationAgent;
* policies;
* operations;
* test goals.

## Block 28 — Final Integration

* Kernel;
* Cognitive Layer;
* Planner;
* Workflow System;
* Execution Engine;
* Semantic Engine;
* Validation System;
* Memory;
* Knowledge Store;
* E2E tests;
* documentation;
* global suite.

⸻


# Expected Capabilities
* register agents as configurations;
* register goals;
* normalize goals;
* define success criteria;
* define constraints;
* maintain persistent goals;
* prioritize goals;
* create subgoals;
* manage dependencies;
* detect duplicate goals;
* detect incompatible goals;
* assign agents;
* observe repositories;
* observe files;
* observe validations;
* observe memory;
* observe knowledge;
* detect changes;
* produce snapshots;
* load relevant knowledge;
* select cognitive profiles;
* reason about the next step;
* detect missing information;
* formulate questions;
* search resources;
* preserve uncertainty;
* create workflows;
* validate plans;
* version plans;
* replan;
* apply policies;
* resolve policy conflicts;
* limit autonomy;
* request approval;
* modify plans after conditional approval;
* manage budgets;
* reserve budget;
* detect exhaustion;
* execute registered operations;
* prevent arbitrary commands;
* execute reversible operations;
* use checkpoints;
* validate before and after;
* stop on blocking errors;
* retry;
* reobserve;
* replan;
* perform rollback;
* execute compensations;
* escalate;
* pause;
* resume;
* cancel;
* recover after restarts;
* avoid duplication;
* use locks;
* evaluate results;
* compare criteria;
* detect side effects;
* detect regressions;
* detect generated debt;
* complete partially;
* update goals;
* propose knowledge updates;
* save operational lessons;
* update authorized memory;
* emit events;
* preserve traceability;
* operate from CLI;
* operate from API;
* integrate with UI;
* integrate with n8n;
* integrate with future domains;
* use local or remote models;
* work with deterministic decisions;
* generate human- and machine-readable results.

⸻

# Security

* least privilege;
* permissions per agent;
* permissions per run;
* permissions per goal;
* permissions per resource;
* permissions per operation;
* permissions per sensitivity;
* limited autonomy;
* prohibition against self-elevating autonomy;
* mandatory budgets;
* operation allowlist;
* prohibition of arbitrary commands;
* parameter validation;
* controlled environments;
* isolation between users;
* locks;
* idempotency;
* checkpoints;
* backups;
* rollback;
* mandatory validation;
* commit gate;
* approval for sensitive actions;
* approval for destructive actions;
* approval for publications;
* approval for communications;
* approval for spending;
* approval for permissions;
* approval for high-impact decisions;
* prompt injection protection;
* separation between data and instructions;
* external models disabled unless authorized;
* secret redaction;
* encryption;
* safe logs;
* complete audit;
* kill switch;
* safe cancellation;
* time limits;
* operation limits;
* iteration limits;
* retry limits;
* question limits;
* external call limits;
* cost limits;
* controlled recovery;
* no automatic personal decisions;
* no irreversible actions without authorization;
* human review when appropriate.

⸻

# Tests

## Unit Tests

* AgentDefinition;
* AgentRun;
* AgentRuntimeStatus;
* RuntimeDecision;
* Goal;
* GoalStatus;
* GoalPriority;
* SuccessCriterion;
* GoalConstraint;
* GoalDependency;
* GoalRepository;
* Goal Manager;
* Observation;
* ObservationSnapshot;
* ObservedChange;
* Observer Registry;
* Agent Cognitive Request;
* Agent Cognitive Result;
* Planning Request;
* Workflow Plan;
* Policy Request;
* Policy Decision;
* Policy Registry;
* Autonomy Levels;
* Approval Request;
* Approval Decision;
* Action Budget;
* Budget Reservation;
* Runtime State Machine;
* Agent Iteration;
* Operation Capability;
* Checkpoint;
* Recovery Context;
* Recovery Decision;
* Retry Policy;
* Rollback Policy;
* Outcome Evaluation;
* Goal Completion Decision;
* Knowledge Update Proposal;
* Operational Lesson;
* Agent Trace;
* permissions;
* locks;
* idempotency;
* serialization;
* errors.

## Integration

* Goal Manager and persistence;
* Goal Manager and events;
* Observation Engine;
* RepositoryObserver;
* GitObserver;
* ValidationObserver;
* MemoryObserver;
* KnowledgeObserver;
* Cognitive Adapter;
* Interactive Question Engine;
* Planner Adapter;
* Policy Engine;
* Approval System;
* Action Budget;
* Runtime and Planner;
* Runtime and Executor;
* Runtime and Validation System;
* Runtime and Semantic Engine;
* Runtime and Cognitive Layer;
* Runtime and memory;
* Checkpoints;
* rollback;
* replanning;
* recovery;
* persistence;
* resumption;
* CLI;
* API;
* Kernel;
* Event Bus.

## E2E

Minimum scenarios:

1. simple analysis-only goal;
2. ambiguous goal;
3. goal with blocking question;
4. goal with sufficient information;
5. goal with missing resource;
6. goal with internal search;
7. goal with authorized external search;
8. goal with denied external search;
9. goal with subgoal;
10. goal with dependency;
11. blocked goal;
12. paused goal;
13. resumed goal;
14. cancelled goal;
15. partially completed goal;
16. completed goal;
17. failed goal;
18. automatic agent assignment;
19. unauthorized agent;
20. autonomy level 0;
21. autonomy level 1;
22. autonomy level 2;
23. autonomy level 3;
24. autonomy level 4;
25. attempt to elevate autonomy;
26. reversible operation;
27. irreversible operation;
28. unregistered operation;
29. operation with invalid parameters;
30. operation without permissions;
31. operation with approval;
32. approval accepted;
33. approval rejected;
34. approval with changes;
35. approval expired;
36. sufficient budget;
37. budget close to limit;
38. budget exhausted;
39. budget increase;
40. repository observation;
41. change detected;
42. expired snapshot;
43. valid plan;
44. invalid plan;
45. plan with circular dependency;
46. replanning;
47. validation passed;
48. validation with warnings;
49. blocking validation;
50. successful retry;
51. retries exhausted;
52. successful rollback;
53. failed rollback;
54. invalid checkpoint;
55. human escalation;
56. pause waiting for user;
57. pause waiting for resource;
58. pause waiting for approval;
59. recovery after restart;
60. idempotent operation;
61. duplicate operation detection;
62. incompatible lock;
63. lock release;
64. success evaluation;
65. mandatory criterion not satisfied;
66. side effect detected;
67. regression detected;
68. technical debt generated;
69. knowledge proposal;
70. memory proposal;
71. memory rejected;
72. operational lesson;
73. prompt injection in resource;
74. unauthorized sensitive resource;
75. unauthorized remote model;
76. local model;
77. model failure;
78. invalid cognitive output;
79. duplicate event;
80. trigger with cooldown;
81. recurring goal;
82. GeneralAgent;
83. ProjectAgent;
84. MaintenanceAgent;
85. DocumentationAgent;
86. contradiction between code and documentation;
87. dead code detection;
88. duplication detection;
89. semantic correction;
90. complete change validation;
91. commit gate blocked;
92. complete workflow with multiple operations;
93. paused and resumed workflow;
94. cancellation through kill switch;
95. complete trace;
96. CLI output;
97. API output;
98. n8n integration;
99. Kernel integration;
100. E2E agent on a test repository.

⸻

# Documentation

The phase must include:

* Agent Runtime architecture;
* goal-oriented architecture;
* public contracts;
* AgentDefinition;
* agent creation;
* Goal System;
* Goal Manager;
* success criteria;
* constraints;
* dependencies;
* subgoals;
* prioritization;
* Goal Repository;
* Observation Engine;
* observer creation;
* snapshots;
* change detection;
* Cognitive Adapter;
* Phase 8 integration;
* gap resolution;
* Information Acquisition Strategy;
* Planner integration;
* autonomous workflow creation;
* plan validation;
* versioning;
* Policy Engine;
* policy creation;
* policy combination;
* conflict resolution;
* autonomy levels;
* human approval;
* Action Budget;
* custom budgets;
* Runtime State Machine;
* Agent Runtime Loop;
* Operation Registry;
* execution;
* validation;
* checkpoints;
* transactions;
* Recovery Manager;
* retries;
* replanning;
* rollback;
* escalation;
* Outcome Evaluation;
* completion criteria;
* knowledge update;
* memory integration;
* Operational Lessons;
* Agent Trace;
* events;
* persistence;
* resumption;
* triggers;
* recurring goals;
* locks;
* idempotency;
* security;
* prompt injection;
* kill switch;
* observability;
* metrics;
* health checks;
* CLI usage;
* API usage;
* Kernel integration;
* Cognitive Layer integration;
* Planner integration;
* Execution Engine integration;
* Semantic Engine integration;
* Validation System integration;
* Memory integration;
* n8n integration;
* guide for creating domain agents in Phase 10;
* complete examples;
* troubleshooting;
* testing guide.

⸻

# Closure Criteria

* Agent Runtime contracts implemented;
* AgentDefinition;
* AgentRegistry;
* AgentFactory;
* persistent AgentRun;
* Goal;
* GoalStatus;
* GoalPriority;
* SuccessCriterion;
* GoalConstraint;
* GoalDependency;
* GoalHistory;
* GoalRepository;
* Goal Manager;
* goal normalization;
* prioritization;
* subgoals;
* dependencies;
* duplicate detection;
* agent assignment;
* Observation Engine;
* Observer Registry;
* initial observers;
* ObservationSnapshot;
* incremental change detection;
* complete Cognitive Layer integration;
* profile selection;
* gap resolution;
* questions;
* resource loading;
* Information Acquisition Strategy;
* Planner integration;
* AgentWorkflowPlan;
* plan validation;
* plan versioning;
* replanning;
* Policy Engine;
* Policy Registry;
* initial policies;
* conflict resolution;
* autonomy levels;
* Human Approval System;
* conditional approval;
* rejection;
* expiration;
* Action Budget;
* Budget Reservation;
* cost control;
* Runtime State Machine;
* Agent Runtime Loop;
* AgentIteration;
* idempotency;
* locks;
* heartbeat;
* integrated Operation Registry;
* Execution Adapter;
* Execution Engine integration;
* Semantic Engine integration;
* Validation System integration;
* before and after validation;
* commit gate;
* checkpoints;
* transactions;
* restoration;
* Recovery Manager;
* retry;
* reobserve;
* replan;
* rollback;
* compensation;
* escalation;
* pause;
* abort;
* Outcome Evaluation;
* criteria evaluation;
* side effect evaluation;
* debt evaluation;
* partial completion;
* goal updates;
* knowledge proposals;
* memory proposals;
* Operational Lessons;
* Runtime Event Bus;
* structured events;
* complete persistence;
* recovery after restart;
* resumption;
* triggers;
* recurring goals;
* security;
* permissions;
* isolation;
* prompt injection protection;
* kill switch;
* logs;
* metrics;
* health checks;
* CLI;
* API;
* GeneralAgent;
* ProjectAgent;
* MaintenanceAgent;
* DocumentationAgent;
* E2E agent on a test repository;
* unit tests;
* integration tests;
* E2E tests;
* documentation;
* green global suite.

⸻

# Phase Result

CMM OS will have a common autonomous infrastructure capable of transforming persistent goals into controlled cycles of observation, reasoning, planning, execution, validation, and evaluation.

Each run will be able to demonstrate:

* what goal it pursued;
* who created it;
* which agent was assigned;
* what autonomy level it had;
* which success criteria it had to satisfy;
* what constraints existed;
* what knowledge it used;
* what it observed;
* what changes it detected;
* which cognitive profile it applied;
* what information was missing;
* what questions it asked;
* what resources it consulted;
* what plan it generated;
* what assumptions it used;
* what policies it evaluated;
* what actions were allowed;
* what actions were denied;
* what approvals it requested;
* what budget it consumed;
* what operations it executed;
* what resources it modified;
* what validations it performed;
* what errors it found;
* what retries it performed;
* when it replanned;
* when it executed rollback;
* when it escalated;
* what result it obtained;
* which criteria it satisfied;
* what side effects it produced;
* what debt it generated;
* what knowledge it acquired;
* what memory it proposed updating;
* why it continued;
* why it stopped;
* why it considered the goal satisfied or failed.

Phase 9 will turn the Cognitive Layer, the Planner, the Execution Engine, the Validation System, and memory into a system capable of pursuing goals over time in a controlled way.

The published Phase 9 runtime also provides the extension points required for later multimodel integration. Model requirements, economic budgets, fallback policies, and model-execution records are specified as post-publication extensions and must be implemented without altering the provider-independent runtime contracts already audited.

The agent will stop being a monolithic class and become a configuration over a single **Goal Execution Engine**.

From this infrastructure, Phase 10 will be able to create specialized agents for health, university, civil-service exam preparation, relationships, languages, life planning, or project work without duplicating the runtime, reasoning, planning, recovery, policies, or memory.

Phase 9 will therefore be the point where CMM OS stops being limited to understanding and executing individual orders and starts maintaining goals, making operational decisions, acting within limits, checking its own results, and stopping when it needs human intervention.

