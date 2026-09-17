# Phase 11.4 — CLI — Independent Audit V1

**Date:** 2026-09-17
**Auditor:** ChatGPT independent audit
**Phase:** 11.4 — CLI
**Requirement:** `F11-018 — Canonical Operational CLI`
**Design Point:** `DP-104 — Single-Front-Door Fail-Closed Operational CLI`
**Connected Acceptance:** `AT-DP-104 — Canonical CLI Integration Acceptance`
**Verdict:** `FAIL` — one remediation-required MINOR; no blockers or majors

---

## 1. Audit target

Audit bundle:

```text
cmm-phase11-4-cli-audit-74a77c3a1b4e.tar.gz
```

Uploaded duplicate copies were byte-identical.

Independent SHA-256:

```text
f7e88debf0bf376960f4b64ceb696417b0bb965ad024f86c027affed62bc2e70
```

Embedded commit:

```text
74a77c3a1b4e8e52c0de6be9463b6bba3218f2e0
```

Archive members:

```text
2538
```

Archive path/symlink inspection:

```text
UNSAFE_PATHS=0
SYMLINKS=0
```

The archive omits `.git` and `.venv`, as expected for a `git archive`.

A fresh independent extraction plus `git init`, `git add -f -A`,
`git write-tree` produced the content reconstruction hash:

```text
RECONSTRUCTED_CONTENT_TREE=d9b98178902a74a46c6cf75aed44de58fa622e0e
```

The embedded commit identity is authoritative for the exact archive source.

---

## 2. Governing artifacts

Design specification:

```text
docs/superpowers/specs/2026-09-16-phase-11.4-cli-design.md
```

Committed design SHA-256:

```text
5a088af2d1012b667945c0c9514cb811a01afa30e18515d44023fe0796dd5f8a
```

Implementation plan:

```text
docs/superpowers/plans/2026-09-16-phase-11.4-cli-implementation-plan.md
```

Committed plan SHA-256:

```text
0b2e48c08385150c635a5867876693a4c90fd6ef5db098823c3e2684f24cb4f1
```

Plan starting commit:

```text
6d348a8a9628c4d5751c84a2cb4c53706adff5ba
```

The audited implementation descends from the approved plan state.

---

## 3. Scope review

A direct Phase 11.3 → Phase 11.4 archive comparison found 37 changed files in
the implementation candidate.

Production/config scope is restricted to:

```text
pyproject.toml

cmm/cli.py
cmm/__main__.py
cmm/cli_contracts.py
cmm/cli_output.py
cmm/cli_commands.py
cmm/cli_application.py
cmm/cli_doctor.py

cmm/application/__init__.py
cmm/application/contracts.py
cmm/application/requests.py
cmm/application/gateway.py
cmm/application/local_runtime.py
```

No Phase 11.4 production changes were found in:

```text
cmm/platform
cmm/orchestration
cmm/domains
cmm/agent_runtime
cmm/workflows
cmm/runtime/sessions
kernel/llm/provider_registry
```

The only `cmm/application/gateway.py` change beyond the plan's named files is
the narrow propagation of the new `request.channel` value into
`RequestApplicationService`.

This is consistent with the approved transport-neutral channel seam and does
not create a new owner or authority.

Assessment:

```text
SCOPE=PASS
ARCHITECTURAL_DEVIATION=NONE
PLAN_DEVIATION_GATEWAY_CHANNEL_FORWARDING=JUSTIFIED_NARROW_EXTENSION
```

---

## 4. Public CLI architecture

The audited candidate preserves exactly one public console-script entrypoint:

```toml
cmm = "cmm.cli:main"
```

The public CLI continues to use:

```text
cmm/cli.py
cmm/__main__.py
argparse
```

No alternative framework was found in the Phase 11.4 public CLI code:

```text
Typer=ABSENT
Click=ABSENT
Fire=ABSENT
Docopt=ABSENT
Textual=ABSENT
prompt_toolkit=ABSENT
```

No forbidden parallel CLI owner was found:

```text
CommandRegistry=ABSENT
CommandRouter=ABSENT
CommandBus=ABSENT
CommandRuntime=ABSENT
CommandEngine=ABSENT
CLIService=ABSENT
CMMCLIService=ABSENT
OperationalCLIService=ABSENT
CLIStateStore=ABSENT
CLIRepository=ABSENT
CLIHistoryStore=ABSENT
```

Assessment:

```text
ONE_PUBLIC_CLI_FRONT_DOOR=VERIFIED
ARGPARSE_PRESERVED=VERIFIED
NO_PARALLEL_CLI_AUTHORITY=VERIFIED
```

---

## 5. Application-channel seam

The audited implementation adds the approved transport-neutral seam:

```text
ApplicationChannel.API
ApplicationChannel.CLI
```

Application requests default to API.

CLI-created application requests explicitly use CLI.

The request channel participates in public deterministic request serialization
and idempotency fingerprinting.

The application request service maps:

```text
ApplicationChannel.API -> OrchestrationChannel.API
ApplicationChannel.CLI -> OrchestrationChannel.CLI
```

The CLI does not bypass `ApplicationGateway` to reach `Orchestrator`.

Assessment:

```text
APPLICATION_GATEWAY_REUSED=VERIFIED
CLI_CHANNEL_REACHES_ORCHESTRATOR=VERIFIED
APPLICATION_IDEMPOTENCY_CHANNEL_AWARE=VERIFIED
HTTP_API_CHANNEL_DEFAULT_PRESERVED=VERIFIED
```

---

## 6. Canonical local composition

The candidate adds:

```text
cmm/application/local_runtime.py
```

The helper composes existing official/in-memory canonical components.

No second platform/container/domain/agent/provider/session authority was found.

The connected acceptance exercises the resulting:

```text
ApplicationContainer
ApplicationGateway
Orchestrator
canonical Domain routing
canonical Agent routing
official in-memory session/idempotency infrastructure
```

Assessment:

```text
LOCAL_COMPOSITION_HELPER=VERIFIED
SECOND_APPLICATION_RUNTIME_AUTHORITY=ABSENT
```

---

## 7. Namespace and fail-closed behavior

New operational commands verified:

```text
status
doctor
ask
chat
```

Reserved roadmap namespaces are recognized but fail closed with:

```text
CAPABILITY_UNAVAILABLE
exit code 5
```

The connected acceptance explicitly covers reserved examples including:

```text
plugins list
backup create
```

No Plugin System, backup engine, migration engine, metrics backend, goal
authority, workflow authority or approval authority was introduced by Phase
11.4.

Assessment:

```text
ROADMAP_NAMESPACE_RESERVED=VERIFIED
UNAVAILABLE_CAPABILITIES_FAIL_CLOSED=VERIFIED
NO_NEW_PLUGIN_SYSTEM=VERIFIED
NO_NEW_BACKUP_ENGINE=VERIFIED
NO_NEW_MIGRATION_ENGINE=VERIFIED
NO_NEW_METRICS_BACKEND=VERIFIED
NO_NEW_GOAL_AUTHORITY=VERIFIED
NO_NEW_WORKFLOW_AUTHORITY=VERIFIED
NO_NEW_APPROVAL_AUTHORITY=VERIFIED
```

---

## 8. Output and exit-code contract

The audited implementation provides:

```text
human
JSON
YAML
quiet
verbose
```

YAML uses the approved dependency and safe serializer.

Structured success output uses stdout.

Structured errors use stderr.

The connected acceptance verifies parseable JSON/YAML and no traceback leakage.

Stable representative exit codes were exercised.

Assessment:

```text
JSON_OUTPUT=PASS
YAML_OUTPUT=PASS
STDOUT_STDERR_SEPARATION=PASS
STABLE_EXIT_CODES=PASS
SAFE_ERROR_PRESENTATION=PASS
```

---

## 9. Doctor behavior

`cmm doctor` is implemented as a read-only diagnostic aggregator.

It uses canonical application health/capability evidence for available checks
and reports unavailable conceptual checks honestly.

Connected acceptance verifies:

```text
at least one PASS
at least one UNAVAILABLE
no unauthorized mutation
deterministic summary
```

Assessment:

```text
DOCTOR_READ_ONLY=VERIFIED
DOCTOR_NO_REPAIR_SIDE_EFFECTS=VERIFIED
```

---

## 10. Connected acceptance result

On an execution copy with only audit-environment compatibility adjustments:

1. the already-known Python 3.13/domain-dataclass compatibility adjustment,
   inherited from the Phase 11.3 audit environment; and
2. an ephemeral `.venv/bin/python` wrapper pointing to the auditor's active
   Python interpreter,

the full Phase 11.4 connected acceptance result is:

```text
tests/cli/test_phase11_4_dp104_acceptance.py
69 passed
```

Combined connected Phase 11 acceptances:

```text
AT-DP-104
AT-DP-103
AT-DP-102
AT-DP-101
AT-DP-134

247 passed
```

The connected behavioral semantics are therefore independently verified.

However, exact-archive acceptance reproducibility has one issue described in
Finding MINOR-01.

---

## 11. Architecture/OpenAPI gates

Independent audit run:

```text
tests/cli/test_phase11_4_architecture.py
tests/application/test_architecture.py
tests/api/test_architecture.py
tests/api/test_openapi.py
tests/platform/test_architecture.py
tests/orchestration/test_architecture.py
```

Result:

```text
326 passed
```

Assessment:

```text
ARCHITECTURE_GATES=PASS
OPENAPI_GATES=PASS
```

---

## 12. Application/API regression

Independent audit run:

```text
tests/application
tests/api
```

Result:

```text
857 passed
```

The pre-11.4 baseline was 823.

Assessment:

```text
APPLICATION_API_REGRESSION=PASS
```

---

## 13. Platform/orchestration regression

Independent audit run:

```text
tests/platform
tests/orchestration
```

Result:

```text
856 passed
```

Assessment:

```text
PLATFORM_ORCHESTRATION_REGRESSION=PASS
```

---

## 14. Relevant session/domain/agent regressions

Independent audit run:

```text
tests/runtime/test_shared_sessions.py
tests/domains/test_domain_resolver_integration.py
tests/domains/test_domain_permission_resolution.py
tests/domains/test_domain_profile_resolver.py
tests/agent_runtime/test_existing_system_integration.py
tests/agent_runtime/test_agent_runtime_integration.py
```

Result:

```text
622 passed
```

Assessment:

```text
RELEVANT_DOMAIN_AGENT_SESSION_REGRESSION=PASS
```

---

## 15. Inherited CLI regression

Independent audit results:

```text
tests/test_cli.py
tests/test_cmm_cli.py
11 passed
```

```text
tests/domains/test_domain_sdk_cli.py
21 passed
```

```text
tests/agent_runtime/test_agent_runtime_cli.py
324 passed
```

Validation CLI tests in the independent sandbox produced three failures:

```text
tests/validation/test_validation_cli.py
tests/validation/test_validation_cli_json.py
```

The exact same three failures were reproduced against the Phase 11.3 archive
under the same auditor environment.

Therefore those three failures are inherited environment/tooling behavior and
not caused by Phase 11.4.

The repository-native pre-implementation baseline was:

```text
368 passed
```

The Phase 11.4 reference records the implementation-native inherited CLI run as:

```text
368 passed
```

Assessment:

```text
INHERITED_CLI_PHASE11_4_REGRESSION=NONE_DETECTED
VALIDATION_CLI_AUDITOR_ENVIRONMENT_LIMITATION=INHERITED
```

---

## 16. Global suite evidence

The committed Phase 11.4 reference records:

```text
global suite 20433 passed (exit code 0)
```

The auditor did not treat this self-reported count as independent proof.

A clean independent full-suite run is constrained by already-known audit sandbox
differences, including:

```text
Python 3.13 DomainReasoningRuleDefinition dataclass behavior
missing repository-native validation tool environment
exact-archive subprocess interpreter path issue in MINOR-01
```

The focused, connected, architecture and broad subsystem regressions above were
independently executed instead.

This audit does not identify a Phase 11.4 global-suite regression.

---

# 17. Finding MINOR-01

Identifier:

```text
MINOR_01=NON_PORTABLE_SUBPROCESS_INTERPRETER_IN_DP104_TESTS
```

Severity:

```text
MINOR
```

Affected files:

```text
tests/cli/test_phase11_4_dp104_acceptance.py
tests/cli/test_phase11_4_automation.py
```

Observed hard-coded interpreter:

```text
.venv/bin/python
```

Occurrences include the connected acceptance constant:

```python
PYTHON_EXECUTABLE = ".venv/bin/python"
```

and direct subprocess invocations in automation tests.

The exact audit bundle is correctly produced by `git archive`.

A `git archive` deliberately does not include the local virtual environment.

Therefore, from a clean extraction of the exact audited bundle, the subprocess
acceptance scenarios fail before exercising CMM OS:

```text
FileNotFoundError:
[Errno 2] No such file or directory: '.venv/bin/python'
```

This is independently reproducible.

The same tests pass when the auditor provides an ephemeral wrapper at that
location pointing to the active interpreter.

Therefore:

```text
PRODUCTION_DEFECT=NO
CLI_BEHAVIOR_DEFECT=NO
DP104_ARCHITECTURE_DEFECT=NO
TEST_PORTABILITY_DEFECT=YES
EXACT_ARCHIVE_ACCEPTANCE_REPRODUCIBILITY=FAIL
```

Why this matters:

`AT-DP-104` is the closure acceptance for Phase 11.4 and includes explicit
non-TTY real-process scenarios.

Those scenarios should run with the interpreter executing pytest, not assume a
repository-local virtualenv path that is absent from the canonical audit
artifact.

The repository already uses the correct portable pattern elsewhere:

```python
sys.executable
```

Examples exist in validation and Domain SDK execution tests/logic.

Required narrow remediation:

```text
1. import sys in the two affected test modules where needed;
2. replace every Phase 11.4 test subprocess interpreter literal
   ".venv/bin/python" with sys.executable;
3. do not change production code;
4. rerun Phase 11.4 focused tests;
5. rerun AT-DP-104 and inherited acceptances;
6. rerun architecture/OpenAPI gates;
7. rerun repository-native global suite;
8. commit the test-only remediation;
9. generate a new exact-HEAD git-archive bundle;
10. independently re-audit the new bundle.
```

Do not:

```text
commit a .venv
change production runtime behavior
change CLI semantics
weaken or skip subprocess acceptance
```

---

## 18. Finding classification

```text
BLOCKERS=0
MAJORS=0
MINORS=1
```

No security blocker was found.

No architecture major was found.

No canonical owner was reopened.

No fail-open reserved capability was found.

No regression in the application/API, platform/orchestration, connected Phase
11 acceptance, Domain SDK CLI or Agent Runtime CLI surfaces was found.

The only remediation-required finding is test portability/reproducibility.

---

## 19. F11-018 assessment

The implementation provides the intended canonical operational CLI:

```text
one public front door
argparse preserved
existing specialized CLI subtrees preserved
full roadmap namespace reserved
status/doctor/ask/chat operational
future namespaces fail closed
structured output
stable exit semantics
canonical ApplicationGateway delegation
```

Assessment:

```text
F11_018=VERIFIED_EXISTING
```

---

## 20. DP-104 assessment

`DP-104 — Single-Front-Door Fail-Closed Operational CLI` is independently
verified in production architecture and behavior.

Assessment:

```text
DP_104=VERIFIED_EXISTING
```

The MINOR does not invalidate the Design Point itself.

---

## 21. AT-DP-104 assessment

Behavioral execution with the active auditor interpreter:

```text
AT_DP_104_FUNCTIONAL=PASS
AT_DP_104_TEST_COUNT=69
```

Exact canonical archive execution without adding the missing repository-local
virtualenv path:

```text
AT_DP_104_EXACT_ARCHIVE_REPRODUCIBILITY=FAIL
```

Therefore the acceptance cannot receive the final closure marker
`AT_DP_104=PASS` until MINOR-01 is remediated and a new exact-HEAD bundle is
re-audited.

---

## 22. Final Independent Audit V1 verdict

```text
INDEPENDENT_AUDIT_V1=FAIL

BLOCKERS=0
MAJORS=0
MINORS=1

MINOR_01=NON_PORTABLE_SUBPROCESS_INTERPRETER_IN_DP104_TESTS

F11_018=VERIFIED_EXISTING
DP_104=VERIFIED_EXISTING

AT_DP_104_FUNCTIONAL=PASS
AT_DP_104_EXACT_ARCHIVE_REPRODUCIBILITY=FAIL

AT_DP_103=PASS
AT_DP_102=PASS
AT_DP_101=PASS
AT_DP_134=PASS

AUDITED_HEAD=74a77c3a1b4e8e52c0de6be9463b6bba3218f2e0
AUDIT_BUNDLE_SHA256=f7e88debf0bf376960f4b64ceb696417b0bb965ad024f86c027affed62bc2e70
RECONSTRUCTED_CONTENT_TREE=d9b98178902a74a46c6cf75aed44de58fa622e0e

CLOSURE_ELIGIBLE=NO
NEXT=PHASE11_4_REMEDIATION_V1
```

---

## 23. Required remediation boundary

Remediation V1 is test-only.

Authorized files:

```text
tests/cli/test_phase11_4_dp104_acceptance.py
tests/cli/test_phase11_4_automation.py
```

Expected semantic change:

```text
".venv/bin/python"
        ↓
sys.executable
```

No Phase 11.4 production file should change.

No documentation must claim closure before independent re-audit PASS.

A new exact-HEAD bundle is mandatory after the remediation commit.

The current audit bundle remains immutable historical evidence.
