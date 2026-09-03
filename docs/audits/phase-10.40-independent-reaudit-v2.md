# CMM OS — Phase 10.40 — Independent Re-Audit V2

## 1. Verdict

```text
PHASE=10.40
AUDIT=INDEPENDENT_REAUDIT_V2

AUDITED_HEAD=81674e7f96b09a79031ad2e6eefeb6720074edda
AUDIT_BUNDLE_SHA256=6b3cdb30bc73a87832895bae9e43c2faa62abc3eac9158207f35c017b75b5a1f

BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
ARCHIVE_HYGIENE=PASS

V1_BLOCKER_01=CLOSED
V1_MAJOR_01=PARTIALLY_REMEDIATED

BLOCKERS=0
MAJORS=1
MINORS=0

DP-040=NOT_VERIFIED
AT-DP-040=FAIL

CLOSURE_ELIGIBLE=NO
AUDIT_RESULT=FAIL
```

Phase 10.40 is not yet eligible for closure.

The V2 remediation successfully closes the V1 permission blocker and fixes the
specific contradiction / warning / question presentation losses exercised by
the V2 remediation matrix.

However, the V1 presentation-preservation finding remains partially open:
canonical non-question knowledge — including canonical facts explicitly required
by the approved specification — can still disappear between the canonical
Knowledge Package / rule result and Domain presentation references.

The remaining remediation is narrow and remains entirely within Phase 10.40.

---

# 2. Audit target

```text
Phase 10.40 — Integration with Cognitive Layer
```

Remediation base:

```text
c38752a2d9a2f1be79c1b7e3a871e8823b0d806e
```

V1 audited implementation HEAD:

```text
0ddc61acd4b62b9b10b09dfd52a4fa2cae240d03
```

V1 bundle SHA-256:

```text
b636c956218a5158d23f73e74d1f9cab848807e78cc7a90cf87865fb0ce29cf4
```

V2 audited implementation HEAD:

```text
81674e7f96b09a79031ad2e6eefeb6720074edda
```

Submitted V2 bundle:

```text
phase-10.40-audit-v2-81674e7f96b09a79031ad2e6eefeb6720074edda.tar.gz
```

Independent V2 SHA-256:

```text
6b3cdb30bc73a87832895bae9e43c2faa62abc3eac9158207f35c017b75b5a1f
```

Embedded git-archive commit:

```text
81674e7f96b09a79031ad2e6eefeb6720074edda
```

The independently calculated SHA-256 exactly matches the submitted V2 report.

The PAX `comment` field in the exact archive identifies the exact claimed
remediation HEAD.

---

# 3. Archive integrity and hygiene

Independent inspection of the submitted archive:

```text
ENTRIES=2016
UNSAFE_PATHS=0
SYMLINKS_OR_HARDLINKS=0
TRACKED_BYTECODE=0
EXTRACT=PASS
```

No:

```text
absolute paths
../ traversal
unexpected symbolic/hard links
__pycache__
*.pyc
```

were found in the submitted archive.

Required Phase 10.40 evidence is present, including:

```text
docs/superpowers/specs/2026-09-02-phase-10.40-integration-with-cognitive-layer-design.md
docs/superpowers/plans/2026-09-02-phase-10.40-integration-with-cognitive-layer-implementation-plan.md
docs/audits/phase-10.40-independent-audit-v1.md

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

# 4. Independent architecture verification

AST/static inspection of the exact V2 archive confirms:

```text
COGNITIVE_TO_DOMAIN_IMPORTS=0
AGENT_RUNTIME_IMPORTS_IN_PHASE10_40_CORE=0
CROSS_DOMAIN_ENGINE_IMPORTS_IN_PHASE10_40_CORE=0
PARALLEL_COGNITIVE_OWNER_CLASSES=0
DIRECT_KNOWLEDGE_STORE_MUTATOR_CALLS_IN_INTEGRATOR=0
DOMAIN_EVENTS=23/23
COMPILEALL=PASS
```

The Phase 10.40 core remains limited to the approved integration surface.

No new:

```text
DomainCognitiveEngine
DomainKnowledgeStore
DomainKnowledgeGraph
DomainGapEngine
DomainQuestionEngine
DomainConfidenceEngine
DomainContradictionEngine
DomainTemporalEngine
DomainCognitiveTraceStore
DomainCognitiveSessionStore
```

was introduced.

The Phase 10.39 fragmentation boundary remains structurally preserved.

This part of DP-040 remains sound.

---

# 5. V1 BLOCKER-01 — CLOSED

## V1 finding

The V1 audit proved that:

```text
binding.permissions=("sensitive.special.read",)

request.effective_permissions=(
    "resource:read",
    "resource:infer",
)
```

could still cross into canonical adaptation/extraction/reasoning.

## V2 production fix

`DefaultDomainCognitiveIntegrator.integrate(...)` now performs the permission
check immediately after request type validation and before:

```text
timestamp acquisition
resource adaptation
knowledge extraction
KnowledgePackage construction
cognitive validation
rule selection
rule execution
```

The exact V2 code computes missing permissions from:

```text
resource_input.binding.permissions
```

against:

```text
request.effective_permissions
```

and raises:

```text
DomainCognitiveIntegrationBlockedError
```

when any binding-required permission is absent.

No new permission registry/resolver/system was introduced.

## Independent V2 matrix execution

The auditor executed directly from the exact archive:

```text
test_perm_1_one_required_permission_request_has_none_blocks
test_perm_2_two_required_permissions_request_has_one_blocks
test_perm_3_exact_satisfaction_allows
test_perm_4_request_has_superset_allows
test_perm_5_binding_requires_no_permissions_allows
test_perm_6_blocked_path_calls_no_adapter_or_extractor
test_perm_7_blocked_path_evaluates_no_rules
test_adversarial_scenario_h_permission_mismatch_fails_closed
```

Result:

```text
V2_PERMISSION_MATRIX=7/7 PASS
SCENARIO_H=PASS
```

The negative path is now fail-closed before cognitive use.

Therefore:

```text
V1_BLOCKER_01=CLOSED
```

---

# 6. V1 MAJOR-01 — contradiction / warning / question subcases remediated

The V2 implementation extends `_presentation_items(...)` with:

```text
package
validation_results
```

and now maps:

```text
KnowledgePackage.contradictions
rule-result contradictions
non-blocking cognitive validation warnings
canonical QUESTION KnowledgeItems
```

into `DomainPresentationItemRef`.

Contradictions are deduplicated by canonical:

```text
Contradiction.id
```

and canonical QUESTION confidence is preserved.

## Independent V2 PRES matrix execution

The auditor executed directly from the exact archive:

```text
PRES-1 package contradiction preserved
PRES-2 rule-result contradiction preserved
PRES-3 duplicate contradiction deduplicated by canonical ID
PRES-4 canonical QUESTION preserved
PRES-5 canonical Confidence unchanged
PRES-6 non-blocking validation warning represented
PRES-7 real DefaultDomainPresentationPlanner preserves references
```

Result:

```text
V2_PRESENTATION_MATRIX=7/7 PASS
```

The strengthened AT also explicitly requires the seeded:

```text
prior-contradiction-040
```

to survive into:

```text
result.presentation_items
DefaultDomainPresentationPlanner.plan(...)
contradictions presentation section
```

These portions of V1 MAJOR-01 are remediated.

---

# 7. RESIDUAL MAJOR-01 — canonical facts still disappear from presentation

## Severity

```text
MAJOR
```

## Requirement

The approved design specification, AT-DP-040 mandatory assertion J, requires:

```text
Domain presentation may reorder/format permitted output but must preserve:

- facts;
- qualifications;
- confidence;
- uncertainty;
- warnings;
- contradictions;
- approvals;
- provenance/reference integrity.
```

The specification is authoritative over the implementation plan where the plan
contains a narrower example mapping.

## Exact V2 production behavior

The V2 `_presentation_items(...)` implementation maps:

```text
rule_result.findings
rule_result.gaps
package + rule contradictions
rule_result.recommendations
rule_result.escalations
validation warnings
QUESTION KnowledgeItems from package/bundles/rule-produced knowledge
```

For `KnowledgePackage` epistemic categories:

```text
facts
observations
inferences
hypotheses
other_knowledge
```

the implementation calls:

```text
add_question(knowledge_item)
```

which intentionally returns immediately unless:

```text
knowledge_item.kind is KnowledgeKind.QUESTION
```

Likewise, for:

```text
rule_result.produced_knowledge
```

the implementation calls only `add_question(...)`.

Therefore canonical non-question `KnowledgeItem` evidence has no presentation
reference path.

## Independent exact-byte reproduction

Using the exact V2 `_presentation_items(...)` implementation and canonical
Phase 8 `KnowledgeItem`, `KnowledgePackage`, `KnowledgeKind`, and `Confidence`
contracts, the auditor constructed:

```text
KnowledgePackage.facts =
    ["pkg-fact-residual"]

rule_result.produced_knowledge =
    ["rule-fact-residual"]
```

Both are canonical:

```text
KnowledgeKind.FACT
```

with canonical confidence values.

Exact V2 output:

```text
PACKAGE_FACT_PRESENT=False
RULE_FACT_PRESENT=False
ITEMS=[]
```

The facts remain canonical cognitive evidence but disappear entirely from the
Domain presentation-reference set.

## Connected AT-DP-040 coverage gap

The strengthened connected AT seeds:

```text
prior-fact-040
prior-fact-040-alt
prior-contradiction-040
```

It correctly proves:

```text
prior-fact-040 survives into ReasoningRuleContext
prior-fact-040 Confidence remains 0.61
prior-contradiction-040 survives into presentation
canonical QUESTION survives into presentation
```

But it does **not** assert:

```text
prior-fact-040 survives into result.presentation_items
```

or:

```text
prior-fact-040 survives into DefaultDomainPresentationPlanner plan
```

The existing AT therefore still does not prove the specification's explicit
facts-preservation requirement.

## Why this remains part of V1 MAJOR-01

The V1 independent report explicitly recorded that the presentation adapter's
structural omission also leaves canonical package facts/qualifications outside
the Phase 10.40 presentation-reference path.

Its remediation requirement stated that, where canonical package knowledge is
intended to be presented, the implementation must adapt it through existing
presentation contracts without inventing new infrastructure.

V2 fixed contradictions/warnings/questions but did not close this remaining
canonical-knowledge branch.

Therefore:

```text
V1_MAJOR_01=PARTIALLY_REMEDIATED
RESIDUAL_MAJOR_01=OPEN
```

---

# 8. Required narrow remediation for V3

Do not redesign Phase 10.40.

Do not modify Phase 8 ownership.

Do not add a presentation engine.

The remaining fix belongs in the existing Phase 10.40 evidence-to-reference
adapter.

## Required behavior

Canonical presentable `KnowledgeItem` evidence must not be silently dropped
because its kind is not QUESTION.

At minimum add permanent RED/GREEN coverage for:

```text
package FACT
rule-produced FACT
```

and preserve:

```text
KnowledgeItem.id
KnowledgeItem.confidence
provenance requirement
stable deterministic ordering
```

Use existing presentation contracts.

The repository already exposes:

```text
DomainPresentationItemType.FINDING
DomainPresentationEpistemicKind.FACT
DomainPresentationEpistemicKind.INFERENCE
DomainPresentationEpistemicKind.HYPOTHESIS
```

Do not add a new item type or epistemic enum unless an actual generic contract
defect is independently proven.

For canonical kinds without an exact epistemic enum, preserve the evidence using
the closest existing canonical presentation semantics without fabricating a
new cognitive meaning.

## Deduplication

If the same canonical `KnowledgeItem.id` is visible through:

```text
KnowledgePackage
extracted bundle
rule_result.produced_knowledge
```

emit one stable presentation reference.

Do not deduplicate by statement text.

## AT-DP-040

Strengthen the connected AT so:

```text
prior-fact-040
```

must appear in:

```text
result.presentation_items
DefaultDomainPresentationPlanner plan
```

with:

```text
canonical ref ID
FACT epistemic kind where applicable
confidence == 0.61
requires_provenance=True
```

The existing contradiction/question assertions must remain green.

---

# 9. Documentation status

The exact V2 bundle correctly retains Phase 10.40 as:

```text
IMPLEMENTED_PENDING_AUDIT
```

The independently audited baseline remains through Phase 10.39.

No premature Phase 10.40 closure claim was found.

The requirements matrix contains structured:

```text
DP-040
AT-DP-040
```

entries.

The documentation state is suitable for a failed re-audit and does not need a
closure rollback.

---

# 10. Agent-reported gates

The remediation report states:

```text
V2_PERMISSION_MATRIX=7/7 PASS
V2_PRESENTATION_MATRIX=7/7 PASS
FOCUSED=140 passed
PHASE8_REGRESSIONS=697 passed
DOMAIN_REGRESSIONS=992 passed
GLOBAL_SUITE=14611 passed
changed-file Ruff/format=PASS
NEW_RUFF_DIAGNOSTICS=0
NEW_FORMAT_DEBT_FILES=0
DOMAIN_EVENTS=23/23
```

The independent audit does not treat these implementation-agent statements as
sufficient evidence by themselves.

Independent exact-archive checks did confirm:

```text
V2 permission matrix = 7/7 PASS
Scenario H = PASS
V2 presentation matrix = 7/7 PASS
compileall = PASS
reverse dependency = 0
Agent Runtime core imports = 0
CrossDomain core imports = 0
direct store mutator calls = 0
Domain Events = 23/23
archive bytecode = 0
```

The FAIL verdict rests on the separately reproduced canonical-fact presentation
loss.

---

# 11. Auditor environment note

The auditor environment does not include the repository's complete optional
runtime toolchain (`libcst` is unavailable), so a normal aggregate repository
pytest import path is not used as independent evidence.

For focused remediation verification, the auditor loaded the exact extracted
Phase 8/Phase 10 modules with an auditor-only namespace bootstrap that bypasses
unrelated aggregate package imports and then directly executed the committed V2
permission and PRES test functions.

This bootstrap does not alter the audited source bytes and is not used to hide
the residual finding.

`compileall` was run directly against the exact extracted archive and passed.

---

# 12. Findings summary

```text
V1_BLOCKER_01=CLOSED
```

The binding-required permission is now enforced against current effective
permissions before resource adaptation.

```text
V1_MAJOR_01=PARTIALLY_REMEDIATED
```

Contradictions, canonical questions, confidence for questions, and non-blocking
validation warnings are now preserved.

Residual:

```text
MAJOR-01-R1
Canonical non-question KnowledgeItem evidence, including FACT values explicitly
required by the specification, can still disappear from Domain presentation
references.
```

Independent reproduction:

```text
PACKAGE_FACT_PRESENT=False
RULE_FACT_PRESENT=False
ITEMS=[]
```

---

# 13. DP-040 assessment

DP-040's ownership and architectural boundary are substantially preserved:

```text
one-way Domain → Cognitive integration
no reverse cognitive → Domain dependency
no Agent Runtime core dependency
no CrossDomainEngine ownership
no parallel cognitive engine/store/graph
canonical adapters/extractors/materializer reused
canonical KnowledgePackageBuilder reused
canonical CognitiveValidator reused
canonical Domain rule selector/executor reused
read-only KnowledgeStore boundary preserved
reference-only Domain trace preserved
```

However Phase 10.40's approved acceptance contract includes faithful
presentation preservation of canonical cognitive evidence.

Because canonical facts can still be dropped:

```text
DP-040=NOT_VERIFIED
```

---

# 14. AT-DP-040 assessment

The connected AT is materially stronger in V2 and now correctly proves:

```text
binding permission rejection/allow path
pre-existing contradiction → presentation
canonical question → presentation
confidence preservation
canonical validation
store immutability
trace reference behavior
architecture boundaries
```

It still does not prove the explicit facts-preservation assertion from the
approved spec despite seeding canonical facts.

Therefore:

```text
AT-DP-040=FAIL
```

for independent audit purposes.

---

# 15. V3 re-audit acceptance requirements

The next exact-HEAD remediation bundle must preserve all V2 fixes and add:

```text
FACT-1 package canonical FACT → presentation reference
FACT-2 rule-produced canonical FACT → presentation reference
FACT-3 duplicate KnowledgeItem ID across package/rule/bundle → one stable ref
FACT-4 confidence preserved exactly
FACT-5 provenance requirement preserved
FACT-6 real DefaultDomainPresentationPlanner preserves FACT ref
FACT-7 connected AT prior-fact-040 survives to presentation plan
```

Recommended:

```text
V3_FACT_PRESENTATION_MATRIX=7/7 PASS
```

Also re-run:

```text
V2_PERMISSION_MATRIX=7/7 PASS
V2_PRESENTATION_MATRIX=7/7 PASS
PHASE10_40_ADVERSARIAL_MATRIX=18/18 PASS
AT-DP-040 local PASS
Phase 8 regressions
Domain regressions
tests/domains
global pytest
Ruff/format differential gates
compileall
git diff --check
architecture gates
Domain Events 23/23
Phase 10.39 fragmentation acceptance
tracked bytecode 0
```

Any V3 bundle must be created from the new committed exact HEAD with a new
filename and SHA-256.

Do not mutate the V2 bundle.

---

# 16. Final independent V2 verdict

```text
PHASE=10.40
AUDIT=INDEPENDENT_REAUDIT_V2

AUDITED_HEAD=81674e7f96b09a79031ad2e6eefeb6720074edda
AUDIT_BUNDLE_SHA256=6b3cdb30bc73a87832895bae9e43c2faa62abc3eac9158207f35c017b75b5a1f

BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
ARCHIVE_HYGIENE=PASS

V1_BLOCKER_01=CLOSED
V1_MAJOR_01=PARTIALLY_REMEDIATED

BLOCKERS=0
MAJORS=1
MINORS=0

DP-040=NOT_VERIFIED
AT-DP-040=FAIL

CLOSURE_ELIGIBLE=NO
AUDIT_RESULT=FAIL

NEXT=RECORD_AUDIT_V2_FAIL_THEN_REMEDIATE_RESIDUAL_MAJOR_01_ONLY
```
