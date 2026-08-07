# General Domain — Reference

## Domain ID

`domain:general`

## Overview

The General Domain is the base domain for non-specialized requests, general
information analysis, common information organization, goal clarification,
prudent decision support, periodic reviews, and safe fallback when no
specialized domain applies.

It is a declarative, composable layer over the existing Domain Intelligence
infrastructure (Fases 10.1–10.18). It does not create parallel engines,
separate storage, or direct runtime access.

## Resources

Nine resource kinds are declared:

| ID | Kind | Adapter | Sensitivity | Reliability |
|----|------|---------|-------------|-------------|
| `general.user_message` | `user_message` | `cognitive.message` | `INTERNAL` | 0.5 |
| `general.conversation` | `conversation` | `cognitive.conversation` | `INTERNAL` | 0.5 |
| `general.calendar_event` | `calendar_event` | `cognitive.calendar` | `INTERNAL` | 0.7 |
| `general.note` | `note` | `cognitive.note` | `INTERNAL` | 0.6 |
| `general.document` | `document` | `cognitive.document` | `INTERNAL` | 0.7 |
| `general.memory_entry` | `memory_entry` | `cognitive.memory` | `INTERNAL` | 0.8 |
| `general.generic_task` | `generic_task` | `cognitive.task` | `INTERNAL` | 0.6 |
| `general.generic_goal` | `generic_goal` | `cognitive.goal` | `INTERNAL` | 0.6 |
| `general.external_source` | `external_source` | `cognitive.external` | `RESTRICTED` | 0.3 |

## Profile

`GeneralProfile` is a prudent, low-risk profile with:

- Minimum confidence: `0.55`
- Reasoning depth: `STANDARD`
- Maximum questions: `8`
- Memory: read-only (proposals only)
- No external actions
- No sensitive inference
- No persistent task/goal creation without approval

## Rules

Six rules are registered:

| ID | Name | Category |
|----|------|----------|
| `general.temporal_validity` | `GeneralTemporalValidityRule` | `temporality` |
| `general.source_reliability` | `GeneralSourceReliabilityRule` | `epistemic` |
| `general.ambiguity` | `GeneralAmbiguityRule` | `inference` |
| `general.permission` | `GeneralPermissionRule` | `safety` |
| `general.goal_clarification` | `GeneralGoalClarificationRule` | `inference` |
| `general.duplication` | `GeneralDuplicationRule` | `consistency` |

## Operations

Eight operations are registered:

| ID | Type | Approval |
|----|------|----------|
| `general.create_summary` | `ANALYSIS` | No |
| `general.build_timeline` | `ANALYSIS` | No |
| `general.compare_items` | `ANALYSIS` | No |
| `general.prepare_questions` | `PREPARATION` | No |
| `general.create_task` | `PLANNING` | Yes |
| `general.update_goal` | `PLANNING` | Yes |
| `general.generate_report` | `PREPARATION` | No |
| `general.search_knowledge` | `READ` | No |

Every operation is declared by the canonical bootstrap but remains **UNAVAILABLE**
by default (fail-closed) until a real implementation is explicitly injected via
`operation_implementations`. `general.create_task` and `general.update_goal`
have a proposal-only contract: their output schema requires `proposal` +
`binding`, and they never produce implicit direct effects.

## Workflows

Four workflows are registered:

| ID | Name |
|----|------|
| `general.information_review` | `InformationReview` |
| `general.goal_clarification` | `GoalClarification` |
| `general.decision_support` | `DecisionSupport` |
| `general.periodic_review` | `PeriodicReview` |

## Permissions

The General Domain permission policy is low-risk and fail-closed:

- **Allowed**: `RESOURCE_READ`, `MEMORY_READ`, `OPERATION_EXECUTE`
- **Denied**: `SEARCH_EXTERNAL`, `MODEL_EXTERNAL`, `MEMORY_WRITE`,
  `FILE_MODIFY`, `SCHEDULE_MODIFY`, `TASK_CREATE`, `COMMUNICATION_EXTERNAL`,
  `SENSITIVE_INFERENCE`, `EXPORT`, `IRREVERSIBLE_CHANGE`
- **Approval**: `TASK_CREATE`, `GOAL_UPDATE`
- **Autonomy**: `maximum_autonomy_level=1`

## Fallback

The canonical `build_standard_general_domain_bootstrap()` exposes a
`DefaultDomainResolver` configured with `domain:general` as `fallback_domain`.
General Domain is used as fallback only when:

1. No specialized domain candidate is applicable.
2. Resources are truly general.
3. The request is non-specialized.
4. The user explicitly requests it.
5. The resolver needs a safe fallback.

A specialized domain always prevails over General Domain when valid and
sufficiently supported. A specialized domain explicitly signaled but ineligible
(unauthorized or blocked by policy) does NOT silently degrade to General;
resolution fails closed. Without a specialized signal, General fallback remains
permitted. General Domain is never added as a supporting domain by default.

## Presentation

The presentation policy preserves uncertainty, provenance, contradictions,
epistemic kinds, warnings, and approval requirements. It never elevates
confidence, presents recommendations as decisions, hides sources, or converts
hypotheses into facts.

## Trace

General Domain composes caller-supplied typed references into the canonical
Phase 10.17 trace contracts. It does not fabricate missing references:
resource/profile/rule/operation/workflow/permission/approval references appear
only when supplied by the caller. The resolution context/result and composition
IDs are caller-supplied, and `DomainTraceAssembler` produces the canonical
trace. Traces remain reference-only and never contain chain of thought, private
prompts, secrets, or credentials.

## Memory

General Domain uses the common memory of Phase 10.18 exclusively:

- **Read**: `DomainMemoryViewRequest` for `domain:general`
- **Write**: Only proposals (`DomainMemoryProposalSnapshot` +
  `DomainMemoryProposalBinding`)

No separate memory store is created.

## Registries

General Domain integrates with:

- `DomainRegistry` (definition)
- `InMemoryDomainProfileRegistry` (profile)
- `InMemoryDomainResourceRegistry` (resources)
- `InMemoryReasoningRuleRegistry` (rules)
- `InMemoryDomainOperationRegistry` (operations)
- `InMemoryDomainWorkflowRegistry` (workflows)
- `DomainPermissionRegistry` (permissions)

## Canonical Catalog

The single source of truth for General Domain structural IDs is
`cmm/domains/general/catalog.py`.  It exports:

- `CANONICAL_GENERAL_OPERATION_IDS` — the 8 Phase 10.19 operations
- `CANONICAL_GENERAL_RULE_IDS` — the 6 Phase 10.19 rules
- `CANONICAL_GENERAL_RESOURCE_IDS` — the 9 resources
- `CANONICAL_GENERAL_WORKFLOW_IDS` — the 4 workflows
- `HISTORICAL_GENERAL_OPERATION_IDS` — 4 Phase 10.13 placeholders with
  different semantics, preserved for backward compatibility

All General Domain modules (`definition.py`, `operations.py`, `rules.py`,
`resources.py`, `workflows.py`) import from this catalog rather than
re-declaring tuples.  The Phase 10.13 `INITIAL_DOMAIN_OPERATION_IDS` and
`INITIAL_DOMAIN_REASONING_RULE_IDS` are historical partial catalogs covering
all domains; they do not collide with the Phase 10.19 canonical sets.

## Canonical Bootstrap

The recommended composition path is `build_standard_general_domain_bootstrap()`:

```python
from cmm.domains.general import build_standard_general_domain_bootstrap

bootstrap = build_standard_general_domain_bootstrap()
# bootstrap.domain_registry, bootstrap.profile_registry,
# bootstrap.resource_registry, bootstrap.rule_registry,
# bootstrap.operation_registry, bootstrap.workflow_registry,
# bootstrap.permission_registry
```

This factory creates fresh registries, registers the complete General Domain
atomically using the canonical catalog, and returns the composed system. No
global state is modified.

## Atomic Registration

`register_general_domain()` is atomic via **validation-first** semantics:

1. All inputs are validated against every registry *before* the first mutation.
2. If any validation fails, no registry is modified.
3. Duplicate IDs, unknown provided implementation IDs, and mismatched/conflicting
   provided implementations are detected before any registration occurs.
4. Pre-existing entries in any registry are preserved.
5. Retrying after fixing the cause of failure succeeds.

## Public API

```python
from cmm.domains.general import (
    build_general_domain_definition,
    build_general_profile,
    build_general_resource_definitions,
    build_general_rules,
    build_general_operation_definitions,
    build_general_workflow_definitions,
    build_general_permission_policy,
    build_standard_general_domain_bootstrap,
    register_general_domain,
)
```

## Restrictions

- No external actions are executed automatically.
- No direct store access.
- No separate memory.
- No parallel engines.
- No side effects on import.
- No catch-all behavior.

## Non-Objectives

This phase does not implement Health, Relationship, University, Opposition,
or Project domains. It does not access real calendars, send communications,
modify files, perform external searches, persist directly, call external
models, create persistent tasks autonomously, modify goals autonomously, make
medical/legal/financial decisions, or execute arbitrary tools.