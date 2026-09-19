"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from threading import Event

from kernel.llm.exceptions import ProviderError
from kernel.llm.models import LLMRequest, LLMResponse


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response for the given request."""

        raise NotImplementedError

    def stream(
        self, request: LLMRequest, *, cancel_event: Event | None = None
    ) -> Iterator[str]:
        """Yield provider-independent content deltas for one request.

        Streaming is an optional capability of the canonical provider
        abstraction: a provider without a token transport fails closed with a
        normalized :class:`~kernel.llm.exceptions.ProviderError` instead of
        pretending to stream.
        """

        raise ProviderError(f"{type(self).__name__} does not support token streaming")
