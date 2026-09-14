"""Contract tests for discovery reconciliation into the ModelRouteCatalog.

Scope under test is the Plan 2 Task 4 contract: ``discover_models`` turns one
``/models`` result into catalog state. Four decisions are pinned here rather
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
  ``last_seen_at`` is *not* advanced on disappearance: it keeps the timestamp of
  the pass that last advertised the route. Every multi-pass test therefore uses
  distinct per-pass ``seen_at`` values (``T0``/``T1``/``T2``), because a single
  reused timestamp cannot distinguish "left unchanged" from "overwritten with
  the same value".
* **Cross-connection scoping.** Reconciling one connection never touches
  another connection's routes: the vanish scan is scoped by the
  ``{connection_id}:`` prefix, so a shared catalog holds both connections'
  routes independently.
* **Empty-result guard.** An empty ``list_models()`` result carries no routing
  information at all: the client cannot distinguish "provider really has zero
  models" (unreachable for these first-wave providers) from a malformed or
  truncated administrative response. Reconciliation therefore returns early and
  marks nothing unavailable. Without this guard a single bad response would
  mass-deactivate every route of a connection — the data-loss-shaped failure
  Task 1's spec review flagged as a hard Task 4 requirement (spec §7, §14.7).

Activation policy is also pinned: for a manifest with a non-empty
``activation_allowlist``, discovered models outside the allowlist are still
represented in the catalog but are not activated for routing. On first sight
such a model is reported in BOTH ``new_route_ids`` (it is a newly registered
route) and ``unavailable_route_ids`` (it is not activated), and it is never
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
OTHER_CONNECTION_ID = "other:main"


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


def _other_connection() -> ProviderConnection:
    return ProviderConnection(
        connection_id=OTHER_CONNECTION_ID,
        provider_id="other",
        display_name="Other API",
        billing_class=BillingClass.PAYG,
        credential_ref="keychain://cmm-os/other",
        endpoint="https://api.other.example/v1",
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
    # Disappearance does not advance last_seen_at: T1 != T0, so this pins that
    # the vanish scan leaves the field at the prior pass's stamp.
    assert vanished.last_seen_at == T0


def test_vanished_route_keeps_prior_pass_timestamp_not_a_later_one() -> None:
    """The lastSeenAt-unchanged rule, pinned across *three* distinct passes.

    Every pass uses a distinct ``seen_at``, so an implementation that stamps
    ``last_seen_at`` while marking a route unavailable cannot hide behind a
    repeated timestamp: after the T2 pass omits ``model-a`` for the second time,
    its ``last_seen_at`` must still be T0 — the last pass that advertised it —
    and never T1 or T2.
    """
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
        StubClient(("model-b",)),
        catalog,
        seen_at=T2,
    )

    assert result.unavailable_route_ids == ()  # no churn on an already-vanished route

    vanished = catalog.get(f"{CONNECTION_ID}:model-a")
    assert vanished is not None
    assert vanished.available is False
    assert vanished.first_seen_at == T0
    assert vanished.last_seen_at == T0  # T0, not T1 and not T2
    assert vanished.last_seen_at != T1
    assert vanished.last_seen_at != T2

    kept = catalog.get(f"{CONNECTION_ID}:model-b")
    assert kept is not None
    assert kept.available is True
    assert kept.first_seen_at == T0
    assert kept.last_seen_at == T2  # the advertised route does advance


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
    # A re-appearance is a sighting, so last_seen_at IS refreshed to T2 — the
    # counterpart of the vanish rule above.
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
        assert route.last_seen_at != T1


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
    # model-b is counted as unavailable (not activated), never dropped. Being
    # deferred and being new are independent facts, so the two tuples overlap
    # on model-b by design (see ModelDiscoveryResult's docstring).
    assert result.unavailable_route_ids == (f"{CONNECTION_ID}:model-b",)
    assert catalog.get(f"{CONNECTION_ID}:model-b") is not None

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

    # Exactly the two expected routes exist: no duplicated registrations. The
    # full catalog route-id set is asserted, not just one canonical model's
    # route count (the latter would miss a spurious extra route).
    assert {route.route_id for route in catalog.filter_required_capabilities(())} == {
        f"{CONNECTION_ID}:model-a",
        f"{CONNECTION_ID}:model-b",
    }
    assert len(catalog.routes_for_canonical_model("model-a")) == 1
    assert len(catalog.routes_for_canonical_model("model-b")) == 1
    # Both routes carry the pass-T2 stamp and the original T0 identity.
    for model in models:
        route = catalog.get(f"{CONNECTION_ID}:{model}")
        assert route is not None
        assert route.first_seen_at == T0
        assert route.last_seen_at == T2


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


def test_reconcile_of_one_connection_leaves_another_connections_routes_alone() -> None:
    """The cross-connection safety invariant, pinned against a shared catalog.

    Both connections live in ONE ``ModelRouteCatalog``. The primary
    connection's non-empty discovery omits ``model-z`` — which is *not* one of
    its own routes but IS the other connection's available route. Because the
    vanish scan is scoped by the ``{connection_id}:`` prefix, the other
    connection's route must stay available and must never appear in
    ``unavailable_route_ids``. Without that scoping, one connection's reconcile
    would flip another connection's routing off.
    """
    catalog = ModelRouteCatalog()
    other_route_id = f"{OTHER_CONNECTION_ID}:model-z"

    # Seed the OTHER connection's route through reconciliation itself.
    other_result = discover_models(
        _other_connection(),
        _manifest(provider_id="other"),
        StubClient(("model-z",)),
        catalog,
        seen_at=T0,
    )
    assert other_result.new_route_ids == (other_route_id,)
    seeded = catalog.get(other_route_id)
    assert seeded is not None
    assert seeded.available is True

    # The PRIMARY connection discovers its own models; 'model-z' is absent and
    # belongs to the other connection only.
    result = discover_models(
        _connection(),
        _manifest(),
        StubClient(("model-a",)),
        catalog,
        seen_at=T1,
    )

    assert result.connection_id == CONNECTION_ID
    assert result.discovered_route_ids == (f"{CONNECTION_ID}:model-a",)
    assert result.new_route_ids == (f"{CONNECTION_ID}:model-a",)
    # The other connection's route must not be reported or deactivated.
    assert other_route_id not in result.unavailable_route_ids
    assert result.unavailable_route_ids == ()

    survived = catalog.get(other_route_id)
    assert survived is not None
    assert survived.available is True
    assert survived.connection_id == OTHER_CONNECTION_ID
    assert survived.first_seen_at == T0
    assert survived.last_seen_at == T0  # untouched by the other connection's pass

    # The primary connection's own route was created normally.
    own = catalog.get(f"{CONNECTION_ID}:model-a")
    assert own is not None
    assert own.available is True


def test_cross_connection_vanish_scan_ignores_absent_foreign_model_ids() -> None:
    """A foreign route is spared even when its model id is absent upstream.

    This is the sharpest form of the prefix invariant: the primary connection
    advertises ONLY ``model-a``, while the other connection advertises
    ``model-a`` AND ``model-z``. ``model-z`` is absent from the primary
    discovery entirely, so a prefix-less scan would deactivate it. With the
    prefix rule it stays available.
    """
    catalog = ModelRouteCatalog()
    other_route_id = f"{OTHER_CONNECTION_ID}:model-z"
    discover_models(
        _other_connection(),
        _manifest(provider_id="other"),
        StubClient(("model-a", "model-z")),
        catalog,
        seen_at=T0,
    )

    result = discover_models(
        _connection(),
        _manifest(),
        StubClient(("model-a",)),
        catalog,
        seen_at=T1,
    )

    assert result.unavailable_route_ids == ()
    assert other_route_id not in result.unavailable_route_ids
    survived = catalog.get(other_route_id)
    assert survived is not None
    assert survived.available is True

    # And the primary connection's own model-a route is unaffected by the
    # other connection having the same provider model id.
    own = catalog.get(f"{CONNECTION_ID}:model-a")
    assert own is not None
    assert own.available is True


def test_deferred_first_sight_model_overlaps_new_and_unavailable() -> None:
    """The documented overlap is pinned as a literal contract.

    ``ModelDiscoveryResult`` states that a first-sight model excluded by the
    allowlist appears in BOTH ``new_route_ids`` and ``unavailable_route_ids``,
    while a vanished model appears ONLY in ``unavailable_route_ids`` and a
    restored model ONLY in ``restored_route_ids``. This test pins the overlap
    directly (set intersection), so the prose can never silently drift from the
    behaviour.
    """
    catalog = ModelRouteCatalog()
    manifest = _manifest(activation_allowlist=("model-a",))

    result = discover_models(
        _connection(),
        manifest,
        StubClient(("model-a", "model-b")),
        catalog,
        seen_at=T0,
    )

    deferred = f"{CONNECTION_ID}:model-b"
    assert deferred in result.new_route_ids
    assert deferred in result.unavailable_route_ids
    assert set(result.new_route_ids) & set(result.unavailable_route_ids) == {deferred}

    # A model that vanished is never reported new: a route that was AVAILABLE
    # and then disappears is reported only unavailable. (The deferred model-b
    # above was already unavailable, so its later absence is correctly silent —
    # no churn.)
    second = discover_models(
        _connection(),
        manifest,
        StubClient(("model-a", "model-c")),
        catalog,
        seen_at=T1,
    )
    # model-c is deferred on first sight too, so it is reported as both new and
    # unavailable; model-b stays silent.
    assert f"{CONNECTION_ID}:model-b" not in second.unavailable_route_ids
    assert f"{CONNECTION_ID}:model-c" in second.new_route_ids
    assert f"{CONNECTION_ID}:model-c" in second.unavailable_route_ids

    # Now a pass where an ACTIVATED route (model-a) vanishes: it is reported
    # only unavailable, never new and never restored.
    third = discover_models(
        _connection(),
        manifest,
        StubClient(("model-c",)),
        catalog,
        seen_at=T2,
    )
    vanished = f"{CONNECTION_ID}:model-a"
    assert vanished in third.unavailable_route_ids
    assert vanished not in third.new_route_ids
    assert vanished not in third.restored_route_ids


def test_reappearing_model_is_never_reported_new_or_unavailable() -> None:
    """Re-appearance is reported SOLELY as restored.

    The third tuple rule from ``ModelDiscoveryResult``: a reappearing model is
    counted in ``restored_route_ids`` and in neither ``new_route_ids`` nor
    ``unavailable_route_ids``.
    """
    catalog = ModelRouteCatalog()
    discover_models(
        _connection(),
        _manifest(),
        StubClient(("model-a", "model-b")),
        catalog,
        seen_at=T0,
    )
    # A non-empty pass that omits model-a, so the vanish is real routing info
    # (the empty-result guard correctly declines to reconcile an empty result).
    discover_models(
        _connection(), _manifest(), StubClient(("model-b",)), catalog, seen_at=T1
    )

    result = discover_models(
        _connection(),
        _manifest(),
        StubClient(("model-a", "model-b")),
        catalog,
        seen_at=T2,
    )

    restored_id = f"{CONNECTION_ID}:model-a"
    assert result.restored_route_ids == (restored_id,)
    assert restored_id not in result.new_route_ids
    assert restored_id not in result.unavailable_route_ids

    route = catalog.get(restored_id)
    assert route is not None
    assert route.available is True
    assert route.first_seen_at == T0
    assert route.last_seen_at == T2


def test_reconciliation_never_calls_inference_transport() -> None:
    catalog = ModelRouteCatalog()
    client = ForbiddenStubClient(("model-a",))

    with pytest.raises(InferenceForbidden):
        client.generate()  # control: the trap is live
        raise AssertionError("unreachable")
    assert client.calls == 0  # the control call touched no discovery transport

    result = discover_models(_connection(), _manifest(), client, catalog, seen_at=T0)

    assert result.new_route_ids == (f"{CONNECTION_ID}:model-a",)
    # Exactly one fetch per pass: a re-fetch (or a generate() call) fails here.
    assert client.calls == 1
