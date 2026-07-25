from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from cmm.validation.context import ValidationContext
from cmm.validation.errors import ValidationContractError
from .discovery import classify_test_path, discover_tests

_STOPWORDS = {
    "cmm",
    "kernel",
    "src",
    "test",
    "tests",
    "python",
    "py",
    "init",
    "__init__",
}

_PYTHON_CONFIG_FILES = {
    "pyproject.toml",
    "pytest.ini",
    "setup.cfg",
    "tox.ini",
}

_CROSS_CUTTING_PATHS = {
    "conftest.py",
}


def _normalize_path(path: Path | str) -> Path:
    return Path(str(path))


def _tokenize(value: str | Path) -> tuple[str, ...]:
    raw = str(value).replace("\\", "/").lower()
    tokens = re.findall(r"[a-z0-9]+", raw)
    return tuple(token for token in tokens if token and token not in _STOPWORDS)


def _path_tokens(path: Path) -> tuple[str, ...]:
    return _tokenize(path)


def _package_scope_for_change(path: Path) -> str | None:
    parts = path.parts
    if not parts:
        return None
    if parts[0] == "cmm" and len(parts) >= 2:
        return parts[1]
    if parts[0] == "kernel":
        return "kernel"
    if len(parts) == 1:
        stem = path.stem
        if stem == "__init__":
            return None
        return ""
    if parts[0] == "tests":
        return parts[1] if len(parts) >= 3 else ""
    return parts[0]


def _is_python_file(path: Path) -> bool:
    return path.suffix == ".py"


def _is_test_filename(name: str) -> bool:
    lower = name.lower()
    return (lower.startswith("test_") and lower.endswith(".py")) or lower.endswith("_test.py")


def _is_config_change(path: Path) -> bool:
    name = path.name.lower()
    return name in _PYTHON_CONFIG_FILES or name in _CROSS_CUTTING_PATHS


def _is_cross_cutting_change(path: Path) -> bool:
    lower = str(path).replace("\\", "/").lower()
    if lower.startswith("kernel/"):
        return True
    if lower.startswith("cmm/validation/"):
        return True
    if lower.endswith("/executor.py") or lower.endswith("/pipeline.py") or lower.endswith("/registry.py"):
        return True
    return False


def _candidate_test_paths(change: Path, discovered: set[Path]) -> tuple[Path, ...]:
    if change.name == "__init__.py":
        scope = _package_scope_for_change(change)
        if not scope:
            return ()
        prefix = Path("tests") / scope
        matches = [test for test in discovered if str(test).replace("\\", "/").startswith(str(prefix).replace("\\", "/") + "/")]
        return tuple(matches)

    stem = change.stem
    scope = _package_scope_for_change(change)
    candidates: list[Path] = [Path("tests") / f"test_{stem}.py", Path("tests") / f"{stem}_test.py"]
    if scope:
        scope_dir = Path("tests") / scope
        candidates.extend(
            [
                scope_dir / f"test_{stem}.py",
                scope_dir / f"{stem}_test.py",
                scope_dir / f"test_{scope}_{stem}.py",
                scope_dir / f"{scope}_{stem}_test.py",
            ]
        )
    if scope == "":
        candidates.append(Path("tests") / f"test_{change.parent.name}_{stem}.py")
    return tuple(candidate for candidate in candidates if candidate in discovered)


def _score_tokens(change: Path, test_path: Path) -> tuple[float, str | None]:
    change_tokens = set(_path_tokens(change))
    test_tokens = set(_path_tokens(test_path))
    shared = tuple(sorted(change_tokens & test_tokens))
    if not shared:
        return 0.0, None
    if len(shared) >= 3:
        return 0.75, "token_match_strong"
    if len(shared) == 2:
        return 0.5, "token_match_partial"
    return 0.0, None


@dataclass(frozen=True, slots=True)
class TestSelection:
    selected_tests: tuple[Path, ...] = ()
    related_changes: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    confidence: float = 0.0
    requires_full_suite: bool = False
    reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationContractError("TestSelection.confidence must be between 0.0 and 1.0")
        normalized_tests = tuple(Path(str(path)) for path in self.selected_tests)
        if any(path.is_absolute() for path in normalized_tests):
            raise ValidationContractError("TestSelection.selected_tests must be relative paths")
        normalized_related: dict[str, tuple[str, ...]] = {
            str(key): tuple(str(item) for item in value)
            for key, value in dict(self.related_changes or {}).items()
        }
        object.__setattr__(self, "selected_tests", tuple(sorted(normalized_tests, key=str)))
        object.__setattr__(self, "related_changes", normalized_related)
        object.__setattr__(self, "reasons", tuple(self.reasons or ()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "selected_tests": [str(path) for path in self.selected_tests],
            "related_changes": {key: list(value) for key, value in self.related_changes.items()},
            "confidence": self.confidence,
            "requires_full_suite": self.requires_full_suite,
            "reasons": list(self.reasons),
            "metadata": dict(self.metadata or {}),
        }


def _select_from_changed_tests(change: Path, discovered: set[Path]) -> tuple[list[Path], float, list[str]]:
    if change in discovered:
        return [change], 1.0, ["direct_test_change"]
    return [], 0.0, []


def _select_for_change(change: Path, discovered: set[Path]) -> tuple[list[Path], float, list[str]]:
    if change.name == "__init__.py":
        direct = list(_candidate_test_paths(change, discovered))
        if direct:
            return direct, 0.75, ["package_init"]
        return [], 0.0, ["package_init_no_tests"]

    direct = list(_candidate_test_paths(change, discovered))
    if direct:
        if len(direct) == 1 and (change.stem in direct[0].name or direct[0].name == f"test_{change.stem}.py"):
            return direct, 0.9, ["direct_path_match"]
        return direct, 0.85, ["package_path_match"]

    change_tokens = set(_path_tokens(change))
    scored: list[tuple[float, Path, str]] = []
    for test_path in discovered:
        score, reason = _score_tokens(change, test_path)
        if score > 0.0:
            scored.append((score, test_path, reason or "token_match"))

    if not scored:
        return [], 0.0, ["no_related_tests"]

    scored.sort(key=lambda item: (-item[0], str(item[1])))
    best_score = scored[0][0]
    selected = [path for score, path, _ in scored if score == best_score]
    reasons = sorted({reason for score, _, reason in scored if score == best_score})
    if change_tokens:
        reasons.append("token_match")
    return selected, best_score, reasons


def select_affected_tests(context: ValidationContext) -> TestSelection:
    project_root = context.project_root.resolve(strict=False)
    discovered = set(discover_tests(project_root))
    changed_files = tuple(context.changed_files or ())

    selected_tests: list[Path] = []
    related_changes: dict[str, tuple[str, ...]] = {}
    reasons: list[str] = []
    package_scopes: set[str] = set()
    confidence_scores: list[float] = []
    python_changes: list[str] = []
    test_changes: list[str] = []

    for raw_change in changed_files:
        change = Path(str(raw_change))
        normalized = change
        if change.is_absolute():
            try:
                normalized = change.relative_to(project_root)
            except Exception:
                normalized = change
        key = str(normalized)
        if normalized.parts and normalized.parts[0] == "tests" and _is_test_filename(normalized.name):
            matched, score, change_reasons = _select_from_changed_tests(normalized, discovered)
            if matched:
                test_changes.append(key)
                related_changes[key] = tuple(str(path) for path in matched)
                confidence_scores.append(score)
                selected_tests.extend(matched)
                reasons.extend(change_reasons)
                package = _package_scope_for_change(normalized)
                if package is not None:
                    package_scopes.add(package)
            continue

        if not _is_python_file(normalized):
            continue

        python_changes.append(key)
        package = _package_scope_for_change(normalized)
        if package is not None:
            package_scopes.add(package)

        if _is_config_change(normalized):
            reasons.append("pytest_or_packaging_config_change")
            continue
        if _is_cross_cutting_change(normalized):
            reasons.append("cross_cutting_validation_change")
            continue

        matched, score, change_reasons = _select_for_change(normalized, discovered)
        if matched:
            related_changes[key] = tuple(str(path) for path in matched)
            confidence_scores.append(score)
            selected_tests.extend(matched)
            reasons.extend(change_reasons)
        else:
            reasons.append("no_related_tests")

    selected_unique = tuple(dict.fromkeys(sorted(selected_tests, key=str)))
    requires_full_suite = False
    full_suite_reasons: list[str] = []
    if any(_is_config_change(Path(change)) for change in changed_files if _is_python_file(Path(change)) or Path(change).suffix):
        requires_full_suite = True
        full_suite_reasons.append("pytest_or_packaging_config_change")
    if any(_is_cross_cutting_change(Path(change)) for change in changed_files if _is_python_file(Path(change))):
        requires_full_suite = True
        full_suite_reasons.append("cross_cutting_validation_change")
    if "kernel" in package_scopes:
        requires_full_suite = True
        full_suite_reasons.append("kernel_change")
    if len({scope for scope in package_scopes if scope is not None}) > 1:
        requires_full_suite = True
        full_suite_reasons.append("multiple_packages")
    if python_changes and not selected_unique and not requires_full_suite:
        requires_full_suite = True
        full_suite_reasons.append("empty_selection_python_changes")

    confidence = min(confidence_scores) if confidence_scores else 0.0
    if selected_unique and confidence < 0.7 and not requires_full_suite:
        requires_full_suite = True
        full_suite_reasons.append("low_confidence")

    metadata = {
        "strategy": "phase_7_4_basic_heuristics",
        "package_scopes": tuple(sorted(scope for scope in package_scopes if scope is not None)),
        "python_changes": tuple(python_changes),
        "test_changes": tuple(test_changes),
        "selected_count": len(selected_unique),
        "discovered_count": len(discovered),
    }
    if full_suite_reasons:
        reasons.extend(full_suite_reasons)
    if not changed_files:
        reasons.append("no_changed_files")
    if not python_changes and not test_changes:
        reasons.append("no_python_changes")

    return TestSelection(
        selected_tests=selected_unique,
        related_changes=related_changes,
        confidence=confidence,
        requires_full_suite=requires_full_suite,
        reasons=tuple(dict.fromkeys(reasons)),
        metadata=metadata,
    )
