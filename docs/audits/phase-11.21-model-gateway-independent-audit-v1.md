# Phase 11.21 — Model Gateway — Independent Audit V1

**Project:** CMM OS  
**Phase:** 11.21 — Model Gateway  
**Requirement:** `F11-020 — Canonical Provider-Independent Model Gateway`  
**Design Point:** `DP-121 — Canonical Provider-Independent Model Gateway`  
**Acceptance:** `AT-DP-121 — Canonical Provider-Independent Model Gateway Acceptance`  
**Audit type:** Independent Audit V1  
**Auditor:** ChatGPT, independent of the implementation agent  
**Date:** 2026-09-25

---

## 1. Executive verdict

```text
INDEPENDENT_AUDIT_V1=FAIL

AUDITED_HEAD=811d82875a982e43fbb4fde11cf54b342b2c94a3
AUDITED_TREE=153e4e458a6136a41f6807d41de66f53e7ae288f
AUDITED_BUNDLE_SHA256=1b5f1022c9ede049c963eff120395ce0ba9567215f185e30c7aa965007a877f3

BLOCKERS=0
MAJORS=5
MINORS=1

MAJOR_01=AUTO_SELECTION_STOPS_ON_PRIVACY_DENIED_CANDIDATE_INSTEAD_OF_TRYING_NEXT_CANONICAL_MATCH
MAJOR_02=CANCELLATION_TOKEN_IS_DROPPED_WHEN_AUTHORIZED_FALLBACK_BEGINS
MAJOR_03=STREAM_TIMEOUT_CAN_EMIT_CONTENT_AFTER_DEADLINE_AND_CANNOT_BOUND_BLOCKING_NEXT
MAJOR_04=LEGACY_PROVIDER_ADAPTER_SILENTLY_DROPS_TOOLS_AND_STRUCTURED_OUTPUT_REQUIREMENTS
MAJOR_05=PHASE11_21_MODEL_CAPABILITY_FIELDS_ARE_LOST_ACROSS_CANONICAL_PROVIDER_STATE_ROUND_TRIP

MINOR_01=REFERENCE_AND_GATE_DOCUMENTATION_CONTAINS_STALE_ACCEPTANCE_PATH_AND_FOCUSED_TEST_COUNT

F11_020=IMPLEMENTED_REMEDIATION_REQUIRED
DP_121=NOT_VERIFIED
AT_DP_121=PASS_LOCAL_EVIDENCE_ONLY
CLOSURE_ELIGIBLE=NO

NEXT=PHASE11_21_REMEDIATION_V1
```

The implementation is architecturally strong and materially implements the intended Model Gateway boundary. Exact Provider Registry / Model Catalog identity, explicit reasoning effort, real image/PDF bytes, provider-independent contracts, safe privacy injection, tool non-execution, normalized streaming events, cost/accounting, evidence projection and Phase 11.1 composition are all present.

The phase is nevertheless **not closure-eligible**. Five independently reproduced behaviors contradict the frozen Model Gateway contract:

1. AUTO selection does not carry effective privacy into candidate choice and can stop on a privacy-denied remote candidate even when a valid local candidate exists.
2. A cancellation token is dropped when execution transitions into an authorized fallback.
3. streaming may emit content after its deadline and the gateway cannot enforce the timeout while blocked inside `next(adapter_events)`;
4. the legacy provider wrapper silently ignores requested tools and structured-output requirements rather than failing closed;
5. the new reasoning-effort/document/streaming capability metadata is discarded by the canonical Phase 11.34 provider-state round trip.

These findings require Remediation V1 and a new exact-HEAD bundle.

---

## 2. Audit target and immutable identity

The audit was performed against the exact uploaded archive:

```text
cmm-phase11-21-model-gateway-implementation-811d82875a98.tar.gz
```

Independent archive verification:

```text
SHA256=1b5f1022c9ede049c963eff120395ce0ba9567215f185e30c7aa965007a877f3
SIZE=8191876
ENTRIES=2603
UNSAFE_ARCHIVE_MEMBERS=0
SYMLINKS=0
EMBEDDED_GIT_ARCHIVE_HEAD=811d82875a982e43fbb4fde11cf54b342b2c94a3
```

The Git tree was independently reconstructed from the archive contents and tracked file modes:

```text
RECONSTRUCTED_TREE=153e4e458a6136a41f6807d41de66f53e7ae288f
EXPECTED_TREE=153e4e458a6136a41f6807d41de66f53e7ae288f
TREE_IDENTITY=PASS
```

Therefore the audit does not rely on the implementation agent's assertion of HEAD or tree identity.

---

## 3. Governing artifacts

The exact archive contains the frozen governing artifacts:

```text
docs/superpowers/specs/2026-09-25-phase-11.21-model-gateway-design.md
SHA256=6f9bbc405d5d20383714785bca401e6f9ad5de61c319e7463d02bffbc1214400

docs/superpowers/plans/2026-09-25-phase-11.21-model-gateway-implementation-plan.md
SHA256=e82eb2b2e3c9f2b09b828f3ccc9f701d6eb9edc294b38916ab9d9c8281e64fa7
```

Both match the frozen pre-implementation hashes.

The audit therefore evaluates the exact candidate against the approved spec and plan.

---

## 4. Independent execution and environment limits

Independent syntax compilation succeeded:

```text
python3 -m compileall -q \
  kernel/llm \
  cmm/agent_runtime \
  cmm/platform \
  cmm/application \
  cmm/conversation

COMPILEALL=PASS
```

A direct whitespace scan of the audited model-gateway, relevant Phase 11 and test surfaces found:

```text
TRAILING_WHITESPACE_HITS=0
```

The audit environment cannot replay the full pytest suite because `libcst` is not installed. The repository itself declares:

```text
libcst>=1.0
```

in `pyproject.toml`.

The audit environment also has no Ruff executable; the repository declares:

```text
ruff>=0.9,<1
```

This is an audit-environment limitation, not a repository test failure.

Implementation-machine evidence supplied for the exact candidate records:

```text
AT_DP_121=31 passed
FOCUSED_GATEWAY=371 passed
TESTS_LLM=1102 passed
AGENT_RUNTIME_MODEL_REGRESSIONS=167 passed
INHERITED_ACCEPTANCES=PASS
PLATFORM=369 passed
ORCHESTRATION=498 passed
APPLICATION=674 passed
CLI=459 passed
CONVERSATION=860 passed
GLOBAL=21731 passed, 1 warning
RUFF_GLOBAL=837 findings, unchanged from pre-phase baseline
RUFF_NEW_FINDINGS=0
TOUCHED_RUFF=PASS
TOUCHED_FORMAT=PASS
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
```

Those results are implementation evidence rather than independently replayed execution.

Crucially, every MAJOR below was reproduced independently with targeted probes that import only the audited `kernel.llm` surface and therefore do not depend on the missing `libcst`.

---

# 5. Architecture and scope review

## 5.1 Canonical ownership — PASS

The gateway stores the exact supplied:

```text
ProviderRegistry
ModelCatalog
```

and explicitly rejects a catalog bound to a different registry.

`cmm.platform.canonical.model_gateway_binding` composes the gateway as:

```text
model.gateway
```

with the canonical:

```text
provider.registry
```

dependency.

No second production `ProviderRegistry`, `ModelCatalog` or `ModelRouter` was found.

```text
CANONICAL_PROVIDER_AUTHORITY=PASS
CANONICAL_MODEL_CATALOG_AUTHORITY=PASS
PARALLEL_PROVIDER_REGISTRY=NONE
PARALLEL_MODEL_CATALOG=NONE
PARALLEL_ROUTING_POLICY_ENGINE=NONE
```

## 5.2 Kernel / CMM dependency direction — PASS

The `kernel.llm` gateway does not import `cmm`.

Privacy, fallback and agent-run evidence are reached through narrow injected/projected adapters under:

```text
cmm/agent_runtime/
```

This preserves the intended dependency direction.

## 5.3 Real multimodal content — PASS

`ModelInputPart` carries real bytes, calculates the content SHA-256 itself and excludes raw content from ordinary public serialization.

The acceptance fixtures carry real deterministic image and PDF bytes.

No gateway-owned arbitrary filesystem loader, URL fetcher or artifact store was introduced.

```text
REAL_IMAGE_BYTES=PASS
REAL_DOCUMENT_BYTES=PASS
ARBITRARY_PATH_LOADING=ABSENT
ARBITRARY_URL_FETCHING=ABSENT
```

## 5.4 Reasoning effort — PASS for explicit execution

The public enum is closed:

```text
DEFAULT
NONE
LOW
MEDIUM
HIGH
EXTRA_HIGH
```

Unsupported explicit effort fails before provider execution.

Provider-native effort translation remains adapter-local.

No silent downgrade / upgrade was found in the normal explicit path.

## 5.5 Tool execution authority — PASS

The Model Gateway normalizes tool declarations/calls but exposes no tool executor.

A model-generated tool call carries no approval, permission or execution state.

The MAJOR below concerns fail-closed transport behavior in the legacy wrapper, not tool execution authority.

## 5.6 Hidden reasoning boundary — PASS

No public response or stream contract contains a raw chain-of-thought carrier.

The gateway exposes safe reasoning metadata only.

---

# 6. MAJOR findings

## 6.1 MAJOR-01 — AUTO selection stops on a privacy-denied candidate instead of trying the next canonical match

### Evidence

AUTO resolution is performed by:

```text
kernel/llm/model_gateway.py:1129-1160
```

It calls:

```python
matches = find_matching_models(
    self._model_catalog,
    self._provider_registry,
    self._requirements(request),
)
```

then returns the first candidate that passes only:

```text
_validate_capabilities
_validate_modalities
```

The gateway's `_requirements(...)` at:

```text
kernel/llm/model_gateway.py:914-932
```

does not project the request's effective privacy into the existing `ModelRequirements` privacy field.

The actual canonical privacy decision is delayed until `_plan(...)`:

```text
kernel/llm/model_gateway.py:1094-1104
```

after AUTO has already selected one candidate.

### Independent adversarial reproduction

The audited code was instantiated with:

```text
remote model: cheaper, otherwise compatible
local model: more expensive, otherwise compatible
selection_mode=AUTO
privacy=LOCAL_ONLY equivalent injected gate
```

Observed:

```text
error=PRIVACY_DENIED
remote_calls=0
local_calls=0
```

The remote candidate is correctly denied before provider I/O, but AUTO stops instead of trying the already-ranked compatible local candidate.

### Why this is MAJOR

This violates the canonical automatic-selection invariant that privacy remains authoritative during delegated model choice.

It also means CMMChat or another client can ask CMM OS to choose automatically under a restrictive privacy policy and receive a false "no executable path" outcome even though a compliant local model exists.

No new routing intelligence is needed to fix this.

### Required remediation

Keep the order returned by the canonical `find_matching_models(...)` path, but evaluate each candidate through the gateway-owned hard execution gates before selecting it.

At minimum AUTO candidate iteration must account for:

```text
reasoning effort
document modalities
canonical privacy
adapter availability
stale provider authority
provider/model execution availability
```

without re-ranking.

Add adversarial tests:

```text
AUTO + LOCAL_ONLY + cheaper remote first + valid local second -> local executes
AUTO + first candidate has no adapter + valid second candidate -> second executes
AUTO does not introduce new ranking/scoring policy
```

```text
MAJOR_01=OPEN
```

---

## 6.2 MAJOR-02 — Cancellation token is dropped when authorized fallback begins

### Evidence

The primary execution receives the caller's cancellation token.

When fallback begins, `_execute_authorized_fallback(...)` invokes:

```text
kernel/llm/model_gateway.py:833-839
```

with:

```python
self._execute_adapter(
    candidate_plan,
    self._provider_request(request, candidate_plan),
    request,
    None,
)
```

The caller's cancellation token is explicitly replaced by `None`.

### Independent adversarial reproduction

A primary adapter was made to:

1. cancel the real `ModelCallCancellation`;
2. raise a retryable `PROVIDER_FAILURE`.

An explicitly authorized fallback candidate was then available.

Observed:

```text
response=ok:fallback
token_cancelled=True
fallback_calls=1
```

The gateway successfully executed the fallback after the model call had already been cancelled.

### Why this is MAJOR

Cancellation belongs to the model call, not to one provider attempt.

Executing fallback work after the user cancelled the call violates:

```text
DP-121 bounded cancellation/failover semantics
no later model work after cancellation
cooperative cancellation ownership
```

It can also consume provider resources after a user-requested stop.

### Required remediation

Thread the same cancellation token through the complete call lifecycle:

```text
primary
retry
fallback planning
fallback preflight
fallback execution
```

Check cancellation:

```text
before fallback planning
before each fallback candidate preflight
before each adapter invocation
after any retry backoff
```

A cancelled call must end with:

```text
MODEL_CALL_CANCELLED
```

and:

```text
fallback adapter call count = 0
```

when cancellation is already effective.

Add an adversarial acceptance/regression case combining cancellation with fallback.

```text
MAJOR_02=OPEN
```

---

## 6.3 MAJOR-03 — Streaming timeout can emit content after the deadline and cannot bound a blocking `next()`

### Evidence

The streaming loop checks the deadline at:

```text
kernel/llm/model_gateway.py:383-405
```

and then calls:

```python
adapter_event = next(adapter_events)
```

at:

```text
kernel/llm/model_gateway.py:406-407
```

If `next()` blocks beyond the deadline, the gateway cannot observe the timeout until the provider yields again.

Once the late event returns, it is processed immediately as content at:

```text
kernel/llm/model_gateway.py:433-452
```

without re-checking the deadline first.

The reference document itself records this as:

```text
docs/reference/phase-11-model-gateway.md:360-362
```

> Timeout and cancellation are enforced between events; a provider that blocks inside a single chunk is not interruptible except by adapter cooperation.

That is a real limitation, but it contradicts the frozen gateway timeout contract rather than merely documenting an optional degradation.

### Independent adversarial reproduction

A streaming adapter:

```text
yield STARTED
sleep 0.12s
yield CONTENT_DELTA("LATE")
```

was executed with:

```text
timeout_seconds=0.05
```

Observed:

```text
elapsed=0.12s
events=[
  STARTED,
  CONTENT_DELTA("LATE"),
  ERROR(PROVIDER_TIMEOUT)
]
```

Therefore content is emitted after the call's declared timeout.

### Why this is MAJOR

The frozen design assigns per-model-call timeout enforcement to the gateway.

The current stream can:

- exceed the deadline while blocked;
- emit late content after the deadline;
- only report timeout afterward.

The existing timeout test asserts the terminal error but does not assert that late content is suppressed.

### Required remediation

Introduce a bounded mechanism for acquiring the next provider stream event or otherwise guarantee adapter cooperation through an internally owned cancellation/deadline token.

At minimum:

```text
no CONTENT_DELTA / TOOL_CALL_DELTA / USAGE may be emitted after the deadline
timeout must notify cooperative adapters
timeout terminal must be emitted exactly once
a blocking provider event must not make the public gateway wait without bound
```

Add an adversarial test that explicitly asserts:

```text
"LATE" not emitted after deadline
```

and a blocking-event test with a bounded elapsed-time expectation.

```text
MAJOR_03=OPEN
```

---

## 6.4 MAJOR-04 — Legacy provider adapter silently drops tools and structured-output requirements

### Evidence

`LLMProviderModelAdapter.execute(...)` at:

```text
kernel/llm/model_provider_adapter.py:731-779
```

explicitly refuses:

```text
non-text inputs
explicit reasoning effort
```

but does not reject:

```text
request.tools
request.structured_output
```

It then converts the call into the legacy contract:

```python
LLMRequest(
    prompt=prompt,
    system_prompt=None,
    temperature=0.0,
    metadata={},
)
```

which has no transport for the requested tool definitions or structured-output requirement.

### Independent adversarial reproduction

A `ProviderModelRequest` carrying both:

```text
tools=(...)
structured_output=StructuredOutputRequirement(...)
```

was sent directly through the audited `LLMProviderModelAdapter`.

Observed:

```text
content=plain
tool_calls=()
structured_output=None
```

No error was raised.

### Why this is MAJOR

The wrapper exists specifically so current first-party/legacy provider implementations can participate in the new gateway without being forked.

If the canonical model metadata advertises tool or structured-output capability while the wrapped legacy transport cannot carry it, the adapter silently degrades the request instead of failing closed.

A provider adapter must either translate a requested canonical feature or reject it explicitly.

### Required remediation

Before invoking the wrapped `LLMProvider`, fail closed when the legacy transport cannot represent:

```text
tools
structured_output
```

unless real translation support is implemented.

Use safe canonical errors such as:

```text
CAPABILITY_UNSUPPORTED
```

or another already-approved gateway error that accurately represents the boundary failure.

Add tests proving provider `generate()` is not called for unsupported tools/structured output.

```text
MAJOR_04=OPEN
```

---

## 6.5 MAJOR-05 — New Phase 11.21 model capabilities are lost across the canonical Provider Registry persisted-state round trip

### Evidence

Phase 11.21 extends canonical `ModelCapabilities` with:

```text
kernel/llm/capabilities.py:56-58

reasoning_efforts
document_media_types
streaming
```

The canonical Phase 11.34 provider-state serializer at:

```text
kernel/llm/provider_state.py:519-549
```

persists only the older boolean capability set.

`_MODEL_CAPABILITY_NAMES` at:

```text
kernel/llm/provider_state.py:552-562
```

does not contain the Phase 11.21 fields.

The deserializer therefore reconstructs them with their fail-closed defaults:

```text
reasoning_efforts=()
document_media_types=()
streaming=False
```

### Independent adversarial reproduction

A `ModelSpec` with:

```text
reasoning_efforts=(HIGH,)
document_media_types=("application/pdf",)
streaming=True
```

was serialized and reconstructed using the audited canonical model-state helpers.

Observed:

```text
serialized_capabilities={
  reasoning: True,
  ...old boolean fields only...
}

restored_reasoning_efforts=()
restored_document_media_types=()
restored_streaming=False
```

### Why this is MAJOR

This is not merely a display limitation.

The closed Phase 11.34 persisted-state aggregate claims to persist canonical model catalog entries and reconstruct accepted state exactly. Phase 11.21's new capability truth is now part of those canonical model entries.

After a provider-state round trip, models lose the exact capabilities required for:

```text
reasoning-effort controls
PDF/document capability truth
provider token streaming capability truth
```

and therefore fail closed after restart even though the canonical pre-persistence model supported them.

The frozen design prohibited changing Provider Registry **ownership/persistence authority**. It did not prohibit extending the existing canonical state representation under that same authority.

### Required remediation

Extend the existing Phase 11.34 provider-state representation under the same canonical owner.

Do not create a second store.

The remediation must explicitly decide and test the repository's versioning policy for the extended capability shape while preserving fail-closed semantics.

Required round-trip acceptance:

```text
reasoning_efforts survives capture -> serialize -> deserialize -> restore
document_media_types survives capture -> serialize -> deserialize -> restore
streaming survives capture -> serialize -> deserialize -> restore
AT-DP-134 remains green
```

Document the additive closed-phase seam.

```text
MAJOR_05=OPEN
```

---

# 7. MINOR finding

## 7.1 MINOR-01 — Reference and gate documentation contains stale acceptance path and focused test count

### Evidence

The reference header says:

```text
docs/reference/phase-11-model-gateway.md:7

tests/llm/test_phase_11_21_dp121_acceptance.py
```

but the actual acceptance file is:

```text
tests/llm/test_phase11_21_dp121_acceptance.py
```

Later sections use the correct path.

The final reference/roadmap/requirements-matrix evidence also reports:

```text
focused gateway suite = 366 passed
```

while the final implementation evidence reports:

```text
focused gateway suite = 371 passed
```

The final HEAD contains the later AUTO-selection test block added after the earlier 366-count documentation.

### Required remediation

Correct the acceptance path and refresh final focused-gate evidence consistently across:

```text
docs/reference/phase-11-model-gateway.md
docs/roadmap/phase-11-stable-integrated-platform.md
docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md
```

using the new Remediation V1 exact-HEAD results.

```text
MINOR_01=OPEN
```

---

# 8. Review of the implementer's three explicit judgement calls

## 8.1 Capability persistence — NOT ACCEPTED AS A CLOSURE-SAFE KNOWN LIMIT

The fail-closed default after state restoration is safer than guessing, but it still discards canonical capability truth and breaks core 11.21 functionality after persistence.

This is recorded as `MAJOR-05`.

The remediation must extend the existing state owner, not create new persistence.

## 8.2 AUTO selection implementation — ARCHITECTURAL APPROACH ACCEPTED, HARD-GATE FILTERING INCOMPLETE

Using `find_matching_models(...)` and preserving its canonical ordering is the correct architectural direction.

No 11.35 routing policy engine was introduced.

However AUTO currently returns the first capability/modality match before gateway-owned privacy/execution gates are applied across the candidate set.

This is recorded as `MAJOR-01`.

## 8.3 Superseded pre-submission bundles — ACCEPTED, NO FINDING

The only submitted artifact for this audit is:

```text
cmm-phase11-21-model-gateway-implementation-811d82875a98.tar.gz
```

Its SHA, embedded Git archive commit and reconstructed tree all match.

No earlier bundle was submitted to this independent audit, so removing superseded local pre-submission bundles did not rewrite historical audit evidence.

```text
BUNDLE_DISCIPLINE=PASS
```

---

# 9. DP-121 verification result

The design point requires one canonical gateway that, among other properties:

```text
supports bounded timeout/cancellation/failover mechanics
enforces canonical privacy
normalizes tools/structured output
consumes canonical persistent model/provider truth
```

Canonical ownership and most provider-independent contracts are implemented, but the independently reproduced majors mean the design point is not yet fully satisfied.

```text
DP_121=NOT_VERIFIED
```

---

# 10. AT-DP-121 verification result

The implementation evidence reports:

```text
AT_DP_121=31 passed
```

The acceptance construction is materially connected and correctly uses:

```text
real ProviderRegistry
real ModelCatalog
real Phase 11.1 composition
real ModelGateway
official in-memory provider adapter
real canonical privacy adapter
```

However:

- the audit environment cannot independently replay the test due missing `libcst`;
- the current acceptance does not expose the AUTO/privacy interaction;
- it does not combine cancellation with fallback;
- its stream timeout regression does not prohibit late post-deadline content;
- it does not exercise legacy-wrapper tools/structured fail-closed behavior;
- it does not test persistence round-trip of the Phase 11.21 capability fields.

Therefore:

```text
AT_DP_121=PASS_LOCAL_EVIDENCE_ONLY
INDEPENDENT_AT_DP_121_VERIFICATION=INSUFFICIENT_FOR_CLOSURE
```

Remediation V1 must add connected/adversarial coverage for the open MAJOR findings.

---

# 11. Security and fail-closed review

Positive findings:

```text
RAW_ATTACHMENT_SERIALIZATION=BLOCKED
SECRET_SHAPED_METADATA=SCREENED
HIDDEN_REASONING_PUBLIC_FIELD=ABSENT
REMOTE_PRIVACY_DENIAL_BEFORE_PROVIDER_IO=PASS_FOR_EXPLICIT_PATH
TOOL_EXECUTION_AUTHORITY=ABSENT
PROVIDER_NATIVE_REASONING_NAMES_PUBLICLY_HIDDEN=PASS
EXPLICIT_REASONING_DOWNGRADE=BLOCKED
EXPLICIT_MODEL_SILENT_SUBSTITUTION=BLOCKED
```

No BLOCKER-level credential, secret, arbitrary-file-read, arbitrary-network-fetch, authority-duplication or tool-execution issue was found.

The fail-closed defects recorded as MAJOR are substantial but narrowly remediable.

---

# 12. Scope and architecture conclusion

The implementation stayed inside the intended product boundary:

```text
11.35 Routing Policy Engine=NOT_IMPLEMENTED
11.36 Evaluation Framework=NOT_IMPLEMENTED
11.38 Cost Management Layer=NOT_IMPLEMENTED
11.44 Usage Audit persistence=NOT_IMPLEMENTED
11.50 reusable client interfaces=NOT_IMPLEMENTED
CMMChat changes=NONE
CMM Bots changes=NONE
MCP/Actions=NONE
Computer Use=NONE
new privacy engine=NONE
new validation engine=NONE
new application backend=NONE
```

The remediation therefore does not require a redesign of Phase 11.21.

It should be a narrow correction cycle.

---

# 13. Remediation V1 required scope

Remediation V1 must address exactly:

```text
MAJOR_01 AUTO candidate hard-gate iteration
MAJOR_02 cancellation propagation through fallback
MAJOR_03 real streaming deadline enforcement / no late content
MAJOR_04 legacy adapter fail-closed tools/structured behavior
MAJOR_05 canonical persisted capability round-trip
MINOR_01 documentation/path/final gate evidence
```

It must not introduce:

```text
new routing policy
new provider registry
new model catalog
new persistence owner
new privacy engine
new validation system
11.50 client API
CMMChat changes
```

Inherited acceptances:

```text
AT-DP-134
AT-DP-101
AT-DP-102
AT-DP-103
AT-DP-104
AT-DP-105
```

must remain green.

---

# 14. Required Re-audit V2 evidence

The next exact-HEAD bundle must demonstrate:

```text
AUTO_LOCAL_ONLY_REMOTE_FIRST_LOCAL_SECOND=PASS
AUTO_MISSING_ADAPTER_TRIES_NEXT_CANONICAL_CANDIDATE=PASS

CANCELLED_PRIMARY_NEVER_EXECUTES_FALLBACK=PASS
CANCELLATION_PROPAGATES_TO_RETRY_AND_FALLBACK=PASS

STREAM_TIMEOUT_NO_POST_DEADLINE_CONTENT=PASS
STREAM_BLOCKING_NEXT_IS_BOUNDED_OR_COOPERATIVELY_INTERRUPTED=PASS

LEGACY_TOOLS_UNSUPPORTED_FAILS_BEFORE_PROVIDER_IO=PASS
LEGACY_STRUCTURED_OUTPUT_UNSUPPORTED_FAILS_BEFORE_PROVIDER_IO=PASS

MODEL_CAPABILITY_REASONING_EFFORT_PERSISTENCE_ROUNDTRIP=PASS
MODEL_CAPABILITY_DOCUMENT_MEDIA_TYPES_PERSISTENCE_ROUNDTRIP=PASS
MODEL_CAPABILITY_STREAMING_PERSISTENCE_ROUNDTRIP=PASS
AT_DP_134=PASS

REFERENCE_ACCEPTANCE_PATH=CORRECT
FOCUSED_GATE_EVIDENCE=EXACT_FINAL_HEAD

AT_DP_121=PASS
GLOBAL_TESTS=PASS
RUFF_NEW_FINDINGS=0
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
WORKTREE=CLEAN
```

---

# 15. Final Audit V1 status

```text
INDEPENDENT_AUDIT_V1=FAIL

BLOCKERS=0
MAJORS=5
MINORS=1

F11_020=IMPLEMENTED_REMEDIATION_REQUIRED
DP_121=NOT_VERIFIED
AT_DP_121=PASS_LOCAL_EVIDENCE_ONLY
CLOSURE_ELIGIBLE=NO

AUDITED_HEAD=811d82875a982e43fbb4fde11cf54b342b2c94a3
AUDITED_TREE=153e4e458a6136a41f6807d41de66f53e7ae288f
AUDITED_BUNDLE_SHA256=1b5f1022c9ede049c963eff120395ce0ba9567215f185e30c7aa965007a877f3

NEXT=PHASE11_21_REMEDIATION_V1
```

Phase 11.21 must remain **implemented and pending remediation/re-audit**, not closed.
