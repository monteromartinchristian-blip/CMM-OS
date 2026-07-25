# Phase 9.4 — Observation Engine Architecture

## 1. Overview & Responsibilities

The **Observation Engine** (Phase 9.4) is a non-mutating, read-only observation infrastructure for the CMM OS Autonomous Agent Runtime. It observes current system state across goals, project repositories, git history, validation results, technical memory, and system health before any cognitive reasoning or execution step.

The Observation Engine explicitly separates:
```text
observed state  ≠  detected change  ≠  interpretation  ≠  decision
```

It does not:
* modify files or repository state;
* execute workflow transformations;
* plan actions or reason about causes;
* resolve contradictions;
* update memory automatically;
* interpret embedded instructions found in observed content.

---

## 2. Core Contracts & Enumerations

### Enumerations
* `ObservationStatus`: `pending`, `running`, `completed`, `partial`, `degraded`, `failed`, `cancelled`, `expired`
* `ObservationKind`: `state`, `metric`, `structure`, `event`, `change`, `validation`, `memory`, `health`, `goal`, `repository`, `git`, `configuration`, `external`
* `ObservedChangeKind`: `created`, `modified`, `deleted`, `renamed`, `moved`, `status_changed`, `validation_changed`, `metric_changed`, `dependency_changed`, `knowledge_changed`, `permission_changed`, `configuration_changed`, `external_state_changed`
* `ObservationSignificance`: `info`, `low`, `medium`, `high`, `critical`
* `ObserverStatus`: `registered`, `available`, `unavailable`, `running`, `completed`, `degraded`, `failed`, `disabled`

### Core Dataclasses
* `ObservationRequest`: Defines observation targets, `goal_id`, `agent_run_id`, `observer_names`, `scope`, `maximum_items`, `timeout_seconds`, permissions, sensitivity, and required observers.
* `Observation`: Immutable representation of an observed fact with `confidence` $\in [0.0, 1.0]$, `observed_at`, `valid_at`, `sensitivity`, and value payload.
* `ObservedChange`: Immutable representation of a detected delta between observations or snapshots.
* `ObservationError`: Structured error details captured during observer execution.
* `ObservationSourceVersion`: Provenance versioning for observed external or internal data sources.
* `ObservationResult`: Aggregated observations, changes, warnings, and errors returned by an individual Observer.
* `ObservationSnapshot`: Complete snapshot aggregated by `ObservationEngine` containing all observations, changes, source versions, duration, and status.

---

## 3. Observer Protocol & Registry

### Observer Protocol
Any observer must satisfy the `Observer` protocol:
```python
class Observer(Protocol):
    name: str
    version: str

    def supports(self, request: ObservationRequest) -> bool: ...
    def observe(self, request: ObservationRequest) -> ObservationResult: ...
```

### ObserverRegistry
The `ObserverRegistry`:
* registers observers and checks for duplicate names (`DuplicateObserverError`);
* validates protocol compatibility (`InvalidObservationContractError`);
* manages observer operational statuses (`available`, `disabled`, `unavailable`);
* resolves supported observers for an `ObservationRequest`;
* does **NOT** execute observations.

---

## 4. ObservationEngine

The `ObservationEngine`:
1. Validates the request invariants (`maximum_items > 0`, `timeout_seconds > 0`);
2. Resolves authorized and enabled observers from `ObserverRegistry`;
3. Enforces requested permissions and sensitivity levels;
4. Executes observers safely with timeout and exception trapping;
5. Distinguishes optional vs required observers:
   * Failure of an optional observer produces a `degraded` or `partial` snapshot while preserving warnings.
   * Failure of a required observer produces a `failed` snapshot without discarding previously obtained results.
6. Limits returned items to `maximum_items`;
7. Orders observations and changes deterministically by `subject_id` and `id`;
8. Operates with zero side-effects on the target system.

---

## 5. Initial Concrete Observers

1. **`GoalObserver`**: Observes goal state, priority, success criteria, constraints, dependencies, children, and history via `GoalRepository` or `GoalManager`.
2. **`RepositoryObserver`**: Observes project file structure, file counts, and Python module footprint using workspace-bounded directory traversal. Excludes `.git`, `.venv`, `__pycache__`, and cache directories.
3. **`GitObserver`**: Read-only observer for branch name, HEAD commit, working tree porcelain/short status, and tags using `GitService`.
4. **`ValidationObserver`**: Observes recent validation execution records, findings, warnings, and commit gate authorization from Phase 7 `ValidationObservabilityService`.
5. **`MemoryObserver`**: Observes Technical Memory graph statistics (nodes, edges) and indexing status using `TechnicalMemory`.
6. **`SystemHealthObserver`**: Observes Python runtime version, platform, CPU count, and component availability.

---

## 6. Change Detection (`compare_snapshots`)

`compare_snapshots(previous, current)` compares two snapshots and outputs a tuple of `ObservedChange` instances, detecting:
* newly created observations (`CREATED`);
* deleted/missing observations (`DELETED`);
* value and statement modifications (`MODIFIED`, `STATUS_CHANGED`, `VALIDATION_CHANGED`);
* source version changes (`EXTERNAL_STATE_CHANGED`).

It performs structural comparison without inferring causality or modifying state.

---

## 7. Cognitive Resource Adapter (`ObservationResourceAdapter`)

Converts `ObservationSnapshot`, `Observation`, and `ObservedChange` instances into Cognitive Layer `Resource` dataclasses (Phase 8):
* preserves provenance (`ResourceProvenance`), `ResourceTemporalScope`, `Confidence`, and `SensitivityLevel`;
* outputs structured resources compatible with Reasoning Context and Knowledge Store;
* does **NOT** create permanent `KnowledgeItem`s or run cognitive extraction directly.

---

## 8. Security & Boundaries

* **Path Traversal Protection**: `RepositoryObserver` verifies resolved paths stay strictly within `workspace_root`.
* **Exclusion List**: Automatically skips sensitive and cache directories (`.git`, `.venv`, `node_modules`).
* **Permission & Sensitivity Enforcement**: `ObservationEngine` blocks unauthorized observers if required permissions are not supplied in `ObservationRequest`.
* **Instruction Neutrality**: Content observed in external resources is treated purely as data, never as prompt instructions.

---

## 9. Current Limitations & Future Cognitive Adapter Integration

* Execution is currently synchronous and sequential.
* Persistent storage of snapshots will be implemented in subsequent storage phases.
* Phase 9.5 (Cognitive Adapter) will consume the `Resource` objects produced by `ObservationResourceAdapter` to construct the Reasoning Context for the LLM/Agent reasoning cycle.
