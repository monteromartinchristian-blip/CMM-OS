from __future__ import annotations

from pathlib import Path

import pytest


def test_impact_contracts_are_importable_and_serializable() -> None:
    from cmm.validation.impact import (
        ChangeImpactResult,
        ChangeSet,
        ChangeType,
        FileChange,
        FileChangeKind,
        FileVersion,
        ImportChange,
        ImportChangeKind,
        PublicAPIChange,
        SymbolChange,
        SymbolChangeKind,
    )

    before = FileVersion(
        path=Path("pkg/module.py"),
        exists=True,
        content_hash="abc",
        source="before",
        content="def func(x):\n    return x\n",
    )
    after = FileVersion(
        path=Path("pkg/module.py"),
        exists=True,
        content_hash="def",
        source="after",
        content="def func(x, y=1):\n    return x + y\n",
    )
    change = FileChange(
        before_path=Path("pkg/module.py"),
        after_path=Path("pkg/module.py"),
        kind=FileChangeKind.MODIFIED,
        before=before,
        after=after,
        confidence=0.9,
        reasons=("content_hash_changed",),
    )
    symbol_change = SymbolChange(
        module="pkg.module",
        symbol="func",
        kind=SymbolChangeKind.MODIFIED,
        confidence=0.9,
        before_signature="def func(x)",
        after_signature="def func(x, y=1)",
        before_decorators=(),
        after_decorators=(),
    )
    import_change = ImportChange(
        module="pkg.module",
        imported_module="pkg.other",
        kind=ImportChangeKind.ADDED,
        confidence=0.8,
    )
    public_api = PublicAPIChange(
        module="pkg.module",
        added=("func",),
        removed=(),
        changed=("func",),
        confidence=0.8,
    )
    change_set = ChangeSet(
        project_root=Path("/tmp/project"),
        before_root=Path("/tmp/project_before"),
        after_root=Path("/tmp/project_after"),
        file_changes=(change,),
        symbol_changes=(symbol_change,),
        import_changes=(import_change,),
        public_api_changes=(public_api,),
        change_type=ChangeType.STRUCTURAL_CHANGE,
        confidence=0.82,
        requires_full_suite=False,
        uncertainty=("signature_changed",),
        metadata={"source": "snapshots"},
    )
    result = ChangeImpactResult(
        change_type=ChangeType.STRUCTURAL_CHANGE,
        affected_modules=("pkg.module",),
        affected_symbols=("pkg.module:func",),
        affected_tests=("tests/test_module.py",),
        public_api_changed=False,
        confidence=0.82,
        requires_full_suite=False,
        findings=(),
        artifacts=(),
        uncertainty=("signature_changed",),
        metadata={"source": "analyzer"},
    )

    assert change_set.serialize()["file_changes"][0]["kind"] == "modified"
    assert change_set.serialize()["symbol_changes"][0]["symbol"] == "func"
    assert result.serialize()["confidence"] == 0.82
    assert result.serialize()["affected_tests"] == ["tests/test_module.py"]


def test_change_set_rejects_invalid_confidence() -> None:
    from cmm.validation.impact import ChangeSet, ChangeType

    with pytest.raises(Exception):
        ChangeSet(
            project_root=Path("/tmp/project"),
            before_root=None,
            after_root=None,
            file_changes=(),
            change_type=ChangeType.UNKNOWN,
            confidence=1.5,
            requires_full_suite=False,
        )
