# Commit Gate (Subphase 7.10)

The **Commit Gate** provides a structured, observable, and safe barrier between continuous validation results and repository modifications (Git commits).

## Core Architecture

The Commit Gate decouples validation from side effects into four distinct layers:

1. **Validation Result**: Pipeline produces a `ValidationResult` (read-only execution).
2. **Commit Gate Evaluation**: `CommitGateEvaluator.evaluate()` checks policy, required steps, blocking findings, critical errors, timeouts, artifacts, cancellation, and security constraints to produce a `CommitGateResult`.
3. **Explicit Authorization**: `CommitAuthorization` provides an auditable contract recording explicit human approval, actor ID, and target validation ID.
4. **Provisional Commit Creation**: `ProvisionalCommitService` verifies repository safety, stages authorized files, and creates a provisional commit with structured audit trailers.

```
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

## Public API Contracts

### `CommitGateResult`

Immutable, slotted, and serializable representation of a gate evaluation:

```python
from cmm.validation import CommitGateResult, CommitGateReason, CommitGateReasonCode

result = CommitGateResult(
    allowed=True,
    validation_result_id="val-12345",
    policy_name="small_change",
    reasons=(),
    blocking_findings=(),
)
```

### `CommitGateEvaluator`

Pure evaluator with zero I/O or process side effects:

```python
from cmm.validation import CommitGateEvaluator, resolve_validation_policy

policy = resolve_validation_policy(context)
gate_result = CommitGateEvaluator.evaluate(validation_result, policy)

if gate_result.allowed:
    print("Gate passed!")
else:
    for reason in gate_result.reasons:
        print(f"Denied: [{reason.code.value}] {reason.message}")
```

### `CommitAuthorization`

Explicit contract requiring an explicit actor and intention:

```python
from cmm.validation import CommitAuthorization

auth = CommitAuthorization(
    authorized=True,
    actor="human:christian",
    reason="Create provisional commit after passing continuous validation",
    validation_result_id="val-12345",
)
```

### `ProvisionalCommitService`

Service that creates commits only when authorized and when the repository state is safe:

```python
from pathlib import Path
from cmm.validation import ProvisionalCommitService

service = ProvisionalCommitService()
final_result = service.create_commit(
    gate_result=gate_result,
    authorization=auth,
    repository_path=Path("."),
    files_to_commit=[Path("cmm/validation/commit_gate/models.py")],
)

if final_result.commit_created:
    print(f"Provisional commit created: {final_result.commit_hash}")
```

## Safety Rules & Staging Strategy

- **Default Read-Only**: The pipeline never modifies Git automatically.
- **No Indiscriminate Staging**: Does NOT execute `git add -A`. Only files in `files_to_commit` or `validated_files` within the repository root are staged.
- **Scope Verification**: Rejects commit if index contains staged files outside the authorized scope.
- **Safe State Enforcement**: Rejects commit if a merge, rebase, cherry-pick, revert, or index lock is in progress.
- **Forbidden Operations**: The infrastructure strictly forbids `git push`, `git pull`, `git merge`, `git rebase`, `git reset --hard`, `git clean`, `git checkout`, `git switch`, `git tag`, `git release`, `git cherry-pick`, or `git revert`.
