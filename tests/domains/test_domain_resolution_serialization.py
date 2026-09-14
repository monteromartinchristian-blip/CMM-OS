"""Phase 10.6 — Serialization tests for resolution contracts."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cmm.domains.errors import DomainContractValidationError, DomainSerializationError
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionEntity,
    DomainResolutionEvent,
    DomainResolutionHistoryItem,
    DomainResolutionKnowledgeItem,
    DomainResolutionPolicy,
    DomainResolutionResource,
    DomainResolutionSerializationError,
    DomainResolutionSignal,
)

_SAMPLE_DT = datetime(2024, 1, 15, tzinfo=timezone.utc)


def _domain(slug: str) -> DomainId:
    return DomainId.from_str(f"domain:{slug}")


def _basic_signal() -> DomainResolutionSignal:
    return DomainResolutionSignal(kind="entity", source="test", value="hello")


class TestSerialization:
    def test_json_dumps_signal(self) -> None:
        s = _basic_signal()
        d = s.to_dict()
        raw = json.dumps(d)
        assert isinstance(raw, str)
        parsed = json.loads(raw)
        s2 = DomainResolutionSignal.from_dict(parsed)
        assert s == s2

    def test_json_dumps_policy(self) -> None:
        p = DomainResolutionPolicy(
            allowed_domains=[_domain("x")],
            denied_domains=[_domain("y")],
            minimum_confidence=0.5,
        )
        d = p.to_dict()
        raw = json.dumps(d)
        parsed = json.loads(raw)
        p2 = DomainResolutionPolicy.from_dict(parsed)
        assert p == p2

    def test_json_dumps_context(self) -> None:
        ctx = DomainResolutionContext(
            id="ctx-1",
            user_input="Hello world",
            signals=[_basic_signal()],
            created_at=_SAMPLE_DT,
        )
        d = ctx.to_dict()
        raw = json.dumps(d)
        assert isinstance(raw, str)
        parsed = json.loads(raw)
        ctx2 = DomainResolutionContext.from_dict(parsed)
        assert ctx.id == ctx2.id
        assert len(ctx2.signals) == 1

    def test_unknown_fields_rejected(self) -> None:
        with pytest.raises(DomainSerializationError, match="unknown"):
            DomainResolutionContext.from_dict(
                {
                    "id": "x",
                    "created_at": _SAMPLE_DT.isoformat(),
                    "user_input": "hi",
                    "bad_field": True,
                }
            )

    def test_missing_required_fields_rejected(self) -> None:
        with pytest.raises(DomainResolutionSerializationError, match="missing"):
            DomainResolutionContext.from_dict({"id": "x"})

    def test_nested_field_paths_in_error(self) -> None:
        with pytest.raises(Exception, match="DomainResolutionResource"):
            DomainResolutionContext.from_dict(
                {
                    "id": "x",
                    "created_at": _SAMPLE_DT.isoformat(),
                    "user_input": "hi",
                    "resources": [{"id": 123}],
                }
            )

    def test_datetime_always_tz_aware(self) -> None:
        ctx = DomainResolutionContext(
            id="x",
            user_input="hi",
            created_at=_SAMPLE_DT,
        )
        d = ctx.to_dict()
        assert "T" in d["created_at"]
        assert "+" in d["created_at"] or "Z" in d["created_at"]

    def test_bool_strict_signal_from_dict(self) -> None:
        with pytest.raises(DomainContractValidationError, match="confidence"):
            DomainResolutionSignal.from_dict(
                {"kind": "t", "source": "s", "value": 1, "confidence": True}
            )

    def test_bool_strict_policy_from_dict(self) -> None:
        with pytest.raises(DomainResolutionSerializationError):
            DomainResolutionPolicy.from_dict({"allow_disabled": 1})

    def test_nan_rejected_signal_from_dict(self) -> None:
        with pytest.raises(Exception, match="finite"):
            DomainResolutionSignal.from_dict(
                {"kind": "t", "source": "s", "value": 1, "confidence": float("nan")}
            )

    def test_infinity_rejected_signal(self) -> None:
        with pytest.raises(Exception, match="finite"):
            DomainResolutionSignal.from_dict(
                {"kind": "t", "source": "s", "value": 1, "confidence": float("inf")}
            )

    def test_mapping_keys_json_only(self) -> None:
        """Keys must be strings for JSON safety."""
        with pytest.raises(Exception, match="keys must be strings"):
            DomainResolutionSignal(
                kind="t",
                source="s",
                value=1,
                metadata={1: "val"},  # type: ignore[dict-item]
            )

    def test_deep_roundtrip_context_full(self) -> None:
        ctx = DomainResolutionContext(
            id="ctx-deep",
            user_input="Hello world",
            objective="Greet",
            available_domains=[_domain("a"), _domain("b")],
            active_domains=[_domain("a")],
            authorized_domains=[_domain("a"), _domain("b")],
            signals=[_basic_signal()],
            resources=[
                DomainResolutionResource(
                    id="r1",
                    resource_type="file",
                    source="fs",
                ),
            ],
            entities=[
                DomainResolutionEntity(
                    id="e1",
                    entity_type="person",
                    source="nlp",
                ),
            ],
            knowledge_items=[
                DomainResolutionKnowledgeItem(
                    id="k1",
                    knowledge_type="fact",
                    source="kb",
                ),
            ],
            recent_history=[
                DomainResolutionHistoryItem(
                    id="h1",
                    item_type="response",
                    timestamp=_SAMPLE_DT,
                ),
            ],
            kernel_events=[
                DomainResolutionEvent(
                    id="ev1",
                    event_type="kernel.init",
                    source="kernel",
                    timestamp=_SAMPLE_DT,
                ),
            ],
            language="es",
            metadata={"build": "phase-10.6"},
            created_at=_SAMPLE_DT,
        )
        d = ctx.to_dict()
        raw = json.dumps(d)
        parsed = json.loads(raw)
        ctx2 = DomainResolutionContext.from_dict(parsed)
        assert ctx2.id == "ctx-deep"
        assert ctx2.user_input == "Hello world"
        assert ctx2.language == "es"
        assert len(ctx2.signals) == 1
        assert len(ctx2.resources) == 1
        assert len(ctx2.entities) == 1
        assert len(ctx2.knowledge_items) == 1
        assert len(ctx2.recent_history) == 1
        assert len(ctx2.kernel_events) == 1

    def test_serialization_order_stable(self) -> None:
        ctx = DomainResolutionContext(
            id="x",
            user_input="hi",
            available_domains=[_domain("a"), _domain("b")],
            created_at=_SAMPLE_DT,
        )
        d1 = json.dumps(ctx.to_dict(), sort_keys=True)
        d2 = json.dumps(ctx.to_dict(), sort_keys=True)
        assert d1 == d2

    # ── Naive datetime from_dict tests ───────────────────────────────────

    def test_all_from_dict_naive_datetimes_rejected(self) -> None:
        """Every contract's from_dict must reject naive ISO datetime strings."""
        naive_iso = "2024-01-15T00:00:00"

        # Signal.observed_at
        with pytest.raises(DomainResolutionSerializationError, match="timezone-aware"):
            DomainResolutionSignal.from_dict(
                {"kind": "t", "source": "s", "value": 1, "observed_at": naive_iso}
            )

        # Context.created_at
        with pytest.raises(DomainResolutionSerializationError, match="timezone-aware"):
            DomainResolutionContext.from_dict(
                {"id": "x", "created_at": naive_iso, "user_input": "hi"}
            )

        # Context.temporal_reference
        with pytest.raises(DomainResolutionSerializationError, match="timezone-aware"):
            DomainResolutionContext.from_dict(
                {
                    "id": "x",
                    "created_at": _SAMPLE_DT.isoformat(),
                    "user_input": "hi",
                    "temporal_reference": naive_iso,
                }
            )

        # Resource.temporal_reference
        with pytest.raises(DomainResolutionSerializationError, match="timezone-aware"):
            DomainResolutionResource.from_dict(
                {
                    "id": "r1",
                    "resource_type": "file",
                    "source": "fs",
                    "temporal_reference": naive_iso,
                }
            )

        # KnowledgeItem.valid_at
        with pytest.raises(DomainResolutionSerializationError, match="timezone-aware"):
            DomainResolutionKnowledgeItem.from_dict(
                {
                    "id": "k1",
                    "knowledge_type": "fact",
                    "source": "kb",
                    "valid_at": naive_iso,
                }
            )

        # HistoryItem.timestamp
        with pytest.raises(DomainResolutionSerializationError, match="timezone-aware"):
            DomainResolutionHistoryItem.from_dict(
                {
                    "id": "h1",
                    "item_type": "msg",
                    "timestamp": naive_iso,
                }
            )

        # Event.timestamp
        with pytest.raises(DomainResolutionSerializationError, match="timezone-aware"):
            DomainResolutionEvent.from_dict(
                {
                    "id": "ev1",
                    "event_type": "kernel.init",
                    "source": "kernel",
                    "timestamp": naive_iso,
                }
            )
