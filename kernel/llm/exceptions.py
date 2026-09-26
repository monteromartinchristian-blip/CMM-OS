"""Exceptions used by the LLM abstraction layer."""


class LLMError(Exception):
    """Base exception for LLM-related failures."""


class ProviderError(LLMError):
    """Raised when a provider cannot fulfill a request."""


class ProviderTimeoutError(ProviderError):
    """Raised when a provider did not answer within the configured budget.

    Distinct from a generic refusal so a product can tell "too slow" from
    "failed": a timeout is a budget decision, not a provider verdict.
    """


class ParserError(LLMError):
    """Raised when a model response cannot be parsed into a plan."""
