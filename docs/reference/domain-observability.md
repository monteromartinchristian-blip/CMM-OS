# Domain Observability Reference

**Status:** Phase 10.37 — Implemented, pending independent audit
`DP-037 = IMPLEMENTED_PENDING_AUDIT`
`AT-DP-037 = PASS`

## 1. Overview

**Phase 10.37 — Domain Observability** adds one read-only observability
projection over existing canonical Domain evidence: metrics, log entries and
per-domain health derived from already-authoritative components. It creates no
parallel runtime, registry, loader, resolver, event bus, trace, session store,
observability store, or source of truth.

### Core Architectural Invariants

```text
Canonical Domain Intelligence evidence
        ↓
read-only privacy-minimized projection
        ↓
exact metrics OR explicit UNAVAILABLE
        +
per-domain read-only health
        ↓
ephemeral deterministic report
```

1. **Observability is downstream** (`DP037-I01`): Domain Events remain the
   lifecycle event authority; Domain Trace remains the reference-only
   execution trace authority; Domain Sessions remain on shared session
   persistence; the Domain Registry remains the current state authority.
2. **Metrics never influence behavior** (`DP037-I06`): operational Domain
   components never consult Phase 10.37 metrics to decide anything.
3. **Missing evidence is `UNAVAILABLE`, never guessed** (`DP037-I08`,
   `DP037-I09`): `unavailable != 0`, and unavailable is never encoded as
   `0`/`0.0` or an empty bucket pretending to be observed.
4. **Privacy minimization** (`DP037-I10`): projection is reference-first;
   raw payloads, metadata, user text and secret-shaped content are never
   copied into output.
5. **No parallel observability persistence** (`DP037-I11`): no observability
   store, repository, bus, runtime, engine, registry, loader or trace exists.
6. **Phase 10.33 catalog stays 23/23** (`DP037-I12`) and **the Phase 10.36
   DomainAPI contract is unchanged** (`DP037-I13`).

## 2. Production surface

| File | Responsibility |
|---|---|
| `cmm/domains/observability_contracts.py` | Immutable read-model contracts |
| `cmm/domains/observability_metrics.py` | Canonical metric catalog + pure calculator + evidence aggregate |
| `cmm/domains/observability_health.py` | Read-only per-domain health checker |
| `cmm/domains/observability_service.py` | Privacy-minimized log/report projection coordinator |

Public symbols (exported from `cmm.domains`):

- `DomainMetricStatus`, `DomainMetricBucket`, `DomainMetricMeasurement`,
  `DomainMetricsSnapshot`
- `DomainObservabilityLogEntry`
- `DomainHealthStatus`, `DomainHealthFinding`, `DomainHealthResult`
- `DomainObservabilityReport`
- `DomainObservabilityEvidence`, `DomainMetricsCalculator`,
  `DomainHealthChecker`, `DomainObservabilityService`
- `CANONICAL_DOMAIN_OBSERVABILITY_METRICS`
- `InvalidDomainObservabilityContractError`,
  `InvalidDomainObservabilityEvidenceError`

## 3. Metric semantics

Every metric is either `OBSERVED` (exact canonical value) or `UNAVAILABLE`
(insufficient canonical evidence). There is no `estimated`, `guessed`,
inferred-from-text, heuristic or probabilistic status.

**Observed zero** means: the authoritative evidence category exists and zero
matching occurrences occurred.

**Unavailable** means: there is not enough canonical evidence to calculate the
metric honestly. Unavailable metrics use stable reason codes such as
`NO_PERMISSION_EVIDENCE`, `NO_KNOWLEDGE_REUSE_EVIDENCE`,
`NO_TRANSFER_EVIDENCE`, `NO_AVOIDED_QUESTION_EVIDENCE`,
`NO_DUPLICATE_PREVENTION_EVIDENCE`, `NO_LOAD_DURATION_EVIDENCE`,
`NO_WORKFLOW_DURATION_EVIDENCE`.

### 3.1 Metric catalog (25)

| Metric | Type | Authoritative evidence | Unavailable reason |
|---|---|---|---|
| `domains.installed` | scalar count | registry records/definitions | `NO_REGISTRY_EVIDENCE` |
| `domains.active` | scalar count | registry ACTIVE/DEGRADED status | `NO_REGISTRY_EVIDENCE` |
| `loading.duration.mean_ms` | scalar mean | explicit load `duration_ms` only | `NO_LOAD_DURATION_EVIDENCE` |
| `loading.failures` | scalar count | explicit FAILED/REJECTED loads | `NO_LOAD_EVIDENCE` |
| `resolution.decisions_by_domain` | buckets | resolved results by primary domain | `NO_RESOLUTION_EVIDENCE` |
| `resolution.confidence.mean` | scalar mean | explicit resolution confidence only | `NO_RESOLUTION_EVIDENCE` |
| `resolution.ambiguous` | scalar count | explicit AMBIGUOUS status | `NO_RESOLUTION_EVIDENCE` |
| `resolution.fallback` | scalar count | explicit `fallback_used=True` only | `NO_FALLBACK_EVIDENCE` |
| `execution.multi_domain` | scalar count | composition/trace with >1 participant | `NO_EXECUTION_EVIDENCE` |
| `execution.domains.mean` | scalar mean | canonical participant counts | `NO_EXECUTION_EVIDENCE` |
| `conflicts.detected` | scalar count | canonical conflict cases | `NO_CONFLICT_EVIDENCE` |
| `permissions.rejected` | scalar count | canonical denied permission decisions | `NO_PERMISSION_EVIDENCE` |
| `approvals.requested` | scalar count | canonical approval request evidence | `NO_APPROVAL_EVIDENCE` |
| `operations.by_domain` | buckets | canonical operation results | `NO_OPERATION_EVIDENCE` |
| `workflows.by_domain` | buckets | canonical workflow results | `NO_WORKFLOW_EVIDENCE` |
| `workflows.duration.mean_ms` | scalar mean | explicit workflow timing only | `NO_WORKFLOW_DURATION_EVIDENCE` |
| `rules.applied_by_domain` | buckets | rule execution results / trace rule refs | `NO_RULE_EVIDENCE` |
| `resources.loaded_by_domain` | buckets | canonical resource-resolution/load refs | `NO_RESOURCE_EVIDENCE` |
| `cross_domain.transfers` | scalar count | explicit transfer evidence only | `NO_TRANSFER_EVIDENCE` |
| `knowledge.reused` | scalar count | explicit reuse evidence only | `NO_KNOWLEDGE_REUSE_EVIDENCE` |
| `questions.avoided_shared_context` | scalar count | explicit avoided-question evidence only | `NO_AVOIDED_QUESTION_EVIDENCE` |
| `duplicates.prevented` | scalar count | explicit deduplication evidence only | `NO_DUPLICATE_PREVENTION_EVIDENCE` |
| `errors.by_domain_pack` | buckets | explicit domain-attributed load errors | `NO_ERROR_EVIDENCE` |
| `sessions.degraded` | scalar count | canonical degraded session evidence | `NO_SESSION_EVIDENCE` |
| `external_domains.active` | scalar count | canonical active external-domain state | `NO_EXTERNAL_DOMAIN_EVIDENCE` |

### 3.2 Metrics that MUST NOT be inferred by proxy

```text
primary_domain == domain:general        → DOES NOT imply fallback
supporting_domains exist                → DOES NOT imply cross-domain transfer
same knowledge reference appears twice  → DOES NOT imply knowledge reuse
no repeated question appears            → DOES NOT imply a question was avoided
no duplicate object appears             → DOES NOT imply a duplicate was prevented
```

If explicit canonical evidence does not exist, the metric is `UNAVAILABLE`.
Earlier closed contracts are not modified to force these metrics to become
observed.

## 4. Health semantics

`DomainHealthChecker` is read-only. It never installs, loads, reloads,
unloads, enables, disables, repairs, registers, grants permissions, executes
operations or workflows, creates sessions or persists health state.

States: `healthy`, `degraded`, `unhealthy`, `unknown`.

A boolean `True` means positively verified by canonical evidence — never "the
check merely did not raise an exception". A `False` dimension is explained by
a structured `DomainHealthFinding`.

Dimensions: `manifest`, `registry`, `resources`, `rules`, `operations`,
`workflows`, `permissions`, `dependencies`.

- `operations=True` means declared operation contracts are registered
  consistently; it does not mean every operation is executable. A
  deliberately `UNAVAILABLE` operation may remain structurally healthy.
- `permissions=True` means the current permission contract/policy is
  resolvable and structurally valid; it does not mean any user is authorized.
- `dependencies=True` only when required dependencies are present and
  compatible. Optional dependency absence produces a non-blocking finding and
  is never promoted to a required-dependency claim.
- A missing registry record is blocking; the domain cannot be evaluated
  without inventing state.

## 5. Privacy and sanitization

Observability output must not contain raw user input, conversation content,
medical/relationship/legal/financial resource bodies, KnowledgeItem bodies,
memory bodies, private prompts, hidden reasoning, chain-of-thought,
credentials, API keys, tokens, cookies, authorization headers, secrets or
unsafe exception payloads.

Prefer stable IDs, Domain IDs, event types, statuses, public reason codes,
counts, durations, explicit confidence values, public sensitivity labels,
permission IDs, trace IDs, authorized session IDs, and operation/workflow IDs.

The implementation never copies arbitrary event payload or metadata
wholesale: `Phase 10.37` extracts only explicitly safe public fields, and
metric names/bucket labels can never become a covert PII channel or carry
user-generated text.

## 6. Determinism

Identical canonical evidence plus an identical injected generation clock
produce identical serialization and digest. Contracts are frozen/slotted,
timezone-aware, JSON-safe, canonically ordered, caller-alias protected
(via deep-freeze) and digest-covered by stable SHA-256. Pure calculators use
no random IDs.

## 7. Boundaries preserved

- Phase 10.33 Domain Events remain exactly 23/23.
- Phase 10.36 DomainAPI (`cmm/domains/api.py`) is unchanged; no observability
  methods were added to `DomainAPI`.
- No `DomainObservabilityStore`, `DomainObservabilityRepository`,
  `DomainObservabilityEventBus`, `DomainObservabilityRuntime`,
  `DomainObservabilityEngine`, `DomainObservabilityRegistry`,
  `DomainObservabilityLoader` or `DomainObservabilityTrace` was created.
- No `DomainSessionRepository` or session enumeration API was created.
- Operational Domain components (resolver, composer, conflict resolution,
  execution) never import or depend on `observability_*`.

## 8. Known limitations (documented honestly)

The following metrics are `UNAVAILABLE` by design because Phase 10.37 must not
infer them from proxy evidence, and no explicit canonical evidence category
currently exists in earlier closed phases for these semantics:

- `knowledge.reused` — explicit reuse evidence does not exist as a canonical
  result category; repeated knowledge references are not reuse proof.
- `questions.avoided_shared_context` — absence of a repeated question is not
  proof a question was avoided.
- `duplicates.prevented` — absence of duplicate objects is not proof a
  duplicate was prevented.
- `cross_domain.transfers` — becomes `OBSERVED` only when canonical
  `CrossDomainContextTransfer` evidence is supplied; supporting-domain
  participation alone is not a transfer.
- `resolution.fallback` — becomes `OBSERVED` only when a resolution result
  explicitly sets `fallback_used=True`; `domain:general` as primary is not
  fallback proof.

These metrics remain `UNAVAILABLE` unless/until a future phase adds explicit
canonical evidence categories through the appropriate architectural process.