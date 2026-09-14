# Domain Model Policies

**Phase:** 10.46 — Domain Model Policies
**Design Point:** DP-046 — User-Controlled, Model-Agnostic Domain Policy
**Status:** Complete; independently re-audited and closed after V2 PASS
**Design:** `docs/superpowers/specs/2026-09-09-phase-10.46-domain-model-policies-design.md`
**Plan:** `docs/superpowers/plans/2026-09-09-phase-10.46-domain-model-policies-implementation-plan.md`
**Remediation amendment:** `docs/superpowers/specs/2026-09-09-phase-10.46-remediation-design-amendment-v1.md`
**Remediation plan:** `docs/superpowers/plans/2026-09-09-phase-10.46-remediation-v1-implementation-plan.md`
**Final independent re-audit:** `docs/audits/phase-10.46-independent-reaudit-v2.md` — `PASS`
**Audited implementation HEAD:** `f62069cf935fff5bbac6055e5a63d9b0302993a6`
**Audit bundle SHA-256:** `8a7b57f88880092946038a236d3c802f1ea14e7b06e54150fe34928d11686e0a`
**Audit report commit:** `b2c70a1b7b9f6b4e9e1eb377ebf4c3c45a1197fe`
**Acceptance:** `tests/domains/test_domain_model_policy_dp046_acceptance.py` — `AT-DP-046=PASS`; premium-neutrality and strict-adapter-boundary remediation independently verified in Re-audit V2
**Implementation commit:** recorded by Git history on `feature/phase-10-domain-intelligence` (no self-referential placeholder is embedded here).

> Phase 10.46 is complete, independently re-audited and closed after V2 `PASS`.
> Historical V1 `FAIL` is preserved. V2 reports `BLOCKERS=0`, `MAJORS=0`,
> `MINORS=0`, `MAJOR_01=VERIFIED_REMEDIATED`,
> `MAJOR_02=VERIFIED_REMEDIATED`, `DP-046=VERIFIED_EXISTING`,
> `AT-DP-046=PASS`, and `CLOSURE_ELIGIBLE=YES`.
> Audited implementation HEAD `f62069cf935fff5bbac6055e5a63d9b0302993a6`; bundle SHA-256 `8a7b57f88880092946038a236d3c802f1ea14e7b06e54150fe34928d11686e0a`.

---

## 1. Principle

> Domains know the task. Users choose the model and reasoning effort. The runtime
> enforces constraints. The router chooses only when the user delegates.

A Domain Pack may declare only **objective, typed, serializable, auditable**
inference and validation requirements. Model choice and reasoning level belong to
the user/chat/session layer. CMM OS selects a model only when the user explicitly
delegates that choice to automatic routing.

## 2. `DomainModelPolicy`

`cmm/domains/model_policy_contracts.py` owns an immutable, frozen/slotted,
strictly validated and deterministically serializable contract.

Public fields (the complete serialized surface):

```text
domain_id
require_reasoning
require_tool_calling
require_structured_output
require_json_mode
require_json_schema
require_vision
require_audio_input
require_audio_output
require_embeddings
minimum_context_window
require_context_validation
require_response_validation
fallback_policy
metadata
```

Behavior:

- `domain_id` accepts a canonical `domain:<slug>` string or `DomainId`; other
  identifiers are rejected;
- every boolean is validated strictly (`bool` only, never `0/1`);
- `minimum_context_window` is `None` (no contribution) or a positive integer;
- `metadata` is deep-frozen and must be a string-keyed mapping;
- `fallback_policy` is `None` or a typed canonical `ModelFallbackPolicy`;
- `from_dict()` rejects unknown fields, including every forbidden selection
  field below;
- `to_dict()` / `from_dict()` round-trip deterministically.

### Forbidden fields

`DomainModelPolicy` contains none of these, directly or indirectly:

```text
preferred_models
prohibited_models
preferred_providers
prohibited_providers
local_models
premium_fallback with concrete model/provider identities
minimum_quality
latency_tolerance
recommended_budget_eur
concrete provider/model routing weights
```

`metadata` is audit metadata only and is never interpreted as a model/provider
selection channel.

## 3. Domain definition attachment

`DomainDefinition.model_policy: DomainModelPolicy | None` is optional and
backward compatible. Omitted policies serialize as `null`, legacy payloads
without the key still deserialize, mapping payloads are coerced through
`DomainModelPolicy.from_dict`, and the policy `domain_id` must match the
enclosing `DomainDefinition.id`. No existing production Domain Pack was
retrofitted with a guessed policy.

## 4. Adapter boundary

`cmm/agent_runtime/domain_model_policy_adapter.py` is a deliberately thin adapter:

```text
domain_model_requirement_source(policy, *, priority=25) -> ModelRequirementsSource
domain_model_validation_requirements(policy) -> tuple[ValidationRequirement, ...]
domain_model_fallback_policy(policy) -> ModelFallbackPolicy | None
```

The adapter consumes the canonical policy attribute surface structurally, so
`cmm/agent_runtime` never imports the Domain Intelligence package and the
approved one-way dependency (`domains → Agent Runtime → kernel.llm`) holds. The
adapter never queries a provider registry or model catalog, never selects or
ranks models, never constructs or invokes providers, and never inspects keys or
subscriptions.

### Strict fail-closed structural validation

One private validator guards every public adapter seam and the
`resolve_runtime_model_requirements(domain_policies=...)` path. A full-shape
object that merely exposes the attribute names is rejected unless its values
satisfy the canonical policy semantics:

- `domain_id` must be a canonical `domain:<slug>` identifier (lowercase ASCII
  slug, hyphen-separated, no leading/trailing/consecutive hyphens);
- every approved boolean must satisfy `type(value) is bool` (no `"true"`,
  `"false"`, `0`, `1`, or `None`);
- `minimum_context_window` must be `None` or `type(value) is int and value > 0`;
- `fallback_policy` must be `None` or a real canonical `ModelFallbackPolicy`
  (no duck typing);
- `metadata` must be a real `Mapping`;
- every approved attribute must be present.

Invalid input raises the existing `ModelRequirementsResolutionError`; the
adapter never coerces, repairs, infers, or ignores malformed values, and it
imports no domain module.

Requirements mapping injects **only** objective capability/context fields:

```text
minimum_context_window, reasoning, tool_calling, structured_output,
json_mode, json_schema, vision, audio_input, audio_output, embeddings
```

The domain source does not participate in premium permission composition
(`contributes_premium_permission=False`), so it expresses **no opinion** on
premium permission — neither allow nor deny. It also never injects
`allowed_providers`, `excluded_providers`, `privacy`, or cost ceilings. Provenance
is `source_kind="domain"`, `source_id=<domain id>`, `priority=25`.

## 5. Composition

`resolve_runtime_model_requirements(..., domain_policies=...)` appends one
canonical requirement source per domain policy and then calls the existing
`resolve_model_requirements()` unchanged. All canonical most-restrictive
semantics remain in force: capabilities accumulate, minimum context resolves to
the greatest minimum, provider allowlists intersect, exclusions union, privacy
resolves to the strictest value, cost ceilings resolve to the smallest, and
conflicts fail closed. A domain policy can never widen a stricter ancestor
constraint.

### Premium participation

Canonical `ModelRequirementsSource` carries a provenance-level
`contributes_premium_permission: bool = True` flag:

```text
True  -> this source participates in premium allow/deny composition
False -> this source has NO OPINION on premium permission
```

Existing sources keep their semantics by default. The Domain source opts out
with `False`, so premium permission is resolved only across participating
sources. The required truth table holds:

```text
authoritative allow + neutral domain = allow
authoritative deny  + neutral domain = deny
neutral domain only                  = fail-closed deny
adding/removing a neutral domain source never changes premium authority
```

The stored `ModelRequirements.premium_allowed=False` default on a neutral source
is not an authoritative denial; the participation flag determines authority.

## 6. Validation mapping

`require_context_validation=True` produces one blocking `PRE_EXECUTION`
`ValidationRequirementKind.CUSTOM` requirement with stable identity
`domain-model-policy:{domain_id}:context` and metadata
`phase="10.46"`, `semantic_kind="context_validation"`.

`require_response_validation=True` produces one blocking `POST_EXECUTION`
`ValidationRequirementKind.POST_CONDITION` requirement with stable identity
`domain-model-policy:{domain_id}:response` and metadata
`semantic_kind="response_validation"`.

False flags produce no requirements. No validator, engine, or enum is added; the
requirements connect to the existing Agent Runtime validation contracts and
stages.

## 7. Fallback

`fallback_policy` reuses the existing typed `ModelFallbackPolicy`. The adapter
returns that object or `None`; Domains never build candidates, rank fallbacks, or
resolve a domain fallback engine.

## 8. User model/reasoning ownership

Model and reasoning level are chat/session settings, not domain properties. An
explicit user model is validated through canonical model requirements and is
never silently substituted; an incompatible explicit choice fails transparently
and auditably unless a separately authorized user/session fallback policy
permits substitution (not invented by Phase 10.46). `AUTO` delegates selection to
canonical routing, where `DomainModelPolicy` supplies only objective
requirements. Phase 10.46 implements no CMMChat UI, no per-message override, and
no provider-specific reasoning parameter mapping.

## 9. Out of scope

Phase 10.47 benchmark suites, quality metrics, leaderboards, live provider
benchmarking, Model Gateway, new provider registry/model catalog/router/fallback
engine/budget engine/privacy engine, provider API clients, and any
domain → concrete model/provider map remain out of scope.

## 10. Remediation V1 — audit findings

Independent Audit V1 result (historical, preserved):

```text
INDEPENDENT_AUDIT_V1=FAIL
BLOCKERS=0
MAJORS=2
MINORS=0
MAJOR_01=DOMAIN_PREMIUM_PERMISSION_NOT_NEUTRAL
MAJOR_02=STRUCTURAL_ADAPTER_NOT_FAIL_CLOSED
```

- **MAJOR-01** was remediated by adding provenance-level
  `contributes_premium_permission` to `ModelRequirementsSource` (default `True`),
  making the resolver compose premium only across participating sources, and
  making the Domain source opt out (`False`). The Domain source now abstains; it
  neither allows nor denies premium.
- **MAJOR-02** was remediated by replacing attribute-presence-only structural
  validation with strict import-safe semantic validation of the full approved
  policy surface, shared by every adapter seam and the runtime resolver path.

`docs/audits/phase-10.46-independent-audit-v1.md` and the V1 bundle
`phase-10.46-audit-2c0a729d5217b018950109f33407b39687cca2e6.tar.gz` are
unmodified historical evidence.

## 11. Verification evidence (remediation run)

```text
FOCUSED_REMEDIATION=294 passed
  tests/agent_runtime/test_model_requirements_contracts.py
  tests/agent_runtime/test_model_requirements_resolver.py
  tests/agent_runtime/test_domain_model_policy_adapter.py
  tests/domains/test_domain_model_policy_contracts.py
  tests/domains/test_domain_model_policy_definition_serialization.py
  tests/domains/test_domain_model_policy_architecture.py
  tests/domains/test_domain_model_policy_dp046_acceptance.py
MODEL_REQUIREMENTS_REGRESSIONS=207 passed
DOMAIN_SUBSYSTEM=10104 passed
AGENT_RUNTIME_SUBSYSTEM=3590 passed
LLM_SUBSYSTEM=99 passed
GLOBAL_SUITE=15865 passed
RUFF_CHANGED_FILES=pass (8 remediation-changed Python files)
FORMAT_CHANGED_FILES=pass (8 remediation-changed Python files)
COMPILEALL=pass
GIT_DIFF_CHECK=pass
IMPORT_BOUNDARY=pass (agent_runtime and kernel.llm import no cmm.domains)
ANTI_FRAGMENTATION=pass (no parallel router/registry/catalog/fallback/gateway/premium resolver)
```

The earlier V1 implementation-run counts (105 focused / 192 regressions /
10091 domains / 3454 agent-runtime / 99 llm / 15716 global) remain historical.

AT-DP-046 scenarios (real canonical components: representative Health definition
via `dataclasses.replace`, `ProviderRegistry`, `ModelCatalog`, `ModelRouter`,
`model_matches_requirements`, canonical resolver and validation contracts):

```text
AT-DP-046-A_EXPLICIT_COMPATIBLE=PASS_REPORTED
AT-DP-046-B_EXPLICIT_INCOMPATIBLE=PASS_REPORTED
AT-DP-046-C_AUTO=PASS_REPORTED
AT-DP-046-D_CATALOG_REPLACEMENT=PASS_REPORTED
AT-DP-046-E_MULTI_DOMAIN=PASS_REPORTED
AT-DP-046-VALIDATION_BINDINGS=PASS_REPORTED
AT-DP-046-PREMIUM-NEUTRALITY=PASS_REPORTED
AT-DP-046-STRICT-ADAPTER-BOUNDARY=PASS_REPORTED
```

Direct production probes (no mocks):

```text
ALLOW_PLUS_NEUTRAL_DOMAIN=True
DENY_PLUS_NEUTRAL_DOMAIN=False
NEUTRAL_DOMAIN_ONLY=False
NEUTRALITY_INVARIANT=True
REQUIREMENT_SOURCE=REJECTED
VALIDATION_REQUIREMENTS=REJECTED
FALLBACK_POLICY=REJECTED
RUNTIME_RESOLUTION=REJECTED
```

Note on the repository-wide Ruff gate: `ruff check cmm kernel tests` remains red
at the same pre-existing baseline (813 findings; 257 files unformatted) under the
installed Ruff 0.16.2 expanded default rule set; no remediation file is among
them. The project's declared check
([`CONTRIBUTING.md`](../../CONTRIBUTING.md)) scopes Ruff to changed Python files
and passes for all 8 remediation-changed files.

## 12. Architecture invariants

```text
DOMAIN_CONCRETE_MODEL_IDS=NONE
DOMAIN_CONCRETE_PROVIDER_IDS=NONE
NEW_DOMAIN_MODEL_ROUTER=NO
NEW_DOMAIN_PROVIDER_REGISTRY=NO
NEW_DOMAIN_MODEL_CATALOG=NO
NEW_DOMAIN_FALLBACK_ENGINE=NO
NEW_PREMIUM_RESOLVER=NO
KERNEL_TO_DOMAINS_IMPORT=NO
AGENT_RUNTIME_TO_DOMAINS_IMPORT=NO
PHASE_10_47_IMPLEMENTED=NO
```

Guards: `tests/domains/test_domain_model_policy_architecture.py` (AST/import
inspection with detector-calibration tests, including no
`source_kind == "domain"` premium special-case and explicit Domain premium
abstention) plus the pre-existing reverse-import and public-API guards.

## 13. State

```text
PHASE10_46=CLOSED
INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V2=PASS
BLOCKERS=0
MAJORS=0
MINORS=0
MAJOR_01=VERIFIED_REMEDIATED
MAJOR_02=VERIFIED_REMEDIATED
DP-046=VERIFIED_EXISTING
AT-DP-046=PASS
CLOSURE_ELIGIBLE=YES
AUDITED_IMPLEMENTATION_HEAD=f62069cf935fff5bbac6055e5a63d9b0302993a6
AUDIT_BUNDLE_SHA256=8a7b57f88880092946038a236d3c802f1ea14e7b06e54150fe34928d11686e0a
```

Phase 10.46 is closed. Phase 10.47 may begin after verification of the docs-only
closure commit; Phase 10.47 has not started.
