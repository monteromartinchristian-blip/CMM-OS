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

Phase 11.22 records its post-audit state under the explicit marker
`REMEDIATED_AFTER_REAUDIT_V12_PENDING_INDEPENDENT_REAUDIT`: Independent Audit V1
returned `FAIL` (`BLOCKERS=0`, `MAJORS=4`, `MINORS=5`); Remediation V1 fixed all
nine of those findings under strict TDD with adversarial regressions; Independent
Re-audit V2 verified all nine as remediated
(`AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED`) and returned `FAIL` with exactly four
new majors (`BLOCKERS=0`, `MAJORS=4`, `MINORS=0`); Remediation V2 fixed exactly
those four under strict TDD with adversarial regressions; Independent Re-audit V3
verified all nine Audit V1 findings and all four Re-audit V2 reproductions as fixed
(`9/9_VERIFIED`, `4/4_VERIFIED`) and returned `FAIL` with exactly two majors and one
minor (`BLOCKERS=0`, `MAJORS=2`, `MINORS=1`); Remediation V3 fixed exactly those
three under strict TDD with adversarial regressions; Independent Re-audit V4
verified all three Re-audit V3 reproductions as fixed
(`3/3_VERIFIED`) and returned `FAIL` with exactly three majors
(`BLOCKERS=0`, `MAJORS=3`, `MINORS=0`); Remediation V4 fixed exactly those three
under strict TDD with adversarial regressions; Independent Re-audit V5 verified
those three as fixed (`3/3_VERIFIED`) and preserved `279` prior remediation
regressions, then returned `FAIL` with exactly three new majors
(`BLOCKERS=0`, `MAJORS=3`, `MINORS=0`); Remediation V5 fixed exactly those three
under strict TDD with adversarial regressions; Independent Re-audit V6 verified
those three as fixed (`3/3_VERIFIED`) and preserved `350` prior remediation
regressions, then returned `FAIL` with exactly three new majors and one new minor
(`BLOCKERS=0`, `MAJORS=3`, `MINORS=1`); Remediation V6 fixed exactly those four
under strict TDD with adversarial regressions; Independent Re-audit V7 verified
all four V6 findings as fixed (`4/4_VERIFIED`) and preserved `477` prior
remediation regressions, then returned `FAIL` with exactly two new majors and no
minors (`BLOCKERS=0`, `MAJORS=2`, `MINORS=0`); Remediation V7 fixed exactly those
two under strict TDD with adversarial regressions; Independent Re-audit V8 verified
both V7 findings as fixed (`2/2_VERIFIED`) and preserved `604` prior remediation
regressions, then returned `FAIL` with exactly two new majors and one new minor
(`BLOCKERS=0`, `MAJORS=2`, `MINORS=1`); Remediation V8 fixed exactly those three
under strict TDD with adversarial regressions; Independent Re-audit V9 verified
both V8 findings as fixed (`2/2_VERIFIED`) and preserved `604` prior remediation
regressions, then returned `FAIL` with exactly two new majors and one new minor
(`BLOCKERS=0`, `MAJORS=2`, `MINORS=1`); Remediation V9 fixed exactly those three
under strict TDD with adversarial regressions; Independent Re-audit V10 verified all
three V9 findings as fixed (`3/3_VERIFIED`) and preserved `1290` prior remediation
regressions, then returned `FAIL` with exactly one new major, no minors and no
blockers (`BLOCKERS=0`, `MAJORS=1`, `MINORS=0`,
`MAJOR_V10_001=WRAPPED_WINDOWS_DRIVE_ROOT_REFERENCE_BYPASSES_PUBLIC_ROOT_FILESYSTEM_CLASSIFIER`);
Remediation V10 fixed exactly that finding under strict TDD with adversarial
regressions; Independent Re-audit V11 verified the V10 finding as fixed
(`1/1_VERIFIED`) and preserved `1765` prior remediation regressions, then returned
`FAIL` with exactly one new major, no minors and no blockers
(`BLOCKERS=0`, `MAJORS=1`, `MINORS=0`,
`MAJOR_V11_001=WINDOWS_DRIVE_RELATIVE_REFERENCE_BYPASSES_CANONICAL_FILESYSTEM_CLASSIFIER_AND_PERSISTS`);
Remediation V11 fixed exactly that finding under strict TDD with adversarial
regressions; Independent Re-audit V12 verified the V11 finding as fixed
(`1/1_VERIFIED`) and preserved `2473` prior remediation regressions, then returned
`FAIL` with exactly one new major, no minors and no blockers
(`BLOCKERS=0`, `MAJORS=1`, `MINORS=0`,
`MAJOR_V12_001=WINDOWS_SENSITIVE_PRIVATE_FILENAME_EQUIVALENTS_BYPASS_CANONICAL_FILESYSTEM_CLASSIFIER_AND_PERSIST`);
Remediation V12 fixed exactly that finding under strict TDD with adversarial
regressions, and the independent re-audit of the exact-HEAD V13 bundle is still
pending. It is the same state as `IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT`, is not a
closure and is not a verification claim.

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
| Next step | fresh independent ChatGPT re-audit of the exact-HEAD Phase 11.22 V13 bundle (`phase-11.22-event-system-audit-v13.tar.gz`); Phase 11.22 is not closed, not independently verified and not complete; Phase 11.23 and Phase 11.24 are **not** begun |

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
| Next step | fresh independent ChatGPT re-audit of the exact-HEAD Phase 11.22 V13 bundle (`phase-11.22-event-system-audit-v13.tar.gz`); Phase 11.22 is not closed, not independently verified and not complete; Phase 11.23 and Phase 11.24 are **not** begun |

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
| `F11-019` | Canonical Conversational Interface. CMM OS shall expose one canonical, version-aware, interface-neutral, fail-closed conversational boundary that provides persistent multi-turn natural interaction over canonical shared sessions; uses the existing Phase 11.3 `ApplicationGateway` for application-facing message submission and reaches the canonical Phase 11.2 `Orchestrator` rather than implementing alternate routing; consumes existing authorized Domain Intelligence interface projections rather than reconstructing domain state; preserves canonical session revision and optimistic-concurrency semantics; supports safe public conversational messages, responses and versioned contracts; exposes requested versus effective conversational capabilities; exposes authorized context, domain, source, question, workflow, action, approval, result, contradiction, warning and memory-proposal references when available; supports auditable editing and controlled regeneration without destructive transcript rewriting; represents attachment/document references without creating a parallel file authority; exposes streaming and cancellation truthfully according to canonical effective capability; keeps normal conversation usable without Bot or Agent binding and treats optional Bot identifiers as non-authoritative; leaks no hidden reasoning, secrets, raw sensitive context, internal exceptions, credentials or unauthorized references; remains consumable by CMMChat and alternative clients through stable contracts; and introduces no parallel stores, engines, runtimes, registries, routers, planners, approval managers, permission engines, memory systems, knowledge systems, provider systems or session systems. | `SRC-R11` (detailed Phase 11 roadmap §11.5); `docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md` §3–§7, §25–§26 | Phase 11.5 | `cmm/conversation/__init__.py`; `contracts.py`; `errors.py`; `state.py`; `capabilities.py`; `projection.py`; `service.py`; `platform_module.py`; `cmm/application/contracts.py`; `cmm/application/requests.py`; `cmm/application/local_runtime.py`; `cmm/api/app.py`; `cmm/api/models.py` | `VERIFIED_EXISTING` | `AT-DP-105` — `tests/conversation/test_phase11_5_dp105_acceptance.py` |

### 4.12 `F11-019` traceability

| Item | Value |
|---|---|
| Requirement | `F11-019 — Canonical Conversational Interface` |
| Design Point | `DP-105 — Session-Backed Canonical Conversation Boundary` |
| Acceptance test | `AT-DP-105 — Canonical Conversational Interaction Acceptance` — `tests/conversation/test_phase11_5_dp105_acceptance.py` |
| Production package | `cmm/conversation/` (8 modules: `__init__.py`, `contracts.py`, `errors.py`, `state.py`, `capabilities.py`, `projection.py`, `service.py`, `platform_module.py`) |
| Additive seams in closed packages | `cmm/application/contracts.py` (`ApplicationChannel.CONVERSATION`); `cmm/application/requests.py` (channel mapping); `cmm/application/local_runtime.py` (canonical `session_store` reference); `cmm/api/app.py` (optional `conversation` keyword and the five conversation routes); `cmm/api/models.py` (conversation transport DTOs) |
| Focused suite | `tests/conversation/` (860 tests at the Remediation V2 implementation state) |
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
| Mapping status | `VERIFIED_EXISTING` |
| Next step | fresh independent ChatGPT re-audit of the exact-HEAD Phase 11.22 V13 bundle (`phase-11.22-event-system-audit-v13.tar.gz`); Phase 11.22 is not closed, not independently verified and not complete; Phase 11.23 and Phase 11.24 are **not** begun |

`F11-019` is `VERIFIED_EXISTING` and
`DP_105` is implemented in production architecture after Remediation V2 — which
followed the independent Re-audit V1 `INDEPENDENT_REAUDIT_V1=FAIL_RECORDED`
(`BLOCKERS=0`, `MAJORS=1`, `MINORS=2`; the five original Audit V1 findings
independently verified as remediated) — and after the original
`INDEPENDENT_AUDIT_V1=FAIL_RECORDED`; `AT-DP-105` passes in this repository.
Final closure, verification and closure eligibility are recorded for Phase 11.5 after Independent Re-audit V2 `PASS`
before an independent re-audit returns its evidence. The pre-audit state, the
implemented surface, the capability truth table and the recorded residual limits
are documented in
[`docs/reference/phase-11-conversational-interface.md`](phase-11-conversational-interface.md).

### 4.13 `F11-020` — Canonical Provider-Independent Model Gateway

`F11-001` … `F11-013` remain owned by the Phase 10 matrix, `F11-014` is owned
by §4.1, `F11-015` by §4.3, `F11-016` by §4.5, `F11-017` by §4.7, `F11-018`
by §4.9 and `F11-019` by §4.11 of this document. `F11-020` is the next
non-colliding Phase 11 functional identifier, assigned to Phase 11.21 — Model
Gateway. Its pre-audit mapping status is `IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT`:
the implementation exists in this repository and the connected acceptance is
green here, while no independent audit has examined it yet.

| `requirement_id` | Normative requirement | Source | Phase | Production owners | Mapping status | Acceptance test |
|---|---|---|---|---|---|---|
| `F11-020` | Canonical Provider-Independent Model Gateway. CMM OS shall expose exactly one canonical provider-independent model-call execution boundary that consumes the exact Phase 11.34 `ProviderRegistry` and the canonical `ModelCatalog`; validates explicit model, capability, reasoning-effort and input-modality requirements before provider I/O; preserves explicit user model selection without silent substitution; preserves explicit reasoning effort without silent downgrade or upgrade; transports real authorized image and PDF/document content rather than filenames or attachment metadata; normalizes tool declarations and tool calls without executing tools; normalizes provider token streaming with exactly one terminal event and no hidden reasoning; supports bounded timeout, cooperative model-call cancellation and bounded transport retry; executes only an explicitly authorized, requirement-preserving fallback sequence; enforces canonical privacy before remote egress so that `LOCAL_ONLY` plus a remote provider is denied before any provider call and approval cannot widen a refusal; returns factual usage, cost and latency facts with unknown metrics left unknown; emits safe model-call evidence through an injected seam; is composed through the Phase 11.1 root; and introduces no parallel provider registry, model catalog, routing policy engine, privacy engine, validation engine, tool executor, conversation or session store, application backend, event bus or persistent model store. | `SRC-R11` (detailed Phase 11 roadmap §11.21); `docs/superpowers/specs/2026-09-25-phase-11.21-model-gateway-design.md` §3–§24; `docs/superpowers/plans/2026-09-25-phase-11.21-model-gateway-implementation-plan.md` | Phase 11.21 | `kernel/llm/model_gateway.py`; `model_gateway_contracts.py`; `model_gateway_errors.py`; `model_provider_adapter.py`; `model_streaming.py`; `cmm/agent_runtime/model_egress_privacy_adapter.py`; `cmm/agent_runtime/model_fallback_gateway_adapter.py`; `cmm/agent_runtime/model_execution_evidence_projection.py`; `cmm/platform/canonical.py` (`model_gateway_binding`) | `IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT` | `AT-DP-121` — `tests/llm/test_phase11_21_dp121_acceptance.py` |

### 4.14 `F11-020` traceability

| Item | Value |
|---|---|
| Requirement | `F11-020 — Canonical Provider-Independent Model Gateway` |
| Design Point | `DP-121 — Canonical Provider-Independent Model Gateway` |
| Acceptance test | `AT-DP-121 — Canonical Provider-Independent Model Gateway Acceptance` — `tests/llm/test_phase11_21_dp121_acceptance.py` |
| Production package | `kernel/llm/` (5 modules: `model_gateway.py`, `model_gateway_contracts.py`, `model_gateway_errors.py`, `model_provider_adapter.py`, `model_streaming.py`) plus `cmm/agent_runtime/` (3 modules: `model_egress_privacy_adapter.py`, `model_fallback_gateway_adapter.py`, `model_execution_evidence_projection.py`) |
| Additive seams in closed packages | `kernel/llm/capabilities.py` (`ReasoningEffort`; `ModelCapabilities.reasoning_efforts`, `document_media_types`, `streaming`, all defaulted to unknown/unsupported); `cmm/platform/canonical.py` (`PROVIDER_REGISTRY_CONTRACT_VERSION`, `_provider_registry_dependency`, `model_gateway_binding`); `cmm/platform/__init__.py` (export of that builder). `kernel/llm/__init__.py` is deliberately unchanged: Phase 11.21 adds no new `kernel.llm` package export. |
| Focused suite | 16 `tests/llm/test_model_gateway_*.py` modules plus `tests/llm/test_phase11_21_dp121_acceptance.py` (404 passed at the Remediation V2 exact HEAD) |
| Adapter and projection suites | `tests/platform/test_model_gateway_binding.py`; `tests/agent_runtime/test_model_egress_privacy_adapter.py`; `tests/agent_runtime/test_model_fallback_gateway_adapter.py`; `tests/agent_runtime/test_model_execution_evidence_projection.py` |
| Architecture/anti-fragmentation gate | `tests/llm/test_model_gateway_architecture.py`; Scenario M of `AT-DP-121`; inherited `tests/platform/test_architecture.py`, `tests/application/test_architecture.py`, `tests/api/test_architecture.py`, `tests/domains/test_domain_core_conformance_architecture.py` |
| Reference documentation | `docs/reference/phase-11-model-gateway.md` |
| Design specification | `docs/superpowers/specs/2026-09-25-phase-11.21-model-gateway-design.md` |
| Implementation plan | `docs/superpowers/plans/2026-09-25-phase-11.21-model-gateway-implementation-plan.md` |
| Historical independent Audit V1 | `docs/audits/phase-11.21-model-gateway-independent-audit-v1.md` — immutable `FAIL`; `BLOCKERS=0`; `MAJORS=5`; `MINORS=1` |
| Historical independent Re-audit V2 | `docs/audits/phase-11.21-model-gateway-independent-reaudit-v2.md` — immutable `FAIL`; `BLOCKERS=0`; `MAJORS=1`; `MINORS=0`; `PROCESS_DEVIATIONS=1`; residual `MAJOR_01=AUTO_REMOTE_EGRESS_PRECHECK_STILL_ABORTS_BEFORE_VALID_LOCAL_CANDIDATE_WHEN_PRIVACY_METADATA_IS_ABSENT` |
| Remediation V1 design | `docs/superpowers/specs/2026-09-25-phase-11.21-remediation-v1-design.md` |
| Remediation V1 plan | `docs/superpowers/plans/2026-09-25-phase-11.21-remediation-v1-implementation-plan.md` |
| Remediation V2 design | `docs/superpowers/specs/2026-09-25-phase-11.21-remediation-v2-design.md` — freezes the candidate-local `AUTO` egress ruling for the one residual Re-audit V2 finding |
| Remediation V2 plan | `docs/superpowers/plans/2026-09-25-phase-11.21-remediation-v2-implementation-plan.md` |
| Remediation V2 production owner | `kernel/llm/model_gateway.py` — the candidate-set-wide `_require_egress_authority(...)` AUTO precheck is removed; egress/privacy authority is evaluated only inside the per-candidate hard gate |
| Remediation V2 regression tests | `tests/llm/test_model_gateway_execution.py` (six focused `AUTO`/explicit egress tests); `tests/llm/test_phase11_21_dp121_acceptance.py` (Scenario S — `AUTO` mixed remote/local without privacy metadata) |
| Reused canonical owners | Phase 11.34 `ProviderRegistry` and canonical `ModelCatalog` (exact instances); `kernel.llm.model_selection` / `model_router` (`ModelRequirements`, `RoutingCandidate`); `cmm.agent_runtime.model_fallback_contracts` / `model_fallback_decision_engine`; `cmm.agent_runtime.model_execution_contracts`; `cmm.cognitive.privacy.evaluate_privacy_operation`; Phase 11.1 `ApplicationContainer` / `ServiceBinding` / `StaticCompositionModule` |
| Platform service identity | `model.gateway` (owner `kernel.llm`, mode `local`, no authority claim, single dependency edge `provider.registry`) |
| Inherited requirements reused | `F11-019` / `DP-105`, `F11-018` / `DP-104`, `F11-017` / `DP-103`, `F11-016` / `DP-102`, `F11-015` / `DP-101` and `F11-014` / `DP-134` — referenced, **not reopened and not modified** |
| Inherited acceptance regressions | `AT-DP-134` — `tests/llm/test_provider_registry_dp134_acceptance.py` (68 passed); `AT-DP-101` — `tests/platform/test_phase11_1_dp101_acceptance.py` (31 passed); `AT-DP-102` — `tests/orchestration/test_phase11_2_dp102_acceptance.py` (33 passed); `AT-DP-103` — `tests/application/test_phase11_3_dp103_acceptance.py` (47 passed); `AT-DP-104` — `tests/cli/test_phase11_4_dp104_acceptance.py` (69 passed); `AT-DP-105` — `tests/conversation/test_phase11_5_dp105_acceptance.py` (1 passed) |
| Repository-wide Ruff | 837 findings — identical to the inspected pre-phase baseline; Phase 11.21 introduces zero new findings and every touched file is Ruff- and format-clean |
| Mapping status | `IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT` |
| Next step | fresh independent ChatGPT re-audit of the exact-HEAD Phase 11.22 V13 bundle (`phase-11.22-event-system-audit-v13.tar.gz`); Phase 11.22 is not closed, not independently verified and not complete; Phase 11.23 and Phase 11.24 are **not** begun |

### 4.15 `F11-021` — Reusable First-Party Backend Interface

`F11-001` … `F11-013` remain owned by the Phase 10 matrix, `F11-014` is owned
by §4.1, `F11-015` by §4.3, `F11-016` by §4.5, `F11-017` by §4.7, `F11-018`
by §4.9, `F11-019` by §4.11 and `F11-020` by §4.13 of this document. `F11-021`
is the next non-colliding Phase 11 functional identifier, assigned to Phase
11.50 — Reusable Backend Interfaces. Independent Audit V1 examined the
implementation and returned `INDEPENDENT_AUDIT_V1=FAIL` with `BLOCKERS=0`,
`MAJORS=5`, `MINORS=1` and `DP_150=NOT_VERIFIED`; Remediation V1 corrected exactly
those findings. Independent Re-audit V2 then returned `INDEPENDENT_REAUDIT_V2=FAIL`
with `BLOCKERS=0`, `MAJORS=1`, `MINORS=0` — V1 MAJOR-01/03/04/05 and MINOR-01
`VERIFIED_REMEDIATED`, with one residual defect: the exact `client.backend`
composition identity was enforced only by the convenience builder and could be
bypassed by a hand-built canonical `ServiceBinding`
(`CLIENT_BACKEND_SUBCLASS_HAND_BUILT_BINDING=ACCEPTED`); Remediation V2 corrected
that defect by making the exact rule authoritative in the Phase 11.1 registry.
The `IMPLEMENTED_REMEDIATION_V2_PENDING_INDEPENDENT_REAUDIT` status is superseded:
Independent Re-audit V3 examined the Remediation V2 state and returned
`INDEPENDENT_REAUDIT_V3=FAIL` with `BLOCKERS=0`, `MAJORS=1`, `MINORS=0`. The one
residual defect was

```text
MAJOR_V3_01=
EXACT_CLIENT_BACKEND_IDENTITY_REMAINS_CALLER_ASSERTED_BECAUSE_A_HAND_BUILT_BINDING_CAN_REPLACE_THE_RUNTIME_CONTRACT_AND_BYPASS_THE_EXACT_MARKER
```

because the V2 rule derived the effective exactness from
`ServiceBinding.runtime_contract`, a field of the very binding it was validating:
keeping the canonical `client.backend` descriptor and service ID while replacing
only that field restored acceptance, on `register()` and on `replace()` alike.
Remediation V3 corrects exactly that one residual defect, moving the authoritative
runtime identity of the configured canonical service onto the existing Phase 11.1
`ServiceExpectation` configuration path. Independent Re-audit V4 examined the
exact Remediation V3 state and returned `PASS` with `BLOCKERS=0`, `MAJORS=0`,
`MINORS=0`, `F11_021=VERIFIED_EXISTING`, `DP_150=VERIFIED_EXISTING`,
`AT_DP_150=PASS` and `CLOSURE_ELIGIBLE=YES`. The canonical mapping status is now
`VERIFIED_EXISTING`.

| `requirement_id` | Normative requirement | Source | Phase | Production owners | Mapping status | Acceptance test |
|---|---|---|---|---|---|---|
| `F11-021` | Reusable First-Party Backend Interface. CMM OS shall expose exactly one reusable, versioned, transport-neutral first-party client backend interface over the already-closed Phase 11.3 `ApplicationGateway` and Phase 11.5 `ConversationService`; shall require the exact canonical owner types and refuse arbitrary duck-typed replacements and an incoherent gateway pair; shall validate its own interface version and closed operation set and fail closed with zero downstream owner calls on an unsupported version or unknown operation, never routing an operation by string, service name, import path or callable; shall delegate every session operation to the canonical application session boundary and every conversation operation to the exact canonical `ConversationService` without reimplementing orchestration, lineage, retry or persistence; shall reuse canonical public contracts rather than creating semantic copies; shall expose one immutable capability projection whose rows derive only from canonical `ApplicationCapability` and `ConversationCapabilityState` evidence and explicitly injected Phase 11.21 model-boundary declarations, distinguishing model-boundary availability (`boundary_only`) from end-to-end availability, never relabelling a response-event stream as a token stream, and never optimistically upgrading cancellation, multimodal, reasoning-effort or token-stream truth; shall map every failure safely with no traceback, repr, secret, path or hidden reasoning; shall introduce no second application gateway, conversation service, orchestrator, model gateway, provider registry, model catalog, session store, conversation store, router, runtime, engine, registry, repository, resolver, service locator, HTTP server or event bus; and shall compose through the Phase 11.1 root as one `client.backend` service binding whose dependencies point only at the canonical application and conversational services. | `SRC-R11` (detailed Phase 11 roadmap §11.50); `docs/superpowers/specs/2026-09-25-phase-11.50-reusable-backend-interfaces-design.md` §3–§43; `docs/superpowers/plans/2026-09-25-phase-11.50-reusable-backend-interfaces-implementation-plan.md` | Phase 11.50 | `cmm/client_backend/__init__.py`; `contracts.py`; `capabilities.py`; `interface.py`; `platform_module.py`; `cmm/conversation/service.py` (`uses_application_gateway` narrowed non-authoritative coherence evidence; `capability_resolver` reviewed and kept) | `VERIFIED_EXISTING` | `AT-DP-150` — `tests/client_backend/test_phase11_50_dp150_acceptance.py` |

### 4.16 `F11-021` traceability

| Item | Value |
|---|---|
| Requirement | `F11-021 — Reusable First-Party Backend Interface` |
| Design Point | `DP-150 — Canonical Reusable Client Backend Interface` |
| Acceptance test | `AT-DP-150 — Canonical Reusable Client Backend Interface Acceptance` — `tests/client_backend/test_phase11_50_dp150_acceptance.py` |
| Production package | `cmm/client_backend/` (5 modules: `__init__.py`, `contracts.py`, `capabilities.py`, `interface.py`, `platform_module.py`) |
| Seams in closed packages after Remediation V1 | `cmm/conversation/service.py` — `uses_application_gateway(gateway) -> bool`, the **narrowed** form of the additive Phase 11.50 owner accessor: immutable, non-authoritative coherence evidence that returns no owner, no entrypoint and no callable (Audit V1 MAJOR-01 removed `ConversationService.gateway`, which handed back the live `ApplicationGateway` and therefore its `handle(...)` entrypoint). `capability_resolver` was reviewed and **kept**: it is an independently closed canonical Phase 11.5 public contract whose only public operation returns immutable declarative `ConversationCapabilityState` values, and it grants no authority. No replacement public owner accessor exists; `ClientBackend` exposes no live owner and no generic service locator. `cmm/application/gateway.py` is unchanged. |
| Frozen interface version | `CLIENT_BACKEND_INTERFACE_VERSION = "1"` — identifies the facade contract only; replaces no canonical version |
| Closed operation set | `ClientOperation` — `CAPABILITIES`, `CREATE_SESSION`, `GET_SESSION`, `LOAD_CONVERSATION`, `SUBMIT_MESSAGE`, `EDIT_MESSAGE`, `REGENERATE_RESPONSE`, `CANCEL_REQUEST` |
| Closed client error set | `ClientBackendErrorCode` — `UNSUPPORTED_INTERFACE_VERSION`, `INVALID_CLIENT_OPERATION`, `INVALID_CLIENT_CONTRACT`, `INTERNAL_CLIENT_ERROR`; no canonical application or conversational code is duplicated. Since Remediation V1 (Audit V1 MAJOR-03) `ClientBackendError` also preserves a **known canonical downstream failure verbatim** through `from_canonical(code, message)`: the canonical `RESOURCE_NOT_FOUND`/`CONFLICT`/`SESSION_CONFLICT`/`CAPABILITY_UNAVAILABLE`/`POLICY_DENIED`/`APPROVAL_REQUIRED`/`CANCELLED`/`INVALID_REQUEST`/`UNSUPPORTED_VERSION` identity is kept on the real typed and `dispatch` paths, while a canonical internal failure or an unknown exception still becomes `INTERNAL_CLIENT_ERROR` with no raw text. The preserved code must be a real member of the canonical closed taxonomy, so no third taxonomy is created |
| Capability vocabulary | `ClientBackendCapabilityStatus` — `available`, `degraded`, `unavailable`, `boundary_only` (four closed states, no ambiguous booleans) |
| Capability field inventory | `interface_version`; `application_api_version`; `session_create`; `session_get`; `conversation_load`; `conversation_submit`; `conversation_edit`; `conversation_regenerate`; `response_event_stream`; `request_cancellation`; `attachments`; `attachment_effective_mode`; `document_upload`; `model_boundary_reasoning`; `model_boundary_multimodal`; `model_boundary_token_stream`; `end_to_end_reasoning`; `end_to_end_multimodal`; `end_to_end_token_stream` |
| Focused suite | `tests/client_backend/` — `test_contracts.py`, `test_interface.py`, `test_capabilities.py`, `test_platform_module.py`, `test_architecture.py`, `test_phase11_50_dp150_acceptance.py`, plus the test-only helper `_canonical_graph.py` (216 passed at the Remediation V3 HEAD; 192 at the Remediation V2 HEAD) |
| Architecture/anti-fragmentation gate | `tests/client_backend/test_architecture.py` (parallel-authority, forbidden-import, per-module seam pin, reverse-dependency, dynamic-import, service-locator, filesystem/network, hidden-reasoning gates); Scenario H of `AT-DP-150`; additive closed-phase allowlist seams in `tests/application/test_architecture.py` and `tests/platform/test_architecture.py` |
| Reference documentation | `docs/reference/phase-11-reusable-backend-interfaces.md` |
| Design specification | `docs/superpowers/specs/2026-09-25-phase-11.50-reusable-backend-interfaces-design.md` |
| Implementation plan | `docs/superpowers/plans/2026-09-25-phase-11.50-reusable-backend-interfaces-implementation-plan.md` |
| Reused canonical owners | Phase 11.3 `ApplicationGateway` (one public `handle` entrypoint) and its `SessionApplicationService` session boundary; Phase 11.5 `ConversationService` (`load`, `submit`, `edit`, `regenerate`, `cancel`) and `ConversationCapabilityResolver`; Phase 11.2 `Orchestrator` reached only *through* the gateway; Phase 11.1 `ServiceBinding` / `StaticCompositionModule` / `ContractMetadata` |
| Platform service identity | `client.backend` (module `phase11.client-backend`, owner `cmm.client_backend`, mode `local`, authority `client-backend-public-facade`, runtime contract `cmm.client_backend.interface.ClientBackend` with `runtime_contract_match=exact_type` and the private `__cmm_exact_runtime_contract__` marker, dependency edges `application.gateway` and `conversation.service` only). Since Remediation V3 the authoritative runtime identity is the canonical `ServiceExpectation` from `client_backend_service_expectation()` (`runtime_contract=ClientBackend`, `runtime_contract_match=EXACT_TYPE`) carried through `CompositionConfiguration.expected_contracts`; the binding's own `runtime_contract` is only a declaration that must agree, and the marker is defense in depth only |
| Deliberately absent platform dependency | `model.gateway` and `provider.registry` — the client never acquires model execution authority through composition; model-boundary capability facts travel as read-only declarations instead |
| Not exposed to clients | `kernel.llm.ModelGateway`, provider adapters, model selection/routing, raw `ModelCallCancellationToken`, `ModelGateway.stream()`, provider token streaming, image/document bytes, file upload, path resolution and URL download |
| CMMChat relationship | CMMChat is a first-party client and consumes this seam later; `CMMCHAT_CODE_CHANGES=NONE` in Phase 11.50 |
| Phase 11.51 boundary | `PHASE11_51=NOT_IMPLEMENTED` — no MCP, no OpenAI Actions, no external REST expansion, no Claude or ChatGPT adapter |
| Inherited requirements reused | `F11-020` / `DP-121`, `F11-019` / `DP-105`, `F11-018` / `DP-104`, `F11-017` / `DP-103`, `F11-016` / `DP-102`, `F11-015` / `DP-101` and `F11-014` / `DP-134` — referenced, **not reopened and not modified** |
| Inherited acceptance regressions | `AT-DP-134` — 68 passed; `AT-DP-121` — 38 passed; `AT-DP-101` — 31 passed; `AT-DP-102` — 33 passed; `AT-DP-103` — 47 passed; `AT-DP-104` — 69 passed; `AT-DP-105` — 1 passed; every file run as its own required gate command |
| Suite gate results at the implementation HEAD | `tests/application` — 674 passed; `tests/conversation` — 860 passed; `tests/llm` — 1153 passed; `tests/platform` + `tests/orchestration` + `tests/cli` — 2001 passed; `tests/api` + `tests/conversation` — 1054 passed; global `pytest -q` — 21940 passed, zero failures |
| Repository-wide Ruff | 837 findings — identical to the inspected pre-phase baseline; `RUFF_NEW_FINDINGS=0`; every touched file is `ruff check`- and `ruff format --check`-clean |
| Remediation V1 gate results | focused finding-specific selection — 31 passed; `tests/client_backend` — 182 passed; `AT-DP-150` run separately — 18 passed; inherited acceptances `AT-DP-134`/`AT-DP-121`/`AT-DP-101`/`AT-DP-102`/`AT-DP-103`/`AT-DP-104`/`AT-DP-105` — 287 passed; `tests/application` — 675 passed; `tests/conversation` — 860 passed; `tests/llm` — 1153 passed; `tests/platform` — 369 passed; `tests/orchestration` — 498 passed; `tests/cli` — 459 passed; global `pytest -q` — 21965 passed, 0 failed, 1 warning (the +25 over the audited implementation HEAD is exactly the `tests/client_backend` growth from 157 to 182); `RUFF_TOUCHED=PASS`; `FORMAT=PASS`; `COMPILEALL=PASS`; `GIT_DIFF_CHECK=PASS` |
| Other gates | `compileall` PASS over `cmm/client_backend`, `cmm/application`, `cmm/conversation`, `cmm/platform`, `cmm/orchestration`, `kernel/llm`; `git diff --check` PASS |
| Remediation V1 evidence | `AUDITED_HEAD=ed7bdc6f9c48ff94375613bb80c23ad10599710c`, `AUDITED_TREE=c065eb3d78ff19120a64b9e9eb1fff8311a59224`, `AUDITED_BUNDLE_SHA256=fa2ed501bdd5ba6ba87dfdbe713d12e3f37644bd200d73d598487be4862f3654`; `INDEPENDENT_AUDIT_V1=FAIL`, `BLOCKERS=0`, `MAJORS=5`, `MINORS=1`, `DP_150=NOT_VERIFIED`, `AT_DP_150=FAIL_INDEPENDENT`, `CLOSURE_ELIGIBLE=NO` |
| Remediation V1 result | `AUDIT_V1_MAJOR_01..05=IMPLEMENTED_PENDING_REAUDIT`; `PUBLIC_OWNER_ESCAPE_HATCH=ABSENT`; `HEALTH_GET_CLIENT_BYPASS=IMPOSSIBLE`; `APPLICATION_GATEWAY_SUBCLASS=REJECTED`; `CONVERSATION_SERVICE_SUBCLASS=REJECTED`; `CLIENT_BACKEND_SUBCLASS_BINDING=REJECTED`; `CANONICAL_NOT_FOUND=PRESERVED`; `CANONICAL_CONFLICT=PRESERVED`; `UNKNOWN_INTERNAL=INTERNAL_CLIENT_ERROR`; `ATTACHMENTS_STATUS=DEGRADED`; `ATTACHMENTS_MODE=reference_only`; `DOCUMENT_UPLOAD=UNAVAILABLE`; `RESPONSE_EVENT_STREAM=AVAILABLE`; `TOKEN_STREAM_FACTS_SEPARATE=YES`; `REQUEST_CANONICAL_PAYLOAD_JSON_SERIALIZABLE=PASS`; `RESULT_CANONICAL_PAYLOAD_JSON_SERIALIZABLE=PASS`; `OPAQUE_PAYLOAD=FAIL_CLOSED` |
| Remediation V2 authoritative gate | `cmm/platform/contracts.py` — `RuntimeContractMatch` (`INSTANCE_OF` default, `EXACT_TYPE` opt-in) and `ServiceBinding.runtime_contract_match` with fail-closed validation (`RuntimeContractMatch` only; `EXACT_TYPE` requires a real Python type); `cmm/platform/service_registry.py` — one shared effective-match helper where a contract-level `__cmm_exact_runtime_contract__ = True` marker upgrades any declared mode to `EXACT_TYPE`, used by both `register()` and `replace()`; `EXACT_TYPE` requires `type(implementation) is runtime_contract` with no `isinstance` fallback and fails closed for a non-type contract; `cmm/client_backend/interface.py` — the private marker on `ClientBackend`; `cmm/client_backend/platform_module.py` — the binding declares `runtime_contract_match=RuntimeContractMatch.EXACT_TYPE` while keeping the fail-fast `type(service) is ClientBackend` builder check; `cmm/platform/__init__.py` — public export of `RuntimeContractMatch` only. Platform core keeps no service-ID or authority special case, no `cmm.client_backend` import and no parallel policy registry; inherited Phase 11.1 `INSTANCE_OF` semantics (including the safely-uncheckable path) are unchanged. **Superseded in authority by Remediation V3**: the `RuntimeContractMatch` primitive and the marker remain, but the authoritative runtime identity of a configured canonical service is now the configured `ServiceExpectation`, not the caller-authored binding field |
| Remediation V2 gate results | focused four-file selection — 170 passed; `tests/client_backend` — 192 passed; `AT-DP-150` run separately — 21 passed; inherited acceptances `AT-DP-134`/`AT-DP-121`/`AT-DP-101`/`AT-DP-102`/`AT-DP-103`/`AT-DP-104`/`AT-DP-105` — 68/38/31/33/47/69/1 = 287 passed; `tests/platform` — 383 passed; `tests/application` — 675 passed; `tests/conversation` — 860 passed; `tests/llm` — 1153 passed; `tests/orchestration` — 498 passed; `tests/cli` — 459 passed; global `pytest -q` — 21989 passed, 1 warning, 0 failed (the +24 over the Remediation V1 HEAD is exactly the `tests/client_backend` growth from 182 to 192 plus the `tests/platform` growth from 369 to 383); `RUFF_TOUCHED=PASS`; `FORMAT=PASS`; `RUFF_GLOBAL=837`; `RUFF_NEW_FINDINGS=0`; `COMPILEALL=PASS`; `GIT_DIFF_CHECK=PASS` |
| Remediation V2 result | `MAJOR_V2_01=IMPLEMENTED_PENDING_REAUDIT`; `CLIENT_BACKEND_SUBCLASS_BUILDER_BINDING=REJECTED`; `CLIENT_BACKEND_SUBCLASS_HAND_BUILT_BINDING=REJECTED`; `CLIENT_BACKEND_SUBCLASS_REPLACEMENT=REJECTED`; `EXACT_CLIENT_BACKEND_HAND_BUILT_BINDING=ACCEPTED`; `EXACT_RUNTIME_CONTRACT_CANNOT_BE_DOWNGRADED=PASS`; `OMITTED_MATCH_CANNOT_DOWNGRADE_EXACT_CONTRACT=PASS`; `INHERITED_INSTANCE_OF_SEMANTICS=PRESERVED`; `PLATFORM_IMPORTS_CLIENT_BACKEND=NO`; `CLIENT_BACKEND_SPECIAL_CASE_IN_PLATFORM=ABSENT`; `PARALLEL_POLICY_REGISTRY=NO`; `AT-DP-150` Scenario A2 exercises the authoritative registry path directly |
| Re-audit V3 evidence | `AUDITED_HEAD=f7731b7f0616869bcf7d2fba15127a6486057fce`, `AUDITED_TREE=220bf0be54193248556b4daf0926671e6e196889`, `AUDITED_BUNDLE_SHA256=f3e49712983620a390ae1b5a69fccead0a48ef68be8f9acc15d0efa2052ebd0b`; `INDEPENDENT_REAUDIT_V3=FAIL`, `BLOCKERS=0`, `MAJORS=1`, `MINORS=0`, `MAJOR_V3_01=EXACT_CLIENT_BACKEND_IDENTITY_REMAINS_CALLER_ASSERTED_BECAUSE_A_HAND_BUILT_BINDING_CAN_REPLACE_THE_RUNTIME_CONTRACT_AND_BYPASS_THE_EXACT_MARKER`, `DP_150=NOT_VERIFIED`, `AT_DP_150=FAIL_INDEPENDENT`, `CLOSURE_ELIGIBLE=NO` |
| Remediation V3 authoritative runtime identity | `cmm/platform/configuration.py` — the existing `ServiceExpectation` gains the optional authoritative runtime policy (`runtime_contract`, an optional real Python type, plus `runtime_contract_match`), failing closed on a match rule declared without a runtime contract, a runtime contract that is not a real Python type, and a declared runtime contract with no match rule, while `ServiceExpectation(service_id, contract)` stays valid and semantically unchanged (`LEGACY_SERVICE_EXPECTATION_CONSTRUCTION=PRESERVED`). `cmm/platform/service_registry.py` — the one `IntegrationServiceRegistry` holds copied, sorted, externally immutable expectations, exposes one generic `expected_contract_for(service_id)` lookup with no service-ID or authority branch, and applies one expectation-aware assertion path shared by `register()` and `replace()`: the descriptor contract must satisfy `expectation.contract` through the existing `check_contract_compatibility`, the binding must declare `binding.runtime_contract is expectation.runtime_contract` and may neither omit it nor downgrade an `EXACT_TYPE` expectation to `INSTANCE_OF`, and the bound implementation is judged against the expectation (`type(implementation) is expectation.runtime_contract` for `EXACT_TYPE`, `isinstance` otherwise) with a fail-closed guard against a malformed expectation. `cmm/client_backend/platform_module.py` — the canonical `client_backend_service_expectation()` (`client.backend`, the existing contract, `runtime_contract=ClientBackend`, `runtime_contract_match=EXACT_TYPE`), not added to `cmm.client_backend.__all__`. `cmm/platform/container.py` — `configuration.expected_contracts` is authoritative before READY on both the new-registry and the supplied-registry path; `configure_expected_contracts(...)` is monotonic, idempotent for an identical set and atomic. `cmm.platform` core keeps no service-ID or authority special case, no `cmm.client_backend` import, no parallel registry, runtime-type map or container; `FIRST_PARTY_CLIENT_API_EXPANSION=NO`; the V2 `__cmm_exact_runtime_contract__` marker remains defense in depth only (`CANONICAL_RUNTIME_IDENTITY_SOURCE=SERVICE_EXPECTATION`, `BINDING_RUNTIME_CONTRACT_IS_AUTHORITY=NO`) |
| Remediation V3 gate results | focused six-file selection — 298 passed; `tests/platform/test_configuration.py` — 35 passed; `tests/platform/test_service_registry.py` — 105 passed; `tests/platform/test_container.py` — 35 passed; `tests/client_backend/test_platform_module.py` — 40 passed; `AT-DP-150` run separately — 31 passed; `tests/platform` — 439 passed; `tests/client_backend` — 216 passed; inherited acceptances `AT-DP-134`/`AT-DP-121`/`AT-DP-101`/`AT-DP-102`/`AT-DP-103`/`AT-DP-104`/`AT-DP-105` — 68/38/33/33/47/69/1 = 289 passed; `tests/application` — 675 passed; `tests/conversation` — 860 passed; `tests/llm` — 1153 passed; `tests/orchestration` — 498 passed; `tests/cli` — 459 passed; global `pytest -q` — 22069 passed, 1 warning, 0 failed (the +80 over the Remediation V2 HEAD is exactly the `tests/platform` growth from 383 to 439 and the `tests/client_backend` growth from 192 to 216); `RUFF_TOUCHED=PASS`; `FORMAT=PASS`; `RUFF_GLOBAL=837`; `RUFF_NEW_FINDINGS=0`; `COMPILEALL=PASS`; `GIT_DIFF_CHECK=PASS` |
| Remediation V3 result | `MAJOR_V3_01=IMPLEMENTED_PENDING_REAUDIT`; `CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_NONE=REJECTED`; `CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_OBJECT=REJECTED`; `CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_SUBCLASS=REJECTED`; `CLIENT_BACKEND_SUBCLASS_REPLACEMENT_RUNTIME_CONTRACT_NONE=REJECTED`; `CLIENT_BACKEND_SUBCLASS_REPLACEMENT_RUNTIME_CONTRACT_OBJECT=REJECTED`; `CLIENT_BACKEND_SUBCLASS_REPLACEMENT_RUNTIME_CONTRACT_SUBCLASS=REJECTED`; `EXPECTED_RUNTIME_CONTRACT_CANNOT_BE_OMITTED=PASS`; `EXPECTED_EXACT_MATCH_CANNOT_BE_DOWNGRADED=PASS`; `REBUILT_CLIENT_BACKEND_DESCRIPTOR_CANNOT_BYPASS_EXPECTATION=PASS`; `REPLACEMENT_CANNOT_CHANGE_SERVICE_EXPECTATION=PASS`; `EXPECTATION_ATTACHMENT_ATOMIC=PASS`; `EXPECTATION_DOWNGRADE=REJECTED`; `IDENTICAL_EXPECTATION_RECONFIGURATION=IDEMPOTENT`; `PREPOPULATED_FORGED_CLIENT_BACKEND=REJECTED`; `CONTAINER_READY_WITH_FORGED_CLIENT_BACKEND=NO`; `EXACT_CLIENT_BACKEND_CONFIGURED_BINDING=ACCEPTED`; `LEGACY_SERVICE_EXPECTATION_CONSTRUCTION=PRESERVED`; `INHERITED_INSTANCE_OF_SEMANTICS=PRESERVED`; `CANONICAL_RUNTIME_IDENTITY_SOURCE=SERVICE_EXPECTATION`; `BINDING_RUNTIME_CONTRACT_IS_AUTHORITY=NO`; `AT-DP-150` Scenario A3 exercises the configuration-anchored authoritative expectation path over real components and a real `ApplicationContainer` |
| Final Independent Re-audit V4 | `PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`; `F11_021=VERIFIED_EXISTING`; `DP_150=VERIFIED_EXISTING`; `AT_DP_150=PASS`; `CLOSURE_ELIGIBLE=YES`; audited HEAD `a405e883edbafd04acad9d26f357ad54723041f7`; audited tree `0bcd8f69710a28f3c372ac559afc17846a0baeb3`; bundle SHA-256 `526f575a20524dccbc9b1901ee9f4fe4f7dfc34add47fd4ca420144a118aa194`; final report `docs/audits/phase-11.50-reusable-backend-interfaces-independent-reaudit-v4.md`; audit-report commit `bc101c74aa7e29edceafc47e20e69ed816be7b6d` |
| Mapping status | `VERIFIED_EXISTING` |
| Next step | fresh independent ChatGPT re-audit of the exact-HEAD Phase 11.22 V13 bundle (`phase-11.22-event-system-audit-v13.tar.gz`); Phase 11.22 is not closed, not independently verified and not complete; Phase 11.23 and Phase 11.24 are **not** begun |

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

Section 5 is the closed Phase 11.34 Provider Registry state. Sections 6–11
record the closed Phase 11.1–11.4 subphases and are not modified by Phase 11.5.
The Phase 11.5 conversational interface is a separate subphase and is reported
here in its Remediation V2 state:

```text
PHASE11_5=CLOSED

F11_019=VERIFIED_EXISTING
DP_105=VERIFIED_EXISTING
AT_DP_105=PASS

INDEPENDENT_AUDIT_V1=FAIL_RECORDED
INDEPENDENT_REAUDIT_V1=FAIL_RECORDED
REMEDIATION_V2=INDEPENDENTLY_REAUDITED_PASS
CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=CLOSED_AFTER_INDEPENDENT_REAUDIT_V2_PASS
NEXT=PHASE11_NEXT_SUBPHASE_REQUIRES_FRESH_INSPECTION
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
`reference_only`, a Bot association is `opaque_non_authoritative`, and
`domain_projection` is composition-aware (Remediation V2 `MAJOR_R1_01`):
`available` with the effective mode
`authorized_projection_when_supplied_by_canonical_integrator` while
`ConversationService` composes an authorized read-only projection source, and
`unavailable` with `effective=None` and reason
`NO_AUTHORIZED_DOMAIN_PROJECTION_SOURCE` otherwise.

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
Closure, verification and closure eligibility for Phase 11.5 are recorded after Independent Re-audit V2 `PASS` in
this section; an independent audit must examine the exact-HEAD implementation
first.

<!-- PHASE11_5_FINAL_CLOSURE_EVIDENCE -->
## Phase 11.5 — Final closure evidence

```text
PHASE11_5=CLOSED
F11_019=VERIFIED_EXISTING
DP_105=VERIFIED_EXISTING
AT_DP_105=PASS
INDEPENDENT_AUDIT_V1=FAIL_RECORDED
INDEPENDENT_REAUDIT_V1=FAIL_RECORDED
INDEPENDENT_REAUDIT_V2=PASS
BLOCKERS=0
MAJORS=0
MINORS=0
MAJOR_R1_01=VERIFIED_REMEDIATED
MINOR_R1_01=VERIFIED_REMEDIATED
MINOR_R1_02=VERIFIED_REMEDIATED
REMEDIATION_V2=INDEPENDENTLY_REAUDITED_PASS
CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=CLOSED_AFTER_INDEPENDENT_REAUDIT_V2_PASS
AUDITED_HEAD=9fde9db154c5ff957565f8f4ab6ca2391037b15c
AUDITED_TREE=937f4312592baf33a6aedf59e37a2ca475a8e036
AUDITED_BUNDLE_SHA256=56d5eee4f2d1f908465f1b65bc16237ea4b4d40b64f3fc49bc2c6840bef13511
FINAL_REPORT=docs/audits/phase-11.5-conversational-interface-independent-reaudit-v2.md
FINAL_REPORT_SHA256=f5a4f72c12734052f24df63250bb1c28d5017e90d99129e5d56afbf5d71bd67c
AUDIT_REPORT_COMMIT=e3a713bfdb2b108c4db7a38a4da556cc1ce83c86
NEXT=PHASE11_NEXT_SUBPHASE_REQUIRES_FRESH_INSPECTION
```

Phase 11.5 is closed by the dedicated docs-only closure commit after the
Independent Re-audit V2 `PASS`. Historical Audit V1 and Re-audit V1 `FAIL`
evidence remains immutable.

## 13. Phase 11.21 — Model Gateway closed status

Sections 5 to 12 record the already-closed Phase 11.34 and Phase 11.1–11.5
subphases. Phase 11.21 is now also independently verified and closed.

```text
PHASE11_21=CLOSED
INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V2=FAIL
INDEPENDENT_REAUDIT_V3=PASS
BLOCKERS=0
MAJORS=0
MINORS=0
F11_020=VERIFIED_EXISTING
DP_121=VERIFIED_EXISTING
AT_DP_121=PASS
AT_DP_134=PASS
AT_DP_101=PASS
AT_DP_102=PASS
AT_DP_103=PASS
AT_DP_104=PASS
AT_DP_105=PASS
MAJOR_01=VERIFIED_REMEDIATED
MAJOR_02=VERIFIED_REMEDIATED
MAJOR_03=VERIFIED_REMEDIATED
MAJOR_04=VERIFIED_REMEDIATED
MAJOR_05=VERIFIED_REMEDIATED
MINOR_01=VERIFIED_REMEDIATED
CLOSURE_ELIGIBLE=YES
AUDITED_HEAD=fe5eda5ccba327d3002979910f9cf4d8a4053ddc
AUDITED_TREE=0e8a1ac75e5fdf32a5e5e240790a0d8ff986ced7
AUDITED_BUNDLE_SHA256=1873217d10222e87e9d5e319a319eaddf7741c4ef05d384377bb4548f47a5bd3
FINAL_REPORT=docs/audits/phase-11.21-model-gateway-independent-reaudit-v3.md
AUDIT_REPORT_COMMIT=749dd87df5a919775058d116ba17a878cf5adc5f
NEXT=PHASE11_50_FRESH_REPOSITORY_INSPECTION
```

Independent Audit V1 `FAIL` and Independent Re-audit V2 `FAIL` remain immutable
historical evidence. Remediation V1 corrected the original five MAJOR and one
MINOR findings; Remediation V2 corrected the sole residual AUTO/privacy finding.
Independent Re-audit V3 then returned `PASS`, independently reproducing the
mixed remote/local AUTO cases, explicit-remote fail-closed behavior, remote-only
AUTO fail-closed behavior, and the already-remediated cancellation, streaming,
legacy-adapter and schema-v3 persistence invariants.

`DP-121` is therefore `VERIFIED_EXISTING`, `AT-DP-121=PASS`, and the closure
threshold is satisfied with `BLOCKERS=0`, `MAJORS=0`,
`CLOSURE_ELIGIBLE=YES`.

Phase 11.21 does not reopen Phase 11.34 or Phase 11.1–11.5. The Phase 11.34
provider-state schema-v3 addition remains an additive seam under the same
persistence owner; no second store or routing authority exists.

The implemented surface and final evidence are documented in
[`docs/reference/phase-11-model-gateway.md`](phase-11-model-gateway.md).

<!-- PHASE11_21_CLOSED_AFTER_INDEPENDENT_REAUDIT_V3_PASS -->

## 14. Phase 11.50 — Reusable Backend Interfaces — closed after Independent Re-audit V4 PASS

Phase 11.50 implements the frozen design
`docs/superpowers/specs/2026-09-25-phase-11.50-reusable-backend-interfaces-design.md`
(`SHA256=d0296a5de7b0afcc3f3595ade1982d0ed140d9aa3a699afbfffab184a12150c6`)
exactly as the implementation plan
`docs/superpowers/plans/2026-09-25-phase-11.50-reusable-backend-interfaces-implementation-plan.md`
prescribes. Independent Audit V1
(`docs/audits/phase-11.50-reusable-backend-interfaces-independent-audit-v1.md`,
`SHA256=d1a0e7a07b6871850a4c79dbb6a42652fe8e14d9d26d34f8e71c1fdeab087a49`)
returned `INDEPENDENT_AUDIT_V1=FAIL` with `BLOCKERS=0`, `MAJORS=5`, `MINORS=1`,
`DP_150=NOT_VERIFIED` and `CLOSURE_ELIGIBLE=NO`. Remediation V1, designed by
`docs/superpowers/specs/2026-09-25-phase-11.50-remediation-v1-design.md` and
planned by
`docs/superpowers/plans/2026-09-25-phase-11.50-remediation-v1-implementation-plan.md`,
corrected exactly those findings on branch `feature/phase-11-stable-integrated-platform`.

Independent Re-audit V2
(`docs/audits/phase-11.50-reusable-backend-interfaces-independent-reaudit-v2.md`,
`SHA256=8b9e7b4f6e518c7041e65f9d0efa32036f18a15e170616c6db8a7f7abfb279c0`)
then examined that Remediation V1 state at
`AUDITED_HEAD=c626fbfead204f58e67076375dc6f497f56af700` and returned
`INDEPENDENT_REAUDIT_V2=FAIL` with `BLOCKERS=0`, `MAJORS=1`, `MINORS=0`: V1
MAJOR-01/03/04/05 and MINOR-01 `VERIFIED_REMEDIATED`, and one residual defect
(MAJOR_V2_01). Remediation V2, designed by
`docs/superpowers/specs/2026-09-26-phase-11.50-remediation-v2-design.md`
(`SHA256=9fdfd952b2347c06fbc4ac96dbbb0a93a58636068e4f07c8a91dc295206234fe`) and
planned by
`docs/superpowers/plans/2026-09-26-phase-11.50-remediation-v2-implementation-plan.md`
(`SHA256=8260cb3f9f6d8e70f0453ce202743c910a188beb2f6ad69fefc52cecde33b8f4`),
corrects exactly that one residual defect.

Independent Re-audit V3
(`docs/audits/phase-11.50-reusable-backend-interfaces-independent-reaudit-v3.md`,
`SHA256=5604c638fe27669710c147fa329afde5d1c79d30d1cd49ea0d1feda1272f8749`)
then examined that Remediation V2 state at
`AUDITED_HEAD=f7731b7f0616869bcf7d2fba15127a6486057fce`,
`AUDITED_TREE=220bf0be54193248556b4daf0926671e6e196889` and returned
`INDEPENDENT_REAUDIT_V3=FAIL` with `BLOCKERS=0`, `MAJORS=1`, `MINORS=0`, with one
residual defect:

```text
MAJOR_V3_01=
EXACT_CLIENT_BACKEND_IDENTITY_REMAINS_CALLER_ASSERTED_BECAUSE_A_HAND_BUILT_BINDING_CAN_REPLACE_THE_RUNTIME_CONTRACT_AND_BYPASS_THE_EXACT_MARKER
```

Remediation V3, designed by
`docs/superpowers/specs/2026-09-26-phase-11.50-remediation-v3-design.md`
(`SHA256=d5ef219797a2128e80b672c568811ede22a89ef6dbf2a0ae108e70173121debd`) and
planned by
`docs/superpowers/plans/2026-09-26-phase-11.50-remediation-v3-implementation-plan.md`
(`SHA256=b9d90024e7a9f39258c4961ee5a153341eafbec67668569458bef2b4666ce660`),
corrects exactly that one residual defect.

Independent Re-audit V4
(`docs/audits/phase-11.50-reusable-backend-interfaces-independent-reaudit-v4.md`,
`SHA256=b9cc9d5c88538e58123a6ab7e751024a5434ac1012c56e767175d1e4aa9068c7`)
then examined the exact Remediation V3 state at
`AUDITED_HEAD=a405e883edbafd04acad9d26f357ad54723041f7`,
`AUDITED_TREE=0bcd8f69710a28f3c372ac559afc17846a0baeb3` with
`AUDITED_BUNDLE_SHA256=526f575a20524dccbc9b1901ee9f4fe4f7dfc34add47fd4ca420144a118aa194` and returned the final `PASS`.

```text
PHASE11_50=CLOSED
F11_021=VERIFIED_EXISTING
DP_150=VERIFIED_EXISTING
AT_DP_150=PASS
INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V2=FAIL
INDEPENDENT_REAUDIT_V3=FAIL
INDEPENDENT_REAUDIT_V4=PASS
BLOCKERS=0
MAJORS=0
MINORS=0
CLOSURE_ELIGIBLE=YES
```

What Remediation V1 corrects (Audit V1 findings only; `F11-021`, `DP-150` and
`AT-DP-150` are unchanged):

```text
MAJOR_01  public owner escape hatch        -> closed; no public live-owner accessor
MAJOR_02  exact canonical owner types      -> type(...) is gates, subclasses rejected
MAJOR_03  canonical failures re-coded      -> canonical safe identity preserved
MAJOR_04  capability truth contradiction   -> degraded/reference_only + available event stream
MAJOR_05  non-JSON-native serialization    -> JSON-native public wrappers
MINOR_01  report evidence discipline       -> exact start HEAD and commit count
```

What Remediation V2 corrects (Re-audit V2 findings only):

```text
MAJOR_V2_01  exact composition identity enforced only by the convenience builder
             -> authoritative exact-runtime-type enforcement in
                IntegrationServiceRegistry.register() and replace()
```

The reproduced bypass and its closure:

```text
BEFORE  ClientBackendSubclass + canonical client.backend descriptor
        + hand-built ServiceBinding + register()
        -> CLIENT_BACKEND_SUBCLASS_HAND_BUILT_BINDING=ACCEPTED

AFTER   CLIENT_BACKEND_SUBCLASS_HAND_BUILT_BINDING=REJECTED
        CLIENT_BACKEND_SUBCLASS_REPLACEMENT=REJECTED
        EXACT_CLIENT_BACKEND_HAND_BUILT_BINDING=ACCEPTED
        EXACT_RUNTIME_CONTRACT_CANNOT_BE_DOWNGRADED=PASS
        OMITTED_MATCH_CANNOT_DOWNGRADE_EXACT_CONTRACT=PASS
        INHERITED_INSTANCE_OF_SEMANTICS=PRESERVED
        DEFAULT_PHASE11_1_MATCH=INSTANCE_OF
        NEW_OPT_IN_MATCH=EXACT_TYPE
        PLATFORM_IMPORTS_CLIENT_BACKEND=NO
        CLIENT_BACKEND_SPECIAL_CASE_IN_PLATFORM=ABSENT
        PARALLEL_POLICY_REGISTRY=NO
```

Remediation V2 changes no client operation, no DTO, no capability field and no
application/conversation API. The platform mechanism is generic and contract
driven: the exact requirement travels with the runtime contract itself, so the
`cmm.platform` core needs no knowledge of `client.backend`. `AT-DP-150` keeps its
single acceptance identifier and gains Scenario A2, which drives the authoritative
`IntegrationServiceRegistry` path directly with a hand-built binding.

What Remediation V3 corrects (Re-audit V3 findings only):

```text
MAJOR_V3_01  exact composition identity still derived from the caller-authored
             ServiceBinding.runtime_contract field
             -> authoritative runtime identity taken from the configured
                ServiceExpectation in CompositionConfiguration.expected_contracts
```

The reproduced bypass and its closure:

```text
BEFORE  ClientBackendSubclass + canonical client.backend descriptor
        + forged ServiceBinding.runtime_contract (None | object | ClientBackendSubclass)
        + register() / replace()
        -> CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_NONE=ACCEPTED
           CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_OBJECT=ACCEPTED
           CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_SUBCLASS=ACCEPTED

AFTER   CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_NONE=REJECTED
        CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_OBJECT=REJECTED
        CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_SUBCLASS=REJECTED
        CLIENT_BACKEND_SUBCLASS_REPLACEMENT_RUNTIME_CONTRACT_NONE=REJECTED
        CLIENT_BACKEND_SUBCLASS_REPLACEMENT_RUNTIME_CONTRACT_OBJECT=REJECTED
        CLIENT_BACKEND_SUBCLASS_REPLACEMENT_RUNTIME_CONTRACT_SUBCLASS=REJECTED
        EXPECTED_RUNTIME_CONTRACT_CANNOT_BE_OMITTED=PASS
        EXPECTED_EXACT_MATCH_CANNOT_BE_DOWNGRADED=PASS
        REBUILT_CLIENT_BACKEND_DESCRIPTOR_CANNOT_BYPASS_EXPECTATION=PASS
        REPLACEMENT_CANNOT_CHANGE_SERVICE_EXPECTATION=PASS
        EXPECTATION_ATTACHMENT_ATOMIC=PASS
        EXPECTATION_DOWNGRADE=REJECTED
        IDENTICAL_EXPECTATION_RECONFIGURATION=IDEMPOTENT
        PREPOPULATED_FORGED_CLIENT_BACKEND=REJECTED
        CONTAINER_READY_WITH_FORGED_CLIENT_BACKEND=NO
        EXACT_CLIENT_BACKEND_CONFIGURED_BINDING=ACCEPTED
        LEGACY_SERVICE_EXPECTATION_CONSTRUCTION=PRESERVED
        INHERITED_INSTANCE_OF_SEMANTICS=PRESERVED
        CANONICAL_RUNTIME_IDENTITY_SOURCE=SERVICE_EXPECTATION
        BINDING_RUNTIME_CONTRACT_IS_AUTHORITY=NO
```

The authority chain is the existing Phase 11.1 configuration path —
`CompositionConfiguration.expected_contracts` → `ServiceExpectation` →
`IntegrationServiceRegistry` → the binding must agree → `ApplicationContainer`
READY — so the platform needs no product knowledge and introduces no parallel
registry, runtime-type map or container. The V2 `RuntimeContractMatch` primitive
and the private contract marker remain, but only as defense in depth:
`AT-DP-150` keeps its single acceptance identifier and gains Scenario A3, which
exercises the configuration-anchored expectation path over real components and a
real `ApplicationContainer`.

What Phase 11.50 adds:

- one new top-layer package, `cmm/client_backend`, containing a
  **non-authoritative facade** over the exact canonical Phase 11.3
  `ApplicationGateway` and Phase 11.5 `ConversationService`;
- one frozen interface version, `CLIENT_BACKEND_INTERFACE_VERSION = "1"`;
- one closed operation set, `ClientOperation`, and one narrow transport-neutral
  envelope, `ClientBackendRequest` / `ClientBackendResult`;
- one immutable capability projection, `ClientBackendCapabilities`, whose rows
  derive only from canonical evidence and which distinguishes model-boundary
  availability (`boundary_only`) from end-to-end availability;
- one Phase 11.1 service binding, `client.backend`, whose dependency edges are
  `application.gateway` and `conversation.service` only.

What Phase 11.50 does not add, by explicit design ruling:

```text
NEW_EXECUTION_AUTHORITY=NO
NEW_BACKEND_AUTHORITY=NO
NEW_SESSION_AUTHORITY=NO
NEW_ROUTING_AUTHORITY=NO
NEW_MODEL_AUTHORITY=NO
SECOND_APPLICATION_BACKEND=FORBIDDEN
SECOND_CONVERSATION_SERVICE=FORBIDDEN
DIRECT_MODEL_GATEWAY_CLIENT_ACCESS=FORBIDDEN
NEW_HTTP_SERVER=FORBIDDEN
NEW_SESSION_STORE=FORBIDDEN
NEW_STREAM_RUNTIME=FORBIDDEN
```

The broad historical §11.50 roadmap wording is preserved unchanged in
[`docs/roadmap/phase-11-stable-integrated-platform.md`](../roadmap/phase-11-stable-integrated-platform.md);
the scoped implementation is recorded underneath it. `cmm.api` remains the
existing Phase 11.3 HTTP/OpenAPI/SSE adapter and is regression-checked only; the
Phase 11.4 CLI is untouched; MCP, OpenAI Actions and external adapters remain
`PHASE11_51=NOT_IMPLEMENTED`; general event subscriptions remain deferred.

The implemented surface, capability truth table, security invariants and known
limits are documented in
[`docs/reference/phase-11-reusable-backend-interfaces.md`](phase-11-reusable-backend-interfaces.md).

<!-- PHASE11_50_CLOSED_AFTER_INDEPENDENT_REAUDIT_V4_PASS -->

### 4.17 `F11-022` — Canonical Platform Event System

`F11-001` … `F11-013` remain owned by the Phase 10 matrix, `F11-014` is owned
by §4.1, `F11-015` by §4.3, `F11-016` by §4.5, `F11-017` by §4.7, `F11-018`
by §4.9, `F11-019` by §4.11, `F11-020` by §4.13 and `F11-021` by §4.15 of this
document. `F11-022` is the next non-colliding Phase 11 requirement identifier.

| Requirement | `F11-022 — Canonical Platform Event System` |
| --- | --- |
| Source | `SRC-R11` (detailed Phase 11 roadmap §11.22); `docs/superpowers/specs/2026-09-26-phase-11.22-event-system-design.md` §1–§35; `docs/superpowers/plans/2026-09-26-phase-11.22-event-system-implementation-plan.md` |
| Phase | Phase 11.22 |
| Design Point | `DP-122` |
| Acceptance | `AT-DP-122` — `tests/events/test_phase11_22_dp122_acceptance.py` |
| Requirement text | CMM OS shall make its already-existing Phase 9 runtime event infrastructure genuinely platform-usable without adding a second event authority: exactly one canonical in-process event transport (`AgentRuntimeEventBus`), one mutable event registry (`AgentRuntimeEventRegistry`), one event repository contract (`AgentRuntimeEventRepository`, given a durable local implementation) and one replay owner (`AgentRuntimeEventReplayer`), plus the existing dead-letter family. It shall define an immutable twenty-name platform event catalog with exactly one producer disposition per name, register those names through the canonical event-type authority rather than a second registry, translate producer facts only through explicit one-way mappings, and never fabricate a producer for a reserved name. It shall restrict every platform payload to a bounded reference/categorical vocabulary and reject prompts, system/developer prompts, chain-of-thought, hidden or raw reasoning, raw provider request/response payloads, credentials, tokens, authorization headers, cookies, raw tracebacks, opaque runtime objects, arbitrary binary payloads and unrecognised keys **before** durable persistence, in **any** persisted event field — payload data or a persisted free-form header channel — so forbidden material cannot be relocated to bypass the boundary. It shall persist every accepted event before normal delivery, fail closed on same-ID/different-content identity conflicts, treat identical republishes as idempotent duplicates with no second record and no second normal delivery, isolate and bound per-subscriber delivery retries, record exactly one canonical dead-letter entry on exhaustion without storing raw exception content, and replay stored events as notification evidence only to subscribers that explicitly opted in (`accept_replay=False` by default) while preserving event identity, correlation, causation, facts and deterministic local ordering, appending no duplicate record and granting no authority. It shall adapt the Phase 11.2 `OrchestrationEventSink` seam and selected `kernel.events.Event` producers through thin one-way adapters that keep every closed-phase contract and boundary intact, compose through the existing Phase 11.1 application container, expose read-only event-system stats and health suitable for Phase 11.23, and introduce no second bus, registry, repository protocol, replay engine, DLQ subsystem, broker abstraction, command bus, job queue, workflow engine, service locator, second container, external broker dependency, HTTP/SSE/WebSocket event route, CMMChat surface, observability backend or generalised recovery framework. |
| Production package | `cmm/events/` — `__init__.py`; `event_catalog.py`; `event_payload_safety.py`; `event_translation.py`; `event_system.py`; `orchestration_adapter.py`; `kernel_adapter.py`; `platform_module.py`; `storage.py` |
| Additive Phase 9 hardening | `cmm/agent_runtime/runtime_event_bus.py` (bounded `max_delivery_attempts`, `deliver_replay`, declared `event_types` matching, DLQ binding, detached per-subscriber delivery snapshots); `runtime_event_contracts.py` (optional `producer` / `aggregate_id`, `accept_replay`, `retry_total`, `detached_event_copy`); `runtime_event_factory.py` (producer/aggregate passthrough, `event_fingerprint`, `supports_schema_version`, fail-closed schema version); `runtime_event_repository.py` (`FileAgentRuntimeEventRepository`, shared filter helper, `ensure_event_is_reopenable`, detached stored/read snapshots); `runtime_event_replay.py` (notification replay, no re-save); `runtime_event_errors.py` (identity-conflict, persistence-corruption, unsupported-schema, retry-exhausted, replay-denied); `runtime_event_types.py` (16 additive platform names); **Remediation V3** added, inside the same canonical contracts: `runtime_event_contracts.py` `detached_dead_letter_copy()` for dead-letter snapshot detachment; `runtime_event_factory.py` canonical nested JSON-compatible serialization with no `json.dumps(default=str)` and a deep-detaching `AgentRuntimeEventNormalizer.normalize()`; `runtime_event_dead_letter.py` detached `add()`/`get()`/`list()`/`remove()` snapshots; **Remediation V4** added, inside the same canonical contracts: `runtime_event_bus.py` bounded safe DLQ error-category derivation with `bind_error_categorizer()` injection and a defensive check at the single DLQ write point; **Remediation V5** added, inside those same canonical contracts and with no second safety module or payload registry: `event_payload_safety.py` semantic buffer/binary classification via one bounded buffer-protocol probe (covers `bytes`, `bytearray`, `memoryview` and every `array.array` typecode before all generic sequence handling), one canonical `PAYLOAD_KEY_CLASSES` lifecycle value-class specification covering every allowed payload key, recursive structured-reference validation, and `METADATA_KEY_CLASSES`/`METADATA_CONTAINER_KEYS` bounded lifecycle metadata semantics that fail closed on an unknown metadata key; `runtime_event_bus.py` fail-safe DLQ categorization that records the neutral bounded category whenever no external error categorizer is bound |
| Composition | `cmm/application/local_runtime.py` composes the `phase11_22_events` module and the durable event store, so the real Orchestrator reports to the production platform sink through the frozen Phase 11.2 `orchestration.event_sink` identity |
| Documentation | `docs/reference/phase-11-event-system.md` |
| Mapping status | `REMEDIATED_AFTER_REAUDIT_V12_PENDING_INDEPENDENT_REAUDIT` (independent Audit V1 = `FAIL`, `BLOCKERS=0`, `MAJORS=4`, `MINORS=5`; independent Re-audit V2 = `FAIL`, `BLOCKERS=0`, `MAJORS=4`, `MINORS=0`, `AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED`; independent Re-audit V3 = `FAIL`, `BLOCKERS=0`, `MAJORS=2`, `MINORS=1`, `AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED`, `REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_VERIFIED`; independent Re-audit V4 = `FAIL`, `BLOCKERS=0`, `MAJORS=3`, `MINORS=0`, `REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_VERIFIED`; independent Re-audit V5 = `FAIL`, `BLOCKERS=0`, `MAJORS=3`, `MINORS=0`, `V4_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED`, `PRIOR_REMEDIATION_REGRESSIONS=279_PASS`; independent Re-audit V6 = `FAIL`, `BLOCKERS=0`, `MAJORS=3`, `MINORS=1`, `V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED`, `PRIOR_REMEDIATION_REGRESSIONS=350_PASS`; independent Re-audit V7 = `FAIL`, `BLOCKERS=0`, `MAJORS=2`, `MINORS=0`, `V6_CONCRETE_FINDINGS_FIXED=4/4_VERIFIED`, `PRIOR_REMEDIATION_REGRESSIONS=477_PASS`; independent Re-audit V8 = `FAIL`, `BLOCKERS=0`, `MAJORS=2`, `MINORS=1`, `V7_CONCRETE_FINDINGS_FIXED=2/2_VERIFIED`, `PRIOR_REMEDIATION_REGRESSIONS=604_PASS`; independent Re-audit V9 = `FAIL`, `BLOCKERS=0`, `MAJORS=2`, `MINORS=1`, `V8_CONCRETE_FINDINGS_FIXED=2/2_VERIFIED`, `MAJOR_V9_001=WRAPPED_NON_AUTHORITY_FILE_URI_BYPASSES_FAIL_CLOSED_FILESYSTEM_CLASSIFIER`, `MAJOR_V9_002=SUPPORTED_RUNTIME_TIMESTAMP_SEMANTICS_REOPEN_PRIOR_V6_FINDING_AND_KEEP_GLOBAL_GATE_RED`, `MINOR_V9_001=REFERENCE_TEST_EVIDENCE_COUNTS_STALE_AFTER_FINAL_V8_AT_ADDITIONS`; independent Re-audit V10 = `FAIL`, `BLOCKERS=0`, `MAJORS=1`, `MINORS=0`, `V9_FINDINGS_FIXED=3/3_VERIFIED`, `PRIOR_REMEDIATION_REGRESSIONS=1290_PASS`, `MAJOR_V10_001=WRAPPED_WINDOWS_DRIVE_ROOT_REFERENCE_BYPASSES_PUBLIC_ROOT_FILESYSTEM_CLASSIFIER`; independent Re-audit V11 = `FAIL`, `BLOCKERS=0`, `MAJORS=1`, `MINORS=0`, `V10_FINDINGS_FIXED=1/1_VERIFIED`, `PRIOR_REMEDIATION_REGRESSIONS=1765_PASS`, `MAJOR_V11_001=WINDOWS_DRIVE_RELATIVE_REFERENCE_BYPASSES_CANONICAL_FILESYSTEM_CLASSIFIER_AND_PERSISTS`; independent Re-audit V12 = `FAIL`, `BLOCKERS=0`, `MAJORS=1`, `MINORS=0`, `V11_FINDINGS_FIXED=1/1_VERIFIED`, `PRIOR_REMEDIATION_REGRESSIONS=2473_PASS`, `MAJOR_V12_001=WINDOWS_SENSITIVE_PRIVATE_FILENAME_EQUIVALENTS_BYPASS_CANONICAL_FILESYSTEM_CLASSIFIER_AND_PERSIST`) |
| Acceptance status | `DP-122=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION`; `AT-DP-122=PASS_REPORTED` |
| Remediation V1 | `MAJOR_001=REMEDIATED_REPORTED`; `MAJOR_002=REMEDIATED_REPORTED`; `MAJOR_003=REMEDIATED_REPORTED`; `MAJOR_004=REMEDIATED_REPORTED`; `MINOR_001=REMEDIATED_REPORTED`; `MINOR_002=REMEDIATED_REPORTED`; `MINOR_003=REMEDIATED_REPORTED`; `MINOR_004=REMEDIATED_REPORTED`; `MINOR_005=REMEDIATED_REPORTED`; immutable Audit V1 report `docs/audits/phase-11.22-event-system-independent-audit-v1.md` and V1 bundle `phase-11.22-event-system-audit-v1.tar.gz` (`a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3`) preserved byte-identical; V2 bundle `phase-11.22-event-system-audit-v2.tar.gz` (`172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04`) from the exact remediation V1 HEAD; all nine findings independently verified `9/9` by Re-audit V2 and preserved |
| Remediation V2 | `MAJOR_V2_001=REMEDIATED_REPORTED`; `MAJOR_V2_002=REMEDIATED_REPORTED`; `MAJOR_V2_003=REMEDIATED_REPORTED`; `MAJOR_V2_004=REMEDIATED_REPORTED`; `AUDIT_V1_FINDINGS_REMEDIATED=9/9_PRESERVED`; immutable Re-audit V2 report `docs/audits/phase-11.22-event-system-independent-reaudit-v2.md` preserved byte-identical; V3 bundle `phase-11.22-event-system-audit-v3.tar.gz` from the exact Remediation V2 HEAD; `CLOSURE_ELIGIBLE=NO` |
| Remediation V3 | `MAJOR_V3_001=REMEDIATED_REPORTED`; `MAJOR_V3_002=REMEDIATED_REPORTED`; `MINOR_V3_001=REMEDIATED_REPORTED`; `AUDIT_V1_FINDINGS_REMEDIATED=9/9_PRESERVED`; `REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_PRESERVED`; immutable Re-audit V3 report `docs/audits/phase-11.22-event-system-independent-reaudit-v3.md` preserved byte-identical; V1/V2/V3 bundles `phase-11.22-event-system-audit-v1.tar.gz` (`a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3`), `phase-11.22-event-system-audit-v2.tar.gz` (`172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04`) and `phase-11.22-event-system-audit-v3.tar.gz` (`27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589`) preserved byte-identical; V4 bundle `phase-11.22-event-system-audit-v4.tar.gz` from the exact Remediation V3 HEAD; `CLOSURE_ELIGIBLE=NO` |
| Remediation V4 | `MAJOR_V4_001=REMEDIATED_REPORTED` (the shared sequence predicate now classifies `memoryview` as binary, so binary bytes can no longer be canonicalized into an integer array in any persisted Phase 11.22 content channel); `MAJOR_V4_002=REMEDIATED_REPORTED` (manual `publish_event()` now normalizes a canonical sensitivity string to `EventSensitivity` before persistence, so in-memory and file-backed repositories agree); `MAJOR_V4_003=REMEDIATED_REPORTED` (one bounded safe DLQ error category: the class name is kept only when it is a bounded identifier free of credentials and private markers, otherwise `SubscriberDeliveryError`); `REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `AUDIT_V1_FINDINGS_REMEDIATED=9/9_PRESERVED`; `REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_PRESERVED`; immutable Re-audit V4 report `docs/audits/phase-11.22-event-system-independent-reaudit-v4.md` preserved byte-identical; V1/V2/V3/V4 bundles `phase-11.22-event-system-audit-v1.tar.gz` (`a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3`), `phase-11.22-event-system-audit-v2.tar.gz` (`172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04`), `phase-11.22-event-system-audit-v3.tar.gz` (`27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589`) and `phase-11.22-event-system-audit-v4.tar.gz` (`18adf70d86f291b5585f71b746f81139ffa01e56e7c16dcbfc6b67bb794aaa0f`) preserved byte-identical; V5 bundle `phase-11.22-event-system-audit-v5.tar.gz` from the exact Remediation V4 HEAD; `CLOSURE_ELIGIBLE=NO` |
| Remediation V5 | `MAJOR_V5_001=REMEDIATED_REPORTED` (binary/buffer classification is semantic, so `bytes`, `bytearray`, `memoryview` and every `array.array` typecode fail closed before any generic sequence handling and can never become an integer array or durable content); `MAJOR_V5_002=REMEDIATED_REPORTED` (one `PAYLOAD_KEY_CLASSES` specification gives every allowed payload key exactly one explicit lifecycle value class, recursive structured-reference validation, and a bounded `METADATA_KEY_CLASSES` vocabulary that fails closed on an unknown metadata key, so raw user text cannot be relocated into any lifecycle field); `MAJOR_V5_003=REMEDIATED_REPORTED` (the canonical bus records the neutral bounded category `SubscriberDeliveryError` whenever no external error categorizer is bound, so DLQ secret safety no longer depends on an optional second binding); `V4_CONCRETE_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `AUDIT_V1_FINDINGS_REMEDIATED=9/9_PRESERVED`; `REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_PRESERVED`; `PRIOR_REMEDIATION_REGRESSIONS=279_PASS`; immutable Re-audit V5 report `docs/audits/phase-11.22-event-system-independent-reaudit-v5.md` preserved byte-identical; V1/V2/V3/V4/V5 bundles `phase-11.22-event-system-audit-v1.tar.gz` (`a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3`), `phase-11.22-event-system-audit-v2.tar.gz` (`172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04`), `phase-11.22-event-system-audit-v3.tar.gz` (`27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589`), `phase-11.22-event-system-audit-v4.tar.gz` (`18adf70d86f291b5585f71b746f81139ffa01e56e7c16dcbfc6b67bb794aaa0f`) and `phase-11.22-event-system-audit-v5.tar.gz` (`105203eb4ea1d0e1b3200ee30b7130961af70283d8be9fc7b28ed65279003d10`) preserved byte-identical; V6 bundle `phase-11.22-event-system-audit-v6.tar.gz` from the exact Remediation V5 HEAD; `CLOSURE_ELIGIBLE=NO` |
| Remediation V6 | `MAJOR_V6_001=REMEDIATED_REPORTED` (numeric lifecycle facts are now actually bounded by one explicit `MAX_PLATFORM_NUMERIC_FACT = 2**63 - 1` and one `NUMERIC_FACT_SEMANTICS` table, so `10 ** 5000`, negative counts/durations/attempts/sequences and absurd finite floats fail closed before any repository interaction and the two official repositories cannot diverge); `MAJOR_V6_002=REMEDIATED_REPORTED` (a narrow syntactic private-filesystem classifier rejects `file:` URIs, absolute POSIX paths, Windows drive-root paths, UNC shares, user-home directories, known secret-bearing path segments and private key file names on every persisted identifier channel, while `workflow:123`, `domain:legal` and `provider/model` stay valid); `MAJOR_V6_003=REMEDIATED_REPORTED` (one canonical header fact authority: `CANONICAL_HEADER_PAYLOAD_KEYS` are consumed into the canonical header before persistence, a contradictory payload copy fails closed, a stricter payload sensitivity is promoted to the header and a lower one can never downgrade it, on both the factory and the manual `publish_event` path); `MINOR_V6_001=REMEDIATED_REPORTED` (timestamp validation parses real civil time and requires an explicit UTC offset, so impossible months/days/hours/minutes and timezone-less values fail closed); `V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `REAUDIT_V4_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `AUDIT_V1_FINDINGS_REMEDIATED=9/9_PRESERVED`; `REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_PRESERVED`; `PRIOR_REMEDIATION_REGRESSIONS=350_PASS`; immutable Re-audit V6 report `docs/audits/phase-11.22-event-system-independent-reaudit-v6.md` preserved byte-identical and the immutable V6 bundle `phase-11.22-event-system-audit-v6.tar.gz` (`67b27f6effa5297757453aba3021a7211fe4ee88e194a6d65eefa353060f1008`) preserved byte-identical; V1/V2/V3/V4/V5 bundles `phase-11.22-event-system-audit-v1.tar.gz` (`a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3`), `phase-11.22-event-system-audit-v2.tar.gz` (`172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04`), `phase-11.22-event-system-audit-v3.tar.gz` (`27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589`), `phase-11.22-event-system-audit-v4.tar.gz` (`18adf70d86f291b5585f71b746f81139ffa01e56e7c16dcbfc6b67bb794aaa0f`) and `phase-11.22-event-system-audit-v5.tar.gz` (`105203eb4ea1d0e1b3200ee30b7130961af70283d8be9fc7b28ed65279003d10`) preserved byte-identical; V7 bundle `phase-11.22-event-system-audit-v7.tar.gz` from the exact Remediation V6 HEAD; `CLOSURE_ELIGIBLE=NO` |
| Remediation V7 | `MAJOR_V7_001=REMEDIATED_REPORTED` (the existing private-filesystem classifier now also refuses a syntactic `..` traversal segment delimited by `/` or `\`, a sensitive system file in relative form (`etc/shadow`, `etc/passwd`, `etc/sudoers`) and the macOS private system roots in relative form (`private/var`, `private/etc`, `private/tmp`, `private/root`), so `safe/../../etc/shadow` and `foo/../bar/../../private/var` fail closed before persistence on every shared identifier channel while `workflow:123`, `domain:legal`, `provider/model`, `cmm.orchestration` and `events:read` stay valid; segment-based, with no filesystem I/O, no host path resolution and no second path-policy module); `MAJOR_V7_002=REMEDIATED_REPORTED` (one narrow `contains_uri_userinfo_credential()` rule in the same authority refuses `<scheme>://<name>:<secret>@<authority>` by percent-decoding the userinfo and requiring a non-empty password component, so `https://admin:hunter2hunter2@example.com/path` and `postgres://alice:supersecret@example.com/db` fail closed before persistence while credential-free URIs (`https://example.com/model`, `postgres://example.com/db`) and bare-username userinfo stay valid; the check returns a boolean and the rejection message is a static literal, so the refused secret is never echoed; no second credential policy); `V6_CONCRETE_FINDINGS_FIXED=4/4_PRESERVED`; `V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `REAUDIT_V4_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `AUDIT_V1_FINDINGS_REMEDIATED=9/9_PRESERVED`; `REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_PRESERVED`; `PRIOR_REMEDIATION_REGRESSIONS=477_PASS`; immutable Re-audit V7 report `docs/audits/phase-11.22-event-system-independent-reaudit-v7.md` preserved byte-identical and the immutable V7 bundle `phase-11.22-event-system-audit-v7.tar.gz` (`c388ea63ba885e415703ab771174f3413276092bf65358142b8e3a0c1c4bfe01`) preserved byte-identical; V1/V2/V3/V4/V5/V6 bundles preserved byte-identical; V8 bundle `phase-11.22-event-system-audit-v8.tar.gz` from the exact Remediation V7 HEAD; `CLOSURE_ELIGIBLE=NO` |
| Remediation V8 | `MAJOR_V8_001=REMEDIATED_REPORTED` (the shared identifier/path authority now classifies a **pure lexical canonical analysis form** — separators normalized, repeated separators collapsed, `.` segments elided, `..` detected before any elision, no filesystem I/O and no `Path.resolve()` — behind a **fail-closed public-reference allowlist**, so lexically equivalent spellings of one location receive one identical verdict (`etc/shadow`, `etc//shadow`, `etc/./shadow`, `ETC/SHADOW` and `safe/../etc/shadow` all fail closed) and strong system/private paths no pattern names (`proc/self/environ`, `etc/ssh/ssh_host_rsa_key`, `Windows/System32/config/SAM`, `Library/Keychains/login.keychain-db`) cannot enter persistence; the retained V6/V7 pattern tuple is unchanged in content and is evaluated on the canonical form, and the classifier accepts a slash-bearing reference only when its path-shaped **residue** — what remains once every authority-bearing URI reference is removed — is empty (the value is nothing but credential-free URI references) or is rooted in the declared public logical namespaces `cmm`/`provider`, the complete set a real inventory of every identifier value the suite routes through the authority found in use; because the residue is classified too, `proc/self/environ://x` and `etc/shadow://x` are refused exactly as their plain spellings are rather than being exempted for containing a `://`; `MAJOR_V8_002=REMEDIATED_REPORTED` (the URI userinfo rule is now **occurrence-independent**: every authority-bearing `://` occurrence inside the reference is visited and its authority split at the last `@`, percent-decoded and split at the first `:`, so `jdbc:postgresql://alice:supersecret@example.com/db`, `jdbc:mysql://root:hunter2hunter2@example.com/db`, `provider/https://alice:supersecret@example.com/db`, `foo:https://alice:supersecret@example.com/db` and a credential appearing only in a later authority all fail closed, while credential-free URIs and credential-free wrapped URIs, bare-username userinfo and an empty password stay valid; the rejection message remains a static literal, so the refused secret is never echoed; no second credential policy); `MINOR_V8_001=REMEDIATED_REPORTED` (the high-level Phase 11 row in `ROADMAP.md` now states Re-audits `V2/V3/V4/V5/V6/V7` and "was remediated after all seven", then records the Re-audit V8 failure and the Remediation V8 state); `V7_CONCRETE_FINDINGS_FIXED=2/2_PRESERVED`; `V6_CONCRETE_FINDINGS_FIXED=4/4_PRESERVED`; `V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `REAUDIT_V4_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `AUDIT_V1_FINDINGS_REMEDIATED=9/9_PRESERVED`; `REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_PRESERVED`; `PRIOR_REMEDIATION_REGRESSIONS=604_PASS`; immutable Re-audit V8 report `docs/audits/phase-11.22-event-system-independent-reaudit-v8.md` preserved byte-identical and the immutable V8 bundle `phase-11.22-event-system-audit-v8.tar.gz` (`9b46ed3f941ce63c8ff2249da5762fcfe0f156f073c9864f39d3dffdac3708e9`) preserved byte-identical; V1/V2/V3/V4/V5/V6/V7 bundles preserved byte-identical; V9 bundle `phase-11.22-event-system-audit-v9.tar.gz` from the exact Remediation V8 HEAD; `CLOSURE_ELIGIBLE=NO` |
| Remediation V9 | `MAJOR_V9_001=REMEDIATED_REPORTED` (the **existing** `file:` signature in `_PRIVATE_FILESYSTEM_PATTERNS` is anchored at a path *segment* boundary instead of at character zero: `re.compile(r"(?:^|/)file:", re.IGNORECASE)`. The outer identifier grammar admits a public logical wrapper, and the V8 slash-root allowlist accepted that wrapper, so a non-authority `file:` reference reached through it was never classified: `provider/file:C:/Windows/System32/config/SAM`, `cmm/file:C:/Windows/System32/config/SAM`, `provider/file:C:/Windows/System32/config/SECURITY`, `provider/file:/Windows/System32/config/SAM` and `provider/file:C:/ProgramData/Microsoft/Crypto/RSA/MachineKeys` were all durably persisted through every shared identifier channel, both official repositories and a manual `publish_event(...)` call. Because the pattern is evaluated against the canonical lexical analysis form, whose segments are joined by `/`, a segment boundary is exactly where the identifier grammar can carry a scheme token, and `file` is a case-insensitive URI scheme, so `provider//file:`, `provider/./file:`, `PROVIDER/FILE:` and `File:` receive the identical verdict. No literal was appended for any audited filename or location, so an unnamed wrapped location (`provider/file:/boot/grub/grub.cfg`) is refused by the same structural rule. Analysis-only: no filesystem I/O, no host resolution, no rewriting of an accepted persisted identifier, no second path or URI policy; top-level `file:` refusals, credential-free URIs, `provider/model` / `cmm/orchestration/step` and colon-bearing logical identifiers whose `file` token does not begin a segment (`workflow:file:123`, `req:file:mod`) keep their verdicts; Windows-backslash spellings remain refused earlier by the identifier character set, which is recorded as a positive fail-closed fact and did not require widening the grammar); `MAJOR_V9_002=REMEDIATED_REPORTED` (the frozen `00..23` civil-hour range is asserted explicitly by the same canonical timestamp authority, on the value's own text and **before** the parser is consulted — `MAX_PLATFORM_CIVIL_HOUR = 23` with `_TIMESTAMP_CIVIL_TIME_PATTERN` — so CPython 3.14's widened `datetime.fromisoformat`, which accepted the ISO end-of-day `24:00` and rolled it into the next day, can no longer widen the persisted contract or reopen the retained V6 regression case `2026-09-27T24:00:00Z`. The guard is deliberately limited to the hour because that is the only civil bound the parser demonstrably widened: hour `25`, minute `60`, second `60`, month `13`, day `32`, a fractional end-of-day value and an out-of-range UTC offset are all still refused by `fromisoformat` itself, so no wider parser rewrite was undertaken; no second timestamp parser, no accepted-form change, no normalization change, no Python support-metadata change, and `emitted_at >= occurred_at` chronology is untouched); `MINOR_V9_001=REMEDIATED_REPORTED` (the current non-historical references are synchronized: the stale `tests/events/` `1984 collected / 1983 passed` and `AT-DP-122` `474 passed (250 prior + 224 V8)` are corrected, the `NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE` claim is stated with its scope and only now that the V9-001 remediation made it true, and every current-state marker reads `REMEDIATED_AFTER_REAUDIT_V9_PENDING_INDEPENDENT_REAUDIT`; no historical audit report was rewritten); `V8_CONCRETE_FINDINGS_FIXED=2/2_PRESERVED`; `V7_CONCRETE_FINDINGS_FIXED=4/4_PRESERVED`; `V6_CONCRETE_FINDINGS_FIXED=4/4_PRESERVED`; `V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `REAUDIT_V4_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `AUDIT_V1_FINDINGS_REMEDIATED=9/9_PRESERVED`; `REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_PRESERVED`; `PRIOR_REMEDIATION_REGRESSIONS=1290_PASS` (V1–V9); immutable Re-audit V9 report `docs/audits/phase-11.22-event-system-independent-reaudit-v9.md` preserved byte-identical and the immutable V9 bundle `phase-11.22-event-system-audit-v9.tar.gz` (`1f5908e63a728d440cec6f62607d89fd6b4d9add8d77c941d967c3be139488fa`) preserved byte-identical; V1–V8 bundles preserved byte-identical; V10 bundle `phase-11.22-event-system-audit-v10.tar.gz` from the exact Remediation V9 HEAD; `CLOSURE_ELIGIBLE=NO` |
| Remediation V10 | `MAJOR_V10_001=REMEDIATED_REPORTED` (the **existing** raw Windows drive-root signature in `_PRIVATE_FILESYSTEM_PATTERNS` is anchored at a path *segment* boundary instead of at character zero: `re.compile(r"^[A-Za-z]:[\\/]")` → `re.compile(r"(?:^|/)[A-Za-z]:[\\/]")` — the same structural repair Remediation V9 applied to the structurally identical `file:` token. Remediation V9 had already segment-anchored `file:`, but the raw drive-root token stayed whole-value-anchored, so an allowlisted public slash root could carry a raw local drive past the classifier: `provider/C:/Windows/System32/config/SAM`, `cmm/C:/Windows/System32/config/SAM`, `provider//C:/Windows/System32/config/SAM`, `provider/./C:/Windows/System32/config/SAM` and `provider/C:/Windows/System32/config/SECURITY` each returned non-private from `is_private_filesystem_reference()`, passed `validate_platform_identifier()`, passed canonical `EventSystem` publication and were durably persisted — across all 13 shared identifier-bearing channels, in both official repositories and through a manual `publish_event(...)` call. Because the pattern is evaluated against the canonical lexical analysis form whose segments are joined by `/`, a segment boundary is exactly where the identifier grammar can carry a drive token, so `provider//C:/`, `provider/./C:/`, `Provider/C:/`, `PROVIDER/C:/`, `C://Windows/` and lowercase `provider/c:/` receive the identical verdict. The rule still requires real drive-root syntax — a letter, a colon and a path separator — so ordinary colon identifiers (`workflow:123`, `domain:legal`), segment-boundary non-drive colons (`provider/a:1/model`, `cmm/v2:3/detail`) and credential-free URIs (`https://example.com/model`, `http://localhost:8080/health`, `jdbc:postgresql://example.com/db`, `provider/https://example.com/model`) keep their verdicts, as do the V9 `file:`-token-as-logical-scheme controls (`workflow:file:123`, `req:file:mod`). No literal was appended for `SAM`, `SECURITY`, `Windows`, `System32`, `ProgramData`, `MachineKeys` or any audited drive letter, so fresh probes (`provider/D:/private/example`, `cmm/Z:/tmp/example`, `cmm/E:/ProgramData/Example/config.xml`, `provider/A:/boot/grub/grub.cfg`) are refused by the same structural rule. Analysis-only: no filesystem I/O, no `Path.resolve()`, no host resolution, no rewriting of an accepted persisted identifier, no second path/URI/drive-root policy module; Windows-backslash drive spellings (`C:\Windows\…`) remain refused earlier by the identifier character set, which is recorded as a positive fail-closed fact and did not require widening the grammar); `V9_FINDINGS_FIXED=3/3_PRESERVED`; `V8_CONCRETE_FINDINGS_FIXED=2/2_PRESERVED`; `V7_CONCRETE_FINDINGS_FIXED=4/4_PRESERVED`; `V6_CONCRETE_FINDINGS_FIXED=4/4_PRESERVED`; `V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `REAUDIT_V4_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `AUDIT_V1_FINDINGS_REMEDIATED=9/9_PRESERVED`; `REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_PRESERVED`; `PRIOR_REMEDIATION_REGRESSIONS=1765_PASS` (V1–V10); immutable Re-audit V10 report `docs/audits/phase-11.22-event-system-independent-reaudit-v10.md` preserved byte-identical (`ffe8c5e7d96836643362796c5ccfae29461aaa2d1293cc9ce0a6c210f86d7a8c`) and the immutable V10 bundle `phase-11.22-event-system-audit-v10.tar.gz` (`cd594b857a0882cbc4059afbc01eb1f5d3f760c5ca7aacc1c4e9643bbae35840`) preserved byte-identical; V1–V9 bundles preserved byte-identical; V11 bundle `phase-11.22-event-system-audit-v11.tar.gz` from the exact Remediation V10 HEAD; `CLOSURE_ELIGIBLE=NO` |
| Remediation V11 | `MAJOR_V11_001=REMEDIATED_REPORTED` (Windows defines a drive-*root* path `C:/name` and a drive-*relative* path `C:name`, and the latter is still a drive-qualified local filesystem reference — `ntpath.splitdrive("C:Windows") == ("C:", "Windows")`. The retained drive signature required a path separator after the colon, `re.compile(r"(?:^|/)[A-Za-z]:[\\/]")`, so no canonical signature recognized the drive-relative spelling; and because a value such as `C:id_rsa` contains no separator at all, the final path-shape branch also declined to treat it as path-shaped and returned non-private. `is_private_filesystem_reference("C:id_rsa")` returned `False`, `validate_platform_identifier("C:id_rsa")` accepted, and `C:Windows`, `C:id_rsa`, `C:.ssh`, `D:ProgramData` and `Z:tmp` were durably persisted — across all 13 shared identifier-bearing channels, in both official repositories and through a manual `publish_event(...)` call. `id_rsa` was already a sensitive private-file marker in `_PRIVATE_FILESYSTEM_PATTERNS`, so the drive-designator colon was shielding a known private location. The remediation adds one structurally minimal signature for the drive **designator** itself inside the same canonical classifier and the same `_PRIVATE_FILESYSTEM_PATTERNS` tuple: `re.compile(r"^[A-Za-z]:")`, evaluated on the canonical lexical analysis form **before** any separator heuristic or the generic "no separator means not path-shaped" escape. The rule is anchored to the **start of the whole reference**, because that is the only position where drive-relative syntax has that meaning and because the frozen contract deliberately preserves wrapped *segment-colon* logical identifiers (`provider/a:1/model`, `provider/x:0/step`, `cmm/v2:3/detail`, `cmm/orchestration:step`), which a segment-boundary rule would refuse. The V10 segment-boundary drive-root signature is retained verbatim, so the whole V10 wrapper family keeps its audited verdict and the intentional overlap between the two drive rules is documented in place. Bare `C:` (the drive's current directory), lowercase `c:id_rsa`, `C:a`, `X:foo.bar` and unnamed drives and remainders all receive the identical verdict, and no literal was appended for `Windows`, `ProgramData`, `id_rsa`, `.ssh`, `tmp` or any audited drive letter, so fresh probes (`X:foo.bar`, `E:secret.txt`, `Q:zzz-not-a-real-location`) are refused by the same structural rule. Multi-letter colon identifiers (`workflow:123`, `domain:legal`, `events:read`), wrapped segment-colon logical identifiers, the V9 `file:`-token-as-logical-scheme controls (`workflow:file:123`, `req:file:mod`), plain slash references and credential-free URIs keep their verdicts. Analysis-only: no filesystem I/O, no `Path.resolve()`, no host resolution, no grammar widening, no rewriting of an accepted persisted identifier, no second path/URI/Windows policy module; Windows drive-relative backslash spellings (`C:\Windows`) remain refused earlier by the identifier character set, recorded as a positive fail-closed fact that did not require widening the grammar); `V10_FINDINGS_FIXED=1/1_PRESERVED`; `V9_FINDINGS_FIXED=3/3_PRESERVED`; `V8_CONCRETE_FINDINGS_FIXED=2/2_PRESERVED`; `V7_CONCRETE_FINDINGS_FIXED=4/4_PRESERVED`; `V6_CONCRETE_FINDINGS_FIXED=4/4_PRESERVED`; `V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `REAUDIT_V4_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `AUDIT_V1_FINDINGS_REMEDIATED=9/9_PRESERVED`; `REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_PRESERVED`; `PRIOR_REMEDIATION_REGRESSIONS=2473_PASS` (V1–V11); immutable Re-audit V11 report `docs/audits/phase-11.22-event-system-independent-reaudit-v11.md` preserved byte-identical (`2936efb2a17a45838379c586b9ba34d31c158a14091b99d30b9bb6f3094534e2`) and the immutable V11 bundle `phase-11.22-event-system-audit-v11.tar.gz` (`e53b7942f264aaf47045d6c4a7566dc68a796ce0b99488d8561f2c34b8d03a59`) preserved byte-identical; V1–V10 bundles preserved byte-identical; V12 bundle `phase-11.22-event-system-audit-v12.tar.gz` from the exact Remediation V11 HEAD; `CLOSURE_ELIGIBLE=NO` |
| Remediation V12 | `MAJOR_V12_001=REMEDIATED_REPORTED` (the canonical sensitive-private-filename signature already declared the family `id_rsa`, `id_dsa`, `id_ecdsa`, `id_ed25519`, `known_hosts`, but its own rule had two Windows-semantic blind spots, so an already-sensitive private basename stopped being classified as private: the match was case-sensitive although a Windows filename is case-insensitive — so `ID_RSA`, `KNOWN_HOSTS` and `Id_Ed25519.pub` passed — and its only accepted suffix boundary was end-of-value or a literal `.`, although `ntfs` defines `name:stream` as the `stream` alternate data stream of the file `name`, so `id_rsa:stream`, `known_hosts:ads`, `id_ed25519:foo` and `id_ecdsa:data` still denote the private file before the colon. The allowlisted public logical wrappers reached the same verdict: `provider/ID_RSA`, `provider/id_rsa:stream` and `cmm/known_hosts:ads` were admitted by the slash-root allowlist while no signature recognized the basename they carried. `is_private_filesystem_reference("id_rsa:stream")` returned `False`, `validate_platform_identifier("id_rsa:stream")` accepted, and the value was durably appended through all 13 shared identifier-bearing channels, in both official repositories and through a manual `publish_event(...)` call; reopening the file-backed store revealed the exact unsafe value. The remediation repairs that one **existing** signature in the same canonical `_PRIVATE_FILESYSTEM_PATTERNS` tuple: `re.compile(r"(?:^|[\\/])(?:id_rsa|id_dsa|id_ecdsa|id_ed25519|known_hosts)(?:$|[.:])", re.IGNORECASE)`. `:` becomes a suffix boundary exactly as `.` already was, and the already-declared basename family is matched case-insensitively. The invariant is deliberately narrow: the rule stays anchored to the start of the reference or of a path segment, so a colon-bearing identifier whose segment does not *start* with an already-sensitive basename keeps its verdict — `workflow:123`, `domain:legal`, `events:read`, `provider/a:1/model`, `cmm/v2:3/detail`, `provider/model`, `model:id_rsa`, `workflow:id_rsa`, and the generic non-sensitive named-stream controls `foo.txt:stream` and `provider/foo.txt:stream`. No literal was appended for `ID_RSA`, `KNOWN_HOSTS`, `Id_Ed25519`, `stream`, `ads`, `foo` or `data`, so fresh casings and stream names (`Id_Rsa`, `id_RSA`, `Known_Hosts`, `ID_DSA.PUB`, `ID_ECDSA`, `ID_RSA:STREAM`, `Known_Hosts:ADS`, `id_dsa:stream`, `provider/id_ed25519:foo`, `cmm/id_ecdsa:data`) are refused by the same structural rule. No generic colon is banned, no generic `filename:stream` form is refused, no identifier grammar was widened, and no accepted identifier is lowercased or rewritten — case-insensitivity is a classification input only. Analysis-only: no filesystem I/O, no `Path.resolve()`, no second parser, scanner, ADS policy, registry or subsystem; Windows-backslash spellings (`.ssh\id_rsa`) remain refused earlier by the identifier character set, recorded as a positive fail-closed fact that did not require widening the grammar); `V11_FINDINGS_FIXED=1/1_PRESERVED`; `V10_FINDINGS_FIXED=1/1_PRESERVED`; `V9_FINDINGS_FIXED=3/3_PRESERVED`; `V8_CONCRETE_FINDINGS_FIXED=2/2_PRESERVED`; `V7_CONCRETE_FINDINGS_FIXED=4/4_PRESERVED`; `V6_CONCRETE_FINDINGS_FIXED=4/4_PRESERVED`; `V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `REAUDIT_V4_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_PRESERVED`; `AUDIT_V1_FINDINGS_REMEDIATED=9/9_PRESERVED`; `REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_PRESERVED`; `PRIOR_REMEDIATION_REGRESSIONS=2473_PASS` (V1–V11); immutable Re-audit V12 report `docs/audits/phase-11.22-event-system-independent-reaudit-v12.md` preserved byte-identical (`926a9fb3ca1df72c8f8c27b5746aac9001147d262f2bb762e96576f9130204b8`) and the immutable V12 bundle `phase-11.22-event-system-audit-v12.tar.gz` (`c46e717a916c80cd6ffce7ba54e08896cc3826ba6d4b5a1a4ac460d46330bd2a`) preserved byte-identical; V1–V11 bundles preserved byte-identical; V13 bundle `phase-11.22-event-system-audit-v13.tar.gz` from the exact Remediation V12 HEAD; `CLOSURE_ELIGIBLE=NO` |
| Test evidence | `tests/events/` — 5045 passed, 0 failed; `AT-DP-122` — 1039 passed (889 prior + 150 V12); Remediation V12 adversarial regressions — 916 passed (initial red 396 failed / 520 passed); Remediation V11 adversarial regressions preserved — 708 passed (initial red 328 failed / 380 passed); Remediation V10 adversarial regressions preserved — 475 passed; Remediation V9 adversarial regressions preserved — 397 passed; Remediation V8 adversarial regressions preserved — 289 passed; Remediation V7 adversarial regressions preserved — 127 passed; Remediation V6 regressions preserved — 127 passed (the retained civil-time case `2026-09-27T24:00:00Z` is now green, because Remediation V9 asserts the frozen `00..23` hour bound explicitly instead of delegating it to `datetime.fromisoformat`); Remediation V5 regressions preserved — 71 passed; Remediation V4 regressions preserved — 23 passed; Remediation V3 regressions preserved — 44 passed; Remediation V2 regressions preserved — 126 passed; Remediation V1 regressions preserved — 86 passed (prior remediation regressions preserved — 2473 passed, V1–V11); kernel adapter — 76 passed; security/architecture gates — 294 passed; Phase 10.33 Domain Events — 11824 passed (DP-033 acceptance — 92 passed); event inventory `tests/**/*event*.py` — 1270 passed; closed-phase acceptances — 185 passed, 1 warning; platform architecture — 69 passed; orchestration event tests — 498 passed; validation event tests — 533 passed; workflow event tests — 46 passed; Phase 9 runtime regressions — 3635 passed; global `pytest -q` — 27114 collected, 27114 passed, 1 warning, **0 failed**, so `GLOBAL_PYTEST_FAILURES=0` is met at a pass count of `27114` against the `26048` floor (see the implementation evidence §21.7) |
| Ruff / format / compile | changed and new Phase 11.22 files `ruff check`-clean and `ruff format --check`-clean (Remediation V12: `CHANGED_FILE_RUFF=PASS`, `FORMAT_CHECK=PASS`, `GLOBAL_RUFF_COUNT=810` against the V12 baseline `810`, `GLOBAL_RUFF_NO_NEW_DEBT=PASS`; Remediation V11: `CHANGED_FILE_RUFF=PASS`, `FORMAT_CHECK=PASS`, `GLOBAL_RUFF_COUNT=810` against the V11 baseline `810`, `GLOBAL_RUFF_NO_NEW_DEBT=PASS`; Remediation V10: `CHANGED_FILE_RUFF=PASS`, `FORMAT_CHECK=PASS`, `GLOBAL_RUFF_COUNT=810` against the V10 baseline `810`, `GLOBAL_RUFF_NO_NEW_DEBT=PASS`; Remediation V9: `CHANGED_FILE_RUFF=PASS`, `FORMAT_CHECK=PASS`, `GLOBAL_RUFF_COUNT=810` against the V9 baseline `810`, `GLOBAL_RUFF_NO_NEW_DEBT=PASS`; Remediation V8: `CHANGED_FILE_RUFF=PASS`, `FORMAT_CHECK=PASS`, `GLOBAL_RUFF_COUNT=810` against the V8 baseline `810`, `GLOBAL_RUFF_NO_NEW_DEBT=PASS`; Remediation V7: `CHANGED_FILE_RUFF=PASS`, `FORMAT_CHECK=PASS`, `GLOBAL_RUFF_COUNT=810` against the V7 baseline `810`, `GLOBAL_RUFF_NO_NEW_DEBT=PASS`); global Ruff `810` (`ruff check cmm kernel tests`) against the frozen pre-existing baseline `811` and the V2 implementation HEAD `810` (`RUFF_NEW_FINDINGS=0`; the single delta is one pre-existing violation removed while editing `tests/conftest.py` under Remediation V1); `COMPILEALL=PASS`; `GIT_DIFF_CHECK=PASS` |
| One-authority gates | `ONE_CANONICAL_EVENT_BUS=PASS`; `ONE_CANONICAL_EVENT_REGISTRY=PASS`; `ONE_CANONICAL_EVENT_REPOSITORY_CONTRACT=PASS`; `ONE_CANONICAL_REPLAY_OWNER=PASS`; `NO_PARALLEL_DLQ_AUTHORITY=PASS`; `NO_BROKER_ABSTRACTION=PASS`; `NO_SERVICE_LOCATOR=PASS`; `NO_SECOND_CONTAINER=PASS`; `NO_DYNAMIC_EVENT_TYPE_DISPATCH=PASS` |
| Security gates | `WINDOWS_SENSITIVE_PRIVATE_FILENAME_EQUIVALENTS_NEVER_ENTER_EVENT_PERSISTENCE=PASS` (established by Remediation V12; the already-declared private key material family — `id_rsa`, `id_dsa`, `id_ecdsa`, `id_ed25519`, `known_hosts` — keeps its private character under case variation and under an NTFS named-stream `:` suffix, so the invariant is stated only now that it is actually true); `SENSITIVE_PRIVATE_FILENAME_BASENAMES_ARE_CASE_INSENSITIVE=PASS` (Remediation V12); `SENSITIVE_PRIVATE_FILENAME_NTFS_NAMED_STREAM_SUFFIX_IS_A_BOUNDARY=PASS` (Remediation V12); `GENERIC_COLON_IDENTIFIERS_REMAIN_VALID=PASS` (Remediation V12; `workflow:123`, `domain:legal`, `events:read`, `provider/a:1/model`, `cmm/v2:3/detail`, `model:id_rsa` and every wrapped segment-colon logical identifier keep their verdict); `GENERIC_NON_SENSITIVE_NAMED_STREAM_REFERENCES_REMAIN_VALID=PASS` (Remediation V12; `foo.txt:stream` and `provider/foo.txt:stream` keep their verdict); `RELATIVE_PATH_TRAVERSAL_REJECTED_BEFORE_PERSISTENCE=PASS`; `URI_USERINFO_CREDENTIALS_REJECTED_BEFORE_PERSISTENCE=PASS`; `URI_USERINFO_CREDENTIALS_REJECTED_REGARDLESS_OF_PREFIX_OR_WRAPPER=PASS`; `WINDOWS_DRIVE_RELATIVE_REFERENCES_NEVER_ENTER_EVENT_PERSISTENCE=PASS` (established by Remediation V11; a whole-value Windows drive designator — rooted `C:/…` or drive-relative `C:…` — is refused before persistence, so the invariant is stated only now that it is actually true); `WINDOWS_DRIVE_DESIGNATOR_PATHS_ARE_CLASSIFIED_BEFORE_SEPARATOR_HEURISTICS=PASS` (established by Remediation V11; the designator rule is evaluated on the canonical analysis form before any separator heuristic or the generic no-separator escape); `WRAPPED_WINDOWS_DRIVE_ROOT_REFERENCES_HAVE_THE_SAME_UNSAFE_CLASSIFICATION_AS_TOP_LEVEL_DRIVE_ROOT_REFERENCES=PASS` (established by Remediation V10; the invariant is stated only now that a raw drive-root reference carried behind an allowlisted public slash root is actually refused before persistence); `WRAPPED_FILE_URI_REFERENCES_HAVE_THE_SAME_UNSAFE_CLASSIFICATION_AS_TOP_LEVEL_FILE_URI_REFERENCES=PASS` (established by Remediation V9; the invariant is stated only now that the wrapped non-authority `file:` family is actually refused, which the V8 state did not achieve); `NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE=PASS` (established by Remediation V9 for the complete family, top-level and wrapped, extended by Remediation V10 to wrapped raw drive-root references and by Remediation V11 to whole-value drive-relative references); `PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION=PASS`; `PHASE11_22_TIMESTAMP_ACCEPTANCE_IS_INTERPRETER_VERSION_INDEPENDENT=PASS` (established by Remediation V9); `CREDENTIALS_NEVER_ENTER_EVENT_PERSISTENCE=PASS`; `NO_SECOND_PATH_POLICY_MODULE=PASS`; `NO_SECOND_DRIVE_ROOT_POLICY_MODULE=PASS`; `NO_SECOND_CREDENTIAL_POLICY=PASS`; `NO_SECOND_TIMESTAMP_PARSER=PASS`; `EVENTS_GRANT_NO_AUTHORITY=PASS`; `REPLAY_GRANTS_NO_AUTHORITY=PASS`; `UNKNOWN_PLATFORM_EVENT_TYPE_FAILS_CLOSED=PASS`; `PROMPTS_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD=PASS`; `HIDDEN_REASONING_NEVER_ENTERS_ANY_PERSISTED_EVENT_FIELD=PASS`; `CREDENTIALS_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD=PASS`; `RAW_PROVIDER_PAYLOADS_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD=PASS`; `OPAQUE_VALUES_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD=PASS`; `BINARY_MEMORYVIEW_REJECTED_EVERYWHERE=PASS`; `BINARY_BUFFER_VALUES_FAIL_CLOSED=PASS`; `BINARY_BUFFER_VALUES_NEVER_BECOME_INTEGER_ARRAYS=PASS`; `RAW_USER_TEXT_CANNOT_BE_RELOCATED_INTO_LIFECYCLE_FIELDS=PASS`; `METADATA_IS_NOT_A_PROSE_SIDE_CHANNEL=PASS`; `IDENTIFIER_FIELDS_ARE_SEMANTICALLY_BOUNDED=PASS`; `CATEGORICAL_FIELDS_ARE_SEMANTICALLY_BOUNDED=PASS`; `BOOLEAN_FIELDS_REQUIRE_BOOLEAN_VALUES=PASS`; `NUMERIC_FIELDS_REQUIRE_NUMERIC_VALUES=PASS`; `LIFECYCLE_FACT_ONLY_POLICY=PASS`; `DLQ_SECRET_SAFETY_FAILS_SAFE_WITHOUT_EXTERNAL_BINDING=PASS`; `BINARY_VALUES_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD=PASS`; `DLQ_SECRET_SAFETY=PASS`; `RAW_EXCEPTION_MESSAGE_NOT_STORED=PASS`; `UNSAFE_EXCEPTION_CLASS_NAME_NOT_STORED=PASS`; `NONFINITE_NUMBERS_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD=PASS`; `CANONICAL_SENSITIVITY_TYPE_ENFORCED=PASS`; `INVALID_PERMISSION_CONTAINER_FAILS_CLOSED=PASS`; `SOURCE_SENSITIVITY_IS_NOT_DOWNGRADED=PASS`; `CORRUPT_PERSISTED_EVENTS_FAIL_CLOSED=PASS`; `SAME_ID_DIFFERENT_CONTENT_FAILS_CLOSED=PASS`; `REPLAY_TO_SIDE_EFFECT_SUBSCRIBERS_DEFAULT_DENIED=PASS`; `DLQ_REPLAY_CANNOT_BYPASS_SUBSCRIBER_POLICY=PASS` |
| Persistence gates | `COMPLETE_CONTENT_FINGERPRINT=PASS`; `SAME_ID_DIFFERENT_CONTENT_FAILS_CLOSED=PASS`; `TAMPER_DETECTION=PASS`; `MALFORMED_RECORD_CANONICAL_CORRUPTION=PASS`; `UNSUPPORTED_SCHEMA_REJECTED_BEFORE_APPEND=PASS`; `SUPPORTED_SCHEMA_REOPEN_ROUNDTRIP=PASS`; `SAFE_NESTED_MAPPING_PUBLICATION=PASS`; `SAFE_NESTED_SEQUENCE_PUBLICATION=PASS`; `LIVE_EVENT_FACTS_STABLE_AFTER_DELIVERY=PASS`; `FILE_LIVE_AND_REOPENED_FACTS_MATCH=PASS`; `PUBLICATION_RESULT_ALIAS_ISOLATION=PASS`; `SUBSCRIBER_MUTATION_ISOLATION=PASS`; `REPOSITORY_SNAPSHOT_ISOLATION=PASS`; `FINGERPRINT_STABLE_AFTER_PUBLICATION=PASS`; `MANUAL_PUBLISH_EVENT_SENSITIVITY_CANONICAL=PASS`; `IN_MEMORY_AND_FILE_REPOSITORY_PARITY=PASS` |
| Inherited constraints | `F11-021` / `DP-150`, `F11-020` / `DP-121`, `F11-019` / `DP-105`, `F11-018` / `DP-104`, `F11-017` / `DP-103`, `F11-016` / `DP-102`, `F11-015` / `DP-101`, `F11-014` / `DP-134`, Phase 10.33 Domain Events, Phase 7 Continuous Validation and Phase 9 Autonomous Agent Runtime remained the canonical authorities and were **not architecturally replaced or reopened as a new phase**; Phase 9 received **bounded additive compatibility hardening** under Phase 11.22 — the accepted subscription `event_types` delivery correction, the accepted replay no-re-save correction, and the minimal additions Phase 11.22 requires (bounded `max_delivery_attempts`, replay-authorised dispatch, DLQ binding, optional `producer`/`aggregate_id`, `accept_replay`, `retry_total`, content-bound `event_fingerprint`, and the durable repository implementation) — while its contracts, identity and authority were preserved; the Phase 10.33 Domain Event and Phase 7 validation contracts were referenced without modification; closed-phase connected regressions all `PASS` |
| Reserved (registered, never emitted) | `session.created`; `reasoning.completed`; `knowledge.updated`; `backup.created`; `plugin.failed`; `security.alert` |
| Provenance deviation | preflight requested `HEAD=d691c753c25801d1957fc8dee917ef4e6fff4694`; actual starting HEAD `744de6d996e0aa3dc3f9326fdb33fc38ab13ac8d` (parent exactly `d691c753`, tree exactly the required `36255f0293ac23fe93c2c85c94b989dd91ca0ff2`), the only delta being this phase's own committed prompt document and **zero** production-code differences; explicitly authorized by the user; no reset, checkout, stash, clean or worktree operation performed |
| Next step | fresh independent ChatGPT re-audit of the exact-HEAD Phase 11.22 V13 bundle (`phase-11.22-event-system-audit-v13.tar.gz`); Phase 11.22 is not closed, not independently verified and not complete; Phase 11.23 and Phase 11.24 are **not** begun |

<!-- PHASE11_22_REMEDIATED_AFTER_REAUDIT_V12_PENDING_INDEPENDENT_REAUDIT -->
