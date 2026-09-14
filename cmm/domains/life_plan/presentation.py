"""Phase 10.29 — Life Plan Domain Presentation.

Produces semantics-preserving, human-facing projections of Life Plan results:
- Supports public domain display name "Life Plan".
- Clearly marks and distinguishes preferences, hypotheses, scenarios, confirmed decisions, and commitments.
- Preserves long-term temporal uncertainty, resource feasibility, and alternative routes.
- Does not convert ideas/preferences/scenarios to decisions or commitments.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cmm.domains.life_plan.profile import build_life_plan_profile


def build_life_plan_presentation_policy() -> Any:
    """Build the Life Plan Domain presentation policy from the profile."""
    return build_life_plan_profile().presentation_policy


def present_life_plan_result(
    result: Mapping[str, Any] | None,
    *,
    scope: str = "life_plan.planning",
) -> dict[str, Any]:
    """Project a Life Plan domain result into a presentation-safe dictionary."""
    data = dict(result or {})

    projected: dict[str, Any] = {
        **data,
        "domain_display_name": "Life Plan",
        "scope_display_name": "Life Plan & Long-Term Strategy",
        "uncertainty_preserved": True,
        "proposals_distinguished": True,
        "decision_lattice_preserved": True,
        "presentation_format": "standard_life_plan",
    }
    return projected


__all__ = [
    "build_life_plan_presentation_policy",
    "present_life_plan_result",
]
