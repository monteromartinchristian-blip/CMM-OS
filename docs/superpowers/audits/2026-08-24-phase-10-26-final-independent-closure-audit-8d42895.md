# Phase 10.26 — Final Independent Closure Audit (candidate 8d42895)

## Audit identity

- Project: CMM OS
- Phase: 10.26 — Languages Domain
- Candidate HEAD: `8d42895d1d5bd1dfbd5e08973fe0cb60033fcbd4`
- Bundle SHA-256: `e5bc46d4a720e7c46f6ec40fd236a5f65797cc04138259ba7521ab2ca61e0b23`
- External sidecar: PASS
- Internal `SHA256SUMS`: 670/670 PASS
- Archive entries: 707
- Repository modified by independent audit: NO
- Push: NO
- Merge: NO

## Verdict

```text
PHASE10_26_FINAL_INDEPENDENT_CLOSURE_AUDIT=FAIL
BLOCKERS=1
MAJORS=2
MINORS=0
CLOSURE=NO
DP_026=REQUIRES_PHASE_INSPECTION
```

The final invariant consolidation genuinely fixes the previously reported cross-framework level-update leak, incomplete mapping-record applicability, four occurrence-alias certification-authority cases, bool deadline semantics, and generic GoalAlignment shortcut.

Closure is still denied because the approved “single invariant across every proficiency path” is not actually applied to the `CERTIFIED` path, and source-role provenance remains conflated with generic occurrence provenance.

## 1. Integrity and verification evidence

Verified independently:

```text
BUNDLE_EXTERNAL_SHA256=PASS
BUNDLE_INTERNAL_SHA256SUMS=670/670_PASS
CANDIDATE_HEAD=8d42895
CANON=16/15/14/15/9
MODULES=14
PARENTHOOD_UNCHANGED=PASS
```

Hashed logs in the bundle show:

```text
rule/meta suite      204 passed
Languages            406 passed
AT-DP-026             11 passed
shared regressions   572 passed
all domains         6072 passed
global             11602 passed
Ruff                   PASS
compileall              PASS
fresh import            PASS
```

The human-facing summary reported different rule/shared counts (220 and 2639); the hashed logs above are authoritative.

## 2. Previous findings now genuinely resolved

```text
cross-framework evaluate_level_update leak          PASS
stable level update preserves framework             PASS
minimal mapping record rejected                     PASS
textual source_range rejected                       PASS
session/sample/assessment/context cert authority    PASS
days_remaining=True no longer urgent                PASS
generic type=practice no longer universal           PASS
```

## FINAL-B-001 — BLOCKER
### `CERTIFIED` proficiency bypasses the common claim/evidence binding invariant

The final design requires one claim-binding implementation across every path that can establish or update proficiency, binding:

```text
framework
skill scope
claimed/observed value
provenance
```

`_proficiency_evidence_supports_claim()` exists, but `classify_proficiency_record()` only uses it in the non-certified branch.

The `CERTIFIED` branch uses `_is_certifying_evidence()` instead. That helper checks only:

```text
source_kind
credential reference
certification provenance
```

It does not bind the certificate framework, result, scope, or date to the claim being certified.

### Independent reproduction A

Exact bundled `rules.py` executed independently:

```python
classify_proficiency_record(
    kind="CERTIFIED",
    framework="CEFR",
    level_or_score="C2",
    skill_scope="writing",
    evidence=({
        "source_kind": "official_certificate",
        "official_source_id": "official-1",
        "certificate_id": "cert-1",
        "framework": "ACTFL",
        "skill": "speaking",
        "observed": "B1",
        "result": "B1",
        "valid_at": "2026-01-01",
    },),
)
```

Actual:

```text
kind=CERTIFIED
framework=CEFR
level_or_score=C2
skill_scope=writing
is_certified=True
certification_evidence_valid=True
confidence=0.95
```

Therefore:

```text
ACTFL B1 speaking certificate
-> CERTIFIED CEFR C2 writing
```

without framework mapping and without result/scope matching.

### Independent reproduction B

A sparse credential record also certifies the caller-supplied result:

```python
evidence=({
    "source_kind": "official_certificate",
    "source_id": "official-2",
    "certificate_id": "cert-2",
},)
```

with requested `CEFR C2 writing` returns:

```text
CERTIFIED CEFR C2
confidence=0.95
```

despite evidence containing no framework, result, date, or scope.

This violates the frozen design requirement that certified proficiency preserve:

```text
certification
framework
date
result
source
temporal status where relevant
```

### Independent reproduction C — implicit CEFR fallback

```python
classify_proficiency_record(
    kind="ESTIMATED",
    framework=None,
    level_or_score="C1",
    skill_scope="writing",
    evidence=(
        {"provenance_id":"p1","framework":"ACTFL","skill":"writing","observed":"C1"},
        {"provenance_id":"p2","framework":"ACTFL","skill":"writing","observed":"C1"},
    ),
)
```

Actual:

```text
kind=ESTIMATED
framework=CEFR
level_or_score=C1
confidence=0.75
```

Omitting `framework` disables framework matching and later defaults the output to CEFR.

Frozen invariant:

```text
The framework must be explicit whenever a level or score depends on it.
```

### Connected AT-DP-026 impact

Checkpoint 07/08 currently builds a sparse certificate:

```python
{
    "source_kind":"official_certificate",
    "source_id":"official-certificate-record",
    "certificate_id":"certificate-B1",
}
```

and classifies it as `CERTIFIED CEFR B1 writing`.

Thus the connected happy path itself relies on the certification shortcut.

Disposition:

```text
AT_DP_026_STRUCTURE=PASS
AT_DP_026_TRACE=PASS
AT_DP_026_CERTIFIED_PROFICIENCY_BINDING=FAIL
AT_DP_026_CLOSURE_GATE=FAIL
```

## FINAL-M-001 — MAJOR
### Source-role provenance is still conflated with occurrence provenance

#### Framework mapping

Current `_framework_mapping_provenance()` calls `_canonical_provenance()`.

`_canonical_provenance()` is explicitly occurrence provenance and accepts:

```text
provenance_id
source_id
assessment_id
sample_id
context_id
session_id
```

A framework concordance requires source provenance, not a user/sample/session occurrence.

Independent probes show each of these can calibrate IELTS 6.5 -> CEFR B2 when the other mapping fields are present:

```text
assessment_id only -> calibrated=True
sample_id only     -> calibrated=True
context_id only    -> calibrated=True
session_id only    -> calibrated=True
```

The test suite explicitly preserves the contradictory contract:

```python
test_framework_mapping_accepts_each_canonical_provenance_alias
```

and expects `assessment_id`, `sample_id`, and `context_id` to calibrate.

Therefore the bundle’s:

```text
LEGACY_CONTRACT_CONTRADICTIONS=0
```

is false.

#### Certification source authority

`_has_certification_source_authority_identity()` still accepts generic `provenance_id`.

But `provenance_id` is used throughout Languages as generic occurrence provenance for samples, errors, observations, and progression evidence.

Independent reproduction:

```python
evaluate_certification_source(
    sources=({
        "provenance_id":"user-session-evidence",
        "source_type":"official",
        "temporal_state":"current",
    },),
    decision_critical=True,
)
```

Actual:

```text
authority_rank=6
needs_verification=False
```

Final source-authority identity should be narrow:

```text
source_id
official_source_id
```

unless a separately typed source-provenance field is introduced.

The same role discipline must apply to `_is_certifying_evidence()`.

## FINAL-M-002 — MAJOR
### The global meta-gate prints PASS without enumerating every epistemic path

`direct_final_probes.py` directly prints:

```python
print("LEGACY_CONTRACT_CONTRADICTIONS=0")
print("ALL_EPISTEMIC_PATHS_SHARE_INVARIANTS=PASS")
print("ALL_HISTORICAL_BYPASSES_BLOCKED=PASS")
```

after a limited probe matrix.

No assertion covers:

```text
CERTIFIED claim/value/framework/scope binding
sparse certificate rejection
framework=None implicit CEFR fallback
mapping occurrence-provenance aliases
certification source provenance_id
```

Likewise the “all evidence helpers” meta-test omits the certified classification path and source-authority paths.

This is a verification-design defect because cross-path consistency was the explicit final closure mechanism.

## 3. 14-rule disposition

```text
LanguageLevelEvidenceRule        FAIL
SkillSeparationRule              PASS
LanguageVarietyValidityRule      PASS
ProficiencyFrameworkRule         FAIL
ErrorPatternEvidenceRule         PASS
CorrectionPriorityRule           PASS
AdaptiveDifficultyRule           PASS
SpacedReviewRule                 PASS
LearningLoadRule                 PASS
GoalAlignmentRule                PASS
ProgressionEvidenceRule          PASS
CertificationTemporalRule        FAIL
CulturalContextEvidenceRule      PASS
LanguageMemoryConsentRule        PASS
```

## 4. Required surgical remediation

Do not redesign the domain.

### A. Bind CERTIFIED claims

A certificate must establish, not merely accompany:

```text
source identity
credential/result identity
framework
result
date/validity
scope
```

At minimum:
- requested framework == certificate framework;
- requested result == certificate result;
- requested specific skill is supported by certificate scope;
- sparse credential references cannot certify a caller-supplied level.

A global certificate should use `skill_scope=general` unless the evidence explicitly provides skill-specific certification.

### B. Remove implicit CEFR fallback

If framework is absent:
- infer only from unambiguous grounded evidence if the canonical contract deliberately permits it;
- otherwise leave the framework-dependent level unassessed.

Never relabel ACTFL evidence as CEFR merely because the caller omitted framework.

### C. Role-specific source identity

For framework concordance authority:

```text
source_id
official_source_id
```

For certification source authority:

```text
source_id
official_source_id
```

Do not accept as source authority:

```text
provenance_id
assessment_id
sample_id
context_id
session_id
```

### D. Correct AT-DP-026 certificate fixture

Use a complete grounded certificate:

```text
source_kind=official_certificate
source_id or official_source_id
certificate_id
framework=CEFR
result=B1
valid_at=<date>
```

Use `skill_scope=general` unless the evidence is explicitly writing-specific.

Keep all 45 checkpoint names unchanged.

### E. Make global markers executable

Do not print global PASS markers unless exact assertions cover:

```text
OBSERVED_PERFORMANCE
ESTIMATED
CERTIFIED
evaluate_level_update
evaluate_framework_mapping
evaluate_certification_source
```

## 5. Mandatory auditor-owned regressions

```text
ACTFL B1 speaking certificate cannot certify CEFR C2 writing
certificate without framework/result/date cannot certify claimed level
matching complete CEFR B1 certificate can certify CEFR B1 general
framework omitted + ACTFL evidence cannot become CEFR estimate

mapping provenance_id not source
mapping assessment_id not source
mapping sample_id not source
mapping context_id not source
mapping session_id not source
mapping source_id accepted when complete
mapping official_source_id accepted when complete

official/current + provenance_id only not rank 6
official/current + source_id rank 6 when valid
official/current + official_source_id rank 6 when valid

AT-DP-026 complete certificate fixture PASS
AT-DP-026 remove certificate result/framework/source/date -> certification gate FAIL
```

## Final markers

```text
BUNDLE_EXTERNAL_SHA256=PASS
BUNDLE_INTERNAL_SHA256SUMS=670/670_PASS
CANDIDATE_HEAD=8d42895

CANON=16/15/14/15/9
MODULES=14
PARENTHOOD_UNCHANGED=PASS

CERTIFIED_CLAIM_BINDING=FAIL
CERTIFIED_FRAMEWORK_BINDING=FAIL
CERTIFIED_RESULT_BINDING=FAIL
CERTIFIED_SCOPE_BINDING=FAIL
IMPLICIT_CEFR_FALLBACK=FAIL

FRAMEWORK_MAPPING_SOURCE_ROLE=FAIL
CERTIFICATION_AUTHORITY_PROVENANCE_ROLE=FAIL

LEGACY_CONTRACT_CONTRADICTIONS=FAIL
ALL_EPISTEMIC_PATHS_SHARE_INVARIANTS=FAIL
ALL_HISTORICAL_BYPASSES_BLOCKED=FAIL

AT_DP_026_CHECKPOINT_COUNT=45_PASS
AT_DP_026_REAL_WORKFLOWS=9_PASS
AT_DP_026_TRACE_RUNTIME_PROVENANCE=PASS
AT_DP_026_CERTIFIED_PROFICIENCY_BINDING=FAIL
AT_DP_026_CLOSURE_GATE=FAIL

PHASE10_26_FINAL_INDEPENDENT_CLOSURE_AUDIT=FAIL
BLOCKERS=1
MAJORS=2
MINORS=0
CLOSURE=NO
DP_026=REQUIRES_PHASE_INSPECTION
PUSH=NO
MERGE=NO
REPO_MODIFIED=NO
```
