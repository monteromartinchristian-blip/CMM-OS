"""Tests for Phase 10.26 Languages Domain Trace Integration."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.enums import DomainRuleSelectionStatus, DomainRuleSource
from cmm.domains.languages.definition import LANGUAGES_DOMAIN_ID
from cmm.domains.languages.profile import (
    LANGUAGES_PEDAGOGICAL_MODES,
    LANGUAGES_PROFILE_NAME,
)
from cmm.domains.languages.rules import build_languages_rules
from cmm.domains.languages.trace import (
    assemble_languages_trace,
    build_languages_trace_contribution,
    build_languages_trace_reference,
    build_supporting_trace_contribution,
    validate_languages_trace,
)
from cmm.domains.rule_contracts import (
    DomainRuleExecutionPlan,
    DomainRuleSourceRecord,
    SelectedReasoningRule,
)
from cmm.domains.rule_execution import DefaultDomainRuleExecutor
from cmm.domains.trace_contracts import (
    DomainTrace,
    DomainTraceContribution,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceRole,
)


def test_build_languages_trace_reference() -> None:
    """Verify trace reference builder for Languages."""
    ref = build_languages_trace_reference(
        ref_id="ref-1",
        kind=DomainTraceReferenceKind.RESOURCE_RESOLUTION,
    )
    assert isinstance(ref, DomainTraceReference)
    assert ref.ref_id == "ref-1"
    assert ref.domain_id == LANGUAGES_DOMAIN_ID
    assert ref.kind is DomainTraceReferenceKind.RESOURCE_RESOLUTION


def test_build_languages_trace_contribution() -> None:
    """Verify primary trace contribution builder."""
    ref = build_languages_trace_reference(
        ref_id="res-1",
        kind=DomainTraceReferenceKind.RESOURCE_RESOLUTION,
    )
    contrib = build_languages_trace_contribution(
        domain_result_id="res-out-1",
        references=(ref,),
    )
    assert isinstance(contrib, DomainTraceContribution)
    assert contrib.role is DomainTraceRole.PRIMARY
    assert contrib.domain_id == LANGUAGES_DOMAIN_ID
    assert len(contrib.references) == 2


def test_assemble_languages_trace_and_validation() -> None:
    """Verify trace assembly with primary and supporting contributions and inventory validation."""
    now = datetime.now(timezone.utc)
    supporting_contrib = build_supporting_trace_contribution(
        domain_result_id="supp-res-1",
        domain_id="domain:university",
    )
    primary_ref = build_languages_trace_reference(
        ref_id="lang-res-1",
        kind=DomainTraceReferenceKind.RESOURCE_RESOLUTION,
    )
    trace = assemble_languages_trace(
        request_id="req-tr-1",
        resolution_context_id="ctx-1",
        resolution_result_id="res-ctx-1",
        composition_id="comp-1",
        domain_result_id="lang-res-out-1",
        started_at=now,
        completed_at=now,
        references=(primary_ref,),
        supporting_domains=("domain:university",),
        contributions=(supporting_contrib,),
    )
    assert isinstance(trace, DomainTrace)
    assert trace.primary_domain == LANGUAGES_DOMAIN_ID
    assert trace.supporting_domains == ("domain:university",)

    # Validate against inventory
    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        domain_results=trace.domain_results,
        cross_domain_results=trace.references.cross_domain_results,
        expected_primary_domain=LANGUAGES_DOMAIN_ID,
        expected_supporting_domains=("domain:university",),
        resolution_result_domains=DomainTraceDomainSelection(
            "res-ctx-1",
            LANGUAGES_DOMAIN_ID,
            ("domain:university",),
        ),
        composition_domains=DomainTraceDomainSelection(
            "comp-1",
            LANGUAGES_DOMAIN_ID,
            ("domain:university",),
        ),
    )
    val_res = validate_languages_trace(trace=trace, inventory=inventory)
    assert val_res.valid is True

    # Bad inventory should fail validation
    ghost = build_languages_trace_reference(
        ref_id="ghost", kind=DomainTraceReferenceKind.FINDING
    )
    bad = replace(inventory, references=(*inventory.references, ghost))
    bad_res = validate_languages_trace(trace=trace, inventory=bad)
    assert bad_res.valid is False


def test_assemble_languages_trace_carries_global_presentation_results() -> None:
    now = datetime.now(timezone.utc)

    trace = assemble_languages_trace(
        request_id="req-presentation-1",
        resolution_context_id="ctx-presentation-1",
        resolution_result_id="res-presentation-1",
        composition_id="comp-presentation-1",
        domain_result_id="domain-result-presentation-1",
        started_at=now,
        completed_at=now,
        presentation_result_ids=("presentation-result-1",),
    )

    assert (
        DomainTraceReference(
            "presentation-result-1",
            DomainTraceReferenceKind.PRESENTATION_RESULT,
        )
        in trace.all_references()
    )


def test_assemble_languages_trace_preserves_caller_metadata() -> None:
    """Caller runtime state remains part of the canonical trace payload."""
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    metadata = {"selected_profile_mode": "practice"}

    trace = assemble_languages_trace(
        request_id="request-profile-mode",
        resolution_context_id="context-profile-mode",
        resolution_result_id="resolution-profile-mode",
        composition_id="composition-profile-mode",
        domain_result_id="domain-result-profile-mode",
        started_at=now,
        completed_at=now,
        metadata=metadata,
    )

    assert trace.metadata["selected_profile_mode"] == "practice"
    assert trace.metadata["selected_profile_mode"] in LANGUAGES_PEDAGOGICAL_MODES
    assert trace.id == trace.canonical_id
    assert trace.digest == trace.calculate_digest()


def test_validation_rejects_definition_id_tampered_as_runtime_rule_result() -> None:
    """Catches a rule definition identity substituted for execution provenance."""
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    rule = next(
        rule
        for rule in build_languages_rules()
        if rule.definition.id == "languages.error_pattern_evidence"
    )
    registry = InMemoryReasoningRuleRegistry()
    registry.register(rule)
    rule_plan = DomainRuleExecutionPlan(
        id="languages-rule-plan-runtime",
        status=DomainRuleSelectionStatus.READY,
        created_at=now,
        selected_rules=(
            SelectedReasoningRule(
                definition=rule.definition,
                sources=(
                    DomainRuleSourceRecord(
                        source=DomainRuleSource.PROFILE,
                        reference=rule.definition.id,
                        required=True,
                        domain_id=LANGUAGES_DOMAIN_ID,
                        profile_name=LANGUAGES_PROFILE_NAME,
                    ),
                ),
                group=DomainRuleSource.PRIMARY_DOMAIN,
                required=True,
            ),
        ),
        contributing_profiles=(LANGUAGES_PROFILE_NAME,),
        contributing_domains=(LANGUAGES_DOMAIN_ID,),
    )
    rule_execution = DefaultDomainRuleExecutor(
        clock=lambda: now,
        id_factory=lambda: "languages-rule-execution-runtime",
    ).execute(
        plan=rule_plan,
        context=ReasoningRuleContext(
            reasoning_id="languages-rule-reasoning-runtime",
            timestamp=now,
            active_domains=(LANGUAGES_DOMAIN_ID,),
            primary_domain=LANGUAGES_DOMAIN_ID,
            metadata={"material": {"observations": ()}},
        ),
        registry=registry,
    )
    runtime_references = (
        build_languages_trace_reference(
            ref_id=rule_plan.id,
            kind=DomainTraceReferenceKind.RULE_PLAN,
        ),
        build_languages_trace_reference(
            ref_id=rule_execution.id,
            kind=DomainTraceReferenceKind.RULE_RESULT,
        ),
    )
    trace = assemble_languages_trace(
        request_id="request-rule-runtime",
        resolution_context_id="context-rule-runtime",
        resolution_result_id="resolution-rule-runtime",
        composition_id="composition-rule-runtime",
        domain_result_id="domain-result-rule-runtime",
        started_at=now,
        completed_at=now,
        references=runtime_references,
    )
    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        domain_results=trace.domain_results,
        cross_domain_results=trace.references.cross_domain_results,
        expected_primary_domain=LANGUAGES_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            "resolution-rule-runtime", LANGUAGES_DOMAIN_ID
        ),
        composition_domains=DomainTraceDomainSelection(
            "composition-rule-runtime", LANGUAGES_DOMAIN_ID
        ),
    )
    assert validate_languages_trace(trace=trace, inventory=inventory).valid is True

    contribution = trace.contributions[0]
    tampered = replace(
        trace,
        contributions=(
            replace(
                contribution,
                references=tuple(
                    replace(reference, ref_id=rule.definition.id)
                    if reference.ref_id == rule_execution.id
                    else reference
                    for reference in contribution.references
                ),
            ),
        ),
    )

    validation = validate_languages_trace(trace=tampered, inventory=inventory)
    assert validation.valid is False
    assert rule_execution.id in validation.missing_references
    assert rule.definition.id in validation.unexpected_references
