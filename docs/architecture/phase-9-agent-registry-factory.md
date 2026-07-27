# Phase 9.23 — Agent Registry & Factory

> Status: **implementation consolidated, documentation initial**.
> Phase not yet closed; see [§11 Known Limits](#11-known-limits).

---

## 1. Objective

Provide a single, typed, thread-safe subsystem that:

* stores and lifecycle-manages declarative **agent descriptors**
  (`AgentDescriptor`);
* registers and executes pluggable **agent factories**
  (`AgentFactory`) with scope-correct instance caching;
* turns a functional **requirement** (`AgentRequirement`) into a
  deterministic, scored **resolution** (`AgentResolution`) that never
  surfaces an incompatible candidate;
* exposes a single façade (`AgentRegistryService`) consumed by the
  Agent Runtime loop, the CLI, and (future) the HTTP and n8n adapters.

The phase replaces ad-hoc agent lookups scattered across
9.x with a contract-first subsystem.

---

## 2. Architecture overview

```
                ┌────────────────────────────┐
                │     AgentRegistryService    │  ◄── single entry point
                └────────────┬────────────────┘
                             │
        ┌────────────────────┼─────────────────────┐
        ▼                    ▼                     ▼
┌───────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ AgentRegistry │   │ AgentFactoryReg. │   │  AgentResolver   │
│ (descriptors) │   │ (factories+caches)│  │ (resolution)     │
└──────┬────────┘   └────────┬─────────┘   └────────┬─────────┘
       │                     │                      │
       ▼                     ▼                      ▼
┌───────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ Store (proto) │   │ Scoped caches    │   │ Compat. checker  │
│ InMemory today│   │ TRANSIENT/etc.   │   │ + scorer         │
└───────────────┘   └──────────────────┘   └──────────────────┘
```

* **Registry** owns descriptors and lifecycle transitions
  (`enable`/`disable`/`deprecate`/`retire`).
* **Factory registry** owns `AgentFactory` instances and applies the
  four scopes (see [§6 Scopes](#6-scopes)).
* **Resolver** owns `AgentCompatibilityChecker` + `AgentCandidateScorer`
  and applies the strategy chosen by the caller.
* **Service** is the only collaborator-aware façade; nothing inside
  the subsystem touches globals.

All components are thread-safe (`threading.RLock`), immutable at the
contract level (`@dataclass(frozen=True)`), and JSON-serializable
through `.to_dict()`.

---

## 3. Modules (production)

| File | Role |
|------|------|
| `cmm/agent_runtime/agent_registry_contracts.py` | Immutable contracts: `AgentCapability`, `AgentDescriptor`, `AgentRequirement`, `AgentVersion`, `AgentInstance`, `AgentFactoryContext`, `AgentResolution`, `AgentResolutionCandidate`, `AgentCompatibilityResult`, `AgentProvisioningResult`. |
| `cmm/agent_runtime/agent_registry_enums.py` | `AgentKind`, `AgentLifecycle`, `AgentAvailability`, `AgentCapabilityKind`, `AgentFactoryScope`, `AgentResolutionStrategy`, `AgentCompatibilityStatus`, `AgentRegistrationStatus`, `AgentVersionStatus`. |
| `cmm/agent_runtime/agent_registry_errors.py` | Error hierarchy with stable `error_code` constants and redaction of sensitive substrings (`api_key`, `password`, `bearer`, `Traceback …`, etc.). |
| `cmm/agent_runtime/agent_registry_validation.py` | `AgentVersionValidator`, `AgentCapabilityValidator`, `AgentDescriptorValidator`, `AgentFactoryValidator`, `AgentRequirementValidator`. |
| `cmm/agent_runtime/agent_registry_store.py` | `AgentRegistryStore` protocol + `InMemoryAgentRegistryStore`. The only persistence abstraction in 9.23. |
| `cmm/agent_runtime/agent_registry.py` | `AgentRegistry` façade (register/unregister/list/snapshot/lifecycle) + `AgentRegistrySnapshot`. |
| `cmm/agent_runtime/agent_factory_contracts.py` | `AgentFactory` Protocol, `AgentFactoryRegistration`, `AgentFactoryRegistrySnapshot`, defensive helpers (`assert_descriptor_match`, `assert_compatible_scope`). |
| `cmm/agent_runtime/agent_factory.py` | `AgentFactoryRegistry` with scope-based caches, structured error mapping, and stats. |
| `cmm/agent_runtime/agent_resolver.py` | `AgentCompatibilityChecker`, `AgentCandidateScorer`, `AgentResolver`. |
| `cmm/agent_runtime/agent_registry_service.py` | `AgentRegistryService` façade + `AgentRegistryHealth` + `AgentRegistryStats`. |

---

## 4. Contracts

### 4.1 Identity

* `AgentDescriptor` identity = `(agent_id, version.canonical())`.
* Multiple versions of the same `agent_id` may coexist.
* Descriptors are immutable; lifecycle transitions return *new*
  descriptors (`descriptor.with_lifecycle(target)`).

### 4.2 Validation

* Validation is split into two layers:
  * `__post_init__` enforces structural shape (id pattern,
    non-empty fields, duplicate detection, JSON-safe metadata).
  * `*Validator.validate()` enforces *cross-field* and *policy* rules
    (e.g. `lifecycle ∈ {RETIRED, DISABLED}` rejected,
    `preferred_agents ∩ excluded_agents = ∅`, `version` parsed when
    given as string).
* Neither layer mutates input.

### 4.3 Security

* Errors never leak `str(exc)` from internal exceptions; messages and
  details are sanitised.
* Forbidden metadata keys (`api_key`, `password`, `chain_of_thought`,
  etc.) are rejected at construction time.

---

## 5. Registry

`AgentRegistry` exposes:

| Method | Behaviour |
|--------|-----------|
| `register(descriptor)` | Validates → reserves aliases → calls `store.add`. On unexpected `store` failure, rolls back alias ownership and raises `AgentRegistryError` (no `str(exc)` leakage). |
| `unregister(agent_id, version)` | Removes from store, releases aliases, returns the removed descriptor. |
| `get(agent_id, version=None)` | `version=None` returns the latest `ACTIVE` descriptor. |
| `get_required(...)` | Same as `get` but raises `AgentRegistryNotFoundError`. |
| `list(lifecycle=..., kind=...)` | Deterministic tuple. |
| `find_by_alias / find_by_capability / find_by_kind / find_by_tag` | Indexed lookups. |
| `enable / disable / deprecate / retire` | Lifecycle transitions; retire is the only transition that *removes* the descriptor (RETIRED state is implicit absence). |
| `snapshot()` | `AgentRegistrySnapshot`, JSON-safe. |
| `register_many(iterable)` | Bulk convenience. |

### 5.1 Alias bookkeeping

* Aliases are stored in a per-registry index: `alias → set[(agent_id,
  version.canonical())]`.
* On register, only the *newly* reserved aliases are tracked so that a
  mid-registration conflict rolls back cleanly without disturbing
  aliases already owned by the same identity.

---

## 6. Factory registry

`AgentFactoryRegistry` exposes:

| Method | Behaviour |
|--------|-----------|
| `register(factory)` | Validates structurally, ensures unique `factory_id`, returns `AgentFactoryRegistration`. |
| `unregister(factory_id)` | Removes the factory and invalidates its caches. |
| `get(factory_id)` / `contains(factory_id)` | Lookup. |
| `list()` / `registrations()` | All factories. |
| `create(descriptor, context)` | Scope-aware creation with caches; maps unexpected exceptions to `AgentFactoryCreationError`. |
| `clear_caches()` | Test helper. |
| `stats()` | Real counters. |
| `snapshot()` | `AgentFactoryRegistrySnapshot`, JSON-safe. |

### 6.1 Scopes

| Scope | Cache key | Notes |
|-------|-----------|-------|
| `TRANSIENT` | none | Every `create()` returns a fresh instance. |
| `REQUEST` | `(factory_id, context.request_id)` | One instance per request. |
| `RUN` | `(factory_id, context.run_id)` | `context.run_id` is mandatory. |
| `SINGLETON` | `factory_id` | Only allowed when the factory declares `thread_safe=True`. |

### 6.2 Defensive checks on `create()`

1. The factory must be registered.
2. The factory must structurally support the descriptor.
3. The factory is invoked inside a safe boundary; any non-typed
   exception becomes `AgentFactoryCreationError("Factory raised …")`
   without exposing `str(exc)`.
4. The returned instance must be an `AgentInstance`, have a non-null
   `runtime_object`, a non-empty `instance_id`, and a matching
   `descriptor` (via `assert_descriptor_match`) and `scope`.

---

## 7. Resolver

The resolver is split into three components:

### 7.1 `AgentCompatibilityChecker`

Returns an `AgentCompatibilityResult` (never raises for normal
incompatibilities). Failures are differentiated:

| Reason | Status |
|--------|--------|
| `agent_excluded` | `EXCLUDED` |
| `lifecycle_disabled` / `lifecycle_retired` / `lifecycle_deprecated_not_allowed` / `lifecycle_experimental_not_allowed` | `INCOMPATIBLE_LIFECYCLE` |
| `kind_mismatch` | `INCOMPATIBLE_RUNTIME` |
| `version_parse_error` / `version_mismatch` | `INCOMPATIBLE_VERSION` |
| `missing_capabilities` / `missing_tags` | `INCOMPATIBLE_CAPABILITY` |
| `missing_operations` | `INCOMPATIBLE_OPERATION` |
| `missing_permissions` | `INCOMPATIBLE_PERMISSION` |
| `missing_components` | `INCOMPATIBLE_COMPONENT` |
| `factory_not_registered` / `factory_does_not_support` / `factory_supports_error` / `factory_registry_unavailable` | `FACTORY_UNAVAILABLE` |

`factory_registry_unavailable` is *not* silently degraded to "no
components" — a registry that throws while listing surfaces a distinct
failure mode.

### 7.2 `AgentCandidateScorer`

Deterministic, weighted scoring:

* matched capabilities × 20
* matched operations × 10
* matched tags × 5
* preferred-agent bonus × 50 (one-shot)
* exact `agent_id` × 100 (one-shot)
* exact version × 30 (one-shot)
* descriptor priority (additive)

### 7.3 `AgentResolver`

| Strategy | Behaviour |
|----------|-----------|
| `EXACT` | If `agent_id` given and no compatible descriptor → `AgentResolutionNotFoundError`; multiple compatibles → `AgentResolutionAmbiguousError`. |
| `BEST_MATCH` (default) | Highest score, with stable tiebreakers; ambiguous ties raise `AgentResolutionAmbiguousError`. |
| `HIGHEST_PRIORITY` | Compatible with max `descriptor.priority`. |
| `HIGHEST_VERSION` | Compatible with max `descriptor.version`. |
| `CAPABILITY_MATCH` | Compatible with most matched capabilities and operations. |

The resolver never selects an incompatible candidate, even under
`BEST_MATCH` (returns `selected=None` and an empty selection instead).

---

## 8. Service

`AgentRegistryService` is the only collaborator-aware façade. It owns:

* `registry`, `factory_registry`, `resolver`,
  `compatibility_checker` (all injectable);
* service-level counters for resolution outcomes;
* `health()`, `stats()`, `snapshot()`, `register_*()`, `resolve_agent()`,
  `create_agent()`, `resolve_and_create()`.

`resolve_and_create()` returns an `AgentProvisioningResult`:

* If resolution finds no compatible descriptor, `instance=None`.
* If the factory fails, a typed `AgentFactoryCreationError` is raised;
  no result is returned claiming success.
* Internal errors never leak `str(exc)`.

`health()` distinguishes `registry_available`, `factory_registry_available`,
`resolver_available`, `registered_agents`, `active_agents`,
`registered_factories`, `resolvable_agents` (active agents whose factory
is registered *and* returns `supports(descriptor) == True`).

`stats()` is driven by real counters — never invented.

---

## 9. Standalone in-memory state

Today the subsystem is **standalone, in-memory**:

* `AgentRegistry` uses `InMemoryAgentRegistryStore` unless a store
  implementing the protocol is injected.
* `AgentFactoryRegistry` caches live inside the process.
* Snapshots are immutable, JSON-safe, and process-local.

There is no cross-process persistence and no replay.

---

## 10. Future integration (planned, not implemented)

* **HTTP API** (Agent Runtime API, phase 9.21) will expose
  `register_agent`, `register_factory`, `resolve_agent`,
  `resolve_and_create`, `health`, `stats`, `snapshot` via the existing
  middleware chain.
* **n8n adapter**: the service is structured so that an
  `AgentRegistryService` instance can be wrapped by an HTTP/Webhook
  adapter without touching internals.
* **Persistence**: replace `InMemoryAgentRegistryStore` with a SQLite
  or remote store implementing the same protocol. Alias and capability
  indexes must remain deterministic.

---

## 11. Known limits

* No persistence outside the process.
* No cross-process cache coherence; `SINGLETON` scope is per-process.
* No factory hot-reload; `unregister`/`register` invalidates caches but
  does not migrate in-flight instances.
* `AgentResolution.__post_init__` uses `is`-based identity to validate
  that `selected` is among candidates, because `AgentDescriptor` is
  not hashable. Descriptors are immutable so identity comparison is
  safe, but a custom `__hash__`/`__eq__` could simplify this in a
  later phase.
* Thread-safety is `RLock`-based; per-call contention is acceptable but
  long-running `create()` on a `SINGLETON` factory serialises.

---

## 12. Test inventory

| File | Block | Tests |
|------|-------|-------|
| `tests/agent_runtime/test_agent_registry_factory.py` | A: enums, errors, version, capability, descriptor, requirement, validators. B: store, registry, lifecycle. C: factory contracts, factory registry, scopes. D: compatibility, resolver, scorer, service, health, stats. | 147 |
| `tests/agent_runtime/test_agent_registry_factory_regressions.py` | Regression suite for gaps surfaced by the Ruff cleanup pass: alias rollback, version parsing, factory registry unavailable vs supports-false vs supports-error, `required_capabilities` filtering, EXACT no-fallback, `resolve_and_create` no-false-success, factory error boundary. | 12 |

Total: **159 tests for 9.23**, all green.

---

## 13. Cleanup summary (this iteration)

* Ruff: 20 → **0** errors across `agent_registry_*.py`,
  `agent_factory*.py`, `agent_resolver.py`, `agent_runtime/__init__.py`,
  `tests/agent_runtime/test_agent_registry_factory*.py`.
* 16 errors fixed automatically (`--fix`); 4 fixed manually (one
  undefined-name, three `BLE001`/`F401`/`SIM102` in resolver).
* `AgentRegistry.register()` now distinguishes `AgentRegistryError`
  vs `AgentRegistryConflictError` rollback paths; only newly-reserved
  aliases are released on failure (previously the whole alias set was
  released unconditionally).
* `AgentCompatibilityChecker.check()` no longer uses bare
  `except Exception`; it surfaces `factory_registry_unavailable` and
  `factory_supports_error` as distinct reasons.
* Dead `_iter_candidates` block (a no-op `if … pass` over
  `requirement.required_capabilities`) removed; compatibility checking
  remains the authoritative gate.
* `AgentResolution.__post_init__` switched from `{descriptor: …}` (which
  required `AgentDescriptor` to be hashable) to `is`-based identity
  comparison; one real bug discovered and fixed.