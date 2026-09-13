"""Phase 10.50 — ``domain:neurodivergence`` privacy policy declaration.

A local, pure declaration of the Domain privacy default.  It projects into the
canonical Phase 8 ``PrivacyMetadata``; it is never an effective-policy
resolver, never an operation evaluator, and never grants remote, provider,
export, cache or approval authority.

Neurodivergence content is **local-only** by default and remains subject to
canonical most-restrictive composition: resource and package privacy may only
make the effective result stricter.  Provider availability cannot weaken the
effective policy, no ``allow_cross_domain`` privacy shortcut is introduced, and
cross-domain authority is never encoded in privacy metadata (frozen design
§17, §19).
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.cognitive.privacy import PrivacyMetadata, PrivacyPolicy, ProcessingLocation
from cmm.domains.identifiers import DomainId
from cmm.domains.privacy_policy_contracts import DomainPrivacyPolicy

__all__ = ["build_neurodivergence_privacy_policy"]


def build_neurodivergence_privacy_policy() -> DomainPrivacyPolicy:
    """Declare the approved ``domain:neurodivergence`` privacy default."""
    return DomainPrivacyPolicy(
        schema_version="1",
        domain_id=DomainId(slug="neurodivergence"),
        default_privacy=PrivacyMetadata(
            policy=PrivacyPolicy.LOCAL_ONLY,
            sensitivity=SensitivityLevel.SENSITIVE,
            allowed_processing_locations=(ProcessingLocation.LOCAL,),
            allow_remote=False,
            allow_premium=False,
            allow_cache=True,
            allow_export=False,
        ),
        require_approval_for_remote=True,
    )
