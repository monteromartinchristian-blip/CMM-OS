"""Client wrapper for the OpenAI Responses API."""

from __future__ import annotations

import importlib
from typing import Any

from kernel.llm.exceptions import ProviderError


class OpenAIClient:
    """Small adapter around the optional OpenAI Python SDK."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def generate(
        self,
        *,
        model: str,
        system: str | None,
        prompt: str,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
    ) -> tuple[str, int, int, str]:
        """Generate text and return content, usage and finish status."""

        client = self._client or self._build_client()

        parameters: dict[str, Any] = {
            "model": model,
            "input": prompt,
        }
        if system is not None:
            parameters["instructions"] = system
        if temperature is not None:
            parameters["temperature"] = temperature
        if max_output_tokens is not None:
            parameters["max_output_tokens"] = max_output_tokens

        try:
            response = client.responses.create(**parameters)
        except Exception as error:
            self._raise_provider_error(error)

        content = getattr(response, "output_text", None)
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("OpenAI response was empty")

        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        status = str(getattr(response, "status", "completed") or "completed")

        return content, prompt_tokens, completion_tokens, status

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
                "OpenAI support is not installed. "
                "Install CMM OS with the 'openai' extra."
            ) from error

        try:
            return openai.OpenAI()
        except Exception as error:
            self._raise_provider_error(error)

    def _raise_provider_error(self, error: Exception) -> None:
        message = str(error)
        lowered = message.lower()

        if "timed out" in lowered or "timeout" in lowered:
            raise ProviderError("OpenAI request timed out") from error
        if "insufficient_quota" in lowered or "current quota" in lowered:
            raise ProviderError("OpenAI quota is exhausted") from error
        if "authentication" in lowered or "api key" in lowered or "401" in lowered:
            raise ProviderError("OpenAI authentication failed") from error
        if "rate limit" in lowered or "429" in lowered:
            raise ProviderError("OpenAI rate limit exceeded") from error

        raise ProviderError(f"OpenAI request failed: {message}") from error
