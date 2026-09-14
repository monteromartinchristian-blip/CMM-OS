"""Phase 10.21 — Relationships Domain Presentation.

The Relationships presentation policy is owned by the conservative Relationships
profile and is surfaced here without duplication.  It mandates the ten safety
sections, disclaimers, provenance, uncertainty, and structured output, and never
speculates or presents hypotheses as facts.
"""

from __future__ import annotations

from cmm.domains.relationships.profile import build_relationships_profile


def build_relationships_presentation_policy():
    """Build the Relationships Domain presentation policy from the profile."""
    return build_relationships_profile().presentation_policy


__all__ = ["build_relationships_presentation_policy"]
