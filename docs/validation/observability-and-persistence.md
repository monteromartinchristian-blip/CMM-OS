# 7.11 — Observability and Persistence

## Objective

Build the observability and persistence layer for the CMM OS validation
infrastructure so that every execution can be:

- identified unambiguously;
- reconstructed after it finishes;
- queried retrospectively;
- audited;
- compared with other executions;
- correlated with results, steps, findings, artifacts, and the Commit Gate;
- consumed by future CLI, API, and CI interfaces (see 7.12);
- provided as structured input to phases 8 and 9.

---

## Architecture

```text
ValidationContext + ValidationResult
            ↓
ValidationObservabilityService
     ┌──────┴──────┐
     │             │
  sanitize    calculate metrics
     │             │
     └──────┬──────┘
            │
  ValidationRepositoryProtocol
            │
  LocalValidationRepository
            │
      Storage Root (.cmm/validation/)
```

### Module layout

```text
cmm/validation/observability/
├── __init__.py          # public API exports
├── exceptions.py        # ValidationPersistenceError, ValidationRecordConflictError, …
├── models.py            # ValidationExecutionRecord, ValidationLogEntry
├── metrics.py           # ValidationMetrics, ValidationMetricsCalculator
├── sanitization.py      # sanitize_validation_data
├── protocols.py         # ValidationRepositoryProtocol (typing.Protocol)
├── history.py           # ValidationHistoryQuery, ValidationHistoryPage
├── repository.py        # LocalValidationRepository
└── service.py           # ValidationObservabilityService
```

---

## Contracts

### `ValidationExecutionRecord`

Immutable (`frozen=True, slots=True`), versionable snapshot of one
validation run.

| Field | Type | Description |
|---|---|---|
| `id` | `str` | `validation-<uuid>` — unique, stable, file-safe |
| `schema_version` | `int` | Always `1` for 7.11 |
| `status` | `str` | `running`, `passed`, `failed`, `warning`, `error`, `cancelled`, `timed_out` |
| `policy` | `str \| None` | Policy name applied |
| `actor` | `str \| None` | Who triggered the run |
| `execution_mode` | `str` | `local`, `ci`, … |
| `project_root` | `str \| None` | Absolute path of the workspace |
| `branch` | `str \| None` | Git branch |
| `base_commit` | `str \| None` | Git base SHA |
| `changed_files` | `tuple[str, …]` | Relative paths of changed files |
| `affected_tests` | `tuple[str, …]` | Tests selected by impact analysis |
| `step_results` | `tuple[dict, …]` | Serialised step results |
| `findings` | `tuple[dict, …]` | Serialised findings |
| `artifacts` | `tuple[dict, …]` | Serialised artifact summaries |
| `metrics` | `dict \| None` | Serialised `ValidationMetrics` |
| `gate_result` | `dict \| None` | Serialised `CommitGateResult` |
| `commit_hash` | `str \| None` | Provisional commit SHA if created |
| `started_at` | `datetime \| None` | UTC start timestamp |
| `completed_at` | `datetime \| None` | UTC completion timestamp |
| `created_at` | `datetime` | UTC record creation timestamp |
| `metadata` | `dict` | Arbitrary safe key/value pairs |

**Invariants:**
- `id` non-empty.
- `schema_version` = 1 (future versions raise `UnsupportedValidationSchemaError`).
- `completed_at >= started_at` when both are set.
- Final statuses (`passed`, `failed`, `warning`, `error`, `cancelled`, `timed_out`) require `completed_at`.
- If `gate_result.commit_created` is `True`, `commit_hash` must be set.
- All collections normalised to tuples; `metadata` defensively copied.

### `ValidationLogEntry`

Structured log event linked to a validation execution.

| Field | Type | Description |
|---|---|---|
| `id` | `str` | `log-<uuid>` |
| `validation_id` | `str` | Parent execution ID |
| `timestamp` | `datetime` | UTC timestamp (tz-aware) |
| `level` | `str` | `debug`, `info`, `warning`, `error`, `critical` |
| `component` | `str` | Emitting subsystem |
| `event` | `str` | Stable event identifier (see Events below) |
| `message` | `str` | Human-readable description |
| `step_name` | `str \| None` | Associated step |
| `duration_ms` | `int \| None` | Operation duration |
| `status` | `str \| None` | Operation status |
| `correlation_id` | `str \| None` | Cross-entry correlation (typically `validation_id`) |
| `metadata` | `dict` | Arbitrary safe key/value pairs |

### `ValidationMetrics`

Aggregated statistics derived from a `ValidationResult`.

| Field | Type | Description |
|---|---|---|
| `total_duration_ms` | `int` | End-to-end wall time |
| `step_durations_ms` | `dict[str, int]` | Per-step durations |
| `total_steps` | `int` | Number of steps executed |
| `passed_steps` | `int` | Steps with PASSED status |
| `failed_steps` | `int` | Steps with FAILED status |
| `warning_steps` | `int` | Steps with WARNING status |
| `skipped_steps` | `int` | Steps with SKIPPED status |
| `timed_out_steps` | `int` | Steps with TIMED_OUT status |
| `cancelled_steps` | `int` | Steps with CANCELLED status |
| `error_steps` | `int` | Steps with ERROR status |
| `tests_executed` | `int` | Tests run (from step metadata) |
| `tests_passed` | `int` | Tests passed |
| `tests_failed` | `int` | Tests failed |
| `tests_skipped` | `int` | Tests skipped |
| `findings_by_severity` | `dict[str, int]` | Findings per severity level |
| `artifacts_count` | `int` | Artifact count |
| `full_suite_executed` | `bool` | Whether the full test suite ran |
| `gate_allowed` | `bool \| None` | Gate decision |
| `timeout_count` | `int` | Step timeouts |
| `cancellation_count` | `int` | Step cancellations |

### `ValidationHistoryQuery`

Immutable filter for querying execution history. All fields optional (`None` = no filter).

Filters: `policy`, `status`, `actor`, `branch`, `started_after`, `started_before`, `gate_allowed`, `has_commit`.
Pagination: `limit` (1–500, default 50), `offset` (default 0).

### `ValidationHistoryPage`

Immutable paginated result: `items`, `total`, `limit`, `offset`, `has_more`.

---

## Storage Layout

```text
<project_root>/.cmm/validation/
├── executions/
│   └── validation-<uuid>.json       ← atomic JSON per execution
├── logs/
│   └── validation-<uuid>.jsonl      ← append-only JSONL log stream
├── artifacts/
│   └── validation-<uuid>/
│       └── <artifact-id>.json       ← one JSON per artifact
└── index.json                       ← compact searchable summary
```

### Conventions

- **UTF-8** everywhere.
- **JSON**: `indent=2`, `sort_keys=True`, `ensure_ascii=False`.
- **JSONL**: one JSON object per line, no trailing commas.
- **File names**: only alphanumerics, hyphens, underscores (see `_safe_filename`).
- **No pickle, no external databases, no shell execution at load time.**

---

## Schema Versioning

Every record carries `schema_version: int`. The only understood version
in 7.11 is **1**.

| Version | Code | Behaviour |
|---|---|---|
| 1 | 7.11 | Read and written normally |
| > 1 | Future | `UnsupportedValidationSchemaError` raised; file left in place |

Migration helpers and down-grade support are **out of scope for 7.11**.

---

## Atomicity

Full execution records and artifact files are written atomically:

```
serialize → write to tempfile → flush → fsync → os.replace → done
```

JSONL logs use `open(…, "a")` append. A single threading lock serialises
writes within one process. Multi-process concurrent writers are **not
supported** in 7.11.

---

## Sanitisation

All data is sanitised before being handed to the repository layer via
`sanitize_validation_data(value)`.

**Sensitive keys** (case-insensitive substring match):
`token`, `api_key`, `apikey`, `password`, `passwd`, `secret`,
`authorization`, `cookie`, `credential`, `private_key`, `access_key`,
`refresh_token`.

**URL-embedded credentials** (`scheme://user:pass@host`) are also redacted.

Replacement value: `[REDACTED]`.

Rules:
- Works recursively on mappings, lists, tuples, strings.
- Original objects are **never mutated**.
- Non-sensitive data is **preserved exactly**.

---

## Logs

### Events

Stable event identifiers (not free-form text):

| Event | Description |
|---|---|
| `validation.started` | Execution started |
| `validation.policy.resolved` | Policy resolved |
| `validation.step.started` | Step started |
| `validation.step.completed` | Step finished successfully |
| `validation.step.failed` | Step finished with failure |
| `validation.step.timed_out` | Step timed out |
| `validation.cancelled` | Execution was cancelled |
| `validation.completed` | Execution finished |
| `validation.failed` | Execution failed overall |
| `validation.persistence.failed` | Persistence error occurred |
| `validation.gate.evaluated` | Commit gate was evaluated |
| `validation.gate.approved` | Gate approved the commit |
| `validation.gate.rejected` | Gate rejected the commit |
| `validation.commit.created` | Provisional commit created |

---

## Metrics

`ValidationMetricsCalculator.calculate(validation_result, gate_result=None)`
is a pure, side-effect-free function. It reads from the existing
`ValidationResult` and derives all counts, durations, and severity
distributions without any I/O.

---

## History and Retrieval

The index (`index.json`) stores compact summaries to enable filtered
listing without reading every execution file. Filters applied in-memory
on the loaded index:

```python
page = repo.list_executions(ValidationHistoryQuery(status="passed", limit=20, offset=0))
```

If the index is corrupt, `list_executions` falls back to a directory
scan of `executions/`. `rebuild_index()` reconstructs the index from
all readable execution files.

---

## Artifacts

Artifacts are persisted as individual JSON files under
`artifacts/<validation-id>/<artifact-id>.json`.

**Content size limit:** `ARTIFACT_CONTENT_MAX_BYTES` (default 512 KiB).
Content exceeding this limit is replaced by a truncation marker:

```json
{
  "_truncated": true,
  "_reason": "content exceeded ARTIFACT_CONTENT_MAX_BYTES",
  "_limit_bytes": 524288
}
```

Files pointing outside the project root are not read automatically.
Binary content is not persisted.

---

## Pipeline Integration

`ValidationPipeline` accepts an optional `observability` field:

```python
pipeline = ValidationPipeline(
    executor=executor,
    registry=registry,
    observability=service,   # or None (default)
)
result = pipeline.run(context, steps)
```

- `observability=None` → identical behaviour to pre-7.11 pipeline.
- With observability: start is recorded, completion is recorded, a stable
  `validation-<uuid>` ID is assigned and used as `result.id`.

**Persistence failure policy:**
- Observability failures are caught and logged; they never alter the
  validation result status or raise to the caller.
- `except Exception: pass` is strictly forbidden except in the internal
  `_record_persistence_failure` best-effort handler.

---

## Commit Gate Integration

After evaluating the gate:

```python
service.record_gate_result(validation_id=vid, gate_result=gate_result)
```

After completing execution with a gate result:

```python
service.complete_execution(
    validation_id=vid,
    result=validation_result,
    gate_result=gate_result,
)
```

The commit hash is extracted from `gate_result.commit_hash` and stored in
the execution record. The gate result is embedded as a sanitised dict.

---

## Recovery

| Failure | Detection | Behaviour |
|---|---|---|
| Invalid JSON in execution file | `json.JSONDecodeError` | `ValidationStorageCorruptionError` — file left in place |
| Truncated JSONL line | `json.JSONDecodeError` | Skip that line; return healthy ones |
| Corrupt index | `json.JSONDecodeError` or wrong type | Fall back to directory scan |
| Unknown schema version | `schema_version > 1` | `UnsupportedValidationSchemaError` |
| Corrupt artifact | `json.JSONDecodeError` | `ValidationArtifactStorageError` |

**No data is deleted automatically.** Corrupt files are left in place for
manual diagnosis.

---

## Exceptions

All exceptions extend `ValidationErrorBase` (code, message, metadata):

| Exception | When raised |
|---|---|
| `ValidationPersistenceError` | General I/O / serialisation failure |
| `ValidationRecordNotFoundError` | Execution ID not in repository |
| `ValidationRecordConflictError` | Disallowed state transition (regression) |
| `ValidationStorageCorruptionError` | File is present but malformed |
| `UnsupportedValidationSchemaError` | `schema_version` is from the future |
| `ValidationArtifactStorageError` | Artifact-specific storage failure |

Extra fields: `path`, `validation_id`, `cause`.

---

## Usage Examples

### Minimal pipeline with observability

```python
from pathlib import Path
from cmm.validation import (
    LocalValidationRepository,
    ValidationObservabilityService,
    ValidationPipeline,
    ValidationExecutor,
    ValidationRegistry,
    ValidationContext,
)

project_root = Path("/workspace")
store = project_root / ".cmm" / "validation"

repo = LocalValidationRepository(store)
service = ValidationObservabilityService(repository=repo)

pipeline = ValidationPipeline(
    executor=ValidationExecutor(),
    registry=ValidationRegistry(),
    observability=service,
)

context = ValidationContext(
    project_root=project_root,
    actor="human:christian",
    branch="feature/my-change",
)
result = pipeline.run(context, steps=[])
```

### Querying history

```python
from cmm.validation import ValidationHistoryQuery, LocalValidationRepository
from pathlib import Path

repo = LocalValidationRepository(Path("/workspace/.cmm/validation"))
page = repo.list_executions(
    ValidationHistoryQuery(status="passed", actor="human:christian", limit=20)
)
for record in page.items:
    print(record.id, record.started_at, record.status)
```

### Rebuilding index after corruption

```python
repo = LocalValidationRepository(store)
count = repo.rebuild_index()
print(f"Rebuilt index with {count} entries")
```

---

## Limitations

- No multi-process concurrent write support.
- No general migration framework (7.11 supports schema version 1 only).
- No SQLite, PostgreSQL, or remote storage (local JSON only).
- No full-text search across log messages.
- Artifact binary content is not persisted (JSON only).
- No automatic backup or compaction.
- CLI, API, and CI interfaces are deferred to 7.12.

---

## Extension Points

- Replace `LocalValidationRepository` with any class satisfying
  `ValidationRepositoryProtocol` (SQLite, remote API, object storage).
- Add migration support by extending `ValidationExecutionRecord.from_mapping`.
- Add Prometheus / OpenTelemetry metrics in a future phase by wrapping
  `ValidationMetricsCalculator`.
- Schema version 2 can add new fields without breaking existing readers
  (they will reject records with unknown versions until upgraded).
