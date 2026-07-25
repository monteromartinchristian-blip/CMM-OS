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


# ── Phase 8.3 errors ─────────────────────────────────────────────────────────


class InvalidResourceInputError(CognitiveError, ValueError):
    """Raised when a ResourceInput contract is invalid."""


class InvalidAdaptationError(CognitiveError, ValueError):
    """Raised when an adaptation contract or result is invalid."""


class InvalidExtractionError(CognitiveError, ValueError):
    """Raised when an extraction contract or result is invalid."""


class InvalidExtractionEvidenceError(CognitiveError, ValueError):
    """Raised when extraction evidence fields are invalid."""


class DuplicateRegistryEntryError(CognitiveError, ValueError):
    """Raised when a component is registered under an already-used name."""


class ComponentNotFoundError(CognitiveError, LookupError):
    """Raised when a named component cannot be found in a registry."""


class ComponentNotCompatibleError(CognitiveError, LookupError):
    """Raised when no registered component supports the given input."""


class InvalidAdapterContractError(CognitiveError, ValueError):
    """Raised when an adapter object does not fulfil the required contract."""
