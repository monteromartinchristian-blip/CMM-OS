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


# ── Phase 8.4 errors ─────────────────────────────────────────────────────


class InvalidKnowledgeItemError(CognitiveError, ValueError):
    """Raised when a KnowledgeItem contract is incomplete or inconsistent."""


class InvalidEvidenceError(CognitiveError, ValueError):
    """Raised when an Evidence contract is invalid."""


class InvalidTemporalValidityError(CognitiveError, ValueError):
    """Raised when a TemporalScope is temporally inconsistent."""


class InvalidKnowledgeRelationError(CognitiveError, ValueError):
    """Raised when a KnowledgeRelation contract is invalid."""


class InvalidContradictionError(CognitiveError, ValueError):
    """Raised when a Contradiction contract is invalid."""


class InvalidKnowledgeBundleError(CognitiveError, ValueError):
    """Raised when a KnowledgeBundle contract is invalid."""


# Alias kept for backward compatibility with WIP commit 32cea48
InvalidKnowledgeModelError = InvalidKnowledgeItemError


# ── Phase 8.5 errors ─────────────────────────────────────────────────────────


class KnowledgeStoreError(CognitiveError):
    """Base error for Knowledge Store operations."""


class KnowledgeStoreNotFoundError(KnowledgeStoreError, LookupError):
    """Raised when a requested entity is not found in the knowledge store."""


class KnowledgeStoreConflictError(KnowledgeStoreError, ValueError):
    """Raised when an entity conflict occurs in the knowledge store."""


class KnowledgeStoreCorruptionError(KnowledgeStoreError, ValueError):
    """Raised when corrupted data or payload is encountered in the knowledge store."""


class KnowledgeStoreSchemaError(KnowledgeStoreError, ValueError):
    """Raised when the store database schema version or structure is invalid."""


class KnowledgeStoreSerializationError(KnowledgeStoreError, ValueError):
    """Raised when serialization or deserialization fails in the store."""
