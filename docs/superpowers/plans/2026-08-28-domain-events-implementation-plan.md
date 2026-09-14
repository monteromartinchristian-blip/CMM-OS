# Phase 10.33 Domain Events Implementation Plan

> **Goal:** Implement the stable, versioned, immutable Domain Intelligence event layer and Kernel publisher boundary for CMM OS Phase 10.33, remediating all Independent Audit V1 findings.

**Architecture:** A lightweight Domain Event layer plus adapter converting Domain Events into `kernel.events.Event` envelopes. Pure Phase 10 components (such as `DomainConflictResolver`) remain completely pure and side-effect free, while an explicit `DomainLifecycleEventBridge` orchestrates lifecycle transitions and Kernel publication.

**Tech Stack:** Python 3.12+, frozen `dataclasses(slots=True)`, `MappingProxyType`, `kernel.events.Event`, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-08-28-domain-events-design.md`

---

## 1. Scope & Principles

- **Exact 23 General Domain Events:** Canonical immutable catalog matching roadmap and spec.
- **Specialized Domain Pack Events:** Allowed in owning domain namespace with strict schema versioning and validation.
- **Fail-Closed Privacy Boundary:** Recursive rejection of forbidden privacy markers (`chain_of_thought`, `system_prompt`, `developer_prompt`, `raw_prompt`, `pii`, `provider_request`, `provider_response`, `tool_arguments`, `tool_response`, `raw_content`, etc.) and secret-like values (Bearer tokens, Authorization headers, API keys, session tokens).
- **Safe Failure Representation:** Failure adapters (`adapt_operation_failed`, `adapt_execution_failed`) sanitize error messages and never leak raw secrets across the event boundary.
- **Schema Version Enforcement:** Strict validation against registry declaration (`event.schema_version == decl.schema_version`), rejecting empty or malformed versions.
- **Strict Deserialization & Factory Construction:** No fail-open coercions (e.g. `actor=123`, `permissions="read"`, `payload=[]`, explicit `event_id=""`, or unsupported provenance objects fail closed).
- **Effective Permission Isolation:** `DomainEvent.permissions` represents the authoritative effective permission context only. Requested/denied capabilities are isolated in payload/provenance and cannot broaden authority.
- **Safe Publication Order:** Events are only recorded in `emitted_events` after successful delivery to Kernel listeners; failed listener delivery raises `DomainEventPublicationError` and does not record the failed event.
- **Kernel Integration Bridge:** `DomainLifecycleEventBridge` provides the production orchestration path for domain resolution and conflict lifecycles without contaminating pure semantic engines.
- **Non-Goals:** No event persistence, replay, durable queues, cross-process transport, or session mutation in Phase 10.33.

---

## 2. Modules and Responsibilities

### Production Modules

1. `cmm/domains/event_catalog.py`
   - Exact 23 `CANONICAL_DOMAIN_EVENTS` tuple and frozenset.
   - Dotted lowercase syntax validation and specialized domain namespace validation (`get_canonical_domain_namespace`, `validate_specialized_event_namespace`).

2. `cmm/domains/event_contracts.py`
   - `DomainEventReference` and `DomainEvent` frozen dataclasses.
   - Comprehensive privacy markers, token sequences, and secret-value regex filters.
   - Deep freeze of `payload` and `metadata` into `MappingProxyType`.
   - Strict `from_dict` and `to_dict` serialization.

3. `cmm/domains/event_registry.py`
   - `DomainEventDeclaration` and `DomainEventRegistry`.
   - Built-in canonical events with canonical schema version `1.0.0`.
   - Semver validation on registration and strict equality check in `validate_event`.

4. `cmm/domains/event_factory.py`
   - `DomainEventFactory` with injectable clock and ID generator.
   - Strict input validation without fail-open truthiness fallbacks.

5. `cmm/domains/event_publisher.py`
   - `DomainKernelEventPublisher` converting validated `DomainEvent` to `kernel.events.Event`.
   - Safe delivery ordering and immutable `emitted_events` snapshot.

6. `cmm/domains/event_adapters.py`
   - Pure adapters translating authoritative results (`resolution`, `composition`, `execution`, `conflict`, `permission`, `approval`, `memory`, `workflow`, `operation`) to `DomainEvent`.
   - Redaction helper `_sanitize_public_error_message` protecting failure adapters.
   - Isolation of requested/denied capabilities from `DomainEvent.permissions`.

7. `cmm/domains/lifecycle_bridge.py`
   - `DomainLifecycleEventBridge` orchestrating resolution and conflict lifecycles to Kernel events.
   - Call-around methods preserving resolver purity.

8. `cmm/domains/errors.py` & `cmm/domains/__init__.py`
   - Typed error hierarchy and stable public exports.

---

## 3. Independent Audit V1 Remediations

- **B1 (Secret Policy):** Verified `.gitignore` protects `.env` and `.env.*`; no secrets tracked in git or copied to tests.
- **B2 (Privacy Boundary):** Implemented recursive scanning for forbidden markers and secret value patterns in payload/metadata; sanitized error text in failure adapters.
- **M1 (Schema Version):** Added `_validate_schema_version` in registry and enforced `event.schema_version == decl.schema_version` for both built-in and specialized events.
- **M2 (Strict Construction):** Replaced fail-open coercions in `DomainEvent.from_dict` and `DomainEventFactory.create_event` with strict type checks.
- **M3 (Permission Context):** Updated `adapt_permission_requested` and `adapt_permission_denied` so capabilities remain in payload and `permissions` defaults to empty or explicit effective context.
- **M4 (Publication State):** Modified `DomainKernelEventPublisher.publish` to deliver to listener before recording in `_emitted_events`.
- **M5 (Kernel Wiring):** Created `DomainLifecycleEventBridge` providing clean production call-around wiring to `kernel.events.Event`.
- **m1 (Implementation Plan):** Created this canonical repository-local plan document.

---

## 4. Verification and Acceptance

- **Audit Regression Suite:** `tests/domains/test_domain_events_audit_v1_regressions.py` covering all B1, B2, M1-M5, m1 findings.
- **Acceptance Gate:** `tests/domains/test_domain_events_dp033_acceptance.py` covering all checkpoints behaviorally.
- **Public API Suite:** `tests/domains/test_domain_public_api.py`.
- **Quality Gates:** Ruff lint (0 violations), Ruff format check (PASS), `compileall` (PASS).
