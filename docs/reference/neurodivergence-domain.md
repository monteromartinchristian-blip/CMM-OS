# Neurodivergence Domain (`domain:neurodivergence`)

**Phase:** 10.53 — Neurodivergence Domain
**Status:** implemented; pending independent re-audit (`PHASE10_53=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT`)
**Design point:** `DP-053`
**Connected acceptance:** `AT-DP-053`
**Canonical domain ID:** `domain:neurodivergence`
**Canonical profile:** `NeurodivergenceProfile`
**Default sensitivity:** `SENSITIVE`
**Default privacy orientation:** `LOCAL_ONLY`

---

## 1. Purpose

`domain:neurodivergence` is the fourteenth first-party CMM OS Domain Pack. It
specializes exploration, longitudinal evidence organization and differential
reasoning for neurodevelopmental questions:

- understanding patterns and possible associations;
- exploring why a hypothesis may fit and why it may not;
- comparing plausible and overlapping explanations;
- organizing developmental, assessment and functional evidence;
- preparing structured evidence for a professional assessment;
- preserving the exact certainty/status of every material claim.

The pack is **not** a diagnostic engine. Its central design principle is:

```text
exploratory inference is allowed
diagnostic promotion is not
```

This is a first-class reasoning invariant, not a presentation preference. It is
encoded in `NeurodivergenceProfile`, in the fourteen domain rules, in the
benchmark and quality declarations, and in `AT-DP-053`.

---

## 2. Exploration-friendly semantics

The pack is deliberately **not** an adversarial system that tries to disprove
every possible association.

```text
NEURODIVERGENCE_REASONING=EXPLORATORY_AND_HYPOTHESIS_FRIENDLY
EXPLORATORY_MODEL_INFERENCE=ALLOWED
ASSOCIATION_AND_PATTERN_REASONING=ALLOWED
WORKING_HYPOTHESES=ALLOWED
DIFFERENTIAL_REASONING=BALANCED_NOT_ADVERSARIAL
NEGATIVE_EVIDENCE=PROPORTIONATE_NOT_ROUTINE
DISCLAIMER_SPAM=PROHIBITED_AS_DEFAULT_BEHAVIOR
```

`neurodivergence.differential_explanations` organizes an exploratory request
into what may fit, why it may fit, what remains unclear, what may not fit,
alternative/overlapping explanations and what evidence would clarify the
picture. It never fabricates a negative case for symmetry
(`negative_evidence_required=False`, `fabricated_negative_evidence=False`) and
never replaces reasoning with a disclaimer
(`disclaimer_only_output=False`, `professional_assessment_substituted_reasoning=False`).

Professional assessment may be suggested as a useful source of clarification.
It does not replace reasoning, and a mandatory disclaimer block is not part of
the profile's presentation policy (`require_disclaimers=False`,
`warning_position="after_content"`).

---

## 3. Diagnostic-promotion boundary

The following transitions fail closed:

```text
MODEL_INFERENCE_TO_CONFIRMED_DIAGNOSIS=BLOCKED
SCREENING_TO_CONFIRMED_DIAGNOSIS=BLOCKED
SELF_REPORT_TO_CONFIRMED_DIAGNOSIS=BLOCKED
ISOLATED_TRAIT_TO_CONFIRMED_IDENTITY=BLOCKED
OBSERVATION_AS_CONTEMPORANEOUS=BLOCKED
```

A confirmed clinical status is only ever carried by the shared runtime-only
`ReasoningAuthorityContext`, populated by trusted canonical integration after the
current permission gate has produced `ALLOW`/`APPROVAL_CONSUMED` and the Health
source owner has established definitive semantics. The authoritative clinical
claim is carried as a provenance-bound `AuthoritativeSourceClaim` built from the
canonical `ResourceProvenance` of the Health-owned artifact that established it,
so authority cannot exist in the trusted channel without source provenance
(`TRUSTED_SOURCE_PROVENANCE_BINDING=IMPLEMENTED`;
`AUTHORITATIVE_CLAIM_WITHOUT_CANONICAL_PROVENANCE=BLOCKED`).
`ReasoningRuleContext.metadata` remains JSON-safe and non-authoritative:
canonical-looking transfers, provenance shapes, authoritative-claim shapes,
decision IDs, booleans and Health verdict mappings in caller data have zero
authority effect, and serialized authority cannot be rehydrated into authority
(`AUTHORITY_SERIALIZATION=STRIPPED`; `CALLER_REHYDRATION_OF_AUTHORITY=BLOCKED`;
`METADATA_ONLY_AUTHORITY_FORGERY=BLOCKED`). See the re-audit V3-redo report
`docs/audits/phase-10.53-independent-reaudit-v3-redo.md` (MAJOR-01/MINOR-01) and
the remediation record
`docs/superpowers/plans/2026-09-13-phase-10.53-reaudit-v3-redo-remediation-v1-implementation-plan.md`. `neurodivergence.certainty_state_preservation`
blocks any upward transition (and any exclusion claim) without an applicable
trusted context, and reports `certified_here=False`,
`confirmed_diagnosis_created=False` and `exclusion_created=False`.

---

## 4. Certainty/status semantics

The visible hierarchy is preserved:

```text
CONFIRMED
IN EVALUATION
HYPOTHESIS
NOT CONFIRMED
RULED OUT
INSUFFICIENTLY SUPPORTED
```

Required distinctions:

```text
NOT CONFIRMED != RULED OUT
INSUFFICIENTLY SUPPORTED != RULED OUT
IN EVALUATION != CONFIRMED
HYPOTHESIS != CONFIRMED
```

These labels are **pack-local, derived and non-authoritative**. They are never
persisted as a second truth, never upgrade canonical Phase 8 knowledge, and can
never grant clinical status. The canonical Phase 8 Cognitive Layer remains the
source of truth for knowledge kind, provenance, uncertainty and contradictions.
No second global certainty enum exists.

---

## 5. Canonical inventory

### 5.1 Resources (10)

| Resource ID | Adapter | Notes |
| --- | --- | --- |
| `neurodivergence.developmental_history` | `cognitive.document` | source/observer identity + temporal provenance required |
| `neurodivergence.assessment_records` | `cognitive.record` | assessment context + clinical-status authority preserved |
| `neurodivergence.psychometric_results` | `cognitive.test_result` | instrument identity; screening is not diagnosis |
| `neurodivergence.executive_function_context` | `cognitive.note` | functional only |
| `neurodivergence.sensory_context` | `cognitive.note` | functional only |
| `neurodivergence.academic_function_context` | `cognitive.external_projection` | authorized University-owned projection |
| `neurodivergence.social_function_context` | `cognitive.external_projection` | authorized Relationships-owned projection |
| `neurodivergence.functional_impact` | `cognitive.note` | trait ≠ impairment |
| `neurodivergence.longitudinal_evidence` | `cognitive.timeline` | current vs historical required; no independent timeline store |
| `neurodivergence.differential_overlap_context` | `cognitive.external_projection` | authorized Mental Health-owned projection |

Every resource belongs to `domain:neurodivergence`, defaults to
`SensitivityLevel.SENSITIVE`, uses the canonical temporal policy with
`historical_allowed=True`, and declares provenance requirements instead of
embedding any raw source body.

### 5.2 Rules (14)

```text
neurodivergence.certainty_state_preservation
neurodivergence.clinical_status_authority
neurodivergence.source_authority
neurodivergence.developmental_temporality
neurodivergence.observation_report_separation
neurodivergence.screening_diagnosis_separation
neurodivergence.trait_function_separation
neurodivergence.longitudinal_corroboration
neurodivergence.contradiction_preservation
neurodivergence.differential_explanations
neurodivergence.overlap_reasoning
neurodivergence.purpose_minimized_cross_domain
neurodivergence.global_attribution_guard
neurodivergence.sensitive_label_persistence
```

`neurodivergence.longitudinal_corroboration` treats absent corroboration as a
confidence reduction, never as disproof. `neurodivergence.contradiction_preservation`
blocks a narrowed evidence set that omits known weakening evidence.
`neurodivergence.global_attribution_guard` blocks an unevidenced global causal
claim while never suppressing ordinary exploratory association
(`exploratory_association_suppressed=False`).

### 5.3 Operations (8, declarative)

```text
neurodivergence.build_developmental_timeline
neurodivergence.review_evidence
neurodivergence.compare_assessment_sources
neurodivergence.map_certainty_states
neurodivergence.review_functional_impact
neurodivergence.analyze_differential_overlap
neurodivergence.prepare_assessment_summary
neurodivergence.propose_memory_update
```

All eight are declarative and register as **UNAVAILABLE** unless a real
implementation is explicitly injected through the canonical operation
registry seam. No operation is `DESTRUCTIVE` or `EXTERNAL`;
`propose_memory_update` is proposal-only and carries the proposed certainty
state so a hypothesis can never be proposed as a confirmed state. No operation
runtime exists.

### 5.4 Workflows (8, shared Workflow Engine only)

```text
neurodivergence.developmental_history_review
neurodivergence.evidence_consolidation_review
neurodivergence.diagnostic_status_review
neurodivergence.neuropsychological_assessment_preparation
neurodivergence.assessment_result_integration
neurodivergence.differential_overlap_review
neurodivergence.functional_impact_review
neurodivergence.sensitive_memory_proposal_review
```

Every workflow starts with the canonical `load → profile → reason` dependency
chain and ends in `COMPLETE` via a `VALIDATE` node.
`neurodivergence.diagnostic_status_review` maps certainty and then applies
Health clinical authority (`clinical_status_created=False`).
`neurodivergence.sensitive_memory_proposal_review` stops at a `PROPOSE_MEMORY`
node behind a real `REQUEST_APPROVAL` gate
(`neurodivergence.sensitive_memory_persistence`); it never writes memory
directly. No Neurodivergence workflow engine exists.

---

## 6. Source-domain authority

`domain:health`, `domain:mental-health`, `domain:university` and
`domain:relationships` are independent sibling packs. Neurodivergence inherits
no clinical authority and never becomes the owner of an imported fact.

| Authority | Remains authoritative for |
| --- | --- |
| `domain:health` | documented diagnosis status, medication, treatment, medical tests, medical contraindications, clinical safety, clinical records |
| `domain:mental-health` | therapy continuity, emotional context, therapy-source provenance, emotional interpretations |
| `domain:university` | courses, exams, grades, deadlines, institutional constraints, academic records |
| `domain:relationships` | relationship-specific events and context |

`neurodivergence.source_authority` blocks re-emitting an imported fact as
Neurodivergence-owned (`rewritten_claims`, `source_authority_preserved=False`),
and `neurodivergence.clinical_status_authority` preserves a Health clinical
status while keeping a competing Neurodivergence hypothesis discussable
(`competing_hypothesis_discussable=True`, `competing_hypothesis_promoted=False`,
`neurodivergence_may_override=False`). Medication and treatment changes remain
blocked (`autonomous_medical_action=False`).

The pack declares no implementation dependency on any sibling: `dependencies`
and `optional_dependencies` are empty, and no pack module imports a sibling
package. Cross-domain participation is registry- and permission-driven.

---

## 7. Permissions

The pack reuses the canonical `DomainPermissionPolicy`,
`DomainPermissionResolver` and `DomainPermissionGate`; it never becomes a
permission engine.

| Capability | Default |
| --- | --- |
| `RESOURCE_READ`, `KNOWLEDGE_READ`, `MEMORY_READ` | allowed |
| `OPERATION_EXECUTE`, `WORKFLOW_EXECUTE` | allowed |
| `SENSITIVE_INFERENCE` (infer/reason) | allowed |
| `MEMORY_WRITE` | prohibited; approval required |
| `SENSITIVE_INFERENCE_PERSIST` | prohibited; approval required |
| `EXPORT` | prohibited; approval required |
| `COMMUNICATION_EXTERNAL` | prohibited; approval required |
| `DOMAIN_CROSS_ACCESS` | prohibited; approval required |
| `MEDICAL_DECISION`, `MEDICAL_ACTION` | prohibited |
| `PERMISSION_MODIFY`, `IRREVERSIBLE_CHANGE` | prohibited |
| `MODEL_EXTERNAL`, `SEARCH_EXTERNAL` | prohibited |

Required principles:

```text
permission to infer != permission to persist
permission to read  != permission to transfer
provider availability != permission
technical transfer object != authority
```

`maximum_autonomy_level=0`; neither reversible nor irreversible changes are
allowed autonomously. A local capability-separation map records each stage
(`read`, `infer`, `propose_persistence`, `persist`, `transfer`, `export`,
`communicate`, `external_mutation`) in policy metadata.

---

## 8. Cross-domain admission and approval

A structurally valid `CrossDomainContextTransfer` is **not** permission
authority. The connected path is:

```text
current DomainPermissionResolver
        ↓
DomainPermissionGate
        ↓
effective current authority
        ↓
if APPROVAL_REQUIRED:
    canonical ApprovalService lifecycle
        ↓
APPROVAL_CONSUMED
        ↓
only then admit the exact matching transfer
        ↓
Neurodivergence minimization/reasoning
```

Fail-closed cases proven by `AT-DP-053`:

```text
DENY + matching transfer                        -> not admitted
APPROVAL_REQUIRED + matching transfer, no consumption -> not admitted
consumed approval for resource A + transfer for B     -> B not admitted
approval for actor/session A + actor/session B        -> not admitted
transfer filed under another purpose                  -> not admitted
```

`neurodivergence.purpose_minimized_cross_domain` includes a projected field
only when an accepted canonical transfer exists whose `identifier` equals the
field name. Provenance and source domains derive only from the transfers
backing an included field, so one authorized field can never launder another
and an unrelated transfer grants no authority at all. When the caller supplies
`permission_authority`, only the literal `True` permits inclusion, so a
structural transfer can never substitute for the current permission decision.

No Neurodivergence permission, approval or privacy engine exists.

---

## 9. Privacy

The pack declares a canonical Phase 10.50 `DomainPrivacyPolicy`:

```text
SensitivityLevel.SENSITIVE
PrivacyPolicy.LOCAL_ONLY
allowed_processing_locations = (LOCAL,)
allow_remote = False
allow_export = False
require_approval_for_remote = True
```

Effective privacy is composed through the canonical privacy resolver/evaluator
and can only become stricter. Provider availability cannot weaken the effective
policy. No `allow_cross_domain` privacy shortcut exists.

---

## 10. Memory (proposal-first)

The pack reuses the shared Phase 8 / Phase 10.18 memory system. No independent
memory store, diagnosis registry, knowledge graph or temporal database exists.

```text
READ != PROPOSE != APPROVE != APPLY
```

- Discussing a working hypothesis performs **zero** memory mutation.
- A permitted update is represented as a canonical
  `DomainMemoryProposalSnapshot` (`requires_confirmation=True`,
  `required_capabilities=(PROPOSE,)`) with a content-bound
  `DomainMemoryProposalBinding`.
- A proposal stays a proposal until the canonical approval path completes; it
  preserves hypothesis status and can never propose a promotion to a confirmed
  state.
- Content kinds that assert clinical status (a confirmed diagnosis, a
  psychiatric label, a medication or treatment change, a rewritten source
  authority) can never be proposed at all.
- Validation delegates to `DefaultDomainMemoryIntegrationValidator`, so a
  malformed, unauthorized or since-revoked permission inventory fails closed
  and a stale binding is invalidated.

Existing Health knowledge is never migrated or duplicated into
Neurodivergence.

---

## 11. Knowledge Package

The pack specializes the canonical Phase 8 `KnowledgePackage` through the
Phase 10.49 `DomainKnowledgePackageSchema`
(`knowledge-package-schema:neurodivergence`, `minimum_sensitivity=SENSITIVE`).
The canonical `KnowledgePackageBuilder` remains the sole builder.

Approved sections are mapped onto canonical package sections declared by the
schema, recorded in `NEURODIVERGENCE_KNOWLEDGE_PACKAGE_SECTIONS`:

| Neurodivergence section | Canonical section |
| --- | --- |
| active exploratory objective | `objective` |
| developmental timeline | `timeline` |
| evidence by source and period | `observations` |
| confirmed information | `facts` |
| in-evaluation information | `current_state` |
| working hypotheses | `hypotheses` |
| inferences (model interpretation) | `inferences` |
| contradictory or insufficient evidence | `contradictions` |
| unsupported or thin evidence | `unknowns` |
| evidence that would clarify | `missing_information` |
| functional observations | `other_knowledge` |
| supporting-domain projections | `resources` |
| privacy and permission evidence | `privacy` |

Field policies keep `facts` and `observations` provenance-bound, keep
`hypotheses`/`inferences`/`other_knowledge` uncertainty-preserving with no fact
kind admitted to the hypotheses field, and preserve `contradictions`. No field
is a hard structural requirement beyond the active objective, so the canonical
construction path is never blocked. The package is not a second medical record.

---

## 12. Trace

The pack uses the canonical reference-only Phase 10.17 Domain Trace. References
may cover the profile, rules, evidence/resources, operations/workflows,
permission decisions, approval decisions, privacy decisions, memory proposals
and cognitive trace. Domain-scoped kinds carry the Neurodivergence `domain_id`;
canonical global kinds (a Knowledge Package, a cross-domain result) omit it and
the contract refuses to relabel a global reference as domain-owned.

The trace stores no raw prompt text, no hidden chain of thought, no raw
sensitive source bodies and no copied subordinate trace bodies. No trace store
exists.

---

## 13. Model policy, benchmarks and quality

**Model policy (Phase 10.46).** `build_neurodivergence_model_policy()` declares
objective requirements only — structured reasoning, uncertainty preservation,
source/provenance fidelity, longitudinal comparison, differential comparison,
context and response validation, and a 32k minimum context window. No provider
or model is named, no routing or ranking exists, and user model choice is
preserved.

**Benchmarks (Phase 10.47).** `benchmark-suite:neurodivergence:core` declares
twelve deterministic, provider-independent cases covering exploratory
hypothesis usefulness, diagnostic non-promotion, screening/self-report
non-promotion, developmental chronology, source/observer separation, balanced
differential reasoning, Health authority, cross-domain DENY, unconsumed
approval, consumed approval, sensitive memory and professional assessment
summary fidelity. Nothing executes; no benchmark runtime exists.

**Quality metrics (Phase 10.48).** Ten metrics are declared:

```text
certainty-fidelity              source-authority-fidelity
developmental-temporality       differential-reasoning-quality
exploratory-usefulness          functional-relevance
cross-domain-minimization       privacy-adherence
sensitive-memory-discipline     assessment-summary-fidelity
```

Weights sum to exactly 1. `NEURODIVERGENCE_BLOCKING_QUALITY_FAILURES` names
every failure that must never be merely deducted;
`NEURODIVERGENCE_METRIC_BLOCKING_FAILURES` binds each one to a blocking metric
with a maximum threshold. `exploratory-usefulness` is blocking, and explicitly
lists `refusal_only_response` and `disclaimer_only_response` as failures: under
this pack, refusing to explore is itself a quality failure. No quality runtime
or evaluator exists.

---

## 14. Registration and bootstrap

- `build_neurodivergence_domain_definition()` builds the immutable
  `domain:neurodivergence` definition (`1.0.0`, kind `PERSONAL`) with its six
  reasoning capabilities and every approved additive surface attached.
- `register_neurodivergence_domain(...)` registers the pack **atomically**:
  validate all inputs against every registry, snapshot every registry, mutate,
  and roll back every touched registry on any failure. It creates no registry.
- `build_standard_neurodivergence_domain_bootstrap()` composes the standard
  General bootstrap with the pack and keeps `domain:general` as the resolver
  fallback. Generic requests still resolve to General; an eligible
  Neurodivergence signal resolves to Neurodivergence; an unavailable or
  unauthorized signal fails closed instead of being absorbed by General.
- Importing the package has no side effects: no registration, no persistence,
  no network, and no module-level registry object.

General fallback remains present, and no historical phase-specific bootstrap is
rewritten to pretend Neurodivergence existed earlier.

---

## 15. Current first-party inventory

```text
FIRST_PARTY_DOMAIN_PACKS=14
CURRENT_DEFERRED_DOMAIN_PACKS=0
```

The closed DP-051 historical baseline (twelve pre-10.52 packs, two deferred
packs) remains preserved verbatim as historical evidence. Only live
current-state assertions were updated; historical audit reports, specs and plans
are not rewritten.

---

## 16. Security analysis

| Threat | Control |
| --- | --- |
| Diagnostic promotion (`model inference → clinical fact`) | certainty-state preservation + Health clinical authority |
| Screening/self-report promotion | screening/diagnosis separation + certainty preservation |
| Cross-domain transfer laundering | current `DomainPermissionResolver` + `DomainPermissionGate` + canonical approval consumption before admission |
| Sensitive-label persistence | proposal-first memory + current permission + approval + preserved hypothesis status |
| Source-authority loss | source-domain authority + provenance preservation + no sibling imports |
| Over-attribution (`every difficulty is neurodivergence`) | global-attribution guard + balanced differential reasoning |
| Observation/report collapse | observation/report separation + evidence-class provenance |
| Temporal over-generalization | developmental temporality + retrospective/contemporaneous separation |

The global-attribution guard is anti-over-attribution, not anti-hypothesis: it
never becomes blanket hypothesis suppression.

---

## 17. AT-DP-053 checkpoints

`AT-DP-053` is a connected acceptance over real canonical components, not a set
of isolated mocks. All 29 checkpoints are implemented in
`tests/domains/test_neurodivergence_domain_dp053_acceptance.py`:

```text
 1 canonical registration
 2 profile resolution
 3 exploratory inference allowed (useful applied behavior)
 4 exploratory inference not promoted to diagnosis
 5 certainty hierarchy
 6 screening/self-report non-promotion
 7 developmental chronology
 8 observer/source separation
 9 balanced differential reasoning
10 Health authority
11 DENY + matching transfer blocked
12 APPROVAL_REQUIRED without consumption blocked
13 canonical approval -> APPROVAL_CONSUMED -> exact transfer admitted
14 authority tuple binding (resource/actor/session/purpose)
15 Mental Health source authority
16 University source authority
17 Relationships source authority
18 cross-domain minimization / no laundering
19 canonical SENSITIVE privacy
20 proposal-first working-hypothesis memory
21 canonical KnowledgePackageBuilder path
22 presentation + canonical trace validation
23 operation/workflow registry reachability
24 benchmark/quality declarations
25 anti-fragmentation
26 first-party inventory 14 / deferred 0
27 prior-domain regressions/authority preserved
```

For the permission checkpoints the matching transfer is always physically
present, so a DENY cannot pass by omitting evidence. For the exploration
checkpoints the result must carry applied, hypothesis-bearing content rather
than merely "not blocked".

---

## 18. Explicit non-goals

Phase 10.53 does not implement autonomous diagnosis, autonomous medical advice,
medication adjustment, treatment modification, medical-contraindication
authority, autonomous external clinical communication, a second medical record,
a diagnosis registry, a Neurodivergence-specific memory store, knowledge graph,
cognitive layer, planner, runtime, workflow engine, permission engine, privacy
engine or approval engine, silent migration of Health knowledge, silent
persistence of a model-generated label, or any Phase 11 UI/platform behavior.

---

## 19. Verification

| Check | Command |
| --- | --- |
| Focused Phase 10.53 suite | `.venv/bin/python -m pytest -ra tests/domains/test_neurodivergence_domain_*.py` |
| Architecture + AT gate | `.venv/bin/python -m pytest -ra tests/domains/test_neurodivergence_domain_architecture.py tests/domains/test_neurodivergence_domain_dp053_acceptance.py` |
| Domain subsystem | `.venv/bin/python -m pytest -ra tests/domains` |
| Global suite | `.venv/bin/python -m pytest -ra` |
| Static | `.venv/bin/python -m ruff check .`; `.venv/bin/python -m ruff format --check .`; `.venv/bin/python -m compileall -q cmm cmm_agent kernel tests` |

The phase remains `IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT` until an independent
re-audit passes. Implementation self-review does not certify it.
