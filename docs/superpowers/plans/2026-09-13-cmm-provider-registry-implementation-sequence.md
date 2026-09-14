# CMM Provider Registry Program — Implementation Sequence

**Approved design:** Hybrid provider discovery, fail-closed, local-first.

The work is intentionally split into four independently reviewable plans:

1. `2026-09-13-cmm-provider-registry-core.md`
   - evolves CMM OS's existing ProviderRegistry/ModelCatalog
   - adds ProviderConnection and ModelRoute identities
   - no providers, credentials, networking, or live calls

2. `2026-09-13-cmm-provider-openai-autodiscovery.md`
   - adds administrative `/models`
   - adds first-wave provider manifests
   - reconciles discovered models into ModelRoutes
   - no inference

3. `2026-09-13-cmm-provider-hybrid-detection-isolation.md`
   - adds candidates/detectors
   - secure credential references / Keychain
   - isolated subscription profiles
   - detect → propose → explicit accept → connect

4. `2026-09-13-cmm-provider-usage-cmmchat-integration.md`
   - exposes provider inventory projections
   - bridges stable route IDs into CMM Usage
   - adds provider/model/usage contracts to CMMChat/Hub/Swift client
   - keeps provider execution out of CMMChat

## Required execution order

```text
Plan 1 Registry Core
       ↓
Plan 2 OpenAI-compatible + autodiscovery
       ↓
Plan 3 Hybrid detection + credentials + isolation
       ↓
Plan 4 CMM Usage + CMMChat projection
```

Plans 1–3 belong canonically to CMM OS because CMM OS is the intelligence/routing plane and already owns ProviderRegistry, ModelCatalog, ProviderFactory and OpenAICompatibleProvider.

Plan 4 crosses repositories deliberately:
- CMM OS: inventory projection
- CMM Routers/CMM Usage: usage enrichment keyed by canonical route IDs
- CMMChat: provider-independent product contract/UI projection

No plan requires modifying CMMChat Router v1.
