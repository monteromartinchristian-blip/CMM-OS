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
from cmm.domains.enums import (
    DomainKind,
    DomainPackKind,
    DomainPackStatus,
    DomainStatus,
)
from cmm.domains.errors import (
    DomainCapabilityConflict,
    DomainContractError,
    DomainContractValidationError,
    DomainDependencyMissing,
    DomainError,
    DomainRegistryConflict,
    DomainRegistryError,
    DomainRegistryNotFound,
    DomainRegistryStateError,
    DomainRegistryValidationError,
    DomainRegistryVersionError,
    DomainSerializationError,
)
from cmm.domains.identifiers import (
    DomainId,
    DomainManifestId,
    DomainResultId,
)
from cmm.domains.manifest import (
    DomainCompatibility,
    DomainComponentReference,
    DomainManifest,
    DomainPermissionReference,
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
    "DomainCapability",
    "DomainCapabilityConflict",
    "DomainCompatibility",
    "DomainComponentReference",
    "DomainConflict",
    "DomainContractError",
    "DomainContractValidationError",
    "DomainDefinition",
    "DomainDefinitionRegistryValidator",
    "DomainDependency",
    "DomainDependencyMissing",
    "DomainError",
    "DomainId",
    "DomainKind",
    "DomainManifest",
    "DomainManifestId",
    "DomainMetadata",
    "DomainPack",
    "DomainPackKind",
    "DomainPackStatus",
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
    "DomainResult",
    "DomainResultId",
    "DomainSerializationError",
    "DomainStatus",
    "DomainValidationResult",
    "InMemoryDomainRegistryStore",
    "ParsedDomainPack",
]
