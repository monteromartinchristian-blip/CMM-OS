# Domain Model Policies

**Phase:** 10.46 — Domain Model Policies
**Design Point:** DP-046 — User-Controlled, Model-Agnostic Domain Policy
**Status:** Implemented; pending independent audit
**Design:** `docs/superpowers/specs/2026-09-09-phase-10.46-domain-model-policies-design.md`
**Plan:** `docs/superpowers/plans/2026-09-09-phase-10.46-domain-model-policies-implementation-plan.md`
**Acceptance:** `tests/domains/test_domain_model_policy_dp046_acceptance.py` — `AT-DP-046=PASS_REPORTED`
**Implementation commit:** recorded by Git history on `feature/phase-10-domain-intelligence` (no self-referential placeholder is embedded here).

> Phase 10.46 is implemented and pending independent audit. It is **not** closed,
> audited, or verified. `DP-046=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION`,
> `AT-DP-046=PASS_REPORTED`, `CLOSURE_ELIGIBLE=NO`.

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

Requirements mapping injects **only** objective capability/context fields:

```text
minimum_context_window, reasoning, tool_calling, structured_output,
json_mode, json_schema, vision, audio_input, audio_output, embeddings
```

The domain never injects `allowed_providers`, `excluded_providers`, `privacy`,
cost ceilings, or `premium_allowed`. Provenance is
`source_kind="domain"`, `source_id=<domain id>`, `priority=25`.

## 5. Composition

`resolve_runtime_model_requirements(..., domain_policies=...)` appends one
canonical requirement source per domain policy and then calls the existing
`resolve_model_requirements()` unchanged. All canonical most-restrictive
semantics remain in force: capabilities accumulate, minimum context resolves to
the greatest minimum, provider allowlists intersect, exclusions union, privacy
resolves to the strictest value, cost ceilings resolve to the smallest, premium
requires every source to allow it, and conflicts fail closed. A domain policy
can never widen a stricter ancestor constraint.

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

## 10. Verification evidence (this implementation run)

```text
FOCUSED_PHASE_10_46=104 passed
  tests/domains/test_domain_model_policy_contracts.py
  tests/domains/test_domain_model_policy_definition_serialization.py
  tests/domains/test_domain_model_policy_architecture.py
  tests/domains/test_domain_model_policy_dp046_acceptance.py
  tests/agent_runtime/test_domain_model_policy_adapter.py
MODEL_REQUIREMENTS_REGRESSIONS=192 passed
DOMAIN_SUBSYSTEM=10091 passed
AGENT_RUNTIME_SUBSYSTEM=3454 passed
LLM_SUBSYSTEM=99 passed
GLOBAL_SUITE=15716 passed
RUFF=pass (declared changed-file scope: 14 changed Python files)
FORMAT=pass (declared changed-file scope: 14 changed Python files)
COMPILEALL=pass
GIT_DIFF_CHECK=pass
IMPORT_BOUNDARY=pass (kernel.llm imports no cmm.domains)
ANTI_FRAGMENTATION=pass (no parallel router/registry/catalog/fallback/gateway)
AGENT_RUNTIME_REVERSE_IMPORTS=pass (cmm.agent_runtime imports no cmm.domains)
```

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
```

Note on the repository-wide Ruff gate: `ruff check cmm kernel tests` is red at
the Phase 10.46 starting HEAD as well (813 findings; 257 files unformatted) under
the installed Ruff 0.16.2 expanded default rule set. No Phase 10.46 file is among
them. The project's declared check
([`CONTRIBUTING.md`](../../CONTRIBUTING.md)) scopes Ruff to changed Python files
and passes for all 14 changed files.

## 11. Architecture invariants

```text
DOMAIN_CONCRETE_MODEL_IDS=NONE
DOMAIN_CONCRETE_PROVIDER_IDS=NONE
NEW_DOMAIN_MODEL_ROUTER=NO
NEW_DOMAIN_PROVIDER_REGISTRY=NO
NEW_DOMAIN_MODEL_CATALOG=NO
NEW_DOMAIN_FALLBACK_ENGINE=NO
KERNEL_TO_DOMAINS_IMPORT=NO
PHASE_10_47_IMPLEMENTED=NO
```

Guards: `tests/domains/test_domain_model_policy_architecture.py` (AST/import
inspection with detector-calibration tests) plus the pre-existing reverse-import
and public-API guards.

## 12. State

```text
PHASE10_46=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
DP-046=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION
AT-DP-046=PASS_REPORTED
CLOSURE_ELIGIBLE=NO
```

Next action: exact-HEAD independent audit of Phase 10.46. Phase 10.47 has not
started.
