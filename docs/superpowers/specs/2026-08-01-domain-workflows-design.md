# Fase 10.14 — Domain Workflows

## Estado

Diseño aprobado por el usuario el 2026-08-01. No se hará commit, push, merge, rebase ni cambio de rama.

## Objetivo

Añadir workflows de dominio versionados, registrables, validables, resolubles, instanciables y ejecutables sin crear un segundo motor. La infraestructura común será una capa mínima en `cmm.workflows`; `cmm.domains` será una especialización que consume composiciones, perfiles, recursos, permisos y operaciones ya resueltos.

## Contexto real del repositorio

El repositorio no contiene actualmente un `WorkflowEngine` ejecutable ni el paquete `cmm.workflows`. Sí contiene contratos y servicios reutilizables:

| Concepto | Símbolos reales | Propietario |
|---|---|---|
| Planificación de workflows | `AgentWorkflowPlan`, `WorkflowPlannerAdapter` | `cmm.agent_runtime.workflow_planner_*` |
| Ejecución de operaciones | `AgentExecutionAdapter`, `AgentOperationRequest`, `AgentOperationExecutionResult` | `cmm.agent_runtime` |
| Operaciones de dominio | `DomainOperationDefinition`, `DomainOperationOrchestrator` | `cmm.domains` |
| Aprobaciones | `ApprovalRequirement`, `ApprovalRequest`, `ApprovalService` | `cmm.agent_runtime` |
| Checkpoints y transacciones | `Checkpoint`, `TransactionBoundary`, `TransactionManager` | `cmm.agent_runtime` |
| Retry y recovery | `RetryPolicy`, `RecoveryPolicy`, evaluadores existentes | `cmm.agent_runtime` |
| Eventos y trazas | `AgentRuntimeEvent`, contratos de trace | `cmm.agent_runtime` |
| Validación de schemas | `validate_operation_schema` | `cmm.agent_runtime.operation_schema` |
| Composición y perfil | `DomainComposition`, `ResolvedDomainProfile` | `cmm.domains` |
| Recursos y disponibilidad | resolvers y contratos de recursos/operaciones | `cmm.domains` |

Los nombres del roadmap se mapearán a estos símbolos o a los nuevos contratos explícitos de esta fase. No se modificará infraestructura ajena salvo que una prueba demuestre una carencia genérica y reutilizable.

## Límites y ownership

```text
cmm.workflows (agnóstico)
        ↑
cmm.domains (especialización)
        ↑
Domain Operations 10.13
```

`cmm.workflows` no importa `cmm.domains`, perfiles, reglas ni operaciones de dominio. El engine común solo conoce contratos y adapters inyectados. No tendrá persistencia, API, CLI, scheduler, workers, colas, red, subprocess, LLM, ejecución distribuida ni escritura directa de memoria/sesiones.

## Capa común mínima

### Contratos

`cmm.workflows.contracts` define contratos congelados, profundamente inmutables y JSON-safe para:

- `WorkflowDefinition`, `WorkflowNode` y `WorkflowDependency`;
- `WorkflowRun`, `WorkflowNodeResult` y `WorkflowResult`;
- `WorkflowEvent`, `WorkflowCheckpoint` y `WaitRequest`;
- bindings estructurados, `RetryPolicy` y referencias versionadas.

Las definiciones serializables no contienen callables, engines, registries, adapters, managers ni servicios. Los handlers viven exclusivamente detrás de adapters runtime.

### Estados y transiciones

La disponibilidad de una definición y el estado de un run son máquinas separadas. `WorkflowAvailabilityStatus` incluye `available`, `unavailable`, `blocked` y `waiting_for_approval`; `WorkflowRunStatus` incluye `pending`, `running`, `paused`, `waiting_for_resource`, `waiting_for_input`, `waiting_for_approval`, `completed`, `failed`, `cancelled`, `recovering` y `rolled_back`. La transición de runs es pura, explícita y validada. No existen transiciones entre estados de disponibilidad y estados de ejecución.

### Validación del grafo

`cmm.workflows.graph` valida IDs únicos, dependencias existentes y no duplicadas, ausencia de self-dependencies y ciclos accidentales, alcanzabilidad, terminales, bindings estructurales y referencias requeridas por el tipo de nodo. No ejecuta nodos ni resuelve dominios. Los bucles solo se aceptan si existe un contrato común explícito; esta fase no añade soporte de bucles.

### Registry

`cmm.workflows.registry` es un registry in-memory inyectable. Registra definiciones después de validar su forma y grafo interno, admite múltiples versiones SemVer, resuelve la versión activa, habilita/deshabilita, lista de forma determinista y filtra solo por conceptos neutrales: ID, versión, enabled, tipo de nodo, referencia de operación, referencia de subworkflow y metadata/scope genérico. No conoce dominios. `validate_registry()` es una operación explícita posterior que comprueba integridad global y ciclos entre workflows cuando todos los registros previstos están presentes; la resolución comprueba existencia y disponibilidad de referencias. El resultado no depende del orden de registro.

### Engine/orchestrator

`cmm.workflows.engine` coordina únicamente:

```text
definition → run pending → ready nodes → injected node adapter
         → state/checkpoint/event/result update
```

Las dependencias runtime son inyectadas mediante protocolos pequeños: reloj, IDs, ejecución de nodos/operaciones, aprobación, checkpoint, subworkflow y cancelación. El engine resuelve nodos listos sin ejecutar implementaciones directamente, no conoce 10.13 y no duplica gates, transacciones, aprobación o recovery de Agent Runtime.

Pause y wait no bloquean procesos: producen `WaitRequest` y checkpoint estructurado. Resume continúa desde el checkpoint sin repetir nodos completados. Cancel marca explícitamente nodos no iniciados, propaga a subworkflows según política y usa el adapter transaccional disponible. Retry solo representa intentos, errores retryable y backoff; no hace sleep. Recovery exige checkpoint y conserva historial; no implementa scheduling ni replay persistente.

## Especialización de dominio

`cmm.domains.workflow_contracts` define:

- `DomainWorkflowDefinition` con ID, dominio primario, versión, schemas, nodos, dependencias, permisos, recursos, gates, criterios, políticas y metadata;
- `DomainWorkflowContext` con `DomainComposition`, `ResolvedDomainProfile`, permisos efectivos, recursos y capacidades ya resueltos;
- `DomainWorkflowResolution` con nodos disponibles/no disponibles, razones, faltantes, bindings, aprobaciones y trazas estructuradas;
- contexto y provenance de dominio como extensión fina de `WorkflowRun`/`WorkflowResult`; no crea una segunda máquina de estados ni duplica campos de estado comunes;
- criterios de completion declarativos (`all_required_nodes_completed`, schema válido, sin fallos bloqueantes, aprobaciones/recursos resueltos, mínimo de nodos y nodo concreto).

La especialización no recompone dominios, vuelve a resolver perfiles, ejecuta reglas directamente, amplía permisos, persiste runs, escribe memoria ni crea tareas/sesiones reales. `WorkflowRun` y `WorkflowResult` comunes son la fuente de verdad para estado, nodos, checkpoints y resultados.

## Resolución y disponibilidad

`cmm.domains.workflow_resolution` será un servicio puro. Evaluará en orden determinista `enabled`, dominio primario/supporting, operaciones registradas y disponibles, permisos deny-wins, recursos, approvals, validadores, capacidades del engine y compatibilidad de subworkflows. Una operación requerida no disponible bloquea; una opcional puede degradar solo si la política declarada lo permite; una aprobación pendiente es `waiting_for_approval`, no `available`. Los dominios supporting no amplían permisos y todo cross-domain debe ser explícito.

## Ejecución y límites de adapters

`cmm.domains.workflow_execution` traducirá contexto y nodos al engine común. Para `execute_operation` delegará exclusivamente en `DomainOperationOrchestrator`/adapter 10.13; nunca accederá a implementaciones ni reproducirá `AgentExecutionAdapter`. `request_approval`, `validate`, `update_session`, `propose_memory`, `wait_for_resource`, `ask_question` e `invoke_subworkflow` usarán adapters inyectados o producirán resultados estructurados de espera/propuesta. `reason`, `detect_gaps` y `apply_profile` no ejecutarán modelos ni reglas.

Los errores de contrato/programación se propagan; los errores operativos esperados se normalizan en errores tipados y sanitizados. No se capturan `BaseException`, no se publican `str(exc)`/`repr(exc)` y no se convierten fallos desconocidos en éxito.

## Subworkflows y cross-domain

Las referencias de subworkflow incluyen ID y versión. La resolución exige registry común, detecta self-reference/ciclos entre workflows, aplica profundidad máxima configurable, interseca permisos, conserva parent/root run IDs y mapea inputs/outputs. Un fallo requerido bloquea el parent; un fallo opcional se representa según política. La cancelación del parent se propaga a hijos activos.

Los workflows cross-domain declaran dominio primario y supporting domains. La provenance acompaña recursos, operaciones y outputs. Las transferencias requieren autorización explícita existente; esta fase no implementa `CrossDomainPermissionRequest` de 10.15.

## Catálogo inicial

Se registran cuatro definiciones declarativas:

- `health.medical_follow_up`;
- `university.semester_planning`;
- `relationships.timeline_analysis`;
- `project.architecture_review`.

El catálogo demuestra registro, resolución, espera, aprobación, propuestas y resultados estructurados. Los nodos profundos sin adapter quedan `unavailable`, `waiting` o `not_applicable`; no se finge diagnóstico, ejecución de calendario, modificación de código, persistencia de memoria, creación de tareas ni comunicación externa.

## Pruebas

Las pruebas de `tests/workflows` cubren contratos, serialización, grafo, registry, estados y engine común de forma aislada. Las pruebas de `tests/domains` cubren definición/resolución, integración con operaciones 10.13, schemas, approvals, waits, resultados, subworkflows, cross-domain, catálogo y boundaries. La integración end-to-end prueba:

```text
ResolvedDomainProfile + DomainComposition
→ DomainWorkflowResolution
→ DomainWorkflowRun
→ common Workflow Engine
→ Domain Operation adapter 10.13
→ pause/approval/resume
→ validated DomainWorkflowResult
```

Se verificarán imports, Python 3.10, ausencia de efectos prohibidos, Ruff, compileall, `git diff --check` y la suite completa. No se ejecutará `graphify update`.

## Resultado esperado

La fase añade una infraestructura común pequeña y reutilizable, más una especialización de workflows de dominio, sin persistencia ni efectos externos y sin modificar el historial Git.
