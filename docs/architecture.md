# Architecture

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

## Layer responsibilities

- User Goal: high-level objective from the user.
- Technical Reasoner: provides deterministic technical context for planning.
- Task Planner: builds an ordered plan from the goal.
- Action Planner: converts plan steps into validated atomic actions.
- Execution Runtime: tracks queue state, transitions, and execution history.
- CompositeExecutor: primary entry point that routes actions by prefix.
- ReadOnlyFilesystemExecutor: read-only filesystem inspection.
- PythonExecutor: semantic Python actions delegated to the Semantic Python Engine.
- GitExecutor: read-only repository inspection actions.

## Implemented capabilities

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

CompositeExecutor is a thin routing layer with no business logic. It delegates execution by action prefix to filesystem.*, python.*, and git.* specialized executors.

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

Phase 6 will introduce a persistent semantic representation of the entire software project, enabling architectural reasoning, dependency analysis, impact analysis, and high-level project understanding beyond tool execution.
