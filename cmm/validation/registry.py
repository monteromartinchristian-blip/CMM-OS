from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Tuple

from .protocols import InternalValidator
from .exceptions import ValidationRegistryError


@dataclass(slots=True)
class ValidationRegistry:
    """In-memory registry of internal validators."""

    _validators: Dict[str, InternalValidator] = field(default_factory=dict)

    def register(
        self, name: str, validator: InternalValidator, *, replace: bool = False
    ) -> None:
        if not name:
            raise ValidationRegistryError(
                code="invalid_name", message="Validator name must not be empty"
            )
        if not hasattr(validator, "validate"):
            raise ValidationRegistryError(
                code="invalid_validator",
                message="Validator must implement validate(context, step)",
            )
        if name in self._validators and not replace:
            raise ValidationRegistryError(
                code="duplicate", message=f"Validator '{name}' already registered"
            )
        self._validators[name] = validator

    def unregister(self, name: str) -> None:
        if not name:
            raise ValidationRegistryError(
                code="invalid_name", message="Validator name must not be empty"
            )
        self._validators.pop(name, None)

    def get(self, name: str) -> InternalValidator:
        if not name:
            raise ValidationRegistryError(
                code="invalid_name", message="Validator name must not be empty"
            )
        try:
            return self._validators[name]
        except KeyError as exc:
            raise ValidationRegistryError(
                code="not_found", message=f"Validator '{name}' not found"
            ) from exc

    def has(self, name: str) -> bool:
        if not name:
            return False
        return name in self._validators

    def names(self) -> Tuple[str, ...]:
        # deterministic order by insertion in Python 3.7+ is preserved; convert to tuple
        return tuple(self._validators.keys())

    def clear(self) -> None:
        self._validators.clear()


__all__ = ["ValidationRegistry"]
