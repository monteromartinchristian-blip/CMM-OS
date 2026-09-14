"""Tests for Phase 10.52 Mental Health Domain operations and workflows.

Task 3: exactly eight declarative operations with frozen semantics and eight
workflows over the shared Workflow Engine contract.  Declaration never means
availability, and no workflow defines its own executor or runtime.
"""

from __future__ import annotations

import pytest

from cmm.domains.mental_health.catalog import (
    MENTAL_HEALTH_OPERATION_IDS,
    MENTAL_HEALTH_WORKFLOW_IDS,
)
from cmm.domains.mental_health.operations import (
    build_mental_health_operation_definitions,
)
from cmm.domains.mental_health.workflows import (
    build_mental_health_workflow_definitions,
)
from cmm.workflows.enums import WorkflowNodeType


def _context(**metadata):
    from datetime import datetime, timezone

    from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext

    return ReasoningRuleContext(
        reasoning_id="rid",
        timestamp=datetime(2026, 8, 1, tzinfo=timezone.utc),
        active_domains=("domain:mental-health",),
        primary_domain="domain:mental-health",
        metadata=metadata,
    )


EXPECTED_OPERATION_TYPES = {
    "mental_health.review_emotional_context": "ANALYSIS",
    "mental_health.prepare_therapy_session": "PREPARATION",
    "mental_health.review_therapy_session": "ANALYSIS",
    "mental_health.analyze_therapy_transcript": "SENSITIVE",
    "mental_health.compare_emotional_periods": "ANALYSIS",
    "mental_health.map_fact_interpretation_uncertainty": "ANALYSIS",
    "mental_health.review_emotional_decision": "ANALYSIS",
    "mental_health.propose_memory_update": "MEMORY",
}


def _operations_by_id():
    return {
        operation.operation_id: operation
        for operation in build_mental_health_operation_definitions()
    }


def test_eight_operations_exist_with_canonical_domain():
    definitions = build_mental_health_operation_definitions()
    assert tuple(d.operation_id for d in definitions) == MENTAL_HEALTH_OPERATION_IDS
    assert len(definitions) == 8
    for operation in definitions:
        assert operation.domain_id == "domain:mental-health"
        assert operation.operation_id in MENTAL_HEALTH_OPERATION_IDS


def test_operation_semantics_are_classified_exactly():
    by_id = _operations_by_id()
    for operation_id, expected_type in EXPECTED_OPERATION_TYPES.items():
        assert by_id[operation_id].operation_type.name == expected_type


def test_no_operation_performs_an_external_or_destructive_effect():
    for operation in build_mental_health_operation_definitions():
        assert operation.operation_type.name not in {"EXTERNAL", "DESTRUCTIVE"}
        assert operation.metadata.get("direct_memory_write") is False


def test_propose_memory_update_is_proposal_only_and_approved():
    proposal = _operations_by_id()["mental_health.propose_memory_update"]
    assert proposal.requires_approval is True
    assert proposal.metadata["proposal_only"] is True
    assert proposal.metadata.get("direct_memory_write") is not True
    # A proposal can never directly persist: output is proposal + binding.
    assert set(proposal.output_schema["required"]) == {"proposal", "binding"}


def test_transcript_analysis_requires_speaker_provenance_inputs():
    transcript = _operations_by_id()["mental_health.analyze_therapy_transcript"]
    assert set(transcript.input_schema["required"]) == {
        "transcript_ref",
        "source_provenance",
        "speaker_turns",
    }
    turn_schema = transcript.input_schema["properties"]["speaker_turns"]["items"]
    assert set(turn_schema["required"]) == {"turn_id", "speaker", "source_ref"}
    assert transcript.required_resources == ("mental_health.therapy_transcript",)


def test_operations_declare_only_structurally_consumed_resources():
    for operation in build_mental_health_operation_definitions():
        for resource_id in operation.required_resources:
            assert resource_id.startswith("mental_health.")


def test_eight_workflows_exist_and_are_ordered():
    workflows = build_mental_health_workflow_definitions()
    assert tuple(w.workflow_id for w in workflows) == MENTAL_HEALTH_WORKFLOW_IDS
    assert len(workflows) == 8
    for workflow in workflows:
        assert workflow.domain_id == "domain:mental-health"
        assert workflow.version == "1.0.0"


def test_workflows_reference_registered_operations_only():
    for workflow in build_mental_health_workflow_definitions():
        for node in workflow.nodes:
            if node.operation_id is not None:
                assert node.operation_id in MENTAL_HEALTH_OPERATION_IDS


def test_workflows_use_existing_node_types_only():
    allowed = {node_type.value for node_type in WorkflowNodeType}
    for workflow in build_mental_health_workflow_definitions():
        for node in workflow.nodes:
            assert node.node_type.value in allowed


def test_workflows_have_strict_load_profile_reason_prefix():
    for workflow in build_mental_health_workflow_definitions():
        by_id = {node.node_id: node for node in workflow.nodes}
        assert by_id["load"].node_type is WorkflowNodeType.LOAD_RESOURCE
        assert by_id["profile"].dependencies == ("load",)
        assert by_id["reason"].dependencies == ("profile",)
        assert by_id["profile"].node_type is WorkflowNodeType.APPLY_PROFILE


def test_complete_never_bypasses_validation():
    for workflow in build_mental_health_workflow_definitions():
        by_id = {node.node_id: node for node in workflow.nodes}
        complete = next(
            node
            for node in workflow.nodes
            if node.node_type is WorkflowNodeType.COMPLETE
        )
        # Walk dependencies backwards; a VALIDATE node must be reachable.
        seen: set[str] = set()
        stack = list(complete.dependencies)
        reachable_validate = False
        while stack:
            node_id = stack.pop()
            if node_id in seen:
                continue
            seen.add(node_id)
            node = by_id[node_id]
            if node.node_type is WorkflowNodeType.VALIDATE:
                reachable_validate = True
            stack.extend(node.dependencies)
        assert reachable_validate, workflow.workflow_id


def test_sensitive_memory_workflow_stops_at_proposal_and_approval():
    workflow = next(
        w
        for w in build_mental_health_workflow_definitions()
        if w.workflow_id == "mental_health.sensitive_memory_proposal_review"
    )
    by_id = {node.node_id: node for node in workflow.nodes}
    assert by_id["approval"].node_type is WorkflowNodeType.REQUEST_APPROVAL
    assert by_id["propose"].node_type is WorkflowNodeType.PROPOSE_MEMORY
    assert by_id["propose"].dependencies == ("approval",)
    assert by_id["complete"].dependencies == ("propose",)
    # No node in this workflow can mutate memory directly.
    assert all(
        node.node_type is not WorkflowNodeType.UPDATE_SESSION for node in workflow.nodes
    )


def test_safety_workflow_is_coordination_only():
    workflow = next(
        w
        for w in build_mental_health_workflow_definitions()
        if w.workflow_id == "mental_health.safety_escalation_review"
    )
    assert workflow.metadata["own_crisis_engine"] is False
    assert workflow.metadata["emotion_triggered_escalation"] is False
    escalate = next(
        node for node in workflow.nodes if node.node_type is WorkflowNodeType.ESCALATE
    )
    # Coordination routes to the existing mechanism; it invents no protocol.
    assert escalate.operation_id is None


def test_no_workflow_defines_its_own_executor_or_runtime():
    for workflow in build_mental_health_workflow_definitions():
        assert not hasattr(workflow, "executor")
        assert "executor" not in workflow.metadata
        assert "runtime" not in workflow.metadata


# ── Therapy provenance (Task 9) ──────────────────────────────────────────────


def test_transcript_workflow_requires_speaker_and_source_provenance():
    workflow = next(
        w
        for w in build_mental_health_workflow_definitions()
        if w.workflow_id == "mental_health.therapy_transcript_review"
    )
    assert workflow.metadata["speaker_provenance_required"] is True
    assert workflow.metadata["source_identity_required"] is True
    operation_ids = {
        node.operation_id for node in workflow.nodes if node.operation_id is not None
    }
    # Speaker-separated evidence and epistemic mapping are both on the path.
    assert "mental_health.analyze_therapy_transcript" in operation_ids
    assert "mental_health.map_fact_interpretation_uncertainty" in operation_ids


def test_transcript_rule_preserves_three_attribution_classes():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rules = {rule.definition.id: rule for rule in build_mental_health_rules()}
    rule = rules["mental_health.therapy_statement_separation"]
    result = rule.evaluate(
        _context(
            transcript_turns=[
                {"id": "t1", "speaker": "therapist"},
                {"id": "t2", "speaker": "user"},
                {"id": "t3", "speaker": "model", "model_interpretation": True},
            ]
        )
    )
    sources = {finding.metadata["statement_source"] for finding in result.findings}
    assert sources == {"therapist", "user", "model"}


def test_fabricated_therapist_statement_is_blocked():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rules = {rule.definition.id: rule for rule in build_mental_health_rules()}
    rule = rules["mental_health.therapy_statement_separation"]
    result = rule.evaluate(
        _context(
            transcript_turns=[
                {"id": "t1", "speaker": "user", "attributed_to_therapist": True},
            ]
        )
    )
    assert result.status.value == "blocked"
    assert result.metadata["fabricated_therapist_statement"] is True


def test_insufficient_provenance_blocks_high_confidence_output():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rules = {rule.definition.id: rule for rule in build_mental_health_rules()}
    rule = rules["mental_health.therapy_speaker_provenance"]
    result = rule.evaluate(
        _context(
            transcript_turns=[
                {"id": "t1", "speaker": "unknown", "clinical_claim": True},
            ]
        )
    )
    assert result.status.value == "blocked"
    assert result.metadata["unattributed_clinical_claims"] == ("t1",)


# ── Audit V1 remediation — MAJOR-02 real therapy source/provenance ──────────
#
# Speaker separation is not source provenance.  The audited rule read only
# speaker-oriented fields yet unconditionally reported
# ``source_identity_preserved=True`` and ``SPEAKER_PROVENANCE_PRESERVED``.
# The remediated rule consumes real canonical ``ResourceProvenance`` evidence
# plus a per-turn source reference, propagates it, and fails closed when the
# evidence is missing or malformed.

TRANSCRIPT_SOURCE_ID = "mental_health.therapy_transcript:session-42"


def _canonical_provenance(source_id: str = TRANSCRIPT_SOURCE_ID):
    """Return the JSON-safe canonical ``ResourceProvenance`` representation."""
    from datetime import datetime, timezone

    from cmm.cognitive.enums import ResourceSourceKind
    from cmm.cognitive.resources import ResourceProvenance

    return ResourceProvenance(
        source_type=ResourceSourceKind.UPLOADED_FILE,
        source_id=source_id,
        author="user",
        retrieved_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    ).to_dict()


def _speaker_provenance_rule():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rules = {rule.definition.id: rule for rule in build_mental_health_rules()}
    return rules["mental_health.therapy_speaker_provenance"]


def test_speaker_without_source_provenance_does_not_report_source_identity_preserved():
    """The V1 false positive: a speaker-only turn must not claim provenance."""
    result = _speaker_provenance_rule().evaluate(
        _context(transcript_turns=[{"id": "t1", "speaker": "therapist"}])
    )
    assert result.status.value == "blocked"
    assert result.trace_entries[0].code != "SPEAKER_PROVENANCE_PRESERVED"
    assert result.metadata["provenance_preserved"] is False
    assert result.metadata["unprovenanced_turns"] == ("t1",)
    attributions = [
        finding for finding in result.findings if finding.code == "SPEAKER_ATTRIBUTION"
    ]
    assert attributions
    assert all(
        finding.metadata["source_identity_preserved"] is False
        for finding in attributions
    )


def test_canonical_source_provenance_is_preserved_and_interpretation_distinct():
    result = _speaker_provenance_rule().evaluate(
        _context(
            source_provenance=_canonical_provenance(),
            transcript_turns=[
                {"id": "t1", "speaker": "therapist", "source_ref": "turn:1"},
                {"id": "t2", "speaker": "user", "source_ref": "turn:2"},
                {
                    "id": "t3",
                    "speaker": "model",
                    "model_interpretation": True,
                    "source_ref": "turn:3",
                },
            ],
        )
    )
    assert result.status.value == "applied"
    assert result.trace_entries[0].code == "SPEAKER_PROVENANCE_PRESERVED"
    assert result.metadata["provenance_preserved"] is True
    assert result.metadata["source_provenance_id"] == TRANSCRIPT_SOURCE_ID

    by_speaker = {finding.metadata["speaker"]: finding for finding in result.findings}
    assert set(by_speaker) == {"therapist", "user", "model"}
    assert all(
        finding.metadata["source_identity_preserved"] is True
        for finding in result.findings
    )
    # The real source reference survives into the finding, not just the speaker.
    assert "turn:1" in by_speaker["therapist"].references
    assert by_speaker["therapist"].metadata["source_ref"] == "turn:1"
    # Model interpretation stays distinguishable from source statements.
    assert by_speaker["model"].metadata["model_interpretation_distinct"] is True
    assert by_speaker["therapist"].metadata["model_interpretation_distinct"] is False


def test_provenance_mapping_is_validated_through_the_canonical_contract():
    result = _speaker_provenance_rule().evaluate(
        _context(
            source_provenance={
                "source_type": "uploaded_file",
                "source_id": TRANSCRIPT_SOURCE_ID,
                "author": "user",
            },
            transcript_turns=[
                {"id": "t1", "speaker": "therapist", "source_ref": "turn:1"}
            ],
        )
    )
    assert result.status.value == "applied"
    assert result.metadata["provenance_preserved"] is True
    assert result.metadata["source_provenance_id"] == TRANSCRIPT_SOURCE_ID


def test_insufficient_source_provenance_creates_no_documented_clinical_fact():
    """Insufficient provenance must not become a high-confidence clinical fact."""
    result = _speaker_provenance_rule().evaluate(
        _context(
            source_provenance=_canonical_provenance(),
            transcript_turns=[
                {"id": "t1", "speaker": "therapist", "clinical_claim": True},
            ],
        )
    )
    assert result.status.value == "blocked"
    assert result.trace_entries[0].code == "SPEAKER_PROVENANCE_INSUFFICIENT"
    assert result.metadata["provenance_preserved"] is False
    assert result.metadata["unprovenanced_turns"] == ("t1",)
    assert not any(
        finding.metadata.get("source_identity_preserved") is True
        for finding in result.findings
    )


def test_absent_transcript_source_provenance_fails_closed():
    result = _speaker_provenance_rule().evaluate(
        _context(
            transcript_turns=[
                {"id": "t1", "speaker": "therapist", "source_ref": "turn:1"}
            ]
        )
    )
    assert result.status.value == "blocked"
    assert result.metadata["provenance_preserved"] is False


@pytest.mark.parametrize(
    "malformed_provenance",
    (
        {"source_id": "only-an-id"},  # incomplete: no canonical source_type
        {"source_type": "not-a-real-kind", "source_id": "x"},
        {"source_type": "uploaded_file", "source_id": "   "},  # blank source id
        "a-string-is-not-provenance",
        ("not", "provenance"),
        None,
    ),
)
def test_malformed_source_provenance_fails_closed(malformed_provenance):
    result = _speaker_provenance_rule().evaluate(
        _context(
            source_provenance=malformed_provenance,
            transcript_turns=[
                {"id": "t1", "speaker": "therapist", "source_ref": "turn:1"}
            ],
        )
    )
    assert result.status.value == "blocked"
    assert result.metadata["provenance_preserved"] is False
    assert result.trace_entries[0].code != "SPEAKER_PROVENANCE_PRESERVED"


@pytest.mark.parametrize("malformed_ref", ("", "   ", None, 1, 0, {}, []))
def test_malformed_turn_source_ref_never_counts_as_provenance(malformed_ref):
    result = _speaker_provenance_rule().evaluate(
        _context(
            source_provenance=_canonical_provenance(),
            transcript_turns=[
                {"id": "t1", "speaker": "therapist", "source_ref": malformed_ref}
            ],
        )
    )
    assert result.status.value == "blocked"
    assert result.metadata["provenance_preserved"] is False
    assert result.metadata["unprovenanced_turns"] == ("t1",)


def test_unknown_speaker_clinical_claim_is_still_reported_alongside_provenance():
    result = _speaker_provenance_rule().evaluate(
        _context(
            source_provenance=_canonical_provenance(),
            transcript_turns=[
                {
                    "id": "t1",
                    "speaker": "unknown",
                    "source_ref": "turn:1",
                    "clinical_claim": True,
                }
            ],
        )
    )
    assert result.status.value == "blocked"
    assert result.metadata["unattributed_clinical_claims"] == ("t1",)
    # The turn is speaker-attributed but not clinically attributable.
    assert result.metadata["provenance_preserved"] is True
    assert result.metadata["high_confidence_output_blocked"] is True


def test_transcript_operation_schema_declares_the_canonical_source_reference():
    from cmm.domains.mental_health.operations import (
        build_mental_health_operation_definitions,
    )

    operation = next(
        item
        for item in build_mental_health_operation_definitions()
        if item.operation_id == "mental_health.analyze_therapy_transcript"
    )
    schema = operation.input_schema
    assert "source_provenance" in schema["required"]
    turn_schema = schema["properties"]["speaker_turns"]["items"]
    assert "source_ref" in turn_schema["required"]
    assert turn_schema["properties"]["source_ref"]["type"] == "string"


# ── Audit V1 remediation — MAJOR-03 canonical cross-domain transfer ─────────
#
# The audited rule consumed an untyped mapping and unconditionally reported
# ``provenance_preserved=True`` with ``CROSS_DOMAIN_MINIMIZED`` — even with no
# source domain and no provenance.  The remediated rule consumes real canonical
# ``CrossDomainContextTransfer`` evidence (which itself enforces non-empty
# provenance and strict transfer flags) and fails closed without it.

PURPOSE = "emotional_context"


def _transfer(
    *,
    source_domain="domain:health",
    target_domain="domain:mental-health",
    identifier="documented_medication_change",
    value=True,
    reason=PURPOSE,
    provenance=("finding:health:1",),
    private=False,
    transferable=True,
    metadata=None,
):
    """Return the JSON-safe canonical ``CrossDomainContextTransfer`` mapping."""
    from cmm.domains.cross_domain_contracts import CrossDomainContextTransfer

    return CrossDomainContextTransfer(
        source_domain=source_domain,
        target_domain=target_domain,
        kind="finding",
        identifier=identifier,
        value=value,
        reason=reason,
        provenance=tuple(provenance),
        private=private,
        transferable=transferable,
        metadata=metadata or {},
    ).to_dict()


def _cross_domain_rule():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rules = {rule.definition.id: rule for rule in build_mental_health_rules()}
    return rules["mental_health.purpose_minimized_cross_domain"]


def _projection(**fields):
    return {
        "purpose": PURPOSE,
        "fields": {name: {"relevant": value} for name, value in fields.items()},
    }


def test_cross_domain_minimization_requires_canonical_transfer_evidence():
    """The exact V1 reproduction: no source domain, no provenance, still claimed."""
    result = _cross_domain_rule().evaluate(
        _context(
            projection={
                "purpose": PURPOSE,
                "source_domain": "unknown",
                "fields": {
                    "should_be_excluded": {"relevant": "false"},
                    "real": {"relevant": True},
                },
            }
        )
    )
    assert result.status.value == "blocked"
    assert result.trace_entries[0].code != "CROSS_DOMAIN_MINIMIZED"
    assert result.metadata["provenance_preserved"] is False
    assert result.metadata["included_fields"] == ()


def test_valid_canonical_transfer_preserves_provenance_and_minimizes_fields():
    result = _cross_domain_rule().evaluate(
        _context(
            projection=_projection(
                documented_medication_change=True,
                appointment_phone=False,
                clinician_personal_notes="false",
            ),
            transfers=(
                _transfer(identifier="documented_medication_change"),
                _transfer(identifier="appointment_phone"),
                _transfer(identifier="clinician_personal_notes"),
            ),
        )
    )
    assert result.status.value == "applied"
    assert result.trace_entries[0].code == "CROSS_DOMAIN_MINIMIZED"
    assert result.metadata["included_fields"] == ("documented_medication_change",)
    assert set(result.metadata["excluded_fields"]) == {
        "appointment_phone",
        "clinician_personal_notes",
    }
    assert result.metadata["provenance_preserved"] is True
    assert result.metadata["provenance_references"] == ("finding:health:1",)
    assert result.metadata["source_domains"] == ("domain:health",)
    assert result.metadata["purpose"] == PURPOSE


def test_unknown_source_domain_is_not_a_canonical_transfer():
    from cmm.domains.cross_domain_contracts import CrossDomainContextTransfer
    from cmm.domains.errors import CrossDomainContractError

    # Layer 1: a bare, un-prefixed source domain is rejected by the canonical
    # contract itself, before any Mental Health logic runs.
    with pytest.raises(CrossDomainContractError):
        CrossDomainContextTransfer(
            source_domain="unknown",
            target_domain="domain:mental-health",
            kind="finding",
            identifier="documented_medication_change",
            value=True,
            reason=PURPOSE,
            provenance=("finding:health:1",),
        )

    # Layer 2: a structurally valid but unknown source slug fails closed.
    result = _cross_domain_rule().evaluate(
        _context(
            projection=_projection(documented_medication_change=True),
            transfers=(_transfer(source_domain="domain:unknown"),),
        )
    )
    assert result.status.value == "blocked"
    assert result.metadata["provenance_preserved"] is False
    assert result.metadata["included_fields"] == ()
    assert result.metadata["rejected_transfers"] == ("source_domain_unknown",)


def test_transfer_without_provenance_is_rejected():
    without_provenance = _transfer()
    without_provenance["provenance"] = []
    result = _cross_domain_rule().evaluate(
        _context(
            projection=_projection(documented_medication_change=True),
            transfers=(without_provenance,),
        )
    )
    assert result.status.value == "blocked"
    assert result.metadata["provenance_preserved"] is False


def test_explicit_permission_denial_blocks_the_transfer():
    result = _cross_domain_rule().evaluate(
        _context(
            projection=_projection(documented_medication_change=True),
            transfers=(_transfer(transferable=False),),
        )
    )
    assert result.status.value == "blocked"
    assert result.metadata["provenance_preserved"] is False


def test_private_context_is_not_transferable():
    result = _cross_domain_rule().evaluate(
        _context(
            projection=_projection(documented_medication_change=True),
            transfers=(_transfer(private=True),),
        )
    )
    assert result.status.value == "blocked"
    assert result.metadata["provenance_preserved"] is False


def test_transfer_purpose_must_match_the_current_operation():
    result = _cross_domain_rule().evaluate(
        _context(
            projection=_projection(documented_medication_change=True),
            transfers=(_transfer(reason="an_unrelated_purpose"),),
        )
    )
    assert result.status.value == "blocked"
    assert result.metadata["provenance_preserved"] is False


def test_transfer_target_must_be_mental_health():
    result = _cross_domain_rule().evaluate(
        _context(
            projection=_projection(documented_medication_change=True),
            transfers=(
                _transfer(
                    source_domain="domain:health", target_domain="domain:project"
                ),
            ),
        )
    )
    assert result.status.value == "blocked"
    assert result.metadata["provenance_preserved"] is False


@pytest.mark.parametrize(
    "malformed_transfer",
    (
        None,
        1,
        "not-a-transfer",
        (),
        {},
        {"source_domain": "domain:health"},
        {"source_domain": "domain:health", "target_domain": "domain:mental-health"},
    ),
)
def test_malformed_transfer_representation_is_rejected(malformed_transfer):
    result = _cross_domain_rule().evaluate(
        _context(
            projection=_projection(documented_medication_change=True),
            transfers=(malformed_transfer,),
        )
    )
    assert result.status.value == "blocked"
    assert result.metadata["provenance_preserved"] is False


@pytest.mark.parametrize("malformed_relevance", ("false", "0", 1, 0, {}, []))
def test_malformed_relevance_never_survives_minimization(malformed_relevance):
    result = _cross_domain_rule().evaluate(
        _context(
            projection={
                "purpose": PURPOSE,
                "fields": {"sensitive_field": {"relevant": malformed_relevance}},
            },
            transfers=(_transfer(identifier="sensitive_field"),),
        )
    )
    assert result.metadata["included_fields"] == ()
    assert "sensitive_field" in result.metadata["excluded_fields"]


def test_missing_purpose_fails_closed():
    result = _cross_domain_rule().evaluate(
        _context(
            projection={"fields": {"documented_medication_change": {"relevant": True}}},
            transfers=(_transfer(),),
        )
    )
    assert result.status.value in {"blocked", "not_applicable"}
    assert result.metadata.get("provenance_preserved") is not True


def test_a_single_valid_transfer_among_rejected_ones_still_minimizes():
    result = _cross_domain_rule().evaluate(
        _context(
            projection=_projection(documented_medication_change=True),
            transfers=(
                _transfer(transferable=False),
                _transfer(identifier="documented_medication_change"),
            ),
        )
    )
    assert result.status.value == "applied"
    assert result.metadata["provenance_preserved"] is True
    assert result.metadata["included_fields"] == ("documented_medication_change",)
