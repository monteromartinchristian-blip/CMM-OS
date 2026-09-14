"""Phase 10.53 — Neurodivergence Domain Presentation.

The Neurodivergence presentation policy is owned by the exploration-friendly
Neurodivergence profile and is surfaced here without duplication.  It keeps
certainty, provenance and alternatives visible, offers a useful exploratory
structure, and never forces a clinical tone or a disclaimer-first opening.

This module never alters facts, never hides uncertainty, never promotes a
hypothesis to a confirmed status, never invents a diagnosis, and never becomes
a Phase 11 renderer or CommunicationProfile.
"""

from __future__ import annotations

from cmm.domains.neurodivergence.profile import build_neurodivergence_profile

__all__ = ["build_neurodivergence_presentation_policy"]


def build_neurodivergence_presentation_policy():
    """Build the Neurodivergence Domain presentation policy from the profile."""
    return build_neurodivergence_profile().presentation_policy
