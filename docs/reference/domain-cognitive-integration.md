# Phase 10.40 — Integration with Cognitive Layer

**Status:** `IMPLEMENTED_PENDING_AUDIT`  
**Requirement:** `DP-040` (`SRC-R10:R10-C40`)  
**Acceptance Test:** `AT-DP-040` (`tests/domains/test_domain_cognitive_dp040_acceptance.py` — `LOCAL_PASS`)  
**Specification:** `docs/superpowers/specs/2026-09-02-phase-10.40-integration-with-cognitive-layer-design.md`  
**Implementation Plan:** `docs/superpowers/plans/2026-09-02-phase-10.40-integration-with-cognitive-layer-implementation-plan.md`  

---

## 1. Architectural Mission & Boundary Constraints

Phase 10.40 establishes the canonical bridge between Domain Intelligence (`cmm.domains`) and the Cognitive Layer (`cmm.cognitive`, established in Phase 8).

### Strict Architectural Invariants

1. **Strict One-Way Dependency:**
   - `cmm.domains → cmm.cognitive` is permitted.
   - `cmm.cognitive → cmm.domains` is strictly forbidden (0 imports; AST verified).
2. **Zero Agent Runtime Dependency in 10.40 Core:**
   - `cmm/domains/cognitive_integration.py` and `cmm/domains/cognitive_integration_contracts.py` have 0 imports of `cmm.agent_runtime` (AST verified).
3. **No CrossDomainEngine Ownership:**
   - `DefaultCrossDomainEngine` is not an owner or prerequisite for Phase 10.40; the integrator runs standalone.
4. **Zero KnowledgeStore / Memory Mutation:**
   - The integrator consumes `KnowledgeStore` in read-only mode for knowledge packaging and context building.
   - It performs zero writes, updates, deletes, or transaction calls on any store.
5. **No Parallel Cognitive Infrastructure:**
   - No parallel cognitive engine, store, graph, gap engine, question engine, confidence engine, trace store, or session store is introduced.
6. **Reference-Only Tracing:**
   - Domain traces record structural references only (`DomainTraceReferences`).
   - No hidden reasoning tokens or scratchpads (`chain_of_thought`, `reasoning_text`, `scratchpad`, `hidden_trace`, `internal_reasoning`) are copied into domain contracts.

---

## 2. Integration Contracts

Phase 10.40 introduces two primary frozen, slotted, immutable contracts in `cmm/domains/cognitive_integration_contracts.py`:

### `DomainCognitiveResourceInput`
Pairs an accepted `DomainResourceBinding` (and its `DomainResourceResolution`) with a raw Cognitive `ResourceInput`.
- Requires `binding` to be present in `resolution.bindings`.
- Requires `source.id == binding.resource_id`.
- Requires `source.sensitivity == binding.sensitivity`.
- Rejects non-executable resolution statuses (`BLOCKED`, `FAILED`).

### `DomainCognitiveIntegrationRequest`
Encapsulates all domain evidence passed across the integration boundary:
- `request_id`, `resolution_context_id`, `resolution_result_id`, `objective` (non-blank).
- `composition`: `DomainComposition` (status must be `COMPOSED` or `PARTIAL`).
- `profile`: `ResolvedDomainProfile` (primary and supporting domains must match `composition`).
- `resources`: tuple of `DomainCognitiveResourceInput` (all bindings must belong to active domains).
- `actor_id`, `session_id` (optional identifiers).
- `effective_permissions`: tuple of granted permission strings.
- `global_mandatory_rules`, `security_rules`, `requested_rule_ids`: rule IDs for canonical selection.
- `metadata`: frozen mapping proxy.

### `DomainCognitiveIntegrationResult`
The immutable evidence bundle returned from cognition:
- `request_id`: matching request.
- `knowledge_package`: canonical Phase 8 `KnowledgePackage`.
- `validation_results`: tuple of canonical Phase 8 `CognitiveValidationResult`.
- `reasoning_context`: canonical Phase 8 `ReasoningRuleContext`.
- `rule_plan`: `DomainRuleExecutionPlan` (Phase 10.13).
- `rule_result`: `DomainRuleExecutionResult` (Phase 10.13 wrapping Phase 8 `ReasoningRuleResult`).
- `adapted_resources`: tuple of canonical Phase 8 `Resource` instances.
- `extracted_bundles`: tuple of canonical Phase 8 `KnowledgeBundle` instances.
- `presentation_items`: tuple of `DomainPresentationItemRef` (Phase 10.16).
- `trace_references`: `DomainTraceReferences` (Phase 10.17).

---

## 3. Integration Pipeline Sequence

The canonical orchestrator `DefaultDomainCognitiveIntegrator` (`cmm/domains/cognitive_integration.py`) implements the `DomainCognitiveIntegrator` protocol through an 8-stage sequence:

```text
DomainCognitiveIntegrationRequest
    │
    ▼
1. Resource Adaptation & Extraction
    ├── ResourceAdapterRegistry.get(binding.adapter).adapt(...)
    │     └── Preserves provenance, sensitivity, temporal scope, reliability
    └── KnowledgeExtractorRegistry.get(extractor_name).extract(...)
          └── materialise_result(...) → KnowledgeBundle
    │
    ▼
2. Knowledge Package Assembly
    └── KnowledgePackageBuilder(store, resources).build(...)
          └── Reads existing knowledge & contradictions without mutating store
    │
    ▼
3. Canonical Cognitive Validation
    └── CognitiveValidator.validate(...)
          ├── Validates package, adapted resources, and extracted items
          └── Blocks execution if BLOCK decision or prohibited content detected
    │
    ▼
4. Reasoning Context Construction
    └── ReasoningRuleContext with primary/supporting domains, profile metadata,
        effective sensitivity, merged knowledge items, and contradictions
    │
    ▼
5. Rule Selection (Global Mandatory Before Domain)
    └── DefaultDomainRuleSelector.select(...)
          └── Orders GLOBAL_MANDATORY before PRIMARY_REQUIRED / DOMAIN rules
    │
    ▼
6. Rule Execution via Canonical Engine
    └── DefaultDomainRuleExecutor.execute(...)
          └── Delegates evaluation to canonical Phase 8 DefaultReasoningRuleEngine
    │
    ▼
7. Presentation Item Mapping
    └── Maps rule gaps, rule findings, rule questions, and extracted questions
        to DomainPresentationItemRef with preserved confidence and provenance
    │
    ▼
8. Trace Reference Projection
    └── Builds reference-only DomainTraceReferences linking resolution,
        profile, rules, validation, knowledge, and presentation
```

---

## 4. Reused Canonical Owners

| Role | Canonical Component | Subsystem |
|---|---|---|
| Resource Normalization | `ResourceAdapterRegistry`, `ResourceAdapter` | Phase 8 Cognitive |
| Knowledge Extraction | `KnowledgeExtractorRegistry`, `KnowledgeExtractor` | Phase 8 Cognitive |
| Package Construction | `KnowledgePackageBuilder` | Phase 8 Cognitive |
| Artifact Validation | `CognitiveValidator` | Phase 8 Cognitive |
| Rule Evaluation | `DefaultReasoningRuleEngine` | Phase 8 Cognitive |
| Rule Selection | `DefaultDomainRuleSelector` | Phase 10.13 Domain |
| Rule Orchestration | `DefaultDomainRuleExecutor` | Phase 10.13 Domain |
| Presentation Planning | `DefaultDomainPresentationPlanner` | Phase 10.16 Domain |
| Trace Assembly | `DomainTraceAssembler` | Phase 10.17 Domain |
| Trace Validation | `DefaultDomainTraceReferenceValidator` | Phase 10.17 Domain |

---

## 5. Epistemic, Question, and Contradiction Semantics

1. **Epistemic Distinctions:**
   - Unverified statements extracted from resources remain `KnowledgeKind.OBSERVATION` or `KnowledgeKind.STATEMENT` with `KnowledgeStatus.UNVERIFIED`.
   - Inferences and hypotheses produced by rules preserve provisional status under `global.distinguish_fact_inference_hypothesis`.
2. **Question Flow:**
   - Questions in source text follow: `CandidateKind.QUESTION` → `KnowledgeKind.QUESTION` in `bundle.items` → string question in `bundle.open_questions` → `DomainPresentationItemRef(item_type=QUESTION, pending=True, requires_user_interaction=True)`.
   - Questions produced by rules during reasoning follow: `ReasoningRuleResult.questions` → `DomainPresentationItemRef`.
   - Question references are consumed and partitioned into presentation sections by `DefaultDomainPresentationPlanner`.
3. **Contradictions:**
   - Stored and extracted contradictions are strictly Phase 8 `Contradiction` instances.
   - Identified contradictions map to `DomainPresentationItemType.CONTRADICTION` for downstream user review.
4. **Confidence Invariance:**
   - Domain profile `minimum_confidence` sets reasoning thresholds; it never overwrites or inflates underlying evidence confidence.

---

## 6. Known Limitations

At this repository baseline Phase 8 does not expose a separate production
InteractiveQuestionEngine class. Phase 10.40 therefore reuses the actual
canonical implemented path: QUESTION extraction/materialization plus
ReasoningGap evidence. A Domain-specific question engine is intentionally
not introduced.

---

## 7. Verification Evidence

- `tests/domains/test_domain_cognitive_integration_contracts.py`: 65 unit contract tests.
- `tests/domains/test_domain_cognitive_integration.py`: 51 integration, adaptation, validation, and adversarial tests.
- `tests/domains/test_domain_cognitive_integration_boundaries.py`: 10 architectural boundary and AST anti-mutation tests.
- `tests/domains/test_domain_cognitive_dp040_acceptance.py`: Connected acceptance test exercising all 21 criteria.
- Total Phase 10.40 test suite: **126 tests passed locally**.
- Global regressions: Phase 8 suite (697 tests) and Domain suite (992 tests) pass with 0 failures.
