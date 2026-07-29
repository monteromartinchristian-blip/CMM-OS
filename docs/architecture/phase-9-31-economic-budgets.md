# Phase 9.31 — Economic Budgets for Goals and Workflows

Phase 9.31 adds economic controls for model-assisted operations without introducing
a second ledger or budget service. The implementation reuses `ActionBudgetService`,
`BudgetAllocation`, `BudgetReservation`, `BudgetConsumption`, `BudgetAdjustment`,
`BudgetResourceType.COST`, existing policy/autonomy/approval adapters, `ModelSpec`
catalog prices, and the Phase 9.30 fallback contracts.

## Scope and hierarchy

`EconomicBudget` is an immutable, JSON-safe declaration that may be attached to a
`Goal`, `AgentWorkflowPlan`, or `AgentWorkflowOperation`. Existing payloads remain
valid because the new field is optional. `EconomicBudgetResolver` combines sources
in Goal → Workflow → Operation → policy → approval order. Numeric limits use the
minimum, premium permission requires every source to allow it, and tolerance and
thresholds use the most restrictive values. All sources and reason codes remain in
`ResolvedEconomicBudget` provenance.

Conflicting currencies fail closed. Currency values are normalized as three-letter
ISO 4217 codes; no exchange-rate conversion is performed. An absent limit is not
turned into an implicit spend allowance: the canonical Action Budget must still be
configured before reservation.

## Cost calculation

`ModelCostCalculator` consumes `ModelSpec.input_cost_per_million`,
`cached_input_cost_per_million`, and `output_cost_per_million`. Calculations use
`Decimal(tokens) * price / Decimal(1_000_000)` and do not round silently. Unknown
prices fail closed by default, or produce an explicitly incomplete
`ModelCostEstimate` when `allow_partial=True`.

## Action Budget integration

`EconomicBudgetActionBudgetAdapter` maps the estimate to one canonical
`BudgetAllocation(BudgetResourceType.COST, amount)`. It delegates reservation,
confirmation, release, failure, concurrency and limit checks to
`ActionBudgetService`; it never edits repositories directly. Stable idempotency
keys include goal/workflow/operation/run, budget, model/provider, routing choice,
price, currency and estimate version. Actual cost may be lower or higher than the
estimate subject to the existing service capacity rules. Partial failed costs use
`ActionBudgetService.fail`.

## Runtime and fallback

`EconomicBudgetDecision.to_snapshot()` produces the structured mapping already
accepted by `ModelFallbackContext.budget`. The snapshot carries availability,
decision, limits, currency and reason codes, so existing 9.30 triggers such as
`ESTIMATED_COST_EXCESSIVE`, `ACTUAL_COST_EXCESSIVE`, and `BUDGET_EXHAUSTED` remain
owned by the existing fallback decision engine.

Warnings, pause/exhaustion states, policy denials, autonomy denials, and approval
expansions remain governed by existing Action Budget, policy, autonomy, recovery,
and approval contracts. Authorized increases must use
`ActionBudgetService.increase_budget` and an `ApprovalResolution`.

## Explicit non-scope

This phase does not implement FX, provider gateways, monthly limits, dashboards,
invoicing, accounting, or the Phase 11 Cost Management Layer.

## Validation

The focused suite covers immutable contracts, invalid money values, hierarchy and
currency conflicts, deterministic Decimal calculations, canonical reservation and
confirmation, fallback snapshots, and Goal/Workflow round-trips. Existing Action
Budget, 9.29 model requirements, and 9.30 fallback tests are retained as regression
coverage.
