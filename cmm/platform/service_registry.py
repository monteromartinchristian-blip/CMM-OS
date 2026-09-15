"""Phase 11.1 — the integration service registry.

``IntegrationServiceRegistry`` is the authoritative registry of **platform
composition bindings only**.  It registers how canonical subsystems are bound
into the platform composition; it never registers providers, agents, domains,
workflows, operations, tools, validators, rules or models themselves.

The registry is an ordinary object with no module-level singleton, so importing
``cmm.platform`` can never register anything globally.  It is a composition
mechanism, not a service locator: normal production components keep receiving
their collaborators through explicit dependency injection.
"""

from __future__ import annotations

from cmm.platform.compatibility import check_contract_compatibility
from cmm.platform.contracts import ServiceBinding
from cmm.platform.errors import (
    DuplicateServiceError,
    FrozenServiceRegistryError,
    IncompatibleContractError,
    InvalidReplacementError,
)

RUNTIME_CONTRACT_MISMATCH = "RUNTIME_CONTRACT_MISMATCH"


def _runtime_contract_satisfied(binding: ServiceBinding) -> tuple[bool, bool]:
    """Return ``(checkable, satisfied)`` for a binding's runtime contract.

    A runtime contract is only enforced when ``isinstance`` is legally usable
    against it.  Anything else (``None``, a non-type such as a string, a
    subscripted generic, an exotic metaclass) is reported as not safely
    checkable rather than guessed at.
    """

    contract = binding.runtime_contract
    if contract is None or not isinstance(contract, type):
        return False, True

    try:
        return True, isinstance(binding.implementation, contract)
    except TypeError:
        return False, True


def _assert_runtime_contract(binding: ServiceBinding) -> None:
    checkable, satisfied = _runtime_contract_satisfied(binding)
    if checkable and not satisfied:
        raise IncompatibleContractError(
            "Bound implementation does not satisfy the declared runtime contract",
            details={
                "service_id": binding.descriptor.service_id,
                "reason_code": RUNTIME_CONTRACT_MISMATCH,
            },
        )


class IntegrationServiceRegistry:
    """Registry of platform composition bindings.

    Supports explicit registration, lookup, deterministic listing, explicit
    replacement before freeze, freeze semantics and graph validation.
    """

    def __init__(self) -> None:
        self._bindings: dict[str, ServiceBinding] = {}
        self._frozen = False

    # ── State ────────────────────────────────────────────────────────────────

    @property
    def frozen(self) -> bool:
        """Return whether the registry has been frozen for readiness."""

        return self._frozen

    def freeze(self) -> None:
        """Freeze the registry.  Idempotent; further mutation fails closed."""

        self._frozen = True

    # ── Registration ─────────────────────────────────────────────────────────

    def register(self, binding: ServiceBinding) -> ServiceBinding:
        """Register one platform composition binding."""

        if not isinstance(binding, ServiceBinding):
            raise TypeError("binding must be a ServiceBinding instance")

        service_id = binding.descriptor.service_id

        if self._frozen:
            raise FrozenServiceRegistryError(
                "Cannot register into a frozen service registry",
                details={"service_id": service_id},
            )

        if service_id in self._bindings:
            raise DuplicateServiceError(
                "Service is already registered; use replace() explicitly",
                details={"service_id": service_id},
            )

        _assert_runtime_contract(binding)

        self._bindings[service_id] = binding
        return binding

    def replace(self, service_id: str, binding: ServiceBinding) -> ServiceBinding:
        """Explicitly replace an existing binding before readiness.

        Replacement keeps the service ID stable and requires a compatible
        contract.  Neither the replaced nor the replacement implementation is
        mutated.
        """

        if not isinstance(binding, ServiceBinding):
            raise TypeError("binding must be a ServiceBinding instance")

        details = {"service_id": service_id}

        if self._frozen:
            raise FrozenServiceRegistryError(
                "Cannot replace a binding in a frozen service registry",
                details=details,
            )

        target = self._bindings.get(service_id)
        if target is None:
            raise InvalidReplacementError(
                "Cannot replace an unregistered service", details=details
            )

        replacement_service_id = binding.descriptor.service_id
        if replacement_service_id != service_id:
            raise InvalidReplacementError(
                "Replacement must keep the same service ID",
                details={
                    **details,
                    "replacement_service_id": replacement_service_id,
                },
            )

        compatibility = check_contract_compatibility(
            target.descriptor.contract, binding.descriptor.contract
        )
        if not compatibility.compatible:
            raise IncompatibleContractError(
                "Replacement contract is not compatible with the existing contract",
                details={**details, "reason_code": compatibility.reason_code},
            )

        _assert_runtime_contract(binding)

        self._bindings[service_id] = binding
        return binding

    # ── Lookup ───────────────────────────────────────────────────────────────

    def get(self, service_id: str) -> ServiceBinding | None:
        """Return the binding for *service_id*, or ``None`` when absent."""

        return self._bindings.get(service_id)

    def list_bindings(self) -> tuple[ServiceBinding, ...]:
        """Return every binding sorted by service ID."""

        return tuple(
            self._bindings[service_id] for service_id in sorted(self._bindings)
        )

    def service_ids(self) -> tuple[str, ...]:
        """Return every registered service ID in deterministic order."""

        return tuple(sorted(self._bindings))

    def __len__(self) -> int:
        return len(self._bindings)


__all__ = ["IntegrationServiceRegistry"]
