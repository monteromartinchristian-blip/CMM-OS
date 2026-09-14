"""Phase 10.47 — Languages domain benchmark assets.

Declarative benchmark cases derived from the audited Languages Domain rules
(``languages.language_level_evidence``, ``languages.skill_separation``,
``languages.error_pattern_evidence``, ``languages.progression_evidence``,
``languages.certification_temporal``) and its existing resource catalog.
These assets are data only; they do not create a learning engine.
"""

from __future__ import annotations

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
)


def build_languages_benchmark_suites() -> tuple[DomainBenchmarkSuite, ...]:
    """Build the deterministic ``benchmark-suite:languages:core`` suite."""
    return (
        DomainBenchmarkSuite(
            id="benchmark-suite:languages:core",
            domain_id="domain:languages",
            schema_version="1",
            version="1",
            cases=(
                DomainBenchmarkCase(
                    id="benchmark-case:languages:proficiency-evidence-001",
                    domain_id="domain:languages",
                    objective=(
                        "Assess a language learner's level from evidence and plan "
                        "the next learning step"
                    ),
                    input_resource_refs=(
                        "languages.writing_sample",
                        "languages.exercise_result",
                        "languages.assessment_result",
                        "languages.language_plan",
                    ),
                    expected_elements=(
                        "level is supported by evidence",
                        "skills are separated",
                        "language variety validity is respected",
                        "a proficiency framework is applied",
                        "error patterns are evidenced",
                        "correction priority is explicit",
                        "difficulty adapts to the learner",
                        "spaced review is considered",
                        "learning load is respected",
                        "goals are aligned",
                        "progression is evidenced",
                        "certification timing is respected",
                        "cultural context is evidenced",
                    ),
                    required_constraints=(
                        "ground every level claim in observed evidence",
                        "respect language memory consent",
                    ),
                    prohibited_behaviors=(
                        "assert a proficiency level without evidence",
                        "conflate separate language skills",
                        "expose learning memory without consent",
                    ),
                    evaluation_criteria=(
                        "language level evidence",
                        "skill separation",
                        "language variety validity",
                        "proficiency framework",
                        "error pattern evidence",
                        "correction priority",
                        "adaptive difficulty",
                        "spaced review",
                        "learning load",
                        "goal alignment",
                        "progression evidence",
                        "certification temporal",
                        "cultural context evidence",
                        "language memory consent",
                    ),
                    required_format="structured",
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "proficiency-evidence",
                    },
                ),
            ),
            metadata={"source": "first-party", "phase": "10.47"},
        ),
    )
