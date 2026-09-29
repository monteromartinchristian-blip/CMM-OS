"""CMMChat Wave E0 — the canonical CMMChat Router provider and seam composition.

The CMMChat Router is the provider/model access boundary of this program: one
loopback-only, OpenAI-compatible, ``CHAT_ONLY`` endpoint at
``http://127.0.0.1:8790/v1``.  This module turns that endpoint into a canonical
CMM OS provider **without adding any provider machinery of its own**:

* the provider definition is an ordinary canonical
  :class:`~kernel.llm.provider_registry.ProviderSpec`, with the bearer resolved
  through its own ``api_key_env`` mechanism and the endpoint pinned to loopback;
* the model identity is an ordinary canonical
  :class:`~kernel.llm.model_catalog.ModelSpec` registered in a canonical
  :class:`~kernel.llm.model_catalog.ModelCatalog` bound to the **canonical
  provider registry instance the caller hands in** — the Phase 11.1 composition
  binds that instance as ``provider.registry``, so no second registry and no
  second catalog abstraction is created;
* discovery reuses the canonical discovery contract (a client exposing
  ``list_models()``), performed by the canonical
  :class:`~kernel.llm.clients.openai_compatible_client.OpenAICompatibleClient`;
* the seam is the canonical
  :class:`~cmm.model_execution.executor.CanonicalModelExecutor` over the
  canonical ``ModelRouter`` and ``ProviderFactory``.

Loopback rule: a non-loopback endpoint is refused at composition time, so this
seam can never reach the router over LAN even if the configuration is edited.

Local runtime lane: the seam additionally composes one ordinary canonical
provider for a loopback-only, OpenAI-compatible local model runtime (configured
through the environment variables named below).  It is registered in the same
canonical registry and catalog and executed by the same canonical factory,
router and provider abstraction — no second or provider-specific machinery.

Residual limit (stated openly): the bearer itself is resolved by the canonical
``ProviderSpec`` at call time, so a *later* environment change is honoured by
the canonical mechanism; only the endpoint is pinned here.
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlsplit

from cmm.model_execution.executor import CanonicalModelExecutor
from kernel.llm.local_runtime_discovery import (
    MIN_REFRESH_INTERVAL_SECONDS,
    LocalRuntimeSnapshot,
    discover_local_runtimes_throttled,
    load_endpoints,
    load_snapshot,
    store_snapshot,
)
from cmm.model_execution.lanes import (
    CHAT_ONLY_ROUTER_PROVIDER_ID,
    LOCAL_RUNTIME_EGRESS_ENV,
    LOCAL_RUNTIME_PROVIDER_ID,
    lane_egress_class,
    lane_locality,
)
from kernel.llm.capabilities import ModelCapabilities, ProviderCapabilities
from kernel.llm.clients.openai_compatible_client import (
    OpenAICompatibleClient,
    configured_reasoning_effort_map,
    configured_vendor_map,
)
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_router import ModelRouter
from kernel.llm.provider_factory import ProviderFactory
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

__all__ = [
    "CHAT_ONLY_ROUTER_BASE_URL",
    "CHAT_ONLY_ROUTER_BASE_URL_ENV",
    "CHAT_ONLY_ROUTER_BEARER_ENV",
    "CHAT_ONLY_ROUTER_CONTEXT_WINDOW",
    "CHAT_ONLY_ROUTER_MODEL_ENV",
    "CHAT_ONLY_ROUTER_PROVIDER_ID",
    "LOCAL_RUNTIME_API_KEY_ENV",
    "LOCAL_RUNTIME_BASE_URL_ENV",
    "LOCAL_RUNTIME_DEFAULT_BASE_URL",
    "LOCAL_RUNTIME_EGRESS_ENV",
    "LOCAL_RUNTIME_MODEL_IDS_ENV",
    "LOCAL_RUNTIME_VISION_MODEL_IDS_ENV",
    "LOCAL_RUNTIME_PROVIDER_ID",
    "LocalModelExecution",
    "build_local_model_execution",
    "chat_only_router_provider_spec",
    "configured_local_runtime_model_ids",
    "configured_model_ids",
    "discover_chat_only_router_models",
    "lane_egress_class",
    "lane_locality",
    "local_runtime_model_vendors",
    "local_runtime_provider_spec",
    "register_chat_only_router",
    "register_discovered_local_runtimes",
    "register_local_runtime",
    "router_disabled",
]

#: The CMMChat Router's documented loopback OpenAI-compatible root.
CHAT_ONLY_ROUTER_BASE_URL = "http://127.0.0.1:8790/v1"

#: The canonical ``ProviderSpec`` environment mechanisms: the bearer (existing
#: supported credential mechanism, never a value in code, tests or docs) and the
#: model identity this canary executes.
CHAT_ONLY_ROUTER_BEARER_ENV = "CMM_ROUTER_TOKEN"
CHAT_ONLY_ROUTER_MODEL_ENV = "CMM_ROUTER_MODEL"

#: Launcher override of the router endpoint for local E2E stacks.  It goes
#: through the same loopback gate as the pinned default, so the override can
#: move the port a test router listens on but can never move the lane off this
#: machine.
CHAT_ONLY_ROUTER_BASE_URL_ENV = "CMM_ROUTER_BASE_URL"

#: The declared context floor of a router model.  The router's ``/v1/models``
#: advertises identities only, and the canonical router refuses a model without
#: a context window, so a conservative floor is declared rather than a provider
#: claim being invented.
CHAT_ONLY_ROUTER_CONTEXT_WINDOW = 32_000

#: The Phase 11.1 composition service id of the one canonical provider registry.
PROVIDER_REGISTRY_SERVICE_ID = "provider.registry"

#: The endpoint and configuration of the loopback local model runtime lane.
#: Model ids are configured explicitly (never bulk-discovered) so credit-gated
#: or broken advertisements cannot enter the catalog.
#: The credential stays an env-resolved name: a loopback runtime ignores its
#: value, but the canonical OpenAI-compatible transport requires a non-empty
#: bearer, so the launcher supplies a placeholder through this variable.
LOCAL_RUNTIME_DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
LOCAL_RUNTIME_BASE_URL_ENV = "CMM_LOCAL_RUNTIME_BASE_URL"
LOCAL_RUNTIME_MODEL_IDS_ENV = "CMM_LOCAL_RUNTIME_MODEL_IDS"
LOCAL_RUNTIME_VISION_MODEL_IDS_ENV = "CMM_LOCAL_RUNTIME_VISION_MODEL_IDS"
LOCAL_RUNTIME_API_KEY_ENV = "CMM_LOCAL_RUNTIME_API_KEY"
LOCAL_RUNTIME_CONTEXT_WINDOW = 32_000

#: Hosts that count as loopback for the router endpoint.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _require_loopback_endpoint(base_url: str) -> str:
    """Return the normalized loopback endpoint, or fail closed."""

    if not isinstance(base_url, str):
        raise TypeError("base_url must be a string")
    normalized = base_url.strip()
    if not normalized:
        raise ValueError("the CMMChat Router endpoint cannot be empty")

    parts = urlsplit(normalized)
    if parts.scheme.lower() not in ("http", "https"):
        raise ValueError("the CMMChat Router endpoint must be an http(s) URL")
    if parts.username is not None or parts.password is not None:
        raise ValueError("the CMMChat Router endpoint cannot contain userinfo")
    if (parts.hostname or "").lower() not in _LOOPBACK_HOSTS:
        raise ValueError(
            "the CMMChat Router endpoint must be a loopback host "
            "(127.0.0.1, localhost or ::1)"
        )
    return normalized.rstrip("/")


def chat_only_router_provider_spec(*, base_url: str | None = None) -> ProviderSpec:
    """Return the canonical provider definition of the CMMChat Router."""

    configured = (
        base_url if base_url is not None else os.getenv(CHAT_ONLY_ROUTER_BASE_URL_ENV)
    )
    # A supplied endpoint — including a blank one — must reach the loopback gate
    # so it fails closed; only an absent override falls back to the pinned root.
    # ``configured or DEFAULT`` would silently turn a blank override into the
    # default and defeat the gate.
    endpoint = CHAT_ONLY_ROUTER_BASE_URL if configured is None else configured
    return ProviderSpec(
        id=CHAT_ONLY_ROUTER_PROVIDER_ID,
        provider_type="local",
        api_style="chat_completions",
        api_key_env=CHAT_ONLY_ROUTER_BEARER_ENV,
        base_url=_require_loopback_endpoint(endpoint),
        capabilities=ProviderCapabilities(chat_completions=True, streaming=True),
    )


def configured_model_ids() -> tuple[str, ...] | None:
    """Return the explicitly configured model identities, or ``None``.

    The canonical configuration mechanism is the environment variable named by
    :data:`CHAT_ONLY_ROUTER_MODEL_ENV`; when it is absent or empty the caller is
    expected to discover the identities from the running router instead.
    """

    raw = os.getenv(CHAT_ONLY_ROUTER_MODEL_ENV)
    if raw is None:
        return None
    identities = tuple(
        dict.fromkeys(part.strip() for part in raw.split(",") if part.strip())
    )
    return identities or None


def router_disabled() -> bool:
    """Whether the router lane is explicitly disabled by configuration.

    Disabling is a launcher decision (``CMM_ROUTER_DISABLED=1``): the seam then
    composes only the configured lanes (e.g. the local runtime) and never
    contacts the router.
    """

    return os.getenv("CMM_ROUTER_DISABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


#: One model as the CMMChat Router declares it, as
#: ``(id, vendor, display_name, version, locality)``.  A plain tuple, not an
#: owner type: this is a value crossing a boundary, and the transport-neutral
#: package deliberately owns no vocabulary for one.  Every optional field is the
#: authority's own statement; ``None`` means the authority declared nothing,
#: which is carried through as an honest unknown rather than reconstructed from
#: the id — a rolling alias such as a bare ``sonnet`` route genuinely names no
#: version, and a display name is a fact the upstream publishes.
_RouterModel = tuple[str, str | None, str | None, str | None, "Literal['local', 'cloud'] | None"]


def _declared_vendor(item: Mapping[str, Any]) -> str | None:
    owner = item.get("owned_by")
    if isinstance(owner, str) and owner.strip():
        return owner.strip()
    return None


def _declared_text(item: Mapping[str, Any], key: str) -> str | None:
    value = item.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _declared_locality(item: Mapping[str, Any]) -> Literal["local", "cloud"] | None:
    value = item.get("locality")
    if value in ("local", "cloud"):
        return value
    return None


def discover_chat_only_router_models(
    *, client: object | None = None, base_url: str | None = None
) -> tuple[str, ...]:
    """Discover the router's model identities over the canonical contract.

    ``client`` is an already-built transport exposing the canonical discovery
    method ``list_models()``; production passes ``None`` and the canonical
    OpenAI-compatible client is built from the provider definition's own bearer
    and base URL.  An empty or malformed advertisement fails closed.
    """

    spec = chat_only_router_provider_spec(base_url=base_url)
    transport = client or OpenAICompatibleClient(
        api_key=spec.resolve_api_key(), base_url=spec.resolve_base_url()
    )
    advertised = tuple(transport.list_models())  # type: ignore[attr-defined]

    identities: list[str] = []
    for identity in advertised:
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("the CMMChat Router advertised a malformed model id")
        identities.append(identity.strip())
    if not identities:
        raise ValueError("the CMMChat Router advertised no model")
    return tuple(dict.fromkeys(identities))


def discover_chat_only_router_model_vendors(
    *, client: object | None = None, base_url: str | None = None
) -> tuple[tuple[str, str | None], ...]:
    """The narrow ``(id, vendor)`` view of the router's catalog.

    Kept as a stable projection over :func:`discover_chat_only_router_models_full`
    for callers that need only the identity and the declared vendor.  A new
    caller should prefer the full form, which also carries the authority's
    display name, version and egress class.
    """

    return tuple(
        (entry[0], entry[1])
        for entry in discover_chat_only_router_models_full(
            client=client, base_url=base_url
        )
    )


def discover_chat_only_router_models_full(
    *, client: object | None = None, base_url: str | None = None
) -> tuple[tuple, ...]:
    """Discover the router's models with the vendor each one declares.

    One ``/models`` call, so the identities and their vendors can never
    disagree.  The vendor is the authority's own ``owned_by`` — the router
    already distinguishes ``cmm:chatgpt`` from ``cmm:claude`` — and a model the
    authority declares nothing about carries ``None`` rather than a guess.

    A transport that only implements the narrower ``list_models()`` contract is
    still supported: every model then reports an unknown vendor.
    """

    spec = chat_only_router_provider_spec(base_url=base_url)
    transport = client or OpenAICompatibleClient(
        api_key=spec.resolve_api_key(), base_url=spec.resolve_base_url()
    )
    # Prefer the lossless wire read: the SDK's typed model keeps only
    # ``id``/``object``/``owned_by``/``created``, so the authority's published
    # display name, version and egress class would be discarded at the first
    # boundary and the product would be left re-deriving them from the id.
    list_descriptors = getattr(transport, "list_model_descriptors", None)
    list_vendors = getattr(transport, "list_model_vendors", None)
    if callable(list_descriptors):
        descriptors = list_descriptors()
        advertised = tuple(
            (
                identity,
                _declared_vendor(item),
                _declared_text(item, "display_name"),
                _declared_text(item, "version"),
                _declared_locality(item),
            )
            for identity, item in descriptors.items()
        )
    elif callable(list_vendors):
        advertised = tuple((identity, vendor, None, None, None) for identity, vendor in list_vendors().items())
    else:
        advertised = tuple(
            (identity, None, None, None, None)
            for identity in tuple(transport.list_models())  # type: ignore[attr-defined]
        )

    discovered: list[tuple] = []
    for identity, vendor, display_name, version, locality in advertised:
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("the CMMChat Router advertised a malformed model id")
        if vendor is not None and (
            not isinstance(vendor, str) or not vendor.strip()
        ):
            raise ValueError("the CMMChat Router advertised a malformed vendor")
        if locality is not None and locality not in ("local", "cloud"):
            raise ValueError("the CMMChat Router advertised a malformed locality")
        discovered.append(
            (identity.strip(), vendor, display_name, version, locality)
        )
    if not discovered:
        raise ValueError("the CMMChat Router advertised no model")

    deduplicated: dict[str, tuple] = {}
    for entry in discovered:
        existing = deduplicated.get(entry[0])
        if existing is None:
            deduplicated[entry[0]] = entry
            continue
        # Keep the richest truth the authority published for this identity.
        deduplicated[entry[0]] = tuple(
            existing[index] or entry[index] for index in range(5)
        )
    return tuple(deduplicated.values())


def register_chat_only_router(
    *,
    provider_registry: ProviderRegistry,
    model_catalog: ModelCatalog,
    model_ids: tuple[str, ...],
    base_url: str | None = None,
    model_vendors: Mapping[str, str | None] | None = None,
    declared: tuple[tuple, ...] | None = None,
) -> tuple[ProviderSpec, tuple[ModelSpec, ...]]:
    """Register the router provider and its model identities canonically.

    The provider identity is registered in the canonical registry the caller
    supplied and the models in the canonical catalog bound to that same
    registry.  Re-registering the canonical definition is idempotent (the
    already-registered definition is reused), while a *divergent* definition
    claiming the canonical router identity — or, above all, a non-loopback
    endpoint — fails closed.

    ``model_vendors`` carries the serving vendor the router declared for each
    identity (its ``owned_by``); an identity absent from it, or mapped to
    ``None``, registers with no vendor rather than a guessed one.

    ``declared`` carries the router's full per-model statements as
    ``(id, vendor, display_name, version, locality)``.  Each optional field is
    the authority's own and is carried through unchanged: a display name the
    router published is never re-derived from the id, a version the router did
    not state stays absent, and an egress class the router declared is not
    overwritten by the lane default.  It only ever *annotates* identities the
    caller supplied; it can never introduce a model.
    """

    if provider_registry is None or not isinstance(provider_registry, ProviderRegistry):
        raise TypeError("provider_registry must be a ProviderRegistry")
    if model_catalog is None or not isinstance(model_catalog, ModelCatalog):
        raise TypeError("model_catalog must be a ModelCatalog")
    if model_catalog.provider_registry is not provider_registry:
        raise TypeError(
            "model_catalog must be bound to the supplied canonical provider_registry"
        )

    router_effort_map = configured_reasoning_effort_map(CHAT_ONLY_ROUTER_PROVIDER_ID)
    vendors = dict(model_vendors or {})
    facts: dict[str, tuple] = {}
    for entry in declared or ():
        facts[entry[0]] = entry
    for vendor_value in vendors.values():
        if vendor_value is not None and (
            not isinstance(vendor_value, str) or not vendor_value.strip()
        ):
            raise ValueError("model_vendors values must be non-empty strings or None")
    identities = tuple(dict.fromkeys(model_ids))
    if not identities:
        raise ValueError("model_ids cannot be empty")
    for identity in identities:
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("model_ids must contain non-empty strings")

    declared = chat_only_router_provider_spec(base_url=base_url)
    if provider_registry.has(declared.id):
        registered = provider_registry.get(declared.id)
        if registered != declared:
            raise ValueError(
                "a different provider definition already claims the CMMChat "
                f"Router identity: {declared.id}"
            )
    else:
        registered = provider_registry.register(declared)

    models: list[ModelSpec] = []
    for identity in identities:
        normalized = identity.strip()
        if model_catalog.has(normalized, provider_id=registered.id):
            models.append(model_catalog.get(normalized, provider_id=registered.id))
            continue
        # The router advertises bare model ids, so without this the provider's
        # real reasoning capability was silently lost at the boundary and every
        # downstream client hid its effort control. The operator-declared effort
        # map is the same sanctioned mechanism the local runtime uses: nothing is
        # invented here, an undeclared model still fails closed to no effort.
        declared_efforts = tuple(router_effort_map.get(normalized.lower(), {}))
        fact = facts.get(normalized)
        declared_display_name = fact[2] if fact is not None else None
        declared_version = fact[3] if fact is not None else None
        declared_locality = fact[4] if fact is not None else None
        models.append(
            model_catalog.register(
                ModelSpec(
                    id=normalized,
                    provider_id=registered.id,
                    # The router's own label, when it published one. Left
                    # absent otherwise, so the projection below falls back to
                    # the id rather than inventing a name.
                    display_name=declared_display_name,
                    locality=declared_locality,
                    version=declared_version,
                    context_window=CHAT_ONLY_ROUTER_CONTEXT_WINDOW,
                    vendor=fact[1] if fact is not None else vendors.get(normalized),
                    capabilities=ModelCapabilities(
                        streaming=True,
                        reasoning=bool(declared_efforts),
                        reasoning_efforts=declared_efforts,
                    ),
                )
            )
        )
    return registered, tuple(models)


def local_runtime_provider_spec(*, base_url: str | None = None) -> ProviderSpec:
    """Return the canonical provider definition of the local model runtime."""

    resolved = base_url
    if resolved is None:
        resolved = (
            os.getenv(LOCAL_RUNTIME_BASE_URL_ENV) or LOCAL_RUNTIME_DEFAULT_BASE_URL
        )
    return ProviderSpec(
        id=LOCAL_RUNTIME_PROVIDER_ID,
        provider_type="local",
        api_style="chat_completions",
        api_key_env=LOCAL_RUNTIME_API_KEY_ENV,
        base_url=_require_loopback_endpoint(resolved),
        capabilities=ProviderCapabilities(chat_completions=True, streaming=True),
    )


def configured_local_runtime_model_ids() -> tuple[str, ...] | None:
    """Return the explicitly configured local runtime identities, or ``None``.

    The local runtime lane is opt-in: absent configuration composes exactly
    the router-only seam as before.
    """

    raw = os.getenv(LOCAL_RUNTIME_MODEL_IDS_ENV)
    if raw is None:
        return None
    identities = tuple(
        dict.fromkeys(part.strip() for part in raw.split(",") if part.strip())
    )
    return identities or None


def register_local_runtime(
    *,
    provider_registry: ProviderRegistry,
    model_catalog: ModelCatalog,
    model_ids: tuple[str, ...],
    base_url: str | None = None,
    model_vendors: Mapping[str, str | None] | None = None,
) -> tuple[ProviderSpec, tuple[ModelSpec, ...]]:
    """Register the local runtime provider and its models canonically.

    Same guarantees as :func:`register_chat_only_router`: the definition lives
    in the caller's canonical registry, the models in the canonical catalog
    bound to it, re-registration of the canonical definition is idempotent and
    a divergent definition claiming this identity fails closed.

    ``model_vendors`` only *annotates* the identities the launcher configured:
    it can never add a model, so the "never bulk-discovered" guarantee above is
    unaffected by it.
    """

    if provider_registry is None or not isinstance(provider_registry, ProviderRegistry):
        raise TypeError("provider_registry must be a ProviderRegistry")
    if model_catalog is None or not isinstance(model_catalog, ModelCatalog):
        raise TypeError("model_catalog must be a ModelCatalog")
    if model_catalog.provider_registry is not provider_registry:
        raise TypeError(
            "model_catalog must be bound to the supplied canonical provider_registry"
        )

    identities = tuple(dict.fromkeys(model_ids))
    if not identities:
        raise ValueError("model_ids cannot be empty")
    for identity in identities:
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("model_ids must contain non-empty strings")

    declared = local_runtime_provider_spec(base_url=base_url)
    if provider_registry.has(declared.id):
        registered = provider_registry.get(declared.id)
        if registered != declared:
            raise ValueError(
                "a different provider definition already claims the local "
                f"runtime identity: {declared.id}"
            )
    else:
        registered = provider_registry.register(declared)

    vision_ids = {
        part.strip().lower()
        for part in os.getenv(
            LOCAL_RUNTIME_VISION_MODEL_IDS_ENV,
            "",
        ).split(",")
        if part.strip()
    }
    effort_map = configured_reasoning_effort_map(LOCAL_RUNTIME_PROVIDER_ID)
    vendors = dict(model_vendors or {})
    for vendor_value in vendors.values():
        if vendor_value is not None and (
            not isinstance(vendor_value, str) or not vendor_value.strip()
        ):
            raise ValueError("model_vendors values must be non-empty strings or None")

    models: list[ModelSpec] = []
    for identity in identities:
        normalized = identity.strip()
        if model_catalog.has(normalized, provider_id=registered.id):
            models.append(model_catalog.get(normalized, provider_id=registered.id))
            continue
        declared_efforts = tuple(effort_map.get(normalized.lower(), {}))
        models.append(
            model_catalog.register(
                ModelSpec(
                    id=normalized,
                    provider_id=registered.id,
                    context_window=LOCAL_RUNTIME_CONTEXT_WINDOW,
                    vendor=vendors.get(normalized),
                    capabilities=ModelCapabilities(
                        vision=normalized.lower() in vision_ids,
                        streaming=True,
                        reasoning=bool(declared_efforts),
                        reasoning_efforts=declared_efforts,
                    ),
                )
            )
        )
    return registered, tuple(models)


@dataclass(frozen=True, slots=True)
class LocalModelExecution:
    """One composed local model execution graph.

    ``provider_spec`` is the definition the canonical registry holds,
    ``models`` are the canonical catalog entries registered for it and
    ``executor`` is the canonical seam over both.
    """

    provider_spec: ProviderSpec
    models: tuple[ModelSpec, ...]
    executor: CanonicalModelExecutor


def local_runtime_model_vendors(model_ids: tuple[str, ...]) -> dict[str, str | None]:
    """Return the operator-declared vendor of each configured local-runtime model.

    A runtime that fronts hosted upstreams serves models that are not local at
    all, and a catalog row that says merely "local" would be a false statement
    about where the context goes.  The vendor is therefore declared by the
    launcher — the same sanctioned mechanism the reasoning-effort map uses —
    rather than probed: probing this lane during composition would put an
    unbounded network call on the catalog path, where a runtime that accepts a
    connection and never answers would block every model from being listed.

    The declaration is an *annotation* of identities the launcher already
    configured, so it can never add a model; an identity absent from the map
    registers with no vendor rather than a guessed one.
    """

    declared = configured_vendor_map(LOCAL_RUNTIME_PROVIDER_ID)
    return {
        identity.strip(): declared.get(identity.strip().lower())
        for identity in model_ids
        if identity.strip()
    }


#: Prefix of the canonical provider identity of a discovered local runtime.
#: One identity per runtime, because locality is a per-model fact: a single
#: runtime can hold on-device weights *and* forward other models to a hosted
#: upstream, which one lane-level locality could not honestly describe.
DISCOVERED_LOCAL_RUNTIME_ID_PREFIX = "local-"


def register_discovered_local_runtimes(
    *,
    provider_registry: ProviderRegistry,
    model_catalog: ModelCatalog,
    snapshot: "LocalRuntimeSnapshot",
) -> tuple[tuple[ProviderSpec, ...], tuple[ModelSpec, ...]]:
    """Register every model a local runtime discovery actually found.

    Each discovered runtime becomes its own canonical provider definition and
    every model it reported becomes a canonical catalog entry carrying the
    egress class the runtime itself stated.  A model the runtime said is
    forwarded to an upstream is registered as ``cloud`` even though it answers
    on loopback: the endpoint says where the process runs, not where the
    context goes.

    A runtime that could not be reached contributes its retained models marked
    unavailable, so a runtime that is simply down removes nothing.
    """

    if provider_registry is None or not isinstance(provider_registry, ProviderRegistry):
        raise TypeError("provider_registry must be a ProviderRegistry")
    if model_catalog is None or not isinstance(model_catalog, ModelCatalog):
        raise TypeError("model_catalog must be a ModelCatalog")
    if model_catalog.provider_registry is not provider_registry:
        raise TypeError(
            "model_catalog must be bound to the supplied canonical provider_registry"
        )

    endpoints = {e.name: e for e in load_endpoints()}
    specs: list[ProviderSpec] = []
    models: list[ModelSpec] = []

    by_runtime: dict[str, list[Any]] = {}
    for entry in snapshot.models:
        by_runtime.setdefault(entry.runtime, []).append(entry)

    for runtime_name, runtime_models in sorted(by_runtime.items()):
        provider_id = f"{DISCOVERED_LOCAL_RUNTIME_ID_PREFIX}{runtime_name}"
        reachable = snapshot.runtime_states.get(runtime_name) == "available"
        endpoint = endpoints.get(runtime_name)
        spec = ProviderSpec(
            id=provider_id,
            provider_type="local",
            api_style="chat_completions",
            api_key_env=endpoint.api_key_env if endpoint is not None else None,
            base_url=(
                endpoint.base_url
                if endpoint is not None
                else LOCAL_RUNTIME_DEFAULT_BASE_URL
            ),
            availability="available" if reachable else "unavailable",
            capabilities=ProviderCapabilities(chat_completions=True, streaming=True),
        )
        if provider_registry.has(spec.id):
            registered = provider_registry.register(spec, replace_existing=True)
        else:
            registered = provider_registry.register(spec)
        specs.append(registered)

        for entry in sorted(runtime_models, key=lambda m: m.id):
            status = snapshot.status_of(entry.id)
            qualified = f"{registered.id}/{entry.id}"
            model_spec = ModelSpec(
                id=qualified,
                provider_id=registered.id,
                display_name=entry.display_name,
                locality=entry.locality,
                vendor=entry.vendor,
                version=entry.version,
                context_window=entry.context_window,
                availability="available" if status == "available" else "unavailable",
                capabilities=ModelCapabilities(streaming=True, reasoning=False),
            )
            if model_catalog.has(qualified, provider_id=registered.id):
                models.append(model_catalog.register(model_spec, replace_existing=True))
            else:
                models.append(model_catalog.register(model_spec))
    return tuple(specs), tuple(models)



def build_local_model_execution(
    *,
    provider_registry: ProviderRegistry,
    model_ids: tuple[str, ...] | None = None,
    base_url: str | None = None,
    client: object | None = None,
) -> LocalModelExecution:
    """Compose the canonical seam over the canonical provider registry.

    The registry is the **existing canonical instance** — the Phase 11.1
    composition binds it as ``provider.registry`` — and is never replaced: this
    function creates no registry, no catalog abstraction and no provider.  The
    canonical catalog it builds is bound to that instance, the canonical router
    selects the model and the canonical factory materializes the provider.
    """

    if provider_registry is None or not isinstance(provider_registry, ProviderRegistry):
        raise TypeError("provider_registry must be the canonical ProviderRegistry")

    model_catalog = ModelCatalog(provider_registry)
    provider_spec: ProviderSpec | None = None
    models: tuple[ModelSpec, ...] = ()

    if not router_disabled():
        resolved_ids = model_ids if model_ids is not None else configured_model_ids()
        # The router's own per-model statements, present only when discovery
        # actually ran. Absent means "this composition was handed explicit ids",
        # and then nothing is claimed on the router's behalf.
        discovered: tuple[tuple, ...] = ()
        if resolved_ids is None:
            discovered = discover_chat_only_router_models_full(
                client=client, base_url=base_url
            )
            resolved_ids = tuple(entry[0] for entry in discovered)
        provider_spec, models = register_chat_only_router(
            provider_registry=provider_registry,
            model_catalog=model_catalog,
            model_ids=tuple(resolved_ids),
            base_url=base_url,
            declared=discovered,
        )

    local_ids = configured_local_runtime_model_ids()
    if local_ids:
        local_spec, local_models = register_local_runtime(
            provider_registry=provider_registry,
            model_catalog=model_catalog,
            model_ids=local_ids,
            model_vendors=local_runtime_model_vendors(model_ids=local_ids),
        )
        if provider_spec is None:
            provider_spec, models = local_spec, local_models

    # Real on-device runtimes.  These are discovered, not declared: the
    # launcher names the runtimes and the runtimes name their models, so a
    # model that is installed and running appears without any configuration
    # listing it, and one that disappears is retired only once its absence has
    # been confirmed.
    discovered_specs, discovered_models = register_discovered_local_runtimes(
        provider_registry=provider_registry,
        model_catalog=model_catalog,
        snapshot=discover_local_runtimes_throttled(),
    )
    if provider_spec is None and discovered_specs:
        provider_spec, models = discovered_specs[0], discovered_models

    if provider_spec is None:
        raise ValueError(
            "no model lane is configured: enable the CMMChat Router or "
            "configure the local runtime"
        )

    executor = CanonicalModelExecutor(
        model_router=ModelRouter(
            provider_registry=provider_registry, model_catalog=model_catalog
        ),
        provider_factory=ProviderFactory(),
        provider_registry=provider_registry,
        model_catalog=model_catalog,
        client=client,
    )
    return LocalModelExecution(
        provider_spec=provider_spec, models=models, executor=executor
    )
