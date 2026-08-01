"""Deterministic domain-operation registry adapter."""

from __future__ import annotations

import inspect
from dataclasses import replace
from functools import cmp_to_key
from threading import RLock
from typing import Any

from cmm.agent_runtime.errors import AgentRuntimeError
from cmm.agent_runtime.operation_registry import AgentOperationRegistry
from cmm.domains.enums import DomainOperationStatus, DomainOperationType
from cmm.domains.errors import DomainOperationRegistryError
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.registry_contracts import compare_versions_desc


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
        self, definition: DomainOperationDefinition, implementation: Any
    ) -> None:
        self._validate_implementation(definition, implementation)
        key = (definition.operation_id, definition.version)
        with self._lock:
            if key in self._definitions:
                raise DomainOperationRegistryError(
                    f"Operation '{definition.operation_id}' version '{definition.version}' is already registered"
                )
            try:
                self._common_registry.register(definition.to_operation_descriptor())
            except AgentRuntimeError as exc:
                raise DomainOperationRegistryError(
                    "Common operation registry rejected the definition",
                    details={
                        "operation_id": definition.operation_id,
                        "version": definition.version,
                    },
                ) from exc
            self._definitions[key] = definition
            self._implementations[key] = implementation

    @staticmethod
    def _validate_implementation(
        definition: DomainOperationDefinition, implementation: Any
    ) -> None:
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
        return self._implementations[(operation_id, version)]

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


__all__ = ["InMemoryDomainOperationRegistry"]
