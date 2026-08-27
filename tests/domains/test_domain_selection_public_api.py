"""Phase 10.31 — Domain selection public API and boundary compatibility."""

from __future__ import annotations

from cmm import domains
from cmm.domains.selection import build_domain_selection_transition
from cmm.domains.selection_contracts import (
    DomainSelectionPolicy,
    DomainSelectionTransition,
)

EXPECTED_SELECTION_EXPORTS = (
    "DomainSelectionPolicy",
    "DomainSelectionTransition",
    "build_domain_selection_transition",
)


def test_phase_10_31_selection_symbols_are_public():
    assert domains.DomainSelectionPolicy is DomainSelectionPolicy
    assert domains.DomainSelectionTransition is DomainSelectionTransition
    assert (
        domains.build_domain_selection_transition is build_domain_selection_transition
    )


def test_phase_10_31_selection_symbols_are_in_all():
    for name in EXPECTED_SELECTION_EXPORTS:
        assert name in domains.__all__, f"{name} missing from __all__"


def test_selection_public_api_does_not_replace_resolution_surface():
    assert hasattr(domains, "DomainResolutionResult")
    assert hasattr(domains, "DomainResolutionPolicy")
    assert hasattr(domains, "DomainScoringPolicy")
    assert hasattr(domains, "DefaultDomainResolver")
    assert hasattr(domains, "DefaultDomainComposer")
