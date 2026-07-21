from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from cmm.execution.execution_context import ExecutionContext
from cmm.execution.python import PythonProjectParser, SemanticContextBuilder
from cmm.transformations import (
    DependencyEdge,
    ImpactDiscrepancyCode,
    ImpactAnalysisRequest,
    ImpactAnalyzer,
    ImpactIssueCode,
    ImpactSeverity,
    ReferenceKind,
    RewriteCapability,
)


def _context(root: Path) -> ExecutionContext:
    snapshot = PythonProjectParser().parse(root)
    semantic = SemanticContextBuilder().build(snapshot, build_reference_index=True)
    return ExecutionContext(root, semantic_context=semantic)


def _write_project(root: Path, files: dict[str, str]) -> None:
    for name, code in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code, encoding="utf-8")


def test_graph_is_deterministic_and_resolves_alias_relative_and_reexport(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "from .source import foo\n__all__ = ['foo']\n",
        "package/source.py": "def foo():\n    return 1\n",
        "package/consumer.py": "from .source import foo as local_foo\nvalue = local_foo()\n",
        "other.py": "from package.source import foo, other\nvalue = foo()\n",
    })
    request = ImpactAnalysisRequest("package.source", "package.target", ("foo",))
    first = ImpactAnalyzer().analyze(_context(tmp_path), request)
    second = ImpactAnalyzer().analyze(_context(tmp_path), request)
    assert first.graph == second.graph
    assert first.success
    assert first.consumer_modules == ("other", "package", "package.consumer")
    assert any(item.relative for item in first.affected_imports)
    assert any(item.reexport for item in first.affected_imports)
    assert all(path.is_absolute() for path in first.affected_paths)


def test_graph_resolves_qualified_module_references(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "",
        "package/source.py": "class Service:\n    pass\n",
        "consumer.py": "import package.source as source\nclass Child(source.Service):\n    pass\nvalue: source.Service\n",
    })
    result = ImpactAnalyzer().analyze(
        _context(tmp_path),
        ImpactAnalysisRequest("package.source", "package.target", ("Service",)),
    )
    assert result.success
    assert any(reference.kind == ReferenceKind.QUALIFIED for reference in result.affected_references)
    assert "consumer" in result.consumer_modules


def test_transitive_dependencies_ignore_builtins_and_locals(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "",
        "package/source.py": "from package.support import helper\n\ndef foo(value):\n    local = value + 1\n    return helper(local) + len([local])\n",
        "package/support.py": "def helper(value):\n    return value\n",
        "package/target.py": "",
    })
    result = ImpactAnalyzer().analyze(
        _context(tmp_path),
        ImpactAnalysisRequest("package.source", "package.target", ("foo",)),
    )
    assert result.success
    assert "package.support.helper" in result.direct_dependencies
    assert "local" not in result.direct_dependencies
    assert "len" not in result.direct_dependencies


def test_unselected_dependency_is_blocking_before_mutation(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "",
        "package/source.py": "def helper():\n    return 1\n\ndef foo():\n    return helper()\n",
        "package/target.py": "",
    })
    result = ImpactAnalyzer().analyze(
        _context(tmp_path),
        ImpactAnalysisRequest("package.source", "package.target", ("foo",)),
    )
    assert not result.success
    assert any(issue.code == ImpactIssueCode.UNSELECTED_DEPENDENCY for issue in result.errors)
    assert all(issue.severity == ImpactSeverity.BLOCKING for issue in result.errors)


def test_direct_and_transitive_cycles_are_structured(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "",
        "package/source.py": "from package.a import value\ndef foo():\n    return value\n",
        "package/a.py": "from package.source import foo\nvalue = foo\n",
        "package/b.py": "from package/c import value\n",
        "package/c.py": "from package/b import value\n",
        "package/target.py": "",
    })
    result = ImpactAnalyzer().analyze(
        _context(tmp_path),
        ImpactAnalysisRequest("package.source", "package.target", ("foo",)),
    )
    assert not result.success
    cycles = {tuple(cycle) for cycle in result.cycles}
    assert ("package.a", "package.source") in cycles
    assert any(issue.code == ImpactIssueCode.ARCHITECTURAL_CYCLE for issue in result.errors)


def test_dynamic_reference_is_blocking_and_cache_is_reused(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "",
        "package/source.py": "def foo():\n    return 1\n",
        "package/target.py": "",
        "consumer.py": "getattr(__import__('package.source'), 'foo')()\n",
    })
    context = _context(tmp_path)
    request = ImpactAnalysisRequest("package.source", "package.target", ("foo",))
    first = context.analyze_impact(request)
    second = context.analyze_impact(request)
    assert first is second
    assert not first.success
    assert any(issue.code == ImpactIssueCode.DYNAMIC_REFERENCE for issue in first.errors)
    dynamic = next(item for item in first.dynamic_references)
    assert dynamic.capability == RewriteCapability.BLOCKING
    assert not dynamic.rewrite_supported


def test_expected_plan_contains_direct_import_and_qualified_rewrite(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "",
        "package/source.py": "def foo():\n    return 1\n",
        "package/target.py": "",
        "consumer.py": "import package.source as source\nvalue = source.foo()\n",
    })
    result = ImpactAnalyzer().analyze(
        _context(tmp_path),
        ImpactAnalysisRequest("package.source", "package.target", ("foo",)),
    )

    assert result.success
    assert result.plan is not None
    assert result.plan.rewritten_imports[0].source_module == "package.target"
    assert result.plan.rewritten_imports[0].imported_symbol is None
    assert result.plan.rewritten_references[0].resolved_target == "package.target"


def test_proposed_cycle_is_blocking_before_mutation(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "",
        "package/source.py": "def foo():\n    return 1\n",
        "package/target.py": "from package.consumer import value\n",
        "package/consumer.py": "from package.source import foo\nvalue = foo()\n",
    })

    result = ImpactAnalyzer().analyze(
        _context(tmp_path),
        ImpactAnalysisRequest("package.source", "package.target", ("foo",)),
    )

    assert not result.success
    assert any(
        issue.code == ImpactIssueCode.ARCHITECTURAL_CYCLE
        and "would introduce" in issue.message
        for issue in result.errors
    )


def test_discrepancy_contract_exposes_all_required_codes() -> None:
    assert {item.value for item in ImpactDiscrepancyCode} >= {
        "missing_target_symbol",
        "source_symbol_still_present",
        "stale_import",
        "stale_reference",
        "unexpected_cycle",
        "unexpected_path_change",
        "missing_reexport",
        "public_api_mismatch",
        "unresolved_reference_after_rewrite",
    }


def test_expected_plan_is_immutable_deterministic_and_json_serializable(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "from .source import foo\n",
        "package/source.py": "def foo():\n    return 1\n",
        "package/target.py": "",
    })
    request = ImpactAnalysisRequest("package.source", "package.target", ("foo",))
    first = ImpactAnalyzer().analyze(_context(tmp_path), request)
    second = ImpactAnalyzer().analyze(_context(tmp_path), request)

    assert first.plan == second.plan
    assert json.loads(json.dumps(first.plan.serialize()))["moved_symbols"][0] == {
        "module": "package.source",
        "symbol": "foo",
        "target_module": "package.target",
        "target_symbol": "foo",
    }


def test_unrelated_dynamic_reference_all_and_cycle_do_not_block(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "",
        "package/source.py": "def foo():\n    return 1\n",
        "package/target.py": "",
        "unrelated/a.py": "from unrelated.b import value\n__all__.append('value')\ngetattr(object(), 'other')\n",
        "unrelated/b.py": "from unrelated.a import value\nvalue = 1\n",
    })

    result = ImpactAnalyzer().analyze(
        _context(tmp_path),
        ImpactAnalysisRequest("package.source", "package.target", ("foo",)),
    )

    assert result.success
    assert ("unrelated.a", "unrelated.b") in result.cycles


def test_mixed_qualified_module_usage_is_blocking(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "",
        "package/source.py": "def foo():\n    return 1\n\ndef other():\n    return 2\n",
        "package/target.py": "",
        "consumer.py": (
            "import package.source as source\n"
            "first = source.foo()\nsecond = source.other()\n"
        ),
    })

    result = ImpactAnalyzer().analyze(
        _context(tmp_path),
        ImpactAnalysisRequest("package.source", "package.target", ("foo",)),
    )

    assert not result.success
    assert any(
        issue.code == ImpactIssueCode.AMBIGUOUS_REFERENCE
        and "mixes moved and non-moved" in issue.message
        for issue in result.errors
    )


def test_relevant_all_mutation_is_blocking(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "from .source import foo\n__all__ = ['foo']\n__all__.append('other')\n",
        "package/source.py": "def foo():\n    return 1\n",
        "package/target.py": "",
    })

    result = ImpactAnalyzer().analyze(
        _context(tmp_path),
        ImpactAnalysisRequest("package.source", "package.target", ("foo",)),
    )

    assert not result.success
    assert any(issue.code == ImpactIssueCode.DYNAMIC_ALL for issue in result.errors)


def test_renamed_ambiguous_reexport_chain_is_blocking(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "from .source import foo\n",
        "package/source.py": "def foo():\n    return 1\n",
        "package/target.py": "",
        "consumer.py": "from package import foo\nfoo()\n",
    })

    result = ImpactAnalyzer().analyze(
        _context(tmp_path),
        ImpactAnalysisRequest(
            "package.source", "package.target", ("foo",), ("bar",)
        ),
    )

    assert not result.success
    assert any(
        issue.code == ImpactIssueCode.AMBIGUOUS_REEXPORT for issue in result.errors
    )


def test_post_validation_reports_missing_source_and_stale_import_details(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "",
        "package/source.py": "def foo():\n    return 1\n",
        "package/target.py": "",
        "consumer.py": "from package.source import foo\nfoo()\n",
    })
    context = _context(tmp_path)
    expected = ImpactAnalyzer().analyze(
        context,
        ImpactAnalysisRequest("package.source", "package.target", ("foo",)),
    )

    result = ImpactAnalyzer().validate_post(context, expected)
    by_code = {item.code: item for item in result.discrepancies}

    assert not result.success
    assert by_code[ImpactDiscrepancyCode.MISSING_TARGET_SYMBOL].expected == "package.target.foo"
    assert by_code[ImpactDiscrepancyCode.SOURCE_SYMBOL_STILL_PRESENT].actual == "package.source.foo"
    assert by_code[ImpactDiscrepancyCode.STALE_IMPORT].path.name == "consumer.py"


def test_post_validation_reports_unexpected_path_cycle_and_dynamic_reference(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "",
        "package/source.py": "def foo():\n    return 1\n",
        "package/target.py": "",
        "consumer.py": "from package.source import foo\nfoo()\n",
        "extra.py": "",
    })
    context = _context(tmp_path)
    expected = ImpactAnalyzer().analyze(
        context,
        ImpactAnalysisRequest("package.source", "package.target", ("foo",)),
    )
    (tmp_path / "package" / "source.py").write_text("", encoding="utf-8")
    (tmp_path / "package" / "target.py").write_text(
        "from consumer import value\ndef foo():\n    return 1\n", encoding="utf-8"
    )
    (tmp_path / "consumer.py").write_text(
        "from package.target import foo\n"
        "value = getattr(__import__('package.source'), 'foo')\n",
        encoding="utf-8",
    )
    context.refresh_semantic_context()

    result = ImpactAnalyzer().validate_post(
        context, expected, (tmp_path / "extra.py",)
    )
    codes = {item.code for item in result.discrepancies}

    assert ImpactDiscrepancyCode.UNEXPECTED_PATH_CHANGE in codes
    assert ImpactDiscrepancyCode.UNEXPECTED_CYCLE in codes
    assert ImpactDiscrepancyCode.UNRESOLVED_REFERENCE_AFTER_REWRITE in codes


def test_post_validation_reports_missing_reexport_and_stale_qualified_reference(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "from .source import foo\n__all__ = ['foo']\n",
        "package/source.py": "def foo():\n    return 1\n",
        "package/target.py": "",
        "consumer.py": "import package.source as source\nsource.foo()\n",
    })
    context = _context(tmp_path)
    expected = ImpactAnalyzer().analyze(
        context,
        ImpactAnalysisRequest("package.source", "package.target", ("foo",)),
    )
    (tmp_path / "package" / "source.py").write_text("", encoding="utf-8")
    (tmp_path / "package" / "target.py").write_text(
        "def foo():\n    return 1\n", encoding="utf-8"
    )
    (tmp_path / "package" / "__init__.py").write_text(
        "__all__ = []\n", encoding="utf-8"
    )
    context.refresh_semantic_context()

    result = ImpactAnalyzer().validate_post(context, expected)
    codes = {item.code for item in result.discrepancies}

    assert ImpactDiscrepancyCode.STALE_REFERENCE in codes
    assert ImpactDiscrepancyCode.MISSING_REEXPORT in codes
    assert ImpactDiscrepancyCode.PUBLIC_API_MISMATCH in codes


def test_rollback_validation_reports_graph_mismatch(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "",
        "package/source.py": "def foo():\n    return 1\n",
        "package/target.py": "",
    })
    context = _context(tmp_path)
    expected = ImpactAnalyzer().analyze(
        context,
        ImpactAnalysisRequest("package.source", "package.target", ("foo",)),
    )
    (tmp_path / "package" / "source.py").write_text(
        "def foo():\n    return 2\n\ndef extra():\n    pass\n", encoding="utf-8"
    )
    context.refresh_semantic_context()

    result = ImpactAnalyzer().validate_rollback(context, expected)

    assert not result.success
    assert not result.rollback_graph_matches
    assert result.rollback_discrepancies[0].code == ImpactDiscrepancyCode.ROLLBACK_GRAPH_MISMATCH


def test_cross_root_relative_import_is_classified_as_non_rewritable(tmp_path) -> None:
    _write_project(tmp_path, {
        "one/__init__.py": "",
        "one/source.py": "def foo():\n    return 1\n",
        "one/consumer.py": "from .source import foo\nfoo()\n",
        "two/__init__.py": "",
        "two/target.py": "",
    })

    result = ImpactAnalyzer().analyze(
        _context(tmp_path),
        ImpactAnalysisRequest("one.source", "two.target", ("foo",)),
    )

    assert not result.success
    affected = next(item for item in result.affected_imports if item.imported_symbol == "foo")
    assert not affected.rewrite_supported
    assert affected.capability == RewriteCapability.BLOCKING


def test_cycle_detection_is_iterative_for_large_graphs() -> None:
    modules = tuple(f"module_{index:04d}" for index in range(1500))
    edges = tuple(
        DependencyEdge(modules[index], modules[index + 1], "import")
        for index in range(len(modules) - 1)
    ) + (DependencyEdge(modules[-1], modules[0], "import"),)

    cycles = ImpactAnalyzer()._cycles(modules, edges)

    assert cycles == (tuple(sorted(modules)),)


def test_rollback_graph_comparison_includes_qualified_references(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "",
        "package/source.py": "def foo():\n    return 1\n",
        "package/target.py": "",
        "consumer.py": "import package.source as source\nsource.foo()\n",
    })
    context = _context(tmp_path)
    expected = ImpactAnalyzer().analyze(
        context,
        ImpactAnalysisRequest("package.source", "package.target", ("foo",)),
    )
    (tmp_path / "consumer.py").write_text(
        "import package.source as source\nsource.other()\n", encoding="utf-8"
    )
    context.refresh_semantic_context()

    result = ImpactAnalyzer().validate_rollback(context, expected)

    assert not result.rollback_graph_matches


def test_technical_memory_error_is_structured(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "",
        "package/source.py": "def foo():\n    return 1\n",
        "package/target.py": "",
    })

    class Memory:
        def refresh(self):
            return SimpleNamespace(success=False, errors=("memory read failed",))

    result = ImpactAnalyzer(Memory()).analyze(
        _context(tmp_path),
        ImpactAnalysisRequest("package.source", "package.target", ("foo",)),
    )

    assert not result.success
    assert result.memory_errors == ("memory read failed",)
    assert any(
        issue.code == ImpactIssueCode.TECHNICAL_MEMORY_ERROR
        for issue in result.errors
    )


def test_dynamic_all_is_blocking_and_memory_refresh_is_reported(tmp_path) -> None:
    _write_project(tmp_path, {
        "package/__init__.py": "from .source import foo\n__all__ = get_names()\n",
        "package/source.py": "def foo():\n    return 1\n",
        "package/target.py": "",
    })

    class Memory:
        def refresh(self):
            return SimpleNamespace(rebuilt=True)

    result = ImpactAnalyzer(Memory()).analyze(
        _context(tmp_path),
        ImpactAnalysisRequest("package.source", "package.target", ("foo",)),
    )
    assert not result.success
    assert result.memory_refreshed
    assert any(issue.code == ImpactIssueCode.DYNAMIC_ALL for issue in result.errors)
