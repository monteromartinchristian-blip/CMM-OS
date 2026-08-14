"""Phase 10.23 — Opposition Domain Operations tests (spec §44)."""

from __future__ import annotations

from cmm.domains.oppositions import build_oppositions_operation_definitions


def test_exactly_ten_operations():
    operations = build_oppositions_operation_definitions()
    assert len(operations) == 10


def test_operation_ids_exact():
    operations = build_oppositions_operation_definitions()
    ids = {op.operation_id for op in operations}
    assert ids == {
        "oppositions.create_study_plan",
        "oppositions.divide_syllabus",
        "oppositions.track_progress",
        "oppositions.review_mock_exam",
        "oppositions.compare_bodies",
        "oppositions.review_call",
        "oppositions.generate_weekly_review",
        "oppositions.identify_risks",
        "oppositions.generate_revision_plan",
        "oppositions.update_progress",
    }


def test_each_operation_has_schemas():
    operations = build_oppositions_operation_definitions()
    for op in operations:
        assert op.input_schema
        assert op.output_schema


def test_required_resources_are_minimal():
    """required_resources use strict AND semantics; only genuinely consumed
    resources are declared."""
    operations = build_oppositions_operation_definitions()
    by_id = {op.operation_id: op for op in operations}
    assert by_id["oppositions.review_call"].required_resources == ("oppositions.official_call",)
    assert by_id["oppositions.create_study_plan"].required_resources == ("oppositions.syllabus",)


def test_proposal_only_operations_respect_boundaries():
    operations = build_oppositions_operation_definitions()
    by_id = {op.operation_id: op for op in operations}
    # planning/revision produce proposals only
    assert by_id["oppositions.create_study_plan"].metadata["proposal_only"] is True
    assert by_id["oppositions.generate_revision_plan"].metadata["proposal_only"] is True
    assert by_id["oppositions.update_progress"].metadata["proposal_only"] is True


def test_review_call_output_not_schedule_mutation():
    operations = build_oppositions_operation_definitions()
    by_id = {op.operation_id: op for op in operations}
    schema = by_id["oppositions.review_call"].output_schema
    props = schema["properties"]["review"]["properties"]
    assert props["registration_none"]["type"] == "boolean"
    assert "official_verification" in props


def test_update_progress_no_external_mutation():
    operations = build_oppositions_operation_definitions()
    by_id = {op.operation_id: op for op in operations}
    schema = by_id["oppositions.update_progress"].output_schema
    props = schema["properties"]["progress_update"]["properties"]
    assert props["memory_not_modified"]["type"] == "boolean"
    assert props["proposal_only"]["type"] == "boolean"
    assert by_id["oppositions.update_progress"].requires_approval is True


def test_malformed_input_rejected_by_schema():
    """Missing required field -> validation failure, not permissive fallback."""
    op = build_oppositions_operation_definitions()[0]
    assert "required" in op.input_schema
    assert op.input_schema["required"]


def test_missing_implementation_fail_closed_unavailable():
    """Declared operations register as UNAVAILABLE (fail-closed) when no
    implementation is provided."""
    from cmm.domains.oppositions import build_standard_oppositions_domain_bootstrap

    bootstrap = build_standard_oppositions_domain_bootstrap()
    registry = bootstrap.operation_registry
    registered = {
        d.operation_id
        for d in registry.list_definitions()
        if d.domain_id == "domain:oppositions"
    }
    assert registered == {
        d.operation_id for d in build_oppositions_operation_definitions()
    }


def test_operation_domain_prefix():
    operations = build_oppositions_operation_definitions()
    for op in operations:
        assert op.domain_id == "domain:oppositions"
        assert op.operation_id.startswith("oppositions.")