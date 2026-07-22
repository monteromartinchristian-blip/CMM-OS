# CMM OS

CMM OS (Code Management Machine Operating System) is an AI-native software development operating system.

It transforms user intent into structured, validated, and testable execution flows instead of allowing direct, unstructured edits.

## CMM OS - Current Architecture (v0.7.0)

```text
User Goal
  |
  v
Technical Reasoner and Planning
  |
  +-- Development Execution Runtime
  |   `-- CompositeExecutor
  |       |-- ReadOnlyFilesystemExecutor
  |       |-- PythonExecutor
  |       `-- GitExecutor
  |
  `-- Architectural Transformation Pipeline
      |-- DAG planning and typed preconditions
      |-- Impact analysis and reference graph
      |-- LibCST/filesystem executors
      `-- Validation and rollback
```

### Layer responsibilities

- User Goal: natural-language objective provided by the user.
- Technical Reasoner: organizes available technical knowledge to support deterministic planning.
- Task Planner: converts the goal into an ordered execution plan.
- Action Planner: turns plan steps into atomic, validated actions.
- Execution Runtime: manages action lifecycle and execution state transitions.
- CompositeExecutor: primary execution entry point that routes actions by prefix.
- ReadOnlyFilesystemExecutor: handles read-only filesystem inspection actions.
- PythonExecutor: handles semantic Python actions through the Semantic Python Engine.
- GitExecutor: handles read-only Git repository inspection actions.
- Architectural Transformation Pipeline: plans and executes validated, reversible project-wide Python transformations.

## Current implemented capabilities

### Semantic Python Engine

- Python semantic indexing
- Class discovery
- Function discovery
- Method discovery
- Module description
- Symbol search

### Execution Layer

#### ReadOnlyFilesystemExecutor

- Read-only filesystem operations

#### PythonExecutor

- Semantic Python operations
- Delegation to the Semantic Python Engine

#### GitExecutor

Supported actions:

- git.status
- git.current_branch
- git.list_branches
- git.log
- git.diff
- git.show
- git.list_tags

#### CompositeExecutor

CompositeExecutor is a thin routing layer with no business logic.

It delegates execution based on action prefix:

- filesystem.* -> ReadOnlyFilesystemExecutor
- python.* -> PythonExecutor
- git.* -> GitExecutor

### Architectural transformations

- Deterministic DAG planning and typed preconditions
- Project impact analysis and advanced reference rewriting
- Byte-accurate rollback and final project validation
- `move_function`, `move_class`, `extract_method`, and `extract_module`
- Rename, move, split, and merge operations for modules
- Rename and move operations for packages

## Architectural principles

- Layered architecture
- Separation of responsibilities
- Thin executors
- Reusable services
- Validated and reversible execution
- Dependency injection where appropriate
- Comprehensive automated tests

## Project status

Completed

- ✓ Phase 0 - Foundations
- ✓ Phase 1 - Semantic Python Engine
- ✓ Phase 2
- ✓ Phase 3
- ✓ Phase 4
- ✓ Phase 5 - Execution Layer
- ✓ Phase 6 - Architectural Transformations

Current release:

v0.7.0

Automated test baseline: 642 passing tests.

## Roadmap

Phases 0–6 are complete. The next milestone focuses on reliability, release engineering, documentation, observability, API stability, regression coverage, packaging, and user experience.

## Project structure

```text
CMM-OS/
|-- cmm/
|-- cmm_agent/
|-- kernel/
|-- runtime/
|-- scripts/
|-- docs/
|-- tests/
|-- README.md
|-- requirements.txt
`-- .gitignore
```

## Installation

```bash
git clone https://github.com/monteromartinchristian-blip/CMM-OS.git
cd CMM-OS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running tests

```bash
.venv/bin/pytest
```

## License

Private project.
