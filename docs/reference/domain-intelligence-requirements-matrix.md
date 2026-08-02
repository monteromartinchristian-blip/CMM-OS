# Domain Intelligence Requirements Matrix

**Status:** Canonical reference for Phase 10.16 through Phase 10.30

**Coverage evidence:** [Domain prompt clause coverage](../audits/domain-prompt-clause-coverage.md)

**Privacy:** The original prompts and external operating specifications remain outside the repository. They contain private and mutable information and are identified here only by logical source IDs and SHA-256 hashes.

## 1. Purpose and scope

This document is the canonical requirements source for the continuation of Phase 10 after the closure of Phase 10.15. It translates the normative content of fifteen domain prompts, two external operating specifications, the Phase 10.15 preflight, and the applicable roadmaps into implementation-assignable requirements without importing provider-specific instructions or personal state.

It defines architectural ownership and acceptance boundaries. It does not design Phase 10.16 classes, reopen completed phases, implement integrations, or reproduce private source content.

The companion coverage appendix records every normative source clause exactly once and maps it to the requirements in this document.

## 2. Mapping status

Every mapping to a repository symbol uses one of these states:

| Status | Meaning |
|---|---|
| `VERIFIED_EXISTING` | The named repository symbol or contract was inspected and already exists. |
| `REQUIRES_PHASE_INSPECTION` | The required capability belongs to a future phase, but the phase must inspect existing contracts before deciding whether an additive change is needed. |
| `NEW_CONTRACT_REQUIRED` | The requirement needs a new integration or trace contract; it must reuse existing semantic contracts rather than replace them. |

`NEW_CONTRACT_REQUIRED` identifies ownership only. It is not a class design.

## 3. Corrected architectural principles

1. Phase 10 specializes one shared Kernel, Cognitive Layer, Knowledge Model, Knowledge Store, Knowledge Graph, Agent Runtime, workflow system, operation system, validation system, and memory infrastructure.
2. Phase 10.16 is Domain Presentation. It structures and exposes an already resolved result; it does not decide how to reason, whether to ask, what action to take, or whether a situation is urgent.
3. Question necessity, reasoning mode, escalation, and workflow decisions remain in Phase 8 infrastructure, Domain Profiles/Rules, Domain Packs, and concrete workflows.
4. `DomainPresentationPolicy` is separate from the Phase 11 `CommunicationProfile` and from Phase 11 renderers.
5. Phase 10.17 records domain participation and references existing traces. It does not duplicate cognitive reasoning, provenance, retrieval, tool traces, provider audit, Knowledge Packages, or Model Gateway observability.
6. Phase 10.18 integrates domains with the existing cognitive knowledge and memory infrastructure. It must not introduce another claim model, store, graph, provenance system, persistent memory, or temporal engine.
7. Mutable personal information is versioned state with provenance and validity, never a stable prompt rule.
8. Provider-specific instructions and product-specific operations are abstracted into resource, workflow, connector, or provider-adapter requirements.
9. Phase 10.15 remains closed. No incompatibility with its permission contracts was demonstrated by this analysis.
10. Implementation remains sequential: 10.16, 10.17, 10.18, 10.19 through 10.30, then Phase 11.

## 4. Source registry

All hashes are SHA-256. `external-private` means that the source is deliberately not stored in this repository.

| `source_id` | Logical name | Version | Location class | SHA-256 |
|---|---|---|---|---|
| `SRC-P01` | Global response instructions prompt | hash-identified | external-private | `1d97746a5bd805151dcfb4cc9250f649cd4b5b7ccdd2d2dbd4db46e21ca278f6` |
| `SRC-P02` | Sport domain prompt | hash-identified | external-private | `a890066e7cc8d536e0288437769d93bb38f67c2b0ee45e46e197aa7e7c51503c` |
| `SRC-P03` | Formation overlay prompt | hash-identified | external-private | `7440abf6e1330f11eb21c01f1ef624c4c32434cacf55212ce7cb98a4dced3efa` |
| `SRC-P04` | Life-plan domain prompt | hash-identified | external-private | `1286a38dfbd535368cb9a017fcd5aeaa21396fe4a7006aee2795eae68dbc5cb0` |
| `SRC-P05` | Languages domain prompt | hash-identified | external-private | `21cba2f33eabbd61ad233d65dee0841f0c348793b528c275b9498a6c3e52c476` |
| `SRC-P06` | Interests specialization prompt | hash-identified | external-private | `28d5d5db6f732430e6d0e6b9f87792cd17b577900c8806929ebfab5636454cf6` |
| `SRC-P07` | Neurodivergence and mental-health domain prompt | hash-identified | external-private | `46f259b823119d5d811282544c9f047254bff021ca948dcd6d7f06184b88e433` |
| `SRC-P08` | Oppositions domain prompt | hash-identified | external-private | `0cbfa0665b860bf81ff8be720d311bb091834ff1a5996ca414875cd1b4f5f7dc` |
| `SRC-P09` | General domain prompt | hash-identified | external-private | `7b8e60a5ce0de543f929a652fea407cf565e265318e8cc8b39aae7abaa157894` |
| `SRC-P10` | Parenthood domain prompt | hash-identified | external-private | `c73f3017b27f75197aae5f101389b4fb8b5c96d046e7b48eab7cc98f2ba92eb8` |
| `SRC-P11` | Reflection domain prompt | hash-identified | external-private | `6bdb66e9651b51dc428f031f0e03ec5dec43d8f49bf04386cdcd47563feae4b8` |
| `SRC-P12` | Relationships domain prompt | hash-identified | external-private | `c8751d9bc652a83cf6b93de5aefdefe52fdef1b8b16789f53c21994e151b4bdf` |
| `SRC-P13` | Health domain prompt | hash-identified | external-private | `555ceb40ac428a8749bdf9ad25be3edc23d6248727f1609512051f8dee9c2f74` |
| `SRC-P14` | University domain prompt | hash-identified | external-private | `56eab7925ef49ada5e9929e19cc1d35d809fb5dde76f7e668a44c515b248b1d8` |
| `SRC-P15` | Clinical documentation organization prompt | hash-identified | external-private | `54328157c118a2a9afae7adf67856a31e6573baf5345ffa82851ca52b21fb643` |
| `SRC-CRS` | Context Resolution Operating Specification | 1.2 | external-private | `ac590dc6f26228347e3d0d0637aa5069fd604c12fa8de55d88087de8f7b284ea` |
| `SRC-DGS` | Document Generation Operating Specification | 1.0 | external-private | `003f38fe147b7497fcda6f9c21144088a312899b1ce0b5a563951640443e68df` |
| `SRC-PF1015` | [Phase 10.15 prompts preflight](../audits/phase-10.15-prompts-preflight.md) | closed 2026-08-02 | repository | `f6a82175927c85215fdc7aeb68ea017a4962fa0641c44ebb47b59a35e35edfa4` |
| `SRC-R10` | [Detailed Phase 10 roadmap](../roadmap/phase-10-domain-intelligence.md) | current at incorporation | repository | `d04e3fbbf73e4b578fbd015dcbe9210a12e6fca746590131354b08233ca524e0` |
| `SRC-RM` | [General roadmap](../../ROADMAP.md) | current at incorporation | repository | `2a8353b398e87efeaf45555efb586b8d939323da91356056d3ab5b764fe0623c` |
| `SRC-P8API` | [Cognitive API reference](cognitive-api.md) | current at analysis | repository | `10308eb09b45326d1e9e385594ee2030677f596a72e0cdf4361dda64d6e5acb3` |
| `SRC-P8INV` | [Cognitive Layer invariants](../architecture/cognitive-layer-invariants.md) | current at analysis | repository | `b20fef7e8d44af5441f92b5397c0a0af86a883e44f86b54be1efcc908edd7d76` |
| `SRC-P9TRACE` | [Phase 9 Agent Runtime trace](../architecture/phase-9-agent-runtime-trace.md) | current at analysis | repository | `36bcb5e6b9077bcc93232ff63b36152112375edd8875242a5b9680d22f2275c7` |
| `SRC-DP` | [Domain Profiles design](../superpowers/specs/2026-08-01-domain-profiles-design.md) | 2026-08-01 | repository | `ef765c7084ca5d49c3d4bf267078b9f95cfca2abbbe9960886881e061fff539a` |
| `SRC-R11` | [Detailed Phase 11 roadmap](../roadmap/phase-11-stable-integrated-platform.md) | current at analysis | repository | `c54190a8838c2bbd0ad36c271cd9c2a1ccdbb61df255651692dfe9fdc94ba2a8` |

## 5. Canonical requirements

The coverage appendix supplies exact clause locations and coverage states. Each requirement below has one responsible phase or one existing-contract owner.

### 5.1 Architecture requirements (`ARC-*`)

| `requirement_id` | Normative requirement | Primary source | Responsible owner | Repository mapping | Mapping status | Acceptance test |
|---|---|---|---|---|---|---|
| `ARC-001` | Ask only when a material information gap or ambiguity changes the valid result. | `SRC-P09:P09-C03` | Existing Phase 8 | `ReasoningGap`; `DomainQuestionPolicy` supplies configuration | `VERIFIED_EXISTING` | `AT-ARC-01` |
| `ARC-002` | Resolve Socratic, directive, reflective, or analytical mode before presentation. | `SRC-P03:P03-C02` | Existing Phase 8 | reasoning profiles; `ResolvedDomainProfile` and workflow resolution supply configuration | `VERIFIED_EXISTING` | `AT-ARC-02` |
| `ARC-003` | Detect urgency and escalation in domain rules and workflows; presentation only orders the resulting warning. | `SRC-P07:P07-C06` | Domain Packs | `ReasoningEscalation`; domain rule result | `VERIFIED_EXISTING` | `AT-ARC-03` |
| `ARC-004` | Preserve epistemic kind, confidence, provenance, temporality, gaps, and contradictions. | `SRC-CRS:CRS-RD4` | Existing Phase 8 | `KnowledgeItem`; `Evidence`; `TemporalScope`; `Contradiction`; `KnowledgePackage` | `VERIFIED_EXISTING` | `AT-ARC-04` |
| `ARC-005` | Resolve authority by attribute, purpose, and time; memory is not a universal source of truth. | `SRC-CRS:CRS-C11A` | Domain Packs | evidence and temporal contracts exist; concrete authority rules belong to packs | `REQUIRES_PHASE_INSPECTION` | `AT-ARC-05` |
| `ARC-006` | Enforce permissions and approvals for sensitive inference, transfer, persistence, and external effects. | `SRC-PF1015:PF-C02` | Existing Phase 10.15 | Domain Permissions contracts and policy engine | `VERIFIED_EXISTING` | `AT-ARC-06` |
| `ARC-007` | Prevent the system from making final clinical, legal, or financial decisions reserved for qualified humans. | `SRC-P13:P13-C02` | Domain Packs | domain rules and prohibited actions infrastructure | `REQUIRES_PHASE_INSPECTION` | `AT-ARC-07` |
| `ARC-008` | Treat dates, medication state, appointments, plans, decisions, and personal figures as versioned mutable state, not stable prompt rules. | `SRC-PF1015:PF-C05` | Phase 10.18 | `KnowledgeItem`; `TemporalScope`; evidence and revision contracts | `VERIFIED_EXISTING` | `AT-ARC-08` |

### 5.2 Domain Presentation requirements (`PRES-*`)

These requirements define Phase 10.16 scope without designing its implementation.

| `requirement_id` | Normative requirement | Primary source | Responsible phase | Repository mapping | Mapping status | Acceptance test |
|---|---|---|---|---|---|---|
| `PRES-001` | Order required, optional, and suppressible sections without changing semantic content. | `SRC-R10:R10-C16` | 10.16 | existing `DomainPresentationPolicy`; `DomainComposition.presentation` | `REQUIRES_PHASE_INSPECTION` | `AT-PRES-01` |
| `PRES-002` | Preserve domain and user terminology; a glossa may explain but not destructively normalize it. | `SRC-DGS:DGS-C04` | 10.16 | existing presentation metadata and policy must be inspected | `REQUIRES_PHASE_INSPECTION` | `AT-PRES-02` |
| `PRES-003` | Control visibility of facts, observations, inferences, hypotheses, confidence, sources, gaps, uncertainty, and contradictions. | `SRC-P07:P07-C12` | 10.16 | Phase 8 epistemic contracts are inputs; presentation mapping is pending | `REQUIRES_PHASE_INSPECTION` | `AT-PRES-03` |
| `PRES-004` | Order warnings using a priority or severity already resolved upstream. | `SRC-R10:R10-C16` | 10.16 | `ReasoningEscalation` and warning outputs exist | `REQUIRES_PHASE_INSPECTION` | `AT-PRES-04` |
| `PRES-005` | Select view or component descriptors compatible with the structured result. | `SRC-R10:R10-C16` | 10.16 | roadmap component vocabulary; no renderer contract yet | `REQUIRES_PHASE_INSPECTION` | `AT-PRES-05` |
| `PRES-006` | Express a requested human, structured, UI, or artifact output type without rendering the artifact. | `SRC-R10:R10-C16` | 10.16 | output intent must remain separate from Phase 11 renderers | `REQUIRES_PHASE_INSPECTION` | `AT-PRES-06` |
| `PRES-007` | Validate preservation of facts, qualifications, confidence, uncertainty, warnings, contradictions, and approvals. | `SRC-P8INV:P8INV-C01` | 10.16 | Cognitive Layer invariants are verified inputs | `REQUIRES_PHASE_INSPECTION` | `AT-PRES-07` |
| `PRES-008` | Display already-resolved questions, modes, workflow progress, approvals, and memory proposals without deciding them. | `SRC-P03:P03-C05` | 10.16 | existing upstream result symbols | `REQUIRES_PHASE_INSPECTION` | `AT-PRES-08` |

### 5.3 Domain Trace requirements (`TRACE-*`)

| `requirement_id` | Normative requirement | Primary source | Responsible phase | Repository mapping | Mapping status | Acceptance test |
|---|---|---|---|---|---|---|
| `TRACE-001` | Record a minimal domain-participation trace with identity, status, and duration. | `SRC-R10:R10-C17` | 10.17 | domain trace aggregate | `NEW_CONTRACT_REQUIRED` | `AT-TRACE-01` |
| `TRACE-002` | Reference domain resolution, primary/supporting domains, and domain composition. | `SRC-R10:R10-C17` | 10.17 | `DomainResolutionContext`; `DomainResolutionResult`; `DomainComposition` | `VERIFIED_EXISTING` | `AT-TRACE-02` |
| `TRACE-003` | Reference resource resolution, resolved profiles, and domain-rule execution without copying their content. | `SRC-R10:R10-C17` | 10.17 | `DomainResourceResolution`; `ResolvedDomainProfile`; `DomainRuleExecutionResult` | `VERIFIED_EXISTING` | `AT-TRACE-03` |
| `TRACE-004` | Reference operations, workflows, permission decisions, approvals, and validations already recorded elsewhere. | `SRC-PF1015:PF-C06` | 10.17 | Phase 9 `AgentTrace`; Phase 10 operation/workflow/permission results | `VERIFIED_EXISTING` | `AT-TRACE-04` |
| `TRACE-005` | Reference cross-domain, cognitive, Knowledge Package, contradiction, gap, finding, and warning results by ID. | `SRC-R10:R10-C17` | 10.17 | `CrossDomainResult`; `CognitiveResult.trace_id`; `KnowledgePackage.id` | `VERIFIED_EXISTING` | `AT-TRACE-05` |
| `TRACE-006` | Exclude chain of thought, private prompts, secrets, sensitive values, and unused content. | `SRC-P9TRACE:P9TRACE-C01` | 10.17 | `AgentTrace` safety policy | `VERIFIED_EXISTING` | `AT-TRACE-06` |

### 5.4 Domain Memory Integration requirements (`MEM-*`)

| `requirement_id` | Normative requirement | Primary source | Responsible phase | Repository mapping | Mapping status | Acceptance test |
|---|---|---|---|---|---|---|
| `MEM-001` | Produce a permission-filtered domain view as a query, not a persistent copy. | `SRC-R10:R10-C18` | 10.18 | `KnowledgePackageRequest.domain`; `KnowledgeQuery`; `KnowledgePackage` | `NEW_CONTRACT_REQUIRED` | `AT-MEM-01` |
| `MEM-002` | Store mutable state with evidence, validity, version, and succession links. | `SRC-CRS:CRS-RD4` | 10.18 | `KnowledgeItem`; `Evidence`; `TemporalScope` | `VERIFIED_EXISTING` | `AT-MEM-02` |
| `MEM-003` | Preserve provenance and source location through existing resource and evidence contracts. | `SRC-CRS:CRS-C04` | 10.18 | `Resource`; `ResourceProvenance`; `Evidence` | `VERIFIED_EXISTING` | `AT-MEM-03` |
| `MEM-004` | Correct through revision, invalidation, or supersession without silently deleting history. | `SRC-P15:P15-C04` | 10.18 | `KnowledgeItem` revision/invalidation; contradiction resolution audit | `VERIFIED_EXISTING` | `AT-MEM-04` |
| `MEM-005` | Distinguish temporal succession from unresolved contradiction. | `SRC-CRS:CRS-RD5` | 10.18 | `TemporalScope`; `KnowledgeRelation`; contradiction services | `VERIFIED_EXISTING` | `AT-MEM-05` |
| `MEM-006` | Consolidate duplicates and reuse shared entities, events, goals, and decisions. | `SRC-R10:R10-C18` | 10.18 | `KnowledgeConsolidator`; `KnowledgeRelation` | `VERIFIED_EXISTING` | `AT-MEM-06` |
| `MEM-007` | Make a domain memory update proposal reference existing update proposals and cognitive objects. | `SRC-R10:R10-C18` | 10.18 | Phase 9 `AgentKnowledgeUpdateProposal`; `MemoryUpdateProposal` | `NEW_CONTRACT_REQUIRED` | `AT-MEM-07` |
| `MEM-008` | Keep memory read, propose, approve, and write as separate permissions and events. | `SRC-PF1015:PF-C02` | 10.18 | reuse Phase 10.15 permission contracts and Agent Runtime proposal flow | `VERIFIED_EXISTING` | `AT-MEM-08` |
| `MEM-009` | When conversational order is unknown, recover ordering evidence or preserve the conflict unresolved. | `SRC-CRS:CRS-C05` | 10.18 | `Evidence.locator`, `observed_at`, and metadata | `REQUIRES_PHASE_INSPECTION` | `AT-MEM-09` |
| `MEM-010` | Treat temporal-series completeness as a Health rule, not a second temporal engine. | `SRC-CRS:CRS-RD6` | 10.20 | Phase 8 temporal/evidence contracts; Health rule pending | `REQUIRES_PHASE_INSPECTION` | `AT-DP-020-06` |
| `MEM-011` | Distinguish an unsuccessful lookup from confirmed absence. | `SRC-CRS:CRS-RD1` | Phase 11 | connector/retrieval outcome contract | `NEW_CONTRACT_REQUIRED` | `AT-F11-CTX-01` |

### 5.5 Domain Pack requirements (`DP-*`)

| `requirement_id` | Pack requirement | Primary source | Responsible phase | Repository mapping | Mapping status | Acceptance test |
|---|---|---|---|---|---|---|
| `DP-019` | General: direct simple answers, material-gap questions, structured complex analysis, technical troubleshooting, household safety, purchasing comparisons, and the Formation overlay. | `SRC-P09:P09-C01` | 10.19 | Domain Profile/Rule/Operation/Workflow infrastructure | `VERIFIED_EXISTING` | `AT-DP-019` |
| `DP-020` | Health: clinical certainty, source authority, longitudinal state, medication safety, differential analysis, urgent escalation, consultation preparation, and clinical-record workflows. | `SRC-P07:P07-C01` | 10.20 | shared domain infrastructure; concrete pack pending | `REQUIRES_PHASE_INSPECTION` | `AT-DP-020` |
| `DP-021` | Relationships: observed behaviour, psychological function, origin only as hypothesis, and recurrence across relationships. | `SRC-P12:P12-C02` | 10.21 | shared domain infrastructure; sensitive inference permissions | `REQUIRES_PHASE_INSPECTION` | `AT-DP-021` |
| `DP-022` | University: cross-workstream prioritization, workload, deadlines, academic risk, source separation, and institutional documents. | `SRC-P14:P14-C02` | 10.22 | shared domain infrastructure | `REQUIRES_PHASE_INSPECTION` | `AT-DP-022` |
| `DP-023` | Oppositions: versioned strategy, official-source verification, milestones, constraints, trade-offs, and study planning. | `SRC-P08:P08-C01` | 10.23 | shared domain infrastructure; external sources deferred | `REQUIRES_PHASE_INSPECTION` | `AT-DP-023` |
| `DP-024` | Reflection: open-ended analysis, prudent hypotheses, interest mapping grounded in sources, and confirmed persistence. | `SRC-P11:P11-C01` | 10.24 | shared domain infrastructure | `REQUIRES_PHASE_INSPECTION` | `AT-DP-024` |
| `DP-025` | Concerns: separate fact from scenario, evaluate control and evidence, avoid reassurance loops, and escalate real immediate risk. | `SRC-R10:R10-C25` | 10.25 | shared domain infrastructure | `REQUIRES_PHASE_INSPECTION` | `AT-DP-025` |
| `DP-026` | Languages: consented onboarding, evidenced level, lesson workflow, practice, error patterns, progression, and reviews. | `SRC-P05:P05-C03` | 10.26 | shared domain infrastructure | `REQUIRES_PHASE_INSPECTION` | `AT-DP-026` |
| `DP-027` | Parenthood: temporal legal verification, medical/legal/financial separation, decision status, scenario uncertainty, and approved external actions. | `SRC-P10:P10-C01` | 10.27 | shared domain infrastructure; providers deferred | `REQUIRES_PHASE_INSPECTION` | `AT-DP-027` |
| `DP-028` | Sport: training load, recovery, injury signals, authorized health constraints, and return-to-training workflow. | `SRC-P02:P02-C05` | 10.28 | shared domain infrastructure | `REQUIRES_PHASE_INSPECTION` | `AT-DP-028` |
| `DP-029` | Life Plan: dependencies, scenarios, resources, decision states, cross-domain impact, and plan drift. | `SRC-P04:P04-C01` | 10.29 | shared domain infrastructure | `REQUIRES_PHASE_INSPECTION` | `AT-DP-029` |
| `DP-030` | Project: generic project resources, milestones, dependencies, status, operations, and workflows. | `SRC-R10:R10-C30` | 10.30 | shared domain infrastructure | `REQUIRES_PHASE_INSPECTION` | `AT-DP-030` |

### 5.6 Phase 11 requirements (`F11-*`)

| `requirement_id` | Deferred requirement | Primary source | Responsible phase | Repository mapping | Mapping status | Acceptance test |
|---|---|---|---|---|---|---|
| `F11-001` | Resolve versioned Communication Profiles for language, register, warmth, personality, rhythm, and channel. | `SRC-R11:R11-C55` | Phase 11 | roadmap `CommunicationProfile` | `REQUIRES_PHASE_INSPECTION` | `AT-F11-COM-01` |
| `F11-002` | Render text/UI/PDF/DOCX/HTML outputs and validate real artifacts. | `SRC-DGS:DGS-C07` | Phase 11 | roadmap response and document renderers | `REQUIRES_PHASE_INSPECTION` | `AT-F11-RND-01` |
| `F11-003` | Audit retrieval, inspected sources, inclusions, exclusions, and context actually sent by CMM OS. | `SRC-CRS:CRS-C08` | Phase 11 | Model Gateway and Model Usage Audit | `REQUIRES_PHASE_INSPECTION` | `AT-F11-CTX-01` |
| `F11-004` | Implement connectors for knowledge services, conversation history, files, calendars, and official sources. | `SRC-PF1015:PF-C06` | Phase 11 | connector and integration roadmap | `REQUIRES_PHASE_INSPECTION` | `AT-F11-CON-01` |
| `F11-005` | Preserve restricted originals while redacting/tokenizing derivatives and filtering outputs by recipient. | `SRC-CRS:CRS-C10` | Phase 11 | `PrivacyMetadata` exists; operational enforcement pending | `VERIFIED_EXISTING` | `AT-F11-PII-01` |
| `F11-006` | Version artifacts and propagate claim invalidation to affected outputs. | `SRC-DGS:DGS-C11` | Phase 11 | Artifact repository capability | `NEW_CONTRACT_REQUIRED` | `AT-F11-ART-01` |
| `F11-007` | Record provider, model, egress, latency, cost, cache, and tool/provider audit outside DomainTrace. | `SRC-R11:R11-CMG` | Phase 11 | Model Gateway/Model Usage Audit roadmap | `REQUIRES_PHASE_INSPECTION` | `AT-F11-MG-01` |

### 5.7 Data extraction requirements (`DATA-*`)

No source values may be copied into implementation prompts, tests, examples, or documentation.

| `requirement_id` | Extraction requirement | Primary source | Responsible phase | Repository mapping | Mapping status | Acceptance test |
|---|---|---|---|---|---|---|
| `DATA-001` | Remove literal identifiers and their allow/deny rules from prompts; represent them through PII policy and protected storage. | `SRC-P01:P01-C06` | Phase 11 | `PrivacyMetadata`; secrets/PII services pending | `VERIFIED_EXISTING` | `AT-DATA-01` |
| `DATA-002` | Extract health, treatment, appointment, restriction, and sport status as sensitive versioned claims. | `SRC-P02:P02-C02` | 10.18 | `KnowledgeItem`; `Evidence`; `TemporalScope` | `VERIFIED_EXISTING` | `AT-DATA-02` |
| `DATA-003` | Extract academic and opposition dates, strategies, priorities, and constraints as versioned goals or decisions. | `SRC-P08:P08-C02` | 10.18 | Knowledge kinds and temporal contracts | `VERIFIED_EXISTING` | `AT-DATA-03` |
| `DATA-004` | Extract parenthood legal, medical, financial, provider, timeline, and preference state as restricted versioned knowledge. | `SRC-P10:P10-C02` | 10.18 | knowledge, evidence, sensitivity, and permission contracts | `VERIFIED_EXISTING` | `AT-DATA-04` |
| `DATA-005` | Extract biographical context, progress, preferences, and personal plans as mutable claims rather than immutable profile rules. | `SRC-P14:P14-C01` | 10.18 | knowledge and temporal contracts | `VERIFIED_EXISTING` | `AT-DATA-05` |

## 6. Exact Phase 10.16 backlog

Phase 10.16 is limited to the following outcomes:

1. Inspect the existing `DomainPresentationPolicy` and `DomainComposition.presentation` boundary.
2. Support ordering of required, optional, and suppressible sections.
3. Preserve domain terminology and optional explanatory glosses.
4. Define visibility of epistemic kinds, confidence, provenance, gaps, uncertainty, and contradictions.
5. Order warnings using severity already resolved upstream.
6. Select view/component descriptors from an already structured result.
7. Represent already-resolved questions, escalations, workflow state, approvals, and memory proposals.
8. Express requested output type without rendering it.
9. Validate semantic preservation across the presentation transformation.
10. Integrate with domain composition without executing rules, operations, or workflows.
11. Document the boundary with Phase 11 Communication Profiles and renderers.

The following are explicitly not Phase 10.16 completion criteria:

- deciding whether to ask a question;
- selecting a reasoning or conversational mode;
- detecting urgency or selecting escalation;
- choosing an operation or workflow transition;
- warmth, personality, conversational rhythm, or channel style;
- generating PDF, DOCX, HTML, or client-specific output.

No detailed Phase 10.16 design is approved by this backlog.

## 7. Exact Phase 10.17 backlog

### 7.1 Owned versus referenced information

| Concern | Ownership classification | Canonical treatment |
|---|---|---|
| Trace identity, status, start, completion, duration | `DOMAIN_TRACE_OWNED` | Stored by DomainTrace. |
| Resolution context/result references | `DOMAIN_TRACE_OWNED` | IDs only. |
| Primary and supporting domain IDs | `DOMAIN_TRACE_OWNED` | Participation facts only. |
| Composition reference | `DOMAIN_TRACE_OWNED` | ID only. |
| Selection reasons and candidate scores | `REFERENCE_EXISTING_TRACE` | Resolve through `DomainResolutionResult`. |
| Resources and resource decisions | `REFERENCE_EXISTING_TRACE` | Resolve through `DomainResourceResolution` and AgentTrace. |
| Profiles and profile-resolution trace | `REFERENCE_EXISTING_TRACE` | Resolve through `ResolvedDomainProfile`. |
| Rules, findings, gaps, recommendations, escalations | `REFERENCE_EXISTING_TRACE` | Resolve through rule plan/result IDs. |
| Operations, workflows, validations | `REFERENCE_EXISTING_TRACE` | Resolve through existing Phase 9/10 results. |
| Permission and approval decisions | `REFERENCE_EXISTING_TRACE` | Resolve through Phase 10.15 and AgentTrace. |
| Cross-domain transfers and results | `REFERENCE_EXISTING_TRACE` | Resolve through `CrossDomainResult`; do not create another transfer trace. |
| Cognitive reasoning | `ALREADY_IMPLEMENTED_PHASE_8` | Reference `CognitiveResult.trace_id`; never copy reasoning. |
| Provenance and Knowledge Package | `ALREADY_IMPLEMENTED_PHASE_8` | Reference existing IDs. |
| Domain memory proposal/result | `PHASE_10_18` | Add references after 10.18 integration. |
| Retrieval, tool, provider, model, cost, cache, egress | `PHASE_11` | Keep in platform traces and Model Gateway audit. |

### 7.2 Reference set

DomainTrace must retain only IDs or safe categorical facts for:

- request, agent trace, and correlation;
- domain resolution context and result;
- primary and supporting domains;
- domain composition;
- resolved profile and profile trace;
- domain rule plan and execution result;
- domain resource resolutions;
- domain workflow runs/results;
- domain operation results;
- permission and approval decisions;
- cross-domain results/traces;
- cognitive results/reasoning traces;
- Knowledge Packages;
- contradictions, gaps, findings, and warnings;
- status and timestamps.

It must not contain source content, rule bodies, prompt text, claim values, sensitive values, chain of thought, provider payloads, or copied subordinate traces.

## 8. Phase 8 reuse map for Phase 10.18

| Requirement | Exact reusable contract | Domain adaptation | Core extension required? | Phase 11 operational storage? | Mapping status |
|---|---|---|---|---|---|
| Domain-filtered view | `KnowledgePackageRequest.domain`; `KnowledgeQuery`; `KnowledgeQueryResult`; `KnowledgePackageBuilder`; `KnowledgePackage` | Resolved domain, memory policy, permissions, temporal scope | No core extension; domain adapter required | No | `VERIFIED_EXISTING` |
| Epistemic categories | `KnowledgeItem.kind`; Knowledge Package categories | Pack-specific taxonomy | No | No | `VERIFIED_EXISTING` |
| Mutable state | `KnowledgeItem.version`; `TemporalScope`; revision/invalidation | Domain validity rules | No | No | `VERIFIED_EXISTING` |
| Provenance | `Resource`; `ResourceProvenance`; `Evidence` | Source locator metadata | No | Connectors populate locators | `VERIFIED_EXISTING` |
| Conversational ordering | `Evidence.locator`; `observed_at`; metadata | Role/turn/order when available | Inspect before proposing typed extension | Conversation connector | `REQUIRES_PHASE_INSPECTION` |
| Contradiction lifecycle | `Contradiction`; detector; policy engine; proposal; executor | Domain authority policy | No | Optional audit persistence | `VERIFIED_EXISTING` |
| Correction/invalidation | KnowledgeItem revision/invalidation; resolution executor | Reason and approval references | No | No | `VERIFIED_EXISTING` |
| Deduplication | `KnowledgeConsolidator` | Domain identity keys | No | No | `VERIFIED_EXISTING` |
| Cross-domain links | `KnowledgeRelation` | Source/target domains and effective permissions | No | No | `VERIFIED_EXISTING` |
| Reasoning context | `KnowledgePackageRequest`; `KnowledgePackage` | Required categories and limits | No | Gateway transport | `VERIFIED_EXISTING` |
| Update proposal | Phase 8 knowledge objects; Phase 9 `AgentKnowledgeUpdateProposal`; `MemoryUpdateProposal` | Domain-scoped adapter referencing existing proposal | No Phase 8 extension | Execution persistence | `NEW_CONTRACT_REQUIRED` |
| Consent | Phase 8 propose/authorize/execute; Phase 9 proposals; Phase 10.15 permissions | Resolved memory policy | No | Client approval UI | `VERIFIED_EXISTING` |
| Resolution memory | `ResolutionMemoryEntry`; `ResolutionMemoryStore` | Domain references/filter | No | Inspect persistence needs | `VERIFIED_EXISTING` |
| Privacy | `PrivacyMetadata`; `SensitivityLevel`; `ResourcePermission` | Effective domain policy | No | Redaction, tokenization, secrets, egress | `VERIFIED_EXISTING` |
| Temporal-series completeness | `TemporalScope`; `Evidence`; `KnowledgeRelation`; contradiction services | Health domain rule | No second temporal engine | Connector must retrieve series | `REQUIRES_PHASE_INSPECTION` |
| Lookup outcome | Knowledge Package missing-information channel | Domain criticality | Connector result contract required | Yes | `NEW_CONTRACT_REQUIRED` |

Phase 10.18 is expressly prohibited from creating another Claim model, Knowledge Store, Knowledge Graph, persistent domain memory, provenance system, Knowledge Package, or temporal engine.

## 9. Sequential Domain Pack backlog

| Phase | Domain | Reduced backlog |
|---|---|---|
| 10.19 | General | Material-gap question rule; direct/simple versus structured/complex handling; technical troubleshooting; household safety; purchasing comparison; Formation as a profile/workflow overlay, not a domain. |
| 10.20 | Health | Clinical certainty; source authority by attribute; longitudinal evidence; medication safety; differential analysis; urgent escalation; consultation preparation; clinical-record workflow; temporal-series completeness. |
| 10.21 | Relationships | Behaviour/function/origin/repetition analysis; origin only as hypothesis; contradiction detection; sensitive inference and transfer limits; no therapist substitution. |
| 10.22 | University | Multi-workstream prioritization; workload and deadline reasoning; academic-risk rules; academic integrity and source separation; overload escalation; institutional-document workflow. |
| 10.23 | Oppositions | Versioned strategy and constraints; official-source verification; milestones and sequencing; trade-off analysis; realistic study planning. |
| 10.24 | Reflection | Open and potentially unresolved reflection; interest-map evidence; authentic-versus-performative hypotheses; sensitive context controls; confirmed persistence only. |
| 10.25 | Concerns | Fact/scenario separation; controlability; balanced evidence; immediate-risk escalation; avoidance of catastrophic certainty and repeated reassurance loops. |
| 10.26 | Languages | Consented onboarding; evidenced proficiency; lesson workflow; productive practice; recurrent-error threshold; vocabulary/grammar progression; periodic review. |
| 10.27 | Parenthood | Temporal legal verification; medical/legal/financial separation; explicit decision status; scenario and cost uncertainty; approved external operations. |
| 10.28 | Sport | Training load; recovery; injury signals; authorized Health constraints; mutable readiness state; return-to-training workflow. |
| 10.29 | Life Plan | Goal dependencies; scenario consistency; resource constraints; explicit decision status; cross-domain impact; plan drift. |
| 10.30 | Project | Generic project resources, milestones, dependencies, status, operations, and workflows. It is not advanced to absorb Formation. |

## 10. Phase 11 responsibilities

Phase 11 owns:

- versioned Communication Profiles and selection by user, session, domain, interaction, and channel;
- real text/UI/PDF/DOCX/HTML rendering and artifact validation;
- knowledge-service, conversation, file, calendar, and official-source connectors;
- Model Gateway context envelopes, provider/model selection, and usage audit;
- tool trace, provider audit, egress, latency, cost, cache, and retry;
- secrets, operational PII, redaction, tokenization, and recipient filtering;
- external mutation with apply, refetch, and verification;
- operational persistence not already supplied by the cognitive stores;
- artifact versioning and cascading invalidation;
- provider-specific prompt compilation and adapters.

## 11. Reassigned acceptance tests

| Test ID | Acceptance condition | Owner |
|---|---|---|
| `AT-ARC-01` | A material gap produces a question; sufficient context produces a direct answer without Presentation deciding either outcome. | Existing Phase 8 + profiles/rules |
| `AT-ARC-02` | A workflow changes Socratic to directive mode without changing presentation policy. | Profiles/Rules/Domain Pack |
| `AT-ARC-03` | An urgent domain condition produces an escalation upstream; presentation only orders it. | Domain Pack |
| `AT-ARC-04` | Epistemic kind, confidence, evidence, temporal scope, and contradiction identity survive domain processing. | Existing Phase 8 |
| `AT-ARC-05` | A critical attribute uses its declared authority rule rather than a universal source hierarchy. | Domain Pack |
| `AT-ARC-06` | Sensitive transfer or write cannot bypass Phase 10.15 decisions. | Existing Phase 10.15 |
| `AT-ARC-07` | A high-impact domain request cannot produce a prohibited final decision. | Domain Pack |
| `AT-ARC-08` | Mutable prompt state cannot be loaded as an immutable rule. | 10.18 |
| `AT-PRES-01` | Reordering sections does not change claim IDs or values. | 10.16 |
| `AT-PRES-02` | Protected terminology is preserved; a glossa does not replace it. | 10.16 |
| `AT-PRES-03` | Required uncertainty, contradiction, and provenance visibility cannot be suppressed. | 10.16 |
| `AT-PRES-04` | Presentation does not create or elevate warning severity. | 10.16 |
| `AT-PRES-05` | Components are selected only from structured result types. | 10.16 |
| `AT-PRES-06` | A requested artifact format produces an output intent, not an artifact. | 10.16 |
| `AT-PRES-07` | Preservation validation blocks loss of facts, qualifications, warnings, or approvals. | 10.16 |
| `AT-PRES-08` | A resolved question is displayed without Presentation deciding to ask it. | 10.16 |
| `AT-TRACE-01` | Each trace identifies exactly one primary domain and its supporting domains. | 10.17 |
| `AT-TRACE-02` | Resolution and composition references resolve to existing objects. | 10.17 |
| `AT-TRACE-03` | Resource/profile/rule content is absent; their references resolve. | 10.17 |
| `AT-TRACE-04` | Operation, workflow, permission, and approval history is reconstructed through existing traces. | 10.17 |
| `AT-TRACE-05` | Cross-domain and cognitive results are referenced, not copied. | 10.17 |
| `AT-TRACE-06` | Trace scanning finds no chain of thought, private prompts, secrets, or sensitive values. | 10.17 |
| `AT-MEM-01` | A domain view returns authorized references and creates no persistent copy. | 10.18 |
| `AT-MEM-02` | A mutable-value change creates a revision or supersession and preserves history. | 10.18 |
| `AT-MEM-03` | Every persisted knowledge item resolves to evidence and a resource. | 10.18 |
| `AT-MEM-04` | Correction requires a proposal/decision and leaves an audit trail. | 10.18 |
| `AT-MEM-05` | A dated succession is not treated as contradiction; unresolved order is not guessed. | 10.18 |
| `AT-MEM-06` | Two domains referring to one event reuse one knowledge item and relations. | 10.18 |
| `AT-MEM-07` | A domain update references the Agent Runtime proposal and does not serialize an alternative claim model. | 10.18 |
| `AT-MEM-08` | Read authorization does not imply write authorization. | 10.15/10.18 integration |
| `AT-MEM-09` | Unknown conversational order remains unresolved unless ordering evidence is retrieved. | 10.18 |
| `AT-DP-020-06` | Equal current values with different temporal histories do not pass series-completeness verification. | 10.20 |
| `AT-F11-CTX-01` | An empty lookup is recorded as not found, never confirmed absent without an exhaustive source. | Phase 11 |
| `AT-F11-COM-01` | A Communication Profile change cannot change facts, confidence, approvals, or actions. | Phase 11 |
| `AT-F11-RND-01` | Two renderers preserve equivalent semantic content from one structured result. | Phase 11 |
| `AT-F11-CON-01` | Connector failures and retries are observable and do not fabricate absence. | Phase 11 |
| `AT-F11-PII-01` | Restricted originals remain intact while derivatives and outputs apply their respective policies. | Phase 11 |
| `AT-F11-ART-01` | Invalidating a knowledge item identifies every dependent artifact. | Phase 11 |
| `AT-F11-MG-01` | Provider/model audit is available without appearing in DomainTrace content. | Phase 11 |
| `AT-DATA-01` | Compiled prompts and repository fixtures contain no literal private identifiers. | Phase 11 |
| `AT-DATA-02` | Health and sport state is versioned knowledge, not static configuration. | 10.18 |
| `AT-DATA-03` | Academic and opposition plans retain provenance, validity, and decision status. | 10.18 |
| `AT-DATA-04` | Parenthood state is restricted, versioned, and absent from static rules. | 10.18 |
| `AT-DATA-05` | Biographical context and preferences can be corrected without editing a rule definition. | 10.18 |
| `AT-DP-019` through `AT-DP-030` | Each pack passes its reduced backlog, permission, cross-domain, and epistemic-preservation tests before the next pack starts. | Respective Domain Pack |

## 12. Discarded or abstracted requirements

The following must not become new contracts in Phase 10:

- another `ContextItem` parallel to Resource/Evidence/KnowledgeItem;
- another Claim model or Knowledge Package;
- another Knowledge Store or Knowledge Graph;
- a persistent memory per domain;
- another provenance or temporal engine;
- a context-selection manifest inside DomainTrace;
- a second cross-domain transfer trace;
- copied resources, rules, operations, workflows, claims, or subordinate traces inside DomainTrace;
- tool/provider/model observability inside DomainTrace;
- question, reasoning-mode, urgency, or workflow decisions inside Domain Presentation;
- Communication Profile attributes as Phase 10.16 completion criteria;
- actual PDF, DOCX, or HTML generation in Phase 10.16;
- provider-specific tool calls as general contracts;
- one external product as a universal source of truth;
- automatic persistence without permission and approval;
- mutable personal facts as stable rules;
- Formation or Interests as new Domain Packs;
- advancement of Phase 10.30 without completing the preceding packs.

The Phase 10.18 roadmap sentence that appears to permit independent persistent domain copies is discarded as internally contradictory to its objective, its no-fragmentation principle, and the shared Phase 10 architecture.

## 13. Final implementation order

```text
10.16 — Domain Presentation
10.17 — Domain Trace
10.18 — Domain Memory Integration
10.19 — General
10.20 — Health
10.21 — Relationships
10.22 — University
10.23 — Oppositions
10.24 — Reflection
10.25 — Concerns
10.26 — Languages
10.27 — Parenthood
10.28 — Sport
10.29 — Life Plan
10.30 — Project
Phase 11 — Stable Integrated Platform
```

Phase 10.15 remains closed. Phase 10.16 is not marked as started by this reference.
