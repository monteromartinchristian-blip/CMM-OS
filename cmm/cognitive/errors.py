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


class InvalidKnowledgePackageError(CognitiveError, ValueError):
    """Raised when a portable KnowledgePackage contract is invalid."""


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


# ── Phase 8.6 errors ─────────────────────────────────────────────────────────


class KnowledgeRetrievalError(CognitiveError):
    """Base error for knowledge retrieval operations."""


class InvalidKnowledgeQueryError(KnowledgeRetrievalError, ValueError):
    """Raised when a KnowledgeQuery contract or parameter is invalid."""


class UnsupportedKnowledgeQueryError(KnowledgeRetrievalError, ValueError):
    """Raised when a query operation or capability is not supported."""


# ── Phase 8.7 errors ─────────────────────────────────────────────────────────


class KnowledgeConsolidationError(CognitiveError):
    """Base error for knowledge consolidation operations."""


class InvalidConsolidationCandidateError(KnowledgeConsolidationError, ValueError):
    """Raised when a ConsolidationCandidate contract or comparison input is invalid."""


class InvalidConsolidationPlanError(KnowledgeConsolidationError, ValueError):
    """Raised when a ConsolidationPlan contract or action sequence is invalid."""


class KnowledgeConsolidationConflictError(KnowledgeConsolidationError, ValueError):
    """Raised when a consolidation plan encounters stale or conflicting store state."""


class KnowledgeConsolidationApplicationError(KnowledgeConsolidationError, RuntimeError):
    """Raised when applying a consolidation plan fails."""


class ManualReviewRequiredError(KnowledgeConsolidationError, ValueError):
    """Raised when trying to automatically apply a plan containing manual review actions."""


# ── Phase 8.8 errors ─────────────────────────────────────────────────────────


class KnowledgeContradictionDetectionError(CognitiveError):
    """Base error for knowledge contradiction detection operations."""


class InvalidContradictionSignalError(KnowledgeContradictionDetectionError, ValueError):
    """Raised when a ContradictionSignal contract is invalid."""


class InvalidContradictionDetectionError(
    KnowledgeContradictionDetectionError, ValueError
):
    """Raised when a ContradictionDetection contract is invalid."""


class KnowledgeContradictionConflictError(
    KnowledgeContradictionDetectionError, ValueError
):
    """Raised when registering a contradiction with conflicting payload."""


class ContradictionRegistrationError(KnowledgeContradictionDetectionError):
    """Raised when registering a contradiction fails."""


# ── Phase 8.9 errors ─────────────────────────────────────────────────────────


class KnowledgeContradictionResolutionError(CognitiveError):
    """Base error for knowledge contradiction resolution operations."""


class InvalidResolutionProposalError(KnowledgeContradictionResolutionError, ValueError):
    """Raised when a ContradictionResolutionProposal contract is invalid."""


class ResolutionConflictError(KnowledgeContradictionResolutionError, ValueError):
    """Raised when conflicts occur during contradiction resolution application."""


# ── Phase 8.11 errors ─────────────────────────────────────────────────────────


class KnowledgeResolutionPolicyError(CognitiveError):
    """Base error for knowledge resolution policy operations."""


class InvalidResolutionPolicyEvaluationError(
    KnowledgeResolutionPolicyError, ValueError
):
    """Raised when a ResolutionPolicyEvaluation contract is invalid."""


class ResolutionPolicyConflictError(KnowledgeResolutionPolicyError, ValueError):
    """Raised when a resolution policy evaluation fails or encounters conflicting configuration."""


# ── Phase 8.12 errors ─────────────────────────────────────────────────────────


class KnowledgeResolutionExecutionError(CognitiveError):
    """Base error for knowledge resolution execution operations."""


class InvalidResolutionExecutionError(KnowledgeResolutionExecutionError, ValueError):
    """Raised when a resolution execution contract, proposal, or evaluation is invalid."""


class ResolutionExecutionConflictError(KnowledgeResolutionExecutionError, ValueError):
    """Raised when execution encounters conflicting knowledge or state in the store."""


class ResolutionExecutionRollbackError(KnowledgeResolutionExecutionError, RuntimeError):
    """Raised when an execution fails and forces a transaction rollback."""


# ── Phase 8.13 errors ─────────────────────────────────────────────────────────


class KnowledgeResolutionMemoryError(CognitiveError):
    """Base error for knowledge resolution memory operations."""


class InvalidResolutionMemoryEntryError(KnowledgeResolutionMemoryError, ValueError):
    """Raised when a ResolutionMemoryEntry or Query contract is invalid."""


class ResolutionMemoryConflictError(
    KnowledgeResolutionMemoryError, LookupError, ValueError
):
    """Raised when a resolution memory entry conflict occurs."""


# ── Phase 8.14 errors ─────────────────────────────────────────────────────────


class KnowledgeReflectionError(CognitiveError):
    """Base error for cognitive reflection operations."""


class InvalidReflectionReportError(KnowledgeReflectionError, ValueError):
    """Raised when a CognitiveReflectionReport or related contract is invalid."""


class ReflectionAnalysisConflictError(KnowledgeReflectionError, ValueError):
    """Raised when reflection analysis encounters a conflict or error."""


# ── Phase 8.15 errors ─────────────────────────────────────────────────────────


class KnowledgeCognitiveCycleError(CognitiveError):
    """Base error for cognitive integration cycle operations."""


class InvalidCognitiveCycleError(KnowledgeCognitiveCycleError, ValueError):
    """Raised when a CognitiveCycleRecord or cycle parameters are invalid."""


class CognitiveCycleExecutionError(KnowledgeCognitiveCycleError, RuntimeError):
    """Raised when execution of a cognitive cycle fails."""


# ── Phase 8.24 errors ─────────────────────────────────────────────────────────


class CognitiveCacheError(CognitiveError):
    """Base error for Cognitive Cache operations."""


class InvalidCognitiveCacheEntryError(CognitiveCacheError, ValueError):
    """Raised when a CognitiveCacheEntry or related contract is invalid."""


class CognitiveCacheConflictError(CognitiveCacheError, ValueError):
    """Raised when a cache entry conflicts with existing incompatible data."""


class CognitiveCacheNotFoundError(CognitiveCacheError, LookupError):
    """Raised when a requested cache entry cannot be found."""


# ── Phase 8.25 errors ─────────────────────────────────────────────────────────


class PrivacyMetadataError(CognitiveError):
    """Base error for privacy and processing-policy metadata operations."""


class InvalidPrivacyMetadataError(PrivacyMetadataError, ValueError):
    """Raised when a PrivacyMetadata, PrivacyOperationContext, or PrivacyDecision
    contract is invalid."""


class PrivacyResolutionError(PrivacyMetadataError, ValueError):
    """Raised when resolving the effective privacy metadata across multiple
    sources fails or receives invalid input."""


# ── Phase 8.26 errors ─────────────────────────────────────────────────────────


class CognitiveValidationError(CognitiveError):
    """Base error for structural cognitive validation operations."""


class InvalidCognitiveValidationContextError(CognitiveValidationError, ValueError):
    """Raised when a CognitiveValidationContext contract is invalid."""


class CognitiveValidationExecutionError(CognitiveValidationError, RuntimeError):
    """Raised when a cognitive validation rule encounters an execution error."""


# ── Phase 10.12 – Common Reasoning Rule errors ───────────────────────────────


class ReasoningRuleError(CognitiveError):
    """Base error for common reasoning-rule infrastructure."""

    code = "REASONING_RULE_ERROR"

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.field = field
        self.details = _freeze_reasoning_details(details or {})


def _freeze_reasoning_details(value: object) -> object:
    """Deeply freeze diagnostic details without retaining caller aliases."""
    from collections.abc import Mapping
    from types import MappingProxyType

    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_reasoning_details(nested) for key, nested in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_reasoning_details(nested) for nested in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_reasoning_details(nested) for nested in value)
    return value


class ReasoningRuleContractError(ReasoningRuleError, ValueError):
    """Raised when a common reasoning-rule contract is invalid."""

    code = "REASONING_RULE_CONTRACT_ERROR"


class ReasoningRuleSerializationError(ReasoningRuleError, ValueError):
    """Raised when strict reasoning-rule serialization fails."""

    code = "REASONING_RULE_SERIALIZATION_ERROR"


class ReasoningRuleRegistryError(ReasoningRuleError):
    """Raised when reasoning-rule registration or lookup fails."""

    code = "REASONING_RULE_REGISTRY_ERROR"


class ReasoningRuleExecutionError(ReasoningRuleError, RuntimeError):
    """Controlled failure reported by reasoning-rule execution."""

    code = "REASONING_RULE_EXECUTION_ERROR"
