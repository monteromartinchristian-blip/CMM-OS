"""Phase 10.26 — DP-026 Acceptance Matrix Tests (AT-DP-026 Evidence).

Implements the 25-step canonical acceptance scenario for Languages Domain.
Establishes implementation-side candidate evidence only; independent audit
closure is a separate lifecycle event and is never claimed here.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.languages.definition import LANGUAGES_DOMAIN_ID
from cmm.domains.languages.operations import (
    assess_sample_result,
    create_learning_plan_result,
    generate_exercises_result,
    generate_lesson_result,
    generate_progress_review_result,
    generate_roleplay_turn_result,
    plan_review_schedule_result,
    prepare_certification_result,
    review_exercise_result,
    review_speaking_result,
    review_writing_result,
)
from cmm.domains.languages.rules import (
    classify_language_variety,
    classify_proficiency_record,
    evaluate_certification_source,
    evaluate_cultural_context,
    evaluate_error_pattern,
    evaluate_progression,
    prioritize_corrections,
    separate_skill_evidence,
)
from cmm.domains.languages.trace import (
    assemble_languages_trace,
    build_languages_trace_reference,
    validate_languages_trace,
)
from cmm.domains.trace_contracts import (
    DomainTraceDomainSelection,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
)


class _ScenarioATDP026:
    """Stateful runner for the 25-step canonical Languages scenario."""

    def __init__(self) -> None:
        self.steps: list[str] = []

    def step_1_to_3_diagnostic_assessment(self) -> dict:
        sample = {"text": "I am preparing for an exam and working on my presentation skills."}
        res = assess_sample_result(
            sample=sample,
            sample_type="writing",
            target_language="English",
            skill_scope="writing",
            preferred_variety="British English",
        )
        assert res["proficiency_kind"] == "OBSERVED_PERFORMANCE"
        assert res["observed_performance"] in ("B2", "A2")
        self.steps.append("1-3-diagnostic")
        return res

    def step_4_epistemic_separation(self, assessment: dict) -> None:
        cert_rec = classify_proficiency_record(
            kind="CERTIFIED",
            framework="CEFR",
            level_or_score="B1",
            skill_scope="writing",
            evidence=(
                {
                    "source_kind": "official_certificate",
                    "source_id": "official-record-1",
                    "certificate_id": "C123",
                },
            ),
        )
        est_rec = classify_proficiency_record(
            kind="ESTIMATED",
            framework="CEFR",
            level_or_score="B2",
            skill_scope="writing",
            evidence=({"id": "est-1", "score": 0.8},),
        )
        assert cert_rec["is_certified"] is True
        assert est_rec["is_certified"] is False
        assert cert_rec["level_or_score"] != assessment["observed_performance"]
        self.steps.append("4-epistemic-separation")

    def step_5_variety_preference(self) -> None:
        var_res = classify_language_variety(
            preferred_variety="British English",
            observed_variety="American English",
            form_status="valid",
        )
        assert var_res["is_valid_alternative"] is True
        assert var_res["variety_mismatch"] is True
        self.steps.append("5-variety-preference")

    def step_6_skill_separation(self) -> None:
        sep = separate_skill_evidence(
            evidence=(
                {"skill": "writing", "score": 0.9},
                {"skill": "speaking", "score": 0.5},
            )
        )
        assert "writing" in sep["by_skill"]
        assert "speaking" in sep["by_skill"]
        assert sep["by_skill"]["writing"]["status"] == "evidenced"
        assert sep["by_skill"]["speaking"]["status"] == "evidenced"
        self.steps.append("6-skill-separation")

    def step_7_to_9_tracking_and_learning_plan(self) -> dict:
        plan = create_learning_plan_result(
            language="English",
            goals=[{"id": "g1", "target": "C1 IELTS"}],
            tracking_consent=True,
        )
        assert plan["tracking_choice"] == "opt_in"
        assert plan["tracking_choice_resolved"] is True
        assert plan["memory_proposal_required"] is True
        assert plan["persistence_applied"] is False
        assert len(plan["phases"]) >= 2
        self.steps.append("7-9-plan")
        return plan

    def step_10_and_11_spaced_review_and_load(self) -> dict:
        sched = plan_review_schedule_result(
            review_items=[
                {"id": "v1", "term": "ubiquitous", "mastery": 0.3, "due": True},
                {"id": "v2", "term": "alleviate", "mastery": 0.8, "due": False},
            ],
            available_time=15,
            energy="low",
        )
        assert sched["recommended_duration_minutes"] <= 15
        assert sched["calendar_modified"] is False
        assert sched["external_action_executed"] is False
        self.steps.append("10-11-load")
        return sched

    def step_12_and_13_lesson_and_exercises(self) -> tuple[dict, dict]:
        lesson = generate_lesson_result(
            language="English",
            target_skill="writing",
            current_level="B2",
            topic="Formal proposals",
        )
        exercises = generate_exercises_result(
            language="English",
            skill="writing",
            difficulty=3,
            target_topic="Inversion for emphasis",
            count=3,
        )
        assert len(exercises["exercises"]) == 3
        assert exercises["difficulty"] == 3
        self.steps.append("12-13-lesson-exercises")
        return lesson, exercises

    def step_14_to_16_error_review_and_priority(self) -> dict:
        # Isolated error is not a pattern
        ex_rev = review_exercise_result(
            exercise_result={"user_answer": "No sooner I had", "is_correct": False},
            language="English",
            target_topic="Inversion",
        )
        assert ex_rev["pattern_candidate"] is False

        # Independent occurrences evaluate to pattern
        obs = (
            {"id": "o1", "context_id": "ctx1", "sentence": "s1", "error_type": "inversion", "comparable": True, "comparison_key": "free-writing"},
            {"id": "o2", "context_id": "ctx2", "sentence": "s2", "error_type": "inversion", "comparable": True, "comparison_key": "free-writing"},
        )
        pat = evaluate_error_pattern(observations=obs)
        assert pat["pattern_state"] == "candidate"

        prio = prioritize_corrections(
            errors=[
                {"id": "e1", "category": "comprehension_blocking"},
                {"id": "e2", "category": "minor_style"},
            ],
            mode="practice",
        )
        assert prio["prioritized_errors"][0]["id"] == "e1"
        self.steps.append("14-16-errors")
        return prio

    def step_17_and_18_roleplay_and_speaking(self) -> tuple[dict, dict]:
        rp = generate_roleplay_turn_result(
            conversation={"turns": []},
            language="English",
            scenario="Workplace presentation Q&A",
        )
        sp = review_speaking_result(
            audio_transcript={"transcript": "I would like to present our quarterly results."},
            target_language="English",
            pronunciation_evidence=None,
        )
        assert sp["pronunciation_assessed"] is False
        self.steps.append("17-18-roleplay-speaking")
        return rp, sp

    def step_19_writing_review(self) -> dict:
        wr = review_writing_result(
            writing_sample={"text": "The colour of the proposal reflects our branding."},
            language="English",
            preferred_variety="British English",
        )
        assert len(wr["valid_alternatives"]) == 1
        assert wr["score"] >= 0.8
        self.steps.append("19-writing-review")
        return wr

    def step_20_progression_evaluation(self) -> dict:
        prog = evaluate_progression(
            previous_evidence=({"provenance_id": "p1", "score": 0.6, "comparable": True, "comparison_key": "writing-argumentative"},),
            current_evidence=(
                {"provenance_id": "c1", "score": 0.85, "comparable": True, "comparison_key": "writing-argumentative"},
                {"provenance_id": "c2", "score": 0.88, "comparable": True, "comparison_key": "writing-argumentative"},
            ),
        )
        assert prog["progression_outcome"] == "stable_improvement"
        assert prog["stable_progression"] is True
        self.steps.append("20-progression")
        return prog

    def step_21_and_22_certification_preparation(self) -> tuple[dict, dict]:
        cert_prep = prepare_certification_result(
            target_certification="IELTS Academic",
            official_source={"source_type": "official", "authority": 3, "date_valid": True},
        )
        assert cert_prep["registration_performed"] is False
        assert cert_prep["payment_performed"] is False
        assert cert_prep["needs_verification"] is False

        # Conflicting sources require verification
        conf_eval = evaluate_certification_source(
            sources=(
                {"source_type": "official", "authority": 3, "task_count": 3},
                {"source_type": "official", "authority": 3, "task_count": 4},
            ),
            decision_critical=True,
        )
        assert conf_eval["unresolved_conflict"] is True
        assert conf_eval["needs_verification"] is True
        self.steps.append("21-22-certification")
        return cert_prep, conf_eval

    def step_23_to_25_cultural_progress_and_trace(self) -> None:
        cult = evaluate_cultural_context(claim="All British people always drink tea at 4pm.", universal_claim=True)
        assert cult["universal_claim_rejected"] is True

        prog_rev = generate_progress_review_result(language="English", period="last_30_days")
        assert prog_rev["language"] == "English"

        # Trace assembly & validation
        now = datetime.now(timezone.utc)
        primary_ref = build_languages_trace_reference(
            ref_id="lang-res-1",
            kind=DomainTraceReferenceKind.RESOURCE_RESOLUTION,
        )
        trace = assemble_languages_trace(
            request_id="req-at-1",
            resolution_context_id="ctx-at-1",
            resolution_result_id="res-at-1",
            composition_id="comp-at-1",
            domain_result_id="res-out-at-1",
            started_at=now,
            completed_at=now,
            references=(primary_ref,),
        )
        inventory = DomainTraceReferenceInventory(
            references=trace.all_references(),
            domain_results=trace.domain_results,
            cross_domain_results=trace.references.cross_domain_results,
            expected_primary_domain=LANGUAGES_DOMAIN_ID,
            expected_supporting_domains=(),
            resolution_result_domains=DomainTraceDomainSelection("res-at-1", LANGUAGES_DOMAIN_ID),
            composition_domains=DomainTraceDomainSelection("comp-at-1", LANGUAGES_DOMAIN_ID),
        )
        val = validate_languages_trace(trace=trace, inventory=inventory)
        assert val.valid is True
        self.steps.append("23-25-trace")


def test_at_dp_026_full_25_step_canonical_scenario() -> None:
    """Execute complete 25-step AT-DP-026 scenario and assert all steps pass."""
    runner = _ScenarioATDP026()
    ass = runner.step_1_to_3_diagnostic_assessment()
    runner.step_4_epistemic_separation(ass)
    runner.step_5_variety_preference()
    runner.step_6_skill_separation()
    runner.step_7_to_9_tracking_and_learning_plan()
    runner.step_10_and_11_spaced_review_and_load()
    runner.step_12_and_13_lesson_and_exercises()
    runner.step_14_to_16_error_review_and_priority()
    runner.step_17_and_18_roleplay_and_speaking()
    runner.step_19_writing_review()
    runner.step_20_progression_evaluation()
    runner.step_21_and_22_certification_preparation()
    runner.step_23_to_25_cultural_progress_and_trace()

    assert len(runner.steps) == 13
    assert runner.steps[-1] == "23-25-trace"
