# Domain ↔ Validation System Integration (Phase 10.43)

**Status:** Implemented and pending independent audit.
`DP-043=IMPLEMENTED_PENDING_AUDIT`; `AT-DP-043=PASS` (implementation evidence;
independent audit has not yet run).

**Independently audited boundary:** Phase 10.42 (unchanged until ChatGPT
returns PASS for Phase 10.43).

Phase 10.43 is an **integration phase, not a new validation system**. Domain
Intelligence declares specialized validation policies and obligations; all
authoritative execution remains owned by the canonical Phase 7 Validation
System and, for agentic runtime execution, the existing Phase 9 validation
bridge.

---

## Purpose

Make validation obligations explicit, policy-bound, auditable, and
fail-closed across Domain Pack installation/update, Domain operations,
Domain workflows, cross-domain execution, specialized results, and Project
Domain code changes — without creating parallel validation infrastructure.

## Canonical ownership

| Concern | Canonical owner | Phase 10.43 role |
|---|---|---|
| Validation context | Phase 7 `cmm.validation.ValidationContext` | Build/bind Domain context via `cmm.domains.validation_context.build_domain_validation_context` |
| Validation policy | Phase 7 `cmm.validation.ValidationPolicy` | Select/construct canonical instances via `cmm.domains.validation_policy_bindings` |
| Validation steps | Phase 7 `cmm.validation.ValidationStep` | Register Domain steps only through canonical registry |
| Step execution | Phase 7 `cmm.validation.ValidationExecutor` | No replacement |
| Pipeline | Phase 7 `cmm.validation.ValidationPipeline` | Reused via `PipelineDomainValidator` and `AgentValidationAdapter` |
| Registry | Phase 7 `cmm.validation.ValidationRegistry` | Reused; no second registry |
| Result truth | Phase 7 `cmm.validation.ValidationResult` | Referenced only; never inferred |
| Commit gate | Phase 7 `cmm.validation.CommitGateEvaluator` | Reused; never duplicated |
| Domain Pack structural validation | Existing `cmm.domains.validation.PipelineDomainValidator` | Extended with optional canonical `policy` parameter only |
| Install gate | `cmm.domains.validation.ensure_domain_validation_allows_install` | Hardened fail-closed; update alias `ensure_domain_validation_allows_update` delegates to it |
| Operation runtime validation | Phase 9 `cmm.agent_runtime.validation_execution_adapter.AgentValidationAdapter` via `cmm.agent_runtime.operation_execution_adapter.AgentExecutionAdapter` | Bind Domain requirement via `requires_validation` / `validation_policy_id` (existing `cmm.domains.operation_execution`) |
| Planning projection | Phase 10.42 `cmm.domains.planner_workflow_integration` | Reused unchanged (`required_validations`, `required_validation_ids`, `validation_policy_id`) |
| Project declarations | `cmm.domains.project.operations.build_project_operation_definitions` | Existing `validation_policy_id` preserved; no validation execution in the pack |
| Domain Trace | Phase 10.17 | Reference-only; validation result IDs only |

```text
Domain declaration / Domain policy
        ↓
Phase 10.43 thin Domain binding
        ↓
Phase 7 ValidationPolicy / ValidationContext / ValidationStep
        ↓
Phase 7 ValidationRegistry
        ↓
Phase 7 ValidationExecutor
        ↓
Phase 7 ValidationPipeline
        ↓
Phase 7 ValidationResult
        ↓
existing Phase 9 runtime decision mapping where agentic execution is involved
```

## Policy families

Implemented in `cmm.domains.validation_policy_bindings`:

```text
DomainPackInstallationPolicy  → build_domain_pack_installation_policy
DomainPackUpdatePolicy        → build_domain_pack_update_policy
DomainOperationPolicy         → build_domain_operation_policy
DomainWorkflowPolicy          → build_domain_workflow_policy
CrossDomainExecutionPolicy    → build_cross_domain_execution_policy
ProjectDomainChangePolicy     → build_project_domain_change_policy
```

Constants `DOMAIN_PACK_INSTALLATION_POLICY_NAME`,
`DOMAIN_PACK_UPDATE_POLICY_NAME`, `DOMAIN_OPERATION_POLICY_NAME`,
`DOMAIN_WORKFLOW_POLICY_NAME`, `CROSS_DOMAIN_EXECUTION_POLICY_NAME`,
`PROJECT_DOMAIN_CHANGE_POLICY_NAME`, and `DOMAIN_PACK_BASE_VALIDATION_IDS`
preserve the six public conceptual identities. Every builder returns the
canonical Phase 7 `ValidationPolicy` (never a Domain replacement type) and
records its family in `metadata["domain_policy_family"]`.

Deterministic monotonic composition: `compose_required_validation_ids`
(lexically sorted dedup, `ValueError` on empty/non-string members; adding
groups never removes obligations).

Project impact escalation reuses the canonical Phase 7 catalog
(`small_change` → `structural_change` → `full`) via
`build_project_domain_change_policy(impact=...)`; no second impact
classifier is hard-coded in Domain code.

## Pack install/update lifecycle

```text
Discover candidate → parse manifest → DomainValidationRequest
→ resolve DomainPackInstallationPolicy / DomainPackUpdatePolicy
→ PipelineDomainValidator.validate(request, policy=...)
→ ValidationPipeline.run(...) → DomainValidationResult
→ ensure_domain_validation_allows_install / ensure_domain_validation_allows_update
→ existing trust/source gates → existing atomic loader registration
→ existing health check → explicit enablement under existing authority
```

`PipelineDomainValidator.validate` accepts an optional canonical
`ValidationPolicy`; unknown `domain.*` steps in the policy fail closed via
`DomainValidationExecutionError`. The eight canonical steps
(`domain.manifest`, `domain.contracts`, `domain.permissions`,
`domain.dependencies`, `domain.compatibility`, `domain.security`,
`domain.fragmentation`, `domain.tests`) are preserved; no new Domain step
was added because no RED test proved a distinct uncovered invariant.

Install/update gates fail closed on `FAILED`, `ERROR`, `PENDING`, `RUNNING`,
blocking findings, and unmet strict-test requirements. `WARNING` retains
existing Phase 7/Domain semantics.

```text
VALIDATED != AUTHORIZED
INSTALLED != ENABLED
TRUSTED != PERMITTED
```

Update preserves the previous working state via the existing loader
snapshot/restore and validation-before-registration behavior; the update
gate delegates to the install gate so both share one fail-closed truth.
Migrations are declaration-validated only (no migration engine; none added).

## Domain validation step mapping

| Roadmap concept | Canonical coverage |
|---|---|
| manifest, schema | `domain.manifest` |
| contracts, rules, operations, workflows | `domain.contracts` + runtime `DomainOperationPolicy` / `DomainWorkflowPolicy` |
| dependencies | `domain.dependencies` |
| compatibility | `domain.compatibility` |
| security | `domain.security` |
| permissions | `domain.permissions` |
| fragmentation | `domain.fragmentation` |
| tests | `domain.tests` |
| results, serialization | `validate_domain_specialized_result` (structural only) |
| migrations | declaration-shape only; no execution |
| documentation | existing manifest/contracts coverage; no new prose evaluator |

## Operation runtime flow

```text
DomainOperationDefinition.validation_policy_id
→ Phase 10.42 _operation_semantics required_validations
→ Agent Runtime plan validation nodes
→ DomainOperationExecutionDelegate → AgentExecutionAdapter
   (metadata requires_validation + validation_policy_id)
→ AgentValidationAdapter → Phase 7 ValidationPipeline
→ canonical result → existing Phase 9 decision
   (CONTINUE / BLOCK / RETRY / ROLLBACK / REPLAN / ESCALATE / PAUSE / ABORT)
```

Helpers in `cmm.domains.validation_integration`:
`domain_operation_requires_validation`,
`build_operation_validation_requirements` (preserves every host-derived ID
as required/blocking so unknown mandatory IDs fail closed in the canonical
adapter). No competing decision model was added. Missing adapter with
`requires_validation=True` raises the existing Phase 9
`ValidationAdapterError` (fail closed, no silent skip).

## Workflow runtime flow

Workflows add obligations; they never remove global, Domain, operation,
dependency, or Project obligations. Phase 10.42 dependency closure and
`required_validations` projection remain canonical and unchanged; Task 5
proved preservation with no production change to
`cmm.domains.planner_workflow_integration`.

## Cross-domain composition

`compose_effective_validation_ids` (thin wrapper over
`compose_required_validation_ids`) computes the deterministic restrictive
union:

```text
global ∪ primary ∪ supporting ∪ operation ∪ workflow ∪ dependency ∪ project
```

Deduplicated, lexically ordered, monotonic. Caller metadata keys
`skip_validation`, `validation_passed`, `required_validation_ids`, `trust`,
`approval` are ignored via `is_ignored_caller_validation_metadata`; the
composer takes no metadata input. Unknown mandatory IDs are preserved and
fail closed at the resolution/execution boundary. Duplicate declarations
yield one effective ID and one canonical reference (no duplicate truth).

## Specialized result validation

`cmm.domains.validation_integration.require_canonical_validation_success`
requires actual canonical `ValidationResult` evidence per required ID
(missing/unknown/malformed/unavailable/failed/errored/timed-out/cancelled →
`DomainValidationIntegrationError`; never synthesizes pass).

`validate_domain_specialized_result` checks structural invariants only:
domain/operation/workflow identity coherence, JSON-safe serialization and
round-trip where supported, confidence range where constrained,
approval/validation reference preservation, and status/result consistency
(no success after required failure). It never rewrites content, raises
confidence, resolves contradictions, or infers facts.

## Project Domain code-change validation

`project.modify_code` retains its canonical declaration
(`validation_policy_id="validation.project.modify_code"`); the Phase 10.43
`ProjectDomainChangePolicy` covers it via
`build_project_domain_change_policy(required_validation_ids=(...))`.
`is_project_domain_code_mutation` / `project_change_requires_validation`
identify code mutations semantically (not via caller metadata).
`project.run_validation` availability never exempts a later mutation.
`project.prepare_commit` remains downstream of canonical validation and the
Phase 7 commit gate (`CommitGateEvaluator.evaluate`); Domain code never
issues commit authorization.

## Error/fail-closed semantics

`DomainValidationIntegrationError` is the only new error, owned strictly by
the thin binding layer. All other errors reuse existing Phase 7/9/Domain
families (`DomainValidationBlocked`, `DomainValidationExecutionError`,
`ValidationAdapterError`, `ValidationContractError`, etc.).

Fail closed on: unknown/malformed policy or validation IDs, unavailable
validators, pipeline exceptions, timeout/cancellation, identity mismatch,
caller downgrade attempts, mutation without evidence, and irreconcilable
cross-domain requirements.

## Security/authority separation

Passing validation grants nothing: no enablement, authorization, trust
elevation, permission, approval, autonomy, external communication, memory
write, or rollback authority. Phase 10.15 permissions, Phase 10.38
trust/authority, Phase 10.41 runtime ownership, and approval ownership are
preserved and proven by dedicated adversarial tests.

## Anti-fragmentation proof

No `DomainValidationEngine`, `DomainValidationRuntime`,
`DomainValidationStore`, `DomainValidationRepository`,
`DomainValidationEventBus`, `DomainValidationHistory`,
`DomainValidationCommitGate`, `DomainValidationPolicyRegistry`,
`DomainValidationExecutor`, second pipeline/registry/executor, store,
history, event bus, runtime, commit gate, or second result/policy truth
model was introduced. `cmm.domains.validation_integration` never
instantiates `ValidationPipeline`/`ValidationRegistry`/`ValidationExecutor`;
it delegates through `PipelineDomainValidator` and Phase 9. Structural
tests enforce this.

## DP-043

`DP-043 — Canonical Domain Validation Integration`:
`IMPLEMENTED_PENDING_AUDIT`. Final `VERIFIED_EXISTING` determination belongs
to the independent auditor.

## AT-DP-043

`tests/domains/test_domain_validation_integration_dp043_acceptance.py`:
`PASS` (implementation evidence). Covers pack install, operation PRE/POST,
workflow closure, cross-domain union, Project mutation regression/correction,
commit-gate ownership, and architectural proof using real canonical
components and official in-memory implementations.

## Known limits / out of scope

Phase 10.44+, Phase 11 migration engine, UI, Model Gateway, provider
validation, new persistence/observability/API/CI/publication/workflow/
rollback/health-check systems, automatic activation/elevation, LLM
prose-quality validation, and arbitrary executable validators were not
implemented.
