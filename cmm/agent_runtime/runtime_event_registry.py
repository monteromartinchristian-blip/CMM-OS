"""Phase 9.20 – Runtime Event Registry.

Registry for event types with validation, aliases, and schema versioning.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventFilter,
)
from cmm.agent_runtime.runtime_event_types import (
    EVENT_TYPE_CATEGORY_MAP,
    EventTypeCategory,
    get_all_registered_event_types,
    is_registered_event_type,
)


class AgentRuntimeEventRegistry:
    """Registry for runtime event types with strict/tolerant modes."""

    def __init__(self, strict_mode: bool = True) -> None:
        self._strict_mode = strict_mode
        self._aliases: dict[str, str] = {}
        self._validators: dict[str, Callable[[dict[str, Any]], None]] = {}
        self._custom_types: set[str] = set()
        self._schema_version: str = "1.0.0"

    @property
    def schema_version(self) -> str:
        """Return the schema version for this registry."""
        return self._schema_version

    def register(
        self,
        event_type: str,
        *,
        alias: str | None = None,
        validator: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Register an event type with optional alias and validator."""
        if not event_type:
            raise ValueError("event_type cannot be empty")
        if "." not in event_type:
            raise ValueError(
                f"event_type '{event_type}' must contain a namespace (dot separator)"
            )
        if event_type in self._aliases.values():
            raise ValueError(f"event_type '{event_type}' is already an alias")
        if alias and alias in self._aliases:
            raise ValueError(f"alias '{alias}' is already registered")
        if alias and not event_type:
            raise ValueError("cannot create alias without a target event_type")
        if event_type in EVENT_TYPE_CATEGORY_MAP:
            raise ValueError(f"event_type '{event_type}' is already a built-in type")
        if event_type in self._custom_types:
            raise ValueError(f"event_type '{event_type}' is already registered")
        self._custom_types.add(event_type)
        if alias:
            self._aliases[alias] = event_type
        if validator:
            self._validators[event_type] = validator

    def unregister(self, event_type: str) -> None:
        """Unregister a custom event type."""
        if event_type in EVENT_TYPE_CATEGORY_MAP:
            raise ValueError("cannot unregister built-in event types")
        if event_type not in self._custom_types:
            raise ValueError(f"event_type '{event_type}' is not registered")
        self._custom_types.discard(event_type)
        self._validators.pop(event_type, None)
        self._aliases = {k: v for k, v in self._aliases.items() if v != event_type}

    def resolve(self, event_type: str) -> str:
        """Resolve an event type, following aliases."""
        if event_type in self._aliases:
            return self._aliases[event_type]
        return event_type

    def contains(self, event_type: str) -> bool:
        """Check if an event type is registered (including aliases)."""
        resolved = self.resolve(event_type)
        return is_registered_event_type(resolved) or resolved in self._custom_types

    def aliases(self) -> dict[str, str]:
        """Return all registered aliases."""
        return dict(self._aliases)

    def validate_payload(self, event_type: str, payload: dict[str, Any]) -> None:
        """Run optional validator for an event type."""
        resolved = self.resolve(event_type)
        validator = self._validators.get(resolved)
        if validator:
            validator(payload)

    def get_category(self, event_type: str) -> EventTypeCategory:
        """Get the category for an event type."""
        resolved = self.resolve(event_type)
        if is_registered_event_type(resolved):
            return EVENT_TYPE_CATEGORY_MAP[resolved]
        return EventTypeCategory.RUNTIME_SYSTEM

    def ensure_registered(self, event_type: str) -> None:
        """Ensure an event type is registered, raising in strict mode."""
        resolved = self.resolve(event_type)
        if is_registered_event_type(resolved) or resolved in self._custom_types:
            return
        if self._strict_mode:
            raise ValueError(f"unknown event_type '{event_type}' in strict mode")
        # tolerate: do not raise

    def filter_events(
        self, events: list[AgentRuntimeEvent], filter: AgentRuntimeEventFilter
    ) -> list[AgentRuntimeEvent]:
        """Filter events using the provided filter."""
        return [event for event in events if filter.matches(event)]


def _initialize_builtin_registry() -> AgentRuntimeEventRegistry:
    """Create a registry pre-loaded with all built-in event types."""
    registry = AgentRuntimeEventRegistry(strict_mode=True)
    for event_type in get_all_registered_event_types():
        registry._custom_types.add(event_type)
    return registry


GLOBAL_REGISTRY = _initialize_builtin_registry()
