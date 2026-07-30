"""Phase 10.6 — Tests for DomainResolutionSignal."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from cmm.domains.errors import DomainContractValidationError, DomainSerializationError
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import (
    DomainResolutionSerializationError,
    DomainResolutionSignal,
)

_SAMPLE_DT = datetime(2024, 1, 15, tzinfo=timezone.utc)


def _domain(slug: str) -> DomainId:
    return DomainId.from_str(f"domain:{slug}")


class TestDomainResolutionSignal:
    """Construction and validation tests."""

    def test_valid_minimal(self) -> None:
        s = DomainResolutionSignal(kind="entity", source="test", value="hello")
        assert s.kind == "entity"

    def test_valid_full(self) -> None:
        s = DomainResolutionSignal(
            kind="intent",
            source="nlp",
            value={"intent": "greeting"},
            domain_ids=tuple(_domain("core-bot") for _ in range(1)),
            confidence=0.85,
            weight=2.0,
            observed_at=_SAMPLE_DT,
            provenance={"model": "classifier-v1"},
            metadata={"key": "val"},
        )
        assert s.confidence == 0.85

    def test_confidence_0_and_1_accepted(self) -> None:
        s0 = DomainResolutionSignal(
            kind="test", source="t", value=1, confidence=0.0, provenance={"src": "auto"}
        )
        assert s0.confidence == 0.0

    def test_confidence_out_of_range_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="confidence"):
            DomainResolutionSignal(kind="t", source="s", value=1, confidence=1.5)

    def test_confidence_nan_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="confidence"):
            DomainResolutionSignal(
                kind="t", source="s", value=1, confidence=float("nan")
            )

    def test_confidence_inf_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="confidence"):
            DomainResolutionSignal(
                kind="t", source="s", value=1, confidence=float("inf")
            )

    def test_confidence_bool_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="confidence"):
            DomainResolutionSignal(kind="t", source="s", value=1, confidence=True)  # type: ignore[arg-type]

    def test_weight_negative_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="weight"):
            DomainResolutionSignal(kind="t", source="s", value=1, weight=-1.0)

    def test_weight_bool_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="weight"):
            DomainResolutionSignal(kind="t", source="s", value=1, weight=False)  # type: ignore[arg-type]

    def test_duplicate_domain_ids_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="Duplicate"):
            DomainResolutionSignal(
                kind="t", source="s", value=1, domain_ids=[_domain("a"), _domain("a")]
            )

    def test_timestamp_naive_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="timezone"):
            DomainResolutionSignal(
                kind="t",
                source="s",
                value=1,
                observed_at=datetime(2024, 1, 1),  # noqa: DTZ001
            )

    def test_provenance_required_when_confidence_set(self) -> None:
        with pytest.raises(DomainContractValidationError, match="provenance"):
            DomainResolutionSignal(kind="t", source="s", value=1, confidence=0.5)

    def test_provenance_empty_frozen(self) -> None:
        s = DomainResolutionSignal(kind="t", source="s", value=1)
        with pytest.raises(TypeError):
            s.provenance["new"] = "bad"  # type: ignore[index]

    def test_credential_keys_rejected_in_metadata(self) -> None:
        with pytest.raises(DomainContractValidationError, match="Credential"):
            DomainResolutionSignal(
                kind="t", source="s", value=1, metadata={"password": "x"}
            )

    def test_roundtrip(self) -> None:
        s = DomainResolutionSignal(
            kind="intent",
            source="nlp",
            value={"intent": "greeting"},
            domain_ids=tuple(_domain("core-bot") for _ in range(1)),
            confidence=0.9,
            weight=1.5,
            observed_at=_SAMPLE_DT,
            provenance={"model": "v1"},
            metadata={"meta": "data"},
        )
        s2 = DomainResolutionSignal.from_dict(s.to_dict())
        assert s == s2

    def test_custom_signal_kind_namespaced_accepted(self) -> None:
        s = DomainResolutionSignal(
            kind="custom.vendor_signal", source="ext", value="test"
        )
        assert s.kind == "custom.vendor_signal"

    def test_from_dict_unknown_fields_rejected(self) -> None:
        with pytest.raises(DomainSerializationError, match="unknown"):
            DomainResolutionSignal.from_dict(
                {"kind": "t", "source": "s", "value": 1, "unknown_field": True}
            )

    def test_from_dict_missing_fields_rejected(self) -> None:
        with pytest.raises(DomainResolutionSerializationError, match="missing"):
            DomainResolutionSignal.from_dict({"kind": "t"})

    def test_immutable_after_construction(self) -> None:
        s = DomainResolutionSignal(kind="t", source="s", value=1)
        with pytest.raises(FrozenInstanceError):
            s.kind = "other"  # type: ignore[misc]
