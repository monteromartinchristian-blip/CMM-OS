# Phase 10.45 — MAJOR-03 Architectural Block Evidence (Remediation V1)

```text
RESULT=MAJOR_03=ARCHITECTURAL_BLOCKED_BY_APPROVED_SPEC
DATE=2026-09-09
INSPECTED_HEAD=e566f148af6743d0014823f556ea58fd9f07ef5b
REMEDIATION_PROMPT_REF=phase-10.45-remediation-v1-agent-prompt.md §6 Outcome B
AUDIT_REF=docs/audits/phase-10.45-independent-audit-v1.md (§6 MAJOR-03)
```

## 1. Finding under remediation

Independent Audit V1 MAJOR-03: for `ADD_SUPPORTING`, even a canonical
permission `ALLOW` is returned as `accepted=False / UNAVAILABLE /
domain_selector_supporting_application_unavailable`, and
`WITHDRAW_SUPPORTING` always returns unavailable after membership validation.
The audit requires both intents to "delegate through canonical
composition/session selection authority" so the actions complete
(audit item 2), while forbidding direct mutation of
`DomainResolutionResult` / `DomainComposition` / `DomainSessionContext`
(audit item 3) and creation of a new selector store, session store,
composition engine or policy engine (audit item 4). Audit item 6 prescribes:
if repository inspection proves no safe canonical authority can perform
these roadmap-required actions, stop and escalate as an architectural
incompatibility requiring explicit design amendment.

The remediation prompt §6 Outcome B permits exactly one terminal state when
such authority does not exist: this evidence note, the report line
`MAJOR_03=ARCHITECTURAL_BLOCKED_BY_APPROVED_SPEC`, and a stop before bundle
creation. Implementing nothing else is intentional.

## 2. Files and symbols inspected (fresh, at HEAD e566f14)

Production (all under `cmm/domains/`):

- `interface_integration.py` — `submit_intent` (lines 959-1077),
  `_permission_verdict` ALLOW branch (835-839), `WITHDRAW_SUPPORTING`
  branch (996-1007), `ADD_SUPPORTING` branch (1040-1074);
  `DefaultDomainInterfaceIntegrator.__init__` (876-883): the integrator is
  constructed only with `resolver` and `permission_resolver`.
- `resolver.py` — `DefaultDomainResolver.resolve`, `_select_supporting`
  (1383-1466); `required_domains` reads at 207, 1293-1306, 1405, 1577.
- `resolution_contracts.py` — `DomainResolutionContext` (explicit /
  available / authorized / active domains, signals, `system_policy`;
  no supporting-membership input), `DomainResolutionPolicy` (only
  allowed/denied/required/high-impact domains plus confidence flags).
- `selection.py` — pure helpers only: `candidate_selection_confidence`,
  `explicit_candidates`, `domain_signal_candidates`,
  `build_domain_selection_transition` (diff-only transition builder; no
  side effects, no persistence).
- `selection_contracts.py` — `DomainSelectionPolicy`,
  `DomainSelectionTransition`; no membership-delta semantics.
- `composer.py` — `DefaultDomainComposer.compose` / `recompose` (425+);
  documented "No registry, no stores, no filesystem, no LLM, no network"
  (394): composition is pure; nothing persists `DomainComposition`.
- `session_contracts.py` — `DomainSessionContext` (session_id,
  primary_domain, supporting_domains snapshot, composition_id,
  last_resolution_id, revision); `DomainSessionResumeRequest` (902+):
  session_id/actor/temporal_reference/current_resource_versions/
  current_knowledge_versions/metadata — no membership-change field.
- `session_resumer.py` — `DomainSessionResumer.resume`: re-resolution is
  triggered only by blocking findings AND an inactive primary (514-516,
  651-664), resolution context explicit_domains = old supporting domains
  (532-536), resulting supporters filtered to active domains only
  (640-644); with the primary active, any remaining blocking finding
  returns BLOCKED/INCOMPATIBLE (666-682); supporting pruning drops only
  no-longer-active domains (693-701) recorded as
  `RECOMPOSITION_SUPPORTING_DISABLED` (841-851); composition is then
  recomposed and the session persisted with revision+1 (722-824,
  1078-1124). The flow is registry-lifecycle-reactive, not command-driven.
- `session_persistence.py` — `SharedSessionDomainAdapter.load_domain_session`
  (71), `save_domain_session` (88, revision+1 enforcement),
  `update_domain_session` (151, generic load-modify-commit primitive with
  no re-resolution/recomposition).
- `permission_resolution.py` / `permission_contracts.py` —
  `DomainPermissionResolver.resolve_cross_domain` returns decisions only
  (DENY / APPROVAL_REQUIRED / ALLOW); nothing applies a membership change.
- `cross_domain_engine.py` — `DefaultCrossDomainEngine.execute` performs
  knowledge transfer, not session membership.
- `api.py` — `DefaultDomainAPI` facade forwards
  `project_interface` / `submit_interface_intent` to the stateless
  integrator; no membership-application service is exposed.

Approved design/plan and roadmap records:

- `docs/superpowers/plans/2026-09-08-phase-10.45-interface-integration-implementation-plan.md`
  §5 (880-912): dependencies must be "the exact existing canonical"
  services; creating "a new authority abstraction, or an interface-owned
  mutation service" is forbidden (900-903); ADD_SUPPORTING /
  WITHDRAW_SUPPORTING are to delegate through the canonical
  composition/session selection path (909-910).
- `docs/superpowers/specs/2026-09-08-phase-10.45-integration-with-interfaces-design.md`
  §11.1 (570-595): the selector must not modify resolution, composition,
  registry, permission, session or policy state "by assignment or direct
  store access"; delegation to existing authority only.
- `docs/roadmap/phase-10-domain-intelligence.md` (6137): implemented-scope
  record states ADD_SUPPORTING "ALLOW→UNAVAILABLE" and "zero
  composition/session mutation" for Phase 10.45.
- `tests/domains/test_domain_interface_integration.py` (2210-2486) and
  `tests/domains/test_domain_interface_dp045_acceptance.py` (1025-1076):
  only DENY→BLOCKED, APPROVAL_REQUIRED→PENDING and eligibility-failure
  branches are exercised; no end-to-end canonical add/withdraw success
  test exists anywhere in the repository.

## 3. Canonical seams that exist

- Resolver authority for primary preference and derived supporting
  selection (re-resolution with an explicit context).
- Pure composition (no persistence outside `DomainSessionResumer.resume`).
- Registry-lifecycle-driven session resumption
  (`DomainSessionResumer.resume`) — the only flow that combines
  re-resolution → recomposition → revisioned session persistence.
- Generic load-modify-commit session persistence
  (`SharedSessionDomainAdapter`).
- Decision-only cross-domain permission authority.
- Read-only selection transition builder (`selection.py`).

## 4. Why none can satisfy the approved add/withdraw behavior

`ADD_SUPPORTING`: permission `ALLOW` establishes eligibility only; the
audit itself accepts DENY rejection and APPROVAL_REQUIRED pending. No
canonical seam accepts "include domain T as a supporting member of the
current composition" as a command:

- `DomainResolutionContext` / `DomainResolutionPolicy` express no
  supporting-membership request: `explicit_domains` steer primary
  selection (two explicit eligible domains become AMBIGUOUS), and
  `system_policy.required_domains` is a global policy lever unrelated to a
  user-issued selector intent; `denied_domains` / missing authorization
  remove availability entirely.
- `DomainSessionResumer.resume` cannot be commanded: its request carries
  no membership delta, its metadata is not consumed as a change request,
  and it re-resolves only when blocking findings coincide with an inactive
  primary; a healthy active session cannot route through it.
- `composer.recompose` is pure and unpersisted outside `resume()`.
- Hand-building a `DomainSessionContext` with revised `supporting_domains`
  through `update_domain_session` would be ad-hoc state patching of the
  canonical derived snapshot — the direct mutation the audit prohibits and
  that MAJOR-01 coherence checks exist to reject.

`WITHDRAW_SUPPORTING`: no lever of any kind removes a currently composed
supporting domain while it remains otherwise available and active; the
only canonical removal path is registry lifecycle (disable/deactivate →
`RECOMPOSITION_SUPPORTING_DISABLED`), and driving it from a selector
intent would be a prohibited registry side effect.

## 5. Why adding the missing authority would exceed Phase 10.45 scope

- A commanded membership-application service (accept a selector intent →
  re-resolution with pinned membership → recomposition → revisioned
  session persistence) is exactly the "selector store / session selector /
  second composer / mutation service" that audit item 4 and remediation
  prompt §6 Outcome B forbid Phase 10.45 from inventing.
- The approved implementation plan binds Phase 10.45 dependencies to the
  canonical services discovered in Task 0 and forbids a new authority
  abstraction or interface-owned mutation service; the approved design
  §11.1 likewise forbids direct or store-level mutation by the selector.
- The approved roadmap implemented-scope record already documents Phase
  10.45 as "zero composition/session mutation"; the shipped
  `UNAVAILABLE` tokens state the missing seam explicitly rather than
  pretending application happened.
- Extending canonical session authority with commanded membership changes
  is therefore a design-level addition (new or amended canonical service +
  contract + orchestration + persistence semantics), which requires an
  explicit design amendment before any implementation — it cannot be
  realized inside the four-MAJOR remediation.

## 6. Verdict and required next step

Outcome B applies. The behavior is not silently left as `UNAVAILABLE`
while claiming remediation complete: this record escalates the
architectural incompatibility. MAJOR-01, MAJOR-02 and MAJOR-04 are not
remediated in this pass because the remediation prompt §6 Outcome B stops
implementation here and requires explicit human/ChatGPT design amendment
before continuing.

Candidate amendment directions (informational only, nothing implemented):

1. Amend the approved design/plan to add commanded supporting-membership
   application to canonical session authority in a later phase, with
   Phase 10.45 binding to it; or
2. Formally amend the approved Phase 10.45 behavior so ADD_SUPPORTING /
   WITHDRAW_SUPPORTING are defined as eligibility/verdict intents
   (ALLOW → application deferred to the later platform), and re-audit
   against that amended design, including an amended AT-DP-045.

## 7. Repository state at stop

```text
HEAD=e566f148af6743d0014823f556ea58fd9f07ef5b (unchanged; no remediation commits)
WORKTREE=CLEAN (this evidence record committed)
QUARANTINE_STASH=PRESERVED (stash@{0})
AUDIT_V1=UNMODIFIED
OLD_BUNDLE=UNMODIFIED (phase-10.45-audit-1a1c29795d572e97e2f34765da979c558a6b179e.tar.gz)
BUNDLE_V2=NOT_CREATED (stop before bundle creation per Outcome B)
PUSH=NO MERGE=NO REBASE=NO
PHASE_10_46=NOT_STARTED
```
