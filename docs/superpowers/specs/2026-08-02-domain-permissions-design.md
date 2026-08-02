# Fase 10.15 — Domain Permissions

**Estado final:** completada y auditada el 2 de agosto de 2026.

## Diseño aprobado

La fase añade una única frontera de permisos declarativa y determinista. Los
contratos agnósticos viven en `cmm.agent_runtime`, reutilizando
`PermissionEffect`, `SensitivityLevel`, `AgentAutonomyLevel` y
`ApprovalRequirement`. `cmm.domains` contiene la política, sus requests, el
registry, la resolución y adapters puros para reglas, operaciones, workflows y
cross-domain. El runtime no importa dominios.

### Componentes

- `cmm.agent_runtime.domain_permission_contracts`: catálogo de capacidades,
  evaluaciones por capa, composición restrictiva, límites de autonomía y
  resultado efectivo.
- `cmm.agent_runtime.permission_restriction_contracts`: fuentes externas,
  egress, exportación y obligaciones de post-verificación.
- `cmm.domains.permission_contracts`: `DomainPermissionPolicy`, requests,
  conflictos, resolución y decisión cross-domain; todos frozen/slots y
  serializables.
- `cmm.domains.permission_registry`: registry in-memory inyectable, con
  versiones SemVer, policy activa y listado estable.
- `cmm.domains.permission_evaluator`: evaluación pura de una política y
  composición de capas, con deny-wins y reloj inyectado para expiry.
- `cmm.domains.permission_resolution`: resolución de políticas ya resueltas,
  sin discovery, ejecución ni mutación de registries.
- `cmm.domains.permission_catalog`: políticas conservadoras de general,
  health, university, relationships y project.
- `cmm.domains.approval_bridge`: traducción pura al sistema canónico de
  aprobaciones sin convertir metadata en evidencia.
- `cmm.domains.permission_gate`: reevaluación y consumo inmediatamente antes
  de las rutas reales de operaciones, workflows y nodos.

### Semántica

`DENY` domina siempre. `ABSTAIN` no concede. `APPROVAL_REQUIRED` solo resulta
efectivo si no hay deny y conserva requirements exactos. Una allowlist ausente
significa no especificada; una allowlist vacía significa deny-all cuando la
política declara ese campo. Las listas de prohibición siempre eliminan
elementos permitidos. Las capas se ordenan global, user, session, domain,
operation, workflow y autonomy, pero la decisión no depende de ese orden.

Los booleanos de capacidades se intersectan; las allowlists se intersectan y
las prohibiciones eliminan; máximos toman `min` y mínimos `max`. El dominio no
puede elevar autonomía, ampliar recursos ni convertir una aprobación en allow.

Los repositorios de aprobación deben ofrecer una sección crítica atómica. Los
grants legacy, `granted_permissions`, `approved_gates` y
`external_domain_trusted` no autorizan ejecución. Una aprobación queda ligada
a todos los campos tipados de seguridad y solo `validate_and_consume()` produce
evidencia ejecutable.

Las restricciones declarativas cubren clase mínima de fuente, proveedor y
egress, exportación e identificadores y post-verificación. Estas restricciones
no ejecutan búsquedas, transferencias, redacción ni verificación. Cuando una
mutación despachada exige post-verificación, permanece `RUNNING` hasta que una
fase posterior satisfaga la obligación.

### Integración y límites

Los adapters de permisos reciben contratos de 10.12–10.14 y devuelven
decisiones. Los gates coordinan las rutas existentes, pero no seleccionan
reglas, recuperan recursos ni autentican actores. No hay conectores, búsqueda
web, Model Gateway, persistencia, secrets, redacción efectiva, trazas completas,
RBAC, tokens ni identidad de Fase 11.

La trazabilidad contiene solo source, matched rules, reason codes, policy IDs,
constraints y evidencias estructuradas. Metadata nunca otorga permisos.

La validación de cierre cubre composición, source/target cross-domain,
operaciones, workflows, scopes de aprobación, concurrencia, serialización,
catálogo, API pública, dirección de dependencias y suite global.
