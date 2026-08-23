# Phase 10.26 — Independent Re-Audit V2

## Audit identity

- **Project:** CMM OS
- **Phase:** 10.26 — Languages Domain
- **Audit role:** independent software auditor
- **Candidate branch reported by bundle:** `feature/phase-10-domain-intelligence`
- **Original implementation/audit baseline:** `93c2679`
- **Remediated candidate HEAD:** `a2833ea1a7b64f64305dcd22fb6154c9d531b2c5`
- **Re-audit bundle:** `phase-10-26-independent-reaudit-bundle.tar.gz`
- **Expected SHA-256:** `ddfc53eaabc19027005793ae9d986a636fc3f693b4d31e495500827577369dc6`
- **Observed SHA-256:** `ddfc53eaabc19027005793ae9d986a636fc3f693b4d31e495500827577369dc6`
- **Bundle integrity:** PASS
- **Repository modified by this audit:** NO
- **Push:** NO
- **Merge:** NO
- **Verdict:** `FAIL`

---

# Executive conclusion

The remediation is a **large and real improvement** over the first audited candidate.

The following first-audit defects are materially fixed:

- workflow `VALIDATE` nodes no longer encode ordinary pedagogical outcomes;
- generic evidence IDs no longer create `CERTIFIED` records;
- evidence deduplication no longer treats caller IDs as provenance;
- stable level/error-pattern reasoning now requires meaningful independence/comparability;
- progression rule now requires a historical baseline and comparable evidence;
- certification temporal authority now distinguishes current/stale/unknown sources;
- the real `DomainPermissionGate + ApprovalService` lifecycle is regression-tested;
- the two explicitly authorized shared-engine changes are narrow and justified;
- the connected candidate now genuinely executes the real resolver, composer, all nine Languages workflows and accumulated `run.outputs`.

However, **Phase 10.26 is still not ready for closure**.

The V2 re-audit found:

```text
BLOCKERS=2
MAJORS=3
MINORS=0
```

The main reason is that `AT-DP-026` still does not prove the complete frozen acceptance contract: it replaced required calendar-action and trace semantics with other checkpoints while retaining a count of 45.

The V2 audit also reproduced semantic defects in operation result builders that the 11,316-test green suite does not currently catch.

---

# Sources reviewed

Authoritative design and plans:

```text
docs/superpowers/specs/2026-08-23-languages-domain-design.md
docs/superpowers/plans/2026-08-23-languages-domain-implementation.md
docs/superpowers/audits/2026-08-23-phase-10-26-independent-audit.md
docs/superpowers/plans/2026-08-23-languages-domain-audit-remediation.md
```

Current Phase 10.26 documentation:

```text
ROADMAP.md
docs/roadmap/phase-10-domain-intelligence.md
docs/reference/languages-domain.md
docs/reference/domain-intelligence-requirements-matrix.md
```

Production:

```text
cmm/domains/languages/*.py
cmm/domains/composition_items.py
cmm/workflows/engine.py
```

Tests:

```text
tests/domains/test_languages_domain_*.py
tests/domains/test_domain_permission_gate.py
tests/workflows/*
selected resolver/composer/shared regression tests bundled for re-audit
```

Evidence:

```text
evidence/languages-focused.txt
evidence/workflow-execution-matrix.txt
evidence/composition-resolver-matrix.txt
evidence/permission-connected-matrix.txt
evidence/all-domains.txt
evidence/global-pytest.txt
evidence/ruff.txt
evidence/ruff-py310.txt
evidence/compileall.txt
evidence/fresh-import-canon.txt
evidence/semantic-direct-probes.txt
evidence/connected-acceptance-markers.txt
evidence/tdd-red-record.md
evidence/final-code-review.md
evidence/git-diff-93c2679-to-a2833ea1a7b64f64305dcd22fb6154c9d531b2c5.patch
```

---

# Fresh evidence status

The bundle records these fresh remediation-side verification results:

```text
Languages focused: 142 passed
Workflow engine/execution consumers: 173 passed
Composer/resolver matrix: 425 passed
Permission/memory/connected acceptance: 63 passed
All domains: 5786 passed
Global suite: 11316 passed
Semantic direct probes: 16/16 PASS
Ruff: PASS
Ruff py310: PASS
compileall: PASS
fresh import: PASS
catalog: 16/15/14/15/9
Languages production modules: 14
git diff --check: PASS
Paternidad diff from 93c2679: empty
```

The independent auditor also performed source-level/metamorphic probes directly against the exact bundled implementation for the new findings documented below.

The closed re-audit bundle intentionally contains selected shared contracts rather than the complete repository dependency graph, so the full 11,316-test suite was not re-executed inside the bundle itself. Its captured output was reviewed as evidence; the new defects below were independently reproduced from the exact bundled source.

---

# Canon audit

**PASS**

The canonical pack remains:

```text
domain:languages
Idiomas
LanguageLearningProfile

16 entities
15 resources
14 rules
15 operations
9 workflows
14 production modules
```

`languages.progress_checkpoint` remains canonical.

No package-boundary drift was found.

---

# Authorized shared changes audit

## `b899502 fix(domains): support typed metadata in domain composition`

**PASS**

The shared change in `cmm/domains/composition_items.py` is narrow.

The extraction path now behaves essentially as:

```python
meta = definition.metadata
if meta is None:
    return None

free_meta = meta if isinstance(meta, Mapping) else meta.metadata
rp = free_meta.get("reasoning_profile")
```

This correctly supports typed `DomainMetadata` while preserving mapping compatibility.

No scoring, ranking, primary/supporting selection or Languages-specific adapter was added.

## `8430794 fix(workflows): expose accumulated outputs to ready-node adapters`

## `8048abc fix(workflows): preserve adapter run state semantics`

**PASS**

The final shared workflow change is narrow:

```python
adapter_run = replace(run, outputs=outputs)
outcome = self._coerce(
    self._node_adapter(node, adapter_run),
    node_id,
)
```

The re-audit found no change to:

```text
scheduling
ordering
readiness
node-state semantics
pause/resume semantics
public output shape
```

Shared regressions prove producer output visibility, multiple accumulated outputs and preservation of the other observable `WorkflowRun` fields.

These shared changes are not findings.

---

# Disposition of the first independent-audit findings

| Original finding | V2 disposition |
|---|---|
| B-001 — disconnected `AT-DP-026` | **PARTIALLY REMEDIATED / still blocking** |
| B-002 — workflow gates encode fixed outcomes | **RESOLVED** |
| M-001 — generic evidence may become CERTIFIED | **RESOLVED** |
| M-002 — duplicate/non-comparable evidence inflation | **RESOLVED** |
| M-003 — progression ignores baseline/comparability | **RESOLVED at rule level** |
| M-004 — stale/current certification precedence | **RESOLVED** |
| M-005 — real permission lifecycle not proven | **RESOLVED** |

B-001 remains unresolved for two independent reasons documented as V2 blockers below.

---

# Positive remediation findings

## Workflow invariant gates

**PASS**

The current workflows gate invariant/boundary fields rather than fixed pedagogical results.

Examples now include:

```text
certificate_overwritten=False
skill_gaps_erased=False
evidence_boundary_valid=True

stable_proficiency_changed=False
error_pattern_promoted_without_evidence=False

pronunciation_evidence_valid=True
pronunciation_inferred_from_transcript_only=False

valid_variety_misclassified=False
proficiency_upgraded_without_evidence=False

pattern_evidence_valid=True
pattern_promoted_without_independent_recurrence=False

calendar_modified=False
external_action_executed=False

temporal_evidence_valid=True
readiness_promoted_to_proficiency=False
registration_performed=False
payment_performed=False
submission_performed=False

progression_evidence_valid=True
cross_skill_inflation=False
```

No current Languages workflow wait-condition uses the previously forbidden ordinary outcomes:

```text
is_correct
score
estimated_level
pattern_candidate
pronunciation_assessed
needs_verification
stable_progression
is_certified
stable_update_supported
```

This closes B-002 structurally.

## Certification evidence authority

**PASS**

`classify_proficiency_record()` now requires recognized official credential source kind, credential reference and certification provenance.

Generic caller IDs do not certify.

## Evidence independence

**PASS**

Caller-controlled `id` is no longer canonical provenance.

The re-audit confirmed dedicated provenance/comparison logic for stable-level, pattern and progression semantics.

## Progression rule

**PASS**

At the canonical rule layer:

- no baseline -> insufficient evidence;
- explicit comparability is required;
- current evidence needs grounded provenance;
- shared comparison key is required;
- stable improvement requires multiple current provenance units.

A separate operation-level defect is documented below; that does not invalidate the improvement to `evaluate_progression()` itself.

## Certification temporal authority

**PASS**

The rule now ranks current official information above stale official information and preserves verification requirements for stale/unknown decision-critical data.

## Permission / memory lifecycle

**PASS**

Current tests use the real:

```text
DomainPermissionResolver
DomainPermissionGate
ApprovalService
InMemoryApprovalRepository
to_approval_requirement
```

and cover:

```text
no approval
valid exact approval
one-shot consumption
reuse denial
expiry
wrong actor/session/scope
policy reevaluation
proposal before consumption
supporting-domain non-widening
```

This closes M-005.

---

# V2 findings

# V2-B-001 — BLOCKER — Frozen calendar-action path is absent from connected `AT-DP-026`

## Exact requirement

Frozen design:

`docs/superpowers/specs/2026-08-23-languages-domain-design.md:4187-4192`

requires:

```text
34. Languages proposes a review schedule.
35. No calendar mutation occurs.
36. The user asks to add a calendar event.
37. Languages routes this to the shared approval/external-operation path
    rather than performing the write itself.
38. A persistent proficiency/progress update is proposed through shared memory.
39. Consent and permission are validated before persistence.
```

The required permission tests also explicitly require:

`docs/superpowers/specs/2026-08-23-languages-domain-design.md:3935-3947`

```text
calendar proposal -> allowed as proposal
calendar write -> not directly authorized by Languages
external communication -> shared approval path
```

## Actual implementation

`tests/domains/test_languages_domain_dp026_acceptance.py:463-465`

proves only:

```python
spaced["calendar_modified"] is False
and spaced["external_action_executed"] is False
```

Immediately afterward, the scenario enters `permission_and_memory()`.

The only permission capability exercised by the connected acceptance is:

`tests/domains/test_languages_domain_dp026_acceptance.py:476-483`

```python
required_permissions=(
    PermissionCapability.MEMORY_WRITE.value,
)
```

Independent source search over the acceptance test found no:

```text
SCHEDULE_MODIFY
calendar_event request
calendar-write permission
calendar external-operation request
```

## Why the 45-checkpoint marker is misleading

The test still has exactly 45 checkpoint names, but the frozen 45 semantic steps were not preserved one-for-one.

The current scenario inserted additional implementation-oriented checkpoints such as:

```text
standard bootstrap
resolution-context construction
stale-only second certification run
```

while omitting frozen steps 36–37.

Therefore:

```text
AT_DP_026_CHECKPOINTS=45
```

proves only a list length, not semantic equivalence to the frozen 45-step acceptance scenario.

## Why this is BLOCKER

The frozen acceptance explicitly uses the calendar request to prove the boundary:

```text
pedagogical proposal
!=
authorized external mutation
```

That is a core Domain Pack safety boundary, not an optional test detail.

The current candidate acceptance can pass without ever demonstrating routing of the user's requested calendar mutation into the shared approval/external-action mechanism.

## Minimal remediation

Extend the connected scenario without replacing other frozen semantics.

Prefer preserving the frozen semantic sequence and, if implementation-specific diagnostics are useful, record them as assertions rather than consuming canonical checkpoint numbers.

Use the real shared permission/external-operation path for a calendar-write request.

Required proof:

```text
review proposal produced
calendar state unchanged
user requests calendar mutation
Languages itself does not mutate
shared gate/path returns approval-required or equivalent authorized boundary
no mutation before shared authorization/execution
```

Do not create a Languages calendar operation.

## Required regression

A connected acceptance test must fail if the calendar-write routing stage is removed while the checkpoint count remains 45.

---

# V2-B-002 — BLOCKER — Connected trace still does not satisfy the frozen trace minimum

## Exact requirement

Frozen trace requirements:

`docs/superpowers/specs/2026-08-23-languages-domain-design.md:3314-3342`

require preservation, where applicable, of:

```text
resolved primary/supporting domains
selected LanguageLearningProfile mode
language
preferred variety
active goal refs
evidence refs
skill scope
proficiency kind
framework
uncertainty
selected rules
operation results
workflow state
observed errors
pattern decisions
progression decisions
certification-source authority
permission decisions
memory proposal state
cross-domain result refs
presentation requirements
```

and:

```text
Trace must reference actual runtime result IDs.
Do not fabricate semantic-looking IDs from response text.
```

Required trace tests are even more explicit:

`docs/superpowers/specs/2026-08-23-languages-domain-design.md:3982-3999`

```text
selected primary/supporting domains
profile mode
actual operation/workflow result IDs
evidence refs
proficiency kind
skill scope
rule decisions
permission decisions
memory proposal state
cross-domain result refs
```

Frozen AT-DP-026 step 44 requires actual:

```text
resolver
workflow
operation
evidence
rule
permission
memory-proposal
result IDs
```

## Actual connected trace

`tests/domains/test_languages_domain_dp026_acceptance.py:638-690`

uses only these explicit `DomainTraceReferenceKind` values:

```text
WORKFLOW_RUN
WORKFLOW_RESULT
OPERATION_RESULT
APPROVAL_REQUEST
APPROVAL_DECISION
FINDING
```

Independent search found **no** connected acceptance references of kind:

```text
PROFILE
RULE_RESULT
PERMISSION_DECISION
```

and no evidence-reference trace kind representing the evidence/rule decisions required by the frozen trace contract.

Only the assessment's `assessment_id` is added as an `OPERATION_RESULT`.

The trace therefore does not establish the required full operation/evidence/rule/permission provenance.

## Semantic type error

For every workflow the test creates:

```python
kind=DomainTraceReferenceKind.WORKFLOW_RESULT
ref_id=run.execution_result.events[-1].event_id
```

at lines 644–648.

But the shared workflow contract defines:

```python
@dataclass(frozen=True, slots=True)
class WorkflowEvent:
    event_id: str
    event_type: str
    workflow_id: str
    run_id: str
    ...
```

A `WorkflowEvent.event_id` is an event identifier.

It is not a `WorkflowResult` identifier.

The shared `WorkflowResult` contract is a different type and does not expose that event ID as its result identity.

Thus the trace labels an actual ID with the wrong semantic kind.

## Self-validating inventory weakness

The connected test constructs:

```python
inventory = DomainTraceReferenceInventory(
    references=trace.all_references(),
    ...
)
```

and then validates the trace against that inventory.

This proves referential self-consistency but cannot detect that:

```text
event ID was mislabeled as workflow result
required rule/profile/permission references are absent
```

The final assertion:

```python
required_trace_ids <= actual_produced_ids
```

only proves those selected IDs existed somewhere in scenario state; it does not prove correct semantic reference kind or required trace completeness.

## Memory proposal typing

The connected trace represents:

```python
memory_proposal.proposal_id
```

as:

```text
DomainTraceReferenceKind.FINDING
```

rather than a semantically explicit memory proposal/permission-state reference.

The shared enum currently has no dedicated memory-proposal kind, so this may require using the correct existing shared trace carrier rather than adding a Languages-specific type. If the shared Phase 10.17 trace contract genuinely cannot express the frozen memory-proposal state, stop and treat that as a shared-contract gap instead of inventing a fake kind.

## Why this is BLOCKER

B-001 from the first audit was specifically about a false connected acceptance and fabricated/semantically disconnected trace.

The runtime/workflow portion is now much stronger, but frozen step 44 is still not proven.

`AT-DP-026=PASS` therefore remains incomplete as closure evidence.

## Minimal remediation

Build a trace inventory from **independently collected runtime objects**, not from `trace.all_references()` itself.

Require an expected-kind mapping, e.g.:

```text
actual profile/profile-mode reference
actual rule decision refs
actual operation result refs
actual workflow run/result refs supported by shared contract
actual evidence refs
actual permission decision refs
actual memory proposal/binding state
actual cross-domain result
```

Then validate:

```text
trace reference ID exists
AND
trace kind matches owning runtime object's semantic kind
AND
all frozen required categories are represented
```

Do not label `WorkflowEvent.event_id` as `WORKFLOW_RESULT`.

If a real workflow-result ID is absent from the shared workflow contracts, use the canonical shared representation supported by the trace design or stop for a narrow shared-contract decision.

---

# V2-M-001 — MAJOR — Progress operation fabricates unrelated skill progress and positive state under insufficient evidence

## Exact files / symbols

`cmm/domains/languages/operations.py:1024-1053`

`generate_progress_review_result()`

## Frozen requirements violated

The frozen design explicitly requires:

`docs/superpowers/specs/2026-08-23-languages-domain-design.md:3744-3749`

```text
missing speaking evidence
-> no speaking estimate fabricated

skill-specific evidence
-> no unrelated-skill inflation
```

and:

`docs/superpowers/specs/2026-08-23-languages-domain-design.md:3816-3820`

```text
comparable repeated improvement -> stable improvement may be supported
non-comparable tasks -> insufficient evidence / qualified result
one poor session -> not automatic regression
skill improvement -> does not inflate all skills
```

Required presentation parity also says:

```text
generate_progress_review
-> uncertainty / insufficient evidence remains visible
```

## Actual production code

The operation delegates the overall progression classification correctly:

```python
prog = evaluate_progression(...)
```

but then always returns:

```python
"skill_progress": {
    "writing": "improving",
    "reading": "consolidated",
},
"active_patterns_count": 1,
"certification_readiness": "in_progress",
"recommended_next_focus": "Writing coherence and timed tasks",
"progression_evidence_valid": True,
"cross_skill_inflation": False,
```

independently of the supplied evidence.

## Independent exact-source reproduction

The auditor executed the exact bundled `evaluate_progression()` plus exact bundled `generate_progress_review_result()`.

Input:

```python
language="English"
period="month"
evidence=()
previous_evidence=()
skill="writing"
```

Actual result:

```python
{
    "overall_progression": "insufficient_evidence",
    "stable_progression": False,
    "skill_progress": {
        "writing": "improving",
        "reading": "consolidated",
    },
    "active_patterns_count": 1,
    "certification_readiness": "in_progress",
    "recommended_next_focus": "Writing coherence and timed tasks",
    "progression_evidence_valid": True,
    "cross_skill_inflation": False,
    ...
}
```

This output is internally contradictory.

The canonical rule says:

```text
insufficient_evidence
```

while the operation asserts positive progression in two skills, an active error pattern, certification progress and a concrete next focus.

`reading="consolidated"` is especially clear cross-skill inflation because the call explicitly scopes the evidence to `writing`.

The output simultaneously claims:

```text
cross_skill_inflation=False
```

which is false.

## Why existing tests missed it

`tests/domains/test_languages_domain_operations.py:251-268`

asserts only:

```python
stable_progression is True
progression_evidence_valid is True
cross_skill_inflation is False
```

for a valid writing progression case.

It never inspects the actual `skill_progress` keys against the evidence skill.

The workflow/adversarial tests similarly validate the invariant flag rather than checking that the output content satisfies the invariant.

This is exactly the class of false-positive invariant flag the V2 audit was designed to catch.

## Minimal remediation

Derive all progress-review fields from actual inputs.

At minimum:

- `skill_progress` only includes skills for which evidence exists;
- no positive skill state under insufficient evidence;
- no unrelated `reading` state from writing-only evidence;
- `active_patterns_count` derives from pattern input/state, not constant `1`;
- `certification_readiness` is unknown/not-assessed unless certification evidence/state is supplied;
- `recommended_next_focus` derives from actual supported gaps/goals/patterns or remains unset/qualified;
- `cross_skill_inflation` is computed from the resulting projection, not hard-coded.

## Required regressions

```text
no evidence
-> no positive skill progress
-> no active pattern fabricated
-> readiness unknown/not assessed

writing-only evidence
-> skill_progress contains no unrelated reading claim

insufficient_evidence
-> presentation preserves insufficient state

actual unrelated-skill insertion
-> cross_skill_inflation=True or result rejected
```

---

# V2-M-002 — MAJOR — Evidence-free operation helpers emit unsupported proficiency/feedback/readiness judgments

## Exact files / symbols

`cmm/domains/languages/operations.py`

- `assess_sample_result()` lines 616–660
- `review_writing_result()` lines 822–854
- `review_speaking_result()` lines 903–928
- `prepare_certification_result()` lines 999–1021

## Frozen requirements violated

Core profile priority:

```text
evidence > intuition about level
progress over time > isolated score
```

Writing/speaking assessment must be evidence appropriate.

The design states:

```text
review oral production when adequate evidence exists
```

and presentation assessment order includes:

```text
evidence
skill assessed
observed performance
strengths/errors
confidence
estimated range if justified
missing evidence
```

The implementation plan also requires malformed/missing inputs never to increase certainty.

## Independent exact-source reproductions

The auditor executed the exact bundled helper functions in isolation.

### Empty assessment object

Input:

```python
assess_sample_result(sample={})
```

Actual substantive output:

```text
observed_performance = "A2"
confidence = 0.75
strengths = ["Initial production"]
```

There is no writing text/evidence.

### Empty writing object

Input:

```python
review_writing_result(writing_sample={})
```

Actual substantive output:

```text
word_count = 0
strengths = ["Coherent structure", "Appropriate register"]
register_feedback = "Formal and appropriate."
estimated_level = "A2"
score = 0.85
proficiency_upgraded_without_evidence = False
```

The function therefore explicitly reports a high score, strengths, register judgment and an estimated level for zero words, while claiming no unsupported proficiency upgrade occurred.

### Empty speaking transcript

Input:

```python
review_speaking_result(audio_transcript={})
```

Actual substantive output:

```text
transcript_text = ""
fluency_score = 0.80
pronunciation_assessed = False
```

The pronunciation boundary is correctly preserved, but fluency is still positively scored without oral-production evidence.

### Certification preparation

`prepare_certification_result()` accepts `current_profile` but never reads it.

It always returns:

```text
readiness_score = 0.72
skill_gaps = ["Timed essay writing", "Formal monologue"]
```

independently of whether the current profile is absent, A1, C2, or contains different skill evidence.

This means a purpose-minimized cross-domain projection can export unsupported `estimated_readiness` and `blocking_language_gap`.

## Why existing tests missed it

The actual-output presentation test proves JSON safety and preservation of selected fields, but it does not test evidence-free/empty object semantics.

Operation schemas accept generic objects without requiring inner evidence fields such as non-empty text or grounded profile evidence.

Therefore `{}` can reach these helpers through structurally valid schemas.

## Minimal remediation

Do not fabricate positive judgments when the required evidence is absent.

Preferred fail-closed semantics:

```text
empty writing sample:
  observed/estimated level = absent/unknown
  score = absent/qualified according to schema
  confidence = 0 or absent
  strengths = []
  missing evidence includes writing sample

empty speaking evidence:
  fluency not assessed
  pronunciation not assessed
  missing evidence explicit

certification current_profile absent:
  readiness unknown / insufficient evidence
  gaps derived only from known requirements vs known profile
```

If current output schemas do not permit unknown/null for evidence-dependent fields, update those operation schemas narrowly rather than filling mandatory fields with invented certainty.

## Required regressions

Use schema-valid empty/minimal objects and prove they fail closed semantically.

Also prove presentation preserves the resulting unknown/missing-evidence state.

---

# V2-M-003 — MAJOR — `review_exercise_result()` accepts non-finite scores and leaks malformed numeric exceptions

## Exact file / symbol

`cmm/domains/languages/operations.py:784-819`

Problematic code:

```python
score = float(
    er.get(
        "score",
        1.0 if is_correct else 0.0,
    )
)
```

## Required contract violated

Original implementation plan:

`docs/superpowers/plans/2026-08-23-languages-domain-implementation.md:1575-1586`

requires a malformed/JSON matrix including:

```text
None
bool
int/float
strings
malformed mappings
duplicate IDs
NaN/Inf where numeric values are accepted
```

and:

```text
No public helper may leak accidental KeyError, TypeError, or AttributeError.
```

The remediation plan further requires:

```text
NaN/Inf cannot create certainty/progression
strict JSON all public semantic outputs
```

`rules.py` itself claims all public outputs are strict JSON-safe and malformed evidence fails closed.

## Independent exact-source reproduction

### NaN

Input:

```python
review_exercise_result(
    exercise_result={
        "is_correct": False,
        "score": float("nan"),
    }
)
```

Call succeeds and returns:

```text
score = nan
```

Strict:

```python
json.dumps(output, allow_nan=False)
```

raises:

```text
ValueError
```

### Infinity

Input:

```text
score = inf
```

Call returns `inf`; strict JSON serialization fails.

### Invalid string

Input:

```text
score = "not-a-number"
```

The helper leaks:

```text
ValueError: could not convert string to float
```

### Nested object

Input:

```python
score = {"nested": 1}
```

The helper leaks:

```text
TypeError: float() argument must be a string or a real number
```

## Why current tests missed it

The adversarial NaN/Inf coverage focuses on confidence/progression semantics.

There is no malformed-score matrix for `review_exercise_result()`.

Schema parity checks validate ordinary generated examples; they do not fuzz numeric values.

## Minimal remediation

Use the existing strict numeric-normalization pattern:

```text
bool -> invalid
non-number -> invalid/fail closed
NaN/Inf -> invalid/fail closed
finite numeric -> accepted
```

Do not allow the helper to emit a non-finite JSON number.

The semantic fail-closed result should be deterministic and should not accidentally mark the item correct or improve evidence.

## Required regressions

```text
score=NaN
score=+Inf
score=-Inf
score=True
score="not-a-number"
score={}
```

must all:

```text
not crash
not emit non-finite output
remain strict JSON-safe
not increase correctness/proficiency certainty
```

---

# Connected acceptance audit

## What is now genuinely connected

The V2 re-audit confirms substantial progress.

The current scenario really uses:

```text
build_standard_languages_domain_bootstrap
DefaultDomainResolver
DefaultDomainComposer
DomainWorkflowExecutor
all 9 canonical Languages workflow definitions
run.inputs
run.outputs
DomainPermissionResolver
DomainPermissionGate
ApprovalService
Languages memory proposal/binding validation
typed DomainResult
presentation
trace assembler/validator
```

Examples of actual state linkage:

- `update_level_evidence` consumes the real upstream `assess` output;
- exercise generation/review is linked through workflow outputs;
- roleplay consumes the conversation result;
- speaking review consumes roleplay/transcript state;
- error remediation consumes errors produced by earlier lesson/speaking workflows;
- certification adapter uses the actual temporal-source rule;
- the stale-only verification case reruns the real certification workflow.

This is no longer the disconnected helper narration from V1.

## Why candidate acceptance still cannot be called complete

Two frozen acceptance obligations remain unproven:

```text
calendar mutation request -> shared approval/external path
full typed trace provenance minimum
```

Therefore the marker:

```text
AT_DP_026_CONNECTED=PASS
```

is stronger than the evidence supports.

---

# Presentation audit

**PARTIAL PASS**

The remediation materially improves actual-output presentation parity, and pronunciation state is preserved.

However V2-M-001/V2-M-002 show that presentation cannot preserve epistemic truth if the underlying operation output already fabricates it.

Example:

```text
empty writing
-> operation says score .85 / A2 / coherent / appropriate register
-> presentation faithfully preserves a false upstream claim
```

This is primarily an operation-semantic defect, not a presentation-rendering defect.

---

# Cross-domain audit

**STRUCTURAL PASS, SEMANTIC DEPENDENCY ON M-001/M-002**

The real resolver/composer path for Oppositions + Languages exists and the projection uses the exact six-field allowlist.

No full vocabulary/error/transcript/writing-history export is present.

However fields such as:

```text
estimated_readiness
blocking_language_gap
progress_toward_shared_goal
```

must only be exported if their source operation values are evidence-grounded.

Because current certification/progress helpers can fabricate those values, purpose minimization is structurally correct while semantic provenance remains incomplete.

Fixing V2-M-001/V2-M-002 should resolve this without changing the six-field allowlist.

---

# Documentation audit

**PASS for current pre-re-audit status**

The current docs correctly avoid claiming closure.

Observed status includes:

```text
Phase 10.26 candidate audit remediation implemented
independent re-audit pending
DP-026 = REQUIRES_PHASE_INSPECTION
AT-DP-026 candidate PASS
```

Because this V2 audit returns `FAIL`, docs must not be advanced to audited/closed.

A later remediation-status update should record the V2 findings before the next re-audit.

---

# Paternidad regression audit

**PASS**

Bundled evidence reports:

```text
PATERNIDAD_DIFF_93c2679_TO_a2833ea...=EMPTY_PASS
```

No Phase 10.27 implementation change belongs to this remediation.

---

# Residual-risk analysis

The V2 findings reveal one general lesson:

```text
invariant flag == expected value
```

is not sufficient proof that the payload itself satisfies the invariant.

Examples:

```text
cross_skill_inflation=False
while reading progress is fabricated from writing-only evidence

proficiency_upgraded_without_evidence=False
while empty writing receives A2 + 0.85

progression_evidence_valid=True
while no-evidence payload contains positive progress claims
```

The final remediation should therefore add **content-derived invariant assertions**, not more hard-coded booleans.

Recommended generic regressions:

1. For every invariant boolean, mutate/source the payload into the prohibited state and prove the flag or validation reflects it.
2. For every evidence-dependent operation, run a schema-valid empty/minimal evidence case.
3. For every numeric input path, fuzz bool/non-number/NaN/Inf.
4. For trace, validate against an independently built expected-kind inventory rather than the trace's own references.
5. For connected acceptance, compare canonical semantic checkpoint identifiers/set against the frozen spec, not only `len(checkpoints) == 45`.

---

# Re-audit verdict

```text
FAIL
```

Counts:

```text
BLOCKERS=2
MAJORS=3
MINORS=0
```

## What passed

```text
bundle integrity
canonical 16/15/14/15/9 catalog
14-module package boundary
authorized composition shared fix
authorized workflow-output shared fix
B-002 workflow gate remediation
M-001 certification evidence remediation
M-002 provenance/comparability remediation
M-003 canonical progression rule remediation
M-004 temporal-authority remediation
M-005 real permission lifecycle remediation
real resolver/composer execution
real nine-workflow execution
real accumulated run.outputs
purpose-minimized six-field projection structure
Paternidad non-regression
pre-re-audit documentation state
```

## What still blocks closure

```text
V2-B-001 calendar mutation-request approval/external-action path absent from AT-DP-026
V2-B-002 connected trace does not meet frozen trace minimum and mislabels WorkflowEvent IDs as WORKFLOW_RESULT
V2-M-001 progress operation fabricates cross-skill/positive state under insufficient evidence
V2-M-002 multiple evidence-dependent operation helpers fabricate judgments for empty evidence
V2-M-003 review_exercise malformed/nonfinite numeric path is not strict JSON-safe
```

No production or repository file was modified by this independent re-audit.

---

```text
PHASE10_26_INDEPENDENT_REAUDIT_V2=FAIL
BLOCKERS=2
MAJORS=3
MINORS=0
ORIGINAL_B002=RESOLVED
ORIGINAL_M001=RESOLVED
ORIGINAL_M002=RESOLVED
ORIGINAL_M003_RULE=RESOLVED
ORIGINAL_M004=RESOLVED
ORIGINAL_M005=RESOLVED
ORIGINAL_B001=PARTIALLY_REMEDIATED_STILL_BLOCKING
AUTHORIZED_SHARED_FIXES=PASS
CANON=16_15_14_15_9
PACKAGE_BOUNDARY=14_PASS
PARENTHOOD_REGRESSION=PASS
REPO_MODIFIED=NO
PUSH=NO
MERGE=NO
CLOSURE=NO
```
