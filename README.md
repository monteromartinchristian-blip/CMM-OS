# CMM OS

CMM OS (Code Management Machine Operating System) is an AI-native software development operating system.

It transforms user intent into structured, validated, and testable execution flows instead of allowing direct, unstructured edits.

## CMM OS - Current Architecture (v0.5.0)

```text
User Goal
  |
  v
Technical Reasoner
  |
  v
Task Planner
  |
  v
Action Planner
  |
  v
Execution Runtime
  |
  v
CompositeExecutor
|-- ReadOnlyFilesystemExecutor
|-- PythonExecutor
`-- GitExecutor
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

## Architectural principles

- Layered architecture
- Separation of responsibilities
- Thin executors
- Reusable services
- Read-only execution layer
- Dependency injection where appropriate
- Comprehensive automated tests

## Project status

Completed

- ✓ Phase 1 - Semantic Python Engine
- ✓ Phase 2
- ✓ Phase 3
- ✓ Phase 4
- ✓ Phase 5 - Execution Layer

Current release:

v0.5.0

## Roadmap

Next milestone:

Phase 6 - Semantic Architecture

Phase 6 introduces a persistent semantic representation of the full software project to enable architectural reasoning, dependency analysis, impact analysis, and high-level project understanding beyond tool execution.

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