"""Phase 10.47 — Reflection domain benchmark assets.

Declarative benchmark cases derived from the audited Reflection Domain rules
(``reflection.multiple_hypotheses``, ``reflection.preserve_ambivalence``,
``reflection.belief_evidence``, ``reflection.open_question``,
``reflection.no_forced_conclusion``) and its existing resource catalog.
These assets are data only.
"""

from __future__ import annotations

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
)


def build_reflection_benchmark_suites() -> tuple[DomainBenchmarkSuite, ...]:
    """Build the deterministic ``benchmark-suite:reflection:core`` suite."""
    return (
        DomainBenchmarkSuite(
            id="benchmark-suite:reflection:core",
            domain_id="domain:reflection",
            schema_version="1",
            version="1",
            cases=(
                DomainBenchmarkCase(
                    id="benchmark-case:reflection:hypotheses-001",
                    domain_id="domain:reflection",
                    objective=(
                        "Structure a personal reflection keeping observation, "
                        "interpretation and hypothesis distinct"
                    ),
                    input_resource_refs=(
                        "reflection.journal_entry",
                        "reflection.note",
                        "reflection.user_message",
                    ),
                    expected_elements=(
                        "observation, interpretation and hypothesis are separated",
                        "ambivalence is preserved",
                        "open questions are recorded",
                        "uncertainty is preserved",
                        "temporal evolution of the reflection is respected",
                    ),
                    required_constraints=(
                        "keep competing hypotheses available",
                        "link beliefs to their supporting evidence",
                    ),
                    prohibited_behaviors=(
                        "promote a hypothesis to a diagnosis",
                        "force a conclusion",
                        "make a personal decision on the user's behalf",
                    ),
                    evaluation_criteria=(
                        "hypothesis separation",
                        "ambivalence preservation",
                        "open-question quality",
                        "uncertainty preservation",
                        "no forced conclusion",
                    ),
                    required_format="structured",
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "hypotheses-and-ambivalence",
                    },
                ),
            ),
            metadata={"source": "first-party", "phase": "10.47"},
        ),
    )
