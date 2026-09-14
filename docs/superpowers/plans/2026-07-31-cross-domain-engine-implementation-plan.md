# Phase 10.9 — Cross-Domain Engine Implementation Plan

## Status

Implemented.

## Base

```text
11deea0 docs(domains): define phase 10.9 cross-domain engine
```

## Objective

Implement `DefaultCrossDomainEngine`, a synchronous, deterministic
orchestrator that coordinates the Domain Resolver, Domain Composition,
Cognitive Layer, Planner, Agent Runtime, Workflow Engine, and Knowledge
Graph through narrow injectable ports, per
`docs/superpowers/specs/2026-07-31-cross-domain-engine-design.md`.

## Files

Created:

```text
cmm/domains/cross_domain_contracts.py
cmm/domains/cross_domain_ports.py
cmm/domains/cross_domain_context.py
cmm/domains/cross_domain_limits.py
cmm/domains/cross_domain_aggregation.py
cmm/domains/cross_domain_engine.py
```

Modified:

```text
cmm/domains/enums.py               (+ CrossDomainStatus, CrossDomainSeverity, CrossDomainStage)
cmm/domains/errors.py              (+ CrossDomain* error hierarchy)
cmm/domains/__init__.py            (+ Phase 10.9 exports)
tests/domains/test_domain_public_api.py                (updated expected export set)
tests/domains/test_domain_composition_public_api.py    (removed obsolete CrossDomainEngine
                                                          forbidden-export guard — Phase 10.9
                                                          now legitimately exports it)
```

Not modified: `resolver.py`, `resolver_contracts.py`, `composer.py`,
`composition_contracts.py`, `contracts.py` — no defect required touching
them. The engine consumes `DomainResolutionResult` and `DomainComposition`
read-only through the new port protocols.

Tests created:

```text
tests/domains/test_cross_domain_contracts.py
tests/domains/test_cross_domain_serialization.py
tests/domains/test_cross_domain_context.py
tests/domains/test_cross_domain_limits.py
tests/domains/test_cross_domain_aggregation.py
tests/domains/test_cross_domain_engine.py
tests/domains/test_cross_domain_ports.py
tests/domains/test_cross_domain_public_api.py
tests/domains/test_cross_domain_boundaries.py
```

## Design decisions beyond the spec's literal text

* **Auxiliary enums**: only `CrossDomainSeverity` and `CrossDomainStage`
  were added beyond `CrossDomainStatus` — both back closed-semantics
  contract fields (`CrossDomainContradiction.severity`,
  `CrossDomainDecision.stage`). `CrossDomainPortStatus`,
  `CrossDomainGapKind`, and `CrossDomainDependencyKind` were judged
  unnecessary: gap/dependency `kind`/`code` remain open, provenance-bearing
  strings (matching the existing Phase 10.1–10.8 pattern for
  `category`/`kind`/`severity` on composition contracts), and port
  availability is already fully expressed via decision codes
  (`PORT_SKIPPED`, `PORT_UNAVAILABLE`).
* **Error translation**: the reused validation helpers from
  `contracts.py`/`resolver_contracts.py` raise the `Domain*` error
  hierarchy. Every Cross-Domain contract must raise `CrossDomain*` errors
  instead, so each reused helper is rebound at import time in
  `cross_domain_contracts.py` to translate `DomainContractValidationError`
  → `CrossDomainContractError` and `DomainSerializationError`/
  `DomainResolutionSerializationError` → `CrossDomainSerializationError`,
  preserving message/field/details without ever calling `str(exc)`.
* **`CrossDomainResult` status invariants** are validated structurally from
  the tuples actually present on the result (blocking gaps/dependencies,
  `PORT_UNAVAILABLE`/`BLOCK_PROPAGATED` blocking decisions,
  `HUMAN_REVIEW_REQUESTED` decisions, unresolved+`requires_review`
  contradictions, `limits.reached_limits`). The engine's `_finalize` step
  computes the same predicates before constructing the result and appends
  a synthetic `HUMAN_REVIEW_REQUESTED` decision whenever
  `require_review_for_high_severity` escalates a result to
  `REQUIRES_REVIEW`, so the derived status and the contract's own
  invariant check are always in agreement.
* **Execution-port selection** (`_select_execution_port`): since
  `CrossDomainPlanResult` has no explicit "needs action vs. needs
  reasoning" field, the engine prefers the Agent port when the plan
  declares `operation_requests`/`workflow_requests` for the current
  round, and the Cognitive port otherwise; either port is used only when
  available, with no automatic double-invocation for the same domain.
* **Blocking propagation scope**: a per-domain block (from
  `CrossDomainDomainResult.status` in `{BLOCKED, FAILED}` or a blocking
  gap/dependency sourced at that domain) only escalates the *global*
  result to `BLOCKED` when `policy.continue_independent_domains` is
  `False`, or when it wiped out all useful output. Otherwise it is
  recorded (`BLOCK_PROPAGATED`, `PARTIAL_RESULT_RETAINED`) and dependent
  domains are skipped (`DOMAIN_SKIPPED`), while independent domains still
  execute — the overall result becomes `PARTIAL`, matching the design
  doc's "independent domains may continue" requirement.
* **Context transfer**: the engine only constructs a transfer when a
  `CrossDomainDependency` from the active plan explicitly targets the
  domain about to run (never inferred from text), and only forwards
  `shared_findings` accumulated so far, tagged with the dependency's own
  `provenance` and `description` (as `reason`). Permission denial is
  checked via exact `deny:<domain-slug>` entries in
  `CrossDomainRequest.permissions`.

## Deliberate exclusions (unchanged from spec)

persistence and restart recovery; distributed execution and real
concurrency; queues, retries, circuit breakers; metrics and events; HTTP
integration; model selection and provider billing; human review UI;
Domain Resources (Phase 10.10).

## Verification

```zsh
python -m ruff format cmm/domains/cross_domain_*.py cmm/domains/enums.py \
  cmm/domains/errors.py cmm/domains/__init__.py tests/domains/test_cross_domain_*.py \
  tests/domains/test_domain_public_api.py
python -m ruff check   <same files>
python -m pytest tests/domains/test_cross_domain_*.py -q
python -m pytest tests/domains -q
python -m pytest tests/validation -q
python -m pytest -q
python -m compileall -q cmm/domains tests/domains
```

No commit or push performed.
