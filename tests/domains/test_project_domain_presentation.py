"""Phase 10.30 — Project Domain Presentation Tests."""

from __future__ import annotations

from cmm.domains.profile_contracts import DomainPresentationPolicy
from cmm.domains.project.presentation import (
    build_project_presentation_policy,
    present_project_result,
)


def test_build_project_presentation_policy() -> None:
    policy = build_project_presentation_policy()
    assert isinstance(policy, DomainPresentationPolicy)
    assert len(policy.preferred_output_types) > 0


def test_present_project_result_preserves_semantics() -> None:
    result = {
        "project_id": "proj:1",
        "title": "CMM OS Core",
        "status": "active",
        "is_proposal": True,
    }
    presented = present_project_result(result)
    assert presented["domain_display_name"] == "Project"
    assert presented["proposals_distinguished"] is True
    assert presented["is_proposal"] is True
    assert presented["project_id"] == "proj:1"
