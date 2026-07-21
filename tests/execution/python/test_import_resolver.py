from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from cmm.execution.python import (
    ImportResolver,
    ImportType,
    PythonProjectParser,
    SemanticContextBuilder,
)


def _resolver(source: str) -> ImportResolver:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        (project_root / "module.py").write_text(source, encoding="utf-8")
        snapshot = PythonProjectParser().parse(project_root)
        return ImportResolver(SemanticContextBuilder().build(snapshot))


def test_resolves_simple_direct_import() -> None:
    resolution = _resolver("import foo\n").resolve_symbol("module", "foo")

    assert resolution is not None
    assert resolution.imported
    assert resolution.source_module == "foo"
    assert resolution.imported_name == "foo"
    assert resolution.alias is None
    assert resolution.import_type == ImportType.DIRECT_IMPORT


def test_resolves_direct_import_alias() -> None:
    resolution = _resolver("import foo as bar\n").resolve_symbol("module", "bar")

    assert resolution is not None
    assert resolution.source_module == "foo"
    assert resolution.imported_name == "foo"
    assert resolution.alias == "bar"
    assert resolution.import_type == ImportType.DIRECT_IMPORT


def test_resolves_from_import_and_alias() -> None:
    resolver = _resolver("from package import foo\nfrom other import value as alias\n")

    direct_resolution = resolver.resolve_symbol("module", "foo")
    alias_resolution = resolver.resolve_symbol("module", "alias")

    assert direct_resolution is not None
    assert direct_resolution.source_module == "package"
    assert direct_resolution.imported_name == "foo"
    assert direct_resolution.import_type == ImportType.FROM_IMPORT
    assert alias_resolution is not None
    assert alias_resolution.source_module == "other"
    assert alias_resolution.imported_name == "value"
    assert alias_resolution.alias == "alias"


def test_resolves_relative_import() -> None:
    resolution = _resolver("from .package import foo\n").resolve_symbol("module", "foo")

    assert resolution is not None
    assert resolution.source_module == ".package"
    assert resolution.import_type == ImportType.RELATIVE_IMPORT


def test_returns_none_for_missing_symbol() -> None:
    resolution = _resolver("import foo\n").resolve_symbol("module", "missing")

    assert resolution is None


def test_resolves_symbols_from_multiple_imports() -> None:
    resolver = _resolver(
        "import one\n"
        "from package import two\n"
        "from .relative import three as local_three\n"
    )

    assert resolver.resolve_symbol("module", "one").source_module == "one"
    assert resolver.resolve_symbol("module", "two").source_module == "package"
    assert (
        resolver.resolve_symbol("module", "local_three").source_module
        == ".relative"
    )
