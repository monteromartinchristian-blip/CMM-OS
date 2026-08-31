# Phase 10.36 — Domain API — Independent Re-Audit V2

## Verdict

**Result:** FAIL — remediation required
**BLOCKERS:** 1
**MAJORS:** 0
**MINORS:** 1
**DP-036:** VERIFIED_EXISTING
**AT-DP-036:** PASS
**CLOSURE_ELIGIBLE:** NO

## Audited artifact

- Bundle: `phase-10.36-domain-api-audit-v2.tar.gz`
- SHA-256: `2b775ff0cb958721080118419d85f10e9729cef36ec8ab9fe8426b1d3592c8e9`
- Exact embedded `git archive` commit: `9e078244a73126406cfc81d674316b0aeef4d24a`
- Archive members: 1952
- Archive path-safety violations: 0
- Archive integrity: PASS
- Exact-HEAD binding through TAR PAX comment: PASS
- `compileall` over archived `cmm/domains` and `tests/domains`: PASS
- Trailing-whitespace scan over V2 remediation files: PASS

## V1 MAJOR-01 remediation

**MAJOR-01 is fully remediated.**

Independent V1 found that the stable public Domain API dependency boundary was
typed against concrete implementations instead of the canonical protocols and
that `get_capabilities` returned `tuple[Any, ...]` in its public annotation.

The V2 artifact now correctly uses:

```text
discovery: DomainDiscovery
resolver: DomainResolver
trace_validator: DomainTraceReferenceValidator
```

and both:

```text
DomainAPI.get_capabilities
DefaultDomainAPI.get_capabilities
```

now expose:

```text
tuple[DomainCapability, ...]
```

The canonical `DomainDefinition.capabilities` contract is also
`tuple[DomainCapability, ...]`.

The V2 diff against the V1 bundle is narrow and appropriate: production changes
are limited to `cmm/domains/api.py`; contract regressions were added to
`tests/domains/test_domain_api_contracts.py`; reference/roadmap wording was
updated; and the committed V1 audit report was added. No unrelated Domain
runtime architecture was changed.

## DP-036 verification

`DP-036` is verified existing.

The audited `cmm/domains/api.py` contains exactly the approved 20 enumerated
public methods on both `DomainAPI` and `DefaultDomainAPI`:

```text
list_domains
get_domain
discover_domains
validate_domain
install_domain
enable_domain
disable_domain
resolve_domain
get_capabilities
get_resources
get_rules
get_operations
get_workflows
execute_operation
start_workflow
get_session
resume_session
resolve_conflict
assemble_trace
validate_trace
```

The implementation preserves the approved canonical ownership:

```text
install_domain      -> DeclarativeDomainLoader.load
resolve_domain      -> DomainResolver.resolve
execute_operation   -> DefaultDomainOperationOrchestrator.execute
start_workflow      -> workflow registry resolve_active + DomainWorkflowExecutor
get_session         -> SharedSessionDomainAdapter.load_domain_session
resume_session      -> DomainSessionResumer.resume
resolve_conflict    -> DomainConflictResolver.resolve
assemble_trace      -> DomainTraceAssembler.assemble
validate_trace      -> DomainTraceReferenceValidator.validate
```

No `DomainAPIError`, trace store, Domain-specific session store, API registry,
API loader, API resolver, trace repository, session enumeration, or persistent
trace lookup was introduced.

Canonical general event invariants are preserved:

```text
GENERAL_EVENTS=23
UNIQUE_GENERAL_EVENTS=23
domain.session.resumed=ABSENT
```

## AT-DP-036 verification

`AT-DP-036` is a connected acceptance over real canonical or official in-memory
components. The audited test connects:

```text
FileSystemDomainDiscovery
-> PipelineDomainValidator
-> DeclarativeDomainLoader / DomainRegistry
-> explicit enable
-> registry-backed inspection
-> DefaultDomainResolver
-> DefaultDomainOperationOrchestrator
-> InMemoryDomainWorkflowRegistry + DomainWorkflowExecutor
-> InMemorySessionStore + SharedSessionDomainAdapter + DomainSessionResumer
-> DomainConflictResolver
-> DomainTraceAssembler + DefaultDomainTraceReferenceValidator
-> explicit disable
```

The acceptance also proves structural anti-fragmentation and the absence of
invented session/trace/public lifecycle surfaces.

The remediation execution evidence reports:

```text
FOCUSED_TESTS=76 passed
CANONICAL_REGRESSIONS=550 passed
AT_DP_036=PASS
```

The audit sandbox could not independently execute pytest because the archive
depends on `libcst`, which is not installed in the sandbox and cannot be fetched
because network access is unavailable. This environment limitation does not
invalidate the local execution evidence; source, test wiring, archive integrity,
and compileability were independently inspected.

---

## BLOCKER-01 — Mandatory Domain and global regression gates are red

### Severity

**BLOCKER**

### Evidence

The remediation agent executed the required Domain and global suites at the V2
implementation state and reported:

```text
DOMAIN_TESTS=8304 passed, 52 failed, 91 errors
GLOBAL_TESTS=13859 passed, same 143 failures/errors
```

Therefore the mandatory gates required by the Phase 10.36 workflow are not
green.

The agent also demonstrated that the failures pre-date the V1 remediation and do
not import or depend on `cmm.domains.api`. That establishes non-causation by
MAJOR-01 remediation, but it does **not** make a red mandatory gate acceptable
for phase closure.

### Root cause independently confirmed in the audited artifact

`tests/domains/domain_session_lifecycle_test_support.py` contains:

```python
_replace_once(
    path,
    r"^\*\*Implemented through:\*\*.*$",
    implemented_through,
)
```

The current committed `ROADMAP.md` instead contains:

```text
**Implemented and audited through:** Phase 10.35 — Domain SDK ...
```

and no `**Implemented through:**` marker.

`portable_archive_fixture(...)` copies the current `ROADMAP.md` and then calls
`set_phase_10_34_documented_state(...)`, so the strict historical fixture
rewriter fails before Phase 10.34 acceptance/audit regression cases can execute.

The other required roadmap markers used by the helper remain present. The
failure is therefore a narrow fixture-compatibility drift caused by the roadmap
label evolving after the Phase 10.34 lifecycle fixtures were written.

### Why this blocks closure

CMM OS phase policy requires, before audit/closure:

```text
focused phase tests PASS
relevant regressions PASS
subsystem suite PASS
global suite PASS
Ruff PASS
format PASS
compileall PASS
git diff --check PASS
```

A previously introduced regression is still a regression at the HEAD being
audited. Closed historical phases must remain testable. Phase 10.36 cannot be
closed while 143 Domain/global tests fail, even when the new Domain API itself
is not their cause.

### Required remediation

Repair the historical Phase 10.34 fixture helper, not `ROADMAP.md` history and
not Domain API runtime code.

The preferred minimal solution is to make the Phase 10.34 fixture rewriter
accept the two canonical roadmap labels:

```text
**Implemented through:**
**Implemented and audited through:**
```

while still requiring exactly one match and still rewriting the temporary
fixture to the historical Phase 10.34 state.

Conceptually the marker may become an exact compatibility regex equivalent to:

```regex
^\*\*Implemented(?: and audited)? through:\*\*.*$
```

The implementation must remain fail-closed for any other wording and must not
weaken the Phase 10.34 evidence validators.

Add focused regression coverage proving the helper can construct its historical
portable fixture from the current roadmap shape.

Then rerun:

```text
Phase 10.34 lifecycle/acceptance/audit regression tests
Phase 10.36 focused tests
canonical Domain regressions
tests/domains
full repository suite
full Ruff over cmm/domains + tests/domains
full format check over cmm/domains + tests/domains
compileall
git diff --check
event invariant gate
```

All must be green before a V3 bundle is generated.

---

## MINOR-01 — One stale concrete trace-validator statement remains in reference docs

### Severity

**MINOR**

### Evidence

`docs/reference/domain-api.md` correctly documents the stable constructor
boundary and method table as:

```text
DomainTraceReferenceValidator
(default: DefaultDomainTraceReferenceValidator)
```

but the later “Reference-only trace boundary” section still states:

```text
validate_trace delegates to DefaultDomainTraceReferenceValidator.validate.
```

That is no longer universally true because the facade accepts any canonical
`DomainTraceReferenceValidator`.

### Required remediation

Change that sentence to describe the protocol boundary, for example:

```text
validate_trace delegates to the injected DomainTraceReferenceValidator;
DefaultDomainTraceReferenceValidator is the standard concrete implementation.
```

No production code change is required for this finding.

---

## Gate assessment

Verified directly from the archive:

```text
ARCHIVE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
SHA256=PASS
V1_MAJOR_01=REMEDIATED
DP_036=VERIFIED_EXISTING
AT_DP_036=PASS_EVIDENCE_ACCEPTED
STATIC_ARCHITECTURE_GATE=PASS
GENERAL_EVENTS=23/23_UNIQUE
DOMAIN_SESSION_RESUMED_EVENT=ABSENT
COMPILEALL=PASS
```

Execution evidence supplied with the V2 bundle:

```text
FOCUSED_TESTS=76 PASS
CANONICAL_REGRESSIONS=550 PASS
DOMAIN_SUITE=FAIL
GLOBAL_SUITE=FAIL
```

The remediation run only re-verified Ruff/format on touched files after its
final edits, rather than re-running the complete required full-tree Ruff and
format commands. V3 must provide fresh full-tree gate evidence after
BLOCKER-01 is corrected.

## V2 closure status

```text
BLOCKERS=1
MAJORS=0
MINORS=1
MAJOR_01=REMEDIATED
DP-036=VERIFIED_EXISTING
AT-DP-036=PASS
CLOSURE_ELIGIBLE=NO
```

Required next sequence:

```text
RECORD AUDIT V2
-> REMEDIATE BLOCKER-01 + MINOR-01 ONLY
-> RUN ALL REQUIRED GATES TO GREEN
-> COMMIT REMEDIATION
-> WORKTREE CLEAN
-> GENERATE phase-10.36-domain-api-audit-v3.tar.gz FROM EXACT HEAD
-> RECORD SHA-256
-> INDEPENDENT RE-AUDIT V3
```
