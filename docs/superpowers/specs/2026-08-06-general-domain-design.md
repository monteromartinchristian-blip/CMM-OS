# General Domain Design — Phase 10.19

## 1. Objetivo y alcance

Implementar `domain:general` como dominio base para solicitudes no especializadas,
análisis general de información, organización de información común, clarificación
de objetivos, apoyo prudente a decisiones, revisiones periódicas y fallback seguro
cuando no existe un dominio especializado aplicable.

El General Domain demuestra que toda la infraestructura de Domain Intelligence
(Fases 10.1–10.18) puede componer un dominio completo sin crear motores paralelos,
almacenamientos separados ni accesos directos al runtime.

## 2. Principios arquitectónicos

1. **Capa declarativa y de composición**: General Domain reutiliza directamente
   los contratos, registries, resolvers, selectors, validators, planners y adapters
   existentes. No crea motores paralelos.
2. **No side effects al importar**: La construcción se realiza mediante factories
   explícitas, deterministas e idempotentes.
3. **Fail-closed**: Ante cualquier estado desconocido, se deniega, rechaza o bloquea.
4. **Low-risk por defecto**: El perfil es prudente y de bajo riesgo.
5. **No catch-all**: General Domain no absorbe silenciosamente solicitudes cuando
   existe un dominio especializado válido.
6. **Determinismo**: Dos construcciones con las mismas entradas producen objetos
   iguales y el mismo digest.
7. **Serialización estricta**: Contratos frozen, deep immutability, enums exactos,
   sin coerción implícita, unknown fields rechazados.

## 3. Dependencias con Fases 10.1–10.18

| Fase | Contrato reutilizado |
|------|---------------------|
| 10.1 | `DomainDefinition`, `DomainMetadata`, `DomainCapability`, `DomainDependency`, `DomainConflict` |
| 10.2 | `DomainManifest`, `DomainPack`, `DomainComponentReference`, `DomainPermissionReference`, `DomainCompatibility` |
| 10.4 | `DeclarativeDomainLoader`, `DomainLoader` |
| 10.5 | `PipelineDomainValidator`, `build_domain_validation_context` |
| 10.6 | `DomainResolutionContextBuilder`, `DomainResolutionContext` |
| 10.7 | `DefaultDomainResolver`, `DomainResolutionResult`, `DomainScoringPolicy` |
| 10.8 | `DefaultDomainComposer`, `DomainComposition` |
| 10.10 | `DomainResourceDefinition`, `DomainResourceTemporalPolicy`, `DomainResourceValidationRule` |
| 10.11 | `DomainProfileDefinition`, `DomainQuestionPolicy`, `DomainPresentationPolicy`, `DomainMemoryPolicy`, `DomainTemporalPolicy`, `DomainProductionPolicy` |
| 10.12 | `DomainReasoningRuleDefinition`, `DomainRuleResult`, `DomainRuleExecutionResult` |
| 10.13 | `DomainOperationDefinition`, `DomainOperationRequest`, `DomainOperationResult` |
| 10.14 | `DomainWorkflowDefinition`, `WorkflowNode`, `WorkflowNodeType` |
| 10.15 | `DomainPermissionPolicy`, `DomainAutonomyLimits`, `PermissionCapability` |
| 10.16 | `DomainPresentationPolicy`, `DomainPresentationPlanner`, `DomainPresentationPlan` |
| 10.17 | `DomainTrace`, `DomainTraceAssembler`, `DomainTraceReference` |
| 10.18 | `DomainMemoryViewRequest`, `DomainMemoryView`, `DomainMemoryProposalSnapshot`, `DomainMemoryProposalBinding` |

## 4. Definición de `domain:general`

- **ID canónico**: `domain:general`
- **Nombre**: `general`
- **Display name**: `General`
- **Versión**: `1.0.0`
- **Kind**: `DomainKind.CORE`
- **Manifest ID**: `manifest:general:1.0.0`
- **Reasoning profile**: `GeneralProfile`
- **Descripción**: Dominio base para solicitudes no especializadas, análisis general
  de información, organización de información común, clarificación de objetivos,
  apoyo prudente a decisiones, revisiones periódicas y fallback seguro.

## 5. Recursos

Nueve resource kinds declarados mediante `DomainResourceDefinition`:

| ID | Kind | Adapter | Sensibilidad | Fiabilidad |
|----|------|---------|--------------|------------|
| `general.user_message` | `user_message` | `cognitive.message` | `INTERNAL` | 0.5 |
| `general.conversation` | `conversation` | `cognitive.conversation` | `INTERNAL` | 0.5 |
| `general.calendar_event` | `calendar_event` | `cognitive.calendar` | `INTERNAL` | 0.7 |
| `general.note` | `note` | `cognitive.note` | `INTERNAL` | 0.6 |
| `general.document` | `document` | `cognitive.document` | `INTERNAL` | 0.7 |
| `general.memory_entry` | `memory_entry` | `cognitive.memory` | `INTERNAL` | 0.8 |
| `general.generic_task` | `generic_task` | `cognitive.task` | `INTERNAL` | 0.6 |
| `general.generic_goal` | `generic_goal` | `cognitive.goal` | `INTERNAL` | 0.6 |
| `general.external_source` | `external_source` | `cognitive.external` | `RESTRICTED` | 0.3 |

Reglas de recursos:
- `user_message`: no verificado, conserva provenance, no se convierte en hecho.
- `conversation`: compuesto/referencia, no expone prompts privados.
- `calendar_event`: preserva fecha/zona horaria/fuente/estado, no implica tarea.
- `note`: puede contener hechos/opiniones/hipótesis, conserva procedencia.
- `document`: conserva referencia/checksum/provenance, no se modifica.
- `memory_entry`: se resuelve mediante Domain Memory Integration.
- `generic_task`: representación genérica, creación requiere operación/permisos.
- `generic_goal`: objetivo no especializado, actualizaciones producen propuestas.
- `external_source`: no confiable por defecto, fail-closed sin provenance.

## 6. Perfil

`GeneralProfile` mediante `DomainProfileDefinition`:

- **ID**: `general.profile`
- **Profile name**: `GeneralProfile`
- **Domain**: `domain:general`
- **Required rules**: `general.temporal_validity`, `general.source_reliability`,
  `general.ambiguity`, `general.permission`, `general.goal_clarification`,
  `general.duplication`
- **Allowed resource kinds**: los nueve kinds del dominio
- **Minimum confidence**: `0.55`
- **Reasoning depth**: `DomainReasoningDepth.STANDARD`
- **Maximum questions**: `8`
- **Prohibited actions**: `external_communication`, `file_modification`,
  `schedule_modification`, `task_creation_persistent`, `goal_update_persistent`,
  `sensitive_inference`, `medical_decision`, `legal_decision`, `financial_decision`,
  `export`, `shell_execution`
- **Memory policy**: `allow_read=True`, `allow_write=False` (solo proposals)
- **Temporal policy**: `require_current_information=True`,
  `allow_historical_information=True`, `require_temporal_provenance=True`
- **Production policy**: `allow_draft=True`, `allow_final=False`,
  `allow_external_action=False`, `require_review=True`, `require_validation=True`
- **Question policy**: `maximum_questions=8`, `require_deduplication=True`,
  `allow_clarification=True`, `stop_on_blocking_gap=True`

## 7. Reglas

Seis reglas mediante `DomainReasoningRuleDefinition`:

| ID | Nombre | Categoría | Prioridad |
|----|--------|-----------|-----------|
| `general.temporal_validity` | `GeneralTemporalValidityRule` | `temporality` | 800 |
| `general.source_reliability` | `GeneralSourceReliabilityRule` | `epistemic` | 790 |
| `general.ambiguity` | `GeneralAmbiguityRule` | `inference` | 780 |
| `general.permission` | `GeneralPermissionRule` | `safety` | 770 |
| `general.goal_clarification` | `GeneralGoalClarificationRule` | `planning` | 760 |
| `general.duplication` | `GeneralDuplicationRule` | `consistency` | 750 |

Todas las reglas son puras, deterministas, model-independent, registrables,
versionadas, componibles, permission-aware, traceable, sin I/O, sin persistencia,
sin acceso directo a stores.

## 8. Operaciones

Ocho operaciones mediante `DomainOperationDefinition`:

| ID | Tipo | Riesgo | Reversible | Approval |
|----|------|--------|------------|----------|
| `general.create_summary` | `ANALYSIS` | `LOW` | No | No |
| `general.build_timeline` | `ANALYSIS` | `LOW` | No | No |
| `general.compare_items` | `ANALYSIS` | `LOW` | No | No |
| `general.prepare_questions` | `PREPARATION` | `LOW` | No | No |
| `general.create_task` | `PLANNING` | `LOW` | No | Sí |
| `general.update_goal` | `PLANNING` | `LOW` | No | Sí |
| `general.generate_report` | `PREPARATION` | `LOW` | No | No |
| `general.search_knowledge` | `READ` | `LOW` | No | No |

`general.create_task` y `general.update_goal` producen propuestas estructuradas
(`DomainMemoryProposalSnapshot` + `DomainMemoryProposalBinding`), no efectos
directos. `general.search_knowledge` es read-only y usa el knowledge port o
`DomainMemoryView` autorizado.

## 9. Workflows

Cuatro workflows mediante `DomainWorkflowDefinition`:

| ID | Nombre | Nodos |
|----|--------|-------|
| `general.information_review` | `InformationReview` | LoadResource → SearchKnowledge → ApplyProfile → Reason → DetectGaps → CreateSummary → PrepareQuestions → Validate → ProposeMemory → Complete |
| `general.goal_clarification` | `GoalClarification` | LoadResource → ApplyProfile → Reason → AskQuestion → Pause → Validate → ProposeMemory → Complete |
| `general.decision_support` | `DecisionSupport` | LoadResource → SearchKnowledge → ApplyProfile → Reason → CompareItems → DetectGaps → PrepareQuestions → GenerateReport → Complete |
| `general.periodic_review` | `PeriodicReview` | LoadResource → SearchKnowledge → ApplyProfile → Reason → BuildTimeline → DetectGaps → PrepareQuestions → Validate → ProposeMemory → Complete |

## 10. Permisos

`DomainPermissionPolicy` para `domain:general`:

- **Permitido**: `RESOURCE_READ`, `MEMORY_READ`, `OPERATION_EXECUTE` (para
  operaciones de análisis/preparación/read)
- **Denegado por defecto**: `SEARCH_EXTERNAL`, `MODEL_EXTERNAL`, `MEMORY_WRITE`,
  `FILE_MODIFY`, `SCHEDULE_MODIFY`, `TASK_CREATE`, `COMMUNICATION_EXTERNAL`,
  `SENSITIVE_INFERENCE`, `SENSITIVE_INFERENCE_PERSIST`, `EXPORT`,
  `IRREVERSIBLE_CHANGE`
- **Approval**: `TASK_CREATE`, `GOAL_UPDATE` (para propuestas persistentes)
- **Autonomy limits**: `maximum_autonomy_level=1`, `allow_reversible_changes=False`,
  `allow_irreversible_changes=False`
- **Memory**: `allow_memory_read=True`, `allow_memory_write=False` (solo proposals)

## 11. Presentación

`DomainPresentationPolicy` para General Domain:

- **Detail level**: `standard`
- **Include uncertainty**: `True`
- **Include provenance**: `True`
- **Include alternatives**: `True`
- **Allow speculation**: `False`
- **Require disclaimers**: `True`
- **Required sections**: `summary`, `facts`, `inferences`, `hypotheses`,
  `sources`, `confidence`, `contradictions`, `gaps`, `questions`
- **Protected terms**: `fact`, `inference`, `hypothesis`, `uncertainty`,
  `provenance`, `contradiction`, `gap`, `warning`
- **Warning position**: `before_content`
- **Allowed output types**: `HUMAN_READABLE`, `STRUCTURED`

## 12. Trace

General Domain compone referencias tipadas suministradas por el caller en los
contratos Phase 10.17. No fabrica referencias ausentes: recursos, perfil, reglas,
operaciones, workflows, permisos o approvals aparecen solo cuando el caller las
suministra. Los IDs de resolution context/result y composition son suministrados
por el caller; `DomainTraceAssembler` produce el trace canónico.

El trace es reference-only y no contiene chain of thought, prompts privados,
secretos, credenciales, contenido sensible innecesario ni payloads completos
cuando existe una referencia.

## 13. Memoria

General Domain utiliza exclusivamente la memoria común de Fase 10.18:

- **Lectura**: `DomainMemoryViewRequest` para `domain:general`, con permission
  decisions válidos, filtrado por kinds autorizados, respetando sensitivity,
  temporalidad y provenance. La view se liga al request digest completo.
- **Escritura**: Solo proposals. `general.create_task` y `general.update_goal`
  generan `DomainMemoryProposalSnapshot` + `DomainMemoryProposalBinding` con
  approvals cuando corresponda. No aplican directamente la propuesta.

No se crean `GeneralMemory`, `GeneralMemoryStore`, `GeneralKnowledgeStore` ni
copias persistentes de resources, entities, goals o tasks.

## 14. Resolución y fallback

El resolver existente (`DefaultDomainResolver`) ya soporta fallback declarativo
mediante el parámetro `fallback_domain`. El canonical bootstrap
(`build_standard_general_domain_bootstrap()`) expone un `DefaultDomainResolver`
configurado con `fallback_domain=DomainId(slug="general")`.

Invariantes:

1. Un dominio especializado válido prevalece sobre General Domain.
2. General Domain puede ser primary cuando no existe candidato especializado,
   los recursos son generales, la solicitud es no especializada, el usuario lo
   pide explícitamente, o el resolver necesita fallback seguro.
3. General Domain puede participar como supporting solo cuando aporta recursos
   o capacidades generales reales.
4. No se añade como supporting por defecto a todas las resoluciones.
5. Una puntuación débil de un dominio especializado no se sustituye por falsa
   certeza de General Domain.
6. Una solicitud sensible no se degrada silenciosamente a General Domain.
7. La ausencia o fallo de un dominio especializado no autoriza acciones que ese
   dominio habría prohibido.
8. Un dominio especializado señalizado explícitamente pero inelegible por
   autorización o política debe bloquear el fallback en lugar de degradar
   silenciosamente a General Domain.
9. El fallback queda trazado mediante `fallback_used`, `candidate_scores`,
   `rejected_domains`, `reasons` y `DOMAIN_FALLBACK_SELECTED`.
10. La selección es determinista.
11. Empates o ambigüedad relevante producen conflicto, pregunta o fallback
    prudente, no selección arbitraria.

## 15. Integración con registries y catálogos

General Domain se integra con:

- `DomainRegistry` (definición)
- `InMemoryDomainProfileRegistry` (perfil)
- `InMemoryDomainResourceRegistry` (recursos)
- `InMemoryReasoningRuleRegistry` (reglas)
- `InMemoryDomainOperationRegistry` (operaciones)
- `WorkflowRegistry` (workflows)
- `DomainPermissionRegistry` (permisos)
- `build_initial_permission_catalog` (policy existente)

Se añade un integration builder explícito que registra el dominio completo de
forma atómica. No se crea un mega-registry nuevo.

## 16. Serialización y determinismo

Todos los contratos siguen los estándares auditados de Fase 10.18:

- Frozen dataclasses
- Deep immutability
- Enums exactos
- Sin case normalization implícita
- Sin coerción de str/list/tuple
- Constructor con tuple exacta
- from_dict con list JSON exacta
- Unknown fields rechazados
- JSON-safe
- Finite numbers
- Canonical ordering
- Deterministic digest
- Exact round-trip

## 17. Seguridad y privacidad

- Permiso desconocido → denegar
- Recurso desconocido → rechazar
- Operación desconocida → bloquear
- Workflow desconocido → bloquear
- Rule desconocida → no ejecutar y registrar conflicto
- Temporalidad UNKNOWN → no tratar como actual
- Sensibilidad desconocida → nivel más restrictivo
- Approval desconocida → no ejecutar
- View digest inválido → rechazar
- Proposal binding inválido → rechazar
- Specialized domain ambiguity → no degradar permisos
- External source sin provenance → no confiar
- Output inválido → no completar
- Trace reference desconocida → rechazar
- Partial registration → rollback

## 18. Errores y fail-closed

Se utilizan los errores contractuales existentes de `cmm.domains.errors`.
No se introducen nuevos tipos de error. Los mensajes son sanitizados, sin PII
ni secrets.

## 19. Tests

Tests separados por responsabilidad:

- `test_general_domain_definition.py`
- `test_general_domain_resources.py`
- `test_general_domain_profile.py`
- `test_general_domain_rules.py`
- `test_general_domain_operations.py`
- `test_general_domain_workflows.py`
- `test_general_domain_permissions.py`
- `test_general_domain_presentation.py`
- `test_general_domain_trace.py`
- `test_general_domain_memory.py`
- `test_general_domain_resolution.py`
- `test_general_domain_integration.py`
- `test_general_domain_public_api.py`
- `test_general_domain_audit.py`

## 20. No objetivos

Esta fase no implementa:

- Health Domain, Relationship Domain, University Domain, Opposition Domain,
  Project Domain
- Acceso real a calendarios
- Envío de comunicaciones
- Modificación real de archivos
- Búsquedas externas reales
- Persistencia directa
- Llamadas directas a modelos externos
- Creación autónoma de tareas persistentes
- Modificación autónoma de objetivos
- Decisiones médicas, legales o financieras
- Ejecución arbitraria de herramientas
- UI final
- Cambios en Fase 11