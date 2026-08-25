# Sport Domain Reference (`domain:sport`)

> **Phase 10.28 — Implemented; audit V2 findings remediated; re-audit pending**

The **Sport Domain** (`domain:sport`) provides CMM OS with athletic training planning, physical activity goal tracking, progression analysis, volume/intensity/frequency load evaluation, recovery tracking, body measurement trends, injury risk signaling, and controlled Health coordination.

---

## 1. Identity & Inventory

- **Canonical Identity:** `domain:sport`
- **Display Name:** `Sport`
- **Version:** `1.0.0`
- **Manifest ID:** `manifest:sport:1.0.0`
- **Reasoning Profile:** `SportProfile`
- **Permission Policy ID:** `domain-permission:sport:1.0.0`

### Inventory Counts
- **Entities (11):** `sport.entity.exercise`, `sport.entity.workout`, `sport.entity.training_plan`, `sport.entity.metric`, `sport.entity.body_measurement`, `sport.entity.injury`, `sport.entity.recovery`, `sport.entity.sport_goal`, `sport.entity.equipment`, `sport.entity.session`, `sport.entity.performance_record`.
- **Resources (9):** `sport.resource.workout_log`, `sport.resource.health_resource`, `sport.resource.body_measurement`, `sport.resource.training_plan`, `sport.resource.calendar_event`, `sport.resource.user_message`, `sport.resource.note`, `sport.resource.wearable_data`, `sport.resource.memory_entry`.
- **Rules (6):** `sport.rule.training_load`, `sport.rule.progressive_overload`, `sport.rule.recovery`, `sport.rule.injury_signal`, `sport.rule.health_constraint`, `sport.rule.measurement_trend`.
- **Operations (8):** `sport.create_training_plan`, `sport.review_progress`, `sport.adjust_training_load`, `sport.generate_workout`, `sport.track_measurements`, `sport.review_recovery`, `sport.identify_risks`, `sport.schedule_sessions`.
- **Workflows (5):** `sport.training_plan_setup`, `sport.weekly_training_review`, `sport.recovery_review`, `sport.progress_review`, `sport.return_to_training_with_health_constraints`.

---

## 2. Core Invariants & Boundaries

1. **Sport / Health Boundary:** Sport receives from Health strictly authorized, purpose-bound, and minimized `health_constraint` projections containing only functional limits (`activity_limits`, `load_limits`, `duration_limits`, `heart_rate_limits`, `environmental_limits`, `monitoring_requirements`, `reassessment_date`). Prohibited clinical details (`diagnosis`, `treatment_plan`, `clinical_notes`, medical histories) are dropped. Unvetted raw dictionaries lacking authorization evidence are rejected. Sport cannot diagnose injuries, modify medical treatments, or claim clinical clearance.
2. **Training Load:** Preserves volume, intensity, and frequency distinctly. Rejects invalid numeric values (Boolean-as-number, NaN, Inf, negative values) and treats missing inputs as `unknown`. Dynamic load adjustments respect actual constraint values (`reduction_pct`, `max_load`) without hardcoding arbitrary percentages.
3. **Progressive Overload:** Compares baseline and proposed loads against explicit finite policy thresholds. Rejects non-finite values (NaN, Inf, booleans). Does not hard-code a universal "10% rule" as absolute domain truth; preserves uncertainty (`certainty=False`) when no threshold exists.
4. **Mutable Recovery & Readiness:** Recovery states (`ready`, `limited`, `hold`, `unknown`) are time-bound evidence, not permanent identity traits. Newer evidence updates operational readiness.
5. **Injury Risk Signals:** Identifies athletic risk signals requiring load reduction, holding, or checking, but never produces named clinical injury diagnoses.
6. **Measurement Trends:** Requires at least two temporally ordered, comparable observations (same metric/unit/method) with valid ISO timestamps. Observations are sorted chronologically before trend evaluation to prevent caller order from fabricating trends. Punctual outliers remain visible.
7. **Approval-Gated Scheduling:** `sport.schedule_sessions` produces schedule proposals; readiness for execution requires scoped `ApprovalRequest` and `ApprovalDecision` identifiers from `ApprovalService`. Bare Boolean flags without scoped approval evidence are rejected. Direct calendar mutation is delegated to the shared external boundary.
8. **Fail-Closed Memory Integration:** State updates produce `requires_confirmation=True` Domain Memory proposals and bindings. Memory validation delegates to `DefaultDomainMemoryIntegrationValidator` and fails closed on validator faults or malformed inventories.

---

## 3. Module Architecture

```text
cmm/domains/sport/
├── __init__.py
├── bootstrap.py
├── catalog.py
├── definition.py
├── integration.py
├── memory.py
├── operations.py
├── permissions.py
├── presentation.py
├── profile.py
├── resources.py
├── rules.py
├── trace.py
└── workflows.py
```

---

## 4. Acceptance Test Entry Point

```bash
.venv/bin/python -m pytest -q tests/domains/test_sport_domain_dp028_acceptance.py
```

AT-DP-028 executes a 44-checkpoint connected state-linked scenario validating domain resolution, profile reuse, catalog parity, load evaluation, overload policy, recovery mutability, injury signal non-diagnosis, Health constraint projection, measurement trend evidence, calendar approval gating, memory proposals, trace provenance, atomic registration, and General fallback.
