# Phase 11.50 — Reusable Backend Interfaces — Independent Audit V1

**Project:** CMM OS  
**Phase:** 11.50 — Reusable Backend Interfaces  
**Requirement:** `F11-021 — Reusable First-Party Backend Interface`  
**Design Point:** `DP-150 — Canonical Reusable Client Backend Interface`  
**Acceptance:** `AT-DP-150 — Canonical Reusable Client Backend Interface Acceptance`  
**Audit:** Independent Audit V1  
**Date:** 2026-09-25  
**Auditor:** ChatGPT, independent of the implementation agent

---

## 1. Final verdict

```text
INDEPENDENT_AUDIT_V1=FAIL

AUDITED_HEAD=ed7bdc6f9c48ff94375613bb80c23ad10599710c
AUDITED_TREE=c065eb3d78ff19120a64b9e9eb1fff8311a59224
AUDITED_BUNDLE_SHA256=fa2ed501bdd5ba6ba87dfdbe713d12e3f37644bd200d73d598487be4862f3654

BLOCKERS=0
MAJORS=5
MINORS=1

MAJOR_01=PUBLIC_CANONICAL_OWNER_ACCESSORS_CREATE_A_CLIENT_ESCAPE_HATCH_AROUND_THE_CLOSED_PHASE11_50_OPERATION_AND_VERSION_BOUNDARY
MAJOR_02=EXACT_CANONICAL_OWNER_TYPE_REQUIREMENT_IS_NOT_ENFORCED_BECAUSE_SUBCLASSES_ARE_ACCEPTED
MAJOR_03=CANONICAL_APPLICATION_AND_CONVERSATION_FAILURES_ARE_LOSSILY_RECODED_AS_INTERNAL_CLIENT_ERROR_ON_REAL_CLIENT_PATHS
MAJOR_04=CAPABILITY_MANIFEST_CONTRADICTS_THE_FROZEN_ATTACHMENT_AND_RESPONSE_EVENT_STREAM_TRUTH
MAJOR_05=CLIENT_REQUEST_SERIALIZATION_IS_NOT_PRIMITIVE_SAFE_OR_JSON_NATIVE_FOR_CANONICAL_PAYLOAD_VALUES

MINOR_01=IMPLEMENTER_REPORT_START_HEAD_AND_COMMIT_COUNT_ARE_INCONSISTENT_WITH_THE_FROZEN_AGENT_HANDOFF

F11_021=IMPLEMENTED_REMEDIATION_REQUIRED
DP_150=NOT_VERIFIED
AT_DP_150=FAIL_INDEPENDENT
CLOSURE_ELIGIBLE=NO

NEXT=PHASE11_50_REMEDIATION_V1
```

The architecture is salvageable without redesign: the canonical owners are reused, no second backend/store/router/runtime was found, and the five MAJOR findings are local to the new facade contract, its capability projection, and its acceptance coverage.

---

## 2. Audited artifact

Bundle:

```text
cmm-phase11-50-reusable-backend-ed7bdc6f9c48.tar.gz
```

Independent SHA-256:

```text
fa2ed501bdd5ba6ba87dfdbe713d12e3f37644bd200d73d598487be4862f3654
```

Archive facts:

```text
ENTRIES=2628
UNSAFE_ARCHIVE_MEMBERS=0
SYMLINKS=0
HARDLINKS=0
EMBEDDED_GIT_ARCHIVE_HEAD=ed7bdc6f9c48ff94375613bb80c23ad10599710c
```

The Git tree was independently reconstructed from the TAR member bytes and Git-relevant TAR modes:

```text
RECONSTRUCTED_TREE=c065eb3d78ff19120a64b9e9eb1fff8311a59224
DECLARED_TREE=c065eb3d78ff19120a64b9e9eb1fff8311a59224
TREE_IDENTITY=PASS
```

Therefore the archive is an exact committed Git tree matching the implementation report.

---

## 3. Governing artifact integrity

Frozen Phase 11.50 design:

```text
docs/superpowers/specs/2026-09-25-phase-11.50-reusable-backend-interfaces-design.md
SHA256=d0296a5de7b0afcc3f3595ade1982d0ed140d9aa3a699afbfffab184a12150c6
```

Frozen Phase 11.50 plan:

```text
docs/superpowers/plans/2026-09-25-phase-11.50-reusable-backend-interfaces-implementation-plan.md
SHA256=369a27f7e0128d2b56bb4f2f575e45179329229a78c8c4bfc4a7922aaaf0db0e
```

Both hashes match exactly.

The final Phase 11.21 independent Re-audit V3 report also remains intact:

```text
docs/audits/phase-11.21-model-gateway-independent-reaudit-v3.md
SHA256=684c7abd94e8c4c21978862c8178a7f3def35ffcb702eb46b6cee5fa83fcf852
```

No Phase 11.21 historical audit mutation was observed.

---

## 4. Positive architecture findings

The implementation correctly establishes a narrow package:

```text
cmm/client_backend/
```

with:

```text
__init__.py
contracts.py
capabilities.py
interface.py
platform_module.py
```

No client-backend-owned:

```text
store
repository
registry
router
runtime
engine
resolver
manager
executor
provider dispatcher
model execution path
HTTP server
event bus
```

was found.

The package imports the canonical:

```text
ApplicationGateway
ConversationService
ApplicationCapability
ConversationCapabilityState
Phase 11.1 composition contracts
```

and does not directly import or execute:

```text
kernel.llm.ModelGateway
ProviderRegistry
ModelCatalog
Orchestrator
cmm.api
CMMChat
web frameworks
```

The composition contribution declares:

```text
client.backend
```

with downward dependencies:

```text
application.gateway
conversation.service
```

and no `model.gateway` execution dependency.

```text
ANTI_FRAGMENTATION_BASELINE=PASS
SECOND_APPLICATION_BACKEND=NO
SECOND_CONVERSATION_SERVICE=NO
DIRECT_MODEL_GATEWAY_IMPORT=NO
PHASE11_51=NOT_IMPLEMENTED
CMMCHAT_CODE_CHANGES=NONE
```

---

## 5. Independent static/test replay

The audit environment does not contain the repository-declared `libcst` dependency, so the full repository test graph cannot be collected directly.

An inert import-only `libcst` shim was used solely to satisfy unrelated import-time references; no LibCST execution path was used by the audited Phase 11.50 probes.

Independent replay obtained:

```text
CLIENT_BACKEND_CONTRACT_AND_ARCHITECTURE_TESTS=66 passed
COMPILEALL_RELEVANT_DIRS=PASS
TRAILING_WHITESPACE_HITS=0
```

The broader focused suite begins successfully under that shim but later reaches an unrelated pre-existing Python 3.13/dataclass-slots `super()` failure while constructing the domain graph. Therefore the implementation agent's exact-head suite counts are treated as local execution evidence, not independently replayed full-suite evidence.

Local exact-head evidence recorded in the repository reports:

```text
CLIENT_BACKEND_TESTS=157 passed
AT_DP_150=17 passed
APPLICATION_SUITE=674 passed
CONVERSATION_SUITE=860 passed
LLM_SUITE=1153 passed
GLOBAL_TESTS=21940 passed, 0 failed
RUFF_GLOBAL_BASELINE=837
RUFF_GLOBAL_FINAL=837
RUFF_NEW_FINDINGS=0
```

No audit finding below depends on the unavailable full replay: each MAJOR was reproduced independently or proven directly from the exact audited source.

---

# 6. MAJOR-01 — public canonical-owner escape hatch

Frozen Phase 11.50 design requires a stable explicit closed facade:

```text
Only the frozen Phase 11.50 operations are accepted.
```

The frozen operation set is:

```text
capabilities
create_session
get_session
load_conversation
submit_message
edit_message
regenerate_response
cancel_request
```

However `ClientBackend` publicly exposes:

```python
@property
def gateway(self) -> ApplicationGateway:
    return self._gateway

@property
def conversation(self) -> ConversationService:
    return self._conversation
```

The implementation also adds:

```python
ConversationService.gateway
```

which returns the exact canonical `ApplicationGateway`.

The accessors are described as "read-only", but the returned objects are live authority-bearing service objects. Returning an `ApplicationGateway` does not merely reveal identity: it exposes its `handle(...)` entrypoint.

Independent adversarial reproduction on the exact audited code:

```text
FROZEN_CLIENT_OPERATIONS=
[
  capabilities,
  create_session,
  get_session,
  load_conversation,
  submit_message,
  edit_message,
  regenerate_response,
  cancel_request
]

HEALTH_IN_CLIENT_OPS=False

client.gateway.handle(
    ApplicationQuery(operation=ApplicationOperation.HEALTH_GET, ...)
)

BYPASS_CALLS=['health.get']
BYPASS_STATUS=success
```

Therefore a first-party client holding only the supposedly closed `ClientBackend` can escape the Phase 11.50 version/operation contract and invoke an application operation that is not in `ClientOperation`.

This violates the frozen design's explicit/closed interface rule and makes the acceptance's use of public owner accessors self-defeating.

Required remediation direction:

```text
do not expose live canonical owners through the public ClientBackend surface
do not return ApplicationGateway or ConversationService to first-party clients
retain owner-identity verification through private/test-safe identity evidence
remove/narrow ConversationService.gateway if it is only present for Phase 11.50 identity inspection
add an adversarial acceptance asserting a public-only client cannot obtain/call ApplicationGateway.handle
```

```text
MAJOR_01=OPEN
```

---

# 7. MAJOR-02 — exact canonical owner types are not exact

Frozen design section 9 states:

```text
Construction must require the exact official owner types.
```

Current construction uses:

```python
if not isinstance(gateway, ApplicationGateway):
    ...

if not isinstance(conversation, ConversationService):
    ...
```

`isinstance(...)` accepts subclasses.

Independent adversarial reproduction:

```text
class GatewaySubclass(ApplicationGateway):
    ...

class ConversationSubclass(ConversationService):
    ...

ClientBackend(
    gateway=GatewaySubclass instance,
    conversation=ConversationSubclass instance wired to that gateway
)
```

Observed:

```text
SUBCLASS_ACCEPTED=True
gateway_type=GatewaySubclass
conversation_type=ConversationSubclass
```

A subclass may override authority-bearing methods while still satisfying the current gates. This does not meet "exact official owner types" and weakens the anti-fragmentation invariant.

The composition builder repeats the same issue:

```python
if not isinstance(service, ClientBackend):
```

so an arbitrary `ClientBackend` subclass may claim the canonical `client.backend` service identity.

Required remediation direction:

```text
enforce exact canonical types where the frozen design requires exact owner identity
cover ApplicationGateway subclass rejection
cover ConversationService subclass rejection
cover ClientBackend subclass rejection at composition binding
retain official canonical in-memory construction path without subclassing
```

```text
MAJOR_02=OPEN
```

---

# 8. MAJOR-03 — canonical failures are lossily re-coded

Frozen design sections 24-25 require:

```text
The interface must project safe public failures.

Prefer reuse/projection from:
ApplicationError
ConversationErrorCode

Only client-interface-specific failures may use client-interface-specific codes.

Do not duplicate/recode canonical:
CONFLICT
NOT_FOUND
CAPABILITY_UNAVAILABLE
POLICY_DENIED
APPROVAL_REQUIRED
CANCELLED
```

The implementation contains a safe helper:

```python
ClientBackend.project_canonical_failure(...)
```

but the actual client execution paths do not consistently use it.

For session operations, `_application_session_from_response(...)` calls:

```python
raise ClientBackendError(_client_error_code_for(error))
```

and `_client_error_code_for(...)` maps every canonical application failure except `INVALID_REQUEST` and `UNSUPPORTED_VERSION` to:

```text
INTERNAL_CLIENT_ERROR
```

Independent exact-code reproduction with a canonical `RESOURCE_NOT_FOUND` response:

```text
DIRECT_SESSION_ERROR=
ClientBackendError
code=INTERNAL_CLIENT_ERROR

DISPATCH_SESSION_ERROR=
{
  code: INTERNAL_CLIENT_ERROR,
  message: "Client backend request failed closed"
}
```

Independent reproduction of a canonical conversational `SESSION_CONFLICT` through generic `dispatch(...)`:

```text
DISPATCH_CONVERSATION_ERROR=
{
  code: INTERNAL_CLIENT_ERROR,
  message: "Client backend request failed closed"
}
```

The generic dispatcher catches every non-`ClientBackendError` exception as an unknown internal exception:

```python
except Exception:
    ... INTERNAL_CLIENT_ERROR
```

so canonical conversational errors are erased there too.

The connected `AT-DP-150` Scenario G does not test this real path. Instead it:

1. calls `project_canonical_failure(...)` directly with a synthetic canonical exception;
2. separately proves a typed direct `submit_message(...)` call can raise `ConversationSessionConflictError`;
3. tests a truly unknown runtime failure through `dispatch(...)`.

That leaves the actual canonical-error-through-generic-client-path untested.

Required remediation direction:

```text
preserve/project canonical application and conversation error code/message on real facade and dispatch paths
use client-specific codes only for client-interface-specific failures
keep unknown internal failures mapped to INTERNAL_CLIENT_ERROR
connect Scenario G to a real canonical failure traversing ClientBackend/dispatch
add session NOT_FOUND/CONFLICT and conversation conflict adversarial coverage
```

```text
MAJOR_03=OPEN
```

---

# 9. MAJOR-04 — capability truth contradicts the frozen design

Capability truth is a load-bearing part of `DP-150`.

Frozen design/plan requires:

```text
attachments=DEGRADED/reference_only
document_upload=UNAVAILABLE
```

and, because a public response-event SSE boundary already exists:

```text
response_event_stream=AVAILABLE
```

while provider/conversation token streaming remains separately unavailable/degraded.

The audited implementation projects the Phase 11.5 `ConversationCapabilityStatus` mechanically:

```python
AVAILABLE -> ClientBackendCapabilityStatus.AVAILABLE
DEGRADED -> ClientBackendCapabilityStatus.DEGRADED
```

Independent projection on the exact code produces:

```text
attachments=available
response_event_stream=degraded
document_upload=unavailable
end_to_end_token_stream=degraded
```

The attachment row is especially significant because Phase 11.5 explicitly says:

```text
attachments = AVAILABLE
effective = reference_only
```

and the same service explicitly states attachment references stay only in conversation state and never enter the application message payload.

The Phase 11.50 manifest drops the `effective=reference_only` qualifier and exposes only:

```text
attachments=available
```

with no attachment reason/effective mode.

A first-party client therefore cannot distinguish "reference-only conversational metadata" from real attachment reachability, directly contradicting the frozen Phase 11.50 ruling.

Likewise, the dedicated `response_event_stream` field is set to `degraded` solely because the older generic Phase 11.5 `response_streaming` row is degraded by absence of provider token streaming. This collapses two truths that the Phase 11.50 design deliberately separated:

```text
response-event stream exists
provider token stream does not
```

The connected `AT-DP-150` Scenario E codifies the implementation's incorrect attachment status:

```python
assert manifest.attachments is ClientBackendCapabilityStatus.AVAILABLE
```

so local acceptance success does not verify the frozen DP.

Required remediation direction:

```text
project attachment references as DEGRADED/reference_only, not AVAILABLE
preserve the reference_only qualifier in client-visible capability evidence
project response_event_stream independently from token-stream availability
keep token-stream truth in its dedicated model/end-to-end rows
update Scenario E to assert frozen design truth rather than implementation truth
```

```text
MAJOR_04=OPEN
```

---

# 10. MAJOR-05 — request serialization is not primitive-safe

Frozen design section 26 requires every public wrapper to:

```text
serialize deterministically
use primitive-safe values
preserve canonical identities
```

The request envelope permits canonical public dataclass values in its payload.

`_primitive_safe(...)` intentionally passes such dataclass values through unchanged:

```python
if _is_canonical_payload_value(value):
    return value
```

but `_thaw(...)` handles only:

```text
Mapping
tuple
Enum
```

and otherwise returns the value unchanged.

Therefore:

```python
ClientBackendRequest.to_dict()
```

is not actually a plain/JSON-native representation when a canonical value is present.

Independent exact-code reproduction:

```text
payload.message type after request.to_dict():
ConversationMessage
```

and:

```text
json.dumps(request.to_dict())
→ TypeError:
  Object of type ConversationMessage is not JSON serializable
```

This affects the primary `SUBMIT_MESSAGE` envelope shape because that operation expects a canonical `ConversationMessage` in the payload.

The contract docstring itself claims `_thaw(...)` returns:

```text
a fresh, plain, JSON-native representation
```

which is false for the supported canonical payload case.

Required remediation direction:

```text
serialize canonical public values through their canonical safe to_dict()/serialized representation
recurse into that representation with the same primitive-safe rules
preserve canonical IDs/timestamps/revisions exactly
add JSON serialization tests for SUBMIT_MESSAGE, EDIT_MESSAGE and any other canonical-value payloads
keep binary/callable/opaque objects fail-closed
```

```text
MAJOR_05=OPEN
```

---

# 11. MINOR-01 — implementer evidence metadata is inconsistent

The frozen implementation-agent handoff started from:

```text
663ced447f96580e9c524b352db7f7206d5b291e
```

because that is the committed Phase 11.50 plan HEAD.

The implementation report instead prints:

```text
PHASE11_50_START_HEAD=f15fc8975359dd94b3028fecae9e51b059ed8f53
```

and then separately explains that the repository was actually at `663ced4`.

The report also labels the implementation history:

```text
Commit (6)
```

while listing seven commit identifiers:

```text
b133515
2207ced
4e040c1
a4a658e
207d35f
0a6f0e3
ed7bdc6
```

This does not corrupt the exact audited bundle, but the implementation evidence should be internally consistent.

Required remediation:

```text
future remediation report must use the actual frozen remediation start HEAD
report exact commit count
do not rewrite historical audit artifacts
```

```text
MINOR_01=OPEN
```

---

# 12. Acceptance assessment

Local evidence:

```text
AT_DP_150=17 passed
```

Independent review of the connected acceptance finds three material gaps:

```text
Scenario A
  proves instance identity by exposing live owners publicly;
  it does not prove the client cannot escape to those owners.

Scenario E
  asserts attachments=AVAILABLE, contradicting the frozen design's
  DEGRADED/reference_only requirement.

Scenario G
  calls project_canonical_failure(...) directly instead of proving that a real
  canonical failure traveling through the generic client path preserves its
  canonical code.
```

The serialization defect is also not covered by a JSON-native request-envelope test.

Therefore:

```text
AT_DP_150=FAIL_INDEPENDENT
```

The local green test count is preserved as evidence but does not independently verify the frozen acceptance contract.

---

# 13. Design Point assessment

The implementation demonstrates important parts of `DP-150`:

```text
one cmm.client_backend package
one facade type
canonical ApplicationGateway reuse
canonical ConversationService reuse
canonical composition dependency declarations
no second store/router/runtime
no direct ModelGateway import/execution
no CMMChat dependency
```

But the Design Point also requires:

```text
closed stable first-party interface
exact canonical owner identity
safe canonical failure projection
truthful capability manifest
stable client-safe serialization
```

Those are currently violated.

Therefore:

```text
DP_150=NOT_VERIFIED
```

---

# 14. Scope and architecture result

```text
SCOPE=PASS_WITH_REMEDIATION_REQUIRED
SECOND_BACKEND=NO
SECOND_STORE=NO
SECOND_ROUTER=NO
SECOND_RUNTIME=NO
SECOND_MODEL_GATEWAY=NO
PHASE11_51=NOT_IMPLEMENTED
CMMCHAT_CHANGES=NONE
```

The audit does not require architectural redesign.

Remediation should remain inside:

```text
cmm/client_backend
the two additive ConversationService read-only seams if needed
tests/client_backend
current Phase 11.50 documentation
```

Do not reopen Phase 11.21 or implement the post-11.50 reasoning/multimodal bridge during remediation.

---

# 15. Remediation V1 required scope

Remediation V1 should correct exactly the five MAJOR findings plus MINOR-01 evidence discipline.

Required behavioral targets:

```text
1. Public first-party facade cannot obtain a live ApplicationGateway or
   ConversationService escape hatch.

2. ClientBackend and its composition binding reject subclasses where the frozen
   contract requires exact canonical types.

3. Real canonical NOT_FOUND / CONFLICT / CAPABILITY_UNAVAILABLE /
   conversation errors preserve/project canonical safe codes on the actual client
   path; only unknown internal defects become INTERNAL_CLIENT_ERROR.

4. attachments=DEGRADED with explicit reference_only truth;
   response_event_stream reports the frozen dedicated event-stream truth;
   token-stream truth stays separate.

5. ClientBackendRequest.to_dict() is deterministic primitive/JSON-safe for
   canonical payloads such as ConversationMessage.

6. AT-DP-150 is extended so Scenarios A/E/G and serialization prove those
   behaviors through the real facade, not helper-only assertions.
```

Keep:

```text
F11-021
DP-150
AT-DP-150
```

unchanged.

No new DP is required.

---

# 16. Final V1 finding matrix

```text
BLOCKERS=0

MAJOR_01=PUBLIC_CANONICAL_OWNER_ACCESSORS_CREATE_A_CLIENT_ESCAPE_HATCH_AROUND_THE_CLOSED_PHASE11_50_OPERATION_AND_VERSION_BOUNDARY
MAJOR_02=EXACT_CANONICAL_OWNER_TYPE_REQUIREMENT_IS_NOT_ENFORCED_BECAUSE_SUBCLASSES_ARE_ACCEPTED
MAJOR_03=CANONICAL_APPLICATION_AND_CONVERSATION_FAILURES_ARE_LOSSILY_RECODED_AS_INTERNAL_CLIENT_ERROR_ON_REAL_CLIENT_PATHS
MAJOR_04=CAPABILITY_MANIFEST_CONTRADICTS_THE_FROZEN_ATTACHMENT_AND_RESPONSE_EVENT_STREAM_TRUTH
MAJOR_05=CLIENT_REQUEST_SERIALIZATION_IS_NOT_PRIMITIVE_SAFE_OR_JSON_NATIVE_FOR_CANONICAL_PAYLOAD_VALUES

MINOR_01=IMPLEMENTER_REPORT_START_HEAD_AND_COMMIT_COUNT_ARE_INCONSISTENT_WITH_THE_FROZEN_AGENT_HANDOFF

MAJORS=5
MINORS=1
```

---

# 17. Final status

```text
INDEPENDENT_AUDIT_V1=FAIL

AUDITED_HEAD=ed7bdc6f9c48ff94375613bb80c23ad10599710c
AUDITED_TREE=c065eb3d78ff19120a64b9e9eb1fff8311a59224
AUDITED_BUNDLE_SHA256=fa2ed501bdd5ba6ba87dfdbe713d12e3f37644bd200d73d598487be4862f3654

BLOCKERS=0
MAJORS=5
MINORS=1

F11_021=IMPLEMENTED_REMEDIATION_REQUIRED
DP_150=NOT_VERIFIED
AT_DP_150=FAIL_INDEPENDENT
CLOSURE_ELIGIBLE=NO

NEXT=PHASE11_50_REMEDIATION_V1
```
