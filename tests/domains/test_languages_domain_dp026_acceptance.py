"""One connected 45-checkpoint AT-DP-026 Languages acceptance scenario."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

import pytest

import cmm.domains.languages.operations as languages_operations
from cmm.agent_runtime.approval_contracts import ApprovalDecision, ApprovalRequest
from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
)
from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.contracts import DomainResult
from cmm.domains.enums import (
    DomainOperationType,
    DomainRuleSelectionStatus,
    DomainRuleSource,
)
from cmm.domains.general.permissions import build_general_permission_policy
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
from cmm.domains.languages.profile import LANGUAGES_PEDAGOGICAL_MODES
from cmm.domains.languages.rules import (
    build_languages_rules,
    classify_language_variety,
    classify_proficiency_record,
    evaluate_certification_source,
    evaluate_error_pattern,
    evaluate_progression,
    prioritize_corrections,
)
from cmm.domains.languages.trace import (
    assemble_languages_trace,
    build_languages_trace_contribution,
    build_languages_trace_reference,
    validate_languages_trace,
)
from cmm.domains.languages.workflows import build_languages_workflow_definitions
from cmm.domains.memory_contracts import (
    DomainMemoryApprovalDecisionSnapshot,
    DomainMemoryApprovalRequestSnapshot,
    DomainMemoryCapability,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryProposalBinding,
    DomainMemoryProposalSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemorySensitivityLevel,
    DomainMemoryTraceSnapshot,
    DomainMemoryViewSnapshot,
)
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.oppositions.definition import build_oppositions_domain_definition
from cmm.domains.permission_gate import (
    DomainPermissionGate,
    PermissionGateOutcome,
    PermissionGateResult,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.profile_contracts import DomainProfileDefinition
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionSignal,
)
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resolver_contracts import DomainResolutionResult
from cmm.domains.rule_contracts import (
    DomainRuleExecutionPlan,
    DomainRuleExecutionResult,
    DomainRuleSourceRecord,
    SelectedReasoningRule,
)
from cmm.domains.rule_execution import DefaultDomainRuleExecutor
from cmm.domains.trace_contracts import (
    CrossDomainTraceReference,
    DomainResultTraceReference,
    DomainTrace,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceStatus,
)
from cmm.domains.workflow_contracts import DomainWorkflowContext
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.workflows.contracts import WorkflowRun
from cmm.workflows.engine import NodeExecution
from cmm.workflows.enums import WorkflowRunStatus
from tests.domains._languages_runtime_state import (
    find_languages_runtime_purity_violations,
    snapshot_languages_module_state,
)

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)

FROZEN_SEMANTIC_CHECKPOINTS = (
    "01-onboard-english",
    "02-resolve-languages-primary",
    "03-prefer-american-english",
    "04-accept-valid-british-alternative",
    "05-preserve-two-active-goals",
    "06-authorize-progress-tracking",
    "07-record-prior-lower-certificate",
    "08-represent-certificate-as-certified",
    "09-assess-initial-writing-sample",
    "10-record-observed-writing-performance",
    "11-preserve-certified-level",
    "12-detect-missing-speaking-evidence",
    "13-preserve-speaking-gap",
    "14-bound-estimated-writing-range-by-evidence",
    "15-create-adaptive-plan",
    "16-execute-adaptive-lesson-workflow",
    "17-complete-real-exercise",
    "18-observe-one-error",
    "19-reject-single-error-as-pattern",
    "20-execute-real-conversation-roleplay-turns",
    "21-observe-later-comparable-target-error",
    "22-evaluate-accumulated-error-pattern-evidence",
    "23-promote-only-supported-recurrence",
    "24-prioritize-corrections-selectively",
    "25-produce-structured-writing-feedback",
    "26-preserve-valid-varieties-as-non-errors",
    "27-execute-progress-checkpoint-workflow",
    "28-reject-one-better-score-as-stable-progress",
    "29-accept-only-comparable-accumulated-progression",
    "30-set-official-certification-target",
    "31-detect-stale-guide-current-source-conflict",
    "32-select-current-official-certification-source",
    "33-separate-readiness-from-proficiency",
    "34-propose-pedagogical-review-schedule",
    "35-preserve-calendar-without-mutation",
    "36-receive-user-calendar-event-request",
    "37-route-calendar-request-to-shared-boundary",
    "38-propose-persistent-progress-update",
    "39-validate-consent-and-permission-before-persistence",
    "40-project-minimum-languages-context-to-oppositions",
    "41-withhold-full-learning-history",
    "42-present-certified-estimated-observed-distinctly",
    "43-present-unassessed-speaking-pronunciation-gaps",
    "44-trace-actual-connected-runtime-identifiers",
    "45-use-no-parallel-domain-infrastructure",
)

REQUIRED_CONNECTED_TRACE_KINDS = frozenset(
    {
        DomainTraceReferenceKind.PROFILE,
        DomainTraceReferenceKind.EVIDENCE,
        DomainTraceReferenceKind.RULE_PLAN,
        DomainTraceReferenceKind.RULE_RESULT,
        DomainTraceReferenceKind.OPERATION_RESULT,
        DomainTraceReferenceKind.WORKFLOW_RUN,
        DomainTraceReferenceKind.PERMISSION_DECISION,
        DomainTraceReferenceKind.MEMORY_PROPOSAL,
        DomainTraceReferenceKind.MEMORY_BINDING,
        DomainTraceReferenceKind.CROSS_DOMAIN_RESULT,
        DomainTraceReferenceKind.PRESENTATION_RESULT,
    }
)

_RUNTIME_OBJECT_OWNER_CONTRACTS: dict[
    DomainTraceReferenceKind, tuple[type[object], str]
] = {
    DomainTraceReferenceKind.RESOLUTION_CONTEXT: (DomainResolutionContext, "id"),
    DomainTraceReferenceKind.RESOLUTION_RESULT: (DomainResolutionResult, "id"),
    DomainTraceReferenceKind.COMPOSITION: (DomainComposition, "id"),
    DomainTraceReferenceKind.DOMAIN_RESULT: (DomainResult, "id"),
    DomainTraceReferenceKind.PROFILE: (DomainProfileDefinition, "id"),
    DomainTraceReferenceKind.RULE_PLAN: (DomainRuleExecutionPlan, "id"),
    DomainTraceReferenceKind.RULE_RESULT: (DomainRuleExecutionResult, "id"),
    DomainTraceReferenceKind.WORKFLOW_RUN: (WorkflowRun, "run_id"),
    DomainTraceReferenceKind.PERMISSION_DECISION: (
        PermissionGateResult,
        "decision_id",
    ),
    DomainTraceReferenceKind.APPROVAL_REQUEST: (ApprovalRequest, "id"),
    DomainTraceReferenceKind.APPROVAL_DECISION: (ApprovalDecision, "id"),
    DomainTraceReferenceKind.MEMORY_PROPOSAL: (
        DomainMemoryProposalSnapshot,
        "proposal_id",
    ),
    DomainTraceReferenceKind.MEMORY_BINDING: (
        DomainMemoryProposalBinding,
        "binding_id",
    ),
    DomainTraceReferenceKind.CROSS_DOMAIN_RESULT: (DomainResult, "id"),
    DomainTraceReferenceKind.CROSS_DOMAIN_TRACE: (DomainResult, "trace_id"),
}


def assert_runtime_owner_inventory(
    *,
    expected_id_to_kind: Mapping[str, DomainTraceReferenceKind],
    expected_id_to_owner: Mapping[str, object],
) -> None:
    """Prove every expected trace ID is owned by its canonical runtime source."""
    assert set(expected_id_to_owner) == set(expected_id_to_kind)
    for ref_id, kind in expected_id_to_kind.items():
        owner = expected_id_to_owner[ref_id]
        if kind in {
            DomainTraceReferenceKind.OPERATION_RESULT,
            DomainTraceReferenceKind.EVIDENCE,
            DomainTraceReferenceKind.PRESENTATION_RESULT,
        }:
            assert isinstance(owner, tuple) and len(owner) == 2
            result_mapping, id_field = owner
            assert isinstance(result_mapping, Mapping)
            assert isinstance(id_field, str)
            assert str(result_mapping[id_field]) == ref_id
            if kind is DomainTraceReferenceKind.OPERATION_RESULT:
                assert id_field.endswith("_id") and id_field != "provenance_id"
            elif kind is DomainTraceReferenceKind.EVIDENCE:
                assert id_field in {"id", "provenance_id"}
            else:
                assert id_field == "result_id"
            continue

        owner_type, id_field = _RUNTIME_OBJECT_OWNER_CONTRACTS[kind]
        assert isinstance(owner, owner_type)
        assert str(getattr(owner, id_field)) == ref_id


def assert_runtime_trace_provenance(
    *,
    trace: DomainTrace,
    expected_id_to_kind: Mapping[str, DomainTraceReferenceKind],
    expected_id_to_owner: Mapping[str, object],
    selected_profile_mode: str,
) -> bool:
    """Validate exact trace parity only after validating runtime ownership."""
    assert_runtime_owner_inventory(
        expected_id_to_kind=expected_id_to_kind,
        expected_id_to_owner=expected_id_to_owner,
    )
    references = trace.all_references()
    for reference in references:
        assert reference.ref_id in expected_id_to_kind
        assert reference.kind is expected_id_to_kind[reference.ref_id]
    assert set(expected_id_to_kind) == {reference.ref_id for reference in references}
    assert len(expected_id_to_kind) == len(references)
    assert trace.metadata["selected_profile_mode"] == selected_profile_mode
    assert selected_profile_mode in LANGUAGES_PEDAGOGICAL_MODES
    return True


def tamper_contribution_reference_ids(
    trace: DomainTrace, replacements: Mapping[str, str]
) -> DomainTrace:
    """Copy a trace while substituting contribution-owned runtime references."""
    return replace(
        trace,
        contributions=tuple(
            replace(
                contribution,
                references=tuple(
                    replace(
                        reference,
                        ref_id=replacements.get(reference.ref_id, reference.ref_id),
                    )
                    for reference in contribution.references
                ),
            )
            for contribution in trace.contributions
        ),
    )


def replace_expected_runtime_id(
    *,
    expected_id_to_kind: Mapping[str, DomainTraceReferenceKind],
    expected_id_to_owner: Mapping[str, object],
    original_id: str,
    replacement_id: str,
    replacement_owner: object,
) -> tuple[dict[str, DomainTraceReferenceKind], dict[str, object]]:
    """Copy an inventory while substituting one purported runtime owner."""
    assert replacement_id not in expected_id_to_kind
    kinds = dict(expected_id_to_kind)
    owners = dict(expected_id_to_owner)
    kind = kinds.pop(original_id)
    owners.pop(original_id)
    kinds[replacement_id] = kind
    owners[replacement_id] = replacement_owner
    return kinds, owners


def swap_expected_runtime_kinds(
    *,
    expected_id_to_kind: Mapping[str, DomainTraceReferenceKind],
    expected_id_to_owner: Mapping[str, object],
    first_id: str,
    second_id: str,
) -> tuple[dict[str, DomainTraceReferenceKind], dict[str, object]]:
    """Copy an inventory while swapping the claimed kinds of two runtime IDs."""
    kinds = dict(expected_id_to_kind)
    kinds[first_id], kinds[second_id] = kinds[second_id], kinds[first_id]
    return kinds, dict(expected_id_to_owner)


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
        assert bootstrap.resolver.fallback_domain == DomainId("general")
        context = DomainResolutionContextBuilder(id_factory=self.ids, clock=lambda: NOW).build(
            registry_snapshot=bootstrap.domain_registry.snapshot(),
            user_input="Help me practise English fluency while preparing for C1.",
            authorized_domains=("domain:general", LANGUAGES_DOMAIN_ID),
            signals=self.signals("languages"),
        )
        self.state["resolution_context"] = context
        self.actual_produced_ids.add(context.id)
        assert context.signals
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
        profile = bootstrap.profile_registry.get_by_domain(DomainId("languages"))
        self.state["profile"] = profile
        assert (
            isinstance(profile, DomainProfileDefinition)
            and profile.profile_name == "LanguageLearningProfile"
        )
        selected_profile_mode = "practice"
        assert selected_profile_mode in LANGUAGES_PEDAGOGICAL_MODES
        self.state["selected_profile_mode"] = selected_profile_mode
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
        self.checkpoint(
            "01-onboard-english", set(self.state["languages"]) == {"English"}
        )
        self.checkpoint(
            "02-resolve-languages-primary",
            str(resolution.primary_domain) == LANGUAGES_DOMAIN_ID,
        )
        self.checkpoint(
            "03-prefer-american-english",
            english["preferred_variety"] == "American English",
        )
        variety = classify_language_variety(preferred_variety="American English", observed_variety="British English", form_status="valid")
        self.state["variety"] = variety
        self.checkpoint(
            "04-accept-valid-british-alternative",
            variety["is_valid_alternative"]
            and variety["classification"] == "valid_alternative",
        )
        self.checkpoint(
            "05-preserve-two-active-goals",
            len(english["goals"]) == 2
            and all(goal["active"] is True for goal in english["goals"]),
        )
        self.checkpoint(
            "06-authorize-progress-tracking", english["tracking_consent"] is True
        )
        self.state["certificate"] = classify_proficiency_record(
            kind="CERTIFIED", framework="CEFR", level_or_score="B1", skill_scope="writing",
            evidence=({"source_kind": "official_certificate", "source_id": "official-certificate-record", "certificate_id": "certificate-B1"},),
        )
        self.checkpoint(
            "07-record-prior-lower-certificate",
            self.state["certificate"]["level_or_score"] == "B1"
            and english["goals"][1]["target"] == "C1",
        )
        self.checkpoint(
            "08-represent-certificate-as-certified",
            self.state["certificate"]["kind"] == "CERTIFIED"
            and self.state["certificate"]["is_certified"] is True,
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
            self.state["lesson_input_mode"] = inputs.get("mode")
            result = generate_lesson_result(language=inputs["language"], target_skill=inputs.get("target_skill", "writing"), current_level=inputs.get("current_level", "B1"), topic=inputs.get("topic", "inversion"), mode=inputs.get("mode"))
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
            dependency_violations = find_languages_runtime_purity_violations(
                plan_review_schedule_result
            )
            runtime_state_before = snapshot_languages_module_state(
                languages_operations
            )
            result = plan_review_schedule_result(review_items=producer["candidate_updates"], available_time=20)
            runtime_state_after = snapshot_languages_module_state(
                languages_operations
            )
            self.state.update(
                schedule_runtime_dependency_violations=dependency_violations,
                schedule_runtime_state_before=runtime_state_before,
                schedule_runtime_state_after=runtime_state_after,
                calendar_mutated=(
                    bool(dependency_violations)
                    or runtime_state_after != runtime_state_before
                ),
            )
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
            result = prepare_certification_result(
                target_certification=inputs["target_certification"],
                current_profile=inputs.get("current_profile"),
                official_source=selected_source,
            )
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
                "mode": self.state["selected_profile_mode"],
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
                "current_profile": {
                    "skill_levels": {"writing": "B2", "speaking": "B1"},
                },
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
        assessment_outputs = runs["languages.proficiency_assessment"].common_run.outputs
        assessment, update = assessment_outputs["assess"], assessment_outputs["level_update"]
        self.state.update(assessment=assessment, level_update=update)
        self.checkpoint(
            "09-assess-initial-writing-sample", bool(assessment["assessment_id"])
        )
        self.checkpoint(
            "10-record-observed-writing-performance",
            assessment["proficiency_kind"] == "OBSERVED_PERFORMANCE",
        )
        self.checkpoint(
            "11-preserve-certified-level",
            update["certificate_overwritten"] is False
            and update["updated_record"]["kind"] == "CERTIFIED"
            and update["updated_record"]["level_or_score"] == "B1",
        )
        self.checkpoint(
            "12-detect-missing-speaking-evidence",
            "speaking" in assessment["missing_evidence"],
        )
        self.checkpoint(
            "13-preserve-speaking-gap",
            update["skill_gaps_erased"] is False
            and "speaking" in assessment["missing_evidence"],
        )
        self.checkpoint(
            "14-bound-estimated-writing-range-by-evidence",
            assessment["skill_scope"] == "writing"
            and assessment["observed_performance"] == "B2"
            and assessment["confidence"] > 0.0
            and update["stable_update_supported"] is False,
        )
        self.checkpoint(
            "15-create-adaptive-plan",
            bool(onboarding["plan_id"])
            and len(onboarding["goals"]) == 2
            and onboarding["persistence_applied"] is False,
        )

        lesson = runs["languages.adaptive_language_lesson"].common_run.outputs
        self.checkpoint(
            "16-execute-adaptive-lesson-workflow",
            bool(lesson["lesson"]["lesson_id"]),
        )
        self.checkpoint(
            "17-complete-real-exercise",
            bool(lesson["exercises"]["exercise_batch_id"])
            and bool(lesson["review"]["review_id"]),
        )
        self.checkpoint(
            "18-observe-one-error", len(lesson["review"]["observed_errors"]) == 1
        )
        self.checkpoint(
            "19-reject-single-error-as-pattern",
            lesson["review"]["pattern_candidate"] is False
            and lesson["review"]["stable_proficiency_changed"] is False,
        )
        practice = runs["languages.conversation_roleplay_practice"].common_run.outputs
        self.checkpoint(
            "20-execute-real-conversation-roleplay-turns",
            bool(practice["conversation_turn"]["turn_id"])
            and bool(practice["roleplay_turn"]["roleplay_id"]),
        )
        errors = self.state["remediation_consumed_errors"]
        self.state["independent_errors"] = errors
        self.checkpoint(
            "21-observe-later-comparable-target-error",
            errors[0]["provenance_id"] != errors[1]["provenance_id"]
            and errors[0]["comparison_key"] == errors[1]["comparison_key"],
        )
        pattern = evaluate_error_pattern(observations=errors)
        self.state["pattern"] = pattern
        self.checkpoint(
            "22-evaluate-accumulated-error-pattern-evidence",
            pattern["eligible"] is True,
        )
        self.checkpoint(
            "23-promote-only-supported-recurrence",
            pattern["pattern_state"] == "candidate"
            and pattern["independent_occurrences"] == 2
            and pattern["comparable_contexts"] == 2,
        )
        priority = prioritize_corrections(errors=(*errors, {"id": "style", "category": "minor_style"}), mode="practice")
        self.state["priority"] = priority
        self.checkpoint(
            "24-prioritize-corrections-selectively",
            priority["selective_density"] is True
            and priority["immediate_correction_count"]
            < len(priority["prioritized_errors"]),
        )

        writing = runs["languages.writing_review"].common_run.outputs["review"]
        writing_presentation = present_languages_result(writing)
        self.state["writing_presentation"] = writing_presentation
        self.checkpoint(
            "25-produce-structured-writing-feedback",
            bool(writing["review_id"])
            and bool(writing["strengths"])
            and bool(writing["register_feedback"]),
        )
        self.checkpoint(
            "26-preserve-valid-varieties-as-non-errors",
            writing_presentation["valid_alternatives"][0]["status"]
            == "valid_alternative"
            and writing_presentation["valid_variety_misclassified"] is False,
        )
        progress = runs["languages.progress_checkpoint"].common_run.outputs["progress"]
        self.checkpoint(
            "27-execute-progress-checkpoint-workflow", bool(progress["review_id"])
        )
        short = evaluate_progression(previous_evidence=baseline, current_evidence=current[:1], skill="writing")
        self.state["short_progress"] = short
        self.checkpoint(
            "28-reject-one-better-score-as-stable-progress",
            short["stable_progression"] is False,
        )
        non_comparable = evaluate_progression(
            previous_evidence=baseline,
            current_evidence=tuple({**item, "comparable": False} for item in current),
            skill="writing",
        )
        self.checkpoint(
            "29-accept-only-comparable-accumulated-progression",
            progress["stable_progression"] is True
            and progress["skill_progress"] == {"writing": "stable_improvement"}
            and non_comparable["stable_progression"] is False,
        )
        certification = runs["languages.certification_preparation"].common_run.outputs["certification"]
        self.checkpoint(
            "30-set-official-certification-target",
            certification["target_certification"] == "Cambridge C1",
        )
        authority = self.state["certification_authority"]
        certification_inputs = workflow_inputs["languages.certification_preparation"]
        self.checkpoint(
            "31-detect-stale-guide-current-source-conflict",
            certification_inputs["official_source"]["id"] == "stale-guide"
            and {source["id"] for source in certification_inputs["official_sources"]}
            == {"stale-official", "current-official"},
        )
        self.checkpoint(
            "32-select-current-official-certification-source",
            authority["selected_source"]["id"] == "current-official",
        )
        self.checkpoint(
            "33-separate-readiness-from-proficiency",
            certification["readiness_score"] > 0.0
            and certification["readiness_promoted_to_proficiency"] is False,
        )
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
        assert stale_certification_run.status is WorkflowRunStatus.COMPLETED
        assert stale_certification["needs_verification"] is True
        spaced = runs["languages.vocabulary_spaced_review"].common_run.outputs["review_plan"]
        self.state["spaced_review"] = spaced
        self.checkpoint(
            "34-propose-pedagogical-review-schedule", bool(spaced["schedule_id"])
        )
        self.checkpoint(
            "35-preserve-calendar-without-mutation",
            spaced["calendar_modified"] is False
            and spaced["external_action_executed"] is False
            and not self.state["schedule_runtime_dependency_violations"]
            and self.state["calendar_mutated"] is False,
        )

        assert len(runs) == 9
        assert self.state["level_update_consumed_assessment"] == assessment
        assert self.state["adapter_saw_inputs"] is True

    def permission_and_memory(self) -> None:
        registry = DomainPermissionRegistry()
        registry.register(build_languages_permission_policy())
        registry.register(build_general_permission_policy())
        service = ApprovalService(InMemoryApprovalRepository())
        gate = DomainPermissionGate(DomainPermissionResolver(registry), service, clock=lambda: NOW)
        calendar_request = {
            "request_id": self.ids(),
            "capability": PermissionCapability.SCHEDULE_MODIFY.value,
            "event": {
                "title": "English spaced review",
                "duration_minutes": self.state["spaced_review"][
                    "recommended_duration_minutes"
                ],
            },
            "requested_by": "user",
        }
        calendar_operation = DomainOperationDefinition(
            operation_id="general.calendar_event_create",
            domain_id="domain:general",
            version="1.0.0",
            name="Create calendar event through shared external boundary",
            description="Test-only request routed to the canonical shared gate.",
            operation_type=DomainOperationType.EXTERNAL,
            required_permissions=(PermissionCapability.SCHEDULE_MODIFY.value,),
            risk_level=PolicyRiskLevel.LOW,
            reversible=True,
        )
        calendar_boundary = gate.evaluate_operation_definition(
            calendar_operation,
            request_id=calendar_request["request_id"],
            actor_id="actor-at-dp-026",
            session_id="session-at-dp-026",
        )
        self.state.update(
            calendar_request=calendar_request,
            calendar_operation=calendar_operation,
            calendar_boundary=calendar_boundary,
        )
        self.checkpoint(
            "36-receive-user-calendar-event-request",
            calendar_request["requested_by"] == "user"
            and calendar_request["event"]["title"]
            == "English spaced review"
            and calendar_request["capability"]
            == PermissionCapability.SCHEDULE_MODIFY.value,
        )
        self.checkpoint(
            "37-route-calendar-request-to-shared-boundary",
            calendar_operation.operation_id == "general.calendar_event_create"
            and calendar_operation.required_permissions
            == (PermissionCapability.SCHEDULE_MODIFY.value,)
            and calendar_boundary.outcome is PermissionGateOutcome.DENY
            and not calendar_boundary.allowed
            and self.state["calendar_mutated"] is False,
        )
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
        trace_id = self.ids()
        proposal = build_languages_memory_proposal(
            proposal_id=proposal_id,
            affected_reference_ids=(reference_id,),
        )
        self.checkpoint(
            "38-propose-persistent-progress-update",
            proposal.proposal_id == proposal_id
            and not service.repository.is_consumed(approval.id),
        )
        consumed = gate.evaluate_operation_definition(
            operation, request_id=permission_request_id,
            actor_id="actor-at-dp-026", session_id="session-at-dp-026",
            approval_request_id=approval.id,
        )
        assert consumed.decision_id is not None
        memory_permission = DomainMemoryPermissionDecisionSnapshot(
            decision_id=consumed.decision_id, allowed=consumed.allowed,
            capabilities=(DomainMemoryCapability.PROPOSE,),
            source_domain_id=LANGUAGES_DOMAIN_ID, target_domain_id=LANGUAGES_DOMAIN_ID,
            sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
        )
        request = build_languages_memory_view_request(
            request_id=self.ids(), trace_id=trace_id,
            requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
            candidates=(reference,), permission_decision_ids=(consumed.decision_id,),
        )
        base_inventory = DomainMemoryReferenceInventory(
            references=(reference,),
            traces=(DomainMemoryTraceSnapshot(trace_id=trace_id, primary_domain=LANGUAGES_DOMAIN_ID),),
            permission_decisions=(memory_permission,),
        )
        view = build_languages_memory_view(request=request, inventory=base_inventory)
        binding = build_languages_memory_binding(
            proposal=proposal, view=view, trace_id=trace_id,
            permission_decision_ids=(consumed.decision_id,), approval_request_ids=(approval.id,),
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
        self.state.update(
            memory_proposal=proposal,
            memory_binding=binding,
            memory_view=view,
            memory_validation=validation,
            memory_permission=memory_permission,
            permission_consumed=consumed,
            actual_gate_results=(calendar_boundary, pending, consumed),
        )
        self.actual_produced_ids.update(
            (
                proposal.proposal_id,
                binding.binding_id,
                view.view_id,
                consumed.decision_id,
                trace_id,
            )
        )
        self.actual_produced_ids.update(
            gate_result.decision_id
            for gate_result in self.state["actual_gate_results"]
            if gate_result.decision_id is not None
        )
        self.checkpoint(
            "39-validate-consent-and-permission-before-persistence",
            self.state["languages"]["English"]["tracking_consent"] is True
            and consumed.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
            and consumed.allowed
            and validation.is_valid,
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
            "40-project-minimum-languages-context-to-oppositions",
            str(resolution.primary_domain) == "domain:oppositions"
            and LANGUAGES_DOMAIN_ID in {str(item) for item in resolution.supporting_domains}
            and str(composition.primary_domain) == "domain:oppositions"
            and set(projection.to_dict()["findings"][0]) == allowed_keys,
        )
        self.checkpoint(
            "41-withhold-full-learning-history",
            not forbidden.intersection(projection.to_dict()["findings"][0]),
        )
        presented = [present_languages_result(result) for result in self.state["operation_outputs"]]
        presented.extend(
            present_languages_result(run.common_run.to_dict())
            for run in self.state["workflow_runs"].values()
        )
        presented.append(present_languages_result(projection.to_dict()))
        self.state["presented_results"] = presented
        presentation_result = {
            "result_id": self.ids(),
            "items": tuple(presented),
        }
        self.state["presentation_result"] = presentation_result
        self.actual_produced_ids.add(presentation_result["result_id"])
        speaking = next(item for item in presented if item.get("transcript_text") is not None)
        self.checkpoint(
            "42-present-certified-estimated-observed-distinctly",
            certificate["kind"] == "CERTIFIED"
            and assessment["proficiency_kind"] == "OBSERVED_PERFORMANCE"
            and self.state["writing_presentation"]["estimated_level"] == "A2"
            and all(
                item["presentation_format"] == "standard_pedagogy"
                for item in presented
            ),
        )
        self.checkpoint(
            "43-present-unassessed-speaking-pronunciation-gaps",
            speaking["pronunciation_assessed"] is False
            and speaking["pronunciation_badge"] == "Audio evidence not provided"
            and "pronunciation_evidence" in speaking["missing_evidence"],
        )

    def execute_selected_trace_rules(self) -> None:
        rules = {rule.definition.id: rule for rule in build_languages_rules()}
        certification_inputs = self.state["workflow_inputs"][
            "languages.certification_preparation"
        ]
        selected_rule_ids = (
            "languages.error_pattern_evidence",
            "languages.progression_evidence",
            "languages.certification_temporal",
        )
        material = {
            "observations": self.state["independent_errors"],
            "previous_evidence": self.state["baseline"],
            "current_evidence": self.state["current"],
            "skill": "writing",
            "sources": certification_inputs["official_sources"],
            "decision_critical": True,
        }
        profile = self.state["profile"]
        rule_plan = DomainRuleExecutionPlan(
            id=self.ids(),
            status=DomainRuleSelectionStatus.READY,
            created_at=NOW,
            selected_rules=tuple(
                SelectedReasoningRule(
                    definition=rules[rule_id].definition,
                    sources=(
                        DomainRuleSourceRecord(
                            source=DomainRuleSource.PROFILE,
                            reference=rule_id,
                            required=True,
                            domain_id=LANGUAGES_DOMAIN_ID,
                            profile_name=profile.profile_name,
                        ),
                    ),
                    group=DomainRuleSource.PRIMARY_DOMAIN,
                    required=True,
                )
                for rule_id in selected_rule_ids
            ),
            contributing_profiles=(profile.profile_name,),
            contributing_domains=(LANGUAGES_DOMAIN_ID,),
        )
        rule_registry = InMemoryReasoningRuleRegistry()
        for rule_id in selected_rule_ids:
            rule_registry.register(rules[rule_id])
        rule_execution = DefaultDomainRuleExecutor(
            clock=lambda: NOW,
            id_factory=self.ids,
        ).execute(
            plan=rule_plan,
            context=ReasoningRuleContext(
                reasoning_id=self.ids(),
                timestamp=NOW,
                session_id="session-at-dp-026",
                active_domains=(LANGUAGES_DOMAIN_ID,),
                primary_domain=LANGUAGES_DOMAIN_ID,
                metadata={"material": material},
            ),
            registry=rule_registry,
        )
        findings = {finding.code: finding for finding in rule_execution.findings}
        assert findings["ERROR_PATTERN_EVALUATED"].metadata["pattern_state"] == "candidate"
        assert (
            findings["PROGRESSION_EVIDENCE_EVALUATED"].metadata[
                "progression_outcome"
            ]
            == "stable_improvement"
        )
        assert (
            findings["CERTIFICATION_TEMPORAL_EVALUATED"].metadata[
                "selected_source"
            ]["id"]
            == "current-official"
        )
        assert (
            findings["CERTIFICATION_TEMPORAL_EVALUATED"].metadata[
                "needs_verification"
            ]
            is False
        )
        self.state["rule_plan"] = rule_plan
        self.state["rule_execution"] = rule_execution
        self.state["selected_rule_results"] = rule_execution.rule_results
        self.actual_produced_ids.update((rule_plan.id, rule_execution.id))

    def trace(self) -> None:
        self.execute_selected_trace_rules()
        operation_result_owners: dict[str, tuple[Mapping[str, Any], str]] = {}
        for result in self.state["operation_outputs"]:
            for id_field, value in result.items():
                if id_field.endswith("_id") and isinstance(value, str):
                    assert value not in operation_result_owners
                    operation_result_owners[value] = (result, id_field)
        operation_results_by_id = {
            result_id: owner[0]
            for result_id, owner in operation_result_owners.items()
        }
        evidence_owners: dict[str, tuple[Mapping[str, Any], str]] = {
            item["provenance_id"]: (item, "provenance_id")
            for item in (*self.state["baseline"], *self.state["current"])
        }
        selected_source = self.state["certification_selected_source"]
        evidence_owners[selected_source["id"]] = (selected_source, "id")
        evidence_by_id = {
            evidence_id: owner[0] for evidence_id, owner in evidence_owners.items()
        }
        runs = self.state["workflow_runs"]
        domain_result = DomainResult(
            id=self.ids(),
            status="completed",
            objective="Connected Languages acceptance result",
            primary_domain=LANGUAGES_DOMAIN_ID,
            operation_result_ids=tuple(sorted(operation_results_by_id)),
            approval_ids=(self.state["approval_request"].id,),
            trace_id=self.state["memory_binding"].trace_id,
            confidence=0.8,
        )
        self.state["domain_result"] = domain_result
        cross = self.state["cross_projection"]
        cross_reference = CrossDomainTraceReference(
            result_id=str(cross.id), trace_id=cross.trace_id
        )
        resolution, composition, context = (
            self.state["resolution"],
            self.state["composition"],
            self.state["resolution_context"],
        )
        profile = self.state["profile"]
        permission_gate_result = self.state["permission_consumed"]
        assert permission_gate_result.decision_id is not None
        memory_proposal = self.state["memory_proposal"]
        memory_binding = self.state["memory_binding"]
        presentation_result = self.state["presentation_result"]
        rule_plan = self.state["rule_plan"]
        rule_execution = self.state["rule_execution"]

        structural_expected_id_to_kind = {
            str(domain_result.id): DomainTraceReferenceKind.DOMAIN_RESULT,
        }
        structural_expected_id_to_owner: dict[str, object] = {
            str(domain_result.id): domain_result,
        }
        expected_id_to_kind = dict(structural_expected_id_to_kind)
        expected_id_to_owner = dict(structural_expected_id_to_owner)

        def expect(
            ref_id: str, kind: DomainTraceReferenceKind, owner: object
        ) -> None:
            assert ref_id not in expected_id_to_kind
            expected_id_to_kind[ref_id] = kind
            expected_id_to_owner[ref_id] = owner

        expect(context.id, DomainTraceReferenceKind.RESOLUTION_CONTEXT, context)
        expect(resolution.id, DomainTraceReferenceKind.RESOLUTION_RESULT, resolution)
        expect(composition.id, DomainTraceReferenceKind.COMPOSITION, composition)
        expect(
            str(cross.id), DomainTraceReferenceKind.CROSS_DOMAIN_RESULT, cross
        )
        expect(cross.trace_id, DomainTraceReferenceKind.CROSS_DOMAIN_TRACE, cross)
        expect(
            presentation_result["result_id"],
            DomainTraceReferenceKind.PRESENTATION_RESULT,
            (presentation_result, "result_id"),
        )
        expect(str(profile.id), DomainTraceReferenceKind.PROFILE, profile)
        for run in runs.values():
            expect(
                run.common_run.run_id,
                DomainTraceReferenceKind.WORKFLOW_RUN,
                run.common_run,
            )
        for result_id, owner in operation_result_owners.items():
            expect(result_id, DomainTraceReferenceKind.OPERATION_RESULT, owner)
        for evidence_id, owner in evidence_owners.items():
            expect(evidence_id, DomainTraceReferenceKind.EVIDENCE, owner)
        expect(rule_plan.id, DomainTraceReferenceKind.RULE_PLAN, rule_plan)
        expect(
            rule_execution.id,
            DomainTraceReferenceKind.RULE_RESULT,
            rule_execution,
        )
        expect(
            permission_gate_result.decision_id,
            DomainTraceReferenceKind.PERMISSION_DECISION,
            permission_gate_result,
        )
        expect(
            self.state["approval_request"].id,
            DomainTraceReferenceKind.APPROVAL_REQUEST,
            self.state["approval_request"],
        )
        expect(
            self.state["approval_decision"].id,
            DomainTraceReferenceKind.APPROVAL_DECISION,
            self.state["approval_decision"],
        )
        expect(
            memory_proposal.proposal_id,
            DomainTraceReferenceKind.MEMORY_PROPOSAL,
            memory_proposal,
        )
        expect(
            memory_binding.binding_id,
            DomainTraceReferenceKind.MEMORY_BINDING,
            memory_binding,
        )

        assert expected_id_to_owner[context.id] is context
        assert expected_id_to_owner[resolution.id] is resolution
        assert expected_id_to_owner[composition.id] is composition
        assert expected_id_to_owner[str(domain_result.id)] is domain_result
        assert expected_id_to_owner[str(profile.id)] is profile
        assert expected_id_to_owner[rule_plan.id] is rule_plan
        assert expected_id_to_owner[rule_execution.id] is rule_execution
        assert (
            expected_id_to_owner[permission_gate_result.decision_id]
            is permission_gate_result
        )
        assert (
            expected_id_to_owner[self.state["approval_request"].id]
            is self.state["approval_request"]
        )
        assert (
            expected_id_to_owner[self.state["approval_decision"].id]
            is self.state["approval_decision"]
        )
        assert expected_id_to_owner[memory_proposal.proposal_id] is memory_proposal
        assert expected_id_to_owner[memory_binding.binding_id] is memory_binding
        assert expected_id_to_owner[str(cross.id)] is cross
        assert expected_id_to_owner[cross.trace_id] is cross
        for run in runs.values():
            assert expected_id_to_owner[run.common_run.run_id] is run.common_run
        for result_id, (result_mapping, id_field) in operation_result_owners.items():
            owner_mapping, owner_id_field = expected_id_to_owner[result_id]
            assert owner_mapping is result_mapping
            assert owner_id_field == id_field
        for evidence_id, (evidence_mapping, id_field) in evidence_owners.items():
            owner_mapping, owner_id_field = expected_id_to_owner[evidence_id]
            assert owner_mapping is evidence_mapping
            assert owner_id_field == id_field
        presentation_owner, presentation_id_field = expected_id_to_owner[
            presentation_result["result_id"]
        ]
        assert presentation_owner is presentation_result
        assert presentation_id_field == "result_id"
        assert_runtime_owner_inventory(
            expected_id_to_kind=expected_id_to_kind,
            expected_id_to_owner=expected_id_to_owner,
        )

        global_kinds = {
            DomainTraceReferenceKind.RESOLUTION_CONTEXT,
            DomainTraceReferenceKind.RESOLUTION_RESULT,
            DomainTraceReferenceKind.COMPOSITION,
            DomainTraceReferenceKind.CROSS_DOMAIN_RESULT,
            DomainTraceReferenceKind.CROSS_DOMAIN_TRACE,
            DomainTraceReferenceKind.PRESENTATION_RESULT,
        }
        expected_references = tuple(
            DomainTraceReference(ref_id, kind)
            if kind in global_kinds
            else build_languages_trace_reference(ref_id=ref_id, kind=kind)
            for ref_id, kind in expected_id_to_kind.items()
        )
        contribution_references = tuple(
            reference
            for reference in expected_references
            if reference.kind
            not in global_kinds | {DomainTraceReferenceKind.DOMAIN_RESULT}
        )
        request_id = self.ids()
        goal_id = self.state["languages"]["English"]["goals"][0]["id"]
        trace_metadata = {
            "selected_profile_mode": self.state["selected_profile_mode"],
        }
        trace_references = DomainTraceReferences(
            resolution_context_id=context.id,
            resolution_result_id=resolution.id,
            composition_id=composition.id,
            cross_domain_results=(cross_reference,),
            presentation_result_ids=(presentation_result["result_id"],),
        )
        probe = DomainTrace(
            id="domain-trace:probe",
            digest="0" * 64,
            request_id=request_id,
            goal_id=goal_id,
            primary_domain=LANGUAGES_DOMAIN_ID,
            supporting_domains=(),
            contributions=(
                build_languages_trace_contribution(
                    domain_result_id=str(domain_result.id),
                    references=contribution_references,
                ),
            ),
            references=trace_references,
            domain_results=(
                DomainResultTraceReference(
                    str(domain_result.id),
                    LANGUAGES_DOMAIN_ID,
                    "domain-trace:probe",
                ),
            ),
            status=DomainTraceStatus.COMPLETED,
            started_at=NOW,
            completed_at=NOW,
            duration_ms=0,
            metadata=trace_metadata,
        )
        expected_trace_id = probe.canonical_id
        domain_result_references = (
            DomainResultTraceReference(
                str(domain_result.id), LANGUAGES_DOMAIN_ID, expected_trace_id
            ),
        )
        inventory = DomainTraceReferenceInventory(
            references=expected_references,
            domain_results=domain_result_references,
            cross_domain_results=(cross_reference,),
            expected_primary_domain=LANGUAGES_DOMAIN_ID,
            expected_supporting_domains=(),
            resolution_result_domains=DomainTraceDomainSelection(
                resolution.id, LANGUAGES_DOMAIN_ID
            ),
            composition_domains=DomainTraceDomainSelection(
                composition.id, LANGUAGES_DOMAIN_ID
            ),
        )
        self.state.update(
            expected_id_to_kind=dict(expected_id_to_kind),
            expected_id_to_owner=dict(expected_id_to_owner),
            structural_expected_id_to_kind=dict(structural_expected_id_to_kind),
            structural_expected_id_to_owner=dict(structural_expected_id_to_owner),
            operation_results_by_id=operation_results_by_id,
            evidence_by_id=evidence_by_id,
            trace_inventory=inventory,
            trace_runtime_objects={
                "profile": profile,
                "operations": operation_results_by_id,
                "evidence": evidence_by_id,
                "rule_plan": rule_plan,
                "rule_execution": rule_execution,
                "permission": permission_gate_result,
                "memory_proposal": memory_proposal,
                "memory_binding": memory_binding,
                "presentation": presentation_result,
            },
        )

        trace = assemble_languages_trace(
            request_id=request_id,
            resolution_context_id=context.id,
            resolution_result_id=resolution.id,
            composition_id=composition.id,
            domain_result_id=str(domain_result.id),
            started_at=NOW,
            completed_at=NOW,
            references=contribution_references,
            cross_domain_results=(cross_reference,),
            presentation_result_ids=(presentation_result["result_id"],),
            goal_id=goal_id,
            metadata=trace_metadata,
        )
        assert trace.id == expected_trace_id
        validation = validate_languages_trace(trace=trace, inventory=inventory)
        ownership_provenance_valid = assert_runtime_trace_provenance(
            trace=trace,
            expected_id_to_kind=expected_id_to_kind,
            expected_id_to_owner=expected_id_to_owner,
            selected_profile_mode=self.state["selected_profile_mode"],
        )
        self.state.update(trace=trace, trace_validation=validation)
        self.required_trace_ids = {item.ref_id for item in trace.all_references()}
        self.actual_produced_ids.update(expected_id_to_kind)
        assert self.required_trace_ids <= self.actual_produced_ids
        trace_kinds = {item.kind for item in trace.all_references()}
        runtime_provenance_valid = (
            ownership_provenance_valid
            and REQUIRED_CONNECTED_TRACE_KINDS <= trace_kinds
            and {
                DomainTraceReferenceKind.RESOLUTION_CONTEXT,
                DomainTraceReferenceKind.RESOLUTION_RESULT,
                DomainTraceReferenceKind.RULE_PLAN,
            }
            <= trace_kinds
            and trace.metadata["selected_profile_mode"]
            == self.state["selected_profile_mode"]
            and set(expected_id_to_kind) == self.required_trace_ids
        )
        self.checkpoint(
            "44-trace-actual-connected-runtime-identifiers",
            validation.valid and runtime_provenance_valid,
        )
        self.checkpoint(
            "45-use-no-parallel-domain-infrastructure",
            len(self.state["workflow_runs"]) == 9
            and isinstance(self.state["resolver"], DefaultDomainResolver)
            and isinstance(self.state["permission_gate"], DomainPermissionGate)
            and self.state["calendar_mutated"] is False,
        )

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


def test_at_dp_026_routes_calendar_request_through_shared_schedule_boundary() -> None:
    scenario = ConnectedLanguagesScenario()
    scenario.run()

    request = scenario.state["calendar_request"]
    boundary = scenario.state["calendar_boundary"]
    assert request["capability"] == PermissionCapability.SCHEDULE_MODIFY.value
    assert boundary.outcome is PermissionGateOutcome.DENY
    assert boundary.action == PermissionCapability.OPERATION_EXECUTE.value
    assert scenario.state["schedule_runtime_dependency_violations"] == ()
    assert (
        scenario.state["schedule_runtime_state_after"]
        == scenario.state["schedule_runtime_state_before"]
    )
    assert scenario.state["calendar_mutated"] is False


def test_at_dp_026_trace_permission_decision_is_real_gate_result() -> None:
    """Catches a synthetic permission ID standing in for the consumed gate result."""
    scenario = ConnectedLanguagesScenario()
    scenario.run()

    consumed = scenario.state["permission_consumed"]
    memory_permission = scenario.state["memory_permission"]
    actual_gate_results = scenario.state["actual_gate_results"]
    trace_permission_ids = {
        reference.ref_id
        for reference in scenario.state["trace"].all_references()
        if reference.kind is DomainTraceReferenceKind.PERMISSION_DECISION
    }

    assert consumed.decision_id is not None
    assert memory_permission.decision_id == consumed.decision_id
    assert trace_permission_ids == {consumed.decision_id}
    assert trace_permission_ids <= {
        gate_result.decision_id
        for gate_result in actual_gate_results
        if gate_result.decision_id is not None
    }


def test_at_dp_026_checkpoints_match_frozen_semantic_sequence() -> None:
    scenario = ConnectedLanguagesScenario()
    scenario.run()
    assert tuple(scenario.checkpoints) == FROZEN_SEMANTIC_CHECKPOINTS
    assert len(scenario.checkpoints) == 45


def test_at_dp_026_trace_never_labels_workflow_events_as_results() -> None:
    scenario = ConnectedLanguagesScenario()
    scenario.run()
    event_ids = {
        event.event_id
        for run in scenario.state["workflow_runs"].values()
        for event in run.execution_result.events
    }

    assert not any(
        reference.ref_id in event_ids
        and reference.kind is DomainTraceReferenceKind.WORKFLOW_RESULT
        for reference in scenario.state["trace"].all_references()
    )


def test_at_dp_026_trace_uses_runtime_rule_execution_not_static_rule_definitions() -> None:
    """Catches static ``languages.*`` definition IDs labeled as rule results."""
    scenario = ConnectedLanguagesScenario()
    scenario.run()

    rule_plan = scenario.state["rule_plan"]
    rule_execution = scenario.state["rule_execution"]
    definition_ids = {
        selected.definition.id for selected in rule_plan.selected_rules
    }
    trace_rule_result_ids = {
        reference.ref_id
        for reference in scenario.state["trace"].all_references()
        if reference.kind is DomainTraceReferenceKind.RULE_RESULT
    }
    trace_rule_plan_ids = {
        reference.ref_id
        for reference in scenario.state["trace"].all_references()
        if reference.kind is DomainTraceReferenceKind.RULE_PLAN
    }

    assert rule_execution.id not in definition_ids
    assert rule_execution.plan_id == rule_plan.id
    assert {result.rule_id for result in rule_execution.rule_results} == definition_ids
    assert trace_rule_plan_ids == {rule_plan.id}
    assert not definition_ids.intersection(trace_rule_result_ids)
    assert trace_rule_result_ids == {rule_execution.id}


def assert_selected_profile_mode_trace_semantics(
    *, scenario: ConnectedLanguagesScenario, trace: DomainTrace
) -> None:
    """Verify trace mode remains the mode used by the adaptive-lesson run."""
    selected_profile_mode = scenario.state["selected_profile_mode"]
    assert selected_profile_mode in LANGUAGES_PEDAGOGICAL_MODES
    assert scenario.state["lesson_input_mode"] == selected_profile_mode
    lesson = scenario.state["workflow_runs"][
        "languages.adaptive_language_lesson"
    ].common_run.outputs["lesson"]
    assert "active use" in lesson["guided_practice"].lower()
    assert trace.metadata["selected_profile_mode"] == selected_profile_mode
    assert trace.metadata["selected_profile_mode"] in LANGUAGES_PEDAGOGICAL_MODES


def test_at_dp_026_trace_preserves_selected_profile_mode() -> None:
    """Catches a connected trace that drops or substitutes the pedagogical mode."""
    scenario = ConnectedLanguagesScenario()
    scenario.run()

    trace = scenario.state["trace"]
    assert_selected_profile_mode_trace_semantics(scenario=scenario, trace=trace)

    unselected_mode = next(
        mode
        for mode in LANGUAGES_PEDAGOGICAL_MODES
        if mode != scenario.state["selected_profile_mode"]
    )
    tampered = replace(
        trace,
        metadata={**trace.metadata, "selected_profile_mode": unselected_mode},
    )

    with pytest.raises(AssertionError):
        assert_selected_profile_mode_trace_semantics(scenario=scenario, trace=tampered)


def test_at_dp_026_trace_matches_independent_runtime_kind_map() -> None:
    scenario = ConnectedLanguagesScenario()
    scenario.run()
    expected_id_to_kind = scenario.state["expected_id_to_kind"]
    actual_id_to_kind = {
        reference.ref_id: reference.kind
        for reference in scenario.state["trace"].all_references()
    }

    assert actual_id_to_kind == expected_id_to_kind
    assert {
        reference.ref_id: reference.kind
        for reference in scenario.state["trace_inventory"].references
    } == expected_id_to_kind


def test_at_dp_026_trace_contains_all_frozen_runtime_categories() -> None:
    scenario = ConnectedLanguagesScenario()
    scenario.run()
    actual_kinds = {
        reference.kind for reference in scenario.state["trace"].all_references()
    }

    assert REQUIRED_CONNECTED_TRACE_KINDS <= actual_kinds


def test_at_dp_026_trace_inventory_proves_runtime_owner_identity() -> None:
    """Catches an expected inventory derived only from trace membership."""
    scenario = ConnectedLanguagesScenario()
    scenario.run()

    assert "expected_id_to_owner" in scenario.state
    expected_id_to_kind = scenario.state["expected_id_to_kind"]
    expected_id_to_owner = scenario.state["expected_id_to_owner"]
    assert_runtime_trace_provenance(
        trace=scenario.state["trace"],
        expected_id_to_kind=expected_id_to_kind,
        expected_id_to_owner=expected_id_to_owner,
        selected_profile_mode=scenario.state["selected_profile_mode"],
    )

    assert expected_id_to_owner[scenario.state["resolution_context"].id] is (
        scenario.state["resolution_context"]
    )
    assert expected_id_to_owner[scenario.state["resolution"].id] is scenario.state[
        "resolution"
    ]
    assert expected_id_to_owner[scenario.state["composition"].id] is scenario.state[
        "composition"
    ]
    assert expected_id_to_owner[str(scenario.state["profile"].id)] is scenario.state[
        "profile"
    ]
    assert expected_id_to_owner[scenario.state["rule_plan"].id] is scenario.state[
        "rule_plan"
    ]
    assert expected_id_to_owner[scenario.state["rule_execution"].id] is (
        scenario.state["rule_execution"]
    )
    assert expected_id_to_owner[
        scenario.state["permission_consumed"].decision_id
    ] is scenario.state["permission_consumed"]
    assert expected_id_to_owner[
        scenario.state["approval_request"].id
    ] is scenario.state["approval_request"]
    assert expected_id_to_owner[
        scenario.state["approval_decision"].id
    ] is scenario.state["approval_decision"]
    assert expected_id_to_owner[
        scenario.state["memory_proposal"].proposal_id
    ] is scenario.state["memory_proposal"]
    assert expected_id_to_owner[
        scenario.state["memory_binding"].binding_id
    ] is scenario.state["memory_binding"]
    assert expected_id_to_owner[str(scenario.state["cross_projection"].id)] is (
        scenario.state["cross_projection"]
    )
    assert expected_id_to_owner[scenario.state["cross_projection"].trace_id] is (
        scenario.state["cross_projection"]
    )

    for run in scenario.state["workflow_runs"].values():
        assert expected_id_to_owner[run.common_run.run_id] is run.common_run
    for result_id, result_mapping in scenario.state[
        "operation_results_by_id"
    ].items():
        owner_mapping, owner_id_field = expected_id_to_owner[result_id]
        assert owner_mapping is result_mapping
        assert result_mapping[owner_id_field] == result_id
    for evidence_id, evidence_mapping in scenario.state["evidence_by_id"].items():
        owner_mapping, owner_id_field = expected_id_to_owner[evidence_id]
        assert owner_mapping is evidence_mapping
        assert evidence_mapping[owner_id_field] == evidence_id
    presentation = scenario.state["presentation_result"]
    presentation_owner, presentation_id_field = expected_id_to_owner[
        presentation["result_id"]
    ]
    assert presentation_owner is presentation
    assert presentation_id_field == "result_id"


def test_at_dp_026_trace_provenance_rejects_negative_mutation_matrix() -> None:
    """Catches kind-correct trace inventories whose IDs have the wrong owners."""
    scenario = ConnectedLanguagesScenario()
    scenario.run()

    assert "expected_id_to_owner" in scenario.state
    trace = scenario.state["trace"]
    expected_kinds = scenario.state["expected_id_to_kind"]
    expected_owners = scenario.state["expected_id_to_owner"]
    mutations: list[
        tuple[
            str,
            DomainTrace,
            dict[str, DomainTraceReferenceKind],
            dict[str, object],
        ]
    ] = []

    rule_execution = scenario.state["rule_execution"]
    rule_definition = scenario.state["rule_plan"].selected_rules[0].definition
    rule_kinds, rule_owners = replace_expected_runtime_id(
        expected_id_to_kind=expected_kinds,
        expected_id_to_owner=expected_owners,
        original_id=rule_execution.id,
        replacement_id=rule_definition.id,
        replacement_owner=rule_definition,
    )
    mutations.append(
        (
            "rule definition as result",
            tamper_contribution_reference_ids(
                trace, {rule_execution.id: rule_definition.id}
            ),
            rule_kinds,
            rule_owners,
        )
    )

    permission = scenario.state["permission_consumed"]
    assert permission.decision_id is not None
    random_permission_id = "random-permission-decision"
    permission_kinds, permission_owners = replace_expected_runtime_id(
        expected_id_to_kind=expected_kinds,
        expected_id_to_owner=expected_owners,
        original_id=permission.decision_id,
        replacement_id=random_permission_id,
        replacement_owner=permission,
    )
    mutations.append(
        (
            "random permission decision",
            tamper_contribution_reference_ids(
                trace, {permission.decision_id: random_permission_id}
            ),
            permission_kinds,
            permission_owners,
        )
    )

    workflow_run = next(iter(scenario.state["workflow_runs"].values()))
    workflow_event = workflow_run.execution_result.events[0]
    workflow_kinds, workflow_owners = replace_expected_runtime_id(
        expected_id_to_kind=expected_kinds,
        expected_id_to_owner=expected_owners,
        original_id=workflow_run.common_run.run_id,
        replacement_id=workflow_event.event_id,
        replacement_owner=workflow_event,
    )
    mutations.append(
        (
            "workflow event as run",
            tamper_contribution_reference_ids(
                trace, {workflow_run.common_run.run_id: workflow_event.event_id}
            ),
            workflow_kinds,
            workflow_owners,
        )
    )

    operation_id = next(
        ref_id
        for ref_id, owner in expected_owners.items()
        if expected_kinds[ref_id] is DomainTraceReferenceKind.OPERATION_RESULT
        and owner[1] == "plan_id"
    )
    evidence_id = next(
        ref_id
        for ref_id, owner in expected_owners.items()
        if expected_kinds[ref_id] is DomainTraceReferenceKind.EVIDENCE
        and owner[1] == "provenance_id"
    )
    evidence_kinds, evidence_owners = swap_expected_runtime_kinds(
        expected_id_to_kind=expected_kinds,
        expected_id_to_owner=expected_owners,
        first_id=operation_id,
        second_id=evidence_id,
    )
    mutations.append(
        (
            "operation as evidence",
            tamper_contribution_reference_ids(
                trace, {operation_id: evidence_id, evidence_id: operation_id}
            ),
            evidence_kinds,
            evidence_owners,
        )
    )

    proposal_id = scenario.state["memory_proposal"].proposal_id
    binding_id = scenario.state["memory_binding"].binding_id
    memory_kinds, memory_owners = swap_expected_runtime_kinds(
        expected_id_to_kind=expected_kinds,
        expected_id_to_owner=expected_owners,
        first_id=proposal_id,
        second_id=binding_id,
    )
    mutations.append(
        (
            "swapped memory proposal and binding",
            tamper_contribution_reference_ids(
                trace, {proposal_id: binding_id, binding_id: proposal_id}
            ),
            memory_kinds,
            memory_owners,
        )
    )

    unselected_mode = next(
        mode
        for mode in LANGUAGES_PEDAGOGICAL_MODES
        if mode != scenario.state["selected_profile_mode"]
    )
    mutations.append(
        (
            "unselected profile mode",
            replace(
                trace,
                metadata={**trace.metadata, "selected_profile_mode": unselected_mode},
            ),
            dict(expected_kinds),
            dict(expected_owners),
        )
    )

    for mutation_name, mutated_trace, mutated_kinds, mutated_owners in mutations:
        assert {
            reference.ref_id: reference.kind
            for reference in mutated_trace.all_references()
        } == mutated_kinds, mutation_name
        with pytest.raises(AssertionError):
            assert_runtime_trace_provenance(
                trace=mutated_trace,
                expected_id_to_kind=mutated_kinds,
                expected_id_to_owner=mutated_owners,
                selected_profile_mode=scenario.state["selected_profile_mode"],
            )
