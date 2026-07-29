# Phase 9.32 — Model Execution Records

`ModelExecutionRecord` is the durable, privacy-safe audit record for one
model-assisted execution. It is intentionally a narrow layer over the
existing model fallback, routing, economic budget, validation, trace, and
runtime-event contracts.

## Boundaries

- `ModelExecutionRecord` stores provider/model identity, run hierarchy,
  token/cost/latency facts, routing/fallback references, validation summaries,
  quality/acceptance state, and trace correlation IDs.
- Prompts, responses, secrets, credentials, and complete payloads are never
  fields on the record. Metadata is rejected recursively when it contains
  sensitive keys or non-JSON values; hashes and authorized references are the
  supported content-retention mechanisms.
- `InMemoryModelExecutionRecordRepository` is the Phase 9.32 storage boundary.
  It returns immutable records, orders results by creation time and ID, and
  provides composable query filters without introducing SQL or another store.
- `ModelExecutionRecordService` owns lifecycle transitions and idempotent
  creation. Runtime events contain only a safe record summary and publication
  is best-effort after persistence.
- `ModelExecutionRecordAssembler` maps `ModelAttemptResult`, routing
  decisions, and economic estimates into the canonical record without making
  the record contract depend on those concrete types.
- `ModelExecutionObservabilityProjector` writes the existing
  `AgentModelInvocationRecord`; it does not create a second metrics or trace
  system.

## Lifecycle

Technical execution (`pending`, `completed`, `failed`) is independent from
quality acceptance (`pending`, `accepted`, `accepted_with_warning`,
`rejected`, `repaired`, `regenerated`, `escalated`, `cancelled`, `failed`).
This permits a technically successful call to be rejected later without
rewriting the execution outcome.
