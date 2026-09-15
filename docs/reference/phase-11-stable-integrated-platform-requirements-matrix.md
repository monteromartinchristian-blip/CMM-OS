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
| `F11-014` | Maintain one canonical, persistent, auditable and fail-closed Provider Registry in which provider identity is authoritative through `ProviderRegistry`, manifests/connections/models/routes are referentially coherent, subscription isolation policy is explicit, onboarding side effects are ownership-safe, discovery remains non-inference, and `DP-134` is verified through `AT-DP-134`. | `SRC-R11` (detailed Phase 11 roadmap §11.34); `docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v2-design.md` §10 | Phase 11 | `kernel/llm/provider_registry.py`; `kernel/llm/provider_manifests.py`; `kernel/llm/provider_connections.py`; `kernel/llm/model_routes.py`; `kernel/llm/model_discovery.py`; `kernel/llm/provider_onboarding.py`; `kernel/llm/provider_state.py`; `kernel/llm/provider_state_repository.py`; `kernel/llm/provider_state_coordinator.py` | `IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT` | `AT-DP-134` — `tests/llm/test_provider_registry_dp134_acceptance.py` |

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
| Remediation V1 design | `docs/superpowers/specs/2026-09-14-phase-11.34-provider-registry-remediation-v1-design.md` (historical: implemented, then audited by Independent Re-audit V2 `FAIL`) |
| Remediation V1 plan | `docs/superpowers/plans/2026-09-14-phase-11.34-provider-registry-remediation-v1-implementation-plan.md` (historical) |
| Remediation V2 design | `docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v2-design.md` — froze the remedy for the five Re-audit V2 findings |
| Remediation V2 plan | `docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v2-implementation-plan.md` (historical: implemented, then audited by Independent Re-audit V3 `FAIL`) |
| Remediation V3 design | `docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v3-design.md` (historical: implemented, then audited by Independent Re-audit V4 `FAIL`) |
| Remediation V3 plan | `docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v3-implementation-plan.md` (historical) |
| Remediation V4 design | `docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v4-design.md` — freezes the remedy for exactly the four Re-audit V4 findings, and changes no design point (`DP-134` unchanged) |
| Remediation V4 plan | `docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v4-implementation-plan.md` — implements that remedy; `REMEDIATION_V4=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT` |
| Remediated findings | `MAJOR-V3-01` (canonical graph identity), `MAJOR-V3-02` (durable route refresh) and `MINOR-V3-01` (format gate evidence) were verified remediated by Independent Re-audit V4. `MAJOR-V4-01` (item-level authority binding), `MAJOR-V4-02` (acceptance-time proposal authority), `MAJOR-V4-03` (discovery manifest authority) and `MINOR-V4-01` (monotonic discovery snapshots) are remediated and pending Independent Re-audit V5; none of them is independently verified yet |
| Lifecycle status | `IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT` |
| Audit status | `PENDING_INDEPENDENT_REAUDIT_V5` |

Persisted-shape note: the V2 persisted manifest shape carries the explicit
isolation policy (`requires_isolation`), which is why `SCHEMA_VERSION` is `"2"`.
Documents written before that change are rejected rather than silently
reinterpreted, and the state envelope still carries opaque `credential_ref`
values only — never secret material.

## 5. Current lifecycle status

```text
PHASE11_34=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V2=FAIL
INDEPENDENT_REAUDIT_V3=FAIL
INDEPENDENT_REAUDIT_V4=FAIL
REMEDIATION_V4=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
F11-014=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
DP-134=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
AT-DP-134=PASS_REPORTED
CLOSURE_ELIGIBLE=NO
AUDIT_STATUS=PENDING_INDEPENDENT_REAUDIT_V5
```

This is the complete current state and the maximum documentary state allowed
before Independent Re-audit V5. `REMEDIATION_V1`, `REMEDIATION_V2` and
`REMEDIATION_V3` are historical context, not current-state markers: each was
implemented and committed, then independently audited by a later re-audit that
returned `FAIL` (Re-audit V2: `BLOCKERS=0`; `MAJORS=5`; `MINORS=0`; Re-audit V3:
`BLOCKERS=0`; `MAJORS=2`; `MINORS=1`; Re-audit V4: `BLOCKERS=0`; `MAJORS=3`;
`MINORS=1`). Re-audit V3 verified `MAJOR-V2-03`, `MAJOR-V2-04` and
`MAJOR-V2-05` as remediated and carried `MAJOR-V2-01` and `MAJOR-V2-02` forward
as `MAJOR-V3-01` and `MAJOR-V3-02`. Re-audit V4 verified `MAJOR-V3-01` and
`MAJOR-V3-02` as remediated and opened the deeper authority/coherence layer
`MAJOR-V4-01`, `MAJOR-V4-02`, `MAJOR-V4-03` and `MINOR-V4-01`. Remediation V4
(design/plan linked in §4.2) closes exactly those four Re-audit V4 findings, and
they are remediated and pending Independent Re-audit V5. No audit report was
rewritten, and no design point was changed: `DP-134` remains the single closure
design point for Phase 11.34.

`AT-DP-134=PASS_REPORTED` means the connected
acceptance was executed on the implementation machine and its evidence is
recorded; it is **not** an independent verification of the acceptance.
Therefore, before Independent Re-audit V5:

- `DP-134`, `AT-DP-134` and `F11-014` are **not** independently verified;
- no artifact in this repository may claim a verified, passing or
  closure-eligible state for them; the reserved tokens for that state are
  reproduced in §6 and are unclaimed;
- Phase 11.34 is not closed, and this matrix is not closure evidence.

## 6. Future closure criteria

`VERIFIED_EXISTING`, `PASS` and `CLOSURE_ELIGIBLE=YES` are reserved for the
post-V5 docs-only closure and are reproduced below **only** as unclaimed future
closure criteria for Independent Re-audit V5. They are not current state. The
line immediately below labels this block; the repository-wide check that no
current-state claim exists outside such a labelled block lives in
`tests/llm/test_provider_registry_dp134_acceptance.py`.

**Future closure criteria — post-Independent-Re-audit-V5 only; not current state:**

```text
BLOCKERS=0
MAJORS=0
DP-134=VERIFIED_EXISTING
AT-DP-134=PASS
F11-014=VERIFIED_EXISTING
CLOSURE_ELIGIBLE=YES
PHASE11_34=CLOSED
```

Until an independent verdict reaches that state, the current status in §5
stands unchanged.

## 7. Deferred scope recorded with this requirement

- CMM Usage integration: deferred and not performed; no Usage Registry bridge
  exists in the Provider Registry surface (`CMM_USAGE_INTEGRATION=NOT_PERFORMED`).
- CMMChat integration: deferred by the user; no CMMChat provider execution
  integration is introduced by Phase 11.34.
- Phase 11.35 Routing Policy Engine: not started; no routing policy is
  implemented here.
- No parallel provider inventory, persistence framework, isolation runtime,
  validation engine, routing engine, event bus or usage catalog is introduced.
