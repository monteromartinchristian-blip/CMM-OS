# CMM Provider Registry → CMM Usage → CMMChat Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the canonical provider/connection/model-route inventory from CMM OS to CMM Usage and CMMChat without duplicating provider catalogs or leaking provider internals into the UI.

**Architecture:** CMM OS remains the intelligence/routing owner. CMM Usage consumes stable route/account IDs and enriches them with quota/cost/reset/forecasting. CMMChat consumes provider/model/usage projections through its existing contract/Hub boundary; SwiftUI never talks directly to Codex, Claude, Antigravity, or third-party APIs.

**Tech Stack:** CMM OS Python contracts, CMM Usage TypeScript adapter/event model, CMMChat OpenAPI 3.1 + FastAPI Hub + Swift/SwiftUI.

**Spec:** `docs/superpowers/specs/2026-09-13-cmm-provider-registry-hybrid-design.md`

## Global Constraints

- Provider Registry owns provider/connection/model-route inventory.
- CMM Usage owns quotas, resets, costs, confidence, forecasting, exhaustion, alerts.
- CMM Usage must not maintain a second provider/model catalog.
- CMMChat remains provider-independent and consumes stable contracts.
- CMM Hub may cache/project state but must not become the routing authority.
- Qwen Token Plan and Qwen Cloud PAYG remain separate accounts even for identical models.
- Historical route IDs must remain stable.
- No secrets or third-party profile paths are exposed through CMMChat contracts.
- No inference is required to render provider/model/usage state.

---

## File Structure

### CMM OS
- Create: `kernel/llm/provider_events.py`
- Create: `tests/llm/test_provider_events.py`
- Modify: `kernel/llm/__init__.py`

### CMM Usage / CMM Routers
- Create or adapt: `src/usage/providers/registry-bridge.ts`
- Create: `tests/usage/providers/registry-bridge.test.ts`
- Modify only if required: existing CMM Usage account/quota normalization types.

### CMMChat
- Modify: `contracts/openapi/cmmchat-v1.yaml`
- Modify: `tests/contracts/test_openapi.py`
- Create: `services/hub/src/cmm_hub/api/providers.py`
- Modify: `services/hub/src/cmm_hub/main.py`
- Extend: `services/hub/src/cmm_hub/schemas.py`
- Create: `services/hub/tests/test_providers.py`
- Create: `apps/apple/CMMChat/Models/ProviderSummary.swift`
- Create: `apps/apple/CMMChat/Models/ModelRouteSummary.swift`
- Create: `apps/apple/CMMChat/Models/UsageSummary.swift`
- Modify: `apps/apple/CMMChat/Networking/HubClient.swift`
- Modify: `apps/apple/CMMChat/Networking/HTTPHubClient.swift`
- Create: `apps/apple/CMMChat/Stores/ProviderStore.swift`
- Create: `apps/apple/CMMChatTests/ProviderStoreTests.swift`

---

### Task 1: Define provider inventory event/projection contract in CMM OS

**Files:**
- Create: `kernel/llm/provider_events.py`
- Create: `tests/llm/test_provider_events.py`
- Modify: `kernel/llm/__init__.py`

**Interfaces:**
- Produces:
  - `ProviderInventorySnapshot`
  - `ProviderConnectionSnapshot`
  - `ModelRouteSnapshot`
  - event names:
    - `provider.detected`
    - `provider.connected`
    - `provider.disconnected`
    - `provider.validation_changed`
    - `model.discovered`
    - `model.available`
    - `model.unavailable`
    - `model.capabilities_changed`

- [ ] **Step 1: Write snapshot serialization tests**

Assert snapshots include:
- provider/connection/route IDs;
- display names;
- billing class;
- availability/status;
- normalized capabilities;
- timestamps.

Assert snapshots exclude:
- `credential_ref`;
- API keys;
- isolation profile filesystem paths;
- raw external config metadata.

- [ ] **Step 2: Run RED**

```bash
.venv/bin/python -m pytest -q tests/llm/test_provider_events.py
```

- [ ] **Step 3: Implement immutable projection types**

Use primitive serializable values suitable for a stable protocol boundary.

- [ ] **Step 4: Run GREEN and commit**

```bash
.venv/bin/python -m pytest -q tests/llm/test_provider_events.py
git add kernel/llm/provider_events.py kernel/llm/__init__.py tests/llm/test_provider_events.py
git commit -m "feat(llm): expose provider inventory projections"
```

---

### Task 2: Bridge Registry route IDs into CMM Usage

**Files:**
- Create/adapt: `src/usage/providers/registry-bridge.ts`
- Create: `tests/usage/providers/registry-bridge.test.ts`

**Interfaces:**
- Consumes Registry snapshots.
- Produces CMM Usage account/model-route keys without inventing model inventory.

Required mapping:

```text
connection_id -> usage account identity
route_id      -> usage model route identity
billing_class -> subscription | payg | api | free_or_api
```

- [ ] **Step 1: Write Qwen separation test**

Input:

```text
qwen-token-plan:main + qwen3.8-max
qwen-cloud:main      + qwen3.8-max
```

Assert CMM Usage creates two account scopes and two route scopes even though canonical model ID matches.

- [ ] **Step 2: Write missing-route history test**

When Registry marks a route unavailable, CMM Usage retains historical samples/forecast state and only updates availability.

- [ ] **Step 3: Implement bridge**

The bridge must reject any attempt to create a provider/model identity absent from the Registry snapshot.

- [ ] **Step 4: Run CMM Usage focused tests**

```bash
npm test -- tests/usage/providers/registry-bridge.test.ts
npm run typecheck
```

- [ ] **Step 5: Commit**

```bash
git add src/usage/providers/registry-bridge.ts tests/usage/providers/registry-bridge.test.ts
git commit -m "feat(usage): consume canonical provider registry routes"
```

---

### Task 3: Extend CMMChat's canonical OpenAPI with provider/model/usage projections

**Files:**
- Modify: `contracts/openapi/cmmchat-v1.yaml`
- Modify: `tests/contracts/test_openapi.py`

**Interfaces:**
Add exact endpoints:

```text
GET /v1/providers
GET /v1/models
```

Add schemas:

```text
ProviderSummary
ModelRouteSummary
UsageSummary
CanonicalModelSummary
```

`ProviderSummary` must contain only product-safe fields:

```text
id
display_name
status
billing_class
detected
connected
last_validated_at
usage
```

`ModelRouteSummary`:

```text
route_id
connection_id
provider_id
provider_model_id
canonical_model_id
available
capabilities
usage
```

- [ ] **Step 1: Add contract tests before schema changes**

Require the two paths and schema fields above.

- [ ] **Step 2: Run RED**

```bash
.contract-venv/bin/pytest tests/contracts/test_openapi.py -q
```

- [ ] **Step 3: Update OpenAPI**

No credential refs, profile paths, raw endpoint overrides, or secret metadata may appear.

- [ ] **Step 4: Run GREEN and commit**

```bash
.contract-venv/bin/pytest tests/contracts/test_openapi.py -q
git add contracts/openapi/cmmchat-v1.yaml tests/contracts/test_openapi.py
git commit -m "feat: add provider and model product contracts"
```

---

### Task 4: Add CMM Hub provider projection endpoints

**Files:**
- Create: `services/hub/src/cmm_hub/api/providers.py`
- Modify: `services/hub/src/cmm_hub/main.py`
- Modify: `services/hub/src/cmm_hub/schemas.py`
- Create: `services/hub/tests/test_providers.py`

**Interfaces:**
- Hub consumes a provider-inventory client/projection source.
- Hub does not execute providers.

- [ ] **Step 1: Write endpoint tests**

Using a fake inventory source:
- `/v1/providers` returns provider summaries;
- `/v1/models` groups canonical model plus routes;
- Qwen Token Plan and Qwen Cloud appear separately;
- usage summary is attached by route/account;
- no secret/profile path fields serialize.

- [ ] **Step 2: Implement projection API**

Keep provider source injectable so Hub tests do not require CMM OS running.

- [ ] **Step 3: Run Hub tests**

```bash
cd services/hub
.venv/bin/pytest tests/test_providers.py -q
.venv/bin/ruff check src tests
```

- [ ] **Step 4: Commit**

```bash
git add services/hub
git commit -m "feat(hub): expose provider and model projections"
```

---

### Task 5: Add provider/model state to the native CMMChat client

**Files:**
- Create:
  - `apps/apple/CMMChat/Models/ProviderSummary.swift`
  - `apps/apple/CMMChat/Models/ModelRouteSummary.swift`
  - `apps/apple/CMMChat/Models/UsageSummary.swift`
  - `apps/apple/CMMChat/Stores/ProviderStore.swift`
- Modify:
  - `apps/apple/CMMChat/Networking/HubClient.swift`
  - `apps/apple/CMMChat/Networking/HTTPHubClient.swift`
- Create:
  - `apps/apple/CMMChatTests/ProviderStoreTests.swift`

**Interfaces:**
Extend `HubClient`:

```swift
func listProviders() async throws -> [ProviderSummary]
func listModelRoutes() async throws -> [ModelRouteSummary]
```

`ProviderStore` state:

```text
providers
modelRoutes
isRefreshing
errorMessage
lastRefreshAt
```

- [ ] **Step 1: Write Swift decoding tests against contract fixtures**

Prove:
- subscription/PAYG billing values decode;
- multiple routes for one canonical model decode;
- unavailable route remains present;
- usage may be absent/unknown.

- [ ] **Step 2: Write ProviderStore tests**

Fake `HubClient` and assert refresh atomically replaces provider/model projections without touching `ChatStore`.

- [ ] **Step 3: Implement models/network/store**

Do not add provider-specific Swift code.

- [ ] **Step 4: Run Apple tests**

```bash
cd apps/apple
xcodebuild \
  -project CMMChat.xcodeproj \
  -scheme CMMChat \
  -destination 'platform=macOS' \
  CODE_SIGNING_ALLOWED=NO \
  test
```

- [ ] **Step 5: Commit**

```bash
git add apps/apple
git commit -m "feat(apple): add provider and usage state"
```

---

### Task 6: End-to-end projection validation

**Files:**
- Create: `docs/testing/provider-registry-usage-cmmchat-validation.md`

- [ ] **Step 1: Run CMM OS LLM tests**

```bash
.venv/bin/python -m pytest -q tests/llm
```

- [ ] **Step 2: Run CMM Usage focused + global type/build gates**

Use the repository's canonical CMM Usage test/build commands and record exact counts.

- [ ] **Step 3: Run CMMChat contract, Hub, and Apple tests**

Use the canonical commands from Tasks 3–5.

- [ ] **Step 4: Record acceptance evidence**

Required markers:

```text
REGISTRY_SINGLE_SOURCE_OF_TRUTH=PASS
CMM_USAGE_DUPLICATE_CATALOG=NONE
QWEN_TOKEN_PLAN_PAYG_SEPARATION=PASS
CMMCHAT_PROVIDER_SPECIFIC_LOGIC=NONE
PROVIDER_SECRETS_EXPOSED_TO_CMMCHAT=NONE
PROVIDER_ROUTE_USAGE_PROJECTION=PASS
```

- [ ] **Step 5: Commit validation report**

```bash
git add docs/testing/provider-registry-usage-cmmchat-validation.md
git commit -m "test: validate provider registry usage integration"
```
