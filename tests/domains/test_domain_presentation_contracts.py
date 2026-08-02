"""Phase 10.16 contracts are reference-only, frozen, and deterministic."""

from __future__ import annotations

import json

import pytest

from cmm.domains.composition_contracts import PresentationComposition
from cmm.domains.errors import (
    DomainPresentationContractError,
    DomainPresentationSerializationError,
)
from cmm.domains.presentation_contracts import (
    DomainOutputIntent,
    DomainOutputIntentType,
    DomainPresentationItemRef,
    DomainPresentationItemType,
    DomainPresentationRequest,
)
from cmm.domains.profile_contracts import DomainPresentationPolicy


def _request() -> DomainPresentationRequest:
    return DomainPresentationRequest(
        request_id="presentation-request-1",
        upstream_result_id="domain-result-1",
        composition_id="composition-1",
        policy_id="profile-1",
        presentation=PresentationComposition(
            values={"sections": ["findings", "warnings"]}, provenance={}
        ),
        policy=DomainPresentationPolicy(required_sections=("warnings",)),
        output_intent=DomainOutputIntent(DomainOutputIntentType.HUMAN_READABLE),
        items=(
            DomainPresentationItemRef(
                ref_id="finding-1",
                item_type=DomainPresentationItemType.FINDING,
                source_order=0,
                epistemic_kind="fact",
                confidence=0.7,
                requires_provenance=True,
            ),
        ),
        primary_domain_id="domain:general",
        supporting_domain_ids=("domain:health",),
    )


def test_request_round_trip_and_canonical_digest_are_stable():
    request = _request()

    assert DomainPresentationRequest.from_dict(request.to_dict()) == request
    assert request.calculate_digest() == request.calculate_digest()
    assert json.loads(json.dumps(request.to_dict()))["request_id"] == request.request_id


def test_item_ref_has_no_content_or_unsafe_metadata_surface():
    ref = _request().items[0]

    assert "content" not in ref.to_dict()
    assert "value" not in ref.to_dict()
    with pytest.raises(DomainPresentationSerializationError):
        DomainPresentationItemRef.from_dict({
            **ref.to_dict(),
            "content": "must not be accepted",
        })


def test_artifact_format_requires_logical_artifact_request():
    with pytest.raises(DomainPresentationContractError, match="artifact_format"):
        DomainOutputIntent(DomainOutputIntentType.STRUCTURED, artifact_format="PDF")

    assert DomainOutputIntent(
        DomainOutputIntentType.ARTIFACT_REQUEST, artifact_format="PDF"
    ).artifact_format == "PDF"
