"""Phase 10.32 — Domain Conflict Resolution Public API and backward compatibility tests."""

from __future__ import annotations

from cmm import domains
from cmm.domains.contracts import DomainConflict as ExistingDomainConflict
from cmm.domains.enums import DomainConflictPolicy as ExistingConflictPolicy


def test_phase_1032_public_symbols_are_exported() -> None:
    expected = {
        "DomainConflictReference",
        "DomainConflictCase",
        "DomainConflictResolution",
        "DomainConflictResolutionPolicy",
        "DomainConflictSourceKind",
        "DomainConflictKind",
        "DomainConflictSeverity",
        "DomainConflictStatus",
        "DomainConflictStrategy",
        "DomainConflictAuthority",
        "DomainConflictReasonCode",
        "DomainConflictResolver",
        "DomainConflictResolutionContractError",
        "DomainConflictResolutionSerializationError",
    }
    assert expected <= set(domains.__all__)
    for name in expected:
        assert hasattr(domains, name)


def test_existing_conflict_symbols_keep_identity() -> None:
    assert domains.DomainConflict is ExistingDomainConflict
    assert domains.DomainConflictPolicy is ExistingConflictPolicy
