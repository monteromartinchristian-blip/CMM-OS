# Phase 10.26 — Surgical Final Closure Re-Audit

## Audit identity

- Project: CMM OS
- Phase: 10.26 — Languages Domain
- Audit type: independent surgical final closure re-audit
- Candidate branch: `feature/phase-10-domain-intelligence`
- Candidate HEAD: `f938f2b547b95885ec0644db65478860a70f5007`
- Bundle: `phase-10-26-surgical-final-independent-closure-audit-bundle.tar.gz`
- External SHA-256: `8e45e9f71dae03d92d68edd4389e144d4fbf35852ef85a11b86558dc06ace1bc`
- Sidecar: exact match
- Internal `SHA256SUMS`: 673 / 673 PASS
- Repository modified by independent audit: NO
- Push: NO
- Merge: NO

# Verdict

```text
PHASE10_26_SURGICAL_FINAL_CLOSURE_REAUDIT=FAIL
BLOCKERS=1
MAJORS=2
MINORS=0
CLOSURE=NO
DP_026=REQUIRES_PHASE_INSPECTION
```

The surgical candidate genuinely fixes the exact findings from the previous audit:
- mismatched/sparse `CERTIFIED` claims are rejected;
- complete matching certificates are accepted;
- generic occurrence IDs no longer ground framework mapping or certification source authority;
- the connected certificate fixture is complete and has a negative mutation matrix.

Closure is nevertheless denied because the shared proficiency-binding predicate still does not preserve the frozen distinction:

```text
global proficiency != skill-specific proficiency
```

and the final framework/date metadata boundary is still permissive in alternate paths.

---

# 1. Integrity and verification evidence

Independent verification:

```text
BUNDLE_EXTERNAL_SHA256=PASS
BUNDLE_INTERNAL_SHA256SUMS=673/673_PASS
CANDIDATE_HEAD=f938f2b547b95885ec0644db65478860a70f5007
CANON=16/15/14/15/9
MODULES=14
PARENTHOOD_UNCHANGED=PASS
```

Hashed verification logs contained in the bundle:

```text
auditor-owned regressions    14 passed
rule/meta suite             214 passed
Languages                   417 passed
AT-DP-026                    12 passed
shared regressions          572 passed
all domains                6083 passed
global                    11613 passed
Ruff                          PASS
compileall                     PASS
fresh import                   PASS
```

These logs are real and internally hashed.

---

# 2. Previous final-audit findings — disposition

Exact independent probes now confirm:

```text
ACTFL B1 speaking certificate -> CEFR C2 writing     BLOCKED
sparse credential -> caller-supplied certified level BLOCKED
complete CEFR B1 general certificate                 ACCEPTED
mapping provenance_id                                REJECTED
mapping assessment_id                                REJECTED
mapping sample_id                                    REJECTED
mapping context_id                                   REJECTED
mapping session_id                                   REJECTED
mapping source_id                                    ACCEPTED when complete
mapping official_source_id                           ACCEPTED when complete
cert authority provenance_id                         REJECTED
cert authority source_id                             ACCEPTED
cert authority official_source_id                    ACCEPTED
```

The previous `1 BLOCKER + 2 MAJOR` reproductions are therefore materially remediated.

---

# FINAL-B-001 — BLOCKER
# Global proficiency is still inferred directly from skill-specific evidence

Frozen canonical design:

```text
global proficiency != skill-specific proficiency
```

and:

```text
A global proficiency estimate may exist only as a derived summary when justified.
It must never erase skill-specific evidence.
```

The consolidated predicate `_proficiency_evidence_supports_claim()` enforces a requested skill only when the requested skill is one of the canonical skill dimensions.

For:

```text
requested_skill="general"
```

it performs no scope restriction.

As a result, writing-only evidence can directly establish a global record.

## Independent reproduction A — two writing observations become a global estimate

Input:

```python
classify_proficiency_record(
    kind="ESTIMATED",
    framework="CEFR",
    level_or_score="B1",
    skill_scope="general",
    evidence=(
        {
            "provenance_id":"p1",
            "framework":"CEFR",
            "skill":"writing",
            "observed":"B1",
        },
        {
            "provenance_id":"p2",
            "framework":"CEFR",
            "skill":"writing",
            "observed":"B1",
        },
    ),
)
```

Actual:

```text
kind=ESTIMATED
framework=CEFR
level_or_score=B1
skill_scope=general
confidence=0.75
```

Therefore:

```text
writing evidence
-> global CEFR B1
```

without a derived global-summary step.

## Independent reproduction B — one writing observation becomes global observed performance

Input:

```text
OBSERVED_PERFORMANCE
skill_scope=general
one writing observation
```

Actual:

```text
OBSERVED_PERFORMANCE B1 general
confidence=0.5
```

Again, the scope is promoted from `writing` to `general`.

## Independent reproduction C — writing-only evidence updates a global stable level

Existing:

```text
ESTIMATED CEFR B1 general
```

Two independent comparable writing observations at B2 produce:

```text
stable_update_supported=True
proposed_level=B2
updated_record.skill_scope=general
```

So the same scope leak exists through `evaluate_level_update()`.

## Independent reproduction D — writing-only progression becomes global progression

Input:

```text
skill=None
previous writing score=0.50
current writing scores=0.80, 0.82
```

Actual:

```text
progression_outcome=stable_improvement
stable_progression=True
skill=general
```

Thus `evaluate_progression()` also promotes one skill into global progression.

## Independent reproduction E — unknown skill scopes fail open

This request:

```text
skill_scope="foobar"
```

can be grounded by writing/speaking evidence and returned as:

```text
ESTIMATED ... skill_scope=foobar
```

Likewise:

```text
target_skill="foobar"
```

in `evaluate_level_update()` can produce a stable update whose output scope is `foobar`.

The canonical scope set is:

```text
general
listening
speaking
reading
writing
grammar
vocabulary
pronunciation
interaction
```

Unknown scope must fail closed.

## Root cause

The shared binding predicate distinguishes:

```text
canonical specific skill
vs
everything else
```

instead of:

```text
canonical specific skill
general/global scope
invalid scope
```

The final consolidated invariant is therefore incomplete.

---

# FINAL-M-001 — MAJOR
# Framework context can still be assigned without grounded framework evidence

The surgical remediation claimed:

```text
Framework is inferred only from unambiguous grounded evidence
```

but `classify_proficiency_record()` computes:

```python
ev_frameworks = {
    evidence.framework
    for evidence in deduped_ev
}
```

before checking whether those records have valid provenance or otherwise ground the claim.

## Independent reproduction A — ungrounded record chooses the framework

Input:

```python
framework=None
level_or_score="C1"
skill_scope="writing"

evidence=(
    {"framework":"IELTS"},  # no provenance, no observation
    {"provenance_id":"p1","skill":"writing","observed":"C1"},
    {"provenance_id":"p2","skill":"writing","observed":"C1"},
)
```

Actual:

```text
kind=ESTIMATED
framework=IELTS
level_or_score=C1
confidence=0.75
```

The only record that supplied the framework was epistemically ungrounded.

The two grounded records contained no framework.

Therefore an unsupported framework tag can label otherwise framework-neutral evidence.

The same behavior occurs with an arbitrary framework string.

## Independent reproduction B — `evaluate_level_update()` still defaults missing framework to CEFR

Current source contains:

```python
existing_framework = _safe_str(existing_dict.get("framework")) or "CEFR"
```

Input:

```text
existing:
  kind=ESTIMATED
  level=B1
  skill_scope=writing
  framework missing

two frameworkless comparable writing observations:
  B2
  B2
```

Actual:

```text
stable_update_supported=True
proposed_level=B2
updated_record.framework=CEFR
```

This is an implicit CEFR fallback in an alternate path.

Frozen design:

```text
The framework must be explicit whenever a level or score depends on it.
```

The direct marker `NO_IMPLICIT_CEFR_FALLBACK=PASS` only exercises `classify_proficiency_record()`, so it does not cover this remaining fallback.

---

# FINAL-M-002 — MAJOR
# Malformed certificate date evidence can still produce CERTIFIED confidence

The file-level invariant states:

```text
Malformed evidence fails closed and never increases certainty.
```

Certified proficiency must preserve a real date.

Current `_is_certifying_evidence()` checks only whether one of:

```text
valid_at
effective_date
issue_date
date
timestamp
```

is a non-empty string.

It performs no structural validation that the value is actually a date/timestamp.

## Independent reproduction

Input:

```python
{
    "source_kind":"official_certificate",
    "source_id":"s",
    "certificate_id":"c",
    "framework":"CEFR",
    "result":"B1",
    "valid_at":"banana",
}
```

requested as:

```text
CERTIFIED CEFR B1 general
```

Actual:

```text
is_certified=True
certification_evidence_valid=True
confidence=0.95
```

A malformed temporal value therefore increases certainty to certified status.

The final acceptance fixtures all use ISO dates (`2026-01-01`), so this malformed-input branch is not covered by the current mutation matrix.

A deterministic syntax check is sufficient; no internal clock is required.

---

# 3. Meta-gate disposition

`direct_final_probes.py` is substantially improved and now backs the prior surgical markers with executable assertions.

However its global markers still do not cover:

```text
general/global scope vs skill-specific evidence
unknown skill scope
framework inference from an ungrounded framework tag
evaluate_level_update missing-framework CEFR fallback
malformed certificate date syntax
general progression from skill-specific evidence
```

Therefore:

```text
ALL_EPISTEMIC_PATHS_SHARE_INVARIANTS=PASS
ALL_HISTORICAL_BYPASSES_BLOCKED=PASS
```

cannot yet serve as a closure proof for the complete frozen behavioral invariants.

This is recorded as a verification gap supporting the product findings above, not as a separate severity count.

---

# 4. AT-DP-026 disposition

The connected scenario itself is now materially stronger:

```text
45 frozen semantic checkpoints                     PASS
9 real workflows                                   PASS
complete grounded CEFR B1 certificate              PASS
certificate negative mutation matrix               PASS
runtime trace provenance                           PASS
permission runtime IDs                             PASS
```

The current connected fixture does not exercise the failing global-scope or missing-framework paths.

Disposition:

```text
AT_DP_026_CURRENT_SCENARIO=PASS
DP_026_PHASE_CLOSURE=FAIL
```

---

# 5. Remaining 14-rule matrix

```text
LanguageLevelEvidenceRule        FAIL — global/scope + framework-context binding
SkillSeparationRule              PASS
LanguageVarietyValidityRule      PASS
ProficiencyFrameworkRule         PASS
ErrorPatternEvidenceRule         PASS
CorrectionPriorityRule           PASS
AdaptiveDifficultyRule           PASS
SpacedReviewRule                 PASS
LearningLoadRule                 PASS
GoalAlignmentRule                PASS
ProgressionEvidenceRule          FAIL — skill-specific progression can become general
CertificationTemporalRule        PASS for audited source-authority semantics
CulturalContextEvidenceRule      PASS
LanguageMemoryConsentRule        PASS
```

Certificate temporal syntax failure is inside the LanguageLevel/CERTIFIED evidence path.

---

# 6. Required final root correction

This should be one small claim-context hardening pass, not another redesign.

## A. Canonical proficiency scope validator

Introduce one private scope normalizer/predicate with exactly:

```text
general
listening
speaking
reading
writing
grammar
vocabulary
pronunciation
interaction
```

Unknown non-empty scope:

```text
-> invalid
-> fail closed
```

## B. Global scope must not consume skill-specific evidence as identity evidence

For a requested `general` claim:

```text
evidence skill=writing/speaking/etc
```

must not directly ground the general claim.

General claims may use:
- evidence explicitly scoped `general`; or
- evidence with no skill only when it semantically represents an overall/global assessment; or
- an explicit derived-summary path.

Do not silently collapse a specific skill into global proficiency.

Apply the same rule to:
- `classify_proficiency_record()`;
- `evaluate_level_update()`;
- `evaluate_progression()`.

## C. Framework inference must use grounded evidence only

When caller framework is absent, framework candidates must come only from evidence that is itself eligible to ground the proficiency claim.

An unprovenanced `{framework: ...}` record must not select the framework for other evidence.

## D. Remove all implicit CEFR defaults from stable-update paths

`evaluate_level_update()` must not use:

```text
missing framework -> CEFR
```

If the existing framework is missing:
- infer only from unambiguous grounded comparable evidence if canonical policy deliberately permits it; or
- fail the framework-dependent update closed.

## E. Validate certificate temporal syntax

Require a deterministic date/timestamp shape before certificate evidence can establish certified status.

Accept the canonical fixtures used by Phase 10.26, such as ISO-8601:

```text
YYYY-MM-DD
YYYY-MM-DDTHH:MM:SS[timezone]
```

Reject arbitrary non-date strings.

No current-time comparison is required here; temporal freshness remains the job of `CertificationTemporalRule`.

---

# 7. Mandatory final regressions

The next candidate must contain living tests for:

```text
two writing observations cannot become ESTIMATED general proficiency
one writing observation cannot become OBSERVED_PERFORMANCE general proficiency
writing-only comparable evidence cannot update general proficiency
writing-only progression with skill=None cannot become stable general progression

unknown classify skill_scope fails closed
unknown evaluate_level_update target_skill fails closed

grounded general/overall evidence may support a general claim
specific writing evidence still supports writing claim

ungrounded framework-only record cannot choose framework
grounded unambiguous framework evidence may be inferred if policy permits
mixed grounded frameworks fail closed

evaluate_level_update existing framework missing
+ frameworkless evidence
-> no CEFR fallback

certificate valid_at="banana" -> not certified
certificate valid_at="" -> not certified
certificate valid_at valid ISO date -> certified when all other fields match
```

---

# 8. Final markers

```text
BUNDLE_EXTERNAL_SHA256=PASS
BUNDLE_INTERNAL_SHA256SUMS=673/673_PASS
CANDIDATE_HEAD=f938f2b

PREVIOUS_SURGICAL_CERT_BINDING=PASS
PREVIOUS_SURGICAL_SOURCE_ROLE=PASS
PREVIOUS_SURGICAL_AT_DP_026_CERTIFICATE=PASS

GLOBAL_SCOPE_NOT_SKILL_IDENTITY=FAIL
GENERAL_LEVEL_UPDATE_SCOPE_BINDING=FAIL
GENERAL_PROGRESSION_SCOPE_BINDING=FAIL
UNKNOWN_SKILL_SCOPE_FAIL_CLOSED=FAIL

GROUNDED_FRAMEWORK_INFERENCE_ONLY=FAIL
LEVEL_UPDATE_NO_IMPLICIT_CEFR=FAIL

CERTIFICATE_TEMPORAL_SYNTAX=FAIL

AT_DP_026_CHECKPOINT_COUNT=45_PASS
AT_DP_026_REAL_WORKFLOWS=9_PASS
AT_DP_026_CURRENT_SCENARIO=PASS

CANON=16/15/14/15/9
MODULES=14
PARENTHOOD_UNCHANGED=PASS

PHASE10_26_SURGICAL_FINAL_CLOSURE_REAUDIT=FAIL
BLOCKERS=1
MAJORS=2
MINORS=0
CLOSURE=NO
DP_026=REQUIRES_PHASE_INSPECTION
PUSH=NO
MERGE=NO
REPO_MODIFIED=NO
```
