"""Phase 11.21 — canonical privacy enforcement and local/remote egress tests.

The gateway must evaluate real canonical privacy immediately before provider
I/O.  ``LOCAL_ONLY`` plus a remote provider is denied before any adapter call,
provider availability never grants permission, approval cannot widen a refusal,
and attachment content follows exactly the same egress decision as text.
"""

from __future__ import annotations

import json

import pytest

from cmm.agent_runtime.model_egress_privacy_adapter import CanonicalPrivacyEgressGate
from cmm.cognitive.privacy import (
    PrivacyMetadata,
    PrivacyPolicy,
    ProcessingLocation,
)
from kernel.llm.model_gateway import ModelGateway
from kernel.llm.model_gateway_contracts import (
    ModelGatewayRequest,
    ModelInputPart,
)
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from tests.llm.model_gateway_support import MULTIMODAL, PNG_BYTES, build_runtime

LOCAL_ONLY = PrivacyMetadata(policy=PrivacyPolicy.LOCAL_ONLY)

REMOTE_ALLOWED = PrivacyMetadata(
    policy=PrivacyPolicy.REMOTE_ALLOWED,
    allow_remote=True,
    allowed_processing_locations=(
        ProcessingLocation.LOCAL,
        ProcessingLocation.REMOTE,
    ),
)


def _runtime(
    *, provider_id: str, privacy_gate: object | None = None, **overrides: object
):
    return build_runtime(
        provider_id=provider_id,
        capabilities=MULTIMODAL,
        privacy_gate=privacy_gate,
        **overrides,  # type: ignore[arg-type]
    )


def _request(
    *, provider_id: str = "remote-a", **overrides: object
) -> ModelGatewayRequest:
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "model_id": f"{provider_id}:model-1",
        "input_parts": (ModelInputPart.text_part("confidential"),),
    }
    values.update(overrides)
    return ModelGatewayRequest(**values)  # type: ignore[arg-type]


def test_local_only_blocks_remote_egress_before_any_provider_call() -> None:
    runtime = _runtime(
        provider_id="remote-a", privacy_gate=CanonicalPrivacyEgressGate()
    )
    runtime.adapter("remote-a").add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(privacy=LOCAL_ONLY))

    assert error.value.code is ModelGatewayErrorCode.PRIVACY_DENIED
    assert error.value.retryable is False
    assert error.value.details["reason_code"] == "remote_blocked_local_only"
    assert runtime.adapter("remote-a").call_count == 0


def test_provider_availability_never_grants_egress_permission() -> None:
    runtime = _runtime(
        provider_id="remote-a", privacy_gate=CanonicalPrivacyEgressGate()
    )
    projection = runtime.gateway.model_capabilities("remote-a:model-1")

    assert projection.provider_available is True
    assert projection.is_local is False

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(privacy=LOCAL_ONLY))

    assert error.value.code is ModelGatewayErrorCode.PRIVACY_DENIED
    assert runtime.adapter("remote-a").call_count == 0


def test_local_only_allows_a_compatible_local_adapter() -> None:
    runtime = _runtime(provider_id="local", privacy_gate=CanonicalPrivacyEgressGate())
    runtime.adapter("local").add_response(content="processed locally")

    response = runtime.gateway.execute(
        _request(provider_id="local", privacy=LOCAL_ONLY)
    )

    assert response.content == "processed locally"
    assert response.facts is not None
    assert response.facts.privacy_decision == "allowed"
    assert runtime.adapter("local").call_count == 1


def test_remote_requires_canonical_privacy_metadata() -> None:
    runtime = _runtime(
        provider_id="remote-a", privacy_gate=CanonicalPrivacyEgressGate()
    )
    runtime.adapter("remote-a").add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(privacy=None))

    assert error.value.code is ModelGatewayErrorCode.PRIVACY_DENIED
    assert runtime.adapter("remote-a").call_count == 0


def test_remote_requires_a_canonical_privacy_authority() -> None:
    runtime = _runtime(provider_id="remote-a")
    runtime.adapter("remote-a").add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(privacy=REMOTE_ALLOWED))

    assert error.value.code is ModelGatewayErrorCode.PRIVACY_DENIED
    assert "privacy" in error.value.message
    assert runtime.adapter("remote-a").call_count == 0


def test_remote_allowed_policy_permits_execution() -> None:
    runtime = _runtime(
        provider_id="remote-a", privacy_gate=CanonicalPrivacyEgressGate()
    )
    runtime.adapter("remote-a").add_response(content="remote answer")

    response = runtime.gateway.execute(_request(privacy=REMOTE_ALLOWED))

    assert response.content == "remote answer"
    assert response.facts is not None
    assert response.facts.privacy_decision == "allowed"
    assert runtime.adapter("remote-a").call_count == 1


def test_a_prohibited_remote_provider_is_denied() -> None:
    prohibited = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allow_remote=True,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        prohibited_providers=("remote-a",),
    )
    runtime = _runtime(
        provider_id="remote-a", privacy_gate=CanonicalPrivacyEgressGate()
    )
    runtime.adapter("remote-a").add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(privacy=prohibited))

    assert error.value.code is ModelGatewayErrorCode.PRIVACY_DENIED
    assert error.value.details["reason_code"] == "provider_prohibited"
    assert runtime.adapter("remote-a").call_count == 0


def test_the_gateway_owns_no_approval_authority() -> None:
    runtime = _runtime(provider_id="local", privacy_gate=CanonicalPrivacyEgressGate())

    for forbidden in ("approve", "grant_approval", "approval_gate", "approve_call"):
        assert not hasattr(runtime.gateway, forbidden)

    with pytest.raises(TypeError):
        ModelGateway(
            provider_registry=runtime.graph.providers,
            model_catalog=runtime.graph.models,
            approval_gate=object(),  # type: ignore[call-arg]
        )


def test_a_foreign_gate_object_is_rejected_at_construction() -> None:
    with pytest.raises(TypeError):
        build_runtime(privacy_gate=object())


def test_a_failing_privacy_authority_denies_egress() -> None:
    class _ExplodingGate:
        def evaluate_egress(self, **kwargs: object) -> object:
            raise RuntimeError("privacy backend unavailable")

    runtime = _runtime(provider_id="remote-a", privacy_gate=_ExplodingGate())
    runtime.adapter("remote-a").add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(privacy=REMOTE_ALLOWED))

    assert error.value.code is ModelGatewayErrorCode.PRIVACY_DENIED
    assert runtime.adapter("remote-a").call_count == 0


def test_attachment_content_follows_the_same_egress_decision() -> None:
    runtime = _runtime(
        provider_id="remote-a", privacy_gate=CanonicalPrivacyEgressGate()
    )
    runtime.adapter("remote-a").add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(
                privacy=LOCAL_ONLY,
                input_parts=(
                    ModelInputPart.text_part("confidential"),
                    ModelInputPart.image_part(PNG_BYTES, "image/png"),
                ),
            )
        )

    assert error.value.code is ModelGatewayErrorCode.PRIVACY_DENIED
    assert runtime.adapter("remote-a").call_count == 0


def test_a_local_attachment_executes_and_receives_real_bytes() -> None:
    runtime = _runtime(provider_id="local", privacy_gate=CanonicalPrivacyEgressGate())
    runtime.adapter("local").add_response(content="ok")

    response = runtime.gateway.execute(
        _request(
            provider_id="local",
            privacy=LOCAL_ONLY,
            input_parts=(
                ModelInputPart.text_part("confidential"),
                ModelInputPart.image_part(PNG_BYTES, "image/png"),
            ),
        )
    )

    assert response.content == "ok"
    fingerprints = runtime.adapter("local").received_input_fingerprints[0]
    assert fingerprints[1][0] == "image"
    assert fingerprints[1][1] == len(PNG_BYTES)


def test_privacy_metadata_is_never_forwarded_to_the_adapter() -> None:
    runtime = _runtime(
        provider_id="remote-a", privacy_gate=CanonicalPrivacyEgressGate()
    )
    runtime.adapter("remote-a").add_response(content="ok")

    runtime.gateway.execute(_request(privacy=REMOTE_ALLOWED))

    received = runtime.adapter("remote-a").requests[0]
    assert not hasattr(received, "privacy")
    serialized = json.dumps(received.to_dict())
    assert "privacy" not in serialized
    assert "local_only" not in serialized
    assert "remote_allowed" not in serialized


def test_privacy_evidence_is_safe() -> None:
    runtime = _runtime(
        provider_id="remote-a", privacy_gate=CanonicalPrivacyEgressGate()
    )
    runtime.adapter("remote-a").add_response(content="ok")

    response = runtime.gateway.execute(_request(privacy=REMOTE_ALLOWED))

    payload = response.to_dict()
    assert payload["facts"]["privacy_decision"] == "allowed"
    serialized = json.dumps(payload)
    assert "allow_remote" not in serialized
    assert "sensitivity" not in serialized
