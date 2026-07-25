# ── Phase 8.3 ─────────────────────────────────────────────────────────────────
from cmm.cognitive.adapters import (
    AdaptationContext,
    ExistingResourceAdapter,
    MappingResourceAdapter,
    PlainTextResourceAdapter,
    ResourceAdaptationResult,
    ResourceAdapter,
    ResourceInput,
)
from cmm.cognitive.consolidation import KnowledgeConsolidator
from cmm.cognitive.consolidation_contracts import (
    ConsolidationAction,
    ConsolidationCandidate,
    ConsolidationDecision,
    ConsolidationMatchKind,
    ConsolidationPlan,
    ConsolidationResult,
    knowledge_fingerprint,
    normalize_statement,
)
from cmm.cognitive.contracts import (
    CognitiveActor,
    CognitiveFinding,
    CognitiveResult,
    Confidence,
)
from cmm.cognitive.contradiction_detection import KnowledgeContradictionDetector
from cmm.cognitive.contradiction_detection_contracts import (
    ContradictionDetection,
    ContradictionDetectionResult,
    ContradictionKind,
    ContradictionSignal,
)
from cmm.cognitive.contradiction_resolution import (
    ContradictionResolutionEngine,
    KnowledgeContradictionResolver,
    generate_resolution_proposal_id,
)
from cmm.cognitive.enums import (
    AdaptationStatus,
    CandidateKind,
    CognitiveActorKind,
    CognitiveSeverity,
    CognitiveStatus,
    ContradictionSeverity,
    ContradictionStatus,
    EvidenceKind,
    EvidencePolarityKind,
    ExtractionStatus,
    KnowledgeKind,
    KnowledgeRelationKind,
    KnowledgeStatus,
    ResourceIntegrityStatus,
    ResourceKind,
    ResourcePermissionOperation,
    ResourceSourceKind,
    SensitivityLevel,
    TemporalScopeKind,
    TemporalValidityStatus,
)
from cmm.cognitive.errors import (
    CognitiveError,
    ComponentNotCompatibleError,
    ComponentNotFoundError,
    ContradictionRegistrationError,
    DuplicateRegistryEntryError,
    InvalidAdaptationError,
    InvalidAdapterContractError,
    InvalidCognitiveContractError,
    InvalidCognitiveCycleError,
    InvalidCognitiveIdentifierError,
    InvalidConfidenceError,
    CognitiveCycleExecutionError,

    InvalidConsolidationCandidateError,
    InvalidConsolidationPlanError,
    InvalidContradictionDetectionError,
    InvalidContradictionError,
    InvalidContradictionSignalError,
    InvalidEvidenceError,
    InvalidExtractionError,
    InvalidExtractionEvidenceError,
    InvalidKnowledgeBundleError,
    InvalidKnowledgeItemError,
    InvalidKnowledgeModelError,
    InvalidKnowledgeQueryError,
    InvalidKnowledgeRelationError,
    InvalidReflectionReportError,
    InvalidResolutionExecutionError,
    InvalidResolutionMemoryEntryError,
    InvalidResolutionPolicyEvaluationError,
    InvalidResolutionProposalError,
    InvalidResourceError,
    InvalidResourceInputError,
    InvalidResourcePermissionError,
    InvalidResourceProvenanceError,
    InvalidResourceTemporalScopeError,
    InvalidTemporalValidityError,
    KnowledgeCognitiveCycleError,
    KnowledgeConsolidationApplicationError,

    KnowledgeConsolidationConflictError,
    KnowledgeConsolidationError,
    KnowledgeContradictionConflictError,
    KnowledgeContradictionDetectionError,
    KnowledgeContradictionResolutionError,
    KnowledgeReflectionError,
    KnowledgeResolutionExecutionError,
    KnowledgeResolutionMemoryError,
    KnowledgeResolutionPolicyError,
    KnowledgeRetrievalError,
    KnowledgeStoreConflictError,
    KnowledgeStoreCorruptionError,
    KnowledgeStoreError,
    KnowledgeStoreNotFoundError,
    KnowledgeStoreSchemaError,
    KnowledgeStoreSerializationError,
    ManualReviewRequiredError,
    ReflectionAnalysisConflictError,
    ResolutionConflictError,
    ResolutionExecutionConflictError,
    ResolutionExecutionRollbackError,
    ResolutionMemoryConflictError,
    ResolutionPolicyConflictError,
    UnsupportedKnowledgeQueryError,
)
from cmm.cognitive.extraction import (
    ExtractionCandidate,
    ExtractionContext,
    ExtractionEvidence,
    KnowledgeExtractionResult,
    KnowledgeExtractor,
    MappingKnowledgeExtractor,
    PlainTextKnowledgeExtractor,
)
from cmm.cognitive.identifiers import (
    CognitiveIdentifier,
    generate_cognitive_id,
)
from cmm.cognitive.knowledge import (
    Contradiction,
    Evidence,
    KnowledgeBundle,
    KnowledgeItem,
    KnowledgeRelation,
    TemporalScope,
)
from cmm.cognitive.knowledge_materializer import (
    materialise_candidate,
    materialise_evidence,
    materialise_result,
)
from cmm.cognitive.query import (
    KnowledgeOrderField,
    KnowledgeQuery,
    KnowledgeQueryResult,
    SortDirection,
)
from cmm.cognitive.reflection import (
    CognitiveReflectionEngine,
)
from cmm.cognitive.reflection_contracts import (
    CognitiveReflectionReport,
    ReflectionFinding,
    ReflectionQuery,
    generate_reflection_report_id,
)
from cmm.cognitive.registries import (
    KnowledgeExtractorRegistry,
    ResourceAdapterRegistry,
)
from cmm.cognitive.resolution_contracts import (
    ContradictionResolutionProposal,
    ContradictionResolutionResult,
    ResolutionDecision,
    ResolutionStatus,
)
from cmm.cognitive.resolution_executor import (
    ContradictionResolutionExecutor,
)
from cmm.cognitive.resolution_executor_contracts import (
    ExecutionStatus,
    ResolutionAuditRecord,
    ResolutionExecutionResult,
)
from cmm.cognitive.resolution_policy import (
    ContradictionResolutionPolicyEngine,
)
from cmm.cognitive.resolution_policy_contracts import (
    PolicyDecision,
    PolicySeverity,
    ResolutionPolicyEvaluation,
)

# ── Phase 8.13 ────────────────────────────────────────────────────────────────
from cmm.cognitive.resolution_memory import (
    InMemoryResolutionMemoryStore,
    ResolutionMemoryStore,
    memory_from_execution_result,
)
from cmm.cognitive.resolution_memory_contracts import (
    ResolutionMemoryEntry,
    ResolutionMemoryQuery,
    ResolutionMemoryResult,
    generate_resolution_memory_id,
)

# ── Phase 8.15 ────────────────────────────────────────────────────────────────
from cmm.cognitive.cognitive_cycle import CognitiveCycleEngine
from cmm.cognitive.cognitive_cycle_contracts import (
    CognitiveCycleRecord,
    CognitiveCycleStatus,
    generate_cognitive_cycle_id,
)


# ── Phase 8.2 ─────────────────────────────────────────────────────────────────
from cmm.cognitive.resources import (
    Resource,
    ResourcePermission,
    ResourceProvenance,
    ResourceTemporalScope,
    ResourceTransformation,
)
from cmm.cognitive.retrieval import KnowledgeRetriever
from cmm.cognitive.service import (
    AdaptAndExtractResult,
    ResourceExtractionService,
)
from cmm.cognitive.store import (
    KNOWLEDGE_STORE_SCHEMA_VERSION,
    InMemoryKnowledgeStore,
    KnowledgeStoreProtocol,
    LocalKnowledgeStore,
    SQLiteKnowledgeStore,
)

__all__ = [
    # 8.5 store
    "KNOWLEDGE_STORE_SCHEMA_VERSION",
    # 8.3 service
    "AdaptAndExtractResult",
    # 8.3 adapters
    "AdaptationContext",
    # 8.3 enums
    "AdaptationStatus",
    "CandidateKind",
    # 8.1 contracts
    "CognitiveActor",
    "CognitiveActorKind",
    "CognitiveError",
    "CognitiveFinding",
    "CognitiveIdentifier",
    "CognitiveResult",
    "CognitiveSeverity",
    "CognitiveStatus",
    # 8.3 errors
    "ComponentNotCompatibleError",
    "ComponentNotFoundError",
    "Confidence",
    # 8.7 consolidation
    "ConsolidationAction",
    "ConsolidationCandidate",
    "ConsolidationDecision",
    "ConsolidationMatchKind",
    "ConsolidationPlan",
    "ConsolidationResult",
    "Contradiction",
    # 8.8 contradiction detection
    "ContradictionDetection",
    "ContradictionDetectionResult",
    "ContradictionKind",
    "ContradictionRegistrationError",
    "ContradictionResolutionEngine",
    # 8.12 resolution executor
    "ContradictionResolutionExecutor",
    # 8.11 resolution policy
    "ContradictionResolutionPolicyEngine",
    # 8.9 contradiction resolution
    "ContradictionResolutionProposal",
    "ContradictionResolutionResult",
    "ContradictionSeverity",
    "ContradictionSignal",
    "ContradictionStatus",
    "DuplicateRegistryEntryError",
    "Evidence",
    "EvidenceKind",
    "EvidencePolarityKind",
    "ExecutionStatus",
    "ExistingResourceAdapter",
    # 8.3 extraction
    "ExtractionCandidate",
    "ExtractionContext",
    "ExtractionEvidence",
    "ExtractionStatus",
    "InMemoryKnowledgeStore",
    # 8.13 memory store
    "InMemoryResolutionMemoryStore",
    "InvalidAdaptationError",
    "InvalidAdapterContractError",
    "InvalidCognitiveContractError",
    "InvalidCognitiveIdentifierError",
    "InvalidConfidenceError",
    "InvalidConsolidationCandidateError",
    "InvalidConsolidationPlanError",
    # 8.8 errors
    "InvalidContradictionDetectionError",
    "InvalidContradictionError",
    "InvalidContradictionSignalError",
    "InvalidEvidenceError",
    "InvalidExtractionError",
    "InvalidExtractionEvidenceError",
    "InvalidKnowledgeBundleError",
    "InvalidKnowledgeItemError",
    "InvalidKnowledgeModelError",
    "InvalidKnowledgeQueryError",
    "InvalidKnowledgeRelationError",
    # 8.14 reflection
    "InvalidReflectionReportError",
    "InvalidResolutionExecutionError",
    "InvalidResolutionMemoryEntryError",
    "InvalidResolutionPolicyEvaluationError",
    # 8.9 errors
    "InvalidResolutionProposalError",
    "InvalidResourceError",
    "InvalidResourceInputError",
    "InvalidResourcePermissionError",
    "InvalidResourceProvenanceError",
    "InvalidResourceTemporalScopeError",
    "InvalidTemporalValidityError",
    "KnowledgeBundle",
    "KnowledgeConsolidationApplicationError",
    "KnowledgeConsolidationConflictError",
    "KnowledgeConsolidationError",
    "KnowledgeConsolidator",
    "KnowledgeContradictionConflictError",
    "KnowledgeContradictionDetectionError",
    "KnowledgeContradictionDetector",
    "KnowledgeContradictionResolutionError",
    "KnowledgeContradictionResolver",
    "KnowledgeExtractionResult",
    "KnowledgeExtractor",
    # 8.3 registries
    "KnowledgeExtractorRegistry",
    "KnowledgeItem",
    "KnowledgeKind",
    "KnowledgeOrderField",
    "KnowledgeQuery",
    "KnowledgeQueryResult",
    "KnowledgeReflectionError",
    "KnowledgeRelation",
    "KnowledgeRelationKind",
    "KnowledgeResolutionExecutionError",
    "KnowledgeResolutionMemoryError",
    "KnowledgeResolutionPolicyError",
    "KnowledgeRetrievalError",
    "KnowledgeRetriever",
    "KnowledgeStatus",
    "KnowledgeStoreConflictError",
    "KnowledgeStoreCorruptionError",
    "KnowledgeStoreError",
    "KnowledgeStoreNotFoundError",
    "KnowledgeStoreProtocol",
    "KnowledgeStoreSchemaError",
    "KnowledgeStoreSerializationError",
    "LocalKnowledgeStore",
    "ManualReviewRequiredError",
    "MappingKnowledgeExtractor",
    "MappingResourceAdapter",
    "PlainTextKnowledgeExtractor",
    "PlainTextResourceAdapter",
    "PolicyDecision",
    "PolicySeverity",
    "ReflectionAnalysisConflictError",
    "ReflectionFinding",
    "ReflectionQuery",
    "CognitiveReflectionEngine",
    "CognitiveReflectionReport",
    "ResolutionAuditRecord",
    # 8.9 enums
    "ResolutionConflictError",
    "ResolutionDecision",
    "ResolutionExecutionConflictError",
    "ResolutionExecutionResult",
    "ResolutionExecutionRollbackError",
    # 8.13 memory
    "ResolutionMemoryConflictError",
    "ResolutionMemoryEntry",
    "ResolutionMemoryQuery",
    "ResolutionMemoryResult",
    "ResolutionMemoryStore",
    "ResolutionPolicyConflictError",
    "ResolutionPolicyEvaluation",
    "ResolutionStatus",
    # 8.2 resources
    "Resource",
    "ResourceAdaptationResult",
    "ResourceAdapter",
    "ResourceAdapterRegistry",
    "ResourceExtractionService",
    "ResourceInput",
    "ResourceIntegrityStatus",
    "ResourceKind",
    "ResourcePermission",
    "ResourcePermissionOperation",
    "ResourceProvenance",
    "ResourceSourceKind",
    "ResourceTemporalScope",
    "ResourceTransformation",
    "SQLiteKnowledgeStore",
    "SensitivityLevel",
    "SortDirection",
    "TemporalScope",
    "TemporalScopeKind",
    "TemporalValidityStatus",
    "UnsupportedKnowledgeQueryError",
    # 8.15 cycle
    "CognitiveCycleEngine",
    "CognitiveCycleRecord",
    "CognitiveCycleStatus",
    "CognitiveCycleExecutionError",
    "InvalidCognitiveCycleError",
    "KnowledgeCognitiveCycleError",
    "generate_cognitive_cycle_id",
    "generate_cognitive_id",
    "generate_reflection_report_id",

    "generate_resolution_memory_id",
    "generate_resolution_proposal_id",
    "knowledge_fingerprint",
    # 8.4 materializer
    "materialise_candidate",
    "materialise_evidence",
    "materialise_result",
    "memory_from_execution_result",
    "normalize_statement",
]
