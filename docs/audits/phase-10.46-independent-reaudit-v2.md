# CMM OS — Phase 10.46 — Independent Re-audit V2

**Audit date:** 2026-09-09
**Phase:** 10.46 — Domain Model Policies
**Audit type:** Independent exact-HEAD remediation re-audit
**Verdict:** **PASS**

---

## 1. Audited artifact

```text
BUNDLE=phase-10.46-reaudit-v2-f62069cf935fff5bbac6055e5a63d9b0302993a6.tar.gz
AUDITED_IMPLEMENTATION_HEAD=f62069cf935fff5bbac6055e5a63d9b0302993a6
AUDIT_BUNDLE_SHA256=8a7b57f88880092946038a236d3c802f1ea14e7b06e54150fe34928d11686e0a
```

Fresh independent artifact verification:

```text
GZIP_INTEGRITY=PASS
GIT_ARCHIVE_COMMIT_ID=f62069cf935fff5bbac6055e5a63d9b0302993a6
FILENAME_HEAD_MATCH=PASS
SHA256=8a7b57f88880092946038a236d3c802f1ea14e7b06e54150fe34928d11686e0a
SHA256_MATCH_REPORTED=PASS
ARCHIVE_ENTRY_COUNT=2131
```

The supplied archive is a valid exact-HEAD `git archive`.

---

# 2. Final independent verdict

```text
INDEPENDENT_REAUDIT_V2=PASS

BLOCKERS=0
MAJORS=0
MINORS=0

MAJOR_01=VERIFIED_REMEDIATED
MAJOR_02=VERIFIED_REMEDIATED

DP-046=VERIFIED_EXISTING
AT-DP-046=PASS

CLOSURE_ELIGIBLE=YES
```

Phase 10.46 is eligible for its separate docs-only closure commit.

Phase 10.47 must still not begin until that closure commit is created and the repository is verified clean.

---

# 3. Historical V1 evidence

Independent Audit V1 remains preserved:

```text
INDEPENDENT_AUDIT_V1=FAIL
BLOCKERS=0
MAJORS=2
MINORS=0

MAJOR_01=DOMAIN_PREMIUM_PERMISSION_NOT_NEUTRAL
MAJOR_02=STRUCTURAL_ADAPTER_NOT_FAIL_CLOSED

AUDITED_IMPLEMENTATION_HEAD=2c0a729d5217b018950109f33407b39687cca2e6
AUDIT_BUNDLE_SHA256=57710bde267dc5e67f8acac47b5228b47e396bd466bef07e4ab2b49c4a694698
```

The V2 archive contains:

```text
docs/audits/phase-10.46-independent-audit-v1.md
```

A normalized comparison against the independently generated V1 report produced:

```text
V1_REPORT_SEMANTIC_MATCH=PASS
```

Only the previously required trailing-whitespace cleanup differs.

The V1 bundle was not overwritten.

---

# 4. Remediation scope verification

A clean archive-to-archive comparison between V1 and V2 found exactly:

```text
TOTAL_REMEDIATION_CHANGED_FILES=15
```

Changed production files:

```text
cmm/agent_runtime/model_requirements_contracts.py
cmm/agent_runtime/model_requirements_resolver.py
cmm/agent_runtime/domain_model_policy_adapter.py
```

Changed remediation tests:

```text
tests/agent_runtime/test_model_requirements_contracts.py
tests/agent_runtime/test_model_requirements_resolver.py
tests/agent_runtime/test_domain_model_policy_adapter.py
tests/domains/test_domain_model_policy_architecture.py
tests/domains/test_domain_model_policy_dp046_acceptance.py
```

Changed/added remediation evidence and live documentation:

```text
docs/audits/phase-10.46-independent-audit-v1.md
docs/superpowers/specs/2026-09-09-phase-10.46-remediation-design-amendment-v1.md
docs/superpowers/plans/2026-09-09-phase-10.46-remediation-v1-implementation-plan.md
docs/reference/domain-model-policies.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
ROADMAP.md
```

No Kernel LLM production file changed.

No Domain production file changed during remediation.

No Phase 10.47 or benchmark/evaluation file changed:

```text
PHASE_10_47_REMEDIATION_CHANGES=NONE
```

The remediation scope is consistent with Independent Audit V1 and the approved remediation amendment.

---

# 5. MAJOR-01 — verified remediated

## Finding

V1 showed that a Domain source implicitly contributed:

```text
premium_allowed=False
```

to the canonical restrictive conjunction, so a domain could accidentally veto premium permission owned by another layer.

## Remediation

`ModelRequirementsSource` now contains:

```python
contributes_premium_permission: bool = True
```

The field:

- defaults to `True`;
- is strictly boolean;
- is serialized;
- is deserialized;
- defaults to `True` for old payloads with the field absent;
- is appended to the source contract, preserving prior positional fields.

The Domain adapter explicitly creates:

```python
contributes_premium_permission=False
```

The resolver now calculates premium only over participating sources:

```python
premium_sources = tuple(
    source
    for source in ordered_sources
    if source.contributes_premium_permission
)
```

and fails closed when no source participates:

```python
premium_allowed = (
    all(source.requirements.premium_allowed for source in premium_sources)
    if premium_sources
    else False
)
```

No `source_kind == "domain"` special case exists.

`ModelRequirements.premium_allowed` remains the existing boolean contract.

No Kernel change was introduced.

## Independent semantic reproduction

Fresh direct execution against the exact V2 archive:

```text
ALLOW_PLUS_NEUTRAL_DOMAIN=True
DENY_PLUS_NEUTRAL_DOMAIN=False
NEUTRAL_DOMAIN_ONLY=False
NEUTRALITY_INVARIANT=True
```

Therefore:

```text
PREMIUM_EXISTING_ALLOW_PRESERVED=YES
PREMIUM_EXISTING_DENY_PRESERVED=YES
PREMIUM_DOMAIN_ONLY_FAIL_CLOSED=YES
PREMIUM_NEUTRALITY_INVARIANT=YES
DOMAIN_PREMIUM_SOURCE_PARTICIPATES=NO
```

## Contract regression coverage

Fresh focused execution includes tests proving:

- default participation = `True`;
- explicit `False` round-trips;
- old payload missing the field restores `True`;
- invalid non-bool participation values are rejected;
- neutral Domain source preserves an authoritative allow;
- neutral Domain source preserves an authoritative deny;
- Domain-only remains fail-closed;
- participating deny still wins over participating allow.

## Verdict

```text
MAJOR_01=VERIFIED_REMEDIATED
```

---

# 6. MAJOR-02 — verified remediated

## Finding

V1 showed that the import-safe structural adapter validated only attribute presence. A full-shape object with semantically invalid values could bypass `DomainModelPolicy` validation.

## Remediation

The zero reverse-import invariant remains intact:

```text
cmm.agent_runtime MUST NOT import cmm.domains
```

The adapter now centrally validates the structural surface before every public adapter seam.

It verifies:

### Domain ID

Canonical:

```text
domain:<slug>
```

using the same slug syntax as the existing Domain ID contract:

```text
^[a-z][a-z0-9]*(-[a-z0-9]+)*$
```

### Boolean fields

All eleven approved boolean fields require:

```python
type(value) is bool
```

### Context window

Only:

```text
None
```

or:

```text
type(value) is int and value > 0
```

### Fallback

Only:

```text
None
```

or canonical:

```text
ModelFallbackPolicy
```

### Metadata

Must be a real `Mapping`.

### Surface completeness

All canonical structural attributes must be present.

## Independent adversarial reproduction

A full-shape invalid object containing every expected attribute was passed through the exact production APIs.

It contained invalid values including:

```text
domain_id=not-a-domain-id
require_reasoning=yes
require_context_validation=false
minimum_context_window=0
fallback_policy=not-a-fallback-policy
metadata=None
```

Fresh result:

```text
REQUIREMENT_SOURCE=REJECTED
VALIDATION_REQUIREMENTS=REJECTED
FALLBACK_POLICY=REJECTED
RUNTIME_RESOLUTION=REJECTED
```

The V2 tests additionally exercise:

- malformed Domain IDs;
- string booleans;
- integer boolean surrogates;
- `None` boolean values;
- zero/negative/bool/float/string context windows;
- invalid fallback objects;
- invalid metadata;
- the full runtime resolution seam.

## Verdict

```text
MAJOR_02=VERIFIED_REMEDIATED
```

---

# 7. Independent test execution

The audit container lacks the project's unrelated `libcst` dependency.

An audit-only external import stub was used only to allow package import for Phase 10.46/Agent Runtime tests. It was not written into the audited archive and none of the Phase 10.46 production surfaces use `libcst`.

## Focused remediation suite

Fresh execution:

```text
FOCUSED_REMEDIATION=294 PASSED
```

## Requirements / LLM / validation regressions

Fresh execution:

```text
MODEL_REQUIREMENTS_REGRESSIONS=207 PASSED
```

## AT-DP-046

Fresh execution:

```text
AT_DP_046_MODULE=14 PASSED
```

This includes the original connected acceptance plus premium-neutrality and strict-adapter-boundary remediation scenarios.

## Architecture tests

Fresh execution:

```text
PHASE10_46_ARCHITECTURE=25 PASSED
```

## Kernel LLM subsystem

Fresh execution:

```text
LLM_SUBSYSTEM=99 PASSED
```

## Agent Runtime subsystem

Fresh execution from the exact archive:

```text
3589 PASSED
1 FAILED
```

The sole failure is:

```text
tests/agent_runtime/test_observation_engine.py::test_git_observer_real_repo
```

The test requires the current working directory to contain a live `.git` repository.

An exact `git archive` intentionally contains no `.git` directory, so `GitObserver` returns `DEGRADED`.

This is an audit-container/artifact-form limitation, not a Phase 10.46 regression.

It is the same environment-only failure observed in V1 and is not counted as a finding.

## Domain subsystem / global suite environment note

The normal implementation environment reported:

```text
DOMAIN_SUBSYSTEM=10104 PASSED
GLOBAL_SUITE=15865 PASSED
```

The independent audit container runs Python 3.13 and does not contain real `libcst`.

A full Domain run is therefore not a valid independent comparison in this container:

- two legacy Domain modules encounter Python-3.13-specific zero-argument-`super()`/dataclass behavior at collection;
- broader Domain tests that genuinely use `libcst` cannot be evaluated with an import-only stub.

These environment constraints are not counted as product findings.

They do not undermine the remediation verdict because:

1. V1→V2 changed no Domain production files;
2. the complete Phase 10.46 focused Domain/Agent Runtime acceptance passes independently;
3. Agent Runtime passes 3589 tests independently apart from the archive `.git` environment test;
4. Kernel LLM passes 99/99 independently;
5. both audited semantic failures were reproduced directly and are now independently demonstrated fixed.

---

# 8. Quality and repository-boundary verification

Fresh:

```text
COMPILEALL=PASS
PHASE10_46_TRAILING_WHITESPACE=PASS
WHITESPACE_DIFF_CHECK=PASS
```

The audit container does not provide Ruff, so Ruff could not be independently rerun.

The implementation handoff reports:

```text
RUFF_CHANGED_FILES=PASS
FORMAT_CHANGED_FILES=PASS
```

No remediation-changed file showed whitespace defects during independent diff checks.

Import boundaries were independently verified:

```text
AGENT_RUNTIME_TO_DOMAINS_IMPORT=NO
KERNEL_TO_DOMAINS_IMPORT=NO
SOURCE_KIND_PREMIUM_SPECIAL_CASE=NO
```

Architecture tests independently pass:

```text
25 PASSED
```

No parallel model infrastructure was introduced.

---

# 9. Documentation and traceability

Live documentation before re-audit correctly retained:

```text
PHASE10_46=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
REMEDIATION_V1=IMPLEMENTED_PENDING_REAUDIT
DP-046=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION
AT-DP-046=PASS_REPORTED
AT-DP-046-PREMIUM-NEUTRALITY=PASS_REPORTED
AT-DP-046-STRICT-ADAPTER-BOUNDARY=PASS_REPORTED
CLOSURE_ELIGIBLE=NO
```

Fresh checks found:

```text
PREMATURE_PHASE10_46_MARKERS=NONE
REQUIRED_PREAUDIT_MARKERS=PASS
```

The documentation now correctly describes the premium behavior as source abstention rather than an implicit premium denial.

The V1 failure history remains preserved.

No Phase 10.47 implementation was introduced.

---

# 10. DP-046 verification

The audited implementation now satisfies the design point:

## DP-046 — User-Controlled, Model-Agnostic Domain Policy

Verified properties include:

- Domain policy contains no concrete model IDs.
- Domain policy contains no concrete provider IDs.
- Domain policy does not choose or rank models.
- Domain policy does not construct or invoke providers.
- Domain policy contributes only objective capability/context/validation/fallback declarations.
- Domain premium contribution is neutral and cannot veto user/session/operation premium authority.
- No-authority premium state remains fail-closed.
- Explicit/AUTO ownership boundary remains outside Domains.
- Canonical requirements composition remains the single resolver path.
- Kernel routing infrastructure remains canonical.
- Agent Runtime and Kernel retain zero reverse imports from Domains.
- The import-safe adapter is now semantically fail-closed.
- No parallel router/registry/catalog/fallback/gateway was added.
- Phase 10.47 remains out of scope.

Therefore:

```text
DP-046=VERIFIED_EXISTING
```

---

# 11. AT-DP-046 verification

Fresh exact-archive execution:

```text
AT_DP_046_MODULE=14 PASSED
```

The acceptance remains connected to real canonical infrastructure and now additionally proves both V1 findings.

Independently verified scenarios include:

```text
A explicit compatible model
B explicit incompatible model
C AUTO canonical routing
D catalog replacement
E multi-domain composition
validation bindings
premium neutrality
strict adapter boundary
```

Therefore:

```text
AT-DP-046=PASS
```

---

# 12. Security / privacy / authority review

No remediation code introduced:

- provider invocation;
- credentials/API-key handling;
- subscription inspection;
- Domain-owned model routing;
- Domain-owned provider registry;
- Domain-owned model catalog;
- Domain-owned fallback engine;
- benchmark/evaluation infrastructure;
- concrete model/provider IDs in Domain Packs.

The premium remediation improves authority separation by preventing a non-authoritative Domain source from altering premium permission.

The adapter remediation improves fail-closed behavior at the runtime boundary.

No new security/privacy finding is identified.

---

# 13. Final finding counts

```text
BLOCKERS=0
MAJORS=0
MINORS=0
```

No remediation finding remains open.

---

# 14. Closure eligibility

The minimum closure criteria are now independently satisfied:

```text
BLOCKERS=0
MAJORS=0
DP-046=VERIFIED_EXISTING
AT-DP-046=PASS
CLOSURE_ELIGIBLE=YES
```

Therefore Phase 10.46 is eligible for a separate **docs-only closure commit**.

That commit must:

- update only Phase 10.46 closure/status documentation;
- record this V2 PASS evidence;
- record audited implementation HEAD and bundle SHA-256;
- preserve V1 FAIL history;
- contain no production/test code;
- leave the worktree clean;
- preserve the quarantine stash;
- not push or merge unless explicitly requested.

Phase 10.47 must not begin until the closure commit itself is verified.

---

# 15. Final audit markers

```text
PHASE10_46=REMEDIATED_AND_INDEPENDENTLY_VERIFIED

INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V2=PASS

BLOCKERS=0
MAJORS=0
MINORS=0

MAJOR_01=VERIFIED_REMEDIATED
MAJOR_02=VERIFIED_REMEDIATED

DP-046=VERIFIED_EXISTING
AT-DP-046=PASS

CLOSURE_ELIGIBLE=YES

AUDITED_IMPLEMENTATION_HEAD=f62069cf935fff5bbac6055e5a63d9b0302993a6
AUDIT_BUNDLE_SHA256=8a7b57f88880092946038a236d3c802f1ea14e7b06e54150fe34928d11686e0a
```
