# Auditoría técnica de fases 0 a 6

Fecha: 2026-07-22
Repositorio auditado: `/Users/chris/Development/CMM-OS`  
Modo: inspección de código, ejecución de tests y pruebas manuales en directorios temporales. Fases 0, 1 y 2 fueron actualizadas posteriormente con implementación y pruebas.

## 1. Resumen ejecutivo

El cálculo de cumplimiento usa requisitos obligatorios verificados por fase. Un requisito cuenta como cumplido solo si existe implementación conectada y evidencia de prueba o ejecución; los parciales no cuentan como completos.

| Fase | Estado | Cumplimiento | Evidencia principal | Bloqueadores |
| ---- | -----: | -----------: | ------------------- | ------------ |
| Fase 0 - Fundamentos | ✅ Completa | 9/9 = 100% | `kernel/semantic.py:L19-L229`, `kernel/semantic_executors.py:L15-L192`, `kernel/runtime.py:L7-L27`, `tests/test_semantic_kernel.py:L61-L204` | Ninguno para Fase 0. |
| Fase 1 - Semantic Python Engine | ✅ Completa | 15/15 = 100% | `kernel/semantic_executors.py:L96-L264`, `kernel/services/python_transformer.py:L120-L320`, `tests/test_semantic_python_engine.py:L38-L291` | Ninguno para Fase 1. |
| Fase 2 - Autodesarrollo asistido | ✅ Completa | 10/10 = 100% | `cmm/__main__.py:L24-L37`, `cmm/development/service.py:L47-L179`, `tests/test_assisted_development.py:L52-L447` | Ninguno para Fase 2. |
| Fase 3 - Ciclo autónomo de desarrollo | ✅ Completa | 11/11 = 100% | `cmm/development/autonomous.py:L17-L277`, `cmm/development/service.py:L47-L185`, `tests/test_autonomous_development.py:L39-L176` | Ninguno para Fase 3. |
| Fase 4 - Memoria técnica | ✅ Completa | 16/16 = 100% | `cmm/memory/persistence.py:L19-L286`, `cmm/memory/technical_memory.py:L35-L130`, `cmm/runtime/action_runtime.py:L53-L149`, `tests/test_persistent_memory.py`, `tests/test_action_runtime_execution.py` | Ninguno para Fase 4. |
| Fase 5 - Desarrollo autónomo | ✅ Completa | 16/16 = 100% | `cmm/execution/development.py:L20-L287`, `cmm/execution/executors/filesystem.py:L13-L178`, `cmm/execution/executors/python_executor.py:L15-L365`, `cmm/execution/executors/git_executor.py:L14-L190`, `tests/test_phase5_execution.py` | Ninguno para Fase 5. |
| Fase 6 - Transformaciones arquitectónicas | ✅ Completa y auditada | 18/18 = 100% | Infraestructura 6.1-6.5, seis transformaciones E2E de reorganización 6.6 y auditoría independiente final | Ninguno dentro del alcance estático declarado. |

## 2. Entorno y comandos ejecutados

| Comando | Resultado relevante |
| --- | --- |
| `pwd` | `/Users/chris/Development/CMM-OS` |
| `rg --files` | Inventario completo del repo; se identificaron árboles `kernel/*`, `cmm/*`, `cmm_agent/*`, `tests/*`. |
| `pytest -q` | Falló por entorno: `zsh:1: command not found: pytest`. |
| `python -m pytest -q` | Falló por entorno: `zsh:1: command not found: python`. |
| `python3 -m pytest -q` | Falló por entorno: Python 3.14.6 sin módulo `pytest`. |
| `.venv/bin/python -m pytest -q` | `642 passed in 11.04s` tras la auditoría independiente de 6.6/F6-17. |
| `.venv/bin/python -m pytest -q tests/test_phase5_execution.py` | `8 passed`; cubre filesystem, Python semántico, Git, ActionRuntime, rollback, coordinación multiacción e integración Fase 3. |
| `.venv/bin/python -m pytest -q tests/test_assisted_development.py` | `22 passed in 0.20s`. |
| `.venv/bin/python -m pytest -q tests/test_assisted_development.py tests/test_cmm_cli.py tests/test_end_to_end_runner.py tests/test_semantic_kernel.py tests/test_semantic_python_engine.py tests/test_cli.py tests/core/test_kernel.py tests/planner/test_executor.py tests/llm/test_parser.py` | `83 passed in 0.29s`. |
| `.venv/bin/python -m pytest -q tests/test_semantic_kernel.py` | `9 passed in 0.12s`. |
| `.venv/bin/python -m pytest -q tests/test_semantic_python_engine.py tests/test_semantic_kernel.py` | `21 passed in 0.06s`. |
| `.venv/bin/python -m pytest -q tests/test_insert_method.py ... tests/test_edge_cases.py` | `11 passed in 0.43s`. |
| `.venv/bin/python -m pytest -q tests/test_end_to_end_runner.py tests/test_cmm_cli.py tests/test_cli.py` | `14 passed in 0.58s`. |
| `.venv/bin/python -m pytest -q tests/memory tests/planner/test_task_planner.py tests/runtime/test_action_runtime.py tests/execution/test_action_planner.py tests/execution/test_action_executor.py tests/execution/test_executor_registry.py` | `48 passed in 0.42s`. |
| `.venv/bin/python -m pytest -q tests/transformations tests/execution` | `339 passed in 9.96s`; incluye 62 pruebas específicas de contratos y E2E de reorganización, además de regresiones 6.1-6.5. |
| `.venv/bin/python -m pytest -q tests/planner` | `123 passed in 0.61s`. |
| `.venv/bin/python -m cmm doctor` | Falla: CLI oficial solo acepta `{run}`. |
| `.venv/bin/python -m cmm plan "Añade python.replace_method"` | Falla: CLI oficial solo acepta `{run}`. |
| `.venv/bin/python -m cmm run 'replace method hello in class User' --project /private/tmp/...` | Éxito; reemplaza `User.hello` por `pass` en proyecto temporal. |
| `.venv/bin/python -m cmm develop "create class User in app.py" --project /tmp/... --dry-run` | Presenta análisis y plan; no crea archivos. |
| `printf 'n\n' \| .venv/bin/python -m cmm develop "create class User in app.py" --project /tmp/...` | Solicita `¿Aplicar cambios? [y/N]`; rechazo sin modificaciones. |
| `.venv/bin/python -m cmm develop "create class User in app.py" --project /tmp/... --yes` | Crea `app.py`, ejecuta `filesystem.write_file` y `python.create_class`, valida AST/compilación y muestra diff unificado. |
| `.venv/bin/python -m pytest -q tests/test_autonomous_development.py` | `8 passed in 0.24s`. |
| `.venv/bin/python -m cmm develop "create class User in app.py" --project /tmp/... --autonomous --yes --max-attempts 2` | Ejecuta el ciclo autónomo; primer intento correcto, `Attempts: 1/2`, resultado estructurado y diff. |
| Script manual `DevelopmentService` con tres operaciones y fallo en la segunda | Ejecuta dos operaciones, detiene la tercera, aplica rollback y restaura ambos archivos byte a byte. |
| Script manual `Runtime().run` Python en `/tmp` | Confirmó `remove_import`, `add_import`, `rename_method`, `rename_class`, `delete_class` por flujo semántico común con AST final válido. |
| Script manual `TechnicalMemory -> TechnicalReasoner -> TaskPlanner -> ActionPlanner -> NoOpExecutor` | Éxito con repositorio JSON persistente en proyecto temporal; también se conserva compatibilidad in-memory. |
| Script manual `MoveFunctionTransformation` + `ExecutionPipeline` (antes de 6.2) | Copiaba función y fallaba en `update_imports` por parámetros faltantes; corregido y cubierto por E2E real en 6.2. |
| Script manual `MoveClassTransformation` + `ExecutionPipeline` | Crea módulo en ruta incorrecta por `project_root="."`, luego falla al copiar clase. |

## 3. Resultados globales de tests

Suite global ejecutada con `.venv/bin/python -m pytest -q`.

| Total | Aprobados | Fallidos | Omitidos | Duración |
| ---: | ---: | ---: | ---: | ---: |
| 642 | 642 | 0 | 0 | 11.04s |

Fallos relevantes de entorno:

- `pytest -q` no funciona porque `pytest` no está en PATH.
- `python -m pytest -q` no funciona porque `python` no está en PATH.
- `python3 -m pytest -q` no funciona porque el Python global no tiene `pytest`.
- La suite sí funciona con `.venv/bin/python`.

## 4. Auditoría por fase

### Fase 0 - Fundamentos

| ID | Requisito | Estado | Evidencia de código | Evidencia de test | Observaciones |
| -- | --------- | ------ | ------------------- | ----------------- | ------------- |
| F0-01 | Modelo genérico de acciones/operaciones | ✅ Implementado y funcional | `kernel/semantic.py:L19-L87`; adaptadores legacy/transformación en `kernel/semantic_adapters.py:L19-L75` | `tests/test_semantic_kernel.py:L61-L81`; `tests/test_semantic_kernel.py:L179-L189` | `SemanticOperation` aporta tipo, dominio, parámetros, metadatos, id, validación y serialización; los modelos legacy quedan integrados por adaptadores. |
| F0-02 | Contratos semánticos reutilizables | ✅ Implementado y funcional | `kernel/semantic.py:L90-L145`; `kernel/semantic.py:L122-L145` | `tests/test_semantic_kernel.py:L29-L58`; `tests/test_semantic_kernel.py:L107-L125` | `SemanticResult`, `SemanticPlanResult` y `SemanticExecutor` son el contrato común para dominios actuales y futuros. |
| F0-03 | Parser genérico de interpretación | ✅ Implementado y funcional | Parser legacy en `kernel/protocol/parser.py:L14-L79`; adaptación común en `kernel/semantic_adapters.py:L19-L58`; runtime en `kernel/runtime.py:L13-L19` | `tests/test_semantic_kernel.py:L128-L153` | La entrada legacy pasa por parser y se convierte a `SemanticOperation` antes de ejecutar; acciones desconocidas ahora fallan explícitamente. |
| F0-04 | Runtime o sistema de ejecución | ✅ Implementado y funcional | `kernel/semantic.py:L184-L229`; fachada legacy desacoplada en `kernel/runtime.py:L7-L27` | `tests/test_semantic_kernel.py:L94-L125`; `tests/test_semantic_kernel.py:L128-L153` | El runtime valida, resuelve executor, ejecuta y post-valida sin instanciar servicios de dominio. |
| F0-05 | Registro/resolución de executors | ✅ Implementado y funcional | `kernel/semantic.py:L148-L181`; registry por defecto en `kernel/semantic_executors.py:L177-L192` | `tests/test_semantic_kernel.py:L84-L91`; `tests/test_semantic_kernel.py:L192-L204` | Existe un único punto lógico de resolución para el runtime; los registries anteriores pueden coexistir como APIs de compatibilidad. |
| F0-06 | Validación | ✅ Implementado y funcional | Envelope/params en `kernel/semantic.py:L40-L64`; pre/post en `kernel/semantic.py:L190-L198`; validadores de dominio en `kernel/semantic_executors.py:L26-L31`, `L112-L140` | `tests/test_semantic_kernel.py:L80-L81`; `tests/test_semantic_kernel.py:L94-L125` | Cubre operación inválida, parámetros inválidos, executor no encontrado, error de ejecución y validación posterior. |
| F0-07 | Separación kernel/dominios concretos | ✅ Implementado y funcional | `kernel/runtime.py:L7-L27`; dominio Python encapsulado en `kernel/semantic_executors.py:L96-L140`; filesystem/diff/noop/transformación en `kernel/semantic_executors.py:L15-L192` | `tests/test_semantic_kernel.py:L128-L189` | `Runtime` no instancia `PythonEditor`, `FileSystemService`, Git ni transformaciones; solo recibe un `SemanticRuntime`. |
| F0-08 | Reutilización real por Python/filesystem/Git/transformaciones | ✅ Implementado y funcional | `kernel/semantic_executors.py:L15-L192`; `kernel/semantic_adapters.py:L61-L75` | Python E2E `tests/test_semantic_kernel.py:L128-L153`; filesystem `L156-L166`; Git/NoOp `L169-L176`; transformación `L179-L189` | El flujo común queda demostrado en los dominios exigidos sin implementar fases posteriores. |
| F0-09 | Pruebas del kernel | ✅ Implementado y funcional | `tests/test_semantic_kernel.py:L1-L204` | `.venv/bin/python -m pytest -q tests/test_semantic_kernel.py` -> `9 passed in 0.12s`; `.venv/bin/python -m pytest -q` -> `396 passed in 1.25s` | Cobertura añadida para contrato, registry, runtime, errores, validación, compatibilidad legacy y E2E multi-dominio. |

Veredicto técnico de fase 0: el kernel cuenta ahora con una infraestructura común reutilizable de extremo a extremo. La Fase 0 cumple 9/9 requisitos obligatorios y puede cerrarse oficialmente.

### Fase 1 - Semantic Python Engine

| ID | Requisito | Estado | Evidencia de código | Evidencia de test | Observaciones |
| -- | --------- | ------ | ------------------- | ----------------- | ------------- |
| F1-01 | `python.insert_method` | ✅ Implementado y funcional | Parser `kernel/protocol/parser.py:L71-L77`; adapter `kernel/semantic_adapters.py:L43-L55`; executor `kernel/semantic_executors.py:L99-L187`; editor `kernel/services/python_editor.py:L52-L80`; transformer `kernel/services/python_transformer.py:L120-L133` | `tests/test_semantic_python_engine.py:L38-L55`; suite legacy `tests/test_insert_method.py` | Flujo E2E vía `Runtime -> PlanParser -> SemanticOperation -> SemanticRuntime -> PythonSemanticExecutor`; cubre decorador, docstring y staticmethod. |
| F1-02 | `PythonIndex` | ✅ Implementado y funcional | `kernel/services/python_index.py:L6-L96` | `tests/execution/python/test_semantic_context.py`; tests de memoria usan `ProjectIndexer` | Indexa clases, funciones, métodos, imports y usos AST básicos. |
| F1-03 | `PythonLocator` | ✅ Implementado y funcional | `kernel/services/python_locator.py:L11-L31`; qualified lookup `kernel/services/python_locator.py:L31-L71`; duplicate method guard `kernel/services/python_locator.py:L73-L96` | `tests/test_semantic_python_engine.py:L159-L177`; tests legacy `tests/test_insert_method.py`, `tests/test_edge_cases.py` | Resuelve `Outer.Inner` y falla explícitamente ante clases o métodos ambiguos. |
| F1-04 | `PythonEditor` | ✅ Implementado y funcional | Escritura segura y validación pre/post `kernel/services/python_editor.py:L36-L50`; métodos públicos `kernel/services/python_editor.py:L52-L168`, `L170-L219`, `L221-L328` | `tests/test_semantic_python_engine.py:L38-L291`; `tests/test_edge_cases.py:L8-L197` | Valida AST antes de transformar y antes de escribir; si falla no modifica el archivo. |
| F1-05 | `PlanParser` | ✅ Implementado y funcional | Parser de las 9 acciones Python `kernel/protocol/parser.py:L71-L106` | E2E parser/runtime en `tests/test_semantic_python_engine.py:L14-L31`, `L38-L291` | Soporta entrada estructurada legacy usada por CLI/runner para todas las operaciones obligatorias. |
| F1-06 | `Executor` | ✅ Implementado y funcional | `PythonSemanticExecutor.supports/validate/execute` en `kernel/semantic_executors.py:L96-L175`; dispatch completo `L177-L248`; post-validación `L257-L264` | `tests/test_semantic_python_engine.py:L38-L291`; compatibilidad legacy en `tests/test_semantic_kernel.py:L128-L153` | El executor legacy se mantiene por adaptadores; la ejecución normalizada ocurre en el protocolo semántico común. |
| F1-07 | Protocolo semántico | ✅ Implementado y funcional | `SemanticOperation`/`SemanticRuntime` en `kernel/semantic.py`; adapters Python `kernel/semantic_adapters.py:L43-L155`; registry por defecto `kernel/semantic_executors.py:L96-L264` | `tests/test_semantic_python_engine.py:L38-L291`; `tests/test_semantic_kernel.py:L128-L153` | Todas las operaciones `python.*` entran como `SemanticOperation`, se resuelven por registry y devuelven `SemanticResult`. |
| F1-08 | `python.replace_method` | ✅ Implementado y funcional | Parser `kernel/protocol/parser.py:L79-L80`; adapter `kernel/semantic_adapters.py:L56-L68`; executor `kernel/semantic_executors.py:L126-L127`, `L188-L195`; transformer `kernel/services/python_transformer.py:L300-L309` | `tests/test_semantic_python_engine.py:L58-L78`; suite legacy `tests/test_replace_method.py` | Cubre async, classmethod, docstring, símbolo inexistente y AST final válido. |
| F1-09 | `python.delete_method` | ✅ Implementado y funcional | Parser `kernel/protocol/parser.py:L82-L83`; adapter `kernel/semantic_adapters.py:L69-L80`; executor `kernel/semantic_executors.py:L128-L129`, `L196-L202`; transformer `kernel/services/python_transformer.py:L311-L320` | `tests/test_semantic_python_engine.py:L81-L92`; suite legacy `tests/test_delete_method.py` | Elimina método y deja `pass` cuando la clase queda vacía. |
| F1-10 | `python.rename_method` | ✅ Implementado y funcional | Parser `kernel/protocol/parser.py:L85-L86`; adapter `kernel/semantic_adapters.py:L81-L93`; executor `kernel/semantic_executors.py:L130-L131`, `L203-L210`, warning `L250-L255`; transformer `kernel/services/python_transformer.py:L286-L298` | `tests/test_semantic_python_engine.py:L95-L116`, conflictos `L247-L278` | Renombra método, detecta conflictos y devuelve warning estructurado de referencias no actualizadas. |
| F1-11 | `python.add_import` | ✅ Implementado y funcional | Parser `kernel/protocol/parser.py:L88-L89`; adapter `kernel/semantic_adapters.py:L94-L106`; executor `kernel/semantic_executors.py:L132-L133`, `L211-L218`; transformer `kernel/services/python_transformer.py:L197-L243` | `tests/test_semantic_python_engine.py:L119-L136`; suite legacy `tests/test_imports.py` | Operación oficial `python.add_import`; reutiliza `ensure_import`, soporta alias/relativos y es idempotente. |
| F1-12 | `python.remove_import` | ✅ Implementado y funcional | Parser `kernel/protocol/parser.py:L91-L92`; adapter `kernel/semantic_adapters.py:L107-L119`; executor `kernel/semantic_executors.py:L134-L135`, `L219-L226`; transformer `kernel/services/python_transformer.py:L245-L284` | `tests/test_semantic_python_engine.py:L139-L156`; suite legacy `tests/test_imports.py` | Elimina alias individual de `from pkg import A, B` preservando el resto y respeta `ImportFrom.level`. |
| F1-13 | `python.create_class` | ✅ Implementado y funcional | Parser `kernel/protocol/parser.py:L94-L95`; adapter `kernel/semantic_adapters.py:L120-L132`; executor `kernel/semantic_executors.py:L136-L137`, `L227-L234`; transformer `kernel/services/python_transformer.py:L135-L168` | `tests/test_semantic_python_engine.py:L159-L177`; suite legacy `tests/test_create_class.py` | Crea clases top-level o anidadas por `scope`, con bases y métodos, sin duplicar nombres. |
| F1-14 | `python.rename_class` | ✅ Implementado y funcional | Parser `kernel/protocol/parser.py:L97-L98`; adapter `kernel/semantic_adapters.py:L133-L144`; executor `kernel/semantic_executors.py:L138-L139`, `L235-L241`; transformer `kernel/services/python_transformer.py:L177-L186` | `tests/test_semantic_python_engine.py:L180-L202`; conflictos en `L247-L278` | Soporta clases top-level/anidadas, decoradores/docstrings y warning de referencias no actualizadas. |
| F1-15 | `python.delete_class` | ✅ Implementado y funcional | Parser `kernel/protocol/parser.py:L100-L101`; adapter `kernel/semantic_adapters.py:L145-L155`; executor `kernel/semantic_executors.py:L140-L141`, `L242-L247`; transformer `kernel/services/python_transformer.py:L188-L195` | `tests/test_semantic_python_engine.py:L205-L217`; inválidos en `L281-L291` | Elimina clases top-level/anidadas y mantiene el contenedor AST válido. |

Casos borde verificados:

- Decoradores/docstrings/staticmethod/classmethod/async: `tests/test_semantic_python_engine.py:L38-L78`, `L180-L202`.
- Clases anidadas y ámbitos cualificados: `tests/test_semantic_python_engine.py:L159-L177`, `L180-L217`.
- Duplicados, ambigüedad y conflictos de nombres: `tests/test_semantic_python_engine.py:L247-L278`.
- Imports absolutos, relativos, alias, múltiples e idempotencia: `tests/test_semantic_python_engine.py:L119-L156`.
- Archivo sintácticamente inválido y ausencia de escritura parcial: `tests/test_semantic_python_engine.py:L281-L291`.
- Operación desconocida, parámetros inválidos y símbolo inexistente: `tests/test_semantic_python_engine.py:L220-L244`.

Resultado de flujo E2E demostrado:

```text
Entrada estructurada
-> PlanParser
-> acciones legacy adaptadas
-> SemanticOperation
-> SemanticRuntime
-> SemanticExecutorRegistry
-> PythonSemanticExecutor
-> PythonEditor/PythonTransformer
-> escritura
-> validación AST posterior
-> SemanticResult
```

Este flujo está cubierto por al menos un test E2E para cada una de las 9 operaciones obligatorias.

### Fase 2 - Autodesarrollo asistido

| ID | Requisito | Estado | Evidencia de código | Evidencia de test | Observaciones |
| -- | --------- | ------ | ------------------- | ----------------- | ------------- |
| F2-01 | Comando `cmm develop` real | ✅ Implementado y funcional | `cmm/__main__.py:L24-L37`, `L70-L118`; wrapper único `cmm/cli.py:L1-L13` | `tests/test_assisted_development.py:L52-L83`, `L344-L369`; prueba CLI manual | Disponible tanto con `python -m cmm develop` como con el script `cmm`; `run` conserva su ruta previa. |
| F2-02 | Parsing, selección y contención de proyecto | ✅ Implementado y funcional | Opciones CLI `cmm/__main__.py:L24-L37`; validación y resolución segura `cmm/development/service.py:L162-L206` | `tests/test_assisted_development.py:L52-L83`, `L295-L325` | Rechaza proyecto inexistente/no-directorio, paths absolutos, `..` y escapes por symlink; normaliza a rutas bajo el root real. |
| F2-03 | Análisis estructurado del repositorio | ✅ Implementado y funcional | `cmm/development/analyzer.py:L16-L101`; reutiliza `PythonIndex` en `L10`, `L82-L90` | `tests/test_assisted_development.py:L118-L146` | Indexa módulos, clases, métodos, funciones, imports y relaciones de import; excluye entornos/cachés y registra errores sintácticos. |
| F2-04 | Localización y límite de contexto | ✅ Implementado y funcional | Ranking por objetivo y límite en `cmm/development/analyzer.py:L62-L76`, `L95-L101` | `tests/test_assisted_development.py:L139-L146` | No usa candidatos hardcoded; prioriza paths y símbolos coincidentes y aplica `--max-files`. |
| F2-05 | Proveedor configurable y plan estructurado | ✅ Implementado y funcional | Contrato/proveedores `cmm/development/providers.py:L18-L119`; selección `L136-L146`; modelo validado `cmm/development/models.py:L17-L115` | `tests/test_assisted_development.py:L86-L116`, `L149-L159`, `L162-L181` | Proveedor determinístico para tests/automatización y Ollama opcional con import lazy; acepta respuestas JSON de cliente objeto/diccionario; texto libre no estructurado se rechaza. |
| F2-06 | Conversión plan -> acciones semánticas | ✅ Implementado y funcional | `DevelopmentPlan.to_semantic_operations` en `cmm/development/models.py:L117-L145` | `tests/test_assisted_development.py:L86-L95`, `L194-L243` | Convierte por `PlanParser` y adaptadores de Fases 0/1 a `SemanticOperation` reales con orden y metadatos. |
| F2-07 | Ejecución supervisada mediante runtime semántico | ✅ Implementado y funcional | `SemanticRuntime` inyectado en `cmm/development/service.py:L31-L45`; ejecución secuencial `L92-L100` | `tests/test_assisted_development.py:L194-L276` | No llama directamente a `PythonEditor`; detiene el plan en el primer fallo y no implementa reintentos. |
| F2-08 | Validación posterior controlada | ✅ Implementado y funcional | Allowlist y compilación mínima `cmm/development/service.py:L25`, `L212-L218`; AST/compile `L263-L281` | `tests/test_assisted_development.py:L194-L224`, `L279-L292`, `L328-L341` | Valida AST y compilación de Python afectado; rechaza validadores arbitrarios del proveedor y hace rollback al fallar. |
| F2-09 | Presentación, aprobación, dry-run, diff y resultado | ✅ Implementado y funcional | Aprobación/dry-run `cmm/development/service.py:L71-L90`; diff `L283-L301`; resultado `cmm/development/models.py:L168-L210` | `tests/test_assisted_development.py:L162-L224`, `L379-L447`; pruebas CLI manuales | Muestra plan antes de tocar archivos, requiere confirmación salvo `--yes`, dry-run nunca modifica y devuelve diff/resultado serializable. |
| F2-10 | Error, rollback e integración E2E | ✅ Implementado y funcional | Snapshots/restauración `cmm/development/service.py:L92-L179`, `L253-L280`; wrappers legacy `cmm_agent/runtime.py:L1-L13`; Ollama legacy lazy `cmm_agent/provider.py:L1-L30` | `tests/test_assisted_development.py:L239-L360`, `L420-L447`; script manual de rollback; baseline histórico de Fase 2: `420 passed` | E2E filesystem -> Python -> validación -> diff funciona; fallos semánticos, de validación e inesperados restauran archivos y no ejecutan operaciones restantes. |

Veredicto técnico de fase 2: el flujo oficial es supervisado, configurable, contenido en el proyecto y ejecuta planes estructurados mediante el kernel semántico. La Fase 2 cumple 10/10 requisitos obligatorios y puede cerrarse oficialmente.

### Fase 3 - Ciclo autónomo de desarrollo

| ID | Requisito | Estado | Evidencia de código | Evidencia de test | Observaciones |
| -- | --------- | ------ | ------------------- | ----------------- | ------------- |
| F3-01 | Bucle explícito de iteración | ✅ Implementado y funcional | `AutonomousDevelopmentService.develop` `cmm/development/autonomous.py:L157-L239` | `tests/test_autonomous_development.py:L64-L108` | Ejecuta análisis/plan/implementación/validación y vuelve a planificar solo tras fallos recuperables. |
| F3-02 | Límite máximo de intentos | ✅ Implementado y funcional | Parámetro y guardia `cmm/development/autonomous.py:L157-L169`, `L202-L210` | `tests/test_autonomous_development.py:L111-L129`, `L165-L167` | `max_attempts` es obligatorio, debe ser >= 1 y produce parada estructurada `attempt_limit`. |
| F3-03 | Detección estructurada de fallos | ✅ Implementado y funcional | `FailureKind`/`FailureClassification` `cmm/development/autonomous.py:L28-L60`; classifier `L119-L141` | `tests/test_autonomous_development.py:L76-L108`, `L132-L144` | Distingue planificación, ejecución, validación, aprobación humana y límite sin depender de texto libre. |
| F3-04 | Replanificación/corrección | ✅ Implementado y funcional | `CorrectionProvider` `cmm/development/autonomous.py:L37-L46`; hook `L241-L257`; secuencias determinísticas `cmm/development/providers.py:L27-L96` | `tests/test_autonomous_development.py:L76-L108` | Usa corrección explícita cuando el provider la ofrece y, si no, solicita un nuevo plan al provider normal. |
| F3-05 | Nueva validación tras corrección | ✅ Implementado y funcional | Cada intento vuelve a `DevelopmentService` `cmm/development/autonomous.py:L176-L185`; validación F2 `cmm/development/service.py:L121-L155` | `tests/test_autonomous_development.py:L64-L108` | El intento corregido pasa de nuevo por runtime, validación AST/compile y resultado estructurado. |
| F3-06 | Criterio de éxito | ✅ Implementado y funcional | Estados `COMPLETE` y resultado final `cmm/development/autonomous.py:L191-L194`, `L259-L277` | `tests/test_autonomous_development.py:L39-L62` | Solo termina con éxito tras operación aprobada y validaciones exitosas; dry-run se considera éxito de simulación. |
| F3-07 | Criterio de parada/abandono | ✅ Implementado y funcional | Parada por fallo no recuperable, límite o corrección fallida `cmm/development/autonomous.py:L196-L235` | `tests/test_autonomous_development.py:L111-L162` | Expone `stop_reason` y estado `ABANDONED`; el rechazo humano no inicia otra iteración. |
| F3-08 | Estado entre iteraciones | ✅ Implementado y funcional | `AutonomousAttempt` conserva estados, resultado y fallo `cmm/development/autonomous.py:L63-L82`; contexto de corrección `L37-L46` | `tests/test_autonomous_development.py:L76-L108`, `L132-L144` | Cada intento conserva plan, operaciones, validaciones, diff, rollback y clasificación para la siguiente corrección. |
| F3-09 | Protección contra bucles infinitos | ✅ Implementado y funcional | Bucle acotado por `range(1, max_attempts + 1)` `cmm/development/autonomous.py:L176-L202` | `tests/test_autonomous_development.py:L111-L129`, `L132-L144` | No existe camino de iteración ilimitada; el ciclo termina por éxito, abandono o límite. |
| F3-10 | Rollback/aislamiento | ✅ Implementado y funcional | Snapshots/restore reutilizados de Fase 2 `cmm/development/service.py:L96-L138`, `L256-L283`; ciclo por intento `autonomous.py:L176-L185` | `tests/test_autonomous_development.py:L76-L129` | Cada intento fallido restaura el estado anterior antes de permitir el siguiente; el éxito conserva solo el último cambio válido. |
| F3-11 | Tests de éxito, fallo recuperable y fallo definitivo | ✅ Implementado y funcional | Suite específica `tests/test_autonomous_development.py:L39-L176` | `.venv/bin/python -m pytest -q tests/test_autonomous_development.py` -> `8 passed`; suite global -> `428 passed` | Cubre éxito inicial, corrección, hook de corrección, planificación inválida, rechazo, rollback y límite. |

### Fase 4 - Memoria técnica del proyecto

| ID | Requisito | Estado | Evidencia de código | Evidencia de test | Observaciones |
| -- | --------- | ------ | ------------------- | ----------------- | ------------- |
| F4-01 | `TechnicalMemory` | ✅ Implementado y funcional | `cmm/memory/technical_memory.py:L12-L198` | `tests/memory/test_technical_memory.py` | Fachada funcional tras `load()`. |
| F4-02 | `TechnicalReasoner` | ✅ Implementado y funcional | `cmm/memory/technical_reasoner.py:L10-L133` | `tests/memory/test_technical_reasoner.py` | Usa solo la fachada de memoria. |
| F4-03 | `TaskPlanner` | ✅ Implementado y funcional | `cmm/planner/task_planner.py:L33-L192` | `tests/planner/test_task_planner.py` | Plan determinístico basado en reasoner. |
| F4-04 | `ExecutionPlan` | ✅ Implementado y funcional | `cmm/planner/task_planner.py:L21-L30` | `tests/planner/test_task_planner.py:L27-L95` | Modelo de planificación técnica. |
| F4-05 | `ActionPlanner` | ✅ Implementado y funcional | `cmm/execution/action_planner.py:L61-L195` | `tests/execution/test_action_planner.py` | Produce colas no ejecutoras. |
| F4-06 | `ActionRuntime` | ✅ Implementado y funcional | `cmm/runtime/action_runtime.py:L53-L149`, `L151-L226` | `tests/test_action_runtime_execution.py:L24-L74` | Ejecuta la cola mediante registry, conserva historial, detiene ante error y devuelve resultado estructurado. |
| F4-07 | `ExecutorRegistry` | ✅ Implementado y funcional | `cmm/execution/executor_registry.py:L13-L87` | `tests/execution/test_executor_registry.py` | Resuelve por primer executor compatible. |
| F4-08 | `NoOpExecutor` | ✅ Implementado y funcional | `cmm/execution/executors/base.py:L55-L69` | `tests/execution/test_action_executor.py:L50-L56`; prueba manual GOAL -> NoOp | Funciona como fallback. |
| F4-09 | Persistencia/reconstrucción de memoria | ✅ Implementado y funcional | `cmm/memory/persistence.py:L19-L208`, `cmm/memory/results.py:L31-L72` | `tests/test_persistent_memory.py:L20-L92` | JSON versionado, validación de esquema/proyecto, recuperación de corrupción y escritura atómica. |
| F4-10 | Representación de arquitectura | ✅ Implementado y funcional | `cmm/memory/graph.py`; `cmm/memory/models.py` | `tests/knowledge`, `tests/memory` | Grafo de nodos/aristas funcional. |
| F4-11 | Símbolos/módulos/dependencias/relaciones | ✅ Implementado y funcional | `cmm/memory/indexer.py:L39-L191`; `cmm/memory/persistence.py:L219-L274` | `tests/test_persistent_memory.py:L38-L49`, `L129-L142` | Construye y persiste nodos, aristas, símbolos, imports y metadatos. |
| F4-12 | Consultas de impacto | ✅ Implementado y funcional | `cmm/memory/technical_reasoner.py:L74-L99` | `tests/memory/test_technical_reasoner.py:L104-L159` | Impacto directo, no análisis transitivo profundo. |
| F4-13 | Actualización cuando cambia el proyecto | ✅ Implementado y funcional | `cmm/memory/persistence.py:L72-L119`; `cmm/memory/technical_memory.py:L103-L130`; `cmm/memory/results.py:L9-L28` | `tests/test_persistent_memory.py:L94-L127` | `refresh()` detecta creados, modificados, eliminados, renombrados y errores de parseo; reconstruye de forma segura y evita reescrituras sin cambios. |
| F4-14 | Uso real de memoria por reasoner | ✅ Implementado y funcional | `cmm/memory/technical_reasoner.py:L21-L107` | `tests/test_persistent_memory.py:L129-L142` | Tras `refresh()`, el reasoner ve símbolos nuevos y deja de devolver los eliminados. |
| F4-15 | Uso real por planners | ✅ Implementado y funcional | `cmm/planner/task_planner.py:L40-L152` | `tests/test_persistent_memory.py:L129-L142` | Una instancia nueva de planner consume la memoria persistida actualizada. |
| F4-16 | Flujo GOAL -> acción NoOp ejecutada | ✅ Implementado y funcional | `cmm/planner/task_planner.py:L40-L90`; `cmm/execution/action_planner.py:L68-L111`; `cmm/runtime/action_runtime.py:L99-L149`; `cmm/execution/executors/base.py:L67-L69` | `tests/test_action_runtime_execution.py:L76-L93` | Flujo completo con `TechnicalMemory.for_project()` y repositorio JSON persistente. |

### Fase 5 - Desarrollo autónomo

| ID | Requisito | Estado | Evidencia de código | Evidencia de test | Observaciones |
| -- | --------- | ------ | ------------------- | ----------------- | ------------- |
| F5-01 | `CompositeExecutor` | ✅ Implementado y funcional | `cmm/execution/executors/composite_executor.py:L12-L54` | `tests/execution/test_composite_executor.py`; `tests/test_phase5_execution.py:L11-L31` | Despacha filesystem, Python y Git mutadores y read-only por prefijo. |
| F5-02 | `FilesystemExecutor` | ✅ Implementado y funcional | `cmm/execution/executors/filesystem.py:L13-L178` | `tests/test_phase5_execution.py:L24-L37` | Crea, escribe, append, mueve y elimina archivos/directorios; valida rutas, symlinks y escritura atómica. |
| F5-03 | `PythonExecutor` | ✅ Implementado y funcional | `cmm/execution/executors/python_executor.py:L15-L365`; `kernel/semantic.py:L184-L229` | `tests/test_phase5_execution.py:L40-L62` | Las 9 operaciones mutadoras delegan en `SemanticRuntime`, sin duplicar AST. |
| F5-04 | `GitExecutor` | ✅ Implementado y funcional | `cmm/execution/executors/git_executor.py:L14-L190`; `cmm/execution/services/git_service.py:L18-L174` | `tests/execution/test_git_executor.py`; `tests/test_phase5_execution.py:L103-L123` | Status/diff/branch/switch/restore/listado usan argv controlado, cwd contenido y timeout; no hace commit. |
| F5-05 | Registro de executors | ✅ Implementado y funcional | `cmm/execution/executor_registry.py:L57-L91` | `tests/execution/test_read_only_filesystem_executor.py:L159-L163`; `tests/test_phase5_execution.py:L65-L78` | Registry conserva APIs legacy y el composite resuelve mutaciones. |
| F5-06 | Dispatch por tipo de acción | ✅ Implementado y funcional | `cmm/execution/executors/composite_executor.py:L33-L54`; `cmm/execution/action_planner.py:L13-L68` | `tests/execution/test_composite_executor.py`; `tests/test_phase5_execution.py:L40-L62` | Tipos mutadores son explícitos; no se aceptan comandos shell libres. |
| F5-07 | Ejecución secuencial/coordinada | ✅ Implementado y funcional | `cmm/runtime/action_runtime.py:L99-L149`; `cmm/execution/development.py:L51-L115` | `tests/test_phase5_execution.py:L65-L78`, `L82-L101` | ActionRuntime ejecuta en orden, conserva historial, detiene y omite pendientes. |
| F5-08 | Propagación de errores/resultados estructurados | ✅ Implementado y funcional | `cmm/runtime/action_runtime.py:L53-L77`; `cmm/execution/development.py:L268-L287` | `tests/test_phase5_execution.py:L65-L101` | Resultado global incluye acciones planificadas/ejecutadas, errores, rollback, diff y validaciones. |
| F5-09 | Integración con TechnicalMemory/reasoner/planners | ✅ Implementado y funcional | `cmm/execution/development.py:L51-L66`; `cmm/planner/task_planner.py:L33-L90` | `tests/test_phase5_execution.py:L82-L101` | El coordinador carga/refresca memoria y crea TechnicalReasoner, TaskPlanner y ActionPlanner antes de ejecutar. |
| F5-10 | Uso del Semantic Python Engine para modificar | ✅ Implementado y funcional | `cmm/execution/executors/python_executor.py:L72-L122`; `kernel/semantic_executors.py:L96-L264` | `tests/test_phase5_execution.py:L40-L62` | Conversión Action -> SemanticOperation -> SemanticRuntime -> PythonSemanticExecutor verificada para las 9 operaciones. |
| F5-11 | Operaciones reales de filesystem | ✅ Implementado y funcional | `cmm/execution/executors/filesystem.py:L44-L122` | `tests/test_phase5_execution.py:L24-L37`; E2E CLI | Escrituras atómicas, padres controlados, sobrescritura explícita y rollback por snapshots. |
| F5-12 | Operaciones Git reales o seguras | ✅ Implementado y funcional | `cmm/execution/services/git_service.py:L103-L174` | `tests/test_phase5_execution.py:L103-L123` | Git es opcional; en ausencia de Git el coordinador conserva snapshots como mecanismo principal. |
| F5-13 | Branch/aislamiento | ✅ Implementado y funcional | `cmm/execution/development.py:L122-L143`; `cmm/execution/services/git_service.py:L118-L139` | `tests/test_phase5_execution.py:L103-L123` | `--isolate` crea rama controlada; snapshots siguen siendo el rollback independiente. |
| F5-14 | Diff | ✅ Implementado y funcional | `cmm/execution/development.py:L234-L249` | `tests/test_phase5_execution.py:L82-L101`; E2E CLI | Genera diff unificado completo antes/después, incluidos archivos nuevos y eliminados. |
| F5-15 | Validación + iteración | ✅ Implementado y funcional | `cmm/execution/development.py:L88-L119`, `L207-L233`; `cmm/development/autonomous.py:L156-L225` | `tests/test_phase5_execution.py:L82-L101`; `tests/test_autonomous_development.py` | AST/compile y memoria se validan tras cada intento; Fase 3 reutiliza este backend para clasificar, restaurar y replanificar. |
| F5-16 | Resultado para revisión humana | ✅ Implementado y funcional | `cmm/development/models.py:L168-L231`; `cmm/__main__.py:L165-L177` | `tests/test_phase5_execution.py:L82-L101`; E2E CLI `--json` | Incluye diff, validaciones, acciones, rollback, memoria, archivos creados/eliminados y `review_ready`; no hace commit. |

### Fase 6 - Motor de Transformaciones Arquitectónicas

| ID | Requisito | Estado | Evidencia de código | Evidencia de test | Observaciones |
| -- | --------- | ------ | ------------------- | ----------------- | ------------- |
| F6-01 | Abstracción de transformación | ✅ Implementado y funcional | `cmm/transformations/transformation.py:L10-L20` | `tests/transformations/test_architecture.py` | Contrato existe. |
| F6-02 | Representación en grafo/DAG | ✅ Implementado y funcional | `cmm/transformations/graph.py:L13-L158`; `cmm/transformations/models.py:L11-L37` | `tests/transformations/test_phase_6_infrastructure.py:L29-L117` | Valida duplicados, dependencias inexistentes, ciclos y orden topológico determinista. |
| F6-03 | Nodos y dependencias | ✅ Implementado y funcional | `cmm/transformations/models.py:L11-L26`; `cmm/transformations/plan.py:L11-L22` | `tests/transformations/test_phase_6_infrastructure.py:L29-L117` | `TransformationStep` declara dependencias y precondiciones; `TransformationPlan` conserva id/precondiciones globales. |
| F6-04 | Precondiciones | ✅ Implementado y funcional | `cmm/transformations/preconditions.py`; integración en `cmm/execution/execution_pipeline.py` | `tests/transformations/test_phase_6_infrastructure.py`; `tests/execution/test_phase_6_execution_pipeline.py` | Contrato tipado/extensible; soporta archivo, módulo y símbolo; globales antes del snapshot y de cada paso antes de su operación. |
| F6-05 | Planificación | ✅ Implementado y funcional para infraestructura 6.1 | `cmm/transformations/execution_planner.py:L24-L53` | `tests/transformations/test_execution_planner.py`; `tests/execution/test_phase_6_execution_pipeline.py:L80-L82` | Convierte plan validado a `ExecutionPlan` en orden topológico; no implementa todavía objetivos altos nuevos. |
| F6-06 | Ejecución | ✅ Implementado y funcional para infraestructura 6.1 y transformaciones 6.2-6.6 | `cmm/execution/execution_pipeline.py`; transformaciones, precondiciones y executors Python | Tests E2E de transformaciones simbólicas, extracción y reorganización | Ejecuta secuencialmente con registry, analiza impacto antes del snapshot, detiene en primer fallo y aplica rollback. |
| F6-07 | Validación | ✅ Implementado y funcional para infraestructura 6.1 | `cmm/execution/execution_pipeline.py:L138-L156`, `L265-L283`; `cmm/execution/python/validate_project_executor.py:L13-L47` | `tests/execution/test_phase_6_execution_pipeline.py:L219-L234`, `L265-L288` | Validación final sintáctica de archivos Python afectados; falla y activa rollback. |
| F6-08 | Rollback/compensación | ✅ Implementado y funcional para infraestructura 6.1-6.6 | `cmm/execution/execution_pipeline.py` | Tests de pipeline y `test_reorganization_e2e.py` | Snapshot byte a byte e inventario de layout para reorganización; restaura archivos y directorios vacíos, elimina paths inesperados/creados, revalida grafo y memoria, informa errores y no depende de Git. |
| F6-09 | Reutilización de operaciones anteriores | ✅ Implementado y funcional para 6.1-6.6 | Operaciones tipadas, executors LibCST, `ImpactAnalysisPrecondition` y operaciones específicas | Tests unitarios y E2E de transformaciones/impacto/reorganización | Reutiliza pipeline, validación, snapshots, análisis previo y actualización de imports; mantiene operaciones específicas cuando la semántica requiere cambios de layout. |
| F6-10 | Análisis de impacto | ✅ Implementado y funcional | `cmm/transformations/impact_analysis.py`; `ExecutionContext.analyze_impact/validate_post_impact`; `ImpactAnalysisPrecondition`; planner/pipeline/resultados | `tests/transformations/test_impact_analysis.py`; `tests/execution/test_impact_analysis_e2e.py` | Grafo determinista, plan previsto inmutable/serializable, dependencias directas/transitivas, ciclos propuestos, issues tipados, comparación post-transformación y rollback con comprobación del grafo restaurado. `TechnicalMemory` se refresca antes del análisis, tras éxito y sobre el estado restaurado tras rollback. |
| F6-11 | Actualización de imports | ✅ Implementado y funcional en el alcance estático | `update_imports_executor.py`; `update_import_transformer.py`; `reorganization_transformer.py`; `relative_import_resolver.py` | Tests de executor y E2E de 6.2-6.6 | Reescribe imports simples, aliases, multi-símbolo/multilínea y relativos resolubles; recalcula imports internos tras mover módulos/paquetes y divide bindings conservando símbolos no afectados, reexports y `__all__` literal. Wildcards y resolución ambigua bloquean antes de mutar. |
| F6-12 | Resolución de referencias | ✅ Implementado y funcional en el alcance estático | `impact_analysis.py`; `reference_index.py`; `import_resolver.py`; `execution_context.py`; transformer LibCST | Tests unitarios de impacto y E2E cualificados de función/clase | Resuelve y reescribe imports de módulo absolutos/alias y usos cualificados en llamadas, anotaciones, herencia e `isinstance`; detecta shadowing, reflexión y referencias dinámicas como bloqueantes sin tocar strings/comentarios. |
| F6-13 | Detección de ciclos | ✅ Implementado y funcional | `cmm/transformations/graph.py` | `tests/transformations/test_phase_6_infrastructure.py` | Devuelve `GraphValidationError(code="cycle_detected")` con ciclo directo/indirecto, no bloqueo genérico. |
| F6-14 | Orden topológico | ✅ Implementado y funcional | `cmm/transformations/graph.py`; `cmm/transformations/execution_planner.py` | `tests/transformations/test_phase_6_infrastructure.py`; E2E de ejecución | Kahn iterativo determinista con IDs ordenados; no depende de recursión y tolera dependencias compartidas. |
| F6-15 | Resultados estructurados | ✅ Implementado y funcional para infraestructura 6.1 y análisis 6.5-6.6 | `cmm/execution/execution_result.py`; `execution_pipeline.py`; `impact_analysis.py`; `reorganization_impact.py` | Tests de pipeline, impacto y reorganización | Resultado final incluye impacto previsto, issues/discrepancias estructurados, pasos, operaciones, validaciones, rollback y diff de paths/layout. |
| F6-16 | Tests unitarios e integración | ✅ Implementado y funcional para infraestructura 6.1-6.6 | Tests de DAG, precondiciones, executors, pipeline, grafo de impacto y E2E reales | `tests/transformations tests/execution` -> `339 passed`; suite global -> `642 passed` | Incluye 20 pruebas de contratos/análisis y 42 E2E de reorganización para seguridad de paths, side effects, ciclos, imports internos, API pública, memoria y rollback, sin regresiones en hitos anteriores. |
| F6-17 | Transformaciones enumeradas | ✅ Implementado, auditado y funcional | `reorganization.py`; operaciones tipadas; `reorganization_executor.py`; transformers y validadores | `test_reorganization_transformations.py` -> `20 passed`; `test_reorganization_e2e.py` -> `42 passed` | `rename_module`, `move_module`, `split_module`, `merge_modules`, `rename_package` y `move_package` funcionan E2E sobre proyectos reales dentro del alcance estático declarado. |
| F6-18 | Transformación arquitectónica completa validada | ✅ Implementado y funcional | Transformaciones 6.2-6.6, análisis previo y validación post-impacto integrada | Tests E2E reales de 6.2-6.6 | Todas las transformaciones usan planner/pipeline/contexto, validan y hacen rollback estructurado; los casos dinámicos, ambiguos o con side effects se rechazan antes de mutar. |

Veredicto de hito 6.1: puede cerrarse oficialmente. Existe infraestructura integrada y reutilizable para validar DAG, evaluar precondiciones, planificar en orden topológico, propagar `project_root` mediante contexto seguro, ejecutar por registry/executors, hacer rollback no-Git, validar el resultado final y devolver un resultado homogéneo.

Veredicto de hito 6.2: puede cerrarse oficialmente dentro del alcance declarado. `MoveFunctionTransformation` mueve funciones top-level entre módulos existentes, preserva funciones LibCST, actualiza imports `from` simples y alias, elimina el origen, valida el proyecto, informa resultados estructurados y restaura bytes ante fallos intermedios.

Veredicto de hito 6.3: puede cerrarse oficialmente dentro del alcance declarado. `MoveClassTransformation` mueve clases top-level entre módulos existentes, conserva estructura LibCST, actualiza imports simples, alias, herencia y reexports, rechaza dependencias no soportadas antes de mutar, elimina el origen, valida el proyecto y restaura bytes ante fallos intermedios o de validación.

Veredicto de hito 6.4: puede cerrarse oficialmente dentro del alcance declarado. `ExtractMethodTransformation` extrae bloques contiguos soportados con inputs y como máximo una salida, incluyendo métodos async y acceso a `self`; `ExtractModuleTransformation` extrae funciones/clases top-level seleccionadas, conserva dependencias seleccionadas o imports externos seguros, actualiza consumidores/reexports, admite destino nuevo explícito, valida y hace rollback.

Veredicto de hito 6.5: puede cerrarse oficialmente dentro del alcance estático declarado. El análisis genera un plan previsto, reescribe imports relativos/multi-símbolo y referencias cualificadas inequívocas, actualiza reexports y `__all__` literal, usa `TechnicalMemory` como complemento, compara el grafo posterior y activa rollback ante discrepancias. Los casos dinámicos, con shadowing o ambiguos se mantienen como bloqueadores estructurados previos.

Veredicto de hito 6.6/F6-17: puede cerrarse oficialmente dentro del alcance estático declarado. La auditoría independiente confirmó las seis transformaciones por planner/pipeline/executors reales y corrigió orden de inicialización en merge, relocación relativa, API pública, referencias cualificadas residuales, namespaces ambiguos, clasificación de paths y restauración de directorios/paths inesperados.

Veredicto de Fase 6 completa: puede cerrarse oficialmente. Los 18 requisitos están conectados y probados, la auditoría final independiente no deja bloqueadores funcionales y la suite global está verde.

## 5. Pruebas de extremo a extremo

| Escenario | Comando | Resultado esperado | Resultado real | Archivos afectados | Conclusión |
| --- | --- | --- | --- | --- | --- |
| Suite global actual | `.venv/bin/python -m pytest -q` | Tests pasan | `642 passed in 11.04s` | Ningún fuente | Baseline vigente tras la auditoría final de 6.6/F6-17. El valor histórico de 420 corresponde al cierre de Fase 2. |
| Semantic Python Engine completo | `.venv/bin/python -m pytest -q tests/test_semantic_python_engine.py tests/test_semantic_kernel.py` | 9 operaciones Python E2E y kernel semántico pasan | `21 passed in 0.06s` | Archivos temporales de pytest | Demuestra parser -> SemanticOperation -> runtime -> registry -> executor -> editor/transformer -> validación -> SemanticResult. |
| CLI oficial `run` reemplaza método | `.venv/bin/python -m cmm run 'replace method hello in class User' --project /private/tmp/...` | Plan válido, reemplazo semántico, AST válido | Ejecutó `replace_method`, modificó `user.py`, dejó `def hello(self): pass` | `/private/tmp/.../user.py` | Flujo legacy compatible sigue funcionando para replace_method. |
| Fase 2, éxito supervisado | `.venv/bin/python -m cmm develop "create class User in app.py" --project /tmp/... --yes` | Analizar, planificar, ejecutar y validar | Crea módulo, aplica `python.create_class`, valida AST/compile y muestra diff | `/tmp/.../app.py` | E2E oficial completado sin Ollama. |
| Fase 2, dry-run | Mismo comando con `--dry-run` | Presentar sin modificar | Plan visible; ningún archivo creado | Ninguno | Dry-run demostrado. |
| Fase 2, rechazo humano | Mismo comando; entrada `n` | No aplicar | Solicita confirmación y no crea archivos | Ninguno | Supervisión humana demostrada. |
| Fase 2, fallo y rollback | Script temporal con tres operaciones; la segunda busca símbolo inexistente | Detener y restaurar | Ejecuta 2/3, `rollback=True`, ambos archivos coinciden con sus originales | Dos archivos temporales restaurados | Rollback completo demostrado. |
| Fase 2, entrypoint real | `subprocess.run([sys.executable, "-m", "cmm", "develop", ...])` | El CLI oficial debe ejecutar dry-run en un proceso separado | `returncode=0`, resultado de éxito, archivo sin cambios | `/tmp/cmm-f2-e2e.../app.py` | Confirma integración del entrypoint oficial sin depender del estado del proceso de tests. |
| Fase 3, éxito inicial | `.venv/bin/python -m cmm develop "create class User in app.py" --project /tmp/... --autonomous --yes --max-attempts 2` | Ejecutar una tarea válida una vez y terminar | `Result: success`, `Attempts: 1/2`, AST/compile válidos y diff | `/tmp/cmm-f3-cli.../app.py` | El ciclo nominal completo termina con `stop_reason=success`. |
| Fase 3, recuperación | `AutonomousDevelopmentService` con plan fallido seguido de plan corregido | Restaurar primer intento, replanificar, ejecutar y validar de nuevo | `attempts=2`, primer fallo `execution`, segundo `none`, archivo final corregido | Repositorio temporal con `app.py` | Demuestra fallo recuperable y conservación de estado entre iteraciones. |
| Fase 3, fallo definitivo | `AutonomousDevelopmentService` con plan inválido repetido y `max_attempts=2` | Detener sin bucle infinito y conservar estado original | `attempts=2`, último fallo `attempt_limit`, rollback aplicado | Repositorio temporal con `app.py` | Demuestra criterio de abandono y aislamiento. |
| Python semántico manual multi-operación | Script temporal con `Runtime().run` sobre `remove_import`, `add_import`, `rename_method`, `rename_class`, `delete_class` | Todas las acciones pasan por runtime semántico y dejan AST válido | `manual_results [True, True, True, True, True]`; fuente final `from .rel import C`, `from pkg import B`, `class Outer: pass` | `/tmp/.../sample.py` | Confirma manualmente imports múltiples/relativos, ámbito anidado y validación AST. |
| Fase 4, primera construcción y recarga | Script temporal con `TechnicalMemory.for_project()` en dos instancias | Persistir, recargar y conservar entidades/aristas | `first_origin=reconstructed`, `reload_origin=persisted` | `.cmm/memory.json` y `app.py` temporales | Demuestra persistencia real y reconstrucción entre instancias. |
| Fase 4, actualización | Script temporal: crear, modificar, eliminar y renombrar `.py`, después `TechnicalMemory.refresh()` | Detectar cambios, persistir y actualizar consultas | `changed=created/modified/renamed`, `reasoner_updated=True`, símbolo antiguo ausente | Proyecto temporal | Demuestra refresh seguro mediante reconstrucción completa documentada. |
| Fase 4, sin cambios | Dos llamadas consecutivas a `refresh()` | Conjunto vacío y sin escritura innecesaria | `change_set` vacío y `persisted=False` en ambas | Proyecto temporal | Resultado determinista cuando el proyecto no cambia. |
| Fase 4, corrupción | Sobrescribir la memoria JSON con contenido inválido y crear una nueva instancia | Detectar corrupción y reconstruir sin crash opaco | `corrupt_recovery=True`, `origin=reconstructed` | `.cmm/memory.json` temporal | Recuperación estructurada y persistencia posterior verificada. |
| Fase 4, GOAL -> NoOp persistente | `TechnicalMemory -> TechnicalReasoner -> TaskPlanner -> ActionPlanner -> ActionRuntime -> ExecutorRegistry -> NoOpExecutor` | Ejecutar la acción y conservar estados/resultados | `goal_to_noop=True`, todas las acciones `COMPLETED` | Proyecto temporal con memoria JSON | Flujo completo de Fase 4 probado con persistencia real. |
| Fase 4, fallos de runtime | Cola con executor ausente y executor que devuelve error | Detener cola y marcar pendientes como omitidas | `FAILED` seguido de `SKIPPED`, errores estructurados | Acciones temporales | Cubre frontera de error y conservación de historial. |
| Fase 5, crear y modificar | `.venv/bin/python -m cmm develop 'create class User in app.py' --project /tmp/... --autonomous --yes --json` | Crear archivo, crear clase, validar, diff y refrescar memoria | `success=true`, `created_files=["app.py"]`, `memory_refreshed=true`, diff unificado | `app.py` temporal | E2E oficial con filesystem mutador y Python semántico. |
| Fase 5, varias acciones | `AutonomousExecutionService` con plan estructurado filesystem + `python.add_import` + `python.create_class` + `python.insert_method` | Una cola ordenada y un diff final | Acciones `COMPLETED`, AST/compile válidos y `review_ready=true` | Módulo Python temporal | Demuestra coordinación multioperación. |
| Fase 5, fallo y rollback | Plan temporal: primera acción muta y segunda referencia símbolo inexistente | Detener, omitir pendientes y restaurar bytes originales | `rollback_applied=true`, archivo idéntico al snapshot, memoria no refrescada | `app.py` temporal | Rollback no depende de Git. |
| Fase 5, Git aislado | `GitExecutor` sobre repositorio temporal con `git.create_branch`, `git.current_branch`, `git.list_changed_files` | Rama temporal, diff/estado y ningún commit | Rama `cmm-review`, operaciones exitosas, historial sin commit nuevo | Repo Git temporal | Aislamiento Git seguro verificado. |
| Fase 5, sin Git | `AutonomousExecutionService` sobre directorio normal | Ejecutar, validar, generar diff y mantener rollback por snapshots | Éxito y memoria refrescada sin invocar Git | Proyecto temporal | Git no es una dependencia obligatoria. |
| Fase 5, ciclo autónomo real | `AutonomousDevelopmentService(provider, development=AutonomousExecutionService(provider))` | Fallo clasificable, rollback, nuevo plan y validación | El backend mutador comparte la orquestación de Fase 3; no duplica reintentos | Proyecto temporal | Integración F3 -> F5 preparada y compatible. |
| Fase 6.1, infraestructura E2E exitosa | `.venv/bin/python -m pytest -q tests/execution/test_phase_6_execution_pipeline.py::test_e2e_real_successful_dag_with_preconditions` | Proyecto Python temporal, DAG con dependencia, precondición válida, ejecución real `ExecutionPlanner -> ExecutionPipeline -> OperationExecutorRegistry`, validación final | Incluido en la suite actual `339 passed` de transformations/execution; crea `alpha.py` y `pkg/beta.py` | Archivos temporales de `tmp_path` | Demuestra flujo integrado sin mocks para el camino feliz de 6.1. |
| Fase 6.1, rollback E2E byte a byte | `.venv/bin/python -m pytest -q tests/execution/test_phase_6_execution_pipeline.py::test_e2e_real_failure_restores_bytes` | Crear archivo, modificar módulo real, fallar después y restaurar todo byte a byte | Incluido en la suite actual `339 passed`; rollback completo | Archivos temporales de `tmp_path` | Demuestra rollback no-Git de 6.1. |
| Fase 6.1, validación final con rollback | `.venv/bin/python -m pytest -q tests/execution/test_phase_6_execution_pipeline.py::test_final_validation_failure_triggers_rollback` | Una operación escribe Python inválido, la validación falla y dispara rollback | Incluido en la suite actual `339 passed`; rollback y validación restaurada correctos | `broken.py` temporal | Demuestra validación final transaccional. |
| Fase 6.2, move_function exitoso | `.venv/bin/python -m pytest -q tests/execution/test_move_function_e2e.py::test_move_function_simple_e2e_updates_consumer_and_deletes_source` | Mover `foo` entre módulos existentes y actualizar consumidor | Incluido en `test_move_function_e2e.py` -> `16 passed`; fuente, destino, consumidor y `__init__.py` correctos | Paquete Python temporal | E2E real sin mocks desde `MoveFunctionTransformation` hasta executors y validación. |
| Fase 6.2, semántica y alias | `.venv/bin/python -m pytest -q tests/execution/test_move_function_e2e.py::test_move_function_preserves_async_decorator_docstring_and_annotations tests/execution/test_move_function_e2e.py::test_move_function_supports_simple_from_import_alias` | Preservar async/decorador/docstring/anotaciones y alias simple | Incluido en `test_move_function_e2e.py` -> `16 passed`; contenido preservado y alias mantenido | Paquete Python temporal | Alcance soportado verificado. |
| Fase 6.2, consumidores e imports | `.venv/bin/python -m pytest -q tests/execution/test_move_function_e2e.py::test_move_function_updates_multiple_consumers_and_multiline_import` | Actualizar múltiples consumidores e import multilinea | Incluido en `test_move_function_e2e.py` -> `16 passed`; ambos consumidores actualizados | Paquete Python temporal | Reexport en `__init__.py` cubierto por el E2E simple. |
| Fase 6.2, precondiciones y referencias no soportadas | `.venv/bin/python -m pytest -q tests/execution/test_move_function_e2e.py::test_move_function_conflict_fails_before_mutation tests/execution/test_move_function_e2e.py::test_move_function_rejects_unsupported_direct_import_before_mutation tests/execution/test_move_function_e2e.py::test_move_function_rejects_unavailable_global_dependency` | Rechazar conflicto, `import module` ambiguo y global no disponible antes de mutar | Incluido en `test_move_function_e2e.py` -> `16 passed`; errores estructurados y bytes intactos | Paquete Python temporal | Casos inseguros quedan explícitamente fuera del alcance. |
| Fase 6.2, rollback intermedio | `.venv/bin/python -m pytest -q tests/execution/test_move_function_e2e.py::test_move_function_rolls_back_after_real_import_update_failure tests/execution/test_move_function_e2e.py::test_move_function_rolls_back_after_real_delete_failure` | Fallar después de actualización/borrado reales | Incluido en `test_move_function_e2e.py` -> `16 passed`; todos los archivos restaurados byte a byte | Paquete Python temporal | Rollback transaccional de `move_function` verificado. |
| `MoveFunctionTransformation` E2E (evidencia histórica previa a 6.1) | Script temporal `ExecutionPlanner` + `ExecutionPipeline` | Copiar, actualizar imports, borrar fuente, validar | En la auditoría anterior copió función y falló en `update_imports`: `Missing import update parameters` | `/tmp/source.py`, `/tmp/target.py` | Evidencia histórica del defecto posteriormente corregido y cerrado en 6.2. |
| `MoveClassTransformation` E2E (evidencia histórica previa a 6.1) | Script temporal `ExecutionPlanner` + `ExecutionPipeline` | Crear target, copiar clase, actualizar imports, borrar fuente, validar | En la auditoría anterior usó `project_root="."` y falló al copiar clase: `Target module not found` | Se evitó dejar cambios; artefacto accidental limpiado | Evidencia histórica; el hito 6.3 corrige este flujo para destinos existentes con `ExecutionContext` explícito. |
| Fase 6.3, move_class E2E | `.venv/bin/python -m pytest -q tests/execution/test_move_class_e2e.py` | Mover clase simple/compleja, metaclass/keyword, anotaciones, alias, herencia, reexport, conflicto, dependencias no soportadas, homónimos, símbolos duplicados, módulos ausentes, rollback y validación final | `16 passed`; E2E real `MoveClassTransformation -> ExecutionPlanner -> ExecutionPipeline`, sin mocks | Paquetes Python temporales | Hito 6.3 validado dentro del alcance soportado. |
| Fase 6.4, extract_method E2E | `.venv/bin/python -m pytest -q tests/execution/test_extract_method_e2e.py` | Extraer bloques sin salida, con inputs, una salida, async, `self`/`cls`, decoradores, shadowing y validación fallida | `10 passed`; E2E real por planner/pipeline/executor, rollback byte a byte | Paquetes Python temporales | `extract_method` validado en alcance conservador. |
| Fase 6.4, extract_module E2E | `.venv/bin/python -m pytest -q tests/execution/test_extract_module_e2e.py` | Extraer función/clase, dependencias seleccionadas, destino nuevo, consumidores, reexports, conflictos, imports directos rechazados y rollback | `8 passed`; E2E real por planner/pipeline/executor, sin mocks | Paquetes Python temporales | `extract_module` validado en alcance conservador. |
| Fase 6.5, análisis de impacto unitario | `.venv/bin/python -m pytest -q tests/transformations/test_impact_analysis.py` | Grafo/plan determinista y serializable, imports, referencias cualificadas, dependencias, ciclos iterativos, memoria, capacidades y todos los códigos de discrepancia | `23 passed`; análisis real sobre proyectos temporales | Paquetes Python temporales | Cubre contratos, 1.500 módulos sin recursión, casos irrelevantes no bloqueantes, reexports ambiguos y comparación/rollback esperado-real. |
| Fase 6.5, integración E2E | `.venv/bin/python -m pytest -q tests/execution/test_impact_analysis_e2e.py` | Cualificados, colisiones, relativos, API pública, memoria y rollback post-discrepancia | `18 passed`; `Transformation -> ExecutionPlanner -> ExecutionPipeline -> executors -> post-impact`, sin mocks en caminos nominales | Paquetes Python temporales y `.cmm/memory.json` | Demuestra refresh previo/posterior, rollback byte a byte, grafo equivalente y reporte parcial si falla memoria. |
| Fase 6.6, contratos y análisis de reorganización | `.venv/bin/python -m pytest -q tests/transformations/test_reorganization_transformations.py` | Planes/DAG deterministas, metadata completa, códigos de discrepancia y análisis conservador de side effects | `20 passed`; contratos inmutables para las seis transformaciones | ASTs y contratos en memoria | Verifica operaciones, políticas, impacto y rechazo de llamadas, decoradores y operadores ejecutables en inicialización top-level. |
| Fase 6.6, reorganización E2E | `.venv/bin/python -m pytest -q tests/execution/test_reorganization_e2e.py` | Rename/move/split/merge de módulos y rename/move de paquetes, consumidores, relativos, cualificados, reexports, API, memoria y rollback | `42 passed`; proyectos `tmp_path`, executors reales y fault injection solo para validar fallos | Módulos, paquetes, consumidores, `.cmm/memory.json` y archivos no Python temporales | Demuestra las seis transformaciones, dependencias eager, ciclos/colisiones/side effects/path traversal rechazados y restauración byte a byte de archivos, binarios, paths inesperados y directorios vacíos. |

## 6. Hallazgos

### Crítico

1. Transformaciones arquitectónicas no completaban E2E antes del hito 6.3.
   - Evidencia histórica: `MoveClassTransformation` componía `CopySymbolOperation`, pero `PythonCopySymbolExecutor` solo localizaba funciones y el plan intentaba crear destinos existentes.
   - Corrección aplicada: contrato `symbol_kind`, `SymbolLocator`, transformers LibCST genéricos, precondiciones de clase/dependencias y plan integrado en `ExecutionContext`/pipeline.
   - Verificación: `tests/execution/test_move_class_e2e.py` -> `16 passed`; el bloqueador queda resuelto dentro del alcance declarado.

2. La entrega inicial de F6-17 tenía divergencias semánticas y de aislamiento no cubiertas por sus 31 E2E.
   - Hallazgos reproducidos: merge con base definida después del consumidor (`NameError` al importar), import relativo conservado con destino semántico incorrecto, referencia cualificada obsoleta no detectada, namespace convertido implícitamente, origen eliminado clasificado como modificado y rollback que perdía directorios vacíos.
   - Corrección aplicada: orden topológico de dependencias eager, relocación relativa conservadora, grafo de referencias completo, API/layout esperados, inventario transaccional, resultados de paths correctos y side-effect analyzer reforzado.
   - Verificación: `test_reorganization_transformations.py` -> `20 passed`; `test_reorganization_e2e.py` -> `42 passed`; diez escenarios manuales independientes; suite global `642 passed`.

### Medio

3. El kernel está duplicado y fragmentado.
   - Evidencia: modelos separados en `kernel/actions/base.py:L4-L8`, `kernel/planner/operations.py:L18-L130`, `cmm/transformations/operation.py:L8-L16`.
   - Impacto: capacidades añadidas en una capa no quedan disponibles en otras.
   - Fase afectada: 0.
   - Corrección mínima: definir un contrato común o adaptadores oficiales con cobertura E2E entre capas.

### Bajo

4. `ast.unparse` limita preservación de formato.
   - Evidencia: `PythonEditor._apply_transform` escribe `ast.unparse(tree)` en `kernel/services/python_editor.py:L36-L47`.
   - Impacto: puede reformatar agresivamente el archivo.
   - Fase afectada: 1.
   - Corrección mínima: aceptar esta limitación explícitamente o migrar operaciones sensibles a CST.

## 7. Contradicciones

| Documentado | Implementado | Probado |
| --- | --- | --- |
| README afirma fases 1 a 5 completadas en `README.md:L97-L105`. | Fases 0 a 6 tienen flujo funcional probado tras la auditoría final. | `cmm develop --autonomous` usa `AutonomousExecutionService`; las suites por fase y transformaciones permanecen verdes. |
| README describe `Execution Runtime -> CompositeExecutor -> ReadOnlyFilesystemExecutor/PythonExecutor/GitExecutor` en `README.md:L9-L29`. | `ActionRuntime` ejecuta colas mediante `ExecutorRegistry`: `cmm/runtime/action_runtime.py:L99-L149`; la frontera persistente de Fase 4 usa `NoOpExecutor`. | `tests/test_action_runtime_execution.py:L24-L93` cubre éxito, executor ausente, error y flujo GOAL -> NoOp persistente. |
| Roadmap afirma Fase 1 completada con import management y validation en `docs/roadmap.md:L3-L14`. | Tras el cierre, las 9 operaciones requeridas están registradas en parser/adapters/executor y cubiertas por tests E2E. | `.venv/bin/python -m pytest -q tests/test_semantic_python_engine.py tests/test_semantic_kernel.py` -> `21 passed in 0.06s`; suite global `396 passed in 1.25s`. |
| README habla de “structured, validated, and testable execution flows” en `README.md:L3-L5`. | Fases 2 y 3 implementan planes/resultados estructurados, aprobación, runtime semántico, validación, diff, rollback y ciclo acotado. | `tests/test_assisted_development.py` y `tests/test_autonomous_development.py`; E2E manual de éxito, recuperación, rechazo y límite. |
| README marca Phase 5 - Execution Layer completada en `README.md:L101-L105`. | La implementación actual añade mutaciones seguras, validación, diff, snapshots y backend para F3. | `tests/test_phase5_execution.py` y E2E CLI verifican creación/modificación/rollback sin commit automático. |
| README dice que Phase 6 será el siguiente milestone en `README.md:L111-L117`. | Los 18 requisitos funcionales de Fase 6 están implementados y auditados, incluida reorganización de módulos/paquetes. | `339 passed` en transformations/execution y `642 passed` globales; la documentación general queda como actualización futura no bloqueante. |

## 8. Veredicto final

Fase 0: ¿Puede darse oficialmente por cerrada? Sí.  
Existe `SemanticOperation` como contrato común, `SemanticExecutor`/`SemanticResult` como contrato de ejecución, `SemanticExecutorRegistry` como punto lógico único y `SemanticRuntime` desacoplado de dominios. Hay adaptadores legacy y pruebas E2E multi-dominio.

Fase 1: ¿Puede darse oficialmente por cerrada? Sí.  
Las 9 operaciones obligatorias entran por `PlanParser`, se adaptan a `SemanticOperation`, se resuelven por `SemanticExecutorRegistry`, ejecutan `PythonSemanticExecutor` y validan AST antes/después. Hay tests E2E por operación y la suite global está verde.

Fase 2: ¿Puede darse oficialmente por cerrada? Sí.  
`python -m cmm develop` analiza el proyecto, obtiene un plan estructurado de un provider intercambiable, exige aprobación, ejecuta por `SemanticRuntime`, valida, genera diff y restaura snapshots ante fallos. Dry-run, rechazo, éxito y rollback están cubiertos E2E.

Fase 3: ¿Puede darse oficialmente por cerrada? Sí.  
Existe un ciclo acotado que reutiliza `DevelopmentService`, clasifica fallos, genera correcciones o nuevos planes, restaura cada intento fallido, vuelve a validar y expone éxito o abandono estructurado. Los tests cubren éxito, recuperación y fallo definitivo.

Fase 4: ¿Puede darse oficialmente por cerrada? Sí.  
Existe persistencia JSON versionada y atómica, carga/reconstrucción, detección de cambios, `refresh()` determinista, reasoner/planners sobre estado actualizado y ejecución real de colas mediante registry y `NoOpExecutor`. El flujo GOAL -> NoOp está probado E2E con memoria persistente.

Fase 5: ¿Puede darse oficialmente por cerrada? Sí.  
Existe coordinación real desde memoria/reasoner/planners hasta `ActionRuntime`, con executors mutadores filesystem/Python/Git, SemanticRuntime para Python, validación AST/compile, diff, snapshots, rollback y resultado para revisión. Git es opcional y Fase 3 reutiliza este backend.

Fase 6: ¿Puede darse oficialmente por cerrada? Sí.
Los 18 requisitos funcionales están implementados, conectados y auditados. Las seis transformaciones de reorganización tienen E2E reales, impacto previsto/posterior, memoria y rollback; los casos dinámicos, ambiguos, namespace o con side effects quedan rechazados explícitamente como límite estático.

Fases que pueden cerrarse oficialmente: Fase 0, Fase 1, Fase 2, Fase 3, Fase 4, Fase 5 y Fase 6.

## 9. Plan mínimo de cierre

### Fase 0

Fase cerrada. No quedan tareas imprescindibles de Fase 0.

### Fase 1

Fase cerrada. No quedan tareas imprescindibles de Fase 1.

### Fase 2

Fase cerrada. No quedan tareas imprescindibles de Fase 2.

### Fase 3

Fase cerrada. No quedan tareas imprescindibles de Fase 3.

### Fase 4

Fase cerrada. No quedan tareas imprescindibles de Fase 4.

### Fase 5

Fase cerrada. No quedan tareas imprescindibles de Fase 5.

### Fase 6

Fase cerrada. No quedan tareas imprescindibles de Fase 6. La resolución dinámica/reflexiva, namespace packages ambiguos, ejecución de código top-level y preservación explícita de permisos quedan fuera del contrato estático y son trabajo futuro no bloqueante.
