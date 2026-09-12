# Mental Health Domain (`domain:mental-health`)

**Phase:** 10.52
**Status:** `PHASE10_52=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT` — independent
audit remains pending
**Canonical identity:** `domain:mental-health` · namespace `mental_health.*` · version `1.0.0`
**Canonical profile:** `MentalHealthProfile`
**Design:** `docs/superpowers/specs/2026-09-11-phase-10.52-mental-health-domain-design.md`
**Plan:** `docs/superpowers/plans/2026-09-12-phase-10.52-mental-health-domain-implementation-plan.md`
**Acceptance:** `DP-052` / `AT-DP-052`
**Kind:** `DomainKind.PERSONAL` · manifest `manifest:mental-health:1.0.0`

> Pre-audit status only. This document reports implementation and
> self-reported test results. It does **not** claim independent audit PASS and
> does not close the phase.

---

## 1. Purpose

Mental Health is CMM OS's first post-core specialized Domain Pack. It
specializes the already-closed Domain Intelligence substrate for ordinary
emotional conversation and support, therapy continuity, pre- and post-therapy
review, therapy-transcript analysis, longitudinal emotional context and
emotionally relevant decision support.

It is not a new subsystem: it reuses the shared Kernel, Cognitive Layer,
Knowledge Model/Store/Graph, Agent Runtime, Planner, Workflow System,
Operation Contracts, Validation System, Memory Contracts, Domain Registry,
Domain Resolver, Domain Composition, Domain Trace, Domain Memory Integration,
Domain Privacy System, Domain Model Policy System, Benchmark Contracts,
Quality Metric Contracts and Knowledge Package infrastructure.

Semantic posture:

```text
MENTAL_HEALTH_SPECIALIZES
CANONICAL_INFRASTRUCTURE_OWNS
MOST_RESTRICTIVE_AUTHORITY_WINS
SENSITIVE_CONTEXT_IS_MINIMIZED
CLINICAL_AUTHORITY_STAYS_WITH_HEALTH
PERSISTENCE_IS_NEVER_IMPLICIT
PHASE10_53_REMAINS_DEFERRED
```

## 2. Package boundary

Exactly nineteen production modules — no parallel registry, loader, resolver,
composer, runtime, engine, store, planner, permission engine, privacy engine,
safety engine, crisis engine, trace store, validation engine or
therapy-history store:

```text
cmm/domains/mental_health/
├── __init__.py            # public surface, definitions only, no import side effects
├── benchmarks.py          # declarative Phase 10.47 benchmark suite
├── bootstrap.py           # MentalHealthDomainBootstrap (General + Mental Health)
├── catalog.py             # single source of truth for canonical members
├── definition.py          # immutable DomainDefinition
├── integration.py         # atomic validation-first registration + rollback
├── knowledge_package.py   # Phase 10.49 schema narrowing
├── memory.py              # proposal-first shared memory contracts
├── model_policy.py        # Phase 10.46 provider/model-agnostic requirements
├── operations.py          # 8 declarative operations (unavailable by default)
├── permissions.py         # fail-closed restrictive policy
├── presentation.py        # non-pathologizing presentation policy
├── privacy.py             # canonical SENSITIVE privacy declaration
├── profile.py             # MentalHealthProfile
├── quality_metrics.py     # Phase 10.48 blocking quality policy
├── resources.py           # 10 resource definitions over shared adapters
├── rules.py               # deterministic helpers + 13 reasoning rules
├── trace.py               # reference-only Phase 10.17 trace composition
└── workflows.py           # 8 workflows on the shared Workflow Engine
```

Importing `cmm.domains.mental_health` has zero registration side effects: a
fresh import registers nothing globally, opens no storage and touches no
network.

## 3. Resources

Ten resource families, all `SensitivityLevel.SENSITIVE`:
`conversation`, `therapy_session_note`, `therapy_transcript`,
`user_reflection`, `decision`, `goal`, `memory_reference`,
`health_projection`, `relationship_projection`, `external_source`.

`health_projection` and `relationship_projection` are read-only,
purpose-minimized cross-domain projection boundaries (never a duplication of
sibling-domain state). `therapy_transcript` and `therapy_session_note` require
speaker identity, source identity and verbatim-vs-summary provenance.
`health_projection` is Health-owned truth consumed as a projection: Mental
Health never rewrites it.

## 4. Profile

`MentalHealthProfile` (`mental-health.profile`) configures:

- non-pathologizing ordinary mode (`allow_speculation=False`, no clinical or
  diagnostic required section);
- epistemic separation and high uncertainty preservation;
- speaker/source provenance for therapy material;
- proposal-first sensitive memory (`allow_read=True`, `allow_write=False`,
  `retention_scope="session"`, `sensitivity_limit=SENSITIVE`);
- purpose-minimized cross-domain context (`allow_cross_domain=False`);
- Health clinical-authority preservation via prohibited actions
  (`medication_start`, `medication_stop`, `treatment_plan_change`,
  `clinician_override`, `clinical_authority_claim`, ...);
- prohibition of diagnosis presentation, disorder attribution, severity-score
  invention, fabricated therapist statements, implicit persistence, external
  communication, crisis dispatch and export.

## 5. Rules

Thirteen deterministic rules (catalog order):

```text
mental_health.emotional_context_relevance
mental_health.emotional_epistemic_separation
mental_health.non_pathologizing_default
mental_health.material_gap_questioning
mental_health.authorized_longitudinal_continuity
mental_health.therapy_speaker_provenance
mental_health.therapy_statement_separation
mental_health.uncertainty_preservation
mental_health.repetition_without_pathology
mental_health.health_authority
mental_health.purpose_minimized_cross_domain
mental_health.sensitive_persistence_control
mental_health.proportionate_safety_escalation
```

Rules produce canonical findings/gaps/escalations and trace references only.
They never mutate memory, grant permissions, perform external actions, create
diagnosis truth, override Health or replace privacy policy.

Behavioral invariants encoded and tested:

```text
emotion != fact; interpretation != fact; fear != prediction;
intuition != evidence; possibility != probability; repeated thought != diagnosis;
distress != emergency; therapist statement != system fact;
user statement != clinician statement; model interpretation != source statement;
talking about an inference != authorization to persist it.
```

## 6. Operations

Exactly eight declarative operations. Declaration never means availability:
without an injected canonical implementation they register **UNAVAILABLE**
(fail-closed).

| Operation | Type | Highlights |
| --- | --- | --- |
| `mental_health.review_emotional_context` | analysis | ordinary emotional review |
| `mental_health.prepare_therapy_session` | preparation | agenda/questions/unresolved items only |
| `mental_health.review_therapy_session` | analysis | attribution-preserving review |
| `mental_health.analyze_therapy_transcript` | sensitive | requires `transcript_ref` + `speaker_turns`; approval-gated |
| `mental_health.compare_emotional_periods` | analysis | authorized longitudinal references only |
| `mental_health.map_fact_interpretation_uncertainty` | analysis | epistemic separation |
| `mental_health.review_emotional_decision` | analysis | preference/uncertainty/trade-offs preserved |
| `mental_health.propose_memory_update` | memory (proposal-only) | canonical proposal/binding only |

No operation performs a direct external effect and `direct_memory_write` is
`False` for every one of them.

## 7. Workflows

Exactly eight workflows on the shared Workflow Engine. IDs are stable under the
`mental_health.` namespace; display titles are never identifiers.

```text
mental_health.emotional_context_review
mental_health.therapy_session_preparation
mental_health.therapy_session_post_processing
mental_health.therapy_transcript_review
mental_health.longitudinal_emotional_review
mental_health.emotionally_relevant_decision_review
mental_health.sensitive_memory_proposal_review
mental_health.safety_escalation_review
```

Every workflow enforces a strict `load -> profile -> reason` prefix and a
terminal `COMPLETE` node that transitively depends on a `VALIDATE` node. The
sensitive-memory workflow stops at a `PROPOSE_MEMORY` node behind a real
`REQUEST_APPROVAL` gate (`mental_health.sensitive_memory_persistence`), so a
proposal can never become a mutation without the canonical approval path. The
safety workflow is a **coordination** flow: it routes to the existing canonical
escalation/validation mechanism and creates no crisis decision engine.

## 8. Permission policy

`domain-permission:mental-health:1.0.0` — fail-closed. Allowed autonomous
surface: `RESOURCE_READ`, `KNOWLEDGE_READ`, `MEMORY_READ`,
`OPERATION_EXECUTE`, `WORKFLOW_EXECUTE`, `SENSITIVE_INFERENCE`.

Capability separation (explicit, tested):

```text
read | infer | propose_persistence | persist | transfer | export | communicate | external_mutation
```

- memory read allowed under policy; memory write **not** automatic (denied, approval-gated);
- external communication and export denied by default;
- `DOMAIN_CROSS_ACCESS` denied by default and approval-gated;
- sensitive persistence denied by default and approval-gated;
- autonomy level 0: no reversible or irreversible autonomous change.

Unknown or malformed permission state denies; only the literal `True`
authorizes a boolean gate.

## 9. Privacy policy

Canonical `DomainPrivacyPolicy` with `PrivacyPolicy.LOCAL_ONLY` and
`SensitivityLevel.SENSITIVE`, `allowed_processing_locations=(LOCAL,)`,
`allow_remote=False`, `allow_premium=False`, `allow_export=False`,
`require_approval_for_remote=True`.

Most-restrictive composition may only strengthen the result: a more permissive
sibling policy never widens it, `LOCAL_ONLY` is never weakened, and no
`allow_cross_domain` shortcut exists in the declaration or its projection.

## 10. Presentation

`build_mental_health_presentation_policy()` delegates to
`MentalHealthProfile.presentation_policy`. Human, non-pathologizing ordinary
mode with visible uncertainty, visible provenance, visible
interpretation-vs-fact separation and visible sensitive-action confirmation
requirements. `allow_speculation=False`; no clinical or diagnostic section is
required. It never alters facts, hides uncertainty, promotes interpretation to
fact, invents diagnosis, alters confidence or becomes a Phase 11 renderer or
`CommunicationProfile`.

## 11. Trace

`trace.py` composes caller-supplied typed references into the canonical Phase
10.17 contracts via `DomainTraceAssembler`, and validates through
`DefaultDomainTraceReferenceValidator`. Trace data is reference-only: no
private chain-of-thought and no transcript text are copied. The domain-scoped
kinds and result pairings let a trace explain selection, participation,
authority, privacy, knowledge/memory references and operation/workflow
references. No Mental Health trace store exists.

## 12. Memory proposal semantics

`memory.py` builds proposal-only structures over the Phase 10.18 contracts:

```text
READ != PROPOSE != APPROVE != APPLY != INVALIDATE != DELETE
```

- views resolve through `DefaultDomainMemoryViewResolver`;
- proposals are `MEMORY_UPDATE` with `requires_confirmation=True`,
  `required_capabilities=(PROPOSE,)` and no override;
- restricted content kinds (fear, intuition, inferred emotional pattern,
  emotional loop, psychological/psychiatric interpretation, third-party
  motive) are refused before a proposal can be built;
- bindings are content-bound and validated by
  `DefaultDomainMemoryIntegrationValidator`;
- a malformed or unauthorized affected-reference/permission/proposal
  inventory fails closed.

No Mental Health memory store exists.

## 13. Knowledge Package schema

`knowledge-package-schema:mental_health` narrows the canonical Phase 8
`KnowledgePackage` (no second builder). `facts` and `observations` are
provenance-bound; `inferences` and `hypotheses` preserve uncertainty;
`contradictions` stay visible; `minimum_sensitivity=SENSITIVE`. The schema
declares no unbuildable hard requirement, and the real
`KnowledgePackageBuilder` path produces a schema-valid package.

The approved context stays reachable through the pack: active emotional
objective, source-separated conversation/therapy evidence, facts and
observations, interpretations and hypotheses, uncertainty and contradictions,
longitudinal context, authorized supporting-domain projections,
permissions/privacy and therapy speaker identity/provenance.

## 14. Model policy

`build_mental_health_model_policy()` returns a Phase 10.46
`DomainModelPolicy` with requirements, not selections:
`require_reasoning`, `require_structured_output`,
`require_context_validation`, `require_response_validation`,
`minimum_context_window=32768`. No provider or model id is embedded; there is
no router, gateway, ranking engine or provider registry.

## 15. Benchmarks

`benchmark-suite:mental-health:core` — six deterministic declarative cases
covering ordinary emotional conversation without over-clinicalization,
therapy-transcript provenance, Health authority boundary, non-pathologizing
loop handling with proportionate safety, sensitive-memory/purpose-minimized
privacy, and therapy preparation. Cases are portable data with a deterministic
`content_digest`; no benchmark runtime exists.

## 16. Quality metrics

Nine declarative Phase 10.48 metrics (weights sum to 1.00). The following
unacceptable outcomes are **blocking**:

```text
invented diagnosis / treatment-medication change / Health authority violation
interpretation promoted to fact
therapy provenance loss
unauthorized sensitive transfer or persistence
emergency escalation without material basis
```

`health-authority-boundary-fidelity`, `privacy-adherence` and
`sensitive-memory-proposal-discipline` require a perfect 1.00 minimum score.
No quality evaluator runtime exists.

## 17. Resolver and bootstrap

`build_standard_mental_health_domain_bootstrap()` reuses the standard General
bootstrap registries and registers Mental Health into those exact objects.
`DefaultDomainResolver` keeps `fallback_domain=domain:general`.

Verified connected behavior:

```text
ordinary emotional conversation  -> primary domain:mental-health (when eligible)
therapy preparation              -> primary domain:mental-health
documented medication change     -> primary domain:health, supporting domain:mental-health
generic request                  -> domain:general fallback
Mental Health unavailable/unauthorized -> BLOCKED, never silently absorbed by General
Phase 10.53 absent               -> Mental Health boots and works
```

No resolver threshold is weakened and no Mental Health-specific resolver
exists.

## 18. Health clinical-authority boundary

Health owns documented diagnoses, diagnosis status, treatment plans,
medication, medication changes, clinical records and medical safety. Mental
Health consumes authorized projections only and may never rewrite, replace or
upgrade those facts. The connected case
(`tests/domains/test_mental_health_domain_dp052_acceptance.py`) composes real
`build_health_domain_definition()` plus the Mental Health definition and
proves:

```text
HEALTH_AUTHORITY_PRESERVED=YES
MENTAL_HEALTH_SUPPORTING_ALLOWED=YES
MENTAL_HEALTH_CLINICAL_OVERRIDE=NO
```

## 19. Therapy transcript provenance

Transcript handling preserves speaker identity, speaker role, source identity,
provenance, time/reference context, epistemic status, uncertainty, privacy and
permissions. At minimum the model, user and system layers stay distinct:

```text
therapist statement != user statement != model/system interpretation
```

An unattributed clinical claim blocks high-confidence output; a non-therapist
statement attributed to the therapist is blocked as a fabricated therapist
statement. No transcript store or therapy-history database exists.

## 20. Cross-domain minimization

Cross-domain context enters only through existing canonical mechanisms and
must be purpose-minimized, permission-authorized, privacy-authorized,
provenance-preserving, temporally valid and epistemically faithful. The
projection rule includes only explicitly relevant fields and excludes
irrelevant sensitive fields while preserving source-domain provenance
references.

## 21. Safety semantics

Mental Health owns no new safety system. Ordinary distress, sadness, anxiety,
grief, anger, loneliness, repetition or emotional intensity never becomes an
emergency; the loop rule never infers disorder or invents a severity score.
Escalation requires material credible immediate risk and routes through the
existing canonical mechanism. No autonomous external contact, hidden
emergency dispatch, fabricated risk certainty or treatment change exists.

## 22. Atomic registration

`register_mental_health_domain(...)` is validation-first and rollback-capable:
all declarations are validated against every registry before the first
mutation; snapshots are captured before mutation; any failure after a mutation
restores every touched registry to its exact prior state via public
`restore_state()` APIs. A simulated downstream failure was proven to restore
the complete pre-call state in both the focused registration tests and the
connected acceptance. No new transaction manager or registry abstraction was
introduced.

## 23. Known limits

- Operations are declared but **unavailable** until a canonical implementation
  is explicitly injected; the pack ships no operation implementations.
- The pack reasons over authorized references; it provides no persistent
  emotional timeline, transcript warehouse or therapy history.
- Safety escalation is coordination only; it depends on existing canonical
  escalation/policy authorities being configured by the runtime.
- Quality metrics and benchmarks are declarations; no evaluator or benchmark
  runtime is included (by design).
- `domain:mental-health` is not registered by any other first-party
  bootstrap; it is composed only through its own
  `build_standard_mental_health_domain_bootstrap()` (plus the existing Health
  bootstrap when a connected Health case is needed).
- Phase 10.53 Neurodivergence is absent and intentionally not required.

## 24. Test evidence

Focused Phase 10.52 suite (self-reported, pre-audit):

```text
tests/domains/test_mental_health_domain_contracts.py
tests/domains/test_mental_health_domain_registration.py
tests/domains/test_mental_health_domain_resolution.py
tests/domains/test_mental_health_domain_permissions.py
tests/domains/test_mental_health_domain_privacy.py
tests/domains/test_mental_health_domain_memory.py
tests/domains/test_mental_health_domain_knowledge_package.py
tests/domains/test_mental_health_domain_workflows.py
tests/domains/test_mental_health_domain_benchmarks.py
tests/domains/test_mental_health_domain_quality_metrics.py
tests/domains/test_mental_health_domain_architecture.py
tests/domains/test_mental_health_domain_dp052_acceptance.py
```

Regressions preserved: the Phase 10.51 conformance inventory, architecture and
DP-051 acceptance, the first-party benchmark/quality/knowledge-package/privacy
inventories and the whole `tests/domains` subsystem plus the global suite.

## 25. AT-DP-052

`tests/domains/test_mental_health_domain_dp052_acceptance.py` proves, in one
connected journey over real canonical components: the first-party
`DomainDefinition`, atomic registration, real resolver selection,
`MentalHealthProfile` resolution, non-clinical ordinary mode,
therapy preparation/review through the shared Workflow Engine, transcript
speaker/source provenance, canonical epistemic separation, non-persistence of
sensitive inference, Health clinical authority, restrictive cross-domain
permission intersection, canonical `SENSITIVE` privacy, purpose-minimized
supporting context, revalidated authority downgrade that fails closed,
operations unavailable without injection, absence of parallel infrastructure,
Phase 10.53 absence and preserved pre-10.52 first-party domains.

## 26. Anti-fragmentation invariants

`tests/domains/test_mental_health_domain_architecture.py` reuses the canonical
Phase 10.39 fragmentation analyzer and asserts the pack introduces none of:
`MentalHealthRegistry`, `MentalHealthLoader`, `MentalHealthResolver`,
`MentalHealthComposer`, `MentalHealthRuntime`, `MentalHealthEngine`,
`MentalHealthStore`, `MentalHealthMemory(Store)`, `MentalHealthKnowledgeGraph`,
`MentalHealthPlanner`, `MentalHealthWorkflowEngine`,
`MentalHealthPermissionEngine`, `MentalHealthPrivacyEngine`,
`MentalHealthTraceStore`, `MentalHealthValidationEngine`,
`MentalHealthSafetyEngine`, `MentalHealthCrisisEngine`, `TherapyHistoryStore`,
a second `KnowledgePackageBuilder`, a benchmark/quality runtime or a Phase 11
surface. It also asserts `cmm/domains/neurodivergence/` is absent, production
does not import tests, no Mental Health-owned persistent store exists, and a
fresh import is side-effect free.

## 27. Phase 10.51 compatibility

`domain:mental-health` is the thirteenth first-party Domain Pack. The closed
DP-051 historical baseline (28 blocks, 12 pre-10.52 packs, 2 deferred packs)
is preserved verbatim as historical evidence; the current inventory is
extended to 13 packs and 1 deferred pack (Neurodivergence) through the existing
extensibility seam. No Phase 10.51 validation was weakened to admit Mental
Health.

## 28. Pre-audit status

```text
PHASE10_52=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
DP-052=PASS_REPORTED
AT-DP-052=PASS_REPORTED
CLOSURE_ELIGIBLE=UNKNOWN_PENDING_INDEPENDENT_AUDIT
PHASE10_53=NOT_STARTED
```

Independent audit is performed outside the implementation agent. This document
does not claim audit PASS and does not close the phase.
