# CMM OS

**CMM OS is a local-first, provider-independent personal AI operating system in active development, designed for persistent knowledge, domain intelligence, goal-driven agents, and validated action.**

CMM OS turns interchangeable AI models into components of a larger persistent system. Rather than making one model or one chat interface the product, it provides the surrounding architecture for context, memory, structured knowledge, reasoning, goals, domain specialization, permissions, validation, controlled execution, recovery, and human supervision.

CMM OS began as **Code Management Machine Operating System**, a semantic software-engineering runtime. That engineering foundation remains part of the project, but it no longer defines the project's scope.

> **Current release:** `v0.8.0`<br>
> **Implemented:** Phases 0–9<br>
> **Automated test baseline:** 5409 passing tests<br>
> **License:** Apache-2.0

## What CMM OS is

CMM OS is designed as the persistent system around AI models:

- **Persistent** — knowledge, memory, goals, workflows, decisions, and traces can outlive a single conversation or provider.
- **Cognitive** — information is represented with provenance, temporal validity, epistemic type, confidence, contradictions, and explicit uncertainty.
- **Agentic** — persistent goals can be observed, planned, executed, validated, retried, paused, recovered, or escalated under policy.
- **Domain-aware** — the same shared core can be specialized through domain resources, reasoning profiles, rules, operations, workflows, and permissions.
- **Provider-independent** — local and remote models are replaceable resources rather than the permanent owner of context or memory.
- **Controlled** — permissions, validation, rollback, budgets, privacy policies, and human approval constrain side effects and autonomy.
- **Local-first** — the target platform is designed to remain useful without mandatory dependence on a proprietary cloud.

## What CMM OS is not

CMM OS is **not**:

- a foundation model;
- a model provider;
- a chat frontend tied to one vendor;
- an unrestricted autonomous agent;
- only a Python refactoring or software-engineering tool;
- a replacement for Claude, ChatGPT, Gemini, Qwen, GLM, Kimi, Ollama, or other model runtimes.

Those systems can become clients, providers, or execution resources behind CMM OS. The persistent value is intended to remain in provider-independent knowledge, memory, policies, domains, goals, workflows, and audit history.

## Why CMM OS

Most AI products make the model and its interface the center of the system. Context is often temporary, memory is provider-specific, tools are coupled to one runtime, and switching models can mean rebuilding the surrounding workflow.

CMM OS uses the opposite architecture:

```text
Users / clients / interfaces
            ↓
          CMM OS
            ↓
Context · Memory · Knowledge · Domains · Goals
Reasoning · Planning · Permissions · Validation
Execution · Recovery · Audit · Human approval
            ↓
Models · tools · files · services · integrations
```

The model is replaceable. The operating context is not.

## Current architectural state

The project has evolved in layers:

```text
Phases 0–6
Semantic kernel · planning · execution · technical memory
architectural transformation · reversible operations
        ↓
Phase 7
Continuous validation
        ↓
Phase 8
Structured knowledge · provenance · uncertainty · cognition
        ↓
Phase 9
Persistent goals · policy-bounded autonomous agent runtime
        ↓
Phase 10
Domain Intelligence — specialization of the shared system
        ↓
Phase 11
Stable Integrated Platform — orchestration, interfaces,
storage, model gateway, integrations and product runtime
```

The software-engineering runtime remains a first-class capability because it provides the typed execution, validation, rollback, and self-development foundations on which later phases build.

### Architectural principle

```text
One Kernel
One Cognitive Layer
One Knowledge Model
One Agent Runtime
One Validation System
One Memory
        +
Domain specialization
        +
Replaceable models and integrations
        +
Multiple user interfaces
```

CMM OS is therefore intended to become the stable layer between a person and whichever AI models, tools, services, or interfaces are most useful at a given time.

### Implementation status

The architecture is being delivered incrementally rather than presented as a finished product before the underlying capabilities exist.

**Implemented and audited foundation: Phases 0–9**

The current system already includes:

- a shared semantic kernel and typed execution contracts;
- structured planning and controlled operation execution;
- filesystem, Python, and Git execution through registered executors;
- reversible project-wide architectural transformations;
- persistent technical memory and project knowledge;
- continuous validation and commit gating;
- structured knowledge with provenance, temporal validity, confidence, contradictions, and uncertainty;
- a shared Cognitive Layer;
- persistent goals and a policy-bounded Autonomous Agent Runtime;
- validation, rollback, recovery, traces, and explicit human-approval boundaries.

**Current engineering phase: Phase 10 — Domain Intelligence**

Phase 10 specializes the shared system for real areas of work and life through domain resources, reasoning profiles, rules, operations, workflows, permissions, presentation policies, and controlled cross-domain composition.

**Planned integration phase: Phase 11 — Stable Integrated Platform**

Phase 11 will turn the existing engines into the complete product surface: orchestration, persistent application services, conversational interfaces, storage, integrations, a provider-independent Model Gateway, observability, configuration, backup and recovery, and reusable interfaces such as API, MCP, and CLI.

This distinction is deliberate: CMM OS already has substantial working infrastructure, while the complete personal-platform experience remains an active engineering objective.

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
| 7 | Continuous validation | Complete |
| 8 | Cognitive Layer | Complete |
| 9 | Autonomous Agent Runtime | Complete and audited |
| 10 | Domain Intelligence | Planned |
| 11 | Integrated stable platform | Planned |

Phases 0–9 have been implemented and audited against explicit requirements. The current baseline is **5409 passing tests with no failures or skips**.

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
5409 passed
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

The phase audits record implementation evidence, test evidence, architectural guarantees, limitations, and closure criteria for Phases 0–9.

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

Current release: **v0.8.0**

This release closes Phase 8 (Cognitive Layer), providing structured, typed, auditable, and deterministic knowledge processing.

For detailed documentation, see:
- [Cognitive Layer Architecture](docs/architecture/cognitive-layer.md)
- [Cognitive Layer Invariants](docs/architecture/cognitive-layer-invariants.md)
- [Cognitive Layer Public API Reference](docs/reference/cognitive-api.md)
- [Phase 8 Completion Audit](docs/audits/phase-8-completion.md)
- [Phase 9 Completion Audit](docs/audits/phase-9-completion.md)
- [Phases 8–9 Delta Audit](docs/audits/phases-8-9-delta-audit.md)
- [Release Notes v0.8.0](docs/releases/v0.8.0.md)

The implementation baseline now covers Phases 0–9. The next engineering
milestone is Phase 10 — Domain Intelligence. No release newer than `v0.8.0`
has been published yet.

## Project identity

**CMM OS** is the original open-source project created and maintained by **Christian Montero Martín**.

The name “CMM OS” identifies this original project and does not imply endorsement, affiliation, or official status for forks, modified versions, or derivative works.

For attribution and licensing details, see [`NOTICE`](NOTICE) and [`LICENSE`](LICENSE).

## License

CMM OS is licensed under the [Apache License 2.0](LICENSE).

Copyright 2026 Christian Montero Martín.
