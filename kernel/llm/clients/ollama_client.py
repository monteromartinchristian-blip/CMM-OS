"""HTTP client for the Ollama API."""

from __future__ import annotations

from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json

from kernel.llm.exceptions import ProviderError


class OllamaClient:
    """Small HTTP client for calling the Ollama generation API."""

    def __init__(self, host: str = "http://localhost:11434", timeout: float = 120) -> None:
        self.host = host.rstrip("/")
        self.timeout = timeout

    def generate(
        self,
        *,
        model: str,
        system: str | None = None,
        prompt: str = "",
        temperature: float = 0.0,
        num_predict: int | None = None,
    ) -> str:
        """Generate text through the Ollama HTTP API."""

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if system is not None:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        if num_predict is not None:
            payload["num_predict"] = num_predict

        request = Request(
            f"{self.host}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except TimeoutError as exc:
            raise ProviderError("Ollama request timed out") from exc
        except HTTPError as exc:
            status_code = exc.code
            if status_code == 404:
                raise ProviderError("Ollama model not found") from exc
            if status_code == 500:
                raise ProviderError("Ollama host is unreachable") from exc
            raise ProviderError(f"Ollama request failed with status {status_code}") from exc
        except URLError as exc:
            raise ProviderError("Ollama host is unreachable") from exc
        except OSError as exc:
            raise ProviderError("Ollama host is unreachable") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ProviderError("Invalid Ollama response") from exc

        if not isinstance(parsed, dict):
            raise ProviderError("Invalid Ollama response")

        response_text = parsed.get("response")
        if not isinstance(response_text, str) or not response_text.strip():
            raise ProviderError("Ollama response was empty")

        return response_text
