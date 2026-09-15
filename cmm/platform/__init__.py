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

from cmm.platform.contracts import (
    ContainerState,
    ContractCanonicalizationEntry,
    ContractClassification,
    ContractMetadata,
    ServiceBinding,
    ServiceDependency,
    ServiceDescriptor,
    ServiceMode,
)

__all__ = [
    "ContainerState",
    "ContractCanonicalizationEntry",
    "ContractClassification",
    "ContractMetadata",
    "ServiceBinding",
    "ServiceDependency",
    "ServiceDescriptor",
    "ServiceMode",
]
