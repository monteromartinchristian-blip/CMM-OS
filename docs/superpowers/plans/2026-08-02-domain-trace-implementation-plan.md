# Phase 10.17 — Domain Trace Implementation Plan

> **For agentic workers:** execute the steps with a failing focused test before
> every production-code correction.  Do not commit: the approved task forbids
> commits and pushes.

**Goal:** Deliver a reference-only, deterministic Domain Trace with typed
inventory validation and public documentation.

**Architecture:** Contracts remain in `cmm.domains`; the assembler is a pure
canonical constructor and the validator compares traces to an external typed
inventory.  All upstream values are represented only by IDs, preserving the
`agent_runtime` → `domains` absence of dependencies.

**Tech Stack:** Python 3.10, frozen dataclasses, `pytest`, Ruff.

---

### Task 1: Contract boundary

**Files:** `cmm/domains/trace_contracts.py`, `cmm/domains/errors.py`,
`tests/domains/test_domain_trace_contracts.py`

- [x] Add failing tests for final/frozen reference-only contracts, deterministic
  contributions, typed global references, strict metadata, round trips, and
  canonical digest/ID.
- [x] Run the focused contract tests and observe the missing/obsolete-contract
  failures.
- [x] Replace obsolete objective/transfer contracts with request/goal references,
  contribution/reference containers, pairing records, and inventory.
- [x] Re-run contract tests until green.

### Task 2: Pure assembly

**Files:** `cmm/domains/trace_assembler.py`,
`tests/domains/test_domain_trace_assembler.py`

- [x] Add failing tests for deterministic ordering, derived duration, generated
  digest/ID, duplicate rejection, and unchanged results under mapping reorder.
- [x] Run the new assembler tests and observe failure.
- [x] Implement canonical normalization and construction without I/O or upstream
  object copying.
- [x] Re-run assembler and contract tests until green.

### Task 3: Inventory validation and privacy

**Files:** `cmm/domains/trace_validation.py`,
`tests/domains/test_domain_trace_validation.py`,
`tests/domains/test_domain_trace_privacy.py`

- [x] Add failing tests for category/domain mismatch, missing/unexpected/duplicate
  IDs, cross-domain and DomainResult pairings, altered ID/digest, invalid time,
  and recursive private metadata.
- [x] Run the validation/privacy tests and observe the expected failures.
- [x] Implement validator comparison against `DomainTraceReferenceInventory` and
  bounded recursive privacy checks.
- [x] Re-run validation/privacy tests until green.

### Task 4: Public surface and documentation

**Files:** `cmm/domains/__init__.py`, `tests/domains/test_domain_trace_public_api.py`,
`tests/domains/test_domain_public_api.py`, `docs/reference/domain-trace.md`,
`docs/roadmap/phase-10-domain-intelligence.md`, `ROADMAP.md`

- [x] Add failing public API and dependency-direction assertions.
- [x] Export only the agreed Phase 10.17 contracts and implementations.
- [x] Document boundary, reference categories, validation, and non-goals; mark
  10.17 complete and 10.18 next only after the complete test suite is green.
- [x] Run focal, domains, global, lint, compile, search, and diff validation.

### Task 5: Staging audit

**Files:** only Phase 10.17 implementation, tests, and documentation.

- [x] Preserve existing valid staged/unstaged work while staging only 10.17.
- [x] Confirm the two backup patches remain untracked and unstaged.
- [x] Run `git diff --cached --check` and report the staged inventory without
  creating a commit or push.

### Audit correction: authoritative inventory

- [x] Carry domains from resolution and composition in the inventory and reject
  a trace that is internally coherent but upstream-incompatible.
- [x] Reject reference-ID collisions, require exact DomainResult coverage, and
  preserve upstream cross-domain trace IDs.
- [x] Add `PARTIAL`/`CANCELLED`, fail-closed mutation handling, deterministic
  inventory serialization/digest, and detailed validation evidence.

### Audit v2 focal correction

- [x] Normalize DomainResult pairings in both request and final trace; prove
  reversed inputs produce identical ID/digest.
- [x] Sanitize corrupt diagnostic values and guarantee fail-closed validation
  for simultaneous ID/domain/kind mutations.
- [x] Resolve upstream trace IDs through the explicit `CROSS_DOMAIN_TRACE`
  category and verify both sides of each pairing.
- [x] Parse serialized mapping inputs with `DomainTraceAssemblyRequest.from_dict`.
- [x] Reject sensitive key-token variants while preserving allowed audit and
  reference-ID names.
- [x] Bind authoritative domain selections to their resolution/composition
  `source_id` and reject mismatches.
- [x] Reject contradictory `DomainTraceValidationResult` states.
- [x] Re-run focal, domains and global validation, then generate the v3 audit
  archive without AppleDouble/xattrs.

### Audit v3 focal correction

- [x] Reproduce before production changes: 19 focal failures with 70 passing;
  separately reproduce the heterogeneous-key `TypeError` and missing-pairing
  `KeyError`.
- [x] Tokenize private key families across separators, camelCase and PascalCase
  while preserving the four approved reference-ID keys.
- [x] Revalidate the complete final trace/inventory structure in isolated
  fail-closed blocks and reject injected fields without exposing their values.
- [x] Share deterministic participant invariants across request, final trace and
  assembler; canonicalize all semantically unordered final collections.
- [x] Require both cross-domain pairing IDs and reject legacy incomplete mappings
  with a closed serialization error.
- [x] Reject non-string/unknown mapping keys without heterogeneous sorting or
  payload-value disclosure.
- [x] Run the prescribed focal, domains, global, lint, compile, dependency,
  search and diff checks; stage only 10.17 and generate the clean v4 archive.
