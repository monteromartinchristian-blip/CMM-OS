# Phase 10.37 — Domain Observability — Independent Audit V1

**Audit date:** 2026-08-31
**Auditor:** ChatGPT — independent CMM OS audit
**Phase:** 10.37 — Domain Observability
**Branch:** `feature/phase-10-domain-intelligence`
**Implementation start HEAD:** `c692f69a562cb8c116d400fa5dd6c315e4701850`
**Audited implementation HEAD:** `17bebaa04d42fecfe56875ae7959d47bba741544`
**Audit bundle:** `phase-10.37-audit-v1.tar.gz`
**Audit bundle SHA-256:** `882b7a1836c837eecbdcbdc924772d7bccb264af5aff7bc1cb77724d6ae47f21`
**Design:** `docs/superpowers/specs/2026-08-31-domain-observability-design.md`
**Plan:** `docs/superpowers/plans/2026-08-31-domain-observability-implementation-plan.md`

## 1. Verdict

```text
INDEPENDENT_AUDIT_V1=FAIL

BLOCKERS=0
MAJORS=5
MINORS=0

DP-037=NOT_VERIFIED
AT-DP-037=FAIL
CLOSURE_ELIGIBLE=NO
```

Phase 10.37 has the correct high-level architecture and a substantial passing
test baseline, but the exact audited implementation does not yet satisfy the
normative accuracy, canonical-evidence, deduplication, health-version binding,
determinism and connected-acceptance requirements of the approved design.

No Phase 10.38 work may start.

A remediation cycle is required.

---

## 2. Artifact integrity and exact-HEAD binding

The submitted candidate was independently checked by a read-only evidence
collector against the exact TAR.GZ.

Verified:

```text
TAR_SIZE=5043701
TAR_SHA256=882b7a1836c837eecbdcbdc924772d7bccb264af5aff7bc1cb77724d6ae47f21
TAR_SHA256_MATCH=PASS
GZIP_INTEGRITY=PASS
GIT_ARCHIVE_COMMIT=17bebaa04d42fecfe56875ae7959d47bba741544
EXACT_HEAD_BINDING=PASS
ARCHIVE_MEMBERS=1971
ARCHIVE_LINKS=0
UNSAFE_ENTRIES=0
ARCHIVE_PATH_SAFETY=PASS
TREE_PARITY_EXIT_CODE=0
QUARANTINE_STASH=PRESERVED
```

The exact implementation delta contains 21 files and all changed files matched
the corresponding objects from audited HEAD byte-for-byte.

The archive contains no `.git`, `.venv`, cache directories, bytecode or other
forbidden working-directory material.

Therefore all findings below apply to:

```text
17bebaa04d42fecfe56875ae7959d47bba741544
```

and to no other worktree state.

---

## 3. Passing architectural and regression evidence

The following independent gates passed:

```text
DOMAIN_API_UNCHANGED=PASS

NO_PARALLEL_OBSERVABILITY_FILES=PASS
NO_PARALLEL_OBSERVABILITY_SYMBOLS=PASS
NO_FORBIDDEN_OBSERVABILITY_OWNER_IMPORTS=PASS
NO_REVERSE_RUNTIME_DEPENDENCY=PASS

METRIC_STATUS_VALUES=PASS
HEALTH_STATUS_VALUES=PASS
METRIC_CATALOG_25_OF_25=PASS
DOMAIN_EVENT_CATALOG_23_OF_23=PASS
PUBLIC_SURFACE=PASS
```

Test evidence:

```text
AT-DP-037 test file execution:       2 passed
Phase 10.37 focused:               112 passed
Adversarial/privacy/health:         36 passed

Phase 10.17 trace regressions:     156 passed
Phase 10.31 selection:              63 passed
Phase 10.32 conflict:              211 passed
Phase 10.33 events:                848 passed
Phase 10.34 sessions:              470 passed
Phase 10.35 SDK:                    71 passed
Phase 10.36 API:                    76 passed

Full Domain suite:                8570 passed
Ruff:                               PASS
Format:                             PASS
compileall:                         PASS
git diff --check:                   PASS
```

These are strong regressions and are accepted as positive audit evidence.

They do not override the semantic defects found by direct code review.

---

## 4. Global-suite collector note — not a Phase 10.37 finding

The evidence collector reported:

```text
COLLECTOR_COMMAND_FAILURES=1
```

The only failing command was the global suite:

```text
1 failed, 14124 passed
```

Failure:

```text
tests/agent_runtime/test_observation_engine.py::test_git_observer_real_repo
expected ObserverStatus.COMPLETED
received ObserverStatus.DEGRADED
```

This was caused by executing the global suite inside the extracted `git archive`
snapshot. A `git archive` intentionally has no `.git` directory, so the test
named `test_git_observer_real_repo` was not running in a Git repository.

This is an **audit-harness environmental mismatch**, not a demonstrated
Phase 10.37 regression.

It is not counted as a blocker, major or minor.

For the remediation re-audit, the global suite must additionally be executed
against the verified exact-HEAD real repository, while TAR-bound focused and
Domain suites continue to run against the extracted candidate.

---

# 5. MAJOR-01 — canonical evidence normalization does not actually deduplicate all stable IDs

## Requirement

The approved design requires:

```text
canonical evidence
→ validate identity
→ deduplicate by authoritative IDs
→ calculate exact measurements
```

The implementation plan explicitly requires evidence to be deduplicated by
stable authoritative IDs before counting.

## Audited implementation

`cmm/domains/observability_metrics.py` contains:

```python
def _deduplicate_generic(...):
    seen: dict[str, Any] = {}
    for item in items:
        identity = str(identity_fn(item))
        if identity in seen:
            expected = seen[identity]
            if expected != item:
                raise InvalidDomainObservabilityEvidenceError(...)
            continue
        seen[identity] = item
    return tuple(items)
```

The function correctly detects conflicting duplicate IDs, but returns the
**original input tuple** instead of the deduplicated values.

It is used for:

```text
DomainConflictCase
DomainOperationResult
DomainWorkflowResult
DomainRuleExecutionResult
DomainSessionContext
DomainSessionResumeResult
```

Therefore two identical canonical objects with the same authoritative ID
survive normalization and may be counted twice.

This contradicts the Task 4 deduplication contract and the core exact-metrics
invariant.

## Additional occurrence-count defects in the same normalization area

### Load failures

Load-result identity correctly distinguishes attempts using:

```text
candidate_id + loaded_at
```

but `loading.failures` subsequently reduces failures to a set of
`candidate_id`.

Two distinct failed attempts for the same candidate are therefore reported as
one failure.

The metric specification is a count of explicit load failure results/events,
not a count of unique failed candidates.

### Cross-domain transfers

The calculator identifies a transfer using only:

```text
source_domain + target_domain + kind
```

but the canonical `CrossDomainContextTransfer` also has, among other fields:

```text
identifier
iteration
provenance
```

Two distinct context transfers of the same kind between the same two domains
are therefore collapsed into one.

## Impact

Exact metrics can undercount or overcount depending on evidence shape.

`DP037-I08` and the exact-projection contract are not established.

## Required remediation

1. `_deduplicate_generic()` must return the canonical deduplicated collection,
   not the original input.
2. Preserve deterministic ordering of the deduplicated results.
3. Add direct regressions for identical duplicates for operation, workflow,
   rule, conflict, session and resume evidence.
4. Count load-failure occurrences after canonical load-result normalization.
5. Define a deterministic, content/reference-based transfer occurrence identity
   that distinguishes genuinely distinct transfers without using fuzzy text.
6. Add adversarial tests proving repeated identical evidence is counted once
   while distinct attempts/transfers remain distinct.

---

# 6. MAJOR-02 — several canonical metric adapters are incomplete or accept non-canonical duck-typed evidence

This finding covers a single architectural cause: the public evidence aggregate
was not fully bound to the actual canonical contracts, and generic extraction
helpers were used where the repository already has stable typed evidence.

## 6.1 `permissions.rejected` reports a real canonical denial as zero

The connected acceptance supplies a real:

```text
DomainOperationPermissionDecision(
    decision=PermissionOutcome.DENY,
    ...
)
```

The canonical contract has:

```text
operation_id
operation_version
decision
reasons
approval_requirements
requirement_decisions
provenance
effective_constraints
```

It does **not** expose `decision_id` or `id`.

The calculator does:

```python
if outcome_value in ("deny", "denied"):
    decision_id = getattr(
        evidence,
        "decision_id",
        getattr(evidence, "id", None),
    )
    if decision_id:
        return (str(decision_id),)
return ()
```

As a result, the exact canonical denial used by `AT-DP-037` produces no
rejected ID.

Because permission evidence is present, the metric becomes an observed zero
instead of the required observed rejection count.

The acceptance supplies the denial but never asserts
`permissions.rejected`.

## 6.2 `rules.applied_by_domain` direct rule-result path is nonfunctional

The calculator accepts:

```text
rule_evidence: tuple[DomainRuleExecutionResult, ...]
```

then maps each result through:

```python
def _rule_execution_domain(result: DomainRuleExecutionResult) -> str | None:
    return None
```

Therefore non-empty direct rule evidence creates no domain counts.

The implementation then attempts an observed bucket metric with empty buckets,
which violates the metric contract instead of producing a correct value or
`UNAVAILABLE`.

The approved design names Domain Trace rule references/results as the
authoritative source for this metric.

## 6.3 `resources.loaded_by_domain` does not understand the canonical resource-resolution contract

The public evidence field remains:

```text
resource_evidence: tuple[Any, ...]
```

The helper expects:

```python
getattr(item, "domain_id", None)
```

but canonical `DomainResourceResolution` has:

```text
id
resource_id
status
bindings
rejections
permission_denials
validation_issues
shared_domains
decisions
trace_id
resolved_at
metadata
```

Per-domain information lives in `DomainResourceBinding.domain_id`, not a
top-level resolution `domain_id`.

Real canonical resolution evidence therefore cannot be projected correctly by
this path.

Additionally:

```python
def _resource_evidence_id(item):
    return str(getattr(item, "id", id(item)))
```

uses Python process-memory identity as fallback.

`id(item)` is not stable across processes and is prohibited by the deterministic
projection requirement.

## 6.4 `sessions.degraded` infers degradation from unrelated reference presence

For raw `DomainSessionContext`, the implementation treats either:

```text
approval_refs
pending_domain_question_refs
```

as evidence of degradation.

Those fields are continuity/reference inventories; their presence does not
mean the session is degraded.

The function then returns the approval/question reference IDs, so a single
session with multiple refs can be counted as multiple "degraded sessions".

The metric specification requires canonical degraded-session evidence.

Explicit `DomainSessionResumeResult` blocked/incompatible/failed states are a
valid source; arbitrary presence of approval/question refs is not.

## 6.5 `knowledge.reused` can be promoted by arbitrary duck-typed objects

The design says reused knowledge must be observed **only** from explicit
authoritative reuse evidence.

The implementation accepts arbitrary `resource_evidence` objects and treats
either:

```text
item.reused == True
```

or:

```text
item.reuse_count > 0
```

as authoritative evidence.

There is no type/provenance binding here.

An arbitrary object carrying those fields can therefore convert
`knowledge.reused` from `UNAVAILABLE` to `OBSERVED`, violating the canonical
evidence rule.

## Plan deviation

The implementation plan explicitly stated that conceptual `object` placeholders
must be replaced with the actual canonical public result types where stable
contracts exist.

The final audited aggregate still contains:

```text
permission_evidence: tuple[Any, ...]
approval_evidence: tuple[Any, ...]
resource_evidence: tuple[Any, ...]
```

This is not merely typing style: the generic fields are directly responsible
for ambiguous and incorrect metric semantics.

## Impact

Several of the advertised 25 metrics can be incorrect, throw on real canonical
input, or become observed from non-authoritative duck-typed input.

## Required remediation

1. Bind evidence fields to the exact canonical contracts that actually exist.
2. Do not invent a new wrapper registry/store to solve the binding.
3. For permissions, count canonical denied decisions even when the decision
   contract does not carry a standalone decision ID; use only safe canonical
   reference identity supported by existing contracts.
4. Make rule metrics trace-owned unless there is a real domain-bound canonical
   rule result.
5. Bind resource evidence to `DomainResourceResolution` and count accepted
   binding domains using stable resolution/binding references.
6. Remove `id(item)` from all deterministic/public evidence paths.
7. For `sessions.degraded`, count unique session IDs only from explicit
   degraded/blocked/incompatible canonical evidence.
8. Keep `knowledge.reused` `UNAVAILABLE` until a real canonical explicit-reuse
   contract is supplied; do not accept arbitrary duck-typed fields.
9. Add direct tests for the exact canonical contracts, especially the
   `DomainOperationPermissionDecision(DENY)` currently used in acceptance.

---

# 7. MAJOR-03 — report projection does not implement canonical source precedence or order-independent determinism

## Requirement

The approved design specifies log source precedence:

```text
DomainEvent
→ DomainTrace
→ canonical public result only when event/trace does not already represent
  the occurrence
```

The same authoritative occurrence must not be duplicated simply because it is
visible through event, trace and public-result evidence.

The design also requires:

```text
log ordering is deterministic
report ordering/digest is deterministic
```

## Audited implementation

`DomainObservabilityService.build_report()` appends every supplied item:

```text
all events
then all traces
then all operation results
then all workflow results
then all resolution results
then all compositions
then all conflicts
then all permissions
then all approvals
then all sessions
```

There is no normalization/source-precedence stage for log entries.

Thus one occurrence represented by event + trace + result can yield several
observability log entries for the same occurrence.

The function also preserves caller tuple order within every evidence category.

Two semantically identical evidence sets supplied in different tuple order can
therefore produce:

```text
different log_entries ordering
different serialized report
different report digest
```

Health results likewise preserve caller `health_domain_ids` order.

The existing determinism test calls the service twice with the **same input
order**. It does not test permutation invariance.

## Impact

The public report is not a deterministic projection of the canonical evidence
set and does not implement the source-precedence rule approved in the design.

This invalidates part of the integrity/digest semantics.

## Required remediation

1. Normalize/deduplicate evidence before log projection.
2. Implement the approved source precedence using explicit reference identity,
   not fuzzy content matching.
3. Preserve all legitimate evidence references while preventing occurrence
   duplication.
4. Canonically sort final log entries with an explicit stable key.
5. Canonically sort health results by domain ID.
6. Add permutation tests:
   - same events reversed;
   - same traces/results reversed;
   - mixed evidence in alternate tuple order;
   - health domain IDs reversed;
   - same semantic evidence must produce identical report serialization/digest.
7. Add an exact event + trace + canonical-result overlap regression proving one
   occurrence is not duplicated.

---

# 8. MAJOR-04 — health manifest validation is not bound to the currently registered Domain version

## Requirement

The approved design states:

```text
manifest=True only when canonical manifest/validation evidence positively
verifies the currently registered Domain version
```

## Audited implementation

Health lookup:

```python
validation = self._manifest_validation_lookup(domain_id)

if validation is not None and getattr(validation, "status", None) in (
    "passed",
    "valid",
):
    dimensions["manifest"] = True
```

It does not verify:

```text
validation.domain_id == requested/current domain
validation.version == definition.version
```

The canonical `DomainValidationResult` used by the tests contains both
`domain_id` and `version`.

A previously passed validation for version `1.0.0` can therefore make the
currently registered version `2.0.0` report:

```text
manifest=True
```

and potentially:

```text
status=healthy
```

## Impact

Health can falsely certify an updated or mismatched Domain version.

This violates positive-verification health semantics.

## Required remediation

Before setting `manifest=True`, verify at minimum:

```text
canonical validation result
+ PASS status
+ exact domain ID binding
+ exact current registered version binding
```

Use the actual canonical validation contract; do not parse a package separately.

Add regressions for:

```text
matching domain + matching version + PASS → verified
wrong domain + PASS → not verified
stale version + PASS → not verified
current version + non-PASS → not verified
missing validation → degraded/unverified
```

---

# 9. MAJOR-05 — AT-DP-037 test execution passes, but the acceptance contract itself is incomplete

## Requirement

The approved spec says:

```text
AT-DP-037 passes only if all minimum checkpoints hold
```

Among them:

```text
13. workflow evidence uses canonical workflow infrastructure/result
14. observed scalar metrics equal actual evidence
15. domain bucket metrics equal actual evidence
21. event/trace overlap does not double-count the same occurrence
22. a healthy Domain positively verifies all required health dimensions
30. report/snapshot ordering and digest are deterministic
44. independent audit verifies DP-037
45. independent audit verifies AT-DP-037=PASS
```

The plan additionally requires the connected metric scenario to assert every
metric for which explicit evidence was supplied.

## Audited acceptance

The test file executes successfully:

```text
2 passed
```

but the main connected evidence aggregate includes an operation result and does
not include canonical workflow evidence.

It supplies a real canonical denied permission decision but does not assert the
`permissions.rejected` metric. Direct review shows that exact denial is
currently reported incorrectly.

Its health service deliberately uses:

```text
manifest_validation_lookup=lambda domain_id: None
```

and the acceptance asserts only selected health dimensions such as registry
and dependencies. It does not produce the required real `HEALTHY` Domain with
all dimensions positively verified.

The determinism assertion repeats the same evidence in the same order; it does
not prove canonical ordering against reordered equivalent evidence.

The production defects documented in MAJOR-01 through MAJOR-04 are therefore
not caught by the acceptance.

## Audit interpretation

The pytest node status is:

```text
PASS
```

but the named acceptance contract is **not satisfied**.

For CMM OS closure semantics this audit therefore records:

```text
AT-DP-037=FAIL
```

until the connected acceptance is expanded and passes after remediation.

## Required remediation

Expand AT-DP-037, without replacing it with isolated mocks, to include:

1. real canonical workflow evidence;
2. exact assertion of the real denied permission metric;
3. real resource/rule metric evidence where the implementation claims
   observed support;
4. duplicate identical canonical evidence controls;
5. event/trace/result overlap control;
6. a real positively verified healthy Domain using current-version validation;
7. stale-version negative health control;
8. evidence-order permutation determinism;
9. all repaired metrics from this audit.

---

# 10. Design Point assessment

## Verified parts

The audit positively verifies the following architecture:

```text
one read-only Phase 10.37 projection
no observability store/repository
no observability event bus
no observability runtime/engine
no observability registry/loader/trace
no reverse dependency into resolver/composition/conflict runtime
Domain Events remain 23/23
DomainAPI remains unchanged
health checker does not execute workflows/operations
privacy projection does not wholesale-copy event payload/metadata
```

## Not yet verified

The defining DP-037 statement also requires the projection to be:

```text
deterministic
derived exclusively from canonical evidence
exact when observed
correctly unavailable otherwise
deduplicated by authoritative identity
```

MAJOR-01 through MAJOR-04 demonstrate that these properties do not hold for all
advertised public evidence paths.

Therefore:

```text
DP-037=NOT_VERIFIED
```

---

# 11. Final V1 status

```text
PHASE10_37_INDEPENDENT_AUDIT_V1=FAIL

AUDITED_HEAD=17bebaa04d42fecfe56875ae7959d47bba741544
AUDIT_BUNDLE_SHA256=882b7a1836c837eecbdcbdc924772d7bccb264af5aff7bc1cb77724d6ae47f21

BLOCKERS=0
MAJORS=5
MINORS=0

DP-037=NOT_VERIFIED
AT-DP-037=FAIL
CLOSURE_ELIGIBLE=NO

PHASE10_38_STARTED=NO
NEXT=PHASE10_37_AUDIT_V1_REMEDIATION
```

---

# 12. Remediation scope lock

Remediation must correct **only** the five V1 findings.

It must not redesign Phase 10.37.

Permitted production targets are expected to remain principally:

```text
cmm/domains/observability_metrics.py
cmm/domains/observability_health.py
cmm/domains/observability_service.py
```

and, only when needed for exact public typing/exports:

```text
cmm/domains/observability_contracts.py
cmm/domains/__init__.py
```

Expected test targets:

```text
tests/domains/test_domain_observability_metrics.py
tests/domains/test_domain_observability_metrics_adversarial.py
tests/domains/test_domain_observability_service.py
tests/domains/test_domain_observability_health.py
tests/domains/test_domain_observability_dp037_acceptance.py
tests/domains/test_domain_observability_boundaries.py
```

Do not create:

```text
store
repository
event bus
runtime
engine
registry
loader
trace
session repository
```

Do not alter:

```text
Phase 10.33 event catalog
DomainAPI
closed Phase 10 contracts merely to make metrics easier
```

When a canonical evidence contract is genuinely insufficient, the correct
Phase 10.37 result remains:

```text
UNAVAILABLE
```

not a new parallel contract or guessed observation.

After remediation:

```text
new remediation commit(s)
→ rerun focused/adversarial/closed regressions
→ full Domain suite
→ real-repo global suite
→ Ruff / format / compileall / diff-check
→ clean worktree
→ new exact-HEAD git-archive TAR.GZ
→ new SHA-256
→ independent re-audit
```

The V1 TAR.GZ and V1 SHA-256 are historical evidence and must not be modified.
