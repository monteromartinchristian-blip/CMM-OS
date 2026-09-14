"""Phase 10.52 — Mental Health Domain Presentation.

The Mental Health presentation policy is owned by the conservative Mental
Health profile and is surfaced here without duplication.  It mandates a human,
non-pathologizing ordinary mode with visible uncertainty, visible
interpretation-vs-fact separation and visible sensitive-action confirmation
requirements.  It never alters facts, never hides uncertainty, never promotes
an interpretation to a fact, never invents diagnosis, never alters confidence,
and never becomes a Phase 11 renderer or CommunicationProfile.
"""

from __future__ import annotations

from cmm.domains.mental_health.profile import build_mental_health_profile

__all__ = ["build_mental_health_presentation_policy"]


def build_mental_health_presentation_policy():
    """Build the Mental Health Domain presentation policy from the profile."""
    return build_mental_health_profile().presentation_policy
