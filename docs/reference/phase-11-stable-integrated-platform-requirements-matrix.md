# Phase 11 — Stable Integrated Platform — Requirements Matrix

**Canonical owner:** Phase 11 Stable Integrated Platform
**Status:** active, phase in progress
**Detailed roadmap:** [`docs/roadmap/phase-11-stable-integrated-platform.md`](../roadmap/phase-11-stable-integrated-platform.md)
**Top-level roadmap:** [`ROADMAP.md`](../../ROADMAP.md)
**Phase 10 matrix that owns the inherited `F11-001`…`F11-013` planning rows:** [Domain Intelligence Requirements Matrix](domain-intelligence-requirements-matrix.md)

## 1. Purpose and ownership

This document is the canonical requirements/reference matrix for Phase 11 —
Stable Integrated Platform. It exists because Phase 11 requirement identifiers
were preassigned inside the Phase 10 Domain Intelligence matrix, and that
document is the canonical **Phase 10** matrix — not the appropriate owner for a
Phase 11 platform Design Point (Independent Re-audit V2, `MAJOR-V2-05`).

Ownership rules:

- `docs/reference/domain-intelligence-requirements-matrix.md` **remains the
  canonical Phase 10 Domain Intelligence matrix**. This document neither
  rewrites nor supersedes it.
- Its rows `F11-001` … `F11-013` are inherited/preassigned Phase 11 planning
  requirements. They stay normatively owned by that document: this matrix
  references them and never restates, reinterprets or silently re-statuses
  their text.
- Going forward this document is the canonical Phase 11 owner: new Phase 11
  requirements — starting with `F11-014` — are defined, mapped and traced here.

Table shape, mapping-status vocabulary and row conventions mirror the Phase 10
matrix so the two documents can be read side by side.

## 2. Mapping status vocabulary

The vocabulary is the Phase 10 matrix's own (its §2) and is **not redefined**
here: `VERIFIED_EXISTING`, `REQUIRES_PHASE_INSPECTION`, `NEW_CONTRACT_REQUIRED`,
`IMPLEMENTED_PENDING_INDEPENDENT_AUDIT`,
`IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT`.

`IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT` is read exactly as Phase 10 defines
it: the implementation exists, a recorded independent audit `FAIL` (or re-audit
`FAIL`) exists, findings are remediated, and independent re-audit closure is
still pending. It is not a closure and not a verification claim.

## 3. Inherited / preassigned Phase 11 requirements (`F11-001` … `F11-013`)

These rows are **pointers**. The normative requirement text, its mapping and its
mapping status remain owned by the Phase 10 matrix §5.6
(`docs/reference/domain-intelligence-requirements-matrix.md`); the text is
deliberately not duplicated here so the two documents cannot drift. Only the
normalized source row and the acceptance-test identifier are carried over for
traceability, together with the status **as recorded at inheritance**.

| `requirement_id` | Normative-requirement owner | Primary source row | Acceptance test | Mapping status at inheritance | Phase 11 status |
|---|---|---|---|---|---|
| `F11-001` | Phase 10 matrix §5.6, row `F11-001` | `SRC-R11:R11-C55` | `AT-F11-COM-01` | `REQUIRES_PHASE_INSPECTION` | `INHERITED_UNCHANGED` |
| `F11-002` | Phase 10 matrix §5.6, row `F11-002` | `SRC-DGS:DGS-C07` | `AT-F11-RND-01` | `REQUIRES_PHASE_INSPECTION` | `INHERITED_UNCHANGED` |
| `F11-003` | Phase 10 matrix §5.6, row `F11-003` | `SRC-CRS:CRS-C08` | `AT-F11-CTX-01` | `REQUIRES_PHASE_INSPECTION` | `INHERITED_UNCHANGED` |
| `F11-004` | Phase 10 matrix §5.6, row `F11-004` | `SRC-PF1015:PF-C06` | `AT-F11-CON-01` | `REQUIRES_PHASE_INSPECTION` | `INHERITED_UNCHANGED` |
| `F11-005` | Phase 10 matrix §5.6, row `F11-005` | `SRC-CRS:CRS-C10` | `AT-F11-PII-01` | `VERIFIED_EXISTING` | `INHERITED_UNCHANGED` |
| `F11-006` | Phase 10 matrix §5.6, row `F11-006` | `SRC-DGS:DGS-C11` | `AT-F11-ART-01` | `NEW_CONTRACT_REQUIRED` | `INHERITED_UNCHANGED` |
| `F11-007` | Phase 10 matrix §5.6, row `F11-007` | `SRC-R11:R11-CMG` | `AT-F11-MG-01` | `REQUIRES_PHASE_INSPECTION` | `INHERITED_UNCHANGED` |
| `F11-008` | Phase 10 matrix §5.6, row `F11-008` | `SRC-R11:R11-C59` | `AT-F11-BOT-01` | `NEW_CONTRACT_REQUIRED` | `INHERITED_UNCHANGED` |
| `F11-009` | Phase 10 matrix §5.6, row `F11-009` | `SRC-R11:R11-C60` | `AT-F11-CAP-01` | `NEW_CONTRACT_REQUIRED` | `INHERITED_UNCHANGED` |
| `F11-010` | Phase 10 matrix §5.6, row `F11-010` | `SRC-R11:R11-C60` | `AT-F11-TOOL-01` | `REQUIRES_PHASE_INSPECTION` | `INHERITED_UNCHANGED` |
| `F11-011` | Phase 10 matrix §5.6, row `F11-011` | `SRC-R11:R11-C61` | `AT-F11-WEB-01` | `NEW_CONTRACT_REQUIRED` | `INHERITED_UNCHANGED` |
| `F11-012` | Phase 10 matrix §5.6, row `F11-012` | `SRC-R11:R11-C61` | `AT-F11-CU-01` | `NEW_CONTRACT_REQUIRED` | `INHERITED_UNCHANGED` |
| `F11-013` | Phase 10 matrix §5.6, row `F11-013` | `SRC-R11:R11-C59` | `AT-F11-BOT-PORT-01` | `NEW_CONTRACT_REQUIRED` | `INHERITED_UNCHANGED` |

`INHERITED_UNCHANGED` means: inherited as a planning input, with no status
change and no verification claim added by this document. A status recorded
above is the Phase 10 matrix's value at inheritance; the Phase 10 row stays the
authority for it. No Phase 11 subphase has been executed for `F11-001` …
`F11-013`; Phase 11.34 is the only Phase 11 subphase with an implementation so
far, and it introduces the next non-colliding requirement below.

## 4. Phase 11 requirements defined here

### 4.1 `F11-014` — Canonical, persistent, auditable and fail-closed Provider Registry

| `requirement_id` | Normative requirement | Primary source | Responsible phase | Repository mapping | Mapping status | Acceptance test |
|---|---|---|---|---|---|---|
| `F11-014` | Maintain one canonical, persistent, auditable and fail-closed Provider Registry in which provider identity is authoritative through `ProviderRegistry`, manifests/connections/models/routes are referentially coherent, subscription isolation policy is explicit, onboarding side effects are ownership-safe, discovery remains non-inference, and `DP-134` is verified through `AT-DP-134`. | `SRC-R11` (detailed Phase 11 roadmap §11.34); `docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v2-design.md` §10 | Phase 11 | `kernel/llm/provider_registry.py`; `kernel/llm/provider_manifests.py`; `kernel/llm/provider_connections.py`; `kernel/llm/model_routes.py`; `kernel/llm/model_discovery.py`; `kernel/llm/provider_onboarding.py`; `kernel/llm/provider_state.py`; `kernel/llm/provider_state_repository.py`; `kernel/llm/provider_state_coordinator.py` | `VERIFIED_EXISTING` | `AT-DP-134` — `tests/llm/test_provider_registry_dp134_acceptance.py` |

The row is non-colliding: `F11-001` … `F11-013` stay owned by the Phase 10
matrix, and `F11-014` is the next Phase 11 functional identifier
(Remediation V2 spec §8.3).

### 4.2 `F11-014` traceability

| Trace element | Canonical value |
|---|---|
| Requirement | `F11-014` |
| Phase | Phase 11 — Stable Integrated Platform |
| Subphase | 11.34 — Provider Registry |
| Design Point | `DP-134` — Canonical, Persistent and Fail-Closed Provider Registry |
| Connected acceptance | `AT-DP-134` — `tests/llm/test_provider_registry_dp134_acceptance.py` |
| Production owner — provider identity authority | `kernel/llm/provider_registry.py` (`ProviderRegistry`) |
| Production owner — provider-bound metadata | `kernel/llm/provider_manifests.py` (`ProviderManifest`, `ProviderManifestRegistry`) |
| Production owner — accepted connections | `kernel/llm/provider_connections.py` (`ProviderConnection`, `ProviderConnectionRegistry`) |
| Production owner — provider-specific routes | `kernel/llm/model_routes.py` (`ModelRoute`, `ModelRouteCatalog`) |
| Production owner — administrative discovery | `kernel/llm/model_discovery.py` (`discover_models`) |
| Onboarding owner | `kernel/llm/provider_onboarding.py` (`ProviderOnboardingService`) |
| Persistence owner | `kernel/llm/provider_state_repository.py` (`ProviderRegistryStateRepository`, `capture_provider_registry_state`, `restore_provider_registry_state`) over the versioned contracts in `kernel/llm/provider_state.py` (`SCHEMA_VERSION="2"`, `ProviderRegistryAuditRecord`) |
| Commit seam | `kernel/llm/provider_state_coordinator.py` (`ProviderRegistryStateCoordinator`) — the one revision/audit commit path for connection acceptance, route discovery lifecycle and validation transitions |
| Historical Audit V1 | `docs/audits/phase-11.34-provider-registry-independent-audit-v1.md` — independent verdict `FAIL` |
| Historical Re-audit V2 | `docs/audits/phase-11.34-provider-registry-independent-reaudit-v2.md` — independent verdict `FAIL`; `BLOCKERS=0`; `MAJORS=5`; `MINORS=0`; `MAJOR-V2-01`…`MAJOR-V2-05`; audited HEAD `1c54a720c57c6a84d990e8eb8dfc502c7423599e`; bundle SHA-256 `9f186aa51abc2533cfe171363cd760b8b6f7ff618223dc7c1358120e0499fdd4` |
| Historical Re-audit V3 | `docs/audits/phase-11.34-provider-registry-independent-reaudit-v3.md` — independent verdict `FAIL`; `BLOCKERS=0`; `MAJORS=2`; `MINORS=1`; `MAJOR-V3-01`; `MAJOR-V3-02`; `MINOR-V3-01`; audited HEAD `b0ff1169d022ba821f3a9e777497175bf003f47a`; bundle SHA-256 `37eb5579d19d499b55c73f5eda16afe6052af2832ff58c86f9df4116e7e8c679` |
| Historical Re-audit V4 | `docs/audits/phase-11.34-provider-registry-independent-reaudit-v4.md` — independent verdict `FAIL`; `BLOCKERS=0`; `MAJORS=3`; `MINORS=1`; `MAJOR-V4-01`; `MAJOR-V4-02`; `MAJOR-V4-03`; `MINOR-V4-01`; audited HEAD `46ef38ae477c801975b55b92c5f31f9137a3bc12`; audited tree `4f24aed198e86d702791bef46d71df7d281a767d`; bundle SHA-256 `d8a21eac304d56789ee54b08bc6e96fa4e7ed995ef829897e9e1c268771c4f64` |
| Historical Re-audit V5 | `docs/audits/phase-11.34-provider-registry-independent-reaudit-v5.md` — independent verdict `FAIL`; `BLOCKERS=0`; `MAJORS=2`; `MINORS=0`; `MAJOR-V5-01`; `MAJOR-V5-02`; audited HEAD `30dec367279b0b80a9692ee0f067365c6e93b0a7`; audited tree `e058dca561efba5d9c0bc58165b12c19761e797c`; bundle SHA-256 `b72e03d78622b2927a9081bea4b180e1343ba9b8e2aea326bf44604ca3580d32` |
| Historical Re-audit V6 | `docs/audits/phase-11.34-provider-registry-independent-reaudit-v6.md` — independent verdict `FAIL`; `BLOCKERS=0`; `MAJORS=1`; `MINORS=0`; `MAJOR-V6-01`; audited HEAD `cd780e3b7d74d2054470f277107986769ebb39a4`; audited tree `ff534595fdc841bd77f40a271c8e50284c0b40e7`; bundle SHA-256 `af0e5f141ef865479946f3882cc13597bf06e33db50a90add22c38dc0d729e3a` |
| Final Re-audit V7 | `docs/audits/phase-11.34-provider-registry-independent-reaudit-v7.md` — independent verdict `PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`; `MAJOR-V6-01=VERIFIED_REMEDIATED`; `MAJOR-V5-01=VERIFIED_REMEDIATED`; `MAJOR-V5-02=VERIFIED_REMEDIATED`; `DP-134=VERIFIED_EXISTING`; `F11-014=VERIFIED_EXISTING`; `AT-DP-134=PASS`; `CLOSURE_ELIGIBLE=YES`; audited HEAD `a96468094d39f7bd8afe5a2d7a4daab67c0b55be`; audited tree `583a260596bdd5eef331be8b3d9a0017fb5628d7`; bundle SHA-256 `09fd8ae76a64a898a8dca6b1397749defe9145c1f7ca865228646a66c6364100`; audit-report commit `59a4c774b647d980927d02f4cea6476075235ca4` |
| Remediation V1 design | `docs/superpowers/specs/2026-09-14-phase-11.34-provider-registry-remediation-v1-design.md` (historical: implemented, then audited by Independent Re-audit V2 `FAIL`) |
| Remediation V1 plan | `docs/superpowers/plans/2026-09-14-phase-11.34-provider-registry-remediation-v1-implementation-plan.md` (historical) |
| Remediation V2 design | `docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v2-design.md` — froze the remedy for the five Re-audit V2 findings |
| Remediation V2 plan | `docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v2-implementation-plan.md` (historical: implemented, then audited by Independent Re-audit V3 `FAIL`) |
| Remediation V3 design | `docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v3-design.md` (historical: implemented, then audited by Independent Re-audit V4 `FAIL`) |
| Remediation V3 plan | `docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v3-implementation-plan.md` (historical) |
| Remediation V4 design | `docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v4-design.md` (historical: implemented, then audited by Independent Re-audit V5 `FAIL`) |
| Remediation V4 plan | `docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v4-implementation-plan.md` (historical) |
| Remediation V5 design | `docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v5-design.md` (historical: implemented, then audited by Independent Re-audit V6 `FAIL`) |
| Remediation V5 plan | `docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v5-implementation-plan.md` (historical) |
| Remediation V6 design | `docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v6-design.md` — froze the remedy for exactly the one Re-audit V6 finding, and changes no design point (`DP-134` unchanged) |
| Remediation V6 plan | `docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v6-implementation-plan.md` — implemented the one Re-audit V6 remedy and was independently verified by final Re-audit V7 `PASS` |
| Remediated findings | `MAJOR-V3-01`, `MAJOR-V3-02` and `MINOR-V3-01` were verified remediated by Re-audit V4; `MAJOR-V4-01`, `MAJOR-V4-02` and `MAJOR-V4-03` were verified remediated by Re-audit V5; Re-audit V6 verified `MAJOR-V5-02` and held `MAJOR-V5-01` partially remediated while opening `MAJOR-V6-01`; final Re-audit V7 verified `MAJOR-V6-01=VERIFIED_REMEDIATED`, `MAJOR-V5-01=VERIFIED_REMEDIATED` and `MAJOR-V5-02=VERIFIED_REMEDIATED`, with no remaining blocker, major or minor findings |
| Lifecycle status | `CLOSED` |
| Audit status | `INDEPENDENT_REAUDIT_V7=PASS` |

Persisted-shape note: the V2 persisted manifest shape carries the explicit
isolation policy (`requires_isolation`), which is why `SCHEMA_VERSION` is `"2"`.
Documents written before that change are rejected rather than silently
reinterpreted, and the state envelope still carries opaque `credential_ref`
values only — never secret material.

### 4.3 `F11-015` — Canonical Integration Core

`F11-001` … `F11-013` remain owned by the Phase 10 matrix and `F11-014` is owned
by §4.1 of this document. `F11-015` is the next non-colliding Phase 11
functional identifier, assigned to Phase 11.1 — Integration Core.

| `requirement_id` | Normative requirement | Source | Phase | Production owners | Mapping status | Acceptance test |
|---|---|---|---|---|---|---|
| `F11-015` | Canonical Integration Core. CMM OS shall compose existing canonical subsystems through one explicit, version-aware application composition root and platform service-binding registry that preserves subsystem ownership, validates configuration and dependency/contract compatibility, prevents circular or duplicate authority, enforces the canonical runtime boundary of every bound service, supports explicit implementation replacement/test adapters, exposes safe deterministic inspection, keeps descriptor metadata secret-free and recursively immutable, rejects invalid service modes before readiness, reuses the closed Provider Registry, and fails closed without implementing Phase 11.2 orchestration. | `SRC-R11` (detailed Phase 11 roadmap §11.1); `docs/superpowers/specs/2026-09-15-phase-11.1-integration-core-design.md` §20; `docs/superpowers/specs/2026-09-15-phase-11.1-remediation-v1-design.md` §4–6 | Phase 11.1 | `cmm/platform/__init__.py`; `cmm/platform/contracts.py`; `cmm/platform/compatibility.py`; `cmm/platform/errors.py`; `cmm/platform/service_registry.py`; `cmm/platform/configuration.py`; `cmm/platform/modules.py`; `cmm/platform/inspection.py`; `cmm/platform/container.py`; `cmm/platform/canonical.py` | `VERIFIED_EXISTING` | `AT-DP-101` — `tests/platform/test_phase11_1_dp101_acceptance.py` |

### 4.4 `F11-015` traceability

| Item | Value |
|---|---|
| Requirement | `F11-015 — Canonical Integration Core` |
| Design Point | `DP-101 — Canonical Application Composition Root` |
| Acceptance test | `AT-DP-101` — `tests/platform/test_phase11_1_dp101_acceptance.py` |
| Production package | `cmm/platform/` (10 modules) |
| Focused suite | `tests/platform/` |
| Architecture gates | `tests/platform/test_architecture.py` |
| Reference documentation | `docs/reference/phase-11-integration-core.md` |
| Design specification | `docs/superpowers/specs/2026-09-15-phase-11.1-integration-core-design.md` |
| Implementation plan | `docs/superpowers/plans/2026-09-15-phase-11.1-integration-core-implementation-plan.md` |
| Independent Audit V1 | `docs/audits/phase-11.1-integration-core-independent-audit-v1.md` — `INDEPENDENT_AUDIT_V1=FAIL`; `BLOCKERS=0`; `MAJORS=3`; `MINORS=0`; `DP-101=NOT_VERIFIED`; `CLOSURE_ELIGIBLE=NO` |
| Remediation V1 design | `docs/superpowers/specs/2026-09-15-phase-11.1-remediation-v1-design.md` |
| Remediation V1 plan | `docs/superpowers/plans/2026-09-15-phase-11.1-remediation-v1-implementation-plan.md` |
| Independent Re-audit V1 | `docs/audits/phase-11.1-integration-core-independent-reaudit-v1.md` — `INDEPENDENT_REAUDIT_V1=PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`; `MAJOR_01=VERIFIED_REMEDIATED`; `MAJOR_02=VERIFIED_REMEDIATED`; `MAJOR_03=VERIFIED_REMEDIATED`; `F11-015=VERIFIED_EXISTING`; `DP-101=VERIFIED_EXISTING`; `AT-DP-101=PASS`; `AT-DP-134=PASS`; `CLOSURE_ELIGIBLE=YES`; audited HEAD `80dd0e70ebb1c5619fb5e0b3c69cbbe382fb0bf4`; audited tree `63a69f2f25922695f1e3d1f4b006ae1172b34949`; bundle SHA-256 `aacb9c8452710d37f28473ee1d8b9e8010e1f2d8337a3279adc845913da609bb`; report commit `54603acf83f06819409601dcd62aae19120c9baf` |
| Remediation V1 findings | `MAJOR-01=CANONICAL_RUNTIME_BOUNDARY_NOT_ENFORCED`; `MAJOR-02=DESCRIPTOR_METADATA_SECRET_AND_MUTABILITY_GAP`; `MAJOR-03=INVALID_SERVICE_MODE_CAN_REACH_READY` — all independently verified remediated by Re-audit V1 |
| Inherited requirement reused | `F11-014` / `DP-134` (Phase 11.34) — reused as a dependency, **not reopened and not modified** |
| Inherited acceptance regression | `AT-DP-134` — `tests/llm/test_provider_registry_dp134_acceptance.py` |
| Mapping status | `VERIFIED_EXISTING` |

The canonical Provider Registry bound as `provider.registry` **is** the Phase
11.34 authoritative object. Phase 11.1 creates no second provider registry,
stores no parallel provider state, infers no providers and weakens no
fail-closed lifecycle behaviour. Remediation V1 added an enforceable runtime
boundary to the binding, not a second authority: the bound object is still the
exact `kernel.llm.provider_registry.ProviderRegistry` instance, and Phase 11.34
production semantics are unchanged.

Final Independent Re-audit V1 returned `PASS` with `BLOCKERS=0`, `MAJORS=0`,
`MINORS=0`, `F11-015=VERIFIED_EXISTING`, `DP-101=VERIFIED_EXISTING`,
`AT-DP-101=PASS`, `AT-DP-134=PASS` and `CLOSURE_ELIGIBLE=YES`. Phase 11.1 is
therefore closed by the dedicated docs-only closure commit. Final report:
`docs/audits/phase-11.1-integration-core-independent-reaudit-v1.md`; audited HEAD `80dd0e70ebb1c5619fb5e0b3c69cbbe382fb0bf4`; bundle SHA-256 `aacb9c8452710d37f28473ee1d8b9e8010e1f2d8337a3279adc845913da609bb`.

### 4.5 `F11-016` — Canonical Request Orchestration

`F11-001` … `F11-013` remain owned by the Phase 10 matrix, `F11-014` is owned
by §4.1 and `F11-015` by §4.3 of this document. `F11-016` is the next
non-colliding Phase 11 functional identifier, assigned to Phase 11.2 —
Orchestration Layer.

| `requirement_id` | Normative requirement | Source | Phase | Production owners | Mapping status | Acceptance test |
|---|---|---|---|---|---|---|
| `F11-016` | Canonical Request Orchestration. CMM OS shall coordinate each application request through one explicit, fail-closed Orchestrator that resolves request intent and authorized context, delegates domain selection to canonical Domain Intelligence, selects a bounded execution route, delegates agent selection to canonical Agent Runtime authority, preserves restrictive permission/approval/autonomy semantics, records safe orchestration decisions, emits safe lifecycle events through an injected sink, and returns a structured orchestration result without duplicating domain, agent, workflow, execution, validation, session, memory, knowledge, provider or event-system ownership. | `SRC-R11` (detailed Phase 11 roadmap §11.2); `docs/superpowers/specs/2026-09-16-phase-11.2-orchestration-layer-design.md` §45 | Phase 11.2 | `cmm/orchestration/__init__.py`; `contracts.py`; `errors.py`; `intent.py`; `context.py`; `domain_router.py`; `agent_router.py`; `policy.py`; `decision_repository.py`; `events.py`; `orchestrator.py`; `platform_module.py` | `IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT` | `AT-DP-102` — `tests/orchestration/test_phase11_2_dp102_acceptance.py` |

### 4.6 `F11-016` traceability

| Item | Value |
|---|---|
| Requirement | `F11-016 — Canonical Request Orchestration` |
| Design Point | `DP-102 — Fail-Closed Canonical Request Orchestration Pipeline` |
| Acceptance test | `AT-DP-102` — `tests/orchestration/test_phase11_2_dp102_acceptance.py` |
| Production package | `cmm/orchestration/` (12 modules) |
| Focused suite | `tests/orchestration/` |
| Architecture gates | `tests/orchestration/test_architecture.py` |
| Reference documentation | `docs/reference/phase-11-orchestration-layer.md` |
| Design specification | `docs/superpowers/specs/2026-09-16-phase-11.2-orchestration-layer-design.md` |
| Implementation plan | `docs/superpowers/plans/2026-09-16-phase-11.2-orchestration-layer-implementation-plan.md` |
| Reused canonical owners | `cmm.domains.resolver.DefaultDomainResolver`; `cmm.domains.registry.DomainRegistry`; `cmm.domains.resolution_builder.DomainResolutionContextBuilder`; `cmm.domains.permission_registry.DomainPermissionRegistry`; `cmm.domains.permission_resolution.DomainPermissionResolver`; `cmm.domains.profile_registry.DomainProfileRegistry` / `InMemoryDomainProfileRegistry`; `cmm.agent_runtime.agent_registry_service.AgentRegistryService`; `cmm.agent_runtime.agent_resolver.AgentResolver`; `cmm.agent_runtime.agent_registry_store.InMemoryAgentRegistryStore`; `cmm.runtime.sessions.SessionStore` / `InMemorySessionStore` / `FileSessionStore`; `cmm.platform.contracts.ErrorResult`; Phase 11.1 `StaticCompositionModule` / `ApplicationContainer` |
| Inherited requirements reused | `F11-015` / `DP-101` (Phase 11.1) and `F11-014` / `DP-134` (Phase 11.34) — referenced, **not reopened and not modified** |
| Inherited acceptance regressions | `AT-DP-101` — `tests/platform/test_phase11_1_dp101_acceptance.py`; `AT-DP-134` — `tests/llm/test_provider_registry_dp134_acceptance.py` |
| Remediation design | `docs/superpowers/specs/2026-09-16-phase-11.2-remediation-v1-design.md` |
| Remediation plan | `docs/superpowers/plans/2026-09-16-phase-11.2-remediation-v1-implementation-plan.md` |
| Mapping status | `IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT` (this document's §2 vocabulary for exactly the Remediation V1 state: implementation exists, a recorded independent audit `FAIL` exists, findings are remediated, independent re-audit closure still pending) |
| Audit status | `INDEPENDENT_AUDIT_V1=FAIL` (`BLOCKERS=0`, `MAJORS=2`, `MINORS=0`) against `AUDITED_HEAD=5ebc8d064fa3f29825c179eff7f41df204dc837b`; Remediation V1 applied; independent re-audit pending |

Phase 11.2 introduces exactly one new persistence owner
(`OrchestrationDecisionRepository`, in-memory only) because orchestration
decision recording is genuinely new; it introduces no second Provider Registry,
Domain Registry, Agent Registry, Session Store, workflow/execution/validation
engine, Memory/Knowledge Store, Event Bus, planner, model router or policy
engine. Safe decision persistence and safe event emission are the only Phase
11.2-owned side effects, and no downstream operation, workflow, agent run,
memory/knowledge write or provider/model call occurs.

Phase 11.2 does not implement the Phase 11.3 Application Backend; the API,
application services, streaming, pagination, idempotency and concurrency remain
Phase 11.3 scope.

## 5. Current lifecycle status

```text
PHASE11_34=CLOSED
INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V2=FAIL
INDEPENDENT_REAUDIT_V3=FAIL
INDEPENDENT_REAUDIT_V4=FAIL
INDEPENDENT_REAUDIT_V5=FAIL
INDEPENDENT_REAUDIT_V6=FAIL
INDEPENDENT_REAUDIT_V7=PASS
BLOCKERS=0
MAJORS=0
MINORS=0
MAJOR-V6-01=VERIFIED_REMEDIATED
MAJOR-V5-01=VERIFIED_REMEDIATED
MAJOR-V5-02=VERIFIED_REMEDIATED
F11-014=VERIFIED_EXISTING
DP-134=VERIFIED_EXISTING
AT-DP-134=PASS
CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=CLOSED_AFTER_INDEPENDENT_REAUDIT_V7_PASS
```

This is the final closed state after Independent Re-audit V7 `PASS`. Historical
Independent Audit V1 and Re-audits V2–V6 remain immutable `FAIL` evidence;
final Re-audit V7 independently verified every closure requirement with
`BLOCKERS=0`, `MAJORS=0` and `MINORS=0`. `MAJOR-V6-01`, `MAJOR-V5-01` and
`MAJOR-V5-02` are `VERIFIED_REMEDIATED`; `DP-134=VERIFIED_EXISTING`;
`F11-014=VERIFIED_EXISTING`; `AT-DP-134=PASS`; and
`CLOSURE_ELIGIBLE=YES`. The final independent report is
`docs/audits/phase-11.34-provider-registry-independent-reaudit-v7.md`, and
the dedicated docs-only closure records `PHASE11_34=CLOSED` without changing
production code or historical audit artifacts.

## 6. Final closure evidence

Independent Re-audit V7 reached the reserved closure state and the dedicated
docs-only closure now records it as current repository state:

```text
INDEPENDENT_REAUDIT_V7=PASS
BLOCKERS=0
MAJORS=0
MINORS=0
MAJOR-V6-01=VERIFIED_REMEDIATED
MAJOR-V5-01=VERIFIED_REMEDIATED
MAJOR-V5-02=VERIFIED_REMEDIATED
DP-134=VERIFIED_EXISTING
AT-DP-134=PASS
F11-014=VERIFIED_EXISTING
CLOSURE_ELIGIBLE=YES
PHASE11_34=CLOSED
```

Audited implementation HEAD:
`a96468094d39f7bd8afe5a2d7a4daab67c0b55be`.
Audited tree: `583a260596bdd5eef331be8b3d9a0017fb5628d7`.
Bundle SHA-256:
`09fd8ae76a64a898a8dca6b1397749defe9145c1f7ca865228646a66c6364100`.
Final report:
`docs/audits/phase-11.34-provider-registry-independent-reaudit-v7.md`.
Audit-report commit:
`59a4c774b647d980927d02f4cea6476075235ca4`.

## 7. Deferred scope recorded with this requirement

- CMM Usage integration: deferred and not performed; no Usage Registry bridge
  exists in the Provider Registry surface (`CMM_USAGE_INTEGRATION=NOT_PERFORMED`).
- CMMChat integration: deferred by the user; no CMMChat provider execution
  integration is introduced by Phase 11.34.
- Phase 11.35 Routing Policy Engine: not started; no routing policy is
  implemented here.
- No parallel provider inventory, persistence framework, isolation runtime,
  validation engine, routing engine, event bus or usage catalog is introduced.

## 8. Phase 11.1 — Integration Core current status

Sections 5 and 6 record the closed Phase 11.34 Provider Registry and are not
modified by Phase 11.1. The Phase 11.1 integration core is a separate subphase
and is reported here:

```text
PHASE11_1=CLOSED
F11_015=VERIFIED_EXISTING
DP_101=VERIFIED_EXISTING
MAJOR_01=VERIFIED_REMEDIATED
MAJOR_02=VERIFIED_REMEDIATED
MAJOR_03=VERIFIED_REMEDIATED
AT_DP_101=PASS
AT_DP_134=PASS
F11_014=VERIFIED_EXISTING
DP_134=VERIFIED_EXISTING
PHASE11_34=CLOSED
INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V1=PASS
BLOCKERS=0
MAJORS=0
MINORS=0
CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=CLOSED_AFTER_INDEPENDENT_REAUDIT_V1_PASS
```

`IMPLEMENTED_REMEDIATION_V1_PENDING_REAUDIT` is this matrix's §2 vocabulary
term `IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT` applied to Remediation V1. It
records that a recorded independent audit `FAIL` exists
(`INDEPENDENT_AUDIT_V1=FAIL`; `BLOCKERS=0`; `MAJORS=3`; `MINORS=0`), that the
three recorded MAJOR findings are remediated, and that independent re-audit
closure is still pending. It is **not** a closure and **not** a verification
claim: `DP_101` is deliberately not `VERIFIED_EXISTING` and `CLOSURE_ELIGIBLE`
is deliberately `NO` until the independent re-audit passes. Historical Audit V1
at `docs/audits/phase-11.1-integration-core-independent-audit-v1.md` is
immutable and deliberately unedited.

Phase 11.1 does not reopen Phase 11.34. `PHASE11_34=CLOSED`,
`F11-014=VERIFIED_EXISTING`, `DP-134=VERIFIED_EXISTING` and `AT-DP-134=PASS`
remain exactly as recorded in §4.1, §5 and §6.

Remediation V1 changed only the Phase 11.1 public boundary:

- `cmm/platform/canonical.py` declares and enforces one canonical runtime
  boundary per service, so a descriptor identity alone can never confer
  canonical authority;
- `cmm/platform/contracts.py` accepts descriptor metadata only as a small,
  secret-free, recursively immutable descriptive value grammar;
- `cmm/platform/contracts.py` and `cmm/platform/inspection.py` require a real
  `ServiceMode`, so a ready container always exposes a serializable snapshot;
- `AT-DP-101` now permanently carries the three Audit V1 reproducers as
  fail-closed acceptance coverage.

Details, including the runtime boundary selected per service and the metadata
representation, are recorded in
[`docs/reference/phase-11-integration-core.md`](phase-11-integration-core.md)
§14.

Deferred scope recorded with Phase 11.1 (not implemented, not silently pulled
forward):

- Phase 11.2 Orchestration Layer — `Orchestrator`, `IntentResolver`,
  `ContextResolver`, `DomainRouter`, `AgentRouter`, `OrchestrationRequest`,
  `OrchestrationResult`, central user-request processing;
- application API/backend endpoints and any conversational interface;
- CMMChat and CMM Bots integration;
- Model Gateway and the Phase 11.35 Routing Policy Engine;
- real remote transport, authentication and authorization/RBAC;
- secrets management, storage migrations and backup/recovery;
- Phase 11.19 Plugin System lifecycle (discovery, install, enable/disable,
  sandboxing, permission management, upgrade, uninstall);
- Docker runtime, UI, search and notifications;
- a new Event System, audit-trail subsystem or performance/resource-management
  subsystem.

No parallel provider registry, domain registry, agent runtime, planner, workflow
engine, validation engine, knowledge/memory store, tool registry or event bus is
introduced by Phase 11.1.

## 9. Phase 11.2 — Orchestration Layer current status

Sections 5, 6 and 8 record the closed Phase 11.34 Provider Registry and the
closed Phase 11.1 integration core and are not modified by Phase 11.2. The
Phase 11.2 orchestration layer is a separate subphase and is reported here:

```text
PHASE11_2=IMPLEMENTED_REMEDIATION_V1_PENDING_REAUDIT

MAJOR_01=REMEDIATED_PENDING_REAUDIT
MAJOR_02=REMEDIATED_PENDING_REAUDIT

F11_016=IMPLEMENTED_REMEDIATION_V1_PENDING_REAUDIT
DP_102=IMPLEMENTED_REMEDIATION_V1_PENDING_REAUDIT
AT_DP_102=PASS

PHASE11_1=CLOSED
F11_015=VERIFIED_EXISTING
DP_101=VERIFIED_EXISTING
AT_DP_101=PASS

PHASE11_34=CLOSED
F11_014=VERIFIED_EXISTING
DP_134=VERIFIED_EXISTING
AT_DP_134=PASS

CLOSURE_ELIGIBLE=NO
AUDIT_STATUS=REMEDIATION_V1_APPLIED_PENDING_INDEPENDENT_REAUDIT
```

Independent Audit V1 remains recorded historical evidence and is not rewritten:

```text
INDEPENDENT_AUDIT_V1=FAIL

BLOCKERS=0
MAJORS=2
MINORS=0

MAJOR_01=UNSAFE_ORCHESTRATION_ROLE_RUNTIME_CONTRACTS
MAJOR_02=CANONICAL_AGENT_AUTHORITY_NOT_ENFORCED

F11_016=IMPLEMENTED_REMEDIATION_REQUIRED
DP_102=NOT_VERIFIED
AT_DP_102=PASS

AUDITED_HEAD=5ebc8d064fa3f29825c179eff7f41df204dc837b
AUDITED_TREE=989706d15ba78b8333b1e9b3634f820e9180f5bf
AUDIT_BUNDLE_SHA256=85127ed1e9a437e30984f930b60fba79b7ae28959baf3296f86665ce11b93fc9

CLOSURE_ELIGIBLE=NO
```

`INDEPENDENT_AUDIT_V1=PASS`, `DP_102=VERIFIED_EXISTING` and
`CLOSURE_ELIGIBLE=YES` may only be recorded after an independent re-audit of the
Remediation V1 exact-HEAD bundle.

Phase 11.2 does not reopen Phase 11.1 or Phase 11.34. No closed-phase production
semantics were changed: the Phase 11.1 composition core is **extended** by one
new side-effect-free orchestration composition module, and the Phase 11.34
Provider Registry is referenced as a dependency only.

Phase 11.2 introduces no new Phase 11.3 surface:

- no HTTP API, FastAPI/Flask/Starlette, OpenAPI, REST resources, endpoint
  decorators, streaming, pagination or API idempotency/concurrency;
- no application-service facade, conversation service, `GoalService`,
  `WorkflowService`, `KnowledgeService` or `MemoryService`;
- no CMMChat or CMM Bots integration;
- no Model Gateway or provider/model routing;
- no Event Bus, plugin lifecycle, scheduler or queue;
- no new session, goal, workflow, memory, knowledge or event repository.

Deferred Phase 11.2 items recorded with this requirement (implemented nowhere,
not silently pulled forward):

- API and application backend surfaces — **Phase 11.3**;
- durable (file/SQLite/relational) orchestration decision persistence — Phase
  11.15 storage work; Phase 11.2 provides the official in-memory repository
  only;
- per-actor domain authorization — canonical permission evidence today, the
  dedicated authorization owner in Phase 11.13;
- Model Gateway / Phase 11.35 Routing Policy Engine integration — later routing
  work; Phase 11.2 correctness does not depend on remote inference;
- distributed tracing, metrics infrastructure, dashboards and alerting — later
  Phase 11 observability work; Phase 11.2 propagates existing references only;
- CMMChat / CMM Bots consumption of the orchestration result — after the Phase
  11.3 Application Backend.

Implementation decisions and deviations are recorded in
[`docs/reference/phase-11-orchestration-layer.md`](phase-11-orchestration-layer.md)
§18; the Audit V1 Remediation V1 record, including the canonical collaborator
classification table, is in the same document §17.
