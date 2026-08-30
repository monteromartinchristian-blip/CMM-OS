# Phase 10.35 — Domain SDK Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a thin public Domain SDK that lets developers create, canonically validate, safely test, and deterministically package external CMM OS Domain Packs without adding domain-specific logic to the Domain core.

**Architecture:** `cmm.domains.sdk` is a developer-facing facade over the already-implemented Domain contracts, discovery, manifest reader, validation pipeline, loader, registries, execution semantics, and trace/permission machinery. The SDK owns builders, scaffolding, fixtures, an isolated test harness, packaging, and `argparse` CLI integration; it must not duplicate runtime subsystems.

**Tech Stack:** Python 3, existing CMM OS Domain Intelligence contracts and registries, `argparse`, `pytest`, Python standard-library `json`/`tarfile`/`gzip`/`pathlib`, Ruff and the repository's existing validation tooling.

**Spec:** `docs/superpowers/specs/2026-08-30-domain-sdk-design.md`

**Frozen design commit:** `f19cb47` (`docs(domains): design phase 10.35 domain sdk`)

## Global Constraints

- Repository: `/Users/chris/CMM OS`.
- Branch: `feature/phase-10-domain-intelligence`.
- Design commit `f19cb47` MUST be an ancestor of the implementation HEAD.
- Implementation execution starts from the commit that adds this plan; the later implementation-agent prompt will bind the exact plan commit SHA.
- `PUSH=NO`.
- `MERGE=NO`.
- Preserve exactly: `stash@{0}: On feature/phase-10-domain-intelligence: quarantine: post-audit phase 10.32 uncommitted changes`.
- Do not use `git stash`, `git stash pop`, `git stash apply`, `git stash drop`, `git reset`, `git clean`, or `git worktree` unless the human explicitly authorizes it.
- The canonical SDK manifest filename is `manifest.json`.
- Do not add YAML support.
- Do not create a second Domain Runtime, Registry, Loader, Validator, Resolver, Conflict Resolver, Workflow Engine, permission system, event family, marketplace, installer, or remote publisher.
- Required CLI for closure: `cmm domain create`, `cmm domain validate`, `cmm domain test`, `cmm domain pack`.
- `install`, `uninstall`, `enable`, `disable`, `reload`, `publish`, `capabilities`, `operations`, `workflows`, `permissions`, `resolve`, and `trace` remain out of Phase 10.35.
- `basic_domain` is the mandatory template.
- Existing built-in Domain Packs are references/regressions only; do not migrate or mass-rewrite them.
- Domain Events remain `23/23`; do not add `domain.session.resumed` or SDK lifecycle events.
- Domain Sessions retain `Persisted domain snapshot != current authorization != current truth`.
- `DomainConflictResolver` remains pure.
- Use TDD for every new production behavior: RED → confirm failure reason → minimal GREEN → focused regression.
- Before every commit: exact scope, `git diff --check`, relevant tests green.
- Before audit packaging: implementation/docs committed, full verification green, clean worktree, quarantine stash preserved.
- Independent audit is performed later by ChatGPT; the implementation agent must not self-certify closure.

---

## Planned File Structure

Create the SDK as a focused package:

```text
cmm/domains/sdk/
├── __init__.py
├── builders.py
├── scaffold.py
├── fixtures.py
├── harness.py
├── packager.py
└── cli.py
```

Modify only the established CLI/public surfaces needed for integration:

```text
cmm/__main__.py
cmm/domains/__init__.py          # only if established export policy requires it
cmm/domains/errors.py            # only if a narrow SDK-specific error is actually needed
```

Primary new tests:

```text
tests/domains/test_domain_sdk_builders.py
tests/domains/test_domain_sdk_scaffold.py
tests/domains/test_domain_sdk_fixtures.py
tests/domains/test_domain_sdk_harness.py
tests/domains/test_domain_sdk_packager.py
tests/domains/test_domain_sdk_cli.py
tests/domains/test_domain_sdk_public_api.py
tests/domains/test_domain_sdk_dp035_acceptance.py
```

Documentation expected during implementation:

```text
docs/reference/domain-sdk.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
ROADMAP.md                         # only if current roadmap convention requires implementation-state update
```

Do not create extra SDK modules, audit wrappers, registries, protocol layers, or documentation files unless a concrete implementation need is demonstrated.

---

## Task 0: Repository Alignment and Exact Contract Map

**Files:**
- Read: `docs/superpowers/specs/2026-08-30-domain-sdk-design.md`
- Read: this implementation plan
- Read: `cmm/domains/manifest.py`
- Read: `cmm/domains/manifest_reader.py`
- Read: `cmm/domains/pack.py`
- Read: `cmm/domains/discovery.py`
- Read: `cmm/domains/discovery_contracts.py`
- Read: `cmm/domains/validation.py`
- Read: `cmm/domains/validation_contracts.py`
- Read: `cmm/domains/loader.py`
- Read: `cmm/domains/registry.py`
- Read: `cmm/domains/resource_registry.py`
- Read: `cmm/domains/profile_registry.py`
- Read: `cmm/domains/operation_registry.py`
- Read: `cmm/domains/workflow_registry.py`
- Read: `cmm/domains/permission_registry.py`
- Read: current reasoning-rule registry used by hardened Domain Packs
- Read: `cmm/__main__.py`
- Read: `cmm/validation/cli.py`
- Read representative built-in packages: `cmm/domains/general/`, `cmm/domains/health/`, `cmm/domains/project/`
- Read relevant existing tests named below
- No production changes

**Interfaces:**
- Consumes: frozen Phase 10.35 spec plus actual current repository APIs.
- Produces: an exact reuse map for builders, discovery, validation request construction, isolated registries, test execution, packaging input, and CLI dispatch. No new abstraction is allowed until this map is complete.

- [ ] **Step 1: Verify immutable project state**

Run:

```bash
cd "/Users/chris/CMM OS"
set -euo pipefail

test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"
git merge-base --is-ancestor f19cb47 HEAD
test -z "$(git status --porcelain)"
git stash list | grep -Fq \
  "quarantine: post-audit phase 10.32 uncommitted changes"

git log -4 --oneline --decorate
git status --short --branch
```

Expected: design commit is an ancestor, worktree clean, quarantine stash present.

- [ ] **Step 2: Read the frozen spec and plan fully**

Run:

```bash
cat docs/superpowers/specs/2026-08-30-domain-sdk-design.md
cat docs/superpowers/plans/2026-08-30-domain-sdk-implementation-plan.md
```

Do not implement from memory.

- [ ] **Step 3: Record exact canonical construction/parsing APIs**

Run:

```bash
rg -n \
  'class DomainManifest|from_declarative_dict|to_dict|class JsonDomainManifestReader|read_document|class DomainPack|class ParsedDomainPack' \
  cmm/domains/manifest.py \
  cmm/domains/manifest_reader.py \
  cmm/domains/pack.py \
  tests/domains/test_domain_manifest.py \
  tests/domains/test_domain_manifest_reader.py \
  tests/domains/test_domain_pack.py \
  tests/domains/test_domain_pack_serialization.py
```

Record, before writing SDK code:

```text
MANIFEST_INPUT_SHAPE=
MANIFEST_SERIALIZATION_METHOD=
PACK_CONSTRUCTION_METHOD=
PACK_REQUIRED_COMPONENTS=
PACK_TEST_DECLARATION_SHAPE=
```

Use the repository-native values in all later tasks.

- [ ] **Step 4: Record exact discovery and validation APIs**

Run:

```bash
rg -n \
  'class DomainSource|class DomainCandidate|class FileSystemDomainDiscovery|def discover|class DomainValidationRequest|class DomainValidationResult|class PipelineDomainValidator|def validate' \
  cmm/domains/discovery_contracts.py \
  cmm/domains/discovery.py \
  cmm/domains/validation_contracts.py \
  cmm/domains/validation.py
```

Record:

```text
DISCOVERY_SOURCE_CONSTRUCTOR=
DISCOVERY_RESULT_CANDIDATE_ACCESS=
VALIDATION_REQUEST_FIELDS=
VALIDATION_PASS_STATUSES=
BLOCKING_FINDINGS_ACCESS=
```

The SDK facade must call these exact APIs.

- [ ] **Step 5: Record exact isolated registry/runtime construction**

Run:

```bash
rg -n \
  'class InMemory|class DomainPermissionRegistry|build_standard_general_domain_bootstrap|InMemoryReasoningRuleRegistry|snapshot|restore' \
  cmm/domains \
  cmm/cognitive \
  tests/domains \
  --glob '*.py'
```

At minimum map:

```text
domain registry
resource registry
profile registry
reasoning-rule registry
operation registry
workflow registry
permission registry
```

Prefer the smallest set actually required by the generated `basic_domain` pack. Do not instantiate unused subsystems merely to make the harness look comprehensive.

- [ ] **Step 6: Record exact CLI extension pattern**

Run:

```bash
sed -n '1,240p' cmm/__main__.py
sed -n '1,220p' cmm/validation/cli.py
rg -n \
  'build_parser|add_subparsers|add_parser|set_defaults|args.command|return .*main|validation.cli' \
  cmm/__main__.py \
  cmm/validation/cli.py \
  tests/test_cmm_cli.py \
  tests/test_cli.py \
  tests/validation
```

Decision:

```text
cmm.domains.sdk.cli
```

must expose parser registration/dispatch helpers compatible with the existing `argparse` style; `cmm/__main__.py` remains the root CLI entrypoint.

- [ ] **Step 7: Confirm template admission rule**

For each historical template:

```text
personal_domain
high_risk_domain
project_domain
read_only_domain
external_service_domain
multi_domain_extension
```

apply this exact rule:

```text
IF its meaningful behavioral difference can be represented solely by
existing canonical manifest/pack fields and generated declarative content,
without SDK runtime branching or a new runtime kind:
    it may be implemented as a thin scaffold preset.
ELSE:
    do not create a misleading alias; document it as intentionally deferred
    under the approved Phase 10.35 YAGNI rule.
```

`basic_domain` is always implemented.

- [ ] **Step 8: Verify Task 0 made no mutation**

Run:

```bash
git status --short
git diff --check
test -z "$(git status --porcelain)"
```

Expected: clean.

---

## Task 1: Public Builders and SDK Package Surface

**Files:**
- Create: `cmm/domains/sdk/__init__.py`
- Create: `cmm/domains/sdk/builders.py`
- Test: `tests/domains/test_domain_sdk_builders.py`
- Test: `tests/domains/test_domain_sdk_public_api.py`

**Interfaces:**
- Consumes: repository-native `DomainManifest`, manifest identifiers, `DomainDefinition`, and serialization methods discovered in Task 0.
- Produces:
  - `ManifestBuilder`
  - `DomainBuilder`
  - intentional public imports from `cmm.domains.sdk`
- Does not register, enable, load, execute, or mutate runtime state.

- [ ] **Step 1: Write failing public-import tests**

Start with:

```python
def test_sdk_exposes_only_intended_builder_surface() -> None:
    from cmm.domains.sdk import DomainBuilder, ManifestBuilder

    assert DomainBuilder is not None
    assert ManifestBuilder is not None
```

Also assert a fresh import has no registry/filesystem side effects by snapshotting the relevant canonical registry or importing in a subprocess following existing public-API test patterns.

- [ ] **Step 2: Run RED**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_sdk_builders.py \
  tests/domains/test_domain_sdk_public_api.py
```

Expected: collection/import failure because `cmm.domains.sdk` does not yet exist.

- [ ] **Step 3: Implement `ManifestBuilder` as a canonical-contract facade**

The public shape is:

```python
class ManifestBuilder:
    def __init__(
        self,
        *,
        slug: str,
        version: str = "0.1.0",
        name: str | None = None,
    ) -> None: ...

    def with_description(self, description: str) -> "ManifestBuilder": ...
    def with_metadata(self, **metadata: object) -> "ManifestBuilder": ...
    def build(self) -> DomainManifest: ...
    def to_dict(self) -> dict[str, object]: ...
```

Implementation rules:

- normalize no values beyond what the canonical contract already permits;
- construct through `DomainManifest.from_declarative_dict(...)` if Task 0 confirms that is the canonical declarative path;
- otherwise construct the canonical `DomainManifest` directly with exact repository fields;
- use canonical default/schema/version values already proven by manifest tests;
- `to_dict()` delegates to the canonical manifest serialization;
- no duplicate schema validator.

Add tests proving:

```python
manifest = ManifestBuilder(slug="example").build()
assert manifest.to_dict() == ManifestBuilder(slug="example").to_dict()
```

and invalid slugs/versions fail through canonical Domain exceptions/contracts.

- [ ] **Step 4: Implement minimal `DomainBuilder`**

Public shape:

```python
class DomainBuilder:
    def __init__(self, manifest: DomainManifest) -> None: ...

    def build(self) -> DomainDefinition: ...
```

Only include additional fluent component methods if Task 0 proves that the canonical `DomainDefinition`/`DomainPack` construction requires them for the minimal external pack. Do not create registry-like `register_*` storage inside the builder.

The builder may hold immutable/declarative construction input; it must not call `DomainRegistry.register()`.

- [ ] **Step 5: Prove builders are side-effect free**

Tests must verify:

- building does not write files;
- building does not mutate `DomainRegistry`;
- repeated equivalent builds serialize identically;
- malformed inputs fail canonically.

- [ ] **Step 6: Run focused GREEN and Ruff**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_sdk_builders.py \
  tests/domains/test_domain_sdk_public_api.py

.venv/bin/python -m ruff check \
  cmm/domains/sdk/__init__.py \
  cmm/domains/sdk/builders.py \
  tests/domains/test_domain_sdk_builders.py \
  tests/domains/test_domain_sdk_public_api.py
```

Use the repository's exact Ruff invocation if it differs.

- [ ] **Step 7: Commit coherent builder slice**

Run:

```bash
git diff --check
git status --short
git add \
  cmm/domains/sdk/__init__.py \
  cmm/domains/sdk/builders.py \
  tests/domains/test_domain_sdk_builders.py \
  tests/domains/test_domain_sdk_public_api.py
git diff --cached --check
git commit -m "feat(domains): add domain sdk builders"
```

---

## Task 2: Scaffold Engine, `basic_domain`, and `cmm domain create`

**Files:**
- Create: `cmm/domains/sdk/scaffold.py`
- Modify: `cmm/domains/sdk/__init__.py`
- Create/Modify: `cmm/domains/sdk/cli.py`
- Modify: `cmm/__main__.py`
- Test: `tests/domains/test_domain_sdk_scaffold.py`
- Test: `tests/domains/test_domain_sdk_cli.py`

**Interfaces:**
- Consumes: `ManifestBuilder`, canonical manifest serialization, root `argparse` integration.
- Produces:
  - `DomainScaffolder`
  - `DomainTemplate`/`TemplateSpec` only if a small immutable preset object materially improves clarity
  - `basic_domain`
  - `register_domain_cli(...)` or equivalent root-parser helper
  - `cmm domain create`

- [ ] **Step 1: Write RED scaffold tests**

Test exact behavior:

```python
def test_basic_domain_scaffold_creates_minimal_canonical_pack(tmp_path: Path) -> None:
    destination = tmp_path / "example"

    result = DomainScaffolder().create(
        name="example",
        destination=destination,
        template="basic_domain",
    )

    assert result == destination.resolve()
    assert (destination / "manifest.json").is_file()
    assert (destination / "README.md").is_file()
    assert (destination / "fixtures" / "sample.json").is_file()
    assert (destination / "tests" / "test_domain.py").is_file()
```

Then parse `manifest.json` using the real `JsonDomainManifestReader` or real discovery path, not `json.loads()` alone.

- [ ] **Step 2: Add path/overwrite RED cases**

Tests must reject:

```text
name="../escape"
name="/absolute"
destination already exists and is non-empty
template unknown
destination resolution escaping the requested parent through symlink/path traversal
```

No `force` mode is introduced in 10.35.

- [ ] **Step 3: Implement deterministic `basic_domain` scaffold**

Requirements:

- write UTF-8 with final newline;
- sort JSON keys or otherwise use repository-canonical deterministic JSON;
- no timestamps/random IDs in generated files;
- generated test imports only public SDK/runtime contracts;
- no empty placeholder directories;
- no `manifest.yaml`;
- no built-in registration edits;
- no shell commands embedded in manifest metadata.

The scaffold's generated test should be genuinely runnable and minimal, for example asserting canonical discovery/manifest identity rather than containing `pass`.

- [ ] **Step 4: Add root `domain` parser and `create` command**

`cmm/domains/sdk/cli.py` should expose a small registration/dispatch surface compatible with current `argparse`, conceptually:

```python
def register_domain_parser(subparsers: argparse._SubParsersAction) -> None: ...

def run_domain_command(args: argparse.Namespace) -> int: ...
```

Use a public annotation type if the repository avoids private `argparse` typing; follow Task 0 findings rather than forcing `_SubParsersAction`.

CLI contract:

```bash
.venv/bin/python -m cmm domain create example --path /tmp/example
```

If established CLI conventions prefer positional destination or `--destination`, follow them consistently and update tests/docs accordingly. Do not add a second CLI framework.

- [ ] **Step 5: Test CLI in-process and subprocess**

Subprocess test must use:

```python
subprocess.run(
    [sys.executable, "-m", "cmm", "domain", "create", ...],
    check=False,
    capture_output=True,
    text=True,
)
```

Assert:

- return code `0` on success;
- non-zero on invalid name/existing destination;
- generated `manifest.json` exists;
- no traceback for expected developer errors.

- [ ] **Step 6: Evaluate optional template presets**

Apply Task 0's admission rule.

For each admitted template, add a deterministic preset and a test that demonstrates a real canonical difference.

For each non-admitted template, add no fake alias.

Do not block completion if only `basic_domain` can be represented meaningfully under current canonical contracts.

- [ ] **Step 7: Run focused tests and Ruff**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_sdk_builders.py \
  tests/domains/test_domain_sdk_scaffold.py \
  tests/domains/test_domain_sdk_cli.py

.venv/bin/python -m ruff check \
  cmm/domains/sdk \
  cmm/__main__.py \
  tests/domains/test_domain_sdk_scaffold.py \
  tests/domains/test_domain_sdk_cli.py
```

- [ ] **Step 8: Commit create/scaffold slice**

```bash
git diff --check
git add \
  cmm/domains/sdk \
  cmm/__main__.py \
  tests/domains/test_domain_sdk_scaffold.py \
  tests/domains/test_domain_sdk_cli.py
git diff --cached --check
git commit -m "feat(domains): scaffold sdk domain packs"
```

---

## Task 3: Canonical Validation Facade and `cmm domain validate`

**Files:**
- Modify: `cmm/domains/sdk/cli.py`
- Create test coverage in: `tests/domains/test_domain_sdk_cli.py`
- Extend: `tests/domains/test_domain_sdk_scaffold.py`
- Do not create a new validator module unless a reusable facade is demonstrably needed by harness/packager; if needed, keep it private/small inside an existing SDK module rather than building a validation subsystem.

**Interfaces:**
- Consumes:
  - `FileSystemDomainDiscovery`
  - canonical `DomainSource`/`DomainCandidate`
  - `JsonDomainManifestReader`
  - canonical `DomainValidationRequest`
  - `PipelineDomainValidator`
- Produces:
  - one shared SDK helper that maps a filesystem pack root to canonical discovery + validation
  - `cmm domain validate <path>`

- [ ] **Step 1: Write RED validation tests**

Create a `basic_domain`, then assert:

```python
result = validate_domain_path(pack_root)
assert result.status is canonical_pass_or_warning_status
assert result.manifest_valid is True
assert result.compatibility_valid is True
assert result.security_valid is True
assert result.fragmentation_valid is True
```

Use exact status enum names discovered in Task 0.

- [ ] **Step 2: Prove invalid SDK pack fails canonically**

Tamper `manifest.json` in a way already rejected by `tests/domains/test_domain_manifest.py` or `test_domain_validation_manifest.py`.

Assert the SDK exposes the canonical failed/blocking result rather than accepting the pack.

- [ ] **Step 3: Implement one shared path-to-validation helper**

Flow:

```text
resolve pack root safely
→ construct canonical filesystem DomainSource
→ FileSystemDomainDiscovery.discover(...)
→ require exactly the intended candidate
→ canonical manifest/pack construction as required
→ DomainValidationRequest(...)
→ PipelineDomainValidator.validate(...)
→ return DomainValidationResult
```

No custom compatibility/security/fragmentation logic is permitted.

The helper must be reusable by:

```text
CLI validate
DomainTestHarness
DomainPackager
```

- [ ] **Step 4: Implement CLI output and exit status**

Human-readable output must include at minimum:

```text
domain id
version
status
blocking finding count
warning count
```

Exit code:

```text
0 = canonical validation has no blocking failure and status is accepted
non-zero = invalid path, discovery failure, validation failure/error
```

Do not silently downgrade canonical failures to warnings.

- [ ] **Step 5: Test no runtime mutation**

Snapshot an empty `DomainRegistry` or use a fresh registry and prove `cmm domain validate` does not register/enable the pack.

- [ ] **Step 6: Run canonical validation regressions**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_manifest.py \
  tests/domains/test_domain_manifest_reader.py \
  tests/domains/test_domain_discovery.py \
  tests/domains/test_domain_validation_contracts.py \
  tests/domains/test_domain_validation_manifest.py \
  tests/domains/test_domain_validation_compatibility.py \
  tests/domains/test_domain_validation_dependencies.py \
  tests/domains/test_domain_validation_security.py \
  tests/domains/test_domain_validation_fragmentation.py \
  tests/domains/test_domain_validation_service.py \
  tests/domains/test_domain_sdk_scaffold.py \
  tests/domains/test_domain_sdk_cli.py
```

- [ ] **Step 7: Commit validation slice**

```bash
git diff --check
git add cmm/domains/sdk tests/domains/test_domain_sdk_scaffold.py tests/domains/test_domain_sdk_cli.py
git diff --cached --check
git commit -m "feat(domains): validate sdk domain packs"
```

---

## Task 4: Fixture Loader and Isolated Domain Test Harness

**Files:**
- Create: `cmm/domains/sdk/fixtures.py`
- Create: `cmm/domains/sdk/harness.py`
- Modify: `cmm/domains/sdk/__init__.py`
- Test: `tests/domains/test_domain_sdk_fixtures.py`
- Test: `tests/domains/test_domain_sdk_harness.py`

**Interfaces:**
- Consumes:
  - shared path-to-validation helper from Task 3
  - canonical in-memory registries/stores discovered in Task 0
  - `DeclarativeDomainLoader` only if canonical runtime loading is required by the actual minimal pack
  - canonical rule/operation/workflow/permission components only when exercised
- Produces:
  - `DomainFixtureLoader`
  - `DomainTestHarness`
  - small immutable result contract only if necessary to report validation/test outcome

- [ ] **Step 1: Write fixture-loader RED tests**

Public shape:

```python
class DomainFixtureLoader:
    def load(self, pack_root: Path, fixture: str = "sample.json") -> object: ...
```

Tests:

- `fixtures/sample.json` loads deterministically;
- missing fixture yields a clear SDK/developer error;
- `../outside.json` is rejected;
- absolute path is rejected;
- symlink escape is rejected where applicable;
- malformed JSON fails without partial state;
- fixture content is returned as data only, never executed.

- [ ] **Step 2: Implement minimal fixture loader**

Use:

```python
Path.resolve()
json.load/json.loads
```

and an `_is_within`-equivalent local SDK path guard or a shared safe-path helper if one already exists publicly.

Do not import private loader internals solely for path checking.

- [ ] **Step 3: Write harness RED tests for isolation**

Public shape:

```python
class DomainTestHarness:
    def validate(self, pack_root: Path) -> DomainValidationResult: ...
    def load_fixture(
        self,
        pack_root: Path,
        fixture: str = "sample.json",
    ) -> object: ...
    def prepare(self, pack_root: Path) -> object: ...
```

`prepare()` may return an immutable harness context/result whose exact type is defined once Task 0 identifies the minimum canonical registries required.

Tests must prove:

- two harness instances do not share mutable registry state;
- preparing/testing a pack does not mutate production/global registries;
- invalid canonical validation blocks preparation;
- permission/rule/operation/workflow semantics are delegated to canonical components when present;
- no persisted session/fixture state grants authority by itself.

- [ ] **Step 4: Construct isolated canonical state**

Use repository-native in-memory implementations discovered in Task 0, such as the actual equivalents of:

```text
DomainRegistry
InMemoryDomainResourceRegistry
InMemoryDomainProfileRegistry
InMemoryReasoningRuleRegistry
InMemoryDomainOperationRegistry
InMemoryDomainWorkflowRegistry
DomainPermissionRegistry
```

Only instantiate registries required by actual pack components.

If the pack is purely declarative and loader registration alone is sufficient, keep the harness correspondingly small.

Do not create SDK registries.

- [ ] **Step 5: Add loader integration only when required**

If runtime preparation uses `DeclarativeDomainLoader`, construct it with:

```text
JsonDomainManifestReader
isolated DomainRegistry
candidate from canonical discovery
```

and assert loading registers but does not implicitly enable/authorize the domain.

If the generated pack does not need loading for its tests, do not add loader calls merely for ceremony.

- [ ] **Step 6: Prove canonical security invariants**

Add focused tests around any canonical operation/workflow/permission path the generated pack actually exercises.

No SDK-specific permission evaluator may appear.

- [ ] **Step 7: Run focused and registry regressions**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_sdk_fixtures.py \
  tests/domains/test_domain_sdk_harness.py \
  tests/domains/test_domain_registry.py \
  tests/domains/test_domain_registry_store.py \
  tests/domains/test_domain_loader.py \
  tests/domains/test_domain_resource_registry.py \
  tests/domains/test_domain_profile_registry.py \
  tests/domains/test_domain_operation_registry.py \
  tests/domains/test_domain_permission_registry.py
```

Include current workflow/rule registry tests located in Task 0.

- [ ] **Step 8: Commit harness slice**

```bash
git diff --check
git add \
  cmm/domains/sdk/__init__.py \
  cmm/domains/sdk/fixtures.py \
  cmm/domains/sdk/harness.py \
  tests/domains/test_domain_sdk_fixtures.py \
  tests/domains/test_domain_sdk_harness.py
git diff --cached --check
git commit -m "feat(domains): add isolated domain sdk harness"
```

---

## Task 5: Safe `cmm domain test`

**Files:**
- Modify: `cmm/domains/sdk/cli.py`
- Test: `tests/domains/test_domain_sdk_cli.py`
- Extend scaffold generated test template in: `cmm/domains/sdk/scaffold.py` if needed
- Extend: `tests/domains/test_domain_sdk_scaffold.py`

**Interfaces:**
- Consumes: `DomainTestHarness`, canonical validation result, Python interpreter path.
- Produces: `cmm domain test <path>`.

- [ ] **Step 1: Write RED command test**

Create a `basic_domain` in a temp directory and run:

```python
completed = subprocess.run(
    [
        sys.executable,
        "-m",
        "cmm",
        "domain",
        "test",
        str(pack_root),
    ],
    capture_output=True,
    text=True,
    check=False,
)
assert completed.returncode == 0
```

- [ ] **Step 2: Prove validation happens before pytest**

Tamper the manifest so canonical validation blocks it while its Python test itself would pass.

Assert `cmm domain test` returns non-zero without treating a passing pytest result as success.

- [ ] **Step 3: Implement safe test execution**

Required process invocation:

```python
subprocess.run(
    [sys.executable, "-m", "pytest", "-q", str(test_path)],
    cwd=str(pack_root),
    check=False,
)
```

Adjust arguments only to match existing repository test conventions.

Forbidden:

```python
shell=True
os.system(...)
subprocess.run("...user input...", shell=True)
```

Manifest fields must not supply arbitrary command fragments.

- [ ] **Step 4: Constrain test path**

The command may execute only the generated/pack-owned test directory selected by the SDK contract.

Resolve the test path and assert it remains within `pack_root`.

Do not execute arbitrary absolute test paths from manifest metadata.

- [ ] **Step 5: Add failure and injection tests**

Cover:

- pytest failure → non-zero;
- validation failure → non-zero;
- path with spaces → works;
- path containing shell metacharacters → treated as literal filesystem path, never shell syntax;
- no tests directory → clear non-zero developer error;
- expected errors do not print a Python traceback by default.

- [ ] **Step 6: Run focused tests**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_sdk_scaffold.py \
  tests/domains/test_domain_sdk_harness.py \
  tests/domains/test_domain_sdk_cli.py
```

- [ ] **Step 7: Commit test command slice**

```bash
git diff --check
git add \
  cmm/domains/sdk/cli.py \
  cmm/domains/sdk/scaffold.py \
  tests/domains/test_domain_sdk_scaffold.py \
  tests/domains/test_domain_sdk_cli.py
git diff --cached --check
git commit -m "feat(domains): test sdk domain packs"
```

---

## Task 6: Deterministic Domain Packager and `cmm domain pack`

**Files:**
- Create: `cmm/domains/sdk/packager.py`
- Modify: `cmm/domains/sdk/__init__.py`
- Modify: `cmm/domains/sdk/cli.py`
- Test: `tests/domains/test_domain_sdk_packager.py`
- Extend: `tests/domains/test_domain_sdk_cli.py`

**Interfaces:**
- Consumes: shared canonical validation helper.
- Produces:
  - `DomainPackager`
  - deterministic `.tar.gz`
  - `cmm domain pack <path>`

- [ ] **Step 1: Write RED packaging test**

Public shape:

```python
class DomainPackager:
    def pack(
        self,
        pack_root: Path,
        output: Path | None = None,
    ) -> Path: ...
```

Test:

```python
archive = DomainPackager().pack(pack_root)
assert archive.suffixes[-2:] == [".tar", ".gz"]
assert archive.is_file()
```

- [ ] **Step 2: Require canonical validation first**

Create an invalid pack and assert:

```python
with pytest.raises(...):
    DomainPackager().pack(pack_root)
assert not output.exists()
```

Use the narrowest existing/SDK error appropriate to validation-blocked packaging.

- [ ] **Step 3: Implement deterministic archive collection**

Archive input rules:

- pack root is resolved once;
- recursively sort source paths lexicographically by normalized relative POSIX path;
- reject members whose resolved source escapes root;
- skip directories/files matching the explicit transient policy;
- never follow an escaping symlink;
- archive names are relative and never absolute;
- no `..` archive member names.

Minimum excluded names:

```text
__pycache__/
.pytest_cache/
.DS_Store
.venv/
venv/
*.pyc
```

Do not invent a broad secret-ignore mechanism; canonical security validation remains authoritative.

- [ ] **Step 4: Normalize archive metadata**

For deterministic output, normalize tar metadata:

```text
uid = 0
gid = 0
uname = ""
gname = ""
mtime = 0
```

Use stable permission modes derived conservatively from file type or a fixed safe file/dir mode if repository expectations permit it.

Write gzip with deterministic timestamp:

```python
gzip.GzipFile(..., mtime=0)
```

or an equivalent standard-library path proven deterministic by a test.

- [ ] **Step 5: Add byte-for-byte determinism test**

Package unchanged source twice to different output paths and assert:

```python
assert first.read_bytes() == second.read_bytes()
```

- [ ] **Step 6: Add unpack/revalidate test**

Extract with a safe test-only extraction helper that rejects traversal, then run canonical SDK validation on the unpacked root.

Do not use unsafe `extractall()` without validating members.

- [ ] **Step 7: Add CLI command**

Example:

```bash
.venv/bin/python -m cmm domain pack ./example --output /tmp/example.tar.gz
```

Assert non-zero on invalid pack/output path and `0` on success.

Packing must not install/register/enable/publish anything.

- [ ] **Step 8: Run focused and security regressions**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_sdk_packager.py \
  tests/domains/test_domain_sdk_cli.py \
  tests/domains/test_domain_validation_security.py \
  tests/domains/test_domain_validation_fragmentation.py
```

- [ ] **Step 9: Commit packager slice**

```bash
git diff --check
git add \
  cmm/domains/sdk/__init__.py \
  cmm/domains/sdk/packager.py \
  cmm/domains/sdk/cli.py \
  tests/domains/test_domain_sdk_packager.py \
  tests/domains/test_domain_sdk_cli.py
git diff --cached --check
git commit -m "feat(domains): package sdk domain packs"
```

---

## Task 7: DP-035 External Pack Acceptance and Architecture Regressions

**Files:**
- Create: `tests/domains/test_domain_sdk_dp035_acceptance.py`
- Extend: `tests/domains/test_domain_sdk_public_api.py`
- Modify existing architecture/public API tests only if required by established conventions

**Interfaces:**
- Consumes: complete create → validate → test → pack SDK.
- Produces: acceptance evidence that a new external Domain Pack works without domain-specific core modification.

- [ ] **Step 1: Write full acceptance flow**

One acceptance test module must perform:

```text
1. scaffold external `example`
2. assert no `cmm/domains/example` exists
3. canonically discover/parse it
4. canonically validate it
5. prepare isolated harness state
6. run its SDK-owned tests
7. package it
8. safely unpack into a fresh directory
9. rediscover/reparse it
10. canonically revalidate it
```

Use temporary directories only.

- [ ] **Step 2: Prove no hard-coded core registration**

Capture relevant central files before the flow or statically assert the example slug is absent from:

```text
cmm/domains/registry.py
cmm/domains/resolver.py
cmm/domains/permission_*.py
cmm/domains/workflow_*.py
cmm/domains/operation_*.py
```

The acceptance test should focus on behavioral proof; avoid brittle whole-repo string scans if a more precise invariant is available.

- [ ] **Step 3: Add fresh-import/no-side-effect regression**

Follow existing hardened-domain public API test style.

Importing:

```python
import cmm.domains.sdk
```

must not:

- write files;
- mutate DomainRegistry;
- register operations/workflows/resources/profiles;
- emit runtime events.

- [ ] **Step 4: Lock event/session/conflict invariants**

Run or add minimal assertions using existing tests rather than duplicating them:

```text
GENERAL_EVENT_COUNT=23
GENERAL_EVENT_UNIQUE_COUNT=23
no domain.session.resumed
DomainConflictResolver purity
Domain Sessions revalidation behavior
```

Do not create SDK-specific audit wrappers around these invariants.

- [ ] **Step 5: Run acceptance + relevant Phase 10 regressions**

At minimum:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_sdk_*.py \
  tests/domains/test_domain_discovery.py \
  tests/domains/test_domain_loader.py \
  tests/domains/test_domain_manifest.py \
  tests/domains/test_domain_manifest_reader.py \
  tests/domains/test_domain_pack.py \
  tests/domains/test_domain_pack_serialization.py \
  tests/domains/test_domain_registry.py \
  tests/domains/test_domain_validation_*.py \
  tests/domains/test_domain_event_catalog.py \
  tests/domains/test_domain_session_*.py \
  tests/domains/test_domain_conflict_resolution.py \
  tests/domains/test_domain_conflict_resolution_adversarial.py
```

If shell glob expansion produces too many irrelevant audit-version files, enumerate current canonical test modules intentionally.

- [ ] **Step 6: Commit acceptance slice**

```bash
git diff --check
git add \
  tests/domains/test_domain_sdk_dp035_acceptance.py \
  tests/domains/test_domain_sdk_public_api.py
git diff --cached --check
git commit -m "test(domains): prove phase 10.35 sdk acceptance"
```

---

## Task 8: Reference Documentation and Roadmap State

**Files:**
- Create: `docs/reference/domain-sdk.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Modify: `ROADMAP.md` only if current roadmap convention requires it

**Interfaces:**
- Consumes: implemented public API and actual verified CLI.
- Produces: concise operational Domain SDK reference and Phase 10.35 implementation-status documentation.
- Must not claim independent audit or closure.

- [ ] **Step 1: Write `docs/reference/domain-sdk.md` from actual behavior**

Required sections:

```text
Purpose
Architecture / canonical reuse
manifest.json format
Python public imports
basic_domain scaffold
cmm domain create
cmm domain validate
cmm domain test
cmm domain pack
fixture handling
test harness isolation
packaging/exclusions/determinism
security/path rules
10.35 vs 10.36 boundary
external pack example
```

Commands must be copied from passing CLI tests.

- [ ] **Step 2: Reconcile historical `manifest.yaml` wording**

Update Phase 10.35 roadmap text so it does not falsely present YAML as implemented canonical format.

Use wording equivalent to:

```text
The earlier manifest.yaml tree was conceptual. The implemented Domain SDK
uses manifest.json, matching FileSystemDomainDiscovery and
JsonDomainManifestReader.
```

Do not rewrite unrelated Phase 10 roadmap sections.

- [ ] **Step 3: Record Phase 10.35 implementation state conservatively**

Before independent audit, use only:

```text
implementation complete — independent audit pending
```

Do not write:

```text
independently audited
closed
PASS
```

- [ ] **Step 4: Update requirements matrix using existing convention**

If current matrix uses `DP-035`/`AT-DP-035`, add/update exactly that convention.

If the matrix uses a different canonical row naming, follow it.

Do not create a new evidence schema.

- [ ] **Step 5: Check documentation for false capabilities**

Run:

```bash
rg -n \
  'manifest\.yaml|domain install|domain uninstall|domain enable|domain disable|domain publish|Domain API|independently audited|closed' \
  docs/reference/domain-sdk.md \
  docs/roadmap/phase-10-domain-intelligence.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  ROADMAP.md
```

Every hit must be either:

- explicit historical/out-of-scope explanation; or
- a truthful current status.

- [ ] **Step 6: Commit docs**

```bash
git diff --check
git add \
  docs/reference/domain-sdk.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md

if ! git diff --quiet -- ROADMAP.md; then
  git add ROADMAP.md
fi

git diff --cached --check
git commit -m "docs(domains): document phase 10.35 domain sdk"
```

---

## Task 9: Full Verification and Implementation Candidate

**Files:**
- No new architecture.
- Fix only genuine defects found by verification.
- If fixes change production behavior, use RED-before-fix whenever reproducible.

**Interfaces:**
- Consumes: complete Phase 10.35 implementation.
- Produces: committed implementation candidate ready for independent-audit bundle generation.

- [ ] **Step 1: Inspect implementation diff/history**

Run:

```bash
git status --short --branch
git log --oneline --decorate f19cb47..HEAD
git diff --check
```

Ensure no unrelated subsystem refactor entered the phase.

- [ ] **Step 2: Placeholder and forbidden-architecture scan**

Run:

```bash
rg -n \
  'TODO|FIXME|TBD|PLACEHOLDER|NotImplemented|raise NotImplementedError' \
  cmm/domains/sdk \
  tests/domains/test_domain_sdk_*.py \
  docs/reference/domain-sdk.md \
  || true

rg -n \
  'class .*Registry|class .*Resolver|class .*WorkflowEngine|class .*Permission.*Engine|manifest\.ya?ml|shell=True|os\.system' \
  cmm/domains/sdk \
  || true
```

Interpret intentionally; any runtime subsystem duplication is a blocker.

- [ ] **Step 3: Run focused Phase 10.35 suite**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_sdk_*.py
```

All green.

- [ ] **Step 4: Run canonical substrate regressions**

Run current equivalents of:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_manifest.py \
  tests/domains/test_domain_manifest_reader.py \
  tests/domains/test_domain_pack.py \
  tests/domains/test_domain_pack_serialization.py \
  tests/domains/test_domain_discovery.py \
  tests/domains/test_domain_discovery_contracts.py \
  tests/domains/test_domain_loader.py \
  tests/domains/test_domain_loader_contracts.py \
  tests/domains/test_domain_registry.py \
  tests/domains/test_domain_registry_store.py \
  tests/domains/test_domain_validation_contracts.py \
  tests/domains/test_domain_validation_manifest.py \
  tests/domains/test_domain_validation_compatibility.py \
  tests/domains/test_domain_validation_dependencies.py \
  tests/domains/test_domain_validation_security.py \
  tests/domains/test_domain_validation_fragmentation.py \
  tests/domains/test_domain_validation_service.py
```

- [ ] **Step 5: Run event/session/conflict regression gate**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_domain_event_catalog.py \
  tests/domains/test_domain_events_dp033_acceptance.py \
  tests/domains/test_domain_session_acceptance.py \
  tests/domains/test_domain_session_adversarial.py \
  tests/domains/test_domain_session_events.py \
  tests/domains/test_domain_session_permissions.py \
  tests/domains/test_domain_session_revalidation.py \
  tests/domains/test_domain_session_resumer.py \
  tests/domains/test_domain_conflict_resolution.py \
  tests/domains/test_domain_conflict_resolution_adversarial.py \
  tests/domains/test_domain_conflict_resolution_dp032_acceptance.py
```

Verify explicitly:

```text
GENERAL_EVENT_COUNT=23
GENERAL_EVENT_UNIQUE_COUNT=23
domain.session.resumed absent
```

- [ ] **Step 6: Run complete Domain suite**

```bash
.venv/bin/python -m pytest -q tests/domains
```

All green.

- [ ] **Step 7: Run full repository suite**

```bash
.venv/bin/python -m pytest -q
```

All green. If the suite must be partitioned because of environment limits, record every partition and prove full coverage; do not claim a full-suite PASS from an interrupted run.

- [ ] **Step 8: Run lint/format/compile checks**

Discover current workflow commands first:

```bash
rg -n 'ruff|compileall|format' pyproject.toml .github scripts Makefile 2>/dev/null || true
```

Then run repository-native equivalents, at minimum:

```bash
.venv/bin/python -m ruff check cmm/domains/sdk cmm/__main__.py tests/domains/test_domain_sdk_*.py
.venv/bin/python -m compileall -q cmm/domains/sdk
git diff --check
```

If Ruff format checking is part of current policy, run it on changed Python.

- [ ] **Step 9: Verify worktree and quarantine stash**

```bash
git status --short --branch
git stash list | sed -n '1,3p'
git stash list | grep -Fq \
  "quarantine: post-audit phase 10.32 uncommitted changes"
```

If verification required fixes, commit them coherently before continuing and rerun affected gates.

Expected before Task 10:

```text
worktree clean
implementation/docs committed
quarantine stash preserved
PUSH=NO
MERGE=NO
```

---

## Task 10: Build Exact-HEAD Independent Audit Bundle

**Files:**
- No repository source changes.
- Output only under:
  `$HOME/Library/Mobile Documents/com~apple~CloudDocs/Downloads/`

**Interfaces:**
- Consumes: clean, fully verified, committed Phase 10.35 implementation HEAD.
- Produces: versioned `phase-10.35-audit-vN.tar.gz` generated solely from exact Git HEAD with `git archive`.
- Does not perform the independent audit.

- [ ] **Step 1: Precheck audit eligibility**

Run:

```bash
cd "/Users/chris/CMM OS"
set -euo pipefail

test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"
git merge-base --is-ancestor f19cb47 HEAD
test -z "$(git status --porcelain)"
git stash list | grep -Fq \
  "quarantine: post-audit phase 10.32 uncommitted changes"

AUDIT_HEAD="$(git rev-parse HEAD)"
echo "AUDIT_HEAD=$AUDIT_HEAD"
```

- [ ] **Step 2: Select next free bundle version**

```bash
OUT_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Downloads"
N=1
while [ -e "$OUT_DIR/phase-10.35-audit-v${N}.tar.gz" ]; do
    N=$((N + 1))
done
AUDIT_BUNDLE="$OUT_DIR/phase-10.35-audit-v${N}.tar.gz"
```

Never overwrite an older audit bundle.

- [ ] **Step 3: Generate bundle from exact committed HEAD**

```bash
SHORT_HEAD="$(git rev-parse --short=12 "$AUDIT_HEAD")"
ARCHIVE_PREFIX="CMM-OS-phase-10.35-${SHORT_HEAD}/"

mkdir -p "$OUT_DIR"

git archive \
    --format=tar \
    --prefix="$ARCHIVE_PREFIX" \
    "$AUDIT_HEAD" \
    | gzip -n > "$AUDIT_BUNDLE"
```

The worktree is not an archive source.

- [ ] **Step 4: Verify bundle**

```bash
test -s "$AUDIT_BUNDLE"
gzip -t "$AUDIT_BUNDLE"

AUDIT_BUNDLE_SHA256="$(
  shasum -a 256 "$AUDIT_BUNDLE" | awk '{print $1}'
)"

echo "AUDIT_BUNDLE=$AUDIT_BUNDLE"
echo "AUDIT_BUNDLE_SHA256=$AUDIT_BUNDLE_SHA256"
echo "AUDIT_SOURCE_HEAD=$AUDIT_HEAD"

tar -tzf "$AUDIT_BUNDLE" | sed -n '1,60p'
```

- [ ] **Step 5: Freeze audited source**

After bundle generation, do not commit or modify repository files before handing the bundle to ChatGPT.

If any implementation correction is made later:

```text
new source commit
→ old bundle becomes stale
→ generate next phase-10.35-audit-vN.tar.gz
```

- [ ] **Step 6: Report implementation state, not closure**

Return:

```text
PHASE10_35_DOMAIN_SDK_IMPLEMENTATION
DESIGN_COMMIT=f19cb47
PLAN_COMMIT=<exact plan commit from history>
IMPLEMENTATION_HEAD=<exact audited HEAD>
PUBLIC_SDK=PASS
CLI_CREATE=PASS
CLI_VALIDATE=PASS
CLI_TEST=PASS
CLI_PACK=PASS
DOMAIN_TEST_HARNESS=PASS
DOMAIN_FIXTURES=PASS
DOMAIN_PACKAGER=PASS
BASIC_DOMAIN_TEMPLATE=PASS
ADDITIONAL_TEMPLATES=<implemented names or intentionally deferred under admission rule>
DP_035_ACCEPTANCE=PASS
DOMAIN_EVENTS=23/23
DOMAIN_SESSION_REGRESSIONS=PASS
DOMAIN_CONFLICT_RESOLVER_PURITY=PASS
FOCUSED_TESTS=<fresh count>
DOMAIN_REGRESSIONS=<fresh count>
FULL_SUITE=<fresh count>
LINT=PASS
FORMAT=<PASS or repository policy N/A>
COMPILEALL=PASS
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
PUSH=NO
MERGE=NO
AUDIT_SOURCE_HEAD=<exact HEAD>
AUDIT_BUNDLE=<absolute iCloud Downloads path>
AUDIT_BUNDLE_SHA256=<sha256>
PHASE10_35_IMPLEMENTATION=COMPLETE
INDEPENDENT_AUDIT=PENDING
PHASE10_35_CLOSED=NO
NEXT=INDEPENDENT_CHATGPT_AUDIT
```

Also include:

```bash
git log -6 --oneline --decorate
git status --short --branch
git stash list | sed -n '1,3p'
```

Stop there.

Do not start Phase 10.36.

---

## Self-Review

### Spec coverage

- Task 0 binds implementation to the exact live canonical APIs and prevents guessed parallel infrastructure.
- Task 1 covers public SDK builders and side-effect-free construction.
- Task 2 covers `basic_domain`, scaffolding, path safety, template admission, and `cmm domain create`.
- Task 3 covers canonical discovery/validation reuse and `cmm domain validate`.
- Task 4 covers fixture loading and isolated canonical test state.
- Task 5 covers safe test execution and `cmm domain test`.
- Task 6 covers validate-before-package, deterministic transport archives, archive safety, and `cmm domain pack`.
- Task 7 proves the external-pack lifecycle and inherited event/session/conflict invariants.
- Task 8 covers the public reference, `manifest.json` reconciliation, matrix/roadmap state, and the 10.35/10.36 boundary.
- Task 9 provides focused, substrate, inherited Phase 10, full-domain, global, lint, compile, and Git hygiene gates.
- Task 10 creates the required exact-HEAD `git archive` audit bundle and stops before independent audit.

### Placeholder scan

This plan intentionally contains no `TBD`, `TODO`, “implement later”, fake method body, or unspecified mandatory behavior.

The only conditional behavior is the approved template-admission rule: advanced historical template names are added only when the current canonical contract can express a meaningful difference without new runtime semantics. That rule is deterministic and prevents misleading aliases.

### Type and dependency consistency

The plan consistently uses these new public SDK names:

```text
ManifestBuilder
DomainBuilder
DomainScaffolder
DomainFixtureLoader
DomainTestHarness
DomainPackager
```

and relies on repository-native exact types discovered in Task 0 for:

```text
DomainManifest
DomainDefinition
DomainSource
DomainCandidate
DomainValidationRequest
DomainValidationResult
PipelineDomainValidator
FileSystemDomainDiscovery
JsonDomainManifestReader
DeclarativeDomainLoader
canonical in-memory registries
```

No later task requires a second SDK registry, resolver, compatibility checker, validation engine, workflow engine, permission engine, or runtime.

### Scope check

Phase 10.35 remains one coherent developer-tooling subsystem centered on:

```text
create → validate → test → pack
```

Installation lifecycle, enable/disable/reload, operational domain queries, remote publication, marketplace behavior, HTTP API, and broader Domain API work remain Phase 10.36 or later.

### Baseline correctness

The plan does not incorrectly require implementation to start from design commit `f19cb47`.

Instead:

```text
f19cb47 = frozen design ancestor
future plan commit = implementation starting HEAD
```

The implementation-agent prompt created after this plan is committed will bind the exact plan commit SHA.

### Audit boundary

The implementation agent may generate the exact-HEAD audit TAR.GZ only after all implementation-side gates pass.

It must not:

```text
perform independent audit
commit an independent audit report
declare Phase 10.35 closed
push
merge
start Phase 10.36
```

Independent audit remains a separate ChatGPT step.
