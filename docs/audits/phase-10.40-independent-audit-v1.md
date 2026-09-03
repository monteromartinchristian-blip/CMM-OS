# CMM OS — Phase 10.40 — Independent Audit V1

## 1. Verdict

```text
PHASE=10.40
AUDIT=INDEPENDENT_AUDIT_V1

AUDITED_HEAD=0ddc61acd4b62b9b10b09dfd52a4fa2cae240d03
AUDIT_BUNDLE_SHA256=b636c956218a5158d23f73e74d1f9cab848807e78cc7a90cf87865fb0ce29cf4

BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
ARCHIVE_HYGIENE=PASS

BLOCKERS=1
MAJORS=1
MINORS=0

DP-040=NOT_VERIFIED
AT-DP-040=FAIL

CLOSURE_ELIGIBLE=NO
AUDIT_RESULT=FAIL
```

Phase 10.40 is not eligible for closure.

The implementation is structurally close to the approved architecture and preserves the principal one-way Domain → Cognitive ownership boundary, but independent adversarial review found:

1. a current-permission bypass at the Domain resource → Cognitive integration boundary; and
2. incomplete preservation of canonical cognitive evidence into Domain presentation references.

Both findings are inside the Phase 10.40 scope and should be remediated narrowly without creating new infrastructure.

---

# 2. Audit target

## Repository phase

```text
Phase 10.40 — Integration with Cognitive Layer
```

## Implementation baseline

```text
9a257eb3e5060ee81b7b1158aef8c4a5a35072ed
```

## Audited implementation HEAD

```text
0ddc61acd4b62b9b10b09dfd52a4fa2cae240d03
```

## Submitted audit bundle

```text
phase-10.40-audit-0ddc61acd4b62b9b10b09dfd52a4fa2cae240d03.tar.gz
```

## Independent SHA-256

```text
b636c956218a5158d23f73e74d1f9cab848807e78cc7a90cf87865fb0ce29cf4
```

## Embedded git-archive HEAD

```text
0ddc61acd4b62b9b10b09dfd52a4fa2cae240d03
```

The independently calculated SHA-256 exactly matches the implementation agent's reported SHA-256.

The `git archive` embedded commit ID exactly matches the claimed implementation HEAD.

---

# 3. Bundle integrity and hygiene

Independent archive inspection:

```text
ENTRIES=2014
UNSAFE_PATHS=0
SYMLINKS_OR_HARDLINKS=0
TRACKED_BYTECODE=0
EXTRACT=PASS
```

No:

```text
absolute archive paths
../ traversal
unexpected links
__pycache__
*.pyc
```

were found.

Required Phase 10.40 evidence was present, including:

```text
docs/superpowers/specs/2026-09-02-phase-10.40-integration-with-cognitive-layer-design.md
docs/superpowers/plans/2026-09-02-phase-10.40-integration-with-cognitive-layer-implementation-plan.md

cmm/domains/cognitive_integration_contracts.py
cmm/domains/cognitive_integration.py

tests/domains/test_domain_cognitive_integration_contracts.py
tests/domains/test_domain_cognitive_integration.py
tests/domains/test_domain_cognitive_integration_boundaries.py
tests/domains/test_domain_cognitive_dp040_acceptance.py

docs/reference/domain-cognitive-integration.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
ROADMAP.md
```

Result:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
ARCHIVE_HYGIENE=PASS
```

---

# 4. Positive architecture findings

Independent AST/static review of the exact audited bytes confirmed:

```text
COGNITIVE_TO_DOMAIN_IMPORTS=0
AGENT_RUNTIME_IMPORTS_IN_PHASE10_40_CORE=0
CROSS_DOMAIN_ENGINE_IMPORTS_IN_PHASE10_40_CORE=0
PARALLEL_COGNITIVE_OWNER_CLASSES=0
COMPILEALL=PASS
```

The Phase 10.40 core classes are limited to the intended integration surface:

```text
DomainCognitiveIntegrator
DefaultDomainCognitiveIntegrator
DomainCognitiveResourceInput
DomainCognitiveIntegrationRequest
DomainCognitiveIntegrationResult
```

No new:

```text
CognitiveEngine
KnowledgeStore
KnowledgeGraph
GapEngine
QuestionEngine
ConfidenceEngine
CognitiveTraceStore
CognitiveSessionStore
```

was introduced in the core integration modules.

This part of DP-040 is well aligned with the approved design.

---

# 5. Positive ownership findings

The audited implementation correctly delegates to canonical owners:

```text
ResourceAdapterRegistry
KnowledgeExtractorRegistry
materialise_result
KnowledgePackageBuilder
CognitiveValidator
DefaultDomainRuleSelector
DefaultDomainRuleExecutor
ReasoningRuleContext
DefaultDomainPresentationPlanner-compatible DomainPresentationItemRef
DomainTraceReferences
```

The implementation does not directly evaluate reasoning rules.

The existing Domain execution path remains responsible for canonical reasoning-rule execution.

The integrator is therefore an orchestrator rather than a second cognitive engine.

---

# 6. Positive trace findings

`DefaultDomainCognitiveIntegrator.integrate(...)` delegates trace-reference construction to:

```text
_build_trace_references(...)
```

The resulting `DomainTraceReferences` carries:

```text
resolution_context_id
resolution_result_id
composition_id
knowledge_package_ids=(package.id,)
```

and does not fabricate:

```text
cognitive_result_ids
reasoning_trace_ids
```

No hidden-reasoning/chain-of-thought field was added by Phase 10.40.

Task 8's reviewed behavior is consistent with the exact audited bytes.

---

# 7. Positive memory/store finding

Static inspection of `cmm/domains/cognitive_integration.py` found no direct canonical store mutator call.

The Phase 10.40 integrator does not define direct persistence logic.

This supports the intended:

```text
read-only KnowledgeStore usage
```

boundary.

---

# 8. Documentation state

The detailed Phase 10 roadmap and requirements matrix correctly keep Phase 10.40 in pre-audit status:

```text
IMPLEMENTED_PENDING_AUDIT
```

The independently audited Domain Intelligence boundary remains through Phase 10.39.

No premature Phase 10.40 closure claim was found in the audited Phase 10.40 documentation.

---

# 9. Agent-reported verification evidence

The implementation agent reported:

```text
FOCUSED=126
PHASE8_REGRESSIONS=697
DOMAIN_REGRESSIONS=992
DOMAIN_SUITE=9042
GLOBAL_SUITE=14597

CHANGED_PYTHON_RUFF=PASS
CHANGED_PYTHON_FORMAT=PASS
GLOBAL_RUFF_DIFFERENTIAL=PASS
NEW_RUFF_DIAGNOSTICS=0
GLOBAL_FORMAT_DIFFERENTIAL=PASS
NEW_FORMAT_DEBT_FILES=0
COMPILEALL=PASS
DIFF_CHECK=PASS
TRACKED_BYTECODE=0

DOMAIN_EVENTS=23/23
DOMAIN_FRAGMENTATION=PASS
PHASE10_40_ADVERSARIAL_MATRIX=18/18 PASS
```

These are implementation-agent claims and are not by themselves independent audit evidence.

The exact archive independently passed `compileall`.

The auditor environment does not contain the repository's full optional runtime toolchain (`libcst` is missing), so a normal full pytest collection from the extracted bundle is not possible in this environment.

Using an auditor-only package-namespace bootstrap to avoid unrelated aggregator imports, the exact bundle produced:

```text
125 passed
1 failed
```

across the four Phase 10.40 focused files.

The single failure occurred while constructing the pre-existing canonical Domain rule catalog under the auditor's Python 3.13 environment and is not classified as a Phase 10.40 product finding.

The independent audit does not rely on that environment failure for its FAIL verdict.

The FAIL verdict instead rests on the exact-byte adversarial reproductions below.

---

# 10. BLOCKER-01 — Binding-required Domain permissions are not enforced against the current integration request

## Severity

```text
BLOCKER
```

## Requirement violated

The approved design requires:

```text
Before a Domain-provided resource/rule/configuration is used,
the canonical Domain permission/trust boundary must already permit
that contribution.
```

It also preserves Phase 10.38 authority invariants.

The approved implementation plan explicitly requires:

```text
Task 10 — H. Permission mismatch

A binding with required permissions absent from effective permissions
is rejected.
```

The final adversarial matrix likewise requires:

```text
Permission mismatch rejected.
```

## Production evidence

`DomainCognitiveResourceInput.__post_init__` validates:

```text
resolution type
binding type
binding membership in resolution.bindings
resolution status
ResourceInput type
source.id == binding.resource_id
source.sensitivity == binding.sensitivity
extractor name
```

but it does not validate the binding's:

```text
binding.permissions
```

against the current request's:

```text
effective_permissions
```

`DomainCognitiveIntegrationRequest.__post_init__` validates that `effective_permissions`
is a unique sequence of non-blank strings, but it does not enforce that every
resource binding's required permissions are contained in it.

`DefaultDomainCognitiveIntegrator.integrate(...)` then passes the request's
`effective_permissions` into adaptation context, but again never verifies:

```text
binding.permissions ⊆ request.effective_permissions
```

The adapted Phase 8 `Resource.permissions` are also left to the adapter payload
and are not a representation/enforcement of the Domain binding permission tuple.

## Independent exact-byte reproduction

An auditor-only adversarial request was built from the committed Phase 10.40
contracts and helpers.

The accepted canonical Domain binding was changed to require:

```text
binding.permissions = ("sensitive.special.read",)
```

The current integration request carried only:

```text
effective_permissions = ("resource:read", "resource:infer")
```

Therefore:

```text
"sensitive.special.read" ∉ effective_permissions
```

Expected:

```text
REJECT / FAIL CLOSED BEFORE ADAPTATION OR REASONING
```

Actual exact audited behavior:

```text
RESULT=ALLOWED

binding_permissions=('sensitive.special.read',)
effective_permissions=('resource:read', 'resource:infer')

adapted_resources=1
extracted_bundles=1

cognitive validation:
knowledge package = accept
resource = accept
materialized items = accept

rule_result.status=no_applicable_rules
```

The mismatched binding is therefore accepted and processed.

## Why the committed Task 10 test does not catch it

The committed test:

```text
test_adversarial_scenario_h_permission_mismatch_fails_closed
```

does not actually create a Domain binding whose required permissions are absent
from the request.

Instead, it replaces the Phase 8 payload `Resource.permissions` so that it lacks
the canonical `INFER` operation, then expects extraction to fail.

That proves:

```text
Phase 8 extraction rejects a Resource that lacks INFER
```

but does not prove:

```text
DomainResourceBinding.permissions must be satisfied by
DomainCognitiveIntegrationRequest.effective_permissions
```

The test name/docstring claims the latter while its mechanics exercise the former.

The implementation agent's reported:

```text
PHASE10_40_ADVERSARIAL_MATRIX=18/18 PASS
```

is therefore not valid evidence for the required permission-mismatch case.

## Security impact

A previously accepted `DomainResourceBinding` can be presented to the
Domain-to-Cognitive integration boundary under a current request that does not
possess the binding-required permission string.

This disconnects:

```text
current effective authorization
```

from:

```text
resource authority accepted by the integration boundary
```

and can permit a Domain contribution to influence canonical cognitive
processing after the current permission context has become insufficient.

This is a Phase 10.38 inherited-authority regression at the new Phase 10.40
handoff.

## Required remediation

Keep the existing architecture.

Do not create a permission registry or a second permission system.

Add a fail-closed check at the Phase 10.40 boundary, preferably where the full
request and resource bindings are simultaneously visible:

```text
for every DomainCognitiveResourceInput in request.resources:
    binding.permissions must be satisfied by request.effective_permissions
```

Use exact canonical permission representation already used by Domain resource
resolution.

Do not silently widen or normalize unrelated permission namespaces.

Add RED tests for at least:

```text
binding requires one permission, request has none        → BLOCK
binding requires two, request has only one               → BLOCK
binding requirements exactly satisfied                   → ALLOW
binding has no required permissions                       → preserve current behavior
```

The negative case must prove:

```text
adapter not called
extractor not called
rule executor not called
```

Strengthen AT-DP-040 so the permission/trust outcome is actually connected to the
integration request instead of being an adjacent independent check.

The AT must demonstrate a denied permission prevents the exact resource binding
from crossing the Phase 10.40 boundary.

---

# 11. MAJOR-01 — Canonical package evidence can disappear from Domain presentation

## Severity

```text
MAJOR
```

## Requirement violated

The approved design states that Domain presentation must preserve:

```text
confidence
uncertainty
warnings
contradictions
provenance
approval state
```

AT-DP-040 additionally requires presentation preservation of:

```text
facts
qualifications
confidence
uncertainty
warnings
contradictions
approvals
provenance/reference integrity
```

The implementation plan requires the real presentation planner test to prove:

```text
questions/warnings/contradictions remain represented
```

and the connected AT plan specifically calls for question/contradiction refs to
remain preserved.

## Production evidence

The Phase 10.40 presentation adapter is:

```python
_presentation_items(
    *,
    request,
    bundles,
    rule_result,
)
```

It has no input for:

```text
KnowledgePackage
CognitiveValidationResult[]
```

It maps:

```text
rule_result.findings
rule_result.gaps
rule_result.contradictions
rule_result.recommendations
rule_result.escalations
extracted QUESTION KnowledgeItems
rule-produced QUESTION KnowledgeItems
```

It does not map:

```text
KnowledgePackage contradictions
KnowledgePackage facts
KnowledgePackage observations
KnowledgePackage inferences
KnowledgePackage hypotheses
KnowledgePackage other knowledge
non-blocking CognitiveValidationResult findings/warnings
```

A contradiction already known by the canonical Knowledge Store therefore remains
present in the `KnowledgePackage` and `ReasoningRuleContext`, but is not
necessarily represented in `DomainPresentationItemRef`.

## Independent exact-byte reproduction

The auditor seeded the official canonical in-memory Knowledge Store with:

```text
integration-provenance-item
other-item
existing-contradiction
```

The integration succeeded.

Exact audited result:

```text
PACKAGE_CONTRADICTIONS=['existing-contradiction']
CONTEXT_CONTRADICTIONS=['existing-contradiction']
PRESENTATION_CONTRADICTION_REFS=[]
ALL_PRESENTATION=[]
```

Therefore canonical contradiction evidence can be present in cognitive context
and disappear completely from the Domain presentation reference set.

## AT-DP-040 coverage gap

The committed AT-DP-040 seeds:

```text
prior-contradiction-040
```

and verifies it remains in:

```text
KnowledgePackage.contradictions
ReasoningRuleContext.contradictions
```

but it does not assert that the prior canonical contradiction appears in the
presentation plan.

Its presentation assertion concentrates on the canonical question and confidence.

The connected AT therefore does not satisfy the planned contradiction
presentation-preservation assertion.

## Impact

A consumer that feeds `result.presentation_items` into the canonical
`DefaultDomainPresentationPlanner` can receive a presentation plan that lacks a
canonical contradiction already known to the Cognitive Layer.

This can make a Domain-facing result appear less uncertain or less conflicted
than the canonical cognitive evidence actually is.

The same structural omission also leaves package-level facts/qualifications and
non-blocking validation warnings outside the Phase 10.40 presentation-reference
adapter.

## Required remediation

Keep `DefaultDomainPresentationPlanner` as the owner.

Do not render content in the integrator and do not create a second presentation system.

Extend the Phase 10.40 evidence-to-reference adapter so the canonical evidence
set required by the spec is available when building `DomainPresentationItemRef`.

At minimum:

```text
package contradictions must be represented
rule-produced contradictions must remain represented
duplicates must be stable-deduped by canonical ID
canonical question refs remain preserved
existing Confidence values must not be rewritten
non-blocking canonical warnings required for presentation must not disappear
```

Where canonical package knowledge is intended to be presented, adapt it through
existing `DomainPresentationItemType` / `DomainPresentationEpistemicKind`
semantics without copying payload content into reference IDs.

Add connected RED tests proving:

```text
pre-existing package contradiction → presentation ref present
rule-result contradiction           → presentation ref present
same contradiction from both paths  → one stable ref
canonical question                   → still present
confidence                           → unchanged
required warning                     → represented
```

Strengthen AT-DP-040 so the real `DefaultDomainPresentationPlanner` plan contains
the pre-existing canonical contradiction seeded for the acceptance scenario.

---

# 12. Audit notes — not counted as findings

## Auditor runtime limitation

A normal extracted-repository pytest run cannot collect because the auditor
environment lacks `libcst`, reached through unrelated package aggregators.

An auditor-only namespace bootstrap allowed 125 of the 126 Phase 10.40 focused
tests to execute.

The remaining AT failure in that environment occurred while constructing the
pre-existing Domain rule catalog under Python 3.13 and is not used as a product
finding.

The independent blockers/majors above were reproduced directly against the
committed Phase 10.40 bytes and do not depend on this limitation.

## Final agent report completeness

The implementation agent's final summary reports all primary PASS/FAIL gate
markers and exact pytest counts, but does not include the requested explicit:

```text
BASELINE_RUFF_DIAGNOSTICS
CURRENT_RUFF_DIAGNOSTICS
BASELINE_FORMAT_DEBT_FILES
CURRENT_FORMAT_DEBT_FILES
IMPLEMENTATION_FILES
```

summary fields.

This is recorded as an audit-process note rather than a product finding because
the implementation transcript shows that the corresponding differential/scope
commands were executed.

A remediation report should include the full requested evidence fields.

---

# 13. Findings summary

```text
BLOCKER-01
Current binding-required Domain permissions are not enforced against
DomainCognitiveIntegrationRequest.effective_permissions.

Independent reproduction:
binding.permissions=("sensitive.special.read",)
effective_permissions=("resource:read","resource:infer")
→ integration ALLOWED
```

```text
MAJOR-01
Canonical KnowledgePackage evidence is not fully preserved into Domain
presentation references.

Independent reproduction:
package/context contains existing-contradiction
→ presentation contradiction refs = []
```

No additional product finding is required to explain the V1 FAIL.

---

# 14. DP-040 assessment

The implementation satisfies several important portions of DP-040:

```text
one-way Domain → Cognitive dependency
no reverse cognitive → Domain import
no new cognitive engine/store/graph
canonical adapter/extractor/materializer reuse
canonical KnowledgePackageBuilder reuse
canonical CognitiveValidator reuse
canonical Domain rule selector/executor reuse
reference-only Domain trace linkage
no direct cognitive memory write
no Agent Runtime dependency in Phase 10.40 core
no CrossDomainEngine ownership
```

However DP-040 also requires permission-safe Domain specialization and faithful
presentation of canonical cognitive evidence.

Because both are violated:

```text
DP-040=NOT_VERIFIED
```

---

# 15. AT-DP-040 assessment

The committed connected AT exercises a substantial real path and is valuable,
but it does not close the two audited defects:

1. its permission branch is not connected to an actual binding-vs-current-
   effective-permissions rejection; and
2. its seeded canonical contradiction is not required to survive into the
   presentation plan.

Therefore:

```text
AT-DP-040=FAIL
```

for independent audit purposes.

The local test may still be green; the independent audit criterion is stronger:
the connected acceptance must prove the mandated behavior.

---

# 16. Required remediation scope

Remediation should remain narrow.

Expected production focus:

```text
cmm/domains/cognitive_integration_contracts.py
cmm/domains/cognitive_integration.py
```

Expected tests:

```text
tests/domains/test_domain_cognitive_integration_contracts.py
tests/domains/test_domain_cognitive_integration.py
tests/domains/test_domain_cognitive_dp040_acceptance.py
```

Potential documentation synchronization after code/test remediation:

```text
docs/reference/domain-cognitive-integration.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
ROADMAP.md
```

Do not modify Phase 8 production owners merely to fix these findings unless a
new RED test proves a generic Phase 8 defect.

Do not modify historical Phase 10.39 audit artifacts.

Do not start Phase 10.41.

---

# 17. V2 remediation acceptance requirements

A future exact-HEAD V2 bundle must independently demonstrate:

## Permission boundary

```text
binding permission absent from current effective permissions → BLOCK
partial permission satisfaction                              → BLOCK
exact satisfaction                                           → ALLOW
no adapter/extractor/rule evaluation after permission block
```

## Presentation preservation

```text
existing canonical package contradiction → Domain presentation reference
rule contradiction                       → Domain presentation reference
duplicate contradiction                  → stable deduped reference
canonical question                       → preserved
canonical confidence                     → unchanged
required warnings                        → represented
```

## Inherited gates

Preserve:

```text
COGNITIVE_TO_DOMAIN_IMPORTS=0
AGENT_RUNTIME_IMPORTS=0
CROSS_DOMAIN_ENGINE_OWNER=NO
all parallel owner gates = 0
DOMAIN_EVENTS=23/23
DOMAIN_FRAGMENTATION=PASS
read-only KnowledgeStore
Phase 8 regressions
Domain regressions
tests/domains
global pytest
Ruff/format differential gates
compileall
git diff --check
tracked bytecode = 0
```

---

# 18. Final independent V1 verdict

```text
PHASE=10.40
AUDIT=INDEPENDENT_AUDIT_V1
AUDITED_HEAD=0ddc61acd4b62b9b10b09dfd52a4fa2cae240d03
AUDIT_BUNDLE_SHA256=b636c956218a5158d23f73e74d1f9cab848807e78cc7a90cf87865fb0ce29cf4

BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
ARCHIVE_HYGIENE=PASS

BLOCKERS=1
MAJORS=1
MINORS=0

DP-040=NOT_VERIFIED
AT-DP-040=FAIL

CLOSURE_ELIGIBLE=NO
AUDIT_RESULT=FAIL

NEXT=RECORD_AUDIT_V1_FAIL_THEN_REMEDIATE_ONLY_FINDINGS
```
