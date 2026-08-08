"""Phase 10.20 — Health Domain Presentation.

The Health presentation policy is owned by the conservative Health profile and
is surfaced here without duplication.  It mandates the nine safety sections,
disclaimers, provenance, uncertainty, and structured output.
"""

from __future__ import annotations

from cmm.domains.health.profile import build_health_profile


def build_health_presentation_policy():
    """Build the Health Domain presentation policy from the profile."""
    return build_health_profile().presentation_policy


__all__ = ["build_health_presentation_policy"]