# Phase 11.21 — Model Gateway — Independent Re-audit V3

**Project:** CMM OS  
**Phase:** 11.21 — Model Gateway  
**Requirement:** `F11-020`  
**Design Point:** `DP-121 — Canonical Provider-Independent Model Gateway`  
**Acceptance:** `AT-DP-121`  
**Audit:** Independent Re-audit V3 after Remediation V2  
**Date:** 2026-09-25  
**Auditor:** ChatGPT, independent of the implementation/remediation agent

---

## 1. Final verdict

```text
INDEPENDENT_REAUDIT_V3=PASS

AUDITED_HEAD=fe5eda5ccba327d3002979910f9cf4d8a4053ddc
AUDITED_TREE=0e8a1ac75e5fdf32a5e5e240790a0d8ff986ced7
AUDITED_BUNDLE_SHA256=1873217d10222e87e9d5e319a319eaddf7741c4ef05d384377bb4548f47a5bd3

BLOCKERS=0
MAJORS=0
MINORS=0

AUDIT_V1_MAJOR_01=VERIFIED_REMEDIATED
AUDIT_V1_MAJOR_02=VERIFIED_REMEDIATED
AUDIT_V1_MAJOR_03=VERIFIED_REMEDIATED
AUDIT_V1_MAJOR_04=VERIFIED_REMEDIATED
AUDIT_V1_MAJOR_05=VERIFIED_REMEDIATED
AUDIT_V1_MINOR_01=VERIFIED_REMEDIATED

F11_020=VERIFIED_EXISTING
DP_121=VERIFIED_EXISTING
AT_DP_121=PASS
AT_DP_134=PASS
AT_DP_101=PASS
AT_DP_102=PASS
AT_DP_103=PASS
AT_DP_104=PASS
AT_DP_105=PASS

CLOSURE_ELIGIBLE=YES

PROCESS_DEVIATION_HISTORY=1
CURRENT_REMEDIATION_V2_PROCESS_DEVIATION=NONE_REPORTED_OR_OBSERVED_IN_ARTIFACT

NEXT=PHASE11_21_DOCS_ONLY_CLOSURE
```

Phase 11.21 is now independently verified and eligible for closure.

This report itself does **not** close the phase. The next and only permitted step is a separate docs-only closure commit.

---

## 2. Exact artifact identity

Audited bundle:

```text
cmm-phase11-21-remediation-v2-fe5eda5ccba3.tar.gz
```

Independent SHA-256:

```text
1873217d10222e87e9d5e319a319eaddf7741c4ef05d384377bb4548f47a5bd3
```

Archive facts:

```text
ENTRIES=2609
UNSAFE_ARCHIVE_MEMBERS=0
SYMLINKS=0
EMBEDDED_GIT_ARCHIVE_HEAD=fe5eda5ccba327d3002979910f9cf4d8a4053ddc
```

The Git tree was independently reconstructed directly from the TAR member bytes and TAR file modes:

```text
RECONSTRUCTED_TREE=0e8a1ac75e5fdf32a5e5e240790a0d8ff986ced7
DECLARED_TREE=0e8a1ac75e5fdf32a5e5e240790a0d8ff986ced7
TREE_IDENTITY=PASS
```

Therefore the audited archive is the exact committed tree declared by the implementation report.

---

## 3. Governing artifact integrity

The exact bundle preserves every frozen governing artifact:

```text
ORIGINAL_DESIGN_SHA256=6f9bbc405d5d20383714785bca401e6f9ad5de61c319e7463d02bffbc1214400
ORIGINAL_PLAN_SHA256=e82eb2b2e3c9f2b09b828f3ccc9f701d6eb9edc294b38916ab9d9c8281e64fa7
AUDIT_V1_SHA256=f56198e8652fa12b7ae33d4b3147f9addf34c6d045e5982026448059fc08cfef
REMEDIATION_V1_DESIGN_SHA256=921578ce79631832ec7ff376186429f093271e5774d9d8b29fd7526cf3dfb67e
REMEDIATION_V1_PLAN_SHA256=83416198d56c6868cab0cb2eedcb7dc588e230d199af215afaf9e27fb7dd66dc
REAUDIT_V2_SHA256=88aa7194e49db0fc90b9869917b9a91c41a8d758e1d388378fe74eb4196de48f
REMEDIATION_V2_DESIGN_SHA256=3507564538c215fe3e903dfe7f9f39d552f3177cce7b577ad2f13191a96957cc
REMEDIATION_V2_PLAN_SHA256=013c5324d556726a4a593d31e43e6510a30eb9440dc877b3235ae05bc8c60803
```

Historical Audit V1 and Re-audit V2 remain immutable.

---

## 4. Remediation V2 scope audit

A direct archive-to-archive comparison against the prior Remediation V1 audit candidate shows:

### Added historical/governing artifacts

```text
docs/audits/phase-11.21-model-gateway-independent-reaudit-v2.md
docs/superpowers/plans/2026-09-25-phase-11.21-remediation-v2-implementation-plan.md
docs/superpowers/specs/2026-09-25-phase-11.21-remediation-v2-design.md
```

### Changed production/test/current-state files

```text
ROADMAP.md
docs/reference/phase-11-model-gateway.md
docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md
docs/roadmap/phase-11-stable-integrated-platform.md
kernel/llm/model_gateway.py
tests/llm/test_model_gateway_execution.py
tests/llm/test_phase11_21_dp121_acceptance.py
```

### Removed files

```text
NONE
```

The production diff in `kernel/llm/model_gateway.py` is narrow:

- removes the candidate-set-wide `_require_egress_authority(...)` invocation;
- removes that helper;
- retains candidate-local privacy handling in `_candidate_gate(...)`;
- updates the corresponding explanatory comment.

No new authority, router, store, runtime or client surface was introduced.

```text
REMEDIATION_V2_SCOPE=PASS
```

---

## 5. Residual MAJOR-01 — VERIFIED_REMEDIATED

Re-audit V2 identified:

```text
AUTO_REMOTE_EGRESS_PRECHECK_STILL_ABORTS_BEFORE_VALID_LOCAL_CANDIDATE_WHEN_PRIVACY_METADATA_IS_ABSENT
```

The audited Remediation V2 removes the candidate-set-wide precheck.

Current AUTO flow is:

```text
find_matching_models(...)
        ↓
canonical ordered candidates
        ↓
_candidate_gate(candidate)
        ↓
candidate-local privacy / capability / adapter decision
        ↓
continue on candidate-local hard-gate failure
        ↓
first executable candidate wins
```

No re-ranking was introduced.

---

## 6. Independent AUTO/privacy reproduction matrix

The six required Re-audit V3 cases were independently exercised directly against the exact audited `kernel.llm` code.

### 6.1 AUTO + mixed remote/local + `privacy=None`

Canonical order independently verified:

```text
remote-a:cheap-remote
local:pricey-local
```

Observed:

```text
selected_provider=local
selected_model=pricey-local
remote_calls=0
local_calls=1
```

```text
AUTO_PRIVACY_NONE_REMOTE_FIRST_LOCAL_SECOND=PASS
```

### 6.2 AUTO + mixed remote/local + no privacy gate

Observed:

```text
selected_provider=local
selected_model=pricey-local
remote_calls=0
local_calls=1
```

```text
AUTO_NO_PRIVACY_GATE_REMOTE_FIRST_LOCAL_SECOND=PASS
```

### 6.3 EXPLICIT remote + `privacy=None`

Observed:

```text
error=PRIVACY_DENIED
remote_calls=0
```

```text
EXPLICIT_REMOTE_PRIVACY_NONE=DENIED_BEFORE_IO
```

### 6.4 EXPLICIT remote + no privacy gate

Observed:

```text
error=PRIVACY_DENIED
remote_calls=0
```

```text
EXPLICIT_REMOTE_NO_PRIVACY_GATE=DENIED_BEFORE_IO
```

### 6.5 AUTO only remote + `privacy=None`

Observed:

```text
error=PRIVACY_DENIED
remote_a_calls=0
remote_b_calls=0
```

```text
AUTO_ONLY_REMOTE_PRIVACY_NONE=FAIL_CLOSED_BEFORE_IO
```

### 6.6 AUTO only remote + no privacy gate

Observed:

```text
error=PRIVACY_DENIED
remote_a_calls=0
remote_b_calls=0
```

```text
AUTO_ONLY_REMOTE_NO_PRIVACY_GATE=FAIL_CLOSED_BEFORE_IO
```

---

## 7. LOCAL_ONLY regression — PASS

The original Audit V1 AUTO/privacy case was re-probed independently with:

```text
remote first
local second
remote privacy denied
local privacy allowed
```

Observed:

```text
selected_provider=local
selected_model=pricey-local
remote_calls=0
local_calls=1
```

```text
AUTO_LOCAL_ONLY_REMOTE_FIRST_LOCAL_SECOND=PASS
```

---

## 8. Canonical ordering — VERIFIED

The independent mixed-catalog probe verified the canonical model-selection order before execution:

```text
remote-a:cheap-remote
local:pricey-local
```

The gateway selected the local model only because the earlier remote candidate failed its own privacy hard gate.

No local-first sorting or gateway-owned re-ranking was introduced.

```text
CANONICAL_AUTO_ORDER_PRESERVED=PASS
PHASE11_35_ROUTING_POLICY_INTRODUCED=NO
```

---

## 9. Audit V1 MAJOR-02 — STILL VERIFIED_REMEDIATED

Call-wide cancellation was independently re-probed using a primary adapter that:

1. receives the exact caller token;
2. cancels that token;
3. raises retryable `PROVIDER_FAILURE`;
4. has an authorized fallback available.

Observed:

```text
terminal_error=MODEL_CALL_CANCELLED
primary_calls=1
fallback_calls=0
same_cancellation_object=True
```

```text
AUDIT_V1_MAJOR_02=VERIFIED_REMEDIATED
```

---

## 10. Audit V1 MAJOR-03 — STILL VERIFIED_REMEDIATED

The exact audited streaming tests were executed directly without global pytest collection.

Passed:

```text
test_the_public_stream_drops_content_arriving_after_the_deadline
test_a_permanently_blocked_provider_iterator_is_publicly_bounded
test_user_cancellation_while_the_provider_blocks_terminates_as_cancelled
```

Therefore:

```text
NO_LATE_CONTENT_AFTER_TIMEOUT=PASS
BLOCKING_PROVIDER_NEXT_PUBLICLY_BOUNDED=PASS
BLOCKED_STREAM_USER_CANCELLATION=PASS
AUDIT_V1_MAJOR_03=VERIFIED_REMEDIATED
```

---

## 11. Audit V1 MAJOR-04 — STILL VERIFIED_REMEDIATED

The exact audited adapter regression tests were executed directly.

Passed:

```text
test_legacy_provider_wrapper_refuses_tools_before_provider_io
test_legacy_provider_wrapper_refuses_structured_output_before_provider_io
test_legacy_provider_wrapper_plain_text_path_is_unchanged
```

Therefore:

```text
LEGACY_TOOLS_FAIL_CLOSED_BEFORE_PROVIDER_IO=PASS
LEGACY_STRUCTURED_OUTPUT_FAIL_CLOSED_BEFORE_PROVIDER_IO=PASS
LEGACY_PLAIN_TEXT_REGRESSION=PASS
AUDIT_V1_MAJOR_04=VERIFIED_REMEDIATED
```

---

## 12. Audit V1 MAJOR-05 — STILL VERIFIED_REMEDIATED

The exact audited provider-state tests were executed directly.

Passed:

```text
test_the_persisted_schema_is_version_three
test_phase11_capabilities_survive_the_persistence_round_trip
test_the_version_two_capability_shape_is_rejected
test_canonical_document_media_type_order_is_preserved
test_phase11_capabilities_survive_the_canonical_state_path
```

The `AT-DP-134` schema-v3 real-restart checkpoint was also invoked independently with a temporary filesystem and passed:

```text
test_phase11_21_schema_v3_capabilities_survive_a_real_restart=PASS
```

Therefore:

```text
SCHEMA_V3_CAPABILITY_PERSISTENCE=PASS
SCHEMA_V2_REJECTION=PASS
CANONICAL_RESTART_CAPABILITY_TRUTH=PASS
AT_DP_134_SCHEMA_V3_CHECKPOINT=PASS
AUDIT_V1_MAJOR_05=VERIFIED_REMEDIATED
```

---

## 13. Audit V1 MINOR-01 — STILL VERIFIED_REMEDIATED

Current implementation-state docs use:

```text
tests/llm/test_phase11_21_dp121_acceptance.py
```

and exact Remediation V2 evidence:

```text
Focused gateway suite=404 passed
AT-DP-121=38 passed
LLM suite=1153 passed
Global suite=21782 passed, 1 warning
```

No stale current-state evidence remains.

```text
AUDIT_V1_MINOR_01=VERIFIED_REMEDIATED
```

---

## 14. AT-DP-121 result

The connected acceptance now contains Remediation V2 Scenario S:

```text
AUTO mixed remote/local without privacy metadata
```

Its source verifies:

```text
canonical remote first
canonical local second
privacy=None
remote call count=0
local call count=1
selected local model
```

Local exact-HEAD evidence reports:

```text
AT_DP_121=38 passed
```

The audit environment cannot perform full pytest collection because it lacks the repository-declared `libcst` dependency. That environment limitation is unchanged from V1/V2.

However:

- the connected acceptance source is present and structurally connected;
- Scenario S semantics were independently reproduced;
- the critical semantics of prior remediation scenarios were independently re-executed;
- no contradictory behavior remains.

Therefore:

```text
AT_DP_121=PASS
```

---

## 15. Inherited acceptance evidence

Exact-head implementation evidence reports:

```text
AT_DP_134=PASS (68)
AT_DP_101=PASS (31)
AT_DP_102=PASS (33)
AT_DP_103=PASS (47)
AT_DP_104=PASS (69)
AT_DP_105=PASS (1)
```

The audit independently re-executed the new schema-v3 restart checkpoint inside the existing `AT-DP-134` suite and found no closed-owner regression.

No production file from Phase 11.1–11.5 was changed by Remediation V2.

```text
INHERITED_ACCEPTANCE_REGRESSION=NONE_OBSERVED
```

---

## 16. Global/local gate evidence

Implementation-machine evidence for exact HEAD:

```text
FOCUSED_TESTS=404 passed
LLM_SUITE=1153 passed
SUBSYSTEM_TESTS=2860 passed
GLOBAL_TESTS=21782 passed, 1 warning

RUFF_TOUCHED=PASS
FORMAT=PASS
RUFF_GLOBAL_BASELINE=837
RUFF_GLOBAL_FINAL=837
RUFF_NEW_FINDINGS=0

COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
```

Independent audit execution:

```text
COMPILEALL=PASS
TRAILING_WHITESPACE_HITS=0
```

Full independent pytest replay remains unavailable solely because this audit environment lacks `libcst`.

That limitation does not mask any remaining audit finding because the closure-critical behaviors were independently executed directly.

---

## 17. Architecture and scope result

The final implementation preserves:

```text
ProviderRegistry canonical ownership
ModelCatalog canonical ownership
Phase 11.34 persistence ownership
Phase 11.1 composition ownership
canonical privacy authority boundary
Agent Runtime fallback authority
tool non-execution
no hidden reasoning exposure
real image/document transport
bounded model-call/stream lifecycle
```

Not introduced:

```text
Phase 11.35 Routing Policy Engine
Phase 11.50 client interfaces
new provider registry
new model catalog
new persistence store
new privacy engine
new validation engine
new event bus
CMMChat changes
CMM Bots changes
```

```text
ARCHITECTURE=PASS
SCOPE=PASS
ANTI_FRAGMENTATION=PASS
```

---

## 18. Process-discipline history

Independent Re-audit V2 preserved one historical process deviation:

```text
git stash
git stash pop
```

during Remediation V1.

That deviation remains part of the audit history and is not erased.

For Remediation V2, the implementation agent explicitly reports:

```text
PROHIBITED_GIT_COMMANDS_USED=NO
STASH=EMPTY
WORKTREE=CLEAN
```

The TAR cannot independently prove shell-command history, but no artifact inconsistency or new process deviation is observed.

```text
PROCESS_DEVIATION_HISTORY=1
CURRENT_REMEDIATION_V2_PROCESS_DEVIATION=NONE_REPORTED_OR_OBSERVED_IN_ARTIFACT
```

The historical deviation does not invalidate the independently verified final exact-HEAD artifact.

---

## 19. DP-121 final verification

The final Model Gateway now independently satisfies the frozen Design Point:

```text
one canonical provider-independent execution boundary
canonical provider/model authority reuse
explicit model authority
AUTO canonical-order execution with candidate-local hard gates
reasoning-effort truth
real image/PDF/document content
structured-output normalization
tool-call normalization without execution
provider-token streaming
bounded timeout
call-wide cancellation
privacy-aware local/remote execution
safe retry/fallback
usage/cost/latency truth
safe evidence
Phase 11.1 composition
Phase 11.34 persistent capability truth
```

No open blocker, major or minor remains.

```text
DP_121=VERIFIED_EXISTING
```

---

## 20. Final finding matrix

```text
BLOCKERS=0
MAJORS=0
MINORS=0

AUDIT_V1_MAJOR_01=VERIFIED_REMEDIATED
AUDIT_V1_MAJOR_02=VERIFIED_REMEDIATED
AUDIT_V1_MAJOR_03=VERIFIED_REMEDIATED
AUDIT_V1_MAJOR_04=VERIFIED_REMEDIATED
AUDIT_V1_MAJOR_05=VERIFIED_REMEDIATED
AUDIT_V1_MINOR_01=VERIFIED_REMEDIATED
```

---

## 21. Closure eligibility

The permanent Phase 11.21 threshold is now satisfied:

```text
BLOCKERS=0
MAJORS=0
DP-121=VERIFIED_EXISTING
AT-DP-121=PASS
CLOSURE_ELIGIBLE=YES
```

Therefore Phase 11.21 is eligible for its dedicated docs-only closure commit.

No code change is permitted in that closure commit.

---

## 22. Final Re-audit V3 status

```text
INDEPENDENT_REAUDIT_V3=PASS

AUDITED_HEAD=fe5eda5ccba327d3002979910f9cf4d8a4053ddc
AUDITED_TREE=0e8a1ac75e5fdf32a5e5e240790a0d8ff986ced7
AUDITED_BUNDLE_SHA256=1873217d10222e87e9d5e319a319eaddf7741c4ef05d384377bb4548f47a5bd3

BLOCKERS=0
MAJORS=0
MINORS=0

F11_020=VERIFIED_EXISTING
DP_121=VERIFIED_EXISTING
AT_DP_121=PASS

CLOSURE_ELIGIBLE=YES

NEXT=PHASE11_21_DOCS_ONLY_CLOSURE
```

Phase 11.21 is independently verified but is not yet formally closed until the separate docs-only closure commit is made and verified.
