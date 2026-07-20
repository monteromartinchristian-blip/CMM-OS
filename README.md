# CMM OS

CMM OS (Code Management Machine Operating System) is an AI-native software development operating system.

Instead of allowing an LLM to directly modify files, CMM OS translates user intent into structured execution plans that are validated and executed by a semantic kernel.

## What is the Semantic Python Engine?

The Semantic Python Engine is the first execution layer of CMM OS for safe, structured Python code editing. It works by parsing Python source into AST, applying semantic transformations, and writing the file back only when the change is valid.

This phase focuses on the core editing primitives for Python classes, methods, and imports.

## Architecture (simplified)

```text
User intent
  -> Plan / action parsing
  -> Executor
  -> PythonEditor
  -> PythonTransformer
  -> AST-based file updates
```

The main building blocks are:

- cmm: CLI entry points
- cmm_agent: planning and agent orchestration
- kernel: execution engine, parser, validator, and Python editing services
- tests: regression and behavior coverage for the semantic engine

## Implemented capabilities

The Semantic Python Engine currently supports:

- create_class
- replace_class
- insert_method
- replace_method
- rename_method
- delete_method
- ensure_import
- remove_import
- has_import

These operations are implemented through AST-based transformations and validated through Python parsing.

## Project structure

```text
CMM-OS/
├── cmm/
├── cmm_agent/
├── kernel/
├── runtime/
├── scripts/
├── docs/
├── tests/
├── README.md
├── requirements.txt
└── .gitignore
```

## Installation

Clone the repository:

```bash
git clone https://github.com/monteromartinchristian-blip/CMM-OS.git
cd CMM-OS
```

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running

Generate a plan:

```bash
cmm plan "Your objective"
```

Apply the plan:

```bash
cmm apply
```

## Tests

Run the full test suite:

```bash
.venv/bin/pytest
```

## Current status

Current version: v0.1.0-engine

Phase 1 status: completed

The Semantic Python Engine now supports the core class, method, and import operations required for safe AST-based editing.

## Roadmap

Next phases will focus on:

- richer semantic editing operations
- broader validation and safety checks
- deeper integration with planner and executor flows
- support for larger refactoring scenarios

## License

Private project.