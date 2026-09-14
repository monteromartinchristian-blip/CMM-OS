#!/usr/bin/env python3
"""Phase 10.48 remediation — baseline-aware Ruff/format no-regression verifier.

Compares whole-repository Ruff lint debt and format debt between a pinned
pre-10.48 baseline and the current working tree, and additionally requires every
Python file changed since that baseline to be fully Ruff- and format-clean.

The historical baseline is materialised with ``git archive`` into a temporary
directory. This script only reads Git history; it never mutates branches, the
index, the working tree, or stored history.

Reading this report truthfully:

* ``BASELINE_AWARE_GATE=PASS`` means the remediation added no new Ruff or format
  debt. It does not mean the whole repository is globally Ruff-clean.
* ``GLOBAL_RUFF`` / ``GLOBAL_FORMAT`` are reported as ``PASS`` only when the
  corresponding measured global debt is actually zero.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

BASELINE_HEAD = "35bf9d2b33c9e3c31ecd789c5d1237590eb31816"

_DEFAULT_REPO_PARENTS = 2


@dataclass(frozen=True)
class RuffDebtSnapshot:
    lint_violations: int
    format_files: int


@dataclass(frozen=True)
class GateDecision:
    changed_python_ruff_pass: bool
    changed_python_format_pass: bool
    no_new_ruff_regressions: bool
    no_new_format_regressions: bool

    @property
    def passed(self) -> bool:
        return all(
            (
                self.changed_python_ruff_pass,
                self.changed_python_format_pass,
                self.no_new_ruff_regressions,
                self.no_new_format_regressions,
            )
        )


def evaluate_gate(
    *,
    baseline: RuffDebtSnapshot,
    current: RuffDebtSnapshot,
    changed_lint_violations: int,
    changed_format_files: int,
) -> GateDecision:
    return GateDecision(
        changed_python_ruff_pass=changed_lint_violations == 0,
        changed_python_format_pass=changed_format_files == 0,
        no_new_ruff_regressions=current.lint_violations <= baseline.lint_violations,
        no_new_format_regressions=current.format_files <= baseline.format_files,
    )


# ── Subprocess plumbing ───────────────────────────────────────────────────────


def _run(
    args: list[str],
    *,
    cwd: Path,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        text=True,
        capture_output=True,
    )


def _default_repo() -> Path:
    return Path(__file__).resolve().parents[_DEFAULT_REPO_PARENTS]


# ── Baseline extraction (read-only Git history access) ────────────────────────


def _extract_baseline(repo: Path, destination: Path, baseline: str) -> None:
    _run(
        ["git", "rev-parse", "--verify", f"{baseline}^{{commit}}"],
        cwd=repo,
        check=True,
    )

    archive = subprocess.run(
        ["git", "archive", "--format=tar", baseline],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout

    with tarfile.open(fileobj=BytesIO(archive), mode="r:") as tar:
        tar.extractall(destination, filter="data")


# ── Ruff measurement ──────────────────────────────────────────────────────────


def _ruff_version(ruff_python: Path, repo: Path) -> str:
    return _run(
        [str(ruff_python), "-m", "ruff", "--version"],
        cwd=repo,
        check=True,
    ).stdout.strip()


def _ruff_lint_count(ruff_python: Path, root: Path) -> tuple[int, int]:
    proc = _run(
        [
            str(ruff_python),
            "-m",
            "ruff",
            "check",
            "--output-format",
            "json",
            ".",
        ],
        cwd=root,
    )
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"ruff check failed to execute in {root}: {proc.stdout}{proc.stderr}"
        )
    payload = json.loads(proc.stdout or "[]")
    return proc.returncode, len(payload)


def _baseline_python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _tracked_python_files(repo: Path) -> list[Path]:
    proc = _run(
        ["git", "ls-files", "--", "*.py"],
        cwd=repo,
        check=True,
    )
    return [
        repo / line
        for line in proc.stdout.splitlines()
        if line and (repo / line).is_file()
    ]


def _format_debt_count(
    ruff_python: Path,
    *,
    root: Path,
    files: list[Path],
) -> int:
    debt = 0
    for path in files:
        relative = path.relative_to(root)
        proc = _run(
            [
                str(ruff_python),
                "-m",
                "ruff",
                "format",
                "--check",
                str(relative),
            ],
            cwd=root,
        )
        if proc.returncode == 1:
            debt += 1
        elif proc.returncode != 0:
            raise RuntimeError(
                f"ruff format failed for {relative}: {proc.stdout}{proc.stderr}"
            )
    return debt


def _global_format_exit(ruff_python: Path, root: Path) -> int:
    proc = _run(
        [str(ruff_python), "-m", "ruff", "format", "--check", "."],
        cwd=root,
    )
    if proc.returncode not in (0, 1):
        raise RuntimeError(proc.stdout + proc.stderr)
    return proc.returncode


# ── Changed-Python discovery and checks ───────────────────────────────────────


def _changed_python_files(repo: Path, baseline: str) -> list[Path]:
    changed = _run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMRT",
            baseline,
            "--",
            "*.py",
        ],
        cwd=repo,
        check=True,
    ).stdout.splitlines()

    untracked = _run(
        [
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            "*.py",
        ],
        cwd=repo,
        check=True,
    ).stdout.splitlines()

    paths = {
        repo / name
        for name in (*changed, *untracked)
        if name and (repo / name).is_file()
    }
    return sorted(paths)


def _changed_lint_count(
    ruff_python: Path,
    *,
    repo: Path,
    files: list[Path],
) -> int:
    if not files:
        return 0

    args = [
        str(ruff_python),
        "-m",
        "ruff",
        "check",
        "--output-format",
        "json",
        *[str(path.relative_to(repo)) for path in files],
    ]
    proc = _run(args, cwd=repo)
    if proc.returncode not in (0, 1):
        raise RuntimeError(proc.stdout + proc.stderr)
    return len(json.loads(proc.stdout or "[]"))


# ── Evidence reporting ────────────────────────────────────────────────────────


def _pass_fail(value: bool) -> str:
    return "PASS" if value else "FAIL"


def _debt_state(current: int, baseline: int) -> str:
    return "PRESERVED_OR_REDUCED" if current <= baseline else "INCREASED"


def _emit_evidence(
    *,
    ruff_version: str,
    baseline_head: str,
    baseline_lint_exit: int,
    baseline_lint: int,
    current_lint_exit: int,
    current_lint: int,
    baseline_format_exit: int,
    baseline_format: int,
    current_format_exit: int,
    current_format: int,
    changed: list[Path],
    repo: Path,
    changed_lint: int,
    changed_format: int,
    decision: GateDecision,
) -> None:
    print(f"RUFF_VERSION={ruff_version}")
    print(f"BASELINE_HEAD={baseline_head}")
    print()
    print(f"GLOBAL_RUFF_BASELINE_EXIT={baseline_lint_exit}")
    print(f"GLOBAL_RUFF_BASELINE={baseline_lint}")
    print(f"GLOBAL_RUFF_CURRENT_EXIT={current_lint_exit}")
    print(f"GLOBAL_RUFF_CURRENT={current_lint}")
    print()
    print(f"GLOBAL_FORMAT_BASELINE_EXIT={baseline_format_exit}")
    print(f"GLOBAL_FORMAT_BASELINE={baseline_format}")
    print(f"GLOBAL_FORMAT_CURRENT_EXIT={current_format_exit}")
    print(f"GLOBAL_FORMAT_CURRENT={current_format}")
    print()
    print(f"CHANGED_PYTHON_FILES={len(changed)}")
    print(f"CHANGED_PYTHON_RUFF_VIOLATIONS={changed_lint}")
    print(f"CHANGED_PYTHON_FORMAT_FILES={changed_format}")
    print()
    print(f"CHANGED_PYTHON_RUFF={_pass_fail(decision.changed_python_ruff_pass)}")
    print(f"CHANGED_PYTHON_FORMAT={_pass_fail(decision.changed_python_format_pass)}")
    print(f"NO_NEW_RUFF_REGRESSIONS={_pass_fail(decision.no_new_ruff_regressions)}")
    print(f"NO_NEW_FORMAT_REGRESSIONS={_pass_fail(decision.no_new_format_regressions)}")
    print()
    print(f"LEGACY_RUFF_DEBT={_debt_state(current_lint, baseline_lint)}")
    print(f"LEGACY_FORMAT_DEBT={_debt_state(current_format, baseline_format)}")
    print()
    if current_lint == 0:
        print("GLOBAL_RUFF=PASS")
    else:
        print(f"GLOBAL_RUFF=DEBT_PRESENT ({current_lint} violations)")
    if current_format == 0:
        print("GLOBAL_FORMAT=PASS")
    else:
        print(f"GLOBAL_FORMAT=DEBT_PRESENT ({current_format} files)")
    print()
    print(f"BASELINE_AWARE_GATE={_pass_fail(decision.passed)}")
    print()
    print("CHANGED_PYTHON_PATHS_BEGIN")
    for path in changed:
        print(path.relative_to(repo))
    print("CHANGED_PYTHON_PATHS_END")


# ── Entry point ───────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify that Phase 10.48 changes introduced no new repository Ruff or "
            "format debt relative to a pinned baseline."
        )
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Git repository root (defaults to the repository containing this script).",
    )
    parser.add_argument(
        "--baseline",
        default=BASELINE_HEAD,
        help="Baseline commit used for the no-regression comparison.",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve() if args.repo else _default_repo()
    ruff_python = repo / ".venv" / "bin" / "python"
    if not ruff_python.exists():
        print(
            f"ERROR=missing virtualenv interpreter: {ruff_python}",
            file=sys.stderr,
        )
        return 2

    try:
        ruff_version = _ruff_version(ruff_python, repo)

        with tempfile.TemporaryDirectory(prefix="phase-10-48-baseline-") as tmp:
            baseline_root = Path(tmp)
            _extract_baseline(repo, baseline_root, args.baseline)

            baseline_lint_exit, baseline_lint = _ruff_lint_count(
                ruff_python, baseline_root
            )
            baseline_format_exit = _global_format_exit(ruff_python, baseline_root)
            baseline_format = _format_debt_count(
                ruff_python,
                root=baseline_root,
                files=_baseline_python_files(baseline_root),
            )

            current_lint_exit, current_lint = _ruff_lint_count(ruff_python, repo)
            current_format_exit = _global_format_exit(ruff_python, repo)
            current_format = _format_debt_count(
                ruff_python,
                root=repo,
                files=_tracked_python_files(repo),
            )

        changed = _changed_python_files(repo, args.baseline)
        changed_lint = _changed_lint_count(ruff_python, repo=repo, files=changed)
        changed_format = _format_debt_count(ruff_python, root=repo, files=changed)

        decision = evaluate_gate(
            baseline=RuffDebtSnapshot(
                lint_violations=baseline_lint,
                format_files=baseline_format,
            ),
            current=RuffDebtSnapshot(
                lint_violations=current_lint,
                format_files=current_format,
            ),
            changed_lint_violations=changed_lint,
            changed_format_files=changed_format,
        )

        _emit_evidence(
            ruff_version=ruff_version,
            baseline_head=args.baseline,
            baseline_lint_exit=baseline_lint_exit,
            baseline_lint=baseline_lint,
            current_lint_exit=current_lint_exit,
            current_lint=current_lint,
            baseline_format_exit=baseline_format_exit,
            baseline_format=baseline_format,
            current_format_exit=current_format_exit,
            current_format=current_format,
            changed=changed,
            repo=repo,
            changed_lint=changed_lint,
            changed_format=changed_format,
            decision=decision,
        )
    except (RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        return 2

    return 0 if decision.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
