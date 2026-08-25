# Life Plan Domain Reference (`domain:life-plan`)

> **Phase 10.29 — Implementation Complete; Ready for Independent Audit**

The **Life Plan Domain** (`domain:life-plan`) provides CMM OS with multi-year life planning, strategic goal coordination, explicit non-collapsible decision lattice tracking, exploratory scenario comparisons, multi-dimensional resource constraint evaluation (time, money, energy, capacity), alternative route preservation, plan drift detection, and fail-closed cross-domain coordination (Health, University, Oppositions, Parenthood, Project).

---

## 1. Identity & Inventory

- **Canonical Identity:** `domain:life-plan`
- **Display Name:** `Life Plan`
- **Version:** `1.0.0`
- **Manifest ID:** `manifest:life_plan:1.0.0`
- **Reasoning Profile:** `LifePlanProfile`
- **Permission Policy ID:** `domain-permission:life-plan:1.0.0`

### Inventory Counts
- **Entities (13):** `life_plan.entity.life_goal`, `life_plan.entity.milestone`, `life_plan.entity.scenario`, `life_plan.entity.dependency`, `life_plan.entity.resource_constraint`, `life_plan.entity.life_domain_state`, `life_plan.entity.decision`, `life_plan.entity.commitment`, `life_plan.entity.alternative_route`, `life_plan.entity.plan_drift`, `life_plan.entity.financial_plan`, `life_plan.entity.timeline`, `life_plan.entity.review_record`.
- **Resources (12):** `life_plan.resource.life_plan`, `life_plan.resource.goal`, `life_plan.resource.decision`, `life_plan.resource.financial_plan`, `life_plan.resource.timeline`, `life_plan.resource.scenario`, `life_plan.resource.calendar_event`, `life_plan.resource.user_message`, `life_plan.resource.note`, `life_plan.resource.memory_entry`, `life_plan.resource.review_record`, `life_plan.resource.health_constraints`.
- **Rules (8):** `life_plan.rule.goal_dependency`, `life_plan.rule.resource_constraint`, `life_plan.rule.decision_status`, `life_plan.rule.scenario_consistency`, `life_plan.rule.long_term_temporal`, `life_plan.rule.alternative_route`, `life_plan.rule.cross_domain_impact`, `life_plan.rule.plan_drift`.
- **Operations (10):** `life_plan.build_timeline`, `life_plan.compare_scenarios`, `life_plan.review_goals`, `life_plan.detect_dependencies`, `life_plan.identify_risks`, `life_plan.update_plan`, `life_plan.create_milestones`, `life_plan.generate_periodic_review`, `life_plan.evaluate_feasibility`, `life_plan.track_decisions`.
- **Workflows (7):** `life_plan.life_plan_setup`, `life_plan.quarterly_life_review`, `life_plan.scenario_comparison`, `life_plan.goal_dependency_review`, `life_plan.cross_domain_impact_review`, `life_plan.plan_drift_review`, `life_plan.annual_life_plan_update`.

---

## 2. Core Invariants & Boundaries

1. **Explicit Non-Collapsible Decision Lattice:** `preference != decision`, `scenario != decision`, `scenario != commitment`, `inference != confirmed fact`. Epistemic transitions require explicit evidence. Unconfirmed preferences, ideas, hypotheses, and scenarios cannot be promoted to confirmed decisions or commitments without explicit user confirmation. Closed decisions cannot be reopened without explicit new evidence.
2. **Resource Constraints:** Four dimensions (`time`, `money`, `energy`, `available_capacity`) are evaluated independently without coercing missing evidence to 0. Invalid numeric values (`NaN`, `+Inf`, `-Inf`, booleans) are rejected.
3. **Alternative Route Preservation:** Switching to an alternative or contingency route does not infer goal abandonment or failure (`alternative route != abandonment`, `fallback != failure`).
4. **Plan Drift Detection:** Divergence between planned milestones and reality is measured without automatically abandoning goals.
5. **Fail-Closed Cross-Domain Coordination:** Cross-domain inputs (Health, University, Oppositions, Parenthood, Project) are purpose-minimized and must be authorized by `DomainPermissionGate` / `DomainPermissionResolver`. Unvetted dictionaries, caller booleans, and clinical dossiers are rejected.
6. **Proposal-Only Memory Persistence:** All state changes produce `requires_confirmation=True` memory proposals. Direct memory writes and silent persistence are strictly prohibited.
7. **Major Decision Support:** `life_plan.cross_domain_impact_review` coordinates multi-domain impacts preserving uncertainty, alternatives, and disclaimers.

---

## 3. Module Architecture

```text
cmm/domains/life_plan/
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
.venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_dp029_acceptance.py
```

AT-DP-029 executes a 45-checkpoint connected state-linked scenario validating domain resolution, profile reuse, catalog parity, decision lattice semantics, scenario comparison, resource constraints, temporal ordering, cross-domain health integration, approval gating, memory proposals, trace provenance, atomic registration, and Major Decision Support.
