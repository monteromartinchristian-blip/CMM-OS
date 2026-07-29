# Phase 9.3 — Goal Intake and Goal Normalization Architecture

## Overview & Responsibility

The **Goal Intake and Goal Normalization** layer converts raw inputs (user messages, system events, workflow triggers, periodic checks, recovery signals) into structured, validated, and auditable goal proposals (`GoalProposal`). 

Goal Intake acts strictly as a **gatekeeper and transformer**:
* It does **not** execute goals.
* It does **not** perform autonomous actions.
* It does **not** query external LLM models directly.
* It does **not** alter system knowledge or trigger workflows.
* It does **not** activate goals automatically.

---

## Conceptual Hierarchy: Request → Proposal → Goal

1. **`GoalNormalizationRequest`**: Raw, unvalidated input DTO containing text, source, actor ID, explicit parameters, and optional hints.
2. **`GoalProposal`**: Structured, immutable, intermediate candidate goal specifying title, description, criteria, constraints, ambiguities, gaps, confidence, and confirmation requirements.
3. **`Goal`**: Registered operational entity managed by `GoalManager` with formal lifecycle state machine (starts as `PROPOSED`).

---

## Deterministic Normalization

Normalization is executed by `DeterministicGoalNormalizer` without reliance on external probabilistic models:
* Extracts titles and descriptions cleanly from raw objectives.
* Respects explicit type hints, priority scores, constraints, permissions, and deadlines.
* Detects recurring goals, remediation needs, analysis, and validation objectives.
* Preserves `raw_objective` verbatim for full auditability.
* Maintains strict safety boundaries: does **not** invent deadlines, permissions, or elevate requested autonomy.

---

## Ambiguities and Information Gaps

When input objective statements are ambiguous or incomplete:
* The normalizer identifies blocking ambiguities (`GoalAmbiguity`) and formulates structured questions (`GoalInformationGap`).
* The proposal is set to status `requires_clarification` with `requires_confirmation = True`.
* Confidence score is lowered (e.g. `0.5`).
* Proposal acceptance is blocked until ambiguities are resolved.

---

## Proposal States and Lifecycle

```text
  [Raw Input] ──> CREATED ──> NORMALIZING
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
               READY                   REQUIRES_CLARIFICATION
                 │                               │
                 ├───────────────────────────────┤
                 ▼                               ▼
              ACCEPTED                        REJECTED
                 │
                 ▼
         Goal(status=PROPOSED)
```

Proposal status values:
* `created`: Initialized proposal.
* `normalizing`: Processing normalization request.
* `ready`: Normalized proposal with no blocking ambiguities, ready for user/policy review.
* `requires_clarification`: Proposal has missing information or blocking ambiguities.
* `accepted`: Approved proposal converted into a registered `Goal`.
* `rejected`: Proposal explicitly turned down.
* `expired`: Stale proposal past validity window.
* `failed`: Normalization or validation failure.

---

## Acceptance, Rejection, and State Safeguards

* **Double Acceptance Prevention**: Attempting to accept an already `ACCEPTED` proposal raises `GoalProposalStateError`.
* **Rejection Boundary**: Rejected proposals cannot be accepted.
* **Invalid Proposal Safeguard**: Proposals with status `failed`, `expired`, or unresolved blocking ambiguities cannot generate a Goal.
* **Conservative Goal Initialization**: Converted Goals start in `GoalStatus.PROPOSED` and are **not** automatically activated.

---

## Duplicate Goal Detection

When a `GoalManager` is connected:
* Goal Intake searches active (non-terminal) goals for matching normalized title, kind, owner actor ID, and parent goal ID.
* If a potential duplicate is detected, Goal Intake returns a `merge_with_existing` decision with candidate goal IDs and sets status to `requires_clarification`.
* Auto-merging is **never** executed automatically.

---

## Current Boundaries & Future Integration

Current Phase 9.3 boundaries:
* Normalization is entirely deterministic.
* Information gaps are represented as structured DTOs without direct interaction with Cognitive Engine or Question Engine.

Future Phase Integration:
* **Phase 9.5 (Cognitive Adapter)**: Will enable semantic resolution of complex natural language objectives into GoalProposals when deterministic normalization yields `requires_clarification`.
* **Phase 9.6 (Information Acquisition Strategy)**: Will automatically resolve `GoalInformationGap` items by querying cognitive memory, documentation, or user interfaces.

---

## Usage Example

```python
from cmm.agent_runtime import (
    DeterministicGoalNormalizer,
    GoalIntakeService,
    GoalManager,
    GoalNormalizationRequest,
    GoalSource,
    InMemoryGoalProposalRepository,
    InMemoryGoalRepository,
)

# 1. Initialize services
proposal_repo = InMemoryGoalProposalRepository()
goal_repo = InMemoryGoalRepository()
goal_manager = GoalManager(repository=goal_repo)
intake_service = GoalIntakeService(
    normalizer=DeterministicGoalNormalizer(),
    proposal_repo=proposal_repo,
    goal_manager=goal_manager,
)

# 2. Process intake request
request = GoalNormalizationRequest(
    raw_objective="Add integration tests for goal intake service",
    source=GoalSource.USER_MESSAGE,
    actor_id="actor-dev",
)
result = intake_service.process_request(request)

# 3. Accept proposal and generate operational Goal
goal = intake_service.accept_proposal(result.proposal.id)
assert goal.status == "proposed"
assert goal.title == "Add integration tests for goal intake service"
```
