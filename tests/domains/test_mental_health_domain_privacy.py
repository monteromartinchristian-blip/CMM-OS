"""Phase 10.52 — Mental Health privacy declaration tests.

Mental Health privacy projects into canonical Phase 8 ``PrivacyMetadata`` with
``SensitivityLevel.SENSITIVE`` and local-only default processing.  Canonical
most-restrictive composition may only make the effective result stricter; the
declaration never grants remote, export, cache-widening or cross-domain
authority, and never introduces an ``allow_cross_domain`` shortcut.
"""

from __future__ import annotations

import json

from cmm.cognitive.enums import SensitivityLevel
from cmm.cognitive.privacy import (
    PrivacyMetadata,
    PrivacyPolicy,
    ProcessingLocation,
    resolve_effective_privacy_metadata,
)
from cmm.domains.mental_health.privacy import build_mental_health_privacy_policy
from cmm.domains.privacy_policy_contracts import project_domain_privacy_metadata


def _policy():
    return build_mental_health_privacy_policy()


def test_privacy_identity_and_canonical_sensitivity():
    policy = _policy()
    assert str(policy.domain_id) == "domain:mental-health"
    assert policy.default_privacy.sensitivity is SensitivityLevel.SENSITIVE
    assert policy.default_privacy.policy is PrivacyPolicy.LOCAL_ONLY
    assert policy.require_approval_for_remote is True


def test_declaration_never_grants_remote_export_or_premium():
    default = _policy().default_privacy
    assert default.allow_remote is False
    assert default.allow_premium is False
    assert default.allow_export is False
    assert default.allowed_processing_locations == (ProcessingLocation.LOCAL,)


def test_no_cross_domain_shortcut_is_introduced():
    """Cross-domain authority is never encoded in privacy metadata."""
    payload = _policy().to_dict()
    serialized = json.dumps(payload, sort_keys=True)
    assert "allow_cross_domain" not in serialized
    assert "cross_domain" not in serialized.replace("allowed_processing_locations", "")
    assert "cross_domain" not in _policy().default_privacy.to_dict()


def test_serialization_round_trip_is_deterministic():
    policy = _policy()
    payload = policy.to_dict()
    assert policy.from_dict(payload) == policy
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload


def test_projection_into_canonical_privacy_metadata():
    projected = project_domain_privacy_metadata(
        _policy(), processing_location=ProcessingLocation.LOCAL
    )
    assert isinstance(projected, PrivacyMetadata)
    assert projected.sensitivity is SensitivityLevel.SENSITIVE
    assert projected.policy is PrivacyPolicy.LOCAL_ONLY
    assert projected.allow_remote is False
    assert projected.allow_export is False


def test_remote_projection_adds_approval_without_widening():
    projected = project_domain_privacy_metadata(
        _policy(), processing_location=ProcessingLocation.REMOTE
    )
    assert projected.requires_approval is True
    assert projected.allow_remote is False
    assert projected.allow_export is False
    assert projected.sensitivity is SensitivityLevel.SENSITIVE


def test_composition_can_only_strengthen_the_declaration():
    declared = _policy().default_privacy
    # A more permissive sibling policy must not widen the Mental Health default.
    more_permissive = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        sensitivity=SensitivityLevel.INTERNAL,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        allow_remote=True,
        allow_export=True,
        allow_cache=True,
    )
    resolution = resolve_effective_privacy_metadata(more_permissive, declared)
    effective = resolution.effective
    assert effective.sensitivity is SensitivityLevel.SENSITIVE
    assert effective.policy is PrivacyPolicy.LOCAL_ONLY
    assert effective.allow_remote is False
    assert effective.allow_export is False
    assert ProcessingLocation.REMOTE not in effective.allowed_processing_locations
    assert "allow_cross_domain" not in effective.to_dict()


def test_declaration_does_not_weaken_stronger_ancestor():
    declared = _policy().default_privacy
    restricted = PrivacyMetadata(
        policy=PrivacyPolicy.LOCAL_ONLY,
        sensitivity=SensitivityLevel.RESTRICTED,
        allowed_processing_locations=(ProcessingLocation.LOCAL,),
        allow_remote=False,
        allow_export=False,
    )
    resolution = resolve_effective_privacy_metadata(declared, restricted)
    assert resolution.effective.sensitivity is SensitivityLevel.RESTRICTED
    assert resolution.effective.allow_export is False
    assert resolution.effective.allow_remote is False
