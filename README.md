# CMM OS

**CMM OS (Code Management Machine Operating System)** is an AI-native software engineering system that turns high-level intent into structured, inspectable, validated, and reversible execution flows.

Instead of allowing an AI model to edit a repository through unstructured text or arbitrary commands, CMM OS separates reasoning, planning, execution, validation, memory, and rollback behind explicit contracts.

> **Current release:** `v0.7.0`  
> **Implemented:** Phases 0–6  
> **Automated test baseline:** 642 passing tests  
> **License:** Apache-2.0

## Why CMM OS

AI-assisted development is useful, but direct model-to-filesystem access is difficult to trust.

CMM OS is built around a different principle:

```text
User intent
    ↓
Technical reasoning
    ↓
Structured plan
    ↓
Typed semantic operations
    ↓
Controlled execution
    ↓
Validation
    ↓
Result, diff and rollback evidence
```

The system is designed so that changes can be inspected, reproduced, validated, rejected, or reverted without relying on opaque free-form editing.

## Current architecture

```text
User Goal
  |
  v
Technical Reasoner and Planning
  |
  +-- Development Execution Runtime
  |   `-- CompositeExecutor
  |       |-- FilesystemExecutor
  |       |-- PythonExecutor
  |       `-- GitExecutor
  |
  `-- Architectural Transformation Pipeline
      |-- DAG planning and typed preconditions
      |-- Impact analysis and reference graph
      |-- LibCST and filesystem executors
      |-- Project validation
      `-- Byte-accurate rollback
```

### Main layers

- **Semantic Kernel** — common operation, result, executor, registry, validation, and runtime contracts.
- **Semantic Python Engine** — structural discovery and safe Python modifications.
- **Assisted Development** — repository analysis, structured planning, dry-run, approval, execution, validation, and diff.
- **Autonomous Development Loop** — bounded retries, failure classification, correction, re-planning, and rollback.
- **Technical Memory** — persistent project model used by the reasoner and planners.
- **Execution Layer** — controlled filesystem, Python, and Git operations through a composite executor.
- **Architectural Transformation Engine** — validated project-wide transformations with impact analysis and recovery.

## Implemented capabilities

### Semantic Python Engine

CMM OS supports semantic indexing and discovery of:

- modules;
- classes;
- functions;
- methods;
- imports;
- symbols;
- qualified and nested scopes.

Implemented semantic operations:

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

### Assisted and autonomous development

The development workflow can:

- analyze a Python repository;
- select relevant context;
- obtain a structured plan from a configurable provider;
- convert that plan into semantic operations;
- show the plan before execution;
- run in dry-run mode;
- require explicit human approval;
- execute operations through the semantic runtime;
- validate Python AST and compilation;
- generate a unified diff;
- stop at the first failure;
- restore modified files on failure;
- retry and re-plan within a bounded autonomous loop.

### Execution layer

The execution runtime routes registered operations through controlled executors:

```text
filesystem.* → FilesystemExecutor
python.*     → PythonExecutor
git.*        → GitExecutor
```

Supported Git inspection includes:

```text
git.status
git.current_branch
git.list_branches
git.log
git.diff
git.show
git.list_tags
```

Mutation is constrained to registered operations. CMM OS does not expose unrestricted shell execution as its normal execution model.

### Architectural transformations

The transformation engine includes:

- deterministic DAG planning;
- typed global and per-step preconditions;
- topological execution;
- project impact analysis;
- static reference resolution;
- import rewriting;
- pre- and post-impact comparison;
- final project validation;
- byte-accurate rollback;
- structured execution results.

Implemented transformations include:

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

Ambiguous, dynamic, unsafe, or unsupported cases are rejected before mutation where the declared static scope cannot guarantee a safe result.

## Project status

| Phase | Capability | Status |
| --- | --- | --- |
| 0 | Foundations and semantic kernel | Complete |
| 1 | Semantic Python Engine | Complete |
| 2 | Assisted self-development | Complete |
| 3 | Autonomous development loop | Complete |
| 4 | Persistent technical memory | Complete |
| 5 | Autonomous execution layer | Complete |
| 6 | Architectural transformations | Complete |
| 7 | Continuous validation | Planned |
| 8 | Cognitive Layer | Planned |
| 9 | Autonomous Agent Runtime | Planned |
| 10 | Domain Intelligence | Planned |
| 11 | Integrated stable platform | Planned |

Phases 0–6 were audited against explicit implementation requirements. The current baseline is **642 passing tests with no failures or skips**.

See the technical audit and full roadmap for the supporting evidence and future architecture.

## Roadmap

The next stages evolve CMM OS from a software-engineering runtime into a general, controlled AI operating platform:

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
Integrate the system into a stable local platform
```

- **Phase 7 — Continuous Validation:** reusable validation policies, affected tests, static analysis, security checks, artifacts, observability, CI integration, and commit gates.
- **Phase 8 — Cognitive Layer:** resources, provenance, epistemic knowledge models, temporal reasoning, contradictions, confidence, information gaps, questions, sessions, and structured reasoning traces.
- **Phase 9 — Autonomous Agent Runtime:** persistent goals, observations, planning, policy evaluation, approvals, budgets, execution, validation, recovery, and outcome evaluation.
- **Phase 10 — Domain Intelligence:** reusable domain packs, profiles, rules, workflows, operations, permissions, memory policies, and cross-domain coordination.
- **Phase 11 — Stable Integrated Platform:** orchestration, backend and API, storage, migrations, local Docker runtime, UI, observability, backup, recovery, and complete end-to-end integration.

Read the complete roadmap in [`ROADMAP.md`](ROADMAP.md).

## Installation

### Requirements

- Python 3
- Git

Clone the repository and create an isolated environment:

```bash
git clone https://github.com/monteromartinchristian-blip/CMM-OS.git
cd CMM-OS

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

## Usage

### Run a semantic operation

```bash
python -m cmm run 'replace method hello in class User' --project /path/to/project
```

### Preview an assisted development plan

```bash
python -m cmm develop \
  "create class User in app.py" \
  --project /path/to/project \
  --dry-run
```

### Execute with explicit approval bypass

```bash
python -m cmm develop \
  "create class User in app.py" \
  --project /path/to/project \
  --yes
```

### Run the bounded autonomous loop

```bash
python -m cmm develop \
  "create class User in app.py" \
  --project /path/to/project \
  --autonomous \
  --max-attempts 2 \
  --yes
```

Use `--yes` only in controlled environments where the planned changes have already been reviewed or the execution is intentionally automated.

## Running tests

Run the complete suite from the project virtual environment:

```bash
.venv/bin/python -m pytest -q
```

Current audited baseline:

```text
642 passed
0 failed
0 skipped
```

## Project structure

```text
CMM-OS/
├── cmm/               # Development, memory, planning, execution and transformations
├── cmm_agent/         # Compatibility and provider integrations
├── kernel/            # Semantic contracts, runtime and Python engine
├── runtime/           # Runtime-related components
├── scripts/           # Project scripts
├── docs/              # Technical documentation
├── tests/             # Unit, integration and end-to-end tests
├── README.md
├── ROADMAP.md
├── requirements.txt
├── LICENSE
└── .gitignore
```

## Design principles

- explicit contracts over implicit model behavior;
- structured operations over arbitrary edits;
- deterministic planning where possible;
- separation of reasoning, planning, execution, and validation;
- thin executors with reusable services;
- least-privilege execution;
- reversible changes;
- human approval for sensitive operations;
- structured results suitable for humans and future agents;
- provider independence;
- comprehensive automated testing.

## Documentation

The repository documentation is being organized around:

- architecture and public contracts;
- phase audits;
- implementation roadmap;
- usage guides;
- validation and security;
- release history and release process;
- contribution guidelines.

The detailed Phase 0–6 audit records implementation evidence, test evidence, limitations, and closure criteria for every completed phase.

## Contributing

CMM OS is in active development. Contributions should preserve the project’s core guarantees:

1. use registered and typed operations;
2. keep executors focused and free of planning logic;
3. add or update automated tests;
4. preserve validation and rollback behavior;
5. document public contracts and architectural decisions;
6. avoid introducing unrestricted execution paths.

A dedicated `CONTRIBUTING.md` will define the complete contribution workflow.

## Security

Please do not publish suspected vulnerabilities in a public issue.

A dedicated `SECURITY.md` will define supported versions and the private disclosure process. Until then, report security concerns directly to the repository owner.

## Release

Current release: **v0.7.0**

This release closes Phases 0–6 and integrates the completed architectural transformation engine.

Release notes, changelog, compatibility information, and migration guidance will be maintained alongside future tagged releases.

## License

CMM OS is licensed under the [Apache License 2.0](LICENSE).

Copyright 2026 Christian Montero Martín.
