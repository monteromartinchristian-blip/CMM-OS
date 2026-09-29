"""Client wrapper for OpenAI-compatible Chat Completions APIs."""

from __future__ import annotations

import importlib
import json
import os
from urllib.parse import urlsplit
from collections.abc import Iterator, Sequence
from threading import Event
from typing import Any

from kernel.llm.capabilities import ReasoningEffort
from kernel.llm.exceptions import ProviderError, ProviderTimeoutError

#: Launcher configuration of the wire fragment each canonical reasoning-effort
#: level needs for a given model on a given provider, e.g.
#: ``{"local-runtime": {"qwen3-1.7b": {"medium":
#: {"chat_template_kwargs": {"enable_thinking": true}}}}}``.
#: Capability declaration and wire transmission read this same map, so a level
#: can never be advertised without a way to put it on the wire.
REASONING_EFFORT_MAP_ENV = "CMM_OPENAI_COMPAT_REASONING_EFFORT_MAP_JSON"

#: Per-request budget for the OpenAI-compatible transport, in seconds.  Unset
#: keeps the SDK default; a vision prefill can legitimately stay silent for
#: minutes, so no product default is imposed here.
TIMEOUT_SECONDS_ENV = "CMM_OPENAI_COMPAT_TIMEOUT_SECONDS"

#: Launcher declaration of which vendor actually serves each model of a lane,
#: e.g. ``{"local-runtime": {"gemini-3.8-flash": "gemini"}}``.  A loopback
#: runtime that fronts hosted upstreams serves models that are not local at
#: all, and the vendor is a fact about the upstream, never about the model id's
#: spelling — so it is declared here rather than probed during composition.
VENDOR_MAP_ENV = "CMM_OPENAI_COMPAT_VENDOR_MAP_JSON"

#: Bearer supplied to a loopback endpoint that was given no credential.
#:
#: The OpenAI-compatible transport cannot construct a client without a non-empty
#: bearer, while a loopback runtime commonly ignores the value entirely. The
#: endpoint is loopback-gated before it is ever used, so this constant grants
#: access to nothing a reachable process would not already allow. It is a
#: transport requirement, not a credential: it is never persisted, never logged
#: and never sent anywhere but the loopback address it was resolved for. An
#: endpoint that *does* check authentication is given a real value by its
#: launcher, which takes precedence.
LOOPBACK_NO_AUTH_BEARER = "loopback-no-auth-required"

#: Hosts that are this machine, and therefore need no credential to address.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def configured_reasoning_effort_map(
    provider_id: str,
) -> dict[str, dict[ReasoningEffort, dict[str, Any]]]:
    """Return configured wire fragments per model id and canonical effort level."""

    raw = os.getenv(REASONING_EFFORT_MAP_ENV, "").strip()
    if not raw:
        return {}

    try:
        configured = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ProviderError(
            "OpenAI-compatible reasoning effort map contains invalid JSON"
        ) from error

    if not isinstance(configured, dict):
        raise ProviderError(
            "OpenAI-compatible reasoning effort map must be a JSON object"
        )

    selected = configured.get(provider_id)
    if selected is None:
        return {}
    if not isinstance(selected, dict):
        raise ProviderError(
            "OpenAI-compatible reasoning effort map entry must be a JSON object"
        )

    parsed: dict[str, dict[ReasoningEffort, dict[str, Any]]] = {}
    for model_id, levels in selected.items():
        if not isinstance(model_id, str) or not model_id.strip():
            raise ProviderError(
                "OpenAI-compatible reasoning effort map keys must be model ids"
            )
        if not isinstance(levels, dict):
            raise ProviderError(
                "a reasoning effort map model entry must be a JSON object"
            )
        efforts: dict[ReasoningEffort, dict[str, Any]] = {}
        for level, fragment in levels.items():
            try:
                effort = ReasoningEffort(level)
            except ValueError as error:
                raise ProviderError(
                    f"unknown canonical reasoning effort level in map: {level}"
                ) from error
            if not isinstance(fragment, dict):
                raise ProviderError(
                    "a reasoning effort wire fragment must be a JSON object"
                )
            efforts[effort] = dict(fragment)
        parsed[model_id.strip().lower()] = efforts
    return parsed


def configured_vendor_map(provider_id: str) -> dict[str, str | None]:
    """Return the launcher-declared serving vendor per model id for one lane.

    Reads :data:`VENDOR_MAP_ENV`, a JSON object keyed by provider id then
    model id, e.g. ``{"local-runtime": {"gemini-3.8-flash": "gemini"}}``.  A
    ``null`` value declares "no vendor known"; any other value must be a
    non-empty string.  This lives beside the effort map because both are
    operator declarations of upstream facts that the bare model id cannot
    carry, and both must be parsed where JSON is a permitted dependency.
    """

    raw = os.getenv(VENDOR_MAP_ENV, "").strip()
    if not raw:
        return {}

    try:
        configured = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ProviderError(
            "OpenAI-compatible vendor map contains invalid JSON"
        ) from error

    if not isinstance(configured, dict):
        raise ProviderError("OpenAI-compatible vendor map must be a JSON object")

    selected = configured.get(provider_id)
    if selected is None:
        return {}
    if not isinstance(selected, dict):
        raise ProviderError(
            "OpenAI-compatible vendor map entry must be a JSON object"
        )

    parsed: dict[str, str | None] = {}
    for model_id, vendor in selected.items():
        if not isinstance(model_id, str) or not model_id.strip():
            raise ProviderError("a vendor map key must be a non-empty model id")
        if vendor is None:
            parsed[model_id.strip().lower()] = None
            continue
        if not isinstance(vendor, str) or not vendor.strip():
            raise ProviderError(
                "a vendor map value must be a non-empty string or null"
            )
        parsed[model_id.strip().lower()] = vendor.strip()
    return parsed


class OpenAICompatibleClient:
    """Small adapter around an OpenAI-compatible client."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        provider_id: str | None = None,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._base_url = base_url
        #: The canonical identity of the provider this client speaks for.  Used
        #: to translate the catalog's *qualified* model id back into the id the
        #: upstream actually knows: the catalog addresses a model as
        #: ``<provider>/<model>`` so two providers cannot collide on a bare name,
        #: but a runtime that discovered its own model has never heard of the
        #: product's namespace for it.
        self._provider_id = provider_id

    def generate(
        self,
        *,
        model: str,
        system: str | None,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> tuple[str, int, int, str]:
        """Generate text and return content, usage, and finish reason."""

        client = self._client or self._build_client()

        messages: list[dict[str, str]] = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        upstream_model = self._provider_model_id(model)
        parameters: dict[str, Any] = {
            "model": upstream_model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            parameters["max_tokens"] = max_tokens

        extra_body = self._extra_body_for_model(upstream_model)
        if extra_body:
            parameters["extra_body"] = extra_body

        try:
            response = client.chat.completions.create(**parameters)
        except Exception as error:  # noqa: BLE001
            self._raise_provider_error(error)

        choices = getattr(response, "choices", None)
        if not choices:
            raise ProviderError("OpenAI-compatible response had no choices")

        choice = choices[0]
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("OpenAI-compatible response was empty")

        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        finish_reason = str(getattr(choice, "finish_reason", "stop") or "stop")

        return (
            content,
            prompt_tokens,
            completion_tokens,
            finish_reason,
        )

    def stream_chat(
        self,
        *,
        model: str,
        messages: Sequence[dict[str, Any]],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        cancel_event: Event | None = None,
        request_extras: Mapping[str, Any] | None = None,
    ) -> Iterator[str]:
        """Yield provider-independent content deltas from a streamed chat call.

        ``messages`` is the already-composed transcript; this transport only
        serializes it and reads back ``choices[0].delta.content`` per chunk. A
        set ``cancel_event`` stops the read loop and the stream is always
        closed.  Every transport defect is normalized through
        :meth:`_raise_provider_error`, so no upstream text or credential
        escapes the yielded deltas.
        """

        client = self._client or self._build_client()

        upstream_model = self._provider_model_id(model)
        parameters: dict[str, Any] = {
            "model": upstream_model,
            "messages": list(messages),
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            parameters["max_tokens"] = max_tokens

        extra_body = dict(self._extra_body_for_model(upstream_model) or {})
        # Per-request extras (a translated reasoning effort, for example) win
        # over the per-model configured overrides: a request states what this
        # call needs, the configuration states the model's standing defaults.
        extra_body.update(dict(request_extras or {}))
        if extra_body:
            parameters["extra_body"] = extra_body

        try:
            stream = client.chat.completions.create(**parameters)
        except Exception as error:  # noqa: BLE001
            self._raise_provider_error(error)

        try:
            for chunk in stream:
                if cancel_event is not None and cancel_event.is_set():
                    break
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                content = getattr(delta, "content", None) if delta is not None else None
                if content:
                    yield content
        except Exception as error:  # noqa: BLE001
            self._raise_provider_error(error)
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001, S110 - best effort
                    pass

    def _provider_model_id(self, model: str) -> str:
        """Resolve a canonical model id to its opaque upstream provider id.

        An explicit map still wins — it is how a route whose upstream id is
        nothing like its catalog id is declared. Absent one, the catalog's own
        namespace is removed when the id carries it, because a runtime that
        published this model knows only the name it published.
        """

        if self._provider_id:
            prefix = f"{self._provider_id}/"
            if model.startswith(prefix):
                stripped = model[len(prefix):]
                if stripped:
                    return stripped

        raw = os.getenv("CMM_OPENAI_COMPAT_MODEL_ID_MAP_JSON", "").strip()
        if not raw:
            return model

        try:
            configured = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ProviderError(
                "OpenAI-compatible model id map contains invalid JSON"
            ) from error

        if not isinstance(configured, dict):
            raise ProviderError(
                "OpenAI-compatible model id map must be a JSON object"
            )

        selected = configured.get(model)
        if selected is None:
            return model

        if not isinstance(selected, str) or not selected.strip():
            raise ProviderError(
                "OpenAI-compatible provider model id must be a non-empty string"
            )

        return selected.strip()

    @staticmethod
    def _extra_body_for_model(model: str) -> dict[str, Any] | None:
        """Return configured non-standard Chat Completions fields for one model."""

        raw = os.getenv("CMM_OPENAI_COMPAT_MODEL_OVERRIDES_JSON", "").strip()
        if not raw:
            return None

        try:
            configured = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ProviderError(
                "OpenAI-compatible model overrides contain invalid JSON"
            ) from error

        if not isinstance(configured, dict):
            raise ProviderError(
                "OpenAI-compatible model overrides must be a JSON object"
            )

        selected = configured.get(model)
        if selected is None:
            return None

        if not isinstance(selected, dict):
            raise ProviderError(
                "OpenAI-compatible model override must be a JSON object"
            )

        return dict(selected)

    def list_models(self) -> tuple[str, ...]:
        """Discover model IDs via the administrative /models endpoint.

        This performs no inference: it only calls ``models.list()`` on
        the underlying SDK client built from the existing connection
        configuration. Provider order is preserved; duplicate IDs are
        rejected rather than silently collapsed. An empty list is a valid
        discovery result returned as an empty tuple; it is never an error.
        """

        client = self._client or self._build_client()

        try:
            response = client.models.list()
        except Exception as error:  # noqa: BLE001
            self._raise_provider_error(error)

        data = getattr(response, "data", None)
        if not isinstance(data, list):
            raise ProviderError(
                "OpenAI-compatible model listing response had no data list"
            )

        model_ids: list[str] = []
        seen: set[str] = set()
        for item in data:
            model_id = getattr(item, "id", None)
            if not isinstance(model_id, str) or not model_id:
                raise ProviderError(
                    f"OpenAI-compatible model listing item lacks a string id: {item!r}"
                )
            if model_id in seen:
                raise ProviderError(
                    f"OpenAI-compatible model listing returned duplicate id: {model_id}"
                )
            seen.add(model_id)
            model_ids.append(model_id)

        return tuple(model_ids)

    def list_model_vendors(self) -> dict[str, str | None]:
        """Discover each model's serving vendor via the same /models endpoint.

        The vendor is the authority's own declaration — an OpenAI-compatible
        listing's ``owned_by`` — and is never derived from the model id's
        spelling.  A listing item that declares nothing maps to ``None``, so a
        caller can present "unknown vendor" instead of a guess.

        Same guarantees as :meth:`list_models`: no inference, provider order
        preserved, duplicate ids refused, an empty listing is a valid result.
        """

        client = self._client or self._build_client()

        try:
            response = client.models.list()
        except Exception as error:  # noqa: BLE001
            self._raise_provider_error(error)

        data = getattr(response, "data", None)
        if not isinstance(data, list):
            raise ProviderError(
                "OpenAI-compatible model listing response had no data list"
            )

        vendors: dict[str, str | None] = {}
        for item in data:
            model_id = getattr(item, "id", None)
            if not isinstance(model_id, str) or not model_id:
                raise ProviderError(
                    f"OpenAI-compatible model listing item lacks a string id: {item!r}"
                )
            if model_id in vendors:
                raise ProviderError(
                    f"OpenAI-compatible model listing returned duplicate id: {model_id}"
                )
            owned_by = getattr(item, "owned_by", None)
            vendor = owned_by.strip() if isinstance(owned_by, str) else ""
            vendors[model_id] = vendor or None

        return vendors

    def list_model_descriptors(self) -> dict[str, dict[str, Any]]:
        """Discover each model's **complete** declared descriptor from the wire.

        :meth:`list_models` and :meth:`list_model_vendors` read the listing
        through the SDK's typed model, which carries only ``id``, ``object``,
        ``owned_by`` and ``created`` and silently discards everything else the
        authority published. That is fine for an identity list and wrong for a
        catalog: a version, a display name and an egress class that the
        authority states are exactly the facts a selector needs, and reading
        them through a lossy type would erase them at the first boundary.

        So this reads ``GET {base_url}/models`` at the wire and keeps every
        declared field. Absent stays absent — an authority that names no version
        produces no version, rather than one reconstructed from the id.

        Same guarantees as the other discovery methods: no inference, provider
        order preserved, duplicate ids refused, malformed items fail closed.
        """

        base_url = self._effective_base_url()
        url = f"{base_url}/models"
        headers = {"Accept": "application/json"}
        api_key = self._effective_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            httpx = importlib.import_module("httpx")
        except ImportError as error:  # pragma: no cover - httpx ships with the SDK
            raise ProviderError(
                "OpenAI-compatible support is not installed. "
                "Install CMM OS with the 'openai' extra."
            ) from error

        try:
            with httpx.Client(timeout=self._configured_timeout()) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except Exception as error:  # noqa: BLE001
            self._raise_provider_error(error)

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise ProviderError(
                "OpenAI-compatible model listing response had no data list"
            )

        descriptors: dict[str, dict[str, Any]] = {}
        for item in data:
            if not isinstance(item, dict):
                raise ProviderError(
                    f"OpenAI-compatible model listing item is not an object: {item!r}"
                )
            model_id = item.get("id")
            if not isinstance(model_id, str) or not model_id:
                raise ProviderError(
                    f"OpenAI-compatible model listing item lacks a string id: {item!r}"
                )
            if model_id in descriptors:
                raise ProviderError(
                    f"OpenAI-compatible model listing returned duplicate id: {model_id}"
                )
            descriptors[model_id] = item
        return descriptors

    def _build_client(self) -> Any:
        try:
            dotenv = importlib.import_module("dotenv")
        except ImportError:
            pass
        else:
            dotenv.load_dotenv()

        try:
            openai = importlib.import_module("openai")
        except ImportError as error:
            raise ProviderError(
                "OpenAI-compatible support is not installed. "
                "Install CMM OS with the 'openai' extra."
            ) from error

        parameters: dict[str, Any] = {}
        # The same rule the descriptor read uses: a loopback endpoint with no
        # configured credential gets the documented placeholder so the SDK can
        # construct a client, while anything off this machine still fails closed
        # rather than being handed a constant.
        effective_key = self._effective_api_key()
        if effective_key is not None:
            parameters["api_key"] = effective_key
        if self._base_url is not None:
            parameters["base_url"] = self._base_url
        configured_timeout = os.getenv(TIMEOUT_SECONDS_ENV, "").strip()
        if configured_timeout:
            try:
                parameters["timeout"] = float(configured_timeout)
            except ValueError as error:
                raise ProviderError(
                    "OpenAI-compatible timeout must be a number of seconds"
                ) from error

        try:
            return openai.OpenAI(**parameters)
        except Exception as error:  # noqa: BLE001
            self._raise_provider_error(error)

    def _effective_base_url(self) -> str:
        """The base URL this client is configured against.

        Taken from the explicit configuration when present, otherwise read back
        from an injected SDK client, so a descriptor read cannot silently fall
        back to the provider's public endpoint.
        """

        if isinstance(self._base_url, str) and self._base_url.strip():
            return self._base_url.strip().rstrip("/")
        base_url = getattr(self._client, "base_url", None)
        if base_url is not None:
            return str(base_url).rstrip("/")
        raise ProviderError("OpenAI-compatible client has no base URL configured")

    def _effective_api_key(self) -> str | None:
        """The bearer this client is configured with.

        A loopback endpoint that was given no credential gets the documented
        placeholder: the transport cannot build a client without a bearer, and
        a loopback runtime ignores one. Anything reachable off this machine
        still fails closed with no bearer, because a placeholder must never
        stand in for a real credential on a network an attacker could see.
        """

        if isinstance(self._api_key, str) and self._api_key:
            return self._api_key
        api_key = getattr(self._client, "api_key", None)
        if isinstance(api_key, str) and api_key:
            return api_key
        try:
            base_url = self._effective_base_url()
        except ProviderError:
            return None
        host = urlsplit(base_url).hostname or ""
        if host.lower() in _LOOPBACK_HOSTS:
            return LOOPBACK_NO_AUTH_BEARER
        return None

    @staticmethod
    def _configured_timeout() -> float | None:
        configured = os.getenv(TIMEOUT_SECONDS_ENV, "").strip()
        if not configured:
            return None
        try:
            return float(configured)
        except ValueError as error:
            raise ProviderError(
                "OpenAI-compatible timeout must be a number of seconds"
            ) from error

    @staticmethod
    def _raise_provider_error(error: Exception) -> None:
        message = str(error)
        lowered = message.lower()

        if "timed out" in lowered or "timeout" in lowered:
            raise ProviderTimeoutError(
                "OpenAI-compatible request timed out"
            ) from error
        if "insufficient_quota" in lowered or "current quota" in lowered:
            raise ProviderError("OpenAI-compatible quota is exhausted") from error
        if "authentication" in lowered or "api key" in lowered or "401" in lowered:
            raise ProviderError("OpenAI-compatible authentication failed") from error
        if "rate limit" in lowered or "429" in lowered:
            raise ProviderError("OpenAI-compatible rate limit exceeded") from error

        raise ProviderError(f"OpenAI-compatible request failed: {message}") from error
