"""The catalog's locality truth and its vendor declaration.

Two defects these guard, both reproduced on the real product:

* every model — including cloud subscription models reached through the
  loopback router — was labelled ``local`` because locality was derived from
  ``ProviderSpec.provider_type``, which describes where the serving *process*
  runs, not where the context goes;
* the vendor that actually serves a model was discarded at discovery, so the
  selector could only guess a family from the model id's spelling.
"""

from __future__ import annotations

import pytest

from cmm.model_execution.composition import (
    CHAT_ONLY_ROUTER_PROVIDER_ID,
    LOCAL_RUNTIME_MODEL_IDS_ENV,
    LOCAL_RUNTIME_PROVIDER_ID,
    build_local_model_execution,
    chat_only_router_provider_spec,
    local_runtime_model_vendors,
)
from cmm.model_execution.lanes import lane_locality
from kernel.llm.clients.openai_compatible_client import VENDOR_MAP_ENV
from kernel.llm.provider_registry import ProviderRegistry

LOCAL_MODEL_ID = "gemini-3.8-flash"
ROUTER_MODEL_ID = "claude/sonnet"


class _VendorDiscoveryClient:
    """A discovery double that carries the authority's own ``owned_by``."""

    def __init__(self, vendors: dict[str, str | None]) -> None:
        self.vendors = vendors
        self.calls = 0

    def list_models(self) -> tuple[str, ...]:
        self.calls += 1
        return tuple(self.vendors)

    def list_model_vendors(self) -> dict[str, str | None]:
        self.calls += 1
        return dict(self.vendors)


# ── Locality is the egress answer, not the process location ───────────────────


def test_a_loopback_lane_that_forwards_to_a_vendor_cloud_is_cloud() -> None:
    """Both composed lanes run as loopback processes; neither keeps context here."""

    assert lane_locality(CHAT_ONLY_ROUTER_PROVIDER_ID) == "cloud"


def test_the_local_runtime_lane_is_local_by_default() -> None:
    assert lane_locality(LOCAL_RUNTIME_PROVIDER_ID) == "local"


def test_a_declared_remote_runtime_is_cloud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The negative control: the declaration moves the answer, so the default is
    not merely what every lane happens to return."""

    monkeypatch.setenv("CMM_LOCAL_RUNTIME_EGRESS", "remote")
    assert lane_locality(LOCAL_RUNTIME_PROVIDER_ID) == "cloud"


def test_catalog_projects_the_router_lane_as_cloud() -> None:
    """The registered provider type stays local while the projection says cloud:
    the privacy gates read the type, the selector reads the egress truth."""

    registry = ProviderRegistry()
    execution = build_local_model_execution(
        provider_registry=registry, model_ids=(ROUTER_MODEL_ID,)
    )
    projected = {model.model_id: model for model in execution.executor.catalog()}

    assert projected[ROUTER_MODEL_ID].locality == "cloud"
    assert registry.get(CHAT_ONLY_ROUTER_PROVIDER_ID).provider_type == "local"


def test_catalog_projects_the_local_runtime_lane_as_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LOCAL_RUNTIME_MODEL_IDS_ENV, LOCAL_MODEL_ID)

    execution = build_local_model_execution(
        provider_registry=ProviderRegistry(), model_ids=(ROUTER_MODEL_ID,)
    )
    projected = {model.model_id: model for model in execution.executor.catalog()}

    assert projected[LOCAL_MODEL_ID].locality == "local"
    assert projected[ROUTER_MODEL_ID].locality == "cloud"


# ── The vendor is declared, never guessed from the id ─────────────────────────


def test_discovery_carries_the_declared_vendor_into_the_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LOCAL_RUNTIME_MODEL_IDS_ENV, raising=False)
    registry = ProviderRegistry()
    client = _VendorDiscoveryClient(
        {ROUTER_MODEL_ID: "cmm:claude", "chatgpt/gpt-5.5": "cmm:chatgpt"}
    )

    execution = build_local_model_execution(
        provider_registry=registry, base_url=None, client=client
    )
    projected = {model.model_id: model for model in execution.executor.catalog()}

    assert client.calls == 1, "identities and vendors must come from one call"
    assert projected[ROUTER_MODEL_ID].vendor == "cmm:claude"
    assert projected["chatgpt/gpt-5.5"].vendor == "cmm:chatgpt"


def test_a_model_the_authority_declares_nothing_about_has_no_vendor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LOCAL_RUNTIME_MODEL_IDS_ENV, raising=False)
    registry = ProviderRegistry()
    client = _VendorDiscoveryClient({ROUTER_MODEL_ID: None})

    execution = build_local_model_execution(
        provider_registry=registry, base_url=None, client=client
    )
    projected = {model.model_id: model for model in execution.executor.catalog()}

    assert projected[ROUTER_MODEL_ID].vendor is None


def test_a_narrow_transport_still_composes_with_no_vendor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The narrower ``list_models()`` contract is still supported."""

    monkeypatch.delenv(LOCAL_RUNTIME_MODEL_IDS_ENV, raising=False)

    class _IdentitiesOnly:
        def list_models(self) -> tuple[str, ...]:
            return (ROUTER_MODEL_ID,)

    registry = ProviderRegistry()
    execution = build_local_model_execution(
        provider_registry=registry, base_url=None, client=_IdentitiesOnly()
    )
    projected = {model.model_id: model for model in execution.executor.catalog()}

    assert projected[ROUTER_MODEL_ID].vendor is None


def test_the_vendor_map_annotates_only_configured_identities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An annotation can never add a model the launcher did not configure."""

    monkeypatch.setenv(
        VENDOR_MAP_ENV,
        '{"local-runtime": {"gemini-3.8-flash": "gemini", "never-configured": "bai"}}',
    )

    vendors = local_runtime_model_vendors((LOCAL_MODEL_ID, "deepseek-v4-flash"))

    assert vendors == {LOCAL_MODEL_ID: "gemini", "deepseek-v4-flash": None}
    assert "never-configured" not in vendors


def test_the_vendor_map_reaches_the_registered_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LOCAL_RUNTIME_MODEL_IDS_ENV, LOCAL_MODEL_ID)
    monkeypatch.setenv(
        VENDOR_MAP_ENV, '{"local-runtime": {"gemini-3.8-flash": "gemini"}}'
    )

    execution = build_local_model_execution(
        provider_registry=ProviderRegistry(), model_ids=(ROUTER_MODEL_ID,)
    )
    projected = {model.model_id: model for model in execution.executor.catalog()}

    # The runtime is declared local *and* served by a named vendor: both facts
    # are true at once, which is exactly what "local process, hosted upstream"
    # means and why locality alone could not carry it.
    assert projected[LOCAL_MODEL_ID].locality == "local"
    assert projected[LOCAL_MODEL_ID].vendor == "gemini"


def test_a_blank_router_override_is_refused_not_defaulted() -> None:
    """Regression: ``configured or DEFAULT`` turned a blank override into the
    pinned root and defeated the loopback gate."""

    with pytest.raises(ValueError):
        chat_only_router_provider_spec(base_url="")
