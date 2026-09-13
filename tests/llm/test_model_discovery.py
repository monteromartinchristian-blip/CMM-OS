"""Contract tests for discovery reconciliation into the ModelRouteCatalog.

Scope under test is the Plan 2 Task 4 contract: ``discover_models`` turns one
``/models`` result into catalog state. Three decisions are pinned here rather
than left to implementation taste.

* **Route-id fidelity.** ``route_id`` is exactly
  ``f"{connection.connection_id}:{provider_model_id}"``. Provider model ids are
  opaque upstream keys, so slashes, dots and every other punctuation mark are
  preserved verbatim: ``qwen/qwen3.8-max`` yields ``qwen:qwen/qwen3.8-max``, not
  a slugified variant. A rewritten id would silently strand the route's history
  on the next discovery (spec: provider model ids preserved unchanged).
* **Disappearance is not deletion.** A model absent from a later discovery is
  marked unavailable and stays retrievable with identity and history intact
  (``first_seen_at`` never moves), so ``MODEL_DISAPPEARANCE_HISTORY_PRESERVED``
  holds across a provider-side removal followed by a re-appearance.
* **Empty-result guard.** An empty ``list_models()`` result carries no routing
  information at all: the client cannot distinguish "provider really has zero
  models" (unreachable for these first-wave providers) from a malformed or
  truncated administrative response. Reconciliation therefore returns early and
  marks nothing unavailable. Without this guard a single bad response would
  mass-deactivate every route of a connection — the data-loss-shaped failure
  Task 1's spec review flagged as a hard Task 4 requirement (spec §7, §14.7).

Activation policy is also pinned: for a manifest with a non-empty
``activation_allowlist``, discovered models outside the allowlist are still
represented in the catalog but are not activated for routing, so they are
reported in ``unavailable_route_ids`` rather than ``new_route_ids`` and never
dropped.
"""

from datetime import datetime, timezone

import pytest

from kernel.llm.model_discovery import discover_models
from kernel.llm.model_routes import ModelRouteCatalog
from kernel.llm.provider_connections import BillingClass, ProviderConnection
from kernel.llm.provider_manifests import ProviderManifest

T0 = datetime(2026, 9, 13, 10, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 13, 14, 0, tzinfo=timezone.utc)

CONNECTION_ID = "deepseek:main"


class StubClient:
    """Injected discovery transport returning a scripted model list."""

    def __init__(self, models: tuple[str, ...] = ()) -> None:
        self._models = models
        self.calls = 0

    def list_models(self) -> tuple[str, ...]:
        self.calls += 1
        return self._models


class InferenceForbidden(BaseException):
    """Raised if reconciliation ever reaches an inference transport method."""

    def __init__(self) -> None:
        super().__init__("discovery must never perform an inference request")


class ForbiddenStubClient(StubClient):
    """Mutation guard: a stub whose inference entry point is a trap."""

    def generate(self, **kwargs: object) -> tuple[str, int, int, str]:
        raise InferenceForbidden()


def _connection() -> ProviderConnection:
    return ProviderConnection(
        connection_id=CONNECTION_ID,
        provider_id="deepseek",
        display_name="DeepSeek API",
        billing_class=BillingClass.PAYG,
        credential_ref="keychain://cmm-os/deepseek",
        endpoint="https://api.deepseek.com/v1",
        isolation_profile_ref=None,
        status="connected",
    )


def _manifest(**overrides: object) -> ProviderManifest:
    fields: dict[str, object] = {
        "provider_id": "deepseek",
        "display_name": "DeepSeek API",
        "billing_class": BillingClass.PAYG,
        "default_base_url": "https://api.deepseek.com/v1",
        "auth_scheme": "bearer",
    }
    fields.update(overrides)
    return ProviderManifest(**fields)  # type: ignore[arg-type]


def test_first_discovery_creates_available_routes_with_exact_ids() -> None:
    catalog = ModelRouteCatalog()
    client = StubClient(("model-a", "model-b"))

    result = discover_models(_connection(), _manifest(), client, catalog, seen_at=T0)

    assert result.connection_id == CONNECTION_ID
    assert result.discovered_route_ids == (
        f"{CONNECTION_ID}:model-a",
        f"{CONNECTION_ID}:model-b",
    )
    assert result.new_route_ids == result.discovered_route_ids
    assert result.restored_route_ids == ()
    assert result.unavailable_route_ids == ()

    for model in ("model-a", "model-b"):
        route = catalog.get(f"{CONNECTION_ID}:{model}")
        assert route is not None
        assert route.available is True
        assert route.connection_id == CONNECTION_ID
        assert route.provider_model_id == model
        assert route.first_seen_at == T0
        assert route.last_seen_at == T0  # stamped with seen_at, not wall clock
        assert route.capabilities == ()


def test_second_discovery_keeps_creates_and_marks_unavailable() -> None:
    catalog = ModelRouteCatalog()
    discover_models(
        _connection(),
        _manifest(),
        StubClient(("model-a", "model-b")),
        catalog,
        seen_at=T0,
    )

    result = discover_models(
        _connection(),
        _manifest(),
        StubClient(("model-b", "model-c")),
        catalog,
        seen_at=T1,
    )

    assert result.discovered_route_ids == (
        f"{CONNECTION_ID}:model-b",
        f"{CONNECTION_ID}:model-c",
    )
    assert result.new_route_ids == (f"{CONNECTION_ID}:model-c",)
    assert result.restored_route_ids == ()
    assert result.unavailable_route_ids == (f"{CONNECTION_ID}:model-a",)

    kept = catalog.get(f"{CONNECTION_ID}:model-b")
    assert kept is not None
    assert kept.available is True
    assert kept.first_seen_at == T0
    assert kept.last_seen_at == T1

    created = catalog.get(f"{CONNECTION_ID}:model-c")
    assert created is not None
    assert created.available is True
    assert created.first_seen_at == T1
    assert created.last_seen_at == T1

    # Never deleted: still retrievable with identity and history preserved.
    vanished = catalog.get(f"{CONNECTION_ID}:model-a")
    assert vanished is not None
    assert vanished.available is False
    assert vanished.provider_model_id == "model-a"
    assert vanished.first_seen_at == T0
    assert vanished.last_seen_at == T0


def test_reappearing_model_is_restored_with_original_first_seen_at() -> None:
    catalog = ModelRouteCatalog()
    discover_models(
        _connection(),
        _manifest(),
        StubClient(("model-a", "model-b")),
        catalog,
        seen_at=T0,
    )
    discover_models(
        _connection(),
        _manifest(),
        StubClient(("model-b",)),
        catalog,
        seen_at=T1,
    )

    result = discover_models(
        _connection(),
        _manifest(),
        StubClient(("model-a", "model-b")),
        catalog,
        seen_at=T2,
    )

    assert result.discovered_route_ids == (
        f"{CONNECTION_ID}:model-a",
        f"{CONNECTION_ID}:model-b",
    )
    assert result.restored_route_ids == (f"{CONNECTION_ID}:model-a",)
    assert result.new_route_ids == ()
    assert result.unavailable_route_ids == ()

    restored = catalog.get(f"{CONNECTION_ID}:model-a")
    assert restored is not None
    assert restored.available is True
    assert restored.first_seen_at == T0  # original identity, not T2
    assert restored.last_seen_at == T2


def test_empty_discovery_result_marks_nothing_unavailable() -> None:
    """MANDATORY GUARD: an empty result never mass-deactivates routes.

    An empty ``list_models()`` result is indistinguishable from a malformed or
    truncated administrative response, so it must not be read as "every model
    disappeared". Reconciliation returns early with empty sets and leaves every
    previously-available route available.
    """
    catalog = ModelRouteCatalog()
    discover_models(
        _connection(),
        _manifest(),
        StubClient(("model-a", "model-b")),
        catalog,
        seen_at=T0,
    )

    result = discover_models(
        _connection(), _manifest(), StubClient(()), catalog, seen_at=T1
    )

    assert result.connection_id == CONNECTION_ID
    assert result.discovered_route_ids == ()
    assert result.new_route_ids == ()
    assert result.restored_route_ids == ()
    assert result.unavailable_route_ids == ()

    for model in ("model-a", "model-b"):
        route = catalog.get(f"{CONNECTION_ID}:{model}")
        assert route is not None
        assert route.available is True
        assert route.last_seen_at == T0  # untouched by the empty result


def test_empty_discovery_on_empty_catalog_is_a_no_op() -> None:
    catalog = ModelRouteCatalog()

    result = discover_models(
        _connection(), _manifest(), StubClient(()), catalog, seen_at=T0
    )

    assert result.discovered_route_ids == ()
    assert result.new_route_ids == ()
    assert result.restored_route_ids == ()
    assert result.unavailable_route_ids == ()
    assert catalog.get(f"{CONNECTION_ID}:model-a") is None


def test_activation_allowlist_defers_models_outside_the_allowlist() -> None:
    catalog = ModelRouteCatalog()
    manifest = _manifest(activation_allowlist=("model-a",))

    result = discover_models(
        _connection(),
        manifest,
        StubClient(("model-a", "model-b")),
        catalog,
        seen_at=T0,
    )

    assert result.discovered_route_ids == (
        f"{CONNECTION_ID}:model-a",
        f"{CONNECTION_ID}:model-b",
    )
    # Both are newly created routes for this connection, so both are reported
    # new; the allowlist decides activation, not whether the route is new.
    assert result.new_route_ids == (
        f"{CONNECTION_ID}:model-a",
        f"{CONNECTION_ID}:model-b",
    )
    assert result.restored_route_ids == ()
    # model-b is counted as unavailable (not activated), never dropped.
    assert result.unavailable_route_ids == (f"{CONNECTION_ID}:model-b",)

    active = catalog.get(f"{CONNECTION_ID}:model-a")
    assert active is not None
    assert active.available is True

    # Represented but not activated: present, retrievable, unavailable.
    deferred = catalog.get(f"{CONNECTION_ID}:model-b")
    assert deferred is not None
    assert deferred.provider_model_id == "model-b"
    assert deferred.available is False


def test_allowlisted_model_present_in_allowlist_is_activated() -> None:
    catalog = ModelRouteCatalog()
    manifest = _manifest(activation_allowlist=("model-b", "model-a"))

    result = discover_models(
        _connection(), manifest, StubClient(("model-a",)), catalog, seen_at=T0
    )

    assert result.new_route_ids == (f"{CONNECTION_ID}:model-a",)
    assert result.unavailable_route_ids == ()
    assert catalog.get(f"{CONNECTION_ID}:model-a").available is True


def test_route_id_preserves_slashes_and_punctuation_verbatim() -> None:
    catalog = ModelRouteCatalog()
    provider_model_id = "qwen/qwen3.8-max"
    expected_route_id = f"{CONNECTION_ID}:qwen/qwen3.8-max"

    result = discover_models(
        _connection(),
        _manifest(),
        StubClient((provider_model_id,)),
        catalog,
        seen_at=T0,
    )

    assert result.discovered_route_ids == (expected_route_id,)
    assert result.new_route_ids == (expected_route_id,)

    route = catalog.get(expected_route_id)
    assert route is not None
    assert route.route_id == expected_route_id
    assert route.provider_model_id == provider_model_id
    assert route.first_seen_at == T0
    assert route.available is True

    # No slugified/rewritten alias was created under a different id.
    assert catalog.get(f"{CONNECTION_ID}:qwen-qwen3.8-max") is None


def test_idempotent_discovery_produces_no_churn() -> None:
    catalog = ModelRouteCatalog()
    models = ("model-a", "model-b")
    discover_models(_connection(), _manifest(), StubClient(models), catalog, seen_at=T0)

    first = discover_models(
        _connection(), _manifest(), StubClient(models), catalog, seen_at=T1
    )
    second = discover_models(
        _connection(), _manifest(), StubClient(models), catalog, seen_at=T2
    )

    for result in (first, second):
        assert result.new_route_ids == ()
        assert result.restored_route_ids == ()
        assert result.unavailable_route_ids == ()
        assert result.discovered_route_ids == (
            f"{CONNECTION_ID}:model-a",
            f"{CONNECTION_ID}:model-b",
        )

    stored = catalog.get(f"{CONNECTION_ID}:model-a")
    assert stored is not None
    assert stored.first_seen_at == T0
    assert stored.last_seen_at == T2
    assert stored.available is True
    # Exactly two routes exist: no duplicated registrations.
    assert len(catalog.routes_for_canonical_model("model-a")) == 1


def test_restore_of_allowlisted_out_model_is_not_restored() -> None:
    """A reappearing model still outside the allowlist stays unavailable.

    The third pass sees ``model-b`` again while the allowlist still excludes it,
    so it is not reported as restored and stays unavailable. Deferral has a
    single cause in this module's behaviour: the allowlist. ``first_seen_at``
    still pins the original T0 identity, so no history was lost while deferred.
    """
    catalog = ModelRouteCatalog()
    manifest = _manifest(activation_allowlist=("model-a",))

    discover_models(
        _connection(),
        manifest,
        StubClient(("model-a", "model-b")),
        catalog,
        seen_at=T0,
    )
    discover_models(
        _connection(), manifest, StubClient(("model-a",)), catalog, seen_at=T1
    )

    result = discover_models(
        _connection(),
        manifest,
        StubClient(("model-a", "model-b")),
        catalog,
        seen_at=T2,
    )

    assert result.restored_route_ids == ()
    assert result.unavailable_route_ids == (f"{CONNECTION_ID}:model-b",)
    assert result.new_route_ids == ()
    deferred = catalog.get(f"{CONNECTION_ID}:model-b")
    assert deferred is not None
    assert deferred.available is False
    assert deferred.first_seen_at == T0


def test_reconciliation_never_calls_inference_transport() -> None:
    catalog = ModelRouteCatalog()
    client = ForbiddenStubClient(("model-a",))

    with pytest.raises(InferenceForbidden):
        client.generate()  # control: the trap is live
        raise AssertionError("unreachable")

    result = discover_models(_connection(), _manifest(), client, catalog, seen_at=T0)

    assert result.new_route_ids == (f"{CONNECTION_ID}:model-a",)
    assert client.calls == 1
