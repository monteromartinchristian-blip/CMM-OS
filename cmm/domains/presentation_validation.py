"""Phase 10.16 – preservation checks for Domain Presentation plans."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from cmm.domains.presentation_contracts import (
    DomainPresentationItemRef,
    DomainPresentationItemType,
    DomainPresentationPlan,
    DomainPresentationRequest,
    DomainPresentationValidationResult,
    DomainPresentationValidationState,
)
from cmm.domains.presentation_requirements import (
    effective_required_sections,
    effective_suppressed_sections,
    preferred_output_type,
    required_visibility_refs,
    resolved_output_intent,
)

_GROUPS: tuple[tuple[str, DomainPresentationItemType], ...] = (
    ("warning_refs", DomainPresentationItemType.WARNING),
    ("question_refs", DomainPresentationItemType.QUESTION),
    ("approval_refs", DomainPresentationItemType.APPROVAL),
    ("escalation_refs", DomainPresentationItemType.ESCALATION),
    ("workflow_refs", DomainPresentationItemType.WORKFLOW),
    ("memory_proposal_refs", DomainPresentationItemType.MEMORY_PROPOSAL),
)


@runtime_checkable
class DomainPresentationPreservationValidator(Protocol):
    """Validates that a plan has not changed resolved upstream semantics."""

    def validate(
        self,
        request: DomainPresentationRequest,
        plan: DomainPresentationPlan,
    ) -> DomainPresentationValidationResult: ...


class DefaultDomainPresentationPreservationValidator:
    """Pure, reference-only validator; it cannot inspect source content."""

    def validate(
        self,
        request: DomainPresentationRequest,
        plan: DomainPresentationPlan,
    ) -> DomainPresentationValidationResult:
        codes: list[str] = []
        missing: list[str] = []
        unexpected: list[str] = []
        invariants: list[str] = []
        self._validate_identity(request, plan, codes)
        self._validate_policy_transport(request, plan, codes)
        self._validate_output_intent(request, plan, codes)
        self._validate_terms(request, plan, codes)
        self._validate_items(request, plan, codes, missing, unexpected)
        self._validate_sections(request, plan, codes, missing, unexpected)
        self._validate_visibility(request, plan, codes, missing, unexpected)
        self._validate_groups(request, plan, codes, unexpected)
        self._validate_components(plan, codes)
        self._validate_warnings(request, plan, codes)
        if plan.conflicts:
            _append(codes, "UNRESOLVED_MULTIDOMAIN_CONFLICT")
        if not codes:
            invariants.extend(
                (
                    "REFERENCE_SET_PRESERVED",
                    "SEMANTICS_PRESERVED",
                    "OUTPUT_INTENT_PRESERVED",
                    "VISIBILITY_OBLIGATIONS_PRESERVED",
                    "EFFECTIVE_REQUIRED_SECTIONS_PRESERVED",
                )
            )
        valid = not codes
        return DomainPresentationValidationResult(
            valid=valid,
            state=(
                DomainPresentationValidationState.VALID
                if valid
                else DomainPresentationValidationState.BLOCKED
            ),
            codes=tuple(codes),
            conflicts=plan.conflicts,
            missing_refs=tuple(missing),
            unexpected_refs=tuple(unexpected),
            invariants=tuple(invariants),
            upstream_digest=request.calculate_digest(),
            plan_digest=plan.calculate_digest(),
        )

    @staticmethod
    def _validate_identity(
        request: DomainPresentationRequest, plan: DomainPresentationPlan, codes: list[str]
    ) -> None:
        if plan.request_id != request.request_id:
            _append(codes, "REQUEST_ID_CHANGED")
        if plan.composition_id != request.composition_id:
            _append(codes, "COMPOSITION_ID_CHANGED")
        if plan.policy_id != request.policy_id:
            _append(codes, "POLICY_ID_CHANGED")

    @staticmethod
    def _validate_policy_transport(
        request: DomainPresentationRequest, plan: DomainPresentationPlan, codes: list[str]
    ) -> None:
        if plan.detail_level != request.policy.detail_level:
            _append(codes, "DETAIL_LEVEL_CHANGED")
        if plan.warning_position != request.policy.warning_position:
            _append(codes, "WARNING_POSITION_CHANGED")
        if plan.preferred_output_type != preferred_output_type(request.policy):
            _append(codes, "PREFERRED_OUTPUT_TYPE_CHANGED")
        expected_hypotheses = tuple(
            item.ref_id
            for item in sorted(request.items, key=lambda item: (item.source_order, item.ref_id))
            if (
                request.policy.allow_speculation is False
                and item.epistemic_kind is not None
                and item.epistemic_kind.value == "hypothesis"
            )
        )
        if plan.qualified_hypothesis_refs != expected_hypotheses:
            _append(codes, "HYPOTHESIS_UNQUALIFIED")
        if request.policy.require_disclaimers is True:
            has_section = any(
                section.section_id == "disclaimers" and section.visible
                for section in plan.sections
            )
            has_component = any(
                component.component_id == "disclaimers" for component in plan.components
            )
            if not has_section and not has_component:
                _append(codes, "DISCLAIMERS_MISSING")

    @staticmethod
    def _validate_output_intent(
        request: DomainPresentationRequest, plan: DomainPresentationPlan, codes: list[str]
    ) -> None:
        if plan.output_intent != resolved_output_intent(request):
            _append(codes, "OUTPUT_INTENT_CHANGED")
        allowed = request.policy.allowed_output_types
        if allowed is not None and plan.output_intent.output_type.value not in allowed:
            _append(codes, "OUTPUT_INTENT_NOT_ALLOWED")

    @staticmethod
    def _validate_terms(
        request: DomainPresentationRequest, plan: DomainPresentationPlan, codes: list[str]
    ) -> None:
        if tuple(plan.protected_terms) != tuple(request.policy.protected_terms):
            _append(codes, "PROTECTED_TERMS_CHANGED")
        if dict(plan.term_glosses) != dict(request.policy.term_glosses):
            _append(codes, "TERM_GLOSSES_CHANGED")

    @staticmethod
    def _validate_items(
        request: DomainPresentationRequest,
        plan: DomainPresentationPlan,
        codes: list[str],
        missing: list[str],
        unexpected: list[str],
    ) -> None:
        upstream = {item.ref_id: item for item in request.items}
        presented = {item.ref_id: item for item in plan.item_refs}
        for ref_id in sorted(set(upstream) - set(presented)):
            _append(codes, "MISSING_REF")
            _append_ref(missing, ref_id)
        for ref_id in sorted(set(presented) - set(upstream)):
            _append(codes, "UNKNOWN_REF")
            _append_ref(unexpected, ref_id)
        for ref_id in sorted(set(upstream) & set(presented)):
            _compare_item(upstream[ref_id], presented[ref_id], codes)

    @staticmethod
    def _validate_sections(
        request: DomainPresentationRequest,
        plan: DomainPresentationPlan,
        codes: list[str],
        missing: list[str],
        unexpected: list[str],
    ) -> None:
        by_id = {section.section_id: section for section in plan.sections}
        required_sections = effective_required_sections(request.policy, request.presentation)
        suppressed_sections = set(
            effective_suppressed_sections(request.policy, request.presentation)
        )
        for section_id in required_sections:
            section = by_id.get(section_id)
            invalid = section is None or not section.required or not section.visible
            if section_id in suppressed_sections:
                _append(codes, "EFFECTIVE_REQUIRED_SECTION_SUPPRESSED")
            if section is None:
                _append(codes, "EFFECTIVE_REQUIRED_SECTION_MISSING")
            elif not section.required:
                _append(codes, "EFFECTIVE_REQUIRED_SECTION_NOT_REQUIRED")
            elif not section.visible:
                _append(codes, "EFFECTIVE_REQUIRED_SECTION_HIDDEN")
            if invalid and section_id in request.policy.required_sections:
                _append(codes, "MANDATORY_SECTION_SUPPRESSED")

        plan_item_ids = {item.ref_id for item in plan.item_refs}
        expected_ids = {item.ref_id for item in request.items}
        section_counts: dict[str, int] = {}
        for section in plan.sections:
            for ref_id in section.item_refs:
                section_counts[ref_id] = section_counts.get(ref_id, 0) + 1
                if ref_id not in plan_item_ids:
                    _append(codes, "UNKNOWN_SECTION_REFERENCE")
                    _append_ref(unexpected, ref_id)
                if ref_id not in expected_ids:
                    _append(codes, "UNKNOWN_SECTION_REF")
                    _append_ref(unexpected, ref_id)
        for ref_id, count in section_counts.items():
            if count > 1:
                _append(codes, "DUPLICATE_REFERENCE")
                _append(codes, "ILLEGAL_DUPLICATE_REF")
        for ref_id in sorted(expected_ids - set(section_counts)):
            _append(codes, "MISSING_SECTION_REF")
            _append_ref(missing, ref_id)

    @staticmethod
    def _validate_visibility(
        request: DomainPresentationRequest,
        plan: DomainPresentationPlan,
        codes: list[str],
        missing: list[str],
        unexpected: list[str],
    ) -> None:
        required_refs = required_visibility_refs(request)
        plan_item_by_id = {item.ref_id: item for item in plan.item_refs}
        section_locations: dict[str, list[bool]] = {}
        for section in plan.sections:
            for ref_id in section.item_refs:
                section_locations.setdefault(ref_id, []).append(section.visible)

        obligations = set(plan.visibility_obligations)
        for ref_id in required_refs:
            if ref_id not in obligations:
                _append(codes, "REQUIRED_VISIBILITY_OBLIGATION_MISSING")
        for ref_id in plan.visibility_obligations:
            item = plan_item_by_id.get(ref_id)
            if item is None:
                _append(codes, "UNKNOWN_VISIBILITY_REFERENCE")
                _append_ref(unexpected, ref_id)
                continue
            if not item.visible:
                _append(codes, "REQUIRED_REFERENCE_HIDDEN")
            locations = section_locations.get(ref_id, [])
            if not locations:
                _append(codes, "REQUIRED_REFERENCE_WITHOUT_SECTION")
                _append_ref(missing, ref_id)
            elif len(locations) > 1:
                _append(codes, "DUPLICATE_REFERENCE")
            elif not locations[0]:
                _append(codes, "REQUIRED_SECTION_HIDDEN")

    @staticmethod
    def _validate_groups(
        request: DomainPresentationRequest,
        plan: DomainPresentationPlan,
        codes: list[str],
        unexpected: list[str],
    ) -> None:
        plan_item_by_id = {item.ref_id: item for item in plan.item_refs}
        for attribute, expected_type in _GROUPS:
            actual_refs = getattr(plan, attribute)
            expected_refs = tuple(
                item.ref_id
                for item in sorted(
                    request.items,
                    key=(
                        _warning_order_key
                        if expected_type is DomainPresentationItemType.WARNING
                        else lambda item: (item.source_order, item.ref_id)
                    ),
                )
                if item.item_type is expected_type
            )
            prefix = attribute.removesuffix("_refs").upper()
            for ref_id in actual_refs:
                item = plan_item_by_id.get(ref_id)
                if item is None:
                    _append(codes, "UNKNOWN_REF")
                    _append_ref(unexpected, ref_id)
                elif item.item_type is not expected_type:
                    _append(codes, f"{prefix}_GROUP_TYPE_MISMATCH")
            if actual_refs != expected_refs:
                _append(codes, f"{prefix}_GROUP_MISSING_REF")

    @staticmethod
    def _validate_components(plan: DomainPresentationPlan, codes: list[str]) -> None:
        section_ids = {section.section_id for section in plan.sections}
        for component in plan.components:
            if component.section_id is not None and component.section_id not in section_ids:
                _append(codes, "COMPONENT_UNKNOWN_SECTION")

    @staticmethod
    def _validate_warnings(
        request: DomainPresentationRequest, plan: DomainPresentationPlan, codes: list[str]
    ) -> None:
        warnings = [
            item for item in request.items if item.item_type is DomainPresentationItemType.WARNING
        ]
        expected = tuple(item.ref_id for item in sorted(warnings, key=_warning_order_key))
        warning_section = next(
            (section for section in plan.sections if section.section_id == "warnings"), None
        )
        actual_section = warning_section.item_refs if warning_section else ()
        if plan.warning_refs != expected or actual_section != expected:
            _append(codes, "INVALID_WARNING_PRIORITY")
        if (
            warnings
            and request.policy.warning_position == "before_content"
            and (not plan.sections or plan.sections[0].section_id != "warnings")
        ):
            _append(codes, "WARNING_POSITION_CHANGED")
        if (
            warnings
            and request.policy.warning_position == "after_content"
            and (not plan.sections or plan.sections[-1].section_id != "warnings")
        ):
            _append(codes, "WARNING_POSITION_CHANGED")


def _compare_item(
    upstream: DomainPresentationItemRef,
    presented: DomainPresentationItemRef,
    codes: list[str],
) -> None:
    if upstream.item_type is not presented.item_type:
        _append(codes, "ITEM_TYPE_CHANGED")
    if upstream.epistemic_kind is not presented.epistemic_kind:
        _append(codes, "EPISTEMIC_KIND_CHANGED")
    if upstream.confidence != presented.confidence:
        _append(codes, "CONFIDENCE_CHANGED")
    if upstream.requires_provenance != presented.requires_provenance:
        _append(codes, "PROVENANCE_REQUIREMENT_CHANGED")
    if upstream.warning_priority != presented.warning_priority:
        _append(codes, "WARNING_PRIORITY_CHANGED")
    if upstream.source_order != presented.source_order:
        _append(codes, "SOURCE_ORDER_CHANGED")
    if upstream.visible != presented.visible:
        _append(codes, "VISIBILITY_CHANGED")
    if upstream.domain_ids != presented.domain_ids:
        _append(codes, "DOMAIN_PARTICIPATION_CHANGED")
    if (
        upstream.pending != presented.pending
        or upstream.requires_user_interaction != presented.requires_user_interaction
        or upstream.requires_approval != presented.requires_approval
        or upstream.requires_confirmation != presented.requires_confirmation
        or upstream.explicitly_visible != presented.explicitly_visible
    ):
        _append(codes, "ITEM_VISIBILITY_STATE_CHANGED")


def _warning_order_key(item: DomainPresentationItemRef) -> tuple[int, int, int, str]:
    if item.warning_priority is None:
        return (1, 0, item.source_order, item.ref_id)
    return (0, item.warning_priority, item.source_order, item.ref_id)


def _append(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _append_ref(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


__all__ = [
    "DefaultDomainPresentationPreservationValidator",
    "DomainPresentationPreservationValidator",
]
