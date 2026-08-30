# CMM OS Domain SDK Reference (Phase 10.35)

## 1. Overview

The **Domain SDK** (`cmm.domains.sdk`) provides developer ergonomics and command-line tooling for creating, validating, testing, and packaging CMM OS Domain Packs.

The Domain SDK is strictly a **public facade** over canonical CMM OS Domain subsystems. It does not introduce parallel runtime state, parallel registries, alternate manifest formats, or side-channel lifecycle events.

---

## 2. Core Architecture and Invariants

1. **Pure Facade Over Canonical Subsystems**:
   - Manifest creation uses `DomainManifest` contracts (`manifest.json` only; YAML is strictly prohibited).
   - Validation directly delegates to `PipelineDomainValidator` (`cmm.domains.validation`).
   - Packaging bundles packs into deterministic `.tar.gz` archives with normalized POSIX member paths, stable permissions (`0o755`/`0o644`), zero timestamps, and zero UIDs/GIDs.
   - Test harness isolates in-memory canonical registries (`DomainRegistry`, `InMemoryDomainResourceRegistry`, `InMemoryDomainProfileRegistry`, `InMemoryReasoningRuleRegistry`, `InMemoryDomainOperationRegistry`, `InMemoryDomainWorkflowRegistry`, `DomainPermissionRegistry`).
2. **Deterministic & Side-Effect Free**:
   - Running validation, fixture loading, test execution, or packaging never mutates the global `DomainRegistry`, runtime sessions, or event bus.
3. **Preserved Invariants**:
   - Domain events remain exactly 23 canonical event types.
   - Domain Sessions invariant: snapshot state remains decoupled from active authority.
   - Domain Conflict Resolver remains pure without side effects.

---

## 3. Programmatic API

### 3.1 `ManifestBuilder` and `DomainBuilder`

Fluent builders for constructing canonical manifests and domain definitions:

```python
from cmm.domains.sdk import ManifestBuilder, DomainBuilder

# Construct a canonical DomainManifest
manifest = (
    ManifestBuilder(slug="custom-pack", version="1.0.0", name="Custom Pack")
    .with_description("A custom domain pack for CMM OS")
    .with_metadata(author="Developer", tier="enterprise")
    .build()
)

# Construct a canonical DomainDefinition
domain_def = (
    DomainBuilder(manifest)
    .with_display_name("Custom Pack Display")
    .with_description("Domain definition description")
    .build()
)
```

### 3.2 `DomainScaffolder`

Generates standard domain pack directory trees:

```python
from cmm.domains.sdk import DomainScaffolder

scaffolder = DomainScaffolder()
pack_root = scaffolder.create("analytics-pack", destination="/path/to/target")
```

Generated directory layout:
```text
analytics-pack/
├── manifest.json
├── README.md
├── fixtures/
│   └── sample.json
└── tests/
    └── test_domain.py
```

### 3.3 `DomainFixtureLoader`

Safely loads test JSON fixtures with strict path traversal prevention:

```python
from cmm.domains.sdk import DomainFixtureLoader

loader = DomainFixtureLoader()
data = loader.load("/path/to/analytics-pack", "sample.json")
```

### 3.4 `DomainTestHarness`

Provides an isolated runtime context for pack testing without global side effects:

```python
from cmm.domains.sdk import DomainTestHarness

harness = DomainTestHarness()

# 1. Canonical validation
result = harness.validate("/path/to/analytics-pack")
assert result.manifest_valid is True

# 2. Safe fixture loading
data = harness.load_fixture("/path/to/analytics-pack", "sample.json")

# 3. Isolated context preparation
ctx = harness.prepare("/path/to/analytics-pack")
# ctx provides isolated domain_registry, resource_registry, profile_registry,
# rule_registry, operation_registry, workflow_registry, permission_registry
```

### 3.5 `DomainPackager`

Creates deterministic, byte-for-byte reproducible `.tar.gz` archives:

```python
from cmm.domains.sdk import DomainPackager

packager = DomainPackager()
archive_path = packager.pack(
    "/path/to/analytics-pack",
    output="/path/to/analytics-pack-1.0.0.tar.gz",
)
```

---

## 4. CLI Tooling

The CMM CLI integrates domain management subcommands via `cmm domain`:

### 4.1 `cmm domain create`

```bash
cmm domain create <slug> [--destination <dest_path>] [--template basic_domain]
```

Scaffolds a new domain pack with a valid `manifest.json`, `README.md`, sample fixture, and test file.

### 4.2 `cmm domain validate`

```bash
cmm domain validate <path>
```

Executes canonical `PipelineDomainValidator` against the specified domain pack directory. Returns exit code `0` on success, `1` on failure.

### 4.3 `cmm domain test`

```bash
cmm domain test <path>
```

Validates the domain pack and executes pytest within the pack's `tests/` directory safely without shell execution.

### 4.4 `cmm domain pack`

```bash
cmm domain pack <path> [--output <archive_path>]
```

Validates and packages the domain pack into a deterministic `.tar.gz` archive, automatically excluding transient files (`__pycache__`, `.pytest_cache`, `.DS_Store`, `.pyc`, `.venv`, `.git`).
