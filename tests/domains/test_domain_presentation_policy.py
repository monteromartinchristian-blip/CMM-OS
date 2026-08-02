"""Phase 10.16 policy extensions stay declarative and backwards compatible."""

from __future__ import annotations

import pytest

from cmm.domains.errors import DomainProfileContractError
from cmm.domains.profile_composition import merge_presentation_policy
from cmm.domains.profile_contracts import DomainPresentationPolicy


def test_structural_policy_round_trips_and_preserves_old_payloads():
    policy = DomainPresentationPolicy(
        required_sections=("warnings", "findings"),
        optional_sections=("alternatives",),
        suppressible_sections=("glossary",),
        preferred_section_order=("warnings", "findings", "alternatives"),
        protected_terms=("contraindication",),
        term_glosses={"contraindication": "brief explanatory gloss"},
        preferred_components=("warning-banner",),
        preferred_views=("summary",),
        warning_position="before_content",
        allowed_output_types=("HUMAN_READABLE", "ARTIFACT_REQUEST"),
        preferred_output_types=("HUMAN_READABLE",),
    )

    assert DomainPresentationPolicy.from_dict(policy.to_dict()) == policy
    assert DomainPresentationPolicy.from_dict({"detail_level": "standard"}).detail_level == "standard"


def test_required_sections_cannot_be_suppressible():
    with pytest.raises(DomainProfileContractError, match="must not overlap"):
        DomainPresentationPolicy(
            required_sections=("warnings",), suppressible_sections=("warnings",)
        )


def test_protected_term_gloss_is_complement_not_replacement():
    with pytest.raises(DomainProfileContractError, match="protected_terms"):
        DomainPresentationPolicy(term_glosses={"contraindication": "gloss"})


def test_profile_composition_unions_safety_and_intersects_allowed_outputs():
    current = DomainPresentationPolicy(
        required_sections=("warnings",),
        protected_terms=("risk",),
        allowed_output_types=("HUMAN_READABLE", "STRUCTURED"),
    )
    incoming = DomainPresentationPolicy(
        required_sections=("contradictions",),
        protected_terms=("contraindication",),
        allowed_output_types=("STRUCTURED", "UI_COMPONENTS"),
    )

    merged, _ = merge_presentation_policy(current, incoming)

    assert merged.required_sections == ("warnings", "contradictions")
    assert merged.protected_terms == ("risk", "contraindication")
    assert merged.allowed_output_types == ("STRUCTURED",)
