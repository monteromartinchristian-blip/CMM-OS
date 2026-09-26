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
from dataclasses import dataclass
from urllib.parse import urlsplit

from cmm.model_execution.executor import CanonicalModelExecutor
from kernel.llm.capabilities import ModelCapabilities, ProviderCapabilities
from kernel.llm.clients.openai_compatible_client import (
    OpenAICompatibleClient,
    configured_reasoning_effort_map,
)
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_router import ModelRouter
from kernel.llm.provider_factory import ProviderFactory
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

__all__ = [
    "CHAT_ONLY_ROUTER_BASE_URL",
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
    "local_runtime_provider_spec",
    "register_chat_only_router",
    "register_local_runtime",
    "router_disabled",
]

#: The one provider identity the CMMChat Router holds inside CMM OS.
CHAT_ONLY_ROUTER_PROVIDER_ID = "cmmchat-router"

#: The CMMChat Router's documented loopback OpenAI-compatible root.
CHAT_ONLY_ROUTER_BASE_URL = "http://127.0.0.1:8790/v1"

#: The canonical ``ProviderSpec`` environment mechanisms: the bearer (existing
#: supported credential mechanism, never a value in code, tests or docs) and the
#: model identity this canary executes.
CHAT_ONLY_ROUTER_BEARER_ENV = "CMM_ROUTER_TOKEN"
CHAT_ONLY_ROUTER_MODEL_ENV = "CMM_ROUTER_MODEL"

#: The declared context floor of a router model.  The router's ``/v1/models``
#: advertises identities only, and the canonical router refuses a model without
#: a context window, so a conservative floor is declared rather than a provider
#: claim being invented.
CHAT_ONLY_ROUTER_CONTEXT_WINDOW = 32_000

#: The Phase 11.1 composition service id of the one canonical provider registry.
PROVIDER_REGISTRY_SERVICE_ID = "provider.registry"

#: The identity, endpoint and configuration of the loopback local model
#: runtime lane.  Model ids are configured explicitly (never bulk-discovered)
#: so credit-gated or broken advertisements cannot enter the catalog.
#: The credential stays an env-resolved name: a loopback runtime ignores its
#: value, but the canonical OpenAI-compatible transport requires a non-empty
#: bearer, so the launcher supplies a placeholder through this variable.
LOCAL_RUNTIME_PROVIDER_ID = "local-runtime"
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

    return ProviderSpec(
        id=CHAT_ONLY_ROUTER_PROVIDER_ID,
        provider_type="local",
        api_style="chat_completions",
        api_key_env=CHAT_ONLY_ROUTER_BEARER_ENV,
        base_url=_require_loopback_endpoint(
            CHAT_ONLY_ROUTER_BASE_URL if base_url is None else base_url
        ),
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


#: Honest egress class of the local-runtime lane: ``local`` only when the
#: launcher declares the runtime processes data on this device (a tunneled or
#: remote runtime must be declared ``remote``).
LOCAL_RUNTIME_EGRESS_ENV = "CMM_LOCAL_RUNTIME_EGRESS"


def lane_egress_class(provider_id: str) -> str:
    """Return ``local`` or ``remote``: does context leave this device?"""

    if provider_id == LOCAL_RUNTIME_PROVIDER_ID:
        declared = os.getenv(LOCAL_RUNTIME_EGRESS_ENV, "local").strip().lower()
        return "remote" if declared == "remote" else "local"
    return "remote"


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


def register_chat_only_router(
    *,
    provider_registry: ProviderRegistry,
    model_catalog: ModelCatalog,
    model_ids: tuple[str, ...],
    base_url: str | None = None,
) -> tuple[ProviderSpec, tuple[ModelSpec, ...]]:
    """Register the router provider and its model identities canonically.

    The provider identity is registered in the canonical registry the caller
    supplied and the models in the canonical catalog bound to that same
    registry.  Re-registering the canonical definition is idempotent (the
    already-registered definition is reused), while a *divergent* definition
    claiming the canonical router identity — or, above all, a non-loopback
    endpoint — fails closed.
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
        models.append(
            model_catalog.register(
                ModelSpec(
                    id=normalized,
                    provider_id=registered.id,
                    context_window=CHAT_ONLY_ROUTER_CONTEXT_WINDOW,
                    capabilities=ModelCapabilities(streaming=True),
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
) -> tuple[ProviderSpec, tuple[ModelSpec, ...]]:
    """Register the local runtime provider and its models canonically.

    Same guarantees as :func:`register_chat_only_router`: the definition lives
    in the caller's canonical registry, the models in the canonical catalog
    bound to it, re-registration of the canonical definition is idempotent and
    a divergent definition claiming this identity fails closed.
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
        if resolved_ids is None:
            resolved_ids = discover_chat_only_router_models(
                client=client, base_url=base_url
            )
        provider_spec, models = register_chat_only_router(
            provider_registry=provider_registry,
            model_catalog=model_catalog,
            model_ids=tuple(resolved_ids),
            base_url=base_url,
        )

    local_ids = configured_local_runtime_model_ids()
    if local_ids:
        local_spec, local_models = register_local_runtime(
            provider_registry=provider_registry,
            model_catalog=model_catalog,
            model_ids=local_ids,
        )
        if provider_spec is None:
            provider_spec, models = local_spec, local_models

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
