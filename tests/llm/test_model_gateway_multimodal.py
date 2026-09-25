"""Phase 11.21 — real image and document input tests.

Multimodality must be real: the adapter receives the actual authorized bytes.
A filename, an attachment identifier or a placeholder string is never enough.
The gateway transports content the caller already authorized; it never reads a
filesystem path, fetches a URL, stores files, or silently converts a PDF to
extracted text.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.model_gateway_contracts import (
    InputPartKind,
    ModelGatewayRequest,
    ModelInputPart,
)
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from tests.llm.model_gateway_support import (
    MARKDOWN_BYTES,
    MULTIMODAL,
    PDF_BYTES,
    PNG_BYTES,
    TEXT_DOCUMENT_BYTES,
    build_runtime,
)

VISION_ONLY = ModelCapabilities(vision=True)
DOCUMENTS_PDF = ModelCapabilities(document_media_types=("application/pdf",))


def _request(*parts: ModelInputPart, **overrides: object) -> ModelGatewayRequest:
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "model_id": "local:model-1",
        "input_parts": parts or (ModelInputPart.text_part("describe"),),
    }
    values.update(overrides)
    return ModelGatewayRequest(**values)  # type: ignore[arg-type]


def _runtime(capabilities: ModelCapabilities, **overrides: object):
    return build_runtime(
        capabilities=capabilities,
        derive_content_from_input=True,
        **overrides,  # type: ignore[arg-type]
    )


# ── Real image content ───────────────────────────────────────────────────────


def test_real_image_bytes_reach_the_adapter() -> None:
    runtime = _runtime(MULTIMODAL)
    runtime.adapter().add_response(content="ignored")
    image = ModelInputPart.image_part(PNG_BYTES, "image/png", display_name="pixel.png")

    response = runtime.gateway.execute(
        _request(ModelInputPart.text_part("what is this"), image)
    )

    fingerprints = runtime.adapter().received_input_fingerprints[0]
    assert fingerprints[1] == (
        "image",
        len(PNG_BYTES),
        hashlib.sha256(PNG_BYTES).hexdigest(),
    )
    assert runtime.adapter().requests[0].input_parts[1].content == PNG_BYTES
    expected = hashlib.sha256(
        "|".join(entry[2] for entry in fingerprints).encode("utf-8")
    ).hexdigest()
    assert response.content == f"echo:{expected}"


def test_the_result_derives_from_the_bytes_not_the_filename() -> None:
    runtime = _runtime(MULTIMODAL)
    runtime.adapter().add_response(content="ignored")
    first = runtime.gateway.execute(
        _request(
            ModelInputPart.image_part(PNG_BYTES, "image/png", display_name="a.png")
        )
    )
    runtime.adapter().add_response(content="ignored")
    second = runtime.gateway.execute(
        _request(
            ModelInputPart.image_part(
                PNG_BYTES + b"\x00trailing", "image/png", display_name="a.png"
            )
        )
    )

    assert first.content != second.content
    assert runtime.adapter().call_count == 2


def test_several_images_are_transported_together() -> None:
    runtime = _runtime(MULTIMODAL)
    runtime.adapter().add_response(content="ok")
    second_image = PNG_BYTES + b"\x01"

    runtime.gateway.execute(
        _request(
            ModelInputPart.image_part(PNG_BYTES, "image/png"),
            ModelInputPart.image_part(second_image, "image/png"),
        )
    )

    fingerprints = runtime.adapter().received_input_fingerprints[0]
    assert [entry[0] for entry in fingerprints] == ["image", "image"]
    assert fingerprints[0][2] != fingerprints[1][2]


def test_image_without_vision_capability_fails_before_provider_io() -> None:
    runtime = _runtime(ModelCapabilities())
    runtime.adapter().add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(ModelInputPart.image_part(PNG_BYTES, "image/png"))
        )

    assert error.value.code is ModelGatewayErrorCode.INPUT_MODALITY_UNSUPPORTED
    assert error.value.retryable is False
    assert runtime.adapter().call_count == 0


def test_unknown_vision_capability_is_not_assumed() -> None:
    runtime = _runtime(ModelCapabilities(reasoning=True))
    runtime.adapter().add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(ModelInputPart.image_part(PNG_BYTES, "image/png"))
        )

    assert error.value.code is ModelGatewayErrorCode.INPUT_MODALITY_UNSUPPORTED
    assert runtime.adapter().call_count == 0


def test_metadata_only_image_is_impossible_to_construct() -> None:
    with pytest.raises(ValueError):
        ModelInputPart(
            kind=InputPartKind.IMAGE,
            media_type="image/png",
            display_name="pixel.png",
        )
    with pytest.raises(ValueError):
        ModelInputPart.image_part(b"", "image/png", display_name="pixel.png")


@pytest.mark.parametrize(
    "display_name",
    ["/etc/passwd", "../../secrets.png", "https://example.test/pixel.png"],
)
def test_path_and_url_shaped_display_names_are_rejected(display_name: str) -> None:
    with pytest.raises(ValueError):
        ModelInputPart.image_part(PNG_BYTES, "image/png", display_name=display_name)


def test_a_path_like_prompt_is_transported_as_text_never_read() -> None:
    runtime = _runtime(ModelCapabilities())
    runtime.adapter().add_response(content="ok")

    runtime.gateway.execute(_request(ModelInputPart.text_part("/etc/passwd")))

    received = runtime.adapter().requests[0].input_parts[0]
    assert received.kind is InputPartKind.TEXT
    assert received.text == "/etc/passwd"
    assert received.content == b"/etc/passwd"


# ── Real PDF and document content ────────────────────────────────────────────


def test_real_pdf_bytes_reach_the_adapter() -> None:
    runtime = _runtime(MULTIMODAL)
    runtime.adapter().add_response(content="ignored")
    document = ModelInputPart.document_part(PDF_BYTES, "application/pdf")

    response = runtime.gateway.execute(_request(document))

    fingerprints = runtime.adapter().received_input_fingerprints[0]
    assert fingerprints[0] == (
        "document",
        len(PDF_BYTES),
        hashlib.sha256(PDF_BYTES).hexdigest(),
    )
    assert runtime.adapter().requests[0].input_parts[0].content == PDF_BYTES
    assert response.content.startswith("echo:")


def test_pdf_is_transported_as_document_content_not_extracted_text() -> None:
    runtime = _runtime(MULTIMODAL)
    runtime.adapter().add_response(content="ok")

    runtime.gateway.execute(
        _request(ModelInputPart.document_part(PDF_BYTES, "application/pdf"))
    )

    received = runtime.adapter().requests[0].input_parts[0]
    assert received.kind is InputPartKind.DOCUMENT
    assert received.media_type == "application/pdf"
    assert received.content.startswith(b"%PDF-1.4")
    assert received.content == PDF_BYTES
    assert received.text is None


@pytest.mark.parametrize(
    ("payload", "media_type"),
    [
        (PDF_BYTES, "application/pdf"),
        (TEXT_DOCUMENT_BYTES, "text/plain"),
        (MARKDOWN_BYTES, "text/markdown"),
    ],
)
def test_canonical_document_media_types_are_supported(
    payload: bytes, media_type: str
) -> None:
    runtime = _runtime(MULTIMODAL)
    runtime.adapter().add_response(content="ok")

    runtime.gateway.execute(_request(ModelInputPart.document_part(payload, media_type)))

    fingerprints = runtime.adapter().received_input_fingerprints[0]
    assert fingerprints[0][0] == "document"
    assert fingerprints[0][2] == hashlib.sha256(payload).hexdigest()


def test_document_without_declared_media_type_fails_before_provider_io() -> None:
    runtime = _runtime(ModelCapabilities(vision=True))
    runtime.adapter().add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(ModelInputPart.document_part(PDF_BYTES, "application/pdf"))
        )

    assert error.value.code is ModelGatewayErrorCode.INPUT_MODALITY_UNSUPPORTED
    assert runtime.adapter().call_count == 0


def test_document_media_type_must_be_declared_exactly() -> None:
    runtime = _runtime(DOCUMENTS_PDF)
    runtime.adapter().add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(ModelInputPart.document_part(MARKDOWN_BYTES, "text/markdown"))
        )

    assert error.value.code is ModelGatewayErrorCode.INPUT_MODALITY_UNSUPPORTED
    assert runtime.adapter().call_count == 0


def test_declared_document_media_type_is_accepted() -> None:
    runtime = _runtime(DOCUMENTS_PDF)
    runtime.adapter().add_response(content="ok")

    response = runtime.gateway.execute(
        _request(ModelInputPart.document_part(PDF_BYTES, "application/pdf"))
    )

    assert response.content.startswith("echo:")
    assert runtime.adapter().call_count == 1
    assert runtime.adapter().received_input_fingerprints[0][0][0] == "document"


def test_document_bytes_never_appear_in_serialized_output() -> None:
    runtime = _runtime(MULTIMODAL)
    runtime.adapter().add_response(content="ok")

    response = runtime.gateway.execute(
        _request(
            ModelInputPart.image_part(PNG_BYTES, "image/png", display_name="pixel.png"),
            ModelInputPart.document_part(PDF_BYTES, "application/pdf"),
        )
    )

    serialized = json.dumps(response.to_dict())
    assert "PNG" not in serialized
    assert "%PDF" not in serialized
    assert PNG_BYTES.decode("latin-1") not in serialized
    assert PDF_BYTES.decode("latin-1") not in serialized


def test_mixed_multimodal_request_records_every_modality() -> None:
    runtime = _runtime(MULTIMODAL)
    runtime.adapter().add_response(content="ok")

    response = runtime.gateway.execute(
        _request(
            ModelInputPart.text_part("summarize"),
            ModelInputPart.image_part(PNG_BYTES, "image/png"),
            ModelInputPart.document_part(PDF_BYTES, "application/pdf"),
        )
    )

    assert response.facts is not None
    assert response.facts.input_modalities == ("text", "image", "document")
    assert runtime.adapter().received_input_fingerprints[0] == (
        ("text", len("summarize"), hashlib.sha256(b"summarize").hexdigest()),
        ("image", len(PNG_BYTES), hashlib.sha256(PNG_BYTES).hexdigest()),
        ("document", len(PDF_BYTES), hashlib.sha256(PDF_BYTES).hexdigest()),
    )
