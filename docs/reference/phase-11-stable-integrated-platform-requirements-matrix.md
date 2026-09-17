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

Phase 11.3 records that same state under the explicit audit marker
`IMPLEMENTED_REMEDIATION_V1_PENDING_REAUDIT`: Independent Audit V1 returned
`FAIL` (`BLOCKERS=0`, `MAJORS=1`, `MINORS=1`), Remediation V1 closed exactly its
two findings, and the independent re-audit of the exact-HEAD remediation bundle
is still pending. The two spellings mean the same thing and neither is a closure.

Phase 11.5 records its pre-audit state under the explicit marker
`IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT`: the implementation exists on the
intended branch, the connected acceptance is green in this repository, and no
independent audit has examined the implementation yet. It is the pre-audit
meaning of `IMPLEMENTED_PENDING_INDEPENDENT_AUDIT` under the wording the design
specification's §33 requires before audit, and it is neither a closure nor a
verification claim.

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
| `F11-016` | Canonical Request Orchestration. CMM OS shall coordinate each application request through one explicit, fail-closed Orchestrator that resolves request intent and authorized context, delegates domain selection to canonical Domain Intelligence, selects a bounded execution route, delegates agent selection to canonical Agent Runtime authority, preserves restrictive permission/approval/autonomy semantics, records safe orchestration decisions, emits safe lifecycle events through an injected sink, and returns a structured orchestration result without duplicating domain, agent, workflow, execution, validation, session, memory, knowledge, provider or event-system ownership. | `SRC-R11` (detailed Phase 11 roadmap §11.2); `docs/superpowers/specs/2026-09-16-phase-11.2-orchestration-layer-design.md` §45 | Phase 11.2 | `cmm/orchestration/__init__.py`; `contracts.py`; `errors.py`; `intent.py`; `context.py`; `domain_router.py`; `agent_router.py`; `policy.py`; `decision_repository.py`; `events.py`; `orchestrator.py`; `platform_module.py` | `VERIFIED_EXISTING` | `AT-DP-102` — `tests/orchestration/test_phase11_2_dp102_acceptance.py` |

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
| Independent Re-audit V1 | `docs/audits/phase-11.2-orchestration-layer-independent-reaudit-v1.md` — `FAIL`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=1`; `F11-016=VERIFIED_EXISTING`; `DP-102=VERIFIED_EXISTING`; `AT-DP-102=PASS`; `CLOSURE_ELIGIBLE=NO` |
| Independent Re-audit V2 | `docs/audits/phase-11.2-orchestration-layer-independent-reaudit-v2.md` — `PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`; `MAJOR_01=VERIFIED_REMEDIATED`; `MAJOR_02=VERIFIED_REMEDIATED`; `MINOR_01=VERIFIED_REMEDIATED`; `F11-016=VERIFIED_EXISTING`; `DP-102=VERIFIED_EXISTING`; `AT-DP-102=PASS`; `AT-DP-101=PASS`; `AT-DP-134=PASS`; `CLOSURE_ELIGIBLE=YES`; audited HEAD `68ff78c614d8f7a9dc3295eb22ecea62a425cce5`; audited tree `d586c439fc9b3c87d139eecab8d084d820007bce`; bundle SHA-256 `72d1b5b36104734308e322b2edd038875755d145db5d9ad8f77e2d45c7a7e62e`; report commit `773204c7df06fced504892ed33284f39eca5b63a` |
| Mapping status | `VERIFIED_EXISTING` (final Independent Re-audit V2 `PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`; `CLOSURE_ELIGIBLE=YES`) |
| Audit status | `INDEPENDENT_AUDIT_V1=FAIL`; `INDEPENDENT_REAUDIT_V1=FAIL`; final `INDEPENDENT_REAUDIT_V2=PASS` with `BLOCKERS=0`, `MAJORS=0`, `MINORS=0`; audited HEAD `68ff78c614d8f7a9dc3295eb22ecea62a425cce5`; audited tree `d586c439fc9b3c87d139eecab8d084d820007bce`; bundle SHA-256 `72d1b5b36104734308e322b2edd038875755d145db5d9ad8f77e2d45c7a7e62e`; report commit `773204c7df06fced504892ed33284f39eca5b63a` |

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

### 4.7 `F11-017` — Canonical Application Backend

`F11-001` … `F11-013` remain owned by the Phase 10 matrix, `F11-014` is owned
by §4.1, `F11-015` by §4.3 and `F11-016` by §4.5 of this document. `F11-017` is
the next non-colliding Phase 11 functional identifier, assigned to Phase 11.3 —
Application Backend.

| `requirement_id` | Normative requirement | Source | Phase | Production owners | Mapping status | Acceptance test |
|---|---|---|---|---|---|---|
| `F11-017` | Canonical Application Backend. CMM OS shall expose stable application-facing capabilities through one version-aware, transport-neutral, fail-closed application backend that composes through the canonical Phase 11.1 `ApplicationContainer`, routes user-request processing through the canonical Phase 11.2 `Orchestrator`, exposes explicit public request, response and error contracts, separates application commands from application queries, prevents transport handlers from bypassing application services, prevents application services from re-owning canonical domain, agent, workflow, execution, validation, session, memory, knowledge, provider or orchestration authorities, maps internal failures to safe public errors, supports explicit API versioning, provides deterministic OpenAPI metadata for the HTTP adapter, supports public streaming and cancellation contracts without creating a new event system or inference runtime, supports repeatable command idempotency through a narrow backend-owned seam without introducing durable storage, respects canonical session revision/concurrency semantics rather than inventing a global concurrency subsystem, rejects unavailable or not-yet-owned capabilities explicitly, exposes no secrets, raw internal exceptions, hidden reasoning or raw sensitive context, and remains local-first and independently testable without network access. | `SRC-R11` (detailed Phase 11 roadmap §11.3); `docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md` §3–§5 | Phase 11.3 | `cmm/application/__init__.py`; `contracts.py`; `errors.py`; `idempotency.py`; `sessions.py`; `requests.py`; `health.py`; `capabilities.py`; `gateway.py`; `platform_module.py`; `cmm/api/__init__.py`; `app.py`; `models.py`; `errors.py`; `streaming.py` | `VERIFIED_EXISTING` | `AT-DP-103` — `tests/application/test_phase11_3_dp103_acceptance.py` |

### 4.8 `F11-017` traceability

| Item | Value |
|---|---|
| Requirement | `F11-017 — Canonical Application Backend` |
| Design Point | `DP-103 — Versioned, Fail-Closed Application Gateway` |
| Acceptance test | `AT-DP-103` — `tests/application/test_phase11_3_dp103_acceptance.py` |
| Production packages | `cmm/application/` (10 modules); `cmm/api/` (5 modules) |
| Focused suites | `tests/application/`; `tests/api/` |
| Architecture gates | `tests/application/test_architecture.py`; `tests/api/test_architecture.py` |
| OpenAPI gate | `tests/api/test_openapi.py` |
| Reference documentation | `docs/reference/phase-11-application-backend.md` |
| Design specification | `docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md` |
| Implementation plan | `docs/superpowers/plans/2026-09-16-phase-11.3-application-backend-implementation-plan.md` |
| Remediation V1 design | `docs/superpowers/specs/2026-09-16-phase-11.3-remediation-v1-design.md` — commit `0eb802b` |
| Remediation V1 plan | `docs/superpowers/plans/2026-09-16-phase-11.3-remediation-v1-implementation-plan.md` — commit `a185134` |
| Remediation V1 production owner | `cmm/application/gateway.py` — one private in-process `threading.Lock` over the complete keyed `get -> execute -> put` critical section |
| Remediation V1 regression tests | `tests/application/test_gateway.py` (three focused concurrency tests); `tests/application/test_phase11_3_dp103_acceptance.py` (two connected concurrent scenarios) |
| Reused canonical owners | Phase 11.1 `ApplicationContainer` / `StaticCompositionModule` / `ServiceBinding`; Phase 11.2 `Orchestrator` and its collaborators; `cmm.runtime.sessions.SessionStore` / `InMemorySessionStore` / `FileSessionStore`; canonical `cmm.domains` and `cmm.agent_runtime` authority reached only through the Orchestrator |
| Inherited requirements reused | `F11-015` / `DP-101` (Phase 11.1), `F11-016` / `DP-102` (Phase 11.2) and `F11-014` / `DP-134` (Phase 11.34) — referenced, **not reopened and not modified** |
| Inherited acceptance regressions | `AT-DP-102` — `tests/orchestration/test_phase11_2_dp102_acceptance.py`; `AT-DP-101` — `tests/platform/test_phase11_1_dp101_acceptance.py`; `AT-DP-134` — `tests/llm/test_provider_registry_dp134_acceptance.py` |
| Independent Audit V1 | `docs/audits/phase-11.3-application-backend-independent-audit-v1.md` — `FAIL`; `BLOCKERS=0`; `MAJORS=1`; `MINORS=1`; `MAJOR_01=NON_ATOMIC_IDEMPOTENCY_UNDER_CONCURRENT_REQUESTS`; `MINOR_01=STALE_UNQUALIFIED_IMPLEMENTATION_HEAD_IN_ROOT_ROADMAP`; `AUDITED_HEAD=5fd8cc3b171faec88b802be920ad09ac53224e75`; `AUDITED_TREE=1cfbe114369ac89d1c2563a9787c5ebf096c64df`; `AUDIT_BUNDLE_SHA256=17377075eae659d123ca4ee909fa8f0cef01f625f40c2d498b34f22a47690199`; report commit `c111a57` — immutable |
| Independent Re-audit V1 | `docs/audits/phase-11.3-application-backend-independent-reaudit-v1.md` — `PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`; `MAJOR_01=VERIFIED_REMEDIATED`; `MINOR_01=VERIFIED_REMEDIATED`; `F11_017=VERIFIED_EXISTING`; `DP_103=VERIFIED_EXISTING`; `AT_DP_103=PASS`; `AT_DP_102=PASS`; `AT_DP_101=PASS`; `AT_DP_134=PASS`; `CLOSURE_ELIGIBLE=YES`; audited HEAD `4525f72391792e623730af69e95bcd054ce3cddf`; audited tree `0b650c8133111754452940c74a1bc72f24a0df23`; bundle SHA-256 `152276776b9e2765edb67adcd95b6ee3d2b565d416e1e4bce665777a078d9618`; report commit `c21f2e257a1995b748b78b65b622ff68ca3e6d38` |
| Finding status | `MAJOR_01=VERIFIED_REMEDIATED`; `MINOR_01=VERIFIED_REMEDIATED` |
| Mapping status | `VERIFIED_EXISTING` |
| Next step | Phase 11.4 — CLI is independently re-audited and closed; inspect Phase 11.5 — Conversational Interface next |

`F11-017` is `VERIFIED_EXISTING` and `DP_103=VERIFIED_EXISTING` after Independent
Re-audit V1 `PASS`. Historical Audit V1 `FAIL` remains immutable; Re-audit V1
verified `MAJOR_01` and `MINOR_01` as remediated and confirmed
`AT-DP-103=PASS` with `CLOSURE_ELIGIBLE=YES`.

### 4.9 `F11-018` — Canonical Operational CLI

`F11-001` … `F11-013` remain owned by the Phase 10 matrix, `F11-014` is owned
by §4.1, `F11-015` by §4.3, `F11-016` by §4.5 and `F11-017` by §4.7 of this
document. `F11-018` is the next non-colliding Phase 11 functional identifier,
assigned to Phase 11.4 — CLI.

| `requirement_id` | Normative requirement | Source | Phase | Production owners | Mapping status | Acceptance test |
|---|---|---|---|---|---|---|
| `F11-018` | Canonical Operational CLI. CMM OS shall expose one canonical, scriptable and human-usable command-line interface through the existing `cmm` console entrypoint and root `argparse` command tree; the CLI shall adapt to canonical application and subsystem contracts without becoming an execution, routing, storage, provider, domain, agent, workflow, validation, approval or configuration authority; shall preserve existing specialized CLI surfaces; shall reserve the roadmap's public namespace with explicit fail-closed unavailable capability behavior; and shall provide stable structured output and exit-code semantics suitable for automation and CI. | `SRC-R11` (detailed Phase 11 roadmap §11.4); `docs/superpowers/specs/2026-09-16-phase-11.4-cli-design.md` §6–§8 | Phase 11.4 | `cmm/cli.py`; `cmm/__main__.py`; `cmm/cli_contracts.py`; `cmm/cli_output.py`; `cmm/cli_commands.py`; `cmm/cli_application.py`; `cmm/cli_doctor.py`; `cmm/application/contracts.py`; `cmm/application/requests.py`; `cmm/application/gateway.py`; `cmm/application/local_runtime.py` | `VERIFIED_EXISTING` | `AT-DP-104` — `tests/cli/test_phase11_4_dp104_acceptance.py` |

### 4.10 `F11-018` traceability

| Item | Value |
|---|---|
| Requirement | `F11-018 — Canonical Operational CLI` |
| Design Point | `DP-104 — Single-Front-Door Fail-Closed Operational CLI` |
| Acceptance test | `AT-DP-104 — Canonical CLI Integration Acceptance` — `tests/cli/test_phase11_4_dp104_acceptance.py` |
| Production modules | `cmm/` presentation modules (7: `cli.py`, `__main__.py`, `cli_contracts.py`, `cli_output.py`, `cli_commands.py`, `cli_application.py`, `cli_doctor.py`); `cmm/application/` compatibility/composition additions (`contracts.py`, `requests.py`, `gateway.py`, `local_runtime.py`, `__init__.py`) |
| Focused suites | `tests/cli/` (459 tests) |
| Architecture gate | `tests/cli/test_phase11_4_architecture.py` (52 tests); inherited `tests/application/test_architecture.py`, `tests/api/test_architecture.py`, `tests/platform/test_architecture.py`, `tests/orchestration/test_architecture.py` |
| OpenAPI gate | `tests/api/test_openapi.py` |
| Reference documentation | `docs/reference/phase-11-cli.md` |
| Design specification | `docs/superpowers/specs/2026-09-16-phase-11.4-cli-design.md` |
| Implementation plan | `docs/superpowers/plans/2026-09-16-phase-11.4-cli-implementation-plan.md` |
| Public entrypoint | `pyproject.toml` `[project.scripts]` — `cmm = "cmm.cli:main"`, exactly one occurrence |
| Reserved namespace | 16 families: `status`, `doctor`, `ask`, `chat`, `config`, `goals`, `workflows`, `approvals`, `memory`, `knowledge`, `domains`, `plugins`, `backup`, `migrate`, `logs`, `metrics`; 29 frozen command identities (4 available, 25 unavailable) |
| Reused canonical owners | Phase 11.3 `ApplicationGateway` / `ApplicationChannel` / application services; Phase 11.2 `Orchestrator` and canonical routing; Phase 11.1 `ApplicationContainer` / `StaticCompositionModule`; canonical `cmm.domains`, `cmm.agent_runtime`, `cmm.runtime.sessions` and kernel provider registry reached only through the application boundary or the local composition root |
| Inherited requirements reused | `F11-017` / `DP-103` (Phase 11.3), `F11-016` / `DP-102` (Phase 11.2), `F11-015` / `DP-101` (Phase 11.1) and `F11-014` / `DP-134` (Phase 11.34) — referenced, **not reopened and not modified** |
| Inherited acceptance regressions | `AT-DP-103` — `tests/application/test_phase11_3_dp103_acceptance.py`; `AT-DP-102`; `AT-DP-101`; `AT-DP-134` |
| Mapping status | `VERIFIED_EXISTING` |
| Next step | verify the Phase 11.4 docs-only closure commit, then inspect Phase 11.5 — Conversational Interface |

`F11-018` is `VERIFIED_EXISTING`. Independent Audit V1 `FAIL` is preserved as historical evidence; final Independent Re-audit V1 `PASS` verified `DP-104`, `AT-DP-104`, and `CLOSURE_ELIGIBLE=YES`.

### 4.11 `F11-019` — Canonical Conversational Interface

`F11-001` … `F11-013` remain owned by the Phase 10 matrix, `F11-014` is owned
by §4.1, `F11-015` by §4.3, `F11-016` by §4.5, `F11-017` by §4.7 and `F11-018`
by §4.9 of this document. `F11-019` is the next non-colliding Phase 11
functional identifier, assigned to Phase 11.5 — Conversational Interface. Its
pre-audit mapping status is `IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT`: the
implementation exists in this repository and the connected acceptance is green
here, while no independent audit has examined it yet.

| `requirement_id` | Normative requirement | Source | Phase | Production owners | Mapping status | Acceptance test |
|---|---|---|---|---|---|---|
| `F11-019` | Canonical Conversational Interface. CMM OS shall expose one canonical, version-aware, interface-neutral, fail-closed conversational boundary that provides persistent multi-turn natural interaction over canonical shared sessions; uses the existing Phase 11.3 `ApplicationGateway` for application-facing message submission and reaches the canonical Phase 11.2 `Orchestrator` rather than implementing alternate routing; consumes existing authorized Domain Intelligence interface projections rather than reconstructing domain state; preserves canonical session revision and optimistic-concurrency semantics; supports safe public conversational messages, responses and versioned contracts; exposes requested versus effective conversational capabilities; exposes authorized context, domain, source, question, workflow, action, approval, result, contradiction, warning and memory-proposal references when available; supports auditable editing and controlled regeneration without destructive transcript rewriting; represents attachment/document references without creating a parallel file authority; exposes streaming and cancellation truthfully according to canonical effective capability; keeps normal conversation usable without Bot or Agent binding and treats optional Bot identifiers as non-authoritative; leaks no hidden reasoning, secrets, raw sensitive context, internal exceptions, credentials or unauthorized references; remains consumable by CMMChat and alternative clients through stable contracts; and introduces no parallel stores, engines, runtimes, registries, routers, planners, approval managers, permission engines, memory systems, knowledge systems, provider systems or session systems. | `SRC-R11` (detailed Phase 11 roadmap §11.5); `docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md` §3–§7, §25–§26 | Phase 11.5 | `cmm/conversation/__init__.py`; `contracts.py`; `errors.py`; `state.py`; `capabilities.py`; `projection.py`; `service.py`; `platform_module.py`; `cmm/application/contracts.py`; `cmm/application/requests.py`; `cmm/application/local_runtime.py`; `cmm/api/app.py`; `cmm/api/models.py` | `IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT` | `AT-DP-105` — `tests/conversation/test_phase11_5_dp105_acceptance.py` |

### 4.12 `F11-019` traceability

| Item | Value |
|---|---|
| Requirement | `F11-019 — Canonical Conversational Interface` |
| Design Point | `DP-105 — Session-Backed Canonical Conversation Boundary` |
| Acceptance test | `AT-DP-105 — Canonical Conversational Interaction Acceptance` — `tests/conversation/test_phase11_5_dp105_acceptance.py` |
| Production package | `cmm/conversation/` (8 modules: `__init__.py`, `contracts.py`, `errors.py`, `state.py`, `capabilities.py`, `projection.py`, `service.py`, `platform_module.py`) |
| Additive seams in closed packages | `cmm/application/contracts.py` (`ApplicationChannel.CONVERSATION`); `cmm/application/requests.py` (channel mapping); `cmm/application/local_runtime.py` (canonical `session_store` reference); `cmm/api/app.py` (optional `conversation` keyword and the five conversation routes); `cmm/api/models.py` (conversation transport DTOs) |
| Focused suite | `tests/conversation/` (685 tests) |
| Architecture/security gate | `tests/conversation/test_architecture.py` (125 tests); inherited `tests/application/test_architecture.py`, `tests/api/test_architecture.py`, `tests/platform/test_architecture.py` |
| OpenAPI gate | `tests/api/test_openapi.py`; frozen route surface `tests/api/test_http_v1.py` |
| Reference documentation | `docs/reference/phase-11-conversational-interface.md` |
| Design specification | `docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md` |
| Implementation plan | `docs/superpowers/plans/2026-09-17-phase-11.5-conversational-interface-implementation-plan.md` |
| Session extension | `conversation.v1` inside the canonical shared session (`version: 1`; `{version, session_id, mode, bot_id, active_message_id, messages}`); the canonical `SessionStore` stays the only persistence authority |
| Application seam | `ApplicationChannel.CONVERSATION = "conversation"` mapped one-to-one to the pre-existing `OrchestrationChannel.CONVERSATION`; `API` stays the default and closed values keep their order and spelling |
| HTTP routes | five additive routes under one frozen envelope, all answering `200`: `GET /v1/conversations/{session_id}`; `POST /v1/conversations/{session_id}/messages`; `POST /v1/conversations/{session_id}/messages/{message_id}/edit`; `POST /v1/conversations/{session_id}/responses/{message_id}/regenerate`; `POST /v1/conversations/requests/{request_id}/cancel` |
| Reused canonical owners | Phase 11.3 `ApplicationGateway` / application services / `ApplicationChannel`; Phase 11.2 `Orchestrator` and its collaborators; `cmm.runtime.sessions.SessionStore` / `SharedSessionState` / `InMemorySessionStore` / `FileSessionStore`; Phase 10.45 `cmm.domains.interface_integration_contracts` (authorized `ConversationalDomainView` only); Phase 11.1 `StaticCompositionModule` / `ServiceBinding` |
| Inherited requirements reused | `F11-018` / `DP-104` (Phase 11.4), `F11-017` / `DP-103` (Phase 11.3), `F11-016` / `DP-102` (Phase 11.2), `F11-015` / `DP-101` (Phase 11.1) and `F11-014` / `DP-134` (Phase 11.34) — referenced, **not reopened and not modified** |
| Inherited acceptance regressions | `AT-DP-104` — `tests/cli/test_phase11_4_dp104_acceptance.py`; `AT-DP-103` — `tests/application/test_phase11_3_dp103_acceptance.py`; `AT-DP-102` — `tests/orchestration/test_phase11_2_dp102_acceptance.py`; `AT-DP-101` — `tests/platform/test_phase11_1_dp101_acceptance.py`; `AT-DP-134` — `tests/llm/test_provider_registry_dp134_acceptance.py`; `AT-DP-045` — `tests/domains/test_domain_interface_dp045_acceptance.py` |
| Closed-phase adjustments | two additive architecture-gate seams (`tests/application/test_architecture.py`, `tests/api/test_architecture.py`) and the repaired exact-set/allowlist pins (`tests/application/test_channels.py`, `tests/application/test_local_runtime.py`, `tests/api/test_http_v1.py`, `tests/api/test_openapi.py`, `tests/application/test_phase11_3_dp103_acceptance.py`, `tests/platform/test_architecture.py`) — every change additive, documented with a Phase 11.5/DP-105 comment and recorded in the reference document |
| Mapping status | `IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT` |
| Next step | independent audit of the exact-HEAD Phase 11.5 implementation bundle |

`F11-019` is `IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT` and `DP_105` is
implemented in production architecture; `AT-DP-105` is green in this repository.
No closure, no verification and no closure eligibility is claimed for Phase 11.5
before the independent audit returns its evidence. The pre-audit state, the
implemented surface, the capability truth table and the recorded residual limits
are documented in
[`docs/reference/phase-11-conversational-interface.md`](phase-11-conversational-interface.md).

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
PHASE11_2=CLOSED

INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V2=PASS

BLOCKERS=0
MAJORS=0
MINORS=0

MAJOR_01=VERIFIED_REMEDIATED
MAJOR_02=VERIFIED_REMEDIATED
MINOR_01=VERIFIED_REMEDIATED

F11_016=VERIFIED_EXISTING
DP_102=VERIFIED_EXISTING
AT_DP_102=PASS

PHASE11_1=CLOSED
F11_015=VERIFIED_EXISTING
DP_101=VERIFIED_EXISTING
AT_DP_101=PASS

PHASE11_34=CLOSED
F11_014=VERIFIED_EXISTING
DP_134=VERIFIED_EXISTING
AT_DP_134=PASS

CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=CLOSED_AFTER_INDEPENDENT_REAUDIT_V2_PASS
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

Independent Re-audit V1 is preserved as `FAIL` with `BLOCKERS=0`, `MAJORS=0`
and `MINORS=1`; it independently verified both Audit V1 MAJOR remediations and
left one documentation-only MINOR. Final Independent Re-audit V2 is `PASS` with
`BLOCKERS=0`, `MAJORS=0`, `MINORS=0`, `F11_016=VERIFIED_EXISTING`,
`DP_102=VERIFIED_EXISTING`, `AT_DP_102=PASS` and `CLOSURE_ELIGIBLE=YES`.
The audited V2 implementation HEAD is `68ff78c614d8f7a9dc3295eb22ecea62a425cce5`, tree `d586c439fc9b3c87d139eecab8d084d820007bce`,
with bundle SHA-256 `72d1b5b36104734308e322b2edd038875755d145db5d9ad8f77e2d45c7a7e62e`.

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

## 10. Phase 11.3 — Application Backend current status

Sections 5, 6, 8 and 9 record the closed Phase 11.34 Provider Registry, the
closed Phase 11.1 integration core and the closed Phase 11.2 orchestration layer
and are not modified by Phase 11.3. The Phase 11.3 application backend is a
separate subphase and is reported here:

```text
PHASE11_3=CLOSED

INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V1=PASS

BLOCKERS=0
MAJORS=0
MINORS=0

MAJOR_01=VERIFIED_REMEDIATED
MINOR_01=VERIFIED_REMEDIATED

F11_017=VERIFIED_EXISTING
DP_103=VERIFIED_EXISTING
AT_DP_103=PASS

AT_DP_102=PASS
AT_DP_101=PASS
AT_DP_134=PASS

PHASE11_2=CLOSED
PHASE11_1=CLOSED
PHASE11_34=CLOSED

AUDITED_HEAD=4525f72391792e623730af69e95bcd054ce3cddf
AUDITED_TREE=0b650c8133111754452940c74a1bc72f24a0df23
REAUDIT_BUNDLE_SHA256=152276776b9e2765edb67adcd95b6ee3d2b565d416e1e4bce665777a078d9618
REAUDIT_V1_REPORT_COMMIT=c21f2e257a1995b748b78b65b622ff68ca3e6d38

CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=CLOSED_AFTER_INDEPENDENT_REAUDIT_V1_PASS
```

Phase 11.3 introduces exactly one new requirement identifier (`F11-017`), one
Design Point (`DP-103`), one connected acceptance test (`AT-DP-103`) and two new
packages (`cmm/application/`, `cmm/api/`). It owns one new persistence-ish seam —
the bounded, in-memory-only idempotency repository — and no durable storage,
migration, second container, parallel registry, provider/model routing,
Event Bus, scheduler, queue, background worker system, plugin runtime or
authentication/authorization layer. Domain, agent, provider, session,
orchestration and platform ownership all stay canonical, and the HTTP adapter
reaches them only through `cmm.application`.

Independent Audit V1 of the Phase 11.3 candidate returned `FAIL` with
`BLOCKERS=0`, `MAJORS=1`, `MINORS=1` and remains immutable. Remediation V1
repaired exactly those two findings: the keyed idempotency boundary is now one
atomic critical section owned by `ApplicationGateway`, and root `ROADMAP.md`
qualifies the historical implementation milestone correctly.

Independent Re-audit V1 of exact HEAD `4525f72391792e623730af69e95bcd054ce3cddf` returned `PASS` with
`BLOCKERS=0`, `MAJORS=0`, `MINORS=0`; `MAJOR_01` and `MINOR_01` are
`VERIFIED_REMEDIATED`, `F11_017=VERIFIED_EXISTING`,
`DP_103=VERIFIED_EXISTING`, `AT_DP_103=PASS`, and
`CLOSURE_ELIGIBLE=YES`. Phase 11.3 is therefore closed by the dedicated
documentation-only closure commit.

Phase 11.3 does not reopen Phase 11.1, Phase 11.2 or Phase 11.34. No closed-phase
production semantics were modified: the Phase 11.1 platform gate now names its
sanctioned consumers as the allowlist `("orchestration", "application")` instead
of exempting `cmm.orchestration` alone, which is a documented Phase 11.1 test
adjustment, and the closed-phase production directories are byte-identical to
the Phase 11.3 design commit.

Deferred Phase 11.3 items recorded with this requirement (implemented nowhere,
not silently pulled forward):

- domain and agent listing routes, and every route for goals, workflows,
  operations, approvals, memory, knowledge, bots, tools, configuration, events,
  metrics, backups and plugins — no canonical owner or safe adapter exists yet,
  so no route fabricates behavior and capability discovery reports the honest
  status instead;
- request cancellation runtime — the stable public surface rejects it explicitly
  as `CAPABILITY_UNAVAILABLE` (`503`), and the `request-cancellation` capability
  declares the reason `NO_CANCELLABLE_OWNER`, because the synchronous
  orchestration boundary has no active-request owner to cancel;
- durable idempotency persistence — Phase 11.15 storage work; the official
  in-memory repository is the only Phase 11.3 implementation;
- Model Gateway and the Phase 11.35 Routing Policy Engine — later routing work;
  the public path reaches no provider or model;
- authentication/authorization and RBAC — Phase 11.13;
- Plugin System lifecycle — Phase 11.19;
- Event Bus, scheduler, queue, distributed tracing, metrics infrastructure and
  pagination — later Phase 11 platform/observability work;
- CMMChat and CMM Bots consumption of the backend — after Phase 11.3.

Details, including the frozen `/v1` surface, the public error model, the
idempotency and session-revision semantics, the SSE contract, the OpenAPI gate
and the recorded deviations, are in
[`docs/reference/phase-11-application-backend.md`](phase-11-application-backend.md).

## 11. Phase 11.4 — CLI current status

Sections 5, 6, 8, 9 and 10 record the closed Phase 11.34 Provider Registry and
the closed Phase 11.1, Phase 11.2 and Phase 11.3 subphases and are not modified
by Phase 11.4. The Phase 11.4 CLI is a separate subphase and is reported here in
its pre-audit state:

```text
PHASE11_4=CLOSED

F11_018=VERIFIED_EXISTING
DP_104=VERIFIED_EXISTING
AT_DP_104=PASS

AT_DP_103=PASS
AT_DP_102=PASS
AT_DP_101=PASS
AT_DP_134=PASS

PHASE11_3=CLOSED
PHASE11_2=CLOSED
PHASE11_1=CLOSED
PHASE11_34=CLOSED

CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=PENDING_INDEPENDENT_AUDIT
NEXT=INDEPENDENT_AUDIT
```

Phase 11.4 introduces exactly one new requirement identifier (`F11-018`), one
Design Point (`DP-104`), one connected acceptance test (`AT-DP-104`) and seven
new presentation modules under `cmm/`. It owns one public front door — the
existing `cmm = "cmm.cli:main"` console script over the existing root `argparse`
tree — and no command registry, command router, command bus, CLI service
locator, CLI runtime, CLI state store, CLI history store or second parser root.

Operationally available in this build: `status`, `doctor`, `ask` and `chat`.
The remaining 25 frozen command identities across the roadmap families are
reserved and fail closed with `CAPABILITY_UNAVAILABLE` (exit code `5`) without
starting the platform or fabricating a result. No plugin system, backup engine,
restore engine, migration engine, metrics backend, observability backend,
logging service, Goal subsystem, approval system, workflow engine, memory
engine, knowledge store, configuration authority, provider registry or model
gateway is introduced by Phase 11.4.

Phase 11.4 does not reopen Phase 11.1, Phase 11.2, Phase 11.3 or Phase 11.34. Its
only changes inside the closed `cmm/application/` package are the sanctioned
compatibility and composition additions: the transport-neutral
`ApplicationChannel` field on the public request contract (defaulting to `API`),
the application-to-orchestration channel mapping in `RequestApplicationService`,
channel forwarding through `ApplicationGateway`, the canonical local application
runtime composition helper, and the public exports those require. No domain,
agent, provider, workflow, session, orchestration or platform authority changed
semantics.

Deferred Phase 11.4 items recorded with this requirement (implemented nowhere,
not silently pulled forward):

- goals, workflows, approvals, memory, knowledge, domains, plugins, backup,
  restore, migrate, logs, metrics and configuration commands — reserved and
  fail-closed until canonical owners exist;
- `config show` redaction — withheld until safe redaction can be guaranteed from
  a canonical owner;
- request cancellation, streaming output, file-attachment ingestion, multimodal
  input, `--output-file`, shell completion and confirmation prompts — out of
  scope for the CLI phase;
- CMMChat, web/desktop/mobile UI and bot workspaces — later product surfaces; the
  CLI is one client/adapter surface;
- the experimental `ClineCliProvider` concept in Model Gateway planning — a
  different artifact from the CMM OS user-facing CLI.

Implementation decisions, the frozen command table, exit codes, output formats
and the observed pre-audit evidence are in
[`docs/reference/phase-11-cli.md`](phase-11-cli.md).


### Final Phase 11.4 closure evidence

Phase 11.4 — CLI is closed after Independent Re-audit V1 `PASS`.

```text
PHASE11_4=CLOSED
INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V1=PASS
BLOCKERS=0
MAJORS=0
MINORS=0
MINOR_01=VERIFIED_REMEDIATED
F11_018=VERIFIED_EXISTING
DP_104=VERIFIED_EXISTING
AT_DP_104=PASS
AT_DP_103=PASS
AT_DP_102=PASS
AT_DP_101=PASS
AT_DP_134=PASS
AUDITED_HEAD=1d6208d3ad849a0d59e5e4c85f63f36a331557d9
AUDITED_TREE=65f897686a1509e0bf889eb33c665bda51486337
REAUDIT_BUNDLE_SHA256=7086611069256b01c13a007f64584343382b39c66cef75cd2a2e601ab5ad5a26
AUDIT_V1_REPORT_COMMIT=22b240ec0ebd9fb81958905ec02414d525efba99
REAUDIT_V1_REPORT_COMMIT=0aae35764d74eb992db9c7af96f2086d0933d821
CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=CLOSED_AFTER_INDEPENDENT_REAUDIT_V1_PASS
NEXT=VERIFY_CLOSURE_COMMIT_THEN_INSPECT_PHASE11_5_CONVERSATIONAL_INTERFACE
```

Historical Audit V1 `FAIL` remains preserved in
`docs/audits/phase-11.4-cli-independent-audit-v1.md`. Final independent
Re-audit V1 `PASS` is recorded in
`docs/audits/phase-11.4-cli-independent-reaudit-v1.md`.

## 12. Phase 11.5 — Conversational Interface current status

Sections 5–11 record the closed Phase 11.34 Provider Registry and the closed
Phase 11.1–11.4 subphases and are not modified by Phase 11.5. The Phase 11.5
conversational interface is a separate subphase and is reported here in its
pre-audit state:

```text
PHASE11_5=IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT

F11_019=IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT
DP_105=IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT
AT_DP_105=GREEN_IN_REPOSITORY

CLOSURE_ELIGIBLE=NO
AUDIT_STATUS=PENDING_INDEPENDENT_AUDIT
NEXT=INDEPENDENT_AUDIT
```

Phase 11.5 introduces exactly one new requirement identifier (`F11-019`), one
Design Point (`DP-105`), one connected acceptance test (`AT-DP-105`) and one new
package (`cmm/conversation/`, 8 modules). It owns one new persistence
*translation* — the versioned, namespaced `conversation.v1` extension of the
canonical shared session — and no second session system, conversation store,
conversation repository, conversation runtime, conversation engine, conversation
router, conversation planner, conversation approval manager, conversation
permission engine, conversation memory store, conversation knowledge store,
conversation provider registry, conversation agent runtime, conversation
workflow engine or active-request registry. The canonical `SessionStore` remains
the only persistence authority, the canonical `ApplicationGateway` remains the
only application-facing submission path, and the canonical Phase 11.2
`Orchestrator` remains the only routing path.

The Phase 11.5 production surface is the new `cmm/conversation/` package plus
strictly additive seams in the closed packages: the
`ApplicationChannel.CONVERSATION` value and its one-to-one mapping to the
pre-existing `OrchestrationChannel.CONVERSATION`, the canonical local-runtime
`session_store` reference, and the optional `conversation` keyword with the five
additive `/v1/conversations/...` routes in the HTTP adapter. No Phase 11.1–11.4
production semantics were reopened; the closed-phase test surfaces touched are
the two additive architecture-gate seams and the exact-set/allowlist pins listed
in §4.12, every one of them additive.

At this baseline the conversational capability truth is deliberately honest:
`response_streaming` is `degraded` with the effective mode
`response_event_stream` (no provider token-streaming runtime exists),
`request_cancellation` is `unavailable` with reason `NO_CANCELLABLE_OWNER` (the
canonical cancellation answer stays `CAPABILITY_UNAVAILABLE`), `document_upload`
is `unavailable` with reason `NO_CANONICAL_STORAGE_OWNER`, attachments are
`reference_only` and a Bot association is `opaque_non_authoritative`.

Deferred Phase 11.5 items recorded with this requirement (implemented nowhere,
not silently pulled forward):

- CMMChat and every client application surface;
- the CMM Bots runtime, Bot registry and Bot identity/configuration layer;
- the conversation file workspace, global artifact library, object storage,
  file version history and global file search;
- document upload/ingestion;
- the Model Gateway, provider registry redesign, provider token-streaming
  runtime, Web Search, Browser Use and Computer Use ownership;
- the cancellable-request runtime, active-request registry and background
  worker systems;
- a generalized conversation branch/version-control system;
- conversation import/export, communication profiles, audio ingestion and the
  later Phase 11.55–11.59 subphases;
- authentication/authorization systems and the general storage architecture of
  the later Phase 11 subphases.

The implemented surface, the `conversation.v1` extension semantics, the
`ConversationService` public API, the capability truth table, the HTTP routes
and the measured architecture-gate residual limits are documented in
[`docs/reference/phase-11-conversational-interface.md`](phase-11-conversational-interface.md).
No closure, verification or closure-eligibility claim is made for Phase 11.5 in
this section; an independent audit must examine the exact-HEAD implementation
first.
