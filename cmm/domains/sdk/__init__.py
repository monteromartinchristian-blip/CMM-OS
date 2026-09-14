"""CMM OS Domain SDK (Phase 10.35).

A developer-facing ergonomics and tooling layer for creating, validating,
testing, and packaging CMM OS Domain Packs.
"""

from __future__ import annotations

from cmm.domains.sdk.builders import DomainBuilder, ManifestBuilder
from cmm.domains.sdk.fixtures import DomainFixtureError, DomainFixtureLoader
from cmm.domains.sdk.harness import (
    DomainHarnessContext,
    DomainHarnessError,
    DomainTestHarness,
)
from cmm.domains.sdk.packager import DomainPackager, DomainPackagingError
from cmm.domains.sdk.scaffold import DomainScaffolder, DomainScaffoldError
from cmm.domains.sdk.validation import validate_domain_path

__all__ = [
    "DomainBuilder",
    "DomainFixtureError",
    "DomainFixtureLoader",
    "DomainHarnessContext",
    "DomainHarnessError",
    "DomainPackager",
    "DomainPackagingError",
    "DomainScaffoldError",
    "DomainScaffolder",
    "DomainTestHarness",
    "ManifestBuilder",
    "validate_domain_path",
]
