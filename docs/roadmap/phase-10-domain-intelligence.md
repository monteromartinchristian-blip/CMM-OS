🧩 Phase 10 — Domain Intelligence

Objective

To build specialized infrastructure that will allow CMM OS to understand, reason, plan and act differently depending on the area of life or work involved, without fragmenting the system or creating independent architecture.

Canonical requirements already consolidated for Phases 10.16–10.30 are maintained in the
[Domain Intelligence Requirements Matrix](../reference/domain-intelligence-requirements-matrix.md),
with source-clause evidence in the
[Domain Prompt Clause Coverage](../audits/domain-prompt-clause-coverage.md).
Phase 10.15 remains closed. Phase 10.16 — Domain Presentation, Phase 10.17
— Domain Trace (2026-08-02), and Phase 10.18 — Domain Memory Integration
(2026-08-03) are complete. Their implemented boundaries are
[Domain Presentation](../reference/domain-presentation.md),
[Domain Trace](../reference/domain-trace.md), and
[Domain Memory Integration](../reference/domain-memory-integration.md).
Phase 10.19 — General Domain, Phase 10.20 — Health Domain, Phase 10.21 — Relationships Domain, Phase 10.22 — University Domain, Phase 10.23 — Opposition Domain, Phase 10.24 — Reflection Domain, Phase 10.25 — Concerns Domain, Phase 10.26 — Languages Domain, Phase 10.27 — Paternidad Domain, Phase 10.28 — Sport Domain, Phase 10.29 — Life Plan Domain, and Phase 10.30 — Project Domain are complete and independently audited. Phase 10.30 is independently closed with `DP-030=VERIFIED_EXISTING`, `AT-DP-030=PASS` (56 connected checkpoints), 34-class adversarial closure gate `PASS`, and `BLOCKERS=0`, `MAJORS=0`, `MINORS=0`. Phase 10.52 — Mental Health Domain and Phase 10.53 — Neurodivergence Domain remain planned later Domain Packs.

Domain Intelligence will not be a collection of separate assistants.

It will be a shared specialization layer that configures, for each domain:

* what resources are relevant,
* which entities and relations have to be prioritized;
* which cognitive profile should be used;
* which specific rules should be applied;
* which operations are available;
* what workflows can be run;
* what permissions and restrictions exist;
* which criteria require human approval;
* how the result should be presented;
* how to coordinate with other domains.

All domains should use:

Same Kernel
Same Cognitive Layer
Same Knowledge Model
Same Knowledge Store
Same Knowledge Graph
Same Agent Runtime
Same Planner
Same Workflow System
Same Operation Contracts
Same Validation System
Same Memory Contracts
+
Domain Resources
Domain Profile
Domain Rules
Domain Operations
Domain Workflows
Domain Permissions
Domain Presentation

CMM OS should not behave the same way when handling a medical consultation, university planning, emotional reflection, opposition exam review, or modification of its own project.

It should specialize its behavior while preserving:

* a single source of truth;
* stable contracts;
* shared knowledge
* complete traceability;
* temporality;
* permissions
* coherence between domains
* the possibility of multi-domain reasoning;
* prevention of duplication
* extensibility through new packages.

⸻

General Architecture

User Request / Goal / Event
↓
Domain Resolution Context
↓
Domain Resolver
↓
Primary Domain
+
Supporting Domains
↓
Domain Registry
↓
Domain Pack Loader
↓
Domain Composition
↓
Domain Resources
↓
Domain Profile
↓
Domain Rules
↓
Domain Permissions
↓
Domain Operations
↓
Domain Workflows
↓
Cognitive Layer
↓
Agent Runtime
↓
Cross-Domain Coordination
↓
Domain Result
↓
Domain Trace
↓
Memory Update Proposal

Domain Intelligence should be used:

* from the conversational UI;
* from CLI
* from the API
* from autonomous goals
* from workflows;
* from agents,
* from Kernel events
* from scheduled tasks
* from existing sessions
* from new sessions,
* with a single domain,
* with several domains
* with explicit domains
* with automatically resolved domains;
* with local or remote models
* without depending on a specific provider;
* with internal Domain Packs;
* with external Domain Packs;
* with activated or disabled domains
* with different permissions by user, session and domain.

⸻

10.1 - Domain Contracts

Objective

To define common contracts that will use all domains before applying specific specializations.

Domains cannot define cognitive models, runtimes, planners, memory systems and incompatible execution contracts.

Domain Status

Possible States of an installed domain:

discovered
registered
loading
active
disabled
degraded
incompatible
invalid
failed
unloaded

Domain Kind

Initial types:

core
personal
professional
project
system
external
experimental

Domain Identifier

Any domain should have a stable identifier.

Examples:

domain:health
domain:relationships
domain:university
domain:oppositions
domain:reflection
domain:concerns
domain:languages
domain:parenthood
domain:sport
domain:life-plan
domain:project
domain:general

Domain Definition

DomainDefinition(
id="domain:university",
name="university",
display_name="Universidad",
version="1.0.0",
kind="personal",
description="Management and reasoning about university life",
manifest_id="manifest:university:1.0.0",
reasoning_profile="UniversityProfile",
resources=[],
rules=[],
operations=[],
workflows=[],
permissions=[],
validators=[],
presentation_policy={},
dependencies=[],
optional_dependencies=[],
conflicts=[],
capabilities=[],
enabled=True,
metadata={},
)

Domain Metadata

DomainMetadata(
author="CMM OS",
license="internal",
homepage=None,
repository=None,
created_at="...",
updated_at="...",
minimum_cmm_version="...",
maximum_cmm_version=None,
tags=[],
experimental=False,
deprecated=False,
metadata={},
)

Domain Capability

It will represent a capacity declared by a domain.

DomainCapability(
name="medical_timeline",
kind="reasoning",
provided_by="domain:health",
version="1",
requirements=[],
permissions=[],
metadata={},
)

Initial capability types:

* resource_provider;
* reasoning;
* operation;
* workflow;
* presentation;
* validation;
* classification;
* entity_resolution;
* timeline;
* recommendation;
* planning;
* monitoring;
* reporting;
* memory_extension.

Domain Dependency

DomainDependency(
domain_id="domain:general",
version_constraint=">=1.0.0",
required=True,
reason="Shared fallback behavior",
metadata={},
)

Domain Conflict

DomainConflict(
domain_id="domain:legacy-health",
reason="Provides incompatible medical contracts",
severity="blocking",
metadata={},
)

Domain Result

Special result base contract:

DomainResult(
id="domain-result-123",
status="completed",
objective="...",
primary_domain="domain:health",
supporting_domains=["domain:life-plan"],
reasoning_result_id="reasoning-result-123",
workflow_result_id=None,
operation_results=[],
findings=[],
recommendations=[],
approvals_required=[],
confidence=0.84,
trace_id="domain-trace-123",
session_id="session-123",
created_at="...",
metadata={},
)

Contract Restrictions

Domains must not be free to:

* redefinir KnowledgeItem;
* redefinir Resource;
* redefinir ReasoningResult;
* redefinir Goal;
* redefinir Workflow;
* redefinir OperationResult;
* Redefining global permissions
* Skip the Kernel.
* access backends directly;
* execute actions outside the Agent Runtime;
* write memory without using global policies
* hide procedencia;
* remove contradictions;
* use incompatible data models.

⸻

10.2 - Domain Pack

Objective

To represent each domain as a autocontained, installable, valiant, versioned and dynamically chargeable package.

A Domain Pack will have to group all specialized elements without duplicating common infrastructure.

Base Structure

domain-name/
├── manifest.yaml
├── README.md
├── resources/
├── profiles/
├── rules/
├── operations/
├── workflows/
├── permissions/
├── prompts/
├── presentation/
├── validators/
├── migrations/
├── fixtures/
└── tests/

Manifest

The manif.yaml file will be the main declarative source of the domain.

Example:

id: domain:university
name: university
display_name: Universidad
version: 1.0.0
kind: personal
description: University academic management
minimum_cmm_version: 1.0.0

profile:
default: UniversityProfile

resources:

* university_subject
* academic_record
* examination
* assignment
* university_calendar

rules:

* AcademicDeadlineRule
* WorkloadFeasibilityRule
* ExamAttemptRule
* AcademicTemporalValidityRule

operations:

* university.plan_semester
* university.create_study_plan
* university.compare_academic_periods
* university.prepare_exam_review

workflows:

* university.semester_planning
* university.exam_preparation
* university.academic_review

permissions:
policy: permissions/university.yaml

dependencies:

* domain:general

Domain Manifest

DomainManifest(
id="manifest:university:1.0.0",
domain_id="domain:university",
schema_version="1",
package_version="1.0.0",
entrypoint="...",
resources=[],
profiles=[],
rules=[],
operations=[],
workflows=[],
permissions=[],
validators=[],
presentation=[],
dependencies=[],
compatibility={},
checksum="...",
signature=None,
metadata={},
)

Domain Pack Properties

* autocontenido;
* a declaration where possible
* versioning;
* validable;
* instalable;
* habilitable;
* deshabilitable;
* actualizable;
* migrable;
* trazable;
* aislable;
* compatible with plugins;
* compatible with local load;
* independent of the AI provider;
* Extensible without changing the Kernel.

Internal Domain Pack

Package distributed with CMM OS and held inside the main repository.

External Domain Pack

Package later installed using the plugin system or from an authorized source.

Experimental Domain Pack

Package authorized only under an explicit policy and without complete guarantees of stability.

Restrictions

A Domain Pack should not:

* include credentials;
* amend the Kernel during loading.
* record destructive operations without declaring them;
* overwrite global contracts;
* changing permissions by itself
* To deactivate obligatory rules
* to have access to unauthorised resources,
* run code during discovery;
* To install arbitrary units without approval.
* declarar compatibility falsa;
* introduce prompts as a replacement for structured contracts.

⸻

10.3 - Domain Registry

Objective

To create a central register of available, installed, activated and activated domains.

Contract

class DomainRegistry:
def register(
self,
definition: DomainDefinition,
) -> DomainDefinition:
...

```
def unregister(
    self,
    domain_id: str,
) -> None:
    ...

def get(
    self,
    domain_id: str,
) -> DomainDefinition | None:
    ...

def list(
    self,
    query: DomainQuery | None = None,
) -> list[DomainDefinition]:
    ...

def enable(
    self,
    domain_id: str,
) -> DomainDefinition:
    ...

def disable(
    self,
    domain_id: str,
) -> DomainDefinition:
    ...

def validate(
    self,
    domain_id: str,
) -> DomainValidationResult:
    ...

def resolve_capability(
    self,
    capability: str,
) -> list[DomainDefinition]:
    ...
```

Domain Query

DomainQuery(
kinds=[],
statuses=[],
capabilities=[],
enabled=None,
tags=[],
minimum_version=None,
include_experimental=False,
metadata={},
)

Capacidades

* register domains,
* remove records;
* To discover domains
* query by identifier;
* query by capability;
* query by type;
* habilitar;
* deshabilitar;
* validate;
* detect duplicados;
* check versions;
* resolve dependencies;
* detect conflicts;
* query compatibility;
* listar operations;
* listar workflows;
* list resources;
* list rules;
* preserve version history;
* emitir Kernel events.

Registro inicial

domain:general
domain:health
domain:relationships
domain:university
domain:oppositions
domain:reflection
domain:concerns
domain:languages
domain:parenthood
domain:sport
domain:life-plan
domain:project

Eventos

domain.discovered
domain.registered
domain.enabled
domain.disabled
domain.loading
domain.loaded
domain.degraded
domain.validation.failed
domain.updated
domain.unloaded
domain.unregistered
domain.conflict.detected
domain.dependency.missing

Preventing duplication

The registration should prevent:

* two active domains with the same identifier;
* Two operations with the same identifier and incompatible contract
* two workflows incompatible with the same identifier;
* silent partial records;
* Unversed overlays
* circular dependencies not allowed;
* Invalid domain activation.

⸻

10.4 - Domain Discovery and Domain Loader

Objective

Discover, validate, load, reload and unload Domain Packs without connecting the platform to specific locations.

Domain Discovery

Initial discovery sources:

* internal packages;
* configured directories;
* installed plugins;
* authorized repositories;
* user settings;
* development packages;
* test fixtures.

Domain Candidate

DomainCandidate(
location="...",
source="internal",
manifest_path="...",
detected_version="1.0.0",
checksum="...",
trusted=True,
metadata={},
)

Domain Loader

Contrato:

class DomainLoader:
def discover(
self,
sources: list[DomainSource],
) -> list[DomainCandidate]:
...

```
def load(
    self,
    candidate: DomainCandidate,
) -> DomainLoadResult:
    ...

def reload(
    self,
    domain_id: str,
) -> DomainLoadResult:
    ...

def unload(
    self,
    domain_id: str,
) -> DomainUnloadResult:
    ...

def validate_manifest(
    self,
    candidate: DomainCandidate,
) -> DomainValidationResult:
    ...
```

Domain Load Result

DomainLoadResult(
domain_id="domain:health",
status="loaded",
definition={},
registered_resources=[],
registered_rules=[],
registered_operations=[],
registered_workflows=[],
warnings=[],
errors=[],
duration_ms=82,
metadata={},
)

Loading process

Discover Candidate
↓
Read Manifest
↓
Validate Schema
↓
Verify Compatibility
↓
Verify Integrity
↓
Resolve Dependencies
↓
Check Conflicts
↓
Load Declarative Components
↓
Load Code Components
↓
Validate Contracts
↓
Register Components
↓
Run Domain Health Check
↓
Activate Domain

Atomic Loading

The load should be atomic.

If a required component fails:

* the domain should not be activated;
* partial records should be reverted;
* The previous domain should be preserved if a reload is involved.
* A structured result should be issued.
* The error should be recorded.
* the rest of the system should not be degraded.

Hot Reload

The following may be allowed during development:

* Reloading of rules
* prompt reload;
* workflow reload;
* presentation reload
* configuration reload;
* Reloading of non-critical permissions.

Uncontrolled production should not be permitted:

* replace active contracts;
* amend operations under implementation;
* to change active session permissions;
* replace migrations;
* to change persistent schemes without migration.

⸻

10.5 - Domain Validation

Objective

Validate that a Domain Pack complies with contracts, does not fragment the system and can be activated safely.

Domain Validation Result

DomainValidationResult(
domain_id="domain:health",
status="passed",
manifest_valid=True,
compatibility_valid=True,
dependencies_valid=True,
contracts_valid=True,
permissions_valid=True,
operations_valid=True,
workflows_valid=True,
tests_valid=True,
findings=[],
warnings=[],
duration_ms=640,
metadata={},
)

Mandatory validations

Manifest

* valid scheme
* stable identifier;
* valid version
* required fields;
* existing paths;
* checksum;
* declared compatibility.

Dependencies

* available dependencies;
* compatible versions;
* absence of forbidden cycles;
* optional dependencies that can degrade correctly.

Contracts

* compatible resources,
* compatible rules
* compatible profiles;
* compatible operations;
* compatible workflows;
* structured results
* valid serialization.

Permissions

* declared permissions
* absence of implicit escalation,
* identified sensitive operations;
* configured approvals;
* minimum necessary access.

Security

* absence of secrets;
* absence of forbidden commands;
* absence of unauthorized imports;
* data and instructions separation
* protection against prompt injection;
* Operating limits.

Fragmentation Prevention

* does not duplicate memory;
* does not create its own planner;
* does not create its own Agent Runtime;
* does not create its own Knowledge Store;
* not redefine contracts;
* does not access the backend directly;
* does not omit provenance;
* do not bypass global policies;

Quality

* unit tests;
* integration tests;
* documentation;
* examples;
* health check;
* compatibility with JSON output
* compatibility with observability.

Integration with phase 7

The validation of domains should be integrated into Validation pipeline by means of steps such as:

domain.manifest
domain.contracts
domain.permissions
domain.dependencies
domain.security
domain.tests
domain.compatibility
domain.fragmentation

A Domain Pack cannot be installed, updated or published with a blocking finding.

⸻

10.6 - Domain Resolution Context

Objective

To represent all information necessary to determine what domain or combination of domains corresponds to an application.

DomainResolutionContext(
id="domain-resolution-context-123",
objective="Determine whether I should change my study plan",
user_input="I cannot focus on the opposition exam syllabus",
goal_id=None,
session_id="session-123",
explicit_domains=[],
available_domains=[],
active_domains=[],
resources=[],
entities=[],
knowledge_items=[],
current_profile=None,
current_workflow=None,
event_type=None,
actor="actor-user",
permissions=[],
temporal_reference="2026-07-22",
language="es",
metadata={},
)

To be included

* input text or event;
* objective
* explicit domains;
* available domains
* authorized domains;
* session
* workflow;
* active goal
* resources
* entities;
* knowledge
* current profile;
* requested operations;
* permissions
* temporal reference;
* language;
* recent history;
* metadata.

Resolution signals

* explicit domain;
* resource type
* detected entities;
* intent
* objective
* operation requested
* active workflow;
* cognitive profile;
* relevant knowledge
* previous session
* Kernel events;
* user preferences;
* system policy.

The resolution should not depend only on key words.

⸻

10.7 - Domain Resolver

Objective

Select the main and support domains suitable for each request, target, event or workflow.

Contract

class DomainResolver:
def resolve(
self,
context: DomainResolutionContext,
) -> DomainResolutionResult:
...

Domain Resolution Result

DomainResolutionResult(
id="domain-resolution-123",
status="resolved",
primary_domain="domain:university",
supporting_domains=[
"domain:health",
"domain:life-plan",
],
rejected_domains=[],
ambiguous_domains=[],
confidence=0.86,
reasons=[],
requires_clarification=False,
recommended_question=None,
metadata={},
)

Estados

resolved
ambiguous
insufficient_information
unsupported
blocked
failed

Types of resolution

Explicit Resolution

The user or workflow specifies the domain.

Resource-Based Resolution

The type of resource determines the main domain.

Intent-Based Resolution

The intent of an application indicates a domain.

Entity-Based Resolution

The identified entities guide the resolution.

Session-Based Resolution

The session currently has a main domain.

Goal-Based Resolution

The persistent goal determines the specialization.

Composite Resolution

The request requires several domains.

Fallback Resolution

GeneralDomain is used if there is insufficient specialization.

Capacidades

* select main domain
* to detect secondary domains;
* To detect ambiguity
* seek clarification;
* using session context;
* using active targets;
* preserve confidence;
* explain the resolution
* respect disabled domains;
* respect permissions;
* avoid incompatible domains.
* maintain a secure fallback;
* To solve domains for events
* to solve domains for operations;
* solve workflows domains;
* Reevaluate the domain during a session.

Examples

Entrada:

"I have suspended juvenile law."

Resultado:

Primary:
domain:university

Supporting:
domain:reflection

Entrada:

"Since I started my medication, I have more difficulty with urinating."

Resultado:

Primary:
domain:health

Supporting:
domain:general

Entrada:

"I don't know if to prepare prepare for an opposition exam or study Psychology."

Resultado:

Primary:
domain:life-plan

Supporting:
domain:oppositions
domain:university
domain:reflection

Entrada:

"Test passes, but documentation doesn't match code anymore."

Resultado:

Primary:
domain:project

Supporting:
domain:general

Variance

If a material ambiguity exists, the resolution should:

* using a prudent general domain
* to have candidate domains,
* put a question.
* or continue with a limited composition.

A high impact domain with insufficient confidence should not be chosen quietly.

⸻

10.8 - Domain Composition

Objective

To mix several domains into a single performance without mixed contracts, double results and allow silent conflicts.

Domain Composition

DomainComposition(
id="domain-composition-123",
primary_domain="domain:life-plan",
supporting_domains=[
"domain:university",
"domain:oppositions",
"domain:health",
],
profile_composition={},
rule_composition={},
resource_composition={},
operation_composition={},
workflow_composition={},
permission_intersection={},
presentation_composition={},
conflict_policy="most_restrictive",
metadata={},
)

Principios

Primary Domain

Determina:

* the main objective;
* base profile;
* Main form of result
* workflow central;
* priority rules.

Supporting Domain

Aporta:

* resources
* Additional rules
* restricciones;
* auxiliary operations;
* perspectivas complementarias.

General Domain

Proporciona:

* fallback;
* basic contracts
* general presentation
* universal operations;
* Unspecialized common rules.

Profile composition

No separate cognitive engines should be created.

The composition should produce an effective policy:

EffectiveReasoningProfile(
base_profile="LifePlanProfile",
added_rules=[],
required_rules=[],
prohibited_actions=[],
minimum_confidence=0.85,
maximum_inference_depth=2,
maximum_questions_per_turn=3,
metadata={},
)

Permission composition

The most restrictive policy will be applied by default.

If one domain permissions an action and another prevents it:

* The prohibition should prevail.
* or an explicit policy of exception should be required.
* The decision should be drawn up.

Composition of rules

Orden:

1. Mandatory global rules
2. Security rules
3. Main domain rules
4. secondary domain rules
5. Optional rules
6. rules of presentation.

Composition of operations

The operations available should be the union of authorized operations, leaked by:

* permissions
* autonomy
* session
* actor;
* sensibilidad;
* conflicts;
* presupuesto;
* approvals.

Double enforcement prevention

The composition should detect:

* operations equivalent;
* workflows equivalent;
* duplicated resources
* dual rules
* entities repetidas;
* preguntas equivalent;
* Double memory updates.

⸻

10.9 - Cross-Domain Engine

Objective

To coordinate reasoning, workflows and operations across several areas while maintaining global coherence.

The Cross-Domain Engine will not be a second Reasoning Engine.

He will be a coordinator about:

* Domain Resolver;
* Domain Composition;
* Cognitive Layer;
* Planner;
* Agent Runtime;
* Workflow Engine;
* Knowledge Graph.

Contract

class CrossDomainEngine:
def execute(
self,
request: CrossDomainRequest,
) -> CrossDomainResult:
...

Cross-Domain Request

CrossDomainRequest(
objective="Evaluar la viabilidad del plan profesional",
primary_domain="domain:life-plan",
supporting_domains=[
"domain:university",
"domain:oppositions",
"domain:health",
],
session_id="session-123",
resources=[],
constraints=[],
permissions=[],
maximum_domain_hops=4,
metadata={},
)

Cross-Domain Result

CrossDomainResult(
id="cross-domain-result-123",
status="completed",
objective="...",
composition_id="domain-composition-123",
domain_results=[],
shared_findings=[],
contradictions=[],
dependencies=[],
cross_domain_gaps=[],
recommendations=[],
confidence=0.8,
trace_id="cross-domain-trace-123",
metadata={},
)

Capacidades

* combining knowledge between domains
* detect dependencies;
* detect conflicts;
* transferir contexto;
* reutilizar entities;
* reutilizar timelines;
* coordinate preguntas;
* avoid duplicate questioning;
* generate cross-cutting plans;
* coordinate operations;
* maintain permissions;
* detect impacto multi-domain;
* production of consolidated results;
* maintain partial results;
* stop on bloqueos;
* scale to human review.

Examples

Health and university

Fatiga
↓
Health Domain
↓
Momency of symptoms
↓
Academic Loan
↓
University Domain
↓
Impacto funcional
↓
Plan adaptado

Opposition and Life Plan

Opposition Goal
↓
Opposition Domain
↓
Workload and progress
↓
Life Plan Domain
↓
Economy and deadlines
↓
University Domain
↓
Academic compatibility
↓
Escenarios

Relationships and concerns

Relationship Event
↓
Relationships Domain
↓
Hechos e interpretaciones
↓
Concerns Domain
↓
Support need, concern support, reassurance and uncertainty
↓
Reflection Domain
↓
Broader meaning and open questions
↓
Integrated outcome

Project and validation

Code Change
↓
Project Domain
↓
Architecture Analysis
↓
Validation System
↓
Documentation Consistency
↓
Technical Debt
↓
Agent Outcome Evaluation

Limits

The engine should restrict:

* number of domains;
* transfer depth;
* iteraciones;
* preguntas;
* operations;
* coste;
* tiempo;
* inferencias;
* llamadas externas.

⸻

10.10 - Domain Resources

Objective

To define what resources are relevant to each area and how they are incorporated into the common model of the Cognitive Layer.

Domains will not create incompatible resources.

They should use:

Resource
ResourceProvenance
TemporalScope
Sensitivity
Permissions
KnowledgeItem
Entity
KnowledgeRelation

Domain Resource Definition

DomainResourceDefinition(
kind="medical_report",
domain_id="domain:health",
adapter="MedicalReportAdapter",
entity_types=[],
default_sensitivity="highly_sensitive",
default_permissions=[],
temporal_policy={},
validation_rules=[],
metadata={},
)

Capacidades

* to register types of resources;
* asociar adaptadores;
* declarar entities relevantes;
* declarar sensibilidad;
* declare permissions
* define temporality;
* prioritize sources;
* define reliability by type;
* define validators;
* share resources between domains
* prevent unauthorized access.

Shared resources

A resource may belong to several domains without duplication.

Example:

Resource(
id="resource:calendar:event-123",
domain="general",
metadata={
"applicable_domains": [
"health",
"university",
"oppositions",
],
},
)

Each domain will be able to interpret it from its specialist level without creating independent copies.

Retirement

The derived resources should retain:

* resource of origin
* transformation
* actor;
* fecha;
* version
* permissions
* sensibilidad;
* Checksum as appropriate.

⸻

10.11 - Domain Profiles

Objective

Specify phase 8 cognitive profiles for each domain without creating separate reasoning engines.

Domain Profile Definition

DomainProfileDefinition(
domain_id="domain:health",
profile_name="HealthProfile",
required_rules=[],
optional_rules=[],
prohibited_rules=[],
minimum_confidence=0.9,
allowed_resource_kinds=[],
prohibited_actions=[],
escalation_rules=[],
question_policy={},
presentation_policy={},
memory_policy={},
metadata={},
)

The domain profiles should define:

* Mandatory rules
* Optional rules
* permitted resources;
* priority resources
* minimum confidence
* profundidad;
* inferencias allowed;
* inferencias prohibidas;
* maximum number of questions
* escalation criteria;
* acciones prohibidas;
* memory policy
* temporary policy
* production policy
* permissions.

Perfiles initial

GeneralProfile

HealthProfile

RelationshipProfile

UniversityProfile

OppositionProfile

ReflectionProfile

ConcernSupportProfile

LanguageProfile

ParenthoodProfile

SportProfile

LifePlanProfile

ProjectProfile

Profile resolution

The actual profile may come from:

* Main domain
* secondary domain
* workflow;
* operation
* risk level;
* actor;
* autonomy
* explicit request
* global policy.

Rules of composition

* No composition may deactivate mandatory global rules.
* The highest confidence threshold should be used where risk exists.
* The prohibited actions should prevail.
* the most restrictive limits should be retained.
* Each modification of the actual profile should be drawn up.

⸻

10.12 - Domain Rules

Objective

Add rules specific to each area while maintaining the common ReasoningRule contract.

Contract

class DomainReasoningRule(ReasoningRule):
domain_id: str
category: str
required_permissions: list[str]
risk_level: str

Domain Rule Result

DomainRuleResult(
rule_name="MedicationTemporalRelationshipRule",
domain_id="domain:health",
status="applied",
findings=[],
produced_knowledge=[],
contradictions=[],
gaps=[],
recommendations=[],
escalation=None,
confidence_delta=0.0,
trace_entries=[],
metadata={},
)

Characteristics

The domain rules should be:

* componibles;
* auditables;
* versionadas;
* titititists where possible
* model-independent;
* registrables;
* habilitables;
* disabled if they are not required;
* compatible with partial enforcement
* compatible with traceability,
* with permission.

Overall rules versus domain rules

The global rules determine how CMM OS rapes.

The rules of domain determine what precautions, relationships or structures should be applied in a particular area.

Example:

Global:

DistinguishFactInferenceHypothesis

Domain Health:

DistinguishSymptomDiagnosisHypothesis

Both should be applied.

Rule Registry

The rules will have to be registered with the common rule registry with domain information.

Example:

health.symptom_diagnosis_hypothesis
health.medication_temporal_relationship
health.red_flags
health.clinical_source_priority

university.deadline
university.workload
university.exam_attempt
university.academic_dependency

relationships.fact_interpretation
relationships.intent_uncertainty
relationships.pattern_detection
relationships.need_boundary

project.architecture_contract
project.code_documentation_consistency
project.validation_required
project.technical_debt

⸻

10.13 - Domain Operations

Objective

To define specialized actions that can be performed through the Execution Engine and the Agent Runtime under controlled permissions.

Domains cannot execute actions directly.

Any operation should use:

Operation
OperationContext
OperationResult
Transaction
Approval Gate
Validation Policy
Rollback Policy

Domain Operation

DomainOperation(
id="health.prepare_medical_appointment",
domain_id="domain:health",
version="1",
description="Prepare a summary and questions for a medical consultation",
input_schema={},
output_schema={},
required_resources=[],
required_permissions=[],
risk_level="low",
reversible=True,
requires_approval=False,
validation_policy=None,
rollback_policy=None,
metadata={},
)

Operation Types

Read Operation

Consultation or recovery unchanged.

Analysis Operation

It produces structured analysis.

Preparation Operation

Generates materials for later action.

Memory Operation

Propones or implements authorized changes to memory.

Planning Operation

Builds or updates plans.

External Operation

It interacts with outside services.

Sensitive Operation

It may affect medical, legal, financial or personal areas.

Destructive Operation

May delete, replace, or modify irreversibly.

Estados

registered
available
unavailable
blocked
waiting_for_approval
running
completed
failed
rolled_back
cancelled

Capacidades

* register operations;
* validate inputs;
* validate outputs;
* to solve permissions;
* applying for approval
* execute;
* cancelar;
* reintentar;
* revertir;
* Validation of result
* preserve traceability;
* update sessions;
* produce events;
* propose memory
* integrate with workflows.

Restrictions

A domain operation should not:

* access storage directly;
* sending communications without approval
* amend permissions;
* saltarse transacciones;
* omits validation;
* hide errors;
* persisting sensitive results without policy
* execute arbitrary commands;
* production of free formats where a contract exists.

⸻

10.14 - Domain Workflows

Objective

To create specialized reusable processes for common goals of each domain.

The workflows will have to use the common Workflow Engine.

Domain Workflow Definition

DomainWorkflowDefinition(
id="health.medical_follow_up",
domain_id="domain:health",
version="1",
description="Structured review of a medical problem",
input_schema={},
output_schema={},
nodes=[],
dependencies=[],
required_permissions=[],
approval_gates=[],
completion_criteria=[],
memory_policy={},
metadata={},
)

Nodos available

* LoadResource;
* SearchKnowledge;
* ResolveEntity;
* ApplyProfile;
* Reason;
* DetectGaps;
* AskQuestion;
* WaitForResource;
* ExecuteOperation;
* Validate;
* RequestApproval;
* UpdateSession;
* ProposeMemory;
* EvaluateOutcome;
* Complete;
* Pause;
* Escalate.

Ejemplo

Medical Follow-up

Load Medical Resources
↓
Build Symptom Timeline
↓
Load Medication Timeline
↓
Apply Medical Rules
↓
Detect Contradictions
↓
Detect Missing Information
↓
Ask Blocking Questions
↓
Generate Consultation Summary
↓
Prepare Questions
↓
Propose Memory Update
↓
Complete

University Semester Planning

Load Subjects
↓
Load Deadlines
↓
Load Available Time
↓
Load Academic Constraints
↓
Evaluate Workload
↓
Detect Conflicts
↓
Generate Scenarios
↓
Select Plan
↓
Create Tasks
↓
Schedule Review
↓
Complete

Relationship Timeline Analysis

Load Relationship Events
↓
Resolve People
↓
Build Timeline
↓
Separate Facts and Interpretations
↓
Detect Patterns
↓
Detect Missing Context
↓
Generate Hypotheses
↓
Identify Needs and Boundaries
↓
Produce Reflection Result
↓
Complete

Project Architecture Review

Load Repository
↓
Load Documentation
↓
Build Architecture Model
↓
Detect Contract Violations
↓
Compare Code and Documentation
↓
Run Validation
↓
Detect Technical Debt
↓
Generate Findings
↓
Propose Tasks
↓
Complete

Capacidades

* iniciar;
* pausar;
* reanudar;
* cancelar;
* versionar;
* migrar;
* compose;
* reutilizar nodos;
* llamar a subworkflows;
* crossing domains
* hold a session;
* applying for approval
* recover errors;
* evaluating results,
* update targets
* propose memory.

⸻

10.15 - Domain Permissions

Status: Complete and audited (2026-08-02). The implementation includes
restrictive composition, source/target cross-domain policy, canonical atomic
approvals, real operation/workflow gates, declarative source/egress/export
restrictions, post-verification obligations, public serialization contracts,
and dependency-direction tests. Connectors, real provider calls, effective
redaction, secrets, full traces and Phase 11 RBAC remain out of scope.

Objective

Control what resources, inferences, operations and workflows can use each domain.

Domain Permission Policy

DomainPermissionPolicy(
domain_id="domain:health",
allowed_resource_kinds=[],
allowed_sensitivity_levels=[],
allowed_operations=[],
prohibited_operations=[],
allow_cross_domain_access=False,
allowed_target_domains=[],
allow_sensitive_inference=False,
allow_memory_read=True,
allow_memory_write=False,
allow_external_search=False,
allow_external_models=False,
approval_requirements=[],
autonomy_limits={},
metadata={},
)

Permissions evaluated

* Access to resources
* Access to knowledge
* acceso a entities;
* acceso a relaciones;
* memory access;
* memory writing
* inferencia sensible;
* outside search
* use of external models;
* operation execution
* performance of workflows;
* External communication
* file modification
* job creation
* change of schedules
* update of targets,
* export
* acceso multi-domain.

Permission Intersection

When several domains participate:

# Effective Permissions

Global Permissions
∞
User Permissions
∞
Session Permissions
∞
Domain Permissions
∞
Operation Permissions
∞
Autonomy Policy

The most restrictive intersection should be used by default.

Approval Requirements

Mandatory approval for:

* sending communications
* publication
* change of schedules
* file modification
* cambios irreversibles;
* elimination of knowledge
* Medical decisions
* decisiones legales;
* decisiones financieras;
* gasto;
* modification of permissions
* acceso multi-domain sensible;
* persistence of sensitive inferences;
* non-Reliable external domain activation.

Cross-Domain Permission Request

CrossDomainPermissionRequest(
source_domain="domain:life-plan",
target_domain="domain:health",
resource_ids=[],
requested_operations=[],
reason="Evaluate health constraints affecting long-term plan",
duration="session",
requires_approval=True,
metadata={},
)

⸻

10.16 - Domain Presentation

Status: Complete (2026-08-02). The implementation is constrained by the
[Domain Presentation reference](../reference/domain-presentation.md): it plans
reference-only structure and visibility after upstream resolution, preserves
semantics through validation, and does not render or decide interaction.

Objective

To adapt how to have results according to the domain without changing the epistemological content or concealing uncertainty.

Domain Presentation Policy

DomainPresentationPolicy(
domain_id="domain:health",
format="structured",
sections=[],
terminology={},
confidence_visibility="always",
source_visibility="always",
contradiction_visibility="always",
uncertainty_visibility="always",
warnings_position="first",
maximum_detail="standard",
metadata={},
)

Capacidades

* ordenar secciones;
* adaptar vocabulario;
* prioritize warnings;
* mostrar timelines;
* mostrar tablas;
* mostrar escenarios;
* mostrar planes;
* mostrar contradicciones;
* mostrar preguntas;
* mostrar confianza;
* mostrar procedencia;
* generate human-readable output;
* generate structured output;
* generate UI components.

The submission should not:

* change facts;
* hide contradicciones;
* remove uncertainty;
* elevar confianza;
* to alter epistemological types;
* a recommendation as a decision;
* have a diagnosis hypothesis;
* remove approval requirements.

Componentes initial

* DomainSummary;
* TimelineView;
* EvidencePanel;
* ContradictionPanel;
* InformationGapPanel;
* QuestionCard;
* GoalProgress;
* ScenarioComparison;
* WorkflowProgress;
* ApprovalCard;
* MemoryProposalCard;
* DomainBadge;
* CrossDomainMap.

⸻

10.17 - Domain Trace — Complete (2026-08-02)

`DomainTrace` is a final, frozen, deterministic reference-only aggregate.  It
records request/goal identity, participating primary/supporting domains,
contributions grouped by domain, typed global references, result/trace
pairings, final status and timezone-aware timing.  It does not contain an
objective or copied upstream content.  The pure assembler derives duration,
digest and ID; the external typed inventory validator enforces category,
attribution, pairing, privacy and integrity rules. Authoritative selections are
bound to their resolution/composition source IDs; cross-domain result and trace
IDs resolve through distinct typed categories; DomainResult order is canonical;
and corrupt diagnostics fail closed without echoing unsafe values. See
[Domain Trace](../reference/domain-trace.md).

No cross-domain transfer trace type, second AgentTrace/ReasoningTrace/KnowledgePackage,
store, stream, provider audit, private prompt or chain-of-thought is created.

⸻

10.18 - Domain Memory Integration (Completed 2026-08-03)

Objective

Allow domains to select reference-only memory views and bind update proposals to shared memory without creating separate domain warehouses, persistent copies, or parallel claim models.

Implemented Architecture & Contracts

1. **One Shared Memory**: All knowledge, entities, relations, evidence, resources, and temporal scopes reside in `cmm.cognitive`.
2. **DomainMemoryView**: A deterministic, reference-only view result containing `view_id`, `request_id`, `primary_domain`, required full canonical `request_digest` (SHA-256 of `DomainMemoryViewRequest`), optional `trace_id` and `temporal_reference`, canonical `selection_decisions`, `selected_references`, `content_digest`, and `digest`. `view_id` is content-bound to `request_digest` and selection decisions.
3. **DomainMemoryProposalBinding**: Reference-only binding linking domain execution (`domain_id`, `trace_id`, `view_id`, `view_digest`) to existing canonical Phase 8 `MemoryUpdateProposal` and Phase 9 `AgentKnowledgeUpdateProposal` objects by ID.
4. **Capability Separation**: Read permission does not imply proposal or write authorization (`READ != PROPOSE != APPROVE != APPLY != INVALIDATE != DELETE`).
5. **Fail-Closed Validation**: `DefaultDomainMemoryIntegrationValidator` enforces exact proposal affected-reference inventory coverage, reference integrity, and privacy bounds without side-effects or store mutations.

See [Domain Memory Integration Reference](../reference/domain-memory-integration.md).

Capacidades

* To read relevant knowledge;
* filtering by domain;
* Reusing general knowledge
* reutilizar entities;
* proponer enlaces multi-domain;
* proponer actualizaciones;
* proponer invalidaciones;
* register decisiones;
* preserve provenance;
* avoid duplicates;
* require confirmation;
* respetar sensibilidad.

Preventing fragmentation

Domains must not be free to:

* create independent persistent copies;
* duplicate personas/events/goals/decisions;
* overwrite preferences;
* remove versions;
* retain source-free knowledge.

⸻

10.19 - General Domain

**Status:** Complete and audited (2026-08-08).

Objective

Provide a basic domain for nonspecialist applications, common behavior and secure fallback.

Resources

* user_message;
* conversation;
* calendar_event;
* note;
* document;
* memory_entry;
* generic_task;
* generic_goal;
* external_source.

Rules

* GeneralTemporalValidityRule;
* GeneralSourceReliabilityRule;
* GeneralAmbiguityRule;
* GeneralPermissionRule;
* GeneralGoalClarificationRule;
* GeneralDuplicationRule.

Operaciones

* general.create_summary;
* general.build_timeline;
* general.compare_items;
* general.prepare_questions;
* general.create_task;
* general.update_goal;
* general.generate_report;
* general.search_knowledge.

Workflows

* general.information_review;
* general.goal_clarification;
* general.decision_support;
* general.periodic_review.

Permissions

* low risk by default;
* without automatic external actions
* without sensitive interference,
* controlled memory writing
* fallback prudente.

General Domain should not become a domain that quietly absorbes all applications.

When a specialized domain is available, it should be used.

### Implementation notes

- `domain:general` is implemented via pure factories under `cmm/domains/general/`.
- 13 production modules (including `catalog.py`); 17 test modules.
- The canonical catalog (`cmm/domains/general/catalog.py`) is the single source of truth for the 8 operations, 6 rules, 9 resources, and 4 workflows.
- The Phase 10.13 `INITIAL_DOMAIN_OPERATION_IDS` contains 4 historical `general.*` placeholders with different semantics; they are preserved for backward compatibility and do not collide with the Phase 10.19 canonical set.
- Registration is atomic via validation-first semantics plus snapshot/restore rollback across all registries.
- Canonical bootstrap: `build_standard_general_domain_bootstrap()` constructs the standard registries with General Domain fully integrated.
- The canonical bootstrap exposes a `DefaultDomainResolver` configured with `fallback_domain=DomainId(slug="general")`, using the standard `DomainScoringPolicy` (no manual `minimum_resolution_score` adjustment required).
- Operations are declared and remain **UNAVAILABLE** by default; real implementations must be injected explicitly. `general.create_task` and `general.update_goal` carry a proposal-only contract (output `proposal` + `binding`) and never imply direct effects.
- Permission policy is low-risk/fail-closed: no automatic external actions, no sensitive inference, no memory write, no file modification.
- Memory is accessed via proposals only (`allow_write=False`).
- Specialized domains always prevail when valid and authorized.
- General Domain is not added as a supporting domain by default.

⸻

10.20 - Health Domain

**Status:** Complete and audited (2026-08-08).

Objective

Specify CMM OS to organize health information, analyse temporary evolution, prepare consultations and detect contradictions or signs that require professional review.

The Health Domain will not provide final diagnoses and will not replace health care professionals.

Entidades

* symptom;
* diagnosis;
* medication;
* treatment;
* medical_test;
* medical_report;
* specialist;
* appointment;
* procedure;
* surgery;
* allergy;
* adverse_effect;
* vital_sign;
* medical_condition;
* healthcare_provider.

Resources

* medical_report;
* prescription;
* medication_list;
* symptom_log;
* laboratory_result;
* imaging_report;
* appointment;
* discharge_report;
* treatment_plan;
* user_message;
* health_memory;
* external_medical_source.

Rules

DistinguishSymptomDiagnosisHypothesis

The difference between:

* an established symptom,
* clinical observation
* documented diagnosis
* guidance diagnosis
* system hypothesis
* possibility put forward by the user.

MedicationTemporalRelationshipRule

Analiza:

* start date;
* dose change;
* symptoms occur.
* retirada;
* re-exposure
* temporary evolution.

MedicalRedFlagRule

Detects information that may require:

* urgent care
* query preferred;
* Professional review
* monitoring.

ClinicalSourcePriorityRule

Prioriza:

* Medical report
* Test result
* receta;
* profesional identificado;
* Primary Medical Source
* a statement by the user;
* inferencia.

MedicalTemporalValidityRule

Checks:

* tratamientos activos;
* Withdrawal medication
* provisional diagnoses
* pending tests;
* obsolete results;
* citas futuras;
* state changes.

MedicationConsistencyRule

Detecta:

* dosis incompatible;
* listados diferentes;
* dual medication
* fechas incoherentes;
* treatments listed as an asset and withdrawn.

NoDefinitiveDiagnosisRule

It prevents a diagnosis.

ProfessionalEscalationRule

Scale if:

* exista riesgo;
* Lack of exploration
* missing tests;
* there is a significant deterioration.
* the user requests a clinical decision;
* The system cannot solve an important contradiction.

Operaciones

* health.build_medical_timeline;
* health.build_symptom_timeline;
* health.compare_reports;
* health.compare_test_results;
* health.review_medication_changes;
* health.prepare_medical_appointment;
* health.generate_medical_summary;
* health.prepare_questions;
* health.register_symptom_update;
* health.detect_open_medical_questions;
* health.review_follow_up;
* health.export_medical_context.

Workflows

Medical Follow-up

Symptom Review

Medication Change Review

Specialist Appointment Preparation

Medical Report Comparison

Postoperative Follow-up

Chronic Condition Timeline

Diagnostic Process Review

Presentation

The result should separate:

* documented information;
* Reported symptoms
* cambios temporales;
* hypotheses
* contradicciones;
* information missing,
* alarm signals
* Questions for consultation
* next steps authorized.

Permissions

* sensibilidad alta;
* acceso multi-domain restringido;
* inferencias sensitive limitadas;
* without automatic diagnosis,
* without change of medication,
* without automatic external communications
* without writing of clinical decisions
* confirmation for sensitive memory
* Mandatory human climbing as appropriate.

### Implementation notes

- `domain:health` is implemented via pure factories under `cmm/domains/health/`.
- 14 modules (including the `catalog.py` single source of truth and the `__init__.py` public surface), plus 17 test modules.
- The canonical catalog (`cmm/domains/health/catalog.py`) is the single source of truth for the 12 operations, 8 rules, 15 entities, 12 resources, and 8 workflows, all derived from the sorted-tuple convention.
- `DomainKind` is `PERSONAL` and all health resources are `HIGHLY_SENSITIVE`.
- Registration is atomic via validation-first semantics plus snapshot/restore rollback across all registries (mirrors General).
- Canonical bootstrap: `build_standard_health_domain_bootstrap()` composes General + Health on the SAME registries (it reuses `build_standard_general_domain_bootstrap()` and registers the complete Health Domain into those exact registries), and exposes a `DefaultDomainResolver` configured with `fallback_domain=DomainId(slug="general")`. A generic request resolves to General; a Health signal routes to Health when eligible and is fail-closed (never silently diverted to General) when it is not.
- Operations are declared and remain **UNAVAILABLE** by default (fail-closed); real implementations must be injected explicitly. Higher-risk operations (e.g. `health.export_medical_context`, `health.register_symptom_update`) are approval-gated. `export_medical_context` is a **PREPARATION** operation: it prepares structured, exportable context (context/references/provenance/uncertainty) for a clinician and performs no external transmission.
- Permission policy is HIGH-sensitivity, fail-closed: read-only surface, no automatic external communications, no memory write, no sensitive-inference persistence, no definitive diagnosis.
- Memory is proposal-only (`allow_write=False`); Health never autonomously makes a definitive diagnosis, changes medication, or overrides clinician instructions.
- `NoDefinitiveDiagnosisRule` blocks any non-documented diagnosis claim; `ProfessionalEscalationRule` blocks under risk factors and requests human review.
- General Domain remains the fallback, but Section 15 is honored: a desired Health signal is never silently absorbed by General when Health is unavailable, denied, unauthorized, or disabled (it resolves BLOCKED instead).

⸻

10.21 - Relationships Domain

**Status:** Complete and audited (2026-08-09).

Objective

Specify CMM OS to discuss links, events, patterns, emotions, needs and boundaries without attributing intents as events.

Entidades

* person;
* relationship;
* conversation;
* interaction;
* conflict;
* boundary;
* need;
* emotion;
* expectation;
* commitment;
* rupture;
* reconciliation;
* support_event.

Resources

* user_message;
* conversation;
* relationship_event;
* note;
* memory_entry;
* timeline;
* communication;
* personal_reflection.

Rules

SeparateRelationshipFactInterpretationRule

Distingue:

* What happened?
* What did each person say?
* What did the user interpret?
* What interpretation does the system propose?

DoNotInferIntentRule

It prevents them from clobjectiveing their intents without direct evidence.

RelationshipTimelineRule

Ordena:

* acercamientos;
* distanciamientos;
* conflicts;
* reparaciones;
* frequency changes;
* compromisos;
* limits.

PatternWithoutCertaintyRule

It allows to detect patterns as hypotheses, but as facts.

EmotionNeedDistinctionRule

Distingue:

* emotion
* necesidad;
* deseo;
* expectativa;
* interpretation
* conducta.

BoundaryConsistencyRule

Analiza:

* expressed limits;
* applied limits
* incumplimientos;
* cambios;
* contradicciones.

AmbivalencePreservationRule

He retains contradictory feelings without forcing a single reading.

SelfOtherPerspectiveRule

Separa:

* personal experience;
* conducta observable ajena;
* posible perspectiva ajena;
* information unknown.

Operaciones

* relationships.build_timeline;
* relationships.compare_periods;
* relationships.extract_events;
* relationships.detect_patterns;
* relationships.separate_facts_interpretations;
* relationships.identify_needs;
* relationships.review_boundaries;
* relationships.prepare_conversation;
* relationships.generate_relationship_summary;
* relationships.track_open_questions.

Workflows

Relationship Timeline Analysis

Conflict Review

Boundary Review

Difficult Conversation Preparation

Pattern Evolution Review

Relationship Decision Support

Presentation

The result should separate:

* hechos;
* declaraciones;
* emociones;
* necesidades;
* interpretaciones;
* hypotheses
* patrones;
* contradicciones;
* preguntas abiertas;
* posibles acciones.

Permissions

* sensibilidad alta;
* Prohibition of inferring diagnoses about third parties
* Prohibition of clobjectiveing intents
* controlled memory writing
* confirmation for relative decisions
* absence of automatic communications
* No breakup or contact actions without approval.

⸻

10.22 - University Domain

**Status:** Complete and audited (2026-08-12).

Objective

Specify CMM OS to manage subjects, convocation, jobs, performance, academic burden and university planning.

Entidades

* degree;
* university;
* academic_year;
* semester;
* subject;
* assignment;
* examination;
* exam_attempt;
* grade;
* deadline;
* professor;
* adaptation;
* credit;
* academic_requirement.

Resources

* academic_record;
* subject_guide;
* university_calendar;
* examination_schedule;
* assignment;
* grade;
* email;
* note;
* study_session;
* user_message;
* regulation;
* memory_entry.

Rules

AcademicDeadlineRule

Checks dates, calls, and deadlines.

ECTSConsistencyRule

Valida:

* credit entered,
* advanced credit
* pending load;
* requisitos;
* incompatibilidades.

ExamAttemptRule

Distingue:

* convocatoria ordinaria;
* re-evaluation
* intentos;
* exhaustion of exam attempts;
* cambios normativos.

AcademicWorkloadRule

Valves load according to:

* asignaturas;
* dificultad;
* fechas;
* tiempo disponible;
* health;
* other goals.

AcademicDependencyRule

Detecta:

* prerrequisitos;
* dependencies;
* asignaturas necesarias;
* final degree project deadlines;
* academic record closure.

ObservedPerformanceCapacityRule

Avoid confusing observed performance with intellectual or potential capacity.

AcademicTemporalValidityRule

Checks:

* curso;
* semestre;
* teacher guide
* convocatoria;
* normativa;
* date of assessment.

Operaciones

* university.plan_semester;
* university.create_study_plan;
* university.review_academic_record;
* university.compare_semesters;
* university.prepare_exam;
* university.prepare_assignment;
* university.track_deadlines;
* university.analyse_performance;
* university.generate_academic_summary;
* university.update_subject_status;
* university.review_degree_completion.

Workflows

Semester Planning

Exam Preparation

Academic Review

Reassessment Planning

Assignment Preparation

Degree Completion Review

TFG Planning

Presentation

* asignaturas;
* states;
* fechas;
* dependencies;
* loading;
* riesgos;
* escenarios;
* plan;
* progreso;
* next review.

Permissions

* development of reversible plans
* creation of authorized tasks
* acceso a calendario controlado;
* sending and approving e-mails
* without registration or automatic registration
* without final academic decisions
* external check for changing standards.

⸻

10.23 - Opposition Domain

Statement

Complete — independently audited.

Objective

Specialize CMM OS to manage opposition exams, syllabi, calls, progress, mock exams, workload, risks, and alternative paths.

Entidades

* opposition;
* public_body;
* call;
* exam;
* syllabus;
* topic;
* block;
* mock_exam;
* score;
* study_session;
* deadline;
* requirement;
* merit;
* alternative_route.

Resources

* official_call;
* syllabus;
* regulation;
* study_plan;
* mock_exam;
* score_record;
* calendar_event;
* note;
* user_message;
* external_official_source;
* memory_entry.

Rules

OfficialCallPriorityRule

Prioritizes calls and official sources.

OppositionTemporalValidityRule

Checks:

* convocatoria vigente;
* plazo;
* exam date;
* temario actual;
* normativa;
* requisitos.

SyllabusCoverageRule

Evaluates:

* temas estudiados;
* temas pendientes;
* profundidad;
* repaso;
* olvido;
* simulacros.

StudyFeasibilityRule

Relates:

* tiempo;
* energy
* health;
* universidad;
* trabajo;
* target date.

MockExamInterpretationRule

Distingue:

* rendimiento puntual;
* tendencia;
* knowledge
* velocidad;
* format errors.

AlternativeRouteRule

It allows to compare bodies and routes without treating an alternative as abandonment.

Operaciones

* oppositions.create_study_plan;
* oppositions.divide_syllabus;
* oppositions.track_progress;
* oppositions.review_mock_exam;
* oppositions.compare_bodies;
* oppositions.review_call;
* oppositions.generate_weekly_review;
* oppositions.identify_risks;
* oppositions.generate_revision_plan;
* oppositions.update_progress.

Workflows

Opposition Setup

Weekly Study Review

Mock Exam Review

Call Analysis

Syllabus Revision

Alternative Route Comparison

Exam Readiness Review

Permissions

* query external preferably official;
* Mandatory monitoring of calls
* without automatic registration,
* without payment;
* without giving up targets without an explicit decision,
* Modifiable schedules only under authorisation.

⸻

10.24 - Reflection Domain

Status

Phase 10.24 — Complete — independently audited.

Objective

Specify CMM OS to develop complex reflections, explore hypotheses, organize ideas and preserve ambivalence without requiring a unique conclusion.

Entidades

* reflection;
* belief;
* value;
* question;
* hypothesis;
* emotion;
* need;
* conflict;
* identity_narrative;
* decision;
* uncertainty.

Resources

* user_message;
* conversation;
* note;
* journal_entry;
* memory_entry;
* relationship_event;
* life_event;
* goal;
* decision.

Rules

MultipleHypothesesRule

Mantiene varias explicaciones posibles.

PreserveAmbivalenceRule

Avoids resolving emotional contradictions artificially.

BeliefEvidenceRule

Separa:

* creencia;
* evidencia;
* contraevidencia;
* experiencia;
* interpretation.

OpenQuestionRule

Keep questions without an answer if there's insufficient basis.

ReflectionTemporalEvolutionRule

Compare how an idea has evolved.

NoForcedConclusionRule

It allows to complete a workflow without a final conclusion.

Operaciones

* reflection.structure_reflection;
* reflection.extract_beliefs;
* reflection.compare_versions;
* reflection.identify_open_questions;
* reflection.generate_hypotheses;
* reflection.build_personal_timeline;
* reflection.prepare_notion_entry;
* reflection.generate_summary;
* reflection.review_decision.

Workflows

Structured Reflection

Belief Review

Personal Question Exploration

Decision Reflection

Identity Narrative Review

Longitudinal Reflection Review

Permissions

* alta sensibilidad;
* restricted identity inferences;
* confirmation for semantic memory
* without automatic personal decisions
* without presenting psychological hypotheses as diagnostics.

⸻

**10.25** - **Concerns Domain**

Status

Complete. Independently audited.

Canonical specification:

`docs/superpowers/specs/2026-08-21-concerns-domain-design.md`

Implementation reference:

`docs/reference/concerns-domain.md` (`cmm/domains/concerns/`)

Objective

Specialize CMM OS for conversations in which the user brings a problem,
worry, fear, uncertainty, "rayada", ambiguous situation, repeated concern,
difficult decision, need for reassurance, or need simply to talk something
through.

Concerns is not primarily a risk-analysis domain.

Its central flow is:
```text
Understand the concern
↓
Understand why it matters to the user
↓
Resolve or cautiously infer the current support need
↓
Think through the situation with the user
↓
Separate reality, interpretation, fear, hypothesis, scenario and uncertainty
when useful
↓
Reassure when evidence supports reassurance
OR
acknowledge a real concern when evidence supports it
OR
preserve uncertainty when it cannot be resolved
↓
Explore options or a next step only when useful or wanted
↓
Continue talking when no action is needed
```

Core invariants

```text
concern support != risk analysis only
being helpful != forcing action
being reassuring != inventing certainty
being validating != confirming every interpretation
being analytical != becoming emotionally cold
being cautious != becoming alarmist
repetition != pathology
uncertainty != danger
emotion != evidence
```

Architecture

Implement exactly one specialized Domain Pack:

```text
cmm/domains/concerns/
```

using the shared hardened Phase 10 package boundary:

```text
__init__.py
bootstrap.py
catalog.py
definition.py
integration.py
memory.py
operations.py
permissions.py
presentation.py
profile.py
resources.py
rules.py
trace.py
workflows.py
```

Concerns must not introduce a parallel planner, agent runtime, memory store,
knowledge store, workflow engine, permission engine, temporal engine, or
conversation engine.

It reuses shared Phase 8, Phase 9 and Phase 10 infrastructure.

Semantic behavior and communication style remain separate.

Concerns determines what should be understood, which distinctions matter,
whether reassurance is justified, whether material concern exists, whether
uncertainty remains open, whether another domain should participate, and
whether action is useful.

It does not define a fixed assistant personality. Surface warmth, register,
verbosity, rhythm and channel behavior remain shared presentation concerns
and later Phase 11 Communication Profiles.

Support Need

The central conversational concept is:

```text
support_need
```

Canonical values:

```text
UNDERSTANDING
EXPLORATION
PERSPECTIVE
REALITY_CHECK
REASSURANCE
INFORMATION
PROBLEM_SOLVING
DECISION_SUPPORT
EMOTIONAL_PROCESSING
NEXT_STEP
MIXED
UNCLEAR
```

A support need is a current conversational hypothesis, not a diagnosis,
personality trait or durable identity.

Explicit current user intent has precedence over inference or historical
preference.

Entities — exactly 17

```text
concern
situation
trigger
emotion
fear
need
support_need
fact
interpretation
hypothesis
scenario
evidence
uncertainty
risk
desired_outcome
option
action
```

Resources — exactly 10

```text
user_message
conversation
note
journal_entry
memory_entry
event
goal
decision
domain_result
external_source
```

Rules — exactly 14

```text
UnderstandBeforeInterveneRule
EmotionalValidationRule
ExperienceRealitySeparationRule
SupportNeedCalibrationRule
ContextualQuestionRule
UncertaintyPreservationRule
EvidenceCalibratedReassuranceRule
ProportionalRiskRule
NoCatastrophicEscalationRule
NoFalseReassuranceRule
RepetitionWithoutPathologizingRule
AgencyWithoutPressureRule
DirectnessWithoutHarshnessRule
ImmediateRiskEscalationRule
```

Key semantics

`UnderstandBeforeInterveneRule`

Do not automatically jump from concern to advice, coping instructions,
monitoring, or an action plan. Respond directly when sufficient context
already exists.

`EmotionalValidationRule`

Preserve the legitimacy of the user's lived emotional experience without
promoting an interpretation of external reality to fact.

```text
valid emotional experience != verified external interpretation
```

`ExperienceRealitySeparationRule`

When useful, distinguish:

```text
what happened
what the user experienced
what the user interpreted
what the user fears
what is hypothesized
what may happen
what remains unknown
```

Required distinctions include:

```text
fact != interpretation
interpretation != fear
fear != prediction
prediction != fact
possibility != probability
emotional certainty != evidential certainty
```

`SupportNeedCalibrationRule`

Resolve or cautiously infer what type of support is currently useful.
The inferred need remains revisable throughout the conversation.

`ContextualQuestionRule`

Questions are tools, not rituals. Ask only when the answer would materially
change interpretation, reassurance, risk, routing, decision, or next step.

`UncertaintyPreservationRule`

Preserve genuine uncertainty rather than inventing certainty either to
comfort or to warn. Uncertainty may coexist with reassurance.

`EvidenceCalibratedReassuranceRule`

Reassurance is explicitly allowed when evidence supports it.

Canonical outcomes:

```text
REASSURANCE_SUPPORTED
REASSURANCE_PARTIAL
UNCERTAIN
CONCERN_SUPPORTED
INSUFFICIENT_BASIS
```

Reassurance must remain evidence-calibrated and must not become false
certainty.

`ProportionalRiskRule`

Risk analysis remains available but is not the center of every concern
conversation. Emotional intensity does not determine objective risk.

`NoCatastrophicEscalationRule`

Do not silently promote:

```text
possibility → probability
ambiguity → warning sign
change → deterioration
silence → rejection
symptom → serious disease
setback → failure
uncertainty → danger
```

without adequate evidence.

`NoFalseReassuranceRule`

Do not erase real warning signals merely to comfort the user.

`RepetitionWithoutPathologizingRule`

Returning to the same concern is not automatically a harmful reassurance
loop.

```text
same topic != same question
same question != pathological repetition
repetition != compulsion
continued distress != irrationality
need for further understanding != reassurance seeking
```

The system may revisit the concern and reassure again.

A possible repetitive certainty-seeking pattern requires multiple grounded
signals across turns and must never become an automatic psychiatric
interpretation or conversational punishment.

`AgencyWithoutPressureRule`

Canonical action states:

```text
NO_ACTION_NEEDED
ACTION_OPTIONAL
ACTION_USEFUL
ACTION_RECOMMENDED
DOMAIN_ESCALATION_NEEDED
USER_DECISION_REQUIRED
```

The user may legitimately wait, observe, think, continue talking, act later,
or take no action.

`DirectnessWithoutHarshnessRule`

The system may give a grounded opinion and may respectfully disagree.

Empathy does not require agreement.

`ImmediateRiskEscalationRule`

Credible immediate risk is routed through existing shared or specialized
contracts. Ordinary worry, sadness, fear or uncertainty must not silently
become a crisis workflow.

Profile

Default specialized cognitive profile:

```text
ConcernSupportProfile
```

Its reasoning configuration prioritizes:

```text
high contextual sensitivity
high epistemic discipline
high tolerance for uncertainty
high emotional-context awareness
moderate-to-high interpretive openness
low default action pressure
low default alarm
evidence-calibrated reassurance
willingness to state a grounded opinion
targeted questioning
cross-domain awareness
```

The profile does not encode a fixed communication persona.

Operations — exactly 13

```text
concerns.understand_concern
concerns.infer_support_need
concerns.map_lived_experience
concerns.separate_reality_interpretation
concerns.explore_hypotheses
concerns.calibrate_uncertainty
concerns.evaluate_reassurance
concerns.evaluate_risk
concerns.identify_open_questions
concerns.explore_options
concerns.prepare_next_step
concerns.review_recurring_concern
concerns.prepare_professional_discussion
```

Operations are analytical or preparatory.

They do not directly send messages, contact professionals, modify calendars,
publish, write semantic memory, execute personal decisions, or start
continuous monitoring.

Workflows — exactly 8

```text
Open Concern Conversation
Talk It Through
Reality Check
Reassurance Review
Practical Problem Solving
Decision Under Uncertainty
Recurring Concern Review
Professional Discussion Preparation
```

A valid workflow may end with:

```text
better understood
reassured
partially reassured
still uncertain
material concern acknowledged
decision deferred
no action necessary
continue talking
```

No workflow is required to produce a conclusion, action plan, risk matrix,
or monitoring plan.

First-response behavior

The first response should normally:

1. identify the core issue;
2. recognize why it matters where useful;
3. give substantive perspective immediately when enough context exists;
4. ask a question only if materially necessary;
5. avoid dumping a framework, checklist or generic coping protocol.

Reassurance behavior

The system may provide reassurance repeatedly while it remains grounded.

Repeated discussion must not automatically trigger refusal,
pathologization, or a claim that reassurance itself is harmful.

No forced positivity

Alternative explanations may be explored when plausible, but must not erase
genuine negative evidence.

```text
less negative explanation exists
!=
less negative explanation is true
```

No forced cognitive correction

The domain must not assume:

```text
distress = distorted thought
```

Cross-domain composition

Concerns owns:

```text
concern support
support need
fear and uncertainty framing
reassurance calibration
problem exploration
action pressure
recurring-concern review
```

Specialized domains remain responsible for their own factual and risk
semantics.

Required initial compositions include:

```text
General + Concerns
Relationships + Concerns
Health + Concerns
Reflection + Concerns
University + Concerns
Oppositions + Concerns
Life Plan + Concerns
Project + Concerns
```

No direct private-store access between domains.

Memory

Concern state is sensitive.

The domain may produce memory proposals through shared contracts but must
not silently persist fear, support need, inferred emotional patterns,
recurring-concern patterns, psychological interpretations, risk
interpretations, or third-party motives.

```text
conversation state != semantic memory
```

Permissions

Concerns is a high-sensitivity personal domain.

Required intentions include:

```text
cross-domain access only through authorized projections
no diagnosis
no third-party diagnosis
no automatic personal decisions
no automatic external communication
no automatic semantic-memory persistence
no autonomous monitoring by default
no hidden risk escalation
no unrestricted external research
```

Unknown or malformed authorization fails closed.

Safety

Safety behavior must remain proportional.

Do not automatically convert:

```text
sadness → suicide workflow
health worry → emergency
relationship conflict → abuse classification
repeated worry → psychiatric interpretation
```

When credible immediate risk exists, use the relevant shared policy or
specialized domain.

Trace

The domain trace must expose why Concerns was selected, which supporting
domains participated, what support need was explicit or inferred, which
resources and evidence were used, what uncertainty remained, whether
reassurance or material concern was supported, why questions were asked,
why action was or was not proposed, what memory proposal was created, and
what permissions constrained the result.

DP-025

CMM OS must support a user through a problem, worry, fear or uncertainty by:

- understanding the situation and its lived significance;
- resolving or cautiously inferring the current support need;
- preserving emotional experience without promoting interpretation to fact;
- distinguishing reality, interpretation, hypothesis, fear, scenario and
  uncertainty when relevant;
- providing evidence-calibrated reassurance when justified;
- acknowledging material concern when justified;
- avoiding catastrophic escalation and false reassurance;
- revisiting recurring concerns without automatically pathologizing repetition;
- asking only materially useful questions;
- supporting action and decisions without forcing them;
- coordinating with specialized domains for factual and risk semantics;
- preserving provenance, permissions, uncertainty and memory boundaries.

Canonical acceptance identifiers:

```text
DP-025
AT-DP-025
```

The exhaustive behavioral, adversarial, rollback, permission, memory,
cross-domain, deterministic and E2E requirements are defined in:

`docs/superpowers/specs/2026-08-21-concerns-domain-design.md`

Completion criteria

Phase 10.25 is complete when:

- one canonical `domain:concerns` Domain Pack exists;
- the hardened shared package boundary is preserved;
- exactly 17 entities, 10 resources, 14 rules, 13 operations and
  8 workflows are canonical;
- `ConcernSupportProfile` uses shared profile infrastructure;
- reassurance is allowed when supported;
- false reassurance and catastrophic escalation are prevented;
- emotional validation does not inflate facts;
- recurrence is not automatically pathologized;
- questions are materially useful;
- grounded direct opinions are possible;
- action remains proportional and under user control;
- sensitive inference is not silently persisted;
- cross-domain composition works;
- permissions fail closed;
- bootstrap is atomic;
- rollback is complete;
- fresh import is side-effect free;
- focused, domain and global suites are green;
- `AT-DP-025` passes;
- independent audit leaves no unresolved blocking finding.

Implementation status (2026-08-21)

- One canonical `cmm/domains/concerns/` Domain Pack exists with exactly the
  hardened 14-module boundary.
- Exactly 17 entities, 10 resources, 14 rules, 13 operations and 8 workflows
  are canonical (`catalog.py` single source of truth).
- `ConcernSupportProfile` is bound through the shared profile infrastructure.
- Reassurance is evidence-calibrated; false reassurance and catastrophic
  escalation gates are executable and green.
- Emotional validation never inflates facts; recurrence review never
  pathologizes (`pathology_inferred=False` always); pattern recognition
  requires all five grounded dimensions.
- Questions are material-only; grounded disagreement is possible; action
  remains proportional, proposal-only and user-controlled.
- Sensitive content kinds cannot be silently persisted under any
  authorization chain; permissions fail closed on literal-boolean semantics.
- Bootstrap is atomic validation-first with complete snapshot/restore
  rollback at every registration boundary; fresh import registers nothing.
- Focused, all-domain and global verification suites are green; fresh closure
  evidence is recorded in the Phase 10.25 final closure audit.
- `AT-DP-025`: connected 25-step acceptance scenario plus named gates —
  `PASS`, independently audited.
- Independent audit: complete. All blocking findings from the audit,
  re-audit, final-audit and closure-audit sequence were remediated; the final
  independent closure check is `PASS` with no unresolved blocking finding.

⸻

10.26 - Languages Domain

**Status:** Complete — independently audited and closed. Final independent closure audit: PASS; BLOCKERS=0; MAJORS=0; MINORS=0; AT-DP-026: PASS; DP-026: VERIFIED_EXISTING.

Canonical design:

`docs/superpowers/specs/2026-08-23-languages-domain-design.md`

Canonical identity:

```text
domain:languages
Display name: Idiomas
Profile: LanguageLearningProfile
```

Objective

Specialize CMM OS as an active language-learning tutor and rigorous
longitudinal learning system while preserving the shared Kernel,
Cognitive Layer, Knowledge Model, Agent Runtime, Planner, Workflow
System, Validation System, permissions, and memory contracts.

The domain is multi-language by design, supports multiple concurrent
goals per language, and distinguishes preferred language variety from
exclusive correctness.

Canonical proficiency invariants:

```text
certified proficiency != estimated proficiency
estimated proficiency != observed performance
global proficiency != proficiency by skill
practice result != stable proficiency
certification readiness != general proficiency
```

Canonical error and progression invariants:

```text
observed error != recurrent error pattern
better score once != demonstrated stable progression
valid language variety != error
transcript alone != pronunciation evidence
```

### Entities — 16

```text
language
language_variety
skill_dimension
language_goal
proficiency_framework
proficiency_record
assessment_evidence
practice_session
exercise
observed_error
error_pattern
vocabulary_item
grammar_topic
certification_target
review_item
learning_plan
```

### Resources — 15

```text
user_message
conversation
writing_sample
audio_transcript
exercise_result
assessment_result
language_plan
lesson_material
vocabulary_list
language_reference
certification_guide
official_certification_source
calendar_event
memory_entry
domain_result
```

### Rules — 14

```text
LanguageLevelEvidenceRule
SkillSeparationRule
LanguageVarietyValidityRule
ProficiencyFrameworkRule
ErrorPatternEvidenceRule
CorrectionPriorityRule
AdaptiveDifficultyRule
SpacedReviewRule
LearningLoadRule
GoalAlignmentRule
ProgressionEvidenceRule
CertificationTemporalRule
CulturalContextEvidenceRule
LanguageMemoryConsentRule
```

### Operations — 15

```text
languages.assess_sample
languages.update_level_evidence
languages.create_learning_plan
languages.generate_lesson
languages.generate_exercises
languages.review_exercise
languages.review_writing
languages.generate_conversation_turn
languages.generate_roleplay_turn
languages.review_speaking
languages.review_errors
languages.track_vocabulary
languages.plan_review_schedule
languages.prepare_certification
languages.generate_progress_review
```

### Workflows — 9

```text
Language Onboarding
Proficiency Assessment
Adaptive Language Lesson
Conversation & Roleplay Practice
Writing Review
Error Remediation
Vocabulary & Spaced Review
Certification Preparation
Progress Review
```

Canonical Progress Review workflow ID:

```text
languages.progress_checkpoint
```

Pedagogical modes:

```text
teach
practice
assess
review
certification
immersion
```

Permissions

```text
low-risk internal pedagogy
consent-gated longitudinal progress tracking
shared approval for external mutations
no automatic external actions
calendar proposal != calendar write
```

Memory

```text
session observation != persistent memory
observed error != persistent recurrent pattern
candidate update != confirmed persistence
cross-domain relevance != unrestricted sharing
```

Cross-domain ownership:

```text
Languages
→ language competence, teaching, practice, correction,
  certification preparation and progression

University
→ academic objective and university obligations

Oppositions
→ opposition objective, requirements and deadlines

General
→ non-linguistic knowledge/content

Concerns
→ worry, uncertainty and reassurance

Reflection
→ personal meaning, identity and broad reflection
```

The domain owning the objective is primary. Languages is supporting
when it supplies specialized linguistic competence to another primary
domain.

Phase 10.26 completed its independent closure process successfully.
`AT-DP-026` passes as a connected 45-checkpoint acceptance scenario over the
real shared resolver, composer, Workflow Engine, calendar permission boundary,
memory, projection, presentation, and independently inventoried typed trace
paths.

Current status:

- Phase 10.26: Complete — independently audited and closed
- AT-DP-026: PASS
- DP-026: VERIFIED_EXISTING
- final independent closure audit: PASS
- BLOCKERS=0; MAJORS=0; MINORS=0

⸻

10.27 - Paternidad Domain

**Status:** Complete — independently audited and closed. Final independent closure audit: PASS; BLOCKERS=0; MAJORS=0; MINORS=0; AT-DP-027: PASS; DP-027: VERIFIED_EXISTING.

## Objective

Specialize CMM OS to support parenthood as one coherent domain covering both:

1. the path to becoming a parent; and
2. the long-term exercise of parenting for each child.

The domain must preserve a single architectural identity while exposing different functional spaces according to the stage of the parenting project.

## Canonical Identity

```text
domain:parenthood
```

Public display name:

```text
Paternidad
```

The architecture must not encode:

- a particular child's personal name;
- a particular route to parenthood;
- legacy personal project names;
- legacy abbreviations associated with a specific route.

Personal names belong only to presentation and user data.

---

## Functional Requirement Sources

Phase 10.27 uses two canonical prompt specifications as functional requirement sources:

- `docs/roadmap/requirements/parenthood/camino-a-la-paternidad.md` for `parenthood.journey`;
- `docs/roadmap/requirements/parenthood/paternidad.md` for `parenthood.child:<child_id>`.

Their role is to refine expected domain behavior, rules, operations, workflows, questions, presentation expectations and acceptance criteria.

They are not independent Domain Packs and they are not executable policy.

Prompt requirements must remain subordinate to Kernel contracts, Cognitive Layer epistemic rules, Agent Runtime policy, validation, permissions, privacy, approval requirements, cross-domain restrictions and memory policy.

Material behavior derived from these sources should be traceable to a domain rule, operation, workflow or acceptance test.

## Functional Structure

```text
Paternidad
├── Camino a la Paternidad
│   └── parenthood.journey
│
└── Hijos
    ├── parenthood.child:<child_id>
    ├── parenthood.child:<child_id>
    └── parenthood.child:<child_id>
```

The public interface may display each child workspace using that child's configured name.

Example:

```text
Paternidad
├── Camino a la Paternidad
├── <nombre del hijo 1>
├── <nombre del hijo 2>
└── <nombre del hijo N>
```

Internally:

```text
domain:parenthood

workspace:parenthood-journey-001

child:001
display_name:<configured child name>

child:002
display_name:<configured child name>
```

A child's name is presentation data and must never become a Domain Pack identifier.

---

# Functional Area — Camino a la Paternidad

## Objective

Support the planning and supervised management of the process of becoming a parent.

This functional area covers the period before the exercise of day-to-day parenting begins and may remain available afterwards as historical context.

## Scope

It may organize:

- parenthood goals;
- family-building and reproductive pathways;
- jurisdictions;
- medical pathways;
- medical providers;
- relevant participants;
- medical preparation;
- legal requirements;
- administrative requirements;
- documentation;
- financial scenarios;
- ethical constraints;
- timelines;
- travel and logistics;
- decisions;
- risks;
- transition to birth and parenthood.

The public product name is always **Camino a la Paternidad**.

The architecture must use generic parenthood terminology and must not expose legacy route-specific abbreviations as product or domain identifiers.

## Entities

- `parenthood_goal`;
- `parenthood_pathway`;
- `jurisdiction`;
- `medical_pathway`;
- `medical_provider`;
- `participant`;
- `legal_requirement`;
- `administrative_requirement`;
- `documentation_requirement`;
- `financial_scenario`;
- `ethical_constraint`;
- `timeline`;
- `decision`;
- `risk`;
- `birth_transition`.

## Resources

- `life_plan`;
- `legal_document`;
- `medical_report`;
- `financial_plan`;
- `provider_information`;
- `jurisdiction_information`;
- `decision`;
- `note`;
- `user_message`;
- `external_source`;
- `memory_entry`.

## Rules

### ParenthoodDecisionExplicitRule

Prevents registration of decisions that have not been explicitly adopted by the user.

### LegalTemporalValidityRule

Requires current verification when legal or administrative information may have changed.

### MedicalLegalSeparationRule

Keeps medical, legal, economic and administrative requirements distinguishable.

### EthicalConstraintRule

Preserves the user's ethical criteria as explicit constraints.

### CostUncertaintyRule

Preserves ranges, contingencies and unconfirmed costs.

### JourneyDependencyRule

Relates timing, finances, housing, personal circumstances, medical requirements, legal requirements and other dependencies without converting them into automatic decisions.

### JourneyToChildBoundaryRule

Prevents pre-parenthood operational material from being copied wholesale into a child's parenting workspace.

Only information relevant to the child's ongoing care, identity, health, documentation or family context may be proposed for transfer.

## Operations

- `parenthood.journey.build_timeline`;
- `parenthood.journey.compare_pathways`;
- `parenthood.journey.review_requirements`;
- `parenthood.journey.review_financial_scenarios`;
- `parenthood.journey.prepare_questions`;
- `parenthood.journey.track_decisions`;
- `parenthood.journey.update_plan`;
- `parenthood.journey.generate_documentation_checklist`;
- `parenthood.journey.review_risks`.

## Workflows

- Path to Parenthood Review;
- Pathway Comparison;
- Provider Review;
- Requirements Review;
- Financial Readiness Review;
- Medical Preparation Review;
- Documentation Review;
- Annual Journey Plan Update.

---

# Functional Area — Child Parenting Workspaces

## Objective

Support the exercise of parenthood and the long-term upbringing of each child through an independent child workspace inside the shared Paternidad domain.

Each child must have a stable internal identifier.

The visible workspace name may use the child's configured personal name.

## Child Workspace Contract

Conceptual model:

```python
ChildParentingWorkspace(
    id="child:001",
    domain_id="domain:parenthood",
    display_name="<configured child name>",
    status="active",
    developmental_stage=None,
    created_at="...",
    metadata={},
)
```

The internal identity must remain stable even if the public display name changes.

## Entities

- `child`;
- `developmental_stage`;
- `care_need`;
- `routine`;
- `milestone`;
- `education_plan`;
- `school`;
- `activity`;
- `health_context`;
- `wellbeing_signal`;
- `family_context`;
- `support_network`;
- `parental_decision`;
- `value`;
- `boundary`;
- `schedule`;
- `residence_plan`;
- `long_term_plan`.

## Resources

- `parenting_note`;
- `education_document`;
- `child_development_resource`;
- `health_summary`;
- `schedule`;
- `parental_decision`;
- `school_information`;
- `activity_information`;
- `user_message`;
- `external_source`;
- `memory_entry`.

## Rules

### ChildInterestAndWellbeingRule

Requires recommendations and plans to consider the child's safety, wellbeing, development and individual needs.

### DevelopmentalContextRule

Requires reasoning to account for the child's developmental stage.

### AgeAppropriateGuidanceRule

Rejects recommendations incompatible with age, maturity or current capabilities.

### ParentChildBoundaryRule

Distinguishes the parent's goals, preferences and concerns from the child's own needs, preferences and developing autonomy.

### HealthBoundaryRule

Allows relevant health context without duplicating the Health domain or making autonomous clinical decisions.

### EducationBoundaryRule

Allows educational planning while delegating specialized assessment to the appropriate domain when necessary.

### MinorPrivacyRule

Applies restrictive handling to information concerning minors.

### LongTermContinuityRule

Relates present parenting decisions to long-term objectives while allowing plans to evolve.

### ParentalUncertaintyRule

Preserves uncertainty and alternatives where no single objectively correct parenting choice exists.

### SiblingIdentityIsolationRule

Prevents histories, health information, needs, preferences or decisions from being silently merged between different children.

## Operations

- `parenthood.child.review_needs`;
- `parenthood.child.review_developmental_stage`;
- `parenthood.child.plan_routines`;
- `parenthood.child.prepare_parental_decision`;
- `parenthood.child.review_education_plan`;
- `parenthood.child.review_family_context`;
- `parenthood.child.track_milestones`;
- `parenthood.child.prepare_questions`;
- `parenthood.child.track_decisions`;
- `parenthood.child.update_parenting_plan`;
- `parenthood.child.review_risks_and_needs`.

## Workflows

- Child Needs Review;
- Developmental Stage Review;
- Education Planning Review;
- Routine Review;
- Parental Decision Review;
- Family Context Review;
- Milestone Review;
- Annual Parenting Plan Review.

---

# Transition — Camino a la Paternidad → Child Workspace

The transition must be explicit and traceable.

```text
Camino a la Paternidad
        ↓
Birth / parenthood transition
        ↓
Create child workspace
        ↓
Select relevant transferable context
        ↓
Privacy / memory review
        ↓
Transfer authorized context
        ↓
Continue through the child's parenting workspace
```

The system must not automatically copy the complete journey history into the child's workspace.

Transfer candidates may include:

- identity and civil documentation relevant to the child;
- relevant birth information;
- relevant medical history;
- relevant genetic or family-history information when authorized;
- dates and milestones;
- relevant family context;
- decisions that continue to affect parenting.

The system must preserve provenance for transferred information.

---

# Multiple Children

The domain must support any number of child workspaces without creating new Domain Packs.

```text
Paternidad
├── Camino a la Paternidad
├── <Child workspace 1>
├── <Child workspace 2>
└── <Child workspace N>
```

Each child workspace has:

- independent identity;
- independent timeline;
- independent development state;
- independent health context;
- independent education context;
- independent decisions;
- independent memories and provenance;
- controlled shared-family context.

Shared family information may be referenced across workspaces, but child-specific information must remain isolated unless an explicit cross-child relationship is semantically required.

---

# Cross-Domain Integration

The Paternidad domain may coordinate with:

- `domain:health`;
- `domain:university` or future education-related capabilities when appropriate;
- `domain:life-plan`;
- `domain:general`;
- calendar and scheduling services;
- financial context through scoped resources;
- external information services when current verification is required.

Cross-domain access must follow the restrictive intersection of permissions.

The Paternidad domain must not duplicate another domain's specialized reasoning engine.

---

# Privacy

Initial orientation:

```text
Paternidad -> SENSITIVE
```

Information concerning minors receives restrictive defaults.

The effective policy must consider:

- global privacy policy;
- user policy;
- session policy;
- resource policy;
- child workspace;
- functional area;
- Knowledge Package policy;
- domain policy;
- workflow policy;
- operation policy.

Remote processing of sensitive child information must be denied by default unless explicitly authorized by the effective policy.

---

# Permissions

- high sensitivity;
- restrictive defaults for information concerning minors;
- changing legal, administrative or medical information requires appropriate current verification;
- no autonomous high-impact parental decisions;
- no autonomous external communication concerning a child;
- no autonomous enrolment;
- no autonomous contracting;
- no autonomous payment;
- no autonomous consent;
- no autonomous legal commitment;
- cross-domain access must be scoped and justified;
- health information is imported only when relevant and authorized;
- no persistence of inferred parental decisions;
- no automatic transfer from journey records to child workspaces;
- explicit human approval for external actions.

---

# Profile

```text
ParenthoodProfile
```

The profile may adapt its reasoning according to the active functional scope:

```text
parenthood.journey
parenthood.child:<child_id>
```

This does not create separate reasoning engines or separate Domain Packs.

---

# Completion Criteria

The minimum Paternidad domain is complete when:

- `domain:parenthood` is registered;
- `ParenthoodProfile` is available;
- the public display name is `Paternidad`;
- `Camino a la Paternidad` exists as a functional area;
- child parenting workspaces exist as generic instances;
- child names remain presentation data;
- multiple children are supported;
- child identities remain isolated;
- journey-to-child transfer is explicit and selective;
- privacy rules for minors are enforced;
- parenthood operations use `parenthood.*`;
- no legacy personal project identifier remains in current architecture;
- no legacy route-specific abbreviation is exposed as a public product identifier;
- domain resolution tests pass;
- permission tests pass;
- multi-child isolation tests pass;
- journey-to-child transition tests pass;
- the global suite remains green.

---

# Public Naming

The public naming model is:

```text
Paternidad
├── Camino a la Paternidad
└── <nombre de cada hijo>
```

Architecture:

```text
domain:parenthood
├── parenthood.journey
└── parenthood.child:<child_id>
```

This separation is mandatory.

Public names are human-facing presentation.

Canonical identifiers are stable system contracts.

⸻

10.28 - Sport Domain

Objective

Specify CMM OS to manage training, physical activity, targets, progression, load, recovery and health relation.

Entidades

* exercise;
* workout;
* training_plan;
* metric;
* body_measurement;
* injury;
* recovery;
* sport_goal;
* equipment;
* session;
* performance_record.

Resources

* workout_log;
* health_resource;
* body_measurement;
* training_plan;
* calendar_event;
* user_message;
* note;
* wearable_data;
* memory_entry.

Rules

TrainingLoadRule

It evaluates volume, intensity and frequency.

ProgressiveOverloadRule

It controls reasonable progression.

RecoveryRule

Relates rest, fatigue, pain, and workload.

InjurySignalRule

Detects signs that require stop or check.

HealthConstraintRule

Imports authorized restrictions from the Health Domain.

MeasurementTrendRule

Distinguish trend and punctual variation.

Operaciones

* sport.create_training_plan;
* sport.review_progress;
* sport.adjust_training_load;
* sport.generate_workout;
* sport.track_measurements;
* sport.review_recovery;
* sport.identify_risks;
* sport.schedule_sessions.

Workflows

Training Plan Setup

Weekly Training Review

Recovery Review

Progress Review

Return to Training

Permissions

* Controlled co-ordination with health
* without diagnosis of injuries,
* without high-risk recommendations;
* without automatic modification of treatment;
* calendars under authorisation.

Status: complete — independently audited and closed.

Final Closure Evidence:
* Independent closure: `PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`.
* Acceptance Test: `tests/domains/test_sport_domain_dp028_acceptance.py` (`PASS`, 44 connected checkpoints)
* Closure Adversarial Gate: `tests/domains/test_sport_domain_closure_adversarial.py` (`PASS`, 30 permanent regression checks)

⸻

10.29 - Life Plan Domain

Objective

Specify CMM OS to coordinate vital goals, scenarios, resources, restrictions, decisions and dependencies in the medium and long term.

Entidades

* life_goal;
* milestone;
* scenario;
* dependency;
* constraint;
* risk;
* decision;
* financial_resource;
* career_path;
* education_path;
* housing_goal;
* family_goal;
* timeline.

Resources

* life_plan;
* financial_plan;
* academic_plan;
* opposition_plan;
* health_constraints;
* family_plan;
* housing_plan;
* goal;
* decision;
* calendar_event;
* memory_entry;
* user_message.

Rules

GoalDependencyRule

It relates to goals and prerequisites.

ScenarioConsistencyRule

Checks the internal coherence of each scenario.

ResourceConstraintRule

It evaluates time, money, energy and available capacity.

DecisionStatusRule

Distingue:

* idea;
* preferencia;
* objective
* escenario;
* decision
* compromiso.

LongTermTemporalRule

Checks milestones and sequences.

AlternativeRouteRule

It keeps alternative routes without interpreting them as failure.

CrossDomainImpactRule

Detects impact between:

* health;
* universidad;
* opposition
* economy
* vivienda;
* paternidad;
* proyecto.

PlanDriftRule

It detects deviations between today's plan, decisions and reality.

Operaciones

* life_plan.build_timeline;
* life_plan.compare_scenarios;
* life_plan.review_goals;
* life_plan.detect_dependencies;
* life_plan.identify_risks;
* life_plan.update_plan;
* life_plan.create_milestones;
* life_plan.generate_periodic_review;
* life_plan.evaluate_feasibility;
* life_plan.track_decisions.

Workflows

Life Plan Setup

Quarterly Life Review

Scenario Comparison

Goal Dependency Review

Major Decision Support

Plan Drift Review

Annual Life Plan Update

Permissions

* explicit multidomain access
* decisiones siempre confirmadas;
* inferencias sensitive limitadas;
* without automatic external commitments;
* without payment;
* without automatic abandonment of targets,
* memory writing with increased monitoring.

⸻

10.30 - Project Domain

Objective

Specify CMM OS to analyse, develop, validate and maintain software projects, including CMM OS itself.

Entidades

* repository;
* module;
* package;
* file;
* class;
* method;
* function;
* contract;
* dependency;
* test;
* validation_result;
* issue;
* technical_debt;
* architecture_decision;
* workflow;
* release.

Resources

* source_code;
* project_file;
* documentation;
* test_result;
* validation_result;
* git_history;
* issue;
* roadmap;
* architecture_document;
* commit;
* pull_request;
* memory_entry.

Rules

ArchitectureContractRule

Check that the code respects architectural contracts.

CodeDocumentationConsistencyRule

It detects discrepancies between implementation and documentation.

ValidationRequiredRule

Requires validation before accepting changes.

TechnicalDebtRule

Detects debt, duplication, matching and complexity.

DeadCodeRule

Identifies code missing.

PublicAPIChangeRule

It detects changes affecting public contracts.

BackwardCompatibilityRule

Checks compatibility.

DependencyBoundaryRule

Check interlayer boundaries.

TestCoverageImpactRule

Relates changes and tests.

SemanticTransformationRule

It requires semantic operations as appropriate.

Operaciones

* project.analyse_architecture;
* project.detect_technical_debt;
* project.compare_code_documentation;
* project.detect_dead_code;
* project.detect_duplication;
* project.generate_adr;
* project.create_implementation_plan;
* project.modify_code;
* project.run_validation;
* project.prepare_commit;
* project.review_change;
* project.update_documentation;
* project.generate_release_notes.

Workflows

Architecture Review

Feature Implementation

Bug Resolution

Technical Debt Review

Documentation Synchronisation

Refactor Workflow

Release Preparation

Self-Development Workflow

Self-development flow

Observe Repository
↓
Detect Improvement
↓
Create Goal
↓
Reason with ProjectProfile
↓
Plan Changes
↓
Execute Semantic Operations
↓
Run Validation Pipeline
↓
Evaluate Outcome
↓
Prepare Review
↓
Request Approval
↓
Commit
↓
Update Project Knowledge

Permissions

* reversible modifications with an independent status
* compulsory validation
* committed under politics
* published with approval
* cambios destructivos controlados;
* Prohibition of amending permissions
* rollback obligatorio;
* performance isolation;
* allowed commands;
* Operating limits.

⸻

10.31 - Domain Selection Policies

> **Implementation status:** Complete — independently audited and closed
> **DP-031:** `IMPLEMENTED`
> **AT-DP-031:** `PASS` — 22 connected acceptance checkpoints; independent audit V2 `PASS`
> **Canonical design:** `docs/superpowers/specs/2026-08-27-domain-selection-policies-design.md`
> **Implementation plan:** `docs/superpowers/plans/2026-08-27-domain-selection-policies-implementation-plan.md`
> **Focused Phase 10.31 tests:** 95 passed
> **Domain suite:** 6684 passed
> **Global suite:** 12224 passed
> **Phase 10.31 Python delta:** 14 changed files; Ruff 0 violations; format check PASS; syntax compile PASS
> **Repository-wide Ruff:** 826 pre-existing violations outside the Phase 10.31 Python delta; not part of this milestone
> **Independent audit:** V2 `PASS` — audited HEAD `76dacf3`; BLOCKERS=0; MAJORS=0; MINORS=0; bundle SHA-256 `dfa48d98b154526ce85efe067d7086e3ddde36c9b4c6cf643d097647553d9227`
> **Audit remediation:** V1 findings remediated by `76dacf3`; 11 dedicated audit-regression tests `PASS`

Objective

Define explicit, immutable policies for selecting primary and supporting domains predictably, safely, and audibly while retaining `DefaultDomainResolver` as the single resolution engine.

Domain Selection Policy

```python
DomainSelectionPolicy(
    name="default",
    explicit_domain_priority=True,
    session_domain_priority=True,
    goal_domain_priority=True,
    allow_multi_domain=True,
    maximum_supporting_domains=3,
    minimum_primary_confidence=0.70,
    minimum_supporting_confidence=0.55,
    fallback_domain="domain:general",
    ambiguity_strategy="clarify_or_fallback",
    metadata={},
)
```

Canonical precedence

1. safety, authorization, and availability;
2. explicit domain selection;
3. structured session continuity;
4. structured active-goal domain;
5. ordinary structured evidence;
6. primary selection confidence;
7. supporting-domain confidence and limits;
8. General fallback.

Selection invariants

* Safety, authorization, and availability always precede selection preferences.
* One eligible explicit domain wins over ordinary scoring.
* Multiple eligible explicit domains remain ambiguous regardless of score gap; no arbitrary explicit-domain tie-break is allowed.
* Session continuity and active-goal priority are explicit structured inputs. They are not inferred from `session_id`, `goal_id`, or registry `ACTIVE` state.
* A session/goal disagreement may be resolved by sufficiently clear ordinary evidence; otherwise the result remains ambiguous and requires clarification.
* The default primary confidence floor is `0.70`.
* The default supporting confidence floor is `0.55`.
* Missing declared probabilistic confidence does not invalidate historical structured scoring; declared selection confidence is distinct from aggregate candidate-score confidence.
* Supporting domains are limited by both scoring policy and selection policy.
* `allow_multi_domain=False` disables ordinary supporting-domain selection.
* Required supporting domains that cannot fit the effective policy limit fail closed with `DOMAIN_SELECTION_REQUIRED_DOMAIN_LIMIT_CONFLICT`.
* General fallback cannot widen permissions or bypass an unavailable, denied, or otherwise ineligible General domain.

High-Impact Conservative

High-impact handling is generic and policy-driven. No medical, legal, financial, or other domain slugs are hardcoded into selection logic.

For a domain declared high-impact by the applicable resolution policy, the resolver uses the most restrictive applicable primary-confidence floor across:

* `DomainSelectionPolicy.minimum_primary_confidence`;
* `DomainScoringPolicy.high_impact_minimum_confidence`;
* `DomainResolutionPolicy.minimum_confidence`, when declared.

Reevaluation Policy

Reevaluation is represented by the immutable, side-effect-free `DomainSelectionTransition`.

It records:

* exact previous and new resolution IDs;
* previous and new primary domain;
* previous and new supporting domains;
* primary/supporting change flags;
* declarative reason codes;
* whether recomposition is required;
* whether a session update is required.

Reevaluation does not:

* replay operations;
* mutate a session;
* execute workflows;
* apply persistence;
* perform external side effects.

Those actions remain responsibilities of later orchestration layers.

Phase boundaries

* Phase 10.31 owns selection policy and pure selection transitions.
* Phase 10.32 owns general domain-conflict resolution.
* Phase 10.33 owns domain events.
* Phase 10.34 owns persistent domain sessions.
* The current milestone does not introduce a second resolver or parallel selection engine.

⸻

10.32 - Domain Conflict Resolution

> **Implementation status:** Complete — independently audited and closed
> **DP-032:** `IMPLEMENTED`
> **AT-DP-032:** `PASS` — 32 connected acceptance checkpoints; 125 dedicated audit-regression tests `PASS`; final independent audit V11 `PASS`
> **Canonical design:** `docs/superpowers/specs/2026-08-28-domain-conflict-resolution-policies-design.md`
> **Implementation plan:** `docs/superpowers/plans/2026-08-28-domain-conflict-resolution-implementation-plan.md`
> **Focused Phase 10.32 tests:** 222 passed
> **Domain suite:** 6906 passed
> **Global suite:** 12446 passed
> **Phase 10.32 Python delta:** 22 changed files; Ruff 0 violations; format check PASS; syntax compile PASS
> **Independent audit:** V11 `PASS` — audited HEAD `2fb413d`; BLOCKERS=0; MAJORS=0; MINORS=0; bundle SHA-256 `80f80afbe286c959dd00559e9f11f7dd5b2f6bebb9259d42199c1aa7695904cc`
> **Audit remediation:** V1–V10 findings remediated; 125 dedicated audit-regression tests `PASS`

Objective

To resolve conflicts between domains, rules, operations, permissions or recommendations without concealing discrepancies.

Domain Conflict

DomainConflict(
id="domain-conflict-123",
domains=[
"domain:health",
"domain:sport",
],
kind="recommendation_conflict",
severity="high",
status="open",
affected_items=[],
possible_resolutions=[],
requires_human_review=False,
metadata={},
)

Types

* profile_conflict;
* rule_conflict;
* permission_conflict;
* operation_conflict;
* workflow_conflict;
* recommendation_conflict;
* resource_conflict;
* temporal_conflict;
* memory_conflict;
* presentation_conflict.

Priority of resolution

1. global security
2. permissions
3. Mandatory rules
4. highest risk domain
5. Main domain
6. evidencia;
7. reliability;
8. temporality;
9. human confirmation.

Estrategias

* most_restrictive;
* primary_domain_precedence;
* high_risk_domain_precedence;
* evidence_weighted;
* separate_results;
* ask_user;
* human_review;
* postpone_action;
* maintain_conflict.

Restrictions

No:

* choose the least restrictive choice for comfort;
* hide recomendaciones incompatible;
* proceed while as a blocking conflict exists.
* solve personal decisions automatically
* rule out the result of a domain without traceability.

⸻

10.33 - Domain Events

> **Implementation status:** Complete — independently audited and closed
> **DP-033:** `IMPLEMENTED`
> **AT-DP-033:** `PASS` — 66 connected logical checkpoints (CP-01 through CP-66 in `tests/domains/test_domain_events_dp033_acceptance.py`), 92 parametrized pytest cases
> **Audit remediation:** V1–V8 findings remediated; V9 independent audit `PASS` with BLOCKERS=0, MAJORS=0, MINORS=0; the credential regression matrix is registry-driven with exact 20/20 signature-vector parity; all audit regression suites remain passing.
> **Independent audit:** V9 `PASS` — audited HEAD `6d19556d112606bd145c3f323d8a1ee041d4677e`; BLOCKERS=0; MAJORS=0; MINORS=0; bundle SHA-256 `21a30698da0b121b43739c5ec3de427c70987190ed3c2528ce2648ad8e4de43a`
> **Canonical design:** `docs/superpowers/specs/2026-08-28-domain-events-design.md`
> **Implementation plan:** `docs/superpowers/plans/2026-08-29-phase-10.33-audit-v7-credential-policy-remediation.md`
> **Focused Phase 10.33 tests:** 848 passed
> **Domain suite:** 7840 passed
> **Global suite:** 13380 passed
> **Phase 10.33 Python delta:** 26 files touched/created; Ruff 0 violations; format check PASS; syntax compile PASS

Objective

To integrate domains with the Kernel through stable events.

Eventos generales

domain.resolution.started
domain.resolution.completed
domain.resolution.ambiguous
domain.composition.created
domain.composition.updated
domain.execution.started
domain.execution.completed
domain.execution.failed
domain.conflict.detected
domain.conflict.resolved
domain.permission.requested
domain.permission.denied
domain.approval.requested
domain.approval.received
domain.memory.proposed
domain.memory.updated
domain.workflow.started
domain.workflow.paused
domain.workflow.resumed
domain.workflow.completed
domain.operation.started
domain.operation.completed
domain.operation.failed

Eventos specialized

Domains may declare their own events:

health.symptom.updated
health.medication.changed
university.grade.recorded
university.deadline.approaching
opposition.mock_exam.completed
life_plan.goal.updated
project.validation.failed
project.release.prepared

The specialized events should:

* use Kernel contracts;
* include domain
* include actor;
* including sitting
* include provenance;
* include sensitivity;
* including permissions;
* be versed;
* contain no secrets.

⸻

10.34 - Domain Sessions

> **Status:** Complete — independently audited and closed; final independent audit V10 `PASS`; `DP-034=VERIFIED_EXISTING`; `AT-DP-034=PASS`; BLOCKERS=0; MAJORS=0; MINORS=0
> **Reference document:** `docs/reference/domain-sessions.md`
> **Design specification:** `docs/superpowers/specs/2026-08-30-domain-sessions-design.md`
> **Implementation plan:** `docs/superpowers/plans/2026-08-30-domain-sessions-implementation-plan.md`
> **Focused tests:** 455 passed (`AT-DP-034` — 56/56 portable evidence-bound checkpoints, 41 audit V1 regression tests, 23 audit V3 regression tests, 34 audit V4 regression tests, 32 audit V5 regression tests, 17 audit V6 lifecycle regression tests, 6 audit V8 fixture-isolation regression tests, 6 audit V9 artifact-binding regression tests; 8295 domain tests; 13850 global tests)

Objective

Extend shared Phase 8 Session Context to preserve, revalidate, and restore the specialized state of domain intelligence safely across process restarts and pauses.

Domain Session Context

DomainSessionContext(
session_id="session-123",
primary_domain="domain:health",
supporting_domains=[],
composition_id="domain-composition-123",
active_workflows=[],
available_operations=[],
domain_resources={},
domain_knowledge={},
pending_domain_questions=[],
domain_conflicts=[],
permission_state={},
approval_state={},
last_resolution_id="domain-resolution-123",
next_recommended_step=None,
metadata={},
)

It should store:

* Main domain
* secondary domains;
* composition
* profile effective;
* effective rules;
* effective permissions
* resources by domain
* knowledge by domain
* workflows;
* operations;
* preguntas;
* conflicts;
* approvals;
* partial results
* Domain changes
* traces;
* siguiente paso.

Resumption

On resume:

* to check active domains;
* check versions;
* check compatibility;
* check modified resources;
* re-evaluating permissions
* re-evaluate temporality;
* Reconstruct composition
* detect workflows migrated;
* recover preguntas;
* recover approvals;
* record the resumption.

⸻

10.35 - Domain SDK

> **Status:** Complete — independently audited and closed. Final independent audit V3: `PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`; `DP-035=VERIFIED_EXISTING`; `AT-DP-035=PASS`.
>
> **Audited implementation HEAD:** `6893dc68c64b9780df3da29877a7935cfe5e9cba`
> **Audit V3 bundle SHA-256:** `1d5847215a81d8ae8a29ee42fcf38227a582b0aa0683164d545e3871345f2848`
> **Independent audit:** `docs/audits/phase-10.35-independent-audit-v3.md`

Objective

Allow to create, validate, test and pack new domains without changing CMM OS core.

Implemented CLI

cmm domain create <name>
cmm domain validate <path>
cmm domain test <path>
cmm domain pack <path>

These four commands are the required and delivered Phase 10.35 surface.
Installation, enablement, publication, resolution, trace inspection and the
broader registry/API CLI belong to Phase 10.36 or later. Phase 10.35 does not
claim those commands as implemented.

Scaffold

cmm domain create finance

Resultado:

finance/
├── manifest.json
├── README.md
├── fixtures/
│   └── sample.json
└── tests/
    └── test_domain.py

The older `manifest.yaml` tree elsewhere in this roadmap is conceptual and
historical. The implemented Phase 10.35 SDK uses the canonical declarative
`manifest.json` format and creates external, developer-owned Domain Packs.

Implemented SDK components

* DomainBuilder;
* ManifestBuilder;
* DomainTestHarness;
* DomainFixtureLoader;
* DomainPackager;
* canonical validation facade.

Domain Test Harness

The implemented harness discovers, parses, validates and loads the real target
pack through canonical components into isolated canonical registries. Loading
registers the target but does not enable it, authorize operations or grant
permissions. Pack-owned pytest tests remain the readiness gate used by
`cmm domain test`.

Implemented template

* basic_domain;

⸻

10.36 - Domain API

Status

Complete — independently audited and closed.
`DP-036 = VERIFIED_EXISTING`; `AT-DP-036 = PASS`.

Delivered surface

`cmm.domains.api` exposes the stable public coordination facade:

* `DomainAPI` — runtime-checkable protocol.
* `DefaultDomainAPI` — dependency-injected implementation.

The stable collaborator contract is typed against the canonical protocols
(`DomainDiscovery`, `DomainResolver`, `DomainTraceReferenceValidator`);
concrete defaults (`FileSystemDomainDiscovery`, `DefaultDomainResolver`,
`DefaultDomainTraceReferenceValidator`) are injection examples, not the
public boundary. `get_capabilities` returns `tuple[DomainCapability, ...]`.

Both are exported from `cmm.domains`. Fresh imports are side-effect free.

Approved public methods (canonical owner):

* `list_domains` — `DomainRegistry.list`
* `get_domain` — `DomainRegistry.get`
* `discover_domains` — `DomainDiscovery.discover` (stable protocol boundary; default example: `FileSystemDomainDiscovery`; non-executing, non-registering)
* `validate_domain` — `PipelineDomainValidator.validate` (never installs or enables)
* `install_domain` — `DeclarativeDomainLoader.load` (canonical runtime load + registration only; `install != enable`, `install != authorization`, no durable package store)
* `enable_domain` / `disable_domain` — `DomainRegistry.enable` / `DomainRegistry.disable`
* `resolve_domain` — `DomainResolver.resolve` (stable protocol boundary; default example: `DefaultDomainResolver`; no API-side scoring or selection policy)
* `get_capabilities` — `DomainDefinition.capabilities` via `DomainRegistry.get_required`
* `get_resources` / `get_rules` / `get_operations` / `get_workflows` — `DomainRegistry.list_*`
* `execute_operation` — `DefaultDomainOperationOrchestrator.execute` (permission/approval/transaction/rollback boundaries remain authoritative; no implementation bypass)
* `start_workflow` — `InMemoryDomainWorkflowRegistry.resolve_active` + `DomainWorkflowExecutor.execute_result` (no API-side workflow engine)
* `get_session` — `SharedSessionDomainAdapter.load_domain_session` (shared `SessionStore` remains authoritative)
* `resume_session` — `DomainSessionResumer.resume` (fail-closed current-state revalidation; persisted state is not current authorization)
* `resolve_conflict` — pure `DomainConflictResolver.resolve` (input never mutated)
* `assemble_trace` — `DomainTraceAssembler.assemble` (reference-only)
* `validate_trace` — `DomainTraceReferenceValidator.validate` (stable protocol boundary; default example: `DefaultDomainTraceReferenceValidator`)

Not invented by Phase 10.36

* No session enumeration (`list_all_domain_sessions`, `search_domain_sessions`).
* No trace store, trace repository, trace cache, `get_trace`/`get_trace_by_id`, or `list_traces`.
* No durable package installation, publication, uninstall, or permission-grant APIs.
* No generic `DomainAPIError` hierarchy — canonical subsystem exceptions propagate unchanged.

Canonical shared fix

`DomainMetadata.from_dict` now honors the empty-mapping factory default for the
nested `metadata` field instead of producing `None` (regression:
`tests/domains/test_domain_contracts.py::TestDomainDefinition::test_metadata_from_dict_without_nested_metadata_uses_empty_mapping`).
Declarative Domain Pack manifests with author/license-only metadata previously
crashed typed-metadata consumers during session recomposition.

Reference

* Design: `docs/superpowers/specs/2026-08-31-domain-api-design.md`
* Plan: `docs/superpowers/plans/2026-08-31-domain-api-implementation-plan.md`
* Implementation reference: `docs/reference/domain-api.md`
* Acceptance: `tests/domains/test_domain_api_dp036_acceptance.py` (AT-DP-036)
* Adversarial boundaries: `tests/domains/test_domain_api_adversarial.py`
* Final independent re-audit: `docs/audits/phase-10.36-independent-reaudit-v3.md` — V3 `PASS` (`BLOCKERS=0`, `MAJORS=0`, `MINORS=0`)
* Audited implementation HEAD: `c119abbeaeedf297087ccc5cb01ba311f4cd5c61`
* Audit V3 bundle SHA-256: `add96184a11d98c3625d9bdec786a10460e34a3211b34b972f2d43d62f4221d0`

⸻

10.37 - Observability

Objective

To measure how domains are selected, combined and used.

Logs

The login should record:

* domains found
* loaded domains;
* loading errors;
* resolution
* confianza;
* composition
* conflicts;
* profiles;
* rules
* resources
* operations;
* workflows;
* permissions
* approvals;
* transferencias multi-domain;
* results
* duration
* errors;
* Reported memory.

Initial substances

* domains installed;
* active domains,
* load time;
* load failures;
* decisions by domain
* average confidence of resolution
* resoluciones ambiguas;
* fallback usage;
* ejecuciones multi-domain;
* mean domains by performance
* conflict between domains
* Rejected permissions
* approvals requested;
* operations by domain,
* workflows by domain
* duration per workflow
* Domain rules
* Loaded resources
* transferencias multi-domain;
* Reused knowledge
* questions avoided by sharing context;
* duplicados prevenidos;
* errors by Domain Pack;
* degraded sessions
* Active external domains.

Health Check

Each domain should explain:

DomainHealthResult(
domain_id="domain:health",
status="healthy",
manifest=True,
registry=True,
resources=True,
rules=True,
operations=True,
workflows=True,
permissions=True,
dependencies=True,
last_checked_at="...",
findings=[],
metadata={},
)

Implementation status

Phase 10.37 — Domain Observability is **complete, independently audited and closed**.

```text
DP-037 = VERIFIED_EXISTING
AT-DP-037 = PASS
```

Implemented projection: canonical Domain evidence → read-only privacy-minimized
projection → exact metrics or explicit `UNAVAILABLE` + per-domain read-only
health → ephemeral deterministic report.

* Canonical 25-entry metric catalog: `CANONICAL_DOMAIN_OBSERVABILITY_METRICS`.
* Exact/unavailable semantics: `no evidence != zero != guess`; unavailable is
  never encoded as zero.
* Read-only per-domain health checking (manifest, registry, resources, rules,
  operations, workflows, permissions, dependencies).
* Strict anti-inference: general does not imply fallback; supporting domains do
  not imply transfer; repeated knowledge references do not imply reuse; missing
  questions do not imply avoided; missing duplicates do not imply prevented.
* Reference-first privacy: raw payloads, metadata, user text and secret-shaped
  content are never copied into output.
* No parallel observability infrastructure: no store, repository, event bus,
  runtime, engine, registry, loader or trace; Domain Events remain 23/23;
  DomainAPI remains unchanged.

* Implementation reference: `docs/reference/domain-observability.md`
* Acceptance: `tests/domains/test_domain_observability_dp037_acceptance.py`
  (AT-DP-037)
* Final independent re-audit: `docs/audits/phase-10.37-independent-reaudit-v6.md` — `PASS`.
* Audited implementation HEAD: `a17326421daa2479f58d7ab45b6a66b1bef75936`.
* Audit V6 bundle SHA-256: `401d7fa4eb1b3ee057fed9e1fd2b299804de43e5c383271bd249e4ad1ca3c56c`.
* Closure gates: `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`; `DP-037=VERIFIED_EXISTING`; `AT-DP-037=PASS`.
* The independently audited boundary now extends through Phase 10.37.
* The independently audited Domain Intelligence boundary now extends through **Phase 10.42 — Integration with Planner and Workflow Engine**. Final independent re-audit **V12** = `PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`; `DP-042=VERIFIED_EXISTING`; `AT-DP-042=PASS`; audited implementation HEAD `f3fabd15865fb9ede792e041eede9ba403b8f586`; audit V12 bundle SHA-256 `5584102dfe682cf035d9092cc0fffd5c151e21dc8c46c8f7e835471eee90f9c4`. **Phase 10.43 — Integration with Validation System** is implemented and pending independent audit; the audited boundary remains 10.42 until ChatGPT returns PASS.

⸻

10.38 - Security

Status

**Phase 10.38** — Security — Domain Pack Authority Boundary is **complete, independently audited and closed**. Final independent re-audit **V3** = `PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`.

```text
**DP-038** = VERIFIED_EXISTING
**AT-DP-038** = PASS
```

Implemented boundary

> A Domain Pack may be discovered, validated and explicitly loaded without
> those facts granting authority; activation and runtime capabilities remain
> constrained by an explicit Domain trust policy and the existing canonical
> permission/approval system; and Domain Pack content cannot redefine those
> controls.

* `DomainTrustLevel`: `trusted`, `verified`, `internal`, `community`,
  `untrusted`, `blocked`.
* `DomainTrustPolicy`: immutable explicit declaration with restrictive safe
  defaults and an explicit authorized-source boundary.
* Pure `evaluate_domain_trust`: fail-closed identity/validation/source/
  signature/manual-enable semantics.
* `allow_untrusted=True` remains explicit load/registration permission only;
  it never enables or authorizes.
* Trust is a permission ceiling integrated through the existing
  `DomainPermissionResolver`/`DomainPermissionGate`; the trust layer returns
  only DENY or ABSTAIN and never grants.
* External/non-internal activation requires an explicit trust policy; a trusted
  INTERNAL candidate with no policy preserves Phase 10.36 activation behavior.
* `require_signature`: presence semantics only.
* Pack prompts/configuration are data, never authorization evidence; the
  canonical static `domain.security` scanner remains the only prompt scanner.
* Rejected activation is atomic: no registry mutation, no permission grant, no
  approval created/consumed; exact loader-result coherence proven through
  `DeclarativeDomainLoader.get_loaded`.
* Cross-domain trust ceilings evaluate the actual transferred capability
  (memory write / code execution / sensitive resources / destructive
  operations), not only `DOMAIN_CROSS_ACCESS`.
* Activation requires terminal validation evidence: `PENDING`/`RUNNING`
  validation can never enable a Domain.
* No parallel security infrastructure: no trust store/registry, no security
  engine/runtime/loader/event bus/trace store; canonical owners unchanged;
  Domain Events remain 23/23.
* `signature present != cryptographically verified`; Phase 10.38 provides no
  OS/container sandbox; Phase 11 platform security remains out of scope.

* Implementation reference: `docs/reference/domain-security.md`
* Acceptance: `tests/domains/test_domain_security_dp038_acceptance.py` (AT-DP-038; `PASS`; 34 connected checkpoints; final evidence clean).
* Final independent re-audit: `docs/audits/phase-10.38-independent-reaudit-v3.md` — **V3** `PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`; `CLOSURE_ELIGIBLE=YES`.
* Audited implementation HEAD: `dcf2a058c9ab849642291c44842e1efe53d57906`.
* Audit V3 bundle SHA-256: `dae36ab2b50bd3d09861eb3ea090be8edddc9e905ee720049171a350205300e0`.

Objective

To prevent domain specialization from expanding permissions, fragmenting controls or entering unreliable components.

Mandatory measures

* validation of manifests
* monitoring of integrity
* firmas opcionales;
* list of authorized sources;
* isolation of external domains
* minimum permissions
* atomic load
* installation rollback;
* scan of dependencies;
* list of operations allowed;
* resource limits;
* time limits
* memory limits
* simultaneous domain boundaries
* transfer limits;
* protection against prompt injection;
* data and instructions separation
* validation of outputs
* Prohibition of amending global rules
* Prohibition of amending permissions
* Prohibition of writing memory directly
* traceability;
* text of secrets
* human review for high-risk domains.

Trust Level

DomainTrustLevel:

trusted
verified
internal
community
untrusted
blocked

Domain Trust Policy

DomainTrustPolicy(
domain_id="domain:external",
trust_level="community",
allow_code_execution=False,
allow_external_access=False,
allow_memory_write=False,
allow_sensitive_resources=False,
require_manual_enable=True,
metadata={},
)

External domains

By default:

* they should not have access to sensitive resources.
* cannot write memory
* they are unable to execute operations outside;
* they should not be able to use secrets.
* they cannot be activated automatically.
* they should not be able to modify other domains.
* they cannot register destructive operations.
* They will require review.

Prompt Injection

Domain Packs may contain prompts but:

* Prompts should be configured and have no authority.
* they cannot deactivate rules.
* they cannot change permissions.
* they should not be able to request secrets.
* they cannot redefine contracts;
* have to validate structured responses;
* have to isolate unreliable content.

⸻

10.39 - Preventing fragmentation

**Phase 10.39** — Preventing Fragmentation is **complete, independently audited and closed**. Final independent re-audit **V4** = `PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`.

Objective

Ensure that specialization does not turn CMM OS into an unconnected set of subsytems.

Domains must not be free to:

* To create an own memory
* create an own Knowledge Store
* creating an own Knowledge Graphh
* to create an own Resuscitation Engine
* create an agent Runtime of its own
* To create an own Planner
* To create an own Workflow Engine
* To create an own permit system;
* to create different epistemological contracts;
* to create incompatible identifiers;
* The traceability should be discharged.
* to miss validation
* access tables directly;
* to create duplicated entities;
* to store resources without provenance,
* persist inferences as facts;
* ignore temporality;
* execute operations without OperationResults;
* run sessions outside the Common Session Context.

Domain Architecture Guard

DomainArchitectureGuard(
forbidden_imports=[],
forbidden_dependencies=[],
forbidden_base_classes=[],
required_contracts=[],
required_services=[],
metadata={},
)

Comprobaciones

* forbidden imports;
* acceso directo a persistencia;
* duplication of contracts
* servicios globales recreados;
* events incompatible;
* Unstructured results
* Unmet global rules
* escrituras directas;
* Undeclared permissions
* modelos duplicados.

Those checks should be part of:

* local validation
* CI;
* installation
* update
* publication
* global suite.

### Implementation status

**Canonical guard:** Existing `domain.fragmentation` validation step via
`DomainFragmentationValidator` / `analyze_fragmentation(...)`.
No parallel `DomainArchitectureGuard` service, runtime, store, registry,
resolver, loader, or validation subsystem was introduced.

**DP-039** = VERIFIED_EXISTING
**AT-DP-039** = PASS — `tests/domains/test_domain_architecture_guard_dp039_acceptance.py`
**Implementation evidence:** hardened `cmm/domains/validation_fragmentation.py`
**Final independent re-audit:** `docs/audits/phase-10.39-independent-reaudit-v4.md` — `PASS`
**Audited implementation HEAD:** `93147139e12665e3734328b904277788ac8bd8d6`
**Audit V4 bundle SHA-256:** `b7d39bf5b55ae042f732bf01e7a51685f2158ffce3d6355b62350d51326ce981`
**Closure eligibility:** `YES`

### Architecture

Phase 10.39 hardens the existing canonical fragmentation boundary:

```text
DomainValidationRequest
→ PipelineDomainValidator
→ domain.fragmentation
→ DomainFragmentationValidator
→ analyze_fragmentation(...)
→ DomainValidationResult.fragmentation_valid
→ ensure_domain_validation_allows_install(...)
```

### Protected shared owners

Phase 10.39 protects ownership boundaries of:
- MemoryStore, KnowledgeStore, KnowledgeGraph, Planner, AgentRuntime
- ReasoningEngine, WorkflowEngine, PermissionSystem, SessionStore, SessionContext, OperationResult
- Canonical contracts: KnowledgeItem, Evidence, TemporalScope, Resource, ResourceProvenance, MemoryUpdateProposal, DomainSessionContext, DomainOperationResult
- Recreated canonical global services: DomainRegistry, ResourceRegistry, WorkflowRegistry, EventBus, DomainResolver, DomainLoader, TraceStore

### Detection capabilities

| Finding code | Coverage |
|---|---|
| `DOMAIN_FRAGMENTATION_MEMORY_DUPLICATION` | Private memory infrastructure |
| `DOMAIN_FRAGMENTATION_KNOWLEDGE_STORE_DUPLICATION` | Private Knowledge Store |
| `DOMAIN_FRAGMENTATION_KNOWLEDGE_GRAPH_DUPLICATION` | Private Knowledge Graph |
| `DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION` | Private Planner |
| `DOMAIN_FRAGMENTATION_AGENT_RUNTIME_DUPLICATION` | Private Agent Runtime |
| `DOMAIN_FRAGMENTATION_REASONING_ENGINE_DUPLICATION` | Private Reasoning Engine |
| `DOMAIN_FRAGMENTATION_WORKFLOW_ENGINE_DUPLICATION` | Private Workflow Engine |
| `DOMAIN_FRAGMENTATION_PERMISSION_SYSTEM_DUPLICATION` | Private Permission System |
| `DOMAIN_FRAGMENTATION_SESSION_INFRASTRUCTURE_DUPLICATION` | Private Session Store/Context |
| `DOMAIN_FRAGMENTATION_OPERATION_RESULT_DUPLICATION` | Private OperationResult |
| `DOMAIN_FRAGMENTATION_CONTRACT_REDEFINITION` | Protected canonical contract redefinition |
| `DOMAIN_FRAGMENTATION_REGISTRY_DUPLICATION` | Recreated DomainRegistry/ResourceRegistry/WorkflowRegistry |
| `DOMAIN_FRAGMENTATION_RESOLVER_DUPLICATION` | Recreated DomainResolver |
| `DOMAIN_FRAGMENTATION_LOADER_DUPLICATION` | Recreated DomainLoader |
| `DOMAIN_FRAGMENTATION_EVENT_BUS_DUPLICATION` | Recreated EventBus |
| `DOMAIN_FRAGMENTATION_TRACE_STORE_DUPLICATION` | Recreated TraceStore |
| `DOMAIN_FRAGMENTATION_DIRECT_PERSISTENCE_ACCESS` | Direct backend/persistence imports |
| `DOMAIN_FRAGMENTATION_DIRECT_WRITE` | Direct filesystem writes |
| `DOMAIN_FRAGMENTATION_POLICY_BYPASS` | Explicit validation/policy bypass flags |
| `DOMAIN_FRAGMENTATION_BACKEND_BYPASS` | Direct backend implementation imports |

### Canonical adapter recognition

Legitimate adapters extending canonical imported bases (e.g., `from cmm.planner import TaskPlanner; class MyPlanner(TaskPlanner): ...`) are recognized as canonical reuse and NOT blocked. Adapter exemption is component-aware: a protected component is only exempt when its inherited canonical base is the approved canonical base for that specific component.

⸻

10.40 - Integration with Cognitive Layer

Status

**Phase 10.40** — Integration with Cognitive Layer is **complete, independently audited and closed**.
- **State:** `CLOSED`
- **Final Independent Re-Audit:** **V3** — `PASS` (`docs/audits/phase-10.40-independent-reaudit-v3.md`); `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`.
- **Audited Implementation HEAD:** `35af5c4aa3ac7ef68e43e695cb1269173fdb6084`.
- **Audit V3 Bundle SHA-256:** `171048e000468a8b3ea60be106edd2b9a2e58b64e30a098d088de0bcf4f89d7c`.
- **Design Point:** `DP-040=VERIFIED_EXISTING`.
- **Acceptance:** `AT-DP-040=PASS` (`tests/domains/test_domain_cognitive_dp040_acceptance.py`; connected Domain-to-Cognitive acceptance).
- **Core Production Modules:** `cmm/domains/cognitive_integration.py`, `cmm/domains/cognitive_integration_contracts.py`.
- **Reference Documentation:** `docs/reference/domain-cognitive-integration.md`.
- **Boundary Verification:** 0 cognitive → domain imports, 0 agent runtime imports in 10.40 core, 0 parallel owners, 0 store mutations.
- **Audited Boundary:** The independently audited Domain Intelligence boundary now extends through Phase 10.40.

Objective

Using all phase 8 infrastructure without duplicating cognitive logic.

Domains will contribute to:

* resources
* adaptadores;
* profiles;
* rules
* prioridades;
* permissions
* presentation.

The Cognitive Layer will continue to be responsible for:

* Knowledge Model;
* Knowledge Store;
* Knowledge Graph;
* Reasoning Context;
* Reasoning Engine;
* Information Gap Analysis;
* Interactive Question Engine;
* Contradiction Detection;
* Temporal Reasoning;
* Confidence Evaluation;
* Reasoning Trace;
* Session Context;
* Memory Update Proposal.

Flujo

Domain Resolver
↓
Domain Composition
↓
Resolve Effective Profile
↓
Load Domain Resources
↓
Apply Global Rules
↓
Apply Domain Rules
↓
Reason
↓
Detect Gaps
↓
Ask Questions
↓
Generate Result
↓
Apply Domain Presentation
↓
Generate Domain Trace

Domains should not implement:

* analysis of own gaps
* its own question engine;
* an incompatible own confidence assessment;
* its own cognitive traceability;
* Parallel cognitive sessions.

⸻

10.41 - Integration with Agent Runtime

**Status:** Complete — independently audited and closed. Final independent re-audit **V3**: `PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`; `DP-041=VERIFIED_EXISTING`; `AT-DP-041=PASS`. Audited implementation HEAD `6972e7495bccc0e69ccaa7d007f915ef891e8913`; audit V3 bundle SHA-256 `c9677d836843de8068ba5ed3c0e7d8cd87e12bc4df34e1e2361195f5d8f28458`; independent report `docs/audits/phase-10.41-independent-reaudit-v3.md`. Canonical integrator `cmm/domains/agent_runtime_integration.py`; contracts `cmm/domains/agent_runtime_integration_contracts.py`; reference `docs/reference/domain-agent-runtime-integration.md`; `AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0`. Phase 10.42 is now the next milestone.

Objective

To allow phase 9 agent to use domain specialization throughout its operation cycle.

Ciclo

Goal
↓
Observe
↓
Resolve Domain
↓
Compose Domains
↓
Load Domain Knowledge
↓
Select Effective Profile
↓
Reason
↓
Detect Gaps
↓
Ask / Search / Pause
↓
Select Domain Workflow
↓
Plan Operations
↓
Check Domain Permissions
↓
Execute
↓
Validate
↓
Evaluate Domain Outcome
↓
Update Knowledge
↓
Continue / Replan / Escalate / Complete

The Agent Runtime should have the following power:

* solve domain by target
* Reevaluating domain
* change main domain;
* to add support domains;
* use operations specialized;
* use workflows;
* respect permissions;
* applying for approval
* maintain a master budget;
* evaluating results,
* preserve traceability;
* update memory with proposals.

Action Budget by domain

DomainActionBudget(
domain_id="domain:project",
maximum_operations=20,
maximum_iterations=10,
maximum_questions=3,
maximum_external_calls=5,
maximum_duration_seconds=1800,
maximum_cost=None,
metadata={},
)

Autonomy Policy by Domain

Example:

Health:

Level 1 - Propones actions.

Project:

Level 2 - Run reversible changes.

Life Plan:

Level 1 - Proposes scenarios.

General:

According to global politics.

The domain will never be able to raise the level of autonomy above that globally authorized.

⸻

10.42 - Integration with Planner and Workflow Engine

Objective

To allow plans to use domain capabilities without introducing incompatible nodes.

Nodos conceptuales

Resolve Domain
↓
Compose Domains
↓
Load Domain Resources
↓
Reason with Domain Profile
↓
Execute Domain Operation
↓
Run Domain Workflow
↓
Validate Domain Result
↓
Cross-Domain Handoff
↓
Request Approval
↓
Complete

The Planner should have the power:

* query available operations;
* query workflows;
* check dependencies;
* check permissions;
* calcular impacto multi-domain;
* insert approvals;
* insert validations;
* replanificar;
* reutilizar subworkflows;
* stop on conflicts.

The Planner should not:

* invent operations nonexistent;
* Expand permissions
* to assume that all domains can run;
* duplicate workflows;
* maintain states outside the Workflow Engine.

⸻

**Phase 10.42 status:** Complete — independently audited and closed. Final independent re-audit **V12**: `PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`; `DP-042=VERIFIED_EXISTING`; `AT-DP-042=PASS`; `CLOSURE_ELIGIBLE=YES`. Audited implementation HEAD `f3fabd15865fb9ede792e041eede9ba403b8f586`; audit V12 bundle SHA-256 `5584102dfe682cf035d9092cc0fffd5c151e21dc8c46c8f7e835471eee90f9c4`; independent report `docs/audits/phase-10.42-independent-reaudit-v12.md`. Canonical integrator `cmm/domains/planner_workflow_integration.py`; contracts `cmm/domains/planner_workflow_integration_contracts.py`; reference `docs/reference/domain-planner-workflow-integration.md`. **Phase 10.43 — Integration with Validation System** is implemented and pending independent audit (see 10.43 status below).

⸻

10.43 - Integration with Validation System

Objective

Validate Domain Packs, operations, workflows and specialized results.

Validation Policies initial

DomainPackInstallationPolicy

DomainPackUpdatePolicy

DomainOperationPolicy

DomainWorkflowPolicy

CrossDomainExecutionPolicy

ProjectDomainChangePolicy

Validations

* manifest;
* schema;
* contracts;
* dependencies;
* compatibility;
* Security
* permissions
* fragmentation
* rules
* operations;
* workflows;
* results
* serialization
* migrations;
* tests;
* documentation.

Before activates a domain:

Discover
↓
Validate
↓
Run Domain Tests
↓
Run Compatibility Tests
↓
Run Security Checks
↓
Run Fragmentation Checks
↓
Register
↓
Health Check
↓
Activate

The Project Domain will have to use the Validation System for any code changes.

**Phase 10.43 status:** Implemented and pending independent audit.
`DP-043=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT`; `AT-DP-043=PASS_CONNECTED` (implementation
evidence; independent audit has not yet run). Implementation boundary: six
policy families (`DomainPackInstallationPolicy`, `DomainPackUpdatePolicy`,
`DomainOperationPolicy`, `DomainWorkflowPolicy`,
`CrossDomainExecutionPolicy`, `ProjectDomainChangePolicy`) in
`cmm/domains/validation_policy_bindings.py`; thin integration in
`cmm/domains/validation_integration.py`; canonical Phase 7
`ValidationPolicy`/`ValidationRegistry`/`ValidationPipeline`/
`ValidationResult` reuse via existing `PipelineDomainValidator` and Phase 9
`AgentValidationAdapter`; lifecycle enforcement in
`cmm/domains/loader.py` (install/update policies gate registration);
runtime enforcement via the orchestrator provider seam, the workflow
operation adapter, the orchestrated cross-domain operation port, and the
specialized-result acceptance gate in `cmm/domains/operation_execution.py`
over the generic Phase 9 `validation_requirements` seam;
Phase 10.42 planner/workflow projection unchanged;
connected acceptance
`tests/domains/test_domain_validation_integration_dp043_acceptance.py`
(including V3 provider-omission fail-closed, empty-requirements fail-closed,
provider-independent specialized gate, Project affected-test rejection with
repair and host change derivation without caller hints, and impact escalation via
real runtime operations failing closed with rollback on unmapped steps);
V4 runtime: canonical change scope and impact derived from Phase 7 `ChangeSetBuilder`
and `diff_python_sources` combined monotonically with caller hints refusing downgrade,
post-execution snapshot escalation check with rollback, command result parser
fail-closed hardening (pytest non-zero exit without XML, ruff non-zero exit without diagnostics),
`ProjectDomainChangePolicy` governs `project.modify_code` with canonical Phase 7
escalation, Phase 7 commit gate remains owner;
reference `docs/reference/domain-validation-integration.md`. The
independently audited boundary remains Phase 10.42 until ChatGPT returns
PASS. Next action is independent audit preparation, not Phase 10.44.

⸻

10.44 - Integration with Memory and Knowledge Graph

Objective

To allow specialization without creating knowledge silos.

The Knowledge Graph should relate:

* entities with several domains,
* goals
* events;
* decisiones;
* restricciones;
* resources
* workflows;
* results
* contradicciones;
* dependencies.

Ejemplo

Medication
↓ affects
Symptom
↓ affects
Study Capacity
↓ affects
Opposition Goal
↓ part_of
Life Plan

The system should:

* reutilizar entities;
* retain applicable domains;
* controlar acceso;
* avoid sensitive inferences;
* construir timelines transversales;
* detect contradicciones;
* detect impacto;
* proponer relaciones;
* preserve temporality.

It should not:

* automatically display all information to all domains;
* transferring sensitive resources without permission
* duplicate entities;
* convertir correlaciones en causalidad;
* mezclar periodos incompatible.

⸻

10.45 - Integration with Interfaces

Objective

To allow interfaces to have domains, workflows and results consistently.

UI conversacional

It should show as appropriate:

* Active domain
* secondary domains;
* workflow;
* preguntas;
* approvals;
* sources;
* confianza;
* contradicciones;
* results
* Reported memory.

Domain Selector

It should allow:

* select domain
* using automatic resolution;
* add support domain;
* withdraw domain
* review why it was selected;
* change politics.

Domain Center

It should show:

* domains installed;
* activos;
* deshabilitados;
* degradados;
* versions;
* capabilities;
* permissions
* operations;
* workflows;
* metrics;
* errors;
* actualizaciones available.

Cross-Domain View

It should show:

* Main domain
* secondary domains;
* transferencias;
* dependencies;
* conflicts;
* Consolidated result.

Review Center

It should have:

* operation approvals;
* accesos multi-domain;
* domain installation;
* Upgrading of domains
* persistencia sensible;
* acciones externas;
* conflicts unresolvable.

⸻


10.46 - Domain Model Policies

Objective

Allow every Domain Pack to declare model preferences and restrictions without coupling domain logic to a concrete provider.

Domain Model Policy

```python
DomainModelPolicy(
    domain_id="domain:health",
    default_capability="nuanced_reasoning",
    preferred_models=[],
    preferred_providers=[],
    prohibited_models=[],
    prohibited_providers=[],
    local_models=[],
    premium_fallback=[],
    privacy_default="SENSITIVE",
    minimum_quality="high",
    latency_tolerance="normal",
    context_requirement="long",
    require_structured_output=True,
    require_tool_calling=False,
    require_context_validation=True,
    require_response_validation=True,
    recommended_budget_eur=None,
    fallback_policy=None,
    metadata={},
)
```

A domain may define:

* preferred and prohibited models;
* preferred and prohibited providers;
* default capability;
* minimum quality;
* privacy requirements;
* latency tolerance;
* context-length requirements;
* structured-output requirements;
* tool-calling requirements;
* multimodal requirements;
* local-processing preferences;
* premium fallback;
* recommended budget;
* validation requirements;
* fallback policy.

The policy must be combined with:

* global model policy;
* user policy;
* session policy;
* workflow requirements;
* operation requirements;
* privacy policy;
* economic budget;
* provider availability.

The effective policy must preserve the most restrictive privacy, permission, and cost constraints.

A Domain Pack must not select or invoke a provider directly.

⸻

10.47 - Domain Benchmark Suites

Objective

Provide representative evaluation cases for every domain so models can be compared using real domain requirements rather than only generic benchmarks.

Domain Benchmark Suite

```python
DomainBenchmarkSuite(
    id="benchmark-suite-health",
    domain_id="domain:health",
    version="1",
    cases=[],
    evaluation_policy={},
    privacy_policy={},
    default_budget={},
    created_at="...",
    metadata={},
)
```

Domain Benchmark Case

```python
DomainBenchmarkCase(
    id="health-timeline-001",
    domain_id="domain:health",
    objective="Build a reliable clinical timeline",
    knowledge_package_id=None,
    input_resources=[],
    expected_elements=[],
    required_constraints=[],
    prohibited_behaviors=[],
    quality_criteria=[],
    required_format=None,
    sensitivity="high",
    privacy_policy="SENSITIVE",
    maximum_cost_eur=None,
    candidate_models=[],
    evaluator_ids=[],
    metadata={},
)
```

Initial benchmark areas:

Health:

* clinical timelines;
* fact and symptom separation;
* missing-information detection;
* treatment temporality;
* longitudinal follow-up;
* medical caution.

Relationships:

* fact and interpretation separation;
* ambiguity;
* preservation of uncertainty;
* useful questions;
* emotional continuity;
* tone.

Concerns:

* understanding before intervention;
* support-need calibration;
* emotional validation without fact inflation;
* reality, interpretation, fear and scenario separation;
* evidence-calibrated reassurance;
* preservation of uncertainty;
* proportional risk;
* absence of catastrophic escalation;
* absence of false reassurance;
* recurring concerns without automatic pathologization;
* materially useful questions;
* grounded directness without forced agreement;
* proportional action without pressure;
* cross-domain factual and risk handoff.

University:

* planning;
* priorities;
* dates;
* academic constraints;
* workload;
* progress.

Oppositions:

* official-source priority;
* current regulations;
* syllabus organization;
* call tracking;
* requirement comparison;
* continuity of prior decisions.

Mental Health:

* ordinary emotional conversation without default medicalization;
* fact, interpretation, fear, intuition, and uncertainty separation;
* therapy continuity and session preparation;
* longitudinal emotional context;
* proportionate safety escalation;
* cross-domain minimization and privacy preservation.

Neurodivergence:

* certainty-state preservation;
* developmental and longitudinal evidence;
* differential and overlap analysis;
* executive, sensory, academic, social, and functional context;
* screening/self-report non-promotion;
* purpose-minimized Health and Mental Health coordination.

Project:

* code generation;
* architectural consistency;
* tool calling;
* structured output;
* validation;
* error correction.

Each case must support:

* expected output elements;
* prohibited conclusions;
* quality criteria;
* required schema;
* maximum cost;
* sensitivity;
* privacy;
* candidate models;
* automatic evaluators;
* human evaluation.

Benchmark suites must be versioned, reproducible, exportable, and compatible with the Phase 11 Model Evaluation Framework.

⸻

10.48 - Domain Quality Metrics

Objective

Allow each domain to evaluate model outputs according to its own priorities.

Domain Quality Metric

```python
DomainQualityMetric(
    id="health-prudence",
    domain_id="domain:health",
    name="prudence",
    weight=0.20,
    evaluator="...",
    minimum_score=0.85,
    blocking=True,
    metadata={},
)
```

Initial metrics may include:

* factual fidelity;
* contextual fidelity;
* sensitivity;
* depth;
* usefulness;
* structure;
* prudence;
* temporal correctness;
* clarity;
* precision;
* instruction compliance;
* absence of contradictions;
* relevant questions;
* plan quality;
* tool-calling quality;
* privacy compliance;
* cost efficiency;
* user satisfaction.

Different domains may assign different weights.

Examples:

* Health prioritizes factual fidelity, prudence, temporality, and safety.
* Relationships prioritizes ambiguity handling, contextual continuity, and non-attribution of intent.
* Concerns prioritizes contextual understanding, support-need calibration, epistemic separation, evidence-calibrated reassurance, proportional risk, useful questioning, non-pathologizing recurrence, and user agency.
* University prioritizes dates, constraints, feasibility, and plan quality.
* Project prioritizes correctness, architecture, validation, and tool calling.

* Mental Health prioritizes emotional fidelity, epistemic separation, contextual continuity, non-pathologizing support, safety proportionality, and privacy.
* Neurodivergence prioritizes certainty preservation, developmental/longitudinal evidence, differential reasoning, non-promotion of hypotheses, functional relevance, and privacy.

A high aggregate score must not compensate for a failed blocking metric.

Results must preserve:

* metric values;
* weights;
* evaluator versions;
* blocking failures;
* aggregate score;
* confidence;
* human-review results.

⸻

10.49 - Domain Knowledge Packages

Objective

Specialize the Phase 8 `KnowledgePackage` contract for each domain without creating incompatible context models.

Domain Knowledge Package Schema

```python
DomainKnowledgePackageSchema(
    id="knowledge-package-schema-health",
    domain_id="domain:health",
    version="1",
    base_schema="KnowledgePackage",
    required_sections=[],
    optional_sections=[],
    prohibited_sections=[],
    field_policies={},
    privacy_policy="SENSITIVE",
    validators=[],
    metadata={},
)
```

Initial specializations:

```text
Health Knowledge Package
Relationship Knowledge Package
University Knowledge Package
Opposition Knowledge Package
Reflection Knowledge Package
Concerns Knowledge Package
Life Plan Knowledge Package
Project Knowledge Package
Mental Health Knowledge Package
Neurodivergence Knowledge Package
```

Every specialization must retain the common fields for:

* objective;
* provenance;
* epistemological type;
* temporal validity;
* contradictions;
* uncertainty;
* missing information;
* privacy;
* permissions;
* profile;
* resources;
* version.

Domains may add fields but must not:

* redefine the base contract;
* remove provenance;
* flatten facts and hypotheses;
* hide contradictions;
* weaken privacy;
* create provider-specific package formats;
* duplicate stored knowledge.

A package may be composed across domains through explicit schemas and permission intersection.

⸻

10.50 - Domain Privacy Policies

Objective

Define default privacy behavior for each Domain Pack while preserving resource-level, workflow-level, and operation-level overrides.

Domain Privacy Policy

```python
DomainPrivacyPolicy(
    domain_id="domain:health",
    default_policy="SENSITIVE",
    allowed_processing_locations=["local"],
    allowed_providers=[],
    prohibited_providers=[],
    allow_remote=False,
    allow_premium=False,
    allow_cross_domain=False,
    allow_cache=True,
    allow_export=False,
    require_redaction=False,
    require_approval_for_remote=True,
    metadata={},
)
```

Initial orientation:

```text
Health             -> SENSITIVE
Relationships      -> SENSITIVE
Reflection         -> SENSITIVE
Concerns           -> SENSITIVE
Paternidad / Parenthood   -> SENSITIVE
Mental Health      -> SENSITIVE
Neurodivergence    -> SENSITIVE
University         -> REMOTE_ALLOWED
Oppositions        -> REMOTE_ALLOWED
Languages          -> REMOTE_ALLOWED
Project            -> LOCAL_PREFERRED
General            -> resolved per operation
```

The final effective policy must combine:

* global privacy policy;
* user policy;
* session policy;
* resource policy;
* Knowledge Package policy;
* domain policy;
* workflow policy;
* operation policy;
* model-provider policy.

The most restrictive applicable policy must prevail unless an authorized exception exists.

Domains must not:

* grant themselves remote access;
* weaken `LOCAL_ONLY`;
* export restricted packages;
* send sensitive data to prohibited providers;
* preserve sensitive outputs in unauthorized caches;
* transfer information to supporting domains without permission;
* omit privacy decisions from the Domain Trace.

⸻

10.51 - Implementation Order


Block 1 - Domain Contracts

* DomainStatus;
* DomainKind;
* DomainDefinition;
* DomainMetadata;
* DomainCapability;
* DomainDependency;
* DomainConflict;
* DomainResult;
* identifiers;
* serialization
* errors;
* unit tests.

Block 2 - Domain Manifest

* schema;
* parser;
* validation
* versioning;
* compatibility;
* checksums;
* fixtures;
* unit tests.

Block 3 - Domain Registry

* registry;
* query;
* enablement
* disablement
* capabilities;
* dependencies;
* conflicts;
* events;
* unit tests.

Block 4 - Discovery and Loader

* sources;
* candidates;
* discovery;
* loading;
* unload;
* reload;
* atomic load
* rollback;
* health checks;
* integration tests.

Block 5 - Domain Validation

* contracts;
* dependencies;
* compatibility;
* permissions
* Security
* fragmentation
* tests;
* integration with phase 7.

Block 6 - Domain Resolution

* DomainResolutionContext;
* DomainResolutionResult;
* policies
* explicit resolution
* a decision by means of appeals;
* an intent decision;
* fallback;
* ambiguity
* unit tests.

Block 7 - Domain Composition

* Main domain
* secondary domains;
* profiles effective;
* effective rules;
* effective permissions
* resources
* operations;
* conflicts;
* unit tests.

Block 8 - Cross-Domain Engine

* contrato;
* transferencia;
* dependencies;
* conflicts;
* consolidation
* limits;
* traces;
* integration tests.

Block 9 - Domain Resources

* definiciones;
* registry;
* adaptadores;
* sensibilidad;
* permissions
* temporality;
* shared resources
* tests.

Block 10 - Domain Profiles

* contracts;
* registry;
* composition
* GeneralProfile;
* profiles initial;
* resolution
* unit tests.

Block 11 - Domain Rules

* contrato;
* registry;
* Domain rules
* prioridades;
* composition
* traceability;
* unit tests.

Block 12 - Domain Operations

* contrato;
* registry;
* schemas;
* permissions
* approval
* implementation
* rollback;
* validation
* integration tests.

Block 13 - Domain Workflows

* contrato;
* registry;
* nodos;
* subworkflows;
* pausa;
* Resumption
* migration
* integration tests.

Block 14 - Domain Permissions

* policies
* intersection
* acceso multi-domain;
* approvals;
* autonomy
* Security tests.

Block 15 - Domain Presentation

* policies
* components;
* salida humana;
* salida JSON;
* Multidomain results
* tests.

Block 16 - Domain Trace

* resolution
* composition
* operations;
* workflows;
* transferencias;
* permissions
* persistencia;
* tests.

Block 17 - Memory Integration

* vistas;
* propuestas;
* relaciones multi-domain;
* duplication
* confirmation
* tests.

Block 18 - General Domain

* resources
* profile;
* rules
* operations;
* workflows;
* presentation;
* E2E tests.

Block 19 - Health Domain

* resources
* entities;
* rules
* operations;
* workflows;
* permissions
* presentation;
* E2E tests.

Block 20 - University Domain

* resources
* entities;
* rules
* operations;
* workflows;
* permissions
* presentation;
* E2E tests.

Block 21 - Project Domain

* resources
* entities;
* rules
* operations;
* workflows;
* validation
* autodesarrollo;
* E2E tests.

Block 22 - Life Plan Domain

* resources
* entities;
* rules
* operations;
* workflows;
* Multidomain co-ordination
* E2E tests.

Block 23 - Relationships Domain

* resources
* entities;
* rules
* operations;
* workflows;
* permissions
* E2E tests.

Block 24 - Secondary Domains

* Opposition;
* Reflection;
* Concerns;
* Languages;
* Paternidad;
* Sport;
* minimum functional versions
* tests.

Block 25 - Domain SDK

* scaffold;
* builders;
* test harness;
* fixtures;
* packager;
* CLI;
* plantillas;
* documentation.

Block 26 - API and CLI

* resolution
* registry;
* installation
* enablement
* operations;
* workflows;
* traces;
* conflicts;
* salida JSON;
* tests.

Block 27 - Security and observability

* trust levels;
* aislamiento;
* prompt injection;
* metrics;
* logs;
* health checks;
* audit
* tests.

Block 28 - Final integration

* Kernel;
* Cognitive Layer;
* Agent Runtime;
* Planner;
* Workflow Engine;
* Execution Engine;
* Validation System;
* Memory;
* Knowledge Graph;
* UI;
* cross-domain tests;
* E2E tests;
* documentation;
* global suite.

⸻

Capacidades esperadas

* defining domains through common contracts
* To pack domains;
* descubrir Domain Packs;
* validate Domain Packs;
* Loan domains
* downloading domains;
* Reloading domains
* enable and disable;
* versionar;
* check compatibility;
* resolve dependencies;
* detect conflicts;
* register capabilities;
* automatically solve the domain;
* respect explicit domains;
* To detect ambiguity
* use fallback;
* select main domain
* select secondary domains;
* compose profiles;
* compose rules;
* composing resources
* composing permissions
* compose operations;
* execute multi-domain reasoning;
* transferir contexto;
* avoid duplication.
* have a single memory;
* reutilizar entities;
* using shared resources
* to register domain rules;
* register operations;
* register workflows;
* execute specialized workflows;
* request approvals;
* respect levels of autonomy
* run sessions;
* pausar;
* reanudar;
* change of domain
* preserve traceability;
* production of structured results
* to have specialized results,
* generate multi-domain views;
* propose memory
* controlar inferencias sensitive;
* integrate external sources;
* use local and remote models;
* preserve provider independence;
* creating domains using SDK
* Test domains independently.
* install external domains;
* Isolation of unreliable domains
* Validation of fragmentation
* integrating with CLI
* integrate with API
* integrate with UI
* integrating with agents
* integrate with the Planner;
* integrating with Performance Engine
* integrate with Validation System
* integrating with Memory
* integrating with Knowledge Graph
* enabling autodevelopment through Project Domain.

⸻

Security

* Mandatory validation of Domain Packes
* manifiestos estructurados;
* monitoring of integrity
* compatibility versioned;
* atomic load
* rollback;
* minimum permissions
* restrictive intersection of permissions
* isolation of external domains
* trust levels;
* manual review of unreliable domains
* monitoring of resources
* knowledge monitoring
* control of operations;
* control of workflows;
* control multi-domain;
* inferencias sensitive restringidas;
* External models under authorisation
* outside searches under authorisation
* controlled memory writing
* decisiones personales confirmadas;
* destructive operations with approval;
* external communications with approval;
* modified controlled archives
* validation of results
* protection against prompt injection;
* separation of data and instructions
* without authority over permissions,
* Prohibition of secrets in packages
* Unauthorized login
* cifrado;
* resource limits;
* domain boundaries;
* transfer limits;
* Operating limits
* workflow limits
* time limits
* cost limits
* secure cancellation
* absence of custom planners;
* absence of custom memories;
* absence of custom runtimes;
* absence of custom backends;
* complete traceability;
* human review for high impact domains.

⸻

Pruebas

Unitarias

* DomainStatus;
* DomainKind;
* DomainDefinition;
* DomainMetadata;
* DomainCapability;
* DomainDependency;
* DomainConflict;
* DomainResult;
* manifest;
* parser;
* versioning;
* compatibility;
* registry;
* discovery;
* loader;
* unload;
* reload;
* validation;
* resolution context;
* resolve;
* policies
* composition;
* profiles;
* rules
* resources
* permissions
* operations;
* workflows;
* presentation;
* trace;
* memory views;
* trust levels;
* health checks.

Integration

* discovery a registry;
* Loading validation
* atomic load
* rollback;
* resolution to profile
* resolution to resources
* resolution to rules
* Multidomain composition
* effective permissions
* knowledge transfer
* operations;
* workflows;
* approvals;
* traces;
* sessions
* memory;
* Knowledge Graph;
* Cognitive Layer;
* Agent Runtime;
* Planner;
* Execution Engine;
* Validation System;
* Kernel;
* CLI;
* API;
* SDK.

E2E

Minimum scenarios:

1. discovery of an internal domain;
2. correct registration;
3. Invalid manifest
4. incompatible version
5. dependencia ausente;
6. conflict between domains
7. successful loading;
8. malfunction while loading
9. load rollback;
10. enablement
11. disablement
12. reload;
13. health check;
14. explicit resolution
15. an appeal decision
16. an intent decision;
17. resolution by objective;
18. resolution by session
19. ambiguous domain
20. fallback general;
21. domain disabled
22. main domain with a support;
23. 3 composite domains
24. an excess of blocked domains
25. Section 3
26. Section 3
27. composition of permissions
28. conflict of permissions
29. transferencia multi-domain permitida;
30. transferencia multi-domain denegada;
31. shared resource
32. entidad compartida;
33. duplicado evitado;
34. global rule and rule of domain
35. health rule;
36. regla universitaria;
37. relationships rule;
38. project rule;
39. reading operation
40. an analysis operation;
41. reversible operation;
42. sensitive operation
43. required approval;
44. Rejected approval
45. operation rollback;
46. health workflow;
47. workflow universitario;
48. relationships workflow;
49. project workflow;
50. life-plan workflow;
51. pausa esperando respuesta;
52. Resumption
53. change of domain during session
54. conflict between recommendations
55. Multidomain result
56. complete trace;
57. memory proposal
58. propuesta duplicada evitada;
59. inferencia sensible bloqueada;
60. Unreliable external domain
61. manual installation
62. Closed outside operation
63. prompt injection en Domain Pack;
64. Redefinition of a blocked contract
65. acceso directo a persistencia detectado;
66. custom planner detected;
67. own memory detected;
68. custom Agent Runtime detected;
69. IQ validation
70. scaffold mediante SDK;
71. test harness;
72. empaquetado;
73. salida CLI;
74. salida API;
75. UI Domain Center;
76. Cross-Domain View;
77. Health Domain E2E;
78. University Domain E2E;
79. Project Domain E2E;
80. Life Plan Domain E2E;
81. Relationships Domain E2E;
82. minimal Opposition Domain
83. Minimum reflection Domain
84. Minimum Domain concerns
85. Minimum Domain languages
86. Paternidad Domain minimum
87. Minimum Sport Domain
88. agent with a domain,
89. agente multi-domain;
90. Project Domain self-development.

⸻

Documentation

The phase should include:

* domain architecture
* Principles of specialization
* prevention of fragmentation
* Domain Contracts;
* Domain Pack;
* manifest;
* package structure;
* Domain Registry;
* discovery;
* loader;
* atomic load
* rollback;
* validation
* compatibility;
* versioning;
* dependencies;
* conflicts;
* Domain Resolver;
* selection policies;
* Domain Composition;
* Cross-Domain Engine;
* transferencias;
* profiles;
* rules
* resources
* operations;
* workflows;
* permissions
* approvals;
* presentation;
* traceability;
* sessions
* memory;
* Knowledge Graph;
* Security
* trust levels;
* external domains;
* protection against prompt injection;
* observability;
* logs;
* metrics;
* health checks;
* CLI;
* API;
* SDK;
* creation of domains
* domain tests;
* publication of domains
* General Domain;
* Health Domain;
* Relationships Domain;
* University Domain;
* Opposition Domain;
* Reflection Domain;
* Concerns Domain;
* Languages Domain;
* Paternidad Domain;
* Sport Domain;
* Life Plan Domain;
* Project Domain;

* Mental Health Domain;

* Neurodivergence Domain;
* integration with Cognitive Layer;
* integration with Agent Runtime;
* integration with Planner;
* integration with Workflow Engine;
* integration with Execution Engine;
* integration with Validation System;
* integration with Memory;
* integration with Knowledge Graph;
* integration with Kernel;
* integration with UI;
* examples multi-domain;
* bug resolution;
* migration guide
* compatibility guide
* Security guide
* guide to developing Domain Packs from third parties.

⸻

Closure criteria

* Domain contracts implemented
* DomainDefinition;
* DomainMetadata;
* DomainCapability;
* DomainDependency;
* DomainConflict;
* DomainResult;
* manifest schema;
* manifest parser;
* Domain Pack;
* Standard structure
* versioning;
* compatibility;
* checksums;
* Domain Registry;
* domain registration
* query;
* enablement
* disablement
* Domain Discovery;
* Domain Loader;
* atomic load
* rollback;
* reload;
* unload;
* health checks;
* validation of domains
* integration with Validation System;
* prevention of fragmentation
* DomainResolutionContext;
* DomainResolver;
* Resolution policies
* fallback general;
* detection of ambiguity
* Main domain selection
* secondary domains;
* DomainComposition;
* Section 3
* Section 3
* composition of resources
* operations composition
* composition of permissions
* Cross-Domain Engine;
* transferencias multi-domain;
* conflicts multi-domain;
* limits;
* Domain Resources;
* shared resources
* Domain Profiles;
* profiles specialized;
* Domain Rules;
* registration of rules
* Domain Operations;
* Operational permissions;
* approvals;
* rollback;
* Domain Workflows;
* pausa;
* Resumption
* subworkflows;
* Domain Permissions;
* restrictive intersection
* accesos multi-domain;
* Domain Presentation;
* specialized results;
* Domain Trace;
* traceability of resolution
* transfer traceability;
* Domain Sessions;
* integration with memory
* prevention of duplication
* General Domain funcional;
* Health Domain funcional;
* University Domain funcional;
* Project Domain funcional;
* Life Plan Domain funcional;
* Relationships Domain funcional;
* Minimum Domain opposition
* Minimum reflection Domain
* Minimum Domain concerns
* Minimum Domain languages
* Paternidad Domain minimum
* Minimum Sport Domain

* Minimum Mental Health Domain

* Minimum Neurodivergence Domain
* Domain SDK;
* scaffold;
* test harness;
* packager;
* CLI;
* API;
* domain installation;
* external domains;
* trust levels;
* protection against prompt injection;
* logs;
* metrics;
* observability;
* integration with Cognitive Layer;
* integration with Agent Runtime;
* integration with Planner;
* integration with Workflow Engine;
* integration with Execution Engine;
* integration with Validation System;
* integration with Memory;
* integration with Knowledge Graph;
* integration with Kernel;
* integration with UI;
* domain model policies;
* domain benchmark suites;
* domain-specific quality metrics;
* specialized Knowledge Package schemas;
* domain privacy policies;
* compatibility with the future Model Gateway;
* compatibility with the Model Evaluation Framework;
* unit tests;
* integration tests;
* cross-domain tests;
* E2E tests;
* documentation;
* green global suite.

⸻

Outcome of phase

CMM OS will have a shared specialization layer capable of adapting its reasoning, resources, operations, workflows, permissions, and presentation to the specific scope of each goal.

Each execution may prove:

* what domain was selected;
* why it was selected;
* what confidence level the resolution had;
* which domain acted as primary;
* which domains acted as supporting domains;
* which effective profile was used;
* which global rules were applied;
* which specialized rules were applied;
* which resources were provided by each domain;
* what knowledge was shared;
* what knowledge was isolated;
* which permissions were activated;
* which operations were available;
* which operations were executed;
* what workflows were used;
* what approvals were necessary;
* which conflicts appeared;
* how they were managed;
* what result each domain produced;
* what consolidated conclusion was reached;
* what uncertainty remains;
* which memory update was proposed;
* which model policy was applied;
* which privacy policy was effective;
* which Knowledge Package schema was used;
* which domain quality metrics were evaluated;
* which benchmark evidence supported model selection.

Phase 10 will turn CMM OS's general intelligence into contextual and specialized intelligence prepared for provider-independent multimodel execution.

CMM OS may use the same infrastructure to:

* analyze a medical history;
* understand the evolution of a relationship;
* plan a semester;
* review an opposition exam;
* perform structured reflection;
* discuss a concern;
* design a language plan;
* maintain a personal project;
* review training;
* coordinate a life plan;

* sustain emotional and therapy continuity without turning ordinary emotional conversation into clinical output;

* organize longitudinal neurodivergence evidence without promoting hypotheses, screening results, or model inference to diagnosis;

* sustain emotional and therapy continuity without turning ordinary conversation into clinical assessment;

* organize longitudinal neurodivergence evidence without promoting hypotheses, screening results, or model inferences to diagnosis;
* develop and maintain its own code.

All of this without creating isolated assistants, duplicated memories, or incompatible architecture.

The Cognitive Layer will continue to determine how knowledge is represented and built.

The Agent Runtime will continue to determine how targets and actions are pursued.

Domain Intelligence will determine what specialization should be applied in each context.

From this infrastructure, Phase 11 can integrate UI, goals, workflows, agents, memory, knowledge, permissions, and domains into a complete, extensible, and coherent personal platform.

⸻

10.52 - Mental Health Domain

Objective

Provide a dedicated Domain Pack for emotional wellbeing, personal emotional conversation, therapy continuity, therapy-session analysis, and longitudinal emotional context without turning ordinary conversation into default clinical assessment.

The domain must preserve warmth, humanity, uncertainty, and conversational freedom while remaining compatible with the shared CMM OS epistemic, privacy, permission, memory, validation, and trace contracts.

Canonical identity

```text
domain:mental-health
MentalHealthProfile
DP-052
AT-DP-052
privacy = SENSITIVE
```

Mental Health is a sibling of Health and Neurodivergence.

It is not a child namespace of `domain:health` and does not inherit clinical authority merely because emotional or psychiatric context is present.

Scope

The Mental Health Domain owns specialization for:

* emotional wellbeing;
* ordinary personal emotional conversation and support;
* therapy continuity;
* preparation before therapy sessions;
* processing after therapy sessions;
* analysis of therapy-session transcripts and notes;
* longitudinal emotional context;
* emotionally relevant decisions;
* lived meaning of relationships, life events, goals, setbacks, and transitions;
* distinction between facts, interpretations, fears, intuitions, hypotheses, and uncertainty when relevant;
* detection of rumination, loops, or repeated analysis without automatically pathologizing repetition;
* proportionate safety escalation when an actual immediate-risk condition is resolved upstream or by domain rules.

The domain must be able to operate in at least four semantically distinct interaction states:

```text
ordinary emotional conversation
therapeutic reflection
clinical psychiatric information
actual immediate safety risk
```

These states may alter reasoning and presentation requirements but do not create separate Domain Packs or runtimes.

Non-goals

Mental Health must not:

* medicalize ordinary distress, uncertainty, sadness, frustration, loneliness, conflict, or reflection by default;
* diagnose from conversation;
* infer a stable disorder solely from emotional language;
* alter treatment or medication doses;
* override Health on documented diagnosis, treatment, medication, or medical safety;
* act as a substitute for a qualified clinician where professional assessment is materially required;
* persist sensitive emotional inferences silently;
* export sensitive emotional context silently;
* transfer sensitive emotional context to another domain without purpose and permission;
* contact clinicians, relatives, institutions, or other third parties autonomously;
* create an independent Mental Health planner, runtime, memory store, Knowledge Graph, Cognitive Layer, or temporal engine.

Knowledge and epistemic requirements

Mental Health reuses Phase 8 knowledge contracts and must preserve:

* provenance;
* epistemic kind;
* temporal validity;
* confidence;
* uncertainty;
* contradiction identity;
* correction and supersession history;
* source authority by attribute and purpose;
* sensitivity;
* permission state.

Where useful, domain reasoning must distinguish at least:

```text
FACT
OBSERVATION
INTERPRETATION
HYPOTHESIS
FEAR
INTUITION
PREFERENCE
DECISION
UNCERTAINTY
```

The exact storage representation remains the shared Phase 8 knowledge model; the Domain Pack must not create a competing claim taxonomy or persistence system.

Conversation-derived interpretation must remain revisable and must not be promoted to fact merely because it is repeated, emotionally salient, or consistent with a prior model response.

Resources

Representative resources may include:

* authorized conversation history;
* therapy-session transcripts;
* therapy notes;
* user-authored reflections;
* prior decisions and goals;
* authorized relationship context;
* authorized life-plan context;
* purpose-minimized Health context;
* purpose-minimized Neurodivergence context;
* current safety information when relevant;
* files or external sources explicitly authorized for the active task.

Resource access is scoped. A resource available to Health or Relationships is not automatically available to Mental Health.

Reasoning profile

```text
MentalHealthProfile
```

The profile should support a human, warm, natural conversational mode while preserving epistemic discipline.

It may resolve modes such as:

```text
conversational
supportive
reflective
therapy-preparation
therapy-review
structured-longitudinal-analysis
safety-focused
```

Presentation style must remain separate from reasoning truth conditions, permissions, and safety decisions.

Rules

The minimum rule set must cover:

* emotional-context relevance;
* fact/interpretation/fear/intuition separation when materially useful;
* non-pathologizing default;
* proportionate questioning based on material information gaps;
* continuity with authorized prior emotional context;
* therapy-transcript source/provenance preservation;
* separation between therapist statements, user statements, and model interpretation;
* uncertainty preservation;
* repeated-loop detection without automatic disorder attribution;
* Health authority for clinical diagnosis/treatment/medication;
* purpose-minimized cross-domain imports;
* sensitive-inference persistence controls;
* immediate-risk escalation without converting ordinary distress into emergency framing.

Operations

Representative operations may include:

```text
mental_health.review_emotional_context
mental_health.prepare_therapy_session
mental_health.review_therapy_session
mental_health.analyze_therapy_transcript
mental_health.compare_emotional_periods
mental_health.map_fact_interpretation_uncertainty
mental_health.review_emotional_decision
mental_health.propose_memory_update
```

Operations that persist, export, communicate, or mutate external systems require the applicable Phase 10 permission and approval contracts.

Workflows

Minimum workflows should include:

```text
Emotional Context Review
Therapy Session Preparation
Therapy Session Post-Processing
Therapy Transcript Review
Longitudinal Emotional Review
Emotionally Relevant Decision Review
Sensitive Memory Proposal Review
Safety Escalation Review
```

A workflow may pause for missing information or approval and must reuse the shared Agent Runtime and Workflow Engine.

Permissions and approvals

Default sensitivity:

```text
SENSITIVE
```

The effective permission policy must separate:

* read;
* infer;
* propose persistence;
* persist;
* transfer;
* export;
* communicate;
* external mutation.

Permission to discuss an inference does not imply permission to persist it.

Permission to read therapy material does not imply permission to transfer it to Relationships, Health, Neurodivergence, or an external provider.

No autonomous external communication is allowed for sensitive Mental Health content.

Cross-domain coordination

Mental Health may act as primary with supporting domains such as:

```text
domain:relationships
domain:neurodivergence
domain:health
domain:reflection
domain:concerns
domain:life-plan
domain:general
```

Examples:

```text
"Prepare tomorrow's psychologist session"
primary = domain:mental-health
supporting = relationships / neurodivergence / health when materially relevant
```

```text
"A psychiatrist changed my medication and I feel different emotionally"
primary = domain:health
supporting = mental-health / neurodivergence when materially relevant
```

Any transfer must preserve:

* source-domain authority;
* provenance;
* epistemic kind;
* temporal validity;
* uncertainty;
* sensitivity;
* purpose limitation;
* restrictive permission intersection.

Supporting domains receive only the minimum authorized projection needed for the active purpose.

Memory

Mental Health uses the shared Domain Memory Integration contracts.

It must not create a private parallel memory store.

Sensitive emotional interpretations are proposal-first and require the applicable confirmation before persistence.

Existing Health knowledge must not be silently moved, duplicated, or reclassified into Mental Health.

Any future reclassification must be explicit, provenance-preserving, auditable, and supervised.

Presentation

Mental Health presentation should be capable of being:

* conversational and human;
* emotionally attentive;
* direct when useful;
* structured when the task requires structure;
* non-clinical by default for ordinary emotional conversation;
* explicit about uncertainty when interpretation matters;
* calm and proportionate around safety.

Presentation must not fabricate therapeutic certainty, diagnostic authority, or crisis framing.

Traceability

Domain Trace must identify:

* Mental Health as primary or supporting domain;
* selected profile;
* rule/operation/workflow references;
* cross-domain projections;
* permission and approval decisions;
* memory proposals;
* safety escalations;
* Knowledge Package and cognitive trace references.

It must not copy private prompt content, chain of thought, sensitive transcript bodies, or subordinate traces.

Privacy

Initial orientation:

```text
Mental Health -> SENSITIVE
```

Remote processing is governed by the effective privacy intersection and must not be inferred from general provider availability.

Sensitive therapy or emotional material must not enter unauthorized caches, exports, providers, or supporting-domain contexts.

Knowledge Package

The Mental Health Knowledge Package specializes the shared Phase 8 `KnowledgePackage` and may require domain-relevant sections for:

* active emotional objective;
* source-separated conversation/therapy evidence;
* facts and observations;
* interpretations and hypotheses;
* uncertainty and contradictions;
* relevant longitudinal context;
* authorized supporting-domain projections;
* permissions and privacy.

It must retain the common base contract and must not duplicate stored knowledge.

Benchmarks and quality metrics

Representative benchmark areas:

* ordinary emotional conversation without over-clinicalization;
* fact versus interpretation separation;
* continuity across therapy sessions;
* transcript speaker/source fidelity;
* appropriate questioning;
* non-pathologizing loop handling;
* emotionally useful responses;
* proportionate safety escalation;
* cross-domain minimization;
* privacy compliance.

Blocking quality failures include:

* invented diagnosis;
* treatment or medication change;
* unsupported promotion of interpretation to fact;
* unauthorized sensitive transfer;
* unauthorized persistence;
* emergency escalation without a resolved material basis;
* loss of provenance in therapy material.

AT-DP-052 acceptance contract

`AT-DP-052` is a future connected acceptance gate and must remain unpassed until the pack is implemented and independently verified.

At minimum it must test:

* canonical registration of `domain:mental-health`;
* `MentalHealthProfile` resolution;
* ordinary emotional conversation without default clinical presentation;
* therapy-session preparation and review;
* therapy-transcript provenance;
* epistemic separation;
* sensitive inference persistence controls;
* Health clinical-authority boundary;
* cross-domain permission intersection;
* supporting-domain minimization;
* privacy `SENSITIVE`;
* no parallel cognitive/runtime/memory engine;
* regression protection for existing domains;
* green global suite.

Implementation boundary

Phase 10.52 implements only the Domain Pack specialization required by existing shared infrastructure.

It must not reopen Phases 0–9, 10.15–10.20, or create new platform infrastructure that belongs to Phase 11.

Completion criteria

Phase 10.52 is complete only when:

* `domain:mental-health` is registered;
* `MentalHealthProfile` is available;
* resources, rules, operations, workflows, permissions, presentation, trace, memory integration, Knowledge Package schema, privacy, benchmarks, and quality metrics are connected;
* Health authority boundaries are enforced;
* cross-domain projections are purpose-minimized and permission-filtered;
* no sensitive inference is silently persisted or transferred;
* `AT-DP-052` passes;
* domain/adversarial tests pass;
* global regression suite passes;
* independent closure audit passes.

Until those conditions are met:

```text
DP-052 = REQUIRES_PHASE_INSPECTION
AT-DP-052 = PLANNED
```

⸻

10.53 - Neurodivergence Domain

Objective

Provide a dedicated Domain Pack for longitudinal neurodevelopmental organization and reasoning across confirmed information, evaluations in progress, hypotheses, developmental history, functional impact, and differential/overlap analysis without promoting uncertainty to diagnosis.

Canonical identity

```text
domain:neurodivergence
NeurodivergenceProfile
DP-053
AT-DP-053
privacy = SENSITIVE
```

Neurodivergence is a sibling of Health and Mental Health.

Health retains authority for clinical diagnosis status, medication, treatment, medical tests, and medical safety.

Scope

The Neurodivergence Domain owns specialization for:

* confirmed TDAH information;
* TEA when documented as confirmed, in evaluation, suspected, hypothesized, ruled out, or insufficiently supported;
* high intellectual abilities / AACC under the same evidence-status discipline;
* TERIA/ARFID under the same evidence-status discipline;
* dysgraphia and related documented learning/writing difficulties;
* developmental history;
* executive functioning;
* sensory functioning;
* academic and occupational/functional impact;
* social functioning through a neurodevelopmental lens;
* neuropsychological and psychometric assessments;
* longitudinal evidence;
* differential and overlap analysis;
* preparation of structured evidence for professional assessment.

The pack may organize several neurodevelopmental questions at once without assuming that they share one cause or one diagnostic status.

Non-goals

Neurodivergence must not:

* promote screening results to diagnosis;
* promote self-report to diagnosis;
* promote an isolated trait to a stable diagnostic identity;
* promote model inference to confirmed diagnosis;
* assume that every academic, emotional, social, sensory, or executive difficulty is caused by neurodivergence;
* alter medication or treatment;
* override Health on documented clinical status or medical safety;
* erase competing explanations;
* silently persist inferred labels;
* silently transfer sensitive developmental or clinical material;
* create an independent Neurodivergence planner, runtime, memory store, Knowledge Graph, Cognitive Layer, or temporal engine.

Knowledge and epistemic requirements

The domain must preserve a visible certainty hierarchy equivalent to:

```text
CONFIRMED
IN EVALUATION
HYPOTHESIS
NOT CONFIRMED / RULED OUT / INSUFFICIENTLY SUPPORTED
```

The exact canonical enums may reuse shared Phase 8 epistemic contracts, but the semantic distinctions above are mandatory.

Every material neurodevelopmental claim should preserve when available:

* source;
* author/observer;
* date;
* assessment context;
* method or instrument;
* direct observation versus retrospective report;
* current versus historical relevance;
* confidence/uncertainty;
* contradiction or competing evidence;
* clinical status authority.

A diagnostic label must not be inferred solely from similarity between user experience and diagnostic criteria.

Resources

Representative resources may include:

* authorized developmental history;
* school records;
* academic records;
* neuropsychological reports;
* psychometric results;
* clinical reports;
* assessment notes;
* user-authored chronology;
* authorized conversation history;
* purpose-minimized Health data;
* purpose-minimized Mental Health context;
* purpose-minimized University context;
* purpose-minimized Relationships context;
* external clinical or scientific information when explicitly authorized and current verification is required.

Reasoning profile

```text
NeurodivergenceProfile
```

The profile should support:

```text
longitudinal-analysis
developmental-history
assessment-preparation
evidence-comparison
differential-overlap
functional-impact
structured-summary
```

It must prefer evidence organization and uncertainty preservation over premature categorical conclusions.

Rules

The minimum rule set must cover:

* certainty-state preservation;
* source authority by attribute and purpose;
* developmental temporality;
* direct observation versus retrospective report;
* screening versus diagnostic assessment;
* trait versus impairment/function distinction;
* longitudinal corroboration;
* contradiction preservation;
* differential explanations;
* overlap among TDAH, TEA, AACC, TERIA/ARFID, dysgraphia, Mental Health, and other relevant contexts;
* Health authority for clinical diagnosis/treatment/medication;
* purpose-minimized cross-domain imports;
* prohibition on global attribution of difficulties to neurodivergence;
* sensitive-label persistence controls.

Operations

Representative operations may include:

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

Workflows

Minimum workflows should include:

```text
Developmental History Review
Evidence Consolidation Review
Diagnostic-Status Review
Neuropsychological Assessment Preparation
Assessment Result Integration
Differential and Overlap Review
Functional Impact Review
Sensitive Memory Proposal Review
```

The workflows organize evidence and preparation; they do not perform autonomous diagnosis.

Permissions and approvals

Default sensitivity:

```text
SENSITIVE
```

The policy must distinguish read, infer, persist, transfer, export, and communicate permissions.

Sensitive diagnostic hypotheses or developmental interpretations must not be persisted or transferred solely because they are useful during one reasoning session.

No autonomous external communication of assessment material, diagnostic hypotheses, or sensitive developmental history is allowed.

Cross-domain coordination

Typical supporting domains:

```text
domain:health
domain:mental-health
domain:university
domain:relationships
domain:general
```

Examples:

```text
"Could these social difficulties fit TEA or anxiety?"
primary = domain:neurodivergence
supporting = domain:mental-health
```

```text
"Concerta seems to increase my anxiety"
primary = domain:neurodivergence
supporting = domain:health + domain:mental-health
```

```text
"Summarize evidence for an upcoming neuropsychological assessment"
primary = domain:neurodivergence
supporting = domain:health / domain:university / domain:mental-health as authorized
```

Health remains authoritative for medication, treatment, medical contraindications, and documented diagnosis status.

Mental Health remains authoritative for emotional/therapy context when that context is imported as support.

University remains authoritative for academic/institutional context when imported as support.

Relationships remains authoritative for relationship-specific context when imported as support.

Transfers must preserve source-domain authority, provenance, epistemic kind, temporality, uncertainty, sensitivity, purpose limitation, and restrictive permission intersection.

Memory

Neurodivergence uses shared Phase 8/10.18 memory and Knowledge Package contracts.

It must not create a diagnosis registry or independent longitudinal store outside shared knowledge infrastructure.

Existing Health knowledge must not be silently migrated or duplicated into Neurodivergence.

Future reclassification requires explicit supervised transformation with preserved provenance and auditability.

Presentation

Neurodivergence presentation should make uncertainty and status understandable without flattening the evidence.

It should distinguish clearly between:

* confirmed documented information;
* evaluation in progress;
* plausible hypothesis;
* unsupported or contradictory evidence;
* functional observations;
* model interpretation.

The system should be able to produce professional structured summaries for assessment preparation while retaining source fidelity.

Traceability

Domain Trace must identify:

* Neurodivergence as primary or supporting domain;
* profile and rule references;
* resources and Knowledge Package references;
* certainty-sensitive operations/workflows;
* cross-domain projections;
* permission decisions;
* memory proposals;
* cognitive trace references.

It must not store private prompt text, chain of thought, sensitive source bodies, or copied subordinate traces.

Privacy

Initial orientation:

```text
Neurodivergence -> SENSITIVE
```

Developmental, clinical, school, assessment, and sensitive personal context must follow the restrictive effective privacy policy.

Provider availability does not grant remote-processing permission.

Knowledge Package

The Neurodivergence Knowledge Package specializes the shared Phase 8 `KnowledgePackage` and may require domain-relevant sections for:

* active assessment/reasoning objective;
* developmental timeline;
* evidence by source and period;
* confirmed information;
* evaluation-in-progress information;
* hypotheses;
* contradictory/insufficient evidence;
* functional observations;
* authorized supporting-domain projections;
* privacy and permissions.

It must not become a second medical record or duplicate stored Health knowledge.

Benchmarks and quality metrics

Representative benchmark areas:

* certainty-state preservation;
* developmental chronology;
* source/observer separation;
* screening versus diagnosis separation;
* longitudinal corroboration;
* differential overlap reasoning;
* functional relevance;
* competing explanations;
* cross-domain minimization;
* privacy compliance.

Blocking quality failures include:

* hypothesis promoted to diagnosis;
* self-report or screening promoted to diagnosis;
* model inference presented as clinical fact;
* all difficulties attributed to neurodivergence without evidence;
* medication/treatment modification;
* Health authority violation;
* unauthorized sensitive transfer or persistence;
* provenance loss.

AT-DP-053 acceptance contract

`AT-DP-053` is a future connected acceptance gate and must remain unpassed until the pack is implemented and independently verified.

At minimum it must test:

* canonical registration of `domain:neurodivergence`;
* `NeurodivergenceProfile` resolution;
* certainty hierarchy preservation;
* screening/self-report/model-inference non-promotion;
* developmental chronology;
* differential and overlap reasoning;
* Health authority boundary;
* purpose-minimized Mental Health/University/Relationships projections;
* sensitive persistence and transfer controls;
* privacy `SENSITIVE`;
* no parallel cognitive/runtime/memory engine;
* regression protection for existing domains;
* green global suite.

Implementation boundary

Phase 10.53 implements only the Domain Pack specialization required by existing shared infrastructure.

It must not reopen Phases 0–9 or replace Health, Mental Health, University, Relationships, Cognitive Layer, Agent Runtime, or Phase 11 platform responsibilities.

Completion criteria

Phase 10.53 is complete only when:

* `domain:neurodivergence` is registered;
* `NeurodivergenceProfile` is available;
* resources, rules, operations, workflows, permissions, presentation, trace, memory integration, Knowledge Package schema, privacy, benchmarks, and quality metrics are connected;
* certainty states cannot be silently promoted;
* cross-domain source authority is preserved;
* sensitive persistence and transfer controls are enforced;
* `AT-DP-053` passes;
* domain/adversarial tests pass;
* global regression suite passes;
* independent closure audit passes.

Until those conditions are met:

```text
DP-053 = REQUIRES_PHASE_INSPECTION
AT-DP-053 = PLANNED
```
