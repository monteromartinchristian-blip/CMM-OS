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
    DomainRollbackFailed,
    DomainSerializationError,
    DomainSourceUntrusted,
    DomainUnloadFailed,
    DomainUnloadRollbackFailed,
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

__all__ = [
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
    "DomainValidationResult",
    "FileSystemDomainDiscovery",
    "InMemoryDomainRegistryStore",
    "JsonDomainManifestReader",
    "ParsedDomainPack",
]
