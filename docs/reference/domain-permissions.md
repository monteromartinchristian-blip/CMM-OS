# Domain Permissions (Fase 10.15)

**Estado:** completada y auditada el 2 de agosto de 2026.

## Alcance y arquitectura

10.15 establece una frontera única, declarativa y fail-closed para permisos de
dominio. Los contratos neutrales, la composición restrictiva y los bindings de
aprobación viven en `cmm.agent_runtime`; políticas, registry, resolución,
adapters, bridge y gates viven en `cmm.domains`. La dependencia permitida es
siempre `cmm.domains → cmm.agent_runtime`.

`DENY` domina, `ABSTAIN` no concede y `APPROVAL_REQUIRED` nunca prevalece sobre
una denegación. Las allowlists se intersectan, las prohibiciones se unen, los
máximos toman el menor valor y los mínimos el mayor. La composición incluye
capas global, usuario, sesión, dominio, operación, workflow y autonomía.

## Contratos

`DomainPermissionPolicy` y `DomainPermissionRequest` representan actor, sesión,
dominio, recurso, sensibilidad, propósito, operación/workflow y contexto
cross-domain. Los contratos comunes representan capacidades cerradas,
evaluaciones por capa, resultado efectivo y requisitos de aprobación exactos.
Todos los contratos nuevos son inmutables, deterministas, JSON-safe y disponen
de `to_dict/from_dict` con rechazo de campos o enums desconocidos.

Cross-domain exige políticas vigentes tanto en origen como en destino y limita
capacidad, recursos, tipos, operaciones, workflows, sensibilidad, duración,
scope y dominios. Una política de soporte nunca amplía a la primaria.

## Gates y aprobaciones

Las rutas reales de `DefaultDomainOperationOrchestrator` y
`DomainWorkflowExecutor` siguen este orden:

1. disponibilidad;
2. resolución efectiva con políticas vigentes;
3. reevaluación inmediatamente anterior al efecto;
4. construcción y binding del requisito exacto;
5. `ApprovalService.validate_and_consume()`;
6. despacho.

`BLOCKED` representa denegación y `WAITING_FOR_APPROVAL` aprobación pendiente.
Los grants legacy y `granted_permissions` nunca son evidencia ejecutable. Si un
caller aporta permisos o aprobaciones legacy sin un gate disponible, la ruta
falla cerrada con `permission.gate_unavailable`.

El bridge conserva como campo tipado actor, sesión, dominio fuente/destino,
capacidad, operación/workflow/nodo, recurso, finalidad, sensibilidad, scope,
expiración, reutilización y restricciones. Metadata contiene solo procedencia.

La única evidencia ejecutable procede del servicio canónico. Su repositorio
debe declarar `atomic_consumption_guaranteed` y ofrecer `critical_section()`.
Lectura, validación, revocación/expiración y consumo ocurren dentro de esa misma
sección; el backend en memoria usa un `threading.RLock`. Dry-run no consume,
`one_time` solo puede consumirse una vez y los grants reutilizables conservan
sus límites.

Workflow-scoped se consume al iniciar; node-scoped, justo antes del nodo. Un
nodo no alcanzado no consume y `resume()` vuelve a pasar por los gates vigentes.

## Restricciones declarativas

- Fuentes: `OFFICIAL_ONLY`, `PRIMARY_SOURCES`, `TRUSTED_SECONDARY` y
  `GENERAL_WEB`, con clase mínima, dominios y verificación adicional.
- Egress: proveedor y localidad, dominios de origen, sensibilidad, categorías,
  propósito, recursos/claims, redacción declarada, consentimiento/aprobación y
  retención.
- Exportación: destinatario/clase, propósito, formato, categorías,
  identificadores, redacción/tokenización, sensibilidad, expiración, uso único
  y aprobación. Resumen y evidencia original son scopes distintos.
- Post-verificación: confirmación de despacho, refetch, comparación,
  verificación manual y evidencia de resultado. La obligación viaja en
  `effective_constraints`; una mutación ya despachada permanece `RUNNING`
  mientras esa obligación esté pendiente.

Lectura no implica exportación, inferencia no implica persistencia o egress,
mutación no implica exportación y autorización interna no implica comunicación
externa.

## Compatibilidad y exclusiones

Los campos nuevos son opcionales al leer payloads anteriores. Los enums
existentes y los imports públicos permanecen estables. `PermissionApprovalGrant`
es solo una pista legacy de lectura y `external_domain_trusted` se ignora con
traza explícita.

10.15 no implementa conectores, búsquedas reales, llamadas a modelos, Model
Gateway, secrets, redacción/tokenización efectiva, persistencia de memoria,
trazas completas de 10.17, autenticación ni RBAC de Fase 11.

## Validación final

- batería focal: 416 tests;
- suite global: 7907 tests;
- tests de concurrencia, catálogo, dependencia, API pública y round-trip;
- `compileall`, Ruff de archivos afectados y checks de diff.
