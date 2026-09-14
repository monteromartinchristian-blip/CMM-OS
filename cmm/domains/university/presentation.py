"""Phase 10.22 — University Domain Presentation.

The University presentation policy is owned by the conservative University
profile and is surfaced here without duplication.  It mandates the eight
safety sections, disclaimers, provenance, uncertainty, and structured output,
and never speculates or presents hypotheses as facts.
"""

from __future__ import annotations

from cmm.domains.university.profile import build_university_profile


def build_university_presentation_policy():
    """Build the University Domain presentation policy from the profile."""
    return build_university_profile().presentation_policy


__all__ = ["build_university_presentation_policy"]
