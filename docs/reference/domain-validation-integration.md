# Domain ↔ Validation System Integration (Phase 10.43)

**Status:** Complete, independently audited and closed.
`DP-043=VERIFIED_EXISTING`; `AT-DP-043=PASS`; `CLOSURE_ELIGIBLE=YES`; final independent re-audit **V6** `PASS`.
**Audited implementation HEAD:** `4e6519f2eb03b0ae312d6500df0c16f50e99f1e1`.
**Audit V6 bundle SHA-256:** `2a1f6512136ba2639cff7c899100dfb14f9d6e191f4e2a29cf55eab02a0235b0`.
**Final independent audit:** `docs/audits/phase-10.43-independent-final-reaudit-v6.md`.

**Independently audited boundary:** Phase 10.43.

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
| Operation runtime validation | Phase 9 `cmm.agent_runtime.validation_execution_adapter.AgentValidationAdapter` via `cmm.agent_runtime.operation_execution_adapter.AgentExecutionAdapter` | Host-derived `ValidationRequirement`s on `AgentOperationRequest.validation_requirements` (built by `DefaultDomainOperationOrchestrator` from the canonical definition via the injected provider); PRE/POST requests carry stage-filtered requirements plus `validation_project_root`; unknown required validators raise `ValidationAdapterError` |
| Operation validation provider | `cmm.domains.validation_integration.resolve_domain_operation_validation_requirements` (thin binding, injected into the orchestrator) | Maps definition → executable IDs via the canonical Project change policy for `project.modify_code` (impact-sensitive, fail-closed on unmappable steps: `formatter_check`/`lint`/`syntax_validator`/`ast_validator`/`affected_tests_step` for `small`), otherwise registration-time `domain_validation_requirement_ids`, built-in executable mapping, or the policy identity itself (fail-closed); unions host-computed `additional_ids` (workflow/dependency/cross-domain) with host-owned `validation_impact`/`validation_changed_files` typed channels and `resource_scope` propagation |
| Workflow runtime bridge | `cmm.domains.operation_execution.build_domain_workflow_operation_adapter` | Routes operation nodes through the orchestrator with `DomainWorkflowPolicy`-bound additional IDs; required subworkflow nodes recurse through child executors sharing the adapter; maps results to `NodeExecution` |
| Cross-domain runtime bridge | `cmm.domains.operation_execution.OrchestratedCrossDomainOperationPort` | Resolves coordinated operations canonically, derives the restrictive union via `compose_effective_validation_ids`, executes each through the orchestrator with `effective_validation_ids`, records the `CrossDomainExecutionPolicy` and effective set in result metadata |
| Specialized result acceptance | `DefaultDomainOperationOrchestrator` outcome path + `validate_domain_specialized_result` | Identity-carrying outputs are structurally validated before `COMPLETED`; plain outputs pass through |
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

Project impact escalation reuses the canonical Phase 7 catalog via
`build_project_domain_change_policy(impact=...)`: `small` →
`small_change`, `structural` → `structural_change`, `public` →
`public_api_change`, `broad`/`high`/`full` → `full` (full-suite
escalation preserved). Unknown impact values raise `ValueError`
(fail-closed) instead of downgrading to `small_change`; no second impact
classifier is hard-coded in Domain code.

## Pack install/update lifecycle

```text
Discover candidate → parse manifest
→ DeclarativeDomainLoader.load: build pack
→ resolve DomainPackInstallationPolicy
→ PipelineDomainValidator.validate(request, policy=...) [Phase 7 run]
→ ensure_domain_validation_allows_install
→ existing trust/source gates → existing atomic loader registration
→ existing health check → explicit enablement under existing authority

reload: same shape with DomainPackUpdatePolicy /
ensure_domain_validation_allows_update BEFORE any registry mutation,
so a failed update preserves the previous working version atomically.
```

`PipelineDomainValidator.validate` accepts an optional canonical
`ValidationPolicy` and the policy controls the actual Phase 7 execution:
required `domain.*` steps become the requested step set
(`_apply_policy_to_request`), unknown `domain.*` steps fail closed via
`DomainValidationExecutionError`, required non-`domain.*` steps are
rejected as unsatisfiable by this pack bridge (never silently dropped),
and install/update families missing a mandatory base step are rejected
(no weakened policy). The policy identity is recorded in context metadata
(`domain_policy`); `requested_policy` intentionally stays `None` because
that field resolves against the canonical Phase 7 policy catalog, where
Domain family names are not entries (setting it would make the pipeline
return an `invalid_policy` ERROR instead of executing Domain steps).
The eight canonical steps
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
DomainOperationDefinition (+ registration-time declared IDs)
    ↓ host-derived, never caller metadata
resolve_domain_operation_validation_requirements
    → PRE + POST ValidationRequirement(s)
    ↓ attached to AgentOperationRequest.validation_requirements
AgentExecutionAdapter PRE (stage-filtered requirements)
    ↓ AgentValidationAdapter → Phase 7 ValidationPipeline
execute registered operation
    ↓
AgentExecutionAdapter POST (stage-filtered requirements)
    ↓ AgentValidationAdapter → Phase 7
validate specialized result (structural, identity-carrying outputs)
    ↓ Agent Runtime outcome evaluation
canonical result → existing Phase 9 decision
    (CONTINUE / BLOCK / RETRY / ROLLBACK / REPLAN / ESCALATE / PAUSE / ABORT)
```

For `project.modify_code` the flow above is specialized: only PRE
requirements travel with the pre-mutation request. After the mutation, the
orchestrator captures the after snapshot, derives the actual canonical
Phase 7 `ChangeSet`/`ChangeImpactResult`, materializes POST requirements
from that post-change truth, and executes them through the same canonical
`AgentValidationAdapter` (`_run_post_mutation_project_validation`).
Pre-mutation scope is never reused for POST. See "Project Domain
code-change validation" below.

The orchestrator requires the injected provider for any validation-mandated
operation: `operation_validation_provider=None` with a non-null
`validation_policy_id` (or composition obligations) fails closed
(`DomainValidationIntegrationError`, no metadata-only success). An empty
mandatory requirement set (`requires_validation=True` with
`validation_requirements=()`) fails closed at the canonical Agent execution
boundary (`ValidationAdapterError`). Executable mapping:
registration-time `domain_validation_requirement_ids` from the canonical
definition win; `project.modify_code` resolves through the canonical
`ProjectDomainChangePolicy` selected by host-owned impact
(`resolve_project_domain_change_validation_ids`, deterministic fail-closed
mapping `PROJECT_PHASE7_STEP_EXECUTABLE_VALIDATOR_IDS`; unmappable mandatory
steps raise instead of being silently omitted); any other operation mandating
validation resolves to its policy identity, which the canonical adapter
rejects fail-closed (`ValidationAdapterError`) when no capable step
exists. Host-computed `effective_validation_ids` on the typed request
channel union in additional composition obligations (monotonic; callers
can only add, never remove, definition-derived requirements).
For `project.modify_code`, `validation_project_root` is host authority:
the host-registered operation implementation declares its execution root
via `host_project_root`, and caller metadata `validation_project_root` is
at most a transport hint that must resolve to the same tree (mismatch
rejects the request; missing/undeclared/invalid host roots fail closed
before any mutation). Project validation/provider/root/before-snapshot preflight
completes before `TransactionManager.start_transaction()`, so rejected preflight
leaves zero active transaction/checkpoint residue. For other operations the legacy deployment-setting
behavior is preserved; requirement sets always stay host-derived.

Helpers in `cmm.domains.validation_integration`:
`domain_operation_requires_validation`,
`resolve_operation_validation_ids` (pure ID union),
`resolve_domain_operation_validation_requirements` (PRE+POST for ordinary
operations; PRE-only for `project.modify_code`, whose POST is recomputed
post-mutation),
`build_operation_validation_requirements` (preserves every host-derived ID
as required/blocking so unknown mandatory IDs fail closed in the canonical
adapter), `project_policy_impact_from_canonical_result` (thin adapter from
canonical `ChangeImpactResult` fields to Project policy impact; no source
re-classification). Canonical validation evidence references are retained on
`DomainOperationResult.metadata["validation_result_ids"]` (reference-only),
including the authoritative post-mutation POST result. No competing
decision model was added. Missing adapter with
`requires_validation=True` raises the existing Phase 9
`ValidationAdapterError` (fail closed, no silent skip).

## Workflow runtime flow

Workflows add obligations; they never remove global, Domain, operation,
dependency, or Project obligations. Phase 10.42 dependency closure and
`required_validations` projection remain canonical planning owners.

Execution bridge
(`cmm.domains.operation_execution.build_domain_workflow_operation_adapter`):
operation nodes execute through `DefaultDomainOperationOrchestrator` (real
PRE/POST Phase 9→7 validation per node, with the host-computed
workflow/subworkflow/dependency union bound via a canonical
`DomainWorkflowPolicy` into `effective_validation_ids`); required
subworkflow nodes recurse through child `DomainWorkflowExecutor`s sharing
the same adapter (depth-guarded), so dependency obligations survive
execution, not just planning. Results map to `NodeExecution`
(`operation.*` failure codes; validation references retained in
`operation_result`). Approval/wait nodes keep existing permission-gate
ownership.

## Cross-domain composition

`compose_effective_validation_ids` (thin wrapper over
`compose_required_validation_ids`) computes the deterministic restrictive
union:

```text
global ∪ primary ∪ supporting ∪ operation ∪ workflow ∪ dependency ∪ project
```

Deduplicated, lexically ordered, monotonic. Production enforcement path
(`cmm.domains.operation_execution.OrchestratedCrossDomainOperationPort`):
each coordinated operation is resolved against the canonical operation
registry, the union over all coordinated operations' canonical definitions
plus host global obligations is derived with `compose_effective_validation_ids`
(Domain packs declare validation at operation granularity, so
primary/supporting obligations materialize through member operations),
every operation executes through the orchestrator with that union on the
typed `effective_validation_ids` channel, per-operation failures become
findings (fail-closed), and the `CrossDomainExecutionPolicy` plus effective
set are recorded in result metadata.

Caller metadata keys
`skip_validation`, `validation_passed`, `required_validation_ids`, `trust`,
`approval` are ignored via `is_ignored_caller_validation_metadata`; the
composer and the orchestrator take no requirement input from caller
metadata. The typed `effective_validation_ids` channel is union-merged, so
host callers can only add obligations, never remove definition-derived
ones. Unknown mandatory IDs are preserved and fail closed at the
adapter boundary. Duplicate declarations yield one effective ID and one
canonical execution (the adapter additionally dedupes by step name).

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
confidence, resolves contradictions, or infers facts. Production call
site: `DefaultDomainOperationOrchestrator` invokes it on
identity-carrying operation outputs before accepting `COMPLETED`
(`_check_specialized_result_acceptance`); plain outputs without identity
markers pass through untouched. The gate is unconditional and
provider-independent: invalid specialized results are rejected even when
no `operation_validation_provider` is configured.

## Project Domain code-change validation

`project.modify_code` retains its canonical declaration
(`validation_policy_id="validation.project.modify_code"`). Runtime
enforcement path: the orchestrator provider resolves it through the
canonical `ProjectDomainChangePolicy` selected by host-owned impact
(`build_project_domain_change_policy` → canonical Phase 7 policy →
`resolve_project_domain_change_validation_ids` → Phase 9
`ValidationRequirement` values with `resource_scope` carrying
host-derived changed files → `AgentValidationAdapter` → Phase 7
validators), executed PRE and POST through the real
`AgentValidationAdapter` → Phase 7 chain.

Host change derivation and monotonic combination (V5 remediation):
- Project impact owner is the canonical Phase 7 `ChangeImpactAnalyzer`.
  `derive_host_project_change_impact` builds the canonical `ChangeSet`
  via `ChangeSetBuilder.build_from_snapshots` from in-memory before/after
  snapshots (`scan_project_snapshot`), runs `ChangeImpactAnalyzer.analyze`,
  and translates the canonical result to Project policy impact with
  `project_policy_impact_from_canonical_result` (preserves
  `requires_full_suite`, `uncertainty`, `public_api_changed`,
  `affected_symbols`, and structural change kinds; only a clean local
  change maps to `small`). Domain code does not classify Python
  source diffs independently.
- Pre-execution scope is provisional: before the mutation exists, no host
  change can be derived, so only caller hints are carried. There is no
  top-level-file heuristic; nested/src-layout files are discovered from
  the real mutation ChangeSet.
- Post-execution POST is authoritative:
  `DefaultDomainOperationOrchestrator._run_post_mutation_project_validation`
  captures the after snapshot, derives the actual changed files and
  canonical impact, materializes POST requirements from post-change
  truth, and executes them through the same canonical
  `AgentValidationAdapter`. Pre-mutation scope is never reused.
- Fail-closed derivation: missing/undeclared/mismatched/unreadable host
  root, before/after snapshot capture failure, `ChangeSetBuilder` or
  `ChangeImpactAnalyzer` failure, unmappable mandatory policy steps, empty
  POST requirement set, missing POST adapter, POST infrastructure failure,
  or a non-`CONTINUE` POST decision all prevent acceptance. Pre-mutation
  failures raise `DomainValidationIntegrationError` before execution;
  post-mutation failures roll back via `_failure_with_rollback` (rejected
  with `POST_VALIDATION_FAILED`) using the configured rollback executor —
  the canonical `CheckpointRestorationRollbackExecutor` in acceptance,
  which restores mutated file content, not just status.
- Host-derived impact and caller hints are combined monotonically via
  `combine_validation_impacts` using the strict severity hierarchy
  (`small` < `structural` < `public` < `broad`/`high`/`full`). Caller hints
  can only escalate obligations, never downgrade host-observed impact.
- Changed files are union-merged via `combine_validation_changed_files`.
  Caller hints cannot hide or remove host-changed files from the validation
  scope.
- Command result parser fail-closed hardening: in `CommandResultParser.parse()`,
  a non-zero pytest exit code with a missing XML report fails closed with
  `PYTEST_TEST_FAILED` (exit code is authoritative failure evidence); zero
  tests discovered in `full_suite_step` returns not-applicable; ruff non-zero
  exit without JSON diagnostics fails closed as execution failure.

The `small` baseline requires `formatter_check`, `lint`, `syntax`
(`syntax_validator`), `ast` (`ast_validator`), and `affected_tests`
(`affected_tests_step`); a syntactically valid change that breaks an affected
test is rejected and accepted only after current canonical validation passes.
Stronger impacts (`structural`/`public`/`broad`/`high`/`full`) escalate to the
corresponding canonical Phase 7 policies and fail closed on mandatory steps
without an executable mapping (never silently downgraded to `small`).
`is_project_domain_code_mutation` / `project_change_requires_validation`
identify code mutations semantically (not via caller metadata).
`project.run_validation` availability never exempts a later mutation
(availability is not evidence; only current validation counts).
`project.prepare_commit` remains downstream of canonical validation and the
Phase 7 commit gate (`CommitGateEvaluator.evaluate` with a
`ProjectDomainChangePolicy` selected by impact); Domain code never issues commit
authorization.

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

`DP-043 — Canonical Domain Validation Integration`: `VERIFIED_EXISTING`.
Verified by final independent re-audit **V6** `PASS` with `BLOCKERS=0`, `MAJORS=0`, `MINORS=0`, and `CLOSURE_ELIGIBLE=YES`.

## AT-DP-043

`tests/domains/test_domain_validation_integration_dp043_acceptance.py`:
`PASS` (final independent V6 acceptance). Covers real pack
install/update through the canonical lifecycle, real operation PRE/POST
through orchestrator → adapter → Phase 7, provider-omission fail-closed
with adapter present, empty mandatory requirement fail-closed,
unconditional specialized-result gate without provider, real workflow node
execution including subworkflows, real cross-domain union through engine +
port, real Project mutation fail→fix→pass with valid-syntax affected-test
rejection verified via failure evidence, nested src-layout regression
blocked by affected_tests from the actual mutation ChangeSet with no
caller hints, caller decoy-root rejection against the trusted host root,
canonical `ChangeImpactAnalyzer` escalation (structural/public) failing
closed with canonical file-content restoration, post-mutation
derivation-failure fail-closed, commit-gate ownership, specialized-result
acceptance, and architectural proof using real canonical components and
official in-memory implementations (no fixed-decision doubles, no manual
unions in place of execution, no synthetic validation results on
architectural paths).

## Known limits / out of scope

Phase 10.44+, Phase 11 migration engine, UI, Model Gateway, provider
validation, new persistence/observability/API/CI/publication/workflow/
rollback/health-check systems, automatic activation/elevation, LLM
prose-quality validation, and arbitrary executable validators were not
implemented.
