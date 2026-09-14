"""Contract tests for the versioned provider registry state envelope (MAJOR-02).

The persisted aggregate is the durable boundary of the Provider Registry, so
the contract under test is deliberately strict:

* deterministic serialization (two equal states serialize to equal mappings,
  and the persisted collection order is canonical, not insertion order);
* an exact round trip through ``to_dict``/``from_dict`` and through JSON;
* no raw secret material — only opaque ``keychain://`` refs cross the boundary;
* fail-closed validation: an unsupported schema version, a malformed payload,
  a missing/unknown field, a negative revision or a naive timestamp rejects the
  whole payload instead of producing partial state.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from kernel.llm.capabilities import ModelCapabilities, ProviderCapabilities
from kernel.llm.model_catalog import ModelSpec
from kernel.llm.model_routes import (
    CapabilityConfidence,
    ModelRoute,
    RouteCapabilityState,
)
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
)
from kernel.llm.provider_manifests import ProviderManifest
from kernel.llm.provider_registry import ProviderSpec
from kernel.llm.provider_state import (
    SCHEMA_VERSION,
    ProviderRegistryAuditRecord,
    ProviderRegistryState,
    ProviderStateError,
    ProviderStateSchemaError,
    ProviderStateSerializationError,
)

T0 = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)

_SAFE_REF = "keychain://cmm/providers/qwen-token-plan/main"


def _provider(provider_id: str, *, base_url: str) -> ProviderSpec:
    return ProviderSpec(
        id=provider_id,
        provider_type="remote",
        api_style="chat_completions",
        api_key_env=f"{provider_id.upper().replace('-', '_')}_API_KEY",
        base_url=base_url,
        region="sea",
        data_policy="standard",
        availability="available",
        capabilities=ProviderCapabilities(chat_completions=True, streaming=True),
    )


def _manifest(
    provider_id: str, *, billing: BillingClass, base_url: str
) -> ProviderManifest:
    return ProviderManifest(
        provider_id=provider_id,
        display_name=provider_id,
        billing_class=billing,
        default_base_url=base_url,
        auth_scheme="bearer",
        activation_allowlist=("qwen3.8-max",),
    )


def _model(provider_id: str) -> ModelSpec:
    return ModelSpec(
        id="qwen3.8-max",
        provider_id=provider_id,
        context_window=131072,
        capabilities=ModelCapabilities(reasoning=True, tool_calling=True),
        aliases=("qwen-max",),
        input_cost_per_million=Decimal("1.25"),
        output_cost_per_million=Decimal("5.00"),
        availability="available",
        version="2026-09",
    )


def _connection(provider_id: str, *, status: ConnectionStatus) -> ProviderConnection:
    return ProviderConnection(
        connection_id=f"{provider_id}:main",
        provider_id=provider_id,
        display_name=provider_id,
        billing_class=BillingClass.SUBSCRIPTION,
        credential_ref=_SAFE_REF,
        endpoint="https://token-plan.example.invalid/v1",
        isolation_profile_ref="/tmp/cmm-profiles/qwen-token-plan",
        status=status,
        created_at=T0,
        last_validated_at=T1,
    )


def _route(connection_id: str, *, available: bool) -> ModelRoute:
    return ModelRoute(
        route_id=f"{connection_id}:qwen3.8-max",
        connection_id=connection_id,
        provider_model_id="qwen3.8-max",
        canonical_model_id="qwen3.8-max",
        available=available,
        first_seen_at=T0,
        last_seen_at=T1,
        capabilities=(
            RouteCapabilityState(
                name="tools",
                supported=True,
                confidence=CapabilityConfidence.VERIFIED,
            ),
        ),
    )


def _audit(revision: int = 1) -> ProviderRegistryAuditRecord:
    return ProviderRegistryAuditRecord(
        revision=revision,
        event_type="provider.connected",
        entity_kind="connection",
        entity_id="qwen-token-plan:main",
        occurred_at=T1,
        detail=(("status", "connected"),),
    )


def _state() -> ProviderRegistryState:
    """Build the canonical two-provider aggregate used across these tests."""
    return ProviderRegistryState(
        schema_version=SCHEMA_VERSION,
        revision=7,
        providers=(
            _provider(
                "qwen-token-plan",
                base_url="https://token-plan.example.invalid/v1",
            ),
            _provider("qwen-cloud", base_url="https://qwen-cloud.example.invalid/v1"),
        ),
        manifests=(
            _manifest(
                "qwen-token-plan",
                billing=BillingClass.SUBSCRIPTION,
                base_url="https://token-plan.example.invalid/v1",
            ),
            _manifest(
                "qwen-cloud",
                billing=BillingClass.PAYG,
                base_url="https://qwen-cloud.example.invalid/v1",
            ),
        ),
        models=(_model("qwen-token-plan"), _model("qwen-cloud")),
        connections=(
            _connection("qwen-token-plan", status=ConnectionStatus.CONNECTED),
        ),
        routes=(_route("qwen-token-plan:main", available=False),),
        audit_log=(_audit(),),
    )


def _payload(**overrides: object) -> dict[str, object]:
    """Return a serialized state with ``overrides`` applied on the mapping."""
    payload = _state().to_dict()
    payload.update(overrides)
    return payload


def test_state_round_trips_exactly_through_json() -> None:
    state = _state()

    serialized = state.to_dict()
    restored = ProviderRegistryState.from_dict(json.loads(json.dumps(serialized)))

    assert restored == state
    assert ProviderRegistryState.from_dict(serialized) == state


def test_serialization_is_deterministic_regardless_of_input_order() -> None:
    state = _state()
    reordered = ProviderRegistryState(
        schema_version=state.schema_version,
        revision=state.revision,
        providers=tuple(reversed(state.providers)),
        manifests=tuple(reversed(state.manifests)),
        models=tuple(reversed(state.models)),
        connections=state.connections,
        routes=state.routes,
        audit_log=state.audit_log,
    )

    assert state.to_dict() == state.to_dict()
    assert reordered.to_dict() == state.to_dict()


def test_serialized_collections_are_canonically_ordered() -> None:
    payload = _state().to_dict()

    assert [item["id"] for item in payload["providers"]] == [
        "qwen-cloud",
        "qwen-token-plan",
    ]
    assert [item["qualified_id"] for item in payload["models"]] == [
        "qwen-cloud:qwen3.8-max",
        "qwen-token-plan:qwen3.8-max",
    ]
    assert [item["connection_id"] for item in payload["connections"]] == [
        "qwen-token-plan:main"
    ]
    assert [item["route_id"] for item in payload["routes"]] == [
        "qwen-token-plan:main:qwen3.8-max"
    ]


def test_capability_and_timestamp_state_survives_round_trip() -> None:
    state = _state()

    restored = ProviderRegistryState.from_dict(state.to_dict())

    route = restored.routes[0]
    assert route.available is False
    assert route.first_seen_at == T0
    assert route.last_seen_at == T1
    assert route.capabilities[0].confidence is CapabilityConfidence.VERIFIED
    assert restored.models[1].context_window == 131072
    assert restored.models[1].input_cost_per_million == Decimal("1.25")
    assert restored.models[1].capabilities.reasoning is True
    assert restored.providers[0].capabilities.streaming is True
    assert restored.connections[0].status is ConnectionStatus.CONNECTED
    assert restored.connections[0].credential_ref == _SAFE_REF


def test_state_is_immutable() -> None:
    state = _state()

    with pytest.raises(AttributeError):
        state.revision = 8  # type: ignore[misc]
    with pytest.raises(AttributeError):
        state.providers[0].base_url = "https://mutated.invalid/v1"  # type: ignore[misc]


@pytest.mark.parametrize(
    "secret",
    [
        "keychain://cmm/providers/deepseek/sk-live-abc123",
        "keychain://cmm/providers/deepseek/api-key-abc",
        "keychain://cmm/providers/deepseek/password=abc",
        "keychain://cmm/providers/deepseek/token=abc",
        "keychain://cmm/providers/deepseek/Bearer-abc",
    ],
)
def test_from_dict_rejects_secret_shaped_credential_refs(secret: str) -> None:
    payload = _state().to_dict()
    payload["connections"][0]["credential_ref"] = secret  # type: ignore[index]
    payload["audit_log"] = []

    with pytest.raises(ProviderStateSerializationError, match="credential_ref"):
        ProviderRegistryState.from_dict(payload)


def test_from_dict_accepts_an_opaque_keychain_ref() -> None:
    state = ProviderRegistryState.from_dict(_state().to_dict())

    assert state.connections[0].credential_ref == _SAFE_REF


@pytest.mark.parametrize(
    "detail",
    [
        ("api_key", "sk-live-abc"),
        ("note", "token=abc"),
        ("note", "Bearer abc"),
    ],
)
def test_from_dict_rejects_secret_shaped_audit_detail(
    detail: tuple[str, str],
) -> None:
    payload = _state().to_dict()
    payload["audit_log"][0]["detail"] = [list(detail)]  # type: ignore[index]

    with pytest.raises(ProviderStateSerializationError, match="audit"):
        ProviderRegistryState.from_dict(payload)


def test_from_dict_rejects_unsupported_schema_version() -> None:
    with pytest.raises(ProviderStateSchemaError, match="unsupported schema_version"):
        ProviderRegistryState.from_dict(_payload(schema_version="999"))


def test_construction_rejects_unsupported_schema_version() -> None:
    with pytest.raises(ProviderStateSchemaError, match="unsupported schema_version"):
        ProviderRegistryState(
            schema_version="999",
            revision=1,
            providers=(),
            manifests=(),
            models=(),
            connections=(),
            routes=(),
        )


@pytest.mark.parametrize("revision", [-1, -100])
def test_negative_revision_is_rejected(revision: int) -> None:
    with pytest.raises(ProviderStateError, match="revision"):
        ProviderRegistryState.from_dict(_payload(revision=revision))


def test_naive_audit_timestamp_is_rejected() -> None:
    payload = _state().to_dict()
    naive = datetime(2026, 9, 14, 12, 0)  # noqa: DTZ001
    payload["audit_log"][0]["occurred_at"] = naive.isoformat()  # type: ignore[index]

    with pytest.raises(ProviderStateError, match="timezone-aware"):
        ProviderRegistryState.from_dict(payload)


def test_missing_required_field_is_rejected() -> None:
    payload = _state().to_dict()
    del payload["routes"]

    with pytest.raises(ProviderStateSerializationError, match="routes"):
        ProviderRegistryState.from_dict(payload)


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ProviderStateSerializationError, match="unknown field"):
        ProviderRegistryState.from_dict(_payload(unexpected="value"))


def test_non_mapping_payload_is_rejected() -> None:
    with pytest.raises(ProviderStateSerializationError):
        ProviderRegistryState.from_dict([])  # type: ignore[arg-type]


def test_audit_record_rejects_blank_and_naive_values() -> None:
    with pytest.raises(ProviderStateError, match="event_type"):
        ProviderRegistryAuditRecord(
            revision=1,
            event_type="   ",
            entity_kind="connection",
            entity_id="qwen-token-plan:main",
            occurred_at=T1,
        )
    with pytest.raises(ProviderStateError, match="timezone-aware"):
        ProviderRegistryAuditRecord(
            revision=1,
            event_type="provider.connected",
            entity_kind="connection",
            entity_id="qwen-token-plan:main",
            occurred_at=datetime(2026, 9, 14, 12, 0),  # noqa: DTZ001
        )
    with pytest.raises(ProviderStateError, match="revision"):
        ProviderRegistryAuditRecord(
            revision=-1,
            event_type="provider.connected",
            entity_kind="connection",
            entity_id="qwen-token-plan:main",
            occurred_at=T1,
        )


def test_audit_records_serialize_deterministically() -> None:
    state = ProviderRegistryState(
        schema_version=SCHEMA_VERSION,
        revision=2,
        providers=(),
        manifests=(),
        models=(),
        connections=(),
        routes=(),
        audit_log=(_audit(2), _audit(1)),
    )

    payload = state.to_dict()

    assert [record["revision"] for record in payload["audit_log"]] == [1, 2]
    assert ProviderRegistryState.from_dict(payload) == state
