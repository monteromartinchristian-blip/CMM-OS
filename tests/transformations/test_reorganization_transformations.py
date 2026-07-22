from __future__ import annotations

import ast

import pytest

from cmm.transformations import (
    ImpactAnalysisPrecondition,
    MergeModulesOperation,
    MergeModulesTransformation,
    MoveModuleOperation,
    MoveModuleTransformation,
    MovePackageOperation,
    MovePackageTransformation,
    RenameModuleOperation,
    RenameModuleTransformation,
    RenamePackageOperation,
    RenamePackageTransformation,
    ReorganizationPrecondition,
    SplitModuleGroup,
    SplitModuleOperation,
    SplitModuleTransformation,
)
from cmm.transformations.reorganization_impact import ReorganizationImpactRequest
from cmm.transformations.impact_analysis import ImpactDiscrepancyCode
from cmm.transformations.reorganization_validation import TopLevelSideEffectAnalyzer


@pytest.mark.parametrize(
    ("transformation", "operation_type", "identifier"),
    [
        (RenameModuleTransformation("pkg.old", "pkg.new"), RenameModuleOperation, "rename_module"),
        (MoveModuleTransformation("a.item", "b.item"), MoveModuleOperation, "move_module"),
        (
            SplitModuleTransformation(
                "pkg.source", (SplitModuleGroup("pkg.target", ("value",)),)
            ),
            SplitModuleOperation,
            "split_module",
        ),
        (
            MergeModulesTransformation(("pkg.a", "pkg.b"), "pkg.target"),
            MergeModulesOperation,
            "merge_modules",
        ),
        (RenamePackageTransformation("old", "new"), RenamePackageOperation, "rename_package"),
        (MovePackageTransformation("a.pkg", "b.pkg"), MovePackageOperation, "move_package"),
    ],
)
def test_reorganization_plans_are_deterministic_and_impact_guarded(
    transformation, operation_type, identifier
) -> None:
    first = transformation.create_plan("goal")
    second = transformation.create_plan("other goal")

    assert first == second
    assert first.id == identifier
    assert tuple(step.id for step in first.steps) == (f"{identifier}-1", f"{identifier}-2")
    assert isinstance(first.steps[0].operation, operation_type)
    assert first.steps[1].dependencies == (f"{identifier}-1",)
    assert isinstance(first.preconditions[0], ImpactAnalysisPrecondition)
    assert isinstance(first.preconditions[1], ReorganizationPrecondition)


def test_split_group_and_operation_metadata_are_immutable_and_complete() -> None:
    symbols = ["A", "build"]
    group = SplitModuleGroup("pkg.target", symbols)
    operation = SplitModuleOperation("pkg.source", (group,), delete_empty_source=True)
    symbols.append("later")

    assert group.symbols == ("A", "build")
    assert operation.metadata() == {
        "source_module": "pkg.source",
        "groups": [{"target_module": "pkg.target", "symbols": ["A", "build"]}],
        "delete_empty_source": True,
    }


def test_merge_and_move_policy_metadata_is_explicit() -> None:
    merge = MergeModulesOperation(
        ("pkg.a", "pkg.b"), "pkg.combined", create_target=False, keep_sources=True
    )
    move = MovePackageOperation(
        "root.a", "root.b.a", create_target_parents=True, delete_empty_source_parents=True
    )

    assert merge.metadata()["keep_sources"] is True
    assert merge.metadata()["create_target"] is False
    assert move.metadata()["create_target_parents"] is True
    assert move.metadata()["delete_empty_source_parents"] is True


def test_reorganization_impact_request_describes_module_symbol_and_package_moves() -> None:
    rename = ReorganizationImpactRequest.from_operation(
        RenameModuleOperation("pkg.old", "pkg.new"), "rename"
    )
    split = ReorganizationImpactRequest.from_operation(
        SplitModuleOperation(
            "pkg.source",
            (
                SplitModuleGroup("pkg.one", ("A",)),
                SplitModuleGroup("pkg.two", ("B",)),
            ),
        ),
        "split",
    )
    package = ReorganizationImpactRequest.from_operation(
        RenamePackageOperation("old", "new"), "package"
    )

    assert rename.module_moves == (("pkg.old", "pkg.new"),)
    assert split.symbol_moves == (
        ("pkg.source", "A", "pkg.one"),
        ("pkg.source", "B", "pkg.two"),
    )
    assert package.package_moves == (("old", "new"),)


@pytest.mark.parametrize(
    "source",
    [
        "register()\ndef value():\n    pass\n",
        "for item in values:\n    consume(item)\n",
        "with resource():\n    value = 1\n",
        "try:\n    value = 1\nexcept Exception:\n    value = 2\n",
        "if enabled:\n    value = 1\n",
    ],
)
def test_side_effect_analyzer_rejects_executable_top_level_code(source) -> None:
    assert TopLevelSideEffectAnalyzer().unsafe_statements(ast.parse(source))


def test_side_effect_analyzer_accepts_definitions_imports_and_literal_constants() -> None:
    tree = ast.parse(
        '"""module"""\n'
        "from typing import Final\n"
        "LIMIT: Final = 3\n"
        "VALUES = (1, 2, 3)\n"
        "class Item:\n    pass\n"
        "def build():\n    return Item()\n"
    )

    assert TopLevelSideEffectAnalyzer().unsafe_statements(tree) == ()


def test_side_effect_analyzer_rejects_operator_dispatch_on_imported_binding() -> None:
    tree = ast.parse("from package import plugin\nVALUE = plugin + 1\n")

    assert TopLevelSideEffectAnalyzer().unsafe_statements(tree) == (
        "Unsupported top-level Assign at line 2.",
    )


@pytest.mark.parametrize(
    "source",
    [
        "@register()\ndef value():\n    return 1\n",
        "def value(item=create_default()):\n    return item\n",
        "class Item:\n    register()\n",
    ],
)
def test_side_effect_analyzer_rejects_definition_time_execution(source) -> None:
    assert TopLevelSideEffectAnalyzer().unsafe_statements(ast.parse(source))


def test_reorganization_discrepancy_codes_are_public_and_structured() -> None:
    assert {
        ImpactDiscrepancyCode.MISSING_TARGET_MODULE.value,
        ImpactDiscrepancyCode.SOURCE_MODULE_STILL_PRESENT.value,
        ImpactDiscrepancyCode.MISSING_TARGET_PACKAGE.value,
        ImpactDiscrepancyCode.SOURCE_PACKAGE_STILL_PRESENT.value,
        ImpactDiscrepancyCode.STALE_PACKAGE_IMPORT.value,
        ImpactDiscrepancyCode.SYMBOL_IN_WRONG_MODULE.value,
        ImpactDiscrepancyCode.PACKAGE_CYCLE.value,
        ImpactDiscrepancyCode.FILESYSTEM_LAYOUT_MISMATCH.value,
    } == {
        "missing_target_module",
        "source_module_still_present",
        "missing_target_package",
        "source_package_still_present",
        "stale_package_import",
        "symbol_in_wrong_module",
        "package_cycle",
        "filesystem_layout_mismatch",
    }
