"""Client wrapper for OpenAI-compatible Chat Completions APIs."""

from __future__ import annotations

import importlib
import json
import os
from collections.abc import Iterator, Sequence
from threading import Event
from typing import Any

from kernel.llm.exceptions import ProviderError


class OpenAICompatibleClient:
    """Small adapter around an OpenAI-compatible client."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._base_url = base_url

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
        messages: Sequence[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        cancel_event: Event | None = None,
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

        extra_body = self._extra_body_for_model(upstream_model)
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

    @staticmethod
    def _provider_model_id(model: str) -> str:
        """Resolve a canonical model id to its opaque upstream provider id."""

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
        if self._api_key is not None:
            parameters["api_key"] = self._api_key
        if self._base_url is not None:
            parameters["base_url"] = self._base_url

        try:
            return openai.OpenAI(**parameters)
        except Exception as error:  # noqa: BLE001
            self._raise_provider_error(error)

    @staticmethod
    def _raise_provider_error(error: Exception) -> None:
        message = str(error)
        lowered = message.lower()

        if "timed out" in lowered or "timeout" in lowered:
            raise ProviderError("OpenAI-compatible request timed out") from error
        if "insufficient_quota" in lowered or "current quota" in lowered:
            raise ProviderError("OpenAI-compatible quota is exhausted") from error
        if "authentication" in lowered or "api key" in lowered or "401" in lowered:
            raise ProviderError("OpenAI-compatible authentication failed") from error
        if "rate limit" in lowered or "429" in lowered:
            raise ProviderError("OpenAI-compatible rate limit exceeded") from error

        raise ProviderError(f"OpenAI-compatible request failed: {message}") from error
