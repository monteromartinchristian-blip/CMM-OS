# CMM OS — Phase 10.52 — Independent Re-audit V2

**Audit date:** 2026-09-12
**Phase:** 10.52 — Mental Health Domain
**Audit type:** Independent exact-HEAD remediation re-audit
**Verdict:** **FAIL — one V1 major remains materially open**

## 1. Audited artifact

```text
BUNDLE=phase-10.52-mental-health-domain-reaudit-v2-2d70d7f.tar.gz
AUDITED_REMEDIATION_HEAD=2d70d7fecc79dee904340e77d63404b25ded2950
AUDIT_BUNDLE_SHA256=dc020cc7ae919566902e2e65c64d120ae8ee0644ce5b42f7deae8862222e4479
```

Independent verification:

```text
CALCULATED_SHA256=dc020cc7ae919566902e2e65c64d120ae8ee0644ce5b42f7deae8862222e4479
SHA256_MATCH=YES
GZIP_INTEGRITY=PASS
GIT_ARCHIVE_COMMIT_ID=2d70d7fecc79dee904340e77d63404b25ded2950
HEAD_MATCH=YES
ARCHIVE_MEMBERS=2300
```

Result:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD_PROVEN=YES
```

---

# 2. Frozen evidence integrity

The exact bundle preserves the approved Phase 10.52 design and plan:

```text
SPEC_SHA256=e42f894f3fdf2483d5b4c34cb9d3255ab1fae8af8a109ed65e7b998f84c989f7
PLAN_SHA256=0e2c96ef6b21b1c415325599ff40186ea8513e22760157b4e4a24cc755936562
```

The V1 independent audit remains unchanged:

```text
AUDIT_V1_SHA256=b75e644d2ef143a087990b27821c3403c362c4f7bb91cd74a4e5560c19a697f5
AUDIT_V1_IMMUTABLE=YES
```

Phase 10.53 remains absent:

```text
cmm/domains/neurodivergence/=ABSENT
PHASE10_53=NOT_STARTED
```

Package/test inventory remains:

```text
MENTAL_HEALTH_MODULES=19
MENTAL_HEALTH_PHASE_TEST_FILES=12
```

---

# 3. Re-audit V2 verdict

```text
INDEPENDENT_REAUDIT_V2=FAIL

BLOCKERS=0
MAJORS=1
MINORS=0

MAJOR_01=CLOSED
MAJOR_02=CLOSED
MAJOR_03=OPEN
MINOR_01=CLOSED

DP-052=NOT_VERIFIED
AT-DP-052_TEST_EXECUTION=PASS
AT-DP-052=FAIL_INDEPENDENT_ADEQUACY

PHASE10_52=IMPLEMENTED_PENDING_REMEDIATION
PHASE10_53=NOT_STARTED
CLOSURE_ELIGIBLE=NO
```

The remediation materially fixes three of the four V1 findings. The remaining
failure is narrow and does not require architectural redesign.

---

# 4. Independent executable verification

The audit sandbox still differs from the implementation environment:

```text
Python=3.13.5
libcst=not installed in audit sandbox
```

As in V1, the auditor used only external audit-environment compatibility shims:

```text
import-only libcst stub outside the audited tree
runtime-only compatibility patch for the pre-existing shared
@dataclass(slots=True) + zero-argument super() Python 3.13 issue
```

No audited source file was modified.

Independent focused execution on the exact V2 bundle:

```text
PHASE10_52_FOCUSED_TESTS=272_PASSED
```

Independent architecture + connected acceptance execution:

```text
ARCHITECTURE_PLUS_AT_DP_052=30_PASSED
```

Independent compile gate:

```text
COMPILEALL_FULL=PASS
```

Static anti-fragmentation scan:

```text
MentalHealthRegistry=0
MentalHealthLoader=0
MentalHealthResolver=0
MentalHealthRuntime=0
MentalHealthEngine=0
MentalHealthStore=0
MentalHealthMemoryStore=0
MentalHealthKnowledgeGraph=0
MentalHealthPlanner=0
MentalHealthWorkflowEngine=0
MentalHealthPermissionEngine=0
MentalHealthPrivacyEngine=0
MentalHealthTraceStore=0
MentalHealthValidationEngine=0
MentalHealthSafetyEngine=0
MentalHealthCrisisEngine=0
```

These green tests do not override the direct adversarial reproduction described
under MAJOR-03.

---

# 5. V1 finding closure matrix

| V1 finding | Re-audit V2 result | Independent basis |
| --- | --- | --- |
| MAJOR-01 — truthy malformed sensitive flags | **CLOSED** | direct adversarial reproduction now fails closed; expanded committed tests pass |
| MAJOR-02 — therapy provenance falsely claimed | **CLOSED** | missing provenance blocks; real canonical `ResourceProvenance` + per-turn `source_ref` succeeds; operation schema now requires provenance/source reference |
| MAJOR-03 — cross-domain provenance/authorization false positive | **OPEN** | canonical transfer object is now required, but transfer evidence is not bound per projected field and checkpoint 13 still does not prove canonical current permission/privacy composition |
| MINOR-01 — stale memory binding revocation evidence absent | **CLOSED** | committed real canonical memory validator proof now invalidates the same stale binding after permission revocation |

---

# 6. MAJOR-01 closure — strict high-stakes boolean semantics

V1 independently reproduced Python truthiness vulnerabilities such as:

```text
"false" -> fact
"false" -> Health clinical authority
"false" -> safety escalation
"false" -> longitudinal authorization
"false" -> cross-domain relevance
```

The remediation introduces one local pure helper:

```python
_strict_flag(...)
```

with the required semantics:

```text
literal True  -> true
literal False -> false
missing       -> explicit contract default
other present values -> false
```

Independent exact-V2 reproduction:

```text
classify_emotional_statement({"fact": "false"})
=> unknown

detect_health_owned_clinical_claim({"documented_diagnosis": "false"})
=> is_health_owned=False
=> primary_authority=domain:mental-health

evaluate_safety_proportionality(
    {"distress": True, "material_risk": "false"}
)
=> escalate=False

evaluate_safety_proportionality(
    {"material_risk": True, "credible": "false"}
)
=> escalate=False

authorized="false"
=> longitudinal rule status=blocked
```

The audited source no longer uses ordinary `bool(...)` for the V1-sensitive
authority/evidence/relevance flags.

Result:

```text
MAJOR_01=CLOSED
STRICT_BOOLEAN_FAIL_CLOSED=PASS
```

---

# 7. MAJOR-02 closure — real therapy source provenance

V1 found that a bare speaker label could produce:

```text
source_identity_preserved=True
```

without source evidence.

The remediated rule now consumes:

```text
canonical ResourceProvenance evidence
per-turn source_ref
speaker attribution
model-interpretation flag
```

and requires both canonical source provenance and a real per-turn source
reference.

Independent exact-V2 reproduction:

```text
turn={"id":"t1","speaker":"therapist"}
source_provenance absent
=> status=blocked
=> provenance_preserved=False
=> unprovenanced_turns=("t1",)
```

With real canonical provenance and a source reference:

```text
source_type=conversation
source_id=therapy:session:1
turn.source_ref=turn:1
=> status=applied
=> provenance_preserved=True
=> source_provenance_id=therapy:session:1
=> finding references include turn:1
```

The operation input schema now requires:

```text
transcript_ref
source_provenance
speaker_turns
```

and every `speaker_turn` requires:

```text
turn_id
speaker
source_ref
```

Checkpoint 7 now supplies real provenance and source references and includes a
negative missing-provenance case.

Result:

```text
MAJOR_02=CLOSED
THERAPY_SOURCE_PROVENANCE_REAL=PASS
```

---

# 8. MINOR-01 closure — stale binding fails after permission revocation

V1 found the runtime semantics correct but the required committed adversarial
evidence missing.

The remediation adds a real canonical memory-chain test that:

```text
1. builds a valid Mental Health binding
2. validates it
3. replaces the referenced permission decision with allowed=False
4. revalidates the same stale binding
5. requires the stale binding to be invalid
```

The same behavior is now connected into AT-DP-052 checkpoint 14.

The focused suite and acceptance both pass this evidence.

Result:

```text
MINOR_01=CLOSED
STALE_MEMORY_BINDING_AFTER_PERMISSION_REVOCATION=INVALID
```

---

# 9. MAJOR-03 remains open — canonical transfer evidence is not bound to the projected fields

## 9.1 What the remediation fixed

The V1 implementation accepted a plain untyped projection and hard-coded
`provenance_preserved=True`.

V2 materially improves this:

```text
CrossDomainContextTransfer is now required
non-empty provenance is required by the canonical contract
target must be domain:mental-health
unknown source domain is rejected
private transfer is rejected
non-transferable transfer is rejected
purpose mismatch is rejected
malformed relevance fails closed
```

Those are real improvements.

However, they do not close the complete V1 requirement.

## 9.2 Frozen V1 requirement

The immutable V1 audit required the remediated connected path to prove:

```text
source domain is known
target domain is Mental Health
provenance is non-empty and preserved
transfer is currently permitted
transfer is privacy-compatible
only purpose-relevant fields survive
irrelevant sensitive fields do not survive
malformed relevance does not become relevant
```

It also required:

```text
include only explicitly authorized fields needed for the task
```

and instructed checkpoint 13 to use:

```text
the real canonical transfer/composition path
or an official validated canonical representation that carries the same guarantees
```

## 9.3 Current implementation flaw

`PurposeMinimizedCrossDomainRule.evaluate()` does two independent operations:

1. it builds `included_fields` solely from:

```python
spec["relevant"] is literal True
```

2. it accepts any canonical transfer that passes structural checks.

It never requires a one-to-one or otherwise explicit binding between:

```text
projected included field
and
accepted transfer.identifier
```

After **one** accepted transfer exists, every `relevant=True` projection field is
returned as included.

Therefore provenance/authorization for one field can authorize unrelated fields.

## 9.4 Independent V2 adversarial reproduction

Projection:

```python
{
    "purpose": "emotional_context",
    "fields": {
        "authorized_field": {"relevant": True},
        "UNAUTHORIZED_SENSITIVE_FIELD": {"relevant": True},
    },
}
```

Canonical transfer evidence supplied only for:

```text
identifier=authorized_field
source_domain=domain:health
target_domain=domain:mental-health
provenance=("prov:1",)
private=False
transferable=True
reason=emotional_context
```

Exact V2 result:

```text
status=applied
included_fields=("authorized_field", "UNAUTHORIZED_SENSITIVE_FIELD")
rejected_transfers=()
provenance_references=("prov:1",)
```

The unrelated sensitive field therefore inherits the other field's provenance
and transfer authority.

An even stronger reproduction supplies a valid canonical transfer whose
identifier is not present in the projection at all:

```text
transfer.identifier=not_in_projection
```

The exact V2 result remains:

```text
status=applied
included_fields=("authorized_field", "UNAUTHORIZED_SENSITIVE_FIELD")
```

This proves that the rule validates the *existence* of some transfer, not the
authority/provenance of the actual projected fields.

## 9.5 Current checkpoint 13 remains insufficient

`test_checkpoint_13_supporting_context_is_purpose_minimized` manually constructs
`CrossDomainContextTransfer` instances.

It does not exercise the real canonical permission resolver or privacy
composition for the concrete projected field.

It separately passes one transfer per field in its happy-path fixture, but it
contains no adversarial that proves:

```text
relevant field without matching accepted transfer -> excluded/blocked
unrelated accepted transfer -> cannot authorize projection
```

It also labels:

```text
transferable=False
```

as an explicit permission denial, but the transfer dataclass itself is not a
canonical current `CrossDomainPermissionDecision`, and it carries no binding to
a current permission/privacy resolution.

The canonical repository does have real cross-domain permission resolution and
a cross-domain engine that blocks explicit denied domain paths before creating
transfers. The Mental Health checkpoint does not currently connect its
projection to that path.

## 9.6 Closure significance

The approved spec requires cross-domain context to be:

```text
authorized by canonical permissions
allowed by canonical privacy
compatible with current resolution/composition
minimized to the purpose
provenance-preserving
```

V2 still allows a relevant sensitive field with no matching provenance or
transfer evidence to survive.

This is a direct continuation of V1 MAJOR-03, not a new audit standard.

Result:

```text
MAJOR_03=OPEN
CROSS_DOMAIN_FIELD_AUTHORITY_BINDING=FAIL
CROSS_DOMAIN_CANONICAL_TRANSFER=PARTIAL
CROSS_DOMAIN_PROVENANCE_REAL=PARTIAL
CROSS_DOMAIN_PERMISSION_PRIVACY=NOT_CONNECTED_PER_PROJECTED_FIELD
```

---

# 10. Required MAJOR-03 remediation for V3

The next remediation must remain narrow.

Do not create a new cross-domain engine, registry, permission engine, privacy
engine, provenance store, or transfer contract.

Use the existing canonical infrastructure.

At minimum:

1. bind every `included_field` to accepted transfer evidence for that same
   identifier or to an existing canonical mapping that explicitly proves the
   relationship;
2. a relevant field without matching accepted transfer evidence must be
   excluded or block the projection;
3. a transfer for an identifier not present in the projection must not grant
   authority to projection fields;
4. rejected/private/non-transferable transfers must not be laundered by a
   separate accepted transfer;
5. checkpoint 13 must contain adversarials for those cases;
6. connect the happy path to current canonical permission/privacy evidence,
   preferably by exercising the existing cross-domain engine/composition path
   that produces accepted transfers after permission decisions, or by using an
   official existing validated representation that carries those decisions;
7. preserve the already-closed strict boolean and provenance behavior.

Required RED tests include at minimum:

```text
one authorized field + one relevant field with no transfer
    -> untransferred field not included

accepted transfer identifier absent from projection
    -> cannot authorize any projected field

one accepted transfer + one rejected transfer for a different relevant field
    -> rejected field not included

current canonical permission DENY
    -> corresponding field not included / path blocked

privacy-incompatible/private field
    -> corresponding field not included / path blocked
```

No broader redesign is authorized.

---

# 11. Architecture and anti-fragmentation

Independent V2 architecture checks remain green.

No parallel Mental Health infrastructure was found.

Result:

```text
ANTI_FRAGMENTATION=PASS
PARALLEL_RUNTIME=NO
PARALLEL_REGISTRY=NO
PARALLEL_RESOLVER=NO
PARALLEL_MEMORY_STORE=NO
PARALLEL_PRIVACY_ENGINE=NO
PARALLEL_PERMISSION_ENGINE=NO
PARALLEL_SAFETY_ENGINE=NO
PHASE10_53_NOT_IMPLEMENTED=YES
```

The required V3 remediation must preserve this PASS.

---

# 12. Test/gate interpretation

The remediation agent reported substantial repository-wide gate evidence,
including chunked Domain-suite execution because the WorkBuddy sandbox deadlocks
on long nested-collection runs.

This re-audit independently proves:

```text
FOCUSED_10_52=272_PASSED
ARCHITECTURE_PLUS_AT=30_PASSED
COMPILEALL=PASS
```

The exact focused acceptance passes as written.

However:

```text
passing pytest != independent acceptance adequacy
```

because MAJOR-03's adversarial demonstrates an uncovered semantic path.

The reported WorkBuddy sandbox limitations do not cause this finding and do not
change the V2 verdict.

---

# 13. DP-052 assessment

The Domain Pack architecture, privacy posture, Health authority separation,
therapy provenance path, memory proposal semantics, and anti-fragmentation are
materially present.

But DP-052 also requires purpose-minimized, permission-filtered,
privacy-filtered, provenance-preserving cross-domain coordination.

The exact V2 implementation can still import a relevant field without any
matching transfer/provenance evidence.

Therefore:

```text
DP-052=NOT_VERIFIED
```

---

# 14. AT-DP-052 assessment

The test file executes successfully:

```text
AT-DP-052_TEST_EXECUTION=PASS
```

But checkpoint 13 does not detect the field/transfer authority-laundering path
reproduced independently.

Therefore:

```text
AT-DP-052=FAIL_INDEPENDENT_ADEQUACY
```

---

# 15. Re-audit V2 final markers

```text
INDEPENDENT_REAUDIT_V2=FAIL

AUDITED_REMEDIATION_HEAD=2d70d7fecc79dee904340e77d63404b25ded2950
AUDIT_BUNDLE_SHA256=dc020cc7ae919566902e2e65c64d120ae8ee0644ce5b42f7deae8862222e4479

BUNDLE_INTEGRITY=PASS
SPEC_INTEGRITY=PASS
PLAN_INTEGRITY=PASS
AUDIT_V1_INTEGRITY=PASS
ANTI_FRAGMENTATION=PASS

FOCUSED_TESTS=272_PASSED
ARCHITECTURE_PLUS_AT=30_PASSED
COMPILEALL=PASS

BLOCKERS=0
MAJORS=1
MINORS=0

MAJOR_01=CLOSED
MAJOR_02=CLOSED
MAJOR_03=OPEN
MINOR_01=CLOSED

DP-052=NOT_VERIFIED
AT-DP-052_TEST_EXECUTION=PASS
AT-DP-052=FAIL_INDEPENDENT_ADEQUACY

PHASE10_52=IMPLEMENTED_PENDING_REMEDIATION
PHASE10_53=NOT_STARTED
CLOSURE_ELIGIBLE=NO

PUSH=NO
MERGE=NO
```

Phase 10.52 must not be closed from HEAD
`2d70d7fecc79dee904340e77d63404b25ded2950`.

A narrow MAJOR-03 remediation commit, full gates, and a **new exact-HEAD V3
bundle** are required.
