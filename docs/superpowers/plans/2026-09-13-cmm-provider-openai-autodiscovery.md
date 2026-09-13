# CMM OpenAI-Compatible Provider Autodiscovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add administrative `/models` discovery and manifest-driven onboarding for the approved first-wave OpenAI-compatible providers without one provider subclass per service.

**Architecture:** Extend the existing `OpenAICompatibleClient` with a non-inference model-list operation, introduce declarative provider manifests, and convert discovered provider model IDs into stable `ModelRoute` records. Runtime model discovery is authoritative; manifests define transport/auth/billing defaults, not a hardcoded model catalog.

**Tech Stack:** Python, existing `kernel.llm.clients.openai_compatible_client`, HTTP client already used by CMM OS, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-09-13-cmm-provider-registry-hybrid-design.md`

## Global Constraints

- No generation request is allowed for model discovery.
- `/models` or provider-equivalent administrative endpoints are authoritative where supported.
- Provider model IDs must be preserved unchanged.
- First-wave manifests: Qwen Token Plan, CommandCode, Qwen Cloud PAYG, DeepSeek, Kira, OpenRouter, OpenCode Zen, NVIDIA NIM.
- Kira base URL is `https://kiraai.vn/api/v1`.
- NVIDIA NIM activation scope is initially Kimi K3 even if discovery returns other models.
- Qwen Token Plan and Qwen Cloud PAYG are separate providers/connections.
- No API key may appear in manifests, logs, fixtures, or Git.
- Missing models become unavailable; they are not deleted.
- No automatic inference or compatibility canary occurs in this plan.

---

## File Structure

- Modify: `kernel/llm/clients/openai_compatible_client.py`
- Create: `kernel/llm/provider_manifests.py`
- Create: `kernel/llm/model_discovery.py`
- Create: `kernel/llm/first_wave_providers.py`
- Modify: `kernel/llm/__init__.py`
- Create: `tests/llm/test_provider_manifests.py`
- Create: `tests/llm/test_model_discovery.py`
- Modify: `tests/llm/test_openai_client.py`
- Create: `tests/llm/test_first_wave_providers.py`

---

### Task 1: Add non-inference `/models` client operation

**Files:**
- Modify: `kernel/llm/clients/openai_compatible_client.py`
- Modify: `tests/llm/test_openai_client.py`

**Interfaces:**
- Produces:
  - `OpenAICompatibleClient.list_models() -> tuple[str, ...]`

- [ ] **Step 1: Add RED transport test**

Use the existing HTTP stubbing pattern in `tests/llm/test_openai_client.py` and return:

```json
{
  "object": "list",
  "data": [
    {"id": "model-a", "object": "model"},
    {"id": "model-b", "object": "model"}
  ]
}
```

Assert:

```python
assert client.list_models() == ("model-a", "model-b")
```

Also assert the request method is `GET` and path ends with `/models`.

- [ ] **Step 2: Add malformed response tests**

Require `ProviderError` when:
- top-level `data` is not a list;
- an item lacks string `id`;
- duplicate IDs are returned.

- [ ] **Step 3: Run RED**

```bash
.venv/bin/python -m pytest -q tests/llm/test_openai_client.py -k list_models
```

- [ ] **Step 4: Implement `list_models()`**

Reuse the client's existing base URL/auth/session configuration. Do not call `generate()`. Preserve order from the provider response and reject duplicates rather than silently collapsing them.

- [ ] **Step 5: Run GREEN**

```bash
.venv/bin/python -m pytest -q tests/llm/test_openai_client.py
ruff check kernel/llm/clients/openai_compatible_client.py tests/llm/test_openai_client.py
```

- [ ] **Step 6: Commit**

```bash
git add kernel/llm/clients/openai_compatible_client.py tests/llm/test_openai_client.py
git commit -m "feat(llm): add administrative model discovery"
```

---

### Task 2: Add declarative provider manifests

**Files:**
- Create: `kernel/llm/provider_manifests.py`
- Create: `tests/llm/test_provider_manifests.py`

**Interfaces:**
- Produces:
  - `ProviderManifest`
  - `ProviderManifestRegistry.register(manifest)`
  - `ProviderManifestRegistry.get(provider_id)`
  - `ProviderManifestRegistry.list()`

`ProviderManifest` fields:

```python
provider_id: str
display_name: str
billing_class: BillingClass
default_base_url: str
auth_scheme: str
models_path: str = "/models"
api_styles: tuple[str, ...] = ("chat_completions",)
activation_allowlist: tuple[str, ...] = ()
```

- [ ] **Step 1: Write validation tests**

Require:
- non-empty provider ID/name;
- HTTPS base URL except explicit localhost/custom-provider development mode;
- `auth_scheme == "bearer"` for first-wave API manifests;
- no field named `api_key`, `token`, or `secret`.

- [ ] **Step 2: Run RED**

```bash
.venv/bin/python -m pytest -q tests/llm/test_provider_manifests.py
```

- [ ] **Step 3: Implement manifest registry**

Use duplicate provider-ID rejection consistent with existing registries.

- [ ] **Step 4: Run GREEN and commit**

```bash
.venv/bin/python -m pytest -q tests/llm/test_provider_manifests.py
git add kernel/llm/provider_manifests.py tests/llm/test_provider_manifests.py
git commit -m "feat(llm): add provider manifests"
```

---

### Task 3: Register approved first-wave manifests

**Files:**
- Create: `kernel/llm/first_wave_providers.py`
- Create: `tests/llm/test_first_wave_providers.py`

**Interfaces:**
- Produces:
  - `register_first_wave_manifests(registry: ProviderManifestRegistry) -> tuple[ProviderManifest, ...]`

Required provider IDs:

```text
qwen-token-plan
commandcode
qwen-cloud
deepseek
kira
openrouter
opencode-zen
nvidia-nim
```

- [ ] **Step 1: Write exact-ID tests**

Assert the returned set equals the eight IDs above and no extra provider appears.

- [ ] **Step 2: Add separation test**

Assert:

```python
qtp.billing_class is BillingClass.SUBSCRIPTION
qwen_cloud.billing_class is BillingClass.PAYG
qtp.provider_id != qwen_cloud.provider_id
```

- [ ] **Step 3: Add Kira/NVIDIA policy tests**

Assert:
- Kira base URL equals `https://kiraai.vn/api/v1`.
- Kira model IDs are not hardcoded into the manifest.
- NVIDIA manifest's `activation_allowlist` contains only the approved Kimi K3 provider model ID configured by the implementation spec/fixture; if the exact provider ID is not yet known from live `/models`, keep the allowlist empty and activation must default to manual approval rather than guessing.

- [ ] **Step 4: Implement first-wave manifests**

Use provider documentation/current approved configuration for base URLs. Do not infer or invent an NVIDIA Kimi model ID; discovery remains authoritative.

- [ ] **Step 5: Run GREEN and commit**

```bash
.venv/bin/python -m pytest -q tests/llm/test_first_wave_providers.py
git add kernel/llm/first_wave_providers.py tests/llm/test_first_wave_providers.py
git commit -m "feat(llm): register first-wave provider manifests"
```

---

### Task 4: Convert discovery results into persistent ModelRoutes

**Files:**
- Create: `kernel/llm/model_discovery.py`
- Create: `tests/llm/test_model_discovery.py`

**Interfaces:**
- Consumes:
  - `ProviderManifest`
  - `ProviderConnection`
  - `OpenAICompatibleClient.list_models()`
  - `ModelRouteCatalog`
- Produces:
  - `ModelDiscoveryResult`
  - `discover_models(connection, manifest, client, catalog, *, seen_at)`

`ModelDiscoveryResult`:

```python
connection_id: str
discovered_route_ids: tuple[str, ...]
new_route_ids: tuple[str, ...]
restored_route_ids: tuple[str, ...]
unavailable_route_ids: tuple[str, ...]
```

- [ ] **Step 1: Write RED lifecycle test**

First discovery: `("model-a", "model-b")` creates two available routes.

Second discovery: `("model-b", "model-c")`:
- keeps `model-b`;
- creates `model-c`;
- marks `model-a` unavailable;
- does not delete `model-a`.

- [ ] **Step 2: Add route-ID stability test**

Exact route ID formula:

```python
route_id = f"{connection.connection_id}:{provider_model_id}"
```

Do not rewrite slashes or punctuation in provider model IDs.

- [ ] **Step 3: Add activation-policy test**

For a manifest with a non-empty `activation_allowlist`, discovered models outside the allowlist remain represented but are marked unavailable/not-activated for routing rather than deleted.

- [ ] **Step 4: Run RED**

```bash
.venv/bin/python -m pytest -q tests/llm/test_model_discovery.py
```

- [ ] **Step 5: Implement minimal discovery reconciliation**

Do not add scheduling/background refresh in this task.

- [ ] **Step 6: Run GREEN and commit**

```bash
.venv/bin/python -m pytest -q tests/llm/test_model_discovery.py
git add kernel/llm/model_discovery.py tests/llm/test_model_discovery.py
git commit -m "feat(llm): reconcile discovered provider models"
```

---

### Task 5: Expose APIs and run regression suite

**Files:**
- Modify: `kernel/llm/__init__.py`
- Test: `tests/llm`

- [ ] **Step 1: Export new manifest/discovery contracts**
- [ ] **Step 2: Run all LLM tests**

```bash
.venv/bin/python -m pytest -q tests/llm
.venv/bin/python -m compileall -q kernel/llm
ruff check kernel/llm tests/llm
git diff --check
```

- [ ] **Step 3: Commit**

```bash
git add kernel/llm/__init__.py
git commit -m "feat(llm): expose provider discovery contracts"
```

---

## Acceptance Gate

```text
OPENAI_COMPATIBLE_MODEL_DISCOVERY=PASS
FIRST_WAVE_MANIFESTS=8
QWEN_TOKEN_PLAN_SEPARATE=PASS
KIRA_DISCOVERY=ADMIN_ONLY
NVIDIA_SCOPE_POLICY=PASS
MODEL_DISAPPEARANCE_HISTORY_PRESERVED=PASS
LIVE_INFERENCE_DURING_DISCOVERY=0
```
