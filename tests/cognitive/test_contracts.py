from __future__ import annotations

from datetime import datetime

import pytest

from cmm.cognitive import (
    CognitiveActor,
    CognitiveActorKind,
    CognitiveFinding,
    CognitiveIdentifier,
    CognitiveResult,
    CognitiveSeverity,
    CognitiveStatus,
    Confidence,
    InvalidCognitiveContractError,
    InvalidCognitiveIdentifierError,
    InvalidConfidenceError,
    generate_cognitive_id,
)


def test_cognitive_status_values_are_stable() -> None:
    assert CognitiveStatus.PENDING.value == "pending"
    assert CognitiveStatus.REASONING.value == "reasoning"
    assert CognitiveStatus.COMPLETED.value == "completed"
    assert CognitiveStatus.INSUFFICIENT_INFORMATION.value == "insufficient_information"


def test_confidence_accepts_boundary_values() -> None:
    assert Confidence(0).value == 0.0
    assert Confidence(1).value == 1.0


@pytest.mark.parametrize("value", [-0.01, 1.01, 2, -1])
def test_confidence_rejects_values_outside_range(value: float) -> None:
    with pytest.raises(InvalidConfidenceError):
        Confidence(value)


@pytest.mark.parametrize("value", [True, False, "0.5", None])
def test_confidence_rejects_non_numeric_values(value: object) -> None:
    with pytest.raises(InvalidConfidenceError):
        Confidence(value)  # type: ignore[arg-type]


def test_confidence_serialization_is_structured() -> None:
    confidence = Confidence(
        value=0.82,
        source="system",
        reasons=("direct_evidence",),
        metadata={"rule": "confidence-v1"},
    )

    assert confidence.to_dict() == {
        "value": 0.82,
        "source": "system",
        "reasons": ["direct_evidence"],
        "metadata": {"rule": "confidence-v1"},
    }


def test_identifier_round_trip() -> None:
    identifier = CognitiveIdentifier(
        namespace="knowledge",
        kind="fact",
        value="123",
    )

    assert str(identifier) == "knowledge:fact:123"
    assert CognitiveIdentifier.parse(str(identifier)) == identifier


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "knowledge",
        "knowledge:fact",
        "knowledge:fact:123:extra",
        "Knowledge:fact:123",
        "knowledge:fact:value with spaces",
    ],
)
def test_identifier_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(InvalidCognitiveIdentifierError):
        CognitiveIdentifier.parse(raw)


def test_generated_identifier_has_expected_prefix() -> None:
    generated = generate_cognitive_id("session", "reasoning")

    assert generated.startswith("session:reasoning:")
    assert CognitiveIdentifier.parse(generated).namespace == "session"


def test_actor_is_serializable() -> None:
    actor = CognitiveActor(
        id="actor-user",
        kind=CognitiveActorKind.USER,
        name="Christian",
        permissions=("knowledge.read",),
    )

    assert actor.to_dict() == {
        "id": "actor-user",
        "kind": "user",
        "name": "Christian",
        "permissions": ["knowledge.read"],
        "metadata": {},
    }


def test_actor_rejects_blank_identifier() -> None:
    with pytest.raises(InvalidCognitiveContractError):
        CognitiveActor(
            id=" ",
            kind=CognitiveActorKind.SYSTEM,
        )


def test_finding_is_serializable() -> None:
    finding = CognitiveFinding(
        code="missing-source",
        message="The statement has no source",
        severity=CognitiveSeverity.HIGH,
        blocking=True,
        related_ids=("knowledge:fact:123",),
    )

    assert finding.to_dict() == {
        "code": "missing-source",
        "message": "The statement has no source",
        "severity": "high",
        "blocking": True,
        "source": "cognitive",
        "related_ids": ["knowledge:fact:123"],
        "metadata": {},
    }


def test_completed_result_without_blockers_is_successful() -> None:
    result = CognitiveResult(
        id="cognitive-result:general:123",
        objective="Evaluate available evidence",
        status=CognitiveStatus.COMPLETED,
        confidence=Confidence(0.9),
    )

    assert result.successful is True
    assert result.blocking_findings == ()
    assert result.to_dict()["status"] == "completed"
    assert result.to_dict()["confidence"]["value"] == 0.9


def test_completed_result_with_blocker_is_not_successful() -> None:
    result = CognitiveResult(
        id="cognitive-result:general:123",
        objective="Evaluate available evidence",
        status=CognitiveStatus.COMPLETED,
        confidence=Confidence(0.4),
        findings=(
            CognitiveFinding(
                code="insufficient-evidence",
                message="More evidence is required",
                severity=CognitiveSeverity.HIGH,
                blocking=True,
            ),
        ),
    )

    assert result.successful is False
    assert len(result.blocking_findings) == 1


def test_result_rejects_empty_objective() -> None:
    with pytest.raises(InvalidCognitiveContractError):
        CognitiveResult(
            objective=" ",
            status=CognitiveStatus.PENDING,
            confidence=Confidence(0),
        )


def test_result_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(InvalidCognitiveContractError):
        CognitiveResult(
            objective="Evaluate available evidence",
            status=CognitiveStatus.PENDING,
            confidence=Confidence(0),
            created_at=datetime(2026, 7, 25),
        )


def test_default_result_identifier_is_valid() -> None:
    result = CognitiveResult(
        objective="Evaluate available evidence",
        status=CognitiveStatus.PENDING,
        confidence=Confidence(0),
    )

    parsed = CognitiveIdentifier.parse(result.id)

    assert parsed.namespace == "cognitive-result"
    assert parsed.kind == "general"


def test_base_contracts_metadata_defensive_copy_and_immutability() -> None:
    # 1. Confidence
    src1 = {"key": "original_value"}
    conf = Confidence(value=0.9, metadata=src1)
    src1["key"] = "mutated"
    assert conf.metadata["key"] == "original_value"
    with pytest.raises(TypeError):
        conf.metadata["new_key"] = "forbidden"  # type: ignore[index]

    # 2. CognitiveActor
    src2 = {"key": "original_value"}
    actor = CognitiveActor(
        id="actor-1",
        kind=CognitiveActorKind.USER,
        metadata=src2,
    )
    src2["key"] = "mutated"
    assert actor.metadata["key"] == "original_value"
    with pytest.raises(TypeError):
        actor.metadata["new_key"] = "forbidden"  # type: ignore[index]

    # 3. CognitiveFinding
    src3 = {"key": "original_value"}
    finding = CognitiveFinding(
        code="code-1",
        message="msg",
        metadata=src3,
    )
    src3["key"] = "mutated"
    assert finding.metadata["key"] == "original_value"
    with pytest.raises(TypeError):
        finding.metadata["new_key"] = "forbidden"  # type: ignore[index]

    # 4. CognitiveResult
    src4 = {"key": "original_value"}
    result = CognitiveResult(
        objective="obj",
        status=CognitiveStatus.COMPLETED,
        confidence=conf,
        metadata=src4,
    )
    src4["key"] = "mutated"
    assert result.metadata["key"] == "original_value"
    with pytest.raises(TypeError):
        result.metadata["new_key"] = "forbidden"  # type: ignore[index]
