"""Phase 10.47 — Life Plan domain benchmark assets.

Declarative benchmark cases derived from the audited Life Plan Domain rules
(``life_plan.rule.goal_dependency``, ``life_plan.rule.scenario_consistency``,
``life_plan.rule.resource_constraint``, ``life_plan.rule.alternative_route``,
``life_plan.rule.cross_domain_impact``, ``life_plan.rule.plan_drift``) and its
existing resource catalog. These assets are data only and encode no
user-specific life facts.
"""

from __future__ import annotations

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
)


def build_life_plan_benchmark_suites() -> tuple[DomainBenchmarkSuite, ...]:
    """Build the deterministic ``benchmark-suite:life-plan:core`` suite."""
    return (
        DomainBenchmarkSuite(
            id="benchmark-suite:life-plan:core",
            domain_id="domain:life-plan",
            schema_version="1",
            version="1",
            cases=(
                DomainBenchmarkCase(
                    id="benchmark-case:life-plan:scenario-tradeoff-001",
                    domain_id="domain:life-plan",
                    objective=(
                        "Compare two life-plan scenarios and expose their "
                        "trade-offs, dependencies and resource constraints"
                    ),
                    input_resource_refs=(
                        "life_plan.resource.life_plan",
                        "life_plan.resource.goal",
                        "life_plan.resource.financial_plan",
                        "life_plan.resource.decision",
                    ),
                    expected_elements=(
                        "goal dependencies are identified",
                        "scenarios are internally consistent",
                        "resource constraints are respected",
                        "decision status is explicit",
                        "long-term temporal effects are considered",
                        "alternative routes are offered",
                        "cross-domain impact is stated",
                    ),
                    required_constraints=(
                        "keep alternatives available",
                        "respect declared resource constraints",
                    ),
                    prohibited_behaviors=(
                        "present a scenario as the only option",
                        "ignore a declared resource constraint",
                        "silently drift from the recorded plan",
                    ),
                    evaluation_criteria=(
                        "goal dependency",
                        "scenario consistency",
                        "resource constraint",
                        "decision status",
                        "long-term temporal",
                        "alternative route",
                        "cross-domain impact",
                        "plan drift",
                    ),
                    required_format="structured",
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "scenario-tradeoff",
                    },
                ),
            ),
            metadata={"source": "first-party", "phase": "10.47"},
        ),
    )
