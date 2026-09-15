"""Phase 11.1 — CMM OS platform integration core.

This package owns the platform **composition boundary** and nothing else.  It
composes already-existing canonical subsystems through explicit, version-aware
service bindings; it never becomes the owner of the subsystems it composes.

Direction of dependency::

    cmm.platform  ->  canonical subsystem packages

Importing this package performs no registration, no subsystem construction and
no global mutation.  Canonical subsystem classes stay owned by their own
packages; only Phase 11.1 platform-boundary values are re-exported here.
"""

from __future__ import annotations

from cmm.platform.compatibility import (
    CompatibilityResult,
    CompatibilityStatus,
    check_contract_compatibility,
)
from cmm.platform.configuration import (
    CompositionConfiguration,
    ServiceExpectation,
)
from cmm.platform.contracts import (
    ContainerState,
    ContractCanonicalizationEntry,
    ContractClassification,
    ContractMetadata,
    ErrorResult,
    ServiceBinding,
    ServiceDependency,
    ServiceDescriptor,
    ServiceMode,
)
from cmm.platform.errors import (
    CircularDependencyError,
    ContainerNotReadyError,
    DuplicateAuthorityError,
    DuplicateServiceError,
    FrozenServiceRegistryError,
    IncompatibleContractError,
    InvalidConfigurationError,
    InvalidReplacementError,
    MissingDependencyError,
    PlatformCompositionError,
)
from cmm.platform.modules import CompositionModule, StaticCompositionModule
from cmm.platform.service_registry import IntegrationServiceRegistry

__all__ = [
    "CircularDependencyError",
    "CompatibilityResult",
    "CompatibilityStatus",
    "CompositionConfiguration",
    "CompositionModule",
    "ContainerNotReadyError",
    "ContainerState",
    "ContractCanonicalizationEntry",
    "ContractClassification",
    "ContractMetadata",
    "DuplicateAuthorityError",
    "DuplicateServiceError",
    "ErrorResult",
    "FrozenServiceRegistryError",
    "IncompatibleContractError",
    "IntegrationServiceRegistry",
    "InvalidConfigurationError",
    "InvalidReplacementError",
    "MissingDependencyError",
    "PlatformCompositionError",
    "ServiceBinding",
    "ServiceDependency",
    "ServiceDescriptor",
    "ServiceExpectation",
    "ServiceMode",
    "StaticCompositionModule",
    "check_contract_compatibility",
]
