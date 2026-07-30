"""Phase 10.1 – Domain Intelligence Package.

Exports foundational contracts, enums, identifiers, and errors for the
Domain Intelligence subsystem.
"""

from __future__ import annotations

from cmm.domains.contracts import (
    DomainCapability,
    DomainConflict,
    DomainDefinition,
    DomainDependency,
    DomainMetadata,
    DomainResult,
)
from cmm.domains.discovery import (
    DomainDiscovery,
    FileSystemDomainDiscovery,
)
from cmm.domains.discovery_contracts import (
    DomainCandidate,
    DomainDiscoveryIssue,
    DomainDiscoveryResult,
    DomainSource,
)
from cmm.domains.enums import (
    DomainKind,
    DomainLoadStatus,
    DomainPackKind,
    DomainPackStatus,
    DomainSourceKind,
    DomainStatus,
    DomainValidationStatus,
)
from cmm.domains.errors import (
    DomainCandidateInvalid,
    DomainCapabilityConflict,
    DomainChecksumMismatch,
    DomainContractError,
    DomainContractValidationError,
    DomainDependencyMissing,
    DomainDiscoveryError,
    DomainDiscoverySourceError,
    DomainError,
    DomainLoaderError,
    DomainLoadFailed,
    DomainLoadRejected,
    DomainLoadRollbackFailed,
    DomainPathEscape,
    DomainRegistryConflict,
    DomainRegistryError,
    DomainRegistryNotFound,
    DomainRegistryStateError,
    DomainRegistryValidationError,
    DomainRegistryVersionError,
    DomainReloadFailed,
    DomainReloadRollbackFailed,
    DomainResolutionContextInvalid,
    DomainResolutionContractError,
    DomainResolutionError,
    DomainResolutionLimitExceeded,
    DomainResolutionPolicyError,
    DomainResolutionSerializationError,
    DomainResolutionSnapshotError,
    DomainRollbackFailed,
    DomainSerializationError,
    DomainSourceUntrusted,
    DomainUnloadFailed,
    DomainUnloadRollbackFailed,
    DomainValidationBlocked,
    DomainValidationContextInvalid,
    DomainValidationError,
    DomainValidationExecutionError,
    DomainValidationRequestInvalid,
    DomainValidationStepMissing,
)
from cmm.domains.identifiers import (
    DomainId,
    DomainManifestId,
    DomainResultId,
)
from cmm.domains.loader import (
    DeclarativeDomainLoader,
    DomainLoader,
)
from cmm.domains.loader_contracts import (
    DomainLoaderSnapshot,
    DomainLoadResult,
)
from cmm.domains.manifest import (
    DomainCompatibility,
    DomainComponentReference,
    DomainManifest,
    DomainPermissionReference,
)
from cmm.domains.manifest_reader import (
    DomainManifestDocument,
    DomainManifestReader,
    JsonDomainManifestReader,
)
from cmm.domains.pack import (
    DomainPack,
    ParsedDomainPack,
)
from cmm.domains.registry import (
    DomainRegistry,
)
from cmm.domains.registry_contracts import (
    DomainQuery,
    DomainRegistryRecord,
    DomainRegistrySnapshot,
    DomainRegistryStoreSnapshot,
    DomainValidationResult,
)
from cmm.domains.registry_store import (
    DomainRegistryStore,
    InMemoryDomainRegistryStore,
)
from cmm.domains.registry_validation import (
    DomainDefinitionRegistryValidator,
)

# Phase 10.6 – Domain Resolution Context
from cmm.domains.resolution_builder import (
    DomainResolutionContextBuilder,
)
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionEntity,
    DomainResolutionEvent,
    DomainResolutionHistoryItem,
    DomainResolutionKnowledgeItem,
    DomainResolutionPolicy,
    DomainResolutionResource,
    DomainResolutionSignal,
)

# Phase 10.5 – Domain Validation
from cmm.domains.validation import (
    PipelineDomainValidator,
    build_domain_validation_result,
    ensure_domain_validation_allows_install,
)
from cmm.domains.validation_context import (
    build_domain_validation_context,
)
from cmm.domains.validation_contracts import (
    DomainValidationExecutionContext,
    DomainValidationRequest,
)
from cmm.domains.validation_contracts import (
    DomainValidationResult as DomainValidationResult10,
)
from cmm.domains.validation_steps import (
    ALL_DOMAIN_STEPS,
    build_domain_validation_steps,
)

__all__ = [
    "ALL_DOMAIN_STEPS",
    "DeclarativeDomainLoader",
    "DomainCandidate",
    "DomainCandidateInvalid",
    "DomainCapability",
    "DomainCapabilityConflict",
    "DomainChecksumMismatch",
    "DomainCompatibility",
    "DomainComponentReference",
    "DomainConflict",
    "DomainContractError",
    "DomainContractValidationError",
    "DomainDefinition",
    "DomainDefinitionRegistryValidator",
    "DomainDependency",
    "DomainDependencyMissing",
    "DomainDiscovery",
    "DomainDiscoveryError",
    "DomainDiscoveryIssue",
    "DomainDiscoveryResult",
    "DomainDiscoverySourceError",
    "DomainError",
    "DomainId",
    "DomainKind",
    "DomainLoadFailed",
    "DomainLoadRejected",
    "DomainLoadResult",
    "DomainLoadRollbackFailed",
    "DomainLoadStatus",
    "DomainLoader",
    "DomainLoaderError",
    "DomainLoaderSnapshot",
    "DomainManifest",
    "DomainManifestDocument",
    "DomainManifestId",
    "DomainManifestReader",
    "DomainMetadata",
    "DomainPack",
    "DomainPackKind",
    "DomainPackStatus",
    "DomainPathEscape",
    "DomainPermissionReference",
    "DomainQuery",
    "DomainRegistry",
    "DomainRegistryConflict",
    "DomainRegistryError",
    "DomainRegistryNotFound",
    "DomainRegistryRecord",
    "DomainRegistrySnapshot",
    "DomainRegistryStateError",
    "DomainRegistryStore",
    "DomainRegistryStoreSnapshot",
    "DomainRegistryValidationError",
    "DomainRegistryVersionError",
    "DomainReloadFailed",
    "DomainReloadRollbackFailed",
    "DomainResolutionContext",
    "DomainResolutionContextBuilder",
    "DomainResolutionContextInvalid",
    "DomainResolutionContractError",
    "DomainResolutionEntity",
    "DomainResolutionError",
    "DomainResolutionEvent",
    "DomainResolutionHistoryItem",
    "DomainResolutionKnowledgeItem",
    "DomainResolutionLimitExceeded",
    "DomainResolutionPolicy",
    "DomainResolutionPolicyError",
    "DomainResolutionResource",
    "DomainResolutionSerializationError",
    "DomainResolutionSignal",
    "DomainResolutionSnapshotError",
    "DomainResult",
    "DomainResultId",
    "DomainRollbackFailed",
    "DomainSerializationError",
    "DomainSource",
    "DomainSourceKind",
    "DomainSourceUntrusted",
    "DomainStatus",
    "DomainUnloadFailed",
    "DomainUnloadRollbackFailed",
    "DomainValidationBlocked",
    "DomainValidationContextInvalid",
    "DomainValidationError",
    "DomainValidationExecutionContext",
    "DomainValidationExecutionError",
    "DomainValidationRequest",
    "DomainValidationRequestInvalid",
    "DomainValidationResult",
    "DomainValidationResult10",
    "DomainValidationStatus",
    "DomainValidationStepMissing",
    "FileSystemDomainDiscovery",
    "InMemoryDomainRegistryStore",
    "JsonDomainManifestReader",
    "ParsedDomainPack",
    "PipelineDomainValidator",
    "build_domain_validation_context",
    "build_domain_validation_result",
    "build_domain_validation_steps",
    "ensure_domain_validation_allows_install",
]
