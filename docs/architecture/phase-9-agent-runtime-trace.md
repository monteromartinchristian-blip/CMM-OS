# Phase 9.19 — Agent Runtime Trace

## Objective

Implementar una capa de trazabilidad estructurada para ejecuciones autónomas que permita reconstruir el qué, quién, cómo, por qué y resultado de cada ejecución, sin almacenar chain-of-thought, prompts privados, secretos ni datos sensibles.

## Architecture

The trace system is composed of the following layers:

```
┌─────────────────────────────────────────────────────────┐
│                    AgentTraceService                      │
│  (orchestrator: start, append, build, finalize, export)  │
├─────────────────────────────────────────────────────────┤
│  AgentTraceAssembler  │  AgentTraceRedactor              │
│  AgentTraceIntegrity  │  AgentTraceSummaryBuilder        │
├─────────────────────────────────────────────────────────┤
│  AgentTraceEventNormalizer  │  AgentTraceEventRegistry   │
├─────────────────────────────────────────────────────────┤
│  AgentTraceRepository (InMemoryAgentTraceRepository)     │
├─────────────────────────────────────────────────────────┤
│  AgentTraceCollector (optional Event Bus adapter)        │
└─────────────────────────────────────────────────────────┘
```

## Authoritative Sources

- **AgentRun** (`contracts.py`): agent_run_id, agent_id, autonomy_level, status
- **Goal** (`goal_contracts.py`): goal_id, goal_created_by, status
- **AgentIteration** (`runtime_loop_contracts.py`): iteration_id, sequence, state
- **RuntimeTransition** (`runtime_loop_contracts.py`): state_before, state_after, decision
- **Observation** (`observation_contracts.py`): observation_id, kind, summary
- **AgentCognitiveResult** (`cognitive_adapter_contracts.py`): reasoning_result_id, decision
- **InformationAcquisitionRequest/Result** (`information_acquisition_contracts.py`): gaps, questions
- **AgentWorkflowPlan** (`workflow_planner_contracts.py`): plan_id, status
- **PolicyEvaluationResult** (`policy_contracts.py`): decision, policy_refs
- **ApprovalRequest/ApprovalDecision** (`approval_contracts.py`): approval lifecycle
- **ActionBudget** (`action_budget_contracts.py`): budget events, consumption
- **AgentOperationRequest/Result** (`operation_execution_contracts.py`): operations
- **AgentValidationResult** (`validation_integration_contracts.py`): validations
- **Checkpoint** (`checkpoint_contracts.py`): checkpoint lifecycle
- **TransactionBoundary** (`checkpoint_contracts.py`): transaction lifecycle
- **RecoveryContext/RecoveryDecision** (`recovery_contracts.py`): recovery decisions
- **OutcomeEvaluation** (`outcome_evaluation_contracts.py`): outcome, completion decision
- **KnowledgeUpdateProposal/Result** (`knowledge_update_contracts.py`): knowledge updates
- **Event Bus events**: real-time event stream

## Contracts

All contracts are in `cmm/agent_runtime/agent_trace_contracts.py`:

- **AgentTrace**: Root aggregate with all trace data
- **AgentTraceHeader**: Trace metadata (trace_id, agent_run_id, goal_id, etc.)
- **AgentTraceIteration**: Per-iteration trace data
- **AgentTraceObservation**: Observation records
- **AgentTraceKnowledgeLoad**: Knowledge load records
- **AgentTraceCognitiveProfile**: Cognitive profile used
- **AgentTraceInformationGap**: Information gaps detected
- **AgentTraceQuestion**: Questions asked
- **AgentTraceReasoningReference**: Reference to reasoning result (no CoT)
- **AgentTraceRuntimeDecision**: Runtime decisions with reason codes
- **AgentTracePlanReference**: Plan references
- **AgentTracePolicyDecision**: Policy evaluation decisions
- **AgentTraceApprovalRequest/Decision**: Approval lifecycle
- **AgentTraceOperation**: Operation execution records
- **AgentTraceResourceChange**: Resource modification records
- **AgentTraceValidation**: Validation records
- **AgentTraceRecoveryDecision/Execution**: Recovery lifecycle
- **AgentTraceCheckpoint**: Checkpoint records
- **AgentTraceTransaction**: Transaction records
- **AgentTraceOutcomeEvaluation**: Outcome evaluation records
- **AgentTraceKnowledgeUpdate**: Knowledge update records
- **AgentTraceMemoryUpdate**: Memory update records
- **AgentTraceBudgetEvent**: Budget event records
- **AgentTraceWarning/Error**: Safe warning/error records
- **AgentTraceStopDecision**: Final stop decision
- **AgentTraceSummary**: Structured summary (no reasoning narrative)
- **AgentTraceQuery/QueryResult/Page**: Query types
- **AgentTraceIntegrityReport/RedactionReport**: Integrity and redaction reports
- **AgentTraceRetentionPolicy/ExportRequest/ExportResult**: Retention and export

## Event Registry

`AgentTraceEventRegistry` maps event types from phases 9.1–9.18 to `AgentTraceRecordKind` values. Explicit mapping only; no fallback to UNKNOWN as success. Supports aliases.

## Normalization

`AgentTraceEventNormalizer` converts raw event dicts into typed trace records. Supports custom normalizers per event type. Strict mode raises on unknown events.

## Redaction

`AgentTraceRedactor` removes:
- API keys, credentials, passwords, tokens
- Private keys (PEM format)
- Bearer tokens
- Chain-of-thought, internal reasoning, scratchpad
- Private prompts
- Oversized content (>10KB)
- Sensitive field names

Redaction is non-reversible. Produces a `AgentTraceRedactionReport`.

## Assembler

`AgentTraceAssembler` builds a complete `AgentTrace` from context and events:
1. Validate context
2. Normalize events
3. Deterministic sort
4. Deduplicate
5. Classify records
6. Calculate duration
7. Build summary
8. Compute fingerprint
9. Verify integrity
10. Set final status

## Integrity

`AgentTraceIntegrityVerifier` checks:
- Required IDs present
- Timestamp ordering
- No duplicate events
- Causality chains
- Final event for COMPLETE status
- Outcome presence
- Event count matching source_event_ids
- No prohibited fields

## Repository

`InMemoryAgentTraceRepository` provides thread-safe storage with:
- save/get/delete
- Query with filters (status, agent_run_id, goal_id, agent_id, outcome)
- Cursor-based pagination
- Versioning (previous versions preserved)
- Archive support
- Idempotency (same fingerprint returns existing)

## Service

`AgentTraceService` orchestrates:
- `start_trace()`: Create new trace
- `append_event(s)`: Add events to trace
- `build_trace()`: Full assembly from context
- `finalize_trace()`: Complete with stop decision
- `get_trace()`: Retrieve by ID
- `query_traces()`: Filtered queries
- `verify_trace()`: Integrity check
- `redact_trace()`: Apply redaction
- `archive_trace()`: Archive
- `export_trace()`: Export as JSON/JSONL/NDJSON/SUMMARY

## Collector

`AgentTraceCollector` is an optional Event Bus adapter:
- Subscribe to event types
- Buffer with configurable max size
- Auto-flush on buffer full
- Thread-safe
- Closed collector rejects new events

## Security

- No chain-of-thought stored
- No private prompts
- No credentials or secrets
- No stack traces
- No data outside permissions
- No arbitrary object serialization
- Redaction is non-reversible
- Fingerprint is SHA-256 based

## Events

21 trace events emitted:
- AGENT_TRACE_STARTED, EVENT_RECEIVED, EVENT_NORMALIZED, EVENT_REDACTED, EVENT_REJECTED
- AGENT_TRACE_RECORD_APPENDED, ITERATION_STARTED, ITERATION_COMPLETED
- AGENT_TRACE_BUILD_STARTED, BUILT, INTEGRITY_CHECKED, INTEGRITY_FAILED
- AGENT_TRACE_FINALIZATION_STARTED, FINALIZED
- AGENT_TRACE_REBUILD_STARTED, REBUILT
- AGENT_TRACE_QUERY_EXECUTED, EXPORTED, REDACTED, ARCHIVED, FAILED

## Testing

Test file: `tests/agent_runtime/test_agent_runtime_trace.py`

Covers: contracts, registry, normalizer, redactor, assembler, summary, integrity, repository, service, collector, iterations, errors, budget, outcome, knowledge, events, export, security.

## Limitations

- In-memory repository only (no persistent storage adapter)
- Collector requires manual Event Bus integration
- No automatic retention enforcement
- Export writes to string, not to files