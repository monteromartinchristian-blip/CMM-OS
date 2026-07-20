"""Exceptions used by the LLM abstraction layer."""


class LLMError(Exception):
    """Base exception for LLM-related failures."""


class ProviderError(LLMError):
    """Raised when a provider cannot fulfill a request."""


class ParserError(LLMError):
    """Raised when a model response cannot be parsed into a plan."""
