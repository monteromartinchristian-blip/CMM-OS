"""Phase 10.50 – ``domain:university`` privacy policy declaration.

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

__all__ = ["build_university_privacy_policy"]


def build_university_privacy_policy() -> DomainPrivacyPolicy:
    """Declare the approved ``domain:university`` privacy default.

    University declares a remote-allowed Domain default; remote processing is
    possible only when every other canonical privacy and permission gate permits
    it. The Domain adds no provider allowlist and no remote approval requirement,
    and stricter resource or package privacy still forces local-only.
    """
    return DomainPrivacyPolicy(
        schema_version="1",
        domain_id=DomainId(slug="university"),
        default_privacy=PrivacyMetadata(
            policy=PrivacyPolicy.REMOTE_ALLOWED,
            sensitivity=SensitivityLevel.INTERNAL,
            allowed_processing_locations=(
                ProcessingLocation.LOCAL,
                ProcessingLocation.REMOTE,
            ),
            allow_remote=True,
            allow_premium=False,
            allow_cache=True,
            allow_export=False,
        ),
        require_approval_for_remote=False,
    )
