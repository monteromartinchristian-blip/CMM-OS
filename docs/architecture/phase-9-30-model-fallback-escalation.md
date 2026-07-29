# Phase 9.30 — Workflow Model Fallback and Escalation

Phase 9.30 adds a bounded, declarative policy layer for failed model-assisted
workflow operations. It does not execute providers and does not replace either
`ModelRouter` or the generic recovery engine.

## Reused infrastructure

The decision context carries the effective `kernel.llm.model_selection.ModelRequirements`
from 9.29 and the original `kernel.llm.model_router.RoutingDecision`. Ordered
fallback candidates therefore come from the existing routing catalog and retain
the original constraints. The recovery adapter emits the existing
`RecoveryDecision`; approval, Action Budget, checkpoints, validation, and
observability remain supplied by their existing services through context
snapshots and recovery integration.

## Contracts

`ModelAttemptResult` records the operation, attempt, normalized provider/model,
typed trigger, validation, latency, and costs. `ModelAttemptHistory` preserves
all attempts. `ModelFallbackPolicy` is immutable, versioned, finite, and
serializable. `ModelFallbackContext` joins those records with requirements,
routing, policy, approval, privacy, and budget snapshots. `ModelFallbackDecision`
is an auditable and idempotent result.

The layer owns explicit JSON serializers for routing decisions, candidates,
rejected models, ranking policy, and requirements, so round-trips contain no
live Python objects.

`AgentWorkflowOperation.model_fallback_policy` is optional and round-trips
through the existing workflow contract. Existing operations remain unchanged.

## Triggers and actions

The trigger enum covers provider/model availability, timeout, rate limit,
parsing and structured-output failures, validation and quality failures,
context/capability/privacy conflicts, cost and budget limits, empty/invalid
responses, transient/permanent errors, and exhausted retries.

Actions include same-model retry, modified retry, ordered routing candidate,
equivalent/lower-cost/higher-quality selection, rerouting, reobservation,
revalidation, replanning, approval, escalation, pause, and terminal failure.

## Policy and precedence

The default policy allows at most three total attempts, one attempt per model,
two per provider, and only bounded transient retries. Security/privacy, policy,
approval, budget, attempt limits, validation/quality, and routing preferences
are evaluated in that order. Privacy conflicts, denied policy, exhausted budget,
and exhausted attempts fail closed. Premium escalation requires an approved
snapshot only when structured context identifies the selected use as premium.

## Routing and recovery

The engine filters already-used models and, when configured, the failed provider
from `RoutingDecision.candidates`, returning skipped candidates and reason codes.
Candidate iteration delegates to `ModelRouter.fallback_candidates()`; every
candidate is then rechecked against effective provider, privacy, context, cost,
and budget constraints.
When the original candidates are exhausted it may request rerouting only if the
policy allows it. The pure `ModelFallbackRecoveryAdapter` maps equivalent
actions to existing `RecoveryStrategy` values (`retry`, `reobserve`,
`rerun_validation`, `replan`, `request_approval`, `escalate`, `pause`, and
`fail`) without adding model-specific recovery strategies.

## Audit, idempotency, and limits

Decisions retain operation, workflow, attempt, trigger, selected candidate,
skipped candidates, effective requirements, reason codes, recovery strategy,
approval/pause state, and metadata. The idempotency key is deterministic for
the logical input. No provider calls, storage, metrics service, or parallel
audit system is introduced. Requirement modification is disabled by default;
the implementation never weakens inherited requirements.

Premium is not inferred from model names because the current candidate contract
does not expose a premium classification. Approval is requested only when
structured upstream context marks premium use as required and policy permits it.

## Validation

Focused tests cover contract normalization/serialization, default and bounded
policy behavior, candidate selection, provider exclusion, approval and budget
fail-closed behavior, workflow round-trip, recovery translation, idempotency,
and regression coverage for the existing 9.29 model requirement contracts.
