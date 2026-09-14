"""Phase 10.50 – ``domain:life_plan`` privacy policy declaration.

A local, pure declaration of the Domain privacy default. It projects into the
canonical Phase 8 ``PrivacyMetadata``; it is never an effective-policy resolver,
never an operation evaluator, and never grants remote, provider, export, cache or
approval authority.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.cognitive.privacy import PrivacyMetadata, PrivacyPolicy, ProcessingLocation
from cmm.domains.identifiers import DomainId
from cmm.domains.privacy_policy_contracts import DomainPrivacyPolicy

__all__ = ["build_life_plan_privacy_policy"]


def build_life_plan_privacy_policy() -> DomainPrivacyPolicy:
    """Declare the approved ``domain:life_plan`` privacy default.

    Life Plan is conservative by default: current Life Plan resources include
    restricted and sensitive material, so the Domain declares local-only
    processing that resource and package privacy may only make stricter.
    """
    return DomainPrivacyPolicy(
        schema_version="1",
        domain_id=DomainId(slug="life-plan"),
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
