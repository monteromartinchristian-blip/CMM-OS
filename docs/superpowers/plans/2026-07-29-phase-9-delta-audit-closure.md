# Phase 9 Delta Audit Closure Implementation Plan

> **For agentic workers:** Execute each task in order and validate every
> documentation change before committing.

**Goal:** Alinear README, ROADMAP y auditorías con el cierre verificado de las
Fases 0–9 y dejar preparada la transición a Fase 10.

**Architecture:** Se preservan los cierres históricos, se corrigen los
documentos que representan el estado vigente y se añade un informe específico
para la auditoría delta 8.23–9.32.

**Tech Stack:** Markdown, Git, pytest, Ruff, GitHub Actions.

## Global Constraints

- Release actual: `v0.8.0`.
- Commit técnico final auditado: `41d2d26`.
- Baseline global: 5409 tests.
- Python validado: 3.10, 3.11 y 3.12.
- No modificar código de producción.
- No corregir deuda Ruff histórica fuera del delta.

---

### Task 1: Crear el informe de auditoría delta

**Files:**
- Create: `docs/audits/phases-8-9-delta-audit.md`

- [ ] Documentar alcance 8.23–8.26 y 9.29–9.32.
- [ ] Registrar los hallazgos de idempotencia y trazabilidad.
- [ ] Registrar commits, pruebas, CI y veredicto.
- [ ] Verificar ausencia de placeholders.

### Task 2: Consolidar el cierre de Fase 9

**Files:**
- Modify: `docs/audits/phase-9-completion.md`

- [ ] Actualizar veredicto y commit final.
- [ ] Sustituir 5406 por 5409.
- [ ] Marcar auditoría, integración y CI como completadas.
- [ ] Confirmar compatibilidad Python 3.10–3.12.
- [ ] Mantener únicamente limitaciones aún vigentes.

### Task 3: Añadir continuidad al cierre de Fase 8

**Files:**
- Modify: `docs/audits/phase-8-completion.md`

- [ ] Mantener intacta la evidencia histórica.
- [ ] Añadir una nota final sobre 8.23–8.26.
- [ ] Enlazar el informe delta.

### Task 4: Actualizar documentación pública

**Files:**
- Modify: `README.md`
- Modify: `ROADMAP.md`

- [ ] Declarar Fases 0–9 completas y auditadas.
- [ ] Establecer 5409 como baseline.
- [ ] Mantener `v0.8.0` como release publicada.
- [ ] Establecer Fase 10 como siguiente hito.
- [ ] Actualizar enlaces de auditoría.

### Task 5: Validar y publicar

- [ ] Ejecutar `git diff --check`.
- [ ] Buscar referencias activas obsoletas a 642, 1758, 4989 y 5406 tests.
- [ ] Revisar el diff completo.
- [ ] Crear un commit documental.
- [ ] Integrar mediante fast-forward en `main`.
- [ ] Publicar y comprobar CI.
