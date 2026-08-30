# Domain Sessions Reference

**Status:** `IMPLEMENTED_PENDING_AUDIT`; independent re-audit V5 pending (Phase 10.34)

## 1. Overview

**Phase 10.34 — Domain Sessions** extends the shared Phase 8 session infrastructure to preserve, validate, and restore domain intelligence state across conversational pauses and process restarts.

### Core Architectural Invariants

1. **No Parallel Session Engine**: Domain state is attached to the canonical shared Phase 8 session envelope via `DomainSessionCodec` using `DOMAIN_SESSION_EXTENSION_KEY = "domain_session"`. No secondary session engine, repository, or event store is created.
2. **Untrusted Snapshot Invariant**: `Persisted domain snapshot != current authorization or current truth`. Persisted permissions and operation availabilities are historical evidence and are strictly re-evaluated against current policies upon resumption.
3. **Pure, Side-Effect-Bounded Resumption**: Mere resumption does not execute domain operations, grant approvals, mutate memory, or write knowledge.
4. **Fail-Closed Revalidation**: If primary domain availability, compatibility, high-impact resource/knowledge validity, or security validation fails, resumption is blocked.
5. **Exact 23-Event Catalog**: The general domain event catalog remains fixed at 23 events (`GENERAL_EVENT_COUNT = 23`). No fake `domain.session.resumed` event is created.

---

## 2. Core Contracts

### `DomainSessionContext`

Immutable, slotted, frozen dataclass holding domain state within a session:

```python
@dataclass(frozen=True, slots=True)
class DomainSessionContext:
    session_id: str
    primary_domain: str
    supporting_domains: tuple[str, ...] = ()
    domain_versions: MappingProxyType[str, str] = ...
    composition_id: str | None = None
    effective_profile: str | None = None
    effective_rule_ids: tuple[str, ...] = ()
    effective_permission_refs: tuple[str, ...] = ()
    active_workflow_refs: tuple[str, ...] = ()
    available_operation_ids: tuple[str, ...] = ()
    domain_resource_refs: MappingProxyType[str, tuple[str, ...]] = ...
    domain_knowledge_refs: MappingProxyType[str, tuple[str, ...]] = ...
    pending_domain_question_refs: tuple[str, ...] = ()
    domain_conflict_refs: tuple[str, ...] = ()
    approval_refs: tuple[str, ...] = ()
    partial_result_refs: tuple[str, ...] = ()
    trace_refs: tuple[str, ...] = ()
    domain_transitions: tuple[DomainSessionTransition, ...] = ()
    last_resolution_id: str | None = None
    next_recommended_step: str | None = None
    revision: int = 1
    updated_at: datetime = ...
    metadata: MappingProxyType[str, Any] = ...
```

### `DomainSessionResumeRequest` & `DomainSessionResumeResult`

Input and output contracts for resumption:

```python
@dataclass(frozen=True, slots=True)
class DomainSessionResumeRequest:
    session_id: str
    actor: str | None = None
    temporal_reference: datetime | None = None
    current_resource_versions: MappingProxyType[str, str] = ...
    current_knowledge_versions: MappingProxyType[str, str] = ...
    metadata: MappingProxyType[str, Any] = ...


@dataclass(frozen=True, slots=True)
class DomainSessionResumeResult:
    status: DomainSessionResumeStatus
    session_id: str
    previous_revision: int
    resumed_revision: int
    context: DomainSessionContext | None
    checks: tuple[DomainSessionCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_findings: tuple[str, ...] = ()
    recovered_question_refs: tuple[str, ...] = ()
    recovered_approval_refs: tuple[str, ...] = ()
    next_recommended_step: str | None = None
    recorded_resumption: bool = False
    metadata: MappingProxyType[str, Any] = ...
```

---

## 3. Resumption Lifecycle & Statuses

The `DomainSessionResumer` evaluates state through canonical lifecycle gates:

```text
Extract Context from Envelope
          ↓
Structural & Security Validation (No Credentials)
          ↓
Pure Revalidation (Active Domains, SemVer Compatibility, Drift, Temporal)
          ↓
Domain Continuity & Recomposition (Re-resolve / Recompose)
          ↓
Permission & Operation Availability Recalculation
          ↓
Workflow Reconciliation & Classification
          ↓
Question & Approval Recovery
          ↓
Candidate Resumed Revision Assembly
          ↓
Shared Session Persistence Boundary Execution
          ↓
Event Publication (Only for Real Transitions post-persistence)
```

### Resumption Statuses (`DomainSessionResumeStatus`)

- `RESUMED`: Session is valid, verified, and safe to continue.
- `RE_RESOLVED`: Primary domain was missing/inactive but safely re-resolved to an active fallback domain.
- `RECOMPOSED`: Supporting domains were updated/pruned due to registry changes.
- `REPLAN_REQUIRED`: Workflow or domain drift requires replanning.
- `WAITING_FOR_USER`: Resumed session has active questions requiring user response.
- `WAITING_FOR_APPROVAL`: Resumed session has pending approval requests.
- `BLOCKED`: Fail-closed block due to missing/invalidated resources, active conflicts, or authorization denial.
- `INCOMPATIBLE`: Breaking major version change or incompatible workflow detected.
- `FAILED`: Persistence or transactional execution failure.

---

## 4. Security & Credential Boundary

All domain session structures strictly enforce credential privacy by recursively validating state against canonical high-confidence patterns (`contains_high_confidence_credential`):
- API keys, OAuth tokens, AWS/GCP secrets, private keys, passwords, and authorization headers are rejected immediately.
- Rejection raises `DomainSessionSecurityError` without leaking matched secret fragments.

---

## 5. Event Integration

- Catalog count remains exactly 23 (`CANONICAL_DOMAIN_EVENTS`).
- Nominal resumption emits no invented event.
- Actual lifecycle transitions emit existing Phase 10.33 events (`domain.resolution.completed`, `domain.composition.updated`) only after successful shared-session persistence.

---

## 6. Acceptance & Verification

The subsystem is validated through **AT-DP-034** comprising 56 checkpoints:
- Full test suite: `tests/domains/test_domain_session_*.py`
- Focused domain session suite: 394 unit, security, regression, evidence, and acceptance tests passing on the V5 verified source tree.
- Audit V4 regression suite: 32 tests passing, including mutation-style AT-DP-034 evidence failures.
