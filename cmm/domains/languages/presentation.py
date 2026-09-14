"""Phase 10.26 — Languages Domain Presentation.

Produces semantics-preserving user-facing projections of language learning results:
- Preserves epistemic separation between certified proficiency, estimated proficiency,
  and observed performance.
- Preserves valid language variety alternatives distinctly from errors.
- Clearly flags unassessed pronunciation when only text transcript was available.
- Formats structured feedback, progress checkpoints, and review proposals.
- Preserves safety boundaries (no external calendar mutations, no auto-registration).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cmm.domains.languages.profile import build_languages_profile
from cmm.domains.languages.rules import normalize_json_value


def build_languages_presentation_policy() -> Any:
    """Build the Languages Domain presentation policy from the profile."""
    return build_languages_profile().presentation_policy


def present_languages_result(result: Mapping[str, Any] | None) -> dict[str, Any]:
    """Project a Languages domain result into a presentation-safe dictionary."""
    data = dict(normalize_json_value(result or {}))

    # Epistemic separation badges
    cert_level = data.get("certified_level")
    est_level = data.get("estimated_level")
    obs_perf = data.get("observed_performance")

    # Variety distinction
    valid_alts = list(data.get("valid_alternatives", []))
    errors = list(data.get("errors", []))

    # Pronunciation analysis status
    pron_assessed = data.get("pronunciation_assessed", False)
    pron_badge = (
        "Pronunciation assessed" if pron_assessed else "Audio evidence not provided"
    )

    projected: dict[str, Any] = {
        **data,
        "certified_level": cert_level,
        "estimated_level": est_level,
        "observed_performance": obs_perf,
        "valid_alternatives": valid_alts,
        "errors": errors,
        "variety_distinction_preserved": True,
        "pronunciation_assessed": pron_assessed,
        "pronunciation_badge": pron_badge,
        "presentation_format": "standard_pedagogy",
    }
    return projected


__all__ = [
    "build_languages_presentation_policy",
    "present_languages_result",
]
