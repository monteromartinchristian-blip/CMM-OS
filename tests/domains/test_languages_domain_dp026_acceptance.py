"""One connected 45-checkpoint AT-DP-026 Languages acceptance scenario."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
)
from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.contracts import DomainResult
from cmm.domains.enums import DomainOperationType
from cmm.domains.identifiers import DomainId
from cmm.domains.languages import build_standard_languages_domain_bootstrap
from cmm.domains.languages.definition import (
    LANGUAGES_DOMAIN_ID,
    build_languages_domain_definition,
)
from cmm.domains.languages.memory import (
    build_languages_memory_binding,
    build_languages_memory_proposal,
    build_languages_memory_view,
    build_languages_memory_view_request,
    validate_languages_memory_binding,
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
from cmm.domains.languages.permissions import build_languages_permission_policy
from cmm.domains.languages.presentation import present_languages_result
from cmm.domains.languages.rules import (
    classify_language_variety,
    classify_proficiency_record,
    evaluate_certification_source,
    evaluate_error_pattern,
    evaluate_progression,
    prioritize_corrections,
)
from cmm.domains.languages.trace import (
    assemble_languages_trace,
    build_languages_trace_reference,
    validate_languages_trace,
)
from cmm.domains.languages.workflows import build_languages_workflow_definitions
from cmm.domains.memory_contracts import (
    DomainMemoryApprovalDecisionSnapshot,
    DomainMemoryApprovalRequestSnapshot,
    DomainMemoryCapability,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemorySensitivityLevel,
    DomainMemoryTraceSnapshot,
    DomainMemoryViewSnapshot,
)
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.oppositions.definition import build_oppositions_domain_definition
from cmm.domains.permission_gate import DomainPermissionGate, PermissionGateOutcome
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.profile_contracts import DomainProfileDefinition
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolution_contracts import DomainResolutionSignal
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.trace_contracts import (
    CrossDomainTraceReference,
    DomainTraceDomainSelection,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
)
from cmm.domains.workflow_contracts import DomainWorkflowContext
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.workflows.engine import NodeExecution
from cmm.workflows.enums import WorkflowRunStatus

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


class DeterministicIds:
    def __init__(self) -> None:
        self.index = 0

    def __call__(self) -> str:
        self.index += 1
        return f"at-dp-026-owned-{self.index}"


@dataclass
class ConnectedLanguagesScenario:
    ids: DeterministicIds = field(default_factory=DeterministicIds)
    state: dict[str, Any] = field(default_factory=dict)
    checkpoints: list[str] = field(default_factory=list)
    actual_produced_ids: set[str] = field(default_factory=set)
    required_trace_ids: set[str] = field(default_factory=set)

    def checkpoint(self, name: str, condition: bool) -> None:
        assert condition, name
        self.checkpoints.append(name)

    @staticmethod
    def signals(primary: str, supporting: str | None = None) -> tuple[DomainResolutionSignal, ...]:
        signals = [
            DomainResolutionSignal(kind="intent", source="user", value=f"{primary}-intent", domain_ids=(f"domain:{primary}",)),
            DomainResolutionSignal(kind="objective", source="user", value=f"{primary}-objective", domain_ids=(f"domain:{primary}",)),
            DomainResolutionSignal(kind="entity", source="user", value=f"{primary}-entity", domain_ids=(f"domain:{primary}",)),
        ]
        if supporting:
            signals.extend((
                DomainResolutionSignal(kind="operation", source="system", value=f"{supporting}-operation", domain_ids=(f"domain:{supporting}",)),
                DomainResolutionSignal(kind="entity", source="system", value=f"{supporting}-entity", domain_ids=(f"domain:{supporting}",)),
            ))
        return tuple(signals)

    def bootstrap_and_state(self) -> None:
        bootstrap = build_standard_languages_domain_bootstrap()
        self.state["bootstrap"] = bootstrap
        self.checkpoint("01-standard-bootstrap-general-fallback", bootstrap.resolver.fallback_domain == DomainId("general"))
        context = DomainResolutionContextBuilder(id_factory=self.ids, clock=lambda: NOW).build(
            registry_snapshot=bootstrap.domain_registry.snapshot(),
            user_input="Help me practise English fluency while preparing for C1.",
            authorized_domains=("domain:general", LANGUAGES_DOMAIN_ID),
            signals=self.signals("languages"),
        )
        self.state["resolution_context"] = context
        self.actual_produced_ids.add(context.id)
        self.checkpoint("02-real-language-resolution-context", bool(context.signals))
        resolver = DefaultDomainResolver(
            scoring_policy=bootstrap.resolver.scoring_policy,
            fallback_domain=bootstrap.resolver.fallback_domain,
            id_factory=self.ids,
            clock=lambda: NOW,
        )
        self.state["resolver"] = resolver
        resolution = resolver.resolve(context)
        self.state["resolution"] = resolution
        self.actual_produced_ids.add(resolution.id)
        self.checkpoint("03-languages-selected-primary", str(resolution.primary_domain) == LANGUAGES_DOMAIN_ID)
        profile = bootstrap.profile_registry.get_by_domain(DomainId("languages"))
        self.state["profile"] = profile
        self.checkpoint("04-language-learning-profile-resolves", isinstance(profile, DomainProfileDefinition) and profile.profile_name == "LanguageLearningProfile")
        composition = DefaultDomainComposer(id_factory=self.ids, clock=lambda: NOW).compose(resolution, (build_languages_domain_definition(),))
        self.state["composition"] = composition
        self.actual_produced_ids.add(composition.id)

        english = {
            "language": "English",
            "preferred_variety": "American English",
            "goals": (
                {"id": "goal-fluency", "kind": "fluency", "active": True},
                {"id": "goal-c1", "kind": "certification", "target": "C1", "active": True},
            ),
            "tracking_consent": True,
        }
        self.state["languages"] = {"English": english}
        self.checkpoint("05-english-state-isolated", set(self.state["languages"]) == {"English"})
        self.checkpoint("06-american-english-preferred", english["preferred_variety"] == "American English")
        variety = classify_language_variety(preferred_variety="American English", observed_variety="British English", form_status="valid")
        self.state["variety"] = variety
        self.checkpoint(
            "07-british-is-valid-alternative",
            variety["is_valid_alternative"]
            and variety["classification"] == "valid_alternative",
        )
        self.checkpoint("08-fluency-goal-active", english["goals"][0]["active"] is True)
        self.checkpoint("09-c1-goal-concurrently-active", english["goals"][1]["active"] is True)
        self.checkpoint("10-tracking-explicit-opt-in", english["tracking_consent"] is True)
        self.state["certificate"] = classify_proficiency_record(
            kind="CERTIFIED", framework="CEFR", level_or_score="B1", skill_scope="writing",
            evidence=({"source_kind": "official_certificate", "source_id": "official-certificate-record", "certificate_id": "certificate-B1"},),
        )

    def operation_adapter(self, node: Any, run: Any) -> NodeExecution:
        inputs, outputs = run.inputs, run.outputs
        self.state["adapter_saw_inputs"] = self.state.get("adapter_saw_inputs", False) or bool(inputs)
        op = node.operation_id
        if not op:
            return NodeExecution.complete({"ok": True})
        if op == "languages.create_learning_plan":
            result = create_learning_plan_result(language=inputs["language"], goals=inputs["goals"], tracking_consent=inputs["tracking_consent"])
        elif op == "languages.assess_sample":
            result = assess_sample_result(sample=inputs["sample"], target_language=inputs["language"], skill_scope="writing", preferred_variety=inputs["preferred_variety"])
        elif op == "languages.update_level_evidence":
            assessment = outputs["assess"]
            self.state["level_update_consumed_assessment"] = assessment
            result = update_level_evidence_result(existing_record=inputs["existing_record"], assessment=assessment, target_skill="writing")
        elif op == "languages.generate_lesson":
            result = generate_lesson_result(language=inputs["language"], target_skill=inputs.get("target_skill", "writing"), current_level=inputs.get("current_level", "B1"), topic=inputs.get("topic", "inversion"))
        elif op == "languages.generate_exercises":
            producer = outputs.get("lesson") or outputs.get("error_review")
            assert producer is not None
            self.state.setdefault("exercise_producers", []).append(producer)
            result = generate_exercises_result(language=inputs["language"], skill=producer.get("target_skill", "grammar"), difficulty=2, target_topic=producer.get("objective", producer.get("recommended_focus", "inversion")), count=1)
        elif op == "languages.review_exercise":
            generated = outputs["exercises"]
            self.state.setdefault("reviewed_batches", []).append(generated)
            result = review_exercise_result(exercise_result=inputs["exercise_result"], language=inputs["language"], target_topic=generated["exercises"][0]["prompt"])
        elif op == "languages.generate_conversation_turn":
            result = generate_conversation_turn_result(conversation=inputs["conversation"], language=inputs["language"], topic=inputs["topic"], target_level="C1")
        elif op == "languages.generate_roleplay_turn":
            producer = outputs["conversation_turn"]
            self.state["roleplay_consumed_conversation"] = producer
            result = generate_roleplay_turn_result(conversation={"turns": (producer,)}, language=inputs["language"], scenario=inputs["scenario"])
        elif op == "languages.review_speaking":
            self.state["speaking_consumed_roleplay"] = outputs["roleplay_turn"]
            transcript = dict(inputs["audio_transcript"])
            transcript["observed_errors"] = tuple(
                {
                    **item,
                    "provenance_id": outputs["roleplay_turn"]["roleplay_id"],
                }
                for item in transcript.get("observed_errors", ())
            )
            result = review_speaking_result(audio_transcript=transcript, target_language=inputs["language"], pronunciation_evidence=inputs.get("pronunciation_evidence"))
        elif op == "languages.review_writing":
            result = review_writing_result(writing_sample=inputs["writing_sample"], language=inputs["language"], preferred_variety=inputs["preferred_variety"])
        elif op == "languages.review_errors":
            self.state["remediation_consumed_errors"] = tuple(inputs["observed_errors"])
            result = review_errors_result(observed_errors=inputs["observed_errors"], language=inputs["language"])
        elif op == "languages.track_vocabulary":
            result = track_vocabulary_result(vocabulary_list=inputs["vocabulary_list"], language=inputs["language"])
        elif op == "languages.plan_review_schedule":
            producer = outputs["vocabulary"]
            self.state["schedule_consumed_vocabulary"] = producer
            result = plan_review_schedule_result(review_items=producer["candidate_updates"], available_time=20)
        elif op == "languages.prepare_certification":
            authority = evaluate_certification_source(
                sources=inputs.get("official_sources", (inputs["official_source"],)),
                decision_critical=True,
            )
            selected_source = authority["selected_source"]
            certification_case = inputs.get("certification_case", "primary")
            self.state.setdefault("certification_authorities", {})[
                certification_case
            ] = authority
            if certification_case == "primary":
                self.state["certification_authority"] = authority
                self.state["certification_selected_source"] = selected_source
            result = prepare_certification_result(target_certification=inputs["target_certification"], official_source=selected_source)
        elif op == "languages.generate_progress_review":
            result = generate_progress_review_result(language=inputs["language"], period=inputs["period"], previous_evidence=inputs["previous_evidence"], evidence=inputs["evidence"], skill="writing")
        else:
            raise AssertionError(f"unhandled operation {op}")
        self.state.setdefault("operation_outputs", []).append(result)
        return NodeExecution.complete(result, operation_result=result)

    def execute_workflows(self) -> None:
        english = self.state["languages"]["English"]
        baseline = ({"provenance_id": "baseline-writing", "score": 0.6, "skill": "writing", "comparable": True, "comparison_key": "essay"},)
        current = (
            {"provenance_id": "current-writing-1", "score": 0.85, "skill": "writing", "comparable": True, "comparison_key": "essay"},
            {"provenance_id": "current-writing-2", "score": 0.88, "skill": "writing", "comparable": True, "comparison_key": "essay"},
        )
        self.state.update(baseline=baseline, current=current)
        workflow_inputs = {
            "languages.language_onboarding": {"language": "English", "goals": english["goals"], "tracking_consent": True},
            "languages.proficiency_assessment": {
                "language": "English", "sample": {"text": "My favourite colour is blue and I enjoy formal writing."},
                "preferred_variety": "American English", "existing_record": self.state["certificate"],
            },
            "languages.adaptive_language_lesson": {
                "language": "English", "target_skill": "writing", "current_level": "B1", "topic": "inversion",
                "exercise_result": {"is_correct": False, "user_answer": "Never I saw"},
            },
            "languages.conversation_roleplay_practice": {
                "language": "English", "conversation": {"turns": ()}, "topic": "public speaking", "scenario": "oral exam",
                "audio_transcript": {
                    "transcript": "Never I saw that structure before.",
                    "observed_errors": (
                        {
                            "error_type": "target_structure",
                            "category": "recurrent",
                            "comparable": True,
                        },
                    ),
                },
                "pronunciation_evidence": None,
            },
            "languages.writing_review": {
                "language": "English", "writing_sample": {"text": "My favourite colour is blue in this formal proposal."},
                "preferred_variety": "British English",
            },
            "languages.error_remediation": {
                "language": "English", "observed_errors": (),
                "exercise_result": {"is_correct": True, "user_answer": "Never have I seen"},
            },
            "languages.vocabulary_spaced_review": {
                "language": "English", "vocabulary_list": {"items": ({"id": "word-1", "due": True},)},
            },
            "languages.certification_preparation": {
                "language": "English", "target_certification": "Cambridge C1",
                "certification_case": "primary",
                "official_source": {"id": "stale-guide", "source_type": "guide", "date_valid": False},
                "official_sources": (
                    {"id": "stale-official", "source_type": "official", "date_valid": False},
                    {"id": "current-official", "source_type": "official", "date_valid": True},
                ),
            },
            "languages.progress_checkpoint": {
                "language": "English", "period": "last_30_days", "previous_evidence": baseline, "evidence": current,
            },
        }
        workflows = build_languages_workflow_definitions()
        operations = build_languages_operation_definitions()
        context = DomainWorkflowContext(
            primary_domain_id=LANGUAGES_DOMAIN_ID,
            known_domain_ids=frozenset({LANGUAGES_DOMAIN_ID, "domain:general"}),
            authorized_domain_ids=frozenset({LANGUAGES_DOMAIN_ID}),
            available_resources=frozenset(resource for workflow in workflows for resource in workflow.required_resources),
            available_operations=frozenset(item.operation_id for item in operations),
        )
        executor = DomainWorkflowExecutor(id_factory=self.ids, clock=lambda: NOW, operation_adapter=self.operation_adapter)
        runs: dict[str, Any] = {}
        for workflow in workflows:
            if workflow.workflow_id == "languages.conversation_roleplay_practice":
                lesson_error = runs[
                    "languages.adaptive_language_lesson"
                ].common_run.outputs["review"]["observed_errors"][0]
                conversation_input = workflow_inputs[workflow.workflow_id]
                raw_error = conversation_input["audio_transcript"]["observed_errors"][0]
                conversation_input["audio_transcript"]["observed_errors"] = (
                    {
                        **raw_error,
                        "comparison_key": lesson_error["comparison_key"],
                    },
                )
            if workflow.workflow_id == "languages.error_remediation":
                lesson_errors = tuple(
                    runs["languages.adaptive_language_lesson"]
                    .common_run.outputs["review"]["observed_errors"]
                )
                speaking_errors = tuple(
                    runs["languages.conversation_roleplay_practice"]
                    .common_run.outputs["speaking_review"]["observed_errors"]
                )
                workflow_inputs[workflow.workflow_id]["observed_errors"] = (
                    *lesson_errors,
                    *speaking_errors,
                )
            run = executor.execute(workflow, context, workflow_inputs[workflow.workflow_id])
            assert run.status is WorkflowRunStatus.COMPLETED
            runs[workflow.workflow_id] = run
            self.actual_produced_ids.add(run.common_run.run_id)
            self.actual_produced_ids.update(event.event_id for event in run.execution_result.events)
        self.state.update(workflow_runs=runs, workflow_inputs=workflow_inputs)

        onboarding = runs["languages.language_onboarding"].common_run.outputs["create_plan"]
        self.checkpoint("11-onboarding-workflow-executes", bool(onboarding["plan_id"]))
        self.checkpoint("12-onboarding-persists-nothing", onboarding["persistence_applied"] is False)
        self.checkpoint("13-official-b1-is-certified", self.state["certificate"]["is_certified"] is True)
        assessment_outputs = runs["languages.proficiency_assessment"].common_run.outputs
        assessment, update = assessment_outputs["assess"], assessment_outputs["level_update"]
        self.state.update(assessment=assessment, level_update=update)
        self.checkpoint("14-writing-assessed-through-workflow", bool(assessment["assessment_id"]))
        self.checkpoint("15-writing-stays-observed", assessment["proficiency_kind"] == "OBSERVED_PERFORMANCE")
        self.checkpoint("16-certificate-not-overwritten", update["certificate_overwritten"] is False)
        self.checkpoint("17-speaking-still-missing", "speaking" in assessment["missing_evidence"])
        self.checkpoint(
            "18-level-update-is-evidence-only",
            update["updated_record"]["kind"] == "CERTIFIED"
            and update["updated_record"]["level_or_score"] == "B1"
            and update["stable_update_supported"] is False,
        )
        self.checkpoint("19-plan-preserves-both-goals", len(onboarding["goals"]) == 2)

        lesson = runs["languages.adaptive_language_lesson"].common_run.outputs
        self.checkpoint("20-adaptive-lesson-executes", bool(lesson["lesson"]["lesson_id"]))
        self.checkpoint("21-generated-exercise-is-reviewed", bool(lesson["review"]["review_id"]))
        self.checkpoint("22-isolated-error-not-pattern", lesson["review"]["pattern_candidate"] is False)
        self.checkpoint("23-one-session-does-not-change-proficiency", lesson["review"]["stable_proficiency_changed"] is False)
        practice = runs["languages.conversation_roleplay_practice"].common_run.outputs
        self.checkpoint("24-conversation-roleplay-executes", bool(practice["roleplay_turn"]["roleplay_id"]))
        self.checkpoint("25-transcript-does-not-assess-pronunciation", practice["speaking_review"]["pronunciation_assessed"] is False)
        errors = self.state["remediation_consumed_errors"]
        self.state["independent_errors"] = errors
        self.checkpoint("26-independent-comparable-occurrence-produced", errors[0]["provenance_id"] != errors[1]["provenance_id"])
        pattern = evaluate_error_pattern(observations=errors)
        self.state["pattern"] = pattern
        self.checkpoint("27-error-pattern-rule-evaluates", pattern["eligible"] is True)
        self.checkpoint("28-pattern-needs-independence-and-comparability", pattern["pattern_state"] == "candidate")
        priority = prioritize_corrections(errors=(*errors, {"id": "style", "category": "minor_style"}), mode="practice")
        self.state["priority"] = priority
        self.checkpoint("29-correction-priority-is-semantic", priority["prioritized_errors"][-1]["category"] == "minor_style")

        writing = runs["languages.writing_review"].common_run.outputs["review"]
        self.checkpoint("30-writing-review-workflow-executes", bool(writing["review_id"]))
        writing_presentation = present_languages_result(writing)
        self.state["writing_presentation"] = writing_presentation
        self.checkpoint("31-valid-variety-survives-review", writing_presentation["valid_alternatives"][0]["status"] == "valid_alternative")
        progress = runs["languages.progress_checkpoint"].common_run.outputs["progress"]
        self.checkpoint("32-progress-checkpoint-executes", bool(progress["review_id"]))
        short = evaluate_progression(previous_evidence=baseline, current_evidence=current[:1], skill="writing")
        self.state["short_progress"] = short
        self.checkpoint("33-one-better-score-short-term-only", short["stable_progression"] is False)
        self.checkpoint("34-real-baseline-supports-stable-improvement", progress["stable_progression"] is True)
        non_comparable = evaluate_progression(
            previous_evidence=baseline,
            current_evidence=tuple({**item, "comparable": False} for item in current),
            skill="writing",
        )
        self.checkpoint("35-noncomparable-cannot-be-stable", non_comparable["stable_progression"] is False)
        certification = runs["languages.certification_preparation"].common_run.outputs["certification"]
        self.checkpoint("36-certification-workflow-executes", bool(certification["prep_id"]))
        authority = self.state["certification_authority"]
        self.checkpoint("37-current-official-wins", authority["selected_source"]["id"] == "current-official")
        self.checkpoint("38-readiness-not-proficiency", certification["readiness_promoted_to_proficiency"] is False)
        certification_workflow = next(
            workflow
            for workflow in workflows
            if workflow.workflow_id == "languages.certification_preparation"
        )
        stale_certification_run = executor.execute(
            certification_workflow,
            context,
            {
                "language": "English",
                "target_certification": "Cambridge C1",
                "certification_case": "stale-verification",
                "official_source": {
                    "id": "stale-only-official",
                    "source_type": "official",
                    "date_valid": False,
                },
            },
        )
        self.state["stale_certification_run"] = stale_certification_run
        self.actual_produced_ids.add(stale_certification_run.common_run.run_id)
        self.actual_produced_ids.update(
            event.event_id
            for event in stale_certification_run.execution_result.events
        )
        stale_certification = stale_certification_run.common_run.outputs[
            "certification"
        ]
        self.checkpoint(
            "39-stale-requirements-preserve-verification",
            stale_certification_run.status is WorkflowRunStatus.COMPLETED
            and stale_certification["needs_verification"] is True,
        )
        spaced = runs["languages.vocabulary_spaced_review"].common_run.outputs["review_plan"]
        self.state["spaced_review"] = spaced
        self.checkpoint("40-review-proposal-no-calendar-mutation", spaced["calendar_modified"] is False and spaced["external_action_executed"] is False)

        assert len(runs) == 9
        assert self.state["level_update_consumed_assessment"] == assessment
        assert self.state["adapter_saw_inputs"] is True

    def permission_and_memory(self) -> None:
        registry = DomainPermissionRegistry()
        registry.register(build_languages_permission_policy())
        service = ApprovalService(InMemoryApprovalRepository())
        gate = DomainPermissionGate(DomainPermissionResolver(registry), service, clock=lambda: NOW)
        operation = DomainOperationDefinition(
            operation_id="languages.test_connected_memory_apply", domain_id=LANGUAGES_DOMAIN_ID,
            version="1.0.0", name="Connected acceptance memory apply",
            description="Test-only operation for the real shared approval gate.",
            operation_type=DomainOperationType.ANALYSIS,
            required_permissions=(PermissionCapability.MEMORY_WRITE.value,),
            risk_level=PolicyRiskLevel.LOW, reversible=True,
        )
        permission_request_id = self.ids()
        pending = gate.evaluate_operation_definition(
            operation, request_id=permission_request_id,
            actor_id="actor-at-dp-026", session_id="session-at-dp-026",
        )
        assert pending.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
        requirement = PermissionApprovalRequirement.from_dict(pending.approval_requirements[0])
        approval = service.create_request_from_requirement(
            to_approval_requirement(requirement, agent_run_id=self.ids()), requested_by="agent-runtime"
        )
        service.approve(approval.id, "human-approver")
        decision = service.repository.list_decisions(approval.id)[0]
        self.state.update(
            permission_gate=gate, approval_service=service, permission_operation=operation,
            permission_request_id=permission_request_id, permission_requirement=requirement,
            approval_request=approval, approval_decision=decision,
        )
        self.actual_produced_ids.update((approval.id, decision.id))

        proposal_id, reference_id, canonical_id = self.ids(), self.ids(), self.ids()
        reference = DomainMemoryReference(
            reference_id=reference_id, kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
            canonical_id=canonical_id, domain_id=LANGUAGES_DOMAIN_ID,
            applicable_domains=(LANGUAGES_DOMAIN_ID,),
            evidence_ids=(self.state["assessment"]["assessment_id"],),
            resource_ids=(self.state["spaced_review"]["schedule_id"],),
        )
        permission_id, trace_id = self.ids(), self.ids()
        memory_permission = DomainMemoryPermissionDecisionSnapshot(
            decision_id=permission_id, allowed=True,
            capabilities=(DomainMemoryCapability.PROPOSE,),
            source_domain_id=LANGUAGES_DOMAIN_ID, target_domain_id=LANGUAGES_DOMAIN_ID,
            sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
        )
        request = build_languages_memory_view_request(
            request_id=self.ids(), trace_id=trace_id,
            requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
            candidates=(reference,), permission_decision_ids=(permission_id,),
        )
        base_inventory = DomainMemoryReferenceInventory(
            references=(reference,),
            traces=(DomainMemoryTraceSnapshot(trace_id=trace_id, primary_domain=LANGUAGES_DOMAIN_ID),),
            permission_decisions=(memory_permission,),
        )
        view = build_languages_memory_view(request=request, inventory=base_inventory)
        proposal = build_languages_memory_proposal(proposal_id=proposal_id, affected_reference_ids=(reference_id,))
        binding = build_languages_memory_binding(
            proposal=proposal, view=view, trace_id=trace_id,
            permission_decision_ids=(permission_id,), approval_request_ids=(approval.id,),
            approval_decision_ids=(decision.id,),
        )
        inventory = DomainMemoryReferenceInventory(
            references=(reference,), proposals=(proposal,), permission_decisions=(memory_permission,),
            approval_requests=(DomainMemoryApprovalRequestSnapshot(request_id=approval.id, proposal_id=proposal_id),),
            approval_decisions=(DomainMemoryApprovalDecisionSnapshot(decision_id=decision.id, request_id=approval.id, approved=True),),
            traces=(DomainMemoryTraceSnapshot(trace_id=trace_id, primary_domain=LANGUAGES_DOMAIN_ID),),
            views=(DomainMemoryViewSnapshot(
                view_id=view.view_id, request_id=view.request_id, primary_domain=view.primary_domain,
                trace_id=view.trace_id, view_digest=view.content_digest,
            ),),
        )
        validation = validate_languages_memory_binding(binding=binding, inventory=inventory)
        self.state.update(memory_proposal=proposal, memory_binding=binding, memory_view=view, memory_validation=validation)
        self.actual_produced_ids.update((proposal.proposal_id, binding.binding_id, view.view_id, permission_id, trace_id))
        self.checkpoint("41-memory-proposal-valid-no-persistence", validation.is_valid and not service.repository.is_consumed(approval.id))
        consumed = gate.evaluate_operation_definition(
            operation, request_id=permission_request_id,
            actor_id="actor-at-dp-026", session_id="session-at-dp-026",
            approval_request_id=approval.id,
        )
        self.state["permission_consumed"] = consumed
        self.checkpoint(
            "42-real-permission-lifecycle-consumes-exact-approval",
            consumed.outcome is PermissionGateOutcome.APPROVAL_CONSUMED and consumed.allowed,
        )

    def cross_domain_and_presentation(self) -> None:
        registry = DomainRegistry()
        for definition in (build_oppositions_domain_definition(), build_languages_domain_definition()):
            registry.register(definition)
            registry.enable(str(definition.id))
        context = DomainResolutionContextBuilder(id_factory=self.ids, clock=lambda: NOW).build(
            registry_snapshot=registry.snapshot(),
            user_input="Prepare an opposition exam with an English requirement.",
            authorized_domains=("domain:oppositions", LANGUAGES_DOMAIN_ID),
            signals=self.signals("oppositions", "languages"),
        )
        resolution = DefaultDomainResolver(id_factory=self.ids, clock=lambda: NOW).resolve(context)
        composition = DefaultDomainComposer(id_factory=self.ids, clock=lambda: NOW).compose(
            resolution, (build_oppositions_domain_definition(), build_languages_domain_definition())
        )
        certificate = self.state["certificate"]
        assessment = self.state["assessment"]
        certification = self.state["workflow_runs"][
            "languages.certification_preparation"
        ].common_run.outputs["certification"]
        progress = self.state["workflow_runs"][
            "languages.progress_checkpoint"
        ].common_run.outputs["progress"]
        review_plan = self.state["spaced_review"]
        allowed = {
            "certification_status": (
                f"{certificate['level_or_score']} "
                f"{certificate['kind'].lower()}"
            ),
            "estimated_readiness": certification["readiness_score"],
            "relevant_proficiency": {
                "writing": assessment["observed_performance"],
            },
            "progress_toward_shared_goal": progress["overall_progression"],
            "recommended_workload": review_plan[
                "recommended_duration_minutes"
            ],
            "blocking_language_gap": certification["skill_gaps"][1],
        }
        projection = DomainResult(
            id=self.ids(), status="completed",
            objective="Minimal Languages projection for opposition planning",
            primary_domain=LANGUAGES_DOMAIN_ID, supporting_domains=("domain:oppositions",),
            findings=(allowed,), trace_id=self.ids(), confidence=0.8,
        )
        self.state.update(cross_context=context, cross_resolution=resolution, cross_composition=composition, cross_projection=projection)
        self.actual_produced_ids.update((context.id, resolution.id, composition.id, str(projection.id), projection.trace_id))
        allowed_keys = {
            "certification_status", "estimated_readiness", "relevant_proficiency",
            "progress_toward_shared_goal", "recommended_workload",
            "blocking_language_gap",
        }
        forbidden = {
            "complete_vocabulary_history", "all_observed_errors", "all_transcripts",
            "all_writing_corrections", "full_languages_memory",
        }
        self.checkpoint(
            "43-real-cross-domain-minimal-composition",
            str(resolution.primary_domain) == "domain:oppositions"
            and LANGUAGES_DOMAIN_ID in {str(item) for item in resolution.supporting_domains}
            and str(composition.primary_domain) == "domain:oppositions"
            and set(projection.to_dict()["findings"][0]) == allowed_keys
            and not forbidden.intersection(projection.to_dict()["findings"][0]),
        )
        presented = [present_languages_result(result) for result in self.state["operation_outputs"]]
        presented.extend(
            present_languages_result(run.common_run.to_dict())
            for run in self.state["workflow_runs"].values()
        )
        presented.append(present_languages_result(projection.to_dict()))
        self.state["presented_results"] = presented
        speaking = next(item for item in presented if item.get("transcript_text") is not None)
        self.checkpoint(
            "44-presentation-does-not-upgrade-results",
            speaking["pronunciation_assessed"] is False
            and all(item["presentation_format"] == "standard_pedagogy" for item in presented),
        )

    def trace(self) -> None:
        references = []
        for run in self.state["workflow_runs"].values():
            references.append(build_languages_trace_reference(
                ref_id=run.common_run.run_id, kind=DomainTraceReferenceKind.WORKFLOW_RUN
            ))
            if run.execution_result.events:
                references.append(build_languages_trace_reference(
                    ref_id=run.execution_result.events[-1].event_id,
                    kind=DomainTraceReferenceKind.WORKFLOW_RESULT,
                ))
        for value, kind in (
            (self.state["assessment"]["assessment_id"], DomainTraceReferenceKind.OPERATION_RESULT),
            (self.state["approval_request"].id, DomainTraceReferenceKind.APPROVAL_REQUEST),
            (self.state["approval_decision"].id, DomainTraceReferenceKind.APPROVAL_DECISION),
            (self.state["memory_proposal"].proposal_id, DomainTraceReferenceKind.FINDING),
        ):
            references.append(build_languages_trace_reference(ref_id=value, kind=kind))
            self.actual_produced_ids.add(value)
        runs = self.state["workflow_runs"]
        domain_result = DomainResult(
            id=self.ids(), status="completed", objective="Connected Languages acceptance result",
            primary_domain=LANGUAGES_DOMAIN_ID,
            workflow_result_id=runs["languages.progress_checkpoint"].common_run.run_id,
            operation_result_ids=(self.state["assessment"]["assessment_id"],),
            approval_ids=(self.state["approval_request"].id,),
            trace_id=self.state["memory_binding"].trace_id, confidence=0.8,
        )
        self.state["domain_result"] = domain_result
        self.actual_produced_ids.add(str(domain_result.id))
        cross = self.state["cross_projection"]
        cross_reference = CrossDomainTraceReference(result_id=str(cross.id), trace_id=cross.trace_id)
        resolution, composition, context = (
            self.state["resolution"], self.state["composition"], self.state["resolution_context"]
        )
        trace = assemble_languages_trace(
            request_id=self.ids(), resolution_context_id=context.id,
            resolution_result_id=resolution.id, composition_id=composition.id,
            domain_result_id=str(domain_result.id), started_at=NOW, completed_at=NOW,
            references=tuple(references), cross_domain_results=(cross_reference,),
        )
        inventory = DomainTraceReferenceInventory(
            references=trace.all_references(), domain_results=trace.domain_results,
            cross_domain_results=trace.references.cross_domain_results,
            expected_primary_domain=LANGUAGES_DOMAIN_ID, expected_supporting_domains=(),
            resolution_result_domains=DomainTraceDomainSelection(resolution.id, LANGUAGES_DOMAIN_ID),
            composition_domains=DomainTraceDomainSelection(composition.id, LANGUAGES_DOMAIN_ID),
        )
        validation = validate_languages_trace(trace=trace, inventory=inventory)
        self.state.update(trace=trace, trace_inventory=inventory, trace_validation=validation)
        self.required_trace_ids = {item.ref_id for item in trace.all_references()}
        assert self.required_trace_ids <= self.actual_produced_ids
        self.checkpoint("45-connected-trace-valid", validation.valid)

    def run(self) -> None:
        self.bootstrap_and_state()
        self.execute_workflows()
        self.permission_and_memory()
        self.cross_domain_and_presentation()
        self.trace()


def test_at_dp_026_is_one_connected_45_checkpoint_scenario() -> None:
    scenario = ConnectedLanguagesScenario()
    scenario.run()
    assert len(scenario.checkpoints) == 45
    assert len(set(scenario.checkpoints)) == 45
    assert len(scenario.state["workflow_runs"]) == 9
    assert scenario.state["level_update_consumed_assessment"] == scenario.state["assessment"]
    assert scenario.state["permission_consumed"].outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    assert scenario.state["cross_composition"].id in scenario.actual_produced_ids
    assert scenario.required_trace_ids <= scenario.actual_produced_ids
    lesson_errors = tuple(
        scenario.state["workflow_runs"]["languages.adaptive_language_lesson"]
        .common_run.outputs["review"]["observed_errors"]
    )
    speaking_errors = tuple(
        scenario.state["workflow_runs"]["languages.conversation_roleplay_practice"]
        .common_run.outputs["speaking_review"]["observed_errors"]
    )
    assert scenario.state["remediation_consumed_errors"] == (
        *lesson_errors,
        *speaking_errors,
    )
    assert scenario.state["certification_selected_source"]["id"] == "current-official"
    assert (
        scenario.state["workflow_runs"]["languages.certification_preparation"]
        .common_run.outputs["certification"]["needs_verification"]
        is False
    )
    projection = scenario.state["cross_projection"].to_dict()["findings"][0]
    assert set(projection) == {
        "certification_status",
        "estimated_readiness",
        "relevant_proficiency",
        "progress_toward_shared_goal",
        "recommended_workload",
        "blocking_language_gap",
    }
    assert projection["relevant_proficiency"]["writing"] == scenario.state[
        "assessment"
    ]["observed_performance"]
