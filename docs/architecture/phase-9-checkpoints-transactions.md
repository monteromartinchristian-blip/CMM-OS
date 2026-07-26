# Phase 9.15 — Checkpoints and Transaction Boundaries

## Overview

Phase 9.15 introduces verifiable state checkpoints and structured transaction boundaries into CMM OS Agent Runtime. It enables autonomous agents to:
- Establish safe system snapshots prior to executing relevant or state-modifying operations.
- Explicitly declare state dependencies (resource versions, Git repository state, external storage snapshots, agent memory, and domain knowledge).
- Verify checkpoint integrity deterministically using SHA-256 fingerprints and multi-provider checks.
- Restore resource state in reverse operational sequence under exclusive concurrency locks.
- Categorize operations by recovery characteristics (`REVERSIBLE`, `COMPENSABLE`, `IRREVERSIBLE`).
- Validate restored states post-restoration before authorizing further work.
- Preserve original operational errors separately from restoration runtime failures.
- Prevent concurrent, invalid, or unauthorized state restorations.

---

## Architecture & Component Responsibilities

The Checkpoints and Transaction Boundaries subsystem follows strict separation of concerns:

```
[Agent Execution Adapter / Runtime Loop]
               │
               ▼
   [TransactionManager] ─── (Coordinates boundaries & commit/rollback transitions)
               │
               ├──────────────────────────┐
               ▼                          ▼
      [CheckpointManager]     [CheckpointRestorationManager]
               │                          │
               ├─ Captures snapshots      ├─ Acquires exclusive locks
               ├─ Verifies integrity      ├─ Performs reverse restore
               └─ Saves to Repository     ├─ Runs compensations
                                          └─ Executes post-validation
                                                  │
                                                  ▼
                                      [RestorationValidator]
```

### Component Roles

1. **`CheckpointManager`**: Responsible solely for creating, capturing state snapshots across providers, calculating fingerprints, verifying initial integrity, and activating checkpoints.
2. **`TransactionManager`**: Coordinates transaction boundary lifecycles (`PENDING` -> `ACTIVE` -> `COMMITTED` / `ROLLED_BACK` / `COMPENSATED`), maps operations to boundary kinds, and resolves transaction requirements.
3. **`CheckpointRestorationManager`**: Handles restoration flows: acquires exclusive locks via `RuntimeLockManager`, verifies integrity and expiration, restores state in reverse order, executes compensation actions, restores Git/storage/memory/knowledge states, and runs post-restoration validation.
4. **`CheckpointIntegrityVerifier`**: Performs comprehensive structural and environmental integrity verification over `Checkpoint` contracts.
5. **`CheckpointRepository`**: Thread-safe storage maintaining checkpoint invariants, idempotency controls, and valid status state transitions.

---

## Contracts & Dataclasses

All contracts are immutable (`frozen=True`), serializable, and timezone-aware:

- **`Checkpoint`**: Immutable state snapshot capturing resource versions, Git state, storage snapshot ID, memory & knowledge state versions, locks, and fingerprint.
- **`CheckpointResource`**: Describes an individual resource key, type, version, and criticality.
- **`CheckpointIntegrity`**: Structured verification result containing `CheckpointIntegrityStatus`, fingerprint validity, resource validity, and issues list.
- **`CheckpointCreationRequest` & `CheckpointCreationResult`**: Input and output contracts for checkpoint creation.
- **`CheckpointRestorationRequest` & `CheckpointRestorationResult`**: Input and output contracts for restoration execution.
- **`CheckpointDifference`**: Computes structural diffs between checkpoint state and current state.
- **`TransactionBoundary`**: Defines boundary kind (`ATOMIC`, `COMPENSABLE`, `CHECKPOINT_SEQUENCE`, `INDEPENDENT`, `IRREVERSIBLE_WITH_APPROVAL`), status, and timestamp bounds.
- **`TransactionOperation`**: Tracks executed operations within a transaction along with recovery classification and compensation actions.
- **`CompensationAction`**: Action definition to compensate completed non-reversible operations.
- **`RestorationValidationResult`**: Outcome of post-restoration validation.

---

## Transaction Boundary Kinds

1. **`ATOMIC`**:
   - All operations must be reversible.
   - Requires a complete, valid checkpoint.
   - Failure mandates complete rollback.
   - Forbids external irreversible effects.
2. **`COMPENSABLE`**:
   - Operations without exact rollback must define explicit `CompensationAction`s.
   - Compensation is recorded separately and not treated as exact rollback.
3. **`CHECKPOINT_SEQUENCE`**:
   - Supports intermediate checkpoints across multi-step operation groups.
   - Rollback returns state to the latest valid intermediate checkpoint.
4. **`INDEPENDENT`**:
   - Operations maintain individual results.
   - Operational failure does not trigger automatic rollback of previously succeeded operations.
5. **`IRREVERSIBLE_WITH_APPROVAL`**:
   - Mandates active human/system approval prior to execution.
   - Records residual risk and irreversible side effects explicitly.

---

## Restoration Flow & Invariants

### Sequence
1. Fetch checkpoint by `checkpoint_id`.
2. Assert status is `ACTIVE` and `expires_at` has not passed.
3. Perform integrity verification using `CheckpointIntegrityVerifier`.
4. Acquire exclusive locks on affected resources via `RuntimeLockManager`.
5. Check current resource versions and calculate differences.
6. Perform reverse-order resource version restoration.
7. Execute registered compensation handlers for compensable operations.
8. Restore Git repository state via `GitStateProvider`.
9. Restore external storage snapshot via `StorageSnapshotProvider`.
10. Restore agent memory state via `MemoryStateProvider`.
11. Restore knowledge base state via `KnowledgeStateProvider`.
12. Perform post-restoration validation via `RestorationValidator`.
13. Update checkpoint status (`RESTORED`, `PARTIALLY_RESTORED`, or `FAILED`).
14. Release exclusive locks in `finally` block.

### Key Invariants
- **Original Error Preservation**: The error triggering restoration (`original_error`) is strictly separated from any error occurring during the restoration procedure (`restoration_error`).
- **No Concurrent Restores**: Exclusive locking prevents racing restoration requests.
- **Fail-Safe**: Absence of a required provider or invalid checkpoint integrity blocks restoration cleanly without mutating live resources.
- **No Direct Commit**: `AgentExecutionAdapter` never commits transactions directly; commits require post-validation success via `TransactionManager.commit(...)`.

---

## Integration with Existing Phases

- **Phase 9.13 (Operation Execution Adapter)**: Operates with `AgentExecutionAdapter` to trigger checkpoint creation before state-modifying operations and attach `checkpoint_id` / `transaction_boundary_id` to operation results.
- **Phase 9.14 (Validation Integration)**: `AgentValidationAdapter` executes post-execution validation before transaction commit. If validation mandates `ROLLBACK`, the checkpoint remains `ACTIVE` for Recovery Manager processing in Phase 9.16.
- **Phase 9.16 (Recovery Manager Preview)**: Provides the state foundation, active checkpoints, and compensation actions required for Phase 9.16 automated recovery strategies.

---

## Security Invariants

- No shell commands, `subprocess`, `eval`, or `exec` execution within Agent Runtime.
- Exclusive locks enforced during restoration.
- Irreversible operations strictly require explicit approval.
- No sensitive snapshot data or secrets included in log records or event payloads.
- Path traversal and unverified file access prevented via provider abstractions.
