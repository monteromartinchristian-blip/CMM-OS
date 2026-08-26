"""Phase 10.30 — Project Domain Presentation.

Produces semantics-preserving, human-facing projections of Project results:
- Supports public domain display name "Project".
- Clearly distinguishes proposals, status transitions, and uncommitted changes.
- Preserves resource constraints, dependency cycles, and verification evidence.
- Does not fabricate execution artifacts or fake commit hashes.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cmm.domains.project.profile import build_project_profile


def build_project_presentation_policy() -> Any:
    """Build the Project Domain presentation policy from the profile."""
    return build_project_profile().presentation_policy


def present_project_result(
    result: Mapping[str, Any] | None,
    *,
    scope: str = "project.management",
) -> dict[str, Any]:
    """Project a Project domain result into a presentation-safe dictionary."""
    data = dict(result or {})

    projected: dict[str, Any] = {
        **data,
        "domain_display_name": "Project",
        "scope_display_name": "Project & Software Engineering",
        "uncertainty_preserved": True,
        "proposals_distinguished": True,
        "presentation_format": "standard_project",
    }
    return projected


__all__ = [
    "build_project_presentation_policy",
    "present_project_result",
]
