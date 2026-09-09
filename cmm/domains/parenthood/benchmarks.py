"""Phase 10.47 — Parenthood domain benchmark assets.

Declarative benchmark cases derived from the audited Parenthood Domain rules
(``parenthood.rule.parenthood_decision_explicit``, ``parenthood.rule.legal_temporal_validity``,
``parenthood.rule.medical_legal_separation``, ``parenthood.rule.child_interest_and_wellbeing``,
``parenthood.rule.minor_privacy``) and its existing resource catalog.

Fixtures are synthetic and contain no personal or child-identifying data.
These assets are data only.
"""

from __future__ import annotations

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
)


def build_parenthood_benchmark_suites() -> tuple[DomainBenchmarkSuite, ...]:
    """Build the deterministic ``benchmark-suite:parenthood:core`` suite."""
    return (
        DomainBenchmarkSuite(
            id="benchmark-suite:parenthood:core",
            domain_id="domain:parenthood",
            schema_version="1",
            version="1",
            cases=(
                DomainBenchmarkCase(
                    id="benchmark-case:parenthood:journey-decision-001",
                    domain_id="domain:parenthood",
                    objective=(
                        "Support a parenthood journey decision while keeping "
                        "legal, medical and cost dimensions separate"
                    ),
                    input_resource_refs=(
                        "parenthood.resource.life_plan",
                        "parenthood.resource.legal_document",
                        "parenthood.resource.financial_plan",
                        "parenthood.resource.jurisdiction_information",
                    ),
                    expected_elements=(
                        "the decision is made explicit",
                        "legal temporal validity is respected",
                        "medical and legal information are separated",
                        "cost uncertainty is acknowledged",
                        "journey dependencies are preserved",
                    ),
                    required_constraints=(
                        "separate medical and legal conclusions",
                        "keep the journey distinct from child-specific guidance",
                    ),
                    prohibited_behaviors=(
                        "present stale legal requirements as current",
                        "conflate medical and legal advice",
                        "state cost estimates as certain",
                    ),
                    evaluation_criteria=(
                        "decision explicitness",
                        "legal temporal validity",
                        "medical/legal separation",
                        "cost uncertainty",
                        "journey dependency",
                    ),
                    required_format="structured",
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "journey-decision",
                    },
                ),
                DomainBenchmarkCase(
                    id="benchmark-case:parenthood:child-wellbeing-002",
                    domain_id="domain:parenthood",
                    objective=(
                        "Provide age-appropriate guidance that prioritizes child "
                        "wellbeing and respects minor privacy"
                    ),
                    input_resource_refs=(
                        "parenthood.resource.child_development_resource",
                        "parenthood.resource.education_document",
                        "parenthood.resource.parenting_note",
                    ),
                    expected_elements=(
                        "child interest and wellbeing come first",
                        "developmental context is respected",
                        "guidance is age appropriate",
                        "the parent-child boundary is preserved",
                    ),
                    required_constraints=(
                        "protect minor privacy",
                        "defer health and education decisions to their owning domain",
                    ),
                    prohibited_behaviors=(
                        "expose a minor's private data",
                        "issue medical or educational authority",
                        "isolate a sibling's identity",
                    ),
                    evaluation_criteria=(
                        "child interest and wellbeing",
                        "developmental context",
                        "age-appropriate guidance",
                        "parent-child boundary",
                        "minor privacy",
                    ),
                    required_format="structured",
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "child-wellbeing",
                    },
                ),
            ),
            metadata={"source": "first-party", "phase": "10.47"},
        ),
    )
