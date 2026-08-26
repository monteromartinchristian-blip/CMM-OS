# Project Domain Reference (`domain:project`)

> **Phase 10.30 — Candidate Implementation Complete — Pending Independent Audit**
>
> - **Candidate Implementation Status:** COMPLETE
> - **DP-030 Status:** REQUIRES_PHASE_INSPECTION
> - **AT-DP-030 Status:** PASS (56 connected acceptance checkpoints)
> - **Closure Adversarial Gate:** PASS (34 attack classes)
> - **Independent Audit:** PENDING

The **Project Domain** (`domain:project`) provides CMM OS with comprehensive generic project management, milestone planning, dependency tracking, resource constraint checking, risk analysis, progress verification, and conditional software development capabilities (architecture analysis, change review, test validation, commit readiness evaluation, and rollback-protected mutations).

---

## 1. Identity & Inventory

- **Canonical Identity:** `domain:project`
- **Display Name:** `Project`
- **Version:** `1.0.0`
- **Manifest ID:** `manifest:project:1.0.0`
- **Reasoning Profile:** `ProjectProfile` (Single canonical profile; conditional software capabilities activate upon grounded signals)
- **Permission Policy ID:** `domain-permission:project:1.0.0`

### Canonical Inventory Counts
- **Entities (27):** `project.entity.project`, `project.entity.milestone`, `project.entity.task`, `project.entity.dependency`, `project.entity.deliverable`, `project.entity.risk`, `project.entity.issue`, `project.entity.decision`, `project.entity.resource_allocation`, `project.entity.stakeholder`, `project.entity.timeline`, `project.entity.status_report`, `project.entity.blocker`, `project.entity.scope_item`, `project.entity.repository`, `project.entity.source_file`, `project.entity.code_module`, `project.entity.architecture_component`, `project.entity.change_set`, `project.entity.review_finding`, `project.entity.validation_run`, `project.entity.validation_report`, `project.entity.commit_proposal`, `project.entity.release_manifest`, `project.entity.rollback_target`, `project.entity.test_suite`, `project.entity.audit_evidence`.
- **Resources (22):** `project.resource.project_brief`, `project.resource.project_plan`, `project.resource.milestone_schedule`, `project.resource.dependency_graph`, `project.resource.risk_register`, `project.resource.resource_pool`, `project.resource.status_update`, `project.resource.decision_log`, `project.resource.meeting_notes`, `project.resource.deliverable_spec`, `project.resource.calendar_event`, `project.resource.memory_entry`, `project.resource.source_code`, `project.resource.git_history`, `project.resource.architecture_document`, `project.resource.implementation_plan`, `project.resource.review_feedback`, `project.resource.validation_results`, `project.resource.test_report`, `project.resource.release_notes`, `project.resource.patch`, `project.resource.user_message`.
- **Rules (18):**
  - *Generic Layer (8):* `project.rule.scope_consistency`, `project.rule.dependency_consistency`, `project.rule.resource_feasibility`, `project.rule.status_transition`, `project.rule.risk_assessment`, `project.rule.progress_verification`, `project.rule.cross_domain_projection`, `project.rule.decision_state`.
  - *Software Layer (10):* `project.rule.architecture_conformance`, `project.rule.implementation_plan_alignment`, `project.rule.change_review_safety`, `project.rule.commit_readiness`, `project.rule.semantic_transformation`, `project.rule.test_validation`, `project.rule.rollback_safety`, `project.rule.capability_activation`, `project.rule.audit_trail_completeness`, `project.rule.repository_grounding`.
- **Operations (20):**
  - *Generic Layer (12):* `project.create_project_overview`, `project.plan_milestones`, `project.review_dependencies`, `project.review_resources`, `project.review_risks`, `project.review_status`, `project.generate_progress_summary`, `project.update_project_plan`, `project.track_decisions`, `project.evaluate_feasibility`, `project.build_timeline`, `project.identify_blockers`.
  - *Software Layer (8):* `project.analyse_architecture`, `project.plan_implementation`, `project.modify_code`, `project.review_change`, `project.run_validation`, `project.prepare_commit`, `project.generate_release_manifest`, `project.record_audit_evidence`.
- **Workflows (12):**
  - *Generic Layer (7):* `project.project_setup`, `project.milestone_planning`, `project.dependency_review`, `project.resource_review`, `project.risk_review`, `project.progress_review`, `project.periodic_project_review`.
  - *Software Layer (5):* `project.self_development`, `project.architecture_review`, `project.code_modification`, `project.change_review`, `project.release_preparation`.

---

## 2. Core Invariants & Boundaries

1. **Generic Core & Conditional Software Capability:** Generic project reasoning operates on any project domain without code/software baggage. Software capability activates conditionally upon grounded signals (`project.self_development`, `project.modify_code`, `project.resource.source_code`, or explicit repository-backed metadata).
2. **Canonical Operation Names:** `project.review_change` is canonical. `project.prepare_change_review` is strictly legacy-only and excluded from the canonical catalog.
3. **Commit Readiness & Never Autonomous Git Commit:** `project.prepare_commit` evaluates readiness and gathers verification evidence; it never calls `git commit`, never creates fake commit hashes, and maintains a strict `ready_for_approved_commit` vs `committed=False` distinction.
4. **Formation Boundary Preserved:** The Formation system is an organizational and cognitive overlay in the General domain and is never absorbed into Project domain entities, rules, or workflows.
5. **Purpose-Minimized Life Plan Projection:** Life Plan receives only an authorized, purpose-minimized Project projection containing at most 9 approved fields (`ALLOWED_LIFE_PLAN_PROJECTION_FIELDS`). Raw internal source code, commit history, and internal credentials fail closed.
6. **Fail-Closed Permissions & Mutating Approval Boundary:** Outbound cross-domain calls and direct memory writes fail closed (`DENY`). Code mutations (`project.modify_code`, `FILE_MODIFY`) require human/canonical approval; forged tokens and unapproved execution requests fail closed (`APPROVAL_REQUIRED` / `DENY`).
7. **Proposal-Only Memory Integration:** Memory proposals enforce `requires_confirmation=True`. Memory operations cannot autonomously promote unconfirmed proposals to confirmed decisions or committed changes.
8. **Shared Runtime Reuse:** Directly leverages CMM OS shared infrastructure: `DomainRegistry`, `InMemoryDomainProfileRegistry`, `InMemoryDomainResourceRegistry`, `InMemoryReasoningRuleRegistry`, `InMemoryDomainOperationRegistry`, `InMemoryDomainWorkflowRegistry`, `DomainPermissionRegistry`, `DomainPermissionGate`, `DomainTraceAssembler`, and `DomainMemoryBinding`.

---

## 3. Module Architecture (14 Canonical Modules)

```text
cmm/domains/project/
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

- **AT-DP-030 Acceptance Suite (56 Connected Checkpoints):**
  ```bash
  .venv/bin/python -m pytest -q tests/domains/test_project_domain_dp030_acceptance.py
  ```
- **Permanent Closure Adversarial Gate (34 Attack Classes):**
  ```bash
  .venv/bin/python -m pytest -q tests/domains/test_project_domain_closure_adversarial.py
  ```
- **Complete Project Domain Suite (87 Tests):**
  ```bash
  .venv/bin/python -m pytest -q tests/domains/test_project_domain_*.py
  ```
