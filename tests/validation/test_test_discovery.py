from __future__ import annotations

from pathlib import Path

from cmm.validation.testing.discovery import discover_tests


def test_discover_tests_is_deterministic_and_relative(tmp_path: Path) -> None:
    project_root = tmp_path
    tests_dir = project_root / "tests"
    nested_dir = tests_dir / "pkg"
    cache_dir = tests_dir / "__pycache__"
    venv_dir = project_root / ".venv" / "lib"
    nested_dir.mkdir(parents=True)
    cache_dir.mkdir()
    venv_dir.mkdir(parents=True)

    (tests_dir / "test_alpha.py").write_text(
        "def test_alpha():\n    assert True\n", encoding="utf-8"
    )
    (nested_dir / "beta_test.py").write_text(
        "def test_beta():\n    assert True\n", encoding="utf-8"
    )
    (cache_dir / "test_cache.py").write_text("", encoding="utf-8")
    (venv_dir / "test_ignored.py").write_text("", encoding="utf-8")

    results = discover_tests(project_root)

    assert results == (
        Path("tests/pkg/beta_test.py"),
        Path("tests/test_alpha.py"),
    )
    assert all(not path.is_absolute() for path in results)


def test_discover_tests_ignores_external_symlinks(tmp_path: Path) -> None:
    project_root = tmp_path
    tests_dir = project_root / "tests"
    tests_dir.mkdir()
    outside = tmp_path.parent / "outside_test.py"
    outside.write_text("def test_outside():\n    assert True\n", encoding="utf-8")
    (tests_dir / "test_external.py").symlink_to(outside)

    assert discover_tests(project_root) == ()


def test_discover_tests_handles_missing_tests_directory(tmp_path: Path) -> None:
    assert discover_tests(tmp_path) == ()
