"""Runtime-state observations for Languages purity boundary tests."""

from __future__ import annotations

from collections.abc import MutableMapping, MutableSequence, MutableSet
from copy import deepcopy
from types import ModuleType
from typing import Any

_MUTABLE_RUNTIME_TYPES = (MutableMapping, MutableSequence, MutableSet, bytearray)


def snapshot_languages_module_state(module: ModuleType) -> dict[str, Any]:
    """Deep-copy observable module-owned state, including private containers."""
    return {
        name: deepcopy(value)
        for name, value in vars(module).items()
        if not name.startswith("__")
        and isinstance(value, _MUTABLE_RUNTIME_TYPES)
    }
