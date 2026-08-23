"""Tests for Phase 10.26 Languages Domain Workflows."""

from __future__ import annotations

from cmm.domains.languages.catalog import (
    CANONICAL_LANGUAGES_WORKFLOW_IDS,
    CANONICAL_LANGUAGES_WORKFLOW_NAMES,
)
from cmm.domains.languages.operations import (
    assess_sample_result,
    build_languages_operation_definitions,
    create_learning_plan_result,
    generate_conversation_turn_result,
    generate_exercises_result,
    generate_lesson_result,
    generate_progress_review_result,
    generate_roleplay_turn_result,
    plan_review_schedule_result,
    prepare_certification_result,
    review_errors_result,
    review_exercise_result,
    review_speaking_result,
    review_writing_result,
    track_vocabulary_result,
    update_level_evidence_result,
)
from cmm.domains.languages.workflows import (
    build_languages_workflow_definitions,
)
from cmm.domains.workflow_contracts import DomainWorkflowContext
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.workflows.engine import NodeExecution
from cmm.workflows.enums import WorkflowNodeType, WorkflowRunStatus

FORBIDDEN_OUTCOME_FIELDS = frozenset(
    {
        "is_correct",
        "score",
        "estimated_level",
        "pattern_candidate",
        "pronunciation_assessed",
        "needs_verification",
        "stable_progression",
        "is_certified",
        "stable_update_supported",
    }
)


class _Ids:
    def __init__(self) -> None:
        self._index = 0

    def __call__(self) -> str:
        self._index += 1
        return f"languages-workflow-{self._index}"


def _workflow_by_id(workflow_id: str):
    return next(
        workflow
        for workflow in build_languages_workflow_definitions()
        if workflow.workflow_id == workflow_id
    )


def _run_workflow(workflow_id: str, operation_outputs: dict[str, dict]):
    workflow = _workflow_by_id(workflow_id)

    def adapter(node, run):
        if node.operation_id:
            output = operation_outputs[node.operation_id]
            return NodeExecution.complete(output, operation_result=output)
        return NodeExecution.complete({"ok": True})

    operations = build_languages_operation_definitions()
    context = DomainWorkflowContext(
        primary_domain_id="domain:languages",
        known_domain_ids=frozenset({"domain:languages", "domain:general"}),
        authorized_domain_ids=frozenset({"domain:languages"}),
        available_resources=frozenset(workflow.required_resources),
        available_operations=frozenset(operation.operation_id for operation in operations),
    )
    executor = DomainWorkflowExecutor(id_factory=_Ids(), operation_adapter=adapter)
    return executor.execute(workflow, context, inputs={"language": "English"})


def test_build_languages_workflow_definitions_count_and_names() -> None:
    """Verify exact 9 workflows, canonical names, and acyclic nodes."""
    workflows = build_languages_workflow_definitions()
    assert len(workflows) == 9
    assert tuple(w.workflow_id for w in workflows) == CANONICAL_LANGUAGES_WORKFLOW_IDS
    assert tuple(w.name for w in workflows) == CANONICAL_LANGUAGES_WORKFLOW_NAMES

    for w in workflows:
        assert str(w.domain_id) == "domain:languages"
        assert w.version == "1.0.0"
        node_ids = [n.node_id for n in w.nodes]
        assert len(node_ids) == len(set(node_ids)), f"Duplicate node IDs in {w.workflow_id}"

        # First 3 nodes must be load -> profile -> reason
        assert node_ids[:3] == ["load", "profile", "reason"]
        assert w.nodes[1].dependencies == ("load",)
        assert w.nodes[2].dependencies == ("profile",)

        # Complete node must exist and depend on at least one validate node
        assert "complete" in node_ids
        complete_node = next(n for n in w.nodes if n.node_id == "complete")
        assert complete_node.node_type is WorkflowNodeType.COMPLETE


def test_workflow_validate_nodes_consume_real_producer_fields() -> None:
    """Audit every VALIDATE node: all wait_condition keys must be declared in a direct dependency's output schema."""
    workflows = build_languages_workflow_definitions()
    operations = {op.operation_id: op for op in build_languages_operation_definitions()}

    for w in workflows:
        nodes_by_id = {n.node_id: n for n in w.nodes}
        for node in w.nodes:
            if node.node_type is not WorkflowNodeType.VALIDATE:
                continue
            assert node.wait_condition, f"Validate node {node.node_id} in {w.workflow_id} has empty wait_condition"

            # Check each key in wait_condition
            for condition_key in node.wait_condition:
                found_producer = False
                for dep_id in node.dependencies:
                    dep_node = nodes_by_id.get(dep_id)
                    if dep_node and dep_node.operation_id:
                        op = operations.get(dep_node.operation_id)
                        if op and condition_key in op.output_schema.get("properties", {}):
                            found_producer = True
                            break
                assert found_producer, (
                    f"Workflow {w.workflow_id} validate node {node.node_id} condition '{condition_key}' "
                    f"is not declared in any direct dependency operation schema! (deps: {node.dependencies})"
                )


def test_workflow_wait_conditions_never_gate_business_outcomes() -> None:
    """Workflow gates validate invariants rather than fixed learning outcomes."""
    for workflow in build_languages_workflow_definitions():
        for node in workflow.nodes:
            if node.node_type is WorkflowNodeType.VALIDATE:
                assert FORBIDDEN_OUTCOME_FIELDS.isdisjoint(node.wait_condition)


def test_all_nine_workflows_complete_with_real_variable_operation_outputs() -> None:
    """Each canonical workflow accepts a legitimate qualified pedagogical state."""
    outputs_by_workflow = {
        "languages.language_onboarding": {
            "languages.create_learning_plan": create_learning_plan_result(
                language="English", goals=({"id": "fluency"},), tracking_consent=False
            ),
        },
        "languages.proficiency_assessment": {
            "languages.assess_sample": assess_sample_result(
                sample={"text": "A short sample."},
                sample_type="writing",
                target_language="English",
                skill_scope="writing",
            ),
            "languages.update_level_evidence": update_level_evidence_result(
                existing_record={"kind": "CERTIFIED", "level_or_score": "B1"},
                assessment={"observed_performance": "A2", "assessment_id": "assessment-1"},
                target_skill="writing",
            ),
        },
        "languages.adaptive_language_lesson": {
            "languages.generate_lesson": generate_lesson_result(
                language="English", target_skill="grammar", current_level="A2", topic="past tense"
            ),
            "languages.generate_exercises": generate_exercises_result(
                language="English", skill="grammar", difficulty=2, target_topic="past tense"
            ),
            "languages.review_exercise": review_exercise_result(
                exercise_result={"user_answer": "go", "is_correct": False}, language="English"
            ),
        },
        "languages.conversation_roleplay_practice": {
            "languages.generate_conversation_turn": generate_conversation_turn_result(
                conversation={"turns": []}, language="English", topic="travel"
            ),
            "languages.generate_roleplay_turn": generate_roleplay_turn_result(
                conversation={"turns": []}, language="English", scenario="hotel"
            ),
            "languages.review_speaking": review_speaking_result(
                audio_transcript={"transcript": "Hello"},
                target_language="English",
                pronunciation_evidence=({"source_id": "audio-1"},),
            ),
        },
        "languages.writing_review": {
            "languages.review_writing": review_writing_result(
                writing_sample={"text": "Short colour text."},
                language="English",
                preferred_variety="British English",
            ),
        },
        "languages.error_remediation": {
            "languages.review_errors": review_errors_result(
                observed_errors=(
                    {"context_id": "one", "error_type": "inversion", "comparable": True, "comparison_key": "free-writing"},
                    {"context_id": "two", "error_type": "inversion", "comparable": True, "comparison_key": "free-writing"},
                ),
                language="English",
            ),
            "languages.generate_exercises": generate_exercises_result(
                language="English", skill="grammar", difficulty=3, target_topic="inversion"
            ),
            "languages.review_exercise": review_exercise_result(
                exercise_result={"is_correct": False}, language="English", target_topic="inversion"
            ),
        },
        "languages.vocabulary_spaced_review": {
            "languages.track_vocabulary": track_vocabulary_result(
                vocabulary_list={"items": [{"id": "word-1", "due": True}]}, language="English"
            ),
            "languages.plan_review_schedule": plan_review_schedule_result(
                review_items=({"id": "word-1", "due": True},)
            ),
        },
        "languages.certification_preparation": {
            "languages.prepare_certification": prepare_certification_result(
                target_certification="Cambridge C1",
                official_source={"source_type": "official", "date_valid": False},
            ),
        },
        "languages.progress_checkpoint": {
            "languages.generate_progress_review": generate_progress_review_result(
                language="English",
                period="last_30_days",
                previous_evidence=(
                    {"provenance_id": "baseline", "score": 0.6, "skill": "writing", "comparable": True, "comparison_key": "essay"},
                ),
                evidence=(
                    {"provenance_id": "current-1", "score": 0.85, "skill": "writing", "comparable": True, "comparison_key": "essay"},
                    {"provenance_id": "current-2", "score": 0.88, "skill": "writing", "comparable": True, "comparison_key": "essay"},
                ),
                skill="writing",
            ),
        },
    }

    runs = {
        workflow_id: _run_workflow(workflow_id, outputs)
        for workflow_id, outputs in outputs_by_workflow.items()
    }

    assert set(runs) == set(CANONICAL_LANGUAGES_WORKFLOW_IDS)
    assert all(run.status is WorkflowRunStatus.COMPLETED for run in runs.values())


def test_workflow_invariant_violations_fail_closed() -> None:
    """Calendar and certification action boundary violations stop completion."""
    schedule = plan_review_schedule_result(review_items=())
    schedule["calendar_modified"] = True
    vocabulary_run = _run_workflow(
        "languages.vocabulary_spaced_review",
        {
            "languages.track_vocabulary": track_vocabulary_result(vocabulary_list={"items": []}),
            "languages.plan_review_schedule": schedule,
        },
    )

    certification = prepare_certification_result(target_certification="Cambridge C1")
    certification["registration_performed"] = True
    certification_run = _run_workflow(
        "languages.certification_preparation",
        {"languages.prepare_certification": certification},
    )

    assert vocabulary_run.status is WorkflowRunStatus.FAILED
    assert certification_run.status is WorkflowRunStatus.FAILED


def test_additional_legitimate_pedagogical_outcomes_complete() -> None:
    """Opt-in, stable estimates, transcript-only review, and qualified progress remain valid."""
    onboarding = _run_workflow(
        "languages.language_onboarding",
        {
            "languages.create_learning_plan": create_learning_plan_result(
                language="English", goals=({"id": "fluency"},), tracking_consent=True
            )
        },
    )
    assessment = _run_workflow(
        "languages.proficiency_assessment",
        {
            "languages.assess_sample": assess_sample_result(
                sample={"text": "An independently grounded writing sample."},
                sample_type="writing",
                target_language="English",
                skill_scope="writing",
            ),
            "languages.update_level_evidence": update_level_evidence_result(
                existing_record={"kind": "ESTIMATED", "level_or_score": "B1"},
                assessment={
                    "assessment_id": "assessment-2",
                    "observed": "B2",
                    "skill": "writing",
                    "comparable": True,
                    "comparison_key": "essay",
                },
                evidence=(
                    {
                        "assessment_id": "assessment-1",
                        "observed": "B2",
                        "skill": "writing",
                        "comparable": True,
                        "comparison_key": "essay",
                    },
                ),
                target_skill="writing",
            ),
        },
    )
    practice = _run_workflow(
        "languages.conversation_roleplay_practice",
        {
            "languages.generate_conversation_turn": generate_conversation_turn_result(
                conversation={"turns": []}, language="English"
            ),
            "languages.generate_roleplay_turn": generate_roleplay_turn_result(
                conversation={"turns": []}, language="English", scenario="interview"
            ),
            "languages.review_speaking": review_speaking_result(
                audio_transcript={"transcript": "Transcript only"}, target_language="English"
            ),
        },
    )
    writing = _run_workflow(
        "languages.writing_review",
        {
            "languages.review_writing": review_writing_result(
                writing_sample={"text": "This longer colour sample contains enough words to produce a B2 review result safely."},
                language="English",
                preferred_variety="British English",
            )
        },
    )
    remediation = _run_workflow(
        "languages.error_remediation",
        {
            "languages.review_errors": review_errors_result(
                observed_errors=({"context_id": "only-one", "error_type": "inversion"},)
            ),
            "languages.generate_exercises": generate_exercises_result(
                language="English", skill="grammar", difficulty=2, target_topic="inversion"
            ),
            "languages.review_exercise": review_exercise_result(
                exercise_result={"is_correct": True}, language="English"
            ),
        },
    )
    certification = _run_workflow(
        "languages.certification_preparation",
        {
            "languages.prepare_certification": prepare_certification_result(
                target_certification="Cambridge C1",
                official_source={"source_type": "official", "date_valid": True},
            )
        },
    )
    progress_runs = (
        _run_workflow(
            "languages.progress_checkpoint",
            {
                "languages.generate_progress_review": generate_progress_review_result(
                    language="English", period="month", evidence=()
                )
            },
        ),
        _run_workflow(
            "languages.progress_checkpoint",
            {
                "languages.generate_progress_review": generate_progress_review_result(
                    language="English",
                    period="month",
                    previous_evidence=(
                        {"provenance_id": "baseline", "score": 0.6, "skill": "writing", "comparable": True, "comparison_key": "essay"},
                    ),
                    evidence=(
                        {"provenance_id": "current", "score": 0.85, "skill": "writing", "comparable": True, "comparison_key": "essay"},
                    ),
                    skill="writing",
                )
            },
        ),
    )

    assert all(
        run.status is WorkflowRunStatus.COMPLETED
        for run in (
            onboarding,
            assessment,
            practice,
            writing,
            remediation,
            certification,
            *progress_runs,
        )
    )


def test_onboarding_tracking_boundary_gate() -> None:
    """Verify onboarding workflow contains validate_tracking_boundary reading from create_plan."""
    workflows = {w.workflow_id: w for w in build_languages_workflow_definitions()}
    onb = workflows["languages.language_onboarding"]
    val_node = next(n for n in onb.nodes if n.node_id == "validate_tracking_boundary")
    assert "tracking_choice_resolved" in val_node.wait_condition
    assert "persistence_applied" in val_node.wait_condition
    assert val_node.dependencies == ("create_plan",)


def test_certification_preparation_gates() -> None:
    """Verify certification prep workflow contains gates reading from prepare_certification."""
    workflows = {w.workflow_id: w for w in build_languages_workflow_definitions()}
    cert_wf = workflows["languages.certification_preparation"]
    val_node = next(n for n in cert_wf.nodes if n.node_type is WorkflowNodeType.VALIDATE)
    assert "registration_performed" in val_node.wait_condition
    assert "payment_performed" in val_node.wait_condition
    assert "submission_performed" in val_node.wait_condition
    assert val_node.dependencies == ("certification",)
