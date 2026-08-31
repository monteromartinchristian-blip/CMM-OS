"""Phase 10.23 — Opposition Domain Presentation.

The Opposition presentation policy is owned by the conservative Opposition
profile and surfaced here without duplication.  It preserves source vs
unofficial, provenance, temporal state, source scope, version, uncertainty,
contradictions, gaps, strategy version, proposal vs adoption, point mock
performance vs trend, coverage dimensions, feasibility constraints, risk, and
approval/external-action state.  It never converts proposal->decision,
inference->fact, stale->current, risk->certainty, observation->trend, or
alternative comparison->abandonment.
"""

from __future__ import annotations

from cmm.domains.oppositions.profile import build_oppositions_profile


def build_oppositions_presentation_policy():
    """Build the Opposition Domain presentation policy from the profile."""
    return build_oppositions_profile().presentation_policy


__all__ = ["build_oppositions_presentation_policy"]
