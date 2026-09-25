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

import dataclasses
import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from kernel.llm.capabilities import (
    ModelCapabilities,
    ProviderCapabilities,
    ReasoningEffort,
)
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


# --- manifest isolation policy in the persisted shape (MAJOR-V2-03) ---------


def _codex_state(*, requires_isolation: bool) -> ProviderRegistryState:
    """Build a one-provider aggregate carrying an explicit manifest policy."""
    manifest = dataclasses.replace(
        _manifest(
            "codex",
            billing=BillingClass.SUBSCRIPTION,
            base_url="https://api.openai.com/v1",
        ),
        requires_isolation=requires_isolation,
    )
    return ProviderRegistryState(
        schema_version=SCHEMA_VERSION,
        revision=1,
        providers=(_provider("codex", base_url="https://api.openai.com/v1"),),
        manifests=(manifest,),
        models=(),
        connections=(),
        routes=(),
    )


def test_manifest_isolation_policy_survives_the_persistence_round_trip() -> None:
    """The canonical isolation policy is persisted, not recomputed on load."""
    isolated = _codex_state(requires_isolation=True)
    default = _codex_state(requires_isolation=False)

    payload = isolated.to_dict()
    restored = ProviderRegistryState.from_dict(json.loads(json.dumps(payload)))

    assert payload["manifests"][0]["requires_isolation"] is True
    assert restored.manifests[0].requires_isolation is True
    assert restored == isolated
    # The default policy round-trips too, and the two states stay distinct.
    loaded_default = ProviderRegistryState.from_dict(default.to_dict())
    assert loaded_default.manifests[0].requires_isolation is False
    assert loaded_default != isolated


def test_a_manifest_payload_without_the_isolation_policy_is_rejected() -> None:
    """A missing policy field fails closed instead of defaulting silently."""
    payload = _codex_state(requires_isolation=True).to_dict()
    del payload["manifests"][0]["requires_isolation"]  # type: ignore[index]

    with pytest.raises(ProviderStateSerializationError, match="requires_isolation"):
        ProviderRegistryState.from_dict(payload)


def test_an_unknown_manifest_field_is_rejected() -> None:
    payload = _codex_state(requires_isolation=True).to_dict()
    payload["manifests"][0]["requires_isolations"] = True  # type: ignore[index]

    with pytest.raises(ProviderStateSerializationError, match="unknown field"):
        ProviderRegistryState.from_dict(payload)


def test_the_previous_manifest_shape_version_is_rejected() -> None:
    """The manifest shape changed, so the previous envelope version fails closed.

    ``SCHEMA_VERSION`` identifies exactly one persisted shape: a document
    written before the isolation-policy field existed is rejected by version
    instead of being loaded with an assumed policy.
    """
    payload = _codex_state(requires_isolation=True).to_dict()
    payload["schema_version"] = "1"

    assert payload["schema_version"] != SCHEMA_VERSION
    with pytest.raises(ProviderStateSchemaError, match="unsupported schema_version"):
        ProviderRegistryState.from_dict(payload)


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


# --- review follow-ups: persistence-boundary secret guard totality ----------


def _state_with(
    *,
    endpoint: str | None = None,
    display_name: str | None = None,
    isolation_profile_ref: str | None = None,
    base_url: str | None = None,
    data_policy: str | None = None,
    model_version: str | None = None,
) -> ProviderRegistryState:
    """Build a one-connection aggregate with the given free-text overrides."""
    connection = ProviderConnection(
        connection_id="deepseek:main",
        provider_id="deepseek",
        display_name=display_name or "DeepSeek API",
        billing_class=BillingClass.PAYG,
        credential_ref=_SAFE_REF,
        endpoint=endpoint or "https://api.deepseek.com/v1",
        isolation_profile_ref=isolation_profile_ref,
        status=ConnectionStatus.CONNECTED,
    )
    provider = ProviderSpec(
        id="deepseek",
        provider_type="remote",
        api_style="chat_completions",
        base_url=base_url or "https://api.deepseek.com/v1",
        data_policy=data_policy,
    )
    model = ModelSpec(
        id="deepseek-chat",
        provider_id="deepseek",
        version=model_version,
    )
    return ProviderRegistryState(
        schema_version=SCHEMA_VERSION,
        revision=1,
        providers=(provider,),
        manifests=(),
        models=(model,),
        connections=(connection,),
        routes=(),
        audit_log=(),
    )


@pytest.mark.parametrize(
    ("field", "value", "payload_key"),
    [
        ("endpoint", "https://api.deepseek.com/v1?token=sk-live-abc123", "endpoint"),
        ("display_name", "Provider sk-live-abc123", "display_name"),
        ("isolation_profile_ref", "/tmp/password=hunter2", "isolation_profile_ref"),
        ("base_url", "https://api.deepseek.com/v1?api-key=x", "base_url"),
        ("data_policy", "policy token=abc", "data_policy"),
        ("model_version", "Bearer v1", "version"),
    ],
)
def test_to_dict_rejects_secret_shaped_text_in_any_persisted_field(
    field: str, value: str, payload_key: str
) -> None:
    """The write boundary refuses to emit secret-shaped text, not just refs."""
    state = _state_with(**{field: value})

    with pytest.raises(
        ProviderStateSerializationError,
        match="must not carry plaintext secrets",
    ) as excinfo:
        state.to_dict()
    # The path names the offending field; the secret value is never echoed.
    assert payload_key in str(excinfo.value)
    assert value not in str(excinfo.value)


def test_from_dict_rejects_secret_shaped_text_in_any_persisted_field() -> None:
    """The read boundary rejects a hand-edited file smuggling text secrets."""
    payload = _state_with().to_dict()
    payload["connections"][0]["endpoint"] = (  # type: ignore[index]
        "https://api.deepseek.com/v1?token=sk-live-abc123"
    )

    with pytest.raises(
        ProviderStateSerializationError, match="must not carry plaintext secrets"
    ) as excinfo:
        ProviderRegistryState.from_dict(payload)
    assert "endpoint" in str(excinfo.value)
    assert "sk-live-abc123" not in str(excinfo.value)


def test_the_bearer_auth_scheme_value_is_the_documented_exemption() -> None:
    """The only marker-shaped domain value is the pinned auth scheme."""
    payload = _state().to_dict()

    assert payload["manifests"][0]["auth_scheme"] == "bearer"
    assert ProviderRegistryState.from_dict(payload) == _state()


def test_from_dict_rejects_a_non_finite_cost() -> None:
    """A NaN cost is corruption and must fail with the typed error."""
    payload = _state().to_dict()
    payload["models"][0]["input_cost_per_million"] = "NaN"  # type: ignore[index]

    with pytest.raises(ProviderStateSerializationError, match="finite"):
        ProviderRegistryState.from_dict(payload)


def test_blank_optional_text_round_trips() -> None:
    """Constructible blanks (region/version) must survive the round trip."""
    provider = ProviderSpec(
        id="deepseek",
        provider_type="remote",
        api_style="chat_completions",
        base_url="https://api.deepseek.com/v1",
        region="",
        data_policy="",
    )
    model = ModelSpec(id="deepseek-chat", provider_id="deepseek", version="")
    state = ProviderRegistryState(
        schema_version=SCHEMA_VERSION,
        revision=1,
        providers=(provider,),
        manifests=(),
        models=(model,),
        connections=(),
        routes=(),
    )

    assert ProviderRegistryState.from_dict(state.to_dict()) == state


# ── Remediation V1 MAJOR-05 — the Phase 11.21 capability fields are persisted
#    by the existing Phase 11.34 state owner.
#
# ``ModelCapabilities`` gained ``reasoning_efforts``, ``document_media_types`` and
# ``streaming`` in Phase 11.21.  The closed Phase 11.34 persisted-state aggregate
# claims to reconstruct accepted canonical model entries exactly, so the v3 shape
# must carry those fields explicitly instead of silently rebuilding them from
# their fail-closed defaults.


def _phase11_capabilities() -> ModelCapabilities:
    return ModelCapabilities(
        reasoning=True,
        reasoning_efforts=(ReasoningEffort.HIGH, ReasoningEffort.EXTRA_HIGH),
        document_media_types=("application/pdf", "text/plain"),
        streaming=True,
    )


def _phase11_model(provider_id: str) -> ModelSpec:
    return ModelSpec(
        id="phase11-model",
        provider_id=provider_id,
        context_window=131072,
        capabilities=_phase11_capabilities(),
        availability="available",
    )


def _phase11_state() -> ProviderRegistryState:
    return ProviderRegistryState(
        schema_version=SCHEMA_VERSION,
        revision=3,
        providers=(_provider("local", base_url="http://127.0.0.1:11434/v1"),),
        manifests=(),
        models=(_phase11_model("local"),),
        connections=(),
        routes=(),
    )


def test_the_persisted_schema_is_version_three() -> None:
    """The changed persisted capability shape identifies exactly one version."""
    assert SCHEMA_VERSION == "3"


def test_phase11_capabilities_survive_the_persistence_round_trip() -> None:
    state = _phase11_state()

    payload = state.to_dict()
    restored = ProviderRegistryState.from_dict(json.loads(json.dumps(payload)))

    capabilities = payload["models"][0]["capabilities"]  # type: ignore[index]
    assert capabilities["reasoning_efforts"] == ["high", "extra_high"]
    assert capabilities["document_media_types"] == ["application/pdf", "text/plain"]
    assert capabilities["streaming"] is True

    assert restored.models[0].capabilities.reasoning_efforts == (
        ReasoningEffort.HIGH,
        ReasoningEffort.EXTRA_HIGH,
    )
    assert restored.models[0].capabilities.document_media_types == (
        "application/pdf",
        "text/plain",
    )
    assert restored.models[0].capabilities.streaming is True
    assert restored == state


def test_the_version_two_capability_shape_is_rejected() -> None:
    """A pre-remediation document is rejected by version, never defaulted."""
    payload = _phase11_state().to_dict()
    payload["schema_version"] = "2"

    with pytest.raises(ProviderStateSchemaError, match="unsupported schema_version"):
        ProviderRegistryState.from_dict(payload)


@pytest.mark.parametrize(
    "field",
    ["reasoning_efforts", "document_media_types", "streaming"],
)
def test_a_missing_phase11_capability_key_is_rejected(field: str) -> None:
    payload = _phase11_state().to_dict()
    del payload["models"][0]["capabilities"][field]  # type: ignore[index]

    with pytest.raises(ProviderStateSerializationError, match=field):
        ProviderRegistryState.from_dict(payload)


def test_an_unknown_phase11_capability_key_is_rejected() -> None:
    payload = _phase11_state().to_dict()
    payload["models"][0]["capabilities"]["reasoning_effort"] = ["high"]  # type: ignore[index]

    with pytest.raises(ProviderStateSerializationError, match="unknown field"):
        ProviderRegistryState.from_dict(payload)


def test_an_invalid_reasoning_effort_is_rejected() -> None:
    payload = _phase11_state().to_dict()
    payload["models"][0]["capabilities"]["reasoning_efforts"] = ["turbo"]  # type: ignore[index]

    with pytest.raises(ProviderStateSerializationError):
        ProviderRegistryState.from_dict(payload)


def test_a_duplicate_reasoning_effort_is_rejected() -> None:
    payload = _phase11_state().to_dict()
    payload["models"][0]["capabilities"]["reasoning_efforts"] = ["high", "high"]  # type: ignore[index]

    with pytest.raises(ProviderStateSerializationError):
        ProviderRegistryState.from_dict(payload)


def test_a_malformed_document_media_type_is_rejected() -> None:
    payload = _phase11_state().to_dict()
    payload["models"][0]["capabilities"]["document_media_types"] = ["not-a-media-type"]  # type: ignore[index]

    with pytest.raises(ProviderStateSerializationError):
        ProviderRegistryState.from_dict(payload)


def test_a_malformed_media_type_list_is_rejected() -> None:
    payload = _phase11_state().to_dict()
    payload["models"][0]["capabilities"]["document_media_types"] = "application/pdf"  # type: ignore[index]

    with pytest.raises(ProviderStateSerializationError):
        ProviderRegistryState.from_dict(payload)


@pytest.mark.parametrize("value", [1, "true", 0, None])
def test_a_non_bool_streaming_value_is_rejected(value: object) -> None:
    payload = _phase11_state().to_dict()
    payload["models"][0]["capabilities"]["streaming"] = value  # type: ignore[index]

    with pytest.raises(ProviderStateSerializationError):
        ProviderRegistryState.from_dict(payload)


def test_canonical_document_media_type_order_is_preserved() -> None:
    """Normalized document media types keep their canonical declared order."""
    ordered = ModelCapabilities(
        document_media_types=("text/plain", "application/pdf", "text/markdown"),
    )
    state = ProviderRegistryState(
        schema_version=SCHEMA_VERSION,
        revision=1,
        providers=(_provider("local", base_url="http://127.0.0.1:11434/v1"),),
        models=(ModelSpec(id="ordered", provider_id="local", capabilities=ordered),),
        manifests=(),
        connections=(),
        routes=(),
    )

    restored = ProviderRegistryState.from_dict(state.to_dict())

    assert restored.models[0].capabilities.document_media_types == (
        "text/plain",
        "application/pdf",
        "text/markdown",
    )
