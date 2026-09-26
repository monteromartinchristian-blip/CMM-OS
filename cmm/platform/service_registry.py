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

# The registry reuses the configuration module's single canonicalization of
# ``ServiceExpectation`` values, so a configured expectation set is validated and
# ordered identically wherever it is installed.  Both modules live in the same
# package and the helper stays private: the registry grows no second public
# configuration surface.
from cmm.platform.configuration import (
    ServiceExpectation,
    _canonicalize_expectations,
)
from cmm.platform.contracts import RuntimeContractMatch, ServiceBinding
from cmm.platform.errors import (
    CircularDependencyError,
    DuplicateAuthorityError,
    DuplicateServiceError,
    FrozenServiceRegistryError,
    IncompatibleContractError,
    InvalidConfigurationError,
    InvalidReplacementError,
    MissingDependencyError,
)

RUNTIME_CONTRACT_MISMATCH = "RUNTIME_CONTRACT_MISMATCH"

#: Private runtime-contract marker a canonical contract uses to require exact
#: concrete identity.  It is metadata read off the contract itself, so the
#: registry stays generic: no service ID, authority string or product-specific
#: knowledge is special-cased here.
EXACT_RUNTIME_CONTRACT_MARKER = "__cmm_exact_runtime_contract__"


def _effective_runtime_contract_match(binding: ServiceBinding) -> RuntimeContractMatch:
    """Return the runtime-contract rule the registry must actually enforce.

    A contract that declares :data:`EXACT_RUNTIME_CONTRACT_MARKER` is a *minimum*
    semantic: it upgrades whatever the binding declared to ``EXACT_TYPE``, so a
    hand-built binding can neither omit the field nor declare ``INSTANCE_OF`` to
    downgrade the canonical contract back to subtype-compatible matching.
    """

    if getattr(binding.runtime_contract, EXACT_RUNTIME_CONTRACT_MARKER, False) is True:
        return RuntimeContractMatch.EXACT_TYPE
    return binding.runtime_contract_match


def _runtime_contract_satisfied(binding: ServiceBinding) -> tuple[bool, bool]:
    """Return ``(checkable, satisfied)`` for a binding's runtime contract.

    ``INSTANCE_OF`` (the Phase 11.1 default) is only enforced when ``isinstance``
    is legally usable against the contract.  Anything else (``None``, a non-type
    such as a string, a subscripted generic, an exotic metaclass) is reported as
    not safely checkable rather than guessed at.

    ``EXACT_TYPE`` is always enforced and never falls back to ``isinstance``: the
    implementation's exact type must *be* the declared runtime contract.  A
    contract that is not a real type cannot be checked exactly at all, so it
    fails closed as unsatisfied instead of silently passing.
    """

    contract = binding.runtime_contract

    if _effective_runtime_contract_match(binding) is RuntimeContractMatch.EXACT_TYPE:
        if not isinstance(contract, type):
            return True, False
        return True, type(binding.implementation) is contract

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


def _assert_expectation_contract(
    binding: ServiceBinding, expectation: ServiceExpectation
) -> None:
    """Require the bound descriptor contract to satisfy *expectation*.

    Compatibility reuses the one Phase 11.1 engine; no second compatibility rule
    is introduced here.
    """

    compatibility = check_contract_compatibility(
        expectation.contract, binding.descriptor.contract
    )
    if not compatibility.compatible:
        raise IncompatibleContractError(
            "Bound descriptor contract does not satisfy the configured "
            "service expectation",
            details={
                "service_id": binding.descriptor.service_id,
                "reason_code": compatibility.reason_code,
            },
        )


def _assert_expectation_runtime_contract(
    binding: ServiceBinding,
    expectation: ServiceExpectation,
    expected_contract: type,
) -> None:
    """Enforce the authoritative runtime identity declared by *expectation*.

    ``expectation.runtime_contract`` — never the caller-authored
    ``binding.runtime_contract`` — is the authority.  The binding field is only a
    declaration that must agree with it, so a hand-built binding can neither omit
    the runtime contract, substitute ``object`` or a subclass for it, nor
    downgrade an exact rule back to subtype-compatible matching.  The bound
    implementation is then judged against the expectation.
    """

    service_id = binding.descriptor.service_id

    if binding.runtime_contract is not expected_contract:
        raise IncompatibleContractError(
            "Binding runtime contract declaration does not match the configured "
            "service expectation",
            details={
                "service_id": service_id,
                "reason_code": RUNTIME_CONTRACT_MISMATCH,
            },
        )

    if expectation.runtime_contract_match is RuntimeContractMatch.EXACT_TYPE:
        if binding.runtime_contract_match is not RuntimeContractMatch.EXACT_TYPE:
            raise IncompatibleContractError(
                "Binding declaration cannot downgrade the configured exact "
                "runtime contract match",
                details={
                    "service_id": service_id,
                    "reason_code": RUNTIME_CONTRACT_MISMATCH,
                },
            )
        satisfied = type(binding.implementation) is expected_contract
    else:
        # Fail closed rather than raising: even if a malformed expectation
        # somehow reached the registry, the bound implementation is rejected
        # instead of the check failing open.
        try:
            satisfied = isinstance(binding.implementation, expected_contract)
        except TypeError:
            satisfied = False

    if not satisfied:
        raise IncompatibleContractError(
            "Bound implementation does not satisfy the configured runtime expectation",
            details={
                "service_id": service_id,
                "reason_code": RUNTIME_CONTRACT_MISMATCH,
            },
        )


class IntegrationServiceRegistry:
    """Registry of platform composition bindings.

    Supports explicit registration, lookup, deterministic listing, explicit
    replacement before freeze, freeze semantics and graph validation.

    The registry also holds the **authoritative** runtime expectations of the
    services it composes.  When a :class:`ServiceExpectation` declares a runtime
    contract, that expectation decides which runtime type may claim the service
    identity: the binding must declare the same contract and match rule, and the
    bound implementation is judged against the expectation.  When no expectation
    is configured for a service ID, the inherited Phase 11.1 binding-declared
    behavior is preserved unchanged.

    The expectation set is copied, sorted and externally immutable, and it may
    only be strengthened — never weakened or replaced — so no composition can
    silently relax the identity of a service it already configured.
    """

    def __init__(self, expected_contracts: tuple[ServiceExpectation, ...] = ()) -> None:
        self._bindings: dict[str, ServiceBinding] = {}
        self._expected_contracts: dict[str, ServiceExpectation] = {}
        self._frozen = False
        self._install_expected_contracts(expected_contracts)

    # ── State ────────────────────────────────────────────────────────────────

    @property
    def frozen(self) -> bool:
        """Return whether the registry has been frozen for readiness."""

        return self._frozen

    def freeze(self) -> None:
        """Freeze the registry.  Idempotent; further mutation fails closed."""

        self._frozen = True

    # ── Authoritative service expectations ───────────────────────────────────
    #
    # Remediation V3 for Phase 11.50 MAJOR_V3_01.  The runtime identity of a
    # configured service is owned by the existing Phase 11.1
    # ``CompositionConfiguration.expected_contracts`` path, not by the
    # caller-authored ``ServiceBinding.runtime_contract`` field that is being
    # validated.  The registry only reads generic ``ServiceExpectation`` data: no
    # service ID, authority string or product-specific type is special-cased.

    def configure_expected_contracts(
        self, expected_contracts: tuple[ServiceExpectation, ...]
    ) -> None:
        """Attach authoritative service expectations to an existing registry.

        The operation is monotonic and atomic.  The candidate set must contain
        every already-configured expectation unchanged, so a later weaker,
        removed or different policy fails closed with
        :class:`~cmm.platform.errors.InvalidConfigurationError`; reapplying a
        semantically identical set is idempotent.  When the registry already
        holds bindings, every affected binding is validated against the candidate
        set *before* any expectation is installed, so a rejection leaves both the
        expectation state and the binding state exactly as they were.
        """

        if self._frozen:
            raise FrozenServiceRegistryError(
                "Cannot configure expectations on a frozen service registry"
            )

        self._install_expected_contracts(expected_contracts)

    def expected_contract_for(self, service_id: str) -> ServiceExpectation | None:
        """Return the authoritative expectation configured for *service_id*.

        One generic lookup by service identity: no service ID, authority string
        or product-specific knowledge is special-cased.
        """

        return self._expected_contracts.get(service_id)

    def expected_contracts(self) -> tuple[ServiceExpectation, ...]:
        """Return the configured expectations in deterministic service-ID order.

        A read-only projection: the registry never hands out its internal
        expectation state.
        """

        return tuple(
            self._expected_contracts[service_id]
            for service_id in sorted(self._expected_contracts)
        )

    def _install_expected_contracts(
        self,
        expected_contracts: tuple[ServiceExpectation, ...],
    ) -> None:
        """Validate one candidate expectation set, then install it atomically."""

        canonical = _canonicalize_expectations(expected_contracts)
        candidate = {item.service_id: item for item in canonical}

        for service_id, current in self._expected_contracts.items():
            if candidate.get(service_id) != current:
                raise InvalidConfigurationError(
                    "Configured service expectations cannot be weakened, "
                    "removed or replaced",
                    details={"service_id": service_id},
                )

        if candidate == self._expected_contracts:
            return

        # Atomic attachment: validate every already-registered binding the
        # candidate set covers before a single expectation is installed.
        for service_id in sorted(candidate):
            binding = self._bindings.get(service_id)
            if binding is not None:
                self._assert_binding_acceptable(binding, candidate[service_id])

        self._expected_contracts.update(candidate)

    def _assert_binding_acceptable(
        self,
        binding: ServiceBinding,
        expectation: ServiceExpectation | None,
    ) -> None:
        """The one expectation-aware validation path shared by register/replace.

        With an authoritative expectation the expectation decides; the binding's
        own runtime declaration is only checked for agreement.  Without one, the
        inherited Phase 11.1 binding-declared semantics are preserved unchanged.
        """

        if expectation is None:
            _assert_runtime_contract(binding)
            return

        _assert_expectation_contract(binding, expectation)

        expected_contract = expectation.runtime_contract
        if expected_contract is None:
            # A legacy expectation adds no authoritative runtime-type policy, so
            # the binding keeps the inherited Phase 11.1 runtime semantics.
            _assert_runtime_contract(binding)
            return

        _assert_expectation_runtime_contract(binding, expectation, expected_contract)

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

        self._assert_binding_acceptable(
            binding, self._expected_contracts.get(service_id)
        )

        self._bindings[service_id] = binding
        return binding

    def replace(self, service_id: str, binding: ServiceBinding) -> ServiceBinding:
        """Explicitly replace an existing binding before readiness.

        Replacement keeps the service ID stable and requires a compatible
        contract.  Neither the replaced nor the replacement implementation is
        mutated.

        Replacement changes the *binding only*: the authoritative expectation
        configured for the service is untouched, and the replacement is validated
        against that same expectation through the one shared assertion path that
        ``register()`` uses.
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

        self._assert_binding_acceptable(
            binding, self._expected_contracts.get(service_id)
        )

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
