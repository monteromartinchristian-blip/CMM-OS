# CMM OS — Phase 10.45 — Independent Re-audit V3

**Audit date:** 2026-09-09
**Phase:** 10.45 — Integration with Interfaces
**Audit type:** Independent exact-HEAD re-audit after Re-audit V2 remediation
**Verdict:** **FAIL — one targeted MAJOR remains**

## Audited artifact

```text
BUNDLE=phase-10.45-reaudit-v3-557e30e3bcf25a2912dc0cc7f3839e2c6932b6e6.tar.gz
AUDITED_IMPLEMENTATION_HEAD=557e30e3bcf25a2912dc0cc7f3839e2c6932b6e6
AUDIT_BUNDLE_SHA256=de4f63aad84363a4515ebf90fec68db6d24d48bf583ddcb2bc36ef92f49d8dbe
```

The archive is a valid `git archive`. Its embedded Git commit ID matches both the filename and the reported remediation HEAD.

---

# 1. Independent Re-audit V3 result

```text
INDEPENDENT_REAUDIT_V3=FAIL

BLOCKERS=0
MAJORS=1
MINORS=0

DP-045=NOT_VERIFIED
AT-DP-045_TEST_EXECUTION=PASS
AT-DP-045=FAIL_INDEPENDENT_ADEQUACY

CLOSURE_ELIGIBLE=NO
```

Phase 10.45 must not be closed.

The V3 bundle is immutable historical evidence. Any correction requires a new commit, a new exact-HEAD bundle, a new SHA-256, and Independent Re-audit V4.

---

# 2. Bundle integrity

Fresh independent verification:

```text
GZIP_INTEGRITY=PASS
GIT_ARCHIVE_COMMIT_ID=557e30e3bcf25a2912dc0cc7f3839e2c6932b6e6
FILENAME_HEAD_MATCH=PASS
AUDIT_BUNDLE_SHA256=de4f63aad84363a4515ebf90fec68db6d24d48bf583ddcb2bc36ef92f49d8dbe
```

The archive uses the prefix:

```text
CMM-OS-phase-10.45/
```

This is valid `git archive` packaging and does not affect integrity.

Required source/test/docs/audit artifacts are present.

Historical audit evidence remains intact:

```text
AUDIT_V1_SHA256=e0e7e5048524905cedb861a8398b1524c72e6fa503e5cdf0a8617ecf5757bad2
REAUDIT_V2_SHA256=14096ed98001420bda681f92a23908fabf6b98e698a913b84ed65f265e23172e
```

---

# 3. Fresh execution evidence

The independent audit sandbox lacks the project dependency `libcst`, even though the archive declares `libcst>=1.0` in `pyproject.toml`.

As in earlier audits, an audit-only import stub was placed **outside** the extracted archive solely to let unrelated package imports complete. Phase 10.45 implementation modules do not use `libcst`.

Fresh exact-archive execution:

```text
PHASE10_45_DEDICATED_TESTS=206 PASSED
AT_DP_045_TEST=1 PASSED
AT_DP_045_MARKER=PASS
ARCHITECTURE_TESTS=12 PASSED
PHASE10_45_COMPILEALL=PASS
```

A full `tests/domains` reproduction is not fairly comparable in this sandbox: collection reaches unrelated pre-existing Python-version/runtime behavior in `DomainReasoningRuleDefinition`, and some subprocess import tests intentionally clear `PYTHONPATH` while this extracted archive is not installed as a package. Those environment-only failures are not counted against Phase 10.45.

The agent-reported final-tree evidence remains:

```text
FULL_SUITE_REPORTED=15598 PASSED
PHASE10_45_REPORTED=206 PASSED
```

The V3 audit verdict below does not rely on those reports; it rests on independently reproduced behavior against the exact archive.

---

# 4. V2 remediation status

## V2-MAJOR-02 — permission evidence binding / only-ALLOW-proceeds

**Remediated.**

Independent probes verified:

```text
TARGET_MISMATCH_FAIL_CLOSED=YES
SOURCE_MISMATCH_FAIL_CLOSED=YES
SESSION_MISMATCH_FAIL_CLOSED=YES
ABSTAIN_STATUS=blocked
PERSISTED_REVISION_AFTER_FAILURE=1
```

The coordinator now:

- binds target/source/session permission evidence;
- requires a canonical `CrossDomainPermissionDecision`;
- binds `decision.request_id`;
- allows only `PermissionOutcome.ALLOW`;
- blocks `DENY`;
- pends `APPROVAL_REQUIRED`;
- fails closed for `ABSTAIN`/other outcomes.

```text
V2_MAJOR_02=REMEDIATED
```

## V2-MAJOR-03 — persisted session composition-derived state

**Remediated.**

Independent withdrawal probe seeded stale removed-domain effective refs:

```text
beta.rule
beta.permission
beta.workflow
beta.operation
```

After canonical `WITHDRAW_SUPPORTING(domain:beta)`:

```text
WITHDRAW_STATUS=accepted
DURABLE_REVISION=3
DURABLE_SUPPORTING=('domain:gamma',)

RULES=()
PERMS=()
WORKFLOWS=()
OPS=()

UNRELATED_SESSION_STATE_PRESERVED=True
```

The implementation now derives:

- effective profile;
- effective rule IDs;
- effective granted permission refs;
- effective workflow refs;
- available operation IDs;

from the new canonical `DomainComposition` instead of blindly inheriting them.

```text
V2_MAJOR_03=REMEDIATED
```

## V2-MAJOR-01 — selection-transition authority coherence

**Partially remediated but still fails independent verification.**

The explicit composition-id, primary-domain, context-id, status, and ordinary supporting-set mismatch checks were added.

However, the implementation also added an undocumented exception:

```text
_session_matches_pending_delta(...)
```

which permits an ADD request when the session supporting set equals:

```text
resolution.supporting_domains - {target}
```

That exception violates the approved amendment's requirement that the **current** session, resolution, and composition form one coherent authority chain before the command is evaluated.

A second coherence weakness comes from comparing current supporting membership with `frozenset`, allowing an ordering-divergent session to bind to a tuple-ordered canonical resolution/composition.

```text
V2_MAJOR_01=NOT_REMEDIATED
```

---

# 5. V3 MAJOR-01 — pre/post-delta authority exception bypasses exact session coherence

## Severity

```text
MAJOR
```

## Approved requirement

The committed Phase 10.45 selection-transition amendment states:

> the supplied canonical `DomainSessionContext`, `DomainResolutionResult`, and `DomainComposition` must form one coherent authority chain (session ids, primary/supporting membership, composition id, last resolution id consistent with the resolution and composition supplied)

It also states for both ADD and WITHDRAW:

```text
current canonical resolution/session/composition form one coherent authority chain
```

The V2 remediation prompt further required exact current binding before any permission, resolver, composer, or persistence operation.

## Current implementation

`_bind()` contains:

```python
if frozenset(session.supporting_domains) != frozenset(
    str(domain) for domain in resolution.supporting_domains
) and not _session_matches_pending_delta(
    request, session, resolution.supporting_domains
):
    raise ...
```

The helper explicitly permits:

```text
ADD_SUPPORTING
session supporting = resolution supporting - target
```

while the session may simultaneously claim:

```text
session.last_resolution_id == resolution.id
session.composition_id == composition.id
```

and the composition already contains the target.

That is not a coherent current authority chain; it is a session snapshot whose membership contradicts the exact resolution/composition it claims to represent.

## Independent reproduction A — pending-delta incoherence accepted and persisted

Using genuine canonical objects:

1. create a canonical post-delta resolution whose supporting set contains `domain:delta`;
2. compose a canonical composition from that resolution;
3. create a genuine `DomainSessionContext` whose:
   - `last_resolution_id` equals that post-delta resolution;
   - `composition_id` equals that post-delta composition;
   - supporting domains still contain only the **pre-delta** supporting set;
4. persist it as the current durable revision;
5. submit `ADD_SUPPORTING(domain:delta)`.

Fresh result:

```text
PENDING_DELTA_INCOHERENCE_ACCEPTED=YES
STATUS=accepted
DURABLE_REVISION=3
DURABLE_SUPPORTING=('domain:delta', 'domain:beta', 'domain:gamma')
```

The incoherent current authority is accepted and a new canonical session revision is persisted.

This is precisely the fail-closed class Re-audit V2 required to eliminate.

## Independent reproduction B — supporting order mismatch accepted

A genuine current session was supplied with the same supporting domains as the resolution/composition but in the reverse tuple order.

Fresh result:

```text
REORDERED_SUPPORTING_AUTHORITY_ACCEPTED=YES
STATUS=accepted
DURABLE_REVISION=3
```

The binding check uses set equality rather than the canonical tuple representation.

`DomainSelectionTransition` itself treats supporting-domain tuples as ordered state when calculating `supporting_changed`, so discarding order at the authority boundary is not justified by the existing canonical contract.

## Why this is a MAJOR

The coordinator is the canonical command authority introduced specifically to resolve Audit V1 MAJOR-03.

Its strongest inherited invariant is:

```text
current session ↔ current resolution ↔ current composition exact coherence
```

before deriving a new command-scoped resolution.

Allowing pre-delta session state to bind to post-delta resolution/composition:

- makes stale/incoherent canonical state authoritative;
- allows a command to persist from a state the amendment says must fail closed;
- weakens optimistic concurrency from revision-only protection into semantic ambiguity;
- makes the coordinator capable of "repairing" an incoherent authority chain instead of rejecting it.

That is outside the approved coordinator responsibility.

---

# 6. Required remediation for V3 MAJOR-01

This does **not** require another architectural amendment.

It is a small correctness fix inside the already-approved coordinator.

## 6.1 Remove the pending-delta authority exception

At command entry, require the supplied current authorities to agree exactly.

Remove `_session_matches_pending_delta()` from authority binding unless the design is explicitly amended again to introduce a separate typed transitional authority state.

No such transitional authority exists in the approved design.

The command itself is responsible for deriving the **new** post-delta resolution after binding the coherent pre-delta authority.

## 6.2 Preserve canonical tuple semantics

Require:

```text
session.supporting_domains
==
tuple(str(d) for d in resolution.supporting_domains)
==
tuple(str(d) for d in composition.supporting_domains)
```

unless an existing canonical contract explicitly normalizes supporting order differently.

Do not use `frozenset` at the authority boundary if tuple order is canonical.

## 6.3 Fail before any side effect

Both cases must fail before:

```text
permission evaluation
resolver.resolve
composer.compose
session_adapter.save_domain_session
```

At minimum persistence call count must remain zero.

## 6.4 Add adversarial tests

Required new tests:

```text
test_add_rejects_pre_delta_session_bound_to_post_delta_resolution
test_add_rejects_pre_delta_session_bound_to_post_delta_composition
test_transition_rejects_supporting_order_mismatch
test_interface_add_rejects_pending_delta_authority_mismatch
test_pending_delta_mismatch_never_persists
```

Use genuine canonical objects.

Do not weaken the successful normal ADD path:

```text
coherent pre-delta session/resolution/composition
→ derive request-scoped required target
→ new canonical resolution
→ new composition
→ exactly one new revision
```

That path does not require `_session_matches_pending_delta()`.

---

# 7. Acceptance adequacy

Fresh execution confirms:

```text
AT-DP-045_TEST_EXECUTION=PASS
AT-DP-045_MARKER=PASS
```

Independent adequacy remains:

```text
AT-DP-045=FAIL_INDEPENDENT_ADEQUACY
```

because the connected acceptance does not prove rejection of:

- a pre-delta session claiming post-delta resolution/composition identity;
- an order-divergent current supporting membership.

The acceptance test therefore demonstrates the expected happy/adversarial paths currently encoded, but it does not yet prove the amendment's full current-authority coherence invariant.

---

# 8. Architecture review

The architecture itself remains acceptable:

```text
NO_PARALLEL_SELECTION_STORE=PASS
NO_PARALLEL_SESSION_STORE=PASS
NO_PARALLEL_RESOLVER=PASS
NO_PARALLEL_COMPOSER=PASS
NO_INTERFACE_RUNTIME=PASS
DEPENDENCY_DIRECTION=PASS
ARCHITECTURE_TESTS=12 PASSED
```

The remaining defect is not fragmentation and does not require a new subsystem.

---

# 9. Documentation review

The detailed Phase 10.45 documentation correctly remains pre-closure:

```text
PHASE10_45=REMEDIATED_PENDING_INDEPENDENT_REAUDIT
DP-045=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION
AT-DP-045=PASS_REPORTED
CLOSURE_ELIGIBLE=NO
```

Historical Audit V1 and Re-audit V2 reports remain intact.

Documentation currently states that all V2 authority-coherence findings are remediated. That statement must be corrected during the targeted V3 remediation because the pending-delta exception remains.

No historical audit file should be rewritten.

---

# 10. Environment notes

The audit sandbox lacks:

```text
libcst
ruff
```

although both are declared project dependencies/dev dependencies.

Therefore:

- dedicated Phase 10.45 tests were executed with an external import-only `libcst` stub;
- Ruff was not independently rerun here;
- full-domain/global test reproduction is not directly comparable in this extracted, non-installed Python 3.13 sandbox.

These environment limitations are not counted as findings.

The independently reproduced MAJOR above requires neither `libcst` nor Ruff and executes entirely through canonical Domain components.

---

# 11. Closure decision

```text
INDEPENDENT_REAUDIT_V3=FAIL

BLOCKERS=0
MAJORS=1
MINORS=0

V2_MAJOR_01=NOT_REMEDIATED
V2_MAJOR_02=REMEDIATED
V2_MAJOR_03=REMEDIATED

DP-045=NOT_VERIFIED
AT-DP-045=FAIL_INDEPENDENT_ADEQUACY
CLOSURE_ELIGIBLE=NO

PHASE10_45=CANNOT_CLOSE
NEXT=RECORD_REAUDIT_V3_FAIL_AND_TARGETED_REMEDIATION
```

No Phase 10.46 work may begin.

The next remediation should be limited to the authority-binding exception and the strengthened acceptance/tests/docs needed to prove it.
