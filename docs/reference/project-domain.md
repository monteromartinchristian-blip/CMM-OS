# Project Domain Reference (`domain:project`)

> **Phase 10.30 — Complete — Independently Audited and Closed**
>
> - **Final Independent Re-audit V6:** PASS
> - **Blockers:** 0
> - **Majors:** 0
> - **Minors:** 0
> - **DP-030 Status:** VERIFIED_EXISTING
> - **AT-DP-030 Status:** PASS (56 connected acceptance checkpoints)
> - **Closure Adversarial Gate:** PASS (34 attack classes)
> - **Final Audit:** `docs/audits/phase-10.30-project-independent-reaudit-v6.md`
> - **Audit Lineage:** Independent Audit V1 = FAIL recorded; Independent Re-audit V2 = FAIL recorded; Independent Re-audit V3 = FAIL recorded; Independent Re-audit V4 = FAIL recorded; Independent Re-audit V5 = FAIL recorded; Independent Re-audit V6 = PASS; final closure gate = PASS

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
- **Entities (27):** `project.entity.project`, `project.entity.objective`, `project.entity.milestone`, `project.entity.work_item`, `project.entity.deliverable`, `project.entity.project_resource`, `project.entity.constraint`, `project.entity.risk`, `project.entity.decision`, `project.entity.status_change`, `project.entity.project_event`, `project.entity.repository`, `project.entity.module`, `project.entity.package`, `project.entity.file`, `project.entity.class`, `project.entity.method`, `project.entity.function`, `project.entity.contract`, `project.entity.dependency`, `project.entity.test`, `project.entity.validation_result`, `project.entity.issue`, `project.entity.technical_debt`, `project.entity.architecture_decision`, `project.entity.workflow`, `project.entity.release`.
- **Resources (22):**
  - *Generic Layer (10):* `project.resource.project_brief`, `project.resource.project_plan`, `project.resource.milestone_record`, `project.resource.work_item_record`, `project.resource.dependency_record`, `project.resource.resource_record`, `project.resource.status_report`, `project.resource.decision_record`, `project.resource.risk_record`, `project.resource.project_timeline`.
  - *Software Layer (12):* `project.resource.source_code`, `project.resource.project_file`, `project.resource.documentation`, `project.resource.test_result`, `project.resource.validation_result`, `project.resource.git_history`, `project.resource.issue`, `project.resource.roadmap`, `project.resource.architecture_document`, `project.resource.commit`, `project.resource.pull_request`, `project.resource.memory_entry`.
- **Rules (18):**
  - *Generic Layer (8):* `project.scope_consistency`, `project.milestone_consistency`, `project.dependency_consistency`, `project.status_transition`, `project.resource_constraint`, `project.decision_state`, `project.temporal_validity`, `project.progress_evidence`.
  - *Software Layer (10):* `project.architecture_contract`, `project.code_documentation_consistency`, `project.validation_required`, `project.technical_debt`, `project.dead_code`, `project.public_api_change`, `project.backward_compatibility`, `project.dependency_boundary`, `project.test_coverage_impact`, `project.semantic_transformation`.
- **Operations (20):**
  - *Generic Layer (7):* `project.create_project_overview`, `project.review_status`, `project.plan_milestones`, `project.review_dependencies`, `project.review_resources`, `project.review_risks`, `project.generate_progress_summary`.
  - *Software Layer (13):* `project.analyse_architecture`, `project.detect_technical_debt`, `project.compare_code_documentation`, `project.detect_dead_code`, `project.detect_duplication`, `project.generate_adr`, `project.create_implementation_plan`, `project.modify_code`, `project.run_validation`, `project.prepare_commit`, `project.review_change`, `project.update_documentation`, `project.generate_release_notes`.
- **Workflows (12):**
  - *Generic Layer (4):* `project.project_setup`, `project.status_review`, `project.milestone_dependency_review`, `project.periodic_project_review`.
  - *Software Layer (8):* `project.architecture_review`, `project.feature_implementation`, `project.bug_resolution`, `project.technical_debt_review`, `project.documentation_synchronisation`, `project.refactor`, `project.release_preparation`, `project.self_development`.

---

## 2. Core Invariants & Boundaries

1. **Generic Core & Conditional Software Capability:** Generic project reasoning operates on any project domain without code/software baggage. Software capability activates conditionally upon grounded signals (`project.self_development`, `project.modify_code`, `project.resource.source_code`, or verified repository-backed context).
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
- **Complete Project Domain Suite:**
  ```bash
  .venv/bin/python -m pytest -q tests/domains/test_project_domain_*.py
  ```
