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

import heapq

from cmm.platform.compatibility import check_contract_compatibility
from cmm.platform.contracts import ServiceBinding
from cmm.platform.errors import (
    CircularDependencyError,
    DuplicateAuthorityError,
    DuplicateServiceError,
    FrozenServiceRegistryError,
    IncompatibleContractError,
    InvalidReplacementError,
    MissingDependencyError,
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

    # ── Graph validation ─────────────────────────────────────────────────────

    def _dependencies_of(self, service_id: str) -> tuple[str, ...]:
        return tuple(
            dependency.service_id
            for dependency in self._bindings[service_id].descriptor.dependencies
        )

    def _assert_dependencies_resolve(self) -> None:
        """Every dependency must exist and satisfy the declared contract."""

        for service_id in sorted(self._bindings):
            for dependency in self._bindings[service_id].descriptor.dependencies:
                target = self._bindings.get(dependency.service_id)
                if target is None:
                    raise MissingDependencyError(
                        "Required platform service dependency is not registered",
                        details={
                            "service_id": service_id,
                            "dependency_id": dependency.service_id,
                        },
                    )

                compatibility = check_contract_compatibility(
                    dependency.contract, target.descriptor.contract
                )
                if not compatibility.compatible:
                    raise IncompatibleContractError(
                        "Dependency contract is incompatible with the "
                        "registered service contract",
                        details={
                            "service_id": service_id,
                            "dependency_id": dependency.service_id,
                            "reason_code": compatibility.reason_code,
                        },
                    )

    def _find_cycle(self) -> tuple[str, ...] | None:
        """Return one dependency cycle as a closed path, or ``None``.

        Deterministic: services are visited in sorted order and each node's
        dependencies are visited in their canonical (sorted) order.
        """

        unvisited, in_progress, done = 0, 1, 2
        state = {service_id: unvisited for service_id in self._bindings}
        path: list[str] = []

        def visit(service_id: str) -> tuple[str, ...] | None:
            state[service_id] = in_progress
            path.append(service_id)

            for dependency in self._dependencies_of(service_id):
                if dependency not in state:
                    continue
                if state[dependency] is in_progress:
                    return tuple(path[path.index(dependency) :]) + (dependency,)
                if state[dependency] is unvisited:
                    found = visit(dependency)
                    if found is not None:
                        return found

            path.pop()
            state[service_id] = done
            return None

        for service_id in sorted(self._bindings):
            if state[service_id] is unvisited:
                found = visit(service_id)
                if found is not None:
                    return found

        return None

    def _assert_acyclic(self) -> None:
        cycle = self._find_cycle()
        if cycle is not None:
            raise CircularDependencyError(
                "Platform service graph contains a dependency cycle",
                details={"cycle": " -> ".join(cycle)},
            )

    def _assert_authority_unique(self) -> None:
        """No two distinct services may claim the same platform authority."""

        claims: dict[str, str] = {}
        for service_id in sorted(self._bindings):
            authority = self._bindings[service_id].descriptor.authority
            if authority is None:
                continue

            claimed_by = claims.get(authority)
            if claimed_by is not None and claimed_by != service_id:
                raise DuplicateAuthorityError(
                    "Two platform services claim the same authority",
                    details={
                        "authority": authority,
                        "service_id": claimed_by,
                        "conflicting_service_id": service_id,
                    },
                )
            claims[authority] = service_id

    def validate_graph(self) -> None:
        """Validate the complete platform service graph.

        Read-only and side-effect free: no bound implementation is constructed,
        called or otherwise executed.  Checks run in a documented, deterministic
        order: dependency resolution, cycle detection, authority uniqueness.
        """

        self._assert_dependencies_resolve()
        self._assert_acyclic()
        self._assert_authority_unique()

    def dependency_order(self) -> tuple[str, ...]:
        """Return a deterministic topological order of service IDs.

        Ties are broken by taking the lexically smallest service whose
        dependencies are all already satisfied, so the result depends only on
        the graph and never on registration order.
        """

        self._assert_dependencies_resolve()

        pending = {
            service_id: len(self._dependencies_of(service_id))
            for service_id in self._bindings
        }
        dependents: dict[str, list[str]] = {
            service_id: [] for service_id in self._bindings
        }
        for service_id in sorted(self._bindings):
            for dependency in self._dependencies_of(service_id):
                dependents[dependency].append(service_id)

        ready = [service_id for service_id, count in pending.items() if count == 0]
        heapq.heapify(ready)

        order: list[str] = []
        while ready:
            service_id = heapq.heappop(ready)
            order.append(service_id)
            for dependent in sorted(dependents[service_id]):
                pending[dependent] -= 1
                if pending[dependent] == 0:
                    heapq.heappush(ready, dependent)

        if len(order) != len(self._bindings):
            self._assert_acyclic()

        return tuple(order)


__all__ = ["IntegrationServiceRegistry"]
