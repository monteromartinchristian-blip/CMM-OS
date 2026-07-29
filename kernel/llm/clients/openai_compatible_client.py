"""Client wrapper for OpenAI-compatible Chat Completions APIs."""

from __future__ import annotations

import importlib
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

        parameters: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            parameters["max_tokens"] = max_tokens

        try:
            response = client.chat.completions.create(**parameters)
        except Exception as error:
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
        completion_tokens = int(
            getattr(usage, "completion_tokens", 0) or 0
        )
        finish_reason = str(
            getattr(choice, "finish_reason", "stop") or "stop"
        )

        return (
            content,
            prompt_tokens,
            completion_tokens,
            finish_reason,
        )

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
        except Exception as error:
            self._raise_provider_error(error)

    @staticmethod
    def _raise_provider_error(error: Exception) -> None:
        message = str(error)
        lowered = message.lower()

        if "timed out" in lowered or "timeout" in lowered:
            raise ProviderError(
                "OpenAI-compatible request timed out"
            ) from error
        if "insufficient_quota" in lowered or "current quota" in lowered:
            raise ProviderError(
                "OpenAI-compatible quota is exhausted"
            ) from error
        if (
            "authentication" in lowered
            or "api key" in lowered
            or "401" in lowered
        ):
            raise ProviderError(
                "OpenAI-compatible authentication failed"
            ) from error
        if "rate limit" in lowered or "429" in lowered:
            raise ProviderError(
                "OpenAI-compatible rate limit exceeded"
            ) from error

        raise ProviderError(
            f"OpenAI-compatible request failed: {message}"
        ) from error
