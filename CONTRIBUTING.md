# Contributing to CMM OS

Thank you for your interest in contributing to **CMM OS**.

CMM OS is an AI-native software-engineering runtime focused on structured, validated, reversible, and policy-controlled code transformation. Contributions are welcome when they preserve the project's core guarantees: explicit contracts, safe execution, validation before trust, reversibility, traceability, and least privilege.

---

## Project status

The current stable release is `v0.7.0`.

Phases 0–6 are implemented and audited. The active development target is:

- Phase 7 — Continuous Validation

The full roadmap is available in [`ROADMAP.md`](ROADMAP.md), with detailed specifications under [`docs/roadmap/`](docs/roadmap/).

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

For substantial changes, open an issue before starting implementation so the scope and contracts can be agreed first.

---

## Development principles

All contributions must follow these principles:

- use explicit, typed contracts;
- prefer structured results over free-form output;
- avoid unrestricted shell execution;
- preserve rollback whenever technically possible;
- validate before and after mutation;
- keep side effects explicit and observable;
- preserve deterministic behavior where possible;
- maintain clear error classification;
- avoid hidden autonomy;
- respect least privilege;
- preserve backward compatibility unless a breaking change is explicitly approved;
- include tests and documentation with every meaningful change.

Unsafe or ambiguous behavior should fail before mutation.

---

## Local setup

### Requirements

- Python 3.11 or newer;
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

Install development dependencies when available:

```bash
pip install -e ".[dev]"
```

---

## Running tests

Run the complete test suite before submitting a pull request:

```bash
pytest
```

When working on a focused area, run the relevant tests first, then the full suite:

```bash
pytest tests/path/to/relevant_tests.py
pytest
```

A pull request should not be considered ready while the full suite is failing.

---

## Validation expectations

Depending on the change, contributors should run the relevant checks:

```bash
python -m compileall src tests
pytest
```

If formatter, lint, type-checking, or security commands are defined in the repository, run them as well before opening a pull request.

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

Create a focused branch from the latest `main`:

```bash
git checkout main
git pull
git checkout -b type/short-description
```

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
- include tests;
- document limitations;
- mention migration or compatibility impact;
- link the relevant issue when one exists.

Use this checklist:

```text
[ ] The change is focused and scoped.
[ ] Public contracts remain compatible or the breaking change is documented.
[ ] Tests were added or updated.
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

Significant architecture changes should begin with an issue or design proposal.

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

Follow the instructions in [`SECURITY.md`](SECURITY.md) once available.

Until then, contact the maintainer privately through the GitHub profile associated with this repository.

---

## Code of conduct

Be respectful, precise, and constructive.

Harassment, discrimination, personal attacks, and bad-faith participation are not acceptable.

Technical disagreement is welcome when it remains evidence-based and focused on improving the project.

---

## License

By contributing to CMM OS, you agree that your contributions will be licensed under the repository's [Apache License 2.0](LICENSE).
