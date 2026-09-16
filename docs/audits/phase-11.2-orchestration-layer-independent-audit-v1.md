# Phase 11.2 — Orchestration Layer — Independent Audit V1

**Audit verdict:** `FAIL`
**Audit date:** 2026-09-16
**Auditor:** ChatGPT independent audit
**Scope:** Phase 11.2 — Orchestration Layer on `feature/phase-11-stable-integrated-platform`
**Requirement:** `F11-016 — Canonical Request Orchestration`
**Design Point:** `DP-102 — Fail-Closed Canonical Request Orchestration Pipeline`
**Connected acceptance:** `AT-DP-102`

---

## 1. Audited artifact

- Bundle: `cmm-phase11-2-orchestration-layer-audit-5ebc8d064fa3.tar.gz`
- Audited HEAD: `5ebc8d064fa3f29825c179eff7f41df204dc837b`
- Audited tree: `989706d15ba78b8333b1e9b3634f820e9180f5bf`
- SHA-256: `85127ed1e9a437e30984f930b60fba79b7ae28959baf3296f86665ce11b93fc9`
- Archive members: `2466`

Independent archive verification:

```text
SHA256=PASS
GZIP=PASS
EMBEDDED_COMMIT_ID=5ebc8d064fa3f29825c179eff7f41df204dc837b
RECONSTRUCTED_TREE=989706d15ba78b8333b1e9b3634f820e9180f5bf
TREE_MATCH=PASS
UNSAFE_ARCHIVE_PATHS=0
SYMLINKS=0
```

The tree reconstruction had to force-add the tracked `.cmm/last_plan.json` because
the archive's own `.gitignore` ignores `.cmm/` in a fresh repository. Once the
tracked ignored file was included, the reconstructed tree matched the declared
tree exactly.

---

## 2. Closed-phase preservation

The audited bundle was compared against the exact Phase 11.1 re-audit bundle.

Independent comparison result:

```text
cmm/ production outside cmm/orchestration: BYTE_IDENTICAL
kernel/ production: BYTE_IDENTICAL
cmm_agent/: BYTE_IDENTICAL
```

The only Phase 11.1 test change inspected was
`tests/platform/test_architecture.py`. It narrows the old dependency-direction
gate to exclude the newly sanctioned `cmm.orchestration` consumer and adds a
replacement gate proving that `cmm.orchestration` is the only package allowed
to depend on `cmm.platform`.

No Phase 11.1 or Phase 11.34 production semantics were changed.

```text
PHASE11_1_PRODUCTION_PRESERVED=YES
PHASE11_34_PRODUCTION_PRESERVED=YES
```

---

## 3. Independently replayed tests

The audit sandbox does not contain `libcst`, although `libcst>=1.0` is a normal
project dependency in `pyproject.toml`.

Without that dependency, imports of the inherited execution stack fail before
the orchestration tests can collect.

To isolate that environmental limitation, the auditor used a temporary
out-of-tree import shim for `libcst` only. The shim was not written into the
audited tree and no execution/CST behavior was exercised by these focused
tests. It exists solely to allow the unchanged inherited import chain to load.

### 3.1 Phase 11.2 suite

Directly replayed from the exact bundle:

```text
tests/orchestration
426 passed
```

### 3.2 Connected and inherited acceptances

Directly replayed:

```text
tests/orchestration/test_phase11_2_dp102_acceptance.py
tests/platform/test_phase11_1_dp101_acceptance.py
tests/llm/test_provider_registry_dp134_acceptance.py

121 passed
```

Therefore the test artifacts themselves are green:

```text
AT-DP-102=PASS
AT-DP-101=PASS
AT-DP-134=PASS
```

### 3.3 Additional canonical regressions

Directly replayed:

```text
tests/domains/test_domain_resolver_integration.py
tests/domains/test_domain_permission_resolution.py
tests/domains/test_domain_profile_resolver.py
tests/runtime/test_shared_sessions.py
tests/agent_runtime/test_existing_system_integration.py
tests/agent_runtime/test_agent_runtime_integration.py

622 passed
```

### 3.4 Architecture gates

Directly replayed:

```text
tests/orchestration/test_architecture.py
51 passed
```

### 3.5 Compile and whitespace gates

Directly replayed:

```text
COMPILEALL=PASS
TRAILING_WHITESPACE_HITS=0
```

Ruff is not installed in the audit sandbox and network installation is
unavailable. The implementation-machine result:

```text
RUFF_CHANGED_FILES=PASS
FORMAT_CHANGED_FILES=PASS
GLOBAL_TESTS=19045 passed
AFFECTED_SUBSYSTEM_TESTS=17750 passed
```

is therefore corroborating evidence, not the sole basis of this audit verdict.

The two MAJOR findings below were reproduced independently against production
code from the exact archive and do not depend on the unavailable Ruff/global
sandbox gates.

---

## 4. Positive architecture findings

The audited implementation correctly establishes a dedicated:

```text
cmm/orchestration/
```

package with the frozen twelve production modules.

Independent inspection confirms:

- no FastAPI/Flask/OpenAPI/Application Backend surface in `cmm/orchestration`;
- no Model Gateway/provider/model routing implementation;
- no reverse dependency from canonical packages onto `cmm.orchestration`;
- no new Event Bus;
- no new Provider Registry, Domain Registry, Agent Registry, Session Store,
  workflow engine, execution engine, validation engine, memory store or
  knowledge store;
- no operation/workflow/Agent Runtime execution from the Orchestrator;
- no direct network/subprocess/file-I/O behavior in the new package;
- public contracts are frozen and serialization-oriented;
- deterministic intent classification is fail-closed on unknown structure;
- policy denies/escalates side-effect routes that lack canonical permission
  evidence;
- safe event and error key denylists are present;
- connected acceptance uses real `DefaultDomainResolver`,
  `AgentRegistryService`, `InMemoryAgentRegistryStore`,
  `InMemorySessionStore`, Phase 11.1 `ApplicationContainer`, and official
  in-memory orchestration adapters;
- sensitive marker/context minimization scenarios are present;
- Phase 11.3 Application Backend remains deferred.

These positives do not eliminate the runtime-authority gaps below.

---

# 5. MAJOR-01 — Orchestration runtime contracts are not role-safe

## 5.1 Requirement

The committed design requires:

```text
Every binding must declare a safe runtime contract.
Fake unrelated implementations must not claim these service identities.
```

The implementation plan further requires that unrelated implementations are
rejected by orchestration module construction.

`AT-DP-102` Scenario L requires every orchestration binding to satisfy its
runtime contract before the Phase 11.1 container reaches `READY`.

## 5.2 Implementation

`cmm/orchestration/platform_module.py` uses:

```python
if not isinstance(implementation, runtime_contract):
    raise TypeError(...)
```

where the runtime contracts are `@runtime_checkable` orchestration protocols.

However:

```text
DomainRouter
AgentRouter
```

both expose only a method named:

```text
route
```

at runtime.

Python runtime protocol checks verify attribute presence, not callable
signature compatibility.

Therefore the two distinct service roles are indistinguishable under the
current `isinstance(..., Protocol)` gate.

## 5.3 Independent reproducer

A domain-only implementation:

```python
class DomainOnly:
    def route(self, request, intent, context):
        return DomainRouteDecision(...)
```

produces:

```text
isinstance(DomainOnly(), DomainRouter) = True
isinstance(DomainOnly(), AgentRouter)  = True
```

The exact Phase 11.2 module builder accepts the same object for both
`domain_router` and `agent_router`.

The Phase 11.1 `ApplicationContainer` then reports:

```text
CONTAINER_STATE=ready
AGENT_IMPL_IS_DOMAIN_ONLY=True
```

The first real orchestration request fails only at runtime:

```text
RESULT_STATUS=failed
ERROR_CODE=ORCHESTRATION_INTERNAL_FAILURE
```

## 5.4 Impact

A wrongly wired orchestration service can claim a different service identity
and survive all composition-time validation.

This defeats the purpose of the closed Phase 11.1 runtime-contract boundary and
makes `READY` insufficient to prove role-correct Phase 11.2 composition.

The current test:

```text
test_builder_rejects_a_cross_role_object
```

only swaps an event sink into the intent resolver. It does not exercise
protocols whose runtime member sets collide.

## 5.5 Required remediation

Make Phase 11.2 runtime role contracts discriminating.

Acceptable approaches include an explicit role marker/contract validated by the
module builder, distinct role methods, or another deterministic runtime
boundary that preserves legitimate adapters/test doubles while preventing a
service for one orchestration role from satisfying another merely because both
have a method named `route`.

Add RED/GREEN coverage for at least:

```text
DomainRouter -> AgentRouter = REJECTED
AgentRouter -> DomainRouter = REJECTED
DefaultDomainResolver -> IntentResolver = REJECTED
```

and prove a cross-wired graph can never reach `ApplicationContainer.READY`.

## 5.6 Verdict

```text
MAJOR_01=UNSAFE_ORCHESTRATION_ROLE_RUNTIME_CONTRACTS
```

---

# 6. MAJOR-02 — Canonical agent-selection authority can be replaced by an unchecked fake service

## 6.1 Requirement

The committed design states:

```text
When the route is AUTONOMOUS_AGENT, actual agent compatibility/selection
remains owned by AgentRegistryService / AgentResolver.
```

The implementation plan freezes the constructor conceptually as:

```python
class CanonicalAgentRouter:
    def __init__(
        self,
        *,
        registry_service: AgentRegistryService | None = None,
    ) -> None: ...
```

`F11-016` requires delegation to canonical Agent Runtime authority rather than a
parallel or caller-invented selector.

## 6.2 Implementation

The production implementation instead accepts:

```python
def __init__(self, *, registry_service: Any | None = None) -> None:
    self._registry_service = registry_service
```

No runtime canonical boundary is enforced.

On an autonomous route it calls:

```python
self._registry_service.resolve_agent(requirement)
```

and trusts the returned object's:

```text
selected.agent_id
selected.version.canonical()
```

without verifying that the collaborator is the canonical
`AgentRegistryService` or a separately sanctioned canonical adapter.

## 6.3 Independent reproducer

The auditor supplied:

```python
class FakeRegistryService:
    def resolve_agent(self, requirement):
        return SimpleNamespace(
            selected=SimpleNamespace(
                agent_id="forged.agent",
                version=SimpleNamespace(canonical=lambda: "9.9.9"),
            )
        )
```

Then:

```python
CanonicalAgentRouter(
    registry_service=FakeRegistryService()
).route(...)
```

returned:

```text
FAKE_REGISTRY_ACCEPTED=True
ROUTE=autonomous_agent
AGENT_ID=forged.agent
AGENT_VERSION=9.9.9
```

No canonical `AgentRegistryService` or `AgentResolver` participated.

## 6.4 Impact

The class explicitly named `CanonicalAgentRouter` can produce an autonomous
agent selection from a completely noncanonical authority.

Because the outer orchestration binding validates only that
`CanonicalAgentRouter` satisfies the `AgentRouter` role, Phase 11.1 composition
cannot detect this substitution.

This violates the core Phase 11.2 ownership invariant even though the connected
acceptance happens to compose the real canonical service.

## 6.5 Related boundary review

The same remediation pass must review other canonical collaborators currently
typed/stored as unrestricted `Any`, especially:

```text
CanonicalDomainRouter.resolver
CanonicalDomainRouter.registry
CanonicalDomainRouter.context_builder
CanonicalDomainRouter.permission_registry
CanonicalDomainRouter.permission_resolver
```

and the canonical session seam used by `DefaultContextResolver`.

This does not mean every collaborator must be a concrete class. Where the
repository intentionally supports a canonical protocol/adapter, preserve that
extension point, but make the accepted authority explicit and testable rather
than unrestricted `Any`.

At minimum, `CanonicalAgentRouter` must reject a noncanonical fake authority
before it can return a selected agent.

## 6.6 Required remediation

Enforce the canonical agent-selection boundary at construction/composition
time.

Add RED/GREEN coverage proving:

```text
FakeRegistryService -> REJECTED
real AgentRegistryService -> ACCEPTED
real AgentRegistryService / AgentResolver selection -> preserved
no-compatible canonical agent -> HUMAN_ESCALATION
```

Audit the analogous canonical collaborator boundaries and document any
intentional adapter seam explicitly.

## 6.7 Verdict

```text
MAJOR_02=CANONICAL_AGENT_AUTHORITY_NOT_ENFORCED
```

---

## 7. Decision/event failure observation

The auditor also exercised required event failure behavior.

When the terminal routing event fails after the decision record has already
been persisted:

```text
public result = FAILED
persisted record = allow_route / direct_response
```

The current data model records the routing decision rather than the delivery
outcome, so this is not independently scored as a third MAJOR in Audit V1.

However the remediation must not accidentally worsen this behavior. If Phase
11.2 intends the decision repository to represent final orchestration outcome
rather than only route decision, the distinction must be made explicit and
covered. The current spec wording for Scenario K ("every terminal
orchestration decision") should be clarified during remediation if necessary.

No severity is assigned to this observation in V1.

---

## 8. AT-DP-102 assessment

The connected acceptance is substantial and genuinely connected.

It contains real scenarios for:

```text
A simple question
B domain ambiguity
C cross-domain restriction
D denied command
E approval required
F autonomous goal
G no compatible agent
H session resumption
I context minimization
J multichannel behavior
K decision persistence
L Phase 11.1 composition
```

The exact test file passes independently.

However the acceptance does not catch either MAJOR:

- Scenario L checks each object's current runtime protocol but does not test
  colliding orchestration roles.
- Scenario F proves the happy path with a real `AgentRegistryService`, but does
  not prove that a noncanonical selector is rejected.

Therefore:

```text
AT_DP_102=PASS
DP_102=NOT_VERIFIED
```

A green acceptance is necessary but not sufficient for Design Point
verification.

---

## 9. F11-016 assessment

The majority of `F11-016` is implemented:

- explicit Orchestrator;
- deterministic intent;
- context seam;
- canonical happy-path domain routing;
- bounded execution-route selection;
- restrictive policy;
- decision repository;
- safe event sink;
- structured result;
- no API/backend/model-routing scope leakage.

But canonical agent authority is not enforced and composition runtime contracts
are not role-safe.

Therefore:

```text
F11_016=IMPLEMENTED_REMEDIATION_REQUIRED
```

not `VERIFIED_EXISTING`.

---

## 10. Severity summary

```text
BLOCKERS=0
MAJORS=2
MINORS=0
```

Findings:

```text
MAJOR_01=UNSAFE_ORCHESTRATION_ROLE_RUNTIME_CONTRACTS
MAJOR_02=CANONICAL_AGENT_AUTHORITY_NOT_ENFORCED
```

---

## 11. Final independent verdict

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

PHASE11_1=CLOSED
DP_101=VERIFIED_EXISTING
AT_DP_101=PASS

PHASE11_34=CLOSED
DP_134=VERIFIED_EXISTING
AT_DP_134=PASS

AUDITED_HEAD=5ebc8d064fa3f29825c179eff7f41df204dc837b
AUDITED_TREE=989706d15ba78b8333b1e9b3634f820e9180f5bf
AUDIT_BUNDLE_SHA256=85127ed1e9a437e30984f930b60fba79b7ae28959baf3296f86665ce11b93fc9

CLOSURE_ELIGIBLE=NO
NEXT=PHASE11_2_REMEDIATION_V1
```

Phase 11.2 must not be closed.

The next step is a narrow Remediation V1 design/spec covering only the two
MAJOR findings, followed by a separate remediation implementation plan, agent
prompt, TDD fixes, fresh gates, a new exact-HEAD bundle, and independent
re-audit.
