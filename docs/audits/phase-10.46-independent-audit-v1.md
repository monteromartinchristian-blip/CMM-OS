# CMM OS — Phase 10.46 — Independent Audit V1

**Audit date:** 2026-09-09
**Phase:** 10.46 — Domain Model Policies
**Audit type:** Independent exact-HEAD bundle audit
**Verdict:** **FAIL — remediation required**

## Audited artifact

```text
BUNDLE=phase-10.46-audit-2c0a729d5217b018950109f33407b39687cca2e6.tar.gz
AUDITED_IMPLEMENTATION_HEAD=2c0a729d5217b018950109f33407b39687cca2e6
AUDIT_BUNDLE_SHA256=57710bde267dc5e67f8acac47b5228b47e396bd466bef07e4ab2b49c4a694698
```

Fresh independent verification of the supplied bundle:

```text
GZIP_INTEGRITY=PASS
GIT_ARCHIVE_COMMIT_ID=2c0a729d5217b018950109f33407b39687cca2e6
FILENAME_HEAD_MATCH=PASS
SHA256=57710bde267dc5e67f8acac47b5228b47e396bd466bef07e4ab2b49c4a694698
SHA256_MATCH_REPORTED=PASS
ARCHIVE_ENTRY_COUNT=2128
```

The archive is a valid `git archive`; the embedded commit ID exactly matches the audited implementation HEAD and the filename.

---

# 1. Independent audit result

```text
INDEPENDENT_AUDIT_V1=FAIL

BLOCKERS=0
MAJORS=2
MINORS=0

DP-046=NOT_VERIFIED
AT-DP-046_TEST_EXECUTION=PASS
AT-DP-046=FAIL_INDEPENDENT_ADEQUACY

CLOSURE_ELIGIBLE=NO
```

Phase 10.46 must **not** be closed.

The current bundle is immutable historical evidence. Any remediation requires:

1. scoped remediation only;
2. fresh tests/gates;
3. a new commit;
4. a clean worktree;
5. a new exact-HEAD bundle;
6. a new SHA-256;
7. a new independent re-audit.

---

# 2. Verification performed independently

## 2.1 Required artifact presence

Verified in the exact archive:

```text
docs/superpowers/specs/2026-09-09-phase-10.46-domain-model-policies-design.md
docs/superpowers/plans/2026-09-09-phase-10.46-domain-model-policies-implementation-plan.md

cmm/domains/model_policy_contracts.py
cmm/domains/contracts.py
cmm/domains/__init__.py

cmm/agent_runtime/domain_model_policy_adapter.py
cmm/agent_runtime/model_requirements_resolver.py
cmm/agent_runtime/__init__.py

tests/domains/test_domain_model_policy_contracts.py
tests/domains/test_domain_model_policy_definition_serialization.py
tests/domains/test_domain_model_policy_architecture.py
tests/domains/test_domain_model_policy_dp046_acceptance.py
tests/agent_runtime/test_domain_model_policy_adapter.py
tests/agent_runtime/test_model_requirements_resolver.py

docs/reference/domain-model-policies.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
docs/audits/domain-prompt-clause-coverage.md
ROADMAP.md
```

## 2.2 Dedicated Phase 10.46 execution

The independent audit environment does not contain the unrelated project dependency `libcst`.

An external audit-only import stub was therefore used solely to allow package import. No Phase 10.46 production code uses `libcst`, and the stub was not placed inside or written into the audited archive.

Fresh execution against the extracted exact archive:

```text
PHASE10_46_FOCUSED=105 PASSED
PHASE10_46_ARCHITECTURE_TESTS=20 PASSED
AT_DP_046_TEST_MODULE=6 PASSED
DOMAIN_MODEL_POLICY_ADAPTER_TESTS=14 PASSED
MODEL_REQUIREMENTS_REGRESSIONS=192 PASSED
LLM_SUBSYSTEM=99 PASSED
COMPILEALL=PASS
PHASE10_46_TRAILING_WHITESPACE_SCAN=PASS
```

The green dedicated tests do **not** establish independent acceptance because two tests currently encode or fail to challenge the specification violations documented below.

## 2.3 Wider-suite spot checks

Fresh Agent Runtime execution from the extracted archive:

```text
AGENT_RUNTIME=3453 PASSED, 1 FAILED
```

The single failure is:

```text
tests/agent_runtime/test_observation_engine.py::test_git_observer_real_repo
```

It expects the current working directory to be a live Git worktree. A `git archive` intentionally contains no `.git` directory, so `GitObserver` reports `DEGRADED` rather than `COMPLETED`.

This is an audit-environment artifact and is **not** counted as a Phase 10.46 regression.

The Domain subsystem cannot be fairly reproduced in this audit container because two pre-existing collection paths hit Python-3.13-specific `dataclass`/zero-argument-`super()` behavior in:

```text
tests/domains/test_relationships_domain_remediation.py
tests/domains/test_university_domain_remediation.py
```

These failures are outside Phase 10.46 and are not counted as findings.

The repository-wide Ruff executable is unavailable in this audit container, so the implementation agent's changed-file Ruff result was not independently rerun. This environment limitation is not counted as a Phase 10.46 finding because the independent FAIL below rests on directly reproduced semantic violations in the exact archive.

---

# 3. Architecture/compliance that is correct

The following Phase 10.46 boundaries are correctly implemented in the audited snapshot:

- `DomainModelPolicy` is frozen/slotted and strictly serializable at its own public constructor/deserializer boundary.
- The approved policy field set is present.
- Forbidden concrete-selection fields such as `preferred_models`, `preferred_providers`, `minimum_quality`, and `recommended_budget_eur` are absent.
- Existing production Domain Packs were not retrofitted with model/provider IDs.
- `DomainDefinition.model_policy` is optional and domain-ID coherence is checked.
- Kernel LLM imports no `cmm.domains`.
- Agent Runtime's Phase 10.46 adapter/resolver surfaces import no `cmm.domains`.
- No parallel `ModelRouter`, `ProviderRegistry`, `ModelCatalog`, `FallbackEngine`, or `ModelGateway` was introduced.
- Canonical `ModelRouter`, `ProviderRegistry`, `ModelCatalog`, requirements resolver, fallback contract, and validation contracts are reused.
- Phase 10.47 benchmark/evaluation infrastructure was not started.
- Documentation correctly remains in pre-audit state and contains no premature Phase 10.46 closure claim.
- `AT-DP-046` uses real canonical in-memory model/provider/router components rather than isolated router mocks.

These compliant areas do not outweigh the two major semantic violations below.

---

# 4. MAJOR-01 — A domain policy unintentionally vetoes premium permission

## Severity

```text
MAJOR
```

## Requirement violated

The approved design makes model choice a user/chat/session responsibility and explicitly removes budget/premium preference from the domain.

The spec requires:

- a Domain Pack cannot override user model selection;
- budget preference does not belong to the domain;
- cost/permission/premium restrictions from other layers cannot be widened or silently rewritten by a domain;
- the adapter translates only objective capability/context requirements;
- the reference documentation states that the domain never injects `premium_allowed`.

## Current implementation

`domain_model_requirement_source()` constructs:

```python
ModelRequirements(
    minimum_context_window=...,
    reasoning=...,
    tool_calling=...,
    structured_output=...,
    json_mode=...,
    json_schema=...,
    vision=...,
    audio_input=...,
    audio_output=...,
    embeddings=...,
)
```

`ModelRequirements.premium_allowed` defaults to:

```text
False
```

The canonical resolver computes effective premium permission with:

```python
premium_allowed = all(
    source.requirements.premium_allowed
    for source in ordered_sources
)
```

Therefore the domain source is **not neutral**. Every `DomainModelPolicy` contributes an implicit premium denial.

## Independent reproduction

Exact audited code:

```text
OPERATION_PREMIUM_ALLOWED=True
DOMAIN_SOURCE_PREMIUM_ALLOWED=False
EFFECTIVE_PREMIUM_ALLOWED=False
```

The non-domain operation explicitly allowed premium use.

Adding a model-agnostic Domain policy changed the effective permission to `False`.

That is a real domain-owned veto.

## Test/documentation defect

The new resolver test explicitly codifies the wrong result:

```python
# A domain source never injects premium permission; the canonical
# most-restrictive rule therefore keeps premium disabled.
assert resolved.effective.premium_allowed is False
```

This confuses:

```text
NO DOMAIN OPINION
```

with:

```text
DOMAIN DENIES PREMIUM
```

The reference document simultaneously states:

```text
The domain never injects ... premium_allowed.
```

That statement is semantically false in the current implementation because the domain source injects the canonical default `False`.

## Impact

This violates the user-controlled/model-agnostic boundary.

A domain that should contribute only objective capability/context needs can alter effective premium permission even when another legitimate layer permits premium use.

Although the current Kernel router does not itself filter candidates on `premium_allowed`, the resolved canonical contract is already wrong and is consumed/provenanced as authoritative state. Future or adjacent approval/economic/routing consumers cannot safely treat it as a neutral domain contribution.

## Required remediation

1. Make the domain contribution **neutral** with respect to premium permission.
2. Preserve existing user/session/workflow/operation/economic authority.
3. Do **not** fix this by blindly setting `premium_allowed=True` unless the domain-only case is also proven not to manufacture premium authorization.
4. Because the current boolean cannot represent `NO_OPINION`, use the smallest canonical change that distinguishes:
   - no premium opinion;
   - explicit premium allow;
   - explicit premium deny;
   without creating a parallel resolver.
5. Add regression coverage proving all of:
   - non-domain `premium_allowed=True` + neutral domain policy remains `True`;
   - non-domain `premium_allowed=False` + domain policy remains `False`;
   - a domain-only requirements contribution does not manufacture premium authorization;
   - adding/removing a model-agnostic domain source cannot change premium permission.
6. Correct the reference documentation and acceptance evidence accordingly.

This remediation may require a narrowly scoped spec/plan amendment because the approved code sketch inherited the non-neutral boolean default.

---

# 5. MAJOR-02 — The import-safe structural adapter is not fail-closed

## Severity

```text
MAJOR
```

## Requirement violated

The approved spec requires the Domain → Runtime adapter to:

```text
validate the domain policy
preserve fail-closed semantics
```

The implementation plan likewise requires invalid inputs to fail closed.

The later import-direction remediation correctly avoided any `cmm.agent_runtime -> cmm.domains` import, but the replacement seam still must preserve the strict `DomainModelPolicy` contract.

## Current implementation

The adapter uses:

```python
_POLICY_ATTRIBUTE_SURFACE = (...)
```

and validates only:

```python
if not all(hasattr(policy, name) for name in _POLICY_ATTRIBUTE_SURFACE):
    raise ModelRequirementsResolutionError(...)
```

An object is therefore accepted merely because it exposes matching attribute names.

The adapter does not revalidate:

- canonical `domain_id`;
- strict booleans;
- positive integer context;
- validation booleans;
- fallback-policy type;
- metadata mapping.

The public resolver signature was correspondingly widened to:

```python
domain_policies: Iterable[object] = ()
```

## Independent reproduction

A synthetic object exposing every required attribute but with invalid values was passed directly to the real adapter.

Input characteristics:

```text
domain_id="not-a-domain-id"
require_reasoning="yes"
require_structured_output="sure"
require_context_validation="false"
require_response_validation="false"
fallback_policy="not-a-fallback-policy"
metadata=None
```

Exact results:

```text
REQUIREMENT_SOURCE_ACCEPTED=YES
SOURCE_ID=not-a-domain-id
REASONING_VALUE='yes' str

VALIDATION_ACCEPTED=YES
VALIDATION_REQUIREMENTS=2

FALLBACK_ACCEPTED=YES
FALLBACK_VALUE='not-a-fallback-policy'
```

Because non-empty strings are truthy, the invalid `"false"` strings actually create blocking validation requirements.

The adapter can therefore bypass the strict validation already implemented by `DomainModelPolicy`.

## Existing test gap

Current negative coverage only tests an object that is missing the expected surface:

```python
function("domain:health")
```

and:

```python
resolve_runtime_model_requirements(domain_policies=(object(),))
```

Those tests prove missing attributes are rejected.

They do **not** prove that a structurally complete but semantically invalid object is rejected.

## Impact

The Agent Runtime public seam accepts invalid data that could never be constructed through the canonical Domain contract.

This breaks the spec's fail-closed requirement and weakens the exact contract boundary introduced to preserve import direction.

The import-direction fix itself is valid; the validation strategy is not strict enough.

## Required remediation

Preserve the zero reverse-import invariant, but make the structural seam strict.

At minimum validate, before constructing any canonical requirement:

- `domain_id` is a canonical non-empty `domain:<slug>` identifier representation;
- every required boolean is an actual `bool`;
- `minimum_context_window` is `None` or an integer `> 0`, never `bool`;
- `fallback_policy` is `None` or canonical `ModelFallbackPolicy`;
- `metadata` is a mapping;
- the full expected surface is present.

Possible implementation techniques include an import-safe internal protocol plus runtime validators, or equivalent strict structural validation. Do not import `cmm.domains` into Agent Runtime merely to use `isinstance`.

Add adversarial tests for full-shape invalid objects proving:

```text
domain_model_requirement_source(...) -> REJECT
domain_model_validation_requirements(...) -> REJECT
domain_model_fallback_policy(...) -> REJECT
resolve_runtime_model_requirements(domain_policies=(invalid_full_shape,)) -> REJECT
```

---

# 6. DP-046 assessment

The high-level model-agnostic architecture is visible and much of it is correct.

However, DP-046 cannot be independently verified while:

1. a domain source changes premium authority it is not supposed to own; and
2. the canonical Agent Runtime seam accepts semantically invalid non-domain-policy objects.

Therefore:

```text
DP-046=NOT_VERIFIED
```

---

# 7. AT-DP-046 assessment

Fresh execution:

```text
AT_DP_046_TEST_MODULE=6 PASSED
```

The test uses real canonical components and correctly covers:

- explicit compatible candidate checking;
- explicit incompatible candidate checking;
- AUTO routing through real `ModelRouter`;
- catalog replacement;
- multi-domain capability/context composition;
- validation requirement binding.

However independent adequacy fails because the acceptance suite does not challenge the two major violations above, and adjacent tests actively encode MAJOR-01 as intended behavior.

Therefore:

```text
AT-DP-046_TEST_EXECUTION=PASS
AT-DP-046=FAIL_INDEPENDENT_ADEQUACY
```

After remediation, the connected acceptance should include premium-neutrality and strict adapter-boundary adversaries, or equivalent dedicated regression tests that are included in the re-audit gate.

---

# 8. Documentation review

Pre-audit status discipline is correct:

```text
PHASE10_46=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
DP-046=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION
AT-DP-046=PASS_REPORTED
CLOSURE_ELIGIBLE=NO
```

No premature Phase 10.46 `CLOSED`, `AUDITED`, `DP-046=VERIFIED_EXISTING`, or `CLOSURE_ELIGIBLE=YES` claim was found in the live Phase 10.46 documentation.

One documentation statement must be corrected as part of MAJOR-01 remediation:

```text
The domain never injects ... premium_allowed.
```

The current implementation does inject the semantic default `False`, so that statement is currently inaccurate.

No separate MINOR is counted because this documentation defect is directly coupled to MAJOR-01.

---

# 9. Security / privacy / inherited invariants

No new provider invocation path was found.

No new provider credentials/API-key handling was introduced.

No Domain-specific provider registry/model catalog/router was introduced.

No Kernel → Domains import was found.

No Agent Runtime → Domains import was found on the Phase 10.46 adapter/resolver surfaces.

No concrete model/provider IDs are embedded in current production Domain Packs through Phase 10.46.

The two majors are contract/authority-boundary problems, not evidence of secret leakage or direct provider execution.

---

# 10. Remediation scope

Remediation must be limited to the audit findings.

## Required remediation set

### R1 — Premium neutrality

Correct the canonical composition so a model-agnostic Domain source has no premium allow/deny authority.

Add direct regression tests for true/false/domain-only neutrality.

Update docs/spec/plan only as much as necessary to remove the boolean-neutrality contradiction.

### R2 — Strict import-safe adapter validation

Keep Agent Runtime free of `cmm.domains` imports.

Strengthen the structural adapter to reject semantically invalid full-shape objects.

Add adversarial tests for all three adapter functions and the runtime resolver.

### R3 — Acceptance/gates

Re-run:

```text
focused Phase 10.46 tests
model-requirements regressions
Domain subsystem
Agent Runtime subsystem
Kernel LLM subsystem
global suite
Ruff changed-file gate
format changed-file gate
compileall
git diff --check
import-boundary gates
anti-fragmentation gates
AT-DP-046
```

Documentation must remain:

```text
IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
```

until a new independent re-audit passes.

---

# 11. Required next audit artifact

After remediation:

1. commit only the remediation;
2. leave worktree clean;
3. preserve the quarantine stash;
4. do not push/merge unless explicitly authorized;
5. create a **new** exact-HEAD bundle using `git archive`;
6. calculate a new SHA-256;
7. retain this V1 bundle/report unchanged;
8. submit the new bundle for independent re-audit V2.

---

# 12. Final audit markers

```text
PHASE10_46=IMPLEMENTED_PENDING_REMEDIATION

INDEPENDENT_AUDIT_V1=FAIL

BLOCKERS=0
MAJORS=2
MINORS=0

MAJOR_01=DOMAIN_PREMIUM_PERMISSION_NOT_NEUTRAL
MAJOR_02=STRUCTURAL_ADAPTER_NOT_FAIL_CLOSED

DP-046=NOT_VERIFIED
AT-DP-046_TEST_EXECUTION=PASS
AT-DP-046=FAIL_INDEPENDENT_ADEQUACY

CLOSURE_ELIGIBLE=NO

AUDITED_IMPLEMENTATION_HEAD=2c0a729d5217b018950109f33407b39687cca2e6
AUDIT_BUNDLE_SHA256=57710bde267dc5e67f8acac47b5228b47e396bd466bef07e4ab2b49c4a694698
```
