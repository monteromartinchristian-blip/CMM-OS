"""Phase 10.24 — Reflection Domain canonical catalog tests.

The catalog module is the single source of truth for the frozen canonical
members (spec §5).  These tests pin the exact 11/9/6/9/6 surface plus the
14-module package boundary and clean-import behavior.
"""

from __future__ import annotations

from pathlib import Path

from cmm.domains.reflection.catalog import (
    CANONICAL_REFLECTION_ENTITY_TYPES,
    CANONICAL_REFLECTION_OPERATION_IDS,
    CANONICAL_REFLECTION_RESOURCE_IDS,
    CANONICAL_REFLECTION_RULE_IDS,
    CANONICAL_REFLECTION_RULE_NAMES,
    CANONICAL_REFLECTION_WORKFLOW_IDS,
    CANONICAL_REFLECTION_WORKFLOW_NAMES,
    REFLECTION_RESOURCE_KINDS,
)


def test_entities_exactly_11():
    assert CANONICAL_REFLECTION_ENTITY_TYPES == (
        "reflection",
        "belief",
        "value",
        "question",
        "hypothesis",
        "emotion",
        "need",
        "conflict",
        "identity_narrative",
        "decision",
        "uncertainty",
    )
    assert len(CANONICAL_REFLECTION_ENTITY_TYPES) == 11


def test_resources_exactly_9():
    assert REFLECTION_RESOURCE_KINDS == (
        "user_message",
        "conversation",
        "note",
        "journal_entry",
        "memory_entry",
        "relationship_event",
        "life_event",
        "goal",
        "decision",
    )
    assert len(REFLECTION_RESOURCE_KINDS) == 9
    assert CANONICAL_REFLECTION_RESOURCE_IDS == tuple(
        f"reflection.{kind}" for kind in REFLECTION_RESOURCE_KINDS
    )


def test_rules_exactly_6():
    assert CANONICAL_REFLECTION_RULE_NAMES == (
        "MultipleHypothesesRule",
        "PreserveAmbivalenceRule",
        "BeliefEvidenceRule",
        "OpenQuestionRule",
        "ReflectionTemporalEvolutionRule",
        "NoForcedConclusionRule",
    )
    assert len(CANONICAL_REFLECTION_RULE_NAMES) == 6
    assert CANONICAL_REFLECTION_RULE_IDS == (
        "reflection.multiple_hypotheses",
        "reflection.preserve_ambivalence",
        "reflection.belief_evidence",
        "reflection.open_question",
        "reflection.temporal_evolution",
        "reflection.no_forced_conclusion",
    )


def test_operations_exactly_9():
    assert CANONICAL_REFLECTION_OPERATION_IDS == (
        "reflection.structure_reflection",
        "reflection.extract_beliefs",
        "reflection.compare_versions",
        "reflection.identify_open_questions",
        "reflection.generate_hypotheses",
        "reflection.build_personal_timeline",
        "reflection.prepare_notion_entry",
        "reflection.generate_summary",
        "reflection.review_decision",
    )
    assert len(CANONICAL_REFLECTION_OPERATION_IDS) == 9


def test_workflow_names_exactly_6():
    assert CANONICAL_REFLECTION_WORKFLOW_NAMES == (
        "Structured Reflection",
        "Belief Review",
        "Personal Question Exploration",
        "Decision Reflection",
        "Identity Narrative Review",
        "Longitudinal Reflection Review",
    )
    assert len(CANONICAL_REFLECTION_WORKFLOW_NAMES) == 6
    assert CANONICAL_REFLECTION_WORKFLOW_IDS == (
        "reflection.structured_reflection",
        "reflection.belief_review",
        "reflection.personal_question_exploration",
        "reflection.decision_reflection",
        "reflection.identity_narrative_review",
        "reflection.longitudinal_review",
    )


def test_no_duplicates():
    for values in (
        CANONICAL_REFLECTION_ENTITY_TYPES,
        CANONICAL_REFLECTION_RESOURCE_IDS,
        CANONICAL_REFLECTION_RULE_IDS,
        CANONICAL_REFLECTION_OPERATION_IDS,
        CANONICAL_REFLECTION_WORKFLOW_IDS,
    ):
        assert len(values) == len(set(values))


def test_operation_prefix_is_reflection():
    for operation_id in CANONICAL_REFLECTION_OPERATION_IDS:
        assert operation_id.startswith("reflection.")
        assert operation_id.count(".") == 1


def test_package_boundary_exactly_14_modules():
    """Production package contains exactly the 14 frozen modules (spec §3)."""
    package_dir = Path(__file__).resolve().parents[2] / "cmm" / "domains" / "reflection"
    modules = sorted(
        path.name
        for path in package_dir.glob("*.py")
        if path.name != "__pycache__"
    )
    assert modules == [
        "__init__.py",
        "bootstrap.py",
        "catalog.py",
        "definition.py",
        "integration.py",
        "memory.py",
        "operations.py",
        "permissions.py",
        "presentation.py",
        "profile.py",
        "resources.py",
        "rules.py",
        "trace.py",
        "workflows.py",
    ]


def test_clean_import_does_not_register_globally():
    """``import cmm.domains.reflection`` must not mutate global registration."""
    import cmm.domains.reflection  # noqa: F401
    from cmm.domains.registry import DomainRegistry

    registry = DomainRegistry()
    assert registry.get("domain:reflection") is None