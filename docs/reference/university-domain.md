# University Domain — Reference

## Domain ID

`domain:university`

## Overview

The University Domain specifies CMM OS to manage subjects, convocations,
assignments, performance, academic burden, and university planning — without
ever acting on the official academic record.

It is a declarative, composable layer over the existing Domain Intelligence
infrastructure (Fases 10.1–10.18). It does not create parallel engines,
separate storage, or direct runtime access. It reuses the canonical Entity,
Resource, Rule, Operation, Workflow, Permission, Trace, Memory,
Presentation, and Resolution contracts.

The University safety posture is deliberately conservative:

- **No autonomous academic action.** No operation sends email, submits a formal
  procedure, enrols/registers, or adopts an academic decision.
- **Academic State ≠ Personal Memory.** `update_subject_status` mutates only the
  INTERNAL Academic State; it never touches the official record.
- **Performance ≠ capacity.** Observed academic performance is a fact about
  output, never a measure of intellectual capacity.
- **Academic Integrity Mode C** is the permissive-by-default posture; the domain
  does not police academic conduct.
- **Decision support never adopts a decision.** Planning produces proposals that
  require explicit user confirmation.

## Entities

Fourteen semantic entity types are declared (surfaced through the canonical
Entity/KnowledgeItem bindings and the `entity_types` field of University
resources — they are not new persistent classes):

| Entity |
|--------|
| `academic_requirement` |
| `academic_year` |
| `adaptation` |
| `assignment` |
| `credit` |
| `deadline` |
| `degree` |
| `exam_attempt` |
| `examination` |
| `grade` |
| `professor` |
| `semester` |
| `subject` |
| `university` |

## Resources

Twelve resource kinds are declared, each reusing the canonical provenance /
temporality / reliability / sensitivity contracts:

| ID | Adapter | Sensitivity |
|----|---------|-------------|
| `university.academic_record` | `cognitive.record` | `SENSITIVE` |
| `university.assignment` | `cognitive.document` | `PERSONAL` |
| `university.email` | `cognitive.message` | `PERSONAL` |
| `university.examination_schedule` | `cognitive.schedule` | `PERSONAL` |
| `university.grade` | `cognitive.record` | `SENSITIVE` |
| `university.memory_entry` | `cognitive.memory` | `PERSONAL` |
| `university.note` | `cognitive.note` | `PERSONAL` |
| `university.regulation` | `cognitive.document` | `PERSONAL` |
| `university.study_session` | `cognitive.event` | `PERSONAL` |
| `university.subject_guide` | `cognitive.document` | `PERSONAL` |
| `university.university_calendar` | `cognitive.calendar` | `PERSONAL` |
| `university.user_message` | `cognitive.message` | `PERSONAL` |

Resource semantics preserve the safety model:

- `university.email` represents an existing email or email context. It does
  **NOT** authorize sending.
- `university.memory_entry` represents personal memory and never overrides
  Academic State.
- `university.regulation` carries `expiration_required=True` for external
  checks of changing standards.

## Profile

`UniversityProfile` is a conservative academic profile with:

- Minimum confidence: `0.75`
- Reasoning depth: `STANDARD`
- Maximum questions: `10`
- Allowed inferences: observed facts, source authority by attribute,
  contradictions, hypotheses, open questions, and planning/preparation
  proposals
- **Prohibited inferences**: capacity inference, intellectual capacity,
  psychometric inference, academic decision adoption, sensitive inference
- Memory: read-only (proposals only)
- Production: draft only (`allow_final=False`), no external action
- **21 prohibited actions** encoding the safety model, including
  `academic_decision_adoption`, `email_sending`, `formal_procedure_submission`,
  `enrollment_registration`, `official_record_modification`,
  `calendar_event_creation`, `task_creation`, `capacity_inference_from_performance`,
  `academic_integrity_mode_a`, `academic_integrity_mode_b`,
  `sensitive_inference_persist`, `export`, and `shell_execution`

## Rules

Ten rules are registered. Source authority is resolved **per-attribute**, never
by a global naive ranking; a source that does not supply an attribute never
competes for it.

| ID | Name | Key behavior |
|----|------|--------------|
| `university.academic_contradiction` | `AcademicContradictionRule` | material + unresolved fails **closed** (`MATERIAL_CONTRADICTION_BLOCKED`) |
| `university.academic_deadline` | `AcademicDeadlineRule` | deadline is a fact, never auto-scheduled |
| `university.academic_decision_preservation` | `AcademicDecisionPreservationRule` | decision support never adopts a decision |
| `university.academic_dependency` | `AcademicDependencyRule` | reports blocked prerequisites, never auto-enrols |
| `university.academic_integrity` | `AcademicIntegrityRule` | Mode C permissive by default; unknown mode blocked |
| `university.academic_source_authority` | `AcademicSourceAuthorityRule` | official dominates per attribute, `ATTRIBUTE_AUTHORITY` |
| `university.academic_workload` | `AcademicWorkloadRule` | workload overcommit flagged as a hypothesis/risk |
| `university.ects_consistency` | `ECTSConsistencyRule` | ECTS/declared-hours inconsistency flagged as a hypothesis |
| `university.exam_attempt` | `ExamAttemptRule` | attempt limit reported, never authorizes a retake |
| `university.observed_performance_capacity` | `ObservedPerformanceCapacityRule` | performance never implies capacity (`CAPACITY_INFERENCE_BLOCKED`) |

## Operations

Eleven operations are registered. No operation sends email, submits procedures,
mutates the official university system, or adopts a decision. An operation
without a provided implementation is registered **UNAVAILABLE** (fail-closed).

| ID | Type | Approval | Required resource |
|----|------|----------|-------------------|
| `university.analyse_performance` | `ANALYSIS` | No | `university.grade` |
| `university.compare_semesters` | `ANALYSIS` | No | `university.academic_record` |
| `university.create_study_plan` | `PLANNING` | Yes | `university.academic_record` |
| `university.generate_academic_summary` | `PREPARATION` | No | `university.academic_record` |
| `university.plan_semester` | `PLANNING` | Yes | `university.academic_record` |
| `university.prepare_assignment` | `PREPARATION` | No | `university.assignment` |
| `university.prepare_exam` | `PREPARATION` | No | `university.examination_schedule` |
| `university.review_academic_record` | `ANALYSIS` | No | `university.academic_record` |
| `university.review_degree_completion` | `ANALYSIS` | No | `university.academic_record` |
| `university.track_deadlines` | `ANALYSIS` | No | `university.university_calendar` |
| `university.update_subject_status` | `MEMORY` | Yes | `university.grade` |

Output schemas are closed (recursive, `additionalProperties=False`) and encode
the safety contract:

- `prepare_exam` / `prepare_assignment` declare `preparation_only` and never
  authorize sending/submitting.
- `track_deadlines` declares `calendar_not_modified`.
- `analyse_performance` keeps `capacity_inferred` distinct from performance.
- `update_subject_status` declares `internal_academic_state_only` and
  `official_record_untouched`.
- `review_degree_completion` declares `official_action_none`.
- `plan_semester` / `create_study_plan` declare `adopted_decision` /
  `proposal_only`/`requires_user_confirmation`.

## Workflows

Seven workflows are registered, using the shared Workflow Engine with real
gating and dependencies.

| ID | Name | Approval gate |
|----|------|---------------|
| `university.academic_review` | `AcademicReview` | No |
| `university.assignment_preparation` | `AssignmentPreparation` | No |
| `university.degree_completion_review` | `DegreeCompletionReview` | No |
| `university.exam_preparation` | `ExamPreparation` | No |
| `university.reassessment_planning` | `ReassessmentPlanning` | Yes |
| `university.semester_planning` | `SemesterPlanning` | Yes |
| `university.tfg_planning` | `TfgPlanning` | Yes |

Safety ordering is enforced as a strict dependency chain:

- `load -> profile -> reason`: an analytical operation can never run before
  reasoning, and reasoning never before the profile/context are loaded.
- Every `EXECUTE_OPERATION` node transitively depends on `reason`.
- A terminal `COMPLETE` node always transitively depends on a `VALIDATE` node,
  so completion cannot bypass validation.
- No workflow proposes memory (the memory policy is read-only).
- No workflow enrols, registers, submits, or sends.
- Planning workflows carry a real `REQUEST_APPROVAL` gate on the transitive path
  to completion; without an approved gate they block into
  `WAITING_FOR_APPROVAL`.

## Permissions

The University permission policy is fail-closed:

- **Allowed**: `RESOURCE_READ`, `MEMORY_READ`, `OPERATION_EXECUTE`,
  `WORKFLOW_EXECUTE`, plus three narrow authorization-enriched paths that are
  never autonomous: `SEARCH_EXTERNAL` (OFFICIAL_ONLY-gated),
  `TASK_CREATE` and `SCHEDULE_MODIFY` (approval-gated)
- **Denied** (hard): memory write, file modify, goal update, external
  communication, sensitive inference (+persist), export, publication, external
  domain activate, irreversible change, knowledge delete, permission modify,
  and all medical/legal/financial decisions/actions/spend
- **Approval-gated** (denied by default, reachable only with a valid scoped
  approval — not hard-denied): `TASK_CREATE`, `SCHEDULE_MODIFY`, and inbound
  `DOMAIN_CROSS_ACCESS`
- **Hard-denied external effects**: `COMMUNICATION_EXTERNAL`, `EXPORT`, and
  `FILE_MODIFY`; approval metadata does not override the absence of a base
  capability grant or an explicit prohibition
- **External verification OFFICIAL_ONLY**: `SEARCH_EXTERNAL` is denied without
  a source and denied for any non-official source class; only an `OFFICIAL_ONLY`
  source is accepted, and the permitted search is read-only verification that
  never authorizes an action
- **Autonomy**: `maximum_autonomy_level=0`, no reversible or irreversible
  autonomous changes

Calendar and task mutation are reachable only through a valid scoped approval;
`update_subject_status` remains INTERNAL Academic State only. University grants
no outbound cross-domain access (`allow_cross_domain_access=False`) and never
adopts a supporting domain's permissions.

## Fallback

University composes with General Domain as fallback. A University signal selects
University when authorized and sufficiently supported; a University signal that
is ineligible (unauthorized, denied, or disabled) does **NOT** silently degrade
to General — resolution fails closed. Without a University signal, General
fallback remains permitted.

## Health→University Projection

Health→University defaults to **minimal constraint projection** (hybrid mode):

- Detailed clinical context is NOT transferred by default. Only an authorized
  minimal functional constraint (e.g. reduced available workload) may enter
  University, and only when relevant and permitted.
- The University package never reads a Health store directly; the workload rule
  consumes an *authorized constraint projection* rather than fetching Health
  records.
- Supporting-domain participation must never widen University permissions; the
  most restrictive effective policy wins.

## Presentation

The presentation policy preserves provenance, uncertainty, source authority by
attribute, facts/interpretations/hypotheses, contradictions, open questions,
planning proposals, and possible actions. It never elevates confidence, presents
recommendations as decisions, hides sources, treats hypotheses as facts, or
conflates observed performance with capacity.

## Trace

University composes caller-supplied typed references into the canonical Phase
10.17 trace contracts. The contribution is domain-scoped and PRIMARY. It does
not fabricate missing references: resource/profile/rule/operation/workflow/
permission/approval references appear only when supplied by the caller. The
resolution context/result and composition IDs are caller-supplied, and a shared
`DomainTraceAssembler` produces the canonical trace. Traces remain reference-only
and never contain chain of thought, private prompts, secrets, or credentials.

## Memory

University uses the common memory of Phase 10.18 exclusively:

- **Read**: `DomainMemoryViewRequest` for `domain:university`
- **Write**: Only proposals (`DomainMemoryProposalSnapshot` +
  `DomainMemoryProposalBinding`), with `requires_confirmation=True` and no
  override

No separate memory store is created.

## Registries

University Domain integrates with:

- `DomainRegistry` (definition)
- `InMemoryDomainProfileRegistry` (profile)
- `InMemoryDomainResourceRegistry` (resources)
- `InMemoryReasoningRuleRegistry` (rules)
- `InMemoryDomainOperationRegistry` (operations)
- `InMemoryDomainWorkflowRegistry` (workflows)
- `DomainPermissionRegistry` (permissions)

## Canonical Catalog

The single source of truth for University Domain structural IDs is
`cmm/domains/university/catalog.py`. It exports:

- `CANONICAL_UNIVERSITY_ENTITY_TYPES` — the 14 entities
- `CANONICAL_UNIVERSITY_RESOURCE_IDS` — the 12 resources
- `CANONICAL_UNIVERSITY_RULE_IDS` — the 10 rules
- `CANONICAL_UNIVERSITY_OPERATION_IDS` — the 11 operations
- `CANONICAL_UNIVERSITY_WORKFLOW_IDS` — the 7 workflows

All University modules (`definition.py`, `operations.py`, `rules.py`,
`resources.py`, `workflows.py`) import from this catalog rather than
re-declaring tuples. Resource IDs and rule IDs are canonically sorted.

## Atomic Registration

`register_university_domain()` is atomic via **validation-first** semantics:

1. All inputs are validated against every registry *before* the first mutation.
2. If any validation fails, no registry is modified — proven by a counting spy
   asserting `register_calls == 0`.
3. Duplicate domain / profile / resource / rule / operation / workflow /
   permission entries, unknown/mismatched/invalid-signature operation
   implementations, and pre-registered permission policies are all detected
   before any registration occurs.
4. Pre-existing entries in any registry are preserved.
5. If a post-mutation failure occurs, snapshots are captured before mutation and
   restored, rolling back every registry to its prior state.
6. Permission prevalidation only swallows "not found"; an unrelated error is
   never broadly swallowed as "already registered".

## Public API

```python
from cmm.domains.university import (
    UNIVERSITY_DOMAIN_ID,
    build_university_domain_definition,
    build_university_profile,
    build_university_resource_definitions,
    build_university_rules,
    build_university_operation_definitions,
    build_university_workflow_definitions,
    build_university_permission_policy,
    build_university_trace_reference,
    build_university_memory_view_request,
    build_university_presentation_policy,
    register_university_domain,
)
```

## Restrictions

- No autonomous academic action.
- No email sending or submission of formal procedures.
- No enrollment/registration.
- No modification of the official academic record.
- No direct store access.
- No separate/persistent memory (read-only + proposals).
- No parallel University engines or infrastructure.
- No side effects on import.
- No catch-all behavior.

## Non-Objectives

This phase does not implement Health, Relationships, Opposition, Reflection,
Concerns, Languages, Nil, Sport, or Life Plan domains. It does not access real
university systems, send communications, submit procedures, modify the official
record, create calendar/task events autonomously, adopt academic decisions,
infer intellectual capacity, or execute arbitrary tools.
