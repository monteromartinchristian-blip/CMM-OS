"""Reusable language-agnostic transformation operations."""

from cmm.transformations.operations.copy_symbol import CopySymbolOperation
from cmm.transformations.operations.create_file import CreateFileOperation
from cmm.transformations.operations.create_module import CreateModuleOperation
from cmm.transformations.operations.delete_file import DeleteFileOperation
from cmm.transformations.operations.delete_module import DeleteModuleOperation
from cmm.transformations.operations.delete_symbol import DeleteSymbolOperation
from cmm.transformations.operations.extract_method import ExtractMethodOperation
from cmm.transformations.operations.extract_module import ExtractModuleOperation
from cmm.transformations.operations.move_symbol import MoveSymbolOperation
from cmm.transformations.operations.rename_symbol import RenameSymbolOperation
from cmm.transformations.operations.update_imports import UpdateImportsOperation
from cmm.transformations.operations.validate_project import ValidateProjectOperation
from cmm.transformations.operations.reorganize import (
    MergeModulesOperation,
    MoveModuleOperation,
    MovePackageOperation,
    RenameModuleOperation,
    RenamePackageOperation,
    ReorganizationOperation,
    SplitModuleGroup,
    SplitModuleOperation,
)

__all__ = [
    "CopySymbolOperation",
    "CreateFileOperation",
    "CreateModuleOperation",
    "DeleteFileOperation",
    "DeleteModuleOperation",
    "DeleteSymbolOperation",
    "ExtractMethodOperation",
    "ExtractModuleOperation",
    "MoveSymbolOperation",
    "RenameSymbolOperation",
    "UpdateImportsOperation",
    "ValidateProjectOperation",
    "MergeModulesOperation",
    "MoveModuleOperation",
    "MovePackageOperation",
    "RenameModuleOperation",
    "RenamePackageOperation",
    "ReorganizationOperation",
    "SplitModuleGroup",
    "SplitModuleOperation",
]
