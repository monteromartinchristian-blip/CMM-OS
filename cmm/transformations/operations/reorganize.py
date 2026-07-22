"""Typed operations for safe Python module and package reorganization."""

from __future__ import annotations

from dataclasses import dataclass

from cmm.transformations.operation import TransformationOperation


@dataclass(frozen=True)
class SplitModuleGroup:
    """One explicit destination and its selected top-level symbols."""

    target_module: str
    symbols: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbols", tuple(self.symbols))


class ReorganizationOperation(TransformationOperation):
    """Marker contract for operations that change the project layout."""


@dataclass(frozen=True)
class RenameModuleOperation(ReorganizationOperation):
    source_module: str
    target_module: str

    @property
    def name(self) -> str:
        return "rename_module"

    def describe(self) -> str:
        return f"Rename module {self.source_module} to {self.target_module}."

    def metadata(self) -> dict[str, object]:
        return {"source_module": self.source_module, "target_module": self.target_module}


@dataclass(frozen=True)
class MoveModuleOperation(ReorganizationOperation):
    source_module: str
    target_module: str
    create_target_package: bool = False
    delete_empty_source_package: bool = False

    @property
    def name(self) -> str:
        return "move_module"

    def describe(self) -> str:
        return f"Move module {self.source_module} to {self.target_module}."

    def metadata(self) -> dict[str, object]:
        return {
            "source_module": self.source_module,
            "target_module": self.target_module,
            "create_target_package": self.create_target_package,
            "delete_empty_source_package": self.delete_empty_source_package,
        }


@dataclass(frozen=True)
class SplitModuleOperation(ReorganizationOperation):
    source_module: str
    groups: tuple[SplitModuleGroup, ...]
    delete_empty_source: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "groups", tuple(self.groups))

    @property
    def name(self) -> str:
        return "split_module"

    def describe(self) -> str:
        return f"Split module {self.source_module} into {len(self.groups)} destinations."

    def metadata(self) -> dict[str, object]:
        return {
            "source_module": self.source_module,
            "groups": [
                {"target_module": group.target_module, "symbols": list(group.symbols)}
                for group in self.groups
            ],
            "delete_empty_source": self.delete_empty_source,
        }


@dataclass(frozen=True)
class MergeModulesOperation(ReorganizationOperation):
    source_modules: tuple[str, ...]
    target_module: str
    create_target: bool = True
    keep_sources: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_modules", tuple(self.source_modules))

    @property
    def name(self) -> str:
        return "merge_modules"

    def describe(self) -> str:
        return f"Merge {', '.join(self.source_modules)} into {self.target_module}."

    def metadata(self) -> dict[str, object]:
        return {
            "source_modules": list(self.source_modules),
            "target_module": self.target_module,
            "create_target": self.create_target,
            "keep_sources": self.keep_sources,
        }


@dataclass(frozen=True)
class RenamePackageOperation(ReorganizationOperation):
    source_package: str
    target_package: str

    @property
    def name(self) -> str:
        return "rename_package"

    def describe(self) -> str:
        return f"Rename package {self.source_package} to {self.target_package}."

    def metadata(self) -> dict[str, object]:
        return {"source_package": self.source_package, "target_package": self.target_package}


@dataclass(frozen=True)
class MovePackageOperation(ReorganizationOperation):
    source_package: str
    target_package: str
    create_target_parents: bool = False
    delete_empty_source_parents: bool = False

    @property
    def name(self) -> str:
        return "move_package"

    def describe(self) -> str:
        return f"Move package {self.source_package} to {self.target_package}."

    def metadata(self) -> dict[str, object]:
        return {
            "source_package": self.source_package,
            "target_package": self.target_package,
            "create_target_parents": self.create_target_parents,
            "delete_empty_source_parents": self.delete_empty_source_parents,
        }
