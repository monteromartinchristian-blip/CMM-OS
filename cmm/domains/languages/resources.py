"""Phase 10.26 — Languages Domain Resources.

Builds the fifteen Languages resource definitions deterministically using the
shared ``DomainResourceDefinition`` and ``DomainResourceTemporalPolicy``
contracts.  No resource store is created here: resources are definitions only.

Shared-resource principle: ``user_message``, ``conversation``, ``writing_sample``,
``audio_transcript``, ``exercise_result``, ``assessment_result``, ``language_plan``,
``lesson_material``, ``vocabulary_list``, ``language_reference``,
``certification_guide``, ``official_certification_source``, ``calendar_event``,
``memory_entry`` and ``domain_result`` reuse the shared cognitive adapters.
Resource metadata never creates truth: ``audio_transcript`` metadata clarifies
that transcript is not pronunciation evidence by itself; ``domain_result``
is the minimal authorized cross-domain projection boundary; ``memory_entry``
is provenance (proposal state), not current truth; and
``official_certification_source`` is official reference, not external search.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.languages.catalog import (
    CANONICAL_LANGUAGES_RESOURCE_IDS,
    LANGUAGES_RESOURCE_KINDS,
)
from cmm.domains.resource_contracts import (
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)

__all__ = ["LANGUAGES_RESOURCE_KINDS", "build_languages_resource_definitions"]


def _resource(
    resource_id: str,
    *,
    adapter: str,
    entity_types: tuple[str, ...],
    sensitivity: SensitivityLevel,
    reliability: float,
    effective_date_required: bool = False,
    expiration_required: bool = False,
    metadata: dict | None = None,
) -> DomainResourceDefinition:
    return DomainResourceDefinition(
        id=resource_id,
        kind=resource_id.split(".", 1)[1],
        domain_id="domain:languages",
        adapter=adapter,
        entity_types=entity_types,
        default_sensitivity=sensitivity,
        default_reliability=reliability,
        temporal_policy=DomainResourceTemporalPolicy(
            effective_date_required=effective_date_required,
            expiration_required=expiration_required,
            historical_allowed=True,
        ),
        metadata=metadata or {},
    )


def build_languages_resource_definitions() -> tuple[DomainResourceDefinition, ...]:
    """Build the fifteen Languages Domain resource definitions deterministically.

    Definitions are returned in canonical order (catalog order).
    """
    by_id = {
        "languages.user_message": _resource(
            "languages.user_message",
            adapter="cognitive.message",
            entity_types=("language", "language_goal", "observed_error"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.5,
            metadata={"provenance": True, "user_reported": True, "unverified": True},
        ),
        "languages.conversation": _resource(
            "languages.conversation",
            adapter="cognitive.conversation",
            entity_types=("language", "language_variety", "practice_session", "observed_error"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.6,
            metadata={"provenance": True, "practice_session": True},
        ),
        "languages.writing_sample": _resource(
            "languages.writing_sample",
            adapter="cognitive.note",
            entity_types=("language", "practice_session", "assessment_evidence", "observed_error"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.7,
            metadata={"provenance": True, "user_production": True},
        ),
        "languages.audio_transcript": _resource(
            "languages.audio_transcript",
            adapter="cognitive.note",
            entity_types=("language", "practice_session", "assessment_evidence", "observed_error"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.6,
            metadata={
                "provenance": True,
                "user_production": True,
                "pronunciation_evidence": False,
            },
        ),
        "languages.exercise_result": _resource(
            "languages.exercise_result",
            adapter="cognitive.event",
            entity_types=("exercise", "assessment_evidence", "observed_error"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.7,
            metadata={"provenance": True, "observed_performance": True},
        ),
        "languages.assessment_result": _resource(
            "languages.assessment_result",
            adapter="cognitive.event",
            entity_types=("proficiency_record", "assessment_evidence", "skill_dimension"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.75,
            effective_date_required=True,
            metadata={"provenance": True, "temporality": True, "epistemic_distinction": True},
        ),
        "languages.language_plan": _resource(
            "languages.language_plan",
            adapter="cognitive.goal",
            entity_types=("learning_plan", "language_goal", "certification_target"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.7,
            effective_date_required=True,
            metadata={"provenance": True, "temporality": True, "multi_goal": True},
        ),
        "languages.lesson_material": _resource(
            "languages.lesson_material",
            adapter="cognitive.note",
            entity_types=("exercise", "grammar_topic", "vocabulary_item"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.8,
            metadata={"pedagogical_material": True},
        ),
        "languages.vocabulary_list": _resource(
            "languages.vocabulary_list",
            adapter="cognitive.note",
            entity_types=("vocabulary_item", "review_item"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.7,
            metadata={"provenance": True, "review_backlog": True},
        ),
        "languages.language_reference": _resource(
            "languages.language_reference",
            adapter="cognitive.note",
            entity_types=("language", "language_variety", "grammar_topic", "vocabulary_item"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.85,
            metadata={"linguistic_reference": True, "variety_aware": True},
        ),
        "languages.certification_guide": _resource(
            "languages.certification_guide",
            adapter="cognitive.note",
            entity_types=("certification_target", "proficiency_framework"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.7,
            metadata={"secondary_source": True, "guide_only": True},
        ),
        "languages.official_certification_source": _resource(
            "languages.official_certification_source",
            adapter="cognitive.event",
            entity_types=("certification_target", "proficiency_framework"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.9,
            effective_date_required=True,
            metadata={"official_source": True, "temporality": True, "read_only": True},
        ),
        "languages.calendar_event": _resource(
            "languages.calendar_event",
            adapter="cognitive.event",
            entity_types=("practice_session", "certification_target", "language_goal"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.7,
            effective_date_required=True,
            metadata={"provenance": True, "temporality": True, "schedule_proposal_only": True},
        ),
        "languages.memory_entry": _resource(
            "languages.memory_entry",
            adapter="cognitive.memory",
            entity_types=("proficiency_record", "language_goal", "error_pattern", "review_item", "learning_plan"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.7,
            metadata={
                "memory_integration": True,
                "proposal_only": True,
                "provenance_not_truth": True,
            },
        ),
        "languages.domain_result": _resource(
            "languages.domain_result",
            adapter="cognitive.event",
            entity_types=("language_goal", "proficiency_record", "certification_target", "assessment_evidence"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.75,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "cross_domain_projection": True,
                "minimal_authorized_projection": True,
            },
        ),
    }
    return tuple(
        by_id[resource_id]
        for resource_id in CANONICAL_LANGUAGES_RESOURCE_IDS
    )
