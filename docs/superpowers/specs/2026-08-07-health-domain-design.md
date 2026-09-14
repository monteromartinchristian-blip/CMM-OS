# Phase 10.20 — Health Domain Design

Status: Approved design

Date: 2026-08-07

## 1. Purpose

Health Domain especializa CMM OS para:

- organizar información sanitaria;
- analizar evolución temporal;
- preparar consultas;
- comparar informes y pruebas;
- detectar contradicciones;
- identificar información ausente;
- reconocer señales que requieran revisión profesional;
- producir contexto sanitario trazable.

Health NO:

- proporciona diagnósticos definitivos;
- sustituye profesionales sanitarios;
- inicia/suspende/modifica medicación;
- toma decisiones de tratamiento;
- comunica automáticamente con terceros;
- convierte inferencias del sistema en hechos clínicos.

**Domain ID**: `domain:health`

**Kind**: `personal`

**Sensitivity**: `high`

## 2. Architectural principle

Health será el segundo Domain Pack canónico completo después de General.

Debe reutilizar infraestructura existente:

- Resource / provenance / temporality / sensitivity;
- Entity;
- KnowledgeItem;
- Cognitive Profiles;
- Reasoning Rules;
- Agent Runtime;
- approvals;
- DomainDefinition;
- DomainResourceDefinition;
- DomainProfileDefinition;
- DomainOperationDefinition;
- DomainWorkflowDefinition;
- Domain permissions;
- Domain presentation;
- Domain memory integration;
- Domain trace;
- registries comunes existentes.

Health NO crea:

- `HealthEntity`;
- `HealthEntityStore`;
- `HealthMemory`;
- `HealthTrace`;
- reasoning engine médico;
- planner médico;
- workflow engine médico;
- runtime médico;
- registries médicos paralelos;
- almacenamiento sanitario separado.

Shared data exists once and receives domain bindings.

## 3. Package boundary

Diseño previsto:

```
cmm/domains/health/
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

Responsabilidad:

| Módulo | Responsabilidad |
|--------|-----------------|
| `catalog.py` | single source of truth del contenido canónico Health. |
| `definition.py` | `DomainDefinition`. |
| `profile.py` | `DomainProfileDefinition`. |
| `resources.py` | construcción/validación de resource definitions. |
| `rules.py` | `ReasoningRule` definitions + helpers clínicos puros. |
| `operations.py` | `DomainOperationDefinitions`. |
| `workflows.py` | `DomainWorkflowDefinitions`. |
| `permissions.py` | política Health sobre contratos de permisos existentes. |
| `presentation.py` | presentation policy Health. |
| `memory.py` | adaptación a Domain Memory existente; proposal-only. |
| `trace.py` | referencias Domain Trace existentes; reference-only. |
| `integration.py` | registration validation-first + atomicidad. |
| `bootstrap.py` | construcción oficial del dominio estándar. |
| `__init__.py` | API pública sin side effects. |

## 4. Canonical health entities

Health reconoce exactamente estos **15** tipos semánticos:

- `symptom`
- `diagnosis`
- `medication`
- `treatment`
- `medical_test`
- `medical_report`
- `specialist`
- `appointment`
- `procedure`
- `surgery`
- `allergy`
- `adverse_effect`
- `vital_sign`
- `medical_condition`
- `healthcare_provider`

Estos **NO** son nuevas clases persistentes.

Se expresan utilizando Entity / KnowledgeItem canónicos y bindings de dominio.

Health puede añadir:

- validación semántica;
- clasificación;
- mappings;
- provenance;
- temporalidad;
- relaciones.

Nunca almacenamiento paralelo.

## 5. Canonical resources

Exactamente **12**:

- `health.medical_report`
- `health.prescription`
- `health.medication_list`
- `health.symptom_log`
- `health.laboratory_result`
- `health.imaging_report`
- `health.appointment`
- `health.discharge_report`
- `health.treatment_plan`
- `health.user_message`
- `health.health_memory`
- `health.external_medical_source`

Todos se consideran **high sensitivity**.

Deben reutilizar:

- provenance;
- temporality;
- reliability;
- sensitivity;
- permissions;
- shared resource identity.

Un resource compartido no debe duplicarse para Health.

## 6. Epistemic model

Health debe preservar explícitamente la diferencia entre:

- `documented_information`;
- `clinical_observation`;
- `reported_symptom`;
- `documented_diagnosis`;
- `guidance/provisional diagnosis`;
- `system_hypothesis`;
- `user_possibility`;
- `contradiction`;
- `missing_information`;
- `red_flag`;
- `escalation`.

El sistema jamás puede promover silenciosamente:

```
hypothesis -> diagnosis
possibility -> fact
temporal association -> causation
provisional diagnosis -> confirmed diagnosis
```

La provenance debe conservarse durante todo el pipeline.

## 7. Deterministic clinical helpers

Adoptamos enfoque:

```
declarative domain + pure deterministic clinical helpers.
```

Los helpers:

- no tienen estado;
- no hacen IO;
- no consultan modelos;
- no leen memoria por sí mismos;
- no usan reloj interno;
- no mutan registries;
- reciben fechas/contexto explícitamente;
- devuelven estructuras deterministas.

Conceptualmente:

- `classify_clinical_statement()`
- `build_medication_temporal_relation()`
- `classify_escalation_level()`
- `clinical_source_rank()`
- `evaluate_clinical_temporality()`
- `detect_medication_conflicts()`
- `validate_diagnostic_claim()`
- `evaluate_professional_escalation()`

No introducir estas funciones como infraestructura global salvo que durante
implementación se demuestre una necesidad real.

## 8. Canonical reasoning rules

Exactamente **8**:

1. **DistinguishSymptomDiagnosisHypothesis**

   Distingue:

   - established/reported symptom;
   - clinical observation;
   - documented diagnosis;
   - guidance/provisional diagnosis;
   - system hypothesis;
   - possibility proposed by user.

2. **MedicationTemporalRelationshipRule**

   Representa:

   - start date;
   - dose change;
   - symptom onset;
   - withdrawal;
   - re-exposure;
   - evolution.

   Regla crítica:

   ```
   temporal association != causation
   ```

3. **MedicalRedFlagRule**

   Clasifica necesidad de:

   - monitoring;
   - professional review;
   - priority review;
   - urgent attention.

   No diagnostica la causa de la red flag.

4. **ClinicalSourcePriorityRule**

   Prioridad conceptual:

   - medical report;
   - test result;
   - prescription;
   - identified professional;
   - primary medical source;
   - user statement;
   - inference.

   La prioridad no elimina provenance ni contradicciones.

5. **MedicalTemporalValidityRule**

   Evalúa:

   - active treatment;
   - withdrawn medication;
   - provisional diagnosis;
   - pending test;
   - stale/obsolete result;
   - future appointment;
   - superseded state;
   - state transition.

6. **MedicationConsistencyRule**

   Detecta:

   - incompatible dose records;
   - divergent medication lists;
   - duplicate medication;
   - inconsistent dates;
   - medication simultaneously active/withdrawn.

   Detectar conflicto NO equivale a decidir qué registro es correcto.

7. **NoDefinitiveDiagnosisRule**

   Impide que inferencia/hipótesis sea presentada o persistida como diagnóstico
   definitivo.

8. **ProfessionalEscalationRule**

   Escala cuando exista, entre otros:

   - risk;
   - significant deterioration;
   - insufficient exploration;
   - missing important tests;
   - important unresolved contradiction;
   - request for clinical decision;
   - uncertainty the system cannot safely resolve.

## 9. Health profile

`HealthProfile` debe ser `DomainProfileDefinition` normal.

Perfil conservador:

- provenance weighted strongly;
- temporal validity weighted strongly;
- documentary evidence before inference;
- explicit uncertainty;
- visible contradictions;
- low tolerance for unsupported clinical conclusions;
- early escalation for high-impact uncertainty;
- no promotion of model hypothesis to clinical fact.

No reasoning engine específico.

## 10. Canonical operations

Exactamente **12** IDs:

- `health.build_medical_timeline`
- `health.build_symptom_timeline`
- `health.compare_reports`
- `health.compare_test_results`
- `health.review_medication_changes`
- `health.prepare_medical_appointment`
- `health.generate_medical_summary`
- `health.prepare_questions`
- `health.register_symptom_update`
- `health.detect_open_medical_questions`
- `health.review_follow_up`
- `health.export_medical_context`

Semántica:

| Operation | Semántica |
|-----------|-----------|
| `build_medical_timeline` | timeline estructurada, temporal y trazable. |
| `build_symptom_timeline` | evolución de síntomas sin diagnóstico implícito. |
| `compare_reports` | cambios, diferencias y contradicciones documentadas. |
| `compare_test_results` | comparación temporal/unidades/contexto sin interpretación definitiva. |
| `review_medication_changes` | secuencia de medicación + síntomas + inconsistencias + preguntas. Nunca recomienda iniciar/parar/cambiar dosis. |
| `prepare_medical_appointment` | dossier estructurado para consulta. |
| `generate_medical_summary` | resumen sanitario con provenance e incertidumbre. |
| `prepare_questions` | preguntas para profesional. |
| `register_symptom_update` | proposal-only. Nunca persistencia sensible directa. |
| `detect_open_medical_questions` | identifica preguntas, lagunas y contradicciones abiertas. |
| `review_follow_up` | revisa pendientes, evolución y elementos que necesitan atención. |
| `export_medical_context` | construye contexto exportable. NO envía ni comunica externamente. |

## 11. Operation execution model

Declarar una operation NO implica implementarla.

Health sigue **fail-closed**:

```
missing implementation -> UNAVAILABLE / disabled
as required by canonical operation contracts.
```

Las implementations se inyectan.

Deben validarse usando la validación canónica existente antes de primera
mutation.

Incluso con implementation válida, permission/rule enforcement puede bloquear
la ejecución.

## 12. Canonical workflows

Exactamente **8**:

- `health.medical_follow_up`
- `health.symptom_review`
- `health.medication_change_review`
- `health.specialist_appointment_preparation`
- `health.medical_report_comparison`
- `health.postoperative_follow_up`
- `health.chronic_condition_timeline`
- `health.diagnostic_process_review`

Patrón conceptual:

```
resolve authorized resources
-> validate provenance
-> validate temporality
-> apply Health rules
-> detect contradictions/missing information/red flags
-> determine escalation
-> if escalation required: pause / human review
-> otherwise execute allowed analysis
-> apply presentation policy
-> optional memory proposal
-> stop before external or clinical action
```

**Medication Change Review**:

- Terminal permitido: `professional review / questions / escalation`
- Terminal prohibido: `change medication`

**Diagnostic Process Review**:

Organiza:

- documented diagnoses;
- hypotheses;
- tests performed;
- tests pending;
- contradictions;
- unresolved questions.

Nunca "resuelve" automáticamente el diagnóstico.

## 13. Permissions

Health usa los permission contracts existentes.

Política conservadora:

**ALLOWED**, subject to authorization:

- read authorized health resources;
- organize;
- compare;
- summarize;
- construct timelines;
- identify contradictions;
- identify missing information;
- prepare questions;
- generate structured proposals;
- escalate.

**FORBIDDEN**:

- definitive diagnosis;
- medication start;
- medication stop;
- dose change;
- automatic treatment decision;
- automatic external communication;
- writing inferred clinical decisions as facts;
- unauthorized sensitive cross-domain transfer;
- unconfirmed sensitive memory persistence.

- Sensitive memory requires confirmation.
- Multi-domain access is restricted.
- Sensitive inference is limited.
- Human/professional escalation is mandatory when applicable.
- Composition uses the most restrictive effective policy.

## 14. Presentation policy

Canonical ordering:

1. `documented_information`
2. `reported_symptoms`
3. `temporal_changes`
4. `hypotheses_and_possibilities`
5. `contradictions`
6. `missing_information`
7. `red_flags`
8. `questions_for_professional`
9. `authorized_next_steps`

Presentation preserves:

- provenance;
- uncertainty;
- temporality;
- epistemic category;
- escalation state.

Renderer must not transform:

```
possible adverse effect
-> adverse effect caused by medication
```

or:

```
provisional diagnosis
-> confirmed diagnosis
```

or:

```
user reported X
-> X is clinically established
```

## 15. Memory integration

Reuse Phase 10 Domain Memory contracts.

No `HealthMemory` store.

Health reads only authorized memory views.

Sensitive updates use:

```
DomainMemoryProposalSnapshot
+ canonical proposal binding
+ provenance
+ explicit confirmation
```

`register_symptom_update` is **proposal-only**.

No direct sensitive persistence.

Memory identity remains global, not domain-local.

## 16. Trace integration

Reuse Domain Trace contracts.

No `HealthTrace` model.

Health contributes:

- references;
- domain contribution metadata;
- rule/operation/workflow references;
- provenance references;
- escalation information where contracts permit.

No fabricated semantic IDs.

Trace remains reference-oriented.

## 17. Registration and atomicity

`register_health_domain()` debe nacer con las lecciones de General 10.19 ya
incorporadas.

**Phase 1**: complete deterministic prevalidation BEFORE first mutation.

Debe validar, cuando registry esté presente:

Domain definition collision.

Profile:

- profile ID collision;
- profile domain collision.

Resources:

- canonical local collisions.

Rules:

- canonical local collisions.

Operations:

- DomainOperation duplicate;
- common AgentOperation duplicate;
- provided implementation IDs;
- implementation definition compatibility;
- execute signature compatibility.

Workflows:

- DomainWorkflow duplicate;
- common Workflow duplicate.

Permissions / presentation / demás registries:

- cualquier conflicto determinista que el register posterior pueda rechazar
  y sea observable mediante API pública.

Después:

```
snapshot registries
-> mutate
-> rollback only for unexpected runtime failure.
```

Rollback NO sustituye prevalidation.

Nested common registries must be included in deterministic prevalidation.

## 18. Snapshot/restore policy

Health NO crea snapshot contracts nuevos.

Usa los existentes.

Registration-parity remains mandatory:

```
restore_state(snapshot) cannot admit state that normal register() would reject.
```

Esto aplica a los registries comunes utilizados por Health.

## 19. Domain resolution

Health es **high-impact**.

Debe reutilizar Domain Resolution existente.

No crear `HealthResolver`.

Principios:

- explicit health signals may select Health;
- confidence/eligibility policy remains global;
- insufficient confidence in high-impact context must not silently execute;
- permission/availability/degraded state must be honored;
- General fallback must not bypass an ineligible specialized Health domain when
  global resolver policy says it must block/escalate.

## 20. Public API and imports

Importing `cmm.domains.health`:

- no registry mutation;
- no bootstrap execution;
- no environment reads;
- no IO;
- no model calls;
- no time-dependent side effects.

Public API must expose only intentional Health contracts/builders.

## 21. Catalog reconciliation

`catalog.py` is the single source of truth.

Tests must prove exact reconciliation between catalog and:

- `DomainDefinition.resources`
- `DomainDefinition.rules`
- `DomainDefinition.operations`
- `DomainDefinition.workflows`
- permissions/presentation declarations where represented.

No duplicated hand-maintained lists that may drift.

## 22. Error handling

Prefer existing typed registry/domain errors.

Do not invent Health-specific error hierarchy unless a genuinely novel
contract requires it.

- Deterministic invalid configuration: fail before mutation.
- Runtime unexpected failure: rollback.
- Clinical uncertainty: structured uncertainty/escalation, not exception unless
  contract-invalid.
- Safety violation: blocked through rules/permissions using existing
  infrastructure.

## 23. Testing strategy

Health debe tener profundidad equivalente a General 10.19.

Planificar posteriormente tests para:

- definition;
- catalog reconciliation;
- profile;
- resources;
- rules;
- pure clinical helpers;
- operations;
- workflows;
- permissions;
- presentation;
- memory;
- trace;
- integration;
- rollback;
- bootstrap;
- public API;
- clean import;
- fail-closed implementations;
- validation-first;
- nested common registry collisions;
- sensitive memory proposal behavior;
- temporal association != causation;
- epistemic-category preservation;
- no-definitive-diagnosis;
- medication-change prohibition;
- escalation;
- full domain reconciliation.

No implementación todavía.

## 24. Non-goals for Phase 10.20

No:

- medical diagnosis engine;
- medication recommendation engine;
- drug interaction database;
- emergency triage replacement;
- autonomous clinician communication;
- EHR integration;
- prescription writing;
- clinical decision support certification;
- new persistent health database;
- new model/provider;
- Health-specific planner/runtime/memory/trace;
- UI específica;
- external API integration.

Esas capacidades requerirían fases/decisiones separadas.

## 25. Acceptance criteria

El diseño de 10.20 se considera implementado cuando:

- `domain:health` existe como Domain Pack completo;
- reutiliza contratos existentes;
- no duplica infrastructure;
- contiene exactamente 15 entity semantics;
- contiene exactamente 12 resources;
- contiene exactamente 8 reasoning rules;
- contiene exactamente 12 operations;
- contiene exactamente 8 workflows;
- operations sin implementation son fail-closed;
- no diagnosis definitivo;
- no medication modification;
- no automatic external communication;
- sensitive memory es proposal + confirmation;
- provenance/temporality/uncertainty se preservan;
- temporal relation never silently becomes causation;
- registration is validation-first and atomic;
- common nested registries are prevalidated;
- imports are side-effect free;
- catalog reconciliation is exact;
- focal/domain/global regressions remain green.

## 26. Future considerations — explicitly out of scope

Registrar como follow-up, NO implementar ahora:

1. evaluar si helpers clínicos puros suficientemente genéricos deben ascender
   posteriormente a infraestructura compartida;

2. evaluar hardening de dependencias/security gates si una dependency mínima
   permitida queda afectada por vulnerabilidades conocidas;

3. revisar de forma separada cualquier uso de APIs privadas heredadas en
   memory integration; no resolverlo dentro de Health salvo necesidad directa.
