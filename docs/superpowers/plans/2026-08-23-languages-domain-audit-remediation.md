# Phase 10.26 — Languages Domain Independent-Audit Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate every finding from the first independent audit of Phase 10.26, rebuild `AT-DP-026` as a genuinely connected acceptance proof, and leave `domain:languages` ready for a second independent audit without changing the frozen `16/15/14/15/9` canon or shared architecture.

**Architecture:** Fix the semantic root causes inside the existing 14-module Languages Domain Pack: evidence identity/comparability, certified-evidence authority, progression temporality, invariant-based workflow gates, shared approval lifecycle coverage, real cross-domain composition, presentation parity, and connected acceptance. Reuse the existing `DefaultDomainResolver`, `DefaultDomainComposer`, `DomainWorkflowExecutor`, `DomainPermissionResolver`, `DomainPermissionGate`, canonical `ApprovalService`, shared memory proposal/binding contracts, and trace contracts. No new production module or shared engine is allowed.

**Tech Stack:** Python >=3.10, pytest >=9,<10, Ruff >=0.9,<1, existing CMM OS Domain Intelligence / Workflow / Permission / Approval / Memory / Trace contracts.

**Spec:** `docs/superpowers/specs/2026-08-23-languages-domain-design.md`

**Original implementation plan:** `docs/superpowers/plans/2026-08-23-languages-domain-implementation.md`

**Independent audit:** `docs/superpowers/audits/2026-08-23-phase-10-26-independent-audit.md`

## Global Constraints

- Expected branch: `feature/phase-10-domain-intelligence`.
- Remediation starting HEAD: `93c2679`.
- Known untracked `tmp/` is not part of the task and must remain untouched.
- No push.
- No merge.
- No changes to Phase 10.27 Paternidad.
- Preserve exact canonical counts: `16 entities / 15 resources / 14 rules / 15 operations / 9 workflows`.
- Preserve exact 14 production files under `cmm/domains/languages/`.
- Preserve exact workflow ID `languages.progress_checkpoint`.
- Do not change the frozen entity/resource/rule/operation/workflow catalogs.
- Do not introduce a Languages-specific planner, runtime, workflow engine, permission engine, memory store, knowledge store, conversation engine, assessment engine, lesson engine, spaced-review engine, or calendar engine.
- Do not modify shared infrastructure unless a new reproducible blocker proves the existing shared contract cannot express the frozen design. If that happens, STOP and report it.
- Strict TDD: no production fix before a failing regression that reproduces the audited defect.
- A regression must fail for the audited reason, not due to a typo/import error.
- Do not weaken existing tests.
- Do not use caller-controlled `id` values as evidence independence/provenance.
- Unknown/missing evidence metadata must never increase certainty.
- Business/pedagogical outcomes are not workflow safety gates.
- Workflow `VALIDATE` nodes may gate only invariant/boundary fields, not one particular score, level, correctness result, pattern state, readiness state, or progression outcome.
- `AT-DP-026` must be one state-linked deterministic scenario; a sequence of direct helpers with unrelated fixtures does not count.
- `AT-DP-026` must use actual resolver/composer/workflow/permission/memory/trace outputs and actual IDs produced by that run.
- Tests may import sibling domains/public APIs. Languages production code must not import sibling implementation internals.
- The audit report is authoritative for the seven current findings:
  - B-001 connected acceptance invalid;
  - B-002 workflow gates encode fixed success outcomes;
  - M-001 generic evidence can become CERTIFIED;
  - M-002 duplicate/non-comparable evidence inflates stable level/error pattern;
  - M-003 progression ignores comparability/baseline;
  - M-004 certification temporality ignores stale/current;
  - M-005 real PermissionGate/ApprovalService lifecycle not proven.
- Also close the audit's INFO residual-risk items where they materially strengthen re-audit:
  - real resolver/composition coverage;
  - actual operation outputs through presentation;
  - semantic workflow engine tests, not just field-name audits.

---

# File Map

## Production files allowed to change

```text
cmm/domains/languages/rules.py
cmm/domains/languages/operations.py
cmm/domains/languages/workflows.py
cmm/domains/languages/presentation.py        # only if actual-output parity exposes a real defect
cmm/domains/languages/trace.py               # only if connected trace exposes a real defect
cmm/domains/languages/permissions.py         # only if real lifecycle exposes a real defect
cmm/domains/languages/memory.py              # only if real lifecycle exposes a real defect
cmm/domains/languages/integration.py         # only if connected composition exposes a real defect
```

No other Languages production file should change unless a failing test demonstrates a direct requirement.

## Tests to modify/create

Modify:

```text
tests/domains/test_languages_domain_proficiency.py
tests/domains/test_languages_domain_error_correction.py
tests/domains/test_languages_domain_adaptation_progression.py
tests/domains/test_languages_domain_operations.py
tests/domains/test_languages_domain_workflows.py
tests/domains/test_languages_domain_permissions.py
tests/domains/test_languages_domain_memory.py
tests/domains/test_languages_domain_cross_domain.py
tests/domains/test_languages_domain_presentation.py
tests/domains/test_languages_domain_trace.py
tests/domains/test_languages_domain_dp026_acceptance.py
tests/domains/test_languages_domain_adversarial.py
```

Do not create a parallel second acceptance file unless necessary for readability. The canonical candidate acceptance remains `test_languages_domain_dp026_acceptance.py`.

## Documentation

Install before remediation:

```text
docs/superpowers/audits/2026-08-23-phase-10-26-independent-audit.md
docs/superpowers/plans/2026-08-23-languages-domain-audit-remediation.md
```

After successful remediation, update:

```text
docs/reference/languages-domain.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
ROADMAP.md
```

Status after remediation but before re-audit:

```text
Phase 10.26 implemented; first independent audit findings remediated;
candidate AT-DP-026 PASS; independent re-audit pending.

DP-026 = REQUIRES_PHASE_INSPECTION
```

Never mark independently audited or closed in this plan.

---

# Root-Cause Map

## Root Cause A — Evidence independence was based on caller identity instead of provenance/comparability

Affected:
- M-001
- M-002
- M-003

Current patterns:
- `classify_proficiency_record()` treats a generic evidence record with an `id` as enough to support `CERTIFIED`.
- `_deduplicate_evidence()` includes caller `id` in the dedup key, so the same source/content with two IDs becomes two observations.
- `evaluate_error_pattern()` falls back from `context_id` to `obs_id`, turning caller IDs into independent contexts.
- `evaluate_progression()` does not consume explicit comparability and invents a `0.5` historical baseline.

Fix at the evidence semantics, not at individual tests.

## Root Cause B — Workflow `VALIDATE` nodes were used as expected-output assertions

Affected:
- B-002
- hidden same-class defects in Conversation/Roleplay and Error Remediation

Examples of invalid gates:
- `is_correct=True`
- `score=0.85`
- `estimated_level=B2`
- `needs_verification=False`
- `stable_progression=False`
- `pattern_candidate=False`
- `pronunciation_assessed=False`

These are legitimate variable pedagogical outcomes. Replace them with invariant fields.

## Root Cause C — Temporal authority ranking did not combine authority + currentness

Affected:
- M-004

Source authority and temporal validity must be ranked together.

## Root Cause D — Candidate acceptance tested helpers, not the runtime graph

Affected:
- B-001
- M-005
- cross-domain INFO finding
- trace actual-ID concern

The final acceptance must use real shared machinery and consume prior outputs from `run.outputs`.

---

# Task 0 — Baseline + audit-plan installation gate

**Files:**
- Existing: all Languages files/tests
- Add docs only before agent execution:
  - `docs/superpowers/audits/2026-08-23-phase-10-26-independent-audit.md`
  - `docs/superpowers/plans/2026-08-23-languages-domain-audit-remediation.md`

- [ ] **Step 1: Verify branch / HEAD / clean tracked tree**

```bash
cd "/Users/chris/CMM OS"

test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"
test "$(git rev-parse --short HEAD)" = "<HEAD_AFTER_PLAN_INSTALL>"

UNEXPECTED="$(
  git status --porcelain --untracked-files=all \
    | grep -v '^?? tmp/' \
    || true
)"
test -z "$UNEXPECTED"
```

- [ ] **Step 2: Fresh baseline**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_languages_domain_*.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages \
  tests/domains/test_languages_domain_*.py

git diff --check
```

Record the baseline. Do not use it as evidence that findings are fixed.

---

# Task 1 — Close M-001/M-002/M-003/M-004 at the semantic source

**Files:**
- Modify: `cmm/domains/languages/rules.py`
- Modify: `cmm/domains/languages/operations.py`
- Modify: `tests/domains/test_languages_domain_proficiency.py`
- Modify: `tests/domains/test_languages_domain_error_correction.py`
- Modify: `tests/domains/test_languages_domain_adaptation_progression.py`
- Modify: `tests/domains/test_languages_domain_operations.py`
- Modify: `tests/domains/test_languages_domain_adversarial.py`

## 1A — Certified evidence must be closed and explicit

### Required production behavior

Introduce a private helper in `rules.py` equivalent to:

```python
_CERTIFIED_SOURCE_KINDS = frozenset({
    "official_certificate",
    "official_exam_result",
    "official_credential",
})

def _is_certifying_evidence(record: Any) -> bool:
    if not isinstance(record, Mapping):
        return False
    source_kind = _usable_text(record.get("source_kind"))
    credential_ref = (
        _usable_text(record.get("certificate_id"))
        or _usable_text(record.get("credential_id"))
        or _usable_text(record.get("official_result_id"))
    )
    provenance = (
        _usable_text(record.get("source_id"))
        or _usable_text(record.get("provenance_id"))
        or _usable_text(record.get("official_source_id"))
    )
    return (
        source_kind in _CERTIFIED_SOURCE_KINDS
        and credential_ref is not None
        and provenance is not None
    )
```

Use existing project normalization helpers/naming conventions rather than copying this verbatim if equivalent helpers exist.

`classify_proficiency_record(kind="CERTIFIED", ...)` must only emit:

```text
kind= CERTIFIED
is_certified=True
```

when at least one `_is_certifying_evidence(...)` record exists.

If caller requests `CERTIFIED` without adequate official evidence, fail closed to a non-certified representation. Preferred representation:

```text
kind = OBSERVED_PERFORMANCE or ESTIMATED only if separately justified
is_certified = False
certification_evidence_valid = False
```

Do not silently invent an estimate merely because caller requested CERTIFIED. Preserve requested/evidence state explicitly.

### RED tests

Add exact negatives:

```python
def test_generic_evidence_id_cannot_create_certified_record():
    record = classify_proficiency_record(
        kind="CERTIFIED",
        framework="CEFR",
        level_or_score="C1",
        skill_scope="writing",
        evidence=({"id": "caller-controlled"},),
    )
    assert record["is_certified"] is False

def test_user_sample_cannot_create_certified_record():
    record = classify_proficiency_record(
        kind="CERTIFIED",
        framework="CEFR",
        level_or_score="C1",
        skill_scope="writing",
        evidence=({
            "id": "sample-1",
            "source_kind": "user_sample",
            "source_id": "sample-1",
        },),
    )
    assert record["is_certified"] is False

def test_official_credential_can_create_certified_record():
    record = classify_proficiency_record(
        kind="CERTIFIED",
        framework="CEFR",
        level_or_score="B1",
        skill_scope="writing",
        evidence=({
            "source_kind": "official_certificate",
            "source_id": "cambridge-record-1",
            "certificate_id": "CERT-123",
        },),
    )
    assert record["kind"] == "CERTIFIED"
    assert record["is_certified"] is True
```

Verify RED before implementation.

## 1B — Canonical evidence identity must ignore caller IDs

### Required production behavior

Define one private evidence identity/comparability path reused by:

```text
_deduplicate_evidence
evaluate_level_update
evaluate_error_pattern
evaluate_progression
update_level_evidence_result
```

Evidence independence must derive from actual provenance/occurrence dimensions.

Suggested priority for provenance identity:

```text
provenance_id
source_id
assessment_id
sample_id
context_id
```

Caller-only `id` is metadata and must never by itself prove independence.

When no trustworthy provenance/occurrence identity exists:
- record may remain visible;
- it cannot be counted as a second independent observation.

For semantic deduplication, combine canonical provenance with relevant semantic dimensions:

```text
skill
observed / score
error_type
sentence/task_family as appropriate
```

Two records with:
- same provenance;
- same semantic observation;
- different `id`;

must collapse to one evidence unit.

## 1C — Stable level update requires explicit comparable independent evidence

`evaluate_level_update()` must require:
- target skill match;
- at least two distinct canonical provenance units;
- explicit comparability for the stable update set;
- consistent level signal.

Missing comparability must not default to comparable.

Recommended evidence shape:

```python
{
    "provenance_id": "assessment-2026-08-01",
    "skill": "writing",
    "observed": "B2",
    "score": 0.82,
    "comparable": True,
    "comparison_key": "CEFR-writing-argumentative",
}
```

For stable comparison, records must have:
- `comparable is True`;
- same non-empty `comparison_key`, or an existing equivalent project dimension explicitly proving comparability.

If comparable evidence is absent:

```text
stable_update_supported=False
reason=insufficient_comparable_evidence
```

### RED

```python
def test_same_provenance_different_ids_does_not_support_stable_level():
    evidence = (
        {
            "id": "caller-a",
            "provenance_id": "sample-1",
            "skill": "writing",
            "observed": "B2",
            "score": 0.8,
            "comparable": True,
            "comparison_key": "writing-argumentative",
        },
        {
            "id": "caller-b",
            "provenance_id": "sample-1",
            "skill": "writing",
            "observed": "B2",
            "score": 0.8,
            "comparable": True,
            "comparison_key": "writing-argumentative",
        },
    )
    result = evaluate_level_update(
        existing=None,
        evidence=evidence,
        target_skill="writing",
    )
    assert result["stable_update_supported"] is False

def test_two_non_comparable_samples_do_not_support_stable_level():
    ...
    assert result["stable_update_supported"] is False
    assert result["reason"] == "insufficient_comparable_evidence"
```

Control must prove two independent comparable sources can still support a stable proposal.

## 1D — Error-pattern independence must never fall back to caller ID

`evaluate_error_pattern()` must not use `obs_id` as context/provenance fallback.

Require actual independent occurrence identity, e.g.:

```text
context_id
provenance_id
sample_id
```

Same sentence/provenance under different IDs is one occurrence.

Explicit comparable context is required for recurrent pattern promotion.

### RED

```python
def test_same_error_same_provenance_different_ids_is_not_recurrent_pattern():
    observations = (
        {
            "id": "caller-a",
            "provenance_id": "sample-1",
            "sentence": "No sooner I had...",
            "error_type": "inversion",
            "comparable": True,
            "comparison_key": "free-writing",
        },
        {
            "id": "caller-b",
            "provenance_id": "sample-1",
            "sentence": "No sooner I had...",
            "error_type": "inversion",
            "comparable": True,
            "comparison_key": "free-writing",
        },
    )
    result = evaluate_error_pattern(observations=observations)
    assert result["eligible"] is False
    assert result["independent_occurrences"] == 1
```

Positive control: two distinct provenance IDs + same comparison key + same error type -> candidate/evidenced according to existing threshold semantics.

## 1E — Progression requires historical baseline + comparability

Remove any invented baseline such as:

```python
prev_avg = 0.5
```

`evaluate_progression()` must:
- require non-empty usable previous evidence for stable longitudinal claims;
- require current evidence to be comparable with the baseline;
- require independent provenance;
- preserve skill separation.

If no historical baseline:

```text
progression_outcome = insufficient_evidence
stable_progression = False
```

If current evidence is high but `comparable=False` or comparison keys differ:

```text
insufficient_evidence
```

One comparable better result may be:

```text
short_term_improvement
stable_progression=False
```

At least two independent comparable current observations against a grounded comparable baseline may support `stable_improvement`.

### RED

```python
def test_no_baseline_cannot_create_stable_progression():
    result = evaluate_progression(
        previous_evidence=(),
        current_evidence=(
            {... "score": 0.9, "comparable": True, ...},
            {... "score": 0.92, "comparable": True, ...},
        ),
        skill="writing",
    )
    assert result["stable_progression"] is False
    assert result["progression_outcome"] == "insufficient_evidence"

def test_non_comparable_results_cannot_create_stable_progression():
    ...
```

## 1F — Certification temporal authority must rank currentness before stale authority

Normalize temporal state deterministically.

Recognized current:

```text
date_valid is True
temporal_state in {"current", "active", "verified_current"}
```

Recognized stale/historical:

```text
date_valid is False
temporal_state in {"stale", "historical", "expired", "outdated"}
```

Missing/unknown is `unknown`, never current.

Required precedence:

```text
current official
>
current authoritative secondary
>
stale/historical official
>
historical memory
>
unverified guide
>
unknown/unverified source
```

Within the same effective rank:
- materially conflicting decision-critical facts => unresolved + verification required.

If the best available source is stale or unknown and `decision_critical=True`:

```text
needs_verification=True
```

### RED

```python
def test_current_official_beats_stale_official_even_when_stale_is_first():
    result = evaluate_certification_source(
        sources=(
            {
                "id": "stale",
                "source_type": "official",
                "date_valid": False,
                "format": "old-format",
            },
            {
                "id": "current",
                "source_type": "official",
                "date_valid": True,
                "format": "current-format",
            },
        ),
        decision_critical=True,
    )
    assert result["selected_source"]["id"] == "current"
    assert result["needs_verification"] is False

def test_stale_official_only_requires_verification_for_decision_critical_fact():
    ...

def test_unknown_official_temporality_requires_verification():
    ...
```

## 1G — `update_level_evidence_result()` must delegate to canonical rule semantics

Current operation logic must not implement a weaker independent rule such as:

```text
len(evidence) >= 2
```

It must call `evaluate_level_update()` with evidence derived from:
- upstream assessment;
- explicit evidence;
- target skill;
- existing record.

Add output invariant fields used later by workflows:

```text
certificate_overwritten
skill_gaps_erased
evidence_boundary_valid
```

Required values:

```text
certificate_overwritten=False
skill_gaps_erased=False
evidence_boundary_valid=True
```

Only if canonical helper semantics actually justify them.

Update `_OUTPUT_SCHEMAS` and schema-parity tests.

## Task 1 verification

Run targeted RED/GREEN cycles, then:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_languages_domain_proficiency.py \
  tests/domains/test_languages_domain_error_correction.py \
  tests/domains/test_languages_domain_adaptation_progression.py \
  tests/domains/test_languages_domain_operations.py \
  tests/domains/test_languages_domain_adversarial.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages/rules.py \
  cmm/domains/languages/operations.py \
  tests/domains/test_languages_domain_proficiency.py \
  tests/domains/test_languages_domain_error_correction.py \
  tests/domains/test_languages_domain_adaptation_progression.py \
  tests/domains/test_languages_domain_operations.py \
  tests/domains/test_languages_domain_adversarial.py

git diff --check
```

Commit:

```text
fix(domains): harden languages evidence semantics
```

---

# Task 2 — Replace business-outcome workflow gates with invariant gates

**Files:**
- Modify: `cmm/domains/languages/operations.py`
- Modify: `cmm/domains/languages/workflows.py`
- Modify: `tests/domains/test_languages_domain_operations.py`
- Modify: `tests/domains/test_languages_domain_workflows.py`

This task closes B-002 and proactively fixes every same-class gate.

## Rule

A workflow gate may assert:

```text
boundary preserved
no forbidden mutation/action
evidence contract valid
```

It may NOT require:

```text
right answer
specific score
specific CEFR level
pattern absent
pronunciation absent
verification unnecessary
stable progression absent
```

because each can be a valid result.

## New invariant fields

### `languages.update_level_evidence`

Output must include:

```text
certificate_overwritten: bool
skill_gaps_erased: bool
evidence_boundary_valid: bool
```

Gate:

```python
{
    "certificate_overwritten": False,
    "skill_gaps_erased": False,
    "evidence_boundary_valid": True,
}
```

Do not gate on `is_certified` or `stable_update_supported`.

### `languages.review_exercise`

Add:

```text
stable_proficiency_changed: bool
error_pattern_promoted_without_evidence: bool
```

Canonical operation values:

```text
False
False
```

Gate:

```python
{
    "stable_proficiency_changed": False,
    "error_pattern_promoted_without_evidence": False,
}
```

A wrong answer must still complete the workflow.

### `languages.review_speaking`

Add:

```text
pronunciation_evidence_valid: bool
pronunciation_inferred_from_transcript_only: bool
```

Semantics:

```text
no pronunciation evidence:
    pronunciation_assessed=False
    pronunciation_evidence_valid=True
    pronunciation_inferred_from_transcript_only=False

real pronunciation evidence:
    pronunciation_assessed=True
    pronunciation_evidence_valid=True
    pronunciation_inferred_from_transcript_only=False
```

Gate only:

```python
{
    "pronunciation_evidence_valid": True,
    "pronunciation_inferred_from_transcript_only": False,
}
```

Do not gate on `pronunciation_assessed=False`.

### `languages.review_writing`

Add:

```text
valid_variety_misclassified: bool
proficiency_upgraded_without_evidence: bool
```

Gate:

```python
{
    "valid_variety_misclassified": False,
    "proficiency_upgraded_without_evidence": False,
}
```

Do not gate on exact score/level.

### `languages.review_errors`

Add:

```text
pattern_evidence_valid: bool
pattern_promoted_without_independent_recurrence: bool
```

Gate:

```python
{
    "pattern_evidence_valid": True,
    "pattern_promoted_without_independent_recurrence": False,
}
```

A genuine evidenced pattern may exist and must not fail the workflow.

If Error Remediation currently gates a `review_exercise` output instead of the actual `review_errors` producer, fix the graph so the gate validates the producer that owns recurrent-pattern semantics.

### `languages.plan_review_schedule`

Existing invariant fields are correct:

```python
{
    "calendar_modified": False,
    "external_action_executed": False,
}
```

Keep them.

### `languages.prepare_certification`

Add:

```text
temporal_evidence_valid: bool
readiness_promoted_to_proficiency: bool
```

Gate:

```python
{
    "temporal_evidence_valid": True,
    "readiness_promoted_to_proficiency": False,
    "registration_performed": False,
    "payment_performed": False,
    "submission_performed": False,
}
```

Do not gate on `needs_verification=False`.

`needs_verification=True` is a valid safe result.

### `languages.generate_progress_review`

Add:

```text
progression_evidence_valid: bool
cross_skill_inflation: bool
```

Gate:

```python
{
    "progression_evidence_valid": True,
    "cross_skill_inflation": False,
}
```

Do not gate on `stable_progression=False`.

### `languages.create_learning_plan`

Existing onboarding gate remains:

```python
{
    "tracking_choice_resolved": True,
    "persistence_applied": False,
}
```

Prove both opt-in and opt-out complete.

## RED real-engine matrix

Use actual:

```python
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.workflows.engine import NodeExecution
from cmm.workflows.enums import WorkflowRunStatus
```

Follow the established Concerns helper:

```python
class _Ids:
    def __init__(self):
        self._index = 0
    def __call__(self):
        self._index += 1
        return f"id-{self._index}"
```

Operation adapter must return real operation outputs.

For each of 9 workflows, prove at least one legitimate variable outcome completes:

```text
Language Onboarding:
  opt_in -> complete
  opt_out -> complete

Proficiency Assessment:
  existing certified record preserved -> complete
  supported stable estimate update -> complete

Adaptive Language Lesson:
  incorrect exercise -> complete

Conversation & Roleplay:
  transcript only -> complete
  actual pronunciation evidence -> complete

Writing Review:
  short A2 sample -> complete
  longer B2 sample -> complete
  valid British/American alternative -> complete

Error Remediation:
  no pattern -> complete
  evidenced recurrent pattern -> complete

Vocabulary & Spaced Review:
  review proposal -> complete
  calendar_modified=True -> fail

Certification Preparation:
  current official -> complete
  stale/unknown official -> complete with needs_verification=True
  registration/payment/submission=True -> fail

Progress Review:
  insufficient evidence -> complete
  short-term improvement -> complete
  valid stable progression -> complete
```

Also prove invariant violations fail.

## Static gate audit strengthening

Keep current direct-producer field existence test, and add:
- forbidden business-outcome field list may not appear in `wait_condition`:

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

This prevents regression back to outcome gating.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_languages_domain_operations.py \
  tests/domains/test_languages_domain_workflows.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages/operations.py \
  cmm/domains/languages/workflows.py \
  tests/domains/test_languages_domain_operations.py \
  tests/domains/test_languages_domain_workflows.py

git diff --check
```

Commit:

```text
fix(domains): validate languages workflow invariants
```

---

# Task 3 — Prove real permission lifecycle, real cross-domain composition, and presentation parity

**Files:**
- Modify: `tests/domains/test_languages_domain_permissions.py`
- Modify: `tests/domains/test_languages_domain_memory.py`
- Modify: `tests/domains/test_languages_domain_cross_domain.py`
- Modify: `tests/domains/test_languages_domain_presentation.py`
- Production: only if a new RED exposes a real defect in Languages files.

## 3A — Real MEMORY_WRITE lifecycle

Use existing shared classes:

```python
from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.permission_gate import (
    DomainPermissionGate,
    PermissionGateOutcome,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
```

Use the existing `tests/domains/test_domain_permission_gate.py` and University positive lifecycle tests as authoritative patterns.

Create a **test-only** DomainOperationDefinition for `domain:languages` whose:
- operation type is a harmless test definition;
- `required_permissions` includes `PermissionCapability.MEMORY_WRITE`;
- operation ID is not registered as canonical production operation and is never added to catalog.

This definition exists only to drive the real `DomainPermissionGate.evaluate_operation_definition()` path for the Languages policy.

Required lifecycle:

### No approval

```text
DomainPermissionResolver(build_languages_permission_policy)
→ DomainPermissionGate.evaluate_operation_definition(...)
→ APPROVAL_REQUIRED
```

### Valid scoped approval

1. take the emitted `PermissionApprovalRequirement`;
2. bridge via `to_approval_requirement(...)`;
3. create request in `ApprovalService`;
4. approve it;
5. pass exact request ID back to gate;
6. assert `APPROVAL_CONSUMED` and `allowed=True`.

### Reuse

Call same gate with same one-shot approval again:

```text
not allowed
approval already consumed
```

### Expired

Create approval with expiry before fixed test clock:

```text
not allowed
```

### Out-of-scope / wrong actor / wrong session

Must fail and must not consume an otherwise valid approval.

### Policy reevaluation

Use the existing shared pattern proving:
- current policy is reevaluated before consumption;
- a new DENY does not consume approval.

## 3B — Proposal itself does not consume write permission

Construct:

```text
build_languages_memory_proposal
build_languages_memory_binding
validate_languages_memory_binding
```

before the permission grant.

Assert:
- proposal is created;
- `requires_confirmation=True`;
- repository approval is still unconsumed;
- no persistent mutation is applied.

Only the later shared apply authorization gate consumes the one-shot approval.

Do not invent a Languages memory store just to test this.

## 3C — Supporting domain cannot widen permission

Compose a primary + supporting policy with existing composition helpers.

Prove a supporting domain cannot turn denied/approval-gated Languages memory write into autonomous ALLOW.

## 3D — Real resolver/composer cross-domain ownership

Use:

```python
DefaultDomainResolver
DefaultDomainComposer
DomainResolutionContext
DomainResolutionSignal
```

with real registered domain definitions.

Tests may import public sibling-domain builders/register functions.

Required real cases:

```text
Direct language practice
→ Languages primary

Opposition language requirement
→ Oppositions primary + Languages supporting

Direct C1 oral practice
→ Languages primary

University language task
→ University primary + Languages supporting

B1 explanation of general subject
→ Languages primary + General supporting

Language worry
→ Concerns primary + Languages supporting

Language identity reflection
→ Reflection primary + Languages supporting
```

Do not assert only hand-written strings. Assert actual `DomainResolutionResult`.

For at least Oppositions + Languages, pass the actual resolution to `DefaultDomainComposer.compose()` and assert the real `DomainComposition`.

If default production scoring cannot express one expected relationship, STOP and report the exact missing extension point. Do not alter shared scorer policy in a test merely to force the answer.

## 3E — Typed minimal cross-domain projection

Use the shared typed cross-domain/domain-result contract already present in the repository.

Projection to Oppositions may include only:

```text
certification_status
estimated_readiness
relevant_proficiency
progress_toward_shared_goal
recommended_workload
blocking_language_gap
```

Assert absent:

```text
complete_vocabulary_history
all_observed_errors
all_transcripts
all_writing_corrections
full_languages_memory
```

No raw local dict counts as the only proof if a typed shared result contract exists.

## 3F — Actual-operation presentation parity

Build a representative actual output for **all 15 operation helpers** and pass each to:

```python
present_languages_result()
```

For every result:
- JSON-safe;
- no exception;
- no epistemic upgrade.

Add semantic assertions at minimum for:
- assess sample: OBSERVED stays OBSERVED;
- update level: certificate preservation/invariant fields visible where presentation exposes them;
- writing: valid alternatives remain valid;
- speaking: transcript-only does not become pronunciation assessment;
- errors: candidate/evidenced patterns not invented;
- review schedule: no calendar mutation preserved;
- certification: `needs_verification=True` remains visible;
- progress: stable vs short-term/insufficient state preserved;
- tracking/memory: proposal/candidate state never rendered as persisted.

If presentation currently drops one of these decision-relevant semantics, write RED then fix `presentation.py` minimally.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_languages_domain_permissions.py \
  tests/domains/test_languages_domain_memory.py \
  tests/domains/test_languages_domain_cross_domain.py \
  tests/domains/test_languages_domain_presentation.py

.venv/bin/ruff check --target-version py310 \
  tests/domains/test_languages_domain_permissions.py \
  tests/domains/test_languages_domain_memory.py \
  tests/domains/test_languages_domain_cross_domain.py \
  tests/domains/test_languages_domain_presentation.py \
  cmm/domains/languages/presentation.py \
  cmm/domains/languages/permissions.py \
  cmm/domains/languages/memory.py

git diff --check
```

Commit:

```text
test(domains): prove languages runtime boundaries
```

If a real production defect was exposed and fixed, use:

```text
fix(domains): complete languages runtime boundaries
```

instead, and include both production + tests in that commit.

---

# Task 4 — Rebuild `AT-DP-026` as one genuinely connected 45-checkpoint scenario

**Files:**
- Rewrite substantially: `tests/domains/test_languages_domain_dp026_acceptance.py`
- Modify: `tests/domains/test_languages_domain_trace.py` if a trace regression belongs there.
- Production: only if connected execution reveals a genuine defect.

This is the closure-critical task for B-001.

## Mandatory design

Use one scenario state object, e.g.:

```python
@dataclass
class ConnectedLanguagesScenario:
    ids: DeterministicIds
    state: dict[str, Any]
    checkpoints: list[str]
```

The state must retain actual objects/results produced by earlier steps.

No method may reconstruct the same semantic object independently when an earlier producer result exists.

## Actual shared machinery required

Use real:

```text
build_standard_languages_domain_bootstrap
DefaultDomainResolver
DefaultDomainComposer
DomainWorkflowExecutor
DomainPermissionResolver
DomainPermissionGate
ApprovalService
InMemoryApprovalRepository
Languages memory proposal/binding validation
shared typed cross-domain result
present_languages_result
assemble_languages_trace
validate_languages_trace
```

At minimum execute the real shared engine for all nine canonical Languages workflows. This is deliberately stronger than the first implementation to eliminate the entire workflow-connectivity risk class.

## Operation adapter state propagation

The `DomainWorkflowExecutor` operation adapter receives `(node, run)`.

It MUST use:

```python
run.inputs
run.outputs
```

to consume direct upstream results.

Examples:

### Proficiency Assessment

```text
assess node
→ actual assess_sample_result
→ run.outputs["assess"]

level_update node
→ reads run.outputs["assess"]
→ update_level_evidence_result
```

### Adaptive Lesson

```text
lesson
→ exercises reads lesson objective/skill where applicable
→ review reads generated exercise + scenario exercise result
```

### Conversation & Roleplay

```text
conversation_turn
→ roleplay_turn sees conversation state
→ speaking_review consumes transcript/pronunciation evidence from scenario
→ error_review consumes actual observed errors
```

### Error Remediation

```text
error_review
→ exercises target actual recurrent pattern/focus
→ review consumes actual exercise result
```

Do not return hard-coded unrelated output for downstream nodes.

## 45 canonical checkpoints

The single scenario must append and assert these checkpoints in order:

1. Standard bootstrap exists and General remains fallback.
2. Real resolution context for direct English-learning request is built.
3. Resolver selects `domain:languages` primary.
4. `LanguageLearningProfile` resolves.
5. English language state is created without affecting any other language.
6. Preferred variety is American English.
7. British English is represented as a valid alternative, not error.
8. Fluency goal is active.
9. C1 certification goal is concurrently active.
10. Tracking choice is explicit opt-in.
11. Onboarding workflow executes through `DomainWorkflowExecutor`.
12. Onboarding persists nothing directly.
13. Existing official B1 certificate is represented as `CERTIFIED`.
14. Initial writing sample is assessed through Proficiency Assessment workflow.
15. Writing result is `OBSERVED_PERFORMANCE`.
16. Certified record is not overwritten.
17. Speaking remains missing/insufficient because no speaking evidence exists yet.
18. Level update is proposal/evidence state only.
19. Learning plan preserves both active goals.
20. Adaptive Language Lesson workflow executes.
21. Generated exercise result is reviewed.
22. First isolated error remains `observed_error`, not pattern.
23. Stable proficiency is unchanged by that one exercise/session.
24. Conversation & Roleplay Practice workflow executes.
25. Transcript-only speaking review does not assess pronunciation.
26. A later independent comparable occurrence is produced from a distinct provenance/context.
27. `ErrorPatternEvidenceRule` evaluates the candidate recurrence.
28. Pattern becomes candidate/evidenced only because independence + comparability are satisfied.
29. Correction priority places comprehension/recurrent/goal relevance ahead of minor style.
30. Writing Review workflow executes on real writing sample.
31. Valid British/American variety remains valid after writing presentation/review.
32. `languages.progress_checkpoint` workflow executes.
33. One isolated better score is classified short-term only.
34. Comparable longitudinal evidence with real baseline may support stable improvement.
35. Non-comparable evidence cannot support stable improvement.
36. Certification Preparation workflow executes against stale guide + current official source.
37. Current official source wins temporal authority.
38. Certification readiness remains distinct from proficiency.
39. `needs_verification=True` is preserved for stale/unknown decision-critical source and does not fail workflow.
40. Vocabulary & Spaced Review workflow produces pedagogical review proposal with no calendar mutation.
41. Languages memory proposal is built and validated; still no persistence.
42. Real permission lifecycle returns APPROVAL_REQUIRED before consent grant and APPROVAL_CONSUMED only after exact scoped approval.
43. Real Oppositions + Languages resolution/composition yields Oppositions primary + Languages supporting and only minimal typed projection is shared.
44. Actual operation/workflow/projection results pass through presentation without epistemic upgrade.
45. Trace is assembled/validated using actual resolver result ID, composition ID, workflow run/result IDs, permission/approval references, memory proposal ID, domain-result ID and presentation/result references from this scenario.

Exact wording may vary in code, but all 45 semantic checkpoints must be explicit and individually assertable.

## Real IDs

Forbidden:

```text
"res-at-1"
"comp-at-1"
"rule:<semantic-string>"
"action:proposal-only"
```

unless those exact IDs are emitted by an injected deterministic ID factory at the shared component that owns them.

Allowed:

```text
resolution.id
composition.id
workflow_run.common_run.run_id
actual operation helper output["assessment_id"]
actual operation helper output["review_id"]
actual ApprovalRequest.id
actual memory proposal.proposal_id
actual typed domain_result.result_id
```

For deterministic factories, capture the factory's returned value from the actual object and use that object value later. Do not merely know what the factory would return and type it manually.

## Trace connectivity

Build the trace only after all state exists.

Every trace reference must point to an object/result in `scenario.state`.

Create a final assertion:

```python
for required_id in scenario.required_trace_ids:
    assert required_id in scenario.actual_produced_ids
```

Then validate with the shared `DomainTraceReferenceInventory`.

## Acceptance anti-cheat regressions

Add tests/properties that fail if:

1. workflow adapter ignores `run.outputs`;
2. a downstream operation uses a newly constructed substitute instead of producer output;
3. synthetic trace ID is not present in `actual_produced_ids`;
4. no PermissionGate/ApprovalService path is executed;
5. no actual cross-domain composition is executed;
6. any of the 9 workflows is skipped;
7. checkpoint count is not exactly 45;
8. checkpoint names are duplicated;
9. candidate acceptance directly calls a semantic helper for a stage that should have been produced by the executed workflow, unless the helper is itself invoked by the operation adapter for that workflow.

Direct helper calls remain acceptable for rule-only semantics not owned by an operation/workflow (e.g. inspecting a rule outcome), but their inputs must come from scenario state.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_languages_domain_dp026_acceptance.py \
  tests/domains/test_languages_domain_trace.py \
  tests/domains/test_languages_domain_cross_domain.py \
  tests/domains/test_languages_domain_permissions.py \
  tests/domains/test_languages_domain_memory.py \
  tests/domains/test_languages_domain_workflows.py

.venv/bin/ruff check --target-version py310 \
  tests/domains/test_languages_domain_dp026_acceptance.py \
  tests/domains/test_languages_domain_trace.py

git diff --check
```

Commit:

```text
fix(domains): rebuild connected DP-026 acceptance
```

---

# Task 5 — Exhaustive adversarial closure matrix

**Files:**
- Modify: `tests/domains/test_languages_domain_adversarial.py`
- Modify focused semantic tests if duplication would obscure ownership.
- Production only through RED defects.

The first audit proved that named coverage is not enough. Every adversarial test must assert the actual forbidden transition.

Required matrix, minimum:

## Proficiency / evidence

1. generic evidence ID -> cannot certify;
2. user sample -> cannot certify;
3. official credential without official provenance -> cannot certify;
4. official grounded credential -> can certify;
5. same provenance different IDs -> one evidence unit;
6. non-comparable writing samples -> no stable level;
7. grammar evidence -> no interaction level;
8. writing evidence -> no speaking level.

## Error patterns

9. one error -> no pattern;
10. same copied sentence same provenance different IDs -> no independent recurrence;
11. different provenance but `comparable=False` -> no pattern;
12. two independent comparable recurrences -> candidate/evidenced.

## Progression

13. no baseline -> no stable improvement;
14. one better score -> short-term only;
15. two high non-comparable scores -> no stable progression;
16. comparable baseline + repeated comparable improvement -> stable improvement allowed;
17. one bad session -> no stable regression.

## Certification temporality

18. stale official first + current official second -> current wins;
19. stale official only decision-critical -> verification required;
20. unknown official temporal status -> verification required;
21. equal current official sources with conflicting material facts -> unresolved + verification;
22. readiness never becomes general proficiency.

## Workflow semantics

23. wrong exercise completes adaptive workflow safely;
24. A2 writing completes review;
25. real pattern completes error-remediation workflow;
26. actual pronunciation evidence completes conversation workflow;
27. `needs_verification=True` completes certification workflow;
28. valid stable progression completes progress workflow;
29. calendar mutation attempt fails;
30. certification registration/payment/submission attempt fails.

## Permission / memory

31. raw `"true"` cannot authorize;
32. raw `1` cannot authorize;
33. no approval -> no write authorization;
34. exact one-shot approval -> one successful consumption;
35. second reuse -> denied;
36. expired approval -> denied;
37. wrong actor/session/scope -> denied;
38. proposal construction -> no approval consumption;
39. supporting domain -> cannot widen.

## Cross-domain

40. Oppositions receives minimal projection only;
41. worry in Concerns request -> not proficiency evidence;
42. Reflection identity narrative -> not deficit;
43. University requirement -> not language-level evidence.

## Structural

44. operation output schema parity all 15;
45. workflow invariant-gate fields direct-producer parity;
46. forbidden business-outcome fields absent from wait conditions;
47. input order invariance for evidence sets;
48. caller input non-mutation;
49. NaN/Inf cannot create certainty/progression;
50. strict JSON all public semantic outputs.

Run each new test RED before the production fix responsible for it.

Commit any final production correction under a narrow `fix(domains): ...` message, then commit test-only closure under:

```text
test(domains): close languages audit adversarial gaps
```

---

# Task 6 — Fresh final verification after remediation

No production changes unless a fresh regression is first RED.

## A. Focused Languages

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_languages_domain_*.py
```

## B. Real workflow semantic matrix

Explicitly run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_languages_domain_workflows.py \
  tests/domains/test_languages_domain_dp026_acceptance.py \
  tests/domains/test_languages_domain_adversarial.py
```

## C. Shared permission regressions

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_domain_permission_gate.py \
  tests/domains/test_languages_domain_permissions.py \
  tests/domains/test_languages_domain_memory.py
```

## D. Relevant sibling/composition regressions

Discover actual files; do not use a shell glob that silently matches nothing.

Include:
- Concerns;
- Reflection;
- University;
- Oppositions;
- cross-domain;
- composition;
- resolver;
- workflow execution;
- permission/memory.

## E. Entire Domain suite

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains
```

## F. Global suite

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q
```

## G. Ruff

```bash
.venv/bin/ruff check \
  cmm/domains/languages \
  tests/domains/test_languages_domain_*.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages \
  tests/domains/test_languages_domain_*.py
```

## H. Compileall without dirtying repo

```bash
TMP_VERIFY="$(mktemp -d)"
PYTHONPYCACHEPREFIX="$TMP_VERIFY/pycache" \
  .venv/bin/python -m compileall -q cmm/domains/languages
rm -rf "$TMP_VERIFY"
```

## I. Fresh import

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import cmm.domains.languages
from cmm.domains.registry import DomainRegistry

assert DomainRegistry().get("domain:languages") is None
print("LANGUAGES_FRESH_IMPORT=PASS")
PY
```

## J. Canon/package boundary

Reassert exact:
- 16 entities;
- 15 resources;
- 14 rules;
- 15 operations;
- 9 workflows;
- 14 production modules;
- `languages.progress_checkpoint`.

## K. Semantic direct probes

Run direct probes that reproduce the original audit:

```text
generic ID -> is_certified=False
same provenance/different IDs -> no stable update
same error/provenance/different IDs -> no pattern
non-comparable progression -> no stable progression
no baseline -> no stable progression
stale official vs current official -> current selected
stale official only -> needs_verification=True
wrong exercise -> adaptive workflow COMPLETED
A2 writing -> writing workflow COMPLETED
needs_verification=True -> certification workflow COMPLETED
stable_progression=True with valid evidence -> progress workflow COMPLETED
```

Print each as an explicit PASS marker.

## L. Connected acceptance proof markers

The final verification must print:

```text
AT_DP_026_CHECKPOINTS=45
AT_DP_026_REAL_RESOLVER=PASS
AT_DP_026_REAL_COMPOSER=PASS
AT_DP_026_REAL_WORKFLOWS=9
AT_DP_026_PERMISSION_LIFECYCLE=PASS
AT_DP_026_MEMORY_PROPOSAL=PASS
AT_DP_026_MINIMAL_PROJECTION=PASS
AT_DP_026_ACTUAL_TRACE_IDS=PASS
AT_DP_026_CONNECTED=PASS
```

## M. Git hygiene

```bash
git diff --check
git status --short --branch
```

Expected tracked tree clean; `?? tmp/` only.

---

# Task 7 — Documentation status after remediation

Only after all Task 6 gates pass.

**Files:**
- Modify: `docs/reference/languages-domain.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Modify: `ROADMAP.md`

Do not change the frozen catalog text except where a new helper/invariant field needs technical reference documentation.

Record:

```text
First independent audit: FAIL
Findings remediated: 2 BLOCKER + 5 MAJOR
Candidate AT-DP-026: PASS after connected rebuild
Independent re-audit: PENDING
```

Matrix:

```text
DP-026 = REQUIRES_PHASE_INSPECTION
AT-DP-026 = PASS (remediated connected candidate acceptance; independent re-audit pending)
```

Roadmap next milestone:

```text
Independently re-audit Phase 10.26 — Languages Domain
```

Do not say:
- independently audited;
- complete;
- closed.

Verify Paternidad unchanged and zero real legacy Nil architecture.

Commit:

```text
docs(domains): record phase 10.26 audit remediation
```

---

# Task 8 — Prepare re-audit bundle

After remediation commits and documentation status commit:

Create a new read-only audit bundle named:

```text
phase-10-26-independent-reaudit-bundle.tar.gz
```

It must contain:
- frozen spec;
- original implementation plan;
- first independent audit report;
- this remediation plan;
- current technical reference/matrix/roadmaps;
- all 14 Languages production modules;
- all Languages tests;
- relevant shared contracts;
- fresh final-verification evidence;
- Git commit list/diff from `93c2679..<REMEDIATED_HEAD>`;
- repository-state manifest;
- SHA256.

Do not call the phase closed.

---

# Definition of Done for Remediation

All must be true before re-audit:

```text
[ ] B-001: AT-DP-026 is one connected state-linked scenario
[ ] B-001: exactly 45 explicit canonical checkpoints
[ ] B-001: real resolver used
[ ] B-001: real composer used
[ ] B-001: all 9 canonical Languages workflows executed through DomainWorkflowExecutor
[ ] B-001: downstream operation adapter consumes run.outputs
[ ] B-001: real PermissionGate / ApprovalService path used
[ ] B-001: real memory proposal/binding path used
[ ] B-001: real typed minimal cross-domain projection used
[ ] B-001: trace IDs come from actual produced objects/results
[ ] B-002: no workflow validate gate encodes a business/pedagogical outcome
[ ] B-002: legitimate wrong answer completes adaptive lesson
[ ] B-002: legitimate A2 writing completes writing review
[ ] B-002: legitimate evidenced error pattern completes remediation workflow
[ ] B-002: pronunciation evidence present/absent both safe
[ ] B-002: needs_verification=True completes certification workflow
[ ] B-002: stable_progression=True can complete when evidence-valid
[ ] M-001: generic evidence cannot certify
[ ] M-001: only grounded recognized official credential can certify
[ ] M-002: caller ID does not create evidence independence
[ ] M-002: same provenance different IDs do not create stable level
[ ] M-002: same provenance different IDs do not create error pattern
[ ] M-002: update_level_evidence delegates to canonical rule semantics
[ ] M-003: no baseline cannot create stable progression
[ ] M-003: non-comparable evidence cannot create stable progression
[ ] M-003: comparable longitudinal evidence can create stable progression
[ ] M-004: current official outranks stale official
[ ] M-004: stale/unknown decision-critical info requires verification
[ ] M-004: equal current conflicting official sources remain unresolved
[ ] M-005: real no-approval path proven
[ ] M-005: real approval consume path proven
[ ] M-005: one-shot reuse denied
[ ] M-005: expired/out-of-scope/wrong actor/session denied
[ ] M-005: proposal itself does not consume approval
[ ] M-005: supporting domain cannot widen permission
[ ] cross-domain resolver/composer ownership matrix proven
[ ] purpose-minimized typed projection proven
[ ] actual outputs of all 15 operations pass presentation parity tests
[ ] all 15 helper outputs satisfy operation output schemas
[ ] all workflow invariant fields are produced by direct dependencies
[ ] forbidden business-outcome gate-field scan PASS
[ ] adversarial closure matrix PASS
[ ] Languages focused suite PASS
[ ] shared permission regressions PASS
[ ] relevant sibling/composition regressions PASS
[ ] all tests/domains PASS
[ ] global pytest PASS
[ ] Ruff PASS
[ ] Ruff py310 PASS
[ ] compileall PASS
[ ] fresh import PASS
[ ] package boundary PASS
[ ] exact 16/15/14/15/9 canon PASS
[ ] tracked worktree clean
[ ] Paternidad unchanged
[ ] no push
[ ] no merge
[ ] docs state re-audit pending
```

---

# Expected Remediation Commit Sequence

Prefer this sequence; add a narrow follow-up `fix(domains): ...` only for a newly reproduced defect.

```text
fix(domains): harden languages evidence semantics
fix(domains): validate languages workflow invariants
test(domains): prove languages runtime boundaries
fix(domains): rebuild connected DP-026 acceptance
test(domains): close languages audit adversarial gaps
docs(domains): record phase 10.26 audit remediation
```

If Task 3 uncovers a real presentation/permission/memory production defect, use a `fix(domains): complete languages runtime boundaries` commit instead of misleading test-only commit.

---

# Final Agent Report Required

Return exact fresh evidence:

1. starting remediation HEAD;
2. commits created;
3. files modified;
4. disposition of each audit finding B-001/B-002/M-001..M-005;
5. canon counts;
6. package module count;
7. targeted semantic test results;
8. real workflow semantic matrix result;
9. real permission lifecycle result;
10. cross-domain resolver/composer matrix result;
11. presentation actual-output parity result;
12. `AT-DP-026` checkpoint count;
13. number of real workflows executed in connected acceptance;
14. actual resolver/composer IDs;
15. permission approval request/consumption evidence IDs;
16. memory proposal/binding IDs;
17. typed cross-domain result ID;
18. trace validation status and actual-reference audit;
19. Languages focused suite;
20. shared permission suite;
21. relevant sibling/composition regressions;
22. full Domain suite;
23. global suite;
24. Ruff normal;
25. Ruff py310;
26. compileall;
27. fresh import;
28. package boundary;
29. Git diff hygiene;
30. final Git status;
31. docs status;
32. no push/no merge.

End only with:

```text
PHASE10_26_AUDIT_REMEDIATION_STATUS:
READY_FOR_INDEPENDENT_REAUDIT
```

if every remediation-side gate is fresh and green.

Do not claim Phase 10.26 closed or independently audited.
