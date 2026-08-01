"""Phase 10.10 – Domain Resource Derivation Service.

Validates derivation lineage: derived *effective* permissions can never widen
source *effective* permissions, and derived sensitivity can never be lower
than source sensitivity. No payload, persistence or source fetch is
performed; the service only validates and returns the canonical derivation
record.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel as Sensitivity
from cmm.domains.errors import DomainResourceDerivationError
from cmm.domains.resource_contracts import DomainResourceDerivation

_SENSITIVITY_RANK: dict[Sensitivity, int] = {
    Sensitivity.PUBLIC: 0,
    Sensitivity.INTERNAL: 1,
    Sensitivity.PERSONAL: 2,
    Sensitivity.SENSITIVE: 3,
    Sensitivity.HIGHLY_SENSITIVE: 4,
    Sensitivity.RESTRICTED: 5,
}

_DENY_PREFIX = "deny:"


def _split_permissions(permissions: tuple[str, ...]) -> tuple[set[str], set[str]]:
    """Split a permission tuple into (granted, denied) permission names.

    A ``deny:`` entry without a permission name is malformed and rejected.
    """
    granted: set[str] = set()
    denied: set[str] = set()
    for permission in permissions:
        if permission.startswith(_DENY_PREFIX):
            name = permission[len(_DENY_PREFIX) :]
            if not name:
                raise DomainResourceDerivationError(
                    "deny: entries must name a non-empty permission",
                    field="permissions",
                    details={"value": permission},
                )
            denied.add(name)
        else:
            granted.add(permission)
    return granted, denied


class DomainResourceDerivationService:
    """Validates and records derivation lineage between resources."""

    def record(
        self,
        *,
        derivation: DomainResourceDerivation,
        source_permissions: tuple[str, ...],
        source_sensitivity: Sensitivity,
    ) -> DomainResourceDerivation:
        if not isinstance(derivation, DomainResourceDerivation):
            raise DomainResourceDerivationError(
                "derivation must be a DomainResourceDerivation", field="derivation"
            )

        source_granted, source_denied = _split_permissions(source_permissions)
        derived_granted, derived_denied = _split_permissions(derivation.permissions)

        source_effective = source_granted - source_denied
        derived_effective = derived_granted - derived_denied

        widened = derived_effective - source_effective
        if widened:
            raise DomainResourceDerivationError(
                "derived effective permissions cannot widen source effective "
                "permissions",
                field="permissions",
                details={"widened": sorted(widened)},
            )

        if (
            _SENSITIVITY_RANK[derivation.sensitivity]
            < _SENSITIVITY_RANK[source_sensitivity]
        ):
            raise DomainResourceDerivationError(
                "derived sensitivity cannot be lower than source sensitivity",
                field="sensitivity",
                details={
                    "derived": derivation.sensitivity.value,
                    "source": source_sensitivity.value,
                },
            )

        if not derivation.provenance:
            raise DomainResourceDerivationError(
                "derivation must retain complete lineage provenance",
                field="provenance",
            )

        return derivation


__all__ = ["DomainResourceDerivationService"]
