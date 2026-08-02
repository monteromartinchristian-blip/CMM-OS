"""Phase 10.16 – deterministic planning of already-resolved domain results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from cmm.domains.errors import (
    DomainPresentationOutputIntentError,
    DomainPresentationPolicyError,
)
from cmm.domains.presentation_contracts import (
    DomainOutputIntent,
    DomainPresentationComponentDescriptor,
    DomainPresentationConflict,
    DomainPresentationConflictCode,
    DomainPresentationDecision,
    DomainPresentationDecisionCode,
    DomainPresentationItemRef,
    DomainPresentationItemType,
    DomainPresentationPlan,
    DomainPresentationRequest,
    DomainPresentationSectionPlan,
)
from cmm.domains.presentation_requirements import (
    effective_required_sections,
    effective_suppressed_sections,
    preferred_output_type,
    required_visibility_refs,
    resolved_output_intent,
)

_SECTION_BY_ITEM_TYPE: dict[DomainPresentationItemType, str] = {
    DomainPresentationItemType.FINDING: "findings",
    DomainPresentationItemType.GAP: "gaps",
    DomainPresentationItemType.WARNING: "warnings",
    DomainPresentationItemType.CONTRADICTION: "contradictions",
    DomainPresentationItemType.QUESTION: "questions",
    DomainPresentationItemType.APPROVAL: "approvals",
    DomainPresentationItemType.ESCALATION: "escalations",
    DomainPresentationItemType.WORKFLOW: "workflows",
    DomainPresentationItemType.MEMORY_PROPOSAL: "memory_proposals",
    DomainPresentationItemType.RECOMMENDATION: "recommendations",
    DomainPresentationItemType.DECISION: "decisions",
}

_REFERENCE_GROUPS: dict[DomainPresentationItemType, str] = {
    DomainPresentationItemType.QUESTION: "question_refs",
    DomainPresentationItemType.APPROVAL: "approval_refs",
    DomainPresentationItemType.ESCALATION: "escalation_refs",
    DomainPresentationItemType.WORKFLOW: "workflow_refs",
    DomainPresentationItemType.MEMORY_PROPOSAL: "memory_proposal_refs",
}


@dataclass(frozen=True, slots=True)
class _PresentationCompositionView:
    """Typed, deliberately narrow view over Phase 10.8 mapping composition."""

    optional_sections: tuple[str, ...] = ()
    preferred_section_order: tuple[str, ...] = ()
    components: tuple[str, ...] = ()
    views: tuple[str, ...] = ()
    term_glosses: Mapping[str, str] | None = None

    @classmethod
    def from_request(cls, request: DomainPresentationRequest) -> _PresentationCompositionView:
        values = request.presentation.values
        if not isinstance(values, Mapping):  # defensive; PresentationComposition enforces this
            raise DomainPresentationPolicyError("presentation values must be a mapping", field="presentation")
        return cls(
            optional_sections=_read_tokens(values, "optional_sections"),
            preferred_section_order=_read_tokens(values, "preferred_section_order", fallback="sections"),
            components=_read_tokens(values, "components"),
            views=_read_tokens(values, "views"),
            term_glosses=_read_glosses(values),
        )


def _read_tokens(values: Mapping[str, object], key: str, *, fallback: str | None = None) -> tuple[str, ...]:
    raw = values.get(key, values.get(fallback) if fallback else ())
    if raw is None:
        return ()
    if isinstance(raw, str) or not isinstance(raw, Sequence):
        raise DomainPresentationPolicyError(
            f"presentation composition {key!r} must be a sequence of identifiers",
            field=key,
        )
    result: list[str] = []
    for value in raw:
        if not isinstance(value, str) or not value or value in result:
            raise DomainPresentationPolicyError(
                f"presentation composition {key!r} must contain unique identifiers",
                field=key,
            )
        result.append(value)
    return tuple(result)


def _read_glosses(values: Mapping[str, object]) -> Mapping[str, str] | None:
    raw = values.get("term_glosses")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise DomainPresentationPolicyError(
            "presentation composition 'term_glosses' must be a mapping", field="term_glosses"
        )
    result: dict[str, str] = {}
    for term, gloss in raw.items():
        if not isinstance(term, str) or not term or not isinstance(gloss, str) or not gloss:
            raise DomainPresentationPolicyError(
                "presentation composition 'term_glosses' must contain non-empty strings",
                field="term_glosses",
            )
        result[term] = gloss
    return result


def _ordered_union(*sequences: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for sequence in sequences:
        for value in sequence:
            if value not in result:
                result.append(value)
    return tuple(result)


@runtime_checkable
class DomainPresentationPlanner(Protocol):
    """Transforms reference-only structured results into a presentation plan."""

    def plan(self, request: DomainPresentationRequest) -> DomainPresentationPlan: ...


class DefaultDomainPresentationPlanner:
    """Pure planner with no reasoning, rendering, runtime, or cognitive dependency."""

    def plan(self, request: DomainPresentationRequest) -> DomainPresentationPlan:
        if not isinstance(request, DomainPresentationRequest):
            raise DomainPresentationPolicyError(
                "request must be a DomainPresentationRequest", field="request"
            )
        output_intent = resolved_output_intent(request)
        self._validate_output_intent(request, output_intent)
        composition = _PresentationCompositionView.from_request(request)
        required_sections = effective_required_sections(request.policy, request.presentation)
        suppressed = set(effective_suppressed_sections(request.policy, request.presentation))
        illegal_suppression = set(required_sections) & suppressed
        if illegal_suppression:
            raise DomainPresentationPolicyError(
                "required sections cannot be suppressible: "
                f"{sorted(illegal_suppression)}",
                field="suppressible_sections",
            )

        by_section: dict[str, list[DomainPresentationItemRef]] = {}
        for item in request.items:
            by_section.setdefault(_SECTION_BY_ITEM_TYPE[item.item_type], []).append(item)
        section_order = _ordered_union(
            request.policy.preferred_section_order,
            composition.preferred_section_order,
            required_sections,
            request.policy.optional_sections,
            composition.optional_sections,
            tuple(_SECTION_BY_ITEM_TYPE[item.item_type] for item in request.items),
        )
        if request.policy.require_disclaimers is True:
            section_order = _ordered_union(section_order, ("disclaimers",))
        section_order = _apply_warning_position(
            section_order, request.policy.warning_position
        )
        sections: list[DomainPresentationSectionPlan] = []
        for section_id in section_order:
            section_items = by_section.get(section_id, [])
            if section_id == "warnings":
                section_items = sorted(section_items, key=_warning_order_key)
            else:
                section_items = sorted(section_items, key=lambda item: (item.source_order, item.ref_id))
            is_required = (
                section_id in required_sections
                or (section_id == "disclaimers" and request.policy.require_disclaimers is True)
            )
            if not section_items and not is_required:
                continue
            # Empty required sections intentionally remain visible.  Existing
            # item references are never hidden by a local presentation choice.
            sections.append(
                DomainPresentationSectionPlan(
                    section_id=section_id,
                    item_refs=tuple(item.ref_id for item in section_items),
                    required=is_required,
                    visible=True,
                )
            )

        components = self._components(request, composition, tuple(sections))
        conflicts = self._terminology_conflicts(request, composition)
        warning_refs = tuple(
            ref for section in sections if section.section_id == "warnings" for ref in section.item_refs
        )
        grouped_refs = {
            group: tuple(
                item.ref_id
                for item in sorted(request.items, key=lambda value: (value.source_order, value.ref_id))
                if item.item_type is item_type
            )
            for item_type, group in _REFERENCE_GROUPS.items()
        }
        visibility_obligations = required_visibility_refs(request)
        decisions = (
            DomainPresentationDecision(
                DomainPresentationDecisionCode.SECTION_ORDER,
                tuple(section.section_id for section in sections),
            ),
            DomainPresentationDecision(
                DomainPresentationDecisionCode.WARNING_ORDER,
                warning_refs,
            ),
            DomainPresentationDecision(
                DomainPresentationDecisionCode.OUTPUT_INTENT,
                (output_intent.output_type.value,),
            ),
        )
        payload_id = request.calculate_digest()[:24]
        return DomainPresentationPlan(
            plan_id=f"domain-presentation-{payload_id}",
            request_id=request.request_id,
            composition_id=request.composition_id,
            policy_id=request.policy_id,
            output_intent=output_intent,
            sections=tuple(sections),
            preferred_output_type=preferred_output_type(request.policy),
            detail_level=request.policy.detail_level,
            warning_position=request.policy.warning_position,
            qualified_hypothesis_refs=tuple(
                item.ref_id
                for item in sorted(
                    request.items, key=lambda item: (item.source_order, item.ref_id)
                )
                if (
                    request.policy.allow_speculation is False
                    and item.epistemic_kind is not None
                    and item.epistemic_kind.value == "hypothesis"
                )
            ),
            item_refs=request.items,
            components=components,
            protected_terms=request.policy.protected_terms,
            term_glosses=request.policy.term_glosses,
            warning_refs=warning_refs,
            conflicts=conflicts,
            decisions=decisions,
            visibility_obligations=visibility_obligations,
            question_refs=grouped_refs["question_refs"],
            approval_refs=grouped_refs["approval_refs"],
            escalation_refs=grouped_refs["escalation_refs"],
            workflow_refs=grouped_refs["workflow_refs"],
            memory_proposal_refs=grouped_refs["memory_proposal_refs"],
        )

    @staticmethod
    def _validate_output_intent(
        request: DomainPresentationRequest, output_intent: DomainOutputIntent
    ) -> None:
        allowed = request.policy.allowed_output_types
        if allowed is not None and output_intent.output_type.value not in allowed:
            raise DomainPresentationOutputIntentError(
                "logical output intent is not allowed by effective presentation policy",
                field="output_intent",
                details={"output_type": output_intent.output_type.value},
            )

    @staticmethod
    def _components(
        request: DomainPresentationRequest,
        composition: _PresentationCompositionView,
        sections: tuple[DomainPresentationSectionPlan, ...],
    ) -> tuple[DomainPresentationComponentDescriptor, ...]:
        component_ids = _ordered_union(
            request.policy.preferred_components, composition.components
        )
        view_ids = _ordered_union(request.policy.preferred_views, composition.views)
        if not component_ids:
            return ()
        view_id = view_ids[0] if view_ids else "default"
        section_ids = {section.section_id for section in sections}
        return tuple(
            DomainPresentationComponentDescriptor(
                component_id=component_id,
                view_id=view_id,
                section_id="warnings" if component_id == "warning-banner" and "warnings" in section_ids else None,
            )
            for component_id in component_ids
        )

    @staticmethod
    def _terminology_conflicts(
        request: DomainPresentationRequest,
        composition: _PresentationCompositionView,
    ) -> tuple[DomainPresentationConflict, ...]:
        if composition.term_glosses is None:
            return ()
        conflicts: list[DomainPresentationConflict] = []
        for term, gloss in composition.term_glosses.items():
            policy_gloss = request.policy.term_glosses.get(term)
            if policy_gloss is not None and policy_gloss != gloss:
                conflicts.append(
                    DomainPresentationConflict(
                        DomainPresentationConflictCode.TERMINOLOGY_INCOMPATIBLE,
                        (term,),
                    )
                )
        return tuple(conflicts)


def _warning_order_key(item: DomainPresentationItemRef) -> tuple[int, int, int, str]:
    """Use resolved priority only; unprioritized warnings retain source order."""
    if item.warning_priority is None:
        return (1, 0, item.source_order, item.ref_id)
    return (0, item.warning_priority, item.source_order, item.ref_id)


def _apply_warning_position(
    section_order: tuple[str, ...], warning_position: str | None
) -> tuple[str, ...]:
    """Reposition the existing warning section without deriving warning severity."""
    if warning_position not in {"before_content", "after_content"}:
        return section_order
    without_warnings = tuple(section for section in section_order if section != "warnings")
    if warning_position == "before_content":
        return ("warnings",) + without_warnings
    return without_warnings + ("warnings",)


__all__ = ["DefaultDomainPresentationPlanner", "DomainPresentationPlanner"]
