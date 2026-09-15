# Phase 11 — Integration Core reference

**Status:** `IMPLEMENTED_REMEDIATION_V1_PENDING_REAUDIT`
**Phase:** 11.1 — Integration Core
**Requirement:** `F11-015 — Canonical Integration Core`
**Design Point:** `DP-101 — Canonical Application Composition Root`
**Acceptance Test:** `AT-DP-101` — `tests/platform/test_phase11_1_dp101_acceptance.py`
**Design specification:** `docs/superpowers/specs/2026-09-15-phase-11.1-integration-core-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-09-15-phase-11.1-integration-core-implementation-plan.md`
**Independent Audit V1:** `docs/audits/phase-11.1-integration-core-independent-audit-v1.md` (`INDEPENDENT_AUDIT_V1=FAIL`; `BLOCKERS=0`; `MAJORS=3`; `MINORS=0`)
**Remediation V1 design:** `docs/superpowers/specs/2026-09-15-phase-11.1-remediation-v1-design.md`
**Remediation V1 plan:** `docs/superpowers/plans/2026-09-15-phase-11.1-remediation-v1-implementation-plan.md`

This document records the Phase 11.1 integration-core boundary: the canonical
contract classification, the platform package responsibility split, the service
identities bound by the composition root, and the explicit exclusions.

Phase 11.1 is **implemented, remediated against Independent Audit V1 and pending
independent re-audit**. `IMPLEMENTED_REMEDIATION_V1_PENDING_REAUDIT` is the
Phase 10 matrix vocabulary's `IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT` state
(see the matrix §2): a recorded independent audit `FAIL` exists, the findings
are remediated, and independent re-audit closure is still pending. Nothing in
this document asserts closure, audit success, or verified-existing status.

## 1. Purpose and ownership boundary

Phase 11.1 adds one thin platform composition layer under `cmm/platform/`.

Direction of dependency:

```text
cmm.platform  ->  canonical Phase 0-10 + Phase 11.34 subsystem packages
```

The platform layer **references and composes** canonical subsystem instances.
It never becomes the owner of those subsystems. No canonical subsystem imports
`cmm.platform` in order to function.

`IntegrationServiceRegistry` registers platform **composition bindings** only.
It does not register providers, agents, domains, workflows, operations, tools,
validators, rules or models.

## 2. Canonicalization matrix

Before introducing any public model, every roadmap contract name was classified
against production code. The classification gate was executed read-only with:

```bash
rg -n --glob '*.py' \
  'class (Command|Query|Event|Operation|Workflow|Goal|Session|ApprovalRequest|ValidationResult|ReasoningResult|KnowledgeItem|MemoryRecord|DomainDefinition|AgentResult|ErrorResult|ContractMetadata)\b' \
  cmm kernel tests
```

Classification vocabulary:

- `CANONICAL_EXISTING` — an existing production type remains authoritative.
- `CANONICAL_ADAPTED` — an existing authoritative type satisfies the roadmap
  name through a stable reference; no state model is copied.
- `NEW_PLATFORM_BOUNDARY` — no suitable canonical contract exists.

| Roadmap Contract | Canonical Symbol | Owner | Classification | Contract Version | Schema Version | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `Command` | — none found | — | `NEW_PLATFORM_BOUNDARY` | — | — | Not implemented by 11.1; no production symbol exists. Reserved to later Phase 11 work. |
| `Query` | — none single canonical; `cmm.cognitive.query.KnowledgeQuery`, `cmm.agent_runtime.goal_contracts.GoalQuery`, `cmm.agent_runtime.observation_contracts.ObservationQuery` are subsystem-scoped | respective subsystems | `NEW_PLATFORM_BOUNDARY` | — | — | Not implemented by 11.1. Subsystem query contracts stay authoritative; no unified platform `Query` is created. |
| `Event` | `kernel.events.event.Event` | `kernel.events` | `CANONICAL_EXISTING` | — | — | Canonical kernel event contract reused as-is. No new event bus is introduced. |
| `Operation` | `kernel.planner.operations.Operation` | `kernel.planner` | `CANONICAL_EXISTING` | — | — | Canonical planner operation contract reused as-is. |
| `Workflow` | `cmm.workflows.contracts.WorkflowDefinition` | `cmm.workflows` | `CANONICAL_ADAPTED` | registry SemVer (`_version`) | — | The roadmap name maps to the canonical workflow definition. No platform workflow model is created. |
| `Goal` | `cmm.agent_runtime.goal_contracts.Goal` | `cmm.agent_runtime` | `CANONICAL_EXISTING` | — | — | Canonical goal contract remains owned by the Agent Runtime. |
| `Session` | — none single canonical; `cmm.runtime.sessions` owns `SessionStore`/`FileSessionStore`/`InMemorySessionStore` | `cmm.runtime` | `NEW_PLATFORM_BOUNDARY` | — | — | Not implemented by 11.1. Session storage stays owned by `cmm.runtime`. |
| `ApprovalRequest` | `cmm.agent_runtime.approval_contracts.ApprovalRequest` | `cmm.agent_runtime` | `CANONICAL_EXISTING` | — | — | Canonical approval contract. A distinct `cmm.workflows.contracts.ApprovalRequest` also exists for workflow scoping; neither is duplicated at the platform boundary. |
| `ValidationResult` | `cmm.validation.results.ValidationResult` | `cmm.validation` | `CANONICAL_EXISTING` | — | — | Canonical validation result. Kernel/planner-local `ValidationResult` types remain subsystem-local and are not merged. |
| `ReasoningResult` | `cmm.cognitive.contracts.CognitiveResult` | `cmm.cognitive` | `CANONICAL_ADAPTED` | — | — | The canonical reasoning outcome is `CognitiveResult`. No platform reasoning model is created. |
| `KnowledgeItem` | `cmm.cognitive.knowledge.KnowledgeItem` | `cmm.cognitive` | `CANONICAL_EXISTING` | — | — | Canonical unit of structured knowledge. |
| `MemoryRecord` | — none found; the canonical structured-knowledge unit is `KnowledgeItem`, and `cmm.memory` owns graph/persistence models | `cmm.cognitive` / `cmm.memory` | `NEW_PLATFORM_BOUNDARY` | — | — | Not implemented by 11.1. No second memory store or memory model is introduced. |
| `DomainDefinition` | `cmm.domains.contracts.DomainDefinition` | `cmm.domains` | `CANONICAL_EXISTING` | — | — | Canonical domain definition. No platform domain model or resolver is created. |
| `AgentResult` | `cmm.agent_runtime.contracts.AgentResult` | `cmm.agent_runtime` | `CANONICAL_EXISTING` | — | — | Canonical agent result. No platform agent runtime model is created. |
| `ErrorResult` | `cmm.platform.contracts.ErrorResult` | `cmm.platform` | `NEW_PLATFORM_BOUNDARY` | `1.0.0` | `1` | Implemented by 11.1. The exact symbol was proven absent from production before creation (see §3). Boundary result only; canonical subsystem error types remain authoritative internally. |
| `ContractMetadata` | `cmm.platform.contracts.ContractMetadata` | `cmm.platform` | `NEW_PLATFORM_BOUNDARY` | `1.0.0` | `1` | Implemented by 11.1. Proven absent from production before creation (see §3). Describes a boundary; it does not replace version fields owned by canonical models. |

`ContractCanonicalizationEntry` in `cmm/platform/contracts.py` is the executable
form of one matrix row.

## 3. Absence proof for the two new platform boundary values

`ErrorResult` and `ContractMetadata` were proven absent before being introduced:

```bash
rg -n --glob '*.py' 'class ErrorResult\b|^ErrorResult\s*=' cmm kernel   # no matches
rg -n --glob '*.py' 'class ContractMetadata\b|^ContractMetadata\s*=' cmm kernel   # no matches
```

No canonical production equivalent exists, so 11.1 introduces the minimum
platform-boundary values required for safe structured composition diagnostics
and for version-aware contract boundaries.

## 4. Input and output contract strategy

- Existing canonical types are reused by reference. Phase 11.1 does not copy,
  re-declare, wrap-and-duplicate, or persist a second copy of an authoritative
  object.
- `ServiceDescriptor` carries boundary metadata only: identifiers, contract
  metadata, dependency declarations, mode and an optional authority claim.
- Descriptors never carry secrets, credentials, tokens, provider payloads,
  prompts, hidden reasoning, or copied sensitive domain content.
- The only new registry introduced by Phase 11.1 is
  `IntegrationServiceRegistry`, a registry of composition bindings.

## 5. Platform package responsibilities

| Module | Responsibility |
| --- | --- |
| `cmm/platform/__init__.py` | Public exports of the Phase 11.1 integration surface only. Importing the package performs no registration and no mutation. |
| `cmm/platform/contracts.py` | Immutable platform-boundary values: `ContractMetadata`, `ContractClassification`, `ContractCanonicalizationEntry`, `ServiceMode`, `ServiceDependency`, `ServiceDescriptor`, `ServiceBinding`, `ContainerState`, `ErrorResult`. |
| `cmm/platform/compatibility.py` | Deterministic offline compatibility checks. Default rule: exact contract name, owner, schema version and contract version are required. Unknown or mismatched input fails closed. No migration framework and no semver-range negotiation. |
| `cmm/platform/errors.py` | Typed platform-composition exceptions carrying safe structured details (identifiers and reason codes only). |
| `cmm/platform/service_registry.py` | `IntegrationServiceRegistry`: binding registration, lookup, deterministic listing, explicit replacement, freeze, graph validation, cycle detection, duplicate-authority detection, deterministic dependency order. No global singleton. |
| `cmm/platform/configuration.py` | Strict in-memory Phase 11.1 composition configuration. Not the Phase 11.12 Configuration Center. |
| `cmm/platform/modules.py` | Side-effect-free `CompositionModule` contribution contract. Not the Phase 11.19 Plugin System. |
| `cmm/platform/inspection.py` | Allowlisted, deterministic composition snapshots. |
| `cmm/platform/container.py` | `ApplicationContainer` composition root and readiness lifecycle. |
| `cmm/platform/canonical.py` | Pure binding builders that accept already-constructed canonical subsystem objects. |

## 6. Bound canonical service identities

The representative composition binds these canonical service identities. Each
builder receives an already-created canonical object; no builder constructs a
subsystem. Each builder also declares the canonical **runtime boundary** shown
below and rejects any implementation that does not satisfy it (see §14).

| Service ID | Canonical implementation | Owner package | Runtime boundary |
| --- | --- | --- | --- |
| `validation.application` | `cmm.validation.interfaces.application.ValidationApplicationService` | `cmm.validation` | `ValidationApplicationService` |
| `cognitive.service` | `cmm.cognitive.service.ResourceExtractionService` | `cmm.cognitive` | `ResourceExtractionService` |
| `cognitive.adapter_registry` | `cmm.cognitive.registries.ResourceAdapterRegistry` | `cmm.cognitive` | `ResourceAdapterRegistry` |
| `cognitive.extractor_registry` | `cmm.cognitive.registries.KnowledgeExtractorRegistry` | `cmm.cognitive` | `KnowledgeExtractorRegistry` |
| `agent.runtime.integration` | `cmm.agent_runtime.agent_runtime_integration_service.AgentRuntimeIntegrationService` | `cmm.agent_runtime` | `AgentRuntimeIntegrationService` |
| `domain.registry` | `cmm.domains.registry.DomainRegistry` | `cmm.domains` | `DomainRegistry` |
| `workflow.registry` | `cmm.workflows.registry.InMemoryWorkflowRegistry` | `cmm.workflows` | `InMemoryWorkflowRegistry` |
| `execution.registry` | `cmm.execution.executor_registry.ExecutorRegistry` | `cmm.execution` | `ExecutorRegistry` |
| `provider.registry` | `kernel.llm.provider_registry.ProviderRegistry` (canonical Phase 11.34 authority) | `kernel.llm` | `ProviderRegistry` |

### 6.1 Platform boundary contract metadata

`ContractMetadata` describes the **platform boundary**, not a canonical model's
own version fields. Where the canonical subsystem already publishes the relevant
version, that value is reused; otherwise the value is an adapter-level platform
boundary version owned by `cmm.platform`.

| Service ID | contract_name | contract_version | schema_version | authority |
| --- | --- | --- | --- | --- |
| `validation.application` | `validation.application` | `1.0.0` | `1` | — |
| `cognitive.service` | `cognitive.service` | `1.0.0` | `1` | — |
| `cognitive.adapter_registry` | `cognitive.adapter_registry` | `1.0.0` | `1` | — |
| `cognitive.extractor_registry` | `cognitive.extractor_registry` | `1.0.0` | `1` | — |
| `agent.runtime.integration` | `agent.runtime.integration` | `1.0.0` | `1` | — |
| `domain.registry` | `domain.registry` | `1.0.0` | `1` | — |
| `workflow.registry` | `workflow.registry` | `1.0.0` | `1` | — |
| `execution.registry` | `execution.registry` | `1.0.0` | `1` | — |
| `provider.registry` | `provider.registry` | `2.0.0` | `2` | `provider-registry` |

The `provider.registry` boundary reuses the canonical Phase 11.34 state schema
(`kernel.llm.provider_state.SCHEMA_VERSION == "2"`) rather than inventing a
value; the builder imports that constant, so the platform boundary tracks the
canonical value automatically. No canonical version field is replaced.

`provider.registry` is bound with authority `provider-registry` and holds **the
same object instance** as the canonical Phase 11.34 Provider Registry. Phase 11.1
creates no second provider registry, infers no providers, and stores no parallel
provider state.

### 6.2 Dependency declarations

Declared dependencies reflect real construction requirements only.

`ResourceExtractionService.__init__(adapter_registry, extractor_registry)`
requires both canonical registries positionally. Therefore
`cognitive.service -> cognitive.adapter_registry` and
`cognitive.service -> cognitive.extractor_registry` are genuine composition
requirements, and `cognitive.adapter_registry` /
`cognitive.extractor_registry` are bound as platform services because the
representative composition includes them.

Every other builder declares **no** dependency. `AgentRuntimeIntegrationService`
takes Agent Runtime internals (`store`, `goal_manager`, `registry_service`,
`runtime_loop`, `security_service`, `execution_adapter`), which are owned by
`cmm.agent_runtime` and are deliberately not re-bound at the platform level, so
no platform dependency is declared for it. No dependency is fabricated for graph
coverage; this is asserted by
`tests/platform/test_architecture.py::test_builders_do_not_declare_fabricated_dependencies`.

## 7. Configuration scope

Phase 11.1 configuration is composition configuration only: enabled composition
modules, required service IDs, expected contract/schema versions, and the mode
flag needed to choose a local in-process binding versus an explicit adapter
binding.

It does not own secrets, credentials, user preferences, model-routing policy,
domain privacy policy, autonomy policy, or general application settings.

## 8. Readiness semantics

A container reaches `READY` only after the full ordered pipeline succeeds:

1. validate configuration;
2. validate module IDs;
3. select explicitly enabled modules;
4. collect contributed bindings;
5. register bindings;
6. verify every required service exists;
7. verify configured contract expectations;
8. validate the dependency graph;
9. freeze the registry;
10. create the safe composition snapshot;
11. mark `READY`.

Any failure before step 11 fails closed. A partially ready container is never
reported as `READY`.

## 9. Inspection safety

Per service the snapshot exposes only `service_id`, `implementation_id`,
`contract_name`, `contract_version`, `schema_version`, `owner`,
`dependency_ids`, `mode` and `authority`. The application snapshot exposes only
`state` and `services`.

Arbitrary descriptor metadata is not serialized. Raw implementation objects,
runtime contract objects, secrets, credentials, tokens, prompts, hidden
reasoning, provider payloads and opaque internal state are never exposed. Since
Remediation V1, descriptor metadata is additionally restricted at construction
by the grammar in §14.2, so the inspection allowlist stays exactly as it is and
the metadata boundary is narrowed rather than widened.

## 10. Explicit exclusions

Phase 11.1 does not implement: the Phase 11.2 Orchestrator, `IntentResolver`,
`ContextResolver`, `DomainRouter`, `AgentRouter`, `OrchestrationRequest`,
`OrchestrationResult`, central user-request processing, API or backend
endpoints, a conversational interface, CMMChat or CMM Bots integration, the
Model Gateway, routing policy, real remote transport, authentication,
authorization/RBAC, secrets management, storage migrations, backup/recovery,
the Phase 11.19 Plugin System lifecycle, Docker runtime, a new Event System, UI,
search, notifications, audit-trail subsystem, or performance/resource-management
subsystem.

Future-compatible abstractions are permitted; their behaviour is not.

## 11. Inherited requirement reuse

`F11-014` / `DP-134` (Phase 11.34 Provider Registry) is **closed and already
independently verified**. Phase 11.1 reuses it as a dependency and does not
reopen it. `AT-DP-134` — `tests/llm/test_provider_registry_dp134_acceptance.py`
— remains the acceptance evidence for the provider authority.

## 12. Traceability

| Item | Value |
| --- | --- |
| Requirement | `F11-015 — Canonical Integration Core` |
| Design point | `DP-101 — Canonical Application Composition Root` |
| Acceptance test | `AT-DP-101` — `tests/platform/test_phase11_1_dp101_acceptance.py` |
| Inherited acceptance | `AT-DP-134` — `tests/llm/test_provider_registry_dp134_acceptance.py` |
| Production package | `cmm/platform/` |
| Architecture gates | `tests/platform/test_architecture.py` |

Phase state: `IMPLEMENTED_REMEDIATION_V1_PENDING_REAUDIT` (audit `FAIL` recorded,
findings remediated, independent re-audit pending).

No closure, audit, or verified-existing status is claimed here. Independent
re-audit must return `BLOCKERS=0`, `MAJORS=0`, `DP-101=VERIFIED_EXISTING`,
`AT-DP-101=PASS` and `CLOSURE_ELIGIBLE=YES` before any closure commit exists.

## 13. Implementation decisions and minimal deviations from the committed plan

The committed plan's architecture, scope and acceptance criteria were followed.
The following minimal adjustments were required by repository reality and are
recorded here as required:

1. **`tests/__init__.py` added.** The plan specifies `tests/platform/__init__.py`.
   Under pytest's default `prepend` import mode, that makes the directory
   importable only as the top-level package `platform`, whose name is already
   owned by the Python standard library; collection then fails with
   `ModuleNotFoundError: No module named 'platform.test_...'; 'platform' is not
   a package`. Omitting `tests/platform/__init__.py` instead makes the modules
   rootless and collides with the equally rootless
   `tests/workflows/test_contracts.py` (`import file mismatch`). Adding a single
   `tests/__init__.py` gives every test module a unique identity
   (`tests.<directory>.<module>`), preserves every approved test filename
   verbatim, and leaves the inherited suite green. No production code and no
   approved test filename changed.

2. **Requirements-matrix path.** The plan names
   `docs/reference/phase-11-requirements-matrix.md`. That file does not exist;
   the canonical Phase 11 matrix is
   `docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md`,
   which was updated instead.

3. **`FrozenServiceRegistryError` added.** The plan lists eight concrete
   exception classes. Registering into or replacing within an already-frozen
   registry has no accurate home among them, so one additional typed error was
   added (`SERVICE_REGISTRY_FROZEN`, category `lifecycle`) to keep diagnostics
   precise. It is not a new subsystem or registry.

4. **`ApplicationContainer.failed(error)` added.** The approved design declares
   `ContainerState.FAILED` as part of the lifecycle and lists `container not
   ready` as an error category. `build()` still fails closed by raising and
   returns no container, so `failed(...)` is the explicit constructor that makes
   the `FAILED` state and the `ContainerNotReadyError` category reachable rather
   than dead. A failed container holds no registry and refuses service lookup.

5. **`CompatibilityStatus` is the stored field.** `CompatibilityResult` stores
   `status` and `reason_code`, and exposes `compatible` as a derived property, so
   both the plan's `CompatibilityStatus` output and the plan's
   `result.compatible is True` usage hold.

6. **Version well-formedness guard.** The spec requires malformed versions to
   fail closed. A version token must be a dotted numeric core with an optional
   `-prerelease` / `+build` suffix; anything else fails closed with
   `MALFORMED_VERSION`. No semver-range negotiation, migration or network lookup
   exists.

7. **Two cognitive registry services.** Beyond the required identities,
   `cognitive.adapter_registry` and `cognitive.extractor_registry` are bound
   because `ResourceExtractionService` requires both canonical registries to
   exist. They are existing canonical registries bound by reference — not new
   registries and not graph decoration.

8. **`ROADMAP.md` deliberately unchanged.** The repository's top-level roadmap
   records subphase status only in closed/audited terms; it contains no pre-audit
   status convention. Under the assignment's condition ("only if the repository's
   current pre-audit convention requires a top-level status change"), no change
   was made; the pre-audit status is recorded in the detailed Phase 11 roadmap
   §11.1 and in the Phase 11 requirements matrix §8.

9. **Ruff invocation.** `CONTRIBUTING.md` defines the repository's canonical
   Ruff invocation as scoped to changed Python files
   (`python -m ruff check <changed-python-paths>`). Bare repository-wide
   `ruff check .` / `ruff format --check .` are **not** clean at the Phase 11.1
   starting HEAD for pre-existing reasons unrelated to this subphase. Phase 11.1
   is therefore validated with the canonical scoped invocation; the
   repository-wide baseline was measured and reported without being altered.

No deviation changes the architecture, widens the scope, replaces a canonical
subsystem owner, or pulls Phase 11.2 work forward.

## 14. Remediation V1 — Independent Audit V1 findings

Independent Audit V1 returned `FAIL` with `BLOCKERS=0`, `MAJORS=3`,
`MINORS=0` and `DP-101=NOT_VERIFIED`. Remediation V1 fixes exactly those three
findings inside the Phase 11.1 boundary. It reopens no closed phase, adds no
platform subsystem, weakens no inherited test and implements no Phase 11.2
scope.

### 14.1 `MAJOR-01` — canonical runtime boundaries are enforced

Audit V1 reproduced a binding that could claim the authoritative provider
identity while holding an unrelated object:

```python
provider_registry_binding(object())   # reached ContainerState.READY before remediation
```

The builders in `cmm/platform/canonical.py` now declare an enforceable
`runtime_contract` for every canonical service and fail closed before a binding
can exist:

```python
binding = provider_registry_binding(real_provider_registry)
assert binding.implementation is real_provider_registry
assert binding.runtime_contract is ProviderRegistry

provider_registry_binding(object())   # TypeError
```

| Aspect | Result |
| --- | --- |
| Boundary kind | canonical concrete class per service (§6); no existing runtime-checkable protocol describes these whole-service boundaries, so the canonical owning class is the strongest available boundary |
| Builder-level rejection | `_require_canonical_implementation(...)` raises `TypeError` before the `ServiceBinding` is created |
| Registry-level defense in depth | `IntegrationServiceRegistry.register()` / `replace()` re-check the declared `runtime_contract`; no change was made to that existing enforcement |
| Canonical identity | the bound object is still the exact canonical instance; Phase 11.34 `ProviderRegistry` keeps its identity, state schema and authority semantics |
| Replacement / test adapters | unchanged: an explicitly declared alternate implementation is still bound through `ServiceBinding` plus register/replace with its own boundary, gated by contract compatibility and rejected after freeze |
| Boundary type import | resolved inside each builder, so importing `cmm.platform` stays a thin, side-effect-free import |

Evidence: `tests/platform/test_architecture.py` (per-service runtime contract,
unrelated-object rejection, foreign-canonicity rejection, replacement
preservation), `tests/platform/test_service_registry.py`
(re-registration re-check), `AT-DP-101` (fake authority rejection, forged
binding rejected before readiness, identity preserved for every canonical
binding).

### 14.2 `MAJOR-02` — descriptor metadata is secret-free and recursively immutable

Audit V1 reproduced secret-shaped and mutable nested metadata:

```python
ServiceDescriptor(..., metadata={"token": "sk-secret", "nested": {"password": "p"}})
```

`ServiceDescriptor.metadata` is now a small descriptive boundary.

Allowed values, recursively: `None`, `bool`, `int`, `float`, `str`, mappings of
allowed values, and sequences of allowed values. Mappings are copied and
normalized to immutable mappings (`MappingProxyType`), sequences are normalized
to tuples, and any other object (a live client, callable, `bytes`, arbitrary
runtime object) is rejected with `TypeError`. A caller's later mutation of the
input object cannot reach the descriptor, and no nested value is mutable
through the descriptor. This is the representation chosen in Remediation V1:
recursively immutable mappings plus tuples — no new immutable-collection
framework was added.

Keys are compared against a fixed denylist after deterministic normalization
(lowercasing and non-alphanumeric characters becoming `_`), both as the whole
normalized key and per segment, so all of these fail closed with `ValueError`:

```text
secret  secrets  credential  credentials  password  passwd  token  api_key
apikey  access_key  private_key  auth  authorization  cookie  session_key
prompt  reasoning  provider_payload  payload
```

```python
ServiceDescriptor(..., metadata={"display": {"authorization": "Bearer ..."}})  # ValueError
ServiceDescriptor(..., metadata={"provider_payload": {"x": 1}})                 # ValueError
ServiceDescriptor(..., metadata={"client": object()})                           # TypeError
```

The check is structural and key-based. No content heuristics, entropy scanning,
secrets manager, credential vault, sanitizer framework or DLP subsystem was
introduced, and permitted key spelling is preserved rather than rewritten.

Inspection output is unchanged: descriptor metadata is still excluded from the
public composition snapshot (`ApplicationCompositionSnapshot.to_dict()`).

Evidence: `tests/platform/test_contracts.py` (denylist, nested denylist,
normalization, opaque objects, non-string keys, recursive immutability,
defensive copy), `tests/platform/test_inspection.py` (snapshot still excludes
metadata), `AT-DP-101` (unsafe metadata cannot enter the connected composition;
permitted metadata stays out of the public boundary and is detached).

### 14.3 `MAJOR-03` — invalid service modes are rejected before readiness

Audit V1 reproduced a ready container holding a malformed mode:

```python
ServiceDescriptor(..., mode="bogus")   # reached READY; snapshot().to_dict() then failed
```

`ServiceDescriptor.mode` and `ServiceInspection.mode` now require a real
`ServiceMode` and raise `TypeError` at construction. Arbitrary strings are never
silently coerced, so `mode="bogus"`, `mode="local"` and `mode=None` cannot reach
a container. `ServiceInspection.to_dict()` emits `self.mode.value` from a value
that is guaranteed to be a `ServiceMode`.

The readiness invariant is now permanent:

```python
assert container.state is ContainerState.READY
container.snapshot().to_dict()   # must succeed, deterministically
```

Evidence: `tests/platform/test_contracts.py` and
`tests/platform/test_inspection.py` (strict mode boundary),
`tests/platform/test_container.py` (ready snapshot always serializable and
JSON-round-trippable), `AT-DP-101` (malformed mode rejected at the public
boundary of the real connected graph; ready snapshot serializes with
`state == "ready"`).

### 14.4 Inherited and unaffected behaviour

- `AT-DP-134` remains green and unchanged: `tests/llm/test_provider_registry_dp134_acceptance.py`.
- Phase 11.34 production modules were not modified; no second Provider Registry
  exists and no provider, lifecycle, manifest, connection, model-route or
  discovery semantics changed.
- No canonical Phase 0–10 package imports `cmm.platform`; the dependency
  direction `cmm.platform -> canonical subsystems` is unchanged.
- `IntegrationServiceRegistry` remains the only Phase 11.1 registry.
- No Phase 11.2 symbol, routing, transport or orchestration behaviour was added.

### 14.5 Remediation status

```text
PHASE11_1=IMPLEMENTED_REMEDIATION_V1_PENDING_REAUDIT
MAJOR_01=REMEDIATED_PENDING_REAUDIT
MAJOR_02=REMEDIATED_PENDING_REAUDIT
MAJOR_03=REMEDIATED_PENDING_REAUDIT
DP_101=IMPLEMENTED_REMEDIATION_V1_PENDING_REAUDIT
AT_DP_101=PASS
AT_DP_134=PASS
CLOSURE_ELIGIBLE=NO
```

Only the independent re-audit may conclude `MAJOR_01=VERIFIED_REMEDIATED`,
`MAJOR_02=VERIFIED_REMEDIATED`, `MAJOR_03=VERIFIED_REMEDIATED`,
`DP-101=VERIFIED_EXISTING` and `CLOSURE_ELIGIBLE=YES`. The Audit V1 record at
`docs/audits/phase-11.1-integration-core-independent-audit-v1.md` is historical
evidence and is deliberately left unedited.
