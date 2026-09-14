"""Phase 10.47 — Sport domain benchmark assets.

Declarative benchmark cases derived from the audited Sport Domain rules
(``sport.rule.training_load``, ``sport.rule.progressive_overload``,
``sport.rule.recovery``, ``sport.rule.injury_signal``,
``sport.rule.health_constraint``, ``sport.rule.measurement_trend``) and its
existing resource catalog. These assets are data only; they create no medical
authority and never execute a training program.
"""

from __future__ import annotations

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
)


def build_sport_benchmark_suites() -> tuple[DomainBenchmarkSuite, ...]:
    """Build the deterministic ``benchmark-suite:sport:core`` suite."""
    return (
        DomainBenchmarkSuite(
            id="benchmark-suite:sport:core",
            domain_id="domain:sport",
            schema_version="1",
            version="1",
            cases=(
                DomainBenchmarkCase(
                    id="benchmark-case:sport:training-load-001",
                    domain_id="domain:sport",
                    objective=(
                        "Review a training block and recommend a load adjustment "
                        "that respects recovery and health constraints"
                    ),
                    input_resource_refs=(
                        "sport.resource.workout_log",
                        "sport.resource.training_plan",
                        "sport.resource.body_measurement",
                        "sport.resource.wearable_data",
                    ),
                    expected_elements=(
                        "training load is quantified",
                        "progressive overload is respected",
                        "recovery is considered",
                        "injury signals are surfaced",
                        "health constraints are respected",
                        "measurement trends are reported",
                    ),
                    required_constraints=(
                        "treat health constraints as binding",
                        "escalate injury signals to the health domain",
                    ),
                    prohibited_behaviors=(
                        "ignore injury signals",
                        "override a declared health constraint",
                        "issue medical authority",
                    ),
                    evaluation_criteria=(
                        "training load",
                        "progressive overload",
                        "recovery",
                        "injury signal",
                        "health constraint",
                        "measurement trend",
                    ),
                    required_format="structured",
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "training-load",
                    },
                ),
            ),
            metadata={"source": "first-party", "phase": "10.47"},
        ),
    )
