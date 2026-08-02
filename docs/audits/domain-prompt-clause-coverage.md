# Domain Prompt Clause Coverage

**Status:** Coverage evidence for the [Domain Intelligence Requirements Matrix](../reference/domain-intelligence-requirements-matrix.md)

**Privacy:** Original prompts and external operating specifications remain outside the repository. This appendix stores only logical source identifiers, hashes, clause locations, and non-identifying normative summaries.

## 1. Coverage model

A clause is a homogeneous normative block. A clause may decompose into several canonical requirements, but it appears in exactly one row and has exactly one coverage state.

| State | Meaning |
|---|---|
| `PRIMARY` | Principal normative origin for one or more canonical requirements. |
| `DUPLICATE` | Normative content already represented by another primary clause. |
| `ABSTRACTED` | Product-, provider-, or prompt-specific wording was converted into a general contract. |
| `DECOMPOSED` | One clause was split across multiple architectural owners. |
| `DATA_EXTRACTED` | The clause contains mutable or sensitive state that must leave the prompt and become protected, versioned data. |
| `DEFERRED` | The requirement is valid but belongs to a later phase. |
| `EXISTING` | The requirement is already satisfied by an inspected contract or completed phase. |
| `DISCARDED` | The clause is non-normative, contradictory, provider-specific without a general abstraction, or duplicates an existing model. |

## 2. Complete source registry

All hashes are SHA-256. External private sources are intentionally not stored in the repository.

| `source_id` | Logical name | Version | Class | SHA-256 |
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
| `SRC-PF1015` | Phase 10.15 prompts preflight | closed 2026-08-02 | repository | `f6a82175927c85215fdc7aeb68ea017a4962fa0641c44ebb47b59a35e35edfa4` |
| `SRC-R10` | Detailed Phase 10 roadmap | current at incorporation | repository | `d04e3fbbf73e4b578fbd015dcbe9210a12e6fca746590131354b08233ca524e0` |
| `SRC-RM` | General roadmap | current at incorporation | repository | `2a8353b398e87efeaf45555efb586b8d939323da91356056d3ab5b764fe0623c` |
| `SRC-P8API` | Cognitive API reference | analysis baseline | repository | `10308eb09b45326d1e9e385594ee2030677f596a72e0cdf4361dda64d6e5acb3` |
| `SRC-P8INV` | Cognitive Layer invariants | analysis baseline | repository | `b20fef7e8d44af5441f92b5397c0a0af86a883e44f86b54be1efcc908edd7d76` |
| `SRC-P9TRACE` | Phase 9 Agent Runtime trace | analysis baseline | repository | `36bcb5e6b9077bcc93232ff63b36152112375edd8875242a5b9680d22f2275c7` |
| `SRC-DP` | Domain Profiles design | 2026-08-01 | repository | `ef765c7084ca5d49c3d4bf267078b9f95cfca2abbbe9960886881e061fff539a` |
| `SRC-R11` | Detailed Phase 11 roadmap | analysis baseline | repository | `c54190a8838c2bbd0ad36c271cd9c2a1ccdbb61df255651692dfe9fdc94ba2a8` |

## 3. Coverage of the fifteen prompts

Locations use the original source section and analysis line range. Summaries deliberately omit private values.

| `clause_id` | Source and exact section | Canonical requirement(s) | State | Justification |
|---|---|---|---|---|
| `P01-C01` | `SRC-P01` · Analysis method · lines 5–8 | `ARC-001`, `ARC-004` | `DUPLICATE` | Repeats shared reasoning and gap principles. |
| `P01-C02` | `SRC-P01` · Question interaction · lines 12–17 | `ARC-001` | `ABSTRACTED` | Universal questioning is replaced by material-gap policy. |
| `P01-C03` | `SRC-P01` · Response quality · lines 21–26 | `ARC-004`, `PRES-003` | `DUPLICATE` | Covered by cognitive preservation and visibility. |
| `P01-C04` | `SRC-P01` · Recommendations · lines 30–33 | `ARC-004`, `DP-019`–`DP-030` | `DUPLICATE` | Shared epistemic rule plus pack-specific application. |
| `P01-C05` | `SRC-P01` · Complex problems · lines 37–39 | `ARC-002`, `DP-019`–`DP-030` | `ABSTRACTED` | Cognitive strategy, not presentation logic. |
| `P01-C06` | `SRC-P01` · Document generation · lines 43–48 | `PRES-001`, `F11-002`, `F11-005`, `DATA-001` | `DECOMPOSED` | Separates structure, renderer, privacy, and extracted identifiers. |
| `P01-C07` | `SRC-P01` · General objective · lines 52–54 | `ARC-001`, `ARC-004` | `DUPLICATE` | General restatement without an additional contract. |
| `P02-C01` | `SRC-P02` · Role and interaction · lines 7–16 | `DP-028`, `ARC-004` | `PRIMARY` | Defines Sport reasoning constraints. |
| `P02-C02` | `SRC-P02` · Physical context · lines 18–27 | `DATA-002`, `DP-028` | `DATA_EXTRACTED` | Sensitive mutable state is removed from static instructions. |
| `P02-C03` | `SRC-P02` · Personal context · lines 29–35 | `DATA-005`, `F11-001` | `DATA_EXTRACTED` | Biography/status becomes claims; style becomes communication configuration. |
| `P02-C04` | `SRC-P02` · Pre-recommendation questions · lines 37–41 | `ARC-001`, `DP-028` | `ABSTRACTED` | Workflow/profile configuration decides the questions. |
| `P02-C05` | `SRC-P02` · Prohibited actions · lines 43–48 | `DP-028`, `ARC-007` | `PRIMARY` | Defines concrete Sport safety limits. |
| `P02-C06` | `SRC-P02` · Active pending items · lines 50–56 | `DATA-002` | `DATA_EXTRACTED` | Pending items are temporal goals/state. |
| `P03-C01` | `SRC-P03` · Instructor role · lines 1–3 | `DP-019` | `ABSTRACTED` | Formation is an overlay on General, not a new domain. |
| `P03-C02` | `SRC-P03` · Mixed mode · lines 5–9 | `ARC-002` | `PRIMARY` | Mode transition belongs to profiles/rules/workflows. |
| `P03-C03` | `SRC-P03` · Continuous follow-up · lines 11–17 | `DP-019`, `MEM-001`, `MEM-002` | `PRIMARY` | Defines objective state and checkpoints. |
| `P03-C04` | `SRC-P03` · Feedback · lines 18–23 | `ARC-004` | `DUPLICATE` | Existing epistemic policy. |
| `P03-C05` | `SRC-P03` · Format · lines 25–29 | `PRES-008`, `F11-001` | `DECOMPOSED` | Separates resolved question display from conversational style. |
| `P03-C06` | `SRC-P03` · Avoidances · lines 31–35 | `DP-019`, `ARC-002` | `PRIMARY` | Defines overlay/workflow constraints. |
| `P04-C01` | `SRC-P04` · Role and plan · lines 3–4 | `DP-029`, `DATA-005` | `PRIMARY` | Defines Life Plan scope and mutable plan state. |
| `P04-C02` | `SRC-P04` · Dual function · lines 6–18 | `ARC-002`, `DP-029`, `MEM-007` | `DECOMPOSED` | Separates reasoning mode, domain rules, and update proposals. |
| `P04-C03` | `SRC-P04` · Warning signals · lines 20–23 | `DP-029`, `ARC-003` | `PRIMARY` | Plan-drift and escalation rules. |
| `P04-C04` | `SRC-P04` · Interaction · lines 25–28 | `ARC-001`, `MEM-007`, `F11-004` | `DECOMPOSED` | Questions, memory proposals, and external connector are separate. |
| `P05-C01` | `SRC-P05` · Initial onboarding · lines 1–15 | `DP-026`, `MEM-008` | `ABSTRACTED` | Permanent storage is conditioned on permission. |
| `P05-C02` | `SRC-P05` · Level assessment · lines 16–31 | `DP-026` | `PRIMARY` | Defines evidenced proficiency assessment. |
| `P05-C03` | `SRC-P05` · Daily lesson structure · lines 32–45 | `DP-026` | `PRIMARY` | Defines lesson workflow. |
| `P05-C04` | `SRC-P05` · Progression system · lines 46–63 | `DP-026`, `MEM-002` | `PRIMARY` | Defines versioned learning state. |
| `P05-C05` | `SRC-P05` · Roleplay scenarios · lines 64–78 | `DP-026` | `PRIMARY` | Domain practice operation/workflow. |
| `P05-C06` | `SRC-P05` · Writing review · lines 79–86 | `DP-026`, `PRES-001` | `PRIMARY` | Correction rule and output structure. |
| `P05-C07` | `SRC-P05` · Periodic progress report · lines 87–99 | `DP-026`, `PRES-005` | `PRIMARY` | Review workflow and progress view. |
| `P05-C08` | `SRC-P05` · Cultural context · lines 100–105 | `DP-026` | `PRIMARY` | Language-domain rules. |
| `P05-C09` | `SRC-P05` · Common situations · lines 106–114 | `DP-026`, `F11-001` | `DECOMPOSED` | Pedagogical adaptation versus response wording. |
| `P05-C10` | `SRC-P05` · Final rules · lines 115–125 | `DP-026`, `F11-001` | `DECOMPOSED` | Domain pedagogy versus communication style. |
| `P06-C01` | `SRC-P06` · Role and objective · lines 1–2 | `DP-024` | `PRIMARY` | Interests is a Reflection specialization. |
| `P06-C02` | `SRC-P06` · Sources · lines 4–9 | `DP-024`, `F11-004`, `ARC-005` | `ABSTRACTED` | Logical resources are retained; product-specific access is deferred. |
| `P06-C03` | `SRC-P06` · Method · lines 11–15 | `DP-024`, `ARC-004` | `PRIMARY` | Defines source-grounded hypotheses and patterns. |
| `P06-C04` | `SRC-P06` · Interaction rules · lines 17–21 | `DP-024`, `PRES-003` | `PRIMARY` | Defines contradiction/evidence behaviour and visibility. |
| `P06-C05` | `SRC-P06` · External update · lines 23–24 | `MEM-008`, `F11-004` | `ABSTRACTED` | Propose/confirm and connector ownership replace product commands. |
| `P07-C01` | `SRC-P07` · Role and monitored areas · lines 1–17 | `DP-020`, `DATA-002` | `PRIMARY` | Defines Health scope without retaining personal state. |
| `P07-C02` | `SRC-P07` · Clinical certainty · lines 19–62 | `DP-020`, `ARC-004`, `PRES-003` | `PRIMARY` | Defines clinical taxonomy and its visibility. |
| `P07-C03` | `SRC-P07` · Source priority · lines 64–90 | `ARC-005`, `MEM-003`, `MEM-004` | `PRIMARY` | Defines provenance, authority, and unresolved discrepancies. |
| `P07-C04` | `SRC-P07` · Longitudinal record · lines 92–121 | `MEM-002`, `DP-020` | `PRIMARY` | Defines temporal evidence and stability rules. |
| `P07-C05` | `SRC-P07` · Monitored clinical areas · lines 123–296 | `DP-020` | `PRIMARY` | Domain rule/resource catalogue; no source values retained. |
| `P07-C06` | `SRC-P07` · Immediate risk · line 298 | `ARC-003` | `PRIMARY` | Upstream Health escalation. |
| `P07-C07` | `SRC-P07` · Medication and treatment history · lines 300–333 | `MEM-002`, `DP-020`, `ARC-007` | `PRIMARY` | Temporal treatment record and clinical limits. |
| `P07-C08` | `SRC-P07` · Differential analysis · lines 335–356 | `DP-020`, `PRES-005` | `PRIMARY` | Domain reasoning plus comparative view. |
| `P07-C09` | `SRC-P07` · Document analysis · lines 358–375 | `DP-020`, `MEM-003`, `F11-004` | `DECOMPOSED` | Extraction/rules are separated from external update. |
| `P07-C10` | `SRC-P07` · Connected-record organization · lines 377–424 | `DP-020`, `F11-004`, `MEM-004` | `ABSTRACTED` | Workflow, connector, and historical preservation replace product commands. |
| `P07-C11` | `SRC-P07` · Consultation preparation · lines 426–455 | `DP-020`, `PRES-001`, `F11-002` | `DECOMPOSED` | Separates content, presentation plan, and renderer. |
| `P07-C12` | `SRC-P07` · Response format · lines 457–476 | `PRES-003`, `ARC-004` | `PRIMARY` | Epistemic visibility and preservation. |
| `P07-C13` | `SRC-P07` · Clinical limits · lines 478–496 | `ARC-007`, `DP-020` | `PRIMARY` | High-impact domain boundary. |
| `P08-C01` | `SRC-P08` · Role · line 1 | `DP-023` | `PRIMARY` | Defines Oppositions responsibility. |
| `P08-C02` | `SRC-P08` · Constraints and current strategy · lines 3–14 | `DATA-003`, `DP-023` | `DATA_EXTRACTED` | Current strategy and dates become versioned decisions. |
| `P08-C03` | `SRC-P08` · Session function · lines 16–20 | `DP-023`, `F11-004` | `PRIMARY` | Planning and official-source verification. |
| `P08-C04` | `SRC-P08` · Analysis and interaction · lines 22–43 | `ARC-001`, `ARC-004`, `DP-023` | `DUPLICATE` | Shared reasoning requirements applied to the pack. |
| `P08-C05` | `SRC-P08` · Content language · lines 45–48 | `F11-001` | `DEFERRED` | Communication/localization belongs to Phase 11. |
| `P08-C06` | `SRC-P08` · Documents · lines 50–53 | `F11-002`, `F11-005` | `DEFERRED` | Renderer and output privacy. |
| `P08-C07` | `SRC-P08` · Tools and sources · lines 55–56 | `F11-004`, `DP-023` | `ABSTRACTED` | Logical resource classes replace named tools. |
| `P08-C08` | `SRC-P08` · Prohibited planning behaviour · lines 58–61 | `DP-023` | `PRIMARY` | Pack-specific planning rules. |
| `P09-C01` | `SRC-P09` · Role and areas · lines 1–35 | `DP-019` | `PRIMARY` | General domain scope. |
| `P09-C02` | `SRC-P09` · Response form · lines 40–58 | `PRES-001`, `F11-001`, `DP-019` | `DECOMPOSED` | Structure, communication, and domain reasoning are separate. |
| `P09-C03` | `SRC-P09` · Missing information · lines 62–68 | `ARC-001` | `PRIMARY` | Canonical material-gap policy. |
| `P09-C04` | `SRC-P09` · Multiple options · lines 72–84 | `DP-019`, `PRES-005` | `PRIMARY` | Comparison rule and view. |
| `P09-C05` | `SRC-P09` · Technical troubleshooting · lines 88–98 | `DP-019` | `PRIMARY` | General technical workflow. |
| `P09-C06` | `SRC-P09` · Household guidance · lines 102–109 | `DP-019` | `PRIMARY` | General safety rules. |
| `P09-C07` | `SRC-P09` · Purchasing · lines 113–120 | `DP-019` | `PRIMARY` | General comparison rules. |
| `P09-C08` | `SRC-P09` · Uncertainty · lines 124–130 | `ARC-004`, `PRES-003` | `DUPLICATE` | Existing cognitive and visibility requirements. |
| `P09-C09` | `SRC-P09` · Style · lines 134–141 | `F11-001`, `ARC-001` | `DECOMPOSED` | Communication style versus question necessity. |
| `P10-C01` | `SRC-P10` · Role · lines 3–10 | `DP-027`, `ARC-007` | `PRIMARY` | Defines parenthood specialization and high-impact limits. |
| `P10-C02` | `SRC-P10` · Current project, legal, provider, and medical context · lines 12–38 | `DATA-004`, `DP-027`, `F11-004` | `DATA_EXTRACTED` | Sensitive mutable state and external verification. |
| `P10-C03` | `SRC-P10` · Timeline · lines 39–53 | `DATA-004`, `DP-027` | `DATA_EXTRACTED` | Versioned milestones, not prompt constants. |
| `P10-C04` | `SRC-P10` · Financial plan · lines 55–64 | `DATA-004`, `DP-027` | `DATA_EXTRACTED` | Figures and assumptions are mutable state. |
| `P10-C05` | `SRC-P10` · Housing and benefits · lines 66–76 | `DATA-004`, `DP-027` | `DATA_EXTRACTED` | Plans, laws, and decisions are temporal. |
| `P10-C06` | `SRC-P10` · Parenting preferences · lines 78–83 | `DATA-004`, `DP-027` | `DATA_EXTRACTED` | Personal preferences become versioned constraints. |
| `P10-C07` | `SRC-P10` · Tools and workflow · lines 85–89 | `F11-004`, `MEM-008` | `ABSTRACTED` | Connector and authorized update replace product commands. |
| `P10-C08` | `SRC-P10` · Work method · lines 91–100 | `ARC-001`, `ARC-004`, `DP-027` | `DUPLICATE` | Shared reasoning plus decision-reopening rule. |
| `P10-C09` | `SRC-P10` · Documents · lines 102–106 | `F11-002`, `F11-005` | `DEFERRED` | Renderer and PII enforcement. |
| `P11-C01` | `SRC-P11` · Role and purpose · lines 1–26 | `DP-024` | `PRIMARY` | Reflection domain scope. |
| `P11-C02` | `SRC-P11` · Analysis and interaction · lines 28–46 | `ARC-001`, `ARC-002`, `DP-024` | `PRIMARY` | Defines reflective workflow and gap handling. |
| `P11-C03` | `SRC-P11` · Quality and honesty · lines 48–60 | `ARC-004`, `DP-024` | `PRIMARY` | Epistemic and domain rules. |
| `P11-C04` | `SRC-P11` · Prohibited interaction patterns · lines 62–71 | `DP-024`, `F11-001` | `DECOMPOSED` | Domain limits versus wording/style. |
| `P11-C05` | `SRC-P11` · Format · lines 73–79 | `F11-001`, `PRES-001` | `DECOMPOSED` | Communication versus structural presentation. |
| `P12-C01` | `SRC-P12` · Role · line 1 | `DP-021` | `PRIMARY` | Relationships domain scope. |
| `P12-C02` | `SRC-P12` · Analysis dimensions · lines 3–7 | `DP-021`, `PRES-001` | `PRIMARY` | Domain rule and corresponding sections. |
| `P12-C03` | `SRC-P12` · Work rules · lines 9–14 | `DP-021`, `ARC-001`, `ARC-004` | `PRIMARY` | Hypotheses, contradictions, and gaps. |
| `P13-C01` | `SRC-P13` · Role and capabilities · lines 1–9 | `DP-020`, `PRES-005` | `PRIMARY` | Health operations and views. |
| `P13-C02` | `SRC-P13` · Non-negotiable limits · lines 11–14 | `ARC-007`, `DP-020` | `PRIMARY` | Clinical role boundary. |
| `P13-C03` | `SRC-P13` · Work style · lines 16–20 | `ARC-001`, `ARC-004`, `DATA-001` | `DECOMPOSED` | Questions, epistemic policy, and private identifiers. |
| `P13-C04` | `SRC-P13` · Connected-record structure · lines 22–28 | `DP-020`, `F11-004`, `MEM-004` | `ABSTRACTED` | Workflow, connector, and preservation replace product instructions. |
| `P13-C05` | `SRC-P13` · Document naming · lines 30–31 | `PRES-002`, `F11-002` | `DECOMPOSED` | Naming policy versus artifact generation. |
| `P13-C06` | `SRC-P13` · Response style · lines 33–34 | `F11-001` | `DEFERRED` | Communication Profile. |
| `P14-C01` | `SRC-P14` · Current context · lines 3–6 | `DATA-005` | `DATA_EXTRACTED` | Academic and biographical state is mutable. |
| `P14-C02` | `SRC-P14` · Role · lines 8–9 | `DP-022` | `PRIMARY` | University domain scope. |
| `P14-C03` | `SRC-P14` · Work method · lines 11–17 | `ARC-001`, `ARC-004`, `DP-022` | `DUPLICATE` | Shared reasoning applied to University. |
| `P14-C04` | `SRC-P14` · Workload and overload · lines 19–24 | `DP-022`, `ARC-003` | `PRIMARY` | Domain workload and escalation rule. |
| `P14-C05` | `SRC-P14` · Output preferences · lines 26–31 | `PRES-001`, `F11-001`, `F11-002`, `F11-005` | `DECOMPOSED` | Presentation, communication, renderer, and privacy. |
| `P14-C06` | `SRC-P14` · Prohibited behaviour · lines 33–37 | `DP-022` | `PRIMARY` | University prioritization rules. |
| `P15-C01` | `SRC-P15` · Index and objective · lines 3–22 | `DP-020`, `PRES-001` | `PRIMARY` | Health record structure. |
| `P15-C02` | `SRC-P15` · External implementation · lines 24–37 | `MEM-008`, `F11-004` | `ABSTRACTED` | Automatic mutation is replaced by approval and connector workflow. |
| `P15-C03` | `SRC-P15` · Page structure · lines 39–84 | `DP-020`, `PRES-001`, `PRES-005` | `PRIMARY` | Domain sections and views. |
| `P15-C04` | `SRC-P15` · General criteria · lines 86–98 | `MEM-002`, `MEM-004`, `MEM-006` | `PRIMARY` | Chronology, preservation, and consolidation. |
| `P15-C05` | `SRC-P15` · Record purpose · lines 100–114 | `DP-020`, `PRES-002` | `PRIMARY` | Health purpose and consistent terminology. |

## 4. Context Resolution Operating Specification coverage

| `clause_id` | Source section | Canonical requirement(s) | State | Justification |
|---|---|---|---|---|
| `CRS-C01` | `SRC-CRS` · §0 evidence labels | — | `DISCARDED` | Research-document convention, not runtime behaviour. |
| `CRS-C02` | `SRC-CRS` · §7.1 context ownership | `MEM-003`, `F11-003` | `ABSTRACTED` | Ownership is preserved without another memory hierarchy. |
| `CRS-C03` | `SRC-CRS` · §7.2 proposed components | `ARC-001`–`ARC-008`, `MEM-001`–`MEM-011`, `F11-003`–`F11-007` | `DECOMPOSED` | Proposed components are split among existing contracts and later integrations. |
| `CRS-C04` | `SRC-CRS` · §8.1 ContextItem | `MEM-002`, `MEM-003` | `ABSTRACTED` | Mapped to Resource, Evidence, and KnowledgeItem. |
| `CRS-C05` | `SRC-CRS` · §8.2 ordering status | `MEM-009` | `PRIMARY` | Mandatory unresolved-order behaviour. |
| `CRS-C06` | `SRC-CRS` · §8.3 KnowledgePackage | `ARC-004`, `MEM-001` | `DUPLICATE` | KnowledgePackage already exists in Phase 8. |
| `CRS-C07` | `SRC-CRS` · §8.4 selection manifest | `TRACE-003`–`TRACE-005`, `F11-003` | `DECOMPOSED` | Domain references are separated from retrieval/egress audit. |
| `CRS-C08` | `SRC-CRS` · §8.5 model context envelope | `F11-003`, `F11-007` | `DEFERRED` | Model Gateway responsibility. |
| `CRS-C09` | `SRC-CRS` · §9.1–9.2 usage audit | `TRACE-006`, `F11-003` | `DECOMPOSED` | Safe domain trace versus platform usage audit. |
| `CRS-C10` | `SRC-CRS` · §9.3 ingestion privacy | `F11-005` | `DEFERRED` | Operational privacy belongs to Phase 11. |
| `CRS-C11A` | `SRC-CRS` · §10.3 items 1–3 and 5–7 | `MEM-002`–`MEM-005`, `ARC-005` | `PRIMARY` | Temporal, provenance, literalness, and authority requirements. |
| `CRS-C11B` | `SRC-CRS` · §10.3 item 4 | `MEM-011` | `DEFERRED` | Lookup outcomes belong to connector/retrieval integration. |
| `CRS-C11C` | `SRC-CRS` · §10.3 item 8 | `F11-006` | `DEFERRED` | Artifact invalidation belongs to Phase 11. |
| `CRS-C11D` | `SRC-CRS` · §10.3 item 9 | `ARC-006` | `EXISTING` | Domain barriers are implemented in Phase 10.15. |
| `CRS-C11E` | `SRC-CRS` · §10.3 item 10 | `TRACE-003`, `F11-003` | `DECOMPOSED` | Domain references versus platform context audit. |
| `CRS-C11F` | `SRC-CRS` · §10.3 item 11 | `MEM-008` | `EXISTING` | Confirmation and permission infrastructure exists. |
| `CRS-C11G` | `SRC-CRS` · §10.3 items 12–13 | `F11-003`, `F11-004`, `F11-007` | `DEFERRED` | Tool readiness and provider regression are platform concerns. |
| `CRS-RD1` | `SRC-CRS` · §10.4 RD-1 | `MEM-011` | `PRIMARY` | Failed lookup is not confirmed absence. |
| `CRS-RD2` | `SRC-CRS` · §10.4 RD-2 | `MEM-003`, `TRACE-003` | `PRIMARY` | Source awareness is not source inspection. |
| `CRS-RD3` | `SRC-CRS` · §10.4 RD-3 | `ARC-005` | `PRIMARY` | Memory is an index, not authority. |
| `CRS-RD4` | `SRC-CRS` · §10.4 RD-4 | `MEM-002`, `MEM-003` | `PRIMARY` | Provenance and validity are mandatory. |
| `CRS-RD5` | `SRC-CRS` · §10.4 RD-5 | `MEM-005` | `PRIMARY` | Temporal succession differs from contradiction. |
| `CRS-RD6` | `SRC-CRS` · §10.4 RD-6 | `MEM-010` | `PRIMARY` | Complete temporal series is a domain rule over existing temporal contracts. |

## 5. Document Generation Operating Specification coverage

| `clause_id` | Source section | Canonical requirement(s) | State | Justification |
|---|---|---|---|---|
| `DGS-C01` | `SRC-DGS` · §5.1–5.3 source authority and conflict | `ARC-005`, `MEM-005` | `DUPLICATE` | Refined by the newer Context Resolution specification. |
| `DGS-C02` | `SRC-DGS` · §5.4 markers | `PRES-003`, `DP-020` | `PRIMARY` | Epistemic visibility and Health taxonomy. |
| `DGS-C03` | `SRC-DGS` · §5.5 relevance and deduplication | `MEM-006`, `DP-020` | `PRIMARY` | Consolidation plus domain relevance rules. |
| `DGS-C04` | `SRC-DGS` · §5.6 terminology | `PRES-002` | `PRIMARY` | Domain Presentation owns terminology preservation. |
| `DGS-C05` | `SRC-DGS` · §5.7 domain barriers | `ARC-006` | `EXISTING` | Phase 10.15 owns the permission boundary. |
| `DGS-C06` | `SRC-DGS` · §5.8 question behaviour | `ARC-001`, `ARC-003` | `ABSTRACTED` | Question and urgency decisions are upstream of Presentation. |
| `DGS-C07` | `SRC-DGS` · §§6–9 real document generation | `F11-002` | `DEFERRED` | Renderer and artifact concern. |
| `DGS-C08` | `SRC-DGS` · §10 transversal rules | `ARC-001`–`ARC-008`, `PRES-001`–`PRES-008`, `F11-001`–`F11-005` | `DUPLICATE` | Consolidates prompt clauses covered individually. |
| `DGS-C09` | `SRC-DGS` · §11 domain profiles | `DP-019`–`DP-030` | `PRIMARY` | Source for pack-specific backlog. |
| `DGS-C10` | `SRC-DGS` · §12 alternate context and claim contracts | `MEM-001`–`MEM-003` | `DISCARDED` | Would duplicate Phase 8 semantic contracts. |
| `DGS-C11` | `SRC-DGS` · §§12–15 document contracts and errors | `F11-002`, `F11-006` | `DEFERRED` | Platform document generation and versioning. |
| `DGS-C12` | `SRC-DGS` · §17 tests | `PRES-001`–`PRES-008`, `MEM-001`–`MEM-011`, `F11-002`, `F11-005`, `F11-006` | `PRIMARY` | Tests are reassigned to their architectural owners. |
| `DGS-C13` | `SRC-DGS` · §18 templates | `PRES-001`, `F11-002` | `ABSTRACTED` | Logical presentation template versus rendered artifact. |
| `DGS-C14` | `SRC-DGS` · §19 source-specific actions | `DATA-002`, `F11-006` | `DATA_EXTRACTED` | Source state and artifact corrections are not core contracts. |

## 6. Phase 10.15 preflight coverage

| `clause_id` | Source section | Canonical requirement(s) | State | Justification |
|---|---|---|---|---|
| `PF-C01` | `SRC-PF1015` · §§1–3 verdict and reconciliation | `ARC-001`–`ARC-008`, `DP-019`–`DP-030` | `EXISTING` | Confirms no reopening of completed Phase 10 infrastructure. |
| `PF-C02` | `SRC-PF1015` · §4 P-01–P-10 | `ARC-006`, `MEM-008` | `EXISTING` | Phase 10.15 permission requirements are closed. |
| `PF-C03` | `SRC-PF1015` · §6 C-01 | `ARC-001` | `PRIMARY` | Resolves conflicting question policies. |
| `PF-C04` | `SRC-PF1015` · §6 C-02–C-03 | `ARC-005`, `ARC-006`, `F11-004` | `PRIMARY` | Abstracts automatic external updates and universal source claims. |
| `PF-C05` | `SRC-PF1015` · §6 C-04–C-05 | `ARC-008`, `DATA-001`–`DATA-005` | `PRIMARY` | Mutable state and private values leave prompts. |
| `PF-C06` | `SRC-PF1015` · §8 deferred scope | `PRES-001`–`PRES-008`, `TRACE-001`–`TRACE-006`, `MEM-001`–`MEM-011`, `DP-019`–`DP-030`, `F11-001`–`F11-007` | `DECOMPOSED` | The v2 matrix corrects the earlier coarse phase boundaries. |

## 7. Roadmap coverage

| `clause_id` | Source section | Canonical requirement(s) | State | Justification |
|---|---|---|---|---|
| `R10-C16` | `SRC-R10` · Phase 10.16 Domain Presentation | `PRES-001`–`PRES-008` | `DECOMPOSED` | Cognitive decisions and real rendering are removed from the phase. |
| `R10-C17` | `SRC-R10` · Phase 10.17 Domain Trace | `TRACE-001`–`TRACE-006`, `F11-003`, `F11-007` | `DECOMPOSED` | Domain participation is separated from existing and platform traces. |
| `R10-C18` | `SRC-R10` · Phase 10.18 Domain Memory Integration | `MEM-001`–`MEM-011` | `DECOMPOSED` | Integration is mapped onto Phase 8/9 contracts. |
| `R10-C18-ERRATA` | `SRC-R10` · Phase 10.18 fragmentation-prevention list | — | `DISCARDED` | The apparent permission to create independent copies contradicts the section objective and shared architecture. |
| `R10-C19-C30` | `SRC-R10` · Phases 10.19–10.30 | `DP-019`–`DP-030` | `PRIMARY` | Defines the sequential Domain Pack set. |
| `RM-C10` | `SRC-RM` · Phase 10 overview | `ARC-001`–`ARC-008`; final order | `PRIMARY` | Establishes shared architecture and phase boundary. |
| `R11-C55` | `SRC-R11` · Phase 11.55 Communication Profiles | `F11-001`, `F11-002` | `PRIMARY` | Separates communication style and renderer from 10.16. |

## 8. Final coverage check

The counts below cover the 102 prompt clauses and 50 specification, preflight, and roadmap clauses listed above.

```text
total_clauses = 152
covered_clauses = 152
unclassified_clauses = 0
duplicate_primary_mappings = 0
```

Interpretation:

- every `clause_id` appears exactly once in a coverage table;
- every row has exactly one allowed coverage state;
- a `DECOMPOSED` clause may map to several requirements without acquiring multiple states;
- no source clause is silently omitted;
- no private source value is required to verify coverage because source identity is preserved by SHA-256.
