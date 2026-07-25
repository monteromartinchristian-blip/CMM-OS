from __future__ import annotations


class CognitiveError(Exception):
    """Base error for the Cognitive Layer."""


class InvalidConfidenceError(CognitiveError, ValueError):
    """Raised when a confidence value is outside the accepted range."""


class InvalidCognitiveIdentifierError(CognitiveError, ValueError):
    """Raised when a cognitive identifier is malformed."""


class InvalidCognitiveContractError(CognitiveError, ValueError):
    """Raised when a cognitive contract is incomplete or invalid."""


class InvalidResourceError(CognitiveError, ValueError):
    """Raised when a resource contract is invalid."""


class InvalidResourcePermissionError(CognitiveError, ValueError):
    """Raised when a resource permission contract is invalid."""


class InvalidResourceTemporalScopeError(CognitiveError, ValueError):
    """Raised when a resource temporal scope is invalid."""


class InvalidResourceProvenanceError(CognitiveError, ValueError):
    """Raised when resource provenance is invalid."""
