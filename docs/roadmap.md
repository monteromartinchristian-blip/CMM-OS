# CMM OS Roadmap

This roadmap describes the evolution of **CMM OS (Code Management Machine Operating System)** from a semantic software-engineering runtime into a controlled, persistent, and extensible AI operating platform.

The roadmap distinguishes clearly between:

- **completed and audited capabilities**;
- **planned architecture**;
- **future implementation work**.

> **Current release:** `v0.7.0`  
> **Completed:** Phases 0–6  
> **Current test baseline:** 642 passing tests  
> **Next phase:** Phase 7 — Continuous Validation

---

## Roadmap overview

```text
Phases 0–6
Understand, transform, execute and remember
        ↓
Phase 7
Modify without degrading
        ↓
Phase 8
Reason with structured knowledge and uncertainty
        ↓
Phase 9
Pursue persistent goals within policy
        ↓
Phase 10
Specialize intelligence by domain
        ↓
Phase 11
Integrate everything into a stable local platform
```

| Phase | Name | Status |
| --- | --- | --- |
| 0 | Foundations and Semantic Kernel | Complete |
| 1 | Semantic Python Engine | Complete |
| 2 | Assisted Self-Development | Complete |
| 3 | Autonomous Development Cycle | Complete |
| 4 | Persistent Technical Memory | Complete |
| 5 | Development Execution Layer | Complete |
| 6 | Architectural Transformation Engine | Complete |
| 7 | Continuous Validation | Planned |
| 8 | Cognitive Layer | Planned |
| 9 | Autonomous Agent Runtime | Planned |
| 10 | Domain Intelligence | Planned |
| 11 | Stable Integrated Platform | Planned |

---

# Completed foundation

## Phase 0 — Foundations and Semantic Kernel

**Status:** Complete.

Phase 0 established the common execution model used across CMM OS.

Implemented:

- generic semantic operation contracts;
- structured results and plans;
- reusable executor contracts;
- executor registry and resolution;
- validation before and after execution;
- common semantic runtime;
- adapters for legacy and transformation operations;
- separation between the kernel and concrete domains.

**Outcome:** CMM OS gained a shared execution protocol instead of a collection of disconnected tools.

---

## Phase 1 — Semantic Python Engine

**Status:** Complete.

Phase 1 added structural understanding and safe modification of Python code.

Implemented:

- Python indexing;
- class, function, method, import, and symbol discovery;
- qualified and nested scope resolution;
- AST validation before and after edits;
- semantic operation dispatch;
- safe Python source transformation.

Supported operations:

```text
python.insert_method
python.replace_method
python.delete_method
python.rename_method
python.add_import
python.remove_import
python.create_class
python.rename_class
python.delete_class
```

**Outcome:** CMM OS can inspect and modify Python structure through typed semantic operations.

---

## Phase 2 — Assisted Self-Development

**Status:** Complete.

Phase 2 introduced the first end-to-end development workflow.

Implemented:

- `cmm develop`;
- repository analysis;
- relevant-context selection;
- configurable planning providers;
- structured development plans;
- conversion from plans to semantic operations;
- dry-run mode;
- explicit human approval;
- controlled execution;
- AST and compilation validation;
- unified diff generation;
- rollback on failure;
- structured execution results.

**Outcome:** CMM OS can turn a development goal into a reviewable and safely executable implementation plan.

---

## Phase 3 — Autonomous Development Cycle

**Status:** Complete.

Phase 3 added bounded autonomous correction.

Implemented:

- explicit iterative development loop;
- maximum attempt limits;
- structured failure classification;
- recoverable and non-recoverable failure handling;
- correction and re-planning;
- validation after every attempt;
- rollback between failed attempts;
- explicit success and abandonment criteria;
- protection against infinite loops.

**Outcome:** CMM OS can retry and correct failed development attempts without losing control of repository state.

---

## Phase 4 — Persistent Technical Memory

**Status:** Complete.

Phase 4 gave CMM OS a persistent technical model of the project.

Implemented:

- `TechnicalMemory`;
- persistent project indexing;
- architecture graph;
- modules, symbols, imports, and dependencies;
- technical reasoning;
- impact queries;
- incremental refresh;
- versioned JSON persistence;
- corruption recovery;
- planner integration;
- runtime integration.

**Outcome:** CMM OS no longer reasons only from the current command. It can reuse structured technical knowledge across executions.

---

## Phase 5 — Development Execution Layer

**Status:** Complete.

Phase 5 consolidated real project execution behind controlled executors.

Implemented:

- `CompositeExecutor`;
- filesystem operations;
- Python semantic operations;
- safe Git inspection and branch isolation;
- executor registry integration;
- sequential coordinated execution;
- error propagation;
- snapshots and rollback;
- unified diff;
- result packaging for human review;
- integration with memory, reasoner, planners, and the autonomous loop.

Execution routing:

```text
filesystem.* → FilesystemExecutor
python.*     → PythonExecutor
git.*        → GitExecutor
```

**Outcome:** CMM OS gained a reusable execution layer for real project changes without unrestricted shell access.

---

## Phase 6 — Architectural Transformation Engine

**Status:** Complete, audited, and released in `v0.7.0`.

Phase 6 extended CMM OS from local edits to project-wide architectural transformations.

Implemented:

- transformation contracts;
- DAG planning;
- typed preconditions;
- deterministic topological ordering;
- impact analysis;
- reference graph;
- static reference resolution;
- import rewriting;
- LibCST-based transformations;
- pre- and post-impact validation;
- project validation;
- byte-accurate rollback;
- structured transformation results.

Implemented transformations:

```text
move_function
move_class
extract_method
extract_module
rename_module
move_module
split_module
merge_modules
rename_package
move_package
```

Declared static limits include:

- reflection and dynamic references;
- ambiguous namespace packages;
- unsupported top-level side effects;
- cases where safe static rewriting cannot be guaranteed.

Unsafe or ambiguous cases are rejected before mutation.

**Outcome:** CMM OS can perform validated, reversible, project-wide Python refactoring while preserving structural integrity.

---

# Planned evolution

## Phase 7 — Continuous Validation

**Status:** Planned.  
**Next implementation target.**

### Objective

Build a reusable validation pipeline capable of proving that a change does not degrade the project.

### Main capabilities

- validation contracts and structured findings;
- formatter and lint integration;
- syntax and AST validation;
- affected-test selection;
- unit, integration, and full-suite execution;
- change-impact classification;
- static analysis;
- security checks;
- project-specific validators;
- validation policies;
- commit gate;
- artifacts, logs, metrics, and history;
- CLI, API, and CI integration.

### Core flow

```text
Detect changes
    ↓
Resolve validation policy
    ↓
Format and lint
    ↓
Syntax and AST checks
    ↓
Affected tests
    ↓
Full suite when required
    ↓
Static and security analysis
    ↓
Structured validation result
    ↓
Commit gate
```

### Completion outcome

CMM OS will be able to modify code and produce reproducible evidence showing:

- what was checked;
- what failed;
- which files and tests were affected;
- which findings are blocking;
- whether the change can be considered safe;
- whether it may pass the commit gate.

---

## Phase 8 — Cognitive Layer

**Status:** Planned.

### Objective

Create a shared cognitive infrastructure that converts heterogeneous resources into structured, traceable, temporally valid, and reusable knowledge.

### Main capabilities

- common resource model;
- provenance and temporal scope;
- epistemic knowledge model;
- facts, observations, inferences, hypotheses, opinions, and unknowns;
- evidence and source reliability;
- versioned knowledge store;
- logical knowledge graph;
- entity resolution;
- reasoning rules;
- domain-aware reasoning profiles;
- contradiction detection;
- temporal reasoning;
- confidence evaluation;
- information-gap analysis;
- dynamic question generation;
- persistent cognitive sessions;
- structured reasoning traces;
- controlled memory-update proposals;
- privacy, permissions, and sensitive-inference controls.

### Core flow

```text
Resources
    ↓
Knowledge extraction
    ↓
Knowledge model and store
    ↓
Reasoning context
    ↓
Rules and profiles
    ↓
Contradictions, confidence and gaps
    ↓
Question / pause / continue
    ↓
Reasoning result and trace
    ↓
Memory update proposal
```

### Completion outcome

CMM OS will be able to explain:

- what it knows;
- where that knowledge comes from;
- what it inferred;
- what remains uncertain;
- which contradictions exist;
- what information is missing;
- why it asks, pauses, or concludes.

---

## Phase 9 — Autonomous Agent Runtime

**Status:** Planned.

### Objective

Build a generic, policy-bounded runtime capable of pursuing persistent goals through observation, reasoning, planning, execution, validation, recovery, and outcome evaluation.

### Main capabilities

- persistent goal system;
- success criteria and constraints;
- goal prioritization and dependencies;
- observation engine;
- cognitive-layer integration;
- information-acquisition strategies;
- planner adapter;
- policy engine;
- autonomy levels;
- human approval system;
- action budgets;
- explicit runtime state machine;
- registered-operation execution;
- validation before and after actions;
- checkpoints and transaction boundaries;
- retry, re-observation, re-planning, rollback, and escalation;
- outcome evaluation;
- controlled knowledge and memory updates;
- agent traces;
- runtime event bus;
- persistence and recovery after restart;
- triggers and scheduling;
- declarative agent registry.

### Core loop

```text
Goal
    ↓
Observe
    ↓
Reason
    ↓
Resolve gaps
    ↓
Plan
    ↓
Evaluate policy
    ↓
Request approval when required
    ↓
Execute registered operations
    ↓
Validate
    ↓
Evaluate outcome
    ↓
Continue / retry / replan / rollback / pause / complete
```

### Completion outcome

CMM OS will move from executing isolated commands to maintaining persistent objectives and demonstrating why an objective was completed, paused, escalated, rolled back, or failed.

---

## Phase 10 — Domain Intelligence

**Status:** Planned.

### Objective

Specialize CMM OS for different areas of work and life without creating separate kernels, memories, planners, or agent runtimes.

### Shared architecture

```text
Same Kernel
Same Cognitive Layer
Same Knowledge Model
Same Agent Runtime
Same Planner
Same Validation System
Same Memory
    +
Domain resources
Domain profiles
Domain rules
Domain operations
Domain workflows
Domain permissions
Domain presentation
```

### Main capabilities

- domain contracts;
- installable and versioned Domain Packs;
- domain registry;
- discovery and atomic loading;
- domain validation;
- domain resolution;
- multi-domain composition;
- cross-domain coordination;
- domain-specific resources;
- domain reasoning profiles;
- domain rules;
- domain operations;
- domain workflows;
- domain permissions;
- presentation policies;
- domain traces;
- shared-memory views and controlled updates.

### Initial domains

```text
general
health
relationships
university
oppositions
reflection
concerns
languages
nil
sport
life-plan
project
```

### Completion outcome

CMM OS will adapt how it reasons, plans, validates, asks questions, requests approval, and presents results according to the active domain while preserving one coherent system.

---

## Phase 11 — Stable Integrated Platform

**Status:** Planned.

### Objective

Integrate all previous capabilities into a stable, observable, recoverable, and usable local-first platform.

### Main capabilities

- central orchestrator;
- unified backend and API;
- stable public contracts;
- persistent storage;
- schema versioning and migrations;
- backup and recovery;
- Docker-based local runtime;
- service lifecycle management;
- configuration and secrets management;
- authentication and authorization;
- conversational interface;
- goals, workflows, approvals, agents, and memory UI;
- artifacts and trace inspection;
- real-time updates;
- observability and health checks;
- error management and recovery;
- installation, update, and rollback flows;
- complete end-to-end validation;
- release and operational documentation.

### Platform flow

```text
User / UI / API / CLI
        ↓
Orchestrator
        ↓
Cognitive Layer
        ↓
Agent Runtime
        ↓
Planner and Workflows
        ↓
Execution and Validation
        ↓
Domain Intelligence
        ↓
Storage, Memory and Knowledge
        ↓
Observability, Recovery and UI
```

### Completion outcome

CMM OS will operate as a coherent local platform rather than a collection of engineering components.

---

# Release direction

The current `v0.7.0` release closes Phases 0–6.

Future versioning will follow implemented capabilities rather than planned phase numbers alone. Each release should include:

- tested implementation;
- release notes;
- changelog entry;
- compatibility information;
- known limitations;
- migration guidance when required;
- updated documentation;
- a green full validation pipeline.

The `1.0.0` milestone will represent a stable public platform contract, not merely the completion of a numbered phase.

---

# Roadmap principles

The following principles apply to all future phases:

- one shared kernel;
- explicit public contracts;
- structured inputs and outputs;
- provider independence;
- no unrestricted execution by default;
- least privilege;
- human approval for sensitive actions;
- validation before trust;
- reversible changes where possible;
- structured traces instead of hidden reasoning;
- temporal validity and provenance;
- persistent but controlled memory;
- no silent escalation of autonomy;
- no duplication of core infrastructure between domains or agents;
- complete unit, integration, and end-to-end testing;
- documentation as part of the definition of done.

---

# Detailed specifications

The full implementation specifications for Phases 7–11 are maintained separately because they define contracts, components, security requirements, test scenarios, implementation order, and closure criteria in much greater detail.

Recommended repository structure:

```text
docs/
└── roadmap/
    ├── README.md
    └── phases-7-11.md
```

This file should remain the concise public roadmap. The detailed specification should live in:

```text
docs/roadmap/phases-7-11.md
```

That separation keeps the project direction readable while preserving the complete engineering design.
