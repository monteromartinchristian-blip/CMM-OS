"""Deterministic domain-operation registry adapter."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, replace
from functools import cmp_to_key
from threading import RLock
from typing import Any

from cmm.agent_runtime.errors import AgentRuntimeError
from cmm.agent_runtime.operation_registry import (
    AgentOperationRegistry,
    AgentOperationRegistrySnapshot,
)
from cmm.domains.enums import DomainOperationStatus, DomainOperationType
from cmm.domains.errors import DomainOperationRegistryError
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.registry_contracts import compare_versions_desc


@dataclass(frozen=True, slots=True)
class DomainOperationRegistrySnapshot:
    """Immutable snapshot of the domain operation registry state.

    ``definitions`` is the canonical ordered tuple of registered definitions.
    ``implementations`` is the ordered tuple of ``(operation_id, version, implementation)``
    triples that reconstructs the implementation map.
    ``common_registry`` is the snapshot of the underlying common registry.
    """

    definitions: tuple[DomainOperationDefinition, ...]
    implementations: tuple[tuple[str, str, Any], ...]
    common_registry: AgentOperationRegistrySnapshot


def validate_domain_operation_implementation(
    definition: DomainOperationDefinition, implementation: Any
) -> None:
    """Validate that an implementation is compatible with its operation definition.

    This is the single canonical source of truth for operation-implementation
    compatibility.  It is side-effect free and deterministic: it returns
    ``None`` when the implementation is valid and raises
    :class:`DomainOperationRegistryError` otherwise.  It is reused by the
    registry (``register``/``restore_state``) and by callers that need to
    *pre-validate* implementations before any registry mutation.

    Validation rules:

    - ``implementation.definition`` must equal ``definition``;
    - ``implementation.execute`` must be callable;
    - ``execute`` must not accept ``*args``;
    - ``execute`` must accept exactly one required positional ``request`` and
      only optional additional parameters;
    - ``execute`` must not declare required keyword-only parameters.
    """
    impl_definition = getattr(implementation, "definition", None)
    if impl_definition != definition:
        raise DomainOperationRegistryError(
            "Implementation definition does not match registered definition"
        )
    execute = getattr(implementation, "execute", None)
    if not callable(execute):
        raise DomainOperationRegistryError(
            "Implementation must expose an execute method"
        )
    signature = inspect.signature(execute)
    parameters = tuple(signature.parameters.values())
    if any(parameter.kind is parameter.VAR_POSITIONAL for parameter in parameters):
        raise DomainOperationRegistryError(
            "Implementation execute signature must not accept *args"
        )
    positional = tuple(
        parameter
        for parameter in parameters
        if parameter.kind
        in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
    )
    required_positional = tuple(
        parameter for parameter in positional if parameter.default is parameter.empty
    )
    required_keyword_only = tuple(
        parameter
        for parameter in parameters
        if parameter.kind is parameter.KEYWORD_ONLY
        and parameter.default is parameter.empty
    )
    if (
        len(required_positional) != 1
        or not positional
        or positional[0].default is not positional[0].empty
        or required_keyword_only
    ):
        raise DomainOperationRegistryError(
            "Implementation execute signature must accept one required request "
            "and only optional additional parameters"
        )


class InMemoryDomainOperationRegistry:
    """Store domain definitions/implementations while reusing the common registry."""

    def __init__(self, common_registry: AgentOperationRegistry) -> None:
        self._common_registry = common_registry
        self._definitions: dict[tuple[str, str], DomainOperationDefinition] = {}
        self._implementations: dict[tuple[str, str], Any] = {}
        self._lock = RLock()

    @property
    def common_registry(self) -> AgentOperationRegistry:
        return self._common_registry

    def register(
        self, definition: DomainOperationDefinition, implementation: Any = None
    ) -> None:
        """Register a domain operation definition.

        ``implementation`` is optional.  When ``None``, the operation is
        registered as **UNAVAILABLE** (disabled in the common registry) and
        has no executable implementation.  This is the fail-closed default
        for operations that are declared but not yet implemented.
        """
        if implementation is not None:
            validate_domain_operation_implementation(definition, implementation)
        key = (definition.operation_id, definition.version)
        with self._lock:
            if key in self._definitions:
                raise DomainOperationRegistryError(
                    f"Operation '{definition.operation_id}' version '{definition.version}' is already registered"
                )
            descriptor = definition.to_operation_descriptor()
            if implementation is None:
                # Fail-closed: an operation without an implementation is
                # registered as disabled so the availability resolver marks
                # it UNAVAILABLE.
                from dataclasses import replace

                disabled_definition = replace(definition, enabled=False)
                descriptor = disabled_definition.to_operation_descriptor()
            try:
                self._common_registry.register(descriptor)
            except AgentRuntimeError as exc:
                raise DomainOperationRegistryError(
                    "Common operation registry rejected the definition",
                    details={
                        "operation_id": definition.operation_id,
                        "version": definition.version,
                    },
                ) from exc
            self._definitions[key] = (
                replace(definition, enabled=False)
                if implementation is None
                else definition
            )
            if implementation is not None:
                self._implementations[key] = implementation
            else:
                self._implementations.pop(key, None)

    def get(self, operation_id: str, version: str) -> DomainOperationDefinition:
        try:
            return self._definitions[(operation_id, version)]
        except KeyError as exc:
            raise DomainOperationRegistryError(
                "Domain operation is not registered",
                details={"operation_id": operation_id, "version": version},
            ) from exc

    def get_implementation(self, operation_id: str, version: str) -> Any:
        self.get(operation_id, version)
        try:
            return self._implementations[(operation_id, version)]
        except KeyError as exc:
            raise DomainOperationRegistryError(
                "Domain operation has no implementation and is UNAVAILABLE",
                details={"operation_id": operation_id, "version": version},
            ) from exc

    def resolve_active(
        self, operation_id: str, *, required: bool = True
    ) -> DomainOperationDefinition | None:
        candidates = [
            item
            for item in self._definitions.values()
            if item.operation_id == operation_id and item.enabled
        ]
        if not candidates:
            if required:
                raise DomainOperationRegistryError(
                    "No enabled version is registered",
                    details={"operation_id": operation_id},
                )
            return None
        return min(
            candidates,
            key=cmp_to_key(
                lambda left, right: compare_versions_desc(left.version, right.version)
            ),
        )

    def set_enabled(
        self, operation_id: str, version: str, enabled: bool
    ) -> DomainOperationDefinition:
        if not isinstance(enabled, bool):
            raise DomainOperationRegistryError("enabled must be a boolean")
        with self._lock:
            current = self.get(operation_id, version)
            if current.enabled is enabled:
                return current
            # Fail-closed: an operation without an implementation must never be
            # enabled, otherwise it would be resolvable/available yet unexecutable.
            if enabled and (operation_id, version) not in self._implementations:
                raise DomainOperationRegistryError(
                    "cannot enable operation without implementation",
                    details={"operation_id": operation_id, "version": version},
                )
            updated = replace(current, enabled=enabled)
            self._common_registry.unregister(operation_id, version)
            try:
                self._common_registry.register(updated.to_operation_descriptor())
            except AgentRuntimeError:
                self._common_registry.register(current.to_operation_descriptor())
                raise
            self._definitions[(operation_id, version)] = updated
            return updated

    def list_definitions(
        self,
        *,
        domain_id: str | None = None,
        operation_type: DomainOperationType | str | None = None,
        risk_level: Any | None = None,
    ) -> tuple[DomainOperationDefinition, ...]:
        if operation_type is not None and not isinstance(
            operation_type, DomainOperationType
        ):
            operation_type = DomainOperationType(operation_type)
        values = [
            item
            for item in self._definitions.values()
            if (domain_id is None or item.domain_id == domain_id)
            and (operation_type is None or item.operation_type is operation_type)
            and (risk_level is None or item.risk_level == risk_level)
        ]

        def compare(
            left: DomainOperationDefinition, right: DomainOperationDefinition
        ) -> int:
            if left.operation_id != right.operation_id:
                return -1 if left.operation_id < right.operation_id else 1
            return compare_versions_desc(left.version, right.version)

        return tuple(sorted(values, key=cmp_to_key(compare)))

    def inspect_definitions(self) -> tuple[dict[str, Any], ...]:
        return tuple(item.to_dict() for item in self.list_definitions())

    def list_by_availability(
        self,
        status: DomainOperationStatus | str,
        *,
        resolver: Any,
        context: Any,
    ) -> tuple[DomainOperationDefinition, ...]:
        target = (
            status
            if isinstance(status, DomainOperationStatus)
            else DomainOperationStatus(status)
        )
        return tuple(
            definition
            for definition in self.list_definitions()
            if resolver.resolve(definition, context).status is target
        )

    # ── Snapshot / restore ───────────────────────────────────────────────────

    def snapshot_state(self) -> DomainOperationRegistrySnapshot:
        """Capture the full registry state for transactional rollback."""
        with self._lock:
            definitions = tuple(
                sorted(
                    self._definitions.values(),
                    key=lambda d: (d.operation_id, d.version),
                )
            )
            implementations = tuple(
                sorted(
                    (
                        (op_id, version, impl)
                        for (op_id, version), impl in self._implementations.items()
                    ),
                    key=lambda item: (item[0], item[1]),
                )
            )
            common_snapshot = self._common_registry.snapshot_state()
        return DomainOperationRegistrySnapshot(
            definitions=definitions,
            implementations=implementations,
            common_registry=common_snapshot,
        )

    def restore_state(self, snapshot: DomainOperationRegistrySnapshot) -> None:
        """Restore the full registry state from a snapshot.

        Validates the snapshot completely before mutating.  Rejects wrong
        types and invalid snapshots without modifying the registry.
        """
        if not isinstance(snapshot, DomainOperationRegistrySnapshot):
            raise DomainOperationRegistryError(
                "snapshot must be a DomainOperationRegistrySnapshot",
                field="snapshot",
            )
        if not isinstance(snapshot.definitions, tuple):
            raise DomainOperationRegistryError(
                "snapshot.definitions must be a tuple",
                field="snapshot.definitions",
            )
        if not isinstance(snapshot.implementations, tuple):
            raise DomainOperationRegistryError(
                "snapshot.implementations must be a tuple",
                field="snapshot.implementations",
            )
        if not isinstance(snapshot.common_registry, AgentOperationRegistrySnapshot):
            raise DomainOperationRegistryError(
                "snapshot.common_registry must be an AgentOperationRegistrySnapshot",
                field="snapshot.common_registry",
            )
        for definition in snapshot.definitions:
            if not isinstance(definition, DomainOperationDefinition):
                raise DomainOperationRegistryError(
                    "snapshot.definitions contains a non-DomainOperationDefinition",
                    field="snapshot.definitions",
                )
        for item in snapshot.implementations:
            if not isinstance(item, tuple) or len(item) != 3:
                raise DomainOperationRegistryError(
                    "snapshot.implementations entries must be (operation_id, version, implementation) triples",
                    field="snapshot.implementations",
                )
            op_id, version, _impl = item
            if not isinstance(op_id, str) or not isinstance(version, str):
                raise DomainOperationRegistryError(
                    "snapshot.implementations entries must be (operation_id, version, implementation) triples",
                    field="snapshot.implementations",
                )

        # Validate consistency before mutating
        definition_keys = [(d.operation_id, d.version) for d in snapshot.definitions]
        if len(definition_keys) != len(set(definition_keys)):
            raise DomainOperationRegistryError(
                "snapshot.definitions contains duplicate (operation_id, version) keys",
                field="snapshot.definitions",
            )
        definition_key_set = set(definition_keys)
        implementation_keys = [(op_id, version) for op_id, version, _ in snapshot.implementations]
        if len(implementation_keys) != len(set(implementation_keys)):
            raise DomainOperationRegistryError(
                "snapshot.implementations contains duplicate (operation_id, version) keys",
                field="snapshot.implementations",
            )
        for op_id, version, _impl in snapshot.implementations:
            if (op_id, version) not in definition_key_set:
                raise DomainOperationRegistryError(
                    "snapshot.implementations references a missing definition",
                    field="snapshot.implementations",
                    details={"operation_id": op_id, "version": version},
                )

        definition_by_key = {
            (d.operation_id, d.version): d for d in snapshot.definitions
        }
        implementation_by_key = {
            (op_id, version): impl for op_id, version, impl in snapshot.implementations
        }

        # Cross-layer consistency, validated BEFORE touching the nested common
        # registry so no partial mutation can occur.

        # A. Every implementation must belong to its registered definition.
        for (op_id, version), impl in implementation_by_key.items():
            validate_domain_operation_implementation(
                definition_by_key[(op_id, version)], impl
            )

        # B. Every enabled definition requires an executable implementation.
        for definition in snapshot.definitions:
            if (
                definition.enabled
                and (definition.operation_id, definition.version)
                not in implementation_by_key
            ):
                raise DomainOperationRegistryError(
                    "Cannot restore an enabled definition without an implementation",
                    details={
                        "operation_id": definition.operation_id,
                        "version": definition.version,
                    },
                )

        # C. The common registry descriptors must correspond EXACTLY to the
        # definitions' to_operation_descriptor() representation.
        expected_descriptors: dict[tuple[str, str], Any] = {}
        for definition in snapshot.definitions:
            key = (definition.operation_id, definition.version)
            expected_descriptors[key] = definition.to_operation_descriptor()
        actual_descriptors: dict[tuple[str, str], Any] = {}
        for descriptor in snapshot.common_registry.descriptors:
            actual_descriptors[(descriptor.name, descriptor.version)] = descriptor

        expected_keys = set(expected_descriptors)
        actual_keys = set(actual_descriptors)
        if expected_keys != actual_keys:
            raise DomainOperationRegistryError(
                "Domain operation snapshot common registry is inconsistent with "
                "its definitions",
                details={
                    "missing_descriptors": sorted(expected_keys - actual_keys),
                    "extra_descriptors": sorted(actual_keys - expected_keys),
                },
            )
        for key in expected_keys:
            if actual_descriptors[key] != expected_descriptors[key]:
                raise DomainOperationRegistryError(
                    "Domain operation snapshot common descriptor does not match "
                    "its definition",
                    details={"operation_id": key[0], "version": key[1]},
                )

        # Validate the nested common registry snapshot completely before any
        # local mutation.  This ensures a nested invalid restore cannot leave
        # partial state.
        self._common_registry.restore_state(snapshot.common_registry)

        # All validation passed — mutate
        with self._lock:
            self._definitions = {
                (d.operation_id, d.version): d for d in snapshot.definitions
            }
            self._implementations = {
                (op_id, version): impl
                for op_id, version, impl in snapshot.implementations
            }


__all__ = [
    "DomainOperationRegistrySnapshot",
    "InMemoryDomainOperationRegistry",
    "validate_domain_operation_implementation",
]
