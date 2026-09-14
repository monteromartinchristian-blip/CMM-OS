# Phase 10.37 — Domain Observability — Independent Re-audit V3

**Audit date:** 2026-09-01
**Auditor:** ChatGPT — independent CMM OS audit
**Phase:** 10.37 — Domain Observability
**Branch:** `feature/phase-10-domain-intelligence`
**V2 remediation baseline:** `f3107dd658be8de5c1780636525a2ec264778998`
**Audited V3 HEAD:** `e4d66df57c601652f3206515bf578e57190fc537`
**Audit bundle:** `phase-10.37-audit-v3.tar.gz`
**Audit bundle SHA-256:** `31e36a0b5817e30155495e3d47abe6e1ac89b827d374fbaed0aeb6bd224828da`
**Historical audits:** V1 and V2 preserved unchanged

## 1. Verdict

```text
PHASE10_37_INDEPENDENT_REAUDIT_V3=FAIL

BLOCKERS=0
MAJORS=3
MINORS=0

DP-037=NOT_VERIFIED
AT-DP-037=FAIL
CLOSURE_ELIGIBLE=NO

NEXT=PHASE10_37_AUDIT_V3_REMEDIATION
```

V3 is materially stronger than V2 and all collected test/quality gates pass.
However, direct review of the exact V3 source identifies two remaining
production-contract defects and a connected acceptance false positive.

No Phase 10.38 work may start.

---

# 2. Artifact integrity and exact-HEAD binding

Verified from the submitted V3 evidence collector:

```text
TAR_SHA256=31e36a0b5817e30155495e3d47abe6e1ac89b827d374fbaed0aeb6bd224828da
SHA256_MATCH=PASS
GZIP_INTEGRITY=PASS
GIT_ARCHIVE_HEAD=e4d66df57c601652f3206515bf578e57190fc537
EXACT_HEAD_BINDING=PASS

ARCHIVE_MEMBERS=1978
ARCHIVE_LINKS=0
UNSAFE_ARCHIVE_ENTRIES=0
ARCHIVE_PATH_SAFETY=PASS

LOCAL_HEAD=e4d66df57c601652f3206515bf578e57190fc537
QUARANTINE_STASH=PRESERVED
COLLECTOR_COMMAND_FAILURES=0
```

Required V1/V2 audits, approved spec/plan, all four Phase 10.37 production
modules, AT-DP-037 and reference documentation are present in the exact
candidate.

---

# 3. Passing V3 evidence

The following independently collected gates pass:

```text
V3 audit-regression tests:       21 passed
AT-DP-037 pytest nodes:           3 passed
Phase 10.37 focused:            169 passed
Full Domain suite:             8627 passed
Global suite:                 14182 passed

RUFF=PASS
FORMAT=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS

HISTORICAL_AUDITS_UNCHANGED=PASS
DOMAIN_API_UNCHANGED=PASS
DOMAIN_EVENT_CATALOG_23_OF_23=PASS
NO_PARALLEL_OBSERVABILITY_INFRASTRUCTURE=PASS
NO_REVERSE_RUNTIME_DEPENDENCY=PASS
```

The V2 transfer-iteration fix is accepted.

The V2 permission field/status/version fix is accepted as far as the tests
exercise it.

The V2 health/version binding remains accepted.

These positive findings must be preserved.

---

# 4. MAJOR-01 — source-precedence occurrence identity uses definition IDs as execution IDs

## Requirement

The approved design requires:

```text
same authoritative occurrence
→ explicit canonical reference identity
→ Event > Trace > public result
```

and forbids fuzzy or semantically broad matching.

A definition ID is not an execution occurrence ID.

## Audited V3 implementation

`cmm/domains/observability_service.py` defines:

```python
def _operation_occurrence_keys(result):
    return frozenset(
        {
            ("operation_result", result.result_id),
            ("operation", result.operation_id),
        }
    )
```

and:

```python
def _workflow_occurrence_keys(result):
    run = result.common_result.run
    return frozenset(
        {
            ("workflow_result", result.run_id),
            ("workflow", run.workflow_id),
        }
    )
```

The V3 tests deliberately connect Event/Trace/result by assigning the same
`operation_id` and then treat that as one occurrence.

## Canonical contract evidence

`DomainOperationResult` has separate fields:

```text
result_id
request_id
operation_id
operation_version
...
```

The canonical executor creates a fresh `result_id` while copying
`request.operation_id` into the result.

Therefore `operation_id` identifies the operation definition/action being run,
not one unique execution occurrence.

Two real results can legitimately be:

```text
result_id=result-1
request_id=request-1
operation_id=health.build_summary
```

and:

```text
result_id=result-2
request_id=request-2
operation_id=health.build_summary
```

They are two executions.

V3 gives both the shared key:

```text
("operation", "health.build_summary")
```

and the union-find occurrence normalizer merges them into one log occurrence.

The workflow contract has the same distinction:

```text
DomainWorkflowResult.run_id
WorkflowRun.workflow_id
```

`run_id` identifies the run; `workflow_id` identifies which workflow is being
run.

Two separate runs of the same workflow therefore share `workflow_id`.

V3 gives both the same:

```text
("workflow", workflow_id)
```

and can merge distinct workflow executions.

## Impact

The new source-precedence implementation can silently under-report real
operation/workflow occurrences.

This is not merely a test gap: it violates the core Phase 10.37 deterministic,
exact, canonical-evidence projection invariant.

## Required remediation

1. Do not use `operation_id` or `workflow_id` alone as execution occurrence
   keys.
2. Inspect the canonical event adapters / trace references and determine what
   `operation_run` and `workflow_run` actually reference.
3. Link Event → Trace → public result only through an actual execution/run
   reference such as the canonical result/run/request reference supported by
   the existing contracts.
4. If no explicit cross-channel occurrence reference exists for a public
   result, do not suppress it.
5. Add RED regressions:
   - two `DomainOperationResult` objects with different `result_id`/`request_id`
     but the same `operation_id` remain two log occurrences;
   - two `DomainWorkflowResult` objects with different `run_id` but the same
     `workflow_id` remain two log occurrences;
   - truly linked Event/Trace/result still collapse according to precedence;
   - unrelated evidence remains distinct;
   - input permutation remains digest-stable.

No new runtime/store/registry is permitted.

---

# 5. MAJOR-02 — runtime canonical evidence validation remains incomplete

## Requirement

The approved spec requires:

```text
Malformed or unsafe evidence must fail closed.
```

The V2 remediation prompt further required runtime validation for every
evidence tuple whose canonical type is known.

## Audited V3 implementation

`DomainObservabilityEvidence` declares exact canonical types for all of:

```text
registry_definitions
registry_records
load_results
resolution_results
compositions
conflict_results
events
traces
sessions
session_resume_results
permission_evidence
approval_evidence
operation_evidence
workflow_evidence
rule_evidence
resource_evidence
cross_domain_transfers
```

However `_validate_evidence_element_types()` validates only:

```text
permission_evidence
approval_evidence
resource_evidence
cross_domain_transfers
operation_evidence
workflow_evidence
rule_evidence
conflict_results
sessions
session_resume_results
```

It does not validate:

```text
registry_definitions
registry_records
load_results
resolution_results
compositions
events
traces
```

These fields have equally explicit canonical types.

Supplying malformed content to one of these fields therefore does not fail at
the public evidence boundary as
`InvalidDomainObservabilityEvidenceError`. It proceeds into normalization,
where arbitrary attribute access can instead raise unrelated runtime errors.

This contradicts the public fail-closed evidence contract.

## Additional identity-conflict gap

`_normalize_evidence()` also forwards permission and approval evidence without
a dedicated identity-conflict normalization pass.

For example, two canonical permission objects with the same synthetic
`operation_id + operation_version` identity but contradictory decisions can
reach log occurrence grouping without the explicit conflicting-identity
rejection that the source-precedence code assumes has already happened.

The source-precedence implementation itself states:

```text
Conflicting same-source identity is handled before projection by evidence
normalization.
```

That assertion is not true for every projected source category.

## Required remediation

1. Runtime-validate every canonically typed `DomainObservabilityEvidence` tuple.
2. Malformed elements must fail at construction with
   `InvalidDomainObservabilityEvidenceError`.
3. Error diagnostics remain safe and must not echo arbitrary object contents.
4. Add missing RED tests for malformed:
   - registry definition;
   - registry record;
   - load result;
   - resolution result;
   - composition;
   - event;
   - trace.
5. Normalize/detect contradictory same-identity permission/approval evidence
   before log occurrence precedence, or remove the claim that such conflicts
   have already been normalized and implement the fail-closed check where the
   occurrence is merged.
6. Preserve valid canonical objects and all currently passing behavior.

---

# 6. MAJOR-03 — AT-DP-037 is still a false positive for the remaining occurrence-identity defect

The V3 acceptance now correctly asserts:

```text
linked Event/Trace/result → one log occurrence
unlinked Event/Trace/result → three occurrences
```

This is an improvement over V2.

However the linked fixture makes:

```text
DomainEventReference(kind="operation_run", reference_id=operation.operation_id)
DomainTraceReference(kind=OPERATION_RESULT, ref_id=operation.operation_id)
DomainOperationResult.operation_id = same value
```

and then declares that value to be the shared execution occurrence.

That is the same incorrect production assumption identified in MAJOR-01.

The canonical operation result has a separate generated `result_id` and
`request_id`, while `operation_id` is copied from the operation request and can
repeat across executions.

The acceptance therefore proves only that V3 can merge three objects when a
test forces their **definition ID** to match.

It does not prove correct occurrence identity.

The V3 acceptance also does not exercise malformed values for the unvalidated
typed evidence fields identified in MAJOR-02.

## Required acceptance remediation

AT-DP-037 must add at least:

```text
two separate operation executions
same operation_id
different result_id/request_id
→ remain two occurrences
```

```text
two separate workflow runs
same workflow_id
different run_id
→ remain two occurrences
```

```text
real explicit cross-channel occurrence reference
→ Event > Trace > result
```

without using a reusable definition ID as the occurrence key.

Also prove malformed evidence fail-closed for at least one of the previously
unvalidated core fields, with dedicated focused tests covering all of them.

Until then:

```text
AT-DP-037=FAIL
```

for closure purposes even though its pytest nodes are green.

---

# 7. V2 remediation status after V3

```text
V2_MAJOR_01=REMEDIATED
V2_MAJOR_02=PARTIALLY_REMEDIATED
V2_MAJOR_03=PARTIALLY_REMEDIATED
V2_MAJOR_04=NOT_FULLY_REMEDIATED
```

Accepted V3 improvements include:

```text
cross-domain transfer identity includes iteration
canonical permission status uses decision.value
permission source IDs include operation version
malformed resource/permission/approval/transfer evidence fails closed
health current-version validation remains correct
report clock remains single-capture
source-precedence normalization now exists structurally
linked/unlinked source-precedence tests exist
all quality/regression gates pass
```

The remaining defects are narrow and do not require architectural redesign.

---

# 8. DP-037 assessment

DP-037 requires a projection that is simultaneously:

```text
canonical
read-only
exact
deterministic
privacy-safe
deduplicated by authoritative occurrence identity
fail-closed on malformed/contradictory evidence
```

V3 satisfies the architecture and quality boundaries, but MAJOR-01 and
MAJOR-02 show that authoritative occurrence identity and fail-closed evidence
validation are still incomplete.

Therefore:

```text
DP-037=NOT_VERIFIED
```

---

# 9. Final V3 status

```text
PHASE10_37_INDEPENDENT_REAUDIT_V3=FAIL

AUDITED_HEAD=e4d66df57c601652f3206515bf578e57190fc537
AUDIT_V3_BUNDLE_SHA256=31e36a0b5817e30155495e3d47abe6e1ac89b827d374fbaed0aeb6bd224828da

BLOCKERS=0
MAJORS=3
MINORS=0

DP-037=NOT_VERIFIED
AT-DP-037=FAIL
CLOSURE_ELIGIBLE=NO

PHASE10_38_STARTED=NO
NEXT=PHASE10_37_AUDIT_V3_REMEDIATION
```

---

# 10. V3 remediation scope lock

Remediate only these three V3 findings.

Expected production targets:

```text
cmm/domains/observability_metrics.py
cmm/domains/observability_service.py
```

Expected tests:

```text
tests/domains/test_domain_observability_v2_red.py
tests/domains/test_domain_observability_dp037_acceptance.py
```

A dedicated V3 regression test file is allowed.

Do not change:

```text
DomainAPI
Domain Events catalog
Domain Event public contract
Domain Trace public contract
operation/workflow public contracts
cross-domain public contracts
permission public contracts
historical V1/V2/V3 audit reports
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

After remediation:

```text
RED tests
→ minimal fixes
→ focused Phase 10.37
→ closed-phase regressions
→ full Domain suite
→ global suite in real Git repository
→ Ruff / format / compileall / diff-check
→ clean worktree
→ quarantine stash preserved
→ phase-10.37-audit-v4.tar.gz from exact committed HEAD
→ new SHA-256
→ independent ChatGPT re-audit V4
```

Do not overwrite V1/V2/V3 bundles.
