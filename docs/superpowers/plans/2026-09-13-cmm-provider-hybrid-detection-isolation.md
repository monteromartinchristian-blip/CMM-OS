# CMM Hybrid Provider Detection, Credentials, and Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved hybrid onboarding rule: detect provider candidates automatically, validate them administratively, require one explicit acceptance, then create an isolated CMM-owned durable connection without inheriting mutable third-party configuration.

**Architecture:** Provider detectors return non-routable `ProviderCandidate` records. Acceptance copies/imports only the minimum credential material into a CMM-owned secret/profile namespace and creates `ProviderConnection`; external configs remain read-only evidence. Subscription bridges use isolated profiles, while API providers store credentials through an abstract secret store with a macOS Keychain backend.

**Tech Stack:** Python, macOS `security` CLI backend behind an interface, subprocess, pytest, existing CMM OS LLM registry.

**Spec:** `docs/superpowers/specs/2026-09-13-cmm-provider-registry-hybrid-design.md`

## Global Constraints

- Detect does not mean connect.
- Candidate records are never routable.
- Detectors may check credential presence but must not expose secret values.
- No detector may generate model output or spend model quota.
- External endpoint/base URL overrides are never trusted automatically.
- ChatGPT/Codex must use CMM-managed `CODEX_HOME` and must not import `config.toml`.
- Claude and Antigravity subscription traffic must remain isolated from PAYG credentials.
- API keys must live in Keychain/platform secret storage, never Registry persistence.
- A failed detector must not break unrelated providers.
- No automatic live inference canary.

---

## File Structure

- Create: `kernel/llm/provider_candidates.py`
- Create: `kernel/llm/provider_detectors.py`
- Create: `kernel/llm/credential_store.py`
- Create: `kernel/llm/subscription_profiles.py`
- Create: `kernel/llm/provider_onboarding.py`
- Create: `tests/llm/test_provider_candidates.py`
- Create: `tests/llm/test_provider_detectors.py`
- Create: `tests/llm/test_credential_store.py`
- Create: `tests/llm/test_subscription_profiles.py`
- Create: `tests/llm/test_provider_onboarding.py`
- Modify: `kernel/llm/__init__.py`

---

### Task 1: Candidate domain and detector contract

**Files:**
- Create: `kernel/llm/provider_candidates.py`
- Create: `kernel/llm/provider_detectors.py`
- Create: `tests/llm/test_provider_candidates.py`
- Create: `tests/llm/test_provider_detectors.py`

**Interfaces:**
- Produces:
  - `CandidateRisk`
  - `ProviderCandidate`
  - `ProviderDetector` protocol
  - `detect_all(detectors) -> tuple[ProviderCandidate, ...]`

`ProviderCandidate` exact fields:

```python
provider_id: str
source: str
detected: bool
auth_available: bool
external_config_present: bool
external_endpoint_override_present: bool
risks: tuple[CandidateRisk, ...]
metadata: tuple[tuple[str, str], ...] = ()
```

- [ ] **Step 1: Write tests proving candidates are non-routable**

Assert `ProviderCandidate` has no `credential_ref`, no `connection_id`, and no execution methods.

- [ ] **Step 2: Write detector isolation test**

Create one detector that raises and a second that returns a valid candidate. `detect_all()` must return the valid candidate plus a structured failure result/log hook without raising the first detector's exception to the caller.

- [ ] **Step 3: Implement and run**

```bash
.venv/bin/python -m pytest -q \
  tests/llm/test_provider_candidates.py \
  tests/llm/test_provider_detectors.py
```

- [ ] **Step 4: Commit**

```bash
git add \
  kernel/llm/provider_candidates.py \
  kernel/llm/provider_detectors.py \
  tests/llm/test_provider_candidates.py \
  tests/llm/test_provider_detectors.py
git commit -m "feat(llm): add hybrid provider candidates"
```

---

### Task 2: Secret-store abstraction and macOS Keychain backend

**Files:**
- Create: `kernel/llm/credential_store.py`
- Create: `tests/llm/test_credential_store.py`

**Interfaces:**
- Produces:
  - `CredentialStore` protocol
  - `MacOSKeychainCredentialStore`
  - `credential_ref(provider_id, account) -> str`
  - `put(provider_id, account, secret) -> str`
  - `has(ref) -> bool`
  - `delete(ref) -> None`

- [ ] **Step 1: Write fake-store contract tests**

The test suite must use an in-memory fake for normal tests. Prove Registry objects receive only refs like:

```text
keychain://cmm/providers/deepseek/main
```

- [ ] **Step 2: Add Keychain command-construction tests**

Mock `subprocess.run`; verify:
- `security add-generic-password` receives secret via stdin/input, not command-line argument;
- `security find-generic-password` is used only by the credential store;
- no command string is logged with the secret.

- [ ] **Step 3: Implement backend**

Use a stable Keychain service namespace such as `CMM Provider Registry` and derive account names from provider/account IDs. The returned Registry ref remains provider-oriented and does not expose Keychain internals.

- [ ] **Step 4: Run GREEN and commit**

```bash
.venv/bin/python -m pytest -q tests/llm/test_credential_store.py
ruff check kernel/llm/credential_store.py tests/llm/test_credential_store.py
git add kernel/llm/credential_store.py tests/llm/test_credential_store.py
git commit -m "feat(llm): add secure provider credential store"
```

---

### Task 3: Isolated subscription profile builders

**Files:**
- Create: `kernel/llm/subscription_profiles.py`
- Create: `tests/llm/test_subscription_profiles.py`

**Interfaces:**
- Produces:
  - `SubscriptionProfileManager`
  - `create_codex_profile(source_home, target_home) -> Path`
  - equivalent profile descriptor methods for Claude/Antigravity where the current adapter supports profile scoping.

- [ ] **Step 1: Write Codex contamination regression test**

Fixture source:

```text
source/
  auth.json
  config.toml  # contains openai_base_url = "http://127.0.0.1:17841/v1"
```

Expected target:

```text
target/
  auth.json
```

Assert:
- `auth.json` copied with restrictive permissions;
- `config.toml` absent;
- target files contain no `17841`;
- source remains unchanged.

- [ ] **Step 2: Write no-auth failure test**

If source has no transferable auth material, return a structured `auth_required` result rather than copying arbitrary config.

- [ ] **Step 3: Implement Codex profile builder**

Do not infer other Codex state files as required; only copy artifacts explicitly proven necessary by the current Codex authentication contract.

- [ ] **Step 4: Add Claude/Antigravity descriptor tests**

At minimum prove their CMM profile descriptors carry an isolated home/path and an explicit list of environment names to strip for PAYG isolation.

- [ ] **Step 5: Run GREEN and commit**

```bash
.venv/bin/python -m pytest -q tests/llm/test_subscription_profiles.py
git add kernel/llm/subscription_profiles.py tests/llm/test_subscription_profiles.py
git commit -m "feat(llm): isolate subscription provider profiles"
```

---

### Task 4: Implement detectors for approved provider classes

**Files:**
- Modify: `kernel/llm/provider_detectors.py`
- Modify: `tests/llm/test_provider_detectors.py`

**Interfaces:**
- Detectors:
  - `CodexDetector`
  - `ClaudeCodeDetector`
  - `AntigravityDetector`
  - `QwenTokenPlanDetector`
  - `EnvironmentApiCredentialDetector` configured for CommandCode, Qwen Cloud, DeepSeek, Kira, OpenRouter, OpenCode Zen, NVIDIA NIM.

- [ ] **Step 1: Add Codex override-risk test**

Given a readable `~/.codex/config.toml` containing a noncanonical base URL, detector must set:

```python
external_config_present is True
external_endpoint_override_present is True
CandidateRisk.EXTERNAL_ENDPOINT_OVERRIDE in risks
```

The detector must not return the URL value in candidate metadata.

- [ ] **Step 2: Add environment-key presence tests**

Provide fake environment mappings. Candidate may expose `auth_available=True` but must never include the env value.

- [ ] **Step 3: Implement detectors**

All filesystem/environment inputs must be injectable for deterministic tests.

- [ ] **Step 4: Run GREEN and commit**

```bash
.venv/bin/python -m pytest -q tests/llm/test_provider_detectors.py
git add kernel/llm/provider_detectors.py tests/llm/test_provider_detectors.py
git commit -m "feat(llm): detect approved provider candidates"
```

---

### Task 5: Acceptance/onboarding creates CMM-owned connections

**Files:**
- Create: `kernel/llm/provider_onboarding.py`
- Create: `tests/llm/test_provider_onboarding.py`

**Interfaces:**
- Produces:
  - `ConnectionProposal`
  - `ProviderOnboardingService.propose(candidate) -> ConnectionProposal`
  - `ProviderOnboardingService.accept(proposal, credential=None) -> ProviderConnection`

- [ ] **Step 1: Write API-provider onboarding test**

Given a DeepSeek candidate + user-supplied secret:
- secret is stored via `CredentialStore`;
- connection stores only `credential_ref`;
- endpoint comes from the canonical manifest, not candidate metadata.

- [ ] **Step 2: Write contaminated Codex onboarding test**

Given candidate with external override:
- accepted connection uses a CMM-owned isolation profile;
- external `config.toml` is not copied;
- connection endpoint/config does not inherit port 17841.

- [ ] **Step 3: Write explicit acceptance test**

`propose()` alone must not register a connection. Only `accept()` mutates `ProviderConnectionRegistry`.

- [ ] **Step 4: Implement service**

No provider connection becomes `CONNECTED` until administrative auth validation succeeds. Otherwise use `AUTH_REQUIRED` or `WARNING`.

- [ ] **Step 5: Run GREEN and commit**

```bash
.venv/bin/python -m pytest -q tests/llm/test_provider_onboarding.py
git add kernel/llm/provider_onboarding.py tests/llm/test_provider_onboarding.py
git commit -m "feat(llm): add hybrid provider onboarding"
```

---

### Task 6: Public exports and no-inference audit

**Files:**
- Modify: `kernel/llm/__init__.py`
- Test: `tests/llm`

- [ ] **Step 1: Export candidate/detector/onboarding/credential contracts**
- [ ] **Step 2: Search production discovery paths for calls to `generate(`**

```bash
grep -Rni 'generate(' \
  kernel/llm/provider_candidates.py \
  kernel/llm/provider_detectors.py \
  kernel/llm/provider_onboarding.py \
  kernel/llm/model_discovery.py || true
```

Expected: no model-generation call in discovery/onboarding administrative paths.

- [ ] **Step 3: Run LLM suite**

```bash
.venv/bin/python -m pytest -q tests/llm
ruff check kernel/llm tests/llm
git diff --check
```

- [ ] **Step 4: Commit**

```bash
git add kernel/llm/__init__.py
git commit -m "feat(llm): expose hybrid provider onboarding"
```

---

## Acceptance Gate

```text
HYBRID_PROVIDER_DISCOVERY=PASS
DETECT_NOT_CONNECT=PASS
CODEX_EXTERNAL_CONFIG_INHERITANCE=NONE
CODEX_17841_REGRESSION=PASS
KEYCHAIN_SECRET_PERSISTENCE=PASS
REGISTRY_PLAINTEXT_SECRETS=NONE
DISCOVERY_MODEL_GENERATIONS=0
```
