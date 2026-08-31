# Phase 10.37 — Domain Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 10.37 as a deterministic, read-only Domain Intelligence observability projection that produces privacy-minimized log entries, exact-or-unavailable metrics, and per-domain health results from existing canonical Domain evidence without creating a parallel observability backend.

**Architecture:** Phase 10.37 is downstream of canonical Domain Registry/Loader/Resolver/Composition/Events/Trace/Sessions/Permissions/Operations/Workflows. New code is limited to immutable read-model contracts, a pure metrics calculator, a read-only health checker, and a thin composition service. It creates no store, repository, event bus, runtime, registry, loader, resolver, trace, session persistence, HTTP endpoint or DomainAPI extension.

**Tech Stack:** Python 3, frozen/slotted dataclasses and enums following existing `cmm.domains` conventions, SHA-256 deterministic serialization/digests, pytest, Ruff, `compileall`, existing official in-memory Domain components.

**Spec:** `docs/superpowers/specs/2026-08-31-domain-observability-design.md`

**Implementation start branch:** `feature/phase-10-domain-intelligence`

**Implementation start HEAD:** `33aed9eab68c5598361a842adc1396360b9933e3`

## Global Constraints

- Preserve the quarantine stash containing `quarantine: post-audit phase 10.32 uncommitted changes`.
- Do not use `git stash`, `git stash pop`, `git stash apply`, `git stash drop`, `git reset`, `git clean` or `git worktree`.
- Do not push or merge.
- Follow `TEST RED → MINIMAL IMPLEMENTATION → GREEN → CONTROLLED REFACTOR → NEXT BLOCK`.
- Stop on every unexpected regression; do not continue to later tasks with a known failure.
- Reuse canonical Domain Registry, Loader, Resolver, Composition, Events, Trace, Sessions, permission/approval, operation and workflow infrastructure.
- Domain Events remain the lifecycle event authority.
- Domain Trace remains the reference-only execution trace authority.
- Domain Sessions remain on the shared session persistence boundary.
- Domain Registry remains current Domain state authority.
- The Phase 10.33 general Domain event catalog remains exactly 23 unique built-in events.
- `DomainAPI` remains unchanged by Phase 10.37.
- Phase 10.37 creates no store, repository, event bus, runtime, engine, registry, loader, resolver or trace.
- Metrics never influence resolution, composition, conflict resolution, permissions, execution or memory.
- Health checks are read-only and never repair or mutate Domain state.
- Missing evidence is `UNAVAILABLE`, never guessed.
- `UNAVAILABLE` is semantically distinct from observed zero.
- Do not infer fallback from `primary_domain == domain:general`.
- Do not infer cross-domain transfer from the mere presence of supporting domains.
- Do not infer reused knowledge from repeated references.
- Do not infer avoided questions from absence of repeated questions.
- Do not infer prevented duplicates from absence of duplicates.
- Observability outputs are reference-first and privacy-minimized.
- Do not copy raw user input, prompts, chain-of-thought, resource bodies, KnowledgeItem payloads, memory content, credentials, secrets or unsafe exception payloads.
- User-generated text must never become a metric label.
- Unsupported metric evidence produces `UNAVAILABLE`; malformed, contradictory or unsafe evidence fails closed.
- No HTTP/REST/GraphQL/MCP/CLI/UI observability surface is in scope.
- Phase 11 platform-wide logs, dashboards, alerts, OpenTelemetry, Prometheus/Grafana and provider/model telemetry remain out of scope.
- Before independent audit, documentation may claim only `Phase 10.37 implementation complete — independent audit pending`, `DP-037 = IMPLEMENTED_PENDING_AUDIT`, and `AT-DP-037 = PASS`.
- The final audit candidate must be fully committed, worktree-clean and bundled from exact committed HEAD with `git archive`.

---

## Locked File Map

### Production files

Create:

```text
cmm/domains/observability_contracts.py
cmm/domains/observability_metrics.py
cmm/domains/observability_health.py
cmm/domains/observability_service.py
```

Modify only if required by tests and existing public conventions:

```text
cmm/domains/errors.py
cmm/domains/__init__.py
```

Do not create any equivalent of:

```text
cmm/domains/observability_store.py
cmm/domains/observability_repository.py
cmm/domains/observability_event_bus.py
cmm/domains/observability_runtime.py
cmm/domains/observability_engine.py
cmm/domains/observability_registry.py
cmm/domains/observability_loader.py
cmm/domains/observability_trace.py
```

### Phase 10.37 tests

Create:

```text
tests/domains/test_domain_observability_contracts.py
tests/domains/test_domain_observability_serialization.py
tests/domains/test_domain_observability_metrics.py
tests/domains/test_domain_observability_metrics_adversarial.py
tests/domains/test_domain_observability_health.py
tests/domains/test_domain_observability_service.py
tests/domains/test_domain_observability_privacy.py
tests/domains/test_domain_observability_public_api.py
tests/domains/test_domain_observability_boundaries.py
tests/domains/test_domain_observability_dp037_acceptance.py
```

Modify:

```text
tests/domains/test_domain_public_api.py
```

Reuse existing Domain test support instead of creating a fake runtime. In particular, prefer canonical registry/bootstrap fixtures and `tests/domains/domain_session_test_support.py` where applicable.

### Documentation files

Create:

```text
docs/reference/domain-observability.md
```

Modify after implementation and gates:

```text
docs/roadmap/phase-10-domain-intelligence.md
docs/reference/domain-intelligence-requirements-matrix.md
ROADMAP.md
```

---

## Interface Lock

The plan implements this public surface unless direct inspection of adjacent committed Phase 10 contracts proves a repository naming convention that requires a mechanically equivalent name:

```python
class DomainMetricStatus(str, Enum):
    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"


class DomainHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
```

```python
@dataclass(frozen=True, slots=True)
class DomainMetricBucket:
    key: str
    value: int | float

    def to_dict(self) -> dict[str, object]: ...
    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "DomainMetricBucket": ...
```

```python
@dataclass(frozen=True, slots=True)
class DomainMetricMeasurement:
    name: str
    status: DomainMetricStatus
    unit: str
    value: int | float | None = None
    buckets: tuple[DomainMetricBucket, ...] = ()
    evidence_reference_ids: tuple[str, ...] = ()
    unavailable_reason: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]: ...
    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "DomainMetricMeasurement": ...
```

```python
@dataclass(frozen=True, slots=True)
class DomainMetricsSnapshot:
    generated_at: datetime
    measurements: tuple[DomainMetricMeasurement, ...]
    evidence_event_ids: tuple[str, ...] = ()
    evidence_trace_ids: tuple[str, ...] = ()
    evidence_session_ids: tuple[str, ...] = ()
    digest: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]: ...
    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "DomainMetricsSnapshot": ...
```

```python
@dataclass(frozen=True, slots=True)
class DomainObservabilityLogEntry:
    source_kind: str
    source_id: str
    category: str
    status: str
    occurred_at: datetime
    primary_domain: str | None = None
    supporting_domains: tuple[str, ...] = ()
    session_id: str | None = None
    duration_ms: int | float | None = None
    reference_ids: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]: ...
    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "DomainObservabilityLogEntry": ...
```

```python
@dataclass(frozen=True, slots=True)
class DomainHealthFinding:
    code: str
    component: str
    severity: str
    message: str
    reference_ids: tuple[str, ...] = ()
    blocking: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]: ...
    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "DomainHealthFinding": ...
```

```python
@dataclass(frozen=True, slots=True)
class DomainHealthResult:
    domain_id: str
    status: DomainHealthStatus
    manifest: bool
    registry: bool
    resources: bool
    rules: bool
    operations: bool
    workflows: bool
    permissions: bool
    dependencies: bool
    last_checked_at: datetime
    findings: tuple[DomainHealthFinding, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]: ...
    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "DomainHealthResult": ...
```

```python
@dataclass(frozen=True, slots=True)
class DomainObservabilityReport:
    generated_at: datetime
    log_entries: tuple[DomainObservabilityLogEntry, ...]
    metrics: DomainMetricsSnapshot
    health_results: tuple[DomainHealthResult, ...]
    source_event_ids: tuple[str, ...] = ()
    source_trace_ids: tuple[str, ...] = ()
    source_session_ids: tuple[str, ...] = ()
    findings: tuple[DomainHealthFinding, ...] = ()
    digest: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]: ...
    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "DomainObservabilityReport": ...
```

The implementation may use typed private evidence adapters internally inside `observability_metrics.py` or `observability_service.py`, but MUST NOT export a new evidence registry or event system.

---

### Task 1: Contract RED — observed/unavailable, health and immutable serialization

**Files:**
- Create: `tests/domains/test_domain_observability_contracts.py`
- Create: `tests/domains/test_domain_observability_serialization.py`
- Create: `cmm/domains/observability_contracts.py`
- Modify if required: `cmm/domains/errors.py`

**Interfaces:**
- Produces: `DomainMetricStatus`, `DomainHealthStatus`, `DomainMetricBucket`, `DomainMetricMeasurement`, `DomainMetricsSnapshot`, `DomainObservabilityLogEntry`, `DomainHealthFinding`, `DomainHealthResult`, `DomainObservabilityReport`.
- Consumes: existing Domain JSON-safe/deep-freeze helpers if they are public and semantically generic. Do not duplicate Phase 10.33 privacy helpers under a new implementation if a safe reusable helper already exists.

- [ ] **Step 1: Read adjacent contracts before editing**

Inspect:

```bash
sed -n '1,260p' cmm/domains/event_contracts.py
sed -n '1,300p' cmm/domains/trace_contracts.py
sed -n '1,260p' cmm/domains/api_contracts.py
sed -n '1,260p' cmm/domains/errors.py
```

Record the actual repository conventions for:
- enum definitions;
- frozen/slotted dataclasses;
- `to_dict` / `from_dict`;
- datetime validation;
- metadata freezing;
- safe exception messages;
- digest helpers.

Do not change those existing files except `errors.py` if a narrowly scoped observability contract exception is necessary.

- [ ] **Step 2: Write failing contract tests**

Include tests equivalent to:

```python
def test_unavailable_metric_is_not_observed_zero():
    measurement = DomainMetricMeasurement(
        name="permissions.rejected",
        status=DomainMetricStatus.UNAVAILABLE,
        unit="count",
        unavailable_reason="NO_PERMISSION_EVIDENCE",
    )

    assert measurement.status is DomainMetricStatus.UNAVAILABLE
    assert measurement.value is None
    assert measurement.buckets == ()
    assert measurement.unavailable_reason == "NO_PERMISSION_EVIDENCE"
```

```python
def test_observed_zero_is_valid_and_distinct_from_unavailable():
    measurement = DomainMetricMeasurement(
        name="permissions.rejected",
        status=DomainMetricStatus.OBSERVED,
        unit="count",
        value=0,
        evidence_reference_ids=("permission-evidence:1",),
    )

    assert measurement.value == 0
    assert measurement.unavailable_reason is None
```

```python
def test_observed_metric_cannot_claim_unavailable_reason():
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainMetricMeasurement(
            name="permissions.rejected",
            status=DomainMetricStatus.OBSERVED,
            unit="count",
            value=0,
            evidence_reference_ids=("permission-evidence:1",),
            unavailable_reason="NO_PERMISSION_EVIDENCE",
        )
```

```python
def test_health_timestamps_must_be_timezone_aware():
    with pytest.raises(InvalidDomainObservabilityContractError):
        DomainHealthResult(
            domain_id="domain:health",
            status=DomainHealthStatus.HEALTHY,
            manifest=True,
            registry=True,
            resources=True,
            rules=True,
            operations=True,
            workflows=True,
            permissions=True,
            dependencies=True,
            last_checked_at=datetime(2026, 8, 31, 12, 0),
        )
```

Also assert:
- bucket keys are non-blank;
- bucket values are finite numbers and not booleans;
- canonical bucket ordering;
- canonical evidence-ID ordering/deduplication;
- metadata is deep-frozen/caller-alias safe;
- log entry timestamps are aware;
- negative duration is rejected;
- `DomainHealthStatus.HEALTHY` cannot contain a blocking finding;
- `DomainMetricsSnapshot` and `DomainObservabilityReport` do not accept inconsistent supplied digests.

- [ ] **Step 3: Run RED**

```bash
.venv/bin/pytest -q \
  tests/domains/test_domain_observability_contracts.py \
  tests/domains/test_domain_observability_serialization.py
```

Expected: import/contract failures because Phase 10.37 contracts do not exist.

- [ ] **Step 4: Implement minimum immutable contracts**

Implement the interface lock using repository conventions.

If an exception is needed, add only:

```python
class InvalidDomainObservabilityContractError(DomainError, ValueError):
    "Raised when Phase 10.37 observability data violates its public contract."
```

Use the actual existing Domain base error type found in `errors.py`; do not invent `DomainObservabilityError` as a new hierarchy.

- [ ] **Step 5: Implement deterministic serialization and digest**

Use one private canonical SHA-256 helper in `observability_contracts.py`, for example:

```python
def _digest_payload(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
```

The actual helper must pass repository JSON-safe validation and must not stringify arbitrary objects.

Digest payloads must exclude the digest field itself.

- [ ] **Step 6: Run GREEN**

```bash
.venv/bin/pytest -q \
  tests/domains/test_domain_observability_contracts.py \
  tests/domains/test_domain_observability_serialization.py

.venv/bin/ruff check \
  cmm/domains/observability_contracts.py \
  tests/domains/test_domain_observability_contracts.py \
  tests/domains/test_domain_observability_serialization.py

.venv/bin/ruff format --check \
  cmm/domains/observability_contracts.py \
  tests/domains/test_domain_observability_contracts.py \
  tests/domains/test_domain_observability_serialization.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add \
  cmm/domains/observability_contracts.py \
  cmm/domains/errors.py \
  tests/domains/test_domain_observability_contracts.py \
  tests/domains/test_domain_observability_serialization.py

git diff --cached --check
git commit -m "feat(domains): add observability contracts"
```

If `errors.py` is unchanged, do not stage it.

---

### Task 2: Metric catalog and pure calculator core

**Files:**
- Create: `cmm/domains/observability_metrics.py`
- Create: `tests/domains/test_domain_observability_metrics.py`

**Interfaces:**
- Consumes: Task 1 metric contracts.
- Produces: `CANONICAL_DOMAIN_OBSERVABILITY_METRICS`, `DomainObservabilityEvidence`, `DomainMetricsCalculator`.
- `DomainObservabilityEvidence` is a frozen input aggregate only; it is not a registry/store and is not persisted.

Use this design:

```python
@dataclass(frozen=True, slots=True)
class DomainObservabilityEvidence:
    registry_definitions: tuple[DomainDefinition, ...] = ()
    registry_records: tuple[DomainRegistryRecord, ...] = ()
    load_results: tuple[DomainLoadResult, ...] = ()
    resolution_results: tuple[DomainResolutionResult, ...] = ()
    compositions: tuple[DomainComposition, ...] = ()
    conflict_results: tuple[object, ...] = ()
    events: tuple[DomainEvent, ...] = ()
    traces: tuple[DomainTrace, ...] = ()
    sessions: tuple[DomainSessionContext, ...] = ()
    permission_evidence: tuple[object, ...] = ()
    approval_evidence: tuple[object, ...] = ()
    operation_evidence: tuple[object, ...] = ()
    workflow_evidence: tuple[object, ...] = ()
```

Before production implementation, replace each `object` with the actual canonical public result type discovered in the committed repository when one exists. Final production code must not keep a generic `object` in a field that has an existing stable contract.

Required calculator signature:

```python
class DomainMetricsCalculator:
    def calculate(
        self,
        evidence: DomainObservabilityEvidence,
        *,
        generated_at: datetime,
    ) -> DomainMetricsSnapshot:
        ...
```

- [ ] **Step 1: Read authoritative contracts**

Inspect exact definitions:

```bash
rg -n \
  'class DomainDefinition|class DomainRegistryRecord|class DomainLoadResult|class DomainResolutionResult|class DomainComposition|class DomainTrace|class DomainSessionContext' \
  cmm/domains

rg -n \
  'class .*Permission.*Result|class .*Approval.*|class .*Operation.*Result|class .*Workflow.*Result' \
  cmm/domains cmm/workflows cmm/agent_runtime
```

Bind evidence fields only to existing public contracts.

- [ ] **Step 2: Write RED for exact basic metrics**

Test the canonical catalog exactly:

```python
EXPECTED_METRICS = (
    "domains.installed",
    "domains.active",
    "loading.duration.mean_ms",
    "loading.failures",
    "resolution.decisions_by_domain",
    "resolution.confidence.mean",
    "resolution.ambiguous",
    "resolution.fallback",
    "execution.multi_domain",
    "execution.domains.mean",
    "conflicts.detected",
    "permissions.rejected",
    "approvals.requested",
    "operations.by_domain",
    "workflows.by_domain",
    "workflows.duration.mean_ms",
    "rules.applied_by_domain",
    "resources.loaded_by_domain",
    "cross_domain.transfers",
    "knowledge.reused",
    "questions.avoided_shared_context",
    "duplicates.prevented",
    "errors.by_domain_pack",
    "sessions.degraded",
    "external_domains.active",
)
```

Assert:

```python
assert CANONICAL_DOMAIN_OBSERVABILITY_METRICS == EXPECTED_METRICS
assert len(CANONICAL_DOMAIN_OBSERVABILITY_METRICS) == 25
assert len(set(CANONICAL_DOMAIN_OBSERVABILITY_METRICS)) == 25
```

Build canonical evidence using actual constructors and test:
- installed count;
- active count;
- load failure count;
- mean load duration from only explicit duration values;
- resolution decisions bucketed by explicit primary domain;
- mean confidence from only explicit confidence;
- ambiguous status count;
- multi-domain count from explicit participating domain sets;
- mean domains per execution.

- [ ] **Step 3: Run RED**

```bash
.venv/bin/pytest -q tests/domains/test_domain_observability_metrics.py
```

Expected: calculator/catalog missing.

- [ ] **Step 4: Implement the canonical catalog and pure calculator**

Rules:
- no registry lookups inside `calculate`;
- no event publication;
- no resolver calls;
- no store reads;
- no current-time calls inside the calculator;
- `generated_at` must be supplied and timezone-aware;
- deduplicate evidence by stable authoritative IDs before counting;
- sort all buckets by key;
- sort all measurement objects by canonical catalog order.

- [ ] **Step 5: Add zero/unavailable behavior**

For metrics where the evidence category is present but contains no matching occurrence, observed zero is allowed.

For metrics where no authoritative evidence category is supplied at all, return:

```python
DomainMetricMeasurement(
    name="permissions.rejected",
    status=DomainMetricStatus.UNAVAILABLE,
    unit="count",
    unavailable_reason="NO_PERMISSION_EVIDENCE",
)
```

Use stable reason codes.

- [ ] **Step 6: Run GREEN**

```bash
.venv/bin/pytest -q tests/domains/test_domain_observability_metrics.py

.venv/bin/ruff check \
  cmm/domains/observability_metrics.py \
  tests/domains/test_domain_observability_metrics.py

.venv/bin/ruff format --check \
  cmm/domains/observability_metrics.py \
  tests/domains/test_domain_observability_metrics.py
```

- [ ] **Step 7: Commit**

```bash
git add \
  cmm/domains/observability_metrics.py \
  tests/domains/test_domain_observability_metrics.py

git diff --cached --check
git commit -m "feat(domains): calculate observability metrics"
```

---

### Task 3: Adversarial metric semantics — no proxy inference

**Files:**
- Create: `tests/domains/test_domain_observability_metrics_adversarial.py`
- Modify: `cmm/domains/observability_metrics.py`

**Interfaces:**
- Consumes: Task 2 calculator.
- Produces: hardened semantics for fallback, transfers, knowledge reuse, avoided questions and duplicate prevention.

- [ ] **Step 1: Write RED for General Domain not implying fallback**

Construct a canonical resolved result whose primary domain is `domain:general` but carries no authoritative fallback marker/event.

Expected:

```python
metric.status is DomainMetricStatus.UNAVAILABLE
metric.value is None
```

- [ ] **Step 2: Write RED for supporting domains not implying transfer**

Construct a composition/trace with one primary and one supporting domain but no explicit transfer evidence.

Expected:

```python
metric.status is DomainMetricStatus.UNAVAILABLE
```

- [ ] **Step 3: Write RED for repeated knowledge reference not implying reuse**

Use two canonical traces that reference the same knowledge ID without an explicit reuse event/result.

Expected `knowledge.reused == UNAVAILABLE`.

- [ ] **Step 4: Write RED for absence-of-question not implying avoided question**

Supply session/trace evidence with no repeated question but no explicit avoided-question evidence.

Expected `questions.avoided_shared_context == UNAVAILABLE`.

- [ ] **Step 5: Write RED for absence-of-duplicate not implying duplicate prevention**

Supply resource/trace evidence with no duplicates but no explicit deduplication result.

Expected `duplicates.prevented == UNAVAILABLE`.

- [ ] **Step 6: Write RED for missing numeric samples not becoming zero**

Supply load/workflow evidence with records but no duration field.

Expected mean duration `UNAVAILABLE`, not `0.0`.

- [ ] **Step 7: Run RED**

```bash
.venv/bin/pytest -q tests/domains/test_domain_observability_metrics_adversarial.py
```

- [ ] **Step 8: Implement minimum hardening**

Only count these metrics when explicit authoritative evidence exists.

Do not add guessed fields to existing Phase 10.31–10.34 contracts just to make the metric available.

- [ ] **Step 9: Run focused GREEN**

```bash
.venv/bin/pytest -q \
  tests/domains/test_domain_observability_metrics.py \
  tests/domains/test_domain_observability_metrics_adversarial.py
```

- [ ] **Step 10: Commit**

```bash
git add \
  cmm/domains/observability_metrics.py \
  tests/domains/test_domain_observability_metrics_adversarial.py

git diff --cached --check
git commit -m "test(domains): harden observability metric semantics"
```

---

### Task 4: Evidence identity, canonical deduplication and source precedence

**Files:**
- Modify: `cmm/domains/observability_metrics.py`
- Create or extend: `tests/domains/test_domain_observability_service.py`

**Interfaces:**
- Produces deterministic evidence identity rules used by metrics and service.
- No fuzzy deduplication.

- [ ] **Step 1: Write RED for duplicate identical authoritative IDs**

Create two identical canonical events with the same stable event ID.

Expected:
- counted once;
- evidence ID appears once;
- deterministic snapshot digest.

- [ ] **Step 2: Write RED for conflicting duplicate ID**

Create two pieces of evidence with the same authoritative ID but materially different public content.

Expected a narrow Phase 10.37 invalid-evidence exception with:
- stable code/message;
- safe source type;
- safe source ID;
- no unsafe payload echo.

- [ ] **Step 3: Write RED for event/trace overlap**

Represent one operation occurrence in both DomainEvent and DomainTrace with an explicit shared operation/result reference.

Expected:
- `operations.by_domain` counts the authoritative occurrence once;
- event and trace may both appear in evidence references;
- counting identity comes from the shared stable reference, not string similarity.

- [ ] **Step 4: Implement canonical source precedence**

Use:

```text
DomainEvent
→ DomainTrace
→ canonical public result only when event/trace does not already represent the occurrence
```

Do not drop valid trace references merely because an event exists; deduplicate occurrences, not evidence sources.

- [ ] **Step 5: Run GREEN**

```bash
.venv/bin/pytest -q \
  tests/domains/test_domain_observability_metrics.py \
  tests/domains/test_domain_observability_metrics_adversarial.py \
  tests/domains/test_domain_observability_service.py
```

- [ ] **Step 6: Commit**

```bash
git add \
  cmm/domains/observability_metrics.py \
  tests/domains/test_domain_observability_service.py

git diff --cached --check
git commit -m "feat(domains): deduplicate observability evidence"
```

---

### Task 5: Read-only Domain health checker

**Files:**
- Create: `cmm/domains/observability_health.py`
- Create: `tests/domains/test_domain_observability_health.py`

**Interfaces:**
- Consumes: existing canonical registry/component registries/validation evidence.
- Produces: `DomainHealthChecker`.

Use a dependency-injected constructor bound to existing canonical types:

```python
class DomainHealthChecker:
    def __init__(
        self,
        *,
        domain_registry: DomainRegistry,
        resource_registry: DomainResourceRegistry,
        rule_registry: DomainRuleRegistry,
        operation_registry: DomainOperationRegistry,
        workflow_registry: DomainWorkflowRegistry,
        permission_registry_or_resolver: CanonicalPermissionType,
        manifest_validation_lookup: Callable[[str], DomainValidationResult | None],
        clock: Callable[[], datetime],
    ) -> None:
        ...
```

Replace names with exact committed canonical registry/permission type names discovered before writing production code.

Do not create fallback registries when a dependency is absent. Missing required canonical dependencies must fail closed.

Required method:

```python
def check(self, domain_id: str) -> DomainHealthResult:
    ...
```

- [ ] **Step 1: Inspect exact canonical registry APIs**

```bash
rg -n \
  'class DomainRegistry|class .*Resource.*Registry|class .*Rule.*Registry|class .*Operation.*Registry|class .*Workflow.*Registry|class .*Permission.*Registry' \
  cmm/domains

rg -n \
  'def get\(|def list\(|def resolve|def validate' \
  cmm/domains/*registry*.py cmm/domains/*permission*.py
```

Use those exact read APIs.

- [ ] **Step 2: Write RED for a healthy registered Domain**

Build General or another canonical internal Domain using existing bootstrap/registries.

Assert every dimension is positively verified.

- [ ] **Step 3: Write RED for missing registry record**

Unknown/missing domain:
- non-healthy/unknown status according to spec mapping;
- `registry is False`;
- stable finding code;
- no mutation.

- [ ] **Step 4: Write RED for broken required dependency**

Use a definition with one missing required dependency.

Expected:
- `dependencies is False`;
- non-healthy status;
- blocking finding.

- [ ] **Step 5: Write RED for unavailable optional dependency**

Expected:
- no false blocking required-dependency claim;
- may be `DEGRADED` if the canonical definition says optional dependency degradation applies.

- [ ] **Step 6: Write RED for intentionally unavailable operation**

A registered operation whose implementation availability is deliberately `UNAVAILABLE` remains structurally healthy if the contract is valid and registered.

Assert:

```python
assert result.operations is True
```

- [ ] **Step 7: Write RED for no mutation**

Capture before/after:
- registry snapshots or stable serializations;
- permission state;
- operation/workflow state.

Call `check`.

Assert exact equality.

- [ ] **Step 8: Run RED**

```bash
.venv/bin/pytest -q tests/domains/test_domain_observability_health.py
```

- [ ] **Step 9: Implement minimum read-only checker**

Rules:
- manifest boolean means positive verification, not “no exception”;
- registry missing is blocking;
- operation/workflow health checks registration, not execution;
- permission health checks structural availability/validity, not user authorization;
- no operation/workflow execution;
- no domain enable/disable/load/reload;
- no session creation;
- no health persistence.

- [ ] **Step 10: Run GREEN**

```bash
.venv/bin/pytest -q tests/domains/test_domain_observability_health.py

.venv/bin/ruff check \
  cmm/domains/observability_health.py \
  tests/domains/test_domain_observability_health.py

.venv/bin/ruff format --check \
  cmm/domains/observability_health.py \
  tests/domains/test_domain_observability_health.py
```

- [ ] **Step 11: Commit**

```bash
git add \
  cmm/domains/observability_health.py \
  tests/domains/test_domain_observability_health.py

git diff --cached --check
git commit -m "feat(domains): add read-only health checks"
```

---

### Task 6: Privacy-minimized log projection and report service

**Files:**
- Create: `cmm/domains/observability_service.py`
- Create: `tests/domains/test_domain_observability_privacy.py`
- Modify: `tests/domains/test_domain_observability_service.py`

**Interfaces:**
- Consumes: Task 1 contracts, Task 2 calculator, Task 5 checker, canonical DomainEvent/DomainTrace/public result evidence.
- Produces: `DomainObservabilityService`.

Required constructor:

```python
class DomainObservabilityService:
    def __init__(
        self,
        *,
        metrics_calculator: DomainMetricsCalculator,
        health_checker: DomainHealthChecker,
        clock: Callable[[], datetime],
    ) -> None:
        ...
```

Required methods:

```python
def calculate_metrics(
    self,
    evidence: DomainObservabilityEvidence,
) -> DomainMetricsSnapshot:
    ...
```

```python
def check_domain_health(self, domain_id: str) -> DomainHealthResult:
    ...
```

```python
def build_report(
    self,
    evidence: DomainObservabilityEvidence,
    *,
    health_domain_ids: tuple[str, ...] = (),
) -> DomainObservabilityReport:
    ...
```

- [ ] **Step 1: Write RED for reference-first event projection**

Given a canonical DomainEvent, produce a log entry containing only:
- event/source ID;
- safe event category/status;
- canonical domain IDs;
- timestamps/duration when explicitly available;
- stable public references;
- safe metadata allowlist.

Do not copy arbitrary `payload`/`metadata`.

- [ ] **Step 2: Write RED for trace projection**

Given a DomainTrace, expose:
- trace/source ID;
- participating Domain IDs;
- public reference IDs;
- final status;
- explicit duration.

Do not copy upstream result bodies.

- [ ] **Step 3: Write RED for unsafe secret-shaped content**

Use synthetic secret-like keys/values in caller-provided metadata/evidence.

Expected:
- fail closed;
- exception does not echo the synthetic secret;
- no partial report.

- [ ] **Step 4: Write RED for no raw sensitive content**

Build evidence containing synthetic:
- medical text;
- relationship text;
- memory content;
- raw user input.

Assert the strings do not occur anywhere in:

```python
json.dumps(report.to_dict(), ensure_ascii=False)
```

Only safe IDs/reference categories may remain.

- [ ] **Step 5: Write RED for metric-label safety**

Attempt to use user-generated text as a bucket key via unsupported/adversarial evidence.

Expected rejection or non-use; no dynamic user text metric label.

- [ ] **Step 6: Run RED**

```bash
.venv/bin/pytest -q \
  tests/domains/test_domain_observability_service.py \
  tests/domains/test_domain_observability_privacy.py
```

- [ ] **Step 7: Implement minimum projection service**

Use explicit field extraction.

Forbidden implementation pattern:

```python
metadata=dict(event.metadata)
payload=dict(event.payload)
```

Preferred pattern:

```python
safe_metadata = {
    "event_type": event.event_type,
    "sensitivity": event.sensitivity.value,
}
```

Only include fields that are proven public/safe by the canonical contract.

- [ ] **Step 8: Run GREEN**

```bash
.venv/bin/pytest -q \
  tests/domains/test_domain_observability_service.py \
  tests/domains/test_domain_observability_privacy.py
```

- [ ] **Step 9: Commit**

```bash
git add \
  cmm/domains/observability_service.py \
  tests/domains/test_domain_observability_service.py \
  tests/domains/test_domain_observability_privacy.py

git diff --cached --check
git commit -m "feat(domains): project observability reports"
```

---

### Task 7: Public exports and architectural boundary guards

**Files:**
- Modify: `cmm/domains/__init__.py`
- Modify: `tests/domains/test_domain_public_api.py`
- Create: `tests/domains/test_domain_observability_public_api.py`
- Create: `tests/domains/test_domain_observability_boundaries.py`

**Interfaces:**
- Exports only the approved Phase 10.37 public contracts/calculator/checker/service.
- Does not alter `DomainAPI`.

- [ ] **Step 1: Write RED for Phase 10.37 exports**

Assert importability from `cmm.domains` for the approved public symbols.

- [ ] **Step 2: Write RED for forbidden architecture files/symbols**

Test no forbidden observability infrastructure files or classes exist.

- [ ] **Step 3: Write RED for DomainAPI unchanged**

Capture the canonical `DomainAPI` protocol/method list as of implementation start HEAD using Git:

```bash
git show 33aed9eab68c5598361a842adc1396360b9933e3:cmm/domains/api_contracts.py \
  > /tmp/phase10_37_api_contracts_base.py
```

The implementation gate later also requires no source diff to `api_contracts.py`.

- [ ] **Step 4: Write RED for import side effects**

Fresh subprocess import must publish no event, mutate no registry, create no file and start no thread/task.

- [ ] **Step 5: Implement exports only**

Modify `cmm/domains/__init__.py` without importing internal test helpers or creating eager runtime state.

Do not modify `api_contracts.py`.

- [ ] **Step 6: Run GREEN**

```bash
.venv/bin/pytest -q \
  tests/domains/test_domain_observability_public_api.py \
  tests/domains/test_domain_observability_boundaries.py \
  tests/domains/test_domain_public_api.py
```

- [ ] **Step 7: Commit**

```bash
git add \
  cmm/domains/__init__.py \
  tests/domains/test_domain_observability_public_api.py \
  tests/domains/test_domain_observability_boundaries.py \
  tests/domains/test_domain_public_api.py

git diff --cached --check
git commit -m "feat(domains): expose observability surface"
```

---

### Task 8: Phase 10.33 23/23 and closed-boundary regression guards

**Files:**
- Extend: `tests/domains/test_domain_observability_boundaries.py`

**Interfaces:**
- Produces permanent regression tests protecting Phase 10.17/10.31/10.32/10.33/10.34/10.36 boundaries.

- [ ] **Step 1: Add exact 23/23 Domain Events guard**

Import the actual Phase 10.33 canonical event catalog constant.

Assert:

```python
assert len(CANONICAL_DOMAIN_EVENTS) == 23
assert len(set(CANONICAL_DOMAIN_EVENTS)) == 23
```

Use the actual constant name from `cmm/domains/event_catalog.py`.

- [ ] **Step 2: Guard no AgentRuntimeEventBus coupling**

Assert Phase 10.37 production modules do not import Phase 9/7 observability stores/services as Domain truth.

- [ ] **Step 3: Guard no mutation dependency direction**

Use AST/import inspection or stable source scan to ensure resolver/composer/conflict modules do not import `observability_*`.

- [ ] **Step 4: Guard session persistence boundary**

Assert no new:
- `DomainSessionRepository`;
- session enumeration;
- session store wrapper;
- `domain.session.resumed` event.

- [ ] **Step 5: Guard no trace persistence**

Assert no new trace store/repository and no `DomainObservabilityTrace`.

- [ ] **Step 6: Run focused boundaries**

```bash
.venv/bin/pytest -q tests/domains/test_domain_observability_boundaries.py
```

- [ ] **Step 7: Run existing Phase 10.33 privacy regressions immediately**

```bash
.venv/bin/pytest -q \
  tests/domains/test_domain_events_audit_v1_regressions.py \
  tests/domains/test_domain_events_audit_v2_regressions.py \
  tests/domains/test_domain_events_audit_v3_regressions.py \
  tests/domains/test_domain_events_dp033_acceptance.py \
  tests/domains/test_domain_public_api.py
```

Include later Phase 10.33 audit regression files if present.

- [ ] **Step 8: Commit**

```bash
git add tests/domains/test_domain_observability_boundaries.py
git diff --cached --check
git commit -m "test(domains): guard observability boundaries"
```

---

### Task 9: DP-037 connected acceptance test

**Files:**
- Create: `tests/domains/test_domain_observability_dp037_acceptance.py`

**Interfaces:**
- Consumes all Phase 10.37 production surface.
- Uses real canonical components or official in-memory implementations.
- Produces `AT-DP-037`.

Mocks may observe a boundary but may not replace the behavior being accepted.

- [ ] **Step 1: Build canonical registries and internal domains**

Reuse an existing standard bootstrap such as General + Health or another pair of already closed internal Domain Packs.

Prove:
- at least two real registered internal domains;
- at least one specialized domain active;
- no shadow observability registry.

- [ ] **Step 2: Produce a real canonical resolution**

Use the actual resolver and current canonical resolution context.

Require a specialized domain resolution with explicit confidence.

- [ ] **Step 3: Produce an ambiguity/blocked evidence path**

Use canonical resolver/selection policy for one request that yields explicit ambiguity, insufficient information or blocked state.

- [ ] **Step 4: Produce real composition/multi-domain evidence**

Use canonical composition with primary + supporting Domain.

Preserve the distinction between participation and transfer.

- [ ] **Step 5: Produce Domain Events through Phase 10.33 contracts**

Use `DomainEventFactory`/canonical adapters as appropriate.

Assert general catalog remains 23/23.

- [ ] **Step 6: Use real Domain Trace**

Assemble and validate a reference-only trace through existing Phase 10.17 components.

Do not copy upstream payloads.

- [ ] **Step 7: Use real shared-session evidence**

Reuse `tests/domains/domain_session_test_support.py` and canonical Phase 10.34 shared-session adapter/store.

Do not add a new repository or enumerate sessions.

- [ ] **Step 8: Use canonical permission and approval evidence**

Use existing permission/approval contracts/gates used by Phase 10.36 execution tests.

Demonstrate at least one explicit permission result and one approval request evidence path.

- [ ] **Step 9: Use canonical operation/workflow evidence**

Use official operation/workflow registry/execution result infrastructure without external side effects.

- [ ] **Step 10: Build the report**

Call the service with actual evidence and health domains.

- [ ] **Step 11: Assert connected metric truth**

Assert actual registered/active counts, resolution bucket/confidence, multi-domain execution and every other metric for which explicit evidence was supplied.

Metrics lacking explicit evidence must be `UNAVAILABLE`.

- [ ] **Step 12: Assert anti-inference invariants**

Explicitly assert all five anti-proxy rules from the spec.

- [ ] **Step 13: Assert health truth**

One real healthy Domain must verify all required health dimensions.

One isolated official in-memory broken dependency case must be non-healthy.

- [ ] **Step 14: Assert no mutation**

Snapshot authoritative structures before observability and compare after.

- [ ] **Step 15: Assert privacy**

Synthetic sensitive strings in upstream test payloads must not occur in serialized report output.

- [ ] **Step 16: Assert determinism**

Same evidence + same injected time must produce identical serialization and digest.

- [ ] **Step 17: Run RED then GREEN**

```bash
.venv/bin/pytest -q tests/domains/test_domain_observability_dp037_acceptance.py
```

Expected final: PASS.

- [ ] **Step 18: Commit**

```bash
git add tests/domains/test_domain_observability_dp037_acceptance.py
git diff --cached --check
git commit -m "test(domains): connect phase 10.37 acceptance"
```

---

### Task 10: Complete Phase 10.37 focused suite and controlled refactor

**Files:**
- All Phase 10.37 production/test files.

**Interfaces:**
- No new public behavior.
- Refactor only after focused tests are green.

- [ ] **Step 1: Run all focused tests**

```bash
.venv/bin/pytest -q tests/domains/test_domain_observability_*.py
```

- [ ] **Step 2: Scan forbidden architecture**

```bash
if find cmm/domains -maxdepth 1 -type f | grep -E \
  '/observability_(store|repository|event_bus|runtime|engine|registry|loader|trace)\.py$'; then
  echo "ERROR=PARALLEL_OBSERVABILITY_INFRASTRUCTURE"
  exit 1
fi
```

- [ ] **Step 3: Scan prohibited inference shortcuts**

Review calculator branches involving fallback, transfers, reuse, avoided questions and duplicates.

- [ ] **Step 4: Scan privacy anti-patterns**

```bash
if rg -n \
  'dict\(.*payload|dict\(.*metadata|payload=.*payload|metadata=.*metadata|str\(exc\)|repr\(exc\)' \
  cmm/domains/observability_*.py; then
  echo "REVIEW_REQUIRED=OBSERVABILITY_PRIVACY_PATTERN"
  exit 1
fi
```

- [ ] **Step 5: Controlled refactor**

Allowed: private sorting/normalization/builders only.

Forbidden: platform metrics abstractions or new infrastructure.

- [ ] **Step 6: Re-run focused suite**

```bash
.venv/bin/pytest -q tests/domains/test_domain_observability_*.py
```

- [ ] **Step 7: Commit refactor only if code changed**

```bash
git add cmm/domains/observability_*.py tests/domains/test_domain_observability_*.py
git diff --cached --check
git commit -m "refactor(domains): simplify observability projection"
```

Do not create an empty commit.

---

### Task 11: Closed-phase regression suite

**Files:**
- No production changes expected.

**Interfaces:**
- Proves Phase 10.37 preserves inherited invariants.

- [ ] **Step 1: Discover exact existing regression files before running**

```bash
printf '%s\n' "=== TRACE ==="
find tests/domains -maxdepth 1 -type f -name '*trace*.py' | sort

printf '%s\n' "=== SELECTION ==="
find tests/domains -maxdepth 1 -type f -name '*selection*.py' | sort

printf '%s\n' "=== CONFLICT ==="
find tests/domains -maxdepth 1 -type f -name '*conflict*.py' | sort

printf '%s\n' "=== EVENTS ==="
find tests/domains -maxdepth 1 -type f -name '*events*.py' | sort

printf '%s\n' "=== SESSIONS ==="
find tests/domains -maxdepth 1 -type f -name '*session*.py' | sort

printf '%s\n' "=== API ==="
find tests/domains -maxdepth 1 -type f -name '*api*.py' | sort
```

Do not invent missing file names.

- [ ] **Step 2: Run Phase 10.17 Domain Trace regressions**

Run the exact existing focused/acceptance/reference-validation files.

- [ ] **Step 3: Run Phase 10.31 selection policy regressions**

Run exact existing selection/audit files.

- [ ] **Step 4: Run Phase 10.32 conflict regressions**

Run exact existing conflict/audit files, including latest regression coverage proving unresolved cases cannot claim winners.

- [ ] **Step 5: Run Phase 10.33 exact known regression set**

```bash
.venv/bin/pytest -q \
  tests/domains/test_domain_events_audit_v1_regressions.py \
  tests/domains/test_domain_events_audit_v2_regressions.py \
  tests/domains/test_domain_events_audit_v3_regressions.py \
  tests/domains/test_domain_events_dp033_acceptance.py \
  tests/domains/test_domain_public_api.py
```

Include later audit regression files if present.

- [ ] **Step 6: Run Phase 10.34 Domain Sessions regressions**

Run exact discovered Phase 10.34 focused/audit/acceptance files plus canonical shared-session tests.

- [ ] **Step 7: Run Phase 10.36 Domain API regressions**

If present, include:

```text
tests/domains/test_domain_api_contracts.py
tests/domains/test_domain_api_queries.py
tests/domains/test_domain_api_lifecycle.py
tests/domains/test_domain_api_execution.py
tests/domains/test_domain_api_sessions.py
tests/domains/test_domain_api_conflicts_traces.py
tests/domains/test_domain_api_dp036_acceptance.py
```

Also include any Phase 10.36 audit regression files discovered.

- [ ] **Step 8: Verify DomainAPI file has no implementation diff**

```bash
test -z "$(
  git diff \
    33aed9eab68c5598361a842adc1396360b9933e3..HEAD \
    -- cmm/domains/api_contracts.py
)"
echo "DOMAIN_API_PROTOCOL_UNCHANGED=PASS"
```

- [ ] **Step 9: Verify Phase 10.33 event catalog remains 23/23**

Use the actual existing constant. If its name differs from the conceptual name, do not add an alias solely for the gate.

- [ ] **Step 10: Do not commit anything**

Verification only. Any failure returns to the relevant TDD task.

---

### Task 12: Domain observability reference documentation

**Files:**
- Create: `docs/reference/domain-observability.md`

**Interfaces:**
- Documents implemented truth only.
- No closure claim.

- [ ] **Step 1: Write the reference document**

Required sections:

```text
Phase 10.37 status
Ownership and dependency direction
Public contracts
Canonical evidence sources
Metric catalog
OBSERVED vs UNAVAILABLE
Zero vs UNAVAILABLE
Anti-inference rules
Domain health semantics
Health dimensions
Privacy and sanitization
Determinism and digest
Domain Events 23/23 boundary
Domain Trace boundary
Domain Sessions boundary
DomainAPI boundary
Non-goals
DP-037
AT-DP-037 evidence
Known limitations
```

- [ ] **Step 2: Record metric support honestly**

For each of the 25 metrics, document exact canonical evidence or unavailable semantics.

- [ ] **Step 3: Document health semantics**

State positive verification semantics and non-mutation behavior.

- [ ] **Step 4: Document privacy**

State prohibited raw content explicitly.

- [ ] **Step 5: Mark status only after acceptance passes**

Use:

```text
Phase 10.37 — Implemented, pending independent audit
DP-037 = IMPLEMENTED_PENDING_AUDIT
AT-DP-037 = PASS
```

- [ ] **Step 6: Commit**

```bash
git add docs/reference/domain-observability.md
git diff --cached --check
git commit -m "docs(domains): document phase 10.37 observability"
```

---

### Task 13: Roadmap and requirements matrix — implementation pending audit

**Files:**
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `ROADMAP.md`

**Interfaces:**
- Records implementation state but does not close/audit the phase.

- [ ] **Step 1: Update detailed roadmap**

Record implemented projection, exact/unavailable metrics, health, canonical reuse, `DP-037 = IMPLEMENTED_PENDING_AUDIT`, `AT-DP-037 = PASS`, audit pending.

- [ ] **Step 2: Update requirements matrix**

Add/complete 10.37 observability requirements and DP/AT evidence status.

- [ ] **Step 3: Update top-level ROADMAP**

Implemented-through may include 10.37 pending audit; independently-audited-through remains 10.36.

Do not mark 10.38 started.

- [ ] **Step 4: Diff hygiene**

```bash
git diff --check
git diff -- \
  docs/roadmap/phase-10-domain-intelligence.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  ROADMAP.md
```

- [ ] **Step 5: Commit implementation-status docs**

```bash
git add \
  docs/roadmap/phase-10-domain-intelligence.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  ROADMAP.md

git diff --cached --check
git commit -m "docs(domains): mark phase 10.37 audit pending"
```

This is not the final closure commit.

---

### Task 14: Full quality gates and implementation freeze

**Files:**
- All implementation delta since `33aed9eab68c5598361a842adc1396360b9933e3`.

**Interfaces:**
- Produces the exact committed implementation candidate.

- [ ] **Step 1: Pre-gate safety**

```bash
test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"
git stash list | grep -Fq \
  "quarantine: post-audit phase 10.32 uncommitted changes"
```

- [ ] **Step 2: Determine exact Python delta**

```bash
BASE="33aed9eab68c5598361a842adc1396360b9933e3"

git diff --name-only "$BASE..HEAD" -- '*.py' | while IFS= read -r file; do
  [ -f "$file" ] && printf '%s\n' "$file"
done > /tmp/phase10_37_python_files.txt

cat /tmp/phase10_37_python_files.txt
```

- [ ] **Step 3: Ruff**

```bash
xargs .venv/bin/ruff check < /tmp/phase10_37_python_files.txt
```

- [ ] **Step 4: Format**

```bash
xargs .venv/bin/ruff format --check < /tmp/phase10_37_python_files.txt
```

If formatting changes are required, format, rerun affected tests, and commit narrowly.

- [ ] **Step 5: Compile**

```bash
.venv/bin/python -m compileall -q cmm/domains tests/domains
```

- [ ] **Step 6: Focused Phase 10.37**

```bash
.venv/bin/pytest -q tests/domains/test_domain_observability_*.py
```

- [ ] **Step 7: Domain Events regressions**

Run V1–V3 and every later Phase 10.33 audit regression file that exists, plus `test_domain_events_dp033_acceptance.py`.

- [ ] **Step 8: Trace/selection/conflict/session/API regressions**

Run exact existing discovered sets from Task 11.

- [ ] **Step 9: Full Domain suite**

```bash
.venv/bin/pytest -q tests/domains
```

- [ ] **Step 10: Relevant Validation/Agent observability suites only if shared code was touched**

Preferred architecture touches none.

- [ ] **Step 11: Global suite**

```bash
.venv/bin/pytest -q
```

- [ ] **Step 12: Diff check**

```bash
git diff --check
git diff --cached --check
```

- [ ] **Step 13: Forbidden infrastructure gate**

```bash
if git diff --name-only "$BASE..HEAD" | grep -E \
  '^cmm/domains/observability_(store|repository|event_bus|runtime|engine|registry|loader|trace)\.py$'; then
  echo "ERROR=FORBIDDEN_OBSERVABILITY_INFRASTRUCTURE"
  exit 1
fi
```

- [ ] **Step 14: DomainAPI unchanged gate**

```bash
test -z "$(git diff "$BASE..HEAD" -- cmm/domains/api_contracts.py)"
echo "DOMAIN_API_PROTOCOL_UNCHANGED=PASS"
```

- [ ] **Step 15: Event catalog 23/23 gate**

Import the actual existing Phase 10.33 canonical constant and assert 23 unique entries.

- [ ] **Step 16: Secret path gate**

```bash
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "ERROR=TRACKED_DOTENV"
  exit 1
fi

if git ls-files | grep -Eqi \
  '(^|/)\.env($|\.)|(^|/)(credentials|secrets?)(\.|/|$)|(^|/)id_(rsa|dsa|ecdsa|ed25519)($|\.)|\.(pem|p12|pfx|key)$'; then
  echo "ERROR=FORBIDDEN_TRACKED_SECRET_PATH"
  exit 1
fi
```

- [ ] **Step 17: Confirm implementation documentation status**

No premature independently-audited/closed claim for 10.37.

- [ ] **Step 18: Ensure all implementation work is committed**

```bash
test -z "$(git status --porcelain)"
echo "WORKTREE=CLEAN"
```

- [ ] **Step 19: Record final implementation HEAD**

```bash
IMPLEMENTATION_HEAD="$(git rev-parse HEAD)"
echo "IMPLEMENTATION_HEAD=$IMPLEMENTATION_HEAD"
git log -12 --oneline --decorate
```

This exact HEAD is the only valid audit source.

---

### Task 15: Exact-HEAD audit bundle

**Files:**
- No repository mutation.

**Interfaces:**
- Produces immutable audit candidate and SHA-256.

- [ ] **Step 1: Verify clean exact HEAD**

```bash
test -z "$(git status --porcelain)"
git stash list | grep -Fq \
  "quarantine: post-audit phase 10.32 uncommitted changes"

AUDITED_HEAD="$(git rev-parse HEAD)"
```

- [ ] **Step 2: Build with `git archive`**

```bash
OUTDIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Downloads"
BUNDLE="$OUTDIR/phase-10.37-audit-v1.tar.gz"

git archive --format=tar.gz \
  --output="$BUNDLE" \
  "$AUDITED_HEAD"

test -s "$BUNDLE"
```

- [ ] **Step 3: Calculate SHA-256**

```bash
SHA256="$(shasum -a 256 "$BUNDLE" | awk '{print $1}')"

echo "AUDIT_BUNDLE=$BUNDLE"
echo "AUDIT_BUNDLE_SHA256=$SHA256"
```

- [ ] **Step 4: Verify archive content**

Extract to a temp directory and verify spec, plan, all four Phase 10.37 production modules and `AT-DP-037` test exist.

- [ ] **Step 5: Final handoff**

Report:

```text
PHASE10_37_IMPLEMENTATION=COMPLETE_PENDING_AUDIT
DP_037=IMPLEMENTED_PENDING_AUDIT
AT_DP_037=PASS
AUDITED_HEAD=<exact HEAD>
AUDIT_BUNDLE=<path>
AUDIT_BUNDLE_SHA256=<sha256>
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
PUSH=NO
MERGE=NO
NEXT=INDEPENDENT_CHATGPT_AUDIT
```

Do not create a closure commit before independent audit PASS.

---

## Commit Discipline

Preferred sequence:

```text
feat(domains): add observability contracts
feat(domains): calculate observability metrics
test(domains): harden observability metric semantics
feat(domains): deduplicate observability evidence
feat(domains): add read-only health checks
feat(domains): project observability reports
feat(domains): expose observability surface
test(domains): guard observability boundaries
test(domains): connect phase 10.37 acceptance
refactor(domains): simplify observability projection       # only if needed
docs(domains): document phase 10.37 observability
docs(domains): mark phase 10.37 audit pending
```

Additional remediation commits only for actual failing tests/gates.

Do not squash the committed spec/plan history.

Do not push or merge.

---

## Final Verification Command Set

At implementation end, run an equivalent consolidated gate:

```bash
set -euo pipefail

cd "/Users/chris/CMM OS"

BASE="33aed9eab68c5598361a842adc1396360b9933e3"
QUARANTINE_MARKER="quarantine: post-audit phase 10.32 uncommitted changes"

test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"
git stash list | grep -Fq "$QUARANTINE_MARKER"

git diff --name-only "$BASE..HEAD" -- '*.py' | while IFS= read -r file; do
  [ -f "$file" ] && printf '%s\n' "$file"
done > /tmp/phase10_37_python_files.txt

test -s /tmp/phase10_37_python_files.txt

xargs .venv/bin/ruff check < /tmp/phase10_37_python_files.txt
xargs .venv/bin/ruff format --check < /tmp/phase10_37_python_files.txt

.venv/bin/python -m compileall -q cmm/domains tests/domains
.venv/bin/pytest -q tests/domains/test_domain_observability_*.py

.venv/bin/pytest -q \
  tests/domains/test_domain_events_audit_v1_regressions.py \
  tests/domains/test_domain_events_audit_v2_regressions.py \
  tests/domains/test_domain_events_audit_v3_regressions.py \
  tests/domains/test_domain_events_dp033_acceptance.py \
  tests/domains/test_domain_public_api.py

.venv/bin/pytest -q tests/domains
.venv/bin/pytest -q

git diff --check

if git diff --name-only "$BASE..HEAD" | grep -E \
  '^cmm/domains/observability_(store|repository|event_bus|runtime|engine|registry|loader|trace)\.py$'; then
  echo "ERROR=FORBIDDEN_OBSERVABILITY_INFRASTRUCTURE"
  exit 1
fi

test -z "$(git diff "$BASE..HEAD" -- cmm/domains/api_contracts.py)"

test -z "$(git status --porcelain)"
git stash list | grep -Fq "$QUARANTINE_MARKER"

echo "PHASE10_37_FINAL_GATES=PASS"
echo "WORKTREE=CLEAN"
echo "QUARANTINE_STASH=PRESERVED"
```

Run the exact discovered Phase 10.17/10.31/10.32/10.34/10.36 focused regressions in addition to the consolidated command above.

---

## Plan Self-Review

### Spec coverage

Mapped:

- immutable reference-first contracts → Tasks 1 and 6;
- exact metric catalog → Task 2;
- `UNAVAILABLE != 0` → Tasks 1–3;
- anti-proxy inference → Task 3;
- evidence deduplication/source precedence → Task 4;
- health model/dimensions → Task 5;
- read-only health → Task 5;
- privacy/safe logs → Task 6;
- public surface → Task 7;
- no parallel infrastructure → Tasks 7, 8 and 14;
- Domain Events 23/23 → Tasks 8, 9, 11 and 14;
- Domain Trace authority → Tasks 6, 8 and 9;
- Domain Sessions shared persistence → Tasks 8 and 9;
- DomainAPI unchanged → Tasks 7, 11 and 14;
- DP-037 → Task 9;
- AT-DP-037 → Task 9;
- focused/regression/global gates → Tasks 10, 11 and 14;
- implementation-pending-audit documentation → Tasks 12–13;
- exact-HEAD committed audit bundle → Task 15.

### Placeholder scan

The plan contains no deferred placeholder markers.

Where exact canonical type names depend on committed repository definitions, the plan requires direct inspection and replacement with those exact types before production code is written. It does not authorize leaving guessed types or invented registries in final code.

### Type consistency

The plan consistently uses:

```text
DomainObservabilityEvidence
→ DomainMetricsCalculator.calculate(...)
→ DomainMetricsSnapshot

DomainHealthChecker.check(...)
→ DomainHealthResult

DomainObservabilityService.build_report(...)
→ DomainObservabilityReport
```

All report/metric/health contracts originate in `observability_contracts.py`.

### Scope

The plan implements one coherent subsystem: the read-only Domain Observability projection. It does not implement Phase 11 platform observability, API/UI exposure, persistence, new lifecycle infrastructure, Security 10.38 or Domain Pack quality benchmarking.

---

## Handoff After Plan Commit

After this plan is copied to:

```text
docs/superpowers/plans/2026-08-31-domain-observability-implementation-plan.md
```

and committed on a clean worktree, the next project step is not implementation directly.

The next step in the CMM OS workflow is to generate the dedicated **Phase 10.37 implementation-agent prompt**, bound to:

- branch `feature/phase-10-domain-intelligence`;
- the exact plan commit HEAD;
- this plan;
- the approved Phase 10.37 spec;
- all inherited invariants;
- the TDD sequence;
- exact forbidden actions;
- exact audit handoff requirements.

Only after that prompt is approved should the implementation agent execute Phase 10.37.
