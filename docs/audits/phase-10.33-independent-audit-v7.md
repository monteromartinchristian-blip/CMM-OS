# CMM OS — Phase 10.33 Independent Audit V7

**Date:** 2026-08-29
**Audited branch:** `feature/phase-10-domain-intelligence`
**Audited HEAD:** `2e33566e1d7aebaefe985e0624c27e1142b3c1f3`
**Implementation base:** `b72d47b59d64b5afcc07c9f3883cbf8d9ce5b979`
**Audit V6 report HEAD:** `82c5a9dfaa94097a5df0b903e399d716123ec8ed`
**Bundle SHA-256:** `44079fbdadeb0a6cec4ceb53a25a0f2925474ad1efaa7c31c0bf350f272469df`
**Bundle source:** `git archive 2e33566e1d7aebaefe985e0624c27e1142b3c1f3`
**Verdict:** FAIL — one privacy blocker remains

## Audit summary

- BLOCKERS: 1
- MAJORS: 0
- MINORS: 0
- Phase 10.33 remains `Implemented, pending independent re-audit`.
- Phase 10.34 must not be advanced.
- Both specific V6 findings are independently confirmed remediated.
- The broader `no credentials` invariant remains unclosed because credential detection is still a provider-prefix allow/block list with material gaps.

## V6 remediation disposition

| V6 finding | V7 status | Result |
|---|---|---|
| B2 — privacy validation ordering | PASS | Secret/private mapping keys are privacy-validated before use in nested JSON error paths; independently reproduced V6 attack cases no longer disclose key content. |
| B2 — GitHub/AWS/Google/Slack credential formats | PASS | The credential families explicitly required by V6 are now rejected by the centralized event privacy validator. |

---

## B2 — credential detector remains structurally incomplete

**Severity:** BLOCKER
**Scope:** event-wide privacy / credentials / Kernel boundary

The canonical Phase 10.33 design states:

```text
payload and metadata are JSON-safe
credential- and secret-like keys are rejected recursively
raw secrets and credentials are forbidden
no credentials
events contain no secrets and reject secret-like structures recursively
```

The V6 remediation extends `_SECRET_VALUE_PATTERNS` with GitHub, AWS, Google and Slack token families. Those additions work.

However, the event boundary still depends on enumerating specific provider token prefixes. Other common, high-confidence credential formats remain accepted as ordinary strings.

### Independently reproduced credential families

Synthetic values with the following recognizable credential formats were accepted:

```text
GitLab personal access token: glpat-...
npm access token: npm_...
Hugging Face token: hf_...
SendGrid API key: SG.<segment>.<segment>
DigitalOcean personal access token: dop_v1_...
```

These probes used only synthetic values.

For every tested family, acceptance was reproduced through:

```text
DomainEvent.event_id
DomainEvent.payload nested string
DomainEventReference.reference_id
```

For payloads, the value survived:

```text
DomainEvent
→ DomainKernelEventPublisher
→ kernel.events.Event.payload
```

unchanged.

### DomainId bypass also remains possible

A syntactically valid lower-case GitLab-style credential slug equivalent to:

```text
glpat-aaaaaaaaaaaaaaaaaaaa
```

was independently accepted as:

```text
DomainId.slug
```

and then serialized unchanged into the Kernel event payload.

This demonstrates that the previously remediated DomainId privacy path is only as strong as the centralized secret detector.

### Why this remains a blocker

Phase 10.33 does not claim merely:

```text
reject OpenAI/GitHub/AWS/Google/Slack credentials
```

It claims a strict event boundary containing no credentials.

A detector that closes one provider list per audit cannot establish that invariant. V6 fixed the examples from V6, but not the contract-level guarantee.

### Required remediation direction

Do **not** remediate V7 by adding only these five new regexes and stopping.

The next remediation must explicitly define and implement a durable credential-detection policy.

At minimum:

1. centralize high-confidence provider token signatures in one canonical registry/policy rather than ad hoc scattered regexes;
2. cover a materially broader set of standard provider token families, including at least the independently reproduced V7 families;
3. keep provider/prefix patterns precise enough to avoid broad entropy-based false positives;
4. preserve credential-like key/context rejection (`token`, `api_key`, `secret`, `access_key`, etc.);
5. apply the exact same detector to all public event strings and recursive mappings, including DomainId privacy;
6. preserve non-disclosing error messages;
7. add a table-driven regression matrix so adding a supported credential family automatically verifies:
   - event_id;
   - reference_id;
   - payload;
   - metadata;
   - optional IDs where applicable;
   - DomainId where syntactically applicable;
   - Kernel non-emission.

If the architecture cannot truthfully guarantee detection of arbitrary unknown credential formats, document the exact security contract precisely rather than continuing to imply universal secret detection. Any narrowing of the canonical `no credentials` requirement would itself require an explicit design decision and should not be done silently as a bugfix.

---

## Independently confirmed PASS areas

### Bundle integrity

- SHA-256 independently matches:
  `44079fbdadeb0a6cec4ceb53a25a0f2925474ad1efaa7c31c0bf350f272469df`.
- 1,838 TAR entries inspected.
- no symlink/hardlink entries;
- no absolute paths;
- no path traversal;
- no `.env`;
- no `.git`;
- no `.venv`;
- no cache/`.pyc` entries;
- audit reports V1 through V6 are present;
- internal manifest matches the uploaded external manifest content before its trailing SHA line.

### V6 privacy-ordering remediation

Independent probes with synthetic secret-shaped keys confirmed no secret disclosure for:

```text
payload secret key + arbitrary object
payload secret key + non-finite float
deeply nested payload secret key
metadata secret key
```

The synthetic key was absent from both exception message and details.

### V6 credential families

The V6 audit regression suite is included in the independently executed accumulated audit regressions.

The exact audit-specific suites V1 through V6 executed directly from the V7 bundle under an isolated package loader:

```text
362 passed
```

No audit-regression failures occurred.

### Focused/repository evidence

The V7 manifest records fresh repository-native verification at the audited HEAD:

```text
V6_REGRESSION_TESTS=113 PASS
FOCUSED_REAUDIT_TESTS=466 PASS
AT_DP_033_LOGICAL_CHECKPOINTS=66/66 PASS
AT_DP_033_PYTEST_CASES=92 PASS
DOMAIN_TESTS=7458 PASS
GLOBAL_TESTS=12998 PASS
RUFF_DELTA=PASS
FORMAT_DELTA=PASS
COMPILE_DELTA=PASS
DIFF_CHECK=PASS
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
```

A sandbox attempt to execute the complete 466-test focused gate under the isolated loader produced loader/cwd-specific failures in public-package and source-path checks; those are environmental artifacts of bypassing `cmm.domains.__init__` to avoid the unavailable optional `libcst` dependency, not repository findings. They are therefore not counted as audit findings.

### Catalog / acceptance / architecture

Independent static inspection confirmed:

```text
GENERAL_EVENT_COUNT=23
GENERAL_EVENT_UNIQUE_COUNT=23
AT_DP_033_LOGICAL_CHECKPOINTS=66
AT_DP_033_RANGE=CP-01..CP-66
```

The roadmap still marks Phase 10.33 as:

```text
Implemented, pending independent re-audit
```

and Phase 10.34 has not been advanced.

Phase 10.33 event modules still contain no:

```text
AgentRuntimeEventBus
event persistence
event replay
durable queue
DLQ
```

`DomainConflictResolver` remains free of Domain Event / Kernel publication imports.

### V5 guarantees retained

Static inspection and accumulated regressions preserve:

```text
MappingProxyType goes through JSON validation
caller mappings are deep-frozen into fresh immutable state
non-string unknown field names fail without raw-value disclosure
```

---

## Required next state

```text
PHASE10_33_INDEPENDENT_AUDIT_V7=FAIL
BLOCKERS=1
MAJORS=0
MINORS=0

AUDITED_HEAD=2e33566e1d7aebaefe985e0624c27e1142b3c1f3
AUDIT_BUNDLE_SHA256=44079fbdadeb0a6cec4ceb53a25a0f2925474ad1efaa7c31c0bf350f272469df

V6_PRIVACY_VALIDATION_ORDERING=PASS
V6_CREDENTIAL_FORMATS=PASS

B2_CREDENTIAL_DETECTION_POLICY=FAIL
B2_ADDITIONAL_HIGH_CONFIDENCE_CREDENTIALS=FAIL
KERNEL_CREDENTIAL_BOUNDARY=FAIL

GENERAL_EVENT_COUNT=23
AT_DP_033_ACCOUNTING=PASS

CLOSE_PHASE=NO
ADVANCE_PHASE10_34=NO
NEXT=REMEDIATE_AUDIT_V7
PUSH=NO
MERGE=NO
```
