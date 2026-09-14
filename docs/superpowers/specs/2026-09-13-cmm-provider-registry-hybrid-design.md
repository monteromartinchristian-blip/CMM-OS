# CMM Provider Registry — Hybrid Provider Discovery & CMM Usage Integration

**Status:** Design proposal for review  
**Date:** 2026-09-13  
**Scope:** CMMChat, CMM OS, CMM Bots, CMM Usage, CMM Routers  
**Design decision:** Hybrid provider discovery, fail-closed, local-first

## 1. Purpose

CMM Provider Registry is the canonical provider/model inventory for the CMM ecosystem.

It answers:

- Which providers are available?
- Which accounts/connections exist for each provider?
- Which models does each connection currently expose?
- Which transport/API surface does each route support?
- Which capabilities are available on each route?
- What source/billing class does each connection use?

It does **not** own usage forecasting, quota calculations, provider selection policy, or application UI.

Those responsibilities remain separated:

- **Provider Registry:** availability, identities, models, routes, capabilities.
- **CMM Usage:** quota, resets, cost, confidence, forecasting, exhaustion risk.
- **CMM OS / CMMChat / CMM Bots:** routing and user-facing policy.
- **CMM Routers:** compatibility/fallback transport where required.

## 2. Approved provider scope

### Existing subscription bridges

These already exist as proven subscription integrations and should not be reimplemented as generic API providers:

1. ChatGPT Plus via Codex
2. Claude Pro via Claude Code
3. Google AI Pro via Antigravity

Each must use an isolated CMM-managed profile/configuration and must never inherit arbitrary user-global configuration silently.

### New first-wave providers

1. **Qwen Token Plan**
   - Billing class: `subscription`
   - Independent credential/quota namespace
   - Must remain distinct from Qwen Cloud PAYG

2. **CommandCode API**
   - Billing class: `api`
   - OpenAI-compatible route

3. **Qwen Cloud PAYG**
   - Billing class: `payg`
   - Separate API key from Qwen Token Plan
   - Separate CMM Usage account/limits

4. **DeepSeek API**
   - Billing class: `payg`
   - OpenAI-compatible route

5. **Kira AI**
   - Base URL: `https://kiraai.vn/api/v1`
   - Bearer authentication
   - Billing class: `free_or_api`
   - Currently relevant free models include:
     - `qwen3.8-flash-free`
     - `qwen3.8-27b-free`
     - `glm-5.3-flash-free`
     - `glm-5.3-free`
   - These model IDs are not the canonical catalog; runtime discovery remains authoritative.

6. **OpenRouter**
   - Billing class: `api`
   - Multi-provider fallback/coverage surface

7. **OpenCode Zen**
   - Billing class: `free_or_api`
   - Opportunistic/free-model pool

8. **NVIDIA NIM**
   - Billing class: `free_or_api`
   - Initial CMM scope limited to Kimi K3
   - Discovery may see additional NVIDIA models, but CMM activation policy may keep only the explicitly approved route active.

### Explicitly not in first wave

- X/Grok subscription bridge
- Cline free/API
- Vikey
- OrcaRouter
- TokenHarbor
- Cavoti AI
- TokenRouter
- Ollama/local models

These may later be added through the generic OpenAI-compatible connection flow without requiring a new architecture.

## 3. Core design principle: detect ≠ connect

Provider discovery is hybrid.

CMM may automatically detect:

- installed applications
- known configuration directories
- existing authenticated profiles
- environment-variable presence
- Keychain credential presence
- localhost services
- known provider endpoints
- provider `/models` responses

But detection alone never authorizes use.

A detected source becomes a `ProviderCandidate`.

Only after validation and explicit user acceptance does CMM create a durable `ProviderConnection`.

### Required invariant

> External configuration is evidence, not authority.

CMM must never silently inherit arbitrary base URLs, proxy overrides, transport settings, or other mutable provider configuration from third-party profiles.

This specifically prevents incidents such as a global Codex profile redirecting CMM traffic to an unrelated local bridge.

## 4. Main domain objects

### ProviderDefinition

Describes a provider type.

Required fields:

- `id`
- `displayName`
- `providerClass`
- `supportedTransports`
- `billingClasses`
- `discoveryStrategy`
- `credentialStrategy`
- `modelDiscoveryStrategy`
- `defaultEndpoint`
- `safetyPolicy`

Examples:

- `chatgpt-plus`
- `claude-pro`
- `google-ai-pro`
- `qwen-token-plan`
- `qwen-cloud`
- `commandcode`
- `deepseek`
- `kira`
- `openrouter`
- `opencode-zen`
- `nvidia-nim`

### ProviderCandidate

Ephemeral result of passive discovery.

Example:

```json
{
  "providerId": "chatgpt-plus",
  "detected": true,
  "authAvailable": true,
  "externalConfigPresent": true,
  "externalEndpointOverridePresent": true,
  "risk": ["external-endpoint-override"]
}
```

Candidates are not routable.

### ProviderConnection

Durable CMM-owned connection.

Required fields:

- `connectionId`
- `providerId`
- `displayName`
- `billingClass`
- `credentialRef`
- `endpoint`
- `isolationProfileRef`
- `status`
- `createdAt`
- `lastValidatedAt`

Secrets are never stored inline.

### ModelRoute

A route is a model through a specific provider connection.

Example:

```text
canonical model: qwen3.8-max

routes:
- qwen-token-plan / qwen3.8-max
- qwen-cloud / qwen3.8-max
- commandcode / qwen3.8-max
- openrouter / qwen/qwen3.8-max
```

This distinction is mandatory.

CMM Usage, pricing, quotas, reliability, and routing decisions attach to the route/account, not merely to the model name.

### CanonicalModel

Optional normalized model identity used to group equivalent routes.

Canonical identity must never erase provider-specific model IDs.

## 5. Credential architecture

Durable secrets belong in macOS Keychain or the platform-native secret store.

Registry state stores only opaque references, for example:

```text
keychain://cmm/providers/deepseek/default
keychain://cmm/providers/qwen-token-plan/main
```

### Isolation rules

#### ChatGPT Plus / Codex

- Use a CMM-managed `CODEX_HOME`.
- CMM may detect authentication in a user profile.
- CMM must not inherit the user's `config.toml`.
- Imported authentication must be separated from provider configuration.
- Endpoint/base URL overrides require explicit CMM configuration.

#### Claude Pro

- Use a CMM-managed Claude profile/home where technically supported.
- Do not inherit PAYG environment variables.
- Do not mutate the user's normal Claude Code profile during routing.

#### Google AI Pro / Antigravity

- Use a CMM-managed routing profile/configuration.
- PAYG credentials must remain isolated from subscription traffic.

#### API providers

- Store API key in CMM Keychain namespace.
- Provider endpoint is taken from ProviderDefinition or explicitly approved user configuration.
- An externally discovered endpoint does not override the canonical endpoint automatically.

## 6. Detection pipeline

```text
system/apps/config/keychain/env/localhost
                  |
                  v
          ProviderDetector[]
                  |
                  v
          ProviderCandidate
                  |
                  v
      administrative validation
                  |
                  v
        ConnectionProposal
                  |
             user accepts
                  |
                  v
           CredentialStore
          + ProviderRegistry
                  |
                  v
           ModelDiscovery
                  |
                  v
              CMM Usage
```

### Detector constraints

A detector:

- may read metadata required for discovery
- may check whether a credential exists
- may call non-inference administrative endpoints
- may call `/models`
- may check login/auth status
- must not generate model output
- must not spend subscription quota
- must not spend PAYG credit
- must not write external configuration
- must redact secret values from logs

If a provider requires inference to verify compatibility, the connection remains `unverified` until a user-authorized canary occurs.

## 7. Model autodiscovery

Autodiscovery is the default and authoritative model catalog mechanism.

Discovery occurs:

1. immediately after a provider connection is accepted
2. at application startup when cache is stale
3. periodically in the background according to provider-specific TTL
4. after credential/account changes
5. on explicit refresh

### Model lifecycle

New model:

```text
status = available
firstSeenAt = now
lastSeenAt = now
```

Existing model seen again:

```text
status = available
lastSeenAt = now
```

Missing model:

```text
status = unavailable
lastSeenAt = previous timestamp
```

Missing models are not immediately deleted.

Historical identity must be preserved for CMM Usage and prior conversations.

### Discovery safety

`GET /models` or equivalent administrative discovery is preferred.

No inference request may be made merely to populate the catalog.

## 8. Capability model

Capabilities attach to `ModelRoute`.

Initial normalized capability vocabulary:

- `chat`
- `responses`
- `streaming`
- `tools`
- `structured_output`
- `vision`
- `reasoning`

Capability confidence should also be tracked:

- `declared`
- `discovered`
- `verified`
- `unknown`

A provider/model name alone is not sufficient proof of capability.

Bots and automation policies must be able to require capabilities before cost/quota routing is considered.

Example:

```text
task requires:
- tools
- structured_output

eligible routes =
all available ModelRoutes where both capabilities are verified/accepted
```

## 9. Generic OpenAI-compatible adapter

The generic adapter is the main scaling mechanism.

First-wave users:

- CommandCode
- Qwen Token Plan
- Qwen Cloud PAYG
- DeepSeek
- Kira AI
- OpenRouter
- OpenCode Zen
- NVIDIA NIM

Provider-specific manifests supply:

- base URL
- auth header format
- `/models` location
- supported wire APIs
- billing class
- provider-specific metadata

The adapter owns shared behavior:

- authorization
- Chat Completions transport
- Responses transport where supported
- streaming
- error normalization
- usage extraction
- model discovery
- capability normalization
- timeouts
- retry policy hooks

Provider-specific code is allowed only where protocol behavior truly differs.

## 10. Generic custom provider

CMMChat must support adding a future OpenAI-compatible provider without a software release.

Minimum UI:

```text
Name
Base URL
API key
```

Optional advanced fields may be inferred or shown only when necessary.

Connection flow:

1. validate URL
2. store credential securely
3. call `/models`
4. detect supported administrative/protocol surfaces without inference where possible
5. create ProviderConnection
6. import discovered ModelRoutes
7. mark unverified capabilities conservatively

This is the escape hatch for future providers such as Vikey, OrcaRouter, TokenHarbor, or another gateway not yet known to CMM.

## 11. CMM Usage integration

Provider Registry emits only provider/model inventory and validation events. CMM Usage consumes those events and joins them with runtime usage telemetry and provider-specific quota/price adapters.

Registry event vocabulary:

- `provider.detected`
- `provider.connected`
- `provider.disconnected`
- `provider.validation_changed`
- `model.discovered`
- `model.available`
- `model.unavailable`
- `model.capabilities_changed`

CMM Usage owns and emits usage-domain events such as:

- `usage.recorded`
- `quota.updated`
- `reset.detected`
- `price.updated`

The Registry must not synthesize or persist quota, cost, reset, or forecasting state merely to make these events available.

### Responsibility boundary

Provider Registry owns:

- connection identity
- model identity
- route identity
- provider availability
- discovered capabilities

CMM Usage owns:

- quota windows
- remaining quota
- shared vs model-specific limits
- reset timing
- confidence
- usage history
- PAYG cost
- free-route status where measurable
- exhaustion prediction
- alerts
- forecasting

CMM Usage must not independently maintain a second provider/model catalog.

## 12. Routing consumers

### CMMChat personal chat

Default policy favors quality and already-paid subscriptions.

Example preference family:

```text
ChatGPT Plus
Claude Pro
Google AI Pro
Qwen Token Plan
then API/free alternatives according to policy
```

This is policy, not a hardcoded Registry rule.

### CMM Bots

Bots may optimize for:

- required capabilities
- reliability
- remaining subscription quota
- free-route availability
- latency
- cost

### Automations

Automations should prefer predictable API/local administrative surfaces over fragile consumer-session bridges when unattended operation matters.

Routing must be able to reject a route if:

- quota state is exhausted
- required capabilities are absent
- provider is unhealthy
- cost policy forbids it
- connection validation has expired or failed

## 13. Subscription vs PAYG separation

Qwen is the canonical example.

These are distinct ProviderConnections:

```text
qwen-token-plan
billing = subscription
credential namespace = qwen-token-plan
usage namespace = qwen-token-plan
```

```text
qwen-cloud
billing = payg
credential namespace = qwen-cloud
usage namespace = qwen-cloud
```

They may expose identical models but never share quota/account state unless the provider explicitly proves that they do.

The same principle applies to every provider with multiple billing/account surfaces.

## 14. Fail-closed rules

1. No automatic inference during discovery.
2. No silent PAYG fallback from subscription routes.
3. No cross-provider fallback unless routing policy explicitly allows it.
4. No use of a detected credential until connection acceptance.
5. No secret values in Registry persistence or logs.
6. No inheritance of arbitrary third-party base URL overrides.
7. No deletion of historical model routes solely because `/models` temporarily omits them.
8. Unknown capability means unavailable for capability-required automation.
9. Provider validation failure disables routing through that connection until recovered.
10. Discovery failures must not prevent already-validated unrelated providers from operating.

## 15. UI behavior

### Providers

CMMChat should surface:

- detected but not connected
- connected
- authentication required
- validation warning
- unavailable
- quota exhausted where supplied by CMM Usage

### Models

A model may show several source routes:

```text
Qwen 3.8 Max

Qwen Token Plan     subscription   74% remaining
Qwen Cloud          PAYG           €...
CommandCode         API            available
OpenRouter          API            available
```

The user may choose:

- exact provider route
- canonical model with automatic route selection
- policy/profile

### Discovery notifications

Avoid noisy notifications for every model change.

Prefer a compact event such as:

> Kira updated: 2 models added, 1 unavailable.

## 16. Persistence

Registry persistence must be local-first.

Persist:

- ProviderDefinitions/manifests
- accepted ProviderConnections
- credential references
- model routes
- capability metadata
- discovery timestamps
- connection validation state

Do not persist:

- API keys
- OAuth access tokens in plaintext
- raw model completions
- external config files wholesale

CMM Usage owns its own usage/quota history keyed by Registry route/account IDs.

## 17. Testing strategy

### Deterministic

- provider manifest validation
- detector parsing
- credential-reference handling
- no-secret persistence
- `/models` normalization
- route identity stability
- model disappearance/reappearance
- capability normalization
- Qwen Token Plan vs PAYG separation
- fail-closed contaminated-config detection
- no inference during discovery
- CMM Usage event contract
- custom OpenAI-compatible provider onboarding

### Live canaries

Live provider canaries require explicit authorization when quota or money can be consumed.

Administrative probes that provably do not generate inference may run without generation authorization.

Each live canary must:

- use exactly one provider/route
- disable unrelated providers
- disable automatic retries unless explicitly approved
- verify exact returned route/model where possible
- avoid raw completion logging
- record evidence hashes

## 18. Initial implementation boundaries

The first implementation should deliver:

1. Registry domain model
2. secure credential references
3. generic OpenAI-compatible adapter
4. model autodiscovery
5. provider manifests for the approved first wave
6. detectors for the three existing subscription bridges plus Qwen Token Plan
7. custom OpenAI-compatible provider flow
8. normalized event contract consumed by CMM Usage
9. route-level capability state
10. fail-closed isolation tests

Not required in the first implementation:

- sophisticated automatic routing optimization
- UI polish
- automatic price scraping for every provider
- Grok/X subscription bridge
- local Ollama support
- every secondary gateway
- inference-based benchmarking

## 19. Success criteria

The design is successful when:

1. CMMChat can discover and connect approved providers without one-off adapter code for each OpenAI-compatible API.
2. New models appear through autodiscovery without a CMMChat release.
3. Removed models become unavailable without losing historical usage.
4. Qwen Token Plan and Qwen Cloud PAYG remain completely separate accounts/routes.
5. CMM Usage receives one canonical provider/model/route inventory rather than maintaining a duplicate catalog.
6. CMM never silently uses an external provider override such as a contaminated Codex base URL.
7. No model inference occurs during provider/model discovery.
8. A future OpenAI-compatible provider can be added from CMMChat using name + base URL + credential.
9. CMM Bots and automations can filter routes by required capabilities before considering cost/quota.
10. Credentials never appear in Registry persistence, manifests, logs, or Git-tracked artifacts.

## 20. Canonical architectural decision

CMM Provider Registry uses the **hybrid discovery model**:

> Detect automatically, validate administratively, ask once, then isolate and own the durable connection.

This is the canonical provider-onboarding model for CMMChat and the wider CMM ecosystem.
