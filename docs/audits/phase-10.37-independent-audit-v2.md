# Phase 10.37 — Domain Observability — Independent Audit V2

**Audit date:** 2026-08-31
**Auditor:** ChatGPT — independent CMM OS audit
**Phase:** 10.37 — Domain Observability
**Branch:** `feature/phase-10-domain-intelligence`
**V1 remediation start HEAD:** `b0c7ba22768bc5e20963b3601cdc1a58edd97db5`
**Audited V2 HEAD:** `5f4df64574d96de45724092cc8802210e00e243d`
**Audit bundle:** `phase-10.37-audit-v2.tar.gz`
**Audit bundle SHA-256:** `addfa5505a6527416effe56731c5378aa3c4bed954b7316143c509809a3b617c`
**Design:** `docs/superpowers/specs/2026-08-31-domain-observability-design.md`
**Plan:** `docs/superpowers/plans/2026-08-31-domain-observability-implementation-plan.md`
**Historical V1 audit:** `docs/audits/phase-10.37-independent-audit-v1.md`

## 1. Verdict

```text
PHASE10_37_INDEPENDENT_REAUDIT_V2=FAIL

BLOCKERS=0
MAJORS=4
MINORS=0

DP-037=NOT_VERIFIED
AT-DP-037=FAIL
CLOSURE_ELIGIBLE=NO

NEXT=PHASE10_37_AUDIT_V2_REMEDIATION
```

V2 materially improves the implementation and correctly remediates several V1
sub-findings. However, four residual defects remain in the exact audited source.
They affect canonical occurrence identity, public canonical permission evidence,
source precedence/deduplication, and the connected acceptance contract.

No Phase 10.38 work may start.

---

# 2. V2 artifact integrity

The uploaded V2 TAR.GZ was inspected directly.

Verified:

```text
BUNDLE_SIZE=5062754
AUDIT_V2_SHA256=addfa5505a6527416effe56731c5378aa3c4bed954b7316143c509809a3b617c
EXPECTED_SHA256=addfa5505a6527416effe56731c5378aa3c4bed954b7316143c509809a3b617c
SHA256_MATCH=PASS

GIT_ARCHIVE_PAX_COMMENT=5f4df64574d96de45724092cc8802210e00e243d
EXACT_HEAD_BINDING=PASS

ARCHIVE_MEMBERS=1976
UNSAFE_ARCHIVE_PATHS=0
ARCHIVE_PATH_SAFETY=PASS
```

Required files are present:

```text
docs/audits/phase-10.37-independent-audit-v1.md
docs/superpowers/specs/2026-08-31-domain-observability-design.md
docs/superpowers/plans/2026-08-31-domain-observability-implementation-plan.md

cmm/domains/observability_metrics.py
cmm/domains/observability_health.py
cmm/domains/observability_service.py

tests/domains/test_domain_observability_dp037_acceptance.py
tests/domains/test_domain_observability_major01_red.py
tests/domains/test_domain_observability_major02_red.py
tests/domains/test_domain_observability_major03_red.py
tests/domains/test_domain_observability_major04_red.py
```

The V1 historical audit report inside the V2 bundle is byte-identical to the
previous V1 audit artifact:

```text
V1_AUDIT_REPORT_UNCHANGED=PASS
V1_AUDIT_REPORT_SHA256=8ac399f260c3cd7fb5c9246ab0acf2eb16464eba58f6d250cce5810d0165af09
```

---

# 3. Execution evidence received with V2

The remediation agent reports:

```text
FOCUSED_TESTS=148
DOMAIN_REGRESSIONS=PASS
DOMAIN_SUITE=8606
GLOBAL_SUITE=14161

RUFF=PASS
FORMAT=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS

DOMAIN_EVENT_CATALOG_23_OF_23=PASS
DOMAIN_API_UNCHANGED=PASS
NO_PARALLEL_OBSERVABILITY_INFRASTRUCTURE=PASS
V1_AUDIT_REPORT_UNCHANGED=PASS
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
```

The independent audit sandbox could not execute the repository pytest suite
because the sandbox Python environment does not contain the repository
dependency `libcst`. That is an audit-environment limitation, not a Phase 10.37
test failure.

The exact V2 source was nevertheless directly reviewed from the SHA-bound
archive. The semantic defects below are source-level defects and remain defects
even if the current test suite is green.

---

# 4. V1 remediation assessment

## V1 MAJOR-01

**PARTIALLY REMEDIATED**

Verified improvements:

```text
_deduplicate_generic returns deduplicated values
generic stable-ID duplicates are no longer returned as raw input
loading.failures distinguishes attempts by candidate_id + loaded_at
identical load-result duplicates collapse correctly
```

Residual transfer identity defect remains; see V2 MAJOR-01.

## V1 MAJOR-02

**PARTIALLY REMEDIATED**

Verified improvements:

```text
permission_evidence now has a canonical type annotation
approval_evidence now has a canonical type annotation
resource_evidence now names DomainResourceResolution / DomainResourceBinding
resource domain attribution uses accepted bindings
id(item) process-memory fallback was removed
approval_refs / pending-question refs no longer imply degraded session
knowledge.reused remains UNAVAILABLE without a canonical reuse contract
```

Residual permission and malformed-evidence defects remain; see V2 MAJOR-02.

## V1 MAJOR-03

**PARTIALLY REMEDIATED**

Verified improvements:

```text
report clock is captured once by build_report
derived fallback timestamps use the captured generated_at
log entries receive a deterministic final sort
health domain IDs are deduplicated and sorted
DomainConflictReference.source_id is used correctly
```

Canonical source precedence is still absent; see V2 MAJOR-03.

## V1 MAJOR-04

**REMEDIATED**

The V2 health checker now requires:

```text
DomainValidationResult
DomainValidationStatus.PASSED
validation.domain_id == current domain
validation.version == current registered definition.version
```

before `manifest=True`.

Stale-version and wrong-domain PASS evidence no longer positively verifies the
manifest.

## V1 MAJOR-05

**NOT FULLY REMEDIATED**

The acceptance was expanded substantially, but its overlap checkpoint asserts a
behavior opposite to the approved source-precedence contract and does not cover
the residual canonical identity failures. See V2 MAJOR-04.

---

# 5. V2 MAJOR-01 — Cross-domain transfer identity still treats payload identifier as unique occurrence ID

## Requirement

The metric:

```text
cross_domain.transfers
```

must count explicit canonical transfer occurrences exactly.

The design requires:

```text
canonical evidence
→ validate identity
→ deduplicate by authoritative occurrence identity
→ calculate exact measurement
```

## Audited V2 code

V2 defines:

```python
class _EvidenceIdentity:
    @staticmethod
    def transfer_id(transfer: CrossDomainContextTransfer) -> str:
        return transfer.identifier
```

and:

```python
def _deduplicate_transfers(...):
    identity = transfer.identifier
    ...
    if identity in seen:
        expected = seen[identity]
        if expected != transfer:
            raise InvalidDomainObservabilityEvidenceError(...)
```

The implementation docstring calls `identifier`:

```text
an explicitly unique canonical reference
```

but that is not what the canonical cross-domain contract guarantees.

`CrossDomainContextTransfer` contains independent occurrence fields:

```text
source_domain
target_domain
kind
identifier
iteration
provenance
```

The canonical cross-domain engine creates a transfer with:

```python
identifier=finding.identifier
iteration=iteration
```

and `CrossDomainContextBuilder.add_transfer()` appends accepted transfers without
requiring the identifier to be globally unique.

Therefore the same finding/reference can legitimately be transferred in more
than one iteration while retaining the same `identifier`.

Example canonical shape:

```text
transfer A:
identifier=finding-123
iteration=0

transfer B:
identifier=finding-123
iteration=1
```

These are distinct explicit transfer occurrences.

V2 treats them as one identity and, because the objects differ, raises a
conflicting-duplicate error instead of counting two transfers.

## Why current RED coverage misses it

The V2 regression tests prove only:

```text
same pair/kind + different identifier → 2
same exact transfer object duplicated → 1
```

They do not test:

```text
same identifier + different iteration → 2 valid occurrences
```

## Impact

Valid canonical multi-iteration cross-domain evidence can fail closed as a
false identity conflict, and `cross_domain.transfers` is not exact for the full
canonical contract.

## Required remediation

Define occurrence identity from the actual canonical occurrence dimensions.

At minimum inspect and test a deterministic identity equivalent to:

```text
source_domain
target_domain
kind
identifier
iteration
```

plus any other canonical field required by the real engine semantics.

Do not include raw `value`, free text `reason`, or private payload content in a
public identity.

Add RED tests proving:

```text
same exact transfer duplicated → one
same identifier, same iteration, conflicting public identity fields → fail closed
same identifier, different iteration → two
same pair/kind, different identifier → two
```

---

# 6. V2 MAJOR-02 — Canonical permission evidence is still not bound end-to-end, and malformed typed evidence does not fail closed

This is the residual canonical-evidence defect from V1 MAJOR-02.

## 6.1 Permission rejection identity drops operation version

V2 documents:

```text
stable occurrence identity is operation_id + operation_version
```

but implements:

```python
if isinstance(evidence, DomainOperationPermissionDecision):
    if evidence.decision is PermissionOutcome.DENY:
        return (evidence.operation_id,)
```

The canonical contract contains both:

```text
operation_id
operation_version
decision
```

Two denied canonical decisions for:

```text
operation_id=domain.op
operation_version=1.0.0
```

and:

```text
operation_id=domain.op
operation_version=2.0.0
```

are distinct canonical decisions.

V2 collapses them to the same evidence reference and reports one rejection.

The RED tests use distinct operation IDs and therefore do not cover the bug.

## 6.2 Canonical permission log projection reads the wrong fields

`DomainObservabilityEvidence.permission_evidence` is now typed as:

```text
DomainOperationPermissionDecision
```

but `DomainObservabilityService._project_permission()` still projects it as if
it were another contract:

```python
outcome = getattr(result, "outcome", None)
...
source_id = getattr(result, "decision_id", None) or type(result).__name__
primary_domain = getattr(result, "domain_id", None)
metadata = {"action": getattr(result, "action", None)}
```

The canonical `DomainOperationPermissionDecision` exposes:

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

It does not expose:

```text
outcome
decision_id
domain_id
action
```

Consequences for a real canonical permission decision:

```text
status becomes "None"
source_id becomes "DomainOperationPermissionDecision"
primary_domain becomes None
metadata.action becomes None
```

Multiple permission decisions also share the same synthetic class-name
`source_id`.

That is not an accurate structured observability projection.

## 6.3 Typed evidence fields do not enforce their canonical runtime contract

`DomainObservabilityEvidence` has improved type annotations, but its
`__post_init__()` only converts each field to `tuple`.

It does not validate element types.

The V2 test itself demonstrates this by passing:

```python
resource_evidence=({"reused": True, "reuse_count": 3},)
```

even though the declared public type is:

```text
tuple[DomainResourceResolution | DomainResourceBinding, ...]
```

The object is silently accepted.

The approved spec says:

```text
Malformed or unsafe evidence must fail closed.
```

A dictionary supplied to a public field whose canonical contract is explicitly
`DomainResourceResolution | DomainResourceBinding` is malformed evidence, not a
valid unsupported canonical source.

The same runtime validation gap exists for the other evidence tuple fields.

## Impact

Canonical denied decisions can be undercounted, permission log entries contain
incorrect status/identity, and malformed non-canonical values can enter the
public evidence aggregate without failing closed.

## Required remediation

1. Bind permission rejection reference identity to at least:

```text
operation_id + operation_version
```

using a deterministic safe representation.

2. Update `_project_permission()` to consume the actual canonical
   `DomainOperationPermissionDecision` fields.

3. Use a stable permission log `source_id` derived from canonical safe fields,
   not the class name.

4. Runtime-validate `DomainObservabilityEvidence` tuple element types against
   the declared canonical contracts.

5. Invalid element types must raise
   `InvalidDomainObservabilityEvidenceError` with safe field/source diagnostics.

6. Replace the current duck-typed knowledge-reuse test with:

```text
malformed resource evidence → fail closed
valid canonical resource evidence with no explicit reuse contract
→ knowledge.reused UNAVAILABLE
```

7. Add regressions for:

```text
same operation ID + two semantic versions + DENY → 2
canonical permission log status == deny
canonical permission log source IDs are distinct/stable
invalid permission/resource/approval evidence element → fail closed
```

---

# 7. V2 MAJOR-03 — Source precedence is still not implemented; sorting is not occurrence deduplication

## Requirement

The approved spec states for `DomainObservabilityLogEntry`:

```text
Source precedence

1. canonical DomainEvent
2. canonical DomainTrace
3. canonical public operation/workflow/session result when no event/trace
   represents the required roadmap field.

The same authoritative occurrence MUST NOT be double-counted merely because it
appears in both an event and a trace.

Deduplication must use explicit source/reference identity, not fuzzy matching.
```

The implementation plan additionally requires:

```text
DomainEvent
→ DomainTrace
→ canonical public result only when event/trace does not already represent
  the occurrence
```

## Audited V2 code

`DomainObservabilityService.build_report()` still does:

```python
for event in evidence.events:
    projected.append(self._project_event(event))

for trace in evidence.traces:
    projected.append(self._project_trace(trace))

for operation in evidence.operation_evidence:
    projected.append(self._project_operation(operation))

for workflow in evidence.workflow_evidence:
    projected.append(self._project_workflow(...))

...
```

and finally:

```python
log_entries = tuple(
    sorted(projected, key=lambda entry: (entry.source_kind, entry.source_id))
)
```

This is deterministic ordering.

It is not source precedence.

It is not occurrence normalization.

No explicit shared reference identity is used to suppress a lower-precedence log
entry when an Event/Trace already represents that occurrence.

The report service also does not normalize duplicate identical canonical
operation/workflow/etc. evidence before log projection. Metric normalization and
log projection therefore have different occurrence semantics.

## V2 RED test proves the wrong behavior

`test_shared_reference_occurrence_is_not_duplicated()` says:

```text
One logical occurrence represented by event+trace+result counts once.
```

but asserts:

```python
assert len(report.log_entries) == 3
```

The main expanded acceptance repeats the same pattern:

```python
overlap_report = service.build_report(overlap_evidence)
assert len(overlap_report.log_entries) == 3
```

Moreover, the constructed event/trace/result do not contain the required
explicit shared occurrence reference that would allow canonical precedence to
be tested.

Thus the V2 tests mark the unremediated behavior green.

## Additional determinism consequence

Sorting by:

```text
(source_kind, source_id)
```

is not sufficient when duplicate entries share the same key but differ in
content. Python's stable sort preserves caller order among equal keys, so a
permutation can still alter serialization/digest unless occurrence identity is
normalized first.

## Impact

The Phase 10.37 report can duplicate a single authoritative occurrence across
Event/Trace/result channels and does not implement the architecture approved in
the spec.

This is a defining DP-037 invariant.

## Required remediation

1. Add a private occurrence-normalization stage before log projection.
2. Use explicit canonical reference identity only.
3. Apply precedence:

```text
DomainEvent
→ DomainTrace
→ public result only if not already represented
```

4. Keep all legitimate evidence references, but produce one logical occurrence
   log entry.
5. Normalize identical same-source duplicates before sorting.
6. Conflicting duplicate source identity must fail closed.
7. Then sort canonical normalized log entries.
8. Add RED coverage with genuinely linked Event/Trace/result evidence.

No new store, registry, event catalog, trace system or persistence layer is
permitted.

---

# 8. V2 MAJOR-04 — AT-DP-037 remains a false-positive acceptance for the residual defects

The V2 acceptance is much stronger than V1 and now covers workflow evidence,
resource bindings, health version checks, duplicate evidence and order
permutation.

However, it still cannot be accepted as `AT-DP-037=PASS`.

## 8.1 Overlap checkpoint asserts the opposite of the spec

The acceptance label says:

```text
Event/trace/result overlap does not duplicate one occurrence
```

but asserts:

```python
assert len(overlap_report.log_entries) == 3
```

That is exactly the three-channel duplication the source-precedence rule is
intended to prevent once explicit shared identity exists.

## 8.2 The overlap fixture is not actually connected by shared occurrence identity

The event, trace and operation result are placed in the same evidence aggregate,
but they are not connected by the explicit canonical reference identity required
by the plan.

Co-location is not proof that they represent the same occurrence.

Therefore the acceptance neither proves successful deduplication nor proves the
negative case where unrelated evidence must remain separate.

## 8.3 Residual MAJOR-01 / MAJOR-02 cases are not covered

The expanded acceptance does not prove:

```text
same transfer identifier + different iteration → distinct occurrences
same permission operation ID + different versions → distinct denied decisions
canonical permission log uses decision/status correctly
malformed typed evidence fails closed
```

## Audit interpretation

The pytest node may be green, but the named acceptance contract is not satisfied.

Therefore:

```text
AT-DP-037=FAIL
```

for V2 closure semantics.

## Required remediation

Expand the acceptance again, narrowly, to include the exact residual cases.

At minimum:

```text
1. genuinely linked Event/Trace/result occurrence → one logical log occurrence
2. unrelated Event/Trace/result → remain distinct
3. same transfer identifier, iteration 0 and 1 → two transfers
4. same permission operation ID, versions 1.0.0 and 2.0.0, both DENY → two
5. canonical permission log status/source identity exact
6. malformed evidence tuple element → fail closed
7. reordered normalized evidence → identical report/digest
```

---

# 9. Positive V2 findings retained

The re-audit positively accepts the following improvements:

```text
generic evidence dedup now returns deduplicated values
distinct load attempts are counted independently
resource metric attribution uses DomainResourceBinding.domain_id
process-memory id(item) fallback removed
knowledge.reused stays UNAVAILABLE without explicit canonical reuse
session refs no longer imply degradation
degraded-session metric counts unique session IDs
health manifest validation binds domain + current version + PASSED
report clock capture improved
derived timestamps use captured generated_at
log ordering is explicitly sorted
health_domain_ids ordering is canonicalized
DomainConflictReference.source_id fix is correct
V1 historical audit artifact is preserved
V2 bundle is exact-HEAD and SHA-bound
```

The high-level architecture still has no evidence of:

```text
parallel observability store
parallel repository
parallel event bus
parallel runtime
parallel registry
parallel loader
parallel trace
DomainAPI expansion
Phase 10.33 event-catalog expansion
```

These positive findings should be preserved in the next remediation.

---

# 10. DP-037 assessment

The architectural direction remains correct.

However DP-037 requires one projection that is:

```text
canonical-evidence-bound
exact when observed
correctly unavailable otherwise
deterministic
deduplicated by authoritative occurrence identity
source-precedence-safe
```

V2 MAJOR-01 through MAJOR-03 show that these properties do not yet hold for all
public evidence paths.

Therefore:

```text
DP-037=NOT_VERIFIED
```

---

# 11. Final V2 status

```text
PHASE10_37_INDEPENDENT_REAUDIT_V2=FAIL

AUDITED_HEAD=5f4df64574d96de45724092cc8802210e00e243d
AUDIT_V2_BUNDLE_SHA256=addfa5505a6527416effe56731c5378aa3c4bed954b7316143c509809a3b617c

BLOCKERS=0
MAJORS=4
MINORS=0

V1_MAJOR_01=PARTIALLY_REMEDIATED
V1_MAJOR_02=PARTIALLY_REMEDIATED
V1_MAJOR_03=PARTIALLY_REMEDIATED
V1_MAJOR_04=REMEDIATED
V1_MAJOR_05=NOT_FULLY_REMEDIATED

DP-037=NOT_VERIFIED
AT-DP-037=FAIL
CLOSURE_ELIGIBLE=NO

PHASE10_38_STARTED=NO
NEXT=PHASE10_37_AUDIT_V2_REMEDIATION
```

---

# 12. V2 remediation scope lock

Remediate only the four residual V2 findings.

Expected production targets:

```text
cmm/domains/observability_metrics.py
cmm/domains/observability_service.py
```

Potential supporting target if public evidence runtime validation is best kept
with the aggregate:

```text
cmm/domains/observability_metrics.py
```

No new production subsystem is required.

Expected tests:

```text
tests/domains/test_domain_observability_metrics.py
tests/domains/test_domain_observability_metrics_adversarial.py
tests/domains/test_domain_observability_service.py
tests/domains/test_domain_observability_dp037_acceptance.py
```

A new focused audit-regression file is acceptable if it keeps the four V2
findings explicit.

Do not change:

```text
DomainAPI
Phase 10.33 event catalog
Domain Trace public contract
Cross-domain public contract
Permission public contract
Domain Session public contract
historical V1 audit report
historical V2 audit report after it is committed
```

Do not create:

```text
observability store
observability repository
event bus
runtime
engine
registry
loader
trace
session repository
```

Where canonical evidence cannot honestly support a metric:

```text
UNAVAILABLE
```

remains the correct result.

After remediation:

```text
RED regressions for all four V2 findings
→ minimal fixes
→ focused Phase 10.37
→ closed Phase 10 regressions
→ full Domain suite
→ global suite in real Git repo
→ Ruff
→ format
→ compileall
→ diff-check
→ worktree clean
→ quarantine stash preserved
→ NEW phase-10.37-audit-v3.tar.gz from exact committed HEAD
→ NEW SHA-256
→ independent ChatGPT re-audit V3
```

Do not overwrite V1 or V2 bundles.
