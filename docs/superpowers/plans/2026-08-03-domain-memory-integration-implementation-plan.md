# Domain Memory Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:test-driven-development` for every behavioral change,
> `superpowers:systematic-debugging` for failures, and
> `superpowers:verification-before-completion` before claiming completion.
> Work task-by-task. Do not commit or push; the human performs an independent
> staged-diff audit first.

**Goal:** Build deterministic, permission-aware, reference-only domain views
over shared memory and reference-only bindings to existing memory-update
proposals.

**Architecture:** Add three focused modules under `cmm.domains`: immutable
contracts, a pure view resolver, and a pure fail-closed validator. Reuse the
canonical Cognitive Layer and Agent Runtime models by ID; never duplicate
their payloads or persistence.

**Tech Stack:** Python 3.10+, frozen dataclasses, enums, canonical JSON/hashing
patterns already used in `cmm.domains`, pytest, Ruff.

## Global Constraints

- Work only on `feature/phase-10-domain-intelligence`.
- Expected starting commit: `124621c`.
- Start from a clean working tree.
- No new memory store, graph, claim, provenance, temporal engine or package.
- No inline claims, resources, messages, prompts, reasoning, secrets or PII.
- The resolver and validator are pure; no store, network or adapter access.
- Read/propose/approve/apply/invalidate/delete remain distinct.
- Existing `MemoryUpdateProposal` and `AgentKnowledgeUpdateProposal` remain
  authoritative.
- Preserve Python 3.10 compatibility.
- Do not commit, push, reset, restore, clean or delete user files.

---

## File map

### Create

- `cmm/domains/memory_contracts.py` — enums, immutable contracts,
  serialization, canonicalization, IDs/digests and privacy guards.
- `cmm/domains/memory_view.py` — pure `DomainMemoryViewResolver` protocol and
  default implementation.
- `cmm/domains/memory_validation.py` — pure integration validator and
  fail-closed diagnostics.
- Seven focused test modules named in the approved design.
- Reference, design and implementation-plan documentation.

### Modify

- `cmm/domains/errors.py` — domain-memory error hierarchy.
- `cmm/domains/__init__.py` — intended public exports only.
- `tests/domains/test_domain_public_api.py` — package-level API coverage.
- Phase 10 roadmap/reference files — mark 10.18 implemented and document the
  final contract without changing later phases.

---

### Task 1: Preflight and canonical reuse map

**Files:**
- Read: `ROADMAP.md`
- Read: `docs/reference/domain-intelligence-requirements-matrix.md`
- Read: `docs/roadmap/phase-8-cognitive-layer.md`
- Read: `docs/roadmap/phase-9-autonomous-agent-runtime.md`
- Read: `docs/roadmap/phase-10-domain-intelligence.md`
- Read: `docs/reference/domain-trace.md`
- Read: canonical implementation modules found by symbol search.

**Interfaces:**
- Consumes: existing cognitive, runtime, permission, approval and trace types.
- Produces: an exact import/reuse map used by every later task.

- [ ] **Step 1: Verify repository state**

```bash
git branch --show-current
git log -1 --oneline --decorate
git status --short
```

Expected branch: `feature/phase-10-domain-intelligence`.
Expected HEAD: `124621c`.
Expected status: empty.

- [ ] **Step 2: Locate actual canonical symbols**

```bash
rg -n "class (KnowledgeItem|KnowledgeRelation|Evidence|Resource|TemporalScope|KnowledgePackage|ResolutionMemoryEntry)" cmm
rg -n "class (MemoryUpdateProposal|AgentKnowledgeUpdateProposal)" cmm
rg -n "class .*Permission.*Decision|class .*Approval.*(Request|Decision)" cmm/domains cmm/agent_runtime
rg -n "class DomainTrace|class DomainId" cmm/domains
```

- [ ] **Step 3: Record exact modules and fields**

Before writing tests, list the exact module path, identifier field, sensitivity
type, temporal/version fields and serialization behavior for every reused
contract. Do not invent adapters until this map is complete.

- [ ] **Step 4: Confirm dependency direction**

```bash
rg -n "cmm\.domains" cmm/cognitive cmm/agent_runtime || true
```

Expected: no reverse dependency introduced by the current work.

---

### Task 2: Error hierarchy and core immutable contracts

**Files:**
- Modify: `cmm/domains/errors.py`
- Create: `cmm/domains/memory_contracts.py`
- Create: `tests/domains/test_domain_memory_contracts.py`

**Interfaces:**
- Produces: `DomainMemoryReferenceKind`,
  `DomainMemorySelectionDecisionCode`, `DomainMemoryValidationCode`,
  `DomainMemoryReference`, `DomainMemoryViewRequest`,
  `DomainMemorySelectionDecision`, `DomainMemoryView`,
  `DomainMemoryProposalBinding`, `DomainMemoryReferenceInventory`,
  `DomainMemoryValidationResult`.

- [ ] **Step 1: Write failing contract tests**

Cover frozen/deep immutability, strict enum parsing, unknown-field rejection,
no coercion, finite numbers, deterministic canonical ordering, round-trip
serialization, ID/digest verification and sanitized domain-memory errors.
`DomainMemoryView.request_digest` is a required non-optional field containing
the full 64-character SHA-256 digest of `DomainMemoryViewRequest`. `view_id` is
content-bound to `request_digest` and selection decisions; changes in
`supporting_domains`, `resolution_reference_id`, `requested_kinds`,
`permission_decision_ids`, `trace_id`, or `temporal_reference` change view identity.

Example shape:

```python
def test_domain_memory_view_is_order_independent() -> None:
    first = make_view(selected=("knowledge:2", "knowledge:1"))
    second = make_view(selected=("knowledge:1", "knowledge:2"))
    assert first.id == second.id
    assert first.digest == second.digest
    assert first.to_dict() == second.to_dict()
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_memory_contracts.py
```

Expected: collection/import failure because contracts do not exist.

- [ ] **Step 3: Implement minimum contracts**

Follow established domain serialization helpers and ID/digest conventions.
Reuse `DomainId` and canonical sensitivity/permission types when dependency
direction permits. Store only IDs and typed policy metadata.

- [ ] **Step 4: Verify GREEN**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_memory_contracts.py
```

- [ ] **Step 5: Run focused static checks**

```bash
.venv/bin/python -m ruff check   cmm/domains/errors.py   cmm/domains/memory_contracts.py   tests/domains/test_domain_memory_contracts.py
```

---

### Task 3: Strict privacy and serialization boundary

**Files:**
- Modify: `cmm/domains/memory_contracts.py`
- Create: `tests/domains/test_domain_memory_privacy.py`

**Interfaces:**
- Produces: one shared recursive metadata/payload guard used by every public
  domain-memory contract.

- [ ] **Step 1: Write failing adversarial tests**

Parametrize snake_case, kebab-case, spaced, camelCase and PascalCase forms of
forbidden content/prompt/reasoning/secret/provider/tool keys. Test nested
mappings, lists, tuple injection, non-string keys, excessive depth, oversized
strings and `NaN`/infinity.

```python
@pytest.mark.parametrize(
    "key",
    ("claim_text", "claim-text", "claim text", "claimText", "ClaimText"),
)
def test_metadata_rejects_inline_claim_variants(key: str) -> None:
    with pytest.raises(DomainMemoryPrivacyError):
        DomainMemoryReference(..., metadata={key: "sensitive"})
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_memory_privacy.py
```

- [ ] **Step 3: Implement one normalized recursive guard**

Use a deterministic normalized-key comparison and bounded JSON-safe traversal.
Never include the rejected value in an exception.

- [ ] **Step 4: Verify GREEN and regression**

```bash
.venv/bin/python -m pytest -q   tests/domains/test_domain_memory_contracts.py   tests/domains/test_domain_memory_privacy.py
```

---

### Task 4: Pure deterministic memory-view resolver

**Files:**
- Create: `cmm/domains/memory_view.py`
- Create: `tests/domains/test_domain_memory_view.py`

**Interfaces:**
- Consumes: `DomainMemoryViewRequest` and its candidate descriptors.
- Produces: `DomainMemoryViewResolver` protocol and
  `DefaultDomainMemoryViewResolver.resolve(request, inventory) -> DomainMemoryView`.

- [ ] **Step 1: Write failing behavior tests**

Cover:

- primary-domain inclusion;
- supporting-domain inclusion only with effective cross-domain permission;
- general reusable reference inclusion;
- missing read permission exclusion;
- sensitivity exclusion/confirmation;
- missing evidence/provenance exclusion when required;
- superseded version handling without erasing history;
- unknown order preserved with `ORDERING_UNKNOWN`;
- unresolved conflict preservation;
- duplicate canonical ID handling;
- exactly one decision per candidate;
- selected/excluded disjointness and exact candidate coverage;
- deterministic output under reordered input.

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_memory_view.py
```

- [ ] **Step 3: Implement minimal resolver**

The resolver must use only request-supplied descriptors and permission
references. It must not query a store, graph, package builder or adapter.

- [ ] **Step 4: Verify GREEN**

```bash
.venv/bin/python -m pytest -q   tests/domains/test_domain_memory_contracts.py   tests/domains/test_domain_memory_privacy.py   tests/domains/test_domain_memory_view.py
```

---

### Task 5: Proposal binding and permission separation

**Files:**
- Modify: `cmm/domains/memory_contracts.py`
- Create: `tests/domains/test_domain_memory_proposals.py`

**Interfaces:**
- Consumes: IDs of canonical `MemoryUpdateProposal`,
  `AgentKnowledgeUpdateProposal`, permission decisions, approvals, view and
  trace.
- Produces: deterministic `DomainMemoryProposalBinding`.

- [ ] **Step 1: Write failing tests**

Prove that:

- at least one canonical proposal ID is required;
- additions/updates/invalidations cannot appear inline;
- read permission alone cannot authorize propose/apply/invalidate/delete;
- confirmation/approval references are required when inventory says so;
- affected reference IDs are canonicalized;
- the binding cannot invent a parallel status lifecycle;
- equivalent orderings produce the same ID/digest.

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest -q tests/domains/test_domain_memory_proposals.py
```

- [ ] **Step 3: Implement minimal binding contract**

Keep concrete change payloads and proposal status in the existing Phase 8/9
objects. The binding contains references and domain integration context only.

- [ ] **Step 4: Verify GREEN**

```bash
.venv/bin/python -m pytest -q   tests/domains/test_domain_memory_contracts.py   tests/domains/test_domain_memory_proposals.py
```

---

### Task 6: Fail-closed integration validator

**Files:**
- Create: `cmm/domains/memory_validation.py`
- Create: `tests/domains/test_domain_memory_validation.py`
- Create: `tests/domains/test_domain_memory_audit.py`

**Interfaces:**
- Produces:
  `DomainMemoryIntegrationValidator`,
  `DefaultDomainMemoryIntegrationValidator.validate_view(...)`,
  `DefaultDomainMemoryIntegrationValidator.validate_binding(...)`.

- [ ] **Step 1: Write failing validator tests**

Cover missing/unexpected references, kind/domain mismatches, duplicate IDs,
inline-content detection, evidence/provenance, temporal order, supersession,
version history, permission capability separation, approval linkage, exact
proposal coverage, trace/view mismatch, cross-domain permission, shared-item
duplication, ID/digest tampering, and exact `view.request_digest == request.digest`
equality in `validate_view()`.

- [ ] **Step 2: Add manipulated-instance tests**

Use `object.__new__` / `object.__setattr__` to bypass constructors and prove
the validator returns typed invalid results without leaking `KeyError`,
`TypeError`, `AttributeError`, canonical serialization errors or sensitive
values.

- [ ] **Step 3: Verify RED**

```bash
.venv/bin/python -m pytest -q   tests/domains/test_domain_memory_validation.py   tests/domains/test_domain_memory_audit.py
```

- [ ] **Step 4: Implement pure validator**

Treat inventory as authoritative external evidence. Catch expected contract,
serialization and type failures at the public validator boundary and convert
them to stable validation codes/diagnostics.

- [ ] **Step 5: Verify GREEN**

```bash
.venv/bin/python -m pytest -q   tests/domains/test_domain_memory_contracts.py   tests/domains/test_domain_memory_view.py   tests/domains/test_domain_memory_proposals.py   tests/domains/test_domain_memory_validation.py   tests/domains/test_domain_memory_privacy.py   tests/domains/test_domain_memory_audit.py
```

---

### Task 7: Public API and dependency-direction coverage

**Files:**
- Modify: `cmm/domains/__init__.py`
- Modify: `tests/domains/test_domain_public_api.py`
- Create: `tests/domains/test_domain_memory_public_api.py`

**Interfaces:**
- Produces: the intentional public Phase 10.18 API.

- [ ] **Step 1: Write failing public API tests**

Assert every intended contract, protocol, implementation and error is
available from `cmm.domains`; private helpers must remain unexported.

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest -q   tests/domains/test_domain_memory_public_api.py   tests/domains/test_domain_public_api.py
```

- [ ] **Step 3: Add explicit exports**

Keep `__all__` deterministic and consistent with established package style.

- [ ] **Step 4: Verify GREEN and direction**

```bash
.venv/bin/python -m pytest -q   tests/domains/test_domain_memory_public_api.py   tests/domains/test_domain_public_api.py   tests/agent_runtime/test_dependency_direction.py
```

Also run any Cognitive Layer dependency-direction test discovered in Task 1.

---

### Task 8: Documentation and roadmap closure

**Files:**
- Create: `docs/reference/domain-memory-integration.md`
- Create: `docs/superpowers/specs/2026-08-03-domain-memory-integration-design.md`
- Create: `docs/superpowers/plans/2026-08-03-domain-memory-integration-implementation-plan.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Modify: `ROADMAP.md`

- [ ] **Step 1: Write reference documentation**

Document exact public contracts, flow, invariants, exclusions, dependency
direction, examples using IDs only, and the boundary with Phase 11.

- [ ] **Step 2: Update roadmaps**

Mark 10.18 implemented only after focused tests pass. Preserve later phase
scope and remove any obsolete wording that permits persistent domain copies or
payload-bearing domain proposals.

- [ ] **Step 3: Check documentation diff**

```bash
git diff --   ROADMAP.md   docs/roadmap/phase-10-domain-intelligence.md   docs/reference/domain-memory-integration.md   docs/superpowers/specs/2026-08-03-domain-memory-integration-design.md   docs/superpowers/plans/2026-08-03-domain-memory-integration-implementation-plan.md
```

---

### Task 9: Complete verification and staged audit package

**Files:**
- All Phase 10.18 files only.

- [ ] **Step 1: Focused tests**

```bash
.venv/bin/python -m pytest -q   tests/domains/test_domain_memory_contracts.py   tests/domains/test_domain_memory_view.py   tests/domains/test_domain_memory_proposals.py   tests/domains/test_domain_memory_validation.py   tests/domains/test_domain_memory_privacy.py   tests/domains/test_domain_memory_public_api.py   tests/domains/test_domain_memory_audit.py
```

- [ ] **Step 2: Domain and global regressions**

```bash
.venv/bin/python -m pytest -q tests/domains
.venv/bin/python -m pytest -q
```

- [ ] **Step 3: Static checks**

```bash
.venv/bin/python -m ruff check   cmm/domains/memory_contracts.py   cmm/domains/memory_view.py   cmm/domains/memory_validation.py   tests/domains/test_domain_memory_*.py

.venv/bin/python -m ruff check --target-version py310   cmm/domains/memory_contracts.py   cmm/domains/memory_view.py   cmm/domains/memory_validation.py   tests/domains/test_domain_memory_*.py

.venv/bin/python -m compileall -q cmm tests
.venv/bin/python -m pytest -q tests/agent_runtime/test_dependency_direction.py
git diff --check
git diff --cached --check
```

- [ ] **Step 4: Inspect exact change inventory**

```bash
git status --short
git diff --name-only
git diff --stat
```

Reject unrelated files.

- [ ] **Step 5: Stage only Phase 10.18**

Stage the exact approved inventory after confirming it. Do not stage audit
archives, patches, caches or unrelated edits.

- [ ] **Step 6: Produce evidence**

Capture branch, base commit, status, staged file list/stat, focused/domain/global
test logs, Ruff logs, compileall, dependency tests and both diff checks.

- [ ] **Step 7: Stop**

Do not commit or push. Report the implementation summary, exact files,
verification counts and any remaining risks. The human will package and audit
the exact staged blobs.
