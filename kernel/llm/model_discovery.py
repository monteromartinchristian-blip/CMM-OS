"""Reconcile one ``/models`` discovery result into the route catalog.

Discovery is authoritative for a connection's model list (spec §7, §9): the
manifest declares transport/auth/billing defaults, and every model id the
administrative endpoint reports becomes a durable ``ModelRoute``. This module
contains the reconciliation rules, not the transport — the client is injected
and no scheduling/background refresh exists at this layer.

Reconciliation rules
--------------------

1. **Route id formula.** A route id is exactly
   ``f"{connection.connection_id}:{provider_model_id}"``. Provider model ids are
   opaque upstream keys, so slashes, dots and every other punctuation mark are
   preserved verbatim (``qwen/qwen3.8-max`` yields
   ``qwen:qwen/qwen3.8-max``); they are never slugified, since a rewritten id
   would strand the route's history on the next discovery.

2. **First sight registers; later sightings refresh.** An unknown discovered
   model is registered and then re-stamped with ``mark_seen(route_id, seen_at)``
   (``register`` stamps ``last_seen_at`` from the wall clock, so the extra call
   keeps a reconciliation run on one clock source), and deactivated last if the
   allowlist excludes it — order matters, because ``register`` pins
   ``available=True``. A known model is refreshed with ``mark_seen(route_id,
   seen_at)``, which restores availability and preserves ``first_seen_at``: the
   route's original identity is never rewritten. ``mark_seen`` is preferred over
   ``register`` for a known route precisely because ``register`` rejects an
   existing id.

3. **Disappearance is not deletion.** A route for this connection that is
   absent from a non-empty discovery result is marked unavailable and stays
   retrievable with identity and history intact; it is never removed.

4. **Re-appearance restores.** A previously-unavailable route that shows up
   again is reported in ``restored_route_ids`` and becomes available with its
   ORIGINAL ``first_seen_at`` preserved.

5. **Activation is allowlist-gated.** When ``manifest.activation_allowlist`` is
   non-empty, discovered models outside it are still registered — represented
   in the catalog for observability — but are not activated for routing, so
   they report as unavailable rather than new. A previously-deferred model that
   reappears is not reported as restored, since it still is not activated.

6. **Empty-result guard (mandatory).** An empty discovery result carries no
   routing information at all: the client cannot distinguish "the provider
   really has zero models" (unreachable for first-wave providers, whose
   ``/models`` lists are never empty) from a malformed, truncated or
   auth-mangled administrative response. Treating it as "every model vanished"
   would mass-deactivate every route of the connection on a single bad
   response — a data-loss-shaped failure. Rule 3 is therefore skipped entirely
   for an empty result: reconciliation returns early, marks nothing
   unavailable, and reports empty sets. A route can only be deactivated by a
   non-empty result that genuinely omits it (spec §7, §14.7,
   ``MODEL_DISAPPEARANCE_HISTORY_PRESERVED``).

Discarding an empty result costs nothing today: these first-wave providers
always advertise models, so an empty list is a transport anomaly, and the next
successful discovery reconciles normally.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from kernel.llm.model_routes import ModelRoute, ModelRouteCatalog
from kernel.llm.provider_connections import ProviderConnection
from kernel.llm.provider_manifests import ProviderManifest


@dataclass(frozen=True, slots=True)
class ModelDiscoveryResult:
    """Outcome of one reconciliation pass for a single connection."""

    connection_id: str
    discovered_route_ids: tuple[str, ...]
    new_route_ids: tuple[str, ...]
    restored_route_ids: tuple[str, ...]
    unavailable_route_ids: tuple[str, ...]


def _route_id(connection_id: str, provider_model_id: str) -> str:
    """Return the canonical route id for a connection/model pair."""
    return f"{connection_id}:{provider_model_id}"


def _is_activated(manifest: ProviderManifest, provider_model_id: str) -> bool:
    """Return whether ``provider_model_id`` may be activated for routing.

    An empty allowlist means discovery is authoritative and every model is
    activatable; a non-empty one restricts activation to its listed ids, which
    are compared exactly because provider model ids are case-sensitive.
    """
    allowlist = manifest.activation_allowlist
    return not allowlist or provider_model_id in allowlist


def discover_models(
    connection: ProviderConnection,
    manifest: ProviderManifest,
    client: object,
    catalog: ModelRouteCatalog,
    *,
    seen_at: datetime,
) -> ModelDiscoveryResult:
    """Reconcile ``client.list_models()`` into ``catalog`` at ``seen_at``.

    Applies the six module-level reconciliation rules. Performs no inference and
    no I/O of its own — ``client`` supplies the already-fetched model ids. An
    empty discovery result returns early and marks nothing unavailable
    (rule 6). ``seen_at`` must be timezone-aware, as the catalog requires.
    """
    connection_id = connection.connection_id
    discovered = tuple(client.list_models())

    if not discovered:
        # Rule 6: never reconcile absence against a vacuous result.
        return ModelDiscoveryResult(
            connection_id=connection_id,
            discovered_route_ids=(),
            new_route_ids=(),
            restored_route_ids=(),
            unavailable_route_ids=(),
        )

    discovered_ids = tuple(
        _route_id(connection_id, provider_model_id) for provider_model_id in discovered
    )
    discovered_set = set(discovered_ids)

    new_route_ids: list[str] = []
    restored_route_ids: list[str] = []
    deferred_route_ids: list[str] = []

    for provider_model_id, route_id in zip(discovered, discovered_ids):
        activated = _is_activated(manifest, provider_model_id)
        existing = catalog.get(route_id)
        if existing is None:
            catalog.register(
                ModelRoute(
                    route_id=route_id,
                    connection_id=connection_id,
                    provider_model_id=provider_model_id,
                    canonical_model_id=provider_model_id,
                    first_seen_at=seen_at,
                    last_seen_at=seen_at,
                )
            )
            # ``register`` stamps last_seen_at from the wall clock; re-stamp it
            # with seen_at so a reconciliation run never mixes clock sources.
            catalog.mark_seen(route_id, seen_at)
            if not activated:
                # Represented but not activated for routing; order matters,
                # because register() pins available=True.
                catalog.mark_unavailable(route_id)
                deferred_route_ids.append(route_id)
            new_route_ids.append(route_id)
            continue

        if activated:
            # mark_seen restores availability and keeps first_seen_at.
            catalog.mark_seen(route_id, seen_at)
            if not existing.available:
                restored_route_ids.append(route_id)
        elif existing.available:
            # Newly excluded by the allowlist: deactivate, never delete.
            catalog.mark_unavailable(route_id)
            deferred_route_ids.append(route_id)
        else:
            deferred_route_ids.append(route_id)

    unavailable_route_ids = _mark_vanished_unavailable(
        catalog, connection_id, discovered_set
    )

    return ModelDiscoveryResult(
        connection_id=connection_id,
        discovered_route_ids=discovered_ids,
        new_route_ids=tuple(new_route_ids),
        restored_route_ids=tuple(restored_route_ids),
        unavailable_route_ids=unavailable_route_ids + tuple(deferred_route_ids),
    )


def _mark_vanished_unavailable(
    catalog: ModelRouteCatalog,
    connection_id: str,
    discovered_route_ids: set[str],
) -> tuple[str, ...]:
    """Mark this connection's absent routes unavailable; never delete them.

    Only called for a non-empty discovery result (rule 6 guards the empty case),
    so absence is real routing information here. The scan is prefix-scoped to
    this connection's route ids — the catalog has no per-connection accessor and
    this module must not add one. Routes already unavailable are not re-reported
    so repeated discoveries produce no churn. Returns ids in sorted order.
    """
    prefix = f"{connection_id}:"
    unavailable: list[str] = []
    for route_id in sorted(
        discovered_route_ids | _stored_route_ids(catalog, connection_id)
    ):
        if not route_id.startswith(prefix):
            continue
        if route_id in discovered_route_ids:
            continue
        route = catalog.get(route_id)
        if route is None or not route.available:
            continue
        catalog.mark_unavailable(route_id)
        unavailable.append(route_id)
    return tuple(unavailable)


def _stored_route_ids(catalog: ModelRouteCatalog, connection_id: str) -> set[str]:
    """Return the ids of this connection's available routes in ``catalog``.

    ``ModelRouteCatalog`` exposes lookups by route id but no enumeration, and
    this module must not add an accessor to another module's class.
    ``routes_for_connection`` does not exist, so the catalog is read through its
    own surfaces instead: an empty requirement tuple makes
    ``filter_required_capabilities(())`` return every *available* route (the
    availability check is that query's only filter), and ``get`` resolves the
    candidate ids this module already knows about from the discovery result.

    The candidate set is the union of the discovered ids and the stored
    available ones, which is exactly the set a deactivation pass can act on:
    available routes are the only ones that can newly become unavailable, and
    already-unavailable routes are deliberately not re-reported.
    """
    candidates = {
        route.route_id
        for route in catalog.filter_required_capabilities(())
        if route.connection_id == connection_id
    }
    return {
        route_id
        for route_id in candidates
        if (route := catalog.get(route_id)) is not None and route.available
    }
