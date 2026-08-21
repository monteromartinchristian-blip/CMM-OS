# Conversational Freedom Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve CMM OS safety at fact-promotion, persistence and action boundaries without suppressing useful conversational hypotheses, interpretations or natural human-readable presentation.

**Architecture:** Reuse the existing distinction between `SENSITIVE_INFERENCE` and `SENSITIVE_INFERENCE_PERSIST`. Permit qualified analysis where the specialized domain supports it, while retaining strict controls over fact promotion, diagnosis authority, memory, export and actions. Presentation remains epistemically lossless, but HUMAN_READABLE output must not mechanically expose empty disclaimer scaffolding.

**Tech Stack:** Python 3.10+, pytest, Ruff, existing Phase 8 Cognitive Layer and Phase 10 Domain Intelligence contracts.

**Spec:** Existing Phase 8 / Phase 10 contracts plus the approved Conversational Freedom Principle.

## Global Constraints

- Do not create a parallel reasoning, permission, presentation, memory or safety engine.
- Do not modify `cmm/domains/reflection/*`.
- Do not weaken provenance, uncertainty, temporality or fact/hypothesis distinctions.
- Do not permit automatic sensitive-inference persistence.
- Do not permit automatic memory writes, external communication, export or consequential actions.
- General Domain remains conservative and must not bypass specialized-domain restrictions.
- Use TDD: every production behavior change requires a witnessed failing test first.

---

### Task 1: Separate conversational inference from persistence

**Files:**
- Modify: `cmm/domains/relationships/permissions.py`
- Modify: `cmm/domains/relationships/profile.py`
- Modify: `cmm/domains/relationships/rules.py`
- Modify: `cmm/domains/health/permissions.py`
- Test: `tests/domains/test_conversational_freedom_contract.py`

**Interfaces:**
- `PermissionCapability.SENSITIVE_INFERENCE` permits qualified analysis.
- `PermissionCapability.SENSITIVE_INFERENCE_PERSIST` remains prohibited.
- `DoNotInferIntentRule` prevents intent-as-fact but does not block a tentative hypothesis merely for lacking direct evidence.

- [ ] Write RED tests for Relationships and Health inference permissions.
- [ ] Write RED test proving Relationships keeps `intent_as_fact` prohibited while labelled hypotheses remain allowed.
- [ ] Write RED test proving unsupported intent remains non-established without blocking the whole reasoning result.
- [ ] Run the focused file and verify failures are behavioral, not import/contract errors.
- [ ] Implement the minimum production changes.
- [ ] Run focused Relationships/Health regressions.

### Task 2: Separate diagnostic hypothesis from definitive diagnosis

**Files:**
- Modify only if required: `cmm/domains/health/profile.py`
- Modify: `cmm/domains/health/rules.py`
- Test: `tests/domains/test_conversational_freedom_contract.py`
- Test existing Health rule suites.

**Interfaces:**
- A provisional diagnostic hypothesis remains explicitly hypothetical.
- An unsupported definitive diagnosis remains blocked/escalated.
- A documented diagnosis retains its documented epistemic status.
- No hypothesis is persisted as diagnosis automatically.

- [ ] Add RED tests for tentative diagnostic discussion.
- [ ] Add RED tests retaining the definitive-diagnosis block.
- [ ] Implement the minimum distinction.
- [ ] Run Health regressions.

### Task 3: Human-readable presentation without mechanical disclaimers

**Files:**
- Modify: `cmm/domains/presentation_planner.py`
- Modify only if required: `cmm/domains/presentation_validation.py`
- Test: `tests/domains/test_conversational_freedom_contract.py`
- Test existing Domain Presentation suites.

**Interfaces:**
- `STRUCTURED` and artifact outputs preserve strict structural requirements.
- `HUMAN_READABLE` does not manufacture an empty disclaimer section solely because `require_disclaimers=True`.
- Real warnings, approvals, escalations and required epistemic qualifications remain visible.
- `allow_speculation=False` continues to require hypothesis qualification rather than suppressing hypotheses.

- [ ] Add RED tests for HUMAN_READABLE empty-disclaimer suppression.
- [ ] Add regression proving actual warnings/approvals remain visible.
- [ ] Add regression proving STRUCTURED output remains strict.
- [ ] Implement minimal intent-aware planning/validation.
- [ ] Run complete presentation regressions.

### Task 4: Regression, documentation and commit gate

**Files:**
- Update only the minimal shared/domain reference documentation made inaccurate by Tasks 1–3.
- Do not modify Reflection production files.

- [ ] Run focused conversational-freedom tests.
- [ ] Run Relationships and Health suites.
- [ ] Run Domain Presentation suites.
- [ ] Run all `tests/domains`.
- [ ] Run the global pytest suite.
- [ ] Run Ruff and Ruff py310 over changed Python.
- [ ] Run compileall and dependency-direction tests.
- [ ] Run `git diff --check`.
- [ ] Verify no `cmm/domains/reflection/*` production diff exists.
- [ ] Commit only after all verification is green.

## Implementation outcome

Implemented and verified on `feature/phase-10-domain-intelligence`.

### Conversational inference boundary

- Qualified sensitive analysis is permitted in the specialized Relationships and Health domains.
- Sensitive inference persistence remains prohibited.
- Memory writes, external communication, export and consequential action remain independently restricted.
- Relationships may retain an unsupported intention attribution as a labelled, non-established hypothesis.
- Intent is still not promoted to fact without grounding.
- A caller claiming `direct_evidence=True` without an evidence reference remains blocked.
- A caller claiming `sourced_statement=True` without a source reference remains blocked.
- Third-party diagnosis, intent-as-fact and sensitive inference persistence remain prohibited.

### Human-readable presentation boundary

- `require_disclaimers=True` no longer manufactures an empty disclaimer section for explicit `HUMAN_READABLE` output.
- Real warnings and other safety-relevant references remain visible.
- `STRUCTURED` output retains the strict disclaimer structure.
- `allow_speculation=False` preserves hypotheses as epistemically qualified rather than suppressing them.
- Provenance, uncertainty and preservation validation remain intact.

### Frozen-domain guarantee

No production file under `cmm/domains/reflection/` was modified.

### Verification evidence

Fresh transversal gate:

- `pytest -q tests/domains` → 5226 passed
- conversational-freedom contract → 11 passed
- shared permission boundaries → 44 passed
- presentation subsystem → 40 passed
- Ruff → all checks passed
- `python -m compileall -q cmm tests/domains` → PASS
- `git diff --check` → PASS
- Reflection production diff → EMPTY
