# 🧠 Phase 8 — Cognitive Layer

## Objective

Build the shared cognitive infrastructure that enables CMM OS to transform dispersed information into structured, traceable, temporally valid, and reusable knowledge.

The Cognitive Layer will not be an autonomous agent and will not execute actions on its own initiative. It will be the shared layer that future agents, domains, workflows, and interfaces use to:

* gather relevant information;
* distinguish facts, inferences, hypotheses, and opinions;
* detect contradictions;
* evaluate source reliability;
* preserve uncertainty;
* check the temporal validity of knowledge;
* identify missing information;
* formulate questions;
* produce reasoned results;
* structurally justify its conclusions;
* maintain long cognitive sessions;
* update memory without degrading its epistemological quality.

CMM OS must not be limited to retrieving stored information. It must be able to explain what it knows, where that knowledge comes from, what it has inferred, what remains uncertain, and what information it needs before reaching a conclusion.

⸻

## General Architecture

Resources
↓
Resource Adapters
↓
Knowledge Extraction
↓
Knowledge Model
↓
Knowledge Store
↓
Knowledge Graph
↓
Reasoning Context
↓
Reasoning Rules
↓
Reasoning Profile
↓
Reasoning Engine
↓
Information Gap Analysis
↓
Interactive Question Engine
↓
Reasoning Result
↓
Reasoning Trace
↓
Session Context
↓
Memory Update Proposal

The Cognitive Layer must be usable:

* from the conversational UI;
* from the CLI;
* from the API;
* from workflows;
* from specialized domains;
* from the future Agent Runtime;
* on a new session;
* on a persistent session;
* with stored knowledge;
* with external resources;
* with user responses;
* with local or remote models;
* without depending on a specific AI provider.

⸻

# 8.1 — Cognitive Contracts

## Objective

Define the common contracts for the entire cognitive infrastructure before implementing concrete rules, profiles, or integrations.

## Cognitive Status

Common states of a cognitive execution:

pending
loading_resources
extracting_knowledge
reasoning
waiting_for_user
waiting_for_resource
paused
completed
cancelled
failed
insufficient_information

## Cognitive Severity

Importance levels:

info
low
medium
high
critical

## Confidence

Confidence must be represented as a normalized value between `0.0` and `1.0`.

The system must distinguish between:

* confidence declared by a source;
* confidence calculated by the system;
* source reliability;
* evidence sufficiency;
* overall result confidence.

High confidence will not turn an inference into a fact.

## Knowledge Identifier

Every persistent cognitive element must have a stable identifier.

Examples:

```python
knowledge:fact:123
resource:medical-report:456
session:reasoning:789
question:gap:321
trace:reasoning:654
```

## Cognitive Actor

Representation of the actor that creates, modifies, or validates knowledge:

```python
CognitiveActor(
    id="actor-user",
    kind="user",
    name="Christian",
    permissions=[],
    metadata={},
)
```

Initial types:

* user;
* system;
* model;
* agent;
* workflow;
* external_source;
* human_reviewer.

## Cognitive Result

Base contract for cognitive results:

```python
CognitiveResult(
    id="result-123",
    status="completed",
    objective="...",
    confidence=0.82,
    findings=[],
    trace_id="trace-123",
    session_id="session-123",
    created_at="...",
    metadata={},
)
```

⸻

# 8.2 — Resources

## Objective

Represent any available information source for reasoning in a uniform way.

Resources will not constitute independent systems per domain. All resources will share a base contract and may be specialized through adapters.

## Resource

```python
Resource(
    id="resource-123",
    domain="medical",
    kind="medical_report",
    source="local_file",
    content={},
    provenance={},
    reliability=0.92,
    temporal_scope={},
    entities=[],
    relationships=[],
    version="1",
    sensitivity="high",
    permissions=[],
    created_at="...",
    updated_at="...",
    metadata={},
)
```

## Minimum Properties

* identifier;
* domain;
* type;
* source;
* content;
* creation date;
* content date;
* ingestion date;
* authorship;
* provenance;
* reliability;
* validity;
* temporal scope;
* version;
* language;
* mentioned entities;
* detected relationships;
* sensitivity level;
* access permissions;
* integrity;
* metadata.

## Initial Resource Types

* user_message;
* conversation;
* document;
* medical_report;
* calendar_event;
* email;
* note;
* project_file;
* source_code;
* test_result;
* validation_result;
* university_record;
* opposition_plan;
* relationship_event;
* personal_preference;
* memory_entry;
* external_web_source;
* structured_dataset.

## Resource Provenance

Provenance must be represented explicitly:

```python
ResourceProvenance(
    source_type="uploaded_file",
    source_id="file-123",
    author="Hospital Example",
    retrieved_at="...",
    checksum="...",
    original_location="...",
    transformation_history=[],
    metadata={},
)
```

## Temporal Scope

```python
TemporalScope(
    observed_at="2026-07-22",
    valid_from="2026-07-22",
    valid_until=None,
    event_start=None,
    event_end=None,
    timezone="Europe/Madrid",
    recurrence=None,
    metadata={},
)
```

The system must distinguish between:

* document date;
* ingestion date;
* fact date;
* validity period;
* expiration date;
* last verification date.

## Sensitivity

Initial levels:

public
internal
personal
sensitive
highly_sensitive
restricted

## Permissions

Each resource may define:

* authorized actors;
* authorized domains;
* allowed operations;
* inference capability;
* persistence capability;
* export capability;
* permission expiration date.

⸻

# 8.3 — Resource Adapters and Knowledge Extraction

## Objective

Convert heterogeneous resources into structured knowledge without coupling the Cognitive Layer to concrete formats.

## Resource Adapter

Common contract:

```python
class ResourceAdapter:
    resource_kind: str

    def supports(self, resource: Resource) -> bool:
        ...

    def extract(
        self,
        resource: Resource,
        context: ExtractionContext,
    ) -> ExtractionResult:
        ...
```

## Initial Adapters

* UserMessageAdapter;
* ConversationAdapter;
* DocumentAdapter;
* CalendarAdapter;
* EmailAdapter;
* MemoryAdapter;
* ProjectAdapter;
* ValidationResultAdapter;
* StructuredDataAdapter.

## Extraction Context

```python
ExtractionContext(
    objective="...",
    profile="medical",
    requested_entities=[],
    requested_fields=[],
    temporal_reference="2026-07-22",
    language="es",
    permissions=[],
    metadata={},
)
```

## Extraction Result

```python
ExtractionResult(
    resource_id="resource-123",
    knowledge_items=[],
    entities=[],
    relationships=[],
    unresolved_references=[],
    warnings=[],
    confidence=0.87,
    metadata={},
)
```

## Capabilities

* extract claims;
* identify entities;
* identify relationships;
* preserve source quotes or locations;
* detect dates;
* normalize temporality;
* identify authorship;
* preserve uncertainty;
* mark ambiguous information;
* distinguish explicit text from interpretation;
* detect unresolved references;
* avoid obvious duplicates;
* produce provisional knowledge;
* allow later review.

## Restrictions

Extraction must not:

* automatically convert claims into facts;
* remove contradictory information;
* fill gaps through assumptions;
* alter the original resource;
* remove provenance;
* infer sensitive information when the profile forbids it;
* automatically persist everything extracted.

⸻

# 8.4 — Knowledge Model

## Objective

Define a common epistemological model that enables knowledge representation without confusing facts, inferences, hypotheses, opinions, or preferences.

## Knowledge Kind

Initial types:

fact
observation
inference
hypothesis
opinion
preference
goal
decision
constraint
requirement
question
contradiction
unknown
assumption
recommendation
prediction

## Definitions

### Fact

A claim directly supported by a source considered sufficient for that context.

### Observation

Information observed or declared without additional interpretation.

### Inference

A conclusion derived from one or more knowledge elements.

### Hypothesis

A possible explanation that still requires additional evidence.

### Opinion

A subjective assessment by a person, source, or system.

### Preference

A choice, inclination, or personal criterion.

### Goal

A desired future state.

### Decision

A choice adopted among several alternatives.

### Constraint

A limitation that conditions a conclusion, plan, or action.

### Requirement

A necessary condition for completing an objective.

### Question

Requested information or a pending issue.

### Contradiction

An explicit relationship between incompatible claims.

### Unknown

Relevant information whose value is not known.

### Assumption

A supposition used provisionally and marked as such.

### Recommendation

A proposed course of action, not equivalent to a decision.

### Prediction

An estimate about a future state.

## Knowledge Item

```python
KnowledgeItem(
    id="knowledge-123",
    statement="El usuario tiene una cita médica el 4 de septiembre",
    kind="fact",
    domain="medical",
    confidence=1.0,
    reliability=0.98,
    sources=["calendar:event-123"],
    evidence=[],
    derived_from=[],
    entities=[],
    relationships=[],
    temporal_scope={},
    status="active",
    version=1,
    sensitivity="high",
    permissions=[],
    created_by="actor-system",
    created_at="...",
    updated_at="...",
    metadata={},
)
```

## Minimum Properties

* identifier;
* claim;
* epistemological type;
* domain;
* confidence;
* reliability;
* sources;
* evidence;
* elements it derives from;
* entities;
* relationships;
* temporal scope;
* status;
* version;
* sensitivity;
* permissions;
* author;
* dates;
* metadata.

## Knowledge Status

Initial states:

candidate
active
superseded
invalidated
expired
disputed
archived
deleted

## Evidence

```python
Evidence(
    id="evidence-123",
    source_id="resource-123",
    location={
        "page": 4,
        "paragraph": 2,
    },
    excerpt="...",
    support_type="direct",
    strength=0.91,
    created_at="...",
    metadata={},
)
```

Support types:

* direct;
* indirect;
* corroborating;
* contradicting;
* contextual;
* missing.

## Knowledge Relation

```python
KnowledgeRelation(
    id="relation-123",
    source_id="knowledge-1",
    relation_type="supports",
    target_id="knowledge-2",
    confidence=0.9,
    sources=[],
    temporal_scope={},
    metadata={},
)
```

Initial relations:

* supports;
* contradicts;
* refines;
* supersedes;
* derived_from;
* caused_by;
* correlated_with;
* depends_on;
* part_of;
* refers_to;
* answers;
* blocks;
* enables;
* temporally_precedes;
* temporally_follows;
* same_as;
* possibly_same_as.

## Versioning

Every relevant modification must:

* create a new version;
* preserve the previous version;
* record the actor;
* record the reason;
* record the date;
* preserve the sources;
* indicate whether it replaces or invalidates previous knowledge.

## Invalidation

An element may be invalidated due to:

* temporal expiration;
* new evidence;
* user correction;
* retracted source;
* extraction error;
* resolved contradiction;
* decision change;
* preference change;
* human review.

Invalidation must not erase history.

⸻

# 8.5 — Knowledge Store

## Objective

Create a common knowledge-access service and prevent rules, domains, or agents from depending directly on a concrete database.

The `KnowledgeStore` will be a service abstraction, not a specific backend.

## Contract

```python
class KnowledgeStore:
    def add(self, item: KnowledgeItem) -> KnowledgeItem:
        ...

    def get(self, knowledge_id: str) -> KnowledgeItem | None:
        ...

    def update(self, item: KnowledgeItem) -> KnowledgeItem:
        ...

    def invalidate(
        self,
        knowledge_id: str,
        reason: str,
    ) -> KnowledgeItem:
        ...

    def search(
        self,
        query: KnowledgeQuery,
    ) -> KnowledgeSearchResult:
        ...

    def relate(
        self,
        relation: KnowledgeRelation,
    ) -> KnowledgeRelation:
        ...

    def get_history(
        self,
        knowledge_id: str,
    ) -> list[KnowledgeItem]:
        ...

    def find_contradictions(
        self,
        query: KnowledgeQuery,
    ) -> list[KnowledgeRelation]:
        ...

    def merge_candidates(
        self,
        knowledge_ids: list[str],
    ) -> MergeProposal:
        ...
```

## Knowledge Query

```python
KnowledgeQuery(
    text=None,
    kinds=[],
    domains=[],
    entities=[],
    source_ids=[],
    valid_at=None,
    minimum_confidence=None,
    statuses=["active"],
    sensitivity_levels=[],
    permissions=[],
    limit=100,
    metadata={},
)
```

## Knowledge Search Result

```python
KnowledgeSearchResult(
    items=[],
    total=0,
    query={},
    applied_filters=[],
    warnings=[],
    duration_ms=12,
    metadata={},
)
```

## Capabilities

* add knowledge;
* retrieve by identifier;
* search by text;
* search by entity;
* search by domain;
* search by temporality;
* search by provenance;
* filter by confidence;
* filter by permissions;
* retrieve versions;
* relate elements;
* detect duplicate candidates;
* invalidate;
* archive;
* compare versions;
* preserve history;
* perform hybrid searches;
* support interchangeable persistence.

## Initial Implementations

### InMemoryKnowledgeStore

For unit tests, development, and ephemeral workflows.

### PersistentKnowledgeStore

Initial persistent implementation over the existing storage infrastructure.

## Restrictions

Upper layers must not:

* directly access tables or files;
* assume a concrete backend;
* modify knowledge without versioning;
* ignore permissions;
* silently erase history;
* mix active and invalidated knowledge without indicating it.

⸻

# 8.6 — Knowledge Graph

## Objective

Represent entities, relationships, dependencies, contradictions, and temporality as a navigable knowledge network.

The Knowledge Graph will not necessarily be an independent graph database. It will be a logical model accessible through common contracts.

## Entity

```python
Entity(
    id="entity-person-123",
    type="person",
    canonical_name="...",
    aliases=[],
    attributes={},
    source_ids=[],
    confidence=0.98,
    temporal_scope={},
    sensitivity="personal",
    metadata={},
)
```

## Initial Entity Types

* person;
* organization;
* project;
* place;
* event;
* document;
* medication;
* symptom;
* diagnosis;
* university_subject;
* examination;
* goal;
* task;
* decision;
* file;
* module;
* class;
* method;
* workflow;
* resource.

## Entity Resolution

The system must be able to:

* detect possibly equivalent entities;
* preserve aliases;
* propose merges;
* avoid automatic merges when ambiguity exists;
* separate people or concepts with similar names;
* record resolution evidence.

## Graph Query

```python
GraphQuery(
    start_entities=[],
    relation_types=[],
    max_depth=3,
    valid_at=None,
    domains=[],
    include_disputed=False,
    permissions=[],
    metadata={},
)
```

## Capabilities

* traverse relationships;
* build timelines;
* retrieve dependencies;
* retrieve evidence;
* detect cycles;
* detect contradictions;
* detect isolated entities;
* relate knowledge across domains;
* preserve temporal relationships;
* represent versions;
* allow cognitive impact analysis.

## Duplication Prevention

The graph must:

* reuse existing entities;
* propose merges;
* preserve aliases;
* avoid duplicating equivalent facts;
* keep incompatible claims separate;
* not remove contradictions to simplify the model.

⸻

# 8.7 — Reasoning Context

## Objective

Represent the complete context of a cognitive execution.

## Contract

```python
ReasoningContext(
    id="reasoning-context-123",
    objective="Determinar si una medicación puede explicar un síntoma",
    profile="medical",
    session_id="session-123",
    resources=[],
    knowledge_items=[],
    entities=[],
    constraints=[],
    permissions=[],
    temporal_reference="2026-07-22",
    requested_depth="standard",
    maximum_questions=3,
    actor="actor-user",
    metadata={},
)
```

## Must Include

* objective;
* profile;
* session;
* actor;
* loaded resources;
* retrieved knowledge;
* entities;
* constraints;
* permissions;
* temporal reference;
* language;
* requested depth;
* confidence threshold;
* question limit;
* resource limit;
* allowed domains;
* prohibited actions;
* metadata.

## Reasoning Depth

Initial levels:

minimal
standard
deep
exhaustive

Depth will affect:

* number of sources;
* number of rules;
* temporal scope;
* contradiction search;
* number of hypotheses;
* maximum number of questions;
* result detail.

It may not reduce mandatory safety rules.

⸻

# 8.8 — Reasoning Rules

## Objective

Build reusable, composable, auditable cognitive rules that are independent of the language model used.

## Contract

```python
class ReasoningRule:
    name: str
    version: str
    priority: int

    def applies(
        self,
        context: ReasoningContext,
    ) -> bool:
        ...

    def evaluate(
        self,
        context: ReasoningContext,
    ) -> RuleResult:
        ...
```

## Rule Result

```python
RuleResult(
    rule_name="DetectContradictions",
    status="applied",
    findings=[],
    produced_knowledge=[],
    contradictions=[],
    gaps=[],
    confidence_delta=0.0,
    trace_entries=[],
    metadata={},
)
```

## Rule States

pending
applied
not_applicable
skipped
failed
blocked

## Initial Rules

### DistinguishFactInferenceHypothesis

Prevents mixing explicit claims with derived conclusions.

### DetectContradictions

Identifies incompatible claims.

### DetectMissingInformation

Locates necessary information that is not available.

### AskBeforeAssuming

Prevents introducing relevant assumptions when the user can be asked.

### BuildTimeline

Orders facts and events temporally.

### CompareVersions

Compares different versions of a claim, document, decision, or state.

### MergeKnowledge

Proposes consolidation of compatible knowledge.

### EvaluateConfidence

Calculates confidence from evidence, reliability, and consistency.

### CheckTemporalValidity

Checks whether information is still valid at the reference date.

### ResolveSourceConflicts

Analyzes discrepancies between sources.

### IdentifyUnsupportedClaims

Detects claims without sufficient evidence.

### SeparateObservationFromInterpretation

Separates what is described from the interpretation made.

### DetectAmbiguity

Identifies ambiguous terms, entities, or claims.

### PreserveUncertainty

Prevents removing uncertainty without evidence.

### RequireEvidenceForHighImpactClaims

Requires stronger evidence for medical, legal, financial, or high-impact claims.

### PreferPrimarySources

Prioritizes original sources when available.

### CheckSourceReliability

Evaluates the reliability of each source.

### DetectOutdatedKnowledge

Identifies potentially obsolete information.

### AvoidCircularReasoning

Detects inferences that depend on themselves.

### LimitInferenceDepth

Avoids excessive chains of uncorroborated inferences.

### RequireUserConfirmationForPersonalDecisions

Prevents recording a user's personal decision solely from an inference.

### ProtectSensitiveInference

Blocks sensitive inferences when they are not allowed.

## Rule Properties

Rules must be:

* composable;
* configurable;
* versioned;
* auditable;
* deterministic when possible;
* model-independent;
* activatable by profile;
* prioritizable;
* idempotent when appropriate;
* compatible with partial execution;
* capable of producing structured results.

## Rule Registry

Initial registry:

```text
fact_inference_hypothesis
contradictions
missing_information
ask_before_assuming
timeline
compare_versions
merge_knowledge
confidence
temporal_validity
source_conflicts
unsupported_claims
observation_interpretation
ambiguity
uncertainty
high_impact_evidence
primary_sources
source_reliability
outdated_knowledge
circular_reasoning
inference_depth
personal_decision_confirmation
sensitive_inference
```

⸻

# 8.9 — Reasoning Profiles

## Objective

Define how the system should reason depending on context without creating separate cognitive engines.

## Contract

```python
ReasoningProfile(
    name="medical",
    version="1",
    allowed_domains=["medical", "personal"],
    allowed_resource_kinds=[],
    rules=[],
    required_rules=[],
    disabled_rules=[],
    minimum_confidence=0.85,
    require_sources=True,
    allow_assumptions=False,
    allow_sensitive_inference=False,
    maximum_inference_depth=2,
    maximum_questions_per_turn=3,
    human_escalation_rules=[],
    prohibited_actions=[],
    presentation_policy={},
    metadata={},
)
```

## Properties

* name;
* version;
* allowed domains;
* allowed resources;
* active rules;
* mandatory rules;
* disabled rules;
* caution;
* minimum confidence;
* source requirement;
* allowed inference level;
* depth;
* maximum questions;
* acceptable uncertainty;
* prohibited actions;
* human escalation criteria;
* result presentation format;
* permissions;
* metadata.

## Initial Profiles

### GeneralProfile

General profile for non-specialized queries.

### MedicalProfile

Characteristics:

* high caution;
* mandatory temporal checking;
* mandatory evidence;
* restricted sensitive inferences;
* differentiation between symptom, diagnosis, and hypothesis;
* escalation when warning signs appear;
* prohibition of definitive diagnoses without sufficient basis.

### RelationshipProfile

Characteristics:

* separation between facts and interpretations;
* preservation of ambivalence;
* identification of emotions and needs;
* caution when inferring other people's intentions;
* detection of patterns without converting them into facts;
* priority to the user's declared experience.

### ReflectionProfile

Characteristics:

* open analysis;
* multiple hypotheses;
* tolerance for uncertainty;
* lower need for a single conclusion;
* emphasis on questions and temporal evolution.

### UniversityProfile

Characteristics:

* priority to verifiable academic data;
* temporality of exam sessions;
* objectives, workload, constraints, and dependencies;
* separation between observed performance and inferred capacity.

### OppositionProfile

Characteristics:

* planning;
* syllabi;
* calls;
* available workload;
* risks;
* scenarios;
* alternatives;
* review criteria.

### ProjectProfile

Characteristics:

* priority to the repository;
* documentation;
* contracts;
* validations;
* architectural decisions;
* compatibility between code and design;
* integration with Validation System.

## Profile Registry

Profiles must be registered and resolved through a common service.

## Profile Resolution

The profile may be selected through:

* explicit request;
* domain;
* resource type;
* objective;
* workflow;
* agent;
* system policy;
* automatic classification.

When material ambiguity exists, the system must:

* use a cautious general profile;
* request clarification;
* or combine profiles through an explicit policy.

⸻

# 8.10 — Reasoning Engine

## Objective

Orchestrate knowledge retrieval, rule application, confidence evaluation, contradiction detection, and cognitive result generation.

## Flow

Objective
↓
Build Reasoning Context
↓
Resolve Profile
↓
Load Resources
↓
Extract Knowledge
↓
Search Knowledge Store
↓
Apply Required Rules
↓
Apply Profile Rules
↓
Evaluate Contradictions
↓
Evaluate Temporal Validity
↓
Evaluate Confidence
↓
Detect Information Gaps
↓
Ask / Continue / Pause / Complete
↓
Generate Reasoning Result
↓
Generate Reasoning Trace

## Contract

```python
class ReasoningEngine:
    def reason(
        self,
        context: ReasoningContext,
    ) -> ReasoningResult:
        ...
```

## Reasoning Result

```python
ReasoningResult(
    id="reasoning-result-123",
    objective="...",
    status="completed",
    profile="medical",
    conclusions=[],
    facts=[],
    observations=[],
    inferences=[],
    hypotheses=[],
    contradictions=[],
    unknowns=[],
    information_gaps=[],
    questions=[],
    recommendations=[],
    confidence=0.78,
    source_ids=[],
    trace_id="trace-123",
    session_id="session-123",
    memory_update_proposal=None,
    created_at="...",
    metadata={},
)
```

## Capabilities

* reason with existing knowledge;
* incorporate new resources;
* apply mandatory rules;
* apply profile-specific rules;
* stop when information is insufficient;
* maintain several hypotheses;
* detect contradictions;
* check dates;
* evaluate sources;
* propose questions;
* generate provisional conclusions;
* return partial results;
* produce traceability;
* resume reasoning processes;
* operate without a language model when rules are deterministic;
* use external models through adapters.

## Reasoning Model Adapter

The architecture must allow the use of local or remote models without coupling the engine to a concrete one.

```python
class ReasoningModelAdapter:
    def generate_structured_reasoning(
        self,
        request: ModelReasoningRequest,
    ) -> ModelReasoningResponse:
        ...
```

The model response must be validated against structured contracts before being incorporated.

## Restrictions

The engine must not:

* execute external actions;
* automatically modify user decisions;
* persist sensitive inferences without authorization;
* remove contradictions;
* convert hypotheses into facts;
* ignore mandatory rules;
* hide missing information;
* exceed the context permissions;
* record free-form internal chains of thought.

⸻

# 8.11 — Information Gap Analysis

## Objective

Automatically detect what information is missing to reach an objective with a sufficient confidence level.

## Flow

Objective
↓
Required Knowledge
↓
Available Knowledge
↓
Temporal Validity
↓
Evidence Sufficiency
↓
Missing Information
↓
Gap Classification
↓
Question / Resource / Accept Uncertainty

## Contract

```python
InformationGapResult(
    objective="Determinar si una medicación puede explicar un síntoma",
    known_information=[],
    required_information=[],
    missing_information=[],
    blocking_gaps=[],
    optional_gaps=[],
    irrelevant_information=[],
    unresolved_unknowns=[],
    recommended_questions=[],
    recommended_resources=[],
    acceptable_uncertainty=[],
    confidence=0.71,
    metadata={},
)
```

## Information Gap

```python
InformationGap(
    id="gap-123",
    description="No se conoce la fecha exacta de inicio del síntoma",
    importance="blocking",
    resolution_type="ask_user",
    expected_answer_type="date",
    related_knowledge=[],
    related_rules=[],
    can_be_resolved=True,
    metadata={},
)
```

## Classification

### Blocking Gap

Prevents reaching a sufficiently reliable conclusion.

### Optional Gap

Would improve the analysis, but does not prevent a provisional conclusion.

### Irrelevant Information

Information that does not affect the current objective.

### User-Resolvable Gap

Can be resolved by asking the user.

### Resource-Resolvable Gap

Requires consulting a source, document, calendar, email, or service.

### Inference-Resolvable Gap

Can be resolved through an allowed and sufficiently supported inference.

### Human-Review Gap

Requires professional intervention or human review.

### Unresolvable Gap

Cannot be resolved with the available resources.

### Acceptable Uncertainty

A gap that can be preserved without blocking the result.

## Capabilities

* identify necessary information;
* compare requirements with available knowledge;
* check validity;
* detect insufficient evidence;
* classify gaps;
* prioritize gaps;
* propose questions;
* propose sources;
* distinguish essential from useful;
* recognize acceptable uncertainty;
* avoid irrelevant questions;
* detect gaps that are impossible to resolve.

⸻

# 8.12 — Interactive Question Engine

## Objective

Formulate dynamic and traceable questions to resolve detected information gaps.

## Initial Format

```text
A) ...
B) ...
C) ...
D) Otra respuesta
```

The engine must also allow open answers when closed options are insufficient.

## Question

```python
Question(
    id="question-123",
    text="¿Cuándo comenzó el síntoma?",
    kind="single_choice",
    options=[],
    related_gap_id="gap-123",
    priority=100,
    blocking=True,
    validation={},
    asked_at=None,
    answered_at=None,
    status="pending",
    metadata={},
)
```

## Question Kind

Initial types:

single_choice
multiple_choice
open_text
boolean
date
datetime
number
scale
entity_selection
confirmation

## Question Status

pending
asked
answered
skipped
expired
invalid
cancelled

## Answer

```python
Answer(
    id="answer-123",
    question_id="question-123",
    value="2026-07-10",
    raw_value="El día 10 de julio",
    confidence=1.0,
    provided_by="actor-user",
    created_at="...",
    metadata={},
)
```

## Capabilities

* prioritize blocking questions;
* limit questions per turn;
* adapt the next question;
* avoid repetitions;
* validate answers;
* allow open answers;
* allow “I don't know”;
* allow skipping;
* detect contradictions with previous answers;
* rephrase questions;
* pause;
* resume;
* finish when there is sufficient information;
* generate candidate knowledge from answers;
* link each question to a concrete gap.

## Question Policy

```python
QuestionPolicy(
    maximum_questions_per_turn=3,
    ask_blocking_first=True,
    allow_open_answers=True,
    allow_skip=True,
    repeat_unanswered=False,
    contradiction_strategy="clarify",
    metadata={},
)
```

## Prevention of Excessive Questioning

The engine must:

* group related questions;
* not ask what is already known;
* not repeat resolved questions;
* not ask for irrelevant information;
* briefly explain why a question is necessary when appropriate;
* allow continuing with a provisional conclusion;
* respect the maximum defined by the profile.

⸻

# 8.13 — Contradiction Detection and Conflict Resolution

## Objective

Detect, represent, and manage incompatible claims without arbitrarily removing information.

## Contradiction

```python
Contradiction(
    id="contradiction-123",
    knowledge_ids=["knowledge-1", "knowledge-2"],
    kind="direct",
    severity="medium",
    status="open",
    possible_causes=[],
    preferred_resolution=None,
    confidence=0.89,
    metadata={},
)
```

## Initial Types

direct
temporal
source_conflict
version_conflict
entity_conflict
semantic_conflict
scope_conflict
apparent

## Possible Causes

* temporal change;
* different dates;
* sources with different reliability;
* extraction error;
* ambiguity;
* different meanings;
* later correction;
* partial information;
* subjective claim;
* real contradiction.

## States

open
under_review
resolved
accepted
superseded
dismissed

## Conflict Resolution Proposal

```python
ConflictResolutionProposal(
    contradiction_id="contradiction-123",
    strategy="prefer_newer_verified_source",
    preferred_knowledge_id="knowledge-2",
    rejected_knowledge_ids=[],
    confidence=0.81,
    requires_user_confirmation=False,
    explanation={},
    metadata={},
)
```

## Initial Strategies

* prefer primary source;
* prefer more reliable source;
* prefer verified information;
* prefer later version;
* distinguish temporal periods;
* separate scopes;
* request clarification;
* keep both claims;
* escalate to human review.

## Restrictions

The system must not:

* automatically resolve sensitive contradictions without sufficient basis;
* delete the discarded claim;
* hide disagreements between sources;
* use only the ingestion date;
* assume that the newest source is always correct.

⸻

# 8.14 — Temporal Reasoning

## Objective

Enable CMM OS to reason about dates, periods, sequences, validity, and temporal evolution.

## Initial Capabilities

* order events;
* build timelines;
* distinguish fact date and record date;
* check validity;
* detect expiration;
* detect overlaps;
* compare previous and current states;
* detect changes;
* resolve relative expressions;
* identify potentially obsolete information;
* relate cause and sequence without confusing them;
* preserve time zones;
* manage open intervals.

## Temporal Relation

```python
TemporalRelation(
    source_id="knowledge-1",
    relation="before",
    target_id="knowledge-2",
    confidence=1.0,
    metadata={},
)
```

Initial relations:

before
after
during
overlaps
starts
ends
contains
same_time
unknown_order

## Timeline

```python
Timeline(
    id="timeline-123",
    objective="Evolución del síntoma",
    events=[],
    gaps=[],
    contradictions=[],
    start=None,
    end=None,
    confidence=0.9,
    metadata={},
)
```

## Rules

When a date is imprecise, the system must preserve:

* possible interval;
* precision level;
* original expression;
* normalized interpretation;
* confidence.

Example:

```python
TemporalValue(
    raw="a principios de julio",
    earliest="2026-07-01",
    latest="2026-07-10",
    precision="approximate",
    confidence=0.75,
)
```

⸻

# 8.15 — Confidence Evaluation

## Objective

Calculate the confidence of claims and results without hiding uncertainty or oversimplifying it.

## Initial Factors

* epistemological type;
* number of sources;
* source independence;
* reliability;
* direct evidence;
* corroboration;
* contradictions;
* temporal validity;
* inference depth;
* ambiguity;
* missing information;
* user review;
* human review;
* consistency with existing knowledge.

## Confidence Evaluation

```python
ConfidenceEvaluation(
    target_id="knowledge-123",
    score=0.82,
    source_reliability_score=0.9,
    evidence_score=0.85,
    temporal_validity_score=1.0,
    consistency_score=0.72,
    inference_penalty=0.05,
    contradiction_penalty=0.1,
    missing_information_penalty=0.08,
    reasons=[],
    metadata={},
)
```

## Rules

* no inference will have higher confidence than all its evidence without justification;
* each inference level may reduce confidence;
* duplicate sources will not count as independent sources;
* a user claim may be a fact about what the user declared, but not necessarily about external reality;
* the absence of contradiction will not be equivalent to confirmation;
* confidence will never replace epistemological type;
* scores must be explainable.

⸻

# 8.16 — Reasoning Trace

## Objective

Produce a structured, auditable, and safe justification for each result without storing free-form internal chains of thought.

## Contract

```python
ReasoningTrace(
    id="trace-123",
    objective="...",
    profile="medical",
    facts=[],
    observations=[],
    inferences=[],
    hypotheses=[],
    contradictions=[],
    missing_information=[],
    applied_rules=[],
    skipped_rules=[],
    source_ids=[],
    evidence_ids=[],
    confidence_evaluations=[],
    decisions=[],
    questions=[],
    warnings=[],
    started_at="...",
    completed_at="...",
    duration_ms=420,
    metadata={},
)
```

## Applied Rule Trace

```python
AppliedRuleTrace(
    rule_name="CheckTemporalValidity",
    rule_version="1",
    status="applied",
    inputs=[],
    outputs=[],
    findings=[],
    duration_ms=4,
    metadata={},
)
```

## Must Allow Answering

* what is known;
* what was observed;
* where it comes from;
* what was inferred;
* what remains a hypothesis;
* what contradictions exist;
* what information is missing;
* what rules were applied;
* what rules were skipped;
* what sources were used;
* with what confidence the result was obtained;
* why the system decided to ask, pause, or conclude.

## Restrictions

Traceability must not store:

* free-form internal chains of thought;
* token-by-token reasoning;
* secrets;
* credentials;
* unnecessary sensitive content;
* private system prompts;
* information outside the session permissions.

Traceability will be a structured explanation based on:

* inputs;
* rules;
* evidence;
* results;
* observable decisions.

⸻

# 8.17 — Session Context

## Objective

Persist long cognitive workflows and allow pausing, resuming, and continuing a reasoning process without losing context.

## Session State

Possible states:

created
active
waiting_for_user
waiting_for_resource
paused
completed
cancelled
failed

## Contract

```python
SessionContext(
    id="session-123",
    objective="...",
    status="active",
    profile="medical",
    domain="medical",
    resources=[],
    knowledge_ids=[],
    questions=[],
    answers=[],
    pending_gaps=[],
    open_contradictions=[],
    decisions=[],
    operations=[],
    current_result_id=None,
    current_trace_id=None,
    next_recommended_step=None,
    workflow_version="1",
    created_at="...",
    updated_at="...",
    paused_at=None,
    completed_at=None,
    metadata={},
)
```

## Must Store

* objective;
* state;
* active profile;
* domain;
* loaded resources;
* knowledge used;
* questions asked;
* answers received;
* pending gaps;
* open contradictions;
* decisions made;
* executed operations;
* partial results;
* traces;
* next step;
* pause reason;
* timestamps;
* workflow version;
* actor;
* permissions;
* metadata.

## Capabilities

* create session;
* update;
* pause;
* resume;
* cancel;
* complete;
* retrieve state;
* avoid repeating questions;
* revalidate temporal information;
* migrate version;
* detect abandoned sessions;
* relate sessions;
* generate a resumption summary.

## Resumption

When resuming a session, the system must:

* retrieve the objective;
* check permissions;
* check temporal validity;
* detect modified resources;
* detect invalidated knowledge;
* retrieve pending questions;
* retrieve contradictions;
* reconstruct the next step;
* record a new update.

⸻

# 8.18 — Memory Integration

## Objective

Integrate the Cognitive Layer with existing memory without degrading the quality of persistent knowledge.

## General Principle

Not every cognitive result should become memory.

The Cognitive Layer must generate update proposals that will later be evaluated by memory policies.

## Memory Update Proposal

```python
MemoryUpdateProposal(
    id="memory-proposal-123",
    session_id="session-123",
    additions=[],
    updates=[],
    invalidations=[],
    relations=[],
    decisions=[],
    rejected_items=[],
    requires_user_confirmation=False,
    confidence=0.88,
    reasons=[],
    metadata={},
)
```

## Persistence Candidates

* stable facts;
* durable preferences;
* explicit decisions;
* goals;
* constraints;
* relationships between entities;
* verified knowledge;
* relevant contradictions;
* user corrections;
* workflow results.

## Elements That Must Not Be Automatically Persisted

* weak hypotheses;
* sensitive inferences;
* momentary opinions;
* irrelevant information;
* provisional answers;
* duplicated content;
* knowledge without provenance;
* already expired temporal information;
* rejected conclusions;
* internal chains of thought.

## Integration with Episodic Memory

The following may be persisted:

* relevant sessions;
* questions asked;
* decisions;
* results;
* events;
* state changes;
* accepted conclusions.

## Integration with Semantic Memory

The following may be persisted:

* facts;
* preferences;
* goals;
* constraints;
* entities;
* relationships;
* consolidated knowledge;
* versions;
* open contradictions.

## User Confirmation

It will be mandatory when:

* a non-explicit personal decision is recorded;
* an important preference is modified;
* information provided by the user is invalidated;
* a sensitive inference is stored;
* material ambiguity exists;
* the profile requires it.

⸻

# 8.19 — Security, Privacy, and Cognitive Permissions

## Objective

Prevent improper access, unauthorized sensitive inferences, and propagation of knowledge outside its permitted context.

## Cognitive Permission Policy

```python
CognitivePermissionPolicy(
    allowed_domains=[],
    allowed_resource_kinds=[],
    allowed_sensitivity_levels=[],
    allow_cross_domain_reasoning=False,
    allow_sensitive_inference=False,
    allow_memory_write=False,
    allow_external_model=False,
    allow_external_search=False,
    require_user_confirmation=[],
    metadata={},
)
```

## Mandatory Measures

* access control by resource;
* access control by knowledge item;
* permissions by session;
* isolation between users;
* filtering by sensitivity;
* data minimization;
* access traceability;
* secret redaction;
* encryption at rest;
* prohibition of unauthorized sensitive inferences;
* authorization for memory writes;
* authorization for external model use;
* protection against prompt injection in resources;
* validation of structured outputs;
* depth limits;
* resource limits;
* question limits;
* safe cancellation.

## Prompt Injection and Untrusted Content

External resources must be considered data, not instructions.

The system must:

* separate content from instructions;
* ignore commands embedded in documents;
* mark untrusted resources;
* prevent permission changes from a resource;
* prevent a source from disabling rules;
* prevent a source from requesting secrets;
* record manipulation attempts.

## Sensitive Inferences

Inferences must not be made automatically about:

* health;
* sexual orientation;
* religion;
* political affiliation;
* ethnic origin;
* identity;
* financial information;
* background history;
* precise location;
* intimate relationships;

unless:

* they are necessary for the objective;
* they are allowed by the profile;
* there is sufficient basis;
* permissions allow it;
* and they are kept as inferences, not facts.

## Separation of Responsibilities

The Cognitive Layer may:

* analyze;
* classify;
* infer;
* detect gaps;
* ask questions;
* propose;
* update knowledge when authorized.

It may not by itself:

* send communications;
* publish;
* execute external operations;
* modify files;
* create commitments;
* make personal decisions;
* make diagnoses;
* make payments;
* modify permissions;
* execute irreversible actions.

⸻

# 8.20 — Observability and Persistence

## Objective

Preserve enough information to understand, audit, and improve cognitive executions.

## Data to Record

* execution identifier;
* objective;
* actor;
* profile;
* domain;
* loaded resources;
* retrieved knowledge;
* applied rules;
* skipped rules;
* contradictions;
* gaps;
* questions;
* answers;
* confidence;
* duration;
* result;
* traceability;
* errors;
* proposed memory updates;
* timestamps.

## Logs

Logs must be:

* structured;
* readable;
* filterable;
* persistable;
* linked to sessions;
* suitable for humans and agents;
* free of secrets;
* respectful of permissions;
* configurable by level.

## Initial Metrics

* total duration;
* duration per rule;
* processed resources;
* extracted knowledge;
* reused knowledge;
* detected contradictions;
* detected gaps;
* questions asked;
* questions avoided;
* completed sessions;
* paused sessions;
* average confidence;
* results with insufficient information;
* accepted memory proposals;
* rejected proposals;
* errors by adapter;
* errors by profile;
* most-used rules.

## Persistence

A storage abstraction must exist for:

* resources;
* knowledge;
* entities;
* relationships;
* versions;
* traces;
* sessions;
* questions;
* answers;
* contradictions;
* results;
* metrics.

The initial implementation may use existing persistence and later evolve without modifying public contracts.

⸻

# 8.21 — CLI and API

## CLI

Initial commands:

```text
cmm cognitive reason
cmm cognitive reason --profile medical
cmm cognitive reason --objective "..."
cmm cognitive reason --resource <resource-id>
cmm cognitive inspect <result-id>
cmm cognitive trace <trace-id>
cmm cognitive session create
cmm cognitive session inspect <session-id>
cmm cognitive session resume <session-id>
cmm cognitive session pause <session-id>
cmm cognitive session cancel <session-id>
cmm cognitive knowledge get <knowledge-id>
cmm cognitive knowledge search
cmm cognitive contradictions
cmm cognitive gaps <session-id>
cmm cognitive questions <session-id>
```

## CLI Capabilities

* start reasoning;
* select profile;
* specify objective;
* attach resources;
* continue sessions;
* answer questions;
* query results;
* inspect traces;
* search knowledge;
* show contradictions;
* show gaps;
* human-readable output;
* JSON output;
* verbose mode;
* silent mode.

## API

The API must allow:

* create resources;
* query resources;
* start reasoning processes;
* query state;
* cancel;
* pause;
* resume;
* answer questions;
* obtain results;
* obtain traces;
* query knowledge;
* query entities;
* query relationships;
* query contradictions;
* obtain gaps;
* generate memory proposals;
* approve or reject updates;
* select profiles;
* configure permissions;
* integrate future agents.

## Output Contracts

The CLI and API must use the same internal contracts.

There must not be incompatible results between:

* local;
* API;
* workflows;
* agents;
* domains.

⸻

# 8.22 — Integration with the Existing System

## Kernel

The Cognitive Layer must emit events:

```text
cognitive.reasoning.started
cognitive.resources.loaded
cognitive.extraction.completed
cognitive.rule.started
cognitive.rule.completed
cognitive.contradiction.detected
cognitive.gap.detected
cognitive.question.created
cognitive.answer.received
cognitive.reasoning.paused
cognitive.reasoning.resumed
cognitive.reasoning.completed
cognitive.reasoning.failed
cognitive.memory.proposed
cognitive.memory.updated
```

## Planner

Plans may include cognitive nodes:

```text
Load Resources
        ↓
Reason
        ↓
Detect Gaps
        ↓
Ask User / Load Resource
        ↓
Resume Reasoning
        ↓
Produce Result
```

The Planner must not implement its own reasoning.

## Execution Engine

The executor must be able to:

* start a cognitive execution;
* pause on questions;
* resume with answers;
* collect results;
* stop workflows;
* propagate structured errors;
* maintain session context.

## Semantic Engine

The Cognitive Layer may use:

* indexes;
* references;
* entities;
* relationships;
* structural analysis;
* impact;
* semantic operation results.

Example:

```text
Semantic Transformation
        ↓
Validation Result
        ↓
Cognitive Analysis
        ↓
Decision Support
```

## Validation System

The Cognitive Layer may interpret:

* executed steps;
* findings;
* errors;
* warnings;
* artifacts;
* affected tests;
* impact confidence;
* commit gate result.

It must not analyze only free-form logs when structured results exist.

## Memory

The integration must allow:

* retrieve knowledge;
* check versions;
* propose updates;
* invalidate obsolete information;
* maintain provenance;
* preserve contradictions;
* differentiate episodic and semantic memory.

## Future Agent Runtime

The Phase 9 agent must use the Cognitive Layer to decide:

```text
Continue
Ask user
Load resource
Search
Infer
Plan
Pause
Escalate
Complete
```

The agent must not duplicate:

* cognitive rules;
* profiles;
* gap analysis;
* question engine;
* traceability;
* confidence evaluation.

## Future Domain Intelligence

The Phase 10 domains must provide:

* resources;
* profiles;
* rules;
* permissions;
* operations;
* workflows;

without creating a different Knowledge Model or an independent cognitive engine.

⸻


# 8.23 — Knowledge Packages

**Status: Implemented in CMM OS.** The canonical `KnowledgePackage`,
`KnowledgePackageRequest`, and `KnowledgePackageBuilder` contracts are provider-
independent, immutable, deterministic, and built on the existing Knowledge
Store/retrieval model. The implementation is intentionally limited to the
JSON-compatible canonical representation: 8.24 adds cognitive caching, 8.25
expands privacy metadata, 8.26 integrates structural validation, 10.49 adds
domain-specialized schemas, and 11.43 adds external exports.

## Objective

Create a structured, portable, traceable, and provider-independent representation of the context supplied to models, workflows, domains, agents, or external clients.

A `KnowledgePackage` must contain only information relevant to the current objective while preserving epistemological type, provenance, temporal validity, permissions, privacy, and uncertainty.

## Contract

```python
KnowledgePackage(
    id="knowledge-package-123",
    objective="...",
    profile="medical",
    domain="health",
    session_id="session-123",
    current_state=[],
    timeline=[],
    active_goals=[],
    facts=[],
    observations=[],
    inferences=[],
    hypotheses=[],
    contradictions=[],
    unknowns=[],
    constraints=[],
    preferences=[],
    relevant_memory=[],
    prior_reasoning=[],
    resources=[],
    missing_information=[],
    reasoning_profile={},
    domain_instructions={},
    privacy={},
    temporal_scope={},
    provenance=[],
    created_at="...",
    valid_until=None,
    metadata={},
)
```

## Required Capabilities

* build packages from resources and structured knowledge;
* select only context relevant to the objective;
* preserve facts, observations, inferences, hypotheses, and uncertainty separately;
* preserve provenance and temporal validity;
* include contradictions and missing information;
* apply permissions and privacy before inclusion;
* exclude unauthorized or irrelevant information;
* serialize, validate, version, reuse, and export packages;
* remain independent from any model or provider;
* support domain specialization in Phase 10.

## Restrictions

A Knowledge Package must not:

* include the complete Knowledge Store by default;
* flatten epistemological types into unstructured text;
* hide contradictions or uncertainty;
* expose secrets or restricted information;
* depend on one provider format;
* become permanently valid without version and expiry controls.

⸻

# 8.24 — Cognitive Cache

**Status: implemented** (`cmm/cognitive/cognitive_cache.py`, `tests/cognitive/test_cognitive_cache.py`).

## Objective

Reuse verified cognitive work without treating cached results as permanently valid or independent from their original context.

8.24 caches structured, traceable cognitive artifacts (materialized knowledge, verified summaries, structured reasoning results, document analyses, detected contradictions, resolved questions, cognitive plans, validated conclusions, Knowledge Packages, and other reusable intermediate results). **It never caches prompts or tokens** — provider prompt caching, token-prefix reuse, cached-token accounting, and cache-hit billing are Phase 11.42 concerns and are explicitly out of scope here.

8.25 will expand the privacy and sensitivity metadata this cache enforces today only at the level of `SensitivityLevel` and `ResourcePermission` reuse. 8.26 will integrate the Phase 7 Validation Pipeline into cache revalidation (`CognitiveCacheValidator` is a structural-only extension point today, and never invokes a model). Phase 10 may specialize cache invalidation and revalidation policy per domain. Phase 11.42 will add the provider-facing prompt cache and prompt/token optimization layer, which is a distinct concern from this cognitive-artifact cache.

## Cacheable Elements

* materialized knowledge;
* verified summaries;
* structured reasoning results;
* document analyses;
* detected contradictions;
* resolved questions;
* cognitive plans;
* validated conclusions;
* Knowledge Packages;
* reusable intermediate results.

## Cache Entry

```python
CognitiveCacheEntry(
    id="cognitive-cache-123",
    key="...",
    kind="knowledge_package",
    value={},
    source_ids=[],
    dependency_ids=[],
    context_signature="...",
    profile_version="...",
    domain_version=None,
    model_metadata={},
    confidence=0.9,
    created_at="...",
    last_validated_at="...",
    valid_until=None,
    invalidation_keys=[],
    sensitivity="personal",
    permissions=[],
    status="valid",
    metadata={},
)
```

Each entry must preserve:

* creation and validation dates;
* sources and dependencies;
* context of application;
* temporal validity;
* confidence;
* invalidation keys;
* reasoning-profile version;
* domain version when applicable;
* model or process metadata;
* sensitivity, permissions, and provenance.

The cache must revalidate or invalidate entries when sources, dependencies, permissions, profiles, domain policies, schemas, temporal validity, or relevant knowledge change.

It must never bypass permissions, conceal reuse, return stale data as current, or treat model output as established truth.

⸻

# 8.25 — Privacy and Sensitivity Metadata

## Objective

Propagate privacy requirements from resources and knowledge through reasoning, caching, Knowledge Packages, model requests, workflows, exports, and external integrations.

## Initial Policies

```text
LOCAL_ONLY
LOCAL_PREFERRED
REMOTE_ALLOWED
PREMIUM_ALLOWED
SENSITIVE
```

These policies complement existing sensitivity levels and do not replace them.

## Privacy Metadata

```python
PrivacyMetadata(
    policy="LOCAL_PREFERRED",
    sensitivity="high",
    allowed_processing_locations=["local"],
    allowed_providers=[],
    prohibited_providers=[],
    allow_remote=False,
    allow_premium=False,
    allow_cache=True,
    allow_export=False,
    requires_redaction=False,
    requires_approval=False,
    inherited_from=[],
    metadata={},
)
```

Privacy metadata must propagate through:

```text
Resource
↓
Knowledge Item
↓
Reasoning Context
↓
Cognitive Result
↓
Knowledge Package
↓
Cache Entry
↓
Model Request
↓
Workflow
↓
Export
```

The effective policy must be the most restrictive applicable policy unless an explicitly authorized exception exists.

The system must prevent `LOCAL_ONLY` information from leaving the local runtime, prefer local processing for `LOCAL_PREFERRED`, record exclusions and transmissions, and block unauthorized caching, export, or remote processing.

⸻

# 8.26 — Structural Cognitive Validation

## Objective

Validate cognitive inputs and outputs before they are trusted, cached, exported, persisted, or supplied to a model.

This complements Phase 7 validation and the response-validation layer planned for Phase 11.

## Validation Checks

* consistency between facts;
* explicit contradictions;
* temporal validity;
* missing information;
* insufficient evidence;
* separation between fact and inference;
* schema compliance;
* Knowledge Package completeness;
* provenance and conclusion traceability;
* privacy and sensitivity compliance;
* safe cache reuse;
* permission compatibility;
* dependency and profile compatibility.

## Validation Result

```python
CognitiveValidationResult(
    id="cognitive-validation-123",
    target_id="knowledge-package-123",
    status="passed",
    findings=[],
    blocking_findings=[],
    warnings=[],
    validated_rules=[],
    privacy_result={},
    temporal_result={},
    provenance_result={},
    cache_result=None,
    created_at="...",
    metadata={},
)
```

Possible decisions:

```text
accept
accept_with_warning
repair
rebuild
invalidate
block
request_information
request_approval
escalate
```

## Phase 7 Integration

Possible structured validation steps:

```text
cognitive.schema
cognitive.provenance
cognitive.temporality
cognitive.epistemology
cognitive.contradictions
cognitive.privacy
cognitive.knowledge_package
cognitive.cache
```

Validation must not silently alter facts, remove contradictions, promote hypotheses to facts, infer missing sensitive information, or authorize prohibited remote processing.

⸻

# 8.27 — Implementation Order


## Block 1 — Cognitive Contracts

* CognitiveStatus;
* CognitiveSeverity;
* CognitiveActor;
* Confidence;
* identifiers;
* base results;
* serialization;
* errors;
* unit tests.

## Block 2 — Knowledge Model

* KnowledgeKind;
* KnowledgeStatus;
* KnowledgeItem;
* Evidence;
* KnowledgeRelation;
* TemporalScope;
* versioning;
* invalidation;
* unit tests.

## Block 3 — Knowledge Store

* interface;
* InMemoryKnowledgeStore;
* searches;
* versioning;
* invalidation;
* relations;
* history;
* unit tests.

## Block 4 — Resources

* Resource;
* ResourceProvenance;
* sensitivity;
* permissions;
* temporality;
* resource registry;
* unit tests.

## Block 5 — Resource Adapters

* contract;
* Adapter Registry;
* UserMessageAdapter;
* ConversationAdapter;
* DocumentAdapter;
* MemoryAdapter;
* StructuredDataAdapter;
* ExtractionResult;
* integration tests.

## Block 6 — Knowledge Graph

* Entity;
* EntityRelation;
* Entity Resolution;
* GraphQuery;
* traversals;
* duplicate detection;
* basic timeline;
* unit tests.

## Block 7 — Reasoning Trace

* ReasoningTrace;
* AppliedRuleTrace;
* persistence;
* query;
* sensitive-information redaction;
* unit tests.

## Block 8 — Reasoning Rules

* contract;
* Rule Registry;
* DistinguishFactInferenceHypothesis;
* DetectContradictions;
* CheckTemporalValidity;
* EvaluateConfidence;
* DetectAmbiguity;
* PreserveUncertainty;
* IdentifyUnsupportedClaims;
* unit tests.

## Block 9 — Reasoning Profiles

* contract;
* Profile Registry;
* GeneralProfile;
* MedicalProfile;
* RelationshipProfile;
* ReflectionProfile;
* UniversityProfile;
* OppositionProfile;
* ProjectProfile;
* profile resolution;
* unit tests.

## Block 10 — Reasoning Engine

* ReasoningContext;
* orchestration;
* knowledge loading;
* rule execution;
* results;
* trace integration;
* model adapter;
* output validation;
* integration tests.

## Block 11 — Information Gap Analysis

* InformationGap;
* classification;
* Required Knowledge;
* sufficiency analysis;
* blocking gaps;
* optional gaps;
* recommendations;
* unit tests.

## Block 12 — Interactive Question Engine

* Question;
* Answer;
* QuestionPolicy;
* prioritization;
* validation;
* adaptation;
* pause;
* resumption;
* integration tests.

## Block 13 — Contradictions and Temporality

* Contradiction;
* resolution;
* CompareVersions;
* BuildTimeline;
* TemporalRelation;
* validity;
* obsolete knowledge;
* unit tests.

## Block 14 — Session Context

* creation;
* update;
* pause;
* resumption;
* cancellation;
* persistence;
* migration;
* resumption summary;
* integration tests.

## Block 15 — Memory Integration

* MemoryUpdateProposal;
* policies;
* approval;
* rejection;
* update;
* invalidation;
* episodic memory;
* semantic memory;
* integration tests.

## Block 16 — Security

* CognitivePermissionPolicy;
* sensitivity;
* isolation;
* prompt injection;
* secret protection;
* sensitive inferences;
* external models;
* cognitive limits;
* audit.

## Block 17 — Observability

* logs;
* metrics;
* history;
* traces;
* sessions;
* persistence;
* redaction;
* tests.

## Block 18 — Interfaces

* CLI;
* API;
* JSON output;
* knowledge query;
* sessions;
* questions;
* answers;
* traces;
* contradictions.

## Block 19 — Final Integration

* Kernel;
* Planner;
* Execution Engine;
* Semantic Engine;
* Validation System;
* Memory;
* workflows;
* E2E tests;
* documentation;
* global suite.

⸻

# Expected Capabilities

* register heterogeneous resources;
* preserve provenance;
* extract knowledge;
* distinguish facts, observations, inferences, and hypotheses;
* store versioned knowledge;
* invalidate obsolete information;
* preserve history;
* relate knowledge;
* build a logical graph;
* resolve entities;
* detect duplicate candidates;
* detect contradictions;
* compare sources;
* compare versions;
* check temporal validity;
* build timelines;
* evaluate reliability;
* evaluate confidence;
* preserve uncertainty;
* detect unsupported claims;
* detect ambiguity;
* limit inference depth;
* load profiles;
* apply rules;
* produce structured results;
* detect missing information;
* distinguish blocking and optional gaps;
* formulate dynamic questions;
* avoid repeated questions;
* validate answers;
* pause and resume;
* maintain long sessions;
* generate structured traceability;
* propose memory updates;
* require confirmation when appropriate;
* protect sensitive information;
* be reused from CLI, API, workflows, domains, and agents;
* use local or remote models;
* maintain provider independence;
* function with deterministic rules;
* generate human- and machine-readable results;
* maintain complete traceability.

⸻

# Security

* permission control by resource;
* permission control by knowledge item;
* permission control by session;
* isolation between users;
* sensitivity classification;
* data minimization;
* encryption at rest;
* logs without secrets;
* protection against prompt injection;
* separation between data and instructions;
* external models disabled unless authorized;
* restricted sensitive inferences;
* controlled memory writes;
* confirmation for personal decisions;
* resource limits;
* question limits;
* depth limits;
* temporal limits;
* safe cancellation;
* access traceability;
* logical and versioned deletion;
* no external actions;
* no autonomous execution;
* no irreversible modifications;
* human review for high-impact results.

⸻

# Tests

## Unit

* contracts;
* serialization;
* KnowledgeKind;
* KnowledgeItem;
* Evidence;
* KnowledgeRelation;
* temporality;
* versioning;
* invalidation;
* KnowledgeStore;
* searches;
* entities;
* entity resolution;
* rules;
* profiles;
* confidence;
* contradictions;
* gaps;
* questions;
* answers;
* sessions;
* permissions;
* traces.

## Integration

* resource to knowledge;
* adapters;
* extraction;
* persistent Knowledge Store;
* Knowledge Graph;
* Reasoning Engine;
* rules and profiles;
* gap analysis;
* question engine;
* temporality;
* sessions;
* memory;
* Kernel;
* Planner;
* Executor;
* Validation System;
* CLI;
* API.

## E2E

Minimum scenarios:

1. reasoning with a single fact;
2. differentiation between fact and inference;
3. hypothesis with insufficient evidence;
4. two compatible sources;
5. two contradictory sources;
6. apparent temporal contradiction;
7. obsolete information;
8. resource without provenance;
9. low-reliability source;
10. claim without evidence;
11. blocking missing information;
12. optional missing information;
13. single-choice question;
14. open question;
15. invalid answer;
16. contradiction in an answer;
17. pause while waiting for the user;
18. session resumption;
19. pause while waiting for a resource;
20. cancelled session;
21. reasoning with medical profile;
22. reasoning with relationship profile;
23. reasoning with project profile;
24. blocked sensitive inference;
25. insufficient permission;
26. prompt injection in a resource;
27. proposed memory update;
28. rejected memory update;
29. versioned knowledge;
30. invalidated knowledge;
31. generated timeline;
32. duplicate entity detected;
33. high-confidence result;
34. insufficient-confidence result;
35. complete traceability;
36. integration with Validation Result;
37. integration with Planner;
38. integration with Kernel;
39. CLI output;
40. API output;
41. local model;
42. authorized remote model;
43. model error;
44. invalid structured output;
45. complete cognitive workflow.

⸻

# Documentation

The phase must include:

* architecture;
* public contracts;
* epistemological model;
* resource guide;
* adapter guide;
* extraction guide;
* Knowledge Store;
* Knowledge Graph;
* entities and relationships;
* versioning;
* invalidation;
* cognitive rules;
* creating new rules;
* profiles;
* creating profiles;
* Reasoning Engine;
* gap analysis;
* question engine;
* contradictions;
* temporality;
* confidence;
* traceability;
* sessions;
* memory integration;
* permissions;
* privacy;
* sensitive inferences;
* protection against prompt injection;
* CLI usage;
* API usage;
* integration with Kernel;
* integration with Planner;
* integration with Execution Engine;
* integration with Validation System;
* integration with future agents;
* complete examples;
* troubleshooting;
* guide for adding domains in Phase 10.

⸻

# Closure Criteria

* cognitive contracts implemented;
* common resource contract;
* structured provenance;
* structured temporality;
* sensitivity and permissions;
* resource adapters;
* knowledge extraction;
* epistemological model;
* KnowledgeItem;
* Evidence;
* KnowledgeRelation;
* versioning;
* invalidation;
* Knowledge Store;
* in-memory implementation;
* persistent implementation;
* Knowledge Graph;
* entities;
* relationships;
* basic entity resolution;
* duplication prevention;
* Reasoning Context;
* Rule Registry;
* initial cognitive rules;
* configurable profiles;
* initial profiles;
* Reasoning Engine;
* integration with models through adapters;
* validation of structured results;
* gap analysis;
* gap classification;
* dynamic question engine;
* answer validation;
* pause and resumption;
* contradiction detection;
* structured conflict resolution;
* basic temporal reasoning;
* timelines;
* confidence evaluation;
* Reasoning Trace;
* absence of free-form internal chains of thought;
* persistent Session Context;
* memory integration;
* update proposals;
* confirmation for sensitive information;
* permission policies;
* protection against prompt injection;
* logs;
* metrics;
* persistence;
* CLI;
* API;
* integration with Kernel;
* integration with Planner;
* integration with Execution Engine;
* integration with Semantic Engine;
* integration with Validation System;
* Knowledge Package contract and builder;
* provider-independent package serialization;
* Knowledge Package validation;
* cognitive cache contracts;
* cache invalidation and revalidation;
* privacy metadata propagation;
* enforcement of `LOCAL_ONLY`;
* controlled remote-processing policies;
* structural validation of provenance, temporality, epistemology, privacy, and cache reuse;
* unit tests;
* integration tests;
* E2E tests;
* documentation;
* green global suite.

⸻

# Phase Outcome

CMM OS will have a shared cognitive layer capable of converting dispersed resources into structured, temporally valid, traceable, and reusable knowledge.

Each reasoning process will be able to demonstrate:

* what objective it was trying to solve;
* what resources were used;
* what knowledge existed;
* what information was extracted;
* which claims are facts;
* which claims are observations;
* which elements were inferred;
* which possibilities remain hypotheses;
* what contradictions exist;
* what sources support each claim;
* what information is outdated;
* what information is missing;
* what questions must be asked;
* what rules were applied;
* what profile was used;
* what confidence level the result has;
* what uncertainty remains;
* what memory update is proposed;
* what decisions require human confirmation;
* what Knowledge Package was produced;
* what information was excluded by privacy policy;
* whether cached cognitive work was reused;
* why the cached work remained valid;
* what structural cognitive validations were applied.

Phase 8 will turn CMM OS memory and resources into a reasonable and auditable knowledge base capable of producing portable, privacy-aware, provider-independent context.

From this infrastructure, Phase 9 will be able to build agents capable of pursuing objectives without duplicating their own cognitive logic, and Phase 10 will be able to specialize the system by domains while maintaining a single knowledge model, a single reasoning engine, and common contracts for all of CMM OS.
