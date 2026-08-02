# Preflight de reconciliación — prompts reales vs. Fases 10.11–10.15

**Fecha:** 2 de agosto de 2026
**Corpus:** 15 prompts actuales de Claude
**Objetivo:** determinar si las fases cerradas 10.11–10.14 requieren reapertura y convertir los prompts reales en requisitos verificables para 10.15 — Domain Permissions.

**Estado de cierre:** requisitos P-01–P-10 incorporados en 10.15; fase cerrada y
suite global verde el 2 de agosto de 2026. Este documento se conserva como
trazabilidad del preflight, no como lista de bloqueos vigente.

## 1. Veredicto

1. **No hay que revertir ni reimplementar 10.11–10.14.**
2. **Sí faltó usar los prompts antes como corpus de requisitos y pruebas de aceptación.**
3. La infraestructura cerrada es deliberadamente genérica y declarativa; los prompts aportan principalmente configuración concreta y casos de prueba.
4. **10.15 debía detenerse antes del cierre** hasta incorporar los requisitos de permisos identificados en este documento; esa condición ya está satisfecha.
5. Los deltas no relativos a permisos se asignan a 10.16–10.18 y a los Domain Packs 10.19–10.30.

## 2. Inventario y destino

| Prompt | Dominio CMM OS | Destino principal | Observación |
|---|---|---|---|
| Instrucciones generales Claude | política global | 10.15–10.18 / Phase 11 | Mezcla interacción, documentos y PII literal |
| Cuestiones generales | `domain:general` | 10.19 | Respuesta directa salvo laguna material |
| Salud | `domain:health` | 10.20 | Alto riesgo, Notion, documentos, límites clínicos |
| Neurodivergencia y Salud Mental | `domain:health` | 10.20 | Reglas epistemológicas y temporales profundas |
| Organización clínica Notion | `domain:health` | 10.20 + workflows | Mutaciones persistentes y preservación histórica |
| Relaciones Personales | `domain:relationships` | 10.21 | Inferencias psicológicas sensibles como hipótesis |
| Universidad | `domain:university` | 10.22 | Calendario, documentos, normativa y carga cognitiva |
| Oposiciones | `domain:oppositions` | 10.23 | Verificación oficial obligatoria y estrategia bloqueada |
| Reflexiones | `domain:reflection` | 10.24 | Alta sensibilidad, sin decisiones automáticas |
| Intereses | `domain:reflection` | 10.24 | Lectura de Notion/historial; escritura confirmada |
| Idiomas | `domain:languages` | 10.26 | Seguimiento de progreso con consentimiento |
| Paternidad (Nil) | `domain:nil` | 10.27 | Legal, médico y financiero de alto riesgo |
| Deporte | `domain:sport` | 10.28 | Importación restringida de condicionantes de salud |
| Futuro | `domain:life-plan` | 10.29 | Coordinación multidominio explícita |
| Formación | `domain:general` + overlay instructivo | 10.19 / 10.16 | No justifica un dominio nuevo ahora |

**No crear ahora dominios `formation` o `interests`.** Formación es un modo de interacción/seguimiento sobre General; Intereses es una especialización de Reflection.

## 3. Reconciliación por fase cerrada

### 10.11 — Domain Profiles

**Estado:** no reabrir contrato.

Los prompts confirman que hacen falta perfiles con:

- profundidad variable;
- política de preguntas;
- inferencias permitidas/prohibidas;
- memoria;
- temporalidad;
- presentación;
- producción;
- acciones prohibidas;
- overlays por workflow, operación, riesgo y petición explícita.

Todo ello ya pertenece al diseño de `DomainProfileDefinition` y a la composición monotónica.

**Ajustes futuros de configuración, no de infraestructura:**

- No convertir «preguntar siempre» en regla global obligatoria. Es incompatible con General y Formación.
- Normalizarlo como: preguntar solo ante laguna material, ambigüedad relevante o decisión que requiera al usuario.
- Permitir cambio de modo `socratic → directive` mediante overlay de workflow/operación en Formación.
- Mantener estilos distintos para Reflexión, Relaciones, Universidad y General.

### 10.12 — Domain Rules

**Estado:** no reabrir motor ni contratos.

La fase implementó la infraestructura común y dejó deliberadamente las reglas profundas para los Domain Packs. Los prompts añaden reglas concretas, no otra clase de motor.

**Deltas a registrar para los packs posteriores:**

- `health.temporal_series_completeness` — RD-6: igualdad del valor actual no demuestra igualdad de cronología.
- `health.source_authority_by_attribute` — autoridad según atributo/finalidad, no jerarquía global Notion > documento > memoria.
- `relationships.origin_hypothesis_evidence` — origen psicológico solo como hipótesis respaldada.
- `global.question_necessity` — preguntar solo si la laguna cambia materialmente la respuesta.
- `life_plan.closed_decision_reopening` — una decisión cerrada no se reabre sin nueva evidencia explícita.
- `global.mutable_prompt_state_rejection` — calendarios, medicación, cifras y decisiones no se tratan como reglas estables.

Estas reglas deben implementarse en 10.19–10.30 o como backport aditivo específico; no requieren reescribir 10.12.

### 10.13 — Domain Operations

**Estado:** no reabrir contrato.

Los prompts exigen operaciones que ya encajan en las categorías implementadas:

- lectura: Notion, historial, archivo, fuente oficial;
- análisis: comparación, cronología, detección de contradicciones;
- preparación: documentos, preguntas, planes;
- memoria: proponer o aplicar cambios autorizados;
- planificación: calendario, hitos, estudio, entrenamiento;
- externa: Notion, calendario, correo, web;
- sensible: salud, legal, financiero, relaciones;
- destructiva: borrar, sustituir o modificar irreversiblemente.

**Regla operativa necesaria:** separar siempre `propose` de `apply` y `apply` de `verify`.

Ejemplos:

```text
propose_memory_update → approve → apply_memory_update → verify_memory_update
prepare_email → approve → send_email → verify_delivery
read_notion → propose_notion_patch → approve → update_notion → refetch_and_verify
```

### 10.14 — Domain Workflows

**Estado:** no reabrir contrato.

Los nodos actuales cubren todos los flujos observados: carga, búsqueda, razonamiento, preguntas, espera, operación, validación, aprobación, sesión, propuesta de memoria, resultado, pausa y escalado.

La propia 10.14 dejó las autorizaciones cross-domain para 10.15. Por tanto, los prompts llegan a tiempo para definirlas.

**Workflows futuros derivados del corpus:**

- `health.clinical_notion_update`;
- `health.consultation_preparation`;
- `oppositions.official_call_verification`;
- `university.priority_and_workload_review`;
- `reflection.interest_map_review`;
- `languages.progress_checkpoint`;
- `nil.legal_financial_verification`;
- `sport.return_to_training_with_health_constraints`;
- `life_plan.cross_domain_impact_review`.

Se implementarán en los packs concretos; no bloquean el motor 10.14.

## 4. Requisitos bloqueantes para 10.15

### P-01 — Permisos por efecto, no solo por operación

Distinguir explícitamente:

```text
READ
ANALYZE
INFER
PROPOSE
MUTATE
EXPORT
COMMUNICATE
DELETE
```

Una autorización para leer Notion no autoriza a actualizarlo. Una autorización para generar una inferencia no autoriza a persistirla ni exportarla.

### P-02 — Aprobaciones tipadas y acotadas

`approval_requirements` debe poder expresar como mínimo:

- operación o patrón de operaciones;
- clase de efecto;
- dominio fuente y destino;
- tipos de recurso;
- sensibilidad;
- ámbito: `one_shot | workflow | session | persistent_grant`;
- expiración;
- razón;
- si admite modificación por el usuario;
- si exige reverificación posterior.

La aprobación nunca debe convertirse silenciosamente en permiso permanente.

### P-03 — Memoria: leer, proponer y escribir son permisos distintos

Necesidades del corpus:

- leer progreso o contexto previo;
- proponer una actualización;
- persistir un hecho estable;
- persistir una inferencia sensible;
- invalidar o corregir una entrada;
- borrar una entrada.

`allow_memory_write` por sí solo es demasiado grueso si no se combina con operaciones y aprobaciones tipadas.

### P-04 — Inferencia sensible separada de persistencia y transferencia

Relaciones, Reflexión, Intereses, Salud Mental y Life Plan permiten algunas inferencias sensibles como hipótesis de trabajo, pero:

- no deben presentarse como hechos;
- no deben diagnosticar a terceros;
- no deben cruzar de dominio automáticamente;
- no deben persistirse sin confirmación;
- no deben exportarse a documentos sin autorización específica.

### P-05 — Cross-domain granular

No basta `allowed_target_domains`.

La autorización debe poder limitar:

- recursos concretos o tipos de recurso;
- claims o campos permitidos;
- operaciones;
- propósito;
- duración;
- sensibilidad máxima;
- posibilidad de persistencia/exportación.

Ejemplo: Sport puede recibir de Health únicamente `health_constraint` vigente y autorizado, no el expediente clínico completo.

### P-06 — Búsqueda externa con clase de fuente

Los prompts de Oposiciones y Nil requieren verificación actualizada, pero no cualquier web.

La política debe soportar:

```text
OFFICIAL_ONLY
PRIMARY_SOURCES
TRUSTED_SECONDARY
GENERAL_WEB
DENIED
```

Y registrar qué clase se exigió y cuál se usó.

### P-07 — Modelos externos y salida de datos

`allow_external_models` debe combinarse con:

- sensibilidad máxima exportable;
- dominios permitidos;
- perfil de ejecución;
- redacción/tokenización previa;
- consentimiento cuando proceda;
- prohibición por defecto en Salud, Relaciones, Reflexión y Nil.

Un permiso para usar un proveedor remoto no equivale a permiso para enviarle cualquier contexto.

### P-08 — Mutaciones externas verificadas

Notion, calendario, tareas, objetivos, archivos y comunicaciones requieren:

1. propuesta exacta;
2. aprobación;
3. ejecución transaccional/reversible cuando sea posible;
4. lectura posterior o verificación;
5. traza del resultado.

### P-09 — Exportación e identificadores

Los prompts contienen identificadores personales literales. No deben residir en los Domain Packs ni propagarse a proveedores.

La política debe resolverlos mediante un almacén seguro y aplicar:

- destinatario;
- propósito;
- identificadores permitidos;
- redacción de los no permitidos;
- confirmación para documentos externos;
- prohibición de reutilizar identificadores clínicos o de póliza fuera del original.

### P-10 — Decisiones de alto impacto

Aprobación humana obligatoria para:

- decisiones médicas, legales o financieras;
- pagos y contratos;
- contacto con agencias o profesionales;
- solicitudes, matrículas o inscripciones;
- modificación de estrategia vital;
- abandono de objetivos;
- comunicación a terceros;
- publicación.

El sistema puede analizar, comparar y preparar; no puede cerrar esas decisiones por inferencia.

## 5. Baseline de permisos derivado de los prompts

| Dominio | Memoria | Búsqueda externa | Modelos externos | Cross-domain | Inferencia sensible | Mutaciones / comunicaciones |
|---|---|---|---|---|---|---|
| General | lectura; escritura confirmada | condicional | local/default; remoto según política | no por defecto | no | aprobación |
| Health | lectura; propuesta; escritura confirmada | primaria/oficial cuando sea necesaria | denegado por defecto | restringido | limitada; persistencia confirmada | ninguna decisión clínica; Notion con aprobación |
| Relationships | lectura controlada; escritura confirmada | no por defecto | denegado | Reflection solo con scope | hipótesis limitadas; no diagnóstico tercero | sin contacto automático |
| University | lectura; escritura confirmada | oficial para normas/plazos | según política no sensible | Life Plan/Oppositions/Health constraints | baja | calendario/email/archivo con aprobación |
| Oppositions | lectura; escritura confirmada | oficial obligatoria para datos cambiantes | según política | University/Life Plan | baja | inscripción, calendario y comunicaciones con aprobación |
| Reflection | lectura controlada; escritura confirmada | no por defecto | denegado | Relationships/Concerns con scope | limitada y visible | ninguna decisión automática |
| Concerns | lectura controlada; escritura temporal confirmada | solo si resuelve riesgo real | denegado | Health/Reflection con scope | limitada | sin acciones externas automáticas |
| Languages | progreso con opt-in; corrección permitida | opcional | según política baja sensibilidad | no por defecto | no | calendario con aprobación |
| Nil | lectura; escritura confirmada reforzada | oficial/primaria obligatoria | denegado por defecto | Life Plan/Health/University/finance con scope | limitada | sin pago, contrato ni contacto; aprobación total |
| Sport | lectura; progreso con confirmación | condicional | según política | Health constraints únicamente | no clínica | calendario con aprobación; no tratamiento |
| Life Plan | lectura multi-domain autorizada; escritura reforzada | condicional | denegado para contexto sensible por defecto | explícito y granular | limitada | decisiones y compromisos siempre confirmados |
| Project | lectura repo; escritura según autonomía | documentación técnica | perfil aislado | no datos personales por defecto | no personal | cambios reversibles; commit/publicación con aprobación |

## 6. Conflictos de prompts que 10.15 debe resolver de forma segura

### C-01 — «Preguntar siempre» vs. responder directamente

No es un conflicto de permisos. Se resuelve en perfiles/presentación: preguntar solo si existe laguna material. No tratar la preferencia antigua como restricción global inmutable.

### C-02 — Notion automático vs. confirmación

Salud y organización clínica ordenan actualizaciones automáticas; Intereses exige confirmación. La política efectiva debe usar el criterio más restrictivo:

```text
lectura permitida → propuesta automática permitida → mutación requiere aprobación
```

Puede existir un grant persistente revocable, pero nunca se infiere del prompt.

### C-03 — «Notion como fuente única»

No es permiso, sino autoridad. Notion puede ser registro consolidado; el archivo original conserva autoridad sobre su contenido y la fuente oficial sobre normativa vigente.

### C-04 — Datos mutables dentro del prompt

Fechas, medicación, planes, convocatorias, precios, salarios, diagnósticos y decisiones pasan a claims temporales. No conceden permisos y no deben quedar congelados en el Domain Pack.

### C-05 — PII literal en instrucciones

Se extrae a secrets/profile store. El prompt o pack conserva únicamente referencias declarativas a una política de identificadores.

## 7. Pruebas de aceptación obligatorias de 10.15

1. **Health Notion write:** leer permitido; proponer parche permitido; aplicar sin aprobación denegado.
2. **Interests write:** conclusión consolidada puede generar propuesta; escritura sin confirmación denegada.
3. **Sport → Health:** se concede solo `health_constraint`; pedir informe completo queda denegado.
4. **Life Plan multi-domain:** crea `CrossDomainPermissionRequest`; no importa datos sensibles antes de aprobación.
5. **Relationships inference:** puede producir hipótesis etiquetada; persistirla o exportarla exige aprobación.
6. **Nil official search:** búsqueda oficial permitida; contacto con agencia, contrato o pago denegado.
7. **Oppositions source class:** una cifra cambiante no puede validarse con `GENERAL_WEB` cuando la política exige `OFFICIAL_ONLY`.
8. **University calendar:** plan generado sin aprobación; modificación de calendario espera aprobación.
9. **Languages memory opt-in:** sin grant no persiste evaluación/progreso; con grant acotado sí.
10. **External model egress:** permiso de modelo remoto + recurso sensible denegado por intersección.
11. **Export PII:** documento elimina identificadores no autorizados aunque estén presentes en la fuente derivada.
12. **Approval scope:** una aprobación `one_shot` no autoriza una segunda mutación.
13. **Approval expiry:** un grant expirado vuelve a denegar.
14. **Deny wins:** supporting domain no amplía permiso del primario.
15. **Proposal is not mutation:** `propose_memory_update` no satisface ni consume permiso de `apply_memory_update`.
16. **No implicit persistence:** una decisión inferida en Nil o Life Plan no se guarda.
17. **No third-party diagnosis:** Relationships bloquea inferencia diagnóstica sobre otra persona.
18. **Reverification:** una mutación externa sin lectura posterior queda incompleta/fallida según política.

## 8. Qué se aplaza correctamente

### 10.16 — Presentation

- tono crítico, socrático, directivo o introspectivo;
- preguntas A/B/C/D;
- PDF/Word y estructura visual;
- idioma catalán/castellano por oposición;
- claridad de hechos/inferencias/hipótesis.

### 10.17 — Trace

- fuente consultada;
- búsqueda oficial exigida/usada;
- regla de prompt que originó una decisión;
- propuesta, aprobación, ejecución y verificación;
- exclusiones por sensibilidad o dominio.

### 10.18 — Memory

- consentimiento de persistencia;
- correcciones e invalidaciones;
- seguimiento de objetivos/progreso;
- decisiones explícitas frente a inferidas;
- separación de hechos estables y estado mutable.

### 10.19–10.30 — Domain Packs

- perfiles y reglas concretas;
- catálogos de operaciones;
- workflows reales;
- políticas de presentación;
- recursos y fuentes;
- tests E2E por dominio.

### Phase 11

- compilación de prompts por proveedor;
- adaptadores Claude/ChatGPT/Cline;
- Notion y búsqueda de conversaciones;
- secrets y PII;
- Model Gateway y control de egress.

## 9. Decisión de avance

**No reabrir commits 10.11–10.14.**

Antes de cerrar 10.15:

1. incorporar P-01 a P-10 al diseño;
2. convertir las 18 pruebas de aceptación en tests del perímetro;
3. verificar que los contratos soportan scopes, expiración, cross-domain granular, búsqueda por clase de fuente e inferencia sensible separada de persistencia;
4. implementar 10.15;
5. documentar este corpus como fuente de requisitos;
6. continuar a 10.16.
