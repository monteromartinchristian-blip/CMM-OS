"""Regression coverage for the Phase 10.17 audit findings."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains import DomainResultTraceReference
from cmm.domains.trace_assembler import DomainTraceAssembler
from cmm.domains.trace_contracts import (
    CrossDomainTraceReference,
    DomainTrace,
    DomainTraceAssemblyRequest,
    DomainTraceContractError,
    DomainTraceContribution,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceRole,
    DomainTraceSerializationError,
    DomainTraceStatus,
    DomainTraceValidationCode,
    DomainTraceValidationResult,
)
from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator


def _request(status: DomainTraceStatus = DomainTraceStatus.COMPLETED):
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    return DomainTraceAssemblyRequest(
        request_id="request:1",
        primary_domain="domain:life-plan",
        supporting_domains=("domain:health",),
        contributions=(
            DomainTraceContribution(
                "domain:life-plan", DomainTraceRole.PRIMARY,
                (
                    DomainTraceReference("domain-result:life", DomainTraceReferenceKind.DOMAIN_RESULT, "domain:life-plan"),
                    DomainTraceReference("operation:1", DomainTraceReferenceKind.OPERATION_RESULT, "domain:life-plan"),
                    DomainTraceReference("workflow:1", DomainTraceReferenceKind.WORKFLOW_RESULT, "domain:life-plan"),
                    DomainTraceReference("permission:1", DomainTraceReferenceKind.PERMISSION_DECISION, "domain:life-plan"),
                    DomainTraceReference("approval-request:1", DomainTraceReferenceKind.APPROVAL_REQUEST, "domain:life-plan"),
                    DomainTraceReference("approval-decision:1", DomainTraceReferenceKind.APPROVAL_DECISION, "domain:life-plan"),
                ),
            ),
            DomainTraceContribution("domain:health", DomainTraceRole.SUPPORTING),
        ),
        references=DomainTraceReferences(
            "resolution-context:1", "resolution-result:1", "composition:1",
            cross_domain_results=(CrossDomainTraceReference("cross-domain-result:1", "cross-trace:upstream"),),
        ),
        domain_results=(DomainResultTraceReference("domain-result:life", "domain:life-plan"),),
        started_at=now,
        completed_at=now.replace(second=1),
        status=status,
    )


def _trace_and_inventory(status: DomainTraceStatus = DomainTraceStatus.COMPLETED):
    trace = DomainTraceAssembler().assemble(_request(status))
    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        domain_results=trace.domain_results,
        cross_domain_results=trace.references.cross_domain_results,
        expected_primary_domain="domain:life-plan",
        expected_supporting_domains=("domain:health",),
        resolution_result_domains=DomainTraceDomainSelection("resolution-result:1", "domain:life-plan", ("domain:health",)),
        composition_domains=DomainTraceDomainSelection("composition:1", "domain:life-plan", ("domain:health",)),
    )
    return trace, inventory


def test_validator_rejects_a_self_consistent_trace_with_false_upstream_primary() -> None:
    trace, inventory = _trace_and_inventory()
    object.__setattr__(trace, "primary_domain", trace.supporting_domains[0])
    object.__setattr__(trace, "supporting_domains", ("domain:life-plan",))

    result = DefaultDomainTraceReferenceValidator().validate(trace, inventory)

    assert DomainTraceValidationCode.AUTHORITATIVE_DOMAIN_MISMATCH in result.codes


@pytest.mark.parametrize(
    "references",
    (
        (
            DomainTraceReference("shared:1", DomainTraceReferenceKind.FINDING, "domain:health"),
            DomainTraceReference("shared:1", DomainTraceReferenceKind.WARNING, "domain:health"),
        ),
        (
            DomainTraceReference("shared:1", DomainTraceReferenceKind.FINDING, "domain:health"),
            DomainTraceReference("shared:1", DomainTraceReferenceKind.FINDING, "domain:life-plan"),
        ),
        (
            DomainTraceReference("shared:1", DomainTraceReferenceKind.COGNITIVE_RESULT),
            DomainTraceReference("shared:1", DomainTraceReferenceKind.FINDING, "domain:life-plan"),
        ),
    ),
)
def test_inventory_rejects_one_reference_id_in_two_categories_or_domains(references) -> None:
    with pytest.raises(DomainTraceContractError):
        DomainTraceReferenceInventory(
            references=references,
            expected_primary_domain="domain:life-plan",
            resolution_result_domains=DomainTraceDomainSelection("resolution-result:1", "domain:life-plan"),
            composition_domains=DomainTraceDomainSelection("composition:1", "domain:life-plan"),
        )


def test_validator_requires_exact_domain_result_coverage() -> None:
    trace, inventory = _trace_and_inventory()
    object.__setattr__(trace, "domain_results", ())

    result = DefaultDomainTraceReferenceValidator().validate(trace, inventory)

    assert DomainTraceValidationCode.DOMAIN_RESULT_COVERAGE_MISMATCH in result.codes


def test_validator_rejects_a_duplicate_domain_result_reference() -> None:
    trace, inventory = _trace_and_inventory()
    contribution = trace.contributions[0]
    result_reference = next(
        item for item in contribution.references
        if item.kind is DomainTraceReferenceKind.DOMAIN_RESULT
    )
    object.__setattr__(contribution, "references", contribution.references + (result_reference,))

    result = DefaultDomainTraceReferenceValidator().validate(trace, inventory)

    assert DomainTraceValidationCode.DOMAIN_RESULT_COVERAGE_MISMATCH in result.codes


def test_assembler_preserves_the_existing_cross_domain_trace_id() -> None:
    trace = DomainTraceAssembler().assemble(_request())

    assert trace.references.cross_domain_results[0].trace_id == "cross-trace:upstream"
    assert trace.references.cross_domain_results[0].trace_id != trace.id


@pytest.mark.parametrize("status", tuple(DomainTraceStatus))
def test_new_final_statuses_round_trip_and_validate(status: DomainTraceStatus) -> None:
    trace, inventory = _trace_and_inventory(status)

    assert trace.from_dict(trace.to_dict()).status is status
    assert DefaultDomainTraceReferenceValidator().validate(trace, inventory).valid


def test_validator_fails_closed_when_role_or_kind_are_mutated() -> None:
    trace, inventory = _trace_and_inventory()
    object.__setattr__(trace.contributions[0], "role", "primary")
    object.__setattr__(trace.contributions[0].references[0], "kind", "invalid")

    result = DefaultDomainTraceReferenceValidator().validate(trace, inventory)

    assert result.valid is False
    assert DomainTraceValidationCode.INVALID_TRACE_CONTRACT in result.codes


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        ("contributions", [], DomainTraceValidationCode.INVALID_TRACE_CONTRACT),
        ("status", "running", DomainTraceValidationCode.UNKNOWN_STATUS),
        ("id", "bad id", DomainTraceValidationCode.INVALID_TRACE_ID),
        ("digest", "bad", DomainTraceValidationCode.INVALID_TRACE_DIGEST),
    ),
)
def test_validator_fails_closed_for_corrupt_top_level_fields(field, value, code) -> None:
    trace, inventory = _trace_and_inventory()
    object.__setattr__(trace, field, value)

    result = DefaultDomainTraceReferenceValidator().validate(trace, inventory)

    assert result.valid is False
    assert code in result.codes


def test_inventory_and_validation_result_round_trip_with_digests() -> None:
    trace, inventory = _trace_and_inventory()
    result = DefaultDomainTraceReferenceValidator().validate(trace, inventory)

    assert inventory.from_dict(inventory.to_dict()) == inventory
    assert inventory.digest == inventory.from_dict(inventory.to_dict()).digest
    assert DomainTraceValidationResult.from_dict(result.to_dict()) == result
    assert result.inventory_digest == inventory.digest


def test_reconstruction_references_resolve_by_their_category_and_domain() -> None:
    trace, inventory = _trace_and_inventory()
    expected = {
        ("operation:1", DomainTraceReferenceKind.OPERATION_RESULT, "domain:life-plan"),
        ("workflow:1", DomainTraceReferenceKind.WORKFLOW_RESULT, "domain:life-plan"),
        ("permission:1", DomainTraceReferenceKind.PERMISSION_DECISION, "domain:life-plan"),
        ("approval-request:1", DomainTraceReferenceKind.APPROVAL_REQUEST, "domain:life-plan"),
        ("approval-decision:1", DomainTraceReferenceKind.APPROVAL_DECISION, "domain:life-plan"),
    }

    actual = {(item.ref_id, item.kind, str(item.domain_id)) for item in inventory.references}

    assert expected <= actual
    assert trace.all_references() == inventory.references


def test_full_reference_inventory_reconstructs_every_execution_category_by_id() -> None:
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    domain_kinds = (
        DomainTraceReferenceKind.RESOURCE_RESOLUTION, DomainTraceReferenceKind.PROFILE,
        DomainTraceReferenceKind.PROFILE_TRACE, DomainTraceReferenceKind.RULE_PLAN,
        DomainTraceReferenceKind.RULE_RESULT, DomainTraceReferenceKind.APPLIED_RULE_TRACE,
        DomainTraceReferenceKind.OPERATION_RESULT, DomainTraceReferenceKind.WORKFLOW_RUN,
        DomainTraceReferenceKind.WORKFLOW_RESULT, DomainTraceReferenceKind.PERMISSION_DECISION,
        DomainTraceReferenceKind.APPROVAL_REQUEST, DomainTraceReferenceKind.APPROVAL_DECISION,
        DomainTraceReferenceKind.FINDING, DomainTraceReferenceKind.GAP,
        DomainTraceReferenceKind.CONTRADICTION, DomainTraceReferenceKind.WARNING,
        DomainTraceReferenceKind.DOMAIN_RESULT,
    )
    contribution = DomainTraceContribution(
        "domain:life-plan", DomainTraceRole.PRIMARY,
        tuple(DomainTraceReference(f"reference:{kind.value}", kind, "domain:life-plan") for kind in domain_kinds),
    )
    request = DomainTraceAssemblyRequest(
        request_id="request:reconstruction", primary_domain="domain:life-plan", contributions=(contribution,),
        references=DomainTraceReferences(
            "resolution-context:all", "resolution-result:all", "composition:all", agent_trace_id="agent-trace:1",
            cognitive_result_ids=("cognitive-result:1",), reasoning_trace_ids=("reasoning-trace:1",),
            knowledge_package_ids=("knowledge-package:1",), presentation_plan_ids=("presentation-plan:1",),
            presentation_validation_result_ids=("presentation-validation:1",),
        ),
        domain_results=(DomainResultTraceReference("reference:domain_result", "domain:life-plan"),),
        started_at=now, completed_at=now,
    )
    trace = DomainTraceAssembler().assemble(request)
    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(), domain_results=trace.domain_results,
        expected_primary_domain="domain:life-plan",
        resolution_result_domains=DomainTraceDomainSelection("resolution-result:all", "domain:life-plan"),
        composition_domains=DomainTraceDomainSelection("composition:all", "domain:life-plan"),
    )

    assert DefaultDomainTraceReferenceValidator().validate(trace, inventory).valid
    assert {item.kind for item in inventory.references} == set(domain_kinds) | {
        DomainTraceReferenceKind.RESOLUTION_CONTEXT, DomainTraceReferenceKind.RESOLUTION_RESULT,
        DomainTraceReferenceKind.COMPOSITION, DomainTraceReferenceKind.AGENT_TRACE,
        DomainTraceReferenceKind.COGNITIVE_RESULT, DomainTraceReferenceKind.REASONING_TRACE,
        DomainTraceReferenceKind.KNOWLEDGE_PACKAGE, DomainTraceReferenceKind.PRESENTATION_PLAN,
        DomainTraceReferenceKind.PRESENTATION_VALIDATION_RESULT,
    }


def test_domain_result_order_does_not_change_trace_identity() -> None:
    request = _request()
    first = DomainResultTraceReference("domain-result:a", "domain:life-plan")
    second = DomainResultTraceReference("domain-result:b", "domain:health")
    contribution = request.contributions[0]
    supporting = request.contributions[1]
    object.__setattr__(
        contribution,
        "references",
        contribution.references
        + (DomainTraceReference(first.result_id, DomainTraceReferenceKind.DOMAIN_RESULT, first.domain_id),),
    )
    object.__setattr__(
        supporting,
        "references",
        (DomainTraceReference(second.result_id, DomainTraceReferenceKind.DOMAIN_RESULT, second.domain_id),),
    )
    payload = request.to_dict()
    # Include the original domain-result:life plus the two new ones
    original_result = DomainResultTraceReference("domain-result:life", "domain:life-plan")
    payload["domain_results"] = [original_result.to_dict(), first.to_dict(), second.to_dict()]
    request = DomainTraceAssemblyRequest.from_dict(payload)
    payload["domain_results"].reverse()
    reversed_request = DomainTraceAssemblyRequest.from_dict(payload)

    first_trace = DomainTraceAssembler().assemble(request)
    second_trace = DomainTraceAssembler().assemble(reversed_request)

    assert request.domain_results == reversed_request.domain_results
    assert first_trace.id == second_trace.id
    assert first_trace.digest == second_trace.digest
    assert first_trace.domain_results == second_trace.domain_results


@pytest.mark.parametrize(
    ("ref_id", "domain_id", "kind"),
    (
        ("bad id", "domain:life-plan", "invalid"),
        (object(), "bad domain", "invalid"),
        (None, object(), "invalid"),
    ),
)
def test_validator_sanitizes_corrupt_reference_diagnostics(ref_id, domain_id, kind) -> None:
    trace, inventory = _trace_and_inventory()
    reference = trace.contributions[0].references[0]
    object.__setattr__(reference, "ref_id", ref_id)
    object.__setattr__(reference, "domain_id", domain_id)
    object.__setattr__(reference, "kind", kind)

    result = DefaultDomainTraceReferenceValidator().validate(trace, inventory)

    assert result.valid is False
    assert DomainTraceValidationCode.INVALID_TRACE_CONTRACT in result.codes
    assert all(" " not in item for item in result.reference_kind_mismatches)
    assert all("object at" not in item for item in result.reference_kind_mismatches)


def test_cross_domain_trace_id_is_a_typed_resolvable_reference() -> None:
    trace, inventory = _trace_and_inventory()

    typed = {
        (item.ref_id, item.kind)
        for item in inventory.references
    }

    assert ("cross-trace:upstream", DomainTraceReferenceKind.CROSS_DOMAIN_TRACE) in typed
    assert DefaultDomainTraceReferenceValidator().validate(trace, inventory).valid


def test_assembler_accepts_the_serialized_request_mapping() -> None:
    request = _request()

    from_contract = DomainTraceAssembler().assemble(request)
    from_mapping = DomainTraceAssembler().assemble(request.to_dict())

    assert from_mapping == from_contract


def test_authoritative_domain_selections_are_bound_to_their_source_ids() -> None:
    trace = DomainTraceAssembler().assemble(_request())
    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        domain_results=trace.domain_results,
        cross_domain_results=trace.references.cross_domain_results,
        expected_primary_domain="domain:life-plan",
        expected_supporting_domains=("domain:health",),
        resolution_result_domains=DomainTraceDomainSelection(
            source_id="resolution-result:wrong",
            primary_domain="domain:life-plan",
            supporting_domains=("domain:health",),
        ),
        composition_domains=DomainTraceDomainSelection(
            source_id="composition:1",
            primary_domain="domain:life-plan",
            supporting_domains=("domain:health",),
        ),
    )

    result = DefaultDomainTraceReferenceValidator().validate(trace, inventory)

    assert DomainTraceValidationCode.AUTHORITATIVE_DOMAIN_MISMATCH in result.codes


@pytest.mark.parametrize(
    "result",
    (
        lambda: DomainTraceValidationResult(
            valid=True,
            codes=(DomainTraceValidationCode.MISSING_REFERENCE,),
        ),
        lambda: DomainTraceValidationResult(valid=False),
    ),
)
def test_validation_result_rejects_contradictory_states(result) -> None:
    with pytest.raises(DomainTraceContractError):
        result()


def _refresh_trace_identity(trace: DomainTrace) -> None:
    digest = trace.calculate_digest()
    object.__setattr__(trace, "digest", digest)
    object.__setattr__(trace, "id", f"domain-trace:{digest[:24]}")
    object.__setattr__(
        trace,
        "domain_results",
        tuple(
            DomainResultTraceReference(item.result_id, item.domain_id, trace.id)
            for item in trace.domain_results
        ),
    )


@pytest.mark.parametrize("key", ("promptText", "secretValue", "chainOfThoughtData"))
def test_audit_v3_rejects_exact_camel_case_private_keys(key: str) -> None:
    with pytest.raises(DomainTraceSerializationError):
        DomainTraceAssemblyRequest.from_dict({
            **_request().to_dict(),
            "metadata": {"outer": {key: "safe-id"}},
        })


@pytest.mark.parametrize("field", ("request_id", "goal_id"))
def test_validator_detects_inline_content_even_with_refreshed_identity(field: str) -> None:
    trace, inventory = _trace_and_inventory()
    object.__setattr__(trace, field, "prompt secret text")
    _refresh_trace_identity(trace)

    result = DefaultDomainTraceReferenceValidator().validate(trace, inventory)

    assert result.valid is False
    assert DomainTraceValidationCode.INLINE_CONTENT_DETECTED in result.codes
    assert DomainTraceValidationCode.INVALID_TRACE_CONTRACT in result.codes


def test_validator_rejects_an_injected_correlation_id() -> None:
    class ExtendedDomainTrace(DomainTrace):
        pass

    trace, inventory = _trace_and_inventory()
    extended = ExtendedDomainTrace(
        **{name: getattr(trace, name) for name in DomainTrace.__dataclass_fields__}
    )
    object.__setattr__(extended, "correlation_id", "user medical details")

    result = DefaultDomainTraceReferenceValidator().validate(extended, inventory)

    assert result.valid is False
    assert DomainTraceValidationCode.FORBIDDEN_FIELD in result.codes
    assert DomainTraceValidationCode.INLINE_CONTENT_DETECTED in result.codes


def test_domain_trace_is_intrinsically_canonical_for_direct_and_mapping_input() -> None:
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    request = DomainTraceAssemblyRequest(
        request_id="request:canonical",
        primary_domain="domain:life-plan",
        supporting_domains=("domain:work", "domain:health"),
        contributions=(
            DomainTraceContribution(
                "domain:life-plan",
                DomainTraceRole.PRIMARY,
                (
                    DomainTraceReference("warning:z", DomainTraceReferenceKind.WARNING, "domain:life-plan"),
                    DomainTraceReference("warning:a", DomainTraceReferenceKind.WARNING, "domain:life-plan"),
                ),
            ),
            DomainTraceContribution("domain:work", DomainTraceRole.SUPPORTING),
            DomainTraceContribution("domain:health", DomainTraceRole.SUPPORTING),
        ),
        references=DomainTraceReferences(
            "resolution-context:canonical",
            "resolution-result:canonical",
            "composition:canonical",
            cognitive_result_ids=("cognitive-result:z", "cognitive-result:a"),
        ),
        started_at=now,
        completed_at=now,
    )
    canonical = DomainTraceAssembler().assemble(request)
    payload = canonical.to_dict()
    payload["supporting_domains"].reverse()
    payload["contributions"] = [payload["contributions"][0], *reversed(payload["contributions"][1:])]
    payload["contributions"][0]["references"].reverse()
    payload["references"]["cognitive_result_ids"].reverse()

    restored = DomainTrace.from_dict(payload)
    direct = DomainTrace(
        id=canonical.id,
        digest=canonical.digest,
        request_id=canonical.request_id,
        goal_id=canonical.goal_id,
        primary_domain=canonical.primary_domain,
        supporting_domains=tuple(reversed(canonical.supporting_domains)),
        contributions=(canonical.contributions[0], *reversed(canonical.contributions[1:])),
        references=canonical.references,
        domain_results=canonical.domain_results,
        status=canonical.status,
        started_at=canonical.started_at,
        completed_at=canonical.completed_at,
        duration_ms=canonical.duration_ms,
        metadata=canonical.metadata,
    )

    assert restored == canonical
    assert direct == canonical
    assert restored.id == direct.id == canonical.id
    assert restored.digest == direct.digest == canonical.digest
    assert restored.to_dict() == direct.to_dict() == canonical.to_dict()


def test_final_trace_rejects_primary_repeated_as_supporting() -> None:
    payload = DomainTraceAssembler().assemble(_request()).to_dict()
    payload["supporting_domains"].append("domain:life-plan")
    payload["contributions"].append({
        "domain_id": "domain:life-plan",
        "role": "supporting",
        "references": [],
    })

    with pytest.raises(DomainTraceSerializationError):
        DomainTrace.from_dict(payload)


def test_final_trace_rejects_a_duplicate_contribution() -> None:
    payload = DomainTraceAssembler().assemble(_request()).to_dict()
    payload["supporting_domains"].append("domain:health")
    payload["contributions"].append(payload["contributions"][1])

    with pytest.raises(DomainTraceSerializationError):
        DomainTrace.from_dict(payload)


@pytest.mark.parametrize("trace_id", (None, ""))
def test_audit_v3_rejects_cross_domain_pairing_without_trace_id(trace_id) -> None:
    with pytest.raises(DomainTraceContractError):
        CrossDomainTraceReference("cross-domain-result:1", trace_id)  # type: ignore[arg-type]


def test_audit_v3_from_dict_rejects_a_non_string_key() -> None:
    payload = DomainTraceAssembler().assemble(_request()).to_dict()
    payload[1] = "secret payload"

    with pytest.raises(DomainTraceSerializationError):
        DomainTrace.from_dict(payload)


def test_validator_fails_closed_for_multiple_simultaneous_mutations() -> None:
    trace, inventory = _trace_and_inventory()
    object.__setattr__(trace, "request_id", object())
    object.__setattr__(trace, "goal_id", "raw provider response")
    object.__setattr__(trace, "primary_domain", object())
    object.__setattr__(trace, "metadata", {"outer": {"promptText": "secretValue"}})
    object.__setattr__(trace.references, "resolution_result_id", ["unhashable"])

    result = DefaultDomainTraceReferenceValidator().validate(trace, inventory)

    assert result.valid is False
    assert DomainTraceValidationCode.INVALID_TRACE_CONTRACT in result.codes
    assert DomainTraceValidationCode.INLINE_CONTENT_DETECTED in result.codes


def test_safe_reference_ids_do_not_trigger_inline_content_detection() -> None:
    request = _request()
    object.__setattr__(request, "metadata", {
        "reasoning_trace_id": "reasoning-trace:1",
        "knowledge_package_id": "knowledge-package:1",
        "provider_audit_id": "provider-audit:1",
        "cross_domain_trace_id": "cross-domain-trace:1",
    })
    trace = DomainTraceAssembler().assemble(request)
    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        expected_primary_domain="domain:life-plan",
        expected_supporting_domains=("domain:health",),
        resolution_result_domains=DomainTraceDomainSelection(
            "resolution-result:1", "domain:life-plan", ("domain:health",)
        ),
        composition_domains=DomainTraceDomainSelection(
            "composition:1", "domain:life-plan", ("domain:health",)
        ),
        domain_results=trace.domain_results,
        cross_domain_results=trace.references.cross_domain_results,
    )

    assert DefaultDomainTraceReferenceValidator().validate(trace, inventory).valid


# ── Audit v4 Defecto 1: DomainResult coverage enforcement ──────────────────────


def test_v4_request_rejects_domain_result_ref_without_pairing() -> None:
    """DOMAIN_RESULT in contribution but domain_results is empty."""
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(DomainTraceContractError, match="DOMAIN_RESULT references must exactly match"):
        DomainTraceAssemblyRequest(
            request_id="request:coverage",
            primary_domain="domain:life-plan",
            contributions=(
                DomainTraceContribution(
                    "domain:life-plan", DomainTraceRole.PRIMARY,
                    (DomainTraceReference("domain-result:1", DomainTraceReferenceKind.DOMAIN_RESULT, "domain:life-plan"),),
                ),
            ),
            references=DomainTraceReferences("ctx:1", "res:1", "comp:1"),
            domain_results=(),
            started_at=now, completed_at=now,
        )


def test_v4_request_rejects_pairing_without_domain_result_ref() -> None:
    """Pairing in domain_results without matching DOMAIN_RESULT contribution reference."""
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(DomainTraceContractError, match="DOMAIN_RESULT references must exactly match"):
        DomainTraceAssemblyRequest(
            request_id="request:coverage",
            primary_domain="domain:life-plan",
            contributions=(
                DomainTraceContribution("domain:life-plan", DomainTraceRole.PRIMARY),
            ),
            references=DomainTraceReferences("ctx:1", "res:1", "comp:1"),
            domain_results=(DomainResultTraceReference("domain-result:1", "domain:life-plan"),),
            started_at=now, completed_at=now,
        )


def test_v4_request_rejects_domain_id_mismatch_between_ref_and_pairing() -> None:
    """DOMAIN_RESULT ref domain_id differs from pairing domain_id."""
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(DomainTraceContractError):
        DomainTraceAssemblyRequest(
            request_id="request:coverage",
            primary_domain="domain:life-plan",
            supporting_domains=("domain:health",),
            contributions=(
                DomainTraceContribution(
                    "domain:life-plan", DomainTraceRole.PRIMARY,
                    (DomainTraceReference("domain-result:1", DomainTraceReferenceKind.DOMAIN_RESULT, "domain:life-plan"),),
                ),
                DomainTraceContribution("domain:health", DomainTraceRole.SUPPORTING),
            ),
            references=DomainTraceReferences("ctx:1", "res:1", "comp:1"),
            domain_results=(DomainResultTraceReference("domain-result:1", "domain:health"),),
            started_at=now, completed_at=now,
        )


def test_v4_request_accepts_valid_domain_result_coverage() -> None:
    """Exact match between contribution DOMAIN_RESULT refs and domain_results."""
    request = _request()
    assert request.domain_results


def test_v4_assembler_rejects_coverage_mismatch() -> None:
    """The assembler itself rejects incoherent coverage before producing a trace."""
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    # Build a valid request first, then mutate it to bypass __post_init__
    request = DomainTraceAssemblyRequest(
        request_id="request:asm",
        primary_domain="domain:life-plan",
        contributions=(
            DomainTraceContribution("domain:life-plan", DomainTraceRole.PRIMARY),
        ),
        references=DomainTraceReferences("ctx:1", "res:1", "comp:1"),
        started_at=now, completed_at=now,
    )
    # Force a domain_results entry without the matching contribution ref
    object.__setattr__(request, "domain_results", (DomainResultTraceReference("domain-result:orphan", "domain:life-plan"),))
    with pytest.raises(DomainTraceContractError, match="DOMAIN_RESULT references must exactly match"):
        DomainTraceAssembler().assemble(request)


# ── Audit v4 Defecto 2: Global ID uniqueness ───────────────────────────────────


def test_v4_request_rejects_same_id_as_resolution_context_and_result() -> None:
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(DomainTraceContractError, match="reference IDs must resolve to a single identity"):
        DomainTraceAssemblyRequest(
            request_id="request:collision",
            primary_domain="domain:life-plan",
            contributions=(
                DomainTraceContribution("domain:life-plan", DomainTraceRole.PRIMARY),
            ),
            references=DomainTraceReferences("same:1", "same:1", "comp:1"),
            started_at=now, completed_at=now,
        )


def test_v4_request_rejects_same_id_as_cross_domain_result_and_trace() -> None:
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(DomainTraceContractError, match="reference IDs must resolve to a single identity"):
        DomainTraceAssemblyRequest(
            request_id="request:collision",
            primary_domain="domain:life-plan",
            contributions=(
                DomainTraceContribution("domain:life-plan", DomainTraceRole.PRIMARY),
            ),
            references=DomainTraceReferences(
                "ctx:1", "res:1", "comp:1",
                cross_domain_results=(CrossDomainTraceReference("shared:1", "shared:1"),),
            ),
            started_at=now, completed_at=now,
        )


def test_v4_request_rejects_same_id_as_finding_and_warning() -> None:
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(DomainTraceContractError, match="reference IDs must resolve to a single identity"):
        DomainTraceAssemblyRequest(
            request_id="request:collision",
            primary_domain="domain:life-plan",
            contributions=(
                DomainTraceContribution(
                    "domain:life-plan", DomainTraceRole.PRIMARY,
                    (
                        DomainTraceReference("shared:1", DomainTraceReferenceKind.FINDING, "domain:life-plan"),
                        DomainTraceReference("shared:1", DomainTraceReferenceKind.WARNING, "domain:life-plan"),
                    ),
                ),
            ),
            references=DomainTraceReferences("ctx:1", "res:1", "comp:1"),
            started_at=now, completed_at=now,
        )


def test_v4_request_rejects_same_id_attributed_to_two_domains() -> None:
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(DomainTraceContractError, match="reference IDs must resolve to a single identity"):
        DomainTraceAssemblyRequest(
            request_id="request:collision",
            primary_domain="domain:life-plan",
            supporting_domains=("domain:health",),
            contributions=(
                DomainTraceContribution(
                    "domain:life-plan", DomainTraceRole.PRIMARY,
                    (DomainTraceReference("shared:1", DomainTraceReferenceKind.FINDING, "domain:life-plan"),),
                ),
                DomainTraceContribution(
                    "domain:health", DomainTraceRole.SUPPORTING,
                    (DomainTraceReference("shared:1", DomainTraceReferenceKind.FINDING, "domain:health"),),
                ),
            ),
            references=DomainTraceReferences("ctx:1", "res:1", "comp:1"),
            started_at=now, completed_at=now,
        )


def test_v4_request_allows_distinct_global_refs() -> None:
    """Distinct global reference IDs remain valid."""
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    request = DomainTraceAssemblyRequest(
        request_id="request:nodup",
        primary_domain="domain:life-plan",
        contributions=(
            DomainTraceContribution("domain:life-plan", DomainTraceRole.PRIMARY),
        ),
        references=DomainTraceReferences(
            "ctx:1", "res:1", "comp:1",
            cognitive_result_ids=("cog:1",),
        ),
        started_at=now, completed_at=now,
    )
    assert request.references.cognitive_result_ids == ("cog:1",)


def test_v5_request_rejects_identical_duplicate_global_refs() -> None:
    """A ref_id may appear only once, even with the same kind and domain."""
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(
        DomainTraceContractError,
        match="reference IDs must resolve to a single identity",
    ):
        DomainTraceAssemblyRequest(
            request_id="request:duplicate-global",
            primary_domain="domain:life-plan",
            contributions=(
                DomainTraceContribution(
                    "domain:life-plan",
                    DomainTraceRole.PRIMARY,
                ),
            ),
            references=DomainTraceReferences(
                "ctx:1",
                "res:1",
                "comp:1",
                cross_domain_results=(
                    CrossDomainTraceReference(
                        "cross-domain-result:1",
                        "cross-trace:shared",
                    ),
                    CrossDomainTraceReference(
                        "cross-domain-result:2",
                        "cross-trace:shared",
                    ),
                ),
            ),
            started_at=now,
            completed_at=now,
        )


def test_v5_assembler_rejects_mutated_identical_duplicate_global_refs() -> None:
    """Assembler defensively rejects duplicates introduced after construction."""
    request = _request()
    object.__setattr__(
        request.references,
        "cross_domain_results",
        (
            CrossDomainTraceReference(
                "cross-domain-result:1",
                "cross-trace:shared",
            ),
            CrossDomainTraceReference(
                "cross-domain-result:2",
                "cross-trace:shared",
            ),
        ),
    )

    with pytest.raises(
        DomainTraceContractError,
        match="reference IDs must resolve to a single identity",
    ):
        DomainTraceAssembler().assemble(request)


def test_v4_valid_set_passes_global_uniqueness() -> None:
    """A fully valid request with distinct IDs passes without error."""
    request = _request()
    trace = DomainTraceAssembler().assemble(request)
    assert trace.id.startswith("domain-trace:")


# ── Audit v4 Defecto 3: Closed from_dict() serialization ───────────────────────


@pytest.mark.parametrize(
    ("contract_cls", "valid_payload"),
    (
        (
            DomainTraceDomainSelection,
            {"source_id": "src:1", "primary_domain": "domain:life-plan", "supporting_domains": []},
        ),
        (
            DomainTraceReference,
            {"ref_id": "ref:1", "kind": "finding", "domain_id": "domain:life-plan"},
        ),
        (
            DomainTraceContribution,
            {"domain_id": "domain:life-plan", "role": "primary", "references": []},
        ),
        (
            DomainResultTraceReference,
            {"result_id": "res:1", "domain_id": "domain:life-plan", "trace_id": None},
        ),
        (
            DomainTraceReferences,
            {
                "resolution_context_id": "ctx:1", "resolution_result_id": "res:1",
                "composition_id": "comp:1", "agent_trace_id": None,
                "cognitive_result_ids": [], "reasoning_trace_ids": [],
                "knowledge_package_ids": [], "cross_domain_results": [],
                "presentation_plan_ids": [], "presentation_validation_result_ids": [],
            },
        ),
    ),
)
class TestV4ClosedFromDict:
    """All 5 public subcontract from_dict() methods must raise DomainTraceSerializationError."""

    def test_empty_mapping(self, contract_cls, valid_payload) -> None:
        with pytest.raises(DomainTraceSerializationError):
            contract_cls.from_dict({})

    def test_required_field_absent(self, contract_cls, valid_payload) -> None:
        # Remove the first required field
        incomplete = dict(valid_payload)
        first_key = next(iter(incomplete))
        del incomplete[first_key]
        with pytest.raises(DomainTraceSerializationError):
            contract_cls.from_dict(incomplete)

    def test_unknown_key(self, contract_cls, valid_payload) -> None:
        with pytest.raises(DomainTraceSerializationError):
            contract_cls.from_dict({**valid_payload, "unknown_extra": "x"})

    def test_non_string_key(self, contract_cls, valid_payload) -> None:
        with pytest.raises(DomainTraceSerializationError):
            contract_cls.from_dict({**valid_payload, 42: "x"})

    def test_invalid_id(self, contract_cls, valid_payload) -> None:
        corrupted = dict(valid_payload)
        # Replace the first string value with an invalid ID
        for key, value in corrupted.items():
            if isinstance(value, str) and value:
                corrupted[key] = "invalid id with spaces"
                break
        with pytest.raises(DomainTraceSerializationError):
            contract_cls.from_dict(corrupted)

    def test_valid_payload(self, contract_cls, valid_payload) -> None:
        result = contract_cls.from_dict(valid_payload)
        assert result is not None


def test_v4_domain_trace_reference_from_dict_rejects_unknown_enum() -> None:
    with pytest.raises(DomainTraceSerializationError):
        DomainTraceReference.from_dict({"ref_id": "ref:1", "kind": "nonexistent_kind", "domain_id": None})


def test_v4_contribution_from_dict_rejects_invalid_nested_reference() -> None:
    with pytest.raises(DomainTraceSerializationError):
        DomainTraceContribution.from_dict({
            "domain_id": "domain:life-plan",
            "role": "primary",
            "references": [{"invalid": "structure"}],
        })


def test_v4_references_from_dict_rejects_missing_required_fields() -> None:
    with pytest.raises(DomainTraceSerializationError):
        DomainTraceReferences.from_dict({"resolution_context_id": "ctx:1"})

# ── Audit v5: top-level from_dict() error normalization ──────────────────────


def test_v5_assembly_request_from_dict_wraps_domain_serialization_error() -> None:
    payload = _request().to_dict()
    payload["primary_domain"] = "bad"

    with pytest.raises(DomainTraceSerializationError):
        DomainTraceAssemblyRequest.from_dict(payload)


def test_v5_domain_trace_from_dict_wraps_domain_serialization_error() -> None:
    trace, _ = _trace_and_inventory()
    payload = trace.to_dict()
    payload["primary_domain"] = "bad"

    with pytest.raises(DomainTraceSerializationError):
        DomainTrace.from_dict(payload)


def test_v5_inventory_from_dict_wraps_domain_serialization_error() -> None:
    _, inventory = _trace_and_inventory()
    payload = inventory.to_dict()
    payload["expected_primary_domain"] = "bad"

    with pytest.raises(DomainTraceSerializationError):
        DomainTraceReferenceInventory.from_dict(payload)
