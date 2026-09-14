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
   retrievable with identity and history intact; it is never removed. Its
   ``last_seen_at`` is deliberately **not** advanced: that field records the
   last pass in which the provider advertised the route, so it must keep the
   prior pass's stamp once the route vanishes. The scan is scoped to this
   connection's routes by their ``{connection_id}:`` prefix, so one connection's
   reconciliation never touches another's routes.

4. **Re-appearance restores.** A previously-unavailable route that shows up
   again is reported in ``restored_route_ids`` and becomes available with its
   ORIGINAL ``first_seen_at`` preserved. It is refreshed by ``mark_seen``, so its
   ``last_seen_at`` advances to the re-appearance pass.

5. **Activation is allowlist-gated.** When ``manifest.activation_allowlist`` is
   non-empty, discovered models outside it are still registered — represented
   in the catalog for observability — but are not activated for routing, so
   they are reported in ``unavailable_route_ids`` **as well as** in
   ``new_route_ids`` on first sight (registration and activation are separate
   facts; the allowlist decides only the latter). A previously-deferred model
   that reappears is not reported as restored, since it still is not activated.

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
from typing import Protocol

from kernel.llm.model_routes import ModelRoute, ModelRouteCatalog
from kernel.llm.provider_connections import ProviderConnection
from kernel.llm.provider_manifests import ProviderManifest


class DiscoverableModelClient(Protocol):
    """Minimum discovery transport the reconciler depends on.

    A structural contract, mirroring ``OpenAICompatibleClientProtocol`` in
    ``kernel/llm/openai_compatible_provider.py``: any object exposing a
    no-argument ``list_models()`` returning provider model ids satisfies it.
    Discovery only ever reads the model list — it never reaches an inference
    method, so none is declared here.
    """

    def list_models(self) -> tuple[str, ...]:
        """Return the provider's advertised model ids, in transport order."""
        ...


@dataclass(frozen=True, slots=True)
class ModelDiscoveryResult:
    """Outcome of one reconciliation pass for a single connection.

    Reporting contract for the route-id tuples (the catalog state is the
    source of truth; these tuples describe what this pass *did*):

    * A **first-sight** model excluded by a non-empty ``activation_allowlist``
      appears in **both** ``new_route_ids`` *and* ``unavailable_route_ids``: it
      was newly registered (a new route, reported new) but is not activated for
      routing (reported unavailable). This overlap is intentional.
    * A model that **vanished** appears **only** in ``unavailable_route_ids`` —
      never as new, and never as restored.
    * A model that **reappears** is reported **solely** in
      ``restored_route_ids``: it is never counted as new, and it is absent from
      ``unavailable_route_ids``.
    * A model that was simply **refreshed** (already available, still
      advertised) appears in none of the three outcome tuples.
    """

    connection_id: str
    discovered_route_ids: tuple[str, ...]
    new_route_ids: tuple[str, ...]
    restored_route_ids: tuple[str, ...]
    unavailable_route_ids: tuple[str, ...]


def _route_id(connection_id: str, provider_model_id: str) -> str:
    """Return the canonical route id for a connection/model pair."""
    return f"{connection_id}:{provider_model_id}"


def _is_activated(allowlist: tuple[str, ...], provider_model_id: str) -> bool:
    """Return whether ``provider_model_id`` may be activated for routing.

    An empty allowlist means discovery is authoritative and every model is
    activatable; a non-empty one restricts activation to its listed ids, which
    are compared exactly because provider model ids are case-sensitive.
    """
    return not allowlist or provider_model_id in allowlist


def discover_models(
    connection: ProviderConnection,
    manifest: ProviderManifest,
    client: DiscoverableModelClient,
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

    allowlist = manifest.activation_allowlist
    new_route_ids: list[str] = []
    restored_route_ids: list[str] = []
    deferred_route_ids: list[str] = []

    for provider_model_id in discovered:
        route_id = _route_id(connection_id, provider_model_id)
        activated = _is_activated(allowlist, provider_model_id)
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

    discovered_route_ids = {
        _route_id(connection_id, provider_model_id) for provider_model_id in discovered
    }
    unavailable_route_ids = _mark_vanished_unavailable(
        catalog, connection_id, discovered_route_ids
    )

    return ModelDiscoveryResult(
        connection_id=connection_id,
        discovered_route_ids=tuple(
            _route_id(connection_id, provider_model_id)
            for provider_model_id in discovered
        ),
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

    **Invariant: per-connection scoping.** The scan is restricted to routes
    whose id starts with this connection's ``{connection_id}:`` prefix, so
    reconciling connection A can never deactivate connection B's routes — even
    when the two catalogs share one ``ModelRouteCatalog`` and A's discovery
    omits a model id that B also advertises. ``_connection_candidate_route_ids``
    performs that filtering and is the single place the prefix rule lives.

    Only called for a non-empty discovery result (rule 6 guards the empty case),
    so absence is real routing information here. Every candidate is first
    checked for membership of this pass's discovered ids — an advertised route
    is never a vanish candidate — and already-unavailable routes are not
    re-reported, so repeated discoveries produce no churn. Disappearance does
    not advance ``last_seen_at`` (rule 3): the route keeps the stamp of the last
    pass that advertised it. Returns ids in sorted order.
    """
    unavailable: list[str] = []
    for route_id in sorted(
        _connection_candidate_route_ids(catalog, connection_id, discovered_route_ids)
    ):
        if route_id in discovered_route_ids:
            continue
        route = catalog.get(route_id)
        if route is None or not route.available:
            continue
        catalog.mark_unavailable(route_id)
        unavailable.append(route_id)
    return tuple(unavailable)


def _connection_candidate_route_ids(
    catalog: ModelRouteCatalog,
    connection_id: str,
    discovered_route_ids: set[str],
) -> set[str]:
    """Return only the route ids that belong to ``connection_id``.

    This helper exists to make the cross-connection safety property explicit
    and testable: **a route whose id does not carry this connection's
    ``{connection_id}:`` prefix is never a candidate for deactivation**, no
    matter what the catalog holds or what the discovery result contains. A
    route id is ``f"{connection.connection_id}:{provider_model_id}"`` (rule 1),
    so the prefix is the connection's identity inside a flat, connection-agnostic
    catalog — the catalog has no per-connection accessor and this module must
    not add one. Dropping the prefix filter would let connection A's reconcile
    flip connection B's routes unavailable whenever B's model ids are absent
    from A's list.
    """
    prefix = f"{connection_id}:"
    stored = _stored_route_ids(catalog)
    return {
        route_id
        for route_id in discovered_route_ids | stored
        if route_id.startswith(prefix)
    }


def _stored_route_ids(catalog: ModelRouteCatalog) -> set[str]:
    """Return the ids of every available route currently in ``catalog``.

    ``ModelRouteCatalog`` exposes lookups by route id but no enumeration, and
    this module must not add an accessor to another module's class.
    ``routes_for_connection`` does not exist, so the catalog is read through its
    own surfaces instead: an empty requirement tuple makes
    ``filter_required_capabilities(())`` return every *available* route (the
    availability check is that query's only filter).

    This deliberately enumerates **all** connections' available routes: the
    per-connection scoping is applied by ``_connection_candidate_route_ids``
    through the ``{connection_id}:`` route-id prefix. Keeping a single scoping
    site is what makes the cross-connection invariant testable — a second,
    redundant filter here would silently mask the removal of the prefix check.
    Already-unavailable routes are excluded here because they cannot newly
    become unavailable and are deliberately not re-reported.
    """
    return {
        route_id
        for route_id in (
            route.route_id for route in catalog.filter_required_capabilities(())
        )
        if (route := catalog.get(route_id)) is not None and route.available
    }
