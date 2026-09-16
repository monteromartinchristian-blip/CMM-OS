# Phase 11.3 — Application Backend — Independent Audit V1

**Audit verdict:** `FAIL`
**Audit date:** 2026-09-16
**Auditor:** ChatGPT independent audit
**Scope:** Phase 11.3 — Application Backend
**Requirement:** `F11-017 — Canonical Application Backend`
**Design Point:** `DP-103 — Versioned, Fail-Closed Application Gateway`
**Connected acceptance:** `AT-DP-103`

---

## 1. Final verdict

Independent Audit V1 fails because the public idempotency boundary is not atomic
under concurrent equivalent commands.

A second, documentation-only traceability defect is also recorded.

```text
INDEPENDENT_AUDIT_V1=FAIL

BLOCKERS=0
MAJORS=1
MINORS=1

MAJOR_01=NON_ATOMIC_IDEMPOTENCY_UNDER_CONCURRENT_REQUESTS
MINOR_01=STALE_UNQUALIFIED_IMPLEMENTATION_HEAD_IN_ROOT_ROADMAP

F11_017=IMPLEMENTED_REMEDIATION_REQUIRED
DP_103=NOT_VERIFIED
AT_DP_103=PASS

AT_DP_102=PASS
AT_DP_101=PASS
AT_DP_134=PASS

CLOSURE_ELIGIBLE=NO
```

The Phase 11.3 implementation is substantial and otherwise well aligned with
the approved architecture, but `DP-103` explicitly includes safe idempotency as
a closure property. The concurrency defect allows duplicate canonical request
processing before the second request is rejected, so the Design Point cannot be
verified yet.

---

## 2. Audited artifact identity

Uploaded bundle:

```text
cmm-phase11-3-application-backend-audit-5fd8cc3b171f.tar.gz
```

Independent verification:

```text
AUDITED_HEAD=5fd8cc3b171faec88b802be920ad09ac53224e75
AUDITED_TREE=1cfbe114369ac89d1c2563a9787c5ebf096c64df
AUDIT_BUNDLE_SHA256=17377075eae659d123ca4ee909fa8f0cef01f625f40c2d498b34f22a47690199

GZIP=PASS
EMBEDDED_COMMIT_ID=5fd8cc3b171faec88b802be920ad09ac53224e75
RECONSTRUCTED_TREE=1cfbe114369ac89d1c2563a9787c5ebf096c64df
TREE_MATCH=PASS
ARCHIVE_MEMBERS=2511
UNSAFE_ARCHIVE_PATHS=0
SYMLINKS=0
```

The tree was reconstructed independently from the archive using forced Git
indexing so tracked files that also match ignore rules were not omitted.

The reconstructed tree exactly matches the tree declared by the implementation
handoff.

---

## 3. Governing design and plan

The audited tree contains the committed Phase 11.3 design and implementation
plan:

```text
docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md
docs/superpowers/plans/2026-09-16-phase-11.3-application-backend-implementation-plan.md
```

Canonical identity is consistent:

```text
11.3 = Application Backend
F11-017 = Canonical Application Backend
DP-103 = Versioned, Fail-Closed Application Gateway
AT-DP-103 = Connected Application Backend Acceptance
```

The implemented architecture follows the approved Option A:

```text
cmm/api
    ↓
cmm/application
    ↓
ApplicationContainer / Orchestrator / canonical owners
```

No second HTTP-owned domain, agent, session, provider, workflow, execution,
plugin, auth or model-routing authority was found.

---

## 4. Production surface reviewed

### Application core

```text
cmm/application/__init__.py
cmm/application/capabilities.py
cmm/application/contracts.py
cmm/application/errors.py
cmm/application/gateway.py
cmm/application/health.py
cmm/application/idempotency.py
cmm/application/platform_module.py
cmm/application/requests.py
cmm/application/sessions.py
```

### HTTP adapter

```text
cmm/api/__init__.py
cmm/api/app.py
cmm/api/errors.py
cmm/api/models.py
cmm/api/streaming.py
```

### Focused tests

```text
tests/application/
tests/api/
```

The public route surface is the intended versioned v1 surface:

```text
GET  /v1/health
GET  /v1/capabilities
POST /v1/sessions
GET  /v1/sessions/{session_id}
POST /v1/sessions/{session_id}/messages
POST /v1/sessions/{session_id}/messages/stream
POST /v1/requests/{request_id}/cancel
```

No `/v2` or unversioned application API alias is introduced.

---

## 5. Closed-phase preservation

The current bundle was compared against the previously independently audited
Phase 11.2 exact bundle.

For production source files under:

```text
cmm/platform/
cmm/orchestration/
kernel/llm/
cmm/domains/
cmm/agent_runtime/
```

the comparison found:

```text
SOURCE_DIFFS=0
```

Therefore the production semantics of the closed Phase 11.1, 11.2 and 11.34
owners are preserved.

The one inherited test change is:

```text
tests/platform/test_architecture.py
```

The prior allowlist:

```python
{"orchestration"}
```

was changed to the exact bounded allowlist:

```python
("orchestration", "application")
```

The test still computes all consumers of `cmm.platform` and asserts that the
consumer set is a subset of that explicit tuple.

This is consistent with the approved Phase 11.3 dependency direction:

```text
cmm.application -> cmm.platform
```

and does not create a wildcard or generic exemption.

Assessment:

```text
PLATFORM_ARCHITECTURE_GATE_DEVIATION=ACCEPTED
CLOSED_PHASE_PRODUCTION_SEMANTICS_CHANGED=NO
```

---

## 6. Architecture review

Independent scans found no Phase 11.3 classes or imports matching prohibited
parallel owners such as:

```text
DomainRegistry
AgentRegistry
ProviderRegistry
WorkflowRegistry
OperationRegistry
EventBus
EventStore
ModelGateway
RoutingPolicyEngine
AuthService
RBACEngine
PluginRegistry
PluginLoader
MetricsStore
BackupService
WorkerPool
TaskBroker
Scheduler
```

No direct provider/model-routing import exists in:

```text
cmm/application
cmm/api
```

No direct HTTP import of lower canonical owner packages exists for:

```text
cmm.domains
cmm.agent_runtime
cmm.runtime.sessions
cmm.validation
cmm.workflows
cmm.execution
kernel.*
```

No reverse imports from:

```text
cmm/platform
cmm/orchestration
cmm/domains
cmm/agent_runtime
kernel
```

to:

```text
cmm.application
cmm.api
```

were found.

No Phase 11.3-owned:

```text
SQL/SQLite storage
Event Bus
auth/RBAC
plugin runtime
worker/scheduler/task broker
Model Gateway
Routing Policy Engine
```

was found.

Assessment:

```text
HTTP_IS_ADAPTER_NOT_OWNER=VERIFIED
APPLICATION_CONTAINER_REUSED=VERIFIED
ORCHESTRATOR_REUSED=VERIFIED
DOMAIN_AUTHORITY_PRESERVED=VERIFIED
AGENT_AUTHORITY_PRESERVED=VERIFIED
SESSION_AUTHORITY_PRESERVED=VERIFIED
PROVIDER_AUTHORITY_PRESERVED=VERIFIED
NO_MODEL_ROUTING_OWNER=VERIFIED
NO_NEW_EVENT_BUS=VERIFIED
NO_NEW_AUTH_RBAC=VERIFIED
NO_DURABLE_APP_DB=VERIFIED
NO_PLUGIN_RUNTIME=VERIFIED
NO_BACKGROUND_WORKER_SYSTEM=VERIFIED
```

---

## 7. Application contracts and public-safety review

The implementation provides frozen, version-aware application contracts for:

```text
ApplicationRequest
ApplicationQuery
ApplicationCommand
ApplicationResponse
ApplicationError
ApplicationSession
ApplicationMessage
ApplicationCapability
ApplicationHealth
ApplicationStreamEvent
ApplicationCancellationRequest
```

The public contract grammar:

- bounds metadata depth and item count;
- bounds identifiers and message strings;
- rejects binary values;
- rejects non-finite floats;
- freezes mappings and sequences;
- rejects secret-shaped metadata keys;
- serializes through deterministic JSON-native `to_dict()` projections.

Unexpected exceptions are reduced to a generic:

```text
INTERNAL_FAILURE
Application request failed closed
```

without exception repr or traceback.

Focused adversarial tests confirm safe transport/application error projection.

Assessment:

```text
PUBLIC_ERRORS_SAFE=VERIFIED
PUBLIC_METADATA_BOUNDED=VERIFIED
```

subject to the idempotency MAJOR below.

---

## 8. Session and concurrency review

`SessionApplicationService` accepts only canonical:

```text
InMemorySessionStore
FileSessionStore
```

and rejects arbitrary structural `load/save` objects.

It does not introduce a second session store.

It delegates all session state to the canonical runtime owner.

Stale expected revisions produce:

```text
CONCURRENCY_CONFLICT
```

before orchestration.

Connected acceptance verifies a stale revision never enters the canonical
Orchestrator.

Assessment:

```text
SESSION_CONCURRENCY_FAIL_CLOSED=VERIFIED
```

for the approved optimistic session-revision boundary.

---

## 9. Central request path review

The public message path is:

```text
ApplicationGateway
    ↓
RequestApplicationService
    ↓
OrchestrationRequest(channel=API)
    ↓
real Phase 11.2 Orchestrator
    ↓
OrchestrationResult
    ↓
safe ApplicationResponse projection
```

`RequestApplicationService`:

- requires the real concrete `Orchestrator`;
- requires an existing canonical session before orchestration;
- preserves expected revision checks;
- sets no `bot_id`;
- sets no `intent_hint`;
- requests no fabricated capabilities;
- exposes no raw canonical context;
- exposes no raw policy trace;
- performs no downstream operation/workflow/agent/model execution.

The connected acceptance demonstrates that a normal public text message honestly
reaches:

```text
NEEDS_CLARIFICATION
```

because no `intent_hint` is fabricated.

That behavior is consistent with the approved Phase 11.2 execution boundary.

Assessment:

```text
ORCHESTRATOR_REUSED=VERIFIED
NO_DOWNSTREAM_EXECUTION_FABRICATED=VERIFIED
```

---

## 10. Connected acceptance — AT-DP-103

The acceptance file builds a real connected graph using:

```text
FastAPI create_app + TestClient
ApplicationGateway
SessionApplicationService
RequestApplicationService
CapabilityApplicationService
HealthApplicationService
InMemoryIdempotencyRepository
real ApplicationContainer
real Orchestrator
real DeterministicIntentResolver
real DefaultContextResolver
real CanonicalDomainRouter
real CanonicalAgentRouter
real DefaultOrchestrationPolicy
real InMemoryOrchestrationDecisionRepository
real RecordingOrchestrationEventSink
canonical Domain Registry / permissions / profiles
canonical AgentRegistryService
official InMemorySessionStore
```

It is not mock-only.

Scenarios A–M cover:

- composition;
- health;
- session create/read;
- message reaching the real orchestrator;
- canonical domain/agent authority;
- malformed input fail-closed;
- unsupported version;
- safe internal failure mapping;
- idempotent replay;
- idempotency conflict;
- stale revision conflict;
- unavailable cancellation;
- HTTP/application layering.

Independent replay:

```text
AT-DP-103 + AT-DP-102 + AT-DP-101 + AT-DP-134
175 passed
```

Therefore:

```text
AT_DP_103=PASS
AT_DP_102=PASS
AT_DP_101=PASS
AT_DP_134=PASS
```

The acceptance itself passes, but it does not contain a concurrent same-key
idempotency scenario, which is exactly where `MAJOR-01` exists.

---

## 11. Independent test replay

The audit sandbox lacks the repository's normal `libcst` dependency.

As in the previous Phase 11.2 audit, an out-of-tree, import-only `libcst` shim
was used solely to let the inherited execution import chain load. The shim was
not written into the audited tree and no CST behavior is exercised by the
Phase 11.3 focused tests.

### Application + API suites

```text
tests/application + tests/api
818 passed
```

This independently matches:

```text
625 application
193 api
```

from the implementation handoff.

### Connected + inherited acceptance

```text
175 passed
```

### Architecture/OpenAPI + inherited architecture gates

```text
272 passed
```

### Session regression

```text
15 passed
```

### Domain/agent regression

```text
607 passed
```

### Platform/orchestration regression

```text
856 passed
```

### Compile

```text
COMPILEALL=PASS
```

---

## 12. Global-suite audit-environment limitation

An independent global run in the audit sandbox stopped during collection on two
existing domain tests because the sandbox is Python 3.13 and triggers the known
dataclass/super issue in:

```text
tests/domains/test_relationships_domain_remediation.py
tests/domains/test_university_domain_remediation.py
```

The same two collection failures were reproduced against the older independently
audited Phase 11.2 bundle in the same sandbox.

Therefore they are not Phase 11.3 findings.

The implementation agent reports a repository-native final run:

```text
GLOBAL_TESTS=19935 passed
```

which is consistent with the focused and regression evidence independently
replayed here.

`ruff` is not installed in the independent audit sandbox, so the reported
repository-native Ruff/format results could not be replayed independently.
Changed-scope Python tests, architecture gates and `compileall` all pass.

---

# 13. MAJOR-01 — Non-atomic idempotency under concurrent requests

**Severity:** `MAJOR`

**Identifier:**

```text
MAJOR_01=NON_ATOMIC_IDEMPOTENCY_UNDER_CONCURRENT_REQUESTS
```

## 13.1 Required invariant

The approved design makes safe idempotency a closure property of `DP-103`.

The implementation handoff claims:

```text
IDEMPOTENCY_FAIL_CLOSED=YES
```

The application gateway promises:

```text
same key + same semantic command
    -> replay one safe response
```

and:

```text
same key + different command
    -> IDEMPOTENCY_CONFLICT
```

without duplicate canonical processing.

## 13.2 Root cause

`ApplicationGateway._dispatch_idempotent()` currently performs:

```text
fingerprint
↓
repository.get(key)
↓
if absent:
    execute canonical command
↓
repository.put(record)
```

as separate operations.

`InMemoryIdempotencyRepository` is explicitly documented as:

```text
not thread-safe
```

and no application-gateway lock/reservation spans the complete
`get -> execute -> put` critical section.

FastAPI's synchronous handlers can execute concurrently.

Therefore two equivalent keyed requests can both observe `get(key) is None`
before either has stored the result.

Both can then enter the canonical Orchestrator.

Only after canonical processing does one discover that the other inserted the
record.

## 13.3 Independent reproducer

The audit forced exactly that legal interleaving by synchronizing two concurrent
gateway calls immediately after the repository lookup.

Both commands used:

```text
same Idempotency-Key
same session
same actor
same message identity
same content
same semantic payload
different request_id
```

Observed result:

```text
responses:
  req-2 -> NEEDS_CLARIFICATION
  req-1 -> FAILED / IDEMPOTENCY_CONFLICT

canonical orchestration.request_received:
  req-2
  req-1

canonical decision records:
  orchestration-decision:req-2
  orchestration-decision:req-1
```

That means the second request was rejected only **after** it had already created
canonical orchestration history.

The idempotency contract therefore does not prevent duplicate canonical
processing under concurrency.

## 13.4 Why this is MAJOR

This is not merely an internal repository detail.

The defect crosses the public `/v1` command boundary and invalidates a declared
`DP-103` property:

```text
safe idempotency semantics
```

A future command with real canonical side effects could execute twice under the
same idempotency key.

The architecture deliberately exposes FastAPI as a reusable backend surface, so
concurrent invocation is a normal transport condition, not an exotic invalid
caller state.

## 13.5 Required remediation

Remediation must preserve the approved architecture and remain narrow.

A valid minimal direction is:

```text
ApplicationGateway owns one private lock around the full keyed
get -> execute -> put critical section
```

or another equally narrow atomic claim/replay mechanism.

Do not introduce:

```text
ConcurrencyManager
LockRegistry
distributed lock service
transaction engine
durable idempotency database
background coordinator
```

The v1 in-memory repository may remain non-durable.

The important requirement is that one keyed semantic command may enter the
canonical owner at most once while an equivalent keyed command is in flight.

## 13.6 Required permanent tests

At minimum add:

### Concurrent equivalent command

Two simultaneous commands with:

```text
same idempotency key
same semantic fingerprint
different request IDs
```

must produce:

```text
one canonical Orchestrator invocation
one canonical decision
two safe public results representing the one operation
```

No second canonical side effect.

### Concurrent different command

Two simultaneous commands with:

```text
same idempotency key
different semantic fingerprint
```

must produce:

```text
at most one canonical command execution
one IDEMPOTENCY_CONFLICT
```

The conflicting command must be rejected before entering its canonical owner.

### Repository/gateway regression

All existing sequential replay/conflict tests must remain green.

---

# 14. MINOR-01 — Stale unqualified implementation HEAD in root ROADMAP

**Severity:** `MINOR`

**Identifier:**

```text
MINOR_01=STALE_UNQUALIFIED_IMPLEMENTATION_HEAD_IN_ROOT_ROADMAP
```

## 14.1 Evidence

The exact audited candidate is:

```text
AUDITED_HEAD=5fd8cc3b171faec88b802be920ad09ac53224e75
```

The Phase 11.3 reference correctly qualifies:

```text
Implementation HEAD at this documentation task:
2201d0009b47db7128bab895f4ad25f069712781
```

and the detailed roadmap similarly describes `2201d000...` as pre-audit evidence
observed while preparing documentation.

However root `ROADMAP.md` currently says, without that qualifier:

```text
implementation HEAD 2201d0009b47db7128bab895f4ad25f069712781
```

while the actual audit candidate includes later committed documentation and
format-only remediation and is:

```text
5fd8cc3b171faec88b802be920ad09ac53224e75
```

## 14.2 Impact

No runtime behavior is affected.

The defect is traceability/nomenclature only, but root roadmap readers can
mistake an intermediate implementation milestone for the exact audit candidate
HEAD.

## 14.3 Required remediation

Do not attempt to make a document contain its own future commit hash.

Instead qualify the historical value explicitly, for example:

```text
AT-DP-103 implementation milestone HEAD 2201d000...
```

or remove the unqualified implementation-HEAD field from the pre-audit root
summary.

The exact audit/re-audit HEAD must be recorded only once that bundle exists.

Historical evidence must remain append-only.

---

## 15. OpenAPI and transport review

The OpenAPI gate verifies the intended v1 paths and rejects accidental
unversioned aliases.

The HTTP adapter:

- depends on `cmm.application`;
- does not import canonical lower owners directly;
- maps framework request-validation and routing failures to the public
  application error envelope;
- uses deterministic response models;
- echoes/generates request correlation identity;
- maps application errors to explicit HTTP status codes;
- provides SSE as a delivery projection over one application result;
- does not add WebSockets or provider token streaming.

Assessment:

```text
OPENAPI_VERSIONED=VERIFIED
HTTP_ERROR_BOUNDARY=VERIFIED
SSE_IS_DELIVERY_ADAPTER=VERIFIED
```

No finding is recorded for the documented `uuid5` generated-message identity:
it is a deterministic idempotent-retry adaptation and does not create a new
authority.

---

## 16. Scope/deviation review

### `tests/platform/test_architecture.py`

Accepted as a necessary test-only extension of the exact sanctioned consumer
allowlist.

No closed-phase production file was modified.

### Ruff format remediation

The final candidate includes a format-only remediation reported by the agent.

The independent audit evaluates the final tree itself; all independently replayed
behavioral and architecture tests pass.

No finding is recorded for the format remediation.

### `message_id` via UUID5 when keyed

The behavior is documented and is necessary to keep a retry without an explicit
message ID semantically stable for the command fingerprint.

No finding is recorded.

### Health `"ok"` status and orchestration error-category mapping

Both remain within the approved safe public contract boundary and are covered by
tests.

No finding is recorded.

### Plan starting-HEAD documentation inconsistency

The implementation actually started from the correct committed plan HEAD:

```text
325bc408b4bdfe98396aba58f6c702ea3cabb383
```

The final handoff records that value.

The inconsistent later illustrative text in the plan does not alter the actual
execution baseline, so no separate finding is recorded.

---

## 17. F11-017 assessment

The canonical application backend is implemented:

```text
ApplicationGateway
cmm/application
cmm/api
/v1 API
OpenAPI
SSE
session adapter
orchestration adapter
safe errors
idempotency boundary
architecture gates
connected acceptance
```

However the public idempotency guarantee is not safe under concurrent requests.

Therefore:

```text
F11_017=IMPLEMENTED_REMEDIATION_REQUIRED
```

not yet:

```text
F11_017=VERIFIED_EXISTING
```

---

## 18. DP-103 assessment

`DP-103` requires a versioned, fail-closed application gateway with safe
idempotency semantics.

Most DP properties are independently verified, but `MAJOR-01` defeats the
idempotency closure property.

Therefore:

```text
DP_103=NOT_VERIFIED
```

---

## 19. Severity summary

```text
BLOCKERS=0
MAJORS=1
MINORS=1

MAJOR_01=NON_ATOMIC_IDEMPOTENCY_UNDER_CONCURRENT_REQUESTS
MINOR_01=STALE_UNQUALIFIED_IMPLEMENTATION_HEAD_IN_ROOT_ROADMAP
```

---

## 20. Final independent verdict

```text
INDEPENDENT_AUDIT_V1=FAIL

BLOCKERS=0
MAJORS=1
MINORS=1

MAJOR_01=NON_ATOMIC_IDEMPOTENCY_UNDER_CONCURRENT_REQUESTS
MINOR_01=STALE_UNQUALIFIED_IMPLEMENTATION_HEAD_IN_ROOT_ROADMAP

F11_017=IMPLEMENTED_REMEDIATION_REQUIRED
DP_103=NOT_VERIFIED
AT_DP_103=PASS

PHASE11_2=CLOSED
DP_102=VERIFIED_EXISTING
AT_DP_102=PASS

PHASE11_1=CLOSED
DP_101=VERIFIED_EXISTING
AT_DP_101=PASS

PHASE11_34=CLOSED
DP_134=VERIFIED_EXISTING
AT_DP_134=PASS

AUDITED_HEAD=5fd8cc3b171faec88b802be920ad09ac53224e75
AUDITED_TREE=1cfbe114369ac89d1c2563a9787c5ebf096c64df
AUDIT_BUNDLE_SHA256=17377075eae659d123ca4ee909fa8f0cef01f625f40c2d498b34f22a47690199

CLOSURE_ELIGIBLE=NO
NEXT=PHASE11_3_REMEDIATION_V1_DESIGN
```

Phase 11.3 must not be closed and Phase 11.4 must not begin.

The next workflow step is a narrow Remediation V1 design covering only:

1. atomic in-flight idempotency at the existing application boundary;
2. permanent concurrent idempotency regression tests;
3. the root-roadmap traceability wording correction.

No architecture expansion is authorized.
