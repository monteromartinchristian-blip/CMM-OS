# Phase 9.18 — Knowledge and Memory Update Architecture

## Architectural Overview

Phase 9.18 implements an auditable, policy-driven layer for transforming evaluated execution outcomes into structured proposals for knowledge updates, memory updates, operational lessons, invalidations, relations, and operation facts.

The system strictly enforces that no automated updates write directly to underlying database tables without passing through policy evaluation, deduplication, sensitivity filtering, permission verification, and optional human approval.

```
┌───────────────────────────┐
│     Outcome Evaluation    │ (Phase 9.17)
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│ KnowledgeCandidateExtractor│ (Extracts 17 candidate kinds)
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│   Relevance & Utility     │ (Filters trivial / low-utility)
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│   Confidence Evaluator    │ (Weights evidence & validation)
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│    Sensitivity Policy     │ (Filters secrets & PII)
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│ Deduplication & Conflict  │ (Identifies dupes & contradictions)
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│  Proposal Engine & Repo   │ (Persists proposal, emits events)
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│ Update Execution Manager  │ (Applies via explicit Store Writers)
└───────────────────────────┘
```

## Data Contracts & Immutable Models

All contracts defined in `cmm/agent_runtime/knowledge_update_contracts.py` are frozen dataclasses with deterministic SHA256 fingerprints and UTC timestamps:

- `AgentKnowledgeUpdateProposal`: Complete container of additions, updates, invalidations, relations, facts, decisions, lessons, and rejected items.
- `KnowledgeUpdateCandidate`: Raw candidate unit extracted from runtime outputs.
- `KnowledgeAddition`: Approved addition item.
- `KnowledgeUpdate`: Approved versioned update item.
- `KnowledgeInvalidation`: Approved invalidation item.
- `KnowledgeRelation`: Semantic relationship link.
- `OperationFact`: Auditable operation execution fact.
- `AgentDecisionRecord`: Record of key runtime decisions.
- `OperationalLesson`: Reusable operational pattern or constraint.
- `RejectedKnowledgeItem`: Explicit record of rejected candidate with reason code.
- `MemoryUpdateCandidate` & `MemoryWriteDecision`: Memory write candidate and governance decision.

## Extracted Candidate Kinds (17)

1. `CREATED_GOAL`
2. `COMPLETED_GOAL`
3. `OPERATION_RESULT`
4. `VALIDATED_STATE`
5. `STRUCTURAL_CHANGE`
6. `DECISION`
7. `CONSTRAINT`
8. `EXPLICIT_PREFERENCE`
9. `REPRODUCIBLE_ERROR`
10. `FAILED_STRATEGY`
11. `SUCCESSFUL_STRATEGY`
12. `DEPENDENCY`
13. `CONTRADICTION`
14. `TECHNICAL_DEBT`
15. `GENERATED_ARTIFACT`
16. `NEW_CAPABILITY`
17. `UPDATED_RESOURCE`

## Operational Lessons (9 Kinds)

- `SUCCESS_PATTERN`
- `FAILURE_PATTERN`
- `RECOVERY_PATTERN`
- `ENVIRONMENT_CONSTRAINT`
- `TOOL_LIMITATION`
- `VALIDATION_REQUIREMENT`
- `DEPENDENCY_BEHAVIOR`
- `USER_PREFERENCE`
- `WORKFLOW_OPTIMIZATION`

## Security & Governance Invariants

- **No Chain-of-Thought**: Raw internal reasoning is stripped; only high-level decision summaries are preserved.
- **No Secrets**: Secret patterns (API keys, RSA keys, JWT tokens) are detected and rejected.
- **No Direct Table Writes**: Mutations occur strictly through passed `knowledge_writer` and `memory_writer` adapters.
- **No Fake Success**: Missing writers cause explicit `KnowledgeWriteError`.
- **No Inferred Preferences**: Only user-confirmed explicit preferences can be persisted to memory.
- **No Autoapproval of Restricted Data**: Sensitive/restricted candidates escalate to human approval.

## Integration with Phase 9.17 & Recovery Manager

- Reads authoritative output from `OutcomeEvaluation` and `GoalCompletionDecision`.
- Integrates recovery history from `RecoveryManager` to generate validated failure patterns and recovery lessons.
- Respects `INCONCLUSIVE` and `CANCELLED` states by withholding fact assertions while capturing valid lessons.

## Domain Events

Emits 27 structured events to EventBus with trace metadata:
`KNOWLEDGE_UPDATE_CONTEXT_CREATED`, `KNOWLEDGE_CANDIDATE_EXTRACTED`, `KNOWLEDGE_CANDIDATE_REJECTED`, `KNOWLEDGE_RELEVANCE_EVALUATED`, `KNOWLEDGE_CONFIDENCE_EVALUATED`, `KNOWLEDGE_SENSITIVITY_EVALUATED`, `KNOWLEDGE_PERMISSION_CHECKED`, `KNOWLEDGE_DUPLICATE_DETECTED`, `KNOWLEDGE_CONTRADICTION_DETECTED`, `KNOWLEDGE_UPDATE_PROPOSAL_CREATED`, `KNOWLEDGE_UPDATE_APPROVAL_REQUESTED`, `KNOWLEDGE_UPDATE_DECISION_MADE`, `KNOWLEDGE_UPDATE_APPLY_STARTED`, `KNOWLEDGE_ITEM_ADDED`, `KNOWLEDGE_ITEM_UPDATED`, `KNOWLEDGE_ITEM_INVALIDATED`, `KNOWLEDGE_RELATION_CREATED`, `OPERATIONAL_LESSON_CREATED`, `MEMORY_UPDATE_PROPOSED`, `MEMORY_UPDATE_REJECTED`, `MEMORY_UPDATE_CONFIRMATION_REQUESTED`, `MEMORY_UPDATE_APPLY_STARTED`, `MEMORY_ITEM_WRITTEN`, `MEMORY_ITEM_UPDATED`, `KNOWLEDGE_UPDATE_PARTIALLY_APPLIED`, `KNOWLEDGE_UPDATE_APPLIED`, `KNOWLEDGE_UPDATE_FAILED`.
