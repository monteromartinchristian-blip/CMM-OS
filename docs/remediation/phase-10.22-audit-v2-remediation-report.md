# Phase 10.22 University Domain — Independent Audit V2 Remediation

Status: remediation applied; roadmap remains **Implemented, pending audit**.

This report records canonical production-path evidence for the V2 blockers. No
new University rule, operation, workflow, entity, or resource was introduced.

## V2 blockers

| Finding | Production path | Evidence |
| --- | --- | --- |
| V2-B1 Source Authority — FIXED | AcademicSourceAuthorityRule.evaluate() → classify_academic_source_authority() | tests/domains/test_university_domain_source_authority.py proves specific grounded official authority, recency trap, fabricated official metadata, equal-authority conflict, and supersession. |
| V2-B2 Contradiction — FIXED | AcademicContradictionRule.evaluate() → resolve_academic_conflict() → _claim_source() | tests/domains/test_university_domain_contradiction.py proves attribute-specific resolution, history preservation, unresolved equal authority, and caller flags cannot override derived conflict. |
| V2-B3 ECTS — FIXED | EctsConsistencyRule.evaluate() → check_ects_consistency(records=..., degree_requirement=...) | tests/domains/test_university_domain_ects.py proves missing requirements stay unknown, records derive duplicates and contradictions, enrolled/pending credits do not count, and grounded completion can be confirmed. |
| V2-B4 Exam Attempts — FIXED | ExamAttemptRule.evaluate() → evaluate_exam_attempt(regulation=..., require_complete_evidence=True) | tests/domains/test_university_domain_exam_attempts.py proves missing/stale regulation remains unknown, complete ordinary evidence counts, failed grades alone do not, and reassessments remain separate. |
| V2-B5 Workload — FIXED | AcademicWorkloadRule.evaluate() → structured scenario/constraint feasibility | tests/domains/test_university_domain_workload.py proves infeasible preferred scenarios cannot win, explicit preferences rank only feasible scenarios, no preference ordering is invented, unknown availability stays unresolved, and the Health functional cap changes feasibility. |
| V2-B6 Dependencies — FIXED | AcademicDependencyRule.evaluate() → academic-state records | tests/domains/test_university_domain_dependencies.py proves caller pass booleans do not establish prerequisites, grounded subject records do, credit thresholds derive from records, and pending recognition is conditional. |
| V2-B7 Integrity Mode C — FIXED | AcademicIntegrityRule.evaluate() → scoped evaluate_academic_integrity() | tests/domains/test_university_domain_integrity.py proves exact course/assessment/action scope, wrong-course and stale/superseded restrictions, ambiguity handling, and caller booleans. |
| V2-M3 Verification Integration — FIXED | deadline, contradiction, and exam rules emit verification_need metadata from conditional_verification_trigger() | tests/domains/test_university_domain_verification.py, test_university_domain_contradiction.py, and test_university_domain_exam_attempts.py assert the shared read-only official-only signal. |
| V2-M4 Cross-domain Lifecycle — FIXED | `CrossDomainPermissionRequest` → `DomainPermissionGate.evaluate_cross_domain()` → pure `DomainPermissionResolver.resolve_cross_domain()` → exact current `PermissionApprovalRequirement` → `ApprovalService.validate_and_consume()`; approval evidence never returns to the resolver | `tests/domains/test_university_domain_permission_lifecycle.py` proves the real shared-gate lifecycle, forged-evidence rejection, exact actor/session/target/resource/scope binding, wrong ID, one-shot consumption, revocation, expiration, policy-change-before-consumption, clinical-detail denial, and University outbound denial. |
| Legacy semantic consolidation — FIXED | public legacy helpers delegate to canonical resolvers/classifiers | resolve_source_authority_by_attribute(), evaluate_academic_contradiction(), and evaluate_deadline() are compatibility adapters; canonical rules use the grounded implementations directly. |

## Verification snapshot

- Focal M4 lifecycle tests: 14 passed.
- Shared permission-gate tests: 50 passed.
- University tests: 336 passed.
- Domain tests: 3,894 passed.
- Full suite: 9,405 passed.
- Canonical counts: 14 entities / 12 resources / 10 rules / 11 operations / 7 workflows.

Independent Audit V3 remains the closure authority.

### M4 corrected gate architecture

`DomainPermissionResolver.resolve_cross_domain()` is pure and accepts no
caller-supplied approval evidence. The shared `DomainPermissionGate` evaluates
the current source and target policies first, derives the single aggregate
cross-domain requirement with stable `scope="cross_domain"`, and only then
calls `ApprovalService.validate_and_consume()` with that exact requirement.
The returned `ApprovalConsumptionEvidence` is gate output for traceability; it
is never passed back into policy resolution to produce `ALLOW`.
