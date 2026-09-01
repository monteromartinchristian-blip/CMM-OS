# Domain Security — Domain Pack Authority Boundary (Phase 10.38)

**Status:** Phase 10.38 — Security — implementation complete; Independent Audit V1 = FAIL; V1 findings remediated; independent re-audit V2 pending. This reference describes only what has been implemented and tested in Phase 10.38.

| Design Point | Status |
| --- | --- |
| `DP-038` — Domain Pack Authority Boundary | `IMPLEMENTED_PENDING_REAUDIT` |
| `AT-DP-038` | `PASS_PENDING_INDEPENDENT_VERIFICATION` |

The canonical design is
`docs/superpowers/specs/2026-09-01-phase-10.38-domain-pack-authority-boundary-design.md`.
The implementation plan is
`docs/superpowers/plans/2026-09-01-phase-10.38-domain-pack-authority-boundary-implementation-plan.md`.

---

## 1. Purpose

Phase 10.38 implements one narrow security boundary for Domain Intelligence:

> A Domain Pack must never obtain authority, permissions, activation rights,
> sensitive access, memory-write capability, external-operation capability, or
> cross-domain capability merely because it was discovered, loaded, marked
> trusted, or contains instructions requesting those powers.

The implementation is intentionally small. It composes the existing canonical
security primitives instead of duplicating them.

## 2. Core invariants

```text
DISCOVERY != TRUST
TRUST != AUTHORITY
LOAD != ENABLE
INSTALL != AUTHORIZATION
PROMPT != POLICY
CONTENT != AUTHORITY
PERSISTED STATE != CURRENT AUTHORIZATION
```

Trust may only:

```text
DENY
CONSTRAIN
REQUIRE EXPLICIT ACTIVATION/REVIEW
ABSTAIN
```

Trust never:

```text
GRANTS
AUTHORIZES
BYPASSES VALIDATION
BYPASSES APPROVAL
BYPASSES THE PERMISSION GATE
```

## 3. Domain trust levels

`DomainTrustLevel` (in `cmm.domains.enums`) is exactly:

```text
trusted
verified
internal
community
untrusted
blocked
```

These values describe trust **posture**, not permission grants. They carry no
numeric authority and their declaration order grants nothing.

## 4. Domain trust policy

`DomainTrustPolicy` (in `cmm/domains/trust_contracts.py`) is the immutable
explicit trust declaration supplied by the caller/configuration boundary:

```text
domain_id
trust_level
authorized_source_ids
allow_code_execution
allow_external_access
allow_memory_write
allow_sensitive_resources
allow_destructive_operations
require_manual_enable
require_signature
metadata
```

Safe defaults:

```text
allow_code_execution=False
allow_external_access=False
allow_memory_write=False
allow_sensitive_resources=False
allow_destructive_operations=False
require_manual_enable=True
require_signature=False
```

## 5. Trust evaluation

`evaluate_domain_trust(...)` (in `cmm/domains/trust_evaluator.py`) is a pure,
deterministic, fail-closed evaluator. It consumes canonical evidence only —
`DomainCandidate`, `DomainManifest`, `DomainValidationResult`, and an explicit
`DomainTrustPolicy` — and returns an immutable `DomainTrustDecision`.

Fail-closed conditions include:

```text
trust.validation_failed        identity/validation mismatch, blocking finding,
                               security_valid=False
trust.blocked                  policy trust level BLOCKED
trust.source_not_authorized    source outside authorized_source_ids
trust.signature_required       require_signature=True + no manifest signature
trust.manual_enable_required   require_manual_enable=True + no explicit enable
```

The decision also records denied canonical capabilities (memory-write, external
access, sensitive resources, destructive operations, code execution) as a
**ceiling**, never as a grant.

## 6. Authorized sources

An explicit authorized-source list is binding:

```text
candidate.source_id ∉ policy.authorized_source_ids → activation denied
```

An empty authorized-source tuple authorizes no source.

`candidate.trusted=True` is discovery evidence only. It never bypasses an
explicit source restriction.

## 7. Blocked and low-trust semantics

`BLOCKED` always fails activation/use, even when:

```text
candidate.trusted=True
validation passes
checksum passes
authorized source matches
```

`COMMUNITY`, `UNTRUSTED` and `BLOCKED` remain restrictive through the safe
policy defaults. The policy declaration is explicit; enum order never silently
overrides caller values.

## 8. `allow_untrusted=True` semantics

The canonical loader still supports:

```python
loader.load(candidate, allow_untrusted=True)
```

Its meaning is exactly **allow this explicit load/register attempt**. It never
means:

```text
enable the Domain
authorize an operation
authorize a workflow
grant memory access
grant external access
grant sensitive access
grant cross-domain access
satisfy approval
```

## 9. Signature semantics — presence only

The manifest `signature` field receives **presence semantics** only:

```text
require_signature=True AND manifest.signature absent → fail closed
```

```text
signature present != cryptographically verified
```

A **present signature is not cryptographically verified**. Phase 10.38 does not
introduce PKI, certificate authorities, key management, signing-key rotation,
or package-signature verification infrastructure.

Phase 10.38 must never describe a present signature as:

```text
cryptographically verified
trusted by certificate
authenticated package
verified publisher
```

## 10. Manual enablement

`require_manual_enable=True` means a Domain must not become enabled solely
because it was discovered, validated, loaded or registered.

Explicit activation only happens through the existing
`DefaultDomainAPI.enable_domain(domain_id, version=None)`. Before registry
mutation the API:

1. finds the already-loaded Domain through the canonical loader;
2. obtains the exact loaded candidate and pack from the canonical result;
3. obtains an explicit trust policy via the injected `trust_policy_lookup`;
4. fails closed for external/non-internal candidates with no explicit policy;
5. preserves the existing Phase 10.36 activation behavior only for a trusted
   `DomainSourceKind.INTERNAL` candidate with no explicit policy;
6. runs fresh canonical validation for the exact loaded candidate/pack;
7. evaluates trust with `manual_enable_requested=True`;
8. only then calls the existing `DomainRegistry.enable(...)`.

Every rejection occurs **before** the enabling registry mutation.

## 11. Fresh validation before activation

Activation never relies on stale validation. The API runs the canonical
validation pipeline (`PipelineDomainValidator`) for the exact loaded
candidate/pack, and trust evaluation requires coherent identity across:

```text
candidate.domain_id
candidate.detected_version
validation.domain_id
validation.version
manifest domain_id / package_version
```

Only **terminal** validation evidence may activate: `PASSED` or `WARNING`.
A structurally coherent `PENDING` or `RUNNING` result is not a finished
validation decision and fails closed on every activation path (including the
trusted-INTERNAL/no-policy compatibility path). A failed or security-invalid
validation cannot be overridden by trust.

## 12. Trust is a permission ceiling

Trust integrates through the existing canonical permission system
(`DomainPermissionResolver`, `DomainPermissionGate`,
`intersect_permission_layers`). The trust permission layer (`evaluate_domain_trust_permission`)
may return only:

```text
DENY
ABSTAIN
```

It never returns `ALLOW` or `APPROVAL_REQUIRED`.

```text
effective authority
=
canonical permission authority
∩ trust ceiling
∩ current canonical approval evidence
```

Trust may remove authority. Trust never adds it (no synthetic grants, no
permission-registry mutation from trust, no approval consumption inside trust
evaluation). A canonical permission DENY cannot be widened by trust.

Cross-domain resolution applies two independent trust boundaries:

1. whether cross-domain/external access itself is allowed
   (`DOMAIN_CROSS_ACCESS` against `allow_external_access`); and
2. whether the **actual transferred capability** is allowed by the trust
   ceiling (code execution, memory write, sensitive resources, destructive
   operations) when the requested capability differs from
   `DOMAIN_CROSS_ACCESS`.

Cross-domain trust restrictions can only make the canonical cross-domain
result more restrictive; a trust deny can never make a denied transfer
succeed.

## 13. Prompt/configuration is data, not policy

The canonical static Domain security scanner (`domain.security`) remains the
only prompt-injection scanner. Blocking policy-bypass patterns remain blocking
through canonical validation.

Free-form pack prompts/configuration are **never authorization evidence**:

- they cannot change `DomainTrustPolicy`;
- they cannot add a `PermissionCapability`;
- they cannot turn a trust DENY into ALLOW;
- they cannot turn a canonical permission DENY into ALLOW;
- they cannot write memory, authorize external access, or satisfy approval.

## 14. Explicit non-goals (Phase 11 and later)

Phase 10.38 does **not** provide:

- user authentication;
- global RBAC;
- tenant isolation;
- secrets manager / encrypted secret storage;
- general encryption and key management;
- certificate authorities / PKI;
- SBOM generation / artifact attestations;
- package transparency logs / remote reputation services;
- container or process sandboxing / OS-level isolation.

**Phase 10.38 does not provide an OS/container sandbox.** External-domain
isolation in 10.38 is a **logical authority boundary**, not an OS sandbox.

## 15. No parallel security infrastructure

Phase 10.38 adds no new runtime, engine, registry, store, loader, event bus,
validation pipeline, permission engine, approval system, or trace store. The
canonical owners remain:

```text
DeclarativeDomainLoader        loader
PipelineDomainValidator        validation pipeline
DomainSecurityValidator        static domain.security scanner
DomainPermissionResolver       permission resolution
DomainPermissionGate           permission gate
ApprovalService                approvals
DefaultDomainOperationOrchestrator  operation execution
DomainRegistry                 lifecycle registry
DefaultDomainAPI               facade
```

## 16. Safety of errors and evidence

Trust failures are structured and deterministic. Failure evidence contains only
canonical identity/reference information:

```text
domain_id
candidate_id
source_id
trust_level
reason_codes
```

No secrets, tokens, keys, signature content, prompt content, manifest content,
raw file content, traceback strings, or arbitrary `repr()` are included.

## 17. Files

Production:

```text
cmm/domains/trust_contracts.py
cmm/domains/trust_evaluator.py
cmm/domains/enums.py                (DomainTrustLevel)
cmm/domains/permission_resolution.py (trust_policy_lookup ceiling)
cmm/domains/api.py                   (activation trust boundary)
cmm/domains/__init__.py              (public exports)
```

Tests:

```text
tests/domains/test_domain_trust_contracts.py
tests/domains/test_domain_trust_evaluator.py
tests/domains/test_domain_trust_permissions.py
tests/domains/test_domain_trust_lifecycle.py
tests/domains/test_domain_security_dp038_acceptance.py  (AT-DP-038)
```

## 18. Status

Phase 10.38 — Security — implementation complete; Independent Audit V1 = FAIL;
V1 findings remediated; independent re-audit V2 pending. DP-038 =
`IMPLEMENTED_PENDING_REAUDIT`; AT-DP-038 =
`PASS_PENDING_INDEPENDENT_VERIFICATION`. Closure eligibility is decided only by
the subsequent independent audit.