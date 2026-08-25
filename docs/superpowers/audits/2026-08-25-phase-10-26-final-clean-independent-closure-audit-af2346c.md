# Phase 10.26 — Final Clean Independent Closure Audit

## Audit identity

- Project: CMM OS
- Phase: 10.26 — Languages Domain
- Audit type: final clean independent closure audit
- Candidate branch: `feature/phase-10-domain-intelligence`
- Candidate HEAD: `af2346cdce54474233736804efe515c0ba8fb909`
- Bundle: `phase-10-26-final-clean-independent-closure-audit-bundle.tar.gz`
- External SHA-256: `3606696a19625c73fd43e4531fa72435aae9023129df74b959a2c3f302cddfe2`
- Sidecar: PASS
- Intended internal hashes: 80 / 80 PASS
- Canon: 16 / 15 / 14 / 15 / 9
- Languages production modules: 14
- Paternidad scope: unchanged
- Shared engine scope: unchanged
- Repository modified by independent audit: NO
- Push: NO
- Merge: NO

# Verdict

```text
PHASE10_26_FINAL_CLEAN_INDEPENDENT_CLOSURE_AUDIT=FAIL
BLOCKERS=1
MAJORS=2
MINORS=0
CLOSURE=NO
DP_026=REQUIRES_PHASE_INSPECTION
```

The exact failures reported against `f938f2b` are genuinely repaired:
- specific-skill evidence no longer promotes to `general`;
- unknown scopes fail closed;
- missing-framework `evaluate_level_update()` no longer defaults to CEFR;
- malformed certificate dates fail closed;
- previous certificate/source-role fixes remain intact.

However, two absence-semantics bypasses remain in the common proficiency context boundary.

---

# 1. Bundle integrity

Verified independently:

```text
BUNDLE_EXTERNAL_SHA256=PASS
BUNDLE_INTERNAL_SHA256SUMS=80/80_PASS
CANDIDATE_HEAD=af2346cdce54474233736804efe515c0ba8fb909
SEMANTIC_FILE_COUNT=5
CANON=16/15/14/15/9
MODULES=14
PARENTHOOD_UNCHANGED=PASS
SHARED_ENGINE_UNCHANGED=PASS
```

Fresh captured logs:

```text
claim-context regressions   301 passed
Languages                   444 passed
AT-DP-026                    12 passed
all domains                6110 passed
global                    11640 passed
Ruff                          PASS
compileall                     PASS
fresh import                   PASS
```

The archive also contains Apple extended metadata; it is not part of the intended SHA manifest and does not affect the semantic audit.

---

# 2. `f938f2b` findings — repaired

Independent execution against the exact bundled `rules.py` confirms:

```text
writing evidence -> ESTIMATED general                    BLOCKED
writing evidence -> OBSERVED general                     BLOCKED
writing-only stable general level update                 BLOCKED
writing-only general progression                         BLOCKED

unknown classify scope                                   BLOCKED
unknown level-update scope                               BLOCKED

ungrounded IELTS tag selecting framework                 BLOCKED
missing framework level-update -> CEFR                   BLOCKED

certificate valid_at="banana"                            BLOCKED
invalid calendar date                                    BLOCKED
valid ISO date                                           ACCEPTED

ACTFL/B1/speaking certificate -> CEFR/C2/writing         BLOCKED
sparse credential certifies caller result               BLOCKED

mapping occurrence IDs as source authority              BLOCKED
generic provenance_id as certification authority         BLOCKED
```

These prior roots are materially fixed.

---

# FINAL-B-001 — BLOCKER
# Framework-dependent proficiency still survives with no framework

The frozen canonical design states:

```text
The framework must be explicit whenever a level or score depends on it.
```

It also states that a `proficiency_record` must identify at minimum:

```text
language
kind
framework
level_or_score
skill_scope
evidence_refs
confidence
observed_at / valid_at
source
```

The final invariant design further requires the common proficiency evidence contract to bind:

```text
framework
skill scope
claimed/observed value
canonical evidence provenance
```

Current `classify_proficiency_record()` infers a framework only when grounded candidates contain exactly one non-empty framework. If no framework can be inferred, execution continues anyway.

## Independent reproduction A — frameworkless ESTIMATED standardized level

Input:

```python
classify_proficiency_record(
    kind="ESTIMATED",
    framework=None,
    level_or_score="C1",
    skill_scope="writing",
    evidence=(
        {"provenance_id":"p1","skill":"writing","observed":"C1"},
        {"provenance_id":"p2","skill":"writing","observed":"C1"},
    ),
)
```

Actual:

```text
kind=ESTIMATED
framework=None
level_or_score=C1
skill_scope=writing
confidence=0.75
```

A framework-dependent level is therefore established without framework identity.

## Independent reproduction B — frameworkless OBSERVED standardized level

Input:

```text
kind=OBSERVED_PERFORMANCE
framework=None
level_or_score=C1
one grounded writing observation C1
```

Actual:

```text
OBSERVED_PERFORMANCE
framework=None
level_or_score=C1
confidence=0.5
```

Again, the canonical minimum field `framework` is absent while the framework-dependent proficiency value survives.

## Independent reproduction C — one framework-bearing sample can lend its framework to a frameworkless independent sample

Input:

```text
framework=None

sample 1:
  provenance=p1
  framework=ACTFL
  skill=writing
  observed=C1

sample 2:
  provenance=p2
  framework missing
  skill=writing
  observed=C1
```

Actual:

```text
kind=ESTIMATED
framework=ACTFL
level_or_score=C1
confidence=0.75
```

The frameworkless sample counts toward the independent evidence threshold after the first sample selects ACTFL.

That is not an end-to-end framework-bound evidence contract.

## Root cause

`_proficiency_evidence_supports_claim()` accepts records with `ev_fw=None` even when a requested framework exists, and the classifier does not fail closed when framework inference yields no framework.

The implementation therefore distinguishes:

```text
mismatched framework -> reject
missing framework -> permissive
```

but the final canonical boundary requires a framework-dependent claim to be framework-bound.

---

# FINAL-M-001 — MAJOR
# Missing scope is still treated as explicit global evidence

The previous candidate correctly blocked:

```text
writing -> general
```

but the common predicate still treats **absence of skill/scope** as acceptable evidence for a `general` claim.

The frozen design says:

```text
A global proficiency estimate may exist only as a derived summary when justified.
```

The previous surgical remediation explicitly required that a general claim use:
- evidence explicitly scoped `general`; or
- a semantically represented overall/global assessment; or
- an explicit derived-summary path.

Current code has no semantic overall/global assessment test. For `requested_skill="general"` it simply accepts `ev_skill_raw=None`.

## Independent reproduction A — unscoped observations become global estimate

Input:

```python
framework="CEFR"
level_or_score="B1"
skill_scope="general"

evidence=(
    {"provenance_id":"p1","observed":"B1"},
    {"provenance_id":"p2","observed":"B1"},
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

No evidence record says `general`, `overall`, or equivalent.

## Independent reproduction B — one unscoped observation becomes global observed performance

Actual:

```text
OBSERVED_PERFORMANCE CEFR B1 general
confidence=0.5
```

from one generic `{provenance_id, observed}` record.

## Independent reproduction C — unscoped evidence updates general stable proficiency

Two unscoped comparable B2 observations update:

```text
existing CEFR B1 general
->
stable_update_supported=True
CEFR B2 general
```

## Independent reproduction D — unscoped evidence produces stable global progression

Unscoped previous/current numeric comparable evidence produces:

```text
progression_outcome=stable_improvement
stable_progression=True
skill=general
```

No explicit derived-summary or overall-assessment semantics are present.

## Required Phase 10.26-safe choice

For final closure, use the narrow deterministic contract:

```text
non-certificate proficiency/progression evidence for a `general` claim
must explicitly carry:
skill="general"
or
skill_scope="general"
```

Do not invent a new implicit “overall assessment” representation in this phase.

Official certificates may retain their separate global credential semantics.

---

# FINAL-M-002 — MAJOR
# The final meta-gate still overstates invariant coverage

`direct_final_probes.py` now contains many good executable assertions.

However its global markers:

```text
ALL_FRAMEWORK_CONTEXTS_REQUIRE_GROUNDING=PASS
ALL_CLAIM_SCOPES_USE_CANONICAL_BINDING=PASS
ALL_EPISTEMIC_PATHS_SHARE_INVARIANTS=PASS
ALL_HISTORICAL_BYPASSES_BLOCKED=PASS
```

do not assert the two failing absence cases.

Example:

`ALL_FRAMEWORK_CONTEXTS_REQUIRE_GROUNDING` verifies only:

```text
res["framework"] is None
```

for framework-neutral evidence.

It does not verify:

```text
level_or_score == "unassessed"
confidence == 0.0
```

So the marker passes while the result is still:

```text
ESTIMATED C1
framework=None
confidence=0.75
```

Likewise the scope matrix tests all canonical **explicit** scopes, but never tests absent scope as distinct from explicit `general`.

The global closure markers therefore remain stronger than the executable evidence beneath them.

---

# 3. AT-DP-026 disposition

Current connected scenario:

```text
45 frozen semantic checkpoints     PASS
9 real workflows                   PASS
complete certificate binding       PASS
certificate negative mutations     PASS
trace/runtime provenance           PASS
```

The remaining bypasses are not exercised by the connected happy path.

Disposition:

```text
AT_DP_026_CURRENT_SCENARIO=PASS
DP_026_PHASE_CLOSURE=FAIL
```

---

# 4. Remaining rule matrix

```text
LanguageLevelEvidenceRule        FAIL — missing framework/scope still gains proficiency certainty
SkillSeparationRule              PASS for explicit specific-skill separation
LanguageVarietyValidityRule      PASS
ProficiencyFrameworkRule         PASS for cross-framework mapping semantics
ErrorPatternEvidenceRule         PASS
CorrectionPriorityRule           PASS
AdaptiveDifficultyRule           PASS
SpacedReviewRule                 PASS
LearningLoadRule                 PASS
GoalAlignmentRule                PASS
ProgressionEvidenceRule          FAIL — unscoped evidence can become general progression
CertificationTemporalRule        PASS
CulturalContextEvidenceRule      PASS
LanguageMemoryConsentRule        PASS
```

---

# 5. Required final absence-semantics correction

This is not a redesign.

It is one strict principle:

```text
missing context != explicit context
```

## A. Framework-dependent claim

After permitted grounded framework inference:

```text
if level_or_score is present
and framework is still absent
-> fail closed
```

For Phase 10.26, a proficiency record with a standardized level/score must not survive with `framework=None`.

When framework was inferred from evidence rather than supplied by the caller, only evidence explicitly carrying the inferred framework may count toward the independent evidence threshold.

This blocks:

```text
1 ACTFL sample + 1 frameworkless sample -> ESTIMATED ACTFL
```

## B. General scope

For non-certificate observed/estimated/update/progression evidence:

```text
requested general
requires evidence scope explicitly general
```

Accept:

```text
skill="general"
skill_scope="general"
```

Reject generic evidence where both are absent.

Do not infer “global” from missing scope.

## C. Meta-gate

Add exact executable assertions for:
- frameworkless standardized estimate;
- frameworkless standardized observed performance;
- one framework-bound + one frameworkless independent sample;
- absent-scope general estimate;
- absent-scope general observed result;
- absent-scope general update;
- absent-scope general progression.

Only then print the global PASS markers.

---

# 6. Mandatory final regressions

```text
FRAMEWORKLESS_ESTIMATE_FAILS_CLOSED=PASS
FRAMEWORKLESS_OBSERVED_FAILS_CLOSED=PASS
INFERRED_FRAMEWORK_REQUIRES_EACH_COUNTED_SAMPLE_BOUND=PASS

ABSENT_SCOPE_GENERAL_ESTIMATE_REJECTED=PASS
ABSENT_SCOPE_GENERAL_OBSERVED_REJECTED=PASS
ABSENT_SCOPE_GENERAL_LEVEL_UPDATE_REJECTED=PASS
ABSENT_SCOPE_GENERAL_PROGRESSION_REJECTED=PASS

EXPLICIT_GENERAL_ESTIMATE_ACCEPTED=PASS
EXPLICIT_GENERAL_LEVEL_UPDATE_ACCEPTED=PASS
EXPLICIT_GENERAL_PROGRESSION_ACCEPTED=PASS

SPECIFIC_WRITING_BEHAVIOR_PRESERVED=PASS
COMPLETE_GLOBAL_CERTIFICATE_BEHAVIOR_PRESERVED=PASS

ALL_FRAMEWORK_CONTEXTS_REQUIRE_GROUNDING=PASS
ALL_CLAIM_SCOPES_USE_CANONICAL_BINDING=PASS
ALL_EPISTEMIC_PATHS_SHARE_INVARIANTS=PASS
ALL_HISTORICAL_BYPASSES_BLOCKED=PASS
```

---

# 7. Final markers

```text
BUNDLE_EXTERNAL_SHA256=PASS
BUNDLE_INTERNAL_SHA256SUMS=80/80_PASS
CANDIDATE_HEAD=af2346c

PREVIOUS_SPECIFIC_TO_GENERAL_BYPASS=PASS
PREVIOUS_UNKNOWN_SCOPE_BYPASS=PASS
PREVIOUS_UNGROUNDED_FRAMEWORK_TAG=PASS
PREVIOUS_LEVEL_UPDATE_CEFR_FALLBACK=PASS
PREVIOUS_CERTIFICATE_DATE_SYNTAX=PASS
PREVIOUS_CERTIFICATE_SOURCE_ROLE_FIXES=PASS

FRAMEWORKLESS_ESTIMATE_FAIL_CLOSED=FAIL
FRAMEWORKLESS_OBSERVED_FAIL_CLOSED=FAIL
INFERRED_FRAMEWORK_PER_EVIDENCE_BINDING=FAIL

ABSENT_SCOPE_GENERAL_ESTIMATE=FAIL
ABSENT_SCOPE_GENERAL_OBSERVED=FAIL
ABSENT_SCOPE_GENERAL_UPDATE=FAIL
ABSENT_SCOPE_GENERAL_PROGRESSION=FAIL

FINAL_META_GATE_COMPLETE=FAIL

AT_DP_026_CURRENT_SCENARIO=PASS
CANON=16/15/14/15/9
MODULES=14
PARENTHOOD_UNCHANGED=PASS
SHARED_ENGINE_UNCHANGED=PASS

PHASE10_26_FINAL_CLEAN_INDEPENDENT_CLOSURE_AUDIT=FAIL
BLOCKERS=1
MAJORS=2
MINORS=0
CLOSURE=NO
DP_026=REQUIRES_PHASE_INSPECTION
PUSH=NO
MERGE=NO
REPO_MODIFIED=NO
```
