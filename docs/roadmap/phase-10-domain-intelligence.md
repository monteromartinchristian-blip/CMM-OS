🧩 Phase 10 — Domain Intelligence

Objective

To build specialized infrastructure that will allow CMM OS to understand, reason, plan and act differently depending on the area of life or work involved, without fragmenting the system or creating independent architecture.

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
domain:nil
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

Domains should be free to:

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
domain:nil
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
Beliefs and fear
↓
Reflection Domain
↓
Preguntas abiertas
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
profile_name="MedicalProfile",
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

ConcernProfile

LanguageProfile

NilProfile

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

10.17 - Domain Trace

Objective

Record how each domain was resolved, composed, and used during an execution.

Domain Trace

DomainTrace(
id="domain-trace-123",
objective="...",
resolution_context_id="domain-resolution-context-123",
resolution_result_id="domain-resolution-123",
primary_domain="domain:life-plan",
supporting_domains=[],
composition_id="domain-composition-123",
loaded_resources=[],
applied_profiles=[],
applied_rules=[],
executed_operations=[],
executed_workflows=[],
permission_decisions=[],
approval_decisions=[],
cross_domain_transfers=[],
conflicts=[],
warnings=[],
reasoning_trace_ids=[],
started_at="...",
completed_at="...",
duration_ms=820,
metadata={},
)

Cross-Domain Transfer Trace

CrossDomainTransferTrace(
source_domain="domain:health",
target_domain="domain:life-plan",
transferred_knowledge_ids=[],
transferred_entity_ids=[],
purpose="Apply health constraints to planning",
permissions=[],
filtered_items=[],
created_at="...",
metadata={},
)

The following information should be available:

* why a domain was selected
* what dominion was main,
* which domains have been involved,
* which resources were provided by each domain;
* what rules have been put forward by each domain,
* which effective profile was used;
* what permissions have been applied,
* what information was transferred;
* what information was leaked,
* which operations were executed;
* what approvals have been requested;
* which conflicts appeared;
* how they were resolved;
* What resulted from each domain.

Restrictions

The strap should not include:

* internal chains of thought;
* secrets;
* credenciales;
* contenido sensible innecesario;
* information outside permissions;
* prompts privados;
* information not used.

⸻

10.18 - Domain Memory Integration

Objective

Allow domains to read and propose updates about common memory without creating separate warehouses.

Principio general

No:

HealthMemory
UniversityMemory
RelationshipMemory
ProjectMemory

A common memory with:

* knowledge
* entities;
* relaciones;
* procedencia;
* applicable domains;
* sensibilidad;
* permissions
* temporality;
* versions.

Domain Memory View

DomainMemoryView(
domain_id="domain:university",
knowledge_ids=[],
entity_ids=[],
relation_ids=[],
filters={},
permissions=[],
generated_at="...",
metadata={},
)

The view will be a leaked consultation, not a copy.

Domain Memory Update Proposal

DomainMemoryUpdateProposal(
id="domain-memory-proposal-123",
domain_id="domain:health",
session_id="session-123",
additions=[],
updates=[],
invalidations=[],
relations=[],
cross_domain_links=[],
requires_confirmation=True,
confidence=0.9,
reasons=[],
metadata={},
)

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

Domains should be free to:

* create independent persistent copies
* To cover up knowledge with other authorized domains;
* duplicate personas;
* duplicate events;
* double targets
* duplicate decisiones;
* sobrescribir preferencias;
* remove versions;
* Keep knowledge without sources.

⸻

10.19 - General Domain

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

⸻

10.20 - Health Domain

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

⸻

10.21 - Relationships Domain

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

* opposition.create_study_plan;
* opposition.divide_syllabus;
* opposition.track_progress;
* opposition.review_mock_exam;
* opposition.compare_bodies;
* opposition.review_call;
* opposition.generate_weekly_review;
* opposition.identify_risks;
* opposition.generate_revision_plan;
* opposition.update_progress.

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

10.25 - Concerns Domain

Objective

Specify CMM OS to discuss concerns, fears, scenarios, real signs, uncertainty and potential actions without feeding catastrophic conclusions.

Entidades

* concern;
* fear;
* risk;
* scenario;
* trigger;
* belief;
* evidence;
* uncertainty;
* coping_action;
* unresolved_question.

Resources

* user_message;
* conversation;
* note;
* journal_entry;
* event;
* goal;
* memory_entry;
* domain_result.

Rules

ConcernFactScenarioRule

Distingue:

* hecho;
* possibility;
* escenario;
* miedo;
* prediction.

CatastrophicCertaintyRule

Avoid treating the worse stage as a probable result.

ControllableUncontrollableRule

Separa:

* aspectos controlables;
* parcialmente controlables;
* uncontrollable.

EvidenceBalanceRule

Searches for evidence for and against.

ImmediateRiskRule

It detects when a concern represents a real current risk.

ReassuranceLoopRule

Avoid generating repeated confirmation cycles without new information.

Operaciones

* concerns.structure_concern;
* concerns.separate_fact_scenario;
* concerns.compare_risks;
* concerns.identify_controllable_actions;
* concerns.detect_open_questions;
* concerns.generate_monitoring_plan;
* concerns.review_evolution;
* concerns.prepare_professional_discussion.

Workflows

Concern Analysis

Risk and Scenario Review

Recurring Concern Review

Decision Under Uncertainty

Monitoring Plan

Permissions

* co-ordination with Health at risk
* Coordination with Reflection
* without diagnoses,
* without false peace and quiet,
* without alarm,
* controlled memory for transitional concerns.

⸻

10.26 - Languages Domain

Objective

Specify CMM OS to manage language, level, goals, practice, errors, planning and evaluation.

Entidades

* language;
* skill;
* proficiency_level;
* exercise;
* mistake;
* vocabulary_item;
* grammar_topic;
* study_session;
* exam;
* certification;
* learning_goal.

Resources

* language_plan;
* exercise_result;
* conversation;
* writing_sample;
* audio_transcript;
* vocabulary_list;
* exam_guide;
* calendar_event;
* user_message;
* memory_entry.

Rules

LanguageLevelEvidenceRule

Distinguishes certified level, estimated level, and point-in-time performance.

SkillSeparationRule

Separa:

* oral understanding
* oral expression
* written understanding
* written expression;
* grammar
* vocabulario.

ErrorPatternRule

It detects recurrent errors without generalizing from a minimum sample.

SpacedReviewRule

Prioriza revisiones temporalmente distribuidas.

LearningLoadRule

It adapts the plan to time, energy and other targets.

CertificationTemporalRule

Checks official calls, levels, and current dates.

Operaciones

* languages.assess_sample;
* languages.create_learning_plan;
* languages.generate_exercises;
* languages.review_errors;
* languages.track_vocabulary;
* languages.prepare_exam;
* languages.generate_weekly_review;
* languages.update_level_evidence;
* languages.plan_conversation_practice.

Workflows

Language Level Review

Weekly Language Plan

Writing Review

Speaking Practice

Certification Preparation

Vocabulary Review

Permissions

* bajo riesgo;
* monitoring of recurrent errors
* non-automatic external actions;
* calendars under authorisation.

⸻

10.27 - Nil Domain

Objective

Specify CMM OS to organize the paternity project, its decisions, dependencies, scenarios, documentation and long term planning.

The domain name will be configurable and will not have to link architecture to a particular personal name.

Entidades

* parenthood_goal;
* child_project;
* country;
* legal_route;
* medical_route;
* clinic;
* agency;
* donor;
* financial_scenario;
* legal_requirement;
* timeline;
* decision;
* ethical_constraint;
* school;
* residence_plan.

Resources

* life_plan;
* legal_document;
* medical_report;
* financial_plan;
* agency_information;
* country_information;
* decision;
* note;
* user_message;
* external_source;
* memory_entry.

Rules

ParenthoodDecisionExplicitRule

It prevents registration of decisions that are not expressed by the user.

LegalTemporalValidityRule

It requires monitoring of existing legislation.

MedicalLegalSeparationRule

Distinguish medical, legal, economic and administrative requirements.

EthicalConstraintRule

It retains ethical criteria as restrictions.

CountryComparisonRule

Compare countries using common criteria.

CostUncertaintyRule

Preserves ranges, contingencies, and unconfirmed costs.

LongTermDependencyRule

Relates:

* ingresos;
* vivienda;
* edad;
* training
* estabilidad;
* legislation
* Medical times.

Operaciones

* nil.build_parenthood_timeline;
* nil.compare_countries;
* nil.compare_routes;
* nil.review_legal_requirements;
* nil.review_financial_scenarios;
* nil.prepare_questions;
* nil.track_decisions;
* nil.update_project_plan;
* nil.generate_documentation_checklist;
* nil.review_risks.

Workflows

Parenthood Project Review

Country Comparison

Agency Review

Legal Route Review

Financial Readiness Review

Medical Preparation

Annual Plan Update

Permissions

* sensibilidad alta;
* Mandatory web verification for changing information
* priority official sources;
* without final legal decisions
* without payment;
* without contact with agencies;
* without the persistence of decisions inferred.
* human approval for any outside action.

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

Objective

To define explicit policies to solve domains in a predictable and auditable manner.

Domain Selection Policy

DomainSelectionPolicy(
name="default",
explicit_domain_priority=True,
session_domain_priority=True,
goal_domain_priority=True,
allow_multi_domain=True,
maximum_supporting_domains=3,
minimum_primary_confidence=0.7,
minimum_supporting_confidence=0.55,
fallback_domain="domain:general",
ambiguity_strategy="clarify_or_fallback",
metadata={},
)

Initial policies

Explicit First

It respects the domain expressly indicated with the exception of a security conflict.

Session Continuity

Maintain session domain as long as it remains relevant.

Goal Priority

Prioritizes the domain of the active target.

High-Risk Conservative

It requires better confidence for medical, legal or financial domains.

Multi-Domain Limited

It allows several domains with boundaries.

General Fallback

He uses General Domain if there's insufficient evidence.

Reevaluation Policy

It allows to change the composition if new information appears during the workflow.

Domain change

When changing main domain:

* The ground for registration should be established.
* The context should be preserved.
* permissions should be re-evaluated.
* profiles have to be re-evaluated.
* Reevaluating rules
* Questions have to be re-evaluated.
* they should not duplicate operations;
* The sitting should be updated.

⸻

10.32 - Domain Conflict Resolution

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

Objective

Extender Session Context to preserve the specialized status of a domain performance.

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

Objective

Allow to create, validate, test and pack new domains without changing CMM OS core.

CLI inicial

cmm domain create <name>
cmm domain inspect <domain-id>
cmm domain list
cmm domain discover
cmm domain validate <path>
cmm domain test <path>
cmm domain install <path>
cmm domain uninstall <domain-id>
cmm domain enable <domain-id>
cmm domain disable <domain-id>
cmm domain reload <domain-id>
cmm domain pack <path>
cmm domain publish <path>
cmm domain capabilities <domain-id>
cmm domain operations <domain-id>
cmm domain workflows <domain-id>
cmm domain permissions <domain-id>
cmm domain resolve --input "..."
cmm domain trace <trace-id>

Scaffold

cmm domain create finance

Resultado:

finance/
├── manifest.yaml
├── README.md
├── resources/
│   └── **init**.py
├── profiles/
│   └── finance.py
├── rules/
│   └── **init**.py
├── operations/
│   └── **init**.py
├── workflows/
│   └── review.yaml
├── permissions/
│   └── finance.yaml
├── presentation/
│   └── policy.yaml
├── validators/
│   └── **init**.py
├── fixtures/
│   └── sample.json
└── tests/
├── test_manifest.py
├── test_rules.py
├── test_operations.py
└── test_workflows.py

SDK Components

* DomainBuilder;
* ManifestBuilder;
* ResourceRegistrationAPI;
* RuleRegistrationAPI;
* OperationRegistrationAPI;
* WorkflowRegistrationAPI;
* PermissionBuilder;
* PresentationBuilder;
* DomainTestHarness;
* DomainFixtureLoader;
* DomainPackager;
* DomainCompatibilityChecker.

Domain Test Harness

It should allow:

* Loan the domain independently.
* using memory stors;
* using simulated resources;
* enforce rules;
* execute operations;
* execute workflows;
* simulate permissions
* simular approvals;
* inspeccionar traces;
* check fragmentation
* check compatibility.

Plantillas

* basic_domain;
* personal_domain;
* high_risk_domain;
* project_domain;
* read_only_domain;
* external_service_domain;
* multi_domain_extension.

⸻

10.36 - Domain API

Objective

Expand domain capabilities with stable contracts.

The API should allow:

* list domains
* consult domains;
* descubrir;
* validate;
* instalar;
* habilitar;
* deshabilitar;
* to solve domains;
* query capabilities;
* to consult resources;
* to consult rules;
* query operations;
* query workflows;
* execute operations;
* iniciar workflows;
* To consult sessions;
* query conflicts;
* query traces;
* to consult permissions;
* responder approvals;
* generate memory proposals.

Endpoints conceptuales

GET /domains
GET /domains/{domain_id}
POST /domains/resolve
POST /domains/validate
POST /domains/{domain_id}/enable
POST /domains/{domain_id}/disable
GET /domains/{domain_id}/capabilities
GET /domains/{domain_id}/operations
GET /domains/{domain_id}/workflows
POST /domains/{domain_id}/operations/{operation_id}
POST /domains/{domain_id}/workflows/{workflow_id}
GET /domain-sessions/{session_id}
GET /domain-traces/{trace_id}
GET /domain-conflicts
POST /domain-approvals/{approval_id}

The API and CLI should use the same internal services.

No parallel implementations are required.

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

⸻

10.38 - Security

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

Objective

Ensure that specialization does not turn CMM OS into an unconnected set of subsystems.

Domains should be free to:

* To create an own memory
* create an own Knowledge Store
* creating an own Knowledge Graphh
* to create an own Resuscitation Engine
* create an agent Runtime of its own
* To create an own Planner
* To create an own Workflow Engine
* to create an own permit system;
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

⸻

10.40 - Integration with Cognitive Layer

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
* University prioritizes dates, constraints, feasibility, and plan quality.
* Project prioritizes correctness, architecture, validation, and tool calling.

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
Life Plan Knowledge Package
Project Knowledge Package
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
Nil / Parenthood   -> SENSITIVE
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
* Nil;
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
86. Nil Domain minimum
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
* Nil Domain;
* Sport Domain;
* Life Plan Domain;
* Project Domain;
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
* Nil Domain minimum
* Minimum Sport Domain
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
* develop and maintain its own code.

All of this without creating isolated assistants, duplicated memories, or incompatible architecture.

The Cognitive Layer will continue to determine how knowledge is represented and built.

The Agent Runtime will continue to determine how targets and actions are pursued.

Domain Intelligence will determine what specialization should be applied in each context.

From this infrastructure, Phase 11 can integrate UI, goals, workflows, agents, memory, knowledge, permissions, and domains into a complete, extensible, and coherent personal platform.
