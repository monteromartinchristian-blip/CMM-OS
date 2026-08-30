# Phase 10.35 — Domain SDK Design

**Status:** Approved design
**Phase:** 10.35 — Domain SDK
**Base HEAD:** `84d4df0e7b39c171a347c3dee3e27ca725e04656`
**Branch:** `feature/phase-10-domain-intelligence`
**Implementation status:** Not started

## 1. Purpose

Phase 10.35 introduces a public Domain SDK that allows developers to create, validate, test, and package new CMM OS Domain Packs without modifying Domain Intelligence core code for each new domain.

The SDK is an ergonomics and development layer over the Domain infrastructure already implemented in Phases 10.1–10.34.

It is not a new Domain Runtime.

The defining success criterion is:

> A developer can create a new Domain Pack through the public SDK, validate it with the canonical Domain Validation pipeline, test it in isolation using canonical runtime semantics, and package it for transport without adding domain-specific logic to CMM OS core.

The primary developer workflow is:

```text
create
  ↓
validate
  ↓
test
  ↓
pack
```

The corresponding minimum CLI is:

```text
cmm domain create <name>
cmm domain validate <path>
cmm domain test <path>
cmm domain pack <path>
```

---

## 2. Architectural principle

The Domain SDK MUST remain a thin facade over the existing Domain Intelligence architecture.

The canonical relationship is:

```text
Developer / CLI
       ↓
Domain SDK
       ↓
existing Domain contracts
       ↓
existing Domain Discovery / Manifest Reader
       ↓
existing Domain Validation
       ↓
existing Domain Loader / Registries
       ↓
existing Domain runtime semantics
```

Phase 10.35 MUST NOT introduce parallel versions of:

- `DomainRegistry`;
- Domain Discovery;
- `DomainLoader`;
- Domain Validation;
- Domain Resolver;
- Domain Conflict Resolver;
- Domain Composer;
- resource registries;
- profile registries;
- rule registries;
- operation registries;
- workflow registries;
- permission registries;
- approval machinery;
- trace machinery;
- session machinery;
- memory infrastructure;
- a Planner;
- an Agent Runtime;
- a Workflow Engine;
- a permissions system.

The SDK owns developer ergonomics.

The existing Domain layer owns runtime truth.

---

## 3. Existing canonical infrastructure

Phase 10.35 builds directly on the infrastructure already present at the approved base HEAD.

At minimum, the implementation MUST reuse the existing canonical equivalents of:

- `DomainDefinition`;
- `DomainManifest`;
- `DomainPack`;
- `ParsedDomainPack`;
- `DomainRegistry`;
- `FileSystemDomainDiscovery`;
- `JsonDomainManifestReader`;
- `DeclarativeDomainLoader`;
- `DomainValidationRequest`;
- `DomainValidationResult`;
- the Domain Validation service and Validation pipeline;
- resource registry contracts;
- profile registry contracts;
- rule infrastructure;
- operation registry and execution infrastructure;
- workflow registry and execution infrastructure;
- permission registry/evaluation infrastructure;
- approval contracts;
- trace contracts;
- canonical in-memory registry/store implementations intended for isolated execution.

Existing behavior remains authoritative.

In particular:

- discovery remains non-executing and side-effect free;
- loading remains transactional;
- registry rollback continues to use canonical snapshot/restore semantics;
- compatibility remains part of canonical Domain Validation;
- fragmentation checks remain part of canonical Domain Validation;
- permissions remain governed by the existing permission machinery;
- domain loading does not silently imply authorization or enablement.

---

## 4. Manifest format decision

Earlier Phase 10 planning material used `manifest.yaml` as a conceptual example.

The implemented runtime at the Phase 10.35 base HEAD discovers:

```text
manifest.json
domain.json
```

with `manifest.json` as the preferred filename and uses `JsonDomainManifestReader` as the canonical manifest reader.

Therefore Phase 10.35 standardizes SDK-generated Domain Packs on:

```text
manifest.json
```

Phase 10.35 MUST NOT add YAML manifest support merely to reproduce the historical roadmap illustration.

No second manifest parser or representation is required.

The SDK MUST generate manifests consumable directly by the existing manifest reader and validation pipeline.

Documentation updated during Phase 10.35 MUST clarify that the historical `manifest.yaml` tree was conceptual and that the implemented canonical SDK format is `manifest.json`.

YAML support, if ever desired later, requires a separate explicit design decision.

---

## 5. Public SDK boundary

The SDK should live under the Domain namespace and expose a small, intentional public surface, conceptually:

```text
cmm.domains.sdk
```

The exact file decomposition is an implementation-plan decision, but the SDK has six distinct responsibilities:

1. builders;
2. scaffolding/templates;
3. fixtures;
4. test harness;
5. packaging;
6. CLI integration.

No SDK component may become an alternative runtime subsystem.

---

## 6. Builders

### 6.1 ManifestBuilder

`ManifestBuilder` provides ergonomic construction of canonical `DomainManifest` data.

It MUST:

- produce data valid for the existing `DomainManifest` contract;
- use canonical identifiers and versions;
- use canonical compatibility representation;
- preserve deterministic serialization;
- reject or surface invalid values through canonical contracts;
- avoid maintaining a second schema;
- generate `manifest.json` compatible with `JsonDomainManifestReader`.

It MAY provide safe defaults for fields that have obvious SDK defaults.

It MUST NOT:

- define another manifest object model;
- invent another compatibility algorithm;
- bypass canonical validation;
- silently weaken validation requirements.

### 6.2 DomainBuilder

`DomainBuilder` provides ergonomic construction of canonical domain definition and associated pack declarations.

It MUST build on existing Domain contracts.

It MUST NOT register, enable, execute, or install a domain as a side effect of construction.

Builder construction and runtime mutation remain separate operations.

### 6.3 Historical conceptual builders

The Phase 10 planning document listed conceptual components including:

- `ResourceRegistrationAPI`;
- `RuleRegistrationAPI`;
- `OperationRegistrationAPI`;
- `WorkflowRegistrationAPI`;
- `PermissionBuilder`;
- `PresentationBuilder`;
- `DomainCompatibilityChecker`.

These names are behavioral requirements, not mandatory new runtime classes.

Phase 10.35 MUST NOT create parallel registries or compatibility logic merely to satisfy those historical names.

Where ergonomic helpers are useful, they MUST delegate to canonical contracts or registries.

Where the existing public API is already sufficiently ergonomic, the SDK SHOULD reuse it directly.

`DomainCompatibilityChecker`, if exposed at all, MUST delegate to the canonical compatibility validation behavior rather than implement compatibility independently.

---

## 7. Scaffold model

The SDK MUST provide a scaffold mechanism that can create a new external/local Domain Pack without modifying `cmm/domains` internals.

The first and mandatory template is:

```text
basic_domain
```

The generated scaffold MUST be minimal and executable by the real Phase 10.35 developer workflow.

A conceptual minimal structure is:

```text
example/
├── manifest.json
├── README.md
├── fixtures/
│   └── sample.json
└── tests/
    └── test_domain.py
```

Additional files MUST only be generated when required by the real canonical Domain Pack contract or by a meaningful template capability.

The scaffold MUST NOT create empty directories or placeholder modules merely to resemble the older roadmap tree.

Generated Domain Packs MUST be understandable without requiring edits inside `cmm/domains`.

---

## 8. Templates

The historical Phase 10 design lists:

- `basic_domain`;
- `personal_domain`;
- `high_risk_domain`;
- `project_domain`;
- `read_only_domain`;
- `external_service_domain`;
- `multi_domain_extension`.

These are SDK ergonomics presets.

They MUST NOT become new runtime Domain kinds unless the existing canonical contracts already contain an equivalent concept.

### 8.1 Mandatory closure requirement

`basic_domain` is mandatory for Phase 10.35 closure.

### 8.2 Additional templates

The remaining templates SHOULD be implemented as lightweight data/scaffold presets when this can be done without inventing additional runtime abstractions.

They MAY be deferred within Phase 10.35 until the core create/validate/test/pack vertical slice is working.

They MUST reuse the same scaffold engine.

No template may require a parallel runtime path.

---

## 9. Validation

`cmm domain validate <path>` and the SDK validation facade MUST use the canonical Domain Validation implementation.

The SDK MUST NOT define a reduced “SDK validation” that can disagree with runtime validation.

Canonical validation remains responsible for the existing checks, including the implemented equivalents of:

- manifest validation;
- contract validation;
- permission validation;
- dependency validation;
- compatibility validation;
- security validation;
- fragmentation validation;
- Domain Pack tests where part of the canonical pipeline.

The SDK MAY improve how validation results are presented to developers.

Presentation changes MUST NOT change validation semantics.

The same invalid Domain Pack MUST not pass the SDK while failing the canonical runtime validator.

---

## 10. Domain Test Harness

Phase 10.35 MUST provide a `DomainTestHarness` or equivalent public SDK facility for isolated Domain Pack testing.

The harness MUST use canonical runtime semantics.

It is not a mock Domain Runtime.

Conceptually:

```text
DomainTestHarness
    ├── canonical discovery / manifest parsing
    ├── canonical Domain Validation
    ├── canonical Domain loader where runtime loading is required
    ├── isolated canonical in-memory registries/stores
    ├── real permission semantics
    ├── real rule semantics
    ├── real operation semantics
    ├── real workflow semantics
    ├── real approval contracts where applicable
    └── real trace contracts where applicable
```

The harness MAY supply in-memory state, fixtures and adapters.

Those adapters MUST implement the same existing contracts used by production/runtime code.

The harness MUST NOT:

- create different rule semantics;
- create different permission semantics;
- create a fake workflow engine;
- create a fake resolver;
- bypass approvals that would be required by canonical execution;
- make an invalid pack appear valid.

Isolation means state isolation, not semantic substitution.

---

## 11. Fixtures

Phase 10.35 MUST provide a minimal fixture loading facility for Domain Pack tests.

Conceptually:

```text
DomainFixtureLoader
```

The fixture facility MUST:

- load developer-owned test input from the Domain Pack;
- be deterministic;
- avoid mutating global CMM OS state;
- avoid interpreting fixtures as executable commands;
- expose data to the canonical test harness.

JSON is the preferred fixture format for the first implementation because it matches the existing declarative direction and requires no additional parser dependency.

Additional fixture formats are out of scope unless already provided canonically.

---

## 12. Domain tests and `cmm domain test`

`cmm domain test <path>` MUST provide a safe way to execute the Domain Pack's development tests.

The command MUST:

1. resolve the target Domain Pack safely;
2. validate it through canonical validation;
3. prepare isolated canonical runtime/test state;
4. execute the Domain Pack tests;
5. return a non-zero exit status for validation or test failure.

If pytest is used internally, subprocess invocation MUST avoid shell interpolation.

Preferred execution shape:

```text
sys.executable -m pytest ...
```

The implementation MUST NOT use:

```text
shell=True
```

for user-controlled Domain Pack paths or test declarations.

A manifest MUST NOT be able to inject arbitrary shell commands into `cmm domain test`.

---

## 13. Packaging

Phase 10.35 MUST provide a `DomainPackager` or equivalent public SDK facility.

Its responsibility is:

```text
validate
   ↓
reject blocking validation failures
   ↓
package
```

The packager is not an installer.

It MUST NOT:

- register the domain;
- enable the domain;
- modify the production registry;
- publish the domain to a remote service;
- execute arbitrary install hooks.

The output SHOULD be deterministic for identical source content where practical.

The preferred first transport is a deterministic `.tar.gz` archive implemented with the Python standard library unless an existing canonical package format already provides the required behavior.

Packaging MUST exclude transient and unsafe development artifacts such as appropriate equivalents of:

- `__pycache__/`;
- `.pytest_cache/`;
- `.DS_Store`;
- local virtual environments;
- generated caches;
- obvious editor metadata.

The packager MUST reject path traversal and MUST NOT include files outside the requested Domain Pack root.

---

## 14. CLI architecture

CMM OS currently uses `argparse`.

Phase 10.35 MUST integrate into the existing CLI architecture.

It MUST NOT add Typer, Click, or a second CLI framework.

The mandatory CLI surface is:

```text
cmm domain create <name>
cmm domain validate <path>
cmm domain test <path>
cmm domain pack <path>
```

These commands correspond directly to the Phase 10.35 objective.

### 14.1 `cmm domain create`

Creates a new Domain Pack scaffold using an SDK template.

The default template is `basic_domain`.

It MUST:

- validate the requested domain name/slug;
- refuse unsafe destination traversal;
- avoid overwriting existing files unless an explicit safe policy is later designed;
- create deterministic scaffold content;
- generate `manifest.json`;
- perform no registry mutation.

### 14.2 `cmm domain validate`

Delegates to canonical validation.

It MUST:

- return success only when the canonical validation outcome permits it;
- provide developer-readable diagnostics;
- support automation-friendly exit codes.

### 14.3 `cmm domain test`

Delegates to the canonical test harness and safe test execution path.

### 14.4 `cmm domain pack`

Validates and creates the transport archive.

It MUST refuse packaging when blocking validation errors exist.

---

## 15. Optional CLI conveniences

The historical roadmap also names:

```text
cmm domain inspect
cmm domain list
cmm domain discover
```

These MAY be added during Phase 10.35 only if they are thin, low-risk delegations to already-existing infrastructure.

They are not required for Phase 10.35 closure.

The implementation MUST NOT expand scope or add infrastructure merely to provide them.

---

## 16. Explicit Phase 10.35 / 10.36 boundary

Phase 10.36 is the Domain API phase.

Phase 10.35 MUST NOT absorb 10.36.

The following capabilities are therefore outside the required Phase 10.35 implementation:

```text
cmm domain install
cmm domain uninstall
cmm domain enable
cmm domain disable
cmm domain reload
cmm domain publish
cmm domain capabilities
cmm domain operations
cmm domain workflows
cmm domain permissions
cmm domain resolve
cmm domain trace
```

Some underlying functionality already exists internally.

That does not make its public CLI/API exposure a Phase 10.35 requirement.

In particular Phase 10.35 MUST NOT introduce:

- remote publication infrastructure;
- marketplace infrastructure;
- package repositories;
- installation management;
- an HTTP Domain API;
- a second service layer intended only for later API exposure.

Phase 10.36 should expose stable public contracts over the same internal services created or reused by 10.35.

CLI and future API MUST converge on shared internal services rather than parallel implementations.

---

## 17. Existing built-in domains

Phase 10.35 does not require migrating existing built-in domains to the SDK.

Existing domains such as `general`, `health`, `project`, `sport`, `parenthood`, `relationships`, `university`, `life_plan`, `languages`, `concerns`, `oppositions`, and `reflection` remain valid implementations.

The SDK may use them as architectural references and regression fixtures.

It MUST NOT:

- mass-rewrite them;
- restructure them;
- force them into the new external scaffold shape;
- change their runtime behavior merely for SDK uniformity.

A new SDK-created Domain Pack proves the feature.

Migration of established built-in domains is separate work.

---

## 18. External Domain Pack boundary

A central Phase 10.35 requirement is proving that a Domain Pack can live outside the built-in `cmm/domains/<name>` tree.

The acceptance path MUST exercise a temporary or fixture-owned external Domain Pack directory.

The implementation must not succeed only because the sample domain was manually imported into CMM OS core.

The external pack must reach canonical discovery/validation/testing/packaging through public interfaces.

This is the primary evidence that new domains can be developed without core modification.

---

## 19. Security and path safety

Developer tooling accepts filesystem paths and therefore MUST treat them as untrusted input.

At minimum Phase 10.35 MUST protect against:

- `..` traversal escaping the target root;
- absolute paths where a relative scaffold component is expected;
- symlink escape when collecting package contents where relevant;
- overwrite of unrelated existing files;
- archive members outside the Domain Pack root;
- command injection via paths or manifest values;
- arbitrary shell execution from test metadata;
- accidental inclusion of secrets/caches where existing security validation already detects them.

The SDK MUST delegate content/security validation to canonical Domain Validation whenever possible rather than maintaining a second security ruleset.

Filesystem safety specific to scaffolding and packaging remains the SDK's responsibility.

---

## 20. Error model

The SDK SHOULD expose errors in a form useful to both Python callers and CLI users.

Existing Domain exceptions remain canonical for existing runtime failures.

The SDK MAY define narrowly scoped exceptions for SDK-only concerns such as:

- scaffold destination conflicts;
- invalid scaffold template selection;
- packaging path violations;
- fixture loading errors.

SDK exceptions MUST NOT duplicate existing Domain runtime error classes.

CLI commands MUST translate expected validation/developer errors into concise diagnostics and non-zero exit codes without tracebacks by default.

Unexpected programming errors MAY retain standard failure behavior suitable for debugging.

---

## 21. Side-effect policy

SDK construction, inspection, validation and packaging MUST be side-effect constrained.

The following operations MUST NOT mutate production Domain state:

- builder construction;
- scaffold generation outside its requested destination;
- discovery;
- validation;
- fixture loading;
- packaging.

The test harness MUST use isolated state.

It MUST NOT mutate the process-global or production registry.

Any loader invocation used by the harness must operate only against isolated canonical registries/stores.

---

## 22. Domain Sessions invariant

Phase 10.35 inherits the Phase 10.34 session security model.

The SDK MUST NOT weaken the principle:

```text
Persisted domain snapshot != current authorization != current truth
```

Testing or loading a Domain Pack must not grant authority merely because persisted or fixture state says the domain was previously valid or authorized.

Where Domain Sessions participate in SDK tests, current canonical revalidation semantics remain authoritative.

No SDK helper may create a shortcut around Domain Session revalidation.

---

## 23. Domain Events invariant

Phase 10.35 does not add a new runtime lifecycle event merely because SDK actions exist.

The general Domain event catalog remains:

```text
GENERAL_EVENT_COUNT=23
GENERAL_EVENT_UNIQUE_COUNT=23
```

Phase 10.35 MUST NOT add:

```text
domain.session.resumed
```

or SDK-specific runtime events such as:

```text
domain.sdk.created
domain.sdk.validated
domain.sdk.tested
domain.sdk.packed
```

unless a separate runtime event design is explicitly approved.

CLI/developer tooling output is not a reason to expand the runtime event catalog.

---

## 24. Domain Conflict Resolver invariant

`DomainConflictResolver` remains pure.

Phase 10.35 MUST NOT add SDK-specific state, filesystem access, registration mutation, or packaging concerns to conflict resolution.

If the test harness exercises conflict behavior, it must call the canonical pure resolver through existing contracts.

---

## 25. No core modification per new domain

The phrase “without modifying CMM OS core” means:

Once Phase 10.35 itself is implemented, creating a new SDK Domain Pack MUST NOT require edits to central Domain runtime code.

In particular, a new external Domain Pack must not require adding its slug to:

- a hard-coded kernel switch;
- a resolver conditional;
- a central permission conditional;
- a central workflow conditional;
- a central operation conditional;
- a central registry list;
- a hard-coded Domain loader map.

Core may contain generic SDK infrastructure.

Core must not contain future per-domain knowledge.

---

## 26. Acceptance flow

The Phase 10.35 acceptance test MUST demonstrate the full developer lifecycle with an external temporary/sample Domain Pack.

Minimum flow:

```text
1. create scaffold
2. inspect generated manifest.json
3. discover/parse through canonical infrastructure
4. validate through canonical Domain Validation
5. load or construct isolated canonical test state
6. execute Domain Pack test through DomainTestHarness
7. package the Domain Pack
8. unpack to a fresh location
9. discover/parse the unpacked pack
10. validate the unpacked pack again
```

The acceptance test MUST prove that no edit to `cmm/domains/<new-domain>` or any central domain-specific map was necessary.

This acceptance path becomes the conceptual `AT-DP-035`.

The exact repository naming for `DP-035` / `AT-DP-035` MUST follow the current Phase 10 acceptance/evidence convention discovered in the repo.

No new audit/evidence framework should be invented if the existing convention is sufficient.

---

## 27. Testing strategy

Implementation follows test-driven development.

Tests should be added in focused layers.

### 27.1 Builder tests

Verify:

- canonical objects are produced;
- serialization is deterministic;
- invalid values fail through canonical contracts;
- no registration/runtime mutation occurs.

### 27.2 Scaffold tests

Verify:

- `basic_domain` produces expected minimal files;
- `manifest.json` parses canonically;
- generated paths remain inside destination;
- existing destinations are protected;
- generated pack validates.

### 27.3 Harness tests

Verify:

- isolated canonical registries are used;
- runtime semantics match canonical behavior;
- invalid permissions/rules/operations/workflows do not become valid;
- no global registry mutation occurs;
- fixture state does not bypass authorization.

### 27.4 Fixture tests

Verify deterministic and safe fixture loading.

### 27.5 Packager tests

Verify:

- blocking validation failure prevents packaging;
- archive is valid;
- archive members remain inside root;
- transient files are excluded;
- unpacked content revalidates;
- deterministic packaging where designed.

### 27.6 CLI tests

Verify:

```text
cmm domain create
cmm domain validate
cmm domain test
cmm domain pack
```

including exit status and expected failure paths.

### 27.7 Acceptance test

Verify the complete external lifecycle.

### 27.8 Regression tests

Phase 10.35 closure MUST rerun relevant existing Domain infrastructure regressions, including:

- discovery;
- manifest;
- loader;
- registry;
- validation;
- compatibility;
- fragmentation;
- permissions;
- resources;
- rules;
- operations;
- workflows;
- traces;
- resolver/conflict invariants;
- Domain Sessions;
- Domain Events.

The entire repository test suite must remain green before implementation is considered complete.

---

## 28. Public API

The SDK must expose its intended developer-facing classes/functions through an explicit stable import surface.

Consumers SHOULD be able to use the SDK without importing private implementation modules.

Conceptually:

```python
from cmm.domains.sdk import (
    DomainBuilder,
    ManifestBuilder,
    DomainFixtureLoader,
    DomainTestHarness,
    DomainPackager,
)
```

Exact exported names may be refined in the implementation plan where existing conventions require it, but the public surface must remain small.

The top-level `cmm.domains` package SHOULD only re-export SDK symbols if that matches the package's established public API policy.

No broad wildcard exposure is required.

---

## 29. Documentation

Phase 10.35 documentation MUST cover:

- SDK purpose and non-goals;
- `manifest.json` canonical format;
- creating a Domain Pack;
- validating it;
- testing it;
- packaging it;
- basic template usage;
- relation between SDK and canonical runtime;
- explicit 10.35/10.36 boundary;
- security/path restrictions;
- external Domain Pack example.

Documentation MUST NOT claim:

- independent audit completion before the audit occurs;
- Phase 10.35 closure before the audit occurs;
- YAML support that does not exist;
- installation/publishing capabilities that are deferred;
- API endpoints belonging to Phase 10.36.

Before independent audit, documentation may state:

```text
implementation complete — independent audit pending
```

once implementation is actually complete.

---

## 30. Implementation sequencing

The implementation plan should preserve the following vertical progression.

### Slice 1 — Create + validate

```text
ManifestBuilder
+
minimum DomainBuilder
+
basic_domain scaffold
+
cmm domain create
+
cmm domain validate
+
canonical validation
```

First milestone:

```bash
cmm domain create example
cmm domain validate ./example
```

### Slice 2 — Test

```text
DomainFixtureLoader
+
DomainTestHarness
+
cmm domain test
```

Second milestone:

```bash
cmm domain test ./example
```

### Slice 3 — Pack

```text
DomainPackager
+
cmm domain pack
```

Third milestone:

```bash
cmm domain pack ./example
```

### Slice 4 — Hardening and remaining Phase 10.35 ergonomics

Only after the complete basic lifecycle works:

- additional templates;
- optional inspect/list/discover conveniences if genuinely thin;
- public API hardening;
- security/path edge cases;
- acceptance evidence;
- documentation;
- full regression suite.

This ordering prevents broad SDK scaffolding before one real Domain Pack lifecycle works end-to-end.

---

## 31. Out of scope

The following are explicitly out of scope for Phase 10.35:

- HTTP Domain API;
- marketplace;
- remote registry;
- remote publication;
- signing infrastructure not already canonical;
- dependency download/install;
- environment management;
- installation lifecycle;
- enable/disable management CLI;
- runtime resolution CLI;
- trace query CLI;
- operation execution CLI;
- workflow execution CLI;
- permissions administration CLI;
- migration of built-in domains;
- YAML support;
- a new Domain Runtime;
- a new registry implementation;
- a new compatibility engine;
- a new validator;
- a new resolver;
- a new workflow engine;
- a new permissions engine;
- a new event family;
- Phase 10.36 implementation.

---

## 32. Engineering constraints

Phase 10.35 implementation MUST follow these project-wide constraints:

```text
PUSH=NO
MERGE=NO
```

The existing quarantine stash must remain preserved exactly:

```text
stash@{0}: On feature/phase-10-domain-intelligence: quarantine: post-audit phase 10.32 uncommitted changes
```

The following commands remain forbidden unless explicitly authorized:

```text
git stash
git stash pop
git stash apply
git stash drop
git reset
git clean
git worktree
```

Before implementation commits:

- inspect exact diff scope;
- run `git diff --check`;
- run relevant focused tests;
- keep unrelated files untouched.

Commits should represent meaningful implementation slices rather than excessive audit/documentation fragmentation.

No push or merge occurs during Phase 10.35 implementation/audit unless separately instructed.

---

## 33. Audit boundary

Implementation completion and Phase closure are different states.

When implementation, tests and documentation are complete:

```text
PHASE10_35_IMPLEMENTATION=COMPLETE
INDEPENDENT_AUDIT=PENDING
PHASE10_35_CLOSED=NO
```

The independent audit bundle MUST be generated from the exact committed audited source using:

```text
git archive
```

not from the mutable worktree.

The bundle must be created only after:

- implementation is committed;
- required tests are green;
- documentation is committed;
- worktree is clean;
- quarantine stash remains preserved.

If implementation changes after bundle creation, that bundle is stale and a new versioned audit bundle is required.

The independent auditor for Phase 10.35 is ChatGPT in the CMM OS project unless explicitly changed by the user.

The audit should evaluate the software and its evidence.

Phase 10.35 MUST NOT create audit machinery whose main purpose is to audit other audit machinery.

---

## 34. Definition of done

Phase 10.35 implementation is ready for independent audit only when all of the following are true:

1. a public `cmm.domains.sdk` surface exists;
2. the SDK reuses canonical Domain infrastructure;
3. no second Domain Runtime exists;
4. no second Domain Registry exists;
5. no second Domain Loader exists;
6. no second validation pipeline exists;
7. no second compatibility engine exists;
8. no second resolver exists;
9. no second workflow engine exists;
10. no second permissions system exists;
11. SDK scaffolds use canonical `manifest.json`;
12. `basic_domain` works;
13. `cmm domain create` works;
14. `cmm domain validate` uses canonical validation and works;
15. `DomainTestHarness` uses isolated canonical semantics;
16. `DomainFixtureLoader` works safely;
17. `cmm domain test` works safely;
18. `DomainPackager` validates before packaging;
19. `cmm domain pack` works;
20. a packed Domain Pack can be unpacked and canonically revalidated;
21. a new external Domain Pack requires no domain-specific core modification;
22. relevant path traversal/overwrite/archive safety tests pass;
23. Domain Event catalog remains `23/23`;
24. no `domain.session.resumed` event is introduced;
25. Domain Session security semantics remain intact;
26. Domain Conflict Resolver purity remains intact;
27. focused SDK tests pass;
28. relevant Phase 10 regressions pass;
29. full repository suite passes;
30. lint/format/compile checks required by repository policy pass;
31. developer documentation is complete;
32. implementation is committed;
33. worktree is clean;
34. quarantine stash is preserved;
35. `PUSH=NO`;
36. `MERGE=NO`;
37. an exact-HEAD `git archive` audit bundle is generated;
38. independent audit remains pending until ChatGPT reviews that bundle.

---

## 35. Final architectural criterion

Phase 10.35 succeeds when this workflow is real:

```text
Developer
   |
   | cmm domain create example
   v
External Domain Pack
   |
   | canonical manifest/discovery
   v
cmm domain validate
   |
   | canonical Domain Validation
   v
cmm domain test
   |
   | isolated canonical runtime semantics
   v
cmm domain pack
   |
   v
Portable Domain Pack archive
```

and none of those steps require adding `example`-specific code to the CMM OS Domain core.

The SDK is therefore:

```text
public facade + developer ergonomics
```

over the Domain Intelligence platform that already exists.

It is not another platform inside the platform.
