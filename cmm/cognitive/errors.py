from __future__ import annotations


class CognitiveError(Exception):
    """Base error for the Cognitive Layer."""


class InvalidConfidenceError(CognitiveError, ValueError):
    """Raised when a confidence value is outside the accepted range."""


class InvalidCognitiveIdentifierError(CognitiveError, ValueError):
    """Raised when a cognitive identifier is malformed."""


class InvalidCognitiveContractError(CognitiveError, ValueError):
    """Raised when a cognitive contract is incomplete or invalid."""
