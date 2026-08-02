# Domain Permissions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar la Fase 10.15 como una frontera común de permisos, con políticas de dominio y resolución pura.

**Architecture:** Los contratos y el algoritmo de intersección se alojan en `cmm.agent_runtime`; los contratos y adapters de dominio se alojan en `cmm.domains`. El registry es in-memory e inyectable y la resolución produce decisiones auditables sin ejecutar acciones.

**Tech Stack:** Python 3.10, dataclasses frozen/slots, enums, MappingProxyType, pytest, ruff.

**Estado:** completado y validado el 2 de agosto de 2026.

---

### Task 1: Contratos comunes y composición

**Files:** Create `cmm/agent_runtime/domain_permission_contracts.py`, modify `cmm/agent_runtime/__init__.py`, test `tests/agent_runtime/test_domain_permission_contracts.py`.

- [x] Escribir tests para catálogo estricto, evaluaciones por capa, límites numéricos, serialización profunda y composición deny-wins.
- [x] Ejecutar el módulo nuevo y confirmar fallo por imports ausentes.
- [x] Implementar enums, contratos frozen/slots, validación JSON-safe y `intersect_permission_layers` sin imports de `cmm.domains`.
- [x] Ejecutar tests focales y después la suite de agent runtime.

### Task 2: Política y requests de dominio

**Files:** Create `cmm/domains/permission_contracts.py`, test `tests/domains/test_domain_permission_contracts.py`.

- [x] Añadir tests RED para policy/request/cross-domain/approval fingerprints, unknown fields, semver, expiry y coherencia contextual.
- [x] Implementar contratos inmutables, serialización round-trip y errores sanitizados reutilizando helpers comunes de dominios.
- [x] Verificar imports en ambos órdenes y ausencia de dependencia inversa.

### Task 3: Registry y evaluación pura

**Files:** Create `cmm/domains/permission_registry.py`, `cmm/domains/permission_evaluator.py`, tests focales.

- [x] Cubrir registro explícito, duplicados, versiones SemVer, enable/disable y ausencia de evaluación durante register.
- [x] Implementar registry in-memory inyectable y evaluación por política con reloj explícito.
- [x] Añadir propiedades de conmutatividad, idempotencia y monotonicidad restrictiva.

### Task 4: Resolución, cross-domain y adapters

**Files:** Create `cmm/domains/permission_resolution.py`, `cmm/domains/permission_adapters.py`, tests de resolución, cross-domain, resources, rules, operations y workflows.

- [x] Escribir tests RED para capas, supporting domains, source/target deny, sensibilidad y approvals.
- [x] Implementar resolución determinista y adapters puros que consuman contratos existentes sin ejecución.
- [x] Verificar decisiones de operación 10.13, workflow 10.14 y regla required/optional.

### Task 5: Catálogo, API pública y documentación

**Files:** Create `cmm/domains/permission_catalog.py`, `docs/reference/domain-permissions.md`, modify package `__init__.py` files, tests de catálogo/API.

- [x] Cubrir las cinco políticas conservadoras y exports públicos.
- [x] Implementar catálogo sin singleton mutable y documentar semántica, límites e integraciones.
- [x] Ejecutar validación focal, suites requeridas, compileall, ruff y `git diff --check`.

### Task 6: Bridge, consumo y gates reales

- [x] Reutilizar `BLOCKED` y `WAITING_FOR_APPROVAL`.
- [x] Conservar bindings tipados completos en el bridge.
- [x] Garantizar consumo atómico, revocación, expiración y dry-run.
- [x] Integrar reevaluación inmediata en operaciones, workflows, nodos y `resume()`.
- [x] Hacer fallar cerrado los permisos/aprobaciones legacy sin gate.

### Task 7: Restricciones declarativas finales

- [x] Añadir clases cerradas de fuentes y verificación adicional.
- [x] Añadir egress por proveedor, localidad, sensibilidad, propósito y scope.
- [x] Añadir exportación con identificadores y evidencia original separada.
- [x] Propagar post-verificación como restricción efectiva sin ejecutarla.

### Task 8: Cierre técnico

- [x] Auditar alcance, exclusiones y dirección de dependencias.
- [x] Ejecutar 416 tests focales y 7907 tests globales.
- [x] Verificar concurrencia, catálogo, API pública y serialización.
- [x] Ejecutar `compileall`, Ruff afectado y checks de diff.
