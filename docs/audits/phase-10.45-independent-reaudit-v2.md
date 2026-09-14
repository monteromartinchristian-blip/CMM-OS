# CMM OS — Phase 10.45 — Independent Re-audit V2

**Audit date:** 2026-09-09
**Phase:** 10.45 — Integration with Interfaces
**Audit type:** Independent exact-HEAD re-audit after Audit V1 remediation
**Verdict:** **FAIL — targeted remediation required**

## Audited artifact

```text
BUNDLE=phase-10.45-reaudit-v2-1c651df50ad86d125d3df2ef6c6aa7a2fae30c42.tar.gz
AUDITED_IMPLEMENTATION_HEAD=1c651df50ad86d125d3df2ef6c6aa7a2fae30c42
AUDIT_BUNDLE_SHA256=f096c50262de56d2bdbde4c943a54b303a9009b479c654b02de96f53862d6903
```

The archive is a valid `git archive`. Its embedded Git commit ID matches the filename and the reported remediated HEAD.

---

# 1. Independent Re-audit V2 result

```text
INDEPENDENT_REAUDIT_V2=FAIL

BLOCKERS=0
MAJORS=3
MINORS=0

DP-045=NOT_VERIFIED
AT-DP-045_TEST_EXECUTION=PASS
AT-DP-045=FAIL_INDEPENDENT_ADEQUACY

CLOSURE_ELIGIBLE=NO
```

Phase 10.45 must not be closed.

The V2 bundle is immutable historical evidence. Any correction requires a new commit, a new exact-HEAD bundle, a new SHA-256, and Independent Re-audit V3.

---

# 2. Bundle integrity

Fresh independent verification:

```text
GZIP_INTEGRITY=PASS
GIT_ARCHIVE_COMMIT_ID=1c651df50ad86d125d3df2ef6c6aa7a2fae30c42
FILENAME_HEAD_MATCH=PASS
AUDIT_BUNDLE_SHA256=f096c50262de56d2bdbde4c943a54b303a9009b479c654b02de96f53862d6903
```

Required files are present, including:

```text
docs/audits/phase-10.45-independent-audit-v1.md
docs/audits/phase-10.45-major-03-architectural-block-evidence.md
docs/superpowers/specs/2026-09-09-phase-10.45-major-03-selection-transition-amendment.md
docs/superpowers/plans/2026-09-09-phase-10.45-audit-v1-remediation-plan.md
cmm/domains/interface_integration.py
cmm/domains/interface_integration_contracts.py
cmm/domains/selection_transition.py
cmm/domains/selection_transition_contracts.py
tests/domains/test_domain_interface_dp045_acceptance.py
tests/domains/test_domain_selection_transition.py
```

Audit V1 remains byte-identical to the independently issued V1 report:

```text
AUDIT_V1_SHA256=e0e7e5048524905cedb861a8398b1524c72e6fa503e5cdf0a8617ecf5757bad2
AUDIT_V1_UNMODIFIED=PASS
```

---

# 3. Fresh test execution

The audit sandbox does not have the project dependency `libcst` installed, although the bundle declares `libcst>=1.0` in `pyproject.toml`.

As in Audit V1, an external audit-only `libcst` import stub was placed outside the extracted archive solely so unrelated package imports could complete. No Phase 10.45 implementation file uses `libcst`.

Fresh execution against the exact extracted bundle:

```text
PHASE10_45_DEDICATED_TESTS=197 PASSED
AT_DP_045_TEST=1 PASSED
AT_DP_045_MARKER=PASS
FOCUSED_ORIGINAL_MAJOR_TESTS=8 PASSED
PHASE10_45_COMPILEALL=PASS
```

The audit environment does not contain Ruff, so the agent's reported Ruff/format/global-suite evidence cannot be independently reproduced here. This environmental limitation is not counted as a Phase 10.45 defect.

The V2 FAIL rests on independent behavioral reproductions below.

---

# 4. Audit V1 remediation status

## V1 MAJOR-01 — canonical projection authority binding

The original projection-side finding is materially remediated:

- session composition/resolution/primary/supporting binding is now checked;
- memory/knowledge projection must carry the matching canonical `DomainMemoryKnowledgeProjectionRequest`;
- foreign request/resolution evidence fails closed.

```text
V1_MAJOR_01=REMEDIATED_FOR_ORIGINAL_PROJECTION_PATH
```

A separate authority-binding defect remains in the newly introduced selection-transition command path and is recorded below as V2 MAJOR-01.

## V1 MAJOR-02 — conversational `result_refs`

Remediated.

A bound canonical `CrossDomainResult` is now surfaced reference-only in conversational `result_refs`.

```text
V1_MAJOR_02=REMEDIATED
```

## V1 MAJOR-03 — ADD/WITHDRAW supporting authority

The architectural block was addressed through a design amendment and a new canonical selection-transition coordinator. Successful ADD/WITHDRAW paths now exist and persist revisioned session state through `SharedSessionDomainAdapter`.

However, the new authority violates three approved invariants, so MAJOR-03 cannot yet be considered independently closed.

```text
V1_MAJOR_03=FUNCTIONAL_PATH_IMPLEMENTED_BUT_REMEDIATION_NOT_INDEPENDENTLY_ACCEPTABLE
```

## V1 MAJOR-04 — Review Center unresolved conflicts

Remediated.

A canonical unresolved contradiction with `requires_review=True` is projected reference-only into Review Center.

```text
V1_MAJOR_04=REMEDIATED
```

---

# 5. V2 MAJOR-01 — Selection-transition authority binding is incomplete

## Severity

```text
MAJOR
```

## Approved requirement

The Phase 10.45 MAJOR-03 design amendment requires the supplied:

```text
DomainSessionContext
DomainResolutionResult
DomainComposition
```

to form one coherent authority chain.

The amendment explicitly requires coherence across:

- session id;
- session `composition_id`;
- session `last_resolution_id`;
- primary domain;
- supporting membership;
- composition/resolution identity.

It also requires fail-closed authority-chain mismatch behavior.

## Current implementation

`DefaultDomainSelectionTransitionCoordinator._bind()` checks:

- request ↔ session id;
- request ↔ resolution id;
- session `last_resolution_id` ↔ resolution id;
- request ↔ composition id;
- composition `resolution_id` ↔ resolution id.

It does **not** validate:

```text
session.composition_id == composition.id
session.primary_domain == resolution/composition primary
session.supporting_domains == resolution/composition supporting domains
```

The interface membership-delegation path also does not perform those checks before calling the coordinator.

## Independent reproductions

### A. Misbound composition accepted through the actual interface path

A genuine canonical `DomainSessionContext` was copied with:

```text
session.composition_id=composition:foreign
```

while the supplied resolution/composition remained the valid current authority.

Result:

```text
INTERFACE_MISBOUND_SESSION_RESULT=True ready DOMAIN_SELECTION_REEVALUATED
```

The command was accepted instead of failing closed.

### B. Mismatched supporting membership accepted by coordinator

A genuine canonical session with a supporting set different from the supplied canonical resolution/composition was submitted.

Result:

```text
supporting_domains ACCEPTED_OR_RETURNED accepted
```

### C. Misbound `session.composition_id` accepted directly by coordinator

Result:

```text
composition_id ACCEPTED_OR_RETURNED accepted
```

## Why this matters

The coordinator is the newly amended canonical command authority. A stale or foreign session snapshot can be used as the basis of a persisted membership transition even though it does not describe the supplied composition.

This violates the amendment's explicit authority-coherence requirement and the inherited Phase 10 fail-closed invariant.

## Required remediation

Before any lifecycle, permission, resolution, or persistence work:

1. exact canonical type-check resolution and composition;
2. require canonical allowed statuses;
3. require:
   ```text
   session.composition_id == composition.id
   session.last_resolution_id == resolution.id
   session.primary_domain == str(resolution.primary_domain)
   session.supporting_domains == canonical resolution/composition supporting set
   composition.resolution_id == resolution.id
   ```
4. verify the resolution context is the same contextual authority expected for the supplied resolution where a canonical binding exists;
5. add interface-path and coordinator-path RED tests for all mismatches;
6. verify zero persistence for every mismatch.

---

# 6. V2 MAJOR-02 — Permission evidence is not bound to the membership command and non-ALLOW outcomes can proceed

## Severity

```text
MAJOR
```

## Approved requirement

The design amendment states:

```text
ADD_SUPPORTING always requires a canonical cross-domain permission decision for the target.
ALLOW proceeds.
DENY blocks.
APPROVAL_REQUIRED is pending.
```

Only the target-specific canonical `ALLOW` may reach membership application.

The amendment also prohibits untyped authority payloads.

## Current implementation

### A. Permission request is not bound inside the coordinator

`DomainSelectionTransitionRequest` requires a canonical `CrossDomainPermissionRequest` for ADD, but neither its contract nor the coordinator proves:

```text
permission_request.source_domain == current primary
permission_request.target_domain == request.target_domain
permission_request.session_id == request.session_reference_id
permission decision request_id == permission_request.request_id
```

The interface path performs some source/target checks, but the canonical coordinator itself does not enforce the permission binding promised by its public contract.

### B. Real canonical permission for one domain authorizes another domain

Independent reproduction used the real `DomainPermissionResolver`:

```text
transition target = domain:delta
permission evidence target = domain:beta
permission decision for beta = ALLOW
```

Result:

```text
MISMATCH_PERMISSION_EVIDENCE_RESULT=accepted
```

A target-specific permission for beta was accepted as authority to add delta.

### C. Any outcome other than DENY / APPROVAL_REQUIRED falls through as success

`_check_permission()` handles only:

```text
DENY
APPROVAL_REQUIRED
```

and then returns `None`, which means "continue".

An injected resolver returning a genuine:

```text
CrossDomainPermissionDecision(..., PermissionOutcome.ABSTAIN)
```

produced:

```text
ABSTAIN_RESULT=accepted
```

The current canonical `DomainPermissionResolver.resolve_cross_domain()` normally terminates in DENY / APPROVAL_REQUIRED / ALLOW, but the coordinator contract must still enforce the approved rule that **only ALLOW proceeds**.

### D. Explicit typing contract is violated

The approved amendment says canonical authority payloads must not be typed as `Any` / `object`.

Fresh signature inspection:

```text
DomainSelectionTransitionCoordinator.apply(
    self, request, session, resolution, composition, resolution_context
)
```

has untyped authority parameters.

The implementation constructor declares:

```text
resolver: Any
composer: Any
domain_registry: Any
permission_resolver: Any
session_adapter: Any
```

and `apply()` declares `resolution: Any`, `composition: Any`.

This weakens the canonical boundary and enabled the fail-open collaborator probe above.

## Required remediation

1. bind `permission_request` to the transition request and current session/primary;
2. require the returned object to be an exact canonical `CrossDomainPermissionDecision`;
3. require `decision.request_id == permission_request.request_id`;
4. explicitly branch:
   ```text
   ALLOW -> continue
   DENY -> BLOCKED
   APPROVAL_REQUIRED -> PENDING
   anything else -> fail closed
   ```
5. replace `Any` / untyped public authority surfaces with existing protocols/concrete canonical types:
   - `DomainResolver`;
   - `DomainComposer`;
   - `DomainRegistry`;
   - `DomainPermissionResolver` or a narrow typed canonical protocol;
   - `SharedSessionDomainAdapter`;
   - `DomainResolutionResult`;
   - `DomainComposition`;
   - typed coordinator protocol parameters.
6. add real-resolver adversarial tests where permission target/source/session differ from the command.

---

# 7. V2 MAJOR-03 — Persisted session revision can remain composition-incoherent after membership change

## Severity

```text
MAJOR
```

## Approved requirement

The MAJOR-03 design amendment requires the new session revision to preserve unrelated fields but refresh any **composition-derived field** needed to remain coherent with the new composition, following canonical session-resumer semantics.

It also states that permission intersection is preserved because canonical resolver/composer recompute effective authority.

## Current implementation

`_build_new_session()` uses `dataclasses.replace(session, ...)` and updates only:

```text
revision
updated_at
primary_domain
supporting_domains
domain_versions
composition_id
last_resolution_id
domain_transitions
```

It does not refresh:

```text
effective_profile
effective_rule_ids
effective_permission_refs
active_workflow_refs
available_operation_ids
```

or other composition-derived state.

Those values are inherited blindly from the previous composition.

## Independent reproduction

A genuine `DomainSessionContext` was seeded with beta-specific effective references:

```text
effective_rule_ids=('beta.rule',)
effective_permission_refs=('beta.permission',)
active_workflow_refs=('beta.workflow',)
available_operation_ids=('beta.operation',)
```

Then `WITHDRAW_SUPPORTING(domain:beta)` completed successfully.

Persisted state:

```text
DURABLE_SUPPORTING=('domain:gamma',)
STALE_RULES=('beta.rule',)
STALE_PERMS=('beta.permission',)
STALE_WORKFLOWS=('beta.workflow',)
STALE_OPS=('beta.operation',)
```

The removed domain is no longer part of membership but its composition-derived effective state remains in the canonical session revision.

## Why this matters

The durable session is the state future consumers rely on. Keeping removed-domain rules, permissions, workflows, or operations after recomposition can:

- expose capabilities no longer supplied by the active composition;
- preserve stale permission references;
- mislead interface/domain-session consumers;
- violate the exact coherence the new coordinator was introduced to guarantee.

## Required remediation

1. identify which `DomainSessionContext` fields are composition-derived under existing canonical session-resumer semantics;
2. rebuild those fields from `new_composition` and existing canonical helpers/services;
3. do not invent mappings when a canonical derivation exists;
4. if some effective field requires authority not currently injected, add the minimum canonical typed seam required by the amendment rather than preserving stale values;
5. add connected tests with domain-specific rules/permissions/workflows/operations proving:
   - withdrawn-domain effective refs disappear;
   - added-domain effective refs appear when canonical composition provides them;
   - unrelated session state remains preserved;
6. re-run Phase 10.34 session regressions and all 10.45 tests.

---

# 8. Architecture review

Positive findings:

```text
NO_PARALLEL_SELECTION_STORE=PASS
NO_PARALLEL_SESSION_STORE=PASS
NO_PARALLEL_RESOLVER=PASS
NO_PARALLEL_COMPOSER=PASS
NO_INTERFACE_RUNTIME=PASS
DEPENDENCY_DIRECTION=PASS
```

The coordinator correctly delegates persistence to `SharedSessionDomainAdapter` and does not create a second persistence owner.

The failure is not architectural fragmentation; it is incomplete enforcement/coherence inside the approved canonical coordinator.

---

# 9. Acceptance adequacy

Fresh execution:

```text
AT-DP-045_TEST_EXECUTION=PASS
AT-DP-045_MARKER=PASS
```

Independent adequacy:

```text
AT-DP-045=FAIL_INDEPENDENT_ADEQUACY
```

The connected AT does not currently prove:

- session `composition_id` / primary / supporting coherence on the selector command path;
- target/source/session binding of canonical permission evidence inside the coordinator;
- fail-closed handling of every non-ALLOW permission outcome;
- refresh of composition-derived session state after membership change.

Therefore the AT's successful execution is implementation evidence, not independent verification.

---

# 10. Documentation assessment

The docs correctly remain pre-closure:

```text
PHASE10_45=REMEDIATED_PENDING_INDEPENDENT_REAUDIT
DP_045=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION
AT_DP_045=PASS_REPORTED
CLOSURE_ELIGIBLE=NO
```

No premature Phase 10.45 closure claim was accepted.

However, the reference/roadmap currently overstate the selection-transition remediation as fully coherent and fully remediated. Update them during V2 remediation to reflect the corrected implementation truth before Re-audit V3.

Historical Audit V1 and the MAJOR-03 architectural-block evidence must remain unchanged.

---

# 11. Required targeted remediation

Remediate only these three V2 majors.

## V2 MAJOR-01

```text
- exact coherent session ↔ resolution ↔ composition binding
- fail closed at interface and coordinator
- no persistence on mismatch
```

## V2 MAJOR-02

```text
- permission evidence source/target/session binding
- exact canonical permission decision
- only ALLOW proceeds
- all other outcomes fail closed/pending according to explicit semantics
- remove Any/untyped authority surfaces
```

## V2 MAJOR-03

```text
- refresh composition-derived DomainSessionContext fields
- preserve unrelated session fields
- prove removed-domain refs cannot survive withdrawal
```

Then strengthen `AT-DP-045` with these adversarial branches.

Run fresh:

```text
all Phase 10.45 dedicated tests
selection-transition tests
Phase 10.15 permission regressions
Phase 10.31 selection regressions
Phase 10.34 session regressions
Phase 10.36 API regressions
Phase 10.40–10.44 integration regressions
tests/domains
global suite
Ruff
format
compileall
git diff --check
architecture guards
```

Commit all remediation.

Worktree clean.

Preserve quarantine stash.

Generate a **new** exact-HEAD bundle for Independent Re-audit V3.

Do not overwrite the V1 or V2 bundles.

---

# 12. Closure decision

```text
INDEPENDENT_REAUDIT_V2=FAIL

BLOCKERS=0
MAJORS=3
MINORS=0

DP-045=NOT_VERIFIED
AT-DP-045=FAIL_INDEPENDENT_ADEQUACY
CLOSURE_ELIGIBLE=NO

PHASE10_45=CANNOT_CLOSE
NEXT=RECORD_REAUDIT_V2_FAIL_AND_REMEDIATE
```

No Phase 10.46 work may begin.
