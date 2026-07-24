# Phase 7 — Continuous Validation

## Objective

Harden the development process so that every modification made by a person, an agent, or the system itself is automatically validated before it can be considered safe.

This phase will turn validation into a reusable and observable pipeline that can be executed manually, from the CLI, through the API, in CI, and by future autonomous agents.

CMM OS must not merely modify code. It must be able to demonstrate, through reproducible checks and structured results, that a change does not degrade the project.

---

## General Pipeline

```text
Modify code
        ↓
Detect changes
        ↓
Select validation policy
        ↓
Format
        ↓
Lint
        ↓
Syntax and AST validation
        ↓
Affected tests
        ↓
Full suite when required
        ↓
Static analysis
        ↓
Security checks
        ↓
Custom validations
        ↓
Structured result
        ↓
Commit gate
        ↓
Optional provisional commit
```

Validation must be executable:

- before a transformation;
- after a transformation;
- on specific files;
- on Git changes;
- on the entire project;
- as part of a workflow;
- from CI;
- from a future autonomous agent.

---

# 7.1 — Validation Contracts

## Objective

Define the shared contracts for the entire validation infrastructure before integrating specific tools.

## Components

### Validation Status

Common states:

```text
pending
running
passed
failed
warning
skipped
cancelled
timed_out
error
```

### Validation Severity

Severity levels:

```text
info
warning
error
critical
```

### Validation Finding

Structured representation of a detected issue:

```python
ValidationFinding(
    code="F401",
    message="Imported module is not used",
    severity="warning",
    file_path="src/example.py",
    line=12,
    column=1,
    source="ruff",
    blocking=False,
    metadata={},
)
```

Minimum properties:

- code;
- message;
- severity;
- source;
- file;
- line;
- column;
- blocking status;
- metadata;
- possible fix;
- optional documentation reference.

### Validation Step

Shared contract for each check:

```python
ValidationStep(
    name="lint",
    command=["ruff", "check", "."],
    required=True,
    timeout_seconds=120,
    stop_on_failure=True,
    allowed_exit_codes=[0],
    environment={},
    working_directory=None,
    metadata={},
)
```

Each step must define:

- name;
- type;
- command or internal executor;
- whether it is required;
- timeout;
- allowed exit codes;
- failure behavior;
- working directory;
- environment variables;
- dependencies;
- tags;
- metadata.

### Validation Step Result

Structured result of a step:

```python
ValidationStepResult(
    name="lint",
    status="passed",
    exit_code=0,
    duration_ms=842,
    stdout="",
    stderr="",
    findings=[],
    artifacts=[],
    started_at="...",
    completed_at="...",
    metadata={},
)
```

### Validation Artifact

Reusable artifact generated during validation:

```python
ValidationArtifact(
    id="artifact-123",
    kind="lint_report",
    source="ruff",
    path=None,
    content={},
    findings=[],
    metrics={},
    created_at="...",
    metadata={},
)
```

Initial artifact types:

- formatter report;
- lint report;
- AST report;
- test report;
- coverage report;
- static analysis report;
- security report;
- command log;
- metrics report.

Artifacts will allow future cognitive layers and agents to reason over structured results rather than relying on free-form logs.

### Validation Result

Aggregated pipeline result:

```python
ValidationResult(
    status="passed",
    policy="small_change",
    steps=[],
    artifacts=[],
    blocking_findings=[],
    warnings=[],
    changed_files=[],
    affected_tests=[],
    duration_ms=12400,
    started_at="...",
    completed_at="...",
    can_commit=True,
    metadata={},
)
```

### Validation Context

Execution context:

```python
ValidationContext(
    project_root="...",
    changed_files=[],
    change_type="small_change",
    execution_mode="local",
    requested_steps=None,
    environment={},
    allow_commit=False,
    metadata={},
)
```

It must include:

- project root;
- changed files;
- change type;
- current branch;
- base commit;
- execution mode;
- requested policy;
- selected steps;
- environment variables;
- permissions;
- actor requesting validation;
- workflow identifier;
- metadata.

---

# 7.2 — Validation Pipeline

## Objective

Build the engine that orchestrates all checks in a controlled order.

## Components

### Validation Pipeline

Responsibilities:

- receive a `ValidationContext`;
- resolve the applicable policy;
- build the set of steps;
- order dependencies;
- execute steps;
- stop on blocking failures;
- continue on warnings;
- accumulate results;
- generate artifacts;
- calculate metrics;
- produce a `ValidationResult`.

Conceptual example:

```python
result = validation_pipeline.run(
    context=ValidationContext(
        project_root=project_root,
        changed_files=["src/example.py"],
        change_type="small_change",
        execution_mode="local",
    )
)
```

### Validation Executor

Shared executor for external commands and internal validators.

It must support:

- external processes;
- internal Python validators;
- timeouts;
- cancellation;
- stdout and stderr capture;
- exit codes;
- controlled working directories;
- restricted environments;
- timing metrics;
- structured errors.

### Step Registry

Registry of available validators:

```text
formatter
lint
syntax
ast
unit_tests
integration_tests
affected_tests
full_suite
type_check
security
custom
```

The registry will allow new steps to be added without modifying the pipeline core.

### Step Dependencies

Steps may declare dependencies:

```text
formatter
    ↓
lint
    ↓
syntax
    ↓
ast
    ↓
tests
```

Tests must not run on code that has not passed basic syntax validation.

---

# 7.3 — Formatter, Lint, and Structural Validation

## Formatter

Initial integration with formatting tools.

Capabilities:

- check formatting without modifying files;
- apply formatting when authorized;
- detect files changed by the formatter;
- record differences;
- generate an artifact;
- distinguish between check mode and fix mode.

The formatter must not modify files by default during purely informational validation.

## Lint

Initial integration with Ruff or another configurable tool.

Capabilities:

- analyze the entire project;
- analyze specific files;
- produce structured findings;
- distinguish errors from warnings;
- support configurable rules;
- run in check mode;
- apply fixes only when authorized.

## Syntax Validation

Minimum checks:

- Python compilation;
- syntax errors;
- invalid imports;
- non-parseable files;
- invalid encoding.

## AST Validation

Integration with the existing semantic infrastructure.

It must verify:

- that every modified file can be parsed;
- that the resulting AST is valid;
- that no incomplete nodes exist;
- that expected classes and methods remain present;
- that transformations preserve structure;
- that modified references remain coherent;
- that no structural duplicates are introduced;
- that imports, methods, and classes preserve valid contracts.

CMM OS-specific validators may be added for:

- duplicate methods;
- duplicate classes;
- inconsistent imports;
- broken references;
- incompatible signatures;
- incomplete semantic operations;
- semantic protocol violations.

---

# 7.4 — Testing

## Objective

Run the most relevant tests first and progressively escalate to the full suite when required.

## Test Types

### Affected Tests

Select tests related to the detected changes.

Initial impact sources:

- modified file;
- module;
- imports;
- references;
- affected classes;
- affected methods;
- naming conventions;
- code-to-test mapping;
- coverage history when available.

Example:

```text
src/cmm_os/python/editor.py
        ↓
tests/unit/python/test_editor.py
tests/integration/test_python_operations.py
```

The first version may use simple heuristics and later evolve toward semantic analysis and historical coverage data.

### Unit Tests

Run unit tests related to the change.

### Integration Tests

Run integration tests when the change affects:

- multiple modules;
- operations;
- persistence;
- the planner;
- the kernel;
- public interfaces;
- simulated external integrations.

### Full Suite

The full suite must run when:

- a public API is modified;
- shared contracts change;
- the kernel is modified;
- the executor changes;
- the planner changes;
- cross-cutting infrastructure is modified;
- a release is being prepared;
- a policy requires it;
- impact cannot be determined with sufficient confidence.

## Test Results

Results must include:

- tests executed;
- tests passed;
- tests failed;
- tests skipped;
- duration;
- errors;
- traces;
- optional coverage;
- affected files;
- relationship between change and test;
- pytest artifacts.

---

# 7.5 — Change Impact Detection

## Objective

Determine which parts of the project may be affected by a change.

## Change Set

Structured representation of changes:

```python
ChangeSet(
    added_files=[],
    modified_files=[],
    deleted_files=[],
    renamed_files=[],
    changed_symbols=[],
    changed_imports=[],
    public_api_changes=[],
    metadata={},
)
```

## Change Classification

Initial types:

```text
documentation_only
format_only
small_change
structural_change
imports_change
public_api_change
kernel_change
configuration_change
dependency_change
security_sensitive_change
release
unknown
```

## Detection Sources

- Git diff;
- changed files;
- AST before and after;
- semantic indexes;
- imports;
- references;
- signatures;
- configuration;
- dependencies;
- project manifests.

## Impact Result

```python
ChangeImpactResult(
    change_type="structural_change",
    affected_modules=[],
    affected_symbols=[],
    affected_tests=[],
    public_api_changed=False,
    confidence=0.82,
    requires_full_suite=False,
    findings=[],
)
```

Uncertainty must be preserved.

When impact cannot be determined with sufficient confidence, the system must expand validation rather than reduce it.

---

# 7.6 — Static Analysis

## Objective

Detect issues that do not necessarily appear during test execution.

## Initial Checks

- type checking;
- unused imports;
- circular imports;
- nonexistent references;
- dead code;
- unused variables;
- incompatible signatures;
- inconsistent returns;
- typing errors;
- excessive complexity;
- duplication;
- invalid dependencies.

## Tools

The architecture must support integration with tools such as:

- mypy;
- pyright;
- Ruff;
- Vulture;
- CMM OS-specific tools.

Each integration must implement the `ValidationStep` contract.

---

# 7.7 — Execution Security

## Objective

Prevent the validation infrastructure from becoming a mechanism for arbitrary or destructive execution.

## Command Policy

Every external command must pass through an authorization policy.

```python
CommandPolicy(
    allowed_executables=[
        "python",
        "pytest",
        "ruff",
        "mypy",
        "pyright",
    ],
    forbidden_arguments=[],
    allow_shell=False,
    allow_network=False,
    allowed_working_directories=[],
    environment_allowlist=[],
)
```

## Mandatory Measures

- executable allowlist;
- shell disabled by default;
- argument validation;
- destructive-command prohibition;
- timeout per step;
- output limits;
- resource limits where possible;
- controlled working directory;
- restricted execution environment;
- filtered environment variables;
- no secret exposure;
- network disabled by default;
- safe cancellation;
- auditable logs.

## Forbidden Commands

The system must explicitly reject:

- arbitrary deletion;
- writes outside the project;
- permission changes;
- privilege escalation;
- unauthorized secret access;
- publishing;
- push;
- arbitrary installation;
- execution of non-allowed scripts;
- destructive Git operations.

## Separation of Responsibilities

Validation and publishing must remain separate.

The pipeline may determine that a change is valid, but it must not:

- publish;
- push;
- deploy;
- create a release;
- modify permissions;
- execute irreversible actions.

---

# 7.8 — Validation Policy

## Objective

Configure which checks are mandatory for each context.

## Contract

```python
ValidationPolicy(
    name="small_change",
    required_steps=[
        "formatter_check",
        "lint",
        "syntax",
        "ast",
        "affected_tests",
    ],
    optional_steps=[],
    stop_on_blocking_failure=True,
    require_full_suite=False,
    allow_commit=True,
    metadata={},
)
```

## Initial Policies

### Documentation Only

- file validation;
- formatting;
- link checking;
- documentation-specific validations;
- no full suite unless configured.

### Small Change

- formatter;
- lint;
- syntax;
- AST;
- affected tests.

### Structural Change

- formatter;
- lint;
- syntax;
- AST;
- affected tests;
- unit tests;
- integration tests;
- static analysis.

### Imports Change

- lint;
- syntax;
- AST;
- import analysis;
- affected tests;
- cycle checks.

### Public API Change

- all structural checks;
- unit tests;
- integration tests;
- full suite;
- contract validation;
- associated documentation.

### Kernel Change

- complete pipeline;
- full suite;
- static analysis;
- security checks;
- E2E;
- kernel-specific validations.

### Release

- formatter;
- lint;
- AST;
- full suite;
- static analysis;
- security;
- E2E;
- minimum coverage;
- version validation;
- documentation validation;
- migration validation.

### Autonomous Execution

- restrictive policy;
- allowed commands only;
- all required checks;
- no automatic commit;
- human approval at critical points;
- complete artifacts;
- mandatory traceability.

## Policy Resolution

A policy may be selected through:

- explicit configuration;
- change type;
- project rules;
- CI context;
- workflow;
- requesting agent;
- autonomy level.

---

# 7.9 — Validaciones personalizadas de CMM OS

## Objective

Allow the project to define its own rules without coupling them to the core.

## Contract

```python
class CustomValidator:
    name: str

    def validate(
        self,
        context: ValidationContext,
    ) -> ValidationStepResult: ...
```

## Initial Validators

- coherence between operations and protocols;
- operation registry consistency;
- planner validation;
- model validation;
- event integrity;
- contract compatibility;
- code and documentation consistency;
- detection of unregistered operations;
- detection of non-serializable results;
- persistence validation;
- migration checks;
- architectural rules.

## Registry

Custom validators must be loaded through a registry or plugin system.

---

# 7.10 — Commit Gate


## Objective

Prevent an invalid change from being marked as safe or converted into a provisional commit by enforcing a strict, structured, four-tier commit barrier:
Validation Approved → Gate Approved → Express Authorization → Optional Provisional Commit.

## Flow

```text
ValidationResult
        ↓
Resolved ValidationPolicy
        ↓
Completeness & Required Step Check
        ↓
Blocking Findings & Security Check
        ↓
Critical Errors & Timeout Check
        ↓
Required Artifacts Check
        ↓
Cancellation Check
        ↓
Policy Permission Check (allow_commit)
        ↓
CommitGateResult (allowed: bool, reasons: tuple)
        ↓
Explicit Human Authorization (CommitAuthorization)
        ↓
Safe Repository Inspection (RepositoryState)
        ↓
Optional Provisional Commit (ProvisionalCommitService)
```

## Gate Evaluation Rules & Blocking Reasons

A change is denied approval by `CommitGateEvaluator` when ANY of the following occurs:

- a required step fails (`REQUIRED_STEP_FAILED`);
- a required step is missing or unexecuted (`REQUIRED_STEP_MISSING`);
- a required step was skipped (`REQUIRED_STEP_SKIPPED`);
- a required step timed out (`REQUIRED_STEP_TIMEOUT`);
- a blocking finding or critical severity finding exists (`BLOCKING_FINDING`);
- a security violation is detected (`SECURITY_VIOLATION`);
- a critical pipeline execution error occurred (`CRITICAL_ERROR`);
- a required artifact is missing (`REQUIRED_ARTIFACT_MISSING`);
- the validation policy is unresolved (`POLICY_UNRESOLVED`) or incomplete (`POLICY_INCOMPLETE`);
- the policy forbids commits via `allow_commit=False` (`POLICY_FORBIDS_COMMIT`);
- the validation result is incomplete / in-progress (`VALIDATION_INCOMPLETE`);
- the pipeline execution was cancelled (`PIPELINE_CANCELLED`);
- the contract or validation result ID is invalid or corrupt (`INVALID_CONTRACT`).

## Optional Provisional Commit & Git Safety

The validation infrastructure is **read-only with respect to Git by default**. Creating a provisional commit requires explicit, opt-in execution via `ProvisionalCommitService`.

Creating a provisional commit strictly requires:
1. `CommitGateResult` with `allowed=True`;
2. `CommitAuthorization` with `authorized=True`, valid actor, and matching `validation_result_id`;
3. Safe repository state (`is_git_repository=True`, `work_tree_exists=True`, no merge, rebase, cherry-pick, revert, or index lock in progress);
4. Valid, non-empty commit message (with automated trailers for auditability);
5. Staged files restricted strictly to the authorized/validated scope (no indiscriminate `git add -A`).

The system strictly forbids automatic execution of:
`git push`, `git pull`, `git merge`, `git rebase`, `git reset --hard`, `git clean`, `git checkout`, `git switch`, `git tag`, `git release`, `git cherry-pick`, `git revert`, publishing, or deployment.

## Key Public Contracts

- `CommitGateReasonCode`: Enum of structured denial and operational reasons.
- `CommitGateReason`: Immutable dataclass representing a structured evaluation reason.
- `CommitGateResult`: Frozen, slotted, serializable contract representing gate evaluation state.
- `CommitAuthorization`: Explicit contract capturing actor, timestamp, reason, and target validation ID.
- `CommitGateEvaluator`: Pure, side-effect-free evaluator.
- `GitRepositoryProtocol` / `SubprocessGitRepository`: Safe Git process wrapper (without `shell=True`).
- `ProvisionalCommitService`: Isolated service for creating provisional commits.

---


# 7.11 — Observability and Persistence

## Objective

Preserve enough information to understand, audit, and compare executions.

## Data to Record

- execution identifier;
- policy;
- actor;
- context;
- executed steps;
- duration;
- authorized commands;
- exit codes;
- findings;
- artifacts;
- changed files;
- affected tests;
- errors;
- timeouts;
- gate result;
- associated commit;
- timestamps.

## Logs

Logs must be:

- structured;
- readable;
- filterable;
- persistable;
- suitable for humans and agents;
- free of secrets;
- linked to an execution.

## Initial Metrics

- total duration;
- duration per step;
- success rate;
- failures by validator;
- timeouts;
- tests executed;
- failed tests;
- findings by severity;
- full-suite frequency;
- changes rejected by the gate.

## Persistence

A storage abstraction must exist for:

- results;
- artifacts;
- logs;
- metrics;
- validation history.

The initial implementation may be local and evolve later.

---

# 7.11 — Observability and Persistence

> **Status: Implemented** (commit `feat(validation): add phase 7.11 observability and persistence`)

## Objective

Build the observability and persistence layer for the validation
infrastructure so that every execution can be identified unambiguously,
reconstructed, queried, audited, and consumed by future interfaces
(CLI, API, CI) and phases 8 and 9.

## Components Implemented

### `ValidationExecutionRecord`

Immutable, versionable, serializable snapshot of a validation run.
Contains ID, schema version, status, policy, actor, context, branch,
changed files, step results, findings, artifacts, metrics, gate result,
commit hash, timestamps, and metadata.  Round-trip safe via
`serialize()` / `from_mapping()`.

### `ValidationLogEntry`

Structured log event tied to a validation execution.  Fields: ID,
validation ID, timestamp, level, component, event (stable identifier),
message, step name, duration, status, correlation ID, metadata.

### `ValidationMetrics` / `ValidationMetricsCalculator`

Immutable aggregated statistics.  Pure, I/O-free calculator derives
metrics from `ValidationResult` + optional `CommitGateResult`.

### `ValidationRepositoryProtocol`

`typing.Protocol` (runtime-checkable) defining the storage interface.
Allows plug-in of any backend without changing consumers.

### `LocalValidationRepository`

File-system implementation:

```text
.cmm/validation/
├── executions/<validation-id>.json  ← atomic JSON per execution
├── logs/<validation-id>.jsonl       ← append-only JSONL
├── artifacts/<validation-id>/<artifact-id>.json
└── index.json                       ← compact searchable index
```

Features: atomic writes (`tempfile` + `os.replace`), idempotence,
conflict detection (status regression, cleared commit_hash, timestamp
regression), path traversal guard, JSONL corruption resilience,
index rebuild from disk, artifact content size limit.

### `ValidationObservabilityService`

Coordinator for record construction, metrics calculation, sanitisation,
and persistence.  Does not execute validations.  Persistence failures
are surfaced as structured log entries without altering validation results.

### `sanitize_validation_data`

Recursive sanitisation utility.  Redacts values for sensitive keys
(`token`, `api_key`, `password`, `authorization`, `cookie`, etc.)
and URL-embedded credentials.  Never mutates input objects.

### `ValidationHistoryQuery` / `ValidationHistoryPage`

Immutable filter and paginated result contracts.  Filters: policy,
status, actor, branch, time range, gate decision, commit presence.
Default order: most recent first.

## Pipeline Integration

`ValidationPipeline` accepts an optional `observability` field
(`None` by default).  When provided, it records execution start and
completion and assigns a stable `validation-<uuid>` ID.  Persistence
failures do not alter the validation result.

## Documentation

See `docs/validation/observability-and-persistence.md`.

---

# 7.12 — CLI, API, and CI


## CLI

Initial commands:

```bash
cmm validation run
cmm validation run --policy small_change
cmm validation run --step lint
cmm validation run --files src/example.py
cmm validation inspect <validation-id>
cmm validation artifacts <validation-id>
cmm validation gate <validation-id>
```

Capabilities:

- complete pipeline;
- selected steps;
- specific files;
- human-readable output;
- JSON output;
- CI-compatible exit codes;
- verbose mode;
- quiet mode;
- no commits by default.

## API

The API must support:

- starting validations;
- querying status;
- cancellation;
- retrieving results;
- retrieving artifacts;
- evaluating the commit gate;
- selecting policies;
- selecting steps;
- integrating future agents.

## CI

CI execution must:

- use the same pipeline as local execution;
- produce the same contracts;
- fail with correct exit codes;
- preserve artifacts;
- publish reports;
- run specific policies;
- avoid behavioral differences between local and CI execution.

---

# 7.13 — Integration with the Existing System

## Semantic Engine

Every semantic transformation must be able to request validation:

```text
Semantic Operation
        ↓
Change Set
        ↓
Validation Pipeline
        ↓
Validation Result
```

## Execution Engine

The executor must be able to:

- validate before execution;
- validate after execution;
- stop the workflow;
- request rollback;
- return structured results.

## Planner

Plans may include validation nodes:

```text
Transform
    ↓
Validate
    ↓
Continue / Retry / Rollback / Stop
```

## Kernel

Validation must emit events:

```text
validation.started
validation.step.started
validation.step.completed
validation.failed
validation.completed
validation.gate.rejected
validation.gate.approved
```

## Memory

The system may preserve:

- relevant validations;
- recurring errors;
- decisions;
- rejected changes;
- artifacts;
- historical metrics.

## Future Cognitive Layer

Artifacts and results must be structured enough for Phase 8 to distinguish:

- facts;
- errors;
- warnings;
- impact hypotheses;
- uncertainty;
- missing information;
- commit-gate decisions.

## Future Autonomous Agent

The Phase 9 agent must be able to use the result to decide:

```text
Continue
Retry
Replan
Rollback
Ask user
Escalate
Pause
Abort
Complete
```

---

# 7.14 — Implementation Order

## Block 1 — Contracts

- ValidationStatus;
- ValidationSeverity;
- ValidationFinding;
- ValidationStep;
- ValidationStepResult;
- ValidationArtifact;
- ValidationResult;
- ValidationContext;
- serialization;
- unit tests.

## Block 2 — Runner

- ValidationPipeline;
- ValidationExecutor;
- Step Registry;
- dependencies;
- timeouts;
- stop on failure;
- logs;
- unit tests.

## Block 3 — Basic Validators

- formatter;
- lint;
- syntax;
- AST;
- initial CMM OS validators;
- integration tests.

## Block 4 — Testing

- affected tests;
- unit tests;
- integration tests;
- full suite;
- result parsing;
- artifacts.

## Block 5 — Impact Detection

- ChangeSet;
- change classification;
- import analysis;
- symbol analysis;
- basic test selection;
- impact confidence.

## Block 6 — Static Analysis

- type checking;
- dead code;
- imports;
- references;
- architectural rules.

## Block 7 — Security

- command allowlist;
- argument validation;
- controlled environment;
- timeouts;
- restricted network;
- allowed directories;
- secret protection.

## Block 8 — Policies

- contracts;
- initial policies;
- automatic resolution;
- per-project configuration.

## Block 9 — Commit Gate

- evaluation;
- structured reasons;
- authorization;
- optional provisional commit;
- safe Git integration.

## Block 10 — Observability

- logs;
- artifacts;
- metrics;
- history;
- persistence.

## Block 11 — Interfaces

- CLI;
- API;
- JSON output;
- exit codes;
- CI.

## Block 12 — Final Integration

- Semantic Engine;
- Execution Engine;
- Planner;
- Kernel;
- Memory;
- workflows;
- global E2E.

---

# Expected Capabilities

- execute the full pipeline;
- execute selected steps only;
- validate specific files;
- validate Git changes;
- stop on blocking errors;
- continue on non-blocking warnings;
- identify the exact failing step;
- produce structured findings;
- generate reports readable by humans and agents;
- preserve logs, metrics, and artifacts;
- integrate CMM OS-specific validators;
- select policies according to the change;
- perform basic impact detection;
- run affected tests first;
- escalate to the full suite when required;
- validate before and after a transformation;
- be reusable from the CLI, API, CI, and future agents;
- prevent unsafe commits;
- validate without altering Git;
- create provisional commits only with authorization;
- work locally and in CI;
- maintain reproducible results;
- preserve complete traceability.

---

# Security

- time limits per step;
- command allowlist;
- validated arguments;
- shell disabled by default;
- controlled execution environment;
- allowed working directories;
- output limits;
- safe cancellation;
- destructive-command prohibition;
- restricted network;
- protected secrets;
- separation between validation and publishing;
- no automatic commits without explicit authorization;
- no automatic push, merge, release, or deployment;
- human approval for sensitive operations;
- logs without secret information.

---

# Testing

## Unit Tests

- contracts;
- serialization;
- states;
- executor;
- timeouts;
- parsing;
- findings;
- policies;
- dependencies;
- commit gate;
- command policy;
- impact detection.

## Integration Tests

- formatter;
- Ruff;
- AST;
- pytest;
- static analysis;
- security;
- persistence;
- Git;
- CLI;
- API.

## E2E

Minimum scenarios:

1. valid small change;
2. lint error;
3. syntax error;
4. invalid AST;
5. affected test failure;
6. full-suite failure;
7. timeout;
8. forbidden command;
9. non-blocking warning;
10. public API change;
11. kernel change;
12. rejected commit gate;
13. authorized provisional commit;
14. local validation;
15. CI validation;
16. validation after a semantic transformation;
17. rollback requested after failure;
18. execution with a custom policy.

---

# Documentation

The phase must include:

- architecture;
- public contracts;
- validator implementation guide;
- policy guide;
- per-project configuration;
- CLI usage;
- API usage;
- CI integration;
- integration with semantic operations;
- security;
- commit gate;
- artifacts;
- metrics;
- troubleshooting;
- complete examples;
- guide for future agents.

---

# Completion Criteria

- validation contracts implemented;
- complete pipeline;
- structured results;
- structured artifacts;
- executor with timeouts;
- formatter integrated;
- lint integrated;
- syntax validation integrated;
- AST validation integrated;
- unit tests integrated;
- integration tests integrated;
- full suite integrated;
- basic affected-test selection;
- impact detection;
- static analysis;
- security checks;
- custom validations;
- configurable policies;
- functional commit gate;
- validation without Git modification;
- optional and authorized provisional commit;
- logs;
- metrics;
- persistence;
- CLI;
- API;
- local execution;
- CI execution;
- integration with the Semantic Engine;
- integration with the Execution Engine;
- integration with the Planner;
- integration with the Kernel;
- unit tests;
- integration tests;
- E2E tests;
- documentation;
- globally green test suite.

---

# Phase Outcome

CMM OS will be able to modify code and demonstrate, through a structured, reproducible, and auditable process, that the change does not degrade the project.

Each modification will produce verifiable evidence showing:

- what was checked;
- which steps were executed;
- what failed;
- which warnings appeared;
- which files and tests were affected;
- which artifacts were generated;
- which policy was applied;
- whether the change can be considered safe;
- whether it may pass the commit gate.

Phase 7 will turn validation into a cross-cutting system capability and establish the trust foundation required for the Cognitive Layer, future autonomous agents, and the complete evolution of CMM OS.
