"""Provider inventory projection contract (Plan 4 Task 1).

Snapshots are the provider-independent boundary CMM Usage (and later
CMMChat) consume: primitive-serializable, deterministic, and free of
secrets, isolation profile paths, and raw external config metadata.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone

import pytest

from kernel.llm.model_routes import (
    CapabilityConfidence,
    ModelRoute,
    RouteCapabilityState,
)
from kernel.llm.provider_candidates import ProviderCandidate
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
)
from kernel.llm.provider_events import (
    MODEL_AVAILABLE,
    MODEL_CAPABILITIES_CHANGED,
    MODEL_DISCOVERED,
    MODEL_UNAVAILABLE,
    PROVIDER_CONNECTED,
    PROVIDER_DETECTED,
    PROVIDER_DISCONNECTED,
    PROVIDER_EVENT_NAMES,
    PROVIDER_VALIDATION_CHANGED,
    ProviderInventorySnapshot,
    build_inventory_snapshot,
    connection_snapshot_from_connection,
    connection_snapshot_from_proposal,
    route_snapshot_from_route,
)
from kernel.llm.provider_onboarding import ConnectionProposal

T0 = datetime(2026, 9, 13, 10, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def _connection(**overrides: object) -> ProviderConnection:
    kwargs: dict[str, object] = {
        "connection_id": "qwen-token-plan:main",
        "provider_id": "qwen-token-plan",
        "display_name": "Qwen Token Plan",
        "billing_class": BillingClass.SUBSCRIPTION,
        "credential_ref": "keychain://cmm/qwen-token-plan/main",
        "endpoint": "https://token-plan.example.invalid/v1",
        "isolation_profile_ref": "/tmp/cmm-profiles/qwen-token-plan",
        "status": ConnectionStatus.CONNECTED,
        "created_at": T0,
        "last_validated_at": T1,
    }
    kwargs.update(overrides)
    return ProviderConnection(**kwargs)  # type: ignore[arg-type]


def _route(**overrides: object) -> ModelRoute:
    kwargs: dict[str, object] = {
        "route_id": "qwen-token-plan:qwen3.8-max",
        "connection_id": "qwen-token-plan:main",
        "provider_model_id": "qwen3.8-max",
        "canonical_model_id": "qwen3.8-max",
        "available": True,
        "first_seen_at": T0,
        "last_seen_at": T1,
        "capabilities": (
            RouteCapabilityState(
                name="tools",
                supported=True,
                confidence=CapabilityConfidence.VERIFIED,
            ),
            RouteCapabilityState(
                name="vision",
                supported=False,
                confidence=CapabilityConfidence.DISCOVERED,
            ),
        ),
    }
    kwargs.update(overrides)
    return ModelRoute(**kwargs)  # type: ignore[arg-type]


def _candidate() -> ProviderCandidate:
    return ProviderCandidate(
        provider_id="codex",
        source="codex-home",
        detected=True,
        auth_available=True,
        external_config_present=True,
        external_endpoint_override_present=True,
        risks=(),
        metadata=(("codex_home", "/Users/someone/.codex"),),
    )


def test_connection_snapshot_includes_public_identity() -> None:
    snapshot = connection_snapshot_from_connection(_connection())

    assert snapshot.connection_id == "qwen-token-plan:main"
    assert snapshot.provider_id == "qwen-token-plan"
    assert snapshot.display_name == "Qwen Token Plan"
    assert snapshot.billing_class == "subscription"
    assert snapshot.status == "connected"
    assert snapshot.connected is True
    assert snapshot.last_validated_at == T1.isoformat()
    assert snapshot.created_at == T0.isoformat()

    payload = snapshot.to_dict()
    assert payload["connection_id"] == "qwen-token-plan:main"
    assert payload["billing_class"] == "subscription"
    assert payload["status"] == "connected"


def test_proposal_snapshot_built_from_real_candidate_chain() -> None:
    proposal = ConnectionProposal(
        provider_id="codex",
        display_name="Codex",
        billing_class=BillingClass.SUBSCRIPTION,
        endpoint="https://api.openai.com/v1",
        account="main",
        source_home=_candidate().metadata[0][1],
        requires_isolation=True,
    )
    snapshot = connection_snapshot_from_proposal(proposal)

    assert snapshot.connection_id == "codex:main"
    assert snapshot.provider_id == "codex"
    assert snapshot.display_name == "Codex"
    assert snapshot.billing_class == "subscription"
    assert snapshot.status == "detected"
    assert snapshot.connected is False


def test_route_snapshot_includes_ids_and_capabilities() -> None:
    snapshot = route_snapshot_from_route(_route(), provider_id="qwen-token-plan")

    assert snapshot.route_id == "qwen-token-plan:qwen3.8-max"
    assert snapshot.connection_id == "qwen-token-plan:main"
    assert snapshot.provider_id == "qwen-token-plan"
    assert snapshot.provider_model_id == "qwen3.8-max"
    assert snapshot.canonical_model_id == "qwen3.8-max"
    assert snapshot.available is True
    assert snapshot.first_seen_at == T0.isoformat()
    assert snapshot.last_seen_at == T1.isoformat()

    capabilities = {c["name"]: c for c in snapshot.to_dict()["capabilities"]}
    assert capabilities["tools"] == {
        "name": "tools",
        "supported": True,
        "confidence": "verified",
    }
    assert capabilities["vision"]["supported"] is False


def test_inventory_snapshot_joins_connections_and_routes() -> None:
    inventory = build_inventory_snapshot((_connection(),), (_route(),))

    assert inventory.generated_at is not None
    assert len(inventory.connections) == 1
    assert len(inventory.routes) == 1
    assert inventory.routes[0].provider_id == "qwen-token-plan"
    payload = inventory.to_dict()
    assert payload["connections"][0]["connection_id"] == "qwen-token-plan:main"
    assert payload["routes"][0]["route_id"] == "qwen-token-plan:qwen3.8-max"


def _all_keys(payload: object) -> list[str]:
    keys: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.append(str(key))
            keys.extend(_all_keys(value))
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            keys.extend(_all_keys(item))
    return keys


def test_snapshots_exclude_secrets_and_internals() -> None:
    inventory = build_inventory_snapshot((_connection(),), (_route(),))
    payload = inventory.to_dict()
    lowered = [key.lower() for key in _all_keys(payload)]
    forbidden = (
        "credential_ref",
        "credential",
        "api_key",
        "apikey",
        "secret",
        "password",
        "bearer",
        "isolation",
        "profile",
        "endpoint",
        "metadata",
        "source_home",
    )
    for key in lowered:
        assert not any(marker in key for marker in forbidden), key
    dumped = json.dumps(payload)
    assert "keychain://" not in dumped
    assert "/tmp/cmm-profiles" not in dumped
    assert "/Users/someone/.codex" not in dumped


def test_event_name_constants_match_contract() -> None:
    assert PROVIDER_DETECTED == "provider.detected"
    assert PROVIDER_CONNECTED == "provider.connected"
    assert PROVIDER_DISCONNECTED == "provider.disconnected"
    assert PROVIDER_VALIDATION_CHANGED == "provider.validation_changed"
    assert MODEL_DISCOVERED == "model.discovered"
    assert MODEL_AVAILABLE == "model.available"
    assert MODEL_UNAVAILABLE == "model.unavailable"
    assert MODEL_CAPABILITIES_CHANGED == "model.capabilities_changed"
    assert tuple(sorted(PROVIDER_EVENT_NAMES)) == (
        "model.available",
        "model.capabilities_changed",
        "model.discovered",
        "model.unavailable",
        "provider.connected",
        "provider.detected",
        "provider.disconnected",
        "provider.validation_changed",
    )


def test_snapshots_are_frozen_and_json_round_trippable() -> None:
    inventory = build_inventory_snapshot((_connection(),), (_route(),))
    for snapshot in (
        *inventory.connections,
        *inventory.routes,
        inventory,
    ):
        with pytest.raises(dataclasses.FrozenInstanceError):
            snapshot.provider_id = "mutated"  # type: ignore[misc]
    restored = ProviderInventorySnapshot.from_dict(
        json.loads(json.dumps(inventory.to_dict()))
    )
    assert restored == inventory
