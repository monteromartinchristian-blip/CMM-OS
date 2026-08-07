# General Domain Implementation Plan — Phase 10.19

## Overview

Implements `domain:general` as a declarative, composable domain layer over the
existing Domain Intelligence infrastructure (Fases 10.1–10.18). Each block
follows strict TDD: tests first (RED), minimal production (GREEN), then the
accumulated focused suite.

## Block 1 — Definition, Manifest and Pack

**Files:** `cmm/domains/general/__init__.py`, `cmm/domains/general/definition.py`,
`tests/domains/test_general_domain_definition.py`

**Tests:** valid `DomainId`; frozen definition; valid semver; real enums; no
duplicate IDs; deterministic construction; manifest round-trip; pack validation;
no unsafe paths; stable checksum; registration; repeated registration policy;
loader load/unload; load failure atomicity; no import side effects; no
alternative registries.

## Block 2 — Resources

**Files:** `cmm/domains/general/resources.py`,
`tests/domains/test_general_domain_resources.py`

**Tests:** 9 resource kinds; exact IDs; no duplicates; resolution; validation;
sensitivity; permissions; temporality; provenance; derivation; shared resources
without copy; strict serialization; deterministic ordering; unknown fields;
wrong types; unknown adapters; unauthorized resources; external source
fail-closed.

## Block 3 — General Profile

**Files:** `cmm/domains/general/profile.py`,
`tests/domains/test_general_domain_profile.py`

**Tests:** registration/resolution; composition with global and specialized
profiles; strongest restrictions prevail; no global rule disabling; no minimum
confidence lowering; no prohibited action removal; no permission expansion;
deterministic composition; traceable conflicts; strict serialization; no
mutability; catalog without duplicates.

## Block 4 — Rules

**Files:** `cmm/domains/general/rules.py`,
`tests/domains/test_general_domain_rules.py`

**Tests per rule:** happy path; partial input; missing permissions; unknown
temporality; missing provenance; duplicates; determinism; repeated execution;
no mutation; reference-only trace; sanitized errors; serialization;
registration; selection; execution; global rule conflicts; specialized rule
composition.

## Block 5 — Operations

**Files:** `cmm/domains/general/operations.py`,
`tests/domains/test_general_domain_operations.py`

**Tests per operation:** registration; availability; **UNAVAILABLE by default
without injected implementation**; injected implementations; proposal-only
output (`proposal` + `binding`) for create_task/update_goal; valid/invalid
schema; valid/invalid output; permissions; approval; cancellation; timeout;
delegate error; trace; no direct persistence; no side effects; determinism;
retry; rollback; exact catalog; unique IDs.

## Block 6 — Workflows

**Files:** `cmm/domains/general/workflows.py`,
`tests/domains/test_general_domain_workflows.py`

**Tests:** definition; registration; valid DAG; unique IDs; supported nodes;
valid dependencies; no cycles; deterministic order; pause/resume; cancel;
failure propagation; approval gate; permission denial; completion criteria;
incomplete workflow; safe retry; memory proposal; trace; serialization;
versioning; no side effects; composition; complete catalog.

## Block 7 — Permissions and Autonomy

**Files:** `cmm/domains/general/permissions.py`,
`tests/domains/test_general_domain_permissions.py`

**Tests:** permission intersection; unknown/partial permission; explicit denial;
approval required; cross-domain; autonomy; memory read/proposal; external
action; schedule modification; sensitive inference; file modification;
permission modification; most restrictive wins; determinism; decision trace;
sanitized errors.

## Block 8 — Fallback and Resolution

**Files:** `cmm/domains/general/bootstrap.py`, `cmm/domains/general/integration.py`,
`tests/domains/test_general_domain_resolution.py`

**Tests:** canonical bootstrap resolver with General fallback; general-only;
explicit general; specialized candidate available; ineligible signaled domain
blocks fallback (fail-closed); no specialized signal allows General fallback;
health/university/project-like; sensitive; ambiguous; equal scores; unsupported
specialized; blocked specialized; missing permissions; supporting domain; not
automatically supporting; deterministic repeated; resolution trace;
composition restrictions; no permission widening; no profile weakening.

## Block 9 — Presentation

**Files:** `cmm/domains/general/presentation.py`,
`tests/domains/test_general_domain_presentation.py`

**Tests:** deterministic plan; required sections; warnings/uncertainty/
provenance/contradictions visible; terminology; no mutation; preservation
validator; unknown references; duplicate sections; fallback badge; output
intents; strict serialization.

## Block 10 — Trace

**Files:** `cmm/domains/general/trace.py`,
`tests/domains/test_general_domain_trace.py`

**Tests:** caller-supplied typed references; no fabricated references; canonical
`DomainTraceAssembler`; validation against a full reference inventory;
unknown/incorrect reference; sensitive content; private marker; deterministic
ID/digest; full round-trip; manipulation detection; no duplicate references;
no internal reasoning.

## Block 11 — Domain Memory Integration

**Files:** `cmm/domains/general/memory.py`,
`tests/domains/test_general_domain_memory.py`

**Tests:** valid view; unknown permission; temporally invalid; sensitive
reference; create_task/update_goal proposals; proposal coverage; approval
linkage; full digest binding; manipulation; duplicate proposal; supersession;
provenance; no direct store access; no separate memory; privacy; reference-only
payload; validator GREEN.

## Block 12 — Integration with Catalogs and Registries

**Files:** `cmm/domains/general/integration.py`,
`tests/domains/test_general_domain_integration.py`

**Tests:** complete registration; partial failure; rollback; duplicate ID/
version; unsupported contract version; missing dependency; invalid component;
exact catalog contents; re-registration; unload; reload; snapshot;
deterministic ordering; public API; no import-time registration.

## Block 13 — Public API

**Files:** `cmm/domains/general/__init__.py`,
`tests/domains/test_general_domain_public_api.py`

**Tests:** expected exports; no private exports; `__all__`; clean import; no
import side effects; no cycles; name stability; root API.

## Block 14 — Documentation

**Files:** `docs/reference/general-domain.md`; update
`docs/roadmap/phase-10-domain-intelligence.md`, `ROADMAP.md`, spec, plan.

**Guards:** `domain:general`; 9 resource kinds; 6 rule IDs; 8 operation IDs;
4 workflow IDs; no external actions; memory via proposals; specialized domain
priority; not catch-all.

## Verification

After each block:
```bash
.venv/bin/python -m pytest -q tests/domains/test_general_domain_*.py
.venv/bin/python -m ruff check --target-version py310 cmm/domains tests/domains
git diff --check
```

Final:
```bash
.venv/bin/python -m pytest -q -W error tests/domains/test_general_domain_*.py
.venv/bin/python -m pytest -q tests/domains
.venv/bin/python -m pytest -q -W default -r w
.venv/bin/python -m ruff check cmm/domains tests/domains
.venv/bin/python -m ruff check --target-version py310 cmm/domains tests/domains
.venv/bin/python -m compileall -q cmm tests