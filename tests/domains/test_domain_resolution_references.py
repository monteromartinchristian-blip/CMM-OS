"""Phase 10.6 — Tests for auxiliary reference contracts."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cmm.domains.errors import DomainContractValidationError
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import (
    DomainResolutionEntity,
    DomainResolutionEvent,
    DomainResolutionHistoryItem,
    DomainResolutionKnowledgeItem,
    DomainResolutionResource,
)

_SAMPLE_DT = datetime(2024, 1, 15, tzinfo=timezone.utc)


def _domain(slug: str) -> DomainId:
    return DomainId.from_str(f"domain:{slug}")


class TestDomainResolutionResource:
    def test_valid_minimal(self) -> None:
        r = DomainResolutionResource(id="res-1", resource_type="file", source="fs")
        assert r.id == "res-1"
        assert r.resource_type == "file"
        assert r.sensitivity is None

    def test_valid_full(self) -> None:
        r = DomainResolutionResource(
            id="res-1",
            resource_type="file",
            source="fs",
            domain_ids=[_domain("a")],
            sensitivity="high",
            temporal_reference=_SAMPLE_DT,
            metadata={"key": "val"},
        )
        assert r.sensitivity == "high"
        assert r.temporal_reference == _SAMPLE_DT

    def test_source_required(self) -> None:
        with pytest.raises(DomainContractValidationError, match="source"):
            DomainResolutionResource(id="x", resource_type="f", source="")

    def test_temporal_reference_naive_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="timezone"):
            DomainResolutionResource(
                id="x",
                resource_type="f",
                source="s",
                temporal_reference=datetime(2024, 1, 1),  # noqa: DTZ001
            )

    def test_domain_ids_dedup(self) -> None:
        with pytest.raises(DomainContractValidationError, match="Duplicate"):
            DomainResolutionResource(
                id="x",
                resource_type="f",
                source="s",
                domain_ids=[_domain("a"), _domain("a")],
            )

    def test_roundtrip(self) -> None:
        r = DomainResolutionResource(
            id="r1",
            resource_type="file",
            source="fs",
            domain_ids=[_domain("a")],
            sensitivity="low",
            temporal_reference=_SAMPLE_DT,
            metadata={"m": 1},
        )
        d = r.to_dict()
        json.dumps(d)
        r2 = DomainResolutionResource.from_dict(d)
        assert r == r2

    def test_credential_keys_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="Credential"):
            DomainResolutionResource(
                id="r",
                resource_type="f",
                source="s",
                metadata={"token": "secret"},
            )


class TestDomainResolutionEntity:
    def test_valid_minimal(self) -> None:
        e = DomainResolutionEntity(id="e1", entity_type="person", source="nlp")
        assert e.id == "e1"
        assert e.labels == ()

    def test_label_duplicates_dedup(self) -> None:
        with pytest.raises(DomainContractValidationError, match="Duplicate"):
            DomainResolutionEntity(
                id="e1",
                entity_type="person",
                source="nlp",
                labels=["label", "label"],
            )

    def test_confidence_requires_metadata_provenance(self) -> None:
        with pytest.raises(DomainContractValidationError, match="metadata.source"):
            DomainResolutionEntity(
                id="e1",
                entity_type="person",
                source="nlp",
                confidence=0.9,
            )

    def test_confidence_valid_with_metadata_source(self) -> None:
        e = DomainResolutionEntity(
            id="e1",
            entity_type="person",
            source="nlp",
            confidence=0.9,
            metadata={"source": "extractor-v2"},
        )
        assert e.confidence == 0.9

    def test_roundtrip(self) -> None:
        e = DomainResolutionEntity(
            id="e1",
            entity_type="person",
            source="nlp",
            labels=["human", "user"],
            domain_ids=[_domain("a")],
            confidence=0.8,
            metadata={"source": "et-v1"},
        )
        d = e.to_dict()
        json.dumps(d)
        e2 = DomainResolutionEntity.from_dict(d)
        assert e == e2


class TestDomainResolutionKnowledgeItem:
    def test_valid_minimal(self) -> None:
        k = DomainResolutionKnowledgeItem(
            id="k1",
            knowledge_type="fact",
            source="kb",
        )
        assert k.id == "k1"
        assert k.knowledge_type == "fact"

    def test_relevance_validated(self) -> None:
        with pytest.raises(DomainContractValidationError, match="relevance"):
            DomainResolutionKnowledgeItem(
                id="k1",
                knowledge_type="fact",
                source="kb",
                relevance=1.5,
            )

    def test_valid_at_naive_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="timezone"):
            DomainResolutionKnowledgeItem(
                id="k1",
                knowledge_type="fact",
                source="kb",
                valid_at=datetime(2024, 1, 1),  # noqa: DTZ001
            )

    def test_roundtrip(self) -> None:
        k = DomainResolutionKnowledgeItem(
            id="k1",
            knowledge_type="fact",
            source="kb",
            domain_ids=[_domain("a")],
            relevance=0.7,
            valid_at=_SAMPLE_DT,
            provenance={"src": "kb-v1"},
            metadata={"key": "val"},
        )
        d = k.to_dict()
        json.dumps(d)
        k2 = DomainResolutionKnowledgeItem.from_dict(d)
        assert k == k2


class TestDomainResolutionHistoryItem:
    def test_valid_minimal(self) -> None:
        h = DomainResolutionHistoryItem(
            id="h1",
            item_type="response",
            timestamp=_SAMPLE_DT,
        )
        assert h.id == "h1"
        assert h.item_type == "response"
        assert h.timestamp == _SAMPLE_DT

    def test_timestamp_naive_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError, match="timezone"):
            DomainResolutionHistoryItem(
                id="h1",
                item_type="response",
                timestamp=datetime(2024, 1, 1),  # noqa: DTZ001
            )

    def test_roundtrip(self) -> None:
        h = DomainResolutionHistoryItem(
            id="h1",
            item_type="response",
            timestamp=_SAMPLE_DT,
            domain_ids=[_domain("a")],
            summary="User greeted",
            metadata={"key": "val"},
        )
        d = h.to_dict()
        json.dumps(d)
        h2 = DomainResolutionHistoryItem.from_dict(d)
        assert h == h2

    def test_from_dict_with_string_ts(self) -> None:
        d = {
            "id": "h1",
            "item_type": "response",
            "timestamp": "2024-01-15T00:00:00+00:00",
        }
        h = DomainResolutionHistoryItem.from_dict(d)
        assert h.timestamp == _SAMPLE_DT


class TestDomainResolutionEvent:
    def test_valid_minimal(self) -> None:
        e = DomainResolutionEvent(
            id="ev1",
            event_type="kernel.init",
            source="kernel",
            timestamp=_SAMPLE_DT,
        )
        assert e.id == "ev1"
        assert e.event_type == "kernel.init"
        assert e.actor is None

    def test_payload_frozen(self) -> None:
        e = DomainResolutionEvent(
            id="ev1",
            event_type="kernel.init",
            source="kernel",
            timestamp=_SAMPLE_DT,
            payload={"key": "val"},
        )
        with pytest.raises(TypeError):
            e.payload["new"] = "bad"  # type: ignore[index]

    def test_roundtrip(self) -> None:
        e = DomainResolutionEvent(
            id="ev1",
            event_type="kernel.init",
            source="kernel",
            timestamp=_SAMPLE_DT,
            actor="system",
            domain_ids=[_domain("a")],
            payload={"action": "start"},
            metadata={"trace": "abc"},
        )
        d = e.to_dict()
        json.dumps(d)
        e2 = DomainResolutionEvent.from_dict(d)
        assert e == e2
