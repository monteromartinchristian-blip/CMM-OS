"""Phase 11.1 — the platform composition root.

``ApplicationContainer`` owns the assembled **references** and the readiness
state of the application composition.  It does not own the internal state or
lifecycle semantics of the services it references.

Readiness is never inferred and never partial: a container reports ``READY``
only after the full ordered pipeline below succeeds.  Any failure raises a
typed :class:`~cmm.platform.errors.PlatformCompositionError` and returns no
container, so a failed build can never be mistaken for a usable composition.

``ApplicationContainer.get_service`` exists so composition, wiring and
inspection code can resolve a bound implementation.  Normal production
consumers receive their collaborators through explicit dependency injection and
must not use the container as a global service locator.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from cmm.platform.compatibility import check_contract_compatibility
from cmm.platform.configuration import CompositionConfiguration
from cmm.platform.contracts import (
    ContainerState,
    ErrorResult,
    ServiceBinding,
)
from cmm.platform.errors import (
    ContainerNotReadyError,
    FrozenServiceRegistryError,
    IncompatibleContractError,
    InvalidConfigurationError,
    MissingDependencyError,
    PlatformCompositionError,
)
from cmm.platform.inspection import (
    ApplicationCompositionSnapshot,
    build_composition_snapshot,
)
from cmm.platform.modules import CompositionModule
from cmm.platform.service_registry import IntegrationServiceRegistry

MODULE_CONTRIBUTION_FAILED = "MODULE_CONTRIBUTION_FAILED"


class ApplicationContainer:
    """The one Phase 11.1 platform composition root."""

    __slots__ = ("_failure", "_registry", "_snapshot", "_state")

    def __init__(
        self,
        *,
        state: ContainerState,
        registry: IntegrationServiceRegistry | None,
        snapshot: ApplicationCompositionSnapshot | None,
        failure: ErrorResult | None,
    ) -> None:
        self._state = state
        self._registry = registry
        self._snapshot = snapshot
        self._failure = failure

    # ── Construction ─────────────────────────────────────────────────────────

    @classmethod
    def build(
        cls,
        configuration: CompositionConfiguration,
        modules: Sequence[CompositionModule] = (),
        registry: IntegrationServiceRegistry | None = None,
    ) -> ApplicationContainer:
        """Build a ready composition, or fail closed with a typed error.

        The pipeline order is fixed and matches the approved readiness
        semantics: validate configuration and make its authoritative service
        expectations active, validate module IDs, select enabled modules, collect
        contributions, register bindings, verify required services, verify
        expected contracts, validate the graph, freeze, build a safe snapshot, and
        only then become ready.

        ``configuration.expected_contracts`` is authoritative: for a registry the
        container creates it is installed before any module registers, and for a
        caller-supplied registry it is attached (or revalidated) atomically before
        READY.  A composition can therefore never become READY while a binding
        violates the runtime identity its configuration declares.
        """

        # 1. Validate configuration (and the supplied registry).
        if not isinstance(configuration, CompositionConfiguration):
            raise InvalidConfigurationError(
                "configuration must be a CompositionConfiguration",
                details={"field": "configuration"},
            )

        if registry is None:
            # The configuration's authoritative service expectations must be
            # active *before* any module contribution registers, so a bad
            # contributed binding fails at registration rather than only at final
            # inspection.
            registry = IntegrationServiceRegistry(configuration.expected_contracts)
        elif not isinstance(registry, IntegrationServiceRegistry):
            raise InvalidConfigurationError(
                "registry must be an IntegrationServiceRegistry",
                details={"field": "registry"},
            )
        else:
            if registry.frozen:
                raise FrozenServiceRegistryError(
                    "Composition registry must not be frozen before the build"
                )

            # Composing an already-populated registry stays supported, but it can
            # no longer bypass the configuration's expectations: they are
            # attached (or revalidated) atomically before the composition may
            # reach READY, so a pre-populated forged binding is rejected here and
            # the registry keeps its previous expectation and binding state.
            registry.configure_expected_contracts(configuration.expected_contracts)

        # 2. Validate module IDs.
        module_ids: list[str] = []
        for module in modules:
            module_id = getattr(module, "module_id", None)
            if not isinstance(module_id, str) or not module_id.strip():
                raise InvalidConfigurationError(
                    "composition module must expose a non-empty module_id",
                    details={"field": "module_id"},
                )
            if module_id in module_ids:
                raise InvalidConfigurationError(
                    "duplicate composition module ID",
                    details={"module_id": module_id},
                )
            module_ids.append(module_id)

        # 3. Select explicitly enabled modules.
        enabled = set(configuration.enabled_modules)
        provided = set(module_ids)
        unprovided = sorted(enabled - provided)
        if unprovided:
            raise InvalidConfigurationError(
                "Enabled composition module was not provided",
                details={"module_id": unprovided[0]},
            )

        selected = [module for module in modules if module.module_id in enabled]

        # 4. Collect contributed bindings.
        contributed: list[ServiceBinding] = []
        for module in selected:
            contributed.extend(cls._contribute(module, configuration))

        # 5. Register bindings.
        for binding in contributed:
            registry.register(binding)

        # 6. Verify every configured required service exists.
        for service_id in configuration.required_services:
            if registry.get(service_id) is None:
                raise MissingDependencyError(
                    "Required platform service is not composed",
                    details={"service_id": service_id},
                )

        # 7. Verify configured contract expectations.
        for expectation in configuration.expected_contracts:
            binding = registry.get(expectation.service_id)
            if binding is None:
                raise MissingDependencyError(
                    "Configured contract expectation references an absent service",
                    details={"service_id": expectation.service_id},
                )

            compatibility = check_contract_compatibility(
                expectation.contract, binding.descriptor.contract
            )
            if not compatibility.compatible:
                raise IncompatibleContractError(
                    "Configured contract expectation is not satisfied",
                    details={
                        "service_id": expectation.service_id,
                        "reason_code": compatibility.reason_code,
                    },
                )

        # 8. Validate the dependency graph.
        registry.validate_graph()

        # 9. Freeze the registry.
        registry.freeze()

        # 10. Create the safe composition snapshot.
        snapshot = build_composition_snapshot(ContainerState.READY, registry)

        # 11. Mark ready.
        return cls(
            state=ContainerState.READY,
            registry=registry,
            snapshot=snapshot,
            failure=None,
        )

    @classmethod
    def failed(cls, error: ErrorResult) -> ApplicationContainer:
        """Create an explicitly failed composition.

        A failed container records the structured failure, holds no registry and
        refuses service lookup or inspection, so a failed build can never be
        used as though readiness had succeeded.
        """

        if not isinstance(error, ErrorResult):
            raise TypeError("error must be an ErrorResult")

        return cls(
            state=ContainerState.FAILED, registry=None, snapshot=None, failure=error
        )

    @staticmethod
    def _contribute(
        module: CompositionModule,
        configuration: CompositionConfiguration,
    ) -> tuple[ServiceBinding, ...]:
        """Collect one module's contribution, failing closed on any defect."""

        module_id = module.module_id

        try:
            contributed = module.contribute(configuration)
        except PlatformCompositionError:
            raise
        except Exception as error:
            # A module contribution must fail closed: any defect becomes a
            # typed platform error carrying only the module identity.
            raise PlatformCompositionError(
                "Composition module failed to contribute bindings",
                code=MODULE_CONTRIBUTION_FAILED,
                details={"module_id": module_id},
            ) from error

        if not isinstance(contributed, tuple) or not all(
            isinstance(item, ServiceBinding) for item in contributed
        ):
            raise PlatformCompositionError(
                "Composition module returned a malformed contribution",
                code=MODULE_CONTRIBUTION_FAILED,
                details={"module_id": module_id},
            )

        return contributed

    # ── Readiness surface ────────────────────────────────────────────────────

    @property
    def state(self) -> ContainerState:
        """Return the composition lifecycle state."""

        return self._state

    def failure(self) -> ErrorResult | None:
        """Return the structured failure for a failed composition."""

        return self._failure

    def snapshot(self) -> ApplicationCompositionSnapshot:
        """Return the safe deterministic composition snapshot."""

        if self._snapshot is None:
            raise ContainerNotReadyError(
                "Application composition is not ready",
                details={"state": self._state.value},
            )
        return self._snapshot

    def get_service(self, service_id: str) -> Any:
        """Return the implementation bound to *service_id*.

        Composition, wiring and inspection facility only: production components
        receive collaborators through explicit dependency injection rather than
        resolving them from the container at runtime.
        """

        if self._state is not ContainerState.READY or self._registry is None:
            raise ContainerNotReadyError(
                "Application composition is not ready",
                details={"state": self._state.value},
            )

        binding = self._registry.get(service_id)
        if binding is None:
            raise MissingDependencyError(
                "Service is not part of the ready composition",
                details={"service_id": service_id},
            )

        return binding.implementation


__all__ = ["ApplicationContainer"]
