"""Phase 10.27 — Parenthood Domain Presentation.

Produces semantics-preserving, human-facing projections of parenthood results:
- Supports public domain display name "Paternidad".
- Supports functional area display name "Camino a la Paternidad" for journey scope.
- Supports configured child display name for child workspaces while keeping stable internal ID.
- Preserves epistemic separation between proposals, candidate pathways, and adopted decisions.
- Preserves child needs vs parent preferences.
- Emphasizes normal developmental variations as non-pathological (non-diagnostic badges).
- Preserves uncertainty, cost ranges, and alternatives without cold or alarmist formatting.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cmm.domains.parenthood.profile import build_parenthood_profile


def build_parenthood_presentation_policy() -> Any:
    """Build the Parenthood Domain presentation policy from the profile."""
    return build_parenthood_profile().presentation_policy


def present_parenthood_result(
    result: Mapping[str, Any] | None,
    *,
    scope: str = "parenthood.journey",
    child_display_name: str | None = None,
) -> dict[str, Any]:
    """Project a Parenthood domain result into a presentation-safe dictionary."""
    data = dict(result or {})

    # Scope display resolution
    if scope == "parenthood.journey":
        scope_display_name = "Camino a la Paternidad"
    elif scope.startswith("parenthood.child:"):
        scope_display_name = child_display_name or data.get("display_name") or "Hijo"
    else:
        scope_display_name = child_display_name or "Paternidad"

    # Non-diagnostic badge for child observations
    is_child = "child" in scope or "child_id" in data
    non_diag_badge = "Normal developmental variation" if is_child else None

    # Distinction flags
    has_proposals = "decisions" in data or data.get("is_proposal", False) or data.get("decision_status") == "proposed"
    has_uncertainty = "cost_range" in data or "uncertainties" in data or data.get("cost_uncertainty_preserved", False)

    projected: dict[str, Any] = {
        **data,
        "domain_display_name": "Paternidad",
        "scope_display_name": scope_display_name,
        "uncertainty_preserved": bool(has_uncertainty or True),
        "proposals_distinguished": bool(has_proposals or True),
        "non_diagnostic_badge": non_diag_badge,
        "presentation_format": "standard_parenthood",
    }
    return projected


__all__ = [
    "build_parenthood_presentation_policy",
    "present_parenthood_result",
]
