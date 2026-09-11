# Domain Privacy Policies

**Phase:** 10.50 — Domain Privacy Policies
**Design Point:** `DP-050` — Domain Privacy Defaults
**Acceptance Test:** `AT-DP-050` — Connected Domain Privacy Acceptance
**Status:** `PHASE10_50=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT` · `DP-050=PASS_REPORTED` · `AT-DP-050=PASS_REPORTED` (no independent audit has been performed; no closure or severity counts are claimed)

> A Domain Pack declares the privacy posture its content starts from. The
> declaration can only **restrict** — it never grants remote, provider, export,
> cache or approval authority, and it never becomes a second privacy engine.

## 1. Purpose and boundaries

Phase 10.50 adds a canonical Domain Intelligence **privacy default** layer on top
of the existing Phase 8 processing-policy owner:

```text
Domain Pack
    ↓
DomainDefinition.privacy_policy        (Phase 10.50 declaration)
    ↓ pure projection only
canonical PrivacyMetadata              (Phase 8, sole truth)
    ↓
resolve_effective_privacy_metadata(...)
    ↓
evaluate_privacy_operation(...)
```

`DomainPrivacyPolicy` is a **declarative Domain input only**. It is never the
authoritative effective-policy resolver, never an operation evaluator, and never
a competitor to `cmm.cognitive.privacy`.

Phase 10.50 adds no engine, resolver, registry, store, runtime, provider policy,
redaction system, cache, export subsystem, approval system, Knowledge Package
builder or Domain Pack parser.

## 2. Public contracts

Exposed additively through `cmm.domains`:

```python
DomainPrivacyPolicy
project_domain_privacy_metadata
```

### 2.1 `DomainPrivacyPolicy`

Immutable, frozen/slotted, versioned Domain declaration:

```python
DomainPrivacyPolicy(
    schema_version="1",
    domain_id=DomainId(slug="health"),
    default_privacy=PrivacyMetadata(...),
    require_approval_for_remote=True,
    metadata={},
)
```

| Field | Type | Notes |
|---|---|---|
| `schema_version` | `str` | Exactly `"1"`; any other value fails closed. |
| `domain_id` | `DomainId` | Canonical `domain:<slug>`; must match the owning `DomainDefinition.id`. |
| `default_privacy` | `PrivacyMetadata` | The canonical Phase 8 payload. No processing-policy field is duplicated outside it. |
| `require_approval_for_remote` | `bool` | Additional obligation only, never an authorization. Literal `bool` required. |
| `metadata` | `Mapping[str, Any]` | Descriptive audit metadata, deep-frozen; credential/secret-like keys rejected. |

There is deliberately **no** `allow_cross_domain` field. Cross-domain authority
remains owned by Phase 10.15.

The contract is immutable, typed, versioned, strict on unknown fields,
deterministic, serializable, credential-free, provider-independent,
model-independent, non-executable and incapable of granting authority by itself.

## 3. Serialization

`to_dict()` is deterministic and emits canonical enum string values on the wire:

```python
{
    "schema_version": "1",
    "domain_id": "domain:health",
    "default_privacy": {
        "schema_version": 1,
        "policy": "local_only",
        "sensitivity": "sensitive",
        "allowed_processing_locations": ["local"],
        "allowed_providers": None,
        "prohibited_providers": [],
        "allow_remote": False,
        "allow_premium": False,
        "allow_cache": True,
        "allow_export": False,
        "requires_redaction": False,
        "requires_approval": False,
        "inherited_from": [],
        "permissions": [],
        "permissions_denied": False,
        "metadata": {},
    },
    "require_approval_for_remote": True,
    "metadata": {},
}
```

`from_dict()` is strict: unknown fields, missing required fields, unsupported
schema versions and malformed nested `PrivacyMetadata` all raise
`DomainPrivacyPolicySerializationError`. Round-trip equality is preserved.

## 4. Pure projection

```python
def project_domain_privacy_metadata(
    policy: DomainPrivacyPolicy,
    *,
    processing_location: ProcessingLocation,
) -> PrivacyMetadata: ...
```

The projection is a thin adapter:

1. returns `policy.default_privacy` unchanged for local processing;
2. for a remote attempt with `require_approval_for_remote=True`, returns an
   immutable copy with `requires_approval=True`;
3. otherwise returns the declared metadata unchanged.

It never resolves effective privacy, never evaluates an operation, never
performs approval or redaction, never calls a provider and never widens a
restriction. It does not mutate `PrivacyMetadata`.

## 5. `SENSITIVE` reconciliation

The roadmap's historical `SENSITIVE` shorthand is an **orientation label**, not
a processing-policy enum member.

- Canonical `PrivacyPolicy` values remain `LOCAL_ONLY`, `LOCAL_PREFERRED`,
  `REMOTE_ALLOWED`, `PREMIUM_ALLOWED`.
- `SensitivityLevel.SENSITIVE` remains the sensitivity concept.
- Phase 10.50 does **not** add `PrivacyPolicy.SENSITIVE`.

A sensitive Domain expresses its orientation through
`PrivacyPolicy.LOCAL_ONLY` plus canonical `SensitivityLevel.SENSITIVE` or
stronger.

## 6. Remote approval is an obligation, never an authorization

```text
approval requirement ≠ permission to process remotely
```

`LOCAL_ONLY` + `require_approval_for_remote=True` remains **remote denied** even
when approval exists. Approval may only add a requirement to an otherwise
allowable path; it can never widen `LOCAL_ONLY`, `allow_remote=False`,
`allow_export=False`, `allow_cache=False` or a provider prohibition.

## 7. First-party Domain matrix

Exactly 12 first-party Domains are implemented; 11 declare an explicit
`DomainPrivacyPolicy`. General is the explicit no-Domain-wide-default case.

| Domain | Processing default | Sensitivity orientation | Remote | Premium | Cache | Export | Remote approval |
|---|---|---|---:|---:|---:|---:|---:|
| general | `None` / operation-resolved | inherited from canonical inputs | no Domain grant | no Domain grant | inherited | inherited | inherited |
| health | `LOCAL_ONLY` | `SENSITIVE` | no | no | yes | no | yes |
| relationships | `LOCAL_ONLY` | `SENSITIVE` | no | no | yes | no | yes |
| reflection | `LOCAL_ONLY` | `SENSITIVE` | no | no | yes | no | yes |
| concerns | `LOCAL_ONLY` | `SENSITIVE` | no | no | yes | no | yes |
| parenthood | `LOCAL_ONLY` | `SENSITIVE` | no | no | yes | no | yes |
| sport | `LOCAL_ONLY` | `SENSITIVE` | no | no | yes | no | yes |
| life_plan | `LOCAL_ONLY` | `SENSITIVE` | no | no | yes | no | yes |
| university | `REMOTE_ALLOWED` | `INTERNAL` | yes, subject to effective policy | no | yes | no | no by Domain default |
| oppositions | `REMOTE_ALLOWED` | `INTERNAL` | yes, subject to effective policy | no | yes | no | no by Domain default |
| languages | `REMOTE_ALLOWED` | `INTERNAL` | yes, subject to effective policy | no | yes | no | no by Domain default |
| project | `LOCAL_PREFERRED` | `INTERNAL` | only when every gate allows | no | yes | no | yes if remote is attempted |

Every declared policy satisfies
`definition.privacy_policy.domain_id == definition.id`.

Each Domain owns an explicit local declaration module:

```text
cmm/domains/health/privacy.py
cmm/domains/relationships/privacy.py
cmm/domains/reflection/privacy.py
cmm/domains/concerns/privacy.py
cmm/domains/parenthood/privacy.py
cmm/domains/sport/privacy.py
cmm/domains/life_plan/privacy.py
cmm/domains/university/privacy.py
cmm/domains/oppositions/privacy.py
cmm/domains/languages/privacy.py
cmm/domains/project/privacy.py
```

General intentionally has no privacy builder. There is no central first-party
privacy registry and no generic privacy engine.

## 8. Knowledge Package composition

The canonical Phase 8 `KnowledgePackageBuilder` remains the only package owner.
Phase 10.50 consumes package privacy through
`privacy_from_knowledge_package(package)` and composes the Domain default through
`resolve_effective_privacy_metadata(...)`.

Phase 10.49's `DomainKnowledgePackageSchema.minimum_sensitivity` remains a
**minimum canonical sensitivity floor only**. It is never reinterpreted as
remote-processing, provider, export, cache or approval authority. A Domain policy
never mutates a `KnowledgePackage` and never rewrites resource privacy.

## 9. Permission boundary

The authorization equation is:

```text
privacy allows AND permissions allow AND approvals satisfied AND other gates allow
```

Never:

```text
privacy allows => operation authorized
```

A Domain privacy default may make processing more restrictive. It may never
grant cross-domain authority; a permission denial blocks even when privacy would
allow the processing, and an allowed permission path can still be blocked by
privacy.

## 10. Provider neutrality

No first-party Domain privacy module is a model/provider router.

- No concrete model/provider IDs appear as routing choices.
- `allowed_providers=None` keeps its canonical meaning: the Domain adds no
  provider-specific allowlist restriction.
- `prohibited_providers` accumulates through canonical union composition and a
  prohibited provider can never be re-enabled by a Domain default.
- A concrete provider remains subject to global, user/session, resource/package,
  Domain, workflow/operation, model-provider, permission, approval and future
  Phase 11 gateway policy.

## 11. Cache, export and redaction declarations

Phase 10.50 declares privacy requirements only. It implements no cache, no export
engine, no redaction algorithm, no tokenization, no anonymization, no secrets
handling and no remote egress.

`allow_export=False` and `allow_premium=False` are the Domain defaults for every
declared first-party policy. A canonical decision requiring redaction or approval
is surfaced as such; it is never silently converted into `ALLOW`.

## 12. Domain Trace reference

Privacy decisions are not omitted from Domain Trace. The canonical reference
contract is extended additively with:

```python
PRIVACY_DECISION = "privacy_decision"
```

Trace representation stays **reference-only**: it carries the canonical privacy
decision identity by reference and never copies sensitive content, restricted
values, provider payloads, prompts, source documents, secrets, chain of thought
or a complete `PrivacyMetadata` blob.

No `DomainPrivacyTrace`, `DomainPrivacyTraceStore`,
`DomainPrivacyTraceRegistry` or `DomainPrivacyTraceAssembler` is created.

## 13. `DP-050` and `AT-DP-050`

`DP-050 — Domain Privacy Defaults`: a Domain Pack may declaratively contribute an
immutable, typed, versioned and serializable `DomainPrivacyPolicy` that projects
into the canonical Phase 8 `PrivacyMetadata` contract. The Domain policy is a
restrictive input only, participating in canonical most-restrictive resolution
and canonical operation evaluation without granting authority or replacing any
canonical owner. `DP-050` additionally requires all currently implemented
first-party Domain Packs to expose their approved privacy default or, for
General, explicitly expose no Domain-wide default.

`AT-DP-050` (`tests/domains/test_domain_privacy_policy_dp050_acceptance.py`)
exercises real canonical components end to end — real first-party
`DomainDefinition` objects, the real `DomainRegistry`, the canonical
`ParsedDomainPack` path, the real `KnowledgePackageBuilder`,
`privacy_from_knowledge_package`, `resolve_effective_privacy_metadata`,
`evaluate_privacy_operation`, the real Phase 10.15 permission stack and the real
Domain Trace reference contracts — across scenarios A–K:

| Scenario | Proves |
|---|---|
| A | `LOCAL_ONLY` cannot be widened by a less restrictive Domain default; approval cannot convert denial into authorization. |
| B | Real Health stays local by default; remote and export are denied; a provider prohibition survives composition. |
| C | Real University `REMOTE_ALLOWED` is conditional; a stricter package forces `LOCAL_ONLY`; the Domain default grants no provider authorization. |
| D | Remote approval is additive: an otherwise-allowed remote path without approval yields `APPROVAL_REQUIRED`, and approval never bypasses an independent privacy denial. |
| E | `allow_cache=False`, `allow_export=False`, `requires_redaction=True` and `requires_approval=True` all survive most-restrictive composition. |
| F | Allowed-provider constraints intersect, prohibited providers accumulate, and a prohibited provider cannot be re-enabled by a Domain default. |
| G | Real General has `privacy_policy is None`; missing Domain policy never becomes `REMOTE_ALLOWED`. |
| H | Phase 10.15 permissions remain authoritative in both directions. |
| I | The exact 12-Domain inventory with 11 declared policies and General as the explicit no-default case. |
| J | Deterministic declarative round trip through the canonical pack path with no second parser. |
| K | Safe privacy-decision trace reference with no raw restricted payload. |

## 14. Anti-fragmentation

`tests/domains/test_domain_privacy_policy_architecture.py` proves, over the
Phase 10.50 production surface:

```text
DomainPrivacyEngine          absent
DomainPrivacyResolver        absent
DomainPrivacyRegistry        absent
DomainPrivacyStore           absent
DomainPrivacyRuntime         absent
privacy_engine.py            absent
privacy_resolver.py          absent
privacy_registry.py          absent
privacy_store.py             absent
privacy_runtime.py           absent
PrivacyPolicy redefinition   absent
SensitivityLevel redefinition absent
allow_cross_domain           absent
provider/model routing ids   absent
cmm.cognitive -> cmm.domains dependency  absent
```

The canonical `domain.fragmentation` owner is reused rather than re-implemented.

## 15. Deferred work

Explicitly deferred and out of scope for Phase 10.50:

- Mental Health Domain — Phase 10.52;
- Neurodivergence Domain — Phase 10.53;
- provider/model gateway enforcement and real provider calls — Phase 11;
- provider credentials/secrets;
- automatic redaction/tokenization/anonymization;
- real export transport and remote egress;
- broader global/user/session privacy persistence not already canonical;
- an authorized privacy-widening exception mechanism;
- CMMChat/UI privacy controls and connector privacy;
- a new trace subsystem.

Future phases must consume, not replace, `DomainPrivacyPolicy`.
