"""Client for OpenAI-compatible Chat Completions APIs."""

from __future__ import annotations

import importlib
import os
from typing import Any

from kernel.llm.exceptions import ProviderError


class OpenAICompatibleClient:
    """Adapter around OpenAI-compatible Chat Completions endpoints."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        client: Any | None = None,
    ) -> None:
        self._client = client
        self.api_key = api_key
        self.base_url = base_url

    def generate(
        self,
        *,
        model: str,
        system: str | None,
        prompt: str,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
    ) -> tuple[str, int, int, str]:
        """Generate text and return content, usage, and finish reason."""

        client = self._client or self._build_client()

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        parameters: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_output_tokens is not None:
            parameters["max_tokens"] = max_output_tokens

        try:
            response = client.chat.completions.create(**parameters)
        except Exception as error:  # noqa: BLE001
            self._raise_provider_error(error)

        try:
            choice = response.choices[0]
            content = choice.message.content
        except (AttributeError, IndexError, TypeError) as error:
            raise ProviderError(
                "OpenAI-compatible response had an invalid shape"
            ) from error

        if not isinstance(content, str) or not content.strip():
            raise ProviderError("OpenAI-compatible response was empty")

        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        finish_reason = str(getattr(choice, "finish_reason", "stop") or "stop")

        return content, prompt_tokens, completion_tokens, finish_reason

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

        parameters: dict[str, str] = {}

        api_key = self.api_key or os.getenv("OPENAI_API_KEY")
        if api_key:
            parameters["api_key"] = api_key

        if self.base_url:
            parameters["base_url"] = self.base_url

        try:
            return openai.OpenAI(**parameters)
        except Exception as error:  # noqa: BLE001
            self._raise_provider_error(error)

    def _raise_provider_error(self, error: Exception) -> None:
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
