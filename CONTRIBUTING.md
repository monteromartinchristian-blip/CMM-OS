# Contributing to CMM OS

Thank you for your interest in contributing to **CMM OS**.

Agents developing this repository follow [AGENTS.md](AGENTS.md). This document
supplies contributor conventions and commands, not additional authorization.

CMM OS is an AI-native software-engineering runtime focused on structured, validated, reversible, and policy-controlled code transformation. Contributions are welcome when they preserve the project's core guarantees: explicit contracts, safe execution, validation before trust, reversibility, traceability, and least privilege.

---

## Project status

Consult [`ROADMAP.md`](ROADMAP.md) and the relevant phase reference for current
status; historical plans are not an instruction to restart a completed phase.
Detailed specifications live under [`docs/roadmap/`](docs/roadmap/).

---

## Ways to contribute

You can contribute by:

- reporting bugs;
- proposing features;
- improving documentation;
- adding or strengthening tests;
- implementing roadmap items;
- improving validation, safety, or rollback behavior;
- reviewing architecture and public contracts;
- improving developer tooling and CI;
- contributing new semantic operations or transformation support.

For substantial changes, agree scope and contracts through an issue, a design
proposal or an explicit approved task before implementation. Publish an issue
only when that external action is authorized; an agreed local spec is sufficient.

---

## Development principles

All contributions must follow these principles:

- use explicit, typed contracts;
- prefer structured results over free-form output;
- do not introduce unrestricted shell execution into product operations;
- preserve rollback whenever technically possible;
- validate before and after mutation;
- keep side effects explicit and observable;
- preserve deterministic behavior where possible;
- maintain clear error classification;
- avoid hidden autonomy;
- respect least privilege;
- preserve backward compatibility unless a breaking change is explicitly approved;
- include meaningful tests for behavior changes and documentation for affected contracts or usage.

Product operations must reject unsafe or unsupported ambiguous input before
mutation. Developer uncertainty follows the recovery policy in AGENTS.md.

---

## Local setup

### Requirements

- Python 3.10 or newer, matching `pyproject.toml` and CI;
- Git;
- a virtual environment tool;
- project dependencies installed from the repository configuration.

### Clone the repository

```bash
git clone https://github.com/monteromartinchristian-blip/CMM-OS.git
cd CMM-OS
```

### Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

```powershell
.venv\Scripts\activate
```

### Install the project

```bash
pip install -e .
```

Install the declared development dependencies when setting up an environment:

```bash
pip install -e ".[dev]"
```

---

## Running tests

Use the project's virtual environment (`source .venv/bin/activate`, or prefix
commands with `.venv/bin/python`). Run the complete test suite before submitting
a pull request, and at final verification of a code change:

```bash
python -m pytest -ra
```

During implementation, run the relevant tests first, then the full suite at the
code-change boundary above. For example, select the affected test file:

```bash
python -m pytest tests/path/to/relevant_tests.py -q
python -m pytest -ra
```

A pull request should not be considered ready while the full suite is failing.

Pure documentation/instruction changes use link, example, scope and behavioral
scenario checks as applicable; they do not require artificial Python tests or a
full product suite for local delivery. This exception does not waive a task's
explicit gates or the full-suite requirement for PR submission. A change to an
executable example, CI command or runtime behavior needs the affected technical
checks. Reuse valid evidence according to AGENTS.md rather than rerunning at
each role transition.

---

## Validation expectations

Depending on the change, contributors should run the relevant checks:

```bash
python -m compileall -q cmm cmm_agent kernel tests
python -m pytest -ra
```

For changed Python files, run `python -m ruff check <changed-python-paths>` and
`python -m ruff format --check <changed-python-paths>`. Run applicable type,
security and phase-specific gates when their contracts require them; an installed
optional tool alone is not a command or a new gate. Do not silently omit a
required check because it fails or is unavailable.

Changes involving source transformation must also verify:

- syntax before and after execution;
- AST or CST integrity;
- import correctness;
- reference preservation;
- deterministic output;
- rollback behavior;
- unchanged files remaining byte-identical when expected.

---

## Branches

For a new contribution, create a focused branch from the intended base. For an
ongoing task, inspect the current branch and worktree first and follow the Git
policy in AGENTS.md. Do not switch branches or pull just to follow a setup example.

Recommended prefixes:

```text
feat/
fix/
refactor/
test/
docs/
chore/
security/
```

Examples:

```text
feat/validation-pipeline
fix/rollback-import-rewrite
docs/plugin-contracts
test/move-package-edge-cases
```

---

## Commits

Use concise, descriptive commit messages.

Commit only when authorized by the current task as defined in AGENTS.md; the
examples below do not grant authorization or require a commit for local delivery.

Recommended format:

```text
type: short imperative description
```

Examples:

```text
feat: add validation policy resolver
fix: preserve file bytes during rollback
test: cover cyclic transformation dependencies
docs: clarify semantic operation contracts
```

Keep unrelated changes in separate commits.

Do not commit:

- secrets;
- credentials;
- local environment files;
- generated caches;
- private user data;
- unrelated formatting changes;
- large binary files without prior discussion.

---

## Pull requests

A pull request should:

- have a clear title;
- explain the problem being solved;
- describe the implementation;
- identify affected contracts and components;
- list validation performed;
- include meaningful tests for behavior changes, or explain the checks applicable to a documentation-only change;
- document limitations;
- mention migration or compatibility impact;
- link the relevant issue when one exists.

Use this checklist:

```text
[ ] The change is focused and scoped.
[ ] Public contracts remain compatible or the breaking change is documented.
[ ] Behavior changes have meaningful tests; document-only checks are identified.
[ ] The full test suite passes.
[ ] Validation and rollback behavior were verified.
[ ] Documentation was updated.
[ ] No secrets or private data are included.
[ ] Known limitations are documented.
```

Pull requests may be rejected when they:

- bypass existing contracts;
- duplicate core infrastructure;
- introduce unrestricted execution;
- hide side effects;
- remove validation;
- weaken rollback guarantees;
- silently escalate autonomy;
- add undocumented breaking changes;
- depend on unavailable proprietary services without an adapter boundary.

---

## Architecture changes

Significant architecture changes should begin with an agreed design proposal
or issue; a design already approved for the current task need not be reapproved.

The proposal should include:

- problem statement;
- current limitation;
- proposed contracts;
- affected components;
- data flow;
- failure modes;
- security implications;
- migration strategy;
- test strategy;
- alternatives considered.

Keep proposals concise and implementation-oriented.

---

## Adding semantic operations

A new semantic operation should define:

- operation identifier;
- typed input contract;
- executor ownership;
- preconditions;
- mutation boundaries;
- validation rules;
- result contract;
- rollback strategy;
- error categories;
- tests;
- documentation.

Example identifier:

```text
python.example_operation
```

Operations must be registered explicitly and must not rely on unrestricted command execution.

---

## Adding transformations

A transformation must include:

- typed transformation contract;
- impact analysis;
- deterministic planning;
- dependency ordering;
- reference resolution;
- pre-mutation rejection of unsafe cases;
- post-transformation validation;
- rollback;
- structured result;
- unit and integration tests.

Ambiguous or unsupported cases must be rejected safely.

---

## Documentation

Documentation is part of the definition of done.

Update the relevant files when changing:

- public behavior;
- CLI commands;
- API contracts;
- configuration;
- architecture;
- supported operations;
- limitations;
- migrations;
- installation steps.

Use clear Markdown and keep examples executable where possible.

---

## Bug reports

A useful bug report includes:

- CMM OS version;
- Python version;
- operating system;
- installation method;
- exact command or operation;
- expected behavior;
- actual behavior;
- minimal reproduction;
- logs or traceback;
- whether repository state changed;
- whether rollback succeeded.

Never include secrets or sensitive personal data.

---

## Feature requests

Feature requests should describe:

- the problem;
- the intended user;
- the proposed behavior;
- why existing capabilities are insufficient;
- safety and permission implications;
- validation requirements;
- likely roadmap phase;
- possible alternatives.

---

## Security issues

Do not report security vulnerabilities in public issues.

Follow [`SECURITY.md`](SECURITY.md). Publication or messaging still requires
authorization for that action; prepare the report locally when not yet authorized.

---

## Code of conduct

Be respectful, precise, and constructive.

Harassment, discrimination, personal attacks, and bad-faith participation are not acceptable.

Technical disagreement is welcome when it remains evidence-based and focused on improving the project.

---

## License

By contributing to CMM OS, you agree that your contributions will be licensed under the repository's [Apache License 2.0](LICENSE).
