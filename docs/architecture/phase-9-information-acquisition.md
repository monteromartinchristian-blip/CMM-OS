# Phase 9.6 – Information Acquisition Strategy Architecture

## Overview & Responsibility

The **Information Acquisition Strategy** component decides **how to resolve an information gap** detected during goal intake or cognitive reasoning before proceeding to planning or execution.

It acts as an autonomous resolution router:
- It evaluates candidate acquisition strategies against policy, cost, sensitivity, permissions, and risk.
- It selects the optimal strategy deterministically.
- It prepares acquisition requests without executing arbitrary side-effects or inventing parallel reasoning/question engines.

```text
Information Gap + Goal + Agent Run + Cognitive Result + Resources + Permissions + Policy
                                     ↓
                      Acquisition Candidate Evaluation
                                     ↓
                             Selection Decision
       ↓             ↓             ↓             ↓            ↓           ↓
    Ask User / Load Resource / Search Know / Search Repo / Infer / Human Review / Pause / Abort
```

## System Boundaries & Limits

Information Acquisition Strategy:
- **Does NOT** solve the gap cognitively by itself.
- **Does NOT** execute arbitrary state mutations or workflow actions.
- **Does NOT** invent parallel question engines (reuses Phase 8 Interactive Question Engine and `GoalInformationGap`).
- **Does NOT** persist new knowledge directly.
- **Does NOT** modify `Goal` or `AgentRun` contracts.
- **Does NOT** depend on future phases (Planner 9.7, Policy Engine 9.8, Autonomy 9.10, or Action Budget 9.11).

## Supported Strategies

1. `ask_user`: Prompt user when gap is user-resolvable, blocking, and within question limits.
2. `load_internal_resource`: Retrieve pre-existing authorized internal resource.
3. `search_knowledge`: Query persisted knowledge from `KnowledgeStore`.
4. `search_repository`: Query codebase structure, configuration, or documentation.
5. `search_external_source`: Execute authorized external search when permitted by sensitivity & limits.
6. `infer_with_permission`: Delegate limited reasoning inference to Cognitive Layer with explicit permission.
7. `request_human_review`: Escalate high-risk or critical contradictions for professional human judgment.
8. `accept_uncertainty`: Preserve non-blocking gaps when resolution cost is disproportionate.
9. `pause`: Suspend run until external resources or capabilities become available.
10. `abort`: Terminate run safely when no acquisition strategy is permissible.

## Core Contracts

- `InformationAcquisitionRequest`: Input specification specifying gap, context, limits, and permissions.
- `InformationAcquisitionPolicy`: Configurable rules governing allowed/prohibited strategies, cost ceilings, and risk limits.
- `InformationAcquisitionCandidate`: Evaluated candidate strategy with estimated cost, risk, and applicability.
- `InformationAcquisitionDecision`: Structured outcome declaring selected strategy, expected costs, and reason codes.
- `InformationAcquisitionResult`: Complete cycle result containing request, context, candidates, decision, and status.
- `InformationAcquisitionCost` & `InformationAcquisitionEstimate`: Preview data structures for call counts, risk, and duration.

## Deterministic Selection Algorithm

Selection proceeds through 15 steps:
1. Validate request invariants.
2. Extract standardized gap properties.
3. Construct acquisition context.
4. Generate applicable candidates across all strategies.
5. Filter prohibited and non-allowed strategies.
6. Evaluate required permissions against context.
7. Enforce sensitivity rules (e.g. restrict external search on confidential/restricted data).
8. Evaluate availability (question budgets, call limits).
9. Estimate costs and durations.
10. Estimate confidence gain and resolution probability.
11. Sort candidates deterministically:
    - Lower risk
    - Lower cost
    - Higher resolution probability
    - Higher expected confidence gain
    - Lower external resource usage
    - Policy preferred strategy order
    - Stable strategy name string order
12. Select top candidate strategy.
13. Return structured `InformationAcquisitionDecision` and `InformationAcquisitionResult`.

## Relationship to Future Phases

- **9.7 Workflow Planner Adapter**: Consumes resolved information or accepted uncertainty before generating plans.
- **9.8 Policy Engine**: Provides runtime governance rules for acquisition decisions.
- **9.10 Autonomy Levels**: Determines whether approval is required for external acquisition or human escalation.
- **9.11 Action Budget**: Enforces concrete runtime execution budgets; 9.6 provides preview estimates compatible with 9.11.

## Usage Example

```python
from cmm.agent_runtime import (
    InformationAcquisitionRequest,
    InformationAcquisitionPolicy,
    InformationAcquisitionService,
    GoalInformationGap,
)

service = InformationAcquisitionService()

gap = GoalInformationGap(
    id="gap-01",
    question="What is the target deployment region?",
    is_blocking=True,
)

request = InformationAcquisitionRequest(
    id="acq-req-01",
    agent_run_id="run-123",
    goal_id="goal-456",
    gap_id="gap-01",
    gap=gap,
    maximum_questions_remaining=3,
)

result = service.acquire_information(request)
print(result.decision.strategy) # InformationAcquisitionStrategy.ASK_USER
```
