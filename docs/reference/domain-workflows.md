# Domain Workflows (Fase 10.14)

La infraestructura común vive en `cmm.workflows` y es agnóstica a dominios. Define contratos inmutables, valida grafos DAG, mantiene un registry in-memory versionado y coordina un lifecycle mínimo mediante adapters inyectados.

La disponibilidad de una definición usa `WorkflowAvailabilityStatus`; el estado de una ejecución usa `WorkflowRunStatus`. No se mezclan ambas máquinas. `WorkflowRun` es la fuente de verdad para estado, nodos completados, outputs y checkpoints.

`InMemoryWorkflowRegistry` valida la forma del grafo al registrar, admite versiones SemVer y no ejecuta handlers. Las referencias a otros workflows pueden registrarse antes de que exista el destino. `validate_registry()` hace la comprobación global de ciclos de subworkflows cuando el conjunto está completo; la resolución comprueba disponibilidad de referencias.

`WorkflowEngine` solo coordina. Ejecuta nodos mediante un adapter, nunca conoce operaciones de dominio y no persiste estado. `pause`, `resume`, `cancel` y `recover` producen nuevas instancias inmutables. Waiting y backoff se representan como estado/contrato; no bloquean ni hacen scheduling.

Al reanudar, el executor rehidrata el resultado de ejecución previo: conserva resultados por nodo, eventos ordenados, intentos, outputs y jerarquía parent/root/depth; los nodos ya completados no se repiten. Un fallo de nodo opcional se normaliza siempre como `SKIPPED`, con el código operativo original en `reason_code`. Por ello no entra en `failed_nodes`, no bloquea `no_blocking_failures` y puede resolver dependencias; un `SKIPPED` nunca cuenta como nodo completado para criterios de completion. Un fallo o skip de nodo requerido permanece bloqueante.

`cmm.domains` añade `DomainWorkflowDefinition`, `DomainWorkflowContext`, resolución de permisos/recursos y provenance. El registry de dominio filtra por dominio fuera de la capa común. La resolución aplica deny-wins y no recompone perfiles ni amplía permisos. La ejecución de operaciones debe entrar por la infraestructura de Domain Operations 10.13 a través de un adapter inyectado.

El catálogo inicial contiene:

- `health.medical_follow_up`
- `university.semester_planning`
- `relationships.timeline_analysis`
- `project.architecture_review`

Son definiciones conservadoras. Sin adapters de capacidad, los nodos profundos no se presentan como éxito real; se representan como no aplicables, no disponibles o esperando. No hay persistencia, API, CLI, scheduler, workers, colas, red, subprocess, LLM, escritura de memoria, creación de tareas, cambios de calendario ni modificación de código.
