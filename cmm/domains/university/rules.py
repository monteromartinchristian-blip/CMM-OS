"""Phase 10.22 — University Domain Rules and deterministic helpers.

A declarative domain + pure deterministic academic helpers.  The helper
functions are state-free: no IO, no model calls, no registry mutation, no
internal clock.  They receive context explicitly and return deterministic
structures.

The ten reasoning rules are ``@dataclass(frozen=True, slots=True)``
definitions exposing ``definition`` and ``evaluate(context)``, exactly like the
General, Health, and Relationships Domain rules, so they compose with the
existing cognitive layer.

Epistemic-safety core (spec §6–§8): source authority is preserved **by
attribute**, not by a global naive ranking.  A material academic contradiction
that cannot be resolved is **fail-closed** (BLOCKED).  Observed academic
performance never establishes intellectual capacity.  Academic State is never
overridden by Personal Memory.  Academic Integrity Mode C is permissive by
default.  Decision support never adopts an academic decision.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cmm.cognitive.enums import (
    ReasoningRiskLevel,
    ReasoningRuleCategory,
    ReasoningRuleResultStatus,
    ReasoningRuleScope,
    ReasoningRuleStatus,
    ReasoningSeverity,
)
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningEscalation,
    ReasoningFinding,
    ReasoningGap,
    ReasoningRuleContext,
    ReasoningRuleDefinition,
    ReasoningRuleResult,
    ReasoningRuleTraceEntry,
)
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult
from cmm.domains.university.catalog import CANONICAL_UNIVERSITY_RULE_IDS

UNIVERSITY_RULE_IDS: tuple[str, ...] = CANONICAL_UNIVERSITY_RULE_IDS

# ── Closed source-authority levels (spec §9) ──────────────────────────────────

SOURCE_AUTHORITY_ATTRIBUTE = "attribute"
SOURCE_AUTHORITY_OFFICIAL = "official"
SOURCE_AUTHORITY_REGULATION = "regulation"
SOURCE_AUTHORITY_USER_REPORTED = "user_reported"
SOURCE_AUTHORITY_INFERRED = "inferred"
SOURCE_AUTHORITY_UNKNOWN = "unknown"

# A canonical fixed ordering of source types for a *given attribute*.  Source
# authority is resolved per-attribute, not as a global ranking.
_SOURCE_TYPE_RANK = (
    SOURCE_AUTHORITY_OFFICIAL,
    SOURCE_AUTHORITY_REGULATION,
    SOURCE_AUTHORITY_USER_REPORTED,
    SOURCE_AUTHORITY_INFERRED,
    SOURCE_AUTHORITY_UNKNOWN,
)

# ── Closed integrity modes (spec §17) ─────────────────────────────────────────

INTEGRITY_MODE_A = "mode_a"
INTEGRITY_MODE_B = "mode_b"
INTEGRITY_MODE_C = "mode_c"

# ── Closed contradiction states (spec §10) ────────────────────────────────────

CONTRADICTION_RESOLVED = "resolved"
CONTRADICTION_UNRESOLVED = "unresolved"
CONTRADICTION_MATERIAL = "material"


# ═══════════════════════════════════════════════════════════════════════════════
# Pure deterministic university helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _usable_reference(value: Any) -> str | None:
    """Return a usable reference identifier from a raw value, or ``None``.

    A reference is usable only when it is a non-empty string.  Lists/tuples
    yield the first usable reference.  This deliberately never fabricates a
    placeholder (e.g. ``"unknown"``): an absent or blank reference is
    ``None``, never a fake evidence ID.
    """
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    if isinstance(value, (list, tuple)):
        for item in value:
            usable = _usable_reference(item)
            if usable is not None:
                return usable
    return None


def _reference_from(
    mapping: Mapping,
    *keys: str,
) -> str | None:
    """Extract the first usable reference from ``mapping`` under any of ``keys``."""
    for key in keys:
        value = mapping.get(key)
        usable = _usable_reference(value)
        if usable is not None:
            return usable
    return None


def _normalize_references(values: Any) -> tuple[str, ...]:
    """Normalize a collection of reference IDs into a deterministic,
    order-preserving, de-duplicated tuple of usable references.

    Blank/placeholder IDs are dropped and never count as evidence.  This never
    fabricates a placeholder (e.g. ``"unknown"``) for a missing identifier.
    """
    if isinstance(values, str):
        values = (values,)
    if not isinstance(values, (list, tuple)):
        return ()
    seen: list[str] = []
    seen_set: set[str] = set()
    for value in values:
        usable = _usable_reference(value)
        if usable is not None and usable not in seen_set:
            seen_set.add(usable)
            seen.append(usable)
    return tuple(seen)


def resolve_source_authority_by_attribute(
    *,
    attribute: str,
    sources: tuple = (),
) -> dict:
    """Resolve the authoritative source for a *single* academic attribute.

    Source authority is preserved **by attribute**, not by a global naive
    ranking (spec §9).  Each source carries a ``source_type`` chosen from the
    closed set above.  For the given attribute, the highest-ranking source
    type that actually supplies the attribute is authoritative; official /
    regulation sources dominate user-reported and inferred sources.

    A source is only authoritative for the attribute when it *supplies* that
    attribute (``supplied_attributes`` contains ``attribute``).  A source that
    does not supply the attribute never competes for it.
    """
    candidate: str | None = None
    candidate_rank = len(_SOURCE_TYPE_RANK)
    matched: list[dict] = []
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        supplied = source.get("supplied_attributes", ())
        if not isinstance(supplied, (list, tuple)) or attribute not in supplied:
            continue
        source_type = str(source.get("source_type", SOURCE_AUTHORITY_UNKNOWN))
        try:
            rank = _SOURCE_TYPE_RANK.index(source_type)
        except ValueError:
            rank = len(_SOURCE_TYPE_RANK)
        matched.append(
            {
                "source_id": source.get("source_id"),
                "source_type": source_type,
                "rank": rank,
            }
        )
        if rank < candidate_rank:
            candidate_rank = rank
            candidate = source_type
    return {
        "attribute": attribute,
        "authority": candidate,
        "authority_source_type": candidate,
        "matched_sources": tuple(matched),
        "authority_resolved": candidate is not None,
    }


def evaluate_academic_contradiction(
    *,
    statements: tuple = (),
) -> dict:
    """Classify an academic contradiction state deterministically.

    Returns one of: ``resolved``, ``unresolved``, ``material``.

    A contradiction is **material** when it concerns an attribute that is
    required for a pending academic decision/reasoning step and the divergent
    sources cannot be ordered by source authority (e.g. two official sources
    disagree).  A material contradiction that cannot be resolved is
    **fail-closed** (spec §10): the reasoning step must not proceed on the
    assumption.
    """
    if not statements:
        return {
            "state": CONTRADICTION_UNRESOLVED,
            "material": False,
            "resolved": False,
        }
    material = False
    resolved = True
    for statement in statements:
        if not isinstance(statement, Mapping):
            continue
        if statement.get("material"):
            material = True
        if statement.get("unresolved"):
            resolved = False
    if material and not resolved:
        return {
            "state": CONTRADICTION_MATERIAL,
            "material": True,
            "resolved": False,
        }
    if resolved:
        return {
            "state": CONTRADICTION_RESOLVED,
            "material": material,
            "resolved": True,
        }
    return {
        "state": CONTRADICTION_UNRESOLVED,
        "material": False,
        "resolved": False,
    }


def check_ects_consistency(
    *,
    subject_ects: int = 0,
    declared_workload_hours: int = 0,
    hours_per_ect: float = 25.0,
) -> dict:
    """Check ECTS/credit consistency deterministically.

    A declared workload that is implausibly far from the credit-derived
    expectation is flagged as an inconsistency (a hypothesis, never an
    authoritative correction).  The helper only *reports* the discrepancy; it
    never rewrites the official record.
    """
    expected_hours = int(subject_ects * hours_per_ect)
    if expected_hours <= 0:
        return {
            "expected_hours": expected_hours,
            "declared_hours": declared_workload_hours,
            "consistent": True,
            "flagged": False,
            "note": "No ECTS derived expectation to compare.",
        }
    tolerance = max(1, int(expected_hours * 0.5))
    consistent = abs(declared_workload_hours - expected_hours) <= tolerance
    return {
        "expected_hours": expected_hours,
        "declared_hours": declared_workload_hours,
        "consistent": consistent,
        "flagged": not consistent,
        "note": (
            "consistent"
            if consistent
            else "declared workload diverges from ECTS-derived expectation"
        ),
    }


def evaluate_exam_attempt(
    *,
    attempt_count: int = 1,
    max_attempts: int | None = 3,
    passed: bool = False,
) -> dict:
    """Evaluate an exam attempt deterministically against the rules in force.

    Reports whether the attempt count is within the permitted maximum and
    whether the attempt is a pass.  The helper only *reports*; it never
    modifies the official record and never authorizes a retake.
    """
    returned = {
        "attempt_count": attempt_count,
        "max_attempts": max_attempts,
        "passed": bool(passed),
        "within_limits": max_attempts is None or attempt_count <= max_attempts,
    }
    if max_attempts is not None and attempt_count > max_attempts:
        returned["limit_exceeded"] = True
    else:
        returned["limit_exceeded"] = False
    return returned


def evaluate_academic_workload(
    *,
    total_ect: int = 0,
    full_time_ect: int = 30,
    max_ratio: float = 1.5,
) -> dict:
    """Evaluate academic workload against a reference full-time load.

    Produces a workload assessment (a hypothesis).  ``total_ect`` is the
    planned ECTS; ``full_time_ect`` is the nominal full-time reference.  An
    overcommit beyond ``max_ratio`` of the full-time reference is flagged as a
    planning risk, never a definitive overload judgment.
    """
    if full_time_ect <= 0:
        return {
            "total_ect": total_ect,
            "full_time_ect": full_time_ect,
            "ratio": 0.0,
            "overcommitted": False,
            "flagged": False,
        }
    ratio = total_ect / full_time_ect
    overcommitted = ratio > max_ratio
    return {
        "total_ect": total_ect,
        "full_time_ect": full_time_ect,
        "ratio": round(ratio, 2),
        "overcommitted": overcommitted,
        "flagged": overcommitted,
    }


def evaluate_academic_dependency(
    *,
    subject_id: str,
    dependencies: tuple = (),
) -> dict:
    """Evaluate academic dependency relationships deterministically.

    A subject may list prerequisite subjects.  The helper reports which
    prerequisites have been satisfied (passed) and which remain open, and
    flags a dependency that blocks planning.  It never changes the official
    record and never auto-enrols.
    """
    open_prereqs: list[str] = []
    satisfied: list[str] = []
    for dep in dependencies:
        if not isinstance(dep, Mapping):
            continue
        dep_id = _usable_reference(dep.get("id"))
        if dep_id is None:
            continue
        if dep.get("passed"):
            satisfied.append(dep_id)
        else:
            open_prereqs.append(dep_id)
    return {
        "subject_id": subject_id,
        "satisfied_prerequisites": tuple(satisfied),
        "open_prerequisites": tuple(open_prereqs),
        "dependency_blocked": bool(open_prereqs),
    }


def evaluate_performance_capacity(
    *,
    performance_observation: dict | None = None,
) -> dict:
    """Bound observed academic performance away from intellectual capacity.

    Observed performance is a **fact about output**, never a measure of
    capacity (spec §16).  A single poor performance establishes neither
    capacity nor incapacity; performance is contextual, time-bound, and
    non-predictive of future ability.  The helper returns a structured record
    that keeps performance and capacity distinct.
    """
    if performance_observation is None:
        return {
            "performance_observed": False,
            "capacity_inferred": False,
            "statement": "No performance observation supplied.",
        }
    return {
        "performance_observed": True,
        "capacity_inferred": False,
        "statement": (
            "Observed performance is a fact about output, not a measure of "
            "intellectual capacity; it never implies capacity or incapacity."
        ),
        "performance_ref": _usable_reference(performance_observation.get("ref")),
    }


def evaluate_deadline(
    *,
    deadline: str | None = None,
) -> dict:
    """Represent a deadline as a structured fact with its own provenance.

    A deadline is a factual item with a date; it is never invented and never
    auto-scheduled.  The helper reports whether a usable deadline value is
    present.  It does not create calendar events.
    """
    usable = _usable_reference(deadline)
    return {
        "deadline_present": usable is not None,
        "deadline": usable,
        "auto_scheduled": False,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Reasoning rule scaffolding
# ═══════════════════════════════════════════════════════════════════════════════


def _definition(
    rule_id: str,
    name: str,
    category: str,
    priority: int,
    risk_level: ReasoningRiskLevel = ReasoningRiskLevel.LOW,
) -> DomainReasoningRuleDefinition:
    return DomainReasoningRuleDefinition(
        id=rule_id,
        name=name,
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:university",
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=risk_level,
        deterministic=True,
        description=f"Conservative university rule for {rule_id}.",
        metadata={"phase": "10.22"},
    )


def _result(
    definition: ReasoningRuleDefinition,
    context: ReasoningRuleContext,
    status: ReasoningRuleResultStatus,
    *,
    findings: tuple[ReasoningFinding, ...] = (),
    gaps: tuple[ReasoningGap, ...] = (),
    escalation: ReasoningEscalation | None = None,
    code: str,
    message: str,
) -> ReasoningRuleResult:
    return DomainRuleResult(
        rule_id=definition.id,
        rule_name=definition.name,
        rule_version=definition.version,
        domain_id=definition.domain_id,
        status=status,
        findings=findings,
        gaps=gaps,
        escalation=escalation,
        trace_entries=(
            ReasoningRuleTraceEntry(
                code=code,
                message=message,
                rule_id=definition.id,
                domain_id=definition.domain_id,
                status=status,
                occurred_at=context.timestamp,
                output_count=len(findings) + len(gaps) + int(escalation is not None),
            ),
        ),
        started_at=context.timestamp,
        completed_at=context.timestamp,
    )


def _mapping(metadata: Mapping, key: str) -> Mapping | None:
    value = metadata.get(key)
    return value if isinstance(value, Mapping) else None


def _seq(metadata: Mapping, key: str) -> tuple | None:
    value = metadata.get(key)
    return value if isinstance(value, (list, tuple)) else None


# ═══════════════════════════════════════════════════════════════════════════════
# AcademicSourceAuthorityRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AcademicSourceAuthorityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        claims = _seq(context.metadata, "academic_claims")
        if not claims:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No academic claims supplied.",
            )
        findings: list[ReasoningFinding] = []
        for claim in claims:
            if not isinstance(claim, Mapping):
                continue
            attribute = str(claim.get("attribute", "unknown"))
            source_type = str(claim.get("source_type", SOURCE_AUTHORITY_UNKNOWN))
            supplied = claim.get("supplied_attributes", ())
            supplies_attribute = (
                isinstance(supplied, (list, tuple)) and attribute in supplied
            )
            claim_id = _usable_reference(claim.get("id"))
            references = (claim_id,) if claim_id is not None else ()
            findings.append(
                ReasoningFinding(
                    code="ATTRIBUTE_AUTHORITY",
                    message=(
                        f"Attribute {attribute} supplied by source type "
                        f"{source_type}; authority preserved by attribute."
                    ),
                    severity=ReasoningSeverity.INFO,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                    references=references,
                    metadata={
                        "attribute": attribute,
                        "source_type": source_type,
                        "supplies_attribute": supplies_attribute,
                    },
                )
            )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="ATTRIBUTE_SOURCE_AUTHORITY_PRESERVED",
            message="Source authority preserved by attribute, not a global ranking.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AcademicContradictionRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AcademicContradictionRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        statements = _seq(context.metadata, "contradiction_statements")
        if not statements:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No contradiction statements supplied.",
            )
        record = evaluate_academic_contradiction(statements=tuple(statements))
        references: tuple[str, ...] = ()
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            ref = _usable_reference(statement.get("id"))
            if ref is not None:
                references = (*references, ref)
        if record["state"] == CONTRADICTION_MATERIAL:
            finding = ReasoningFinding(
                code="MATERIAL_CONTRADICTION_UNRESOLVED",
                message=(
                    "A material academic contradiction cannot be resolved by "
                    "source authority; reasoning is fail-closed and must not "
                    "proceed on the assumption."
                ),
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                references=references,
            )
            escalation = ReasoningEscalation(
                code="MATERIAL_CONTRADICTION_BLOCKED",
                message="Material contradiction unresolved; reasoning step blocked.",
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                escalation=escalation,
                code="MATERIAL_CONTRADICTION_BLOCKED",
                message="Material contradiction unresolved; blocked.",
            )
        finding = ReasoningFinding(
            code="CONTRADICTION_STATE",
            message=f"Academic contradiction state: {record['state']}.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            references=references,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="CONTRADICTION_EVALUATED",
            message="Academic contradiction evaluated deterministically.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AcademicDeadlineRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AcademicDeadlineRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        deadline = _mapping(context.metadata, "deadline")
        if deadline is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No deadline metadata supplied.",
            )
        record = evaluate_deadline(deadline=deadline.get("value"))
        finding = ReasoningFinding(
            code="DEADLINE_FACT",
            message=(
                "Deadline represented as a structured fact with provenance; "
                "no calendar event is created."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={"deadline_present": record["deadline_present"]},
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="DEADLINE_RECORDED",
            message="Deadline recorded as a fact; no auto-scheduling.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EctsConsistencyRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class EctsConsistencyRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        ects = _mapping(context.metadata, "ects")
        if ects is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No ECTS metadata supplied.",
            )
        record = check_ects_consistency(
            subject_ects=int(ects.get("subject_ects", 0)),
            declared_workload_hours=int(ects.get("declared_workload_hours", 0)),
            hours_per_ect=float(ects.get("hours_per_ect", 25.0)),
        )
        if record["flagged"]:
            finding = ReasoningFinding(
                code="ECTS_INCONSISTENCY",
                message=(
                    f"Declared workload ({record['declared_hours']}h) diverges "
                    f"from ECTS-derived expectation ({record['expected_hours']}h); "
                    "reported as a hypothesis, never an authoritative correction."
                ),
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                metadata=record,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="ECTS_INCONSISTENCY_FLAGGED",
                message="ECTS inconsistency flagged as a hypothesis.",
            )
        finding = ReasoningFinding(
            code="ECTS_CONSISTENT",
            message="Credits and declared workload are consistent.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=record,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="ECTS_CONSISTENT",
            message="ECTS consistency verified.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ExamAttemptRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ExamAttemptRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        attempt = _mapping(context.metadata, "exam_attempt")
        if attempt is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No exam attempt metadata supplied.",
            )
        record = evaluate_exam_attempt(
            attempt_count=int(attempt.get("attempt_count", 1)),
            max_attempts=attempt.get("max_attempts"),
            passed=bool(attempt.get("passed")),
        )
        if record["limit_exceeded"]:
            finding = ReasoningFinding(
                code="EXAM_ATTEMPT_LIMIT_EXCEEDED",
                message=(
                    f"Attempt {record['attempt_count']} exceeds the permitted "
                    f"maximum ({record['max_attempts']}); reported without "
                    "authorizing a retake or modifying the record."
                ),
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                metadata=record,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="EXAM_ATTEMPT_LIMIT_EXCEEDED",
                message="Exam attempt limit exceeded; reported, not acted on.",
            )
        finding = ReasoningFinding(
            code="EXAM_ATTEMPT_EVALUATED",
            message=f"Exam attempt within limits (attempt {record['attempt_count']}).",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=record,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="EXAM_ATTEMPT_EVALUATED",
            message="Exam attempt evaluated within permitted limits.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AcademicWorkloadRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AcademicWorkloadRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        workload = _mapping(context.metadata, "workload")
        if workload is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No workload metadata supplied.",
            )
        record = evaluate_academic_workload(
            total_ect=int(workload.get("total_ect", 0)),
            full_time_ect=int(workload.get("full_time_ect", 30)),
            max_ratio=float(workload.get("max_ratio", 1.5)),
        )
        if record["flagged"]:
            finding = ReasoningFinding(
                code="WORKLOAD_OVERCOMMIT",
                message=(
                    f"Planned load ({record['total_ect']} ECTS) exceeds "
                    f"{record['ratio']}x the full-time reference "
                    f"({record['full_time_ect']} ECTS); flagged as a planning "
                    "risk, not a definitive overload judgment."
                ),
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                metadata=record,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="WORKLOAD_OVERCOMMIT_FLAGGED",
                message="Workload overcommit flagged as a planning risk.",
            )
        finding = ReasoningFinding(
            code="WORKLOAD_ASSESSED",
            message="Planned workload is within the reference full-time load.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata=record,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="WORKLOAD_ASSESSED",
            message="Workload assessed within the reference load.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AcademicDependencyRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AcademicDependencyRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        dependency = _mapping(context.metadata, "dependency")
        if dependency is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No dependency metadata supplied.",
            )
        record = evaluate_academic_dependency(
            subject_id=str(dependency.get("subject_id", "unknown")),
            dependencies=tuple(dependency.get("prerequisites", ()) or ()),
        )
        if record["dependency_blocked"]:
            finding = ReasoningFinding(
                code="DEPENDENCY_BLOCKED",
                message=(
                    f"Open prerequisites block planning for "
                    f"{record['subject_id']}: {', '.join(record['open_prerequisites'])}."
                ),
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                references=record["open_prerequisites"],
                metadata=record,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.APPLIED,
                findings=(finding,),
                code="DEPENDENCY_BLOCKED",
                message="Open prerequisites flagged; no auto-enrolment.",
            )
        finding = ReasoningFinding(
            code="DEPENDENCY_SATISFIED",
            message=f"Prerequisites satisfied for {record['subject_id']}.",
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            references=record["satisfied_prerequisites"],
            metadata=record,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="DEPENDENCY_SATISFIED",
            message="Prerequisites satisfied; dependency resolved.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ObservedPerformanceCapacityRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ObservedPerformanceCapacityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        performance = _mapping(context.metadata, "performance_observation")
        if performance is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No performance observation supplied.",
            )
        record = evaluate_performance_capacity(performance_observation=performance)
        references = (
            (record["performance_ref"],)
            if record.get("performance_ref")
            else ()
        )
        finding = ReasoningFinding(
            code="PERFORMANCE_NOT_CAPACITY",
            message=(
                "Observed academic performance is a fact about output, never a "
                "measure of intellectual capacity; capacity is never inferred "
                "from performance."
            ),
            severity=ReasoningSeverity.WARNING,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            references=references,
            metadata={"capacity_inferred": False},
        )
        escalation = ReasoningEscalation(
            code="CAPACITY_INFERENCE_BLOCKED",
            message="Intellectual capacity inference from performance is blocked.",
            severity=ReasoningSeverity.WARNING,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            escalation=escalation,
            code="PERFORMANCE_NOT_CAPACITY",
            message="Performance kept distinct from capacity.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AcademicIntegrityRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AcademicIntegrityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        integrity = _mapping(context.metadata, "integrity")
        if integrity is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No integrity metadata supplied.",
            )
        mode = str(integrity.get("mode", INTEGRITY_MODE_C))
        # Academic Integrity Mode C is permissive-by-default (spec §17): the
        # domain does not police academic conduct; it only preserves the user's
        # stated mode and never substitutes its own integrity policing for the
        # institution's rules.
        if mode not in (INTEGRITY_MODE_A, INTEGRITY_MODE_B, INTEGRITY_MODE_C):
            finding = ReasoningFinding(
                code="INTEGRITY_MODE_REJECTED",
                message=f"Unknown integrity mode {mode!r}; blocked.",
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,),
                code="INTEGRITY_MODE_REJECTED",
                message="Unsupported integrity mode blocked.",
            )
        finding = ReasoningFinding(
            code="INTEGRITY_MODE_PRESERVED",
            message=(
                f"Academic integrity mode {mode} preserved; the domain does not "
                "substitute its own policing for institutional rules."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={"mode": mode},
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="INTEGRITY_MODE_PRESERVED",
            message="Academic integrity mode preserved (Mode C permissive by default).",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AcademicDecisionPreservationRule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AcademicDecisionPreservationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        decision_support = _mapping(context.metadata, "decision_support")
        if decision_support is None:
            return _result(
                self.definition,
                context,
                ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No decision-support metadata supplied.",
            )
        finding = ReasoningFinding(
            code="DECISION_NOT_ADOPTED",
            message=(
                "Decision support compares options against explicit criteria; "
                "no academic decision is adopted, persisted, or executed."
            ),
            severity=ReasoningSeverity.INFO,
            rule_id=self.definition.id,
            domain_id=self.definition.domain_id,
            metadata={"adopted_decision": False, "requires_user_confirmation": True},
        )
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=(finding,),
            code="DECISION_NOT_ADOPTED",
            message="Academic decision preserved for the user; never adopted.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════════


def build_university_rules() -> tuple[Any, ...]:
    """Build the ten University Domain rules deterministically in canonical order."""
    by_id = {
        "university.academic_contradiction": AcademicContradictionRule(
            definition=_definition(
                "university.academic_contradiction",
                "AcademicContradictionRule",
                ReasoningRuleCategory.CONSISTENCY.value,
                740,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "university.academic_deadline": AcademicDeadlineRule(
            definition=_definition(
                "university.academic_deadline",
                "AcademicDeadlineRule",
                ReasoningRuleCategory.TEMPORALITY.value,
                730,
            )
        ),
        "university.academic_decision_preservation": AcademicDecisionPreservationRule(
            definition=_definition(
                "university.academic_decision_preservation",
                "AcademicDecisionPreservationRule",
                ReasoningRuleCategory.SAFETY.value,
                770,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "university.academic_dependency": AcademicDependencyRule(
            definition=_definition(
                "university.academic_dependency",
                "AcademicDependencyRule",
                ReasoningRuleCategory.CONSISTENCY.value,
                750,
            )
        ),
        "university.academic_integrity": AcademicIntegrityRule(
            definition=_definition(
                "university.academic_integrity",
                "AcademicIntegrityRule",
                ReasoningRuleCategory.SAFETY.value,
                790,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
        "university.academic_source_authority": AcademicSourceAuthorityRule(
            definition=_definition(
                "university.academic_source_authority",
                "AcademicSourceAuthorityRule",
                ReasoningRuleCategory.EPISTEMIC.value,
                720,
            )
        ),
        "university.academic_workload": AcademicWorkloadRule(
            definition=_definition(
                "university.academic_workload",
                "AcademicWorkloadRule",
                ReasoningRuleCategory.INFERENCE.value,
                760,
            )
        ),
        "university.ects_consistency": EctsConsistencyRule(
            definition=_definition(
                "university.ects_consistency",
                "EctsConsistencyRule",
                ReasoningRuleCategory.CONSISTENCY.value,
                735,
            )
        ),
        "university.exam_attempt": ExamAttemptRule(
            definition=_definition(
                "university.exam_attempt",
                "ExamAttemptRule",
                ReasoningRuleCategory.INFERENCE.value,
                745,
            )
        ),
        "university.observed_performance_capacity": ObservedPerformanceCapacityRule(
            definition=_definition(
                "university.observed_performance_capacity",
                "ObservedPerformanceCapacityRule",
                ReasoningRuleCategory.SAFETY.value,
                780,
                risk_level=ReasoningRiskLevel.MEDIUM,
            )
        ),
    }
    return tuple(by_id[rule_id] for rule_id in UNIVERSITY_RULE_IDS)


__all__ = [
    "CONTRADICTION_MATERIAL",
    "CONTRADICTION_RESOLVED",
    "CONTRADICTION_UNRESOLVED",
    "INTEGRITY_MODE_A",
    "INTEGRITY_MODE_B",
    "INTEGRITY_MODE_C",
    "SOURCE_AUTHORITY_ATTRIBUTE",
    "SOURCE_AUTHORITY_INFERRED",
    "SOURCE_AUTHORITY_OFFICIAL",
    "SOURCE_AUTHORITY_REGULATION",
    "SOURCE_AUTHORITY_UNKNOWN",
    "SOURCE_AUTHORITY_USER_REPORTED",
    "UNIVERSITY_RULE_IDS",
    "AcademicContradictionRule",
    "AcademicDeadlineRule",
    "AcademicDecisionPreservationRule",
    "AcademicDependencyRule",
    "AcademicIntegrityRule",
    "AcademicSourceAuthorityRule",
    "AcademicWorkloadRule",
    "EctsConsistencyRule",
    "ExamAttemptRule",
    "ObservedPerformanceCapacityRule",
    "build_university_rules",
    "check_ects_consistency",
    "evaluate_academic_contradiction",
    "evaluate_academic_dependency",
    "evaluate_academic_workload",
    "evaluate_deadline",
    "evaluate_exam_attempt",
    "evaluate_performance_capacity",
    "resolve_source_authority_by_attribute",
]