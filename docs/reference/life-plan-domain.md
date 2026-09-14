# Life Plan Domain Reference (`domain:life-plan`)

> **Phase 10.29 — Complete — Independently Audited and Closed**
>
> - **Final Independent Closure:** PASS
> - **Blockers:** 0
> - **Majors:** 0
> - **Minors:** 0
> - **DP-029 Status:** VERIFIED_EXISTING
> - **AT-DP-029 Status:** PASS (45 connected checkpoints)
> - **Closure Adversarial Gate:** PASS (62 tests)

The **Life Plan Domain** (`domain:life-plan`) provides CMM OS with multi-year life planning, strategic goal coordination, explicit non-collapsible decision lattice tracking, exploratory scenario comparisons, multi-dimensional resource constraint evaluation (time, money, energy, capacity), alternative route preservation, plan drift detection, and fail-closed cross-domain coordination (Health, University, Oppositions, Parenthood, Project).

---

## 1. Identity & Inventory

- **Canonical Identity:** `domain:life-plan`
- **Display Name:** `Life Plan`
- **Version:** `1.0.0`
- **Manifest ID:** `manifest:life-plan:1.0.0`
- **Reasoning Profile:** `LifePlanProfile`
- **Permission Policy ID:** `domain-permission:life-plan:1.0.0`

### Inventory Counts
- **Entities (13):** `life_plan.entity.life_goal`, `life_plan.entity.milestone`, `life_plan.entity.scenario`, `life_plan.entity.dependency`, `life_plan.entity.constraint`, `life_plan.entity.risk`, `life_plan.entity.decision`, `life_plan.entity.financial_resource`, `life_plan.entity.career_path`, `life_plan.entity.education_path`, `life_plan.entity.housing_goal`, `life_plan.entity.family_goal`, `life_plan.entity.timeline`.
- **Resources (12):** `life_plan.resource.life_plan`, `life_plan.resource.financial_plan`, `life_plan.resource.academic_plan`, `life_plan.resource.opposition_plan`, `life_plan.resource.health_constraints`, `life_plan.resource.family_plan`, `life_plan.resource.housing_plan`, `life_plan.resource.goal`, `life_plan.resource.decision`, `life_plan.resource.calendar_event`, `life_plan.resource.memory_entry`, `life_plan.resource.user_message`.
- **Rules (8):** `life_plan.rule.goal_dependency`, `life_plan.rule.scenario_consistency`, `life_plan.rule.resource_constraint`, `life_plan.rule.decision_status`, `life_plan.rule.long_term_temporal`, `life_plan.rule.alternative_route`, `life_plan.rule.cross_domain_impact`, `life_plan.rule.plan_drift`.
- **Operations (10):** `life_plan.build_timeline`, `life_plan.compare_scenarios`, `life_plan.review_goals`, `life_plan.detect_dependencies`, `life_plan.identify_risks`, `life_plan.update_plan`, `life_plan.create_milestones`, `life_plan.generate_periodic_review`, `life_plan.evaluate_feasibility`, `life_plan.track_decisions`.
- **Workflows (7):**
  - `life_plan.life_plan_setup` ("Life Plan Setup")
  - `life_plan.quarterly_life_review` ("Quarterly Life Review")
  - `life_plan.scenario_comparison` ("Scenario Comparison")
  - `life_plan.goal_dependency_review` ("Goal Dependency Review")
  - `life_plan.cross_domain_impact_review` ("Major Decision Support")
  - `life_plan.plan_drift_review` ("Plan Drift Review")
  - `life_plan.annual_life_plan_update` ("Annual Life Plan Update")

---

## 2. Core Invariants & Boundaries

1. **Explicit Non-Collapsible Decision Lattice:** `preference != decision`, `scenario != decision`, `scenario != commitment`, `inference != confirmed fact`. Epistemic transitions require explicit evidence within canonical vocabulary (`idea`, `preference`, `goal`, `scenario`, `decision`, `commitment`). Non-decision states (`inference`, `hypothesis`, `confirmed_fact`, unknown states) fail closed. Unconfirmed preferences, ideas, hypotheses, and scenarios cannot be promoted to confirmed decisions or commitments without explicit user confirmation. Closed decisions cannot be reopened without explicit new evidence.
2. **Computed Scenario Consistency:** Internal scenario coherence computes structured conflicts from mutually exclusive assumption pairs, temporal milestone ordering dependencies, and multi-dimensional resource infeasibilities while strictly preserving unknown / uncertain evidence.
3. **Resource Constraints:** Four dimensions (`time`, `money`, `energy`, `available_capacity`) are evaluated independently without coercing missing evidence to 0. Invalid numeric values (`NaN`, `+Inf`, `-Inf`, booleans) fail closed with `invalid_evidence`.
4. **Alternative Route Preservation:** Switching to an alternative or contingency route does not infer goal abandonment or failure (`alternative route != abandonment`, `fallback != failure`).
5. **Plan Drift Detection:** Divergence between planned milestones and reality is measured without automatically abandoning goals.
6. **Gate-Owned Fail-Closed Cross-Domain Coordination:** Cross-domain inputs (Health, University, Oppositions, Parenthood, Project) are purpose-minimized and validated through gate-owned runtime resolution (`DomainPermissionGate` / `DomainPermissionResolver`). Caller-constructed boolean flags, forged `PermissionGateResult` objects, and context mismatches fail closed. Both direct and wrapped (`{"authorized_artifact": ...}`) contributions require verified internal tokens (`AuthorizedCrossDomainContribution._is_verified is True`). Clinical dossiers (diagnoses, medication lists, clinical histories) are strictly rejected.
7. **Strict Proposal-Only Memory Persistence:** All state changes produce `requires_confirmation=True` memory proposals. Direct memory writes and silent persistence are strictly prohibited. Confirmation validation requires strict boolean evidence (`type(is_confirmed) is bool and is_confirmed is True`), rejecting string coercions (`"false"`, `"true"`), numeric values, and non-empty collections fail closed.
8. **Major Decision Support:** `life_plan.cross_domain_impact_review` (publicly named `"Major Decision Support"`) coordinates multi-domain impacts preserving uncertainty, alternatives, and disclaimers.

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

## 4. Verification and Acceptance Entry Points

- **AT-DP-029 Acceptance Suite (45 Checkpoints):**
  ```bash
  .venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_dp029_acceptance.py
  ```
- **Permanent Closure Adversarial Gate (35+ Attack Classes):**
  ```bash
  .venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_closure_adversarial.py
  ```
- **Complete Life Plan Domain Suite (156+ Tests):**
  ```bash
  .venv/bin/python -m pytest -q tests/domains/test_life_plan*.py
  ```
