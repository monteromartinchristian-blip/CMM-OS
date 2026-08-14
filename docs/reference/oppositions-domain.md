# Oppositions Domain — Reference

## Domain ID

`domain:oppositions`

## Overview

The Oppositions Domain specializes CMM OS for public competitive examinations
(oppositions): public bodies and alternative routes, official calls, syllabi,
topics and blocks, exam milestones, deadlines and requirements, merits, study
plans, study progress, revision, mock exams, scores, workload and feasibility,
risks, alternative routes, and strategy review — without ever acting on an
official public-body system.

It is a declarative, composable layer over the existing Domain Intelligence
infrastructure. It does **not** create parallel engines, separate storage, or
direct runtime access. It reuses the canonical Entity, Resource, Rule,
Operation, Workflow, Permission, Trace, Memory, Presentation, Resolution, and
Integration contracts.

The phase-10.23 safety posture:

- **No autonomous external action.** Nothing registers, submits an application,
  signs, pays a fee, uploads formal documents, impersonates the user, withdraws
  an application, or modifies official public-body records.
- **External verification is read-only and OFFICIAL_ONLY.** Arbitrary search and
  non-official sources are denied.
- **Official Opposition State ≠ CMM Opposition Strategy State ≠ Personal Memory.**
  Grounded official facts, internal planning state, and historical memory stay
  separate; memory never silently becomes current official state, and a proposal
  is not an adopted strategy.
- **Performance ≠ capacity; one mock ≠ trend.** Observed/point performance is
  never converted into intelligence, fixed capacity, or a guaranteed official
  result.
- **Decision support never adopts a decision.** Plans, scenarios, and route
  comparisons produce proposals requiring explicit user confirmation; the active
  target is never changed silently.
- **Call monitoring is semantic.** In the presence of an active objective and
  missing/stale/conflicting/undergrounded call state, the domain emits a
  structured official-verification requirement. It never schedules, polls, or
  opens a browser.

## Entities (14)

Semantic entity types, surfaced through the canonical Entity/KnowledgeItem
bindings and the `entity_types` field of Opposition resources (not new classes):

`opposition`, `public_body`, `call`, `exam`, `syllabus`, `topic`, `block`,
`mock_exam`, `score`, `study_session`, `deadline`, `requirement`, `merit`,
`alternative_route`.

## Resources (11)

Definitions are surfaced in `cmm/domains/oppositions/resources.py` using the
shared resource contracts. The `calendar_event`, `note`, `user_message`,
`memory_entry`, and external-source content reuse shared cognitive adapters and
are not duplicated.

| Resource ID | Kind |
|---|---|
| `oppositions.calendar_event` | calendar_event |
| `oppositions.external_official_source` | external_official_source |
| `oppositions.memory_entry` | memory_entry |
| `oppositions.mock_exam` | mock_exam |
| `oppositions.note` | note |
| `oppositions.official_call` | official_call |
| `oppositions.regulation` | regulation |
| `oppositions.score_record` | score_record |
| `oppositions.study_plan` | study_plan |
| `oppositions.syllabus` | syllabus |
| `oppositions.user_message` | user_message |

A resource existing is **not** the same as a fact being authoritative. Resource
metadata (e.g. `official_capable`) marks capability only; it never creates truth.

## Rules (6)

All rules are pure/deterministic and reuse the shared reasoning contracts:

| Rule | ID |
|---|---|
| OfficialCallPriorityRule | `oppositions.official_call_priority` |
| OppositionTemporalValidityRule | `oppositions.temporal_validity` |
| SyllabusCoverageRule | `oppositions.syllabus_coverage` |
| StudyFeasibilityRule | `oppositions.study_feasibility` |
| MockExamInterpretationRule | `oppositions.mock_exam_interpretation` |
| AlternativeRouteRule | `oppositions.alternative_route` |

### OfficialCallPriorityRule

Source authority is resolved **by attribute** and **scope**, never by a naive
global ranking or by recency. A caller `official=True` label never fabricates
authority; provenance is not truth; a missing usable reference cannot confirm a
decision-critical material fact. Equal top authority with compatible value
corroborates; equal top authority with incompatible value stays unresolved with
a verification need. Supersession requires grounded, current, scope-compatible
records and at least the target's authority. Expired history stays historical.
Malformed scope never becomes global scope. Resolution is input-order invariant.

### OppositionTemporalValidityRule

Preserves distinct temporal states: current/applicable, stale/expired/superseded,
future, unknown, conflicting, missing, malformed. A bare date string is never a
confirmed official deadline; current status requires grounding. Decision-critical
missing/stale/conflicting/undergrounded facts produce a structured
`READ_ONLY + OFFICIAL_ONLY` verification need. The rule never creates a calendar
event. With an active objective and stale/unknown call state it emits a semantic
call-monitoring requirement (no scheduler, no daemon, no browser automation, no
notification).

### SyllabusCoverageRule

Evaluation is multidimensional (studied/exposure, depth, revision, review-due /
retention risk, mock-linked, pending, unknown). Duplicate topic identities are
not double-counted; identityless topics cannot establish complete coverage; a
valid empty collection is distinct from absent/malformed; forgetting is never
proven by elapsed time alone; an aggregate percentage never overrides
contradictory topic-level evidence. A duplicate topic identity with incompatible
studied states (e.g. `studied=yes` and `studied=no`) is preserved as a conflict
and blocks completeness; the domain never silently picks one state.

### StudyFeasibilityRule

Runs the staged pipeline: validate evidence → hard constraints → available
capacity → target-date feasibility → valid scenarios → trade-offs → proposal.
Hard constraints always precede preferences. Target-date feasibility is a real
hard gate: positive remaining work with a zero-day target window is never
called feasible. Health and University participate only through minimal
authorized projections where `authorized is True` (literal boolean only —
`"true"`/`"false"`/`1`/`0` do not authorize); such supporting-domain caps may
never widen a known primary-domain capacity — the most-restrictive constraint
wins. No plan is silently adopted.

### MockExamInterpretationRule

Keeps one observation ≠ trend. A trend requires enough comparable (same/compatible
format and scoring **and scoring base/denominator**), temporally ordered evidence.
Incomparable mocks are never naively combined; dates must be parseable chronology
(arbitrary strings like `"zzz"` are not temporal ordering); unknown/malformed
chronology blocks a temporal trend; duplicate identities are not double-counted,
and incompatible duplicate identities become conflicting evidence that cannot
drive a trend; input order does not change the semantics. Speed, knowledge, and
format/process errors stay separate where evidence permits. No intelligence,
capacity, or pass guarantee is inferred.

### AlternativeRouteRule

Compares primary vs alternatives with trade-offs and uncertainty, but
`alternative considered ≠ alternative selected ≠ primary target abandoned`. A
better computed scenario is still a proposal; hard constraints beat preferences;
the active target changes only through explicit higher-layer user decision
semantics and strategy versioning. Conflicting duplicate alternative-route ids
are unresolved/blocked and can never be the basis for an automatic
recommendation; input order does not change the normalized semantics.

## Versioned strategy (DP-023)

Three-state separation:

- **Official Opposition State**: grounded external facts (call, deadline, exam
  date, syllabus, regulation, requirements, merits).
- **CMM Opposition Strategy State**: internal planning/decision state (target,
  alternatives under review, target date, plan version, milestones, sequencing,
  selected scenario after explicit adoption, constraints, revision strategy,
  review criteria, user priorities).
- **Personal Memory**: historical/user context under the shared memory policy
  (proposal-only; `allow_write=False`).

A material strategy change preserves previous version, proposed change, reason,
evidence/constraints, actor, adoption time when adopted, target relation,
uncertainty, and a trace reference. Official fact changes may invalidate
assumptions and trigger a strategy-review need but never silently rewrite a
user-owned strategy decision.

## Operations (10)

Declarative definitions in `cmm/domains/oppositions/operations.py` using strict
schemas and minimal `required_resources` (strict AND semantics). Operations
without a provided implementation are registered as **UNAVAILABLE** (fail-closed).

- `oppositions.create_study_plan` — structured proposal; never registers, mutates
  the calendar, switches the target, or persists adoption by itself.
- `oppositions.divide_syllabus` — structures grounded/current-known syllabus;
  unresolved material syllabus version keeps output conditional; never invents
  official content.
- `oppositions.track_progress` — internal analysis; no direct write.
- `oppositions.review_mock_exam` — grounded MockExamInterpretation semantics; no
  capacity/intelligence inference.
- `oppositions.compare_bodies` — trade-offs/proposals only; no target change.
- `oppositions.review_call` — authority, temporal validity, requirements,
  deadlines, contradictions/gaps; read-only `OFFICIAL_ONLY` boundary; no
  registration/submission.
- `oppositions.generate_weekly_review` — weekly synthesis (monitoring state,
  progress, coverage/revision, mocks, capacity, risks, gaps, next proposed
  actions); no automatic strategy adoption.
- `oppositions.identify_risks` — structured risks only; risk ≠ certainty.
- `oppositions.generate_revision_plan` — revision proposal grounded in coverage
  and time; elapsed time alone ≠ forgetting.
- `oppositions.update_progress` — structured internal update proposal only; never
  mutates official systems, calendar, tasks, or memory.

## Workflows (7)

Built on the shared Workflow Engine with real dependency/gating semantics
(`load → profile → reason` prefix; `COMPLETE` transitively depends on `VALIDATE`).

| Workflow | ID |
|---|---|
| Opposition Setup | `oppositions.setup` |
| Weekly Study Review | `oppositions.weekly_review` |
| Mock Exam Review | `oppositions.mock_exam_review` |
| Call Analysis | `oppositions.call_analysis` |
| Syllabus Revision | `oppositions.syllabus_revision` |
| Alternative Route Comparison | `oppositions.alternative_route_comparison` |
| Exam Readiness Review | `oppositions.exam_readiness` |

Long-term preparation may exist without a currently open call, but call
uncertainty remains explicit. Weekly review includes call monitoring as a
required concern for active goals. Call Analysis carries an
`OFFICIAL_ONLY + read_only` verification gate. Alternative Route Comparison ends
in an approval gate (proposal only) and never silently changes the target. Exam
Readiness Review returns explicit uncertainty and never guarantees passing.

## Permissions

Fail-closed policy in `cmm/domains/oppositions/permissions.py`:

- Autonomous surface: `RESOURCE_READ`, `MEMORY_READ`, `OPERATION_EXECUTE`,
  `WORKFLOW_EXECUTE`, plus narrowed `SEARCH_EXTERNAL` (official-only),
  `TASK_CREATE`, `SCHEDULE_MODIFY` (approval-gated).
- Hard-denied: memory write, file modification, goal update, external
  communication, export, publication, irreversible change, sensitive inference,
  finance, external models, etc.
- Calendar/task mutation is approval-gated. Inbound cross-domain projection is
  scoped and approval-gated; supporting domains can never widen Opposition
  permissions (most-restrictive policy wins).

## Cross-domain projections

- **Health → Oppositions**: minimal authorized functional constraint only
  (`authorized is True`). No direct Health store/import; no clinical detail is
  consumed/emitted; malformed authorization/cap fails closed.
- **University → Oppositions**: minimal authorized availability/load/deadline
  projection only. No direct University store/import; University state is never
  merged into Opposition strategy; malformed projections are rejected.
- **General**: remains the fallback domain and never becomes a bypass around
  Opposition official-source rules.

## Memory, presentation, trace

- **Memory**: proposal-only view/policy over shared Domain Memory (`allow_write=False`).
  May preserve user-confirmed target, versioned strategy decisions, study
  preferences, historical progress/mocks, constraints, prior comparisons, review
  history. Cannot silently establish current official state or an adopted
  strategy change.
- **Presentation**: the profile's conservative presentation policy preserves
  official vs unofficial, provenance, temporal state, scope, version, uncertainty,
  contradictions, gaps, strategy version, proposal vs adoption, point mock vs
  trend, coverage dimensions, feasibility constraints, risk, and approval/
  external-action state. It never converts proposal→decision, inference→fact,
  stale→current, risk→certainty, observation→trend, or comparison→abandonment.
- **Trace**: reference-only integration via shared trace contracts/assembler.
  No hidden chain-of-thought persistence; invalid references fail validation.

## Integration and rollback

`cmm/domains/oppositions/integration.py` registers the complete pack
validation-first (against every target registry before the first mutation),
captures exact registry snapshots, and restores exact snapshot parity on any
post-mutation failure. No partial registration and no incomplete rollback.

## Bootstrap, resolution, public API

`bootstrap.py` composes **General + Oppositions** on shared registries with
General as fallback. Health/University participate only through normal domain
resolution/composition when needed and authorized; their stores are never loaded
directly. `__init__.py` exposes only the intentional public API; fresh import
causes no registration, I/O, network, memory, model, or environment side effects.

## Known limits (deferred)

Continuous/monitored call tracking via Agent Runtime scheduling and Phase 11
integrations; official-source connectors/search adapters; notification delivery;
portal/application automation; calendar/task connectors; provider/model routing
via the Phase 11 Model Gateway; Life Plan ↔ Oppositions long-horizon composition;
autonomous multi-route optimization; public-body-specific plugins.

## Verification

Focused opposition tests, relevant General/Health/University/cross-domain
regressions, the full domain suite, the global suite, Ruff/static checks,
compileall, fresh-interpreter import, and git whitespace checks are part of the
phase-10.23 verification ladder.

## DP-023 status

`Implemented, pending final independent closure audit` — versioned strategy and constraints,
official-source verification, milestones and sequencing, trade-off analysis, and
realistic study planning are implemented; external official-source connectors are
deferred. The failure of the final independent closure audit is not claimed here.
