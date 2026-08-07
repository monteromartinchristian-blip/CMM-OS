"""Phase 10.19 — General Domain Presentation."""

from __future__ import annotations

from cmm.domains.general.profile import build_general_profile


def build_general_presentation_policy():
    """Build the General Domain presentation policy from the profile."""
    return build_general_profile().presentation_policy


__all__ = ["build_general_presentation_policy"]