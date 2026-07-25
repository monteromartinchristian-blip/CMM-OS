from cmm.cognitive.contracts import (
    CognitiveActor,
    CognitiveFinding,
    CognitiveResult,
    Confidence,
)
from cmm.cognitive.enums import (
    AdaptationStatus,
    CandidateKind,
    CognitiveActorKind,
    CognitiveSeverity,
    CognitiveStatus,
    ExtractionStatus,
    ResourceIntegrityStatus,
    ResourceKind,
    ResourcePermissionOperation,
    ResourceSourceKind,
    SensitivityLevel,
)
from cmm.cognitive.errors import (
    CognitiveError,
    ComponentNotCompatibleError,
    ComponentNotFoundError,
    DuplicateRegistryEntryError,
    InvalidAdaptationError,
    InvalidAdapterContractError,
    InvalidCognitiveContractError,
    InvalidCognitiveIdentifierError,
    InvalidConfidenceError,
    InvalidExtractionError,
    InvalidExtractionEvidenceError,
    InvalidResourceError,
    InvalidResourceInputError,
    InvalidResourcePermissionError,
    InvalidResourceProvenanceError,
    InvalidResourceTemporalScopeError,
)
from cmm.cognitive.identifiers import (
    CognitiveIdentifier,
    generate_cognitive_id,
)

# ── Phase 8.2 ─────────────────────────────────────────────────────────────────
from cmm.cognitive.resources import (
    Resource,
    ResourcePermission,
    ResourceProvenance,
    ResourceTemporalScope,
    ResourceTransformation,
)

# ── Phase 8.3 ─────────────────────────────────────────────────────────────────
from cmm.cognitive.adapters import (
    AdaptationContext,
    ExistingResourceAdapter,
    MappingResourceAdapter,
    PlainTextResourceAdapter,
    ResourceAdapter,
    ResourceAdaptationResult,
    ResourceInput,
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
from cmm.cognitive.registries import (
    KnowledgeExtractorRegistry,
    ResourceAdapterRegistry,
)
from cmm.cognitive.service import (
    AdaptAndExtractResult,
    ResourceExtractionService,
)

# ── Phase 8.4 – Knowledge Model ───────────────────────────────────────────────
from cmm.cognitive.enums import (
    ContradictionSeverity,
    ContradictionStatus,
    EvidenceKind,
    EvidencePolarityKind,
    KnowledgeKind,
    KnowledgeRelationKind,
    KnowledgeStatus,
    TemporalScopeKind,
)
from cmm.cognitive.errors import (
    InvalidContradictionError,
    InvalidEvidenceError,
    InvalidKnowledgeBundleError,
    InvalidKnowledgeItemError,
    InvalidKnowledgeModelError,
    InvalidKnowledgeRelationError,
    InvalidTemporalValidityError,
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

__all__ = [
    # 8.1 contracts
    "CognitiveActor",
    "CognitiveActorKind",
    "CognitiveError",
    "CognitiveFinding",
    "CognitiveIdentifier",
    "CognitiveResult",
    "CognitiveSeverity",
    "CognitiveStatus",
    "Confidence",
    "InvalidCognitiveContractError",
    "InvalidCognitiveIdentifierError",
    "InvalidConfidenceError",
    "generate_cognitive_id",
    # 8.2 resources
    "Resource",
    "ResourceIntegrityStatus",
    "ResourceKind",
    "ResourcePermission",
    "ResourcePermissionOperation",
    "ResourceProvenance",
    "ResourceSourceKind",
    "ResourceTemporalScope",
    "ResourceTransformation",
    "SensitivityLevel",
    "InvalidResourceError",
    "InvalidResourcePermissionError",
    "InvalidResourceProvenanceError",
    "InvalidResourceTemporalScopeError",
    # 8.3 enums
    "AdaptationStatus",
    "CandidateKind",
    "ExtractionStatus",
    # 8.3 errors
    "ComponentNotCompatibleError",
    "ComponentNotFoundError",
    "DuplicateRegistryEntryError",
    "InvalidAdaptationError",
    "InvalidAdapterContractError",
    "InvalidExtractionError",
    "InvalidExtractionEvidenceError",
    "InvalidResourceInputError",
    # 8.3 adapters
    "AdaptationContext",
    "ExistingResourceAdapter",
    "MappingResourceAdapter",
    "PlainTextResourceAdapter",
    "ResourceAdapter",
    "ResourceAdaptationResult",
    "ResourceInput",
    # 8.3 extraction
    "ExtractionCandidate",
    "ExtractionContext",
    "ExtractionEvidence",
    "KnowledgeExtractionResult",
    "KnowledgeExtractor",
    "MappingKnowledgeExtractor",
    "PlainTextKnowledgeExtractor",
    # 8.3 registries
    "KnowledgeExtractorRegistry",
    "ResourceAdapterRegistry",
    # 8.3 service
    "AdaptAndExtractResult",
    "ResourceExtractionService",
    # 8.4 enums
    "ContradictionSeverity",
    "ContradictionStatus",
    "EvidenceKind",
    "EvidencePolarityKind",
    "KnowledgeKind",
    "KnowledgeRelationKind",
    "KnowledgeStatus",
    "TemporalScopeKind",
    # 8.4 errors
    "InvalidContradictionError",
    "InvalidEvidenceError",
    "InvalidKnowledgeBundleError",
    "InvalidKnowledgeItemError",
    "InvalidKnowledgeModelError",
    "InvalidKnowledgeRelationError",
    "InvalidTemporalValidityError",
    # 8.4 knowledge model
    "Contradiction",
    "Evidence",
    "KnowledgeBundle",
    "KnowledgeItem",
    "KnowledgeRelation",
    "TemporalScope",
    # 8.4 materializer
    "materialise_candidate",
    "materialise_evidence",
    "materialise_result",
]
