from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from cmm.validation.security import default_command_policy, evaluate_command_policy


def _policy_findings(command: tuple[str, ...], tmp_path: Path, *, working_directory: Path | None = None, environment: dict[str, str] | None = None):
    return evaluate_command_policy(
        command=command,
        working_directory=working_directory,
        project_root=tmp_path,
        environment=environment or {},
        policy=default_command_policy(),
        security_profile="validation",
        step_name="security-check",
    )


@pytest.mark.parametrize(
    "command",
    [
        (sys.executable, "-m", "pytest", "-q"),
        (sys.executable, "-m", "ruff", "check"),
        (sys.executable, "-m", "mypy", "pkg"),
        (sys.executable, "-m", "vulture", "pkg"),
        (sys.executable, "-m", "bandit", "-f", "json", "pkg/module.py"),
        (sys.executable, "-m", "pip_audit", "-f", "json", "requirements.txt"),
        ("git", "diff", "--stat"),
    ],
)
def test_expected_commands_are_allowed(command: tuple[str, ...], tmp_path: Path) -> None:
    assert _policy_findings(command, tmp_path) == ()


def test_git_commit_is_rejected(tmp_path: Path) -> None:
    findings = _policy_findings(("git", "commit", "-m", "msg"), tmp_path)
    assert len(findings) == 1
    assert findings[0].code == "SECURITY_GIT_MUTATION"


def test_external_workdir_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    findings = _policy_findings((sys.executable, "-m", "pytest", "-q"), tmp_path, working_directory=outside)
    assert any(f.code == "SECURITY_WORKING_DIRECTORY_OUTSIDE_PROJECT" for f in findings)


def test_shell_operator_is_rejected(tmp_path: Path) -> None:
    findings = _policy_findings((sys.executable, "-m", "pytest", "&&", "echo", "boom"), tmp_path)
    assert any(f.code == "SECURITY_SHELL_OPERATOR" for f in findings)


def test_sensitive_environment_is_masked(tmp_path: Path) -> None:
    secret = "AKIA" + "A" * 16
    findings = _policy_findings(
        (sys.executable, "-m", "pytest", "-q"),
        tmp_path,
        environment={"AWS_SECRET_ACCESS_KEY": secret},
    )
    assert len(findings) == 1
    finding = findings[0]
    serialized = json.dumps([item.serialize() for item in findings], sort_keys=True)
    assert finding.code == "SECURITY_SENSITIVE_ENVIRONMENT"
    assert secret not in finding.message
    assert secret not in serialized
    assert "environment_keys" in finding.metadata
