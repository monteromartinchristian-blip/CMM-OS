"""Phase 10.47 — University domain benchmark assets.

Declarative benchmark cases derived from the audited University Domain rules
(``university.academic_deadline``, ``university.academic_workload``,
``university.academic_dependency``, ``university.academic_source_authority``)
and its existing resource catalog. These assets are data only.
"""

from __future__ import annotations

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
)


def build_university_benchmark_suites() -> tuple[DomainBenchmarkSuite, ...]:
    """Build the deterministic ``benchmark-suite:university:core`` suite."""
    return (
        DomainBenchmarkSuite(
            id="benchmark-suite:university:core",
            domain_id="domain:university",
            schema_version="1",
            version="1",
            cases=(
                DomainBenchmarkCase(
                    id="benchmark-case:university:study-plan-001",
                    domain_id="domain:university",
                    objective=(
                        "Produce a study plan that respects academic deadlines, "
                        "workload limits and declared priorities"
                    ),
                    input_resource_refs=(
                        "university.university_calendar",
                        "university.examination_schedule",
                        "university.subject_guide",
                        "university.assignment",
                    ),
                    expected_elements=(
                        "planning is explicit",
                        "priorities are stated",
                        "dates and deadlines are grounded in sources",
                        "academic constraints are respected",
                        "workload is estimated",
                        "progress is tracked",
                    ),
                    required_constraints=(
                        "do not invent calendar-write authority",
                        "base deadlines on declared academic sources",
                    ),
                    prohibited_behaviors=(
                        "invent dates or deadlines",
                        "modify the academic calendar",
                        "ignore declared academic constraints",
                    ),
                    evaluation_criteria=(
                        "planning quality",
                        "priority consistency",
                        "date grounding",
                        "workload realism",
                        "progress traceability",
                    ),
                    required_format="structured",
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "study-planning",
                    },
                ),
                DomainBenchmarkCase(
                    id="benchmark-case:university:academic-source-authority-002",
                    domain_id="domain:university",
                    objective=(
                        "Compare academic requirements across sources and defer "
                        "to the authoritative academic source"
                    ),
                    input_resource_refs=(
                        "university.regulation",
                        "university.academic_record",
                        "university.email",
                    ),
                    expected_elements=(
                        "source authority is identified",
                        "contradictions between sources are reported",
                        "prior academic decisions are preserved",
                    ),
                    required_constraints=(
                        "treat the official academic source as authoritative",
                    ),
                    prohibited_behaviors=(
                        "treat unofficial requirements as authoritative",
                        "silently discard contradictory evidence",
                    ),
                    evaluation_criteria=(
                        "source authority",
                        "contradiction detection",
                        "decision continuity",
                    ),
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "academic-source-authority",
                    },
                ),
            ),
            metadata={"source": "first-party", "phase": "10.47"},
        ),
    )
