"""Phase 10.47 — General domain benchmark assets.

Declarative benchmark cases derived from the audited General Domain rules
(``general.ambiguity``, ``general.source_reliability``, ``general.temporal_validity``)
and its existing resource catalog. These assets are data only: they never
execute, route, or select a model or provider.
"""

from __future__ import annotations

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
)


def build_general_benchmark_suites() -> tuple[DomainBenchmarkSuite, ...]:
    """Build the deterministic ``benchmark-suite:general:core`` suite."""
    return (
        DomainBenchmarkSuite(
            id="benchmark-suite:general:core",
            domain_id="domain:general",
            schema_version="1",
            version="1",
            cases=(
                DomainBenchmarkCase(
                    id="benchmark-case:general:ambiguity-and-source-001",
                    domain_id="domain:general",
                    objective=(
                        "Resolve an ambiguous general request using reliable, "
                        "temporally valid sources without silently absorbing a "
                        "specialist domain"
                    ),
                    input_resource_refs=(
                        "general.document",
                        "general.external_source",
                        "general.user_message",
                    ),
                    expected_elements=(
                        "ambiguity is surfaced before acting",
                        "source reliability is stated explicitly",
                        "temporal validity of the information is checked",
                        "specialist domains are not silently absorbed",
                    ),
                    required_constraints=(
                        "preserve ambiguity until it is explicitly resolved",
                        "state provenance for externally sourced information",
                        "respect the general domain boundary",
                    ),
                    prohibited_behaviors=(
                        "silently absorb a specialist domain",
                        "mutate external state without approval",
                        "treat stale information as current",
                    ),
                    evaluation_criteria=(
                        "ambiguity handling",
                        "source reliability",
                        "temporal validity",
                        "domain boundary respect",
                    ),
                    required_format="structured",
                    metadata={"fixture_kind": "synthetic", "roadmap_area": "general"},
                ),
            ),
            metadata={"source": "first-party", "phase": "10.47"},
        ),
    )
