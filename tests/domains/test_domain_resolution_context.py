"""Phase 10.6 — Tests for DomainResolutionContext invariants."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from cmm.domains.errors import (
    DomainResolutionContextInvalid,
    DomainResolutionContractError,
    DomainResolutionSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionEvent,
    DomainResolutionPolicy,
    DomainResolutionSignal,
)

_SAMPLE_DT = datetime(2024, 1, 15, tzinfo=timezone.utc)


def _domain(slug: str) -> DomainId:
    return DomainId.from_str(f"domain:{slug}")


def _build_id() -> str:
    return "ctx-test-01"


def _basic_signal() -> DomainResolutionSignal:
    return DomainResolutionSignal(kind="explicit_domain", source="user", value="test")


class TestDomainResolutionContext:
    def test_user_input_only_valid(self) -> None:
        ctx = DomainResolutionContext(
            id=_build_id(),
            user_input="Hello world",
            created_at=_SAMPLE_DT,
        )
        assert ctx.user_input == "Hello world"
        assert ctx.id == "ctx-test-01"

    def test_event_only_valid(self) -> None:
        ev = DomainResolutionEvent(
            id="ev1",
            event_type="kernel.init",
            source="kernel",
            timestamp=_SAMPLE_DT,
        )
        ctx = DomainResolutionContext(id=_build_id(), event=ev, created_at=_SAMPLE_DT)
        assert ctx.event == ev

    def test_explicit_domain_only_valid(self) -> None:
        ctx = DomainResolutionContext(
            id=_build_id(),
            explicit_domains=[_domain("a")],
            available_domains=[_domain("a")],
            created_at=_SAMPLE_DT,
        )
        assert len(ctx.explicit_domains) == 1

    def test_empty_context_rejected(self) -> None:
        with pytest.raises(DomainResolutionContextInvalid, match="resolution source"):
            DomainResolutionContext(id=_build_id(), created_at=_SAMPLE_DT)

    def test_explicit_not_available_rejected(self) -> None:
        with pytest.raises(DomainResolutionContextInvalid, match="explicit_domains"):
            DomainResolutionContext(
                id=_build_id(),
                explicit_domains=[_domain("a")],
                available_domains=[_domain("b")],
                created_at=_SAMPLE_DT,
            )

    def test_active_not_available_rejected(self) -> None:
        with pytest.raises(DomainResolutionContextInvalid, match="active_domains"):
            DomainResolutionContext(
                id=_build_id(),
                available_domains=[_domain("b")],
                active_domains=[_domain("a")],
                user_input="hello",
                created_at=_SAMPLE_DT,
            )

    def test_authorized_not_available_rejected(self) -> None:
        with pytest.raises(DomainResolutionContextInvalid, match="authorized_domains"):
            DomainResolutionContext(
                id=_build_id(),
                available_domains=[_domain("b")],
                authorized_domains=[_domain("a")],
                user_input="hello",
                created_at=_SAMPLE_DT,
            )

    def test_explicit_not_authorized_rejected(self) -> None:
        with pytest.raises(DomainResolutionContextInvalid):
            DomainResolutionContext(
                id=_build_id(),
                available_domains=[_domain("a"), _domain("b")],
                authorized_domains=[_domain("b")],
                explicit_domains=[_domain("a")],
                created_at=_SAMPLE_DT,
            )

    def test_policy_denied_as_authorized_rejected(self) -> None:
        policy = DomainResolutionPolicy(denied_domains=[_domain("a")])
        with pytest.raises(DomainResolutionContextInvalid, match="policy-denied"):
            DomainResolutionContext(
                id=_build_id(),
                available_domains=[_domain("a"), _domain("b")],
                authorized_domains=[_domain("a")],
                user_input="hi",
                system_policy=policy,
                created_at=_SAMPLE_DT,
            )

    def test_policy_required_missing_rejected(self) -> None:
        policy = DomainResolutionPolicy(required_domains=[_domain("c")])
        with pytest.raises(DomainResolutionContextInvalid, match="required_domains"):
            DomainResolutionContext(
                id=_build_id(),
                available_domains=[_domain("a")],
                user_input="hi",
                system_policy=policy,
                created_at=_SAMPLE_DT,
            )

    def test_language_valid_bcp47(self) -> None:
        ctx = DomainResolutionContext(
            id=_build_id(),
            language="es",
            user_input="hola",
            created_at=_SAMPLE_DT,
        )
        assert ctx.language == "es"

    def test_language_es_es_valid(self) -> None:
        ctx = DomainResolutionContext(
            id=_build_id(),
            language="es-ES",
            user_input="hola",
            created_at=_SAMPLE_DT,
        )
        assert ctx.language == "es-ES"

    def test_language_und_default(self) -> None:
        ctx = DomainResolutionContext(
            id=_build_id(),
            user_input="hi",
            created_at=_SAMPLE_DT,
        )
        assert ctx.language == "und"

    def test_language_invalid_rejected(self) -> None:
        with pytest.raises(Exception, match="BCP-47"):
            DomainResolutionContext(
                id=_build_id(),
                language="not-valid-!@#",
                user_input="hi",
                created_at=_SAMPLE_DT,
            )

    def test_datetime_naive_rejected(self) -> None:
        with pytest.raises(Exception, match="timezone"):
            DomainResolutionContext(
                id=_build_id(),
                user_input="hi",
                created_at=datetime(2024, 1, 1),  # noqa: DTZ001
            )

    def test_temporal_reference_naive_rejected(self) -> None:
        with pytest.raises(Exception, match="timezone"):
            DomainResolutionContext(
                id=_build_id(),
                user_input="hi",
                temporal_reference=datetime(2024, 1, 1),  # noqa: DTZ001
                created_at=_SAMPLE_DT,
            )

    def test_requested_operations_unique(self) -> None:
        ctx = DomainResolutionContext(
            id=_build_id(),
            user_input="hi",
            requested_operations=["read", "write"],
            created_at=_SAMPLE_DT,
        )
        assert set(ctx.requested_operations) == {"read", "write"}

    def test_requested_operations_duplicates(self) -> None:
        with pytest.raises(Exception, match="Duplicate"):
            DomainResolutionContext(
                id=_build_id(),
                user_input="hi",
                requested_operations=["read", "read"],
                created_at=_SAMPLE_DT,
            )

    def test_permissions_unique(self) -> None:
        ctx = DomainResolutionContext(
            id=_build_id(),
            user_input="hi",
            permissions=["perm-a", "perm-b"],
            created_at=_SAMPLE_DT,
        )
        assert set(ctx.permissions) == {"perm-a", "perm-b"}

    def test_domain_ids_unique(self) -> None:
        with pytest.raises(Exception, match="Duplicate"):
            DomainResolutionContext(
                id=_build_id(),
                user_input="hi",
                available_domains=[_domain("a"), _domain("a")],
                created_at=_SAMPLE_DT,
            )

    def test_nested_immutability(self) -> None:
        ctx = DomainResolutionContext(
            id=_build_id(),
            user_input="hi",
            signals=[_basic_signal()],
            created_at=_SAMPLE_DT,
        )
        with pytest.raises(FrozenInstanceError):
            ctx.signals[0].kind = "bad"  # type: ignore[index]

    def test_metadata_json_safe(self) -> None:
        ctx = DomainResolutionContext(
            id=_build_id(),
            user_input="hi",
            metadata={"key": "val"},
            created_at=_SAMPLE_DT,
        )
        assert dict(ctx.metadata)["key"] == "val"

    def test_metadata_non_json_rejected(self) -> None:
        with pytest.raises(Exception, match="JSON-safe"):
            DomainResolutionContext(
                id=_build_id(),
                user_input="hi",
                metadata={"obj": object()},
                created_at=_SAMPLE_DT,
            )

    def test_secrets_rejected(self) -> None:
        with pytest.raises(Exception, match="Credential"):
            DomainResolutionContext(
                id=_build_id(),
                user_input="hi",
                metadata={"password": "x"},
                created_at=_SAMPLE_DT,
            )

    def test_no_runtime_objects_in_metadata(self) -> None:
        with pytest.raises(Exception, match="JSON-safe"):
            DomainResolutionContext(
                id=_build_id(),
                user_input="hi",
                metadata={"fn": lambda x: x},  # type: ignore[arg-type]
                created_at=_SAMPLE_DT,
            )

    def test_no_resolver_fields_present(self) -> None:
        """Context must NOT contain resolver-specific fields."""
        ctx = DomainResolutionContext(
            id=_build_id(),
            user_input="hi",
            created_at=_SAMPLE_DT,
        )
        # Verify no primary_domain, supporting_domains, confidence_global, etc.
        assert (
            not hasattr(ctx, "primary_domain")
            or getattr(ctx, "primary_domain", None) is None
        )
        d = ctx.to_dict()
        assert "primary_domain" not in d
        assert "supporting_domains" not in d
        assert "resolution_status" not in d
        assert "rejected_domains" not in d

    def test_roundtrip_with_signals(self) -> None:
        ctx = DomainResolutionContext(
            id=_build_id(),
            user_input="Hello world",
            signals=[_basic_signal()],
            created_at=_SAMPLE_DT,
        )
        d = ctx.to_dict()
        json.dumps(d)
        ctx2 = DomainResolutionContext.from_dict(d)
        assert ctx.id == ctx2.id
        assert ctx.user_input == ctx2.user_input
        assert len(ctx2.signals) == 1

    def test_user_preferences_json_safe(self) -> None:
        ctx = DomainResolutionContext(
            id=_build_id(),
            user_input="hi",
            user_preferences={"theme": "dark"},
            created_at=_SAMPLE_DT,
        )
        assert dict(ctx.user_preferences)["theme"] == "dark"

    def test_system_policy_from_mapping(self) -> None:
        ctx = DomainResolutionContext(
            id=_build_id(),
            user_input="hi",
            available_domains=[_domain("x")],
            system_policy={"allowed_domains": [_domain("x")]},
            created_at=_SAMPLE_DT,
        )
        assert ctx.system_policy is not None
        assert len(ctx.system_policy.allowed_domains) == 1

    # ── New: direct nested wrong types rejected ──────────────────────────

    def test_context_direct_nested_wrong_types_rejected(self) -> None:
        """Direct construction with int, object() in nested lists must be rejected."""
        with pytest.raises(DomainResolutionContractError, match="resources"):
            DomainResolutionContext(
                id=_build_id(),
                user_input="hi",
                resources=[123],  # type: ignore[list-item]
                created_at=_SAMPLE_DT,
            )

        with pytest.raises(DomainResolutionContractError, match="signals"):
            DomainResolutionContext(
                id=_build_id(),
                user_input="hi",
                signals=[object()],  # type: ignore[list-item]
                created_at=_SAMPLE_DT,
            )

    def test_context_direct_nested_mappings_coerced(self) -> None:
        """Valid mappings in construction should be coerced to contracts."""
        ctx = DomainResolutionContext(
            id=_build_id(),
            user_input="hi",
            resources=[
                {
                    "id": "r1",
                    "resource_type": "file",
                    "source": "fs",
                }
            ],
            entities=[
                {
                    "id": "e1",
                    "entity_type": "person",
                    "source": "nlp",
                }
            ],
            knowledge_items=[
                {
                    "id": "k1",
                    "knowledge_type": "fact",
                    "source": "kb",
                }
            ],
            created_at=_SAMPLE_DT,
        )
        assert len(ctx.resources) == 1
        assert ctx.resources[0].id == "r1"
        assert len(ctx.entities) == 1
        assert len(ctx.knowledge_items) == 1


class TestNestedResolutionErrorPaths:
    """Tests that nested errors preserve field paths."""

    def test_nested_resolution_error_paths_preserved_resources(self) -> None:
        with pytest.raises(DomainResolutionSerializationError) as exc_info:
            DomainResolutionContext(
                id=_build_id(),
                user_input="hi",
                resources=[
                    {
                        "id": "r1",
                        "resource_type": "file",
                        "source": "fs",
                        "temporal_reference": "2024-01-01T00:00:00",  # naive ISO
                    }
                ],
                created_at=_SAMPLE_DT,
            )
        assert "resources[0]" in exc_info.value.field or "resources" in str(
            exc_info.value.field
        )

    def test_nested_resolution_error_paths_preserved_signals(self) -> None:
        with pytest.raises(DomainResolutionContractError) as exc_info:
            DomainResolutionContext(
                id=_build_id(),
                user_input="hi",
                signals=[
                    {
                        "kind": "t",
                        "source": "s",
                        "value": 1,
                        "confidence": True,  # bool not allowed
                    }
                ],
                created_at=_SAMPLE_DT,
            )
        assert (
            "signals[0]" in exc_info.value.field or "confidence" in exc_info.value.field
        )
