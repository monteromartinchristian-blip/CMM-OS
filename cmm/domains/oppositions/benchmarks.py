"""Phase 10.47 — Oppositions domain benchmark assets.

Declarative benchmark cases derived from the audited Oppositions Domain rules
(``oppositions.official_call_priority``, ``oppositions.temporal_validity``,
``oppositions.syllabus_coverage``, ``oppositions.alternative_route``) and its
existing resource catalog. These assets are data only.
"""

from __future__ import annotations

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
)


def build_oppositions_benchmark_suites() -> tuple[DomainBenchmarkSuite, ...]:
    """Build the deterministic ``benchmark-suite:oppositions:core`` suite."""
    return (
        DomainBenchmarkSuite(
            id="benchmark-suite:oppositions:core",
            domain_id="domain:oppositions",
            schema_version="1",
            version="1",
            cases=(
                DomainBenchmarkCase(
                    id="benchmark-case:oppositions:official-call-001",
                    domain_id="domain:oppositions",
                    objective=(
                        "Track an official call and organize its syllabus using "
                        "current official sources"
                    ),
                    input_resource_refs=(
                        "oppositions.official_call",
                        "oppositions.regulation",
                        "oppositions.syllabus",
                        "oppositions.study_plan",
                    ),
                    expected_elements=(
                        "official sources take priority",
                        "current regulations are used",
                        "syllabus organization is explicit",
                        "call tracking is preserved",
                        "requirements are compared",
                        "continuity of prior decisions is respected",
                    ),
                    required_constraints=(
                        "prefer official and temporally valid sources",
                        "preserve prior decisions unless officially superseded",
                    ),
                    prohibited_behaviors=(
                        "treat stale or unofficial requirements as authoritative",
                        "invent requirements not present in official sources",
                        "discard the official call timeline",
                    ),
                    evaluation_criteria=(
                        "official-source priority",
                        "temporal validity",
                        "syllabus organization",
                        "requirement comparison",
                        "decision continuity",
                    ),
                    required_format="structured",
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "official-call-tracking",
                    },
                ),
            ),
            metadata={"source": "first-party", "phase": "10.47"},
        ),
    )
