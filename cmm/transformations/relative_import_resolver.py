"""Typed resolution and rendering of in-project relative imports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RelativeImportResolution:
    absolute_module: str
    level: int
    module: str


class RelativeImportResolver:
    """Resolve relative imports against one concrete consumer module."""

    def resolve(
        self,
        consumer_module: str,
        level: int,
        module: str,
        *,
        consumer_is_package: bool = False,
    ) -> RelativeImportResolution | None:
        if level < 0 or not consumer_module:
            return None
        if level == 0:
            return RelativeImportResolution(module, 0, module)
        package = consumer_module.split(".")
        if not consumer_is_package:
            package = package[:-1]
        ascend = level - 1
        if ascend > len(package):
            return None
        base = package[: len(package) - ascend]
        if not base:
            return None
        absolute = ".".join((*base, *([module] if module else [])))
        if not absolute:
            return None
        return RelativeImportResolution(absolute, level, module)

    def render_relative(
        self,
        consumer_module: str,
        target_module: str,
        *,
        consumer_is_package: bool = False,
    ) -> RelativeImportResolution | None:
        package = consumer_module.split(".")
        if not consumer_is_package:
            package = package[:-1]
        target = target_module.split(".")
        common = 0
        while common < len(package) and common < len(target) and package[common] == target[common]:
            common += 1
        if common == 0:
            return None
        level = len(package) - common + 1
        suffix = ".".join(target[common:])
        if not suffix:
            return None
        return RelativeImportResolution(target_module, level, suffix)
