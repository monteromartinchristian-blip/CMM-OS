"""Phase 11.1 — deterministic offline contract compatibility.

The Phase 11.1 rule is deliberately conservative:

* exact contract name, exact owner, exact schema version and exact contract
  version are required for compatibility;
* unknown, malformed or non-conforming version tokens fail closed;
* there is no semver-range negotiation, no migration, no coercion, no silent
  downgrade and no remote lookup.

A migration framework belongs to later Phase 11 work, not here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from cmm.platform.contracts import ContractMetadata

#: A version token is a dotted numeric core with an optional ``-prerelease``
#: and/or ``+build`` suffix.  Anything else is malformed and fails closed.
_VERSION_PATTERN = re.compile(r"^[0-9]+(\.[0-9]+)*([-+][0-9A-Za-z.\-]+)?$")

EXACT_MATCH = "EXACT_MATCH"
MALFORMED_CONTRACT_METADATA = "MALFORMED_CONTRACT_METADATA"
MALFORMED_VERSION = "MALFORMED_VERSION"
CONTRACT_NAME_MISMATCH = "CONTRACT_NAME_MISMATCH"
OWNER_MISMATCH = "OWNER_MISMATCH"
SCHEMA_VERSION_MISMATCH = "SCHEMA_VERSION_MISMATCH"
CONTRACT_VERSION_MISMATCH = "CONTRACT_VERSION_MISMATCH"


class CompatibilityStatus(str, Enum):
    """Outcome of one compatibility comparison."""

    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"


@dataclass(frozen=True, slots=True)
class CompatibilityResult:
    """Immutable, serialization-safe compatibility outcome."""

    status: CompatibilityStatus
    reason_code: str

    @property
    def compatible(self) -> bool:
        return self.status is CompatibilityStatus.COMPATIBLE


def _incompatible(reason_code: str) -> CompatibilityResult:
    return CompatibilityResult(CompatibilityStatus.INCOMPATIBLE, reason_code)


def _is_well_formed_version(value: str) -> bool:
    return _VERSION_PATTERN.match(value) is not None


def check_contract_compatibility(
    required: ContractMetadata,
    provided: ContractMetadata,
) -> CompatibilityResult:
    """Return whether *provided* satisfies *required*.

    Evaluation order is deterministic and documented so diagnostics never
    depend on incidental field ordering:

    1. both operands must be ``ContractMetadata``;
    2. both version fields must be well formed;
    3. contract name;
    4. owner;
    5. schema version;
    6. contract version.
    """

    if not isinstance(required, ContractMetadata) or not isinstance(
        provided, ContractMetadata
    ):
        return _incompatible(MALFORMED_CONTRACT_METADATA)

    if not (
        _is_well_formed_version(required.contract_version)
        and _is_well_formed_version(required.schema_version)
        and _is_well_formed_version(provided.contract_version)
        and _is_well_formed_version(provided.schema_version)
    ):
        return _incompatible(MALFORMED_VERSION)

    if required.contract_name != provided.contract_name:
        return _incompatible(CONTRACT_NAME_MISMATCH)
    if required.owner != provided.owner:
        return _incompatible(OWNER_MISMATCH)
    if required.schema_version != provided.schema_version:
        return _incompatible(SCHEMA_VERSION_MISMATCH)
    if required.contract_version != provided.contract_version:
        return _incompatible(CONTRACT_VERSION_MISMATCH)

    return CompatibilityResult(CompatibilityStatus.COMPATIBLE, EXACT_MATCH)


__all__ = [
    "CompatibilityResult",
    "CompatibilityStatus",
    "check_contract_compatibility",
]
