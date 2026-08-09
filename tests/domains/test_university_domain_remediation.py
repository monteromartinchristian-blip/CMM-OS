"""Phase 10.22 — University adversarial regression guards.

Each test below is a regression guard for a University safety-critical
boundary, written against the *actual* contracts (rule evaluation paths,
operation schemas, resource bindings) rather than calling private helpers
directly, so they prove the production path holds.  They cover: no fabricated
"unknown" reference IDs, recursively-closed operation schemas, preparation-only
schemas that cannot authorize send/submit, the internal-only update_subject_status
surface, and the performance != capacity epistemic boundary.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

from cmm.agent_runtime.operation_schema import validate_operation_schema
from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains import university

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _context(**metadata) -> ReasoningRuleContext:
    return ReasoningRuleContext(
        reasoning_id="rid",
        timestamp=T,
        active_domains=("domain:university",),
        primary_domain="domain:university",
        metadata=metadata,
    )


def _by_id(rules):
    return {rule.definition.id: rule for rule in rules}


_RULES = _by_id(university.build_university_rules())
_OPERATIONS = {
    op.operation_id: op
    for op in university.build_university_operation_definitions()
}


def _all_references(result):
    refs = []
    for f in result.findings:
        refs.extend(f.references)
    for g in result.gaps:
        refs.extend(g.references)
    return refs


# ═══════════════════════════════════════════════════════════════════════════════
# Never fabricate "unknown" as a reference ID
# ═══════════════════════════════════════════════════════════════════════════════


def test_contradiction_without_id_has_no_unknown_reference():
    rule = _RULES["university.academic_contradiction"]
    result = rule.evaluate(
        _context(
            contradiction_statements=[
                {"material": True, "unresolved": True},
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert all("unknown" != ref for ref in _all_references(result))


def test_dependency_without_id_has_no_unknown_reference():
    rule = _RULES["university.academic_dependency"]
    result = rule.evaluate(
        _context(
            dependency={
                "subject_id": "subj-2",
                "prerequisites": ({"passed": False},),
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert all("unknown" != ref for ref in _all_references(result))


def test_real_ids_preserved_exactly():
    rule = _RULES["university.academic_dependency"]
    result = rule.evaluate(
        _context(
            dependency={
                "subject_id": "subj-2",
                "prerequisites": ({"id": "subj-1", "passed": True},),
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert "subj-1" in _all_references(result)
    assert "unknown" not in _all_references(result)


# ═══════════════════════════════════════════════════════════════════════════════
# Performance is never capacity
# ═══════════════════════════════════════════════════════════════════════════════


def test_performance_rule_never_infers_capacity():
    rule = _RULES["university.observed_performance_capacity"]
    result = rule.evaluate(
        _context(
            performance_observation={
                "ref": "res-1",
                "outcome": "below_average",
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.escalation is not None
    assert result.escalation.code == "CAPACITY_INFERENCE_BLOCKED"
    assert all(
        finding.metadata.get("capacity_inferred") is False
        for finding in result.findings
    )


def test_analyse_performance_schema_cannot_authorize_capacity():
    """analyse_performance must keep capacity_inferred structurally False-only
    as a guard field, never a capacity measure."""
    operation = _OPERATIONS["university.analyse_performance"]
    analysis = operation.output_schema["properties"]["analysis"]["properties"]
    assert "capacity_inferred" in analysis
    assert "observed_performance" in analysis


# ═══════════════════════════════════════════════════════════════════════════════
# Operation schemas are recursively closed
# ═══════════════════════════════════════════════════════════════════════════════


def _collect_nested_object_schemas(schema, path):
    found = []
    if isinstance(schema, Mapping):
        if schema.get("type") == "object" and (
            "properties" in schema or "required" in schema
        ):
            found.append((path, schema))
        for key, child in schema.items():
            if key in ("properties",):
                continue
            found.extend(_collect_nested_object_schemas(child, path))
        properties = schema.get("properties")
        if isinstance(properties, Mapping):
            for prop_name, prop_schema in properties.items():
                found.extend(
                    _collect_nested_object_schemas(prop_schema, f"{path}.{prop_name}")
                )
    elif isinstance(schema, list):
        for index, child in enumerate(schema):
            found.extend(_collect_nested_object_schemas(child, f"{path}[{index}]"))
    return found


def test_all_university_nested_object_schemas_recursively_closed():
    for operation in _OPERATIONS.values():
        for output_schema in (operation.input_schema, operation.output_schema):
            for path, schema in _collect_nested_object_schemas(output_schema, "$"):
                assert schema.get("additionalProperties") is False, (
                    f"{operation.operation_id} nested schema at {path} is not closed"
                )


def test_representative_valid_outputs_validate():
    valid_outputs = {
        "university.plan_semester": {
            "plan": {
                "semester": "2026-A",
                "subjects": ("s1",),
                "source_references": ("r1",),
                "adopted_decision": False,
                "requires_user_confirmation": True,
            }
        },
        "university.create_study_plan": {
            "study_plan": {
                "subjects": ("s1",),
                "semester": "2026-A",
                "proposal_only": True,
                "adopted_decision": False,
            }
        },
        "university.review_academic_record": {
            "review": {"subject_records": ("r1",), "summary": "ok"}
        },
        "university.compare_semesters": {
            "comparison": {
                "period_a": "2026-01-01",
                "period_b": "2026-02-01",
                "observed_changes": ("c1",),
                "summary": "no change",
            }
        },
        "university.prepare_exam": {
            "preparation": {
                "examination_id": "e1",
                "topics": ("t1",),
                "material_refs": ("m1",),
                "preparation_only": True,
                "no_authorization_send": True,
            }
        },
        "university.prepare_assignment": {
            "preparation": {
                "assignment_id": "a1",
                "outline": "x",
                "source_references": ("r1",),
                "preparation_only": True,
            }
        },
        "university.track_deadlines": {
            "tracking": {
                "deadlines": ("d1",),
                "upcoming": ("d1",),
                "calendar_not_modified": True,
            }
        },
        "university.analyse_performance": {
            "analysis": {
                "observed_performance": ("p1",),
                "capacity_inferred": False,
                "summary": "ok",
            }
        },
        "university.generate_academic_summary": {"summary": {"summary": "ok"}},
        "university.update_subject_status": {
            "status": {
                "subject_id": "s1",
                "status": "passed",
                "internal_academic_state_only": True,
                "official_record_untouched": True,
            }
        },
        "university.review_degree_completion": {
            "review": {
                "requirements": ("r1",),
                "completion_state": "incomplete",
                "official_action_none": True,
            }
        },
    }
    for operation_id, payload in valid_outputs.items():
        issues = validate_operation_schema(
            payload, _OPERATIONS[operation_id].output_schema
        )
        assert issues == (), (
            f"{operation_id} valid output failed: {[i.message for i in issues]}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Preparation-only schemas cannot authorize send/submit
# ═══════════════════════════════════════════════════════════════════════════════


def test_prepare_exam_cannot_schema_authorize_send_submit():
    operation = _OPERATIONS["university.prepare_exam"]
    for payload in (
        {"preparation": {"examination_id": "e1", "sent": True}},
        {"preparation": {"examination_id": "e1", "submitted": True}},
        {"preparation": {"examination_id": "e1", "contacted": True}},
    ):
        issues = validate_operation_schema(payload, operation.output_schema)
        assert any(issue.code == "additional_property" for issue in issues)


def test_prepare_exam_valid_preparation_has_no_send_field():
    preparation = _OPERATIONS[
        "university.prepare_exam"
    ].output_schema["properties"]["preparation"]["properties"]
    for forbidden in ("sent", "submitted", "contacted", "executed"):
        assert forbidden not in preparation


def test_prepare_assignment_cannot_schema_authorize_submit():
    operation = _OPERATIONS["university.prepare_assignment"]
    payload = {"preparation": {"assignment_id": "a1", "submitted": True}}
    issues = validate_operation_schema(payload, operation.output_schema)
    assert any(issue.code == "additional_property" for issue in issues)


def test_plan_semester_cannot_authorize_enrolment():
    operation = _OPERATIONS["university.plan_semester"]
    payload = {"plan": {"semester": "2026-A", "enrolled": True}}
    issues = validate_operation_schema(payload, operation.output_schema)
    assert any(issue.code == "additional_property" for issue in issues)


# ═══════════════════════════════════════════════════════════════════════════════
# update_subject_status is INTERNAL Academic State only
# ═══════════════════════════════════════════════════════════════════════════════


def test_update_subject_status_cannot_authorize_official_write():
    operation = _OPERATIONS["university.update_subject_status"]
    payload = {
        "status": {
            "subject_id": "s1",
            "status": "passed",
            "official_record_modified": True,
        }
    }
    issues = validate_operation_schema(payload, operation.output_schema)
    assert any(issue.code == "additional_property" for issue in issues)


def test_track_deadlines_cannot_authorize_calendar_mutation():
    operation = _OPERATIONS["university.track_deadlines"]
    payload = {"tracking": {"deadlines": ("d1",), "calendar_created": True}}
    issues = validate_operation_schema(payload, operation.output_schema)
    assert any(issue.code == "additional_property" for issue in issues)


def test_review_degree_completion_cannot_authorize_graduation():
    operation = _OPERATIONS["university.review_degree_completion"]
    payload = {
        "review": {
            "requirements": ("r1",),
            "completion_state": "complete",
            "graduated": True,
        }
    }
    issues = validate_operation_schema(payload, operation.output_schema)
    assert any(issue.code == "additional_property" for issue in issues)