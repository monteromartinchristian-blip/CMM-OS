"""Phase 10.47 — Relationships domain benchmark assets.

Declarative benchmark cases derived from the audited Relationships Domain rules
(``relationships.separate_facts_interpretations``, ``relationships.do_not_infer_intent``,
``relationships.ambivalence_preservation``, ``relationships.pattern_without_certainty``)
and its existing resource catalog. These assets are data only.
"""

from __future__ import annotations

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
)


def build_relationships_benchmark_suites() -> tuple[DomainBenchmarkSuite, ...]:
    """Build the deterministic ``benchmark-suite:relationships:core`` suite."""
    return (
        DomainBenchmarkSuite(
            id="benchmark-suite:relationships:core",
            domain_id="domain:relationships",
            schema_version="1",
            version="1",
            cases=(
                DomainBenchmarkCase(
                    id="benchmark-case:relationships:fact-interpretation-001",
                    domain_id="domain:relationships",
                    objective=(
                        "Separate observed facts from interpretations when "
                        "reviewing a relationship episode"
                    ),
                    input_resource_refs=(
                        "relationships.conversation",
                        "relationships.relationship_event",
                        "relationships.user_message",
                    ),
                    expected_elements=(
                        "facts and interpretations are separated",
                        "ambiguity is preserved rather than resolved by assumption",
                        "uncertainty is preserved",
                        "useful clarifying questions are proposed",
                        "emotional continuity and tone are respected",
                    ),
                    required_constraints=(
                        "do not infer intent as fact",
                        "keep both perspectives available",
                    ),
                    prohibited_behaviors=(
                        "attribute unsupported intent",
                        "state a pattern as certainty",
                        "impose a stylistic personality",
                    ),
                    evaluation_criteria=(
                        "fact and interpretation separation",
                        "ambiguity preservation",
                        "uncertainty preservation",
                        "question usefulness",
                        "tone",
                    ),
                    required_format="structured",
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "fact-interpretation",
                    },
                ),
                DomainBenchmarkCase(
                    id="benchmark-case:relationships:ambivalence-001",
                    domain_id="domain:relationships",
                    objective=(
                        "Support reflection on an ambivalent relationship "
                        "decision without forcing a conclusion"
                    ),
                    input_resource_refs=(
                        "relationships.personal_reflection",
                        "relationships.timeline",
                        "relationships.note",
                    ),
                    expected_elements=(
                        "ambivalence is preserved",
                        "boundaries are considered consistently",
                        "patterns are described without certainty",
                    ),
                    required_constraints=(
                        "do not force a conclusion",
                        "respect established boundaries",
                    ),
                    prohibited_behaviors=(
                        "do not infer intent",
                        "pressure a decision",
                        "ignore stated boundaries",
                    ),
                    evaluation_criteria=(
                        "ambivalence preservation",
                        "boundary consistency",
                        "pattern description without certainty",
                    ),
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "ambivalence",
                    },
                ),
            ),
            metadata={"source": "first-party", "phase": "10.47"},
        ),
    )
