# Domain Knowledge Packages

**Phase:** 10.49 — Domain Knowledge Packages
**Design Point:** `DP-049` — Declarative Domain Specialization of the Canonical Phase 8 KnowledgePackage
**Acceptance Test:** `AT-DP-049` — Connected Domain Knowledge Package Acceptance
**Status:** `PHASE10_49=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT` · `DP-049=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION` · `AT-DP-049=PASS_REPORTED` · `BLOCKERS=0` · `MAJORS=0` · `MINORS=0` · `CLOSURE_ELIGIBLE=NO` (independent audit pending)

> A Domain Pack declares how the canonical Phase 8 `KnowledgePackage` must be
> shaped for that domain. The declaration can only **narrow** — require, restrict
> or prohibit. It can never grant authority, and it never becomes a second
> knowledge store.

## 1. Purpose and boundaries

Phase 10.49 adds the canonical Domain Intelligence **knowledge-package schema**
layer:

```text
Phase 8      cmm.cognitive.knowledge_packages.KnowledgePackage  (sole truth)
Phase 10.40  Domain ↔ Cognitive integration (canonical builder seam)
Phase 10.49  Domain knowledge package schema: declare → compose → validate
Phase 10.50  (next) knowledge package schema is an input, not a competitor
```

A Domain Pack may declare which canonical package sections are required,
optional or prohibited, what each field must contain, which epistemic kinds are
admissible, whether provenance/temporal evidence must be retained, whether
uncertainty and contradictions must be preserved, and the minimum sensitivity
floor of the package.

Everything is declarative and local. Phase 10.49 never builds a package, never
stores knowledge, never resolves an opaque validator reference, and never calls
a model or provider.

## 2. Public contracts

Exposed additively through `cmm.domains`:

```python
DomainKnowledgePackageFieldPolicy
DomainKnowledgePackageSchema
EffectiveDomainKnowledgePackageSchema
compose_domain_knowledge_package_schemas
validate_domain_knowledge_package
```

No builder, registry, loader, resolver, store, runtime or engine API is
exported. The canonical Phase 8 `KnowledgePackageBuilder` remains the only
component that constructs a package.

### 2.1 `DomainKnowledgePackageFieldPolicy`

Immutable, frozen/slotted constraint over **exactly one** canonical package
field:

```python
DomainKnowledgePackageFieldPolicy(
    field_name="facts",
    required_non_empty=True,
    minimum_items=None,
    allowed_knowledge_kinds=(KnowledgeKind.FACT,),
    require_provenance=False,
    require_temporal_scope=False,
    preserve_uncertainty=False,
    preserve_contradictions=False,
)
```

* `field_name` must name a field of the canonical `KnowledgePackage`; the finite
  vocabulary is declared literally in `CANONICAL_KNOWLEDGE_PACKAGE_FIELDS` (30
  names) and is never derived at runtime, so the Domain surface stays auditable
  against the Phase 8 dataclass.
* `required_non_empty` and `minimum_items` are the only policies that *require*
  content; both are rejected when the field is also prohibited.
* `allowed_knowledge_kinds` is only valid for the canonical knowledge-item
  category fields (`facts`, `observations`, `inferences`, `hypotheses`,
  `other_knowledge`) and may only name canonical `KnowledgeKind` values.
* `preserve_uncertainty` targets `KnowledgeKind.INFERENCE` / `KnowledgeKind.HYPOTHESIS`
  items and rejects an item whose confidence collapses to `1.0`.
* `preserve_contradictions` rejects a resolved canonical `Contradiction`, keeping
  contradictions visible rather than silently reconciled.

A policy can only narrow or require evidence. It never grants authority.

### 2.2 `DomainKnowledgePackageSchema`

Immutable, versioned Domain declaration:

```python
DomainKnowledgePackageSchema(
    id="knowledge-package-schema:health",
    domain_id=DomainId(slug="health"),
    version="1",
    base_schema="KnowledgePackage",
    required_sections=("objective",),
    optional_sections=(),
    prohibited_sections=(),
    field_policies=(...),
    minimum_sensitivity=SensitivityLevel.SENSITIVE,
    validator_refs=(),
    metadata={},
)
```

* `base_schema` must be exactly `"KnowledgePackage"`; the Domain schema always
  specializes the canonical Phase 8 contract and never replaces it.
* `id`, `domain_id` and `version` are required; `domain_id` is the canonical
  `DomainId` from `cmm.domains.identifiers` — no competing identifier type
  exists.
* `required_sections`, `optional_sections` and `prohibited_sections` must be
  pairwise disjoint.
* `field_policies` is deduplicated by `field_name` and canonically sorted by
  `field_name`.
* `minimum_sensitivity` reuses the canonical Cognitive `SensitivityLevel`; no
  new Domain privacy enum is introduced.
* `validator_refs` are opaque, non-empty, duplicate-free references. Their
  presence neither authorizes nor implies that a validator implementation
  exists, and Phase 10.49 never resolves them.
* `metadata` is immutable, JSON-safe, descriptive audit metadata.

### 2.3 `EffectiveDomainKnowledgePackageSchema`

Immutable composition evidence over one or more Domain schemas:

```text
source_schema_ids, domain_ids, required_sections, optional_sections,
prohibited_sections, field_policies, minimum_sensitivity, validator_refs
```

It is effective **policy** evidence, never a package model: it carries no
knowledge payload and no mutable user state. `source_schema_ids` and `domain_ids`
are canonically sorted, so composition output is order-independent.

## 3. Composition semantics

`compose_domain_knowledge_package_schemas(schemas)` is a pure, deterministic,
monotonic narrowing:

```text
required_sections  = union
optional_sections  = union − required − prohibited
prohibited_sections = union
field_policies     = per-field merge (see below)
minimum_sensitivity = strongest floor by explicit canonical rank
validator_refs     = union
```

Per-field merge:

```text
required_non_empty     = any
minimum_items          = max
allowed_knowledge_kinds = intersection of configured sets (empty ⇒ fail closed)
require_provenance     = any
require_temporal_scope = any
preserve_uncertainty   = any
preserve_contradictions = any
```

Fail-closed conditions:

* an empty schema iterable;
* a non-`DomainKnowledgePackageSchema` element;
* a non-empty intersection of `required_sections` and `prohibited_sections`
  (`details["conflict"]` lists the irreconcilable sections);
* an empty `allowed_knowledge_kinds` intersection for a field;
* a prohibited section whose composed policy still requires content.

Composition never invents a synthetic Domain identity and never grants
authority. Schemas are normalized by `(str(domain_id), version, id)` before
merging, so the result does not depend on caller ordering.

## 4. Validation semantics

`validate_domain_knowledge_package(package, schema)` accepts **only** the exact
canonical `KnowledgePackage` type (a subclass or duck-typed object fails closed),
returns the **same object** on success, and never mutates the package.

Checks run in canonical order:

```text
prohibited sections → required sections → field policies → minimum sensitivity
```

* A prohibited section that carries content fails closed.
* A required section that is empty fails closed.
* Field policies are applied in `field_name` order and cover presence, minimum
  item count, admissible epistemic kinds, retained provenance, retained temporal
  evidence, preserved uncertainty and preserved contradictions.
* `preserve_uncertainty` and `preserve_contradictions` never treat absence as
  erasure: an empty field is not a violation of those policies.

The function is pure and resolves no opaque validator reference.

## 5. Canonical sensitivity ordering

Composition and validation use an **explicit** rank mapping — never enum
declaration order, which is not a security boundary:

```text
PUBLIC(0) < INTERNAL(1) < PERSONAL(2) < SENSITIVE(3)
          < HIGHLY_SENSITIVE(4) < RESTRICTED(5)
```

The schema's `minimum_sensitivity` is a **floor**. Validation derives the
package's effective sensitivity through the canonical
`privacy_from_knowledge_package(package)` (which itself composes
`privacy_from_resource` and `privacy_from_knowledge_item`) and fails closed when
the effective sensitivity ranks below the floor. A package with no recognized
privacy sources resolves to the canonical `PrivacyMetadata()` default
(`RESTRICTED`), which satisfies every floor.

No Domain-specific privacy or permission truth is introduced.

## 6. Metadata authority restrictions

Schema and policy metadata is descriptive audit metadata only and must not carry
model/provider/routing authority. A recursive normalized scan over mapping keys
rejects semantic style/case variants (snake_case, kebab-case, camelCase,
PascalCase and compound aliases) of:

```text
model, models, model_id, model_ids, model_family
provider, providers, provider_id, provider_ids
routing_weight, routing_weights
candidate/preferred/prohibited model(s)/provider(s)
```

Only mapping keys are inspected; human-readable prose values are never
fuzzy-scanned. The predicate is mirrored locally from the hardened Phase
10.47/10.48 boundary so the audited Phase 10.49 modules stay frozen.

## 7. `DomainDefinition` integration

`DomainDefinition` gains one additive, last-declared field:

```python
knowledge_package_schema: DomainKnowledgePackageSchema | None = None
```

* Backward-compatible positional construction; a missing serialized field
  deserializes to `None`.
* A mapping value is parsed through `DomainKnowledgePackageSchema.from_dict`.
* A non-mapping, non-schema value fails closed with the
  `knowledge_package_schema` field.
* `knowledge_package_schema.domain_id` must match the definition's `DomainId`.
* Phase 10.46 `model_policy`, Phase 10.47 `benchmark_suites` and Phase 10.48
  `quality_metrics` are preserved unchanged.

Canonical ownership:

```text
DomainRegistry
    ↓
DomainDefinition
    ↓
knowledge_package_schema
```

There is no knowledge-package registry.

## 8. Canonical Domain Pack integration

The existing declarative path is extended, not replaced:

```text
declarative definition
    ↓
existing ParsedDomainPack / Domain Pack parser
    ↓
DomainDefinition
    ↓
knowledge_package_schema
    ↓
existing DomainRegistry
```

`knowledge_package_schema` is accepted as a declarative mapping on the same
canonical path as `benchmark_suites` and `quality_metrics`; a malformed
container fails closed with the `knowledge_package_schema` field. No
`DomainKnowledgePackageLoader`, registry, resolver, store, runtime or engine is
introduced, and the canonical Domain Pack parser is not duplicated.

## 9. Cognitive integration seam

`DefaultDomainCognitiveIntegrator` accepts an optional schema on its request:

```python
if request.knowledge_package_schema is not None:
    package = validate_domain_knowledge_package(
        package, request.knowledge_package_schema
    )
```

The seam runs **after** the canonical `KnowledgePackageBuilder` has produced the
package and the canonical cognitive validation has passed. The Domain schema
therefore constrains an already-built canonical package; it never replaces the
builder, the extraction pipeline, the privacy resolver or the cognitive
validation rules.

The request field is validated as a canonical `DomainKnowledgePackageSchema`
(or `None`); any other type fails closed at the contract boundary.

## 10. First-party schemas

Exactly twelve already-implemented first-party Domain Packs declare an approved
knowledge package schema through a local, pure factory in
`cmm/domains/<domain>/knowledge_package.py`, attached via
`knowledge_package_schema=build_<domain>_knowledge_package_schema()`:

```text
general, health, relationships, university, oppositions, reflection, concerns,
languages, parenthood, sport, life-plan, project
```

Each first-party schema has a distinct policy body derived from its Domain's
existing canonical semantics:

* **general** — broad fallback, no required factual section;
* **health** — documented facts require provenance and temporal validity;
* **relationships** — observed interaction evidence must retain provenance;
* **university** — academic facts require source authority and temporal validity;
* **oppositions** — official call provenance plus current temporal state;
* **reflection** — non-categorised knowledge restricted to opinions and open
  questions (never decisions), no forced certainty;
* **concerns** — missing information must be recorded explicitly;
* **languages** — proficiency claims require provenance; no contradiction rule
  inherited automatically;
* **parenthood** — legal and medical facts require provenance and temporal scope;
* **sport** — performance data requires temporal scope and resource provenance;
* **life_plan** — active goals required; external assumptions must carry provenance;
* **project** — progress evidence and observed state must retain provenance;
  decisions and questions only for non-categorised knowledge.

`minimum_sensitivity` and `memory_policy.sensitivity_limit` are **separate**
contracts. `minimum_sensitivity` is a schema floor applied to every package
validated against that Domain. `memory_policy.sensitivity_limit` governs how
memory proposals are classified in that Domain. They are not one-to-one
derivations.

| Domain | Schema ID | `minimum_sensitivity` | `memory_policy.sensitivity_limit` | Rationale |
| --- | --- | --- | --- | --- |
| general | `knowledge-package-schema:general` | `INTERNAL` | `internal` | Matched |
| health | `knowledge-package-schema:health` | `SENSITIVE` | `HIGHLY_SENSITIVE` | Schema floor < memory limit |
| relationships | `knowledge-package-schema:relationships` | `SENSITIVE` | `HIGHLY_SENSITIVE` | Schema floor < memory limit |
| university | `knowledge-package-schema:university` | `INTERNAL` | `HIGHLY_SENSITIVE` | Schema floor < memory limit |
| oppositions | `knowledge-package-schema:oppositions` | `INTERNAL` | `HIGHLY_SENSITIVE` | Schema floor < memory limit |
| reflection | `knowledge-package-schema:reflection` | `SENSITIVE` | `HIGHLY_SENSITIVE` | Schema floor < memory limit |
| concerns | `knowledge-package-schema:concerns` | `SENSITIVE` | `HIGHLY_SENSITIVE` | Schema floor < memory limit |
| languages | `knowledge-package-schema:languages` | `INTERNAL` | `PERSONAL` | Schema floor > memory limit |
| parenthood | `knowledge-package-schema:parenthood` | `SENSITIVE` | `SENSITIVE` | Matched |
| sport | `knowledge-package-schema:sport` | `SENSITIVE` | `SENSITIVE` | Matched |
| life_plan | `knowledge-package-schema:life_plan` | `SENSITIVE` | `SENSITIVE` | Matched |
| project | `knowledge-package-schema:project` | `INTERNAL` | `INTERNAL` | Matched |

`domain:mental-health` and `domain:neurodivergence` knowledge package schemas
remain out of scope until Phases 10.52/10.53.

## 11. Determinism

* Schema `field_policies` are canonically sorted by `field_name`.
* Composition normalizes schemas by `(str(domain_id), version, id)`.
* Effective schema section tuples and `validator_refs` are sorted.
* Serialization uses stable key ordering and list-form tuples.
* Identical inputs yield equal schemas, equal effective schemas and equal
  serialized payloads.
* Core contracts create no timestamps and no random IDs.

## 12. Phase 10.50 boundary

Phase 10.50 consumes the knowledge package schema as an input. Phase 10.49
provides declaration, composition and validation only; it does not add the
Phase 10.50 capability itself, and nothing in Phase 10.49 may be treated as
pre-authorizing Phase 10.50 behaviour.

## 13. Phase 10.52 / 10.53 deferral

The `mental_health` and `neurodivergence` Domain schemas are explicitly
**not** implemented. Tests assert their absence so the deferral cannot regress
silently.

## 14. Anti-fragmentation rules

Phase 10.49 introduces **no** second knowledge infrastructure. Prohibited
production names (guarded by AST inspection) include:

```text
DomainKnowledgePackageBuilder, DomainKnowledgePackageRegistry,
DomainKnowledgeRegistry, DomainKnowledgePackageLoader, DomainKnowledgeLoader,
DomainKnowledgePackageResolver, DomainKnowledgeResolver,
DomainKnowledgePackageStore, DomainKnowledgeStore,
DomainKnowledgePackageRuntime, DomainKnowledgeRuntime,
DomainKnowledgePackageEngine, DomainKnowledgeEngine
```

Also prohibited: a second knowledge store, graph, provenance, temporal,
contradiction, privacy or permission truth; a second Cognitive Layer; a second
Domain Pack parser; and any provider/model/runtime or network/persistence import
on the Phase 10.49 surface.

`cmm.domains.cognitive_integration` continues to import and call the canonical
`KnowledgePackageBuilder`, and `cmm.cognitive` never imports `cmm.domains`. The
canonical fragmentation owner (`analyze_fragmentation`) reports no findings on
the Phase 10.49 surface.

## 15. Fail-closed validation summary

Rejected at the contract, composition or validation boundary: unknown serialized
fields; missing required serialized fields; empty required strings; non-canonical
field names; duplicate field policies; empty or non-canonical knowledge kinds;
`allowed_knowledge_kinds` on a non-category field; a `base_schema` other than
`"KnowledgePackage"`; overlapping required/optional/prohibited sections; a
prohibited section whose policy requires content; duplicate `validator_refs`;
non-JSON-safe metadata; reserved model/provider/routing authority metadata keys;
empty composition input; non-schema composition elements; irreconcilable
required/prohibited sections; empty knowledge-kind intersections; a non-canonical
package type; a prohibited section carrying content; an empty required section;
a field violating its policy; and an effective sensitivity below the schema
floor.

## 16. Error behavior

Contract boundaries raise `DomainKnowledgePackageContractError`; deserialization
boundaries raise `DomainKnowledgePackageSerializationError` (a subclass of the
contract error); composition raises `DomainKnowledgePackageCompositionError`;
package validation raises `DomainKnowledgePackageValidationError`. All five
derive from the canonical `DomainKnowledgePackageError`, which derives from
`DomainError`. Nested definition/pack parsing uses the canonical indexed
nested-error wrapping (`knowledge_package_schema`).

## 17. Implementation evidence

Production:

```text
cmm/domains/knowledge_package_contracts.py
cmm/domains/knowledge_package_composition.py
cmm/domains/knowledge_package_validation.py
cmm/domains/errors.py                          (five error types)
cmm/domains/contracts.py                       (DomainDefinition.knowledge_package_schema)
cmm/domains/pack.py                            (declarative knowledge_package_schema)
cmm/domains/manifest.py                        (declarative known-field set)
cmm/domains/cognitive_integration_contracts.py (optional request schema)
cmm/domains/cognitive_integration.py           (validation seam)
cmm/domains/__init__.py                        (public exports)
cmm/domains/<twelve domains>/knowledge_package.py
cmm/domains/<twelve domains>/definition.py
```

Tests:

```text
tests/domains/test_domain_knowledge_package_contracts.py
tests/domains/test_domain_knowledge_package_pack_integration.py
tests/domains/test_domain_knowledge_package_composition.py
tests/domains/test_domain_knowledge_package_validation.py
tests/domains/test_domain_knowledge_package_cognitive_integration.py
tests/domains/test_domain_knowledge_package_first_party.py
tests/domains/test_domain_knowledge_package_architecture.py
tests/domains/test_domain_knowledge_package_dp049_acceptance.py
```

Design and plan:

```text
docs/superpowers/specs/2026-09-10-phase-10.49-domain-knowledge-packages-design.md
docs/superpowers/plans/2026-09-10-phase-10.49-domain-knowledge-packages-implementation-plan.md
```

Audit tooling:

```text
scripts/audit/verify_phase_10_49_ruff_baseline.py
tests/domains/test_phase_10_49_remediation_gates.py
```

`AT-DP-049` covers canonical registry discovery, real first-party ownership,
canonical pack round-trip, effective schema composition, canonical package
construction, semantics preservation, valid-schema acceptance, fail-closed
violation, the authority boundary and anti-fragmentation — all over real
canonical components (real first-party definitions, real `DomainRegistry`, real
declarative pack path, real `KnowledgePackageBuilder`).

## 18. Non-goals

Phase 10.49 does not provide: a knowledge package builder, registry, loader,
resolver, store, runtime or engine; a second knowledge store, graph, provenance,
temporal, contradiction, privacy or permission truth; a second Cognitive Layer or
Domain Pack parser; validator resolution or execution; model/provider invocation;
knowledge extraction or materialization; persistence; or any Phase 10.50–10.53
and Phase 11 behaviour.

## 19. Baseline-aware Ruff/format gate

`scripts/audit/verify_phase_10_49_ruff_baseline.py` reuses the Phase 10.48
methodology: it materialises the pinned baseline
(`BASELINE_HEAD=6f9deeb37b6e3237bea4564c5e5607249eb12b70`) read-only through
`git archive`, measures whole-repository Ruff lint and format debt on both the
baseline and the current tree, and requires every Python file changed since the
baseline to be fully Ruff- and format-clean.

```text
RUFF_VERSION
BASELINE_HEAD
GLOBAL_RUFF_BASELINE / GLOBAL_RUFF_CURRENT
GLOBAL_FORMAT_BASELINE / GLOBAL_FORMAT_CURRENT
CHANGED_PYTHON_FILES
CHANGED_PYTHON_RUFF_VIOLATIONS
CHANGED_PYTHON_FORMAT_FILES
CHANGED_PYTHON_RUFF
CHANGED_PYTHON_FORMAT
NO_NEW_RUFF_REGRESSIONS
NO_NEW_FORMAT_REGRESSIONS
BASELINE_AWARE_GATE
```

The gate fails closed (exit `2`) when the measured Ruff version is not the
pinned `0.16.2`, because lint and format results are not comparable across Ruff
releases. It never mutates branches, the index, the working tree or stored
history, and never uses `shell=True`.

`BASELINE_AWARE_GATE=PASS` means Phase 10.49 added no new Ruff or format debt; it
does not mean the whole repository is globally Ruff-clean. `GLOBAL_RUFF` and
`GLOBAL_FORMAT` are reported as `PASS` only when the measured global debt is
actually zero.

## 20. Pre-audit gate evidence

Measured on the frozen implementation HEAD (see §21) from a clean worktree.

```text
FOCUSED_PHASE_10_49_TESTS=317
FOCUSED_PHASE_10_49_RESULT=PASS
REGRESSION_GATE_TESTS=1328
REGRESSION_GATE_RESULT=PASS
DOMAIN_SUITE_TESTS=10967
DOMAIN_SUITE_FAILURES=0
DOMAIN_SUITE_ERRORS=0
GLOBAL_SUITE_TESTS=16728
GLOBAL_SUITE_FAILURES=0
GLOBAL_SUITE_ERRORS=0
COMPILEALL=PASS
BASELINE_AWARE_GATE=PASS
CLAUSE_COVERAGE=PASS
DIFF_HYGIENE=CLEAN
```

The focused gate is the ten Phase 10.49 test files (eight contract/behaviour
files, the architecture guard, the DP-049 connected acceptance, the baseline
gate decision tests and the clause-coverage ledger invariant). The regression
gate is the Phase 8 knowledge-package, Phase 10.39 fragmentation, Phase 10.40
cognitive-integration, Phase 10.44 memory/knowledge, Phase 10.46–10.48
model-policy/benchmark/quality and Domain Pack/SDK inventories. The global gate
is the canonical `python -m pytest -ra` over `tests`.

Execution-environment note: the local WorkBuddy sandbox brokers filesystem
operations that leave the session workspace to a host process, which adds
roughly thirty seconds of latency per operation and makes workspace-resident
suite execution impractically slow. The suite evidence above was therefore
produced against an exact `git archive` export / clone of the same clean HEAD
(`c85b7f5833e0af541c6cb34afdbeb7dbf270560e`), executed with the repository's own
`.venv` interpreter. Two workspace-resident false positives were isolated and
are **not** Phase 10.49 defects:

* `tests/domains/test_domain_sdk_packager.py::test_packager_preserves_competing_destination_created_at_publication`
  — the sandbox `os.link` interceptor raises `PermissionError` (EEXIST) instead
  of `FileExistsError`, so the packager's specific handler does not fire. The
  same test passes against the identical tree outside the brokered path.
* The Phase 10.34 session lifecycle fixtures perform many brokered `mkdir`
  calls, which stalls suite progress without failing.

Both pass in the unbrokered run recorded above.

## 21. Status

```text
PHASE10_49=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT_V2
MAJOR_01=REMEDIATED_REPORTED
MAJOR_02=REMEDIATED_REPORTED
MINOR_01=REMEDIATED_REPORTED
DOMAIN_SPECIFIC_FIRST_PARTY_POLICIES=PASS
NON_FACT_CANONICAL_PACKAGE_COMPATIBILITY=PASS_WHERE_DOMAIN_POLICY_ALLOWS
RESOLVED_CONTRADICTION_PRESERVATION=PASS
DOMAIN_KNOWLEDGE_PACKAGE_SCHEMA=IMPLEMENTED
EFFECTIVE_SCHEMA_COMPOSITION=IMPLEMENTED
CANONICAL_KNOWLEDGE_PACKAGE_VALIDATION=IMPLEMENTED
CANONICAL_BUILDER=KnowledgePackageBuilder
PARALLEL_BUILDER=NONE
PARALLEL_REGISTRY=NONE
PARALLEL_LOADER=NONE
PARALLEL_RESOLVER=NONE
PARALLEL_STORE=NONE
PARALLEL_RUNTIME=NONE
PARALLEL_ENGINE=NONE
FIRST_PARTY_SCHEMAS=12
MENTAL_HEALTH_SCHEMA=NOT_IMPLEMENTED
NEURODIVERGENCE_SCHEMA=NOT_IMPLEMENTED
DP-049=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION
AT-DP-049=PASS_REPORTED
CLOSURE_ELIGIBLE=NO
```

Phase 10.49 is implemented and reported, but it is **not** closed. Closure
requires an independent audit of the exact-HEAD audit bundle; the implementation
agent is not the auditor and cannot self-certify the phase.
