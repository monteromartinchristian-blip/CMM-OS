"""Phase 11.1 — side-effect-free modular composition contributions.

A composition module contributes :class:`~cmm.platform.contracts.ServiceBinding`
objects, and only when it is explicitly invoked.  Importing this module — or
importing ``cmm.platform`` as a whole — registers nothing, mutates no canonical
registry, and constructs no subsystem.

This is **not** the Phase 11.19 Plugin System.  Phase 11.1 performs no plugin
discovery, installation, sandboxing, permission management, upgrade or
uninstall, and never executes an untrusted entrypoint.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from cmm.platform.configuration import CompositionConfiguration
from cmm.platform.contracts import ServiceBinding


@runtime_checkable
class CompositionModule(Protocol):
    """Contribution contract for Phase 11.1 composition modules."""

    @property
    def module_id(self) -> str:
        """Return the stable, non-empty module identity."""

        ...

    def contribute(
        self,
        configuration: CompositionConfiguration,
    ) -> tuple[ServiceBinding, ...]:
        """Return the bindings this module contributes to the composition."""

        ...


class StaticCompositionModule:
    """A composition module holding an already-built immutable binding tuple.

    The module stores references only.  It never constructs a subsystem, never
    registers anything on construction, and never mutates its inputs.
    """

    def __init__(
        self, module_id: str, bindings: tuple[ServiceBinding, ...] = ()
    ) -> None:
        if not isinstance(module_id, str):
            raise TypeError("module_id must be a string")

        normalized = module_id.strip()
        if not normalized:
            raise ValueError("module_id must be non-empty")

        for binding in bindings:
            if not isinstance(binding, ServiceBinding):
                raise TypeError("bindings must contain ServiceBinding values")

        self._module_id = normalized
        self._bindings = tuple(bindings)

    @property
    def module_id(self) -> str:
        return self._module_id

    def contribute(
        self,
        configuration: CompositionConfiguration,
    ) -> tuple[ServiceBinding, ...]:
        """Return the stored bindings.  Registers nothing by itself.

        _configuration_ is accepted to satisfy the module contract; a static
        module's contribution does not depend on it.
        """

        return self._bindings


__all__ = ["CompositionModule", "StaticCompositionModule"]
