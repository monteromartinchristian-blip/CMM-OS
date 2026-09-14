# CMM OS — Phase 10.33 Independent Audit V1

**Date:** 2026-08-28
**Audited branch:** `feature/phase-10-domain-intelligence`
**Audited HEAD:** `009084d4732bb1224ae96cbd2a1d02fde5f9e0ea`
**Base:** `b72d47b59d64b5afcc07c9f3883cbf8d9ce5b979`
**Bundle SHA-256:** `13700da432b89c9b465880dff3459e50c91e83e14b501f9cef764f786e374d3d`
**Verdict:** FAIL — remediation required before closure

## Audit summary

- BLOCKERS: 2
- MAJORS: 5
- MINORS: 1
- Phase 10.33 must remain `Implemented, pending independent audit`.
- Phase 10.34 must not be advanced.
- No closure commit should be created until all findings are remediated and a clean new audit bundle is generated.

## B1 — Audit bundle leaks a credential

**Severity:** BLOCKER
**Scope:** Audit artifact / security

The V1 TAR.GZ contains repository-root `.env`. Inspection without printing values confirmed:

- 5 non-empty assignments;
- `OPENAI_API_KEY` is non-empty;
- the value has an `sk-` prefix and length consistent with a real OpenAI API credential.

The value was not reproduced in the audit report.

This invalidates the V1 bundle as a safe audit artifact and the credential must be treated as exposed.

### Required remediation

1. Revoke/rotate the exposed OpenAI API key.
2. Do not include `.env`, `.env.*`, credentials, local runtime secrets, or other ignored secret files in audit bundles.
3. Prefer `git archive HEAD` for audit bundles so only committed files are included.
4. Add an explicit forbidden-content check for `.env`, `.env.*`, credential files, `.git`, `.venv`, caches, and generated archives.
5. Generate a fresh V2 bundle after implementation remediation.

## B2 — DomainEvent privacy boundary accepts forbidden secret/private content

**Severity:** BLOCKER
**Scope:** Implementation / security / privacy

`event_contracts.py` rejects credential-like **keys**, but it does not enforce the broader privacy invariants committed in the design.

Adversarial construction accepted all of:

```text
payload={"chain_of_thought": "private"}
payload={"system_prompt": "private"}
payload={"pii": "private"}
payload={"error": "Authorization: Bearer sk-example-secret"}
```

Additionally, `adapt_operation_failed()` and `adapt_execution_failed()` copy caller-provided raw `error` strings directly into event payloads. A secret embedded in an exception/error message therefore crosses the event boundary unchanged.

This violates the committed safeguards:

```text
no credentials
no API keys
no authorization headers
no cookies/tokens
no hidden reasoning
no private prompt capture
no raw sensitive content when a reference is sufficient
```

### Required remediation

- Reuse or align with the established privacy-marker logic already present in `trace_contracts.py` / `memory_contracts.py`.
- Reject private prompt, hidden reasoning, chain-of-thought, raw content, provider request/response, tool arguments/responses, PII, credentials and comparable private markers.
- Add safe handling for secret-like **values**, not only key names.
- Do not serialize raw exception/error text across this boundary. Use a safe error code/classification/reference plus sanitized public message where explicitly allowed.
- Add adversarial regression tests for these cases.

## M1 — Registry does not enforce declared schema version

**Severity:** MAJOR

`DomainEventRegistry.register_specialized()` stores `schema_version`, but `validate_event()` never compares it with `event.schema_version`.

Confirmed behavior:

```text
registered project.release.prepared as schema_version=2.0.0
published/validated event uses schema_version=1.0.0
result: accepted
```

The registry also does not validate that the registered schema version itself is a valid non-empty version identifier.

This breaks the stable/versioned event contract.

### Required remediation

- Validate declaration schema versions.
- Require `event.schema_version == declaration.schema_version` unless an explicit compatible-version policy is later designed.
- Apply the same rule to built-in events.
- Add mismatched-version and malformed-version fail-closed tests.

## M2 — Strict deserialization and factory construction are fail-open

**Severity:** MAJOR

The committed spec requires strict serialization/deserialization and fail-closed behavior.

Confirmed examples:

```text
DomainEvent.from_dict(actor=123)
→ accepted as actor="123"

DomainEvent.from_dict(permissions="read")
→ accepted as ("r", "e", "a", "d")

DomainEventFactory(... provenance=(object(),))
→ silently drops invalid provenance and produces provenance=()

DomainEventFactory(... payload=[])
→ silently replaces invalid payload with {}
```

`event_id=""` can also be replaced by a generated ID due to truthiness-based fallback instead of rejecting an explicitly invalid caller value.

### Required remediation

- Do not coerce invalid required field types through `str(...)`.
- Validate sequence/mapping types before conversion.
- Add an explicit `else: raise` for unsupported provenance entries.
- Replace truthiness fallbacks such as `payload or {}` and `event_id or ...` with `is None` semantics.
- Add adversarial strict-deserialization/factory tests.

## M3 — Permission request/denial events misstate effective permission context

**Severity:** MAJOR

The design defines `DomainEvent.permissions` as identifiers describing the **effective permission context**, explicitly not permission grants.

However:

```python
adapt_permission_requested(capability="domain.project.write", ...)
adapt_permission_denied(capability="domain.project.write", ...)
```

both emit:

```text
permissions=("domain.project.write",)
```

A requested or denied capability is therefore placed into the field reserved for effective permissions.

The current CP-26 test checks only event names and does not assert this invariant.

### Required remediation

- Keep requested/denied capability in payload/provenance only.
- Populate `permissions` from an explicitly supplied authoritative effective-permission context.
- Default to an empty effective context if none is available, rather than treating the requested capability as effective.
- Add tests proving requested/denied capabilities never become effective permissions merely by event creation.

## M4 — Failed listener delivery remains recorded as emitted

**Severity:** MAJOR

`DomainKernelEventPublisher.publish()` appends the Kernel event to `_emitted_events` **before** invoking the listener.

If the listener raises:

```text
publish() → DomainEventPublicationError
emitted_events → still contains the failed event
```

This creates contradictory publication state: the API reports delivery failure while its own `emitted_events` history labels the event as emitted/published.

The existing publication-error tests verify only that the typed error is raised; they do not verify state rollback/non-recording.

### Required remediation

Either:

- call the listener first and append only after successful delivery; or
- explicitly separate `attempted_events` from `successfully_emitted_events`.

Add a regression asserting failed listener delivery does not appear as successfully emitted.

## M5 — No production lifecycle path is wired to DomainKernelEventPublisher

**Severity:** MAJOR
**Scope:** Architectural completeness

Outside the new event modules and package exports, the audit found no production call site for:

```text
DomainKernelEventPublisher
adapt_resolution_started
adapt_resolution_result
adapt_conflict_detected
...
```

The implementation therefore exposes an event API and Kernel converter, but no existing Domain Intelligence lifecycle actually emits these events in production.

The Phase 10.33 objective is:

```text
To integrate domains with the Kernel through stable events.
```

The committed design also states that Phase 10.33 adds adapters/orchestration around existing lifecycle boundaries.

### Required remediation

Add the smallest explicit orchestration/integration boundary required by the design without contaminating pure Phase 10.31/10.32 engines.

At minimum, demonstrate a real production path where an authoritative lifecycle result is adapted and published through `DomainKernelEventPublisher`.

Do not inject event side effects into `DomainConflictResolver` or other pure semantic engines.

If the intended Phase 10.33 scope is deliberately contract-only, amend the committed design and roadmap objective before claiming completion; otherwise production wiring is required.

## m1 — Roadmap references a missing implementation plan

**Severity:** MINOR

`docs/roadmap/phase-10-domain-intelligence.md` references:

```text
docs/superpowers/plans/2026-08-28-domain-events-implementation-plan.md
```

but that file is absent from the audit bundle/repository.

The agent created its plan outside the repository workspace.

### Required remediation

Either:

- add the canonical implementation plan at the referenced path; or
- remove/correct the roadmap reference.

## Positive findings

The audit also confirmed several important requirements are implemented correctly:

- exact canonical catalog of 23 general events;
- Kernel event conversion preserves event name, timestamp and serialized payload;
- unknown event types fail closed at publication;
- immutable/frozen DomainEvent surface with timezone enforcement;
- recursive credential-like **key** rejection exists;
- specialized namespace ownership validation exists;
- `domain.conflict.resolved` is withheld unless status is `RESOLVED` and `can_proceed=True`;
- unresolved/postponed/human-review/maintained conflict paths remain non-resolved;
- no dependency on `AgentRuntimeEventBus` was found in Phase 10.33 event modules;
- `DomainConflictResolver` remains outside the event publisher/factory dependency;
- syntax compilation of the audited event delta passed independently.

## Verification note

The original development environment reported:

```text
142 focused tests PASS
7048 domain tests PASS
12588 global tests PASS
Ruff PASS
format PASS
compile PASS
diff check PASS
```

The independent sandbox successfully verified bundle SHA-256, extracted and inspected the complete bundle, compiled the relevant Python delta, performed AST dependency checks, and executed custom adversarial probes.

The full repository pytest suite could not be independently re-executed in the audit sandbox because the bundle intentionally excludes `.venv` and the sandbox lacks the repository dependency `libcst`; internet/package installation is unavailable. This environment limitation does not affect the reproduced findings above.

## Required next state

```text
PHASE10_33_INDEPENDENT_AUDIT_V1=FAIL
BLOCKERS=2
MAJORS=5
MINORS=1
AUDITED_HEAD=009084d4732bb1224ae96cbd2a1d02fde5f9e0ea
AUDIT_BUNDLE_SHA256=13700da432b89c9b465880dff3459e50c91e83e14b501f9cef764f786e374d3d
NEXT=REMEDIATE_V1_FINDINGS
CLOSE_PHASE=NO
ADVANCE_PHASE10_34=NO
PUSH=NO
MERGE=NO
```
