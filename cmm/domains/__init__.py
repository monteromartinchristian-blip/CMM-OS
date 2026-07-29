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
    DomainStatus,
)
from cmm.domains.errors import (
    DomainContractError,
    DomainContractValidationError,
    DomainError,
    DomainSerializationError,
)
from cmm.domains.identifiers import (
    DomainId,
    DomainManifestId,
    DomainResultId,
)

__all__ = [
    "DomainCapability",
    "DomainConflict",
    "DomainContractError",
    "DomainContractValidationError",
    "DomainDefinition",
    "DomainDependency",
    "DomainError",
    "DomainId",
    "DomainKind",
    "DomainManifestId",
    "DomainMetadata",
    "DomainResult",
    "DomainResultId",
    "DomainSerializationError",
    "DomainStatus",
]
