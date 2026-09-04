# Domain ↔ Agent Runtime Integration (Phase 10.41)

**Status:** Phase 10.41 complete, independently audited and closed.
`DP-041=VERIFIED_EXISTING`; `AT-DP-041=PASS`.
**Final independent verification:** Re-audit **V3** `PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`; `CLOSURE_ELIGIBLE=YES`.

**Audited implementation HEAD:** `6972e7495bccc0e69ccaa7d007f915ef891e8913`.

**Audit V3 bundle SHA-256:** `c9677d836843de8068ba5ed3c0e7d8cd87e12bc4df34e1e2361195f5d8f28458`.

**Independent audit report:** `docs/audits/phase-10.41-independent-reaudit-v3.md`.

---

## Purpose and ownership

Phase 10.41 connects the completed Domain Intelligence subsystem to the
canonical Phase 9 Autonomous Agent Runtime so a Phase 9 agent execution can be
specialized by Domain resolution, composition, profiles, cognition,
permissions, autonomy limits, budget ceilings, and Domain operations — without
creating a second runtime, planner, approval service, budget service,
cognitive engine, store, event bus, or execution engine.

Phase 10.41 is an **integration boundary owned by `cmm.domains`**. The
canonical integration owner is `DefaultDomainAgentRuntimeIntegrator`
(`cmm/domains/agent_runtime_integration.py`), a thin orchestration boundary
that receives every stateful owner by dependency injection. It owns
coordination only.

## Dependency direction

```text
cmm.domains → cmm.agent_runtime   (allowed)
cmm.agent_runtime → cmm.domains   (forbidden; AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0)
```

The reverse direction is enforced by boundary tests
(`tests/domains/test_domain_agent_runtime_integration_boundaries.py`) and by
an explicit AST scan in the Phase 10.41 gates.

## New contracts (`cmm/domains/agent_runtime_integration_contracts.py`)

- `DomainActionBudget` — immutable Domain-side budget **ceiling** value
  object (operation/iteration/question/external-call/duration/cost limits).
  It has no counters and no mutation or increase API; consumed and reserved
  state remains exclusively inside Phase 9 `ActionBudget` /
  `ActionBudgetService`.
- `DomainAgentRuntimeDecisionCode` / `DomainAgentRuntimeDecision` — immutable
  structured decision records (IDs, reason codes, safe metadata only; no
  hidden reasoning, no copied traces).
- `DomainAgentRuntimeIntegrationRequest` — immutable wrapper binding the
  canonical `DomainResolutionContext` and the canonical Phase 9
  `IntegratedAgentExecutionRequest` (identity consistency is validated:
  goal/actor conflicts fail closed).
- `DomainAgentRuntimeIntegrationResult` — immutable integration aggregate
  binding canonical results by reference (`DomainResolutionResult`,
  `DomainComposition`, `ResolvedDomainProfile`, Phase 10.40 cognitive result,
  `IntegratedAgentExecutionResult`). It never clones canonical results.

All contracts are frozen/slotted, deterministic, secret-safe, and JSON-safe
following neighboring Phase 9 / Phase 10.40 conventions.

## Integration sequence

```text
validate wrapper
→ DefaultDomainResolver.resolve(DomainResolutionContext)
→ canonical composition (exact selected Domain definitions)
→ DefaultDomainProfileResolver.resolve(...) via injected profile inputs
→ Phase 10.40 DefaultDomainCognitiveIntegrator (when cognitive resources exist)
→ deterministic cognitive projection into IntegratedAgentExecutionRequest.cognitive_context
→ Domain permission resolution/gate (restrict only)
→ Domain autonomy ceiling (min of incoming and Domain maximum)
→ Domain budget restriction over the canonical ActionBudgetService (decrease only)
→ operation/workflow eligibility binding against the composed Domain
→ canonical Phase 9 AgentRuntimeIntegrationService.execute(specialized request)
→ reference-only result/trace/memory bindings
```

Every `execute(...)` call is a deterministic re-preparation from the current
request; there is no Domain-side state machine.

## Cognitive projection

Phase 10.40 remains the Domain-to-Cognitive owner. Phase 10.41 projects the
safe, materialized subset into the existing Phase 9 seam under the namespace
key `cognitive_context["domain_intelligence"]`: resolution/composition/profile
IDs, primary/supporting domains, knowledge-package ID, adapted resource IDs,
presentation reference IDs, and the Domain cognitive request ID. The
projection is deterministic, contains no hidden reasoning keys, and a
collision with non-equal caller data at the namespace key fails closed.

## Permission narrowing and approval ownership

Domain permissions can only narrow Agent Runtime authority. Set/list
dimensions intersect with the primary Domain allowlist and every Domain
prohibition (supporting-Domain allowlists may narrow only through explicit
prohibitions); booleans use AND semantics; prohibitions win. A Domain `ALLOW`
never adds authority that the Agent permission context lacks.

A Domain `DENY` returns a blocked integration result before any Phase 9 call.
A Domain `APPROVAL_REQUIRED` records the `DOMAIN_APPROVAL_REQUIRED` decision
and passes only the existing Phase 9 `requires_approval` metadata hint; the
canonical Phase 9 approval infrastructure remains the sole authority that
pauses, validates, consumes, and resumes approvals. Phase 10.41 never
manufactures approval evidence, and stale approval IDs are never reused after
a material Domain change — the canonical approval service independently
validates each execution.

## Autonomy ceiling

`DOMAIN_AUTONOMY <= GLOBAL_AUTHORIZED_AUTONOMY` is permanent. The effective
autonomy delivered to Phase 9 is `min(incoming authorized maximum, effective
Domain maximum)`. An absent or unconstrained Domain limit preserves the
incoming Phase 9 value; Phase 10.41 never invents a higher default.

## Budget restriction

Phase 9 `ActionBudgetService` is the only mutable budget owner. Phase 10.41
maps the canonical `BudgetResourceType` dimensions (operation,
duration_seconds, cost) onto `DomainActionBudget` ceilings and uses only the
canonical decrease path; a stricter master limit is preserved untouched and no
increase path exists in the integration modules. Unmapped Domain dimensions
are never enforced through a Phase 10.41 ledger.

## Operation routing and workflow boundary

Selected operations execute only through the registered Agent/Domain
orchestration path (`InMemoryAgentOperationRegistry` →
`InMemoryDomainOperationRegistry` → `AgentExecutionAdapter` →
`DomainOperationExecutionDelegate` → permission/approval gates). Phase 10.41
validates that incoming operations are eligible under the composed Domain and
never calls Domain operation implementations directly. An already-resolved
`AgentWorkflowPlan` is bound by reference only; a Domain-requested workflow
that the current Phase 9 seam cannot represent fails closed with a structured
unsupported decision (Planner/Workflow Engine integration remains Phase
10.42).

## Reevaluation boundaries

Domain reevaluation occurs only at explicit safe boundaries (initial
execution, explicit `force_domain_reevaluation`, continuation/resume, retry or
replan entry, or a resolution that itself requires clarification). Each
execution recomputes resolution, composition, profile, permissions, autonomy
ceiling, budget ceiling, cognitive context, and operation/workflow eligibility
before the next Phase 9 call; a high-risk Domain becoming unavailable blocks
instead of silently falling back to a less restrictive Domain.

## Trace/reference and memory semantics

Domain and Agent traces remain owner-specific and are linked by IDs and
references only (`agent_trace_id`, decision `related_ids`, metadata); no trace
payloads are copied and no trace store is introduced. Memory and knowledge
changes remain proposal-driven through existing Phase 8/9/10.18 contracts;
Phase 10.41 performs zero direct store writes and retains only canonical
proposal/binding IDs.

## Error and fail-closed behavior

The narrow `cmm.domains.errors` family
`DomainAgentRuntimeIntegrationError` / `...ContractError` /
`...BlockedError` distinguishes malformed contract input from policy blocks.
Blocked specialized executions produce no operation side effects and never
silently downgrade to unrestricted General behavior.

## Security and privacy invariants

Secret-bearing metadata keys are rejected with the canonical forbidden-key
semantics; hidden-reasoning keys (`chain_of_thought`, `reasoning_text`,
`internal_reasoning`, `scratchpad`, `hidden_trace`) are rejected in decision
metadata; no raw provider payloads are trusted; sensitivity and approval
controls are never weakened; direct persistence is prohibited.

## Known limits

- `domain_trace_id` is populated by the canonical Domain Trace owner through
  reference linkage; Phase 10.41 does not assemble Domain traces itself.
- Autonomy is expressed through the existing Phase 9
  `max_autonomy_level`/permission-context ceiling; there is no separate
  reversible/irreversible boolean seam in the Agent permission context, so
  those Domain limits bind through the autonomy ceiling.
- Planner/Workflow Engine capability discovery, Domain workflow nodes, and
  Domain subworkflow composition are out of scope (Phase 10.42).

## AT-DP-041 location

`tests/domains/test_domain_agent_runtime_dp041_acceptance.py` — connected
acceptance over the 20 frozen checkpoints (resolution, composition, profile,
cognitive projection, reverse-import gate, permission narrowing, approval
lifecycle, autonomy ceiling, budget preservation/reduction/exhaustion,
registered orchestration path, reference-only trace/memory bindings,
reevaluation, stale-authority invalidation, blocked-path isolation, no
parallel owners, contract strictness, and the AT-DP-040 regression).
