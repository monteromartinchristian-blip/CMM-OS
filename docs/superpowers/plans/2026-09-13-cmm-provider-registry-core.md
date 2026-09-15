# CMM Provider Registry Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve CMM OS's existing `ProviderRegistry` + `ModelCatalog` into a route-aware provider inventory that distinguishes provider definitions, accepted connections, canonical models, and provider-specific model routes without breaking existing LLM execution.

**Architecture:** Reuse the current CMM OS LLM kernel (`ProviderRegistry`, `ModelCatalog`, `ProviderFactory`, `OpenAICompatibleProvider`) and add focused domain types around them rather than replacing them. Existing `ProviderSpec`/`ModelSpec` continue to support current execution while new `ProviderConnection`/`ModelRoute` metadata becomes the canonical inventory consumed by discovery, CMM Usage, and routing.

**Tech Stack:** Python 3.10+, dataclasses, pytest, Ruff, existing `kernel.llm` contracts.

**Spec:** `docs/superpowers/specs/2026-09-13-cmm-provider-registry-hybrid-design.md`

## Global Constraints

- External configuration is evidence, not authority.
- Detection does not create a routable connection.
- No secrets may be persisted in Registry state.
- Provider/model route identity must remain stable across rediscovery.
- Model disappearance must not delete historical route identity.
- Unknown capability is not sufficient for capability-required automation.
- Existing `ProviderRegistry`, `ModelCatalog`, `ProviderFactory`, and `OpenAICompatibleProvider` behavior must remain backward-compatible.
- No provider-specific execution logic belongs in this plan.
- No live inference is allowed in this plan.

---

## File Structure

- Modify: `kernel/llm/provider_registry.py` — preserve `ProviderSpec`; add connection registration/lookup primitives or delegate them to the new connection registry.
- Create: `kernel/llm/provider_connections.py` — `BillingClass`, `ConnectionStatus`, `ProviderConnection`, `ProviderConnectionRegistry`.
- Modify: `kernel/llm/model_catalog.py` — preserve `ModelSpec`; add canonical identity helpers only where required.
- Create: `kernel/llm/model_routes.py` — `CapabilityConfidence`, `RouteCapabilityState`, `ModelRoute`, `ModelRouteCatalog`.
- Modify: `kernel/llm/capabilities.py` — add route capability normalization helpers without changing existing boolean capability contracts.
- Modify: `kernel/llm/__init__.py` — export new public contracts.
- Create: `tests/llm/test_provider_connections.py`.
- Create: `tests/llm/test_model_routes.py`.
- Modify: `tests/llm/test_provider_registry_v2.py` — regression coverage.
- Modify: `tests/llm/test_model_catalog_v2.py` — regression coverage.

---

### Task 1: Add durable provider connection identity without secrets

**Files:**
- Create: `kernel/llm/provider_connections.py`
- Create: `tests/llm/test_provider_connections.py`

**Interfaces:**
- Produces:
  - `BillingClass(str, Enum)`
  - `ConnectionStatus(str, Enum)`
  - `ProviderConnection`
  - `ProviderConnectionRegistry.register(connection) -> ProviderConnection`
  - `ProviderConnectionRegistry.get(connection_id) -> ProviderConnection | None`
  - `ProviderConnectionRegistry.list(provider_id=None) -> tuple[ProviderConnection, ...]`
  - `ProviderConnectionRegistry.update_status(connection_id, status, *, validated_at=None) -> ProviderConnection`

- [ ] **Step 1: Write the failing identity/secret-safety tests**

```python
from datetime import datetime, timezone

import pytest

from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
    ProviderConnectionRegistry,
)


def test_connection_keeps_credential_reference_not_secret() -> None:
    connection = ProviderConnection(
        connection_id="qwen-token-plan:main",
        provider_id="qwen-token-plan",
        display_name="Qwen Token Plan",
        billing_class=BillingClass.SUBSCRIPTION,
        credential_ref="keychain://cmm/providers/qwen-token-plan/main",
        endpoint="https://example.invalid/v1",
        isolation_profile_ref=None,
        status=ConnectionStatus.CONNECTED,
    )

    assert connection.credential_ref.startswith("keychain://")
    assert not hasattr(connection, "api_key")
    assert not hasattr(connection, "secret")


def test_registry_rejects_duplicate_connection_id() -> None:
    registry = ProviderConnectionRegistry()
    connection = ProviderConnection(
        connection_id="deepseek:main",
        provider_id="deepseek",
        display_name="DeepSeek",
        billing_class=BillingClass.PAYG,
        credential_ref="keychain://cmm/providers/deepseek/main",
        endpoint="https://api.deepseek.com",
        isolation_profile_ref=None,
        status=ConnectionStatus.CONNECTED,
    )
    registry.register(connection)

    with pytest.raises(ValueError, match="duplicate connection_id"):
        registry.register(connection)
```

- [ ] **Step 2: Run tests and verify RED**

```bash
.venv/bin/python -m pytest -q tests/llm/test_provider_connections.py
```

Expected: import failure because `provider_connections.py` does not exist.

- [ ] **Step 3: Implement the minimal connection domain**

```python
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum


class BillingClass(str, Enum):
    SUBSCRIPTION = "subscription"
    PAYG = "payg"
    API = "api"
    FREE_OR_API = "free_or_api"


class ConnectionStatus(str, Enum):
    DETECTED = "detected"
    CONNECTED = "connected"
    AUTH_REQUIRED = "auth_required"
    WARNING = "warning"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ProviderConnection:
    connection_id: str
    provider_id: str
    display_name: str
    billing_class: BillingClass
    credential_ref: str | None
    endpoint: str
    isolation_profile_ref: str | None
    status: ConnectionStatus
    created_at: datetime | None = None
    last_validated_at: datetime | None = None


class ProviderConnectionRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ProviderConnection] = {}

    def register(self, connection: ProviderConnection) -> ProviderConnection:
        key = connection.connection_id.strip()
        if not key:
            raise ValueError("connection_id cannot be empty")
        if key in self._items:
            raise ValueError(f"duplicate connection_id: {key}")
        self._items[key] = connection
        return connection

    def get(self, connection_id: str) -> ProviderConnection | None:
        return self._items.get(connection_id)

    def list(self, provider_id: str | None = None) -> tuple[ProviderConnection, ...]:
        values = tuple(self._items.values())
        if provider_id is None:
            return values
        return tuple(v for v in values if v.provider_id == provider_id)

    def update_status(
        self,
        connection_id: str,
        status: ConnectionStatus,
        *,
        validated_at: datetime | None = None,
    ) -> ProviderConnection:
        current = self._items[connection_id]
        updated = replace(
            current,
            status=status,
            last_validated_at=validated_at or current.last_validated_at,
        )
        self._items[connection_id] = updated
        return updated
```

- [ ] **Step 4: Add validation tests**

Add tests that reject empty `provider_id`, empty endpoint, plaintext credential shapes such as values beginning with `sk-`, and verify `credential_ref=None` is allowed for subscription bridges whose isolated profile owns auth.

- [ ] **Step 5: Run GREEN**

```bash
.venv/bin/python -m pytest -q tests/llm/test_provider_connections.py
ruff check kernel/llm/provider_connections.py tests/llm/test_provider_connections.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add kernel/llm/provider_connections.py tests/llm/test_provider_connections.py
git commit -m "feat(llm): add provider connection registry"
```

---

### Task 2: Add provider-specific model routes and canonical grouping

**Files:**
- Create: `kernel/llm/model_routes.py`
- Create: `tests/llm/test_model_routes.py`
- Modify: `kernel/llm/capabilities.py`

**Interfaces:**
- Consumes: `ProviderConnection.connection_id`
- Produces:
  - `CapabilityConfidence`
  - `RouteCapabilityState`
  - `ModelRoute`
  - `ModelRouteCatalog.register(route) -> ModelRoute`
  - `ModelRouteCatalog.mark_seen(route_id, at) -> ModelRoute`
  - `ModelRouteCatalog.mark_unavailable(route_id) -> ModelRoute`
  - `ModelRouteCatalog.routes_for_canonical_model(canonical_model_id) -> tuple[ModelRoute, ...]`

- [ ] **Step 1: Write RED tests for route identity and lifecycle**

```python
from kernel.llm.model_routes import ModelRoute, ModelRouteCatalog


def test_same_model_can_have_multiple_provider_routes() -> None:
    catalog = ModelRouteCatalog()
    catalog.register(
        ModelRoute(
            route_id="qwen-token-plan:qwen3.8-max",
            connection_id="qwen-token-plan:main",
            provider_model_id="qwen3.8-max",
            canonical_model_id="qwen3.8-max",
        )
    )
    catalog.register(
        ModelRoute(
            route_id="qwen-cloud:qwen3.8-max",
            connection_id="qwen-cloud:main",
            provider_model_id="qwen3.8-max",
            canonical_model_id="qwen3.8-max",
        )
    )

    routes = catalog.routes_for_canonical_model("qwen3.8-max")
    assert {route.connection_id for route in routes} == {
        "qwen-token-plan:main",
        "qwen-cloud:main",
    }


def test_missing_route_becomes_unavailable_not_deleted() -> None:
    catalog = ModelRouteCatalog()
    route = catalog.register(
        ModelRoute(
            route_id="kira:glm-5.3-free",
            connection_id="kira:main",
            provider_model_id="glm-5.3-free",
            canonical_model_id="glm-5.3",
        )
    )

    catalog.mark_unavailable(route.route_id)

    assert catalog.get(route.route_id) is not None
    assert catalog.get(route.route_id).available is False
```

- [ ] **Step 2: Run RED**

```bash
.venv/bin/python -m pytest -q tests/llm/test_model_routes.py
```

- [ ] **Step 3: Implement route contracts**

`ModelRoute` must contain exactly:

```python
route_id: str
connection_id: str
provider_model_id: str
canonical_model_id: str
available: bool = True
first_seen_at: datetime | None = None
last_seen_at: datetime | None = None
capabilities: tuple[RouteCapabilityState, ...] = ()
```

`RouteCapabilityState`:

```python
name: str
supported: bool
confidence: CapabilityConfidence
```

`CapabilityConfidence` exact values:

```text
declared
discovered
verified
unknown
```

- [ ] **Step 4: Add capability-filter tests**

Prove that `ModelRouteCatalog.filter_required_capabilities(("tools", "structured_output"))` rejects a route where either capability is absent or `supported=False`, and accepts verified/declared support.

- [ ] **Step 5: Run GREEN**

```bash
.venv/bin/python -m pytest -q tests/llm/test_model_routes.py
ruff check kernel/llm/model_routes.py kernel/llm/capabilities.py tests/llm/test_model_routes.py
```

- [ ] **Step 6: Commit**

```bash
git add kernel/llm/model_routes.py kernel/llm/capabilities.py tests/llm/test_model_routes.py
git commit -m "feat(llm): add provider-specific model routes"
```

---

### Task 3: Preserve existing ProviderRegistry and ModelCatalog behavior

**Files:**
- Modify: `kernel/llm/provider_registry.py`
- Modify: `kernel/llm/model_catalog.py`
- Modify: `tests/llm/test_provider_registry_v2.py`
- Modify: `tests/llm/test_model_catalog_v2.py`

**Interfaces:**
- Existing `ProviderRegistry.register/get/list` and `ModelCatalog.register/get/list` remain valid.
- New connection/route registries remain separate objects at this stage.

- [ ] **Step 1: Add regression tests**

Add explicit tests proving:
- existing `ProviderSpec` duplicate rules are unchanged;
- existing `ModelSpec.provider_id` ownership validation is unchanged;
- registering a `ProviderConnection` does not mutate a `ProviderRegistry`;
- registering a `ModelRoute` does not mutate `ModelCatalog`.

- [ ] **Step 2: Run RED only if compatibility gaps exist**

```bash
.venv/bin/python -m pytest -q \
  tests/llm/test_provider_registry_v2.py \
  tests/llm/test_model_catalog_v2.py \
  tests/llm/test_provider_connections.py \
  tests/llm/test_model_routes.py
```

- [ ] **Step 3: Apply only minimal compatibility changes**

Do not merge connection state into `ProviderSpec`. Do not add credential fields to `ProviderSpec`. Do not make `ModelSpec` route-specific.

- [ ] **Step 4: Run GREEN**

Use the command from Step 2 and require all files pass.

- [ ] **Step 5: Commit**

```bash
git add \
  kernel/llm/provider_registry.py \
  kernel/llm/model_catalog.py \
  tests/llm/test_provider_registry_v2.py \
  tests/llm/test_model_catalog_v2.py
git commit -m "test(llm): preserve registry catalog compatibility"
```

---

### Task 4: Public exports and core validation

**Files:**
- Modify: `kernel/llm/__init__.py`
- Test: all `tests/llm`

**Interfaces:**
- Publicly export:
  - `BillingClass`
  - `ConnectionStatus`
  - `ProviderConnection`
  - `ProviderConnectionRegistry`
  - `CapabilityConfidence`
  - `RouteCapabilityState`
  - `ModelRoute`
  - `ModelRouteCatalog`

- [ ] **Step 1: Add import regression test**

Create or extend `tests/llm/test_imports_v2.py` to import all names from `kernel.llm`.

- [ ] **Step 2: Run focused test**

```bash
.venv/bin/python -m pytest -q tests/llm/test_imports_v2.py
```

- [ ] **Step 3: Export the contracts**

Update `kernel/llm/__init__.py` imports and `__all__`.

- [ ] **Step 4: Run full LLM validation**

```bash
.venv/bin/python -m pytest -q tests/llm
.venv/bin/python -m compileall -q kernel/llm
ruff check kernel/llm tests/llm
git diff --check
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add kernel/llm/__init__.py tests/llm
git commit -m "feat(llm): expose route-aware provider registry contracts"
```

---

## Acceptance Gate

Print only after fresh verification:

```text
CMM_PROVIDER_REGISTRY_CORE=PASS
PROVIDER_CONNECTIONS=PASS
MODEL_ROUTES=PASS
QWEN_TOKEN_PLAN_PAYG_SEPARATION=PASS
NO_SECRET_PERSISTENCE=PASS
NO_LIVE_INFERENCE=PASS
```
