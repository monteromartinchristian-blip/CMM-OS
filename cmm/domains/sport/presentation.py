"""Phase 10.28 — Sport Domain Presentation.

Produces semantics-preserving, human-facing projections of Sport results:
- Supports public domain display name "Sport".
- Preserves training load, progressive overload, readiness snapshots, injury signals.
- Preserves authorized Health constraints and boundaries.
- Does not introduce clinical diagnosis language or treatment modification claims.
- Preserves uncertainty, load metrics, and alternative progression suggestions.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cmm.domains.sport.profile import build_sport_profile


def build_sport_presentation_policy() -> Any:
    """Build the Sport Domain presentation policy from the profile."""
    return build_sport_profile().presentation_policy


def present_sport_result(
    result: Mapping[str, Any] | None,
    *,
    scope: str = "sport.training",
) -> dict[str, Any]:
    """Project a Sport domain result into a presentation-safe dictionary."""
    data = dict(result or {})

    projected: dict[str, Any] = {
        **data,
        "domain_display_name": "Sport",
        "scope_display_name": "Sport & Athletic Training",
        "uncertainty_preserved": True,
        "is_diagnosis": False,
        "proposals_distinguished": True,
        "presentation_format": "standard_sport",
    }
    return projected


__all__ = [
    "build_sport_presentation_policy",
    "present_sport_result",
]
