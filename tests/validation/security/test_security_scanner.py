from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from cmm.validation import ValidationContext
from cmm.validation.catalog import change_impact_step
from cmm.validation.enums import ValidationStatus
from cmm.validation.security import SecurityValidator, security_step
from cmm.validation.steps import (
    ValidationStep,
    ValidationStepResult,
    ValidationStepType,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _security_result(
    tmp_path: Path,
) -> tuple[ValidationContext, ValidationStep, ValidationStepResult]:
    context = ValidationContext(
        project_root=tmp_path,
        changed_files=(
            Path("pkg/module.py"),
            Path("config/security.yaml"),
            Path("requirements.txt"),
            Path("secrets.txt"),
        ),
    )
    impact = change_impact_step(context)
    planned_steps = (
        ValidationStep(
            name="pytest",
            step_type=ValidationStepType.COMMAND,
            command=(sys.executable, "-m", "pytest", "-q"),
            metadata={"security_profile": "validation"},
            working_directory=tmp_path,
        ),
        ValidationStep(
            name="git_diff",
            step_type=ValidationStepType.COMMAND,
            command=("git", "diff", "--stat"),
            metadata={"security_profile": "validation"},
            working_directory=tmp_path,
        ),
    )
    step = security_step(
        context, change_impact_step=impact, planned_steps=planned_steps
    )
    result = SecurityValidator().validate(context, step)
    return context, step, result


def test_security_validator_detects_secrets_code_config_dependency_and_command_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "cmm.validation.security.validation._tool_available",
        lambda name: False if name == "pip_audit" else True,
    )
    _write(
        tmp_path / "pkg" / "module.py",
        """
import hashlib
import os
import pickle
import random
import subprocess
import tempfile

import requests
import yaml

API_KEY = "sk-" + "a" * 24
PASSWORD = "hardcoded-password"
JWT = "eyJ" + "a" * 10 + "." + "b" * 10 + "." + "c" * 10
DATABASE_URL = "postgres://user:pass@localhost/db"

def dangerous(query: str) -> None:
    eval(query)
    exec(query)
    os.system("echo hi")
    os.popen("echo hi")
    subprocess.run(["echo", "hi"], shell=True)
    pickle.loads(b"data")
    yaml.load("debug: true")
    tempfile.mktemp()
    random.random()
    hashlib.md5(b"payload").hexdigest()
    hashlib.sha1(b"payload").hexdigest()
    requests.get("https://example.invalid", verify=False)
    cursor.execute(f"SELECT * FROM users WHERE id = {1}")
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "config" / "security.yaml",
        """
debug: true
allowed_hosts: ["*"]
cors:
  allow_origin: "*"
tls: false
secrets:
  enabled: true
user: root
image: python:3.12
permissions:
  contents: write
run: curl https://example.invalid/install.sh | bash
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "requirements.txt",
        "requests @ git+https://github.com/example/project.git#egg=requests\n",
    )
    _write(
        tmp_path / "secrets.txt",
        "\n".join(
            [
                "sk-" + "a" * 24,
                "AKIA" + "A" * 16,
                "ghp_" + "b" * 24,
                "xoxb-" + "c" * 20,
                "AIza" + "d" * 35,
                "-----BEGIN PRIVATE KEY-----",
                "eyJ" + "e" * 10 + "." + "f" * 10 + "." + "g" * 10,
                "Bearer " + "h" * 32,
                "postgres://user:pass@localhost/db",
                "password='hardcoded-password'",
                "A1b2C3d4E5f6G7h8I9j0KLMNOPQRSTUV",
            ]
        )
        + "\n",
    )

    _, _, result = _security_result(tmp_path)

    assert result.status == ValidationStatus.FAILED
    kinds = {artifact.kind for artifact in result.artifacts}
    assert {
        "secret_scan_report",
        "code_security_report",
        "dependency_security_report",
        "command_security_report",
    }.issubset(kinds)

    codes = {finding.code for finding in result.findings}
    assert "SECURITY_SECRET_OPENAI_KEY" in codes
    assert "SECURITY_SECRET_AWS_KEY" in codes
    assert "SECURITY_SECRET_GITHUB_TOKEN" in codes
    assert "SECURITY_SECRET_SLACK_TOKEN" in codes
    assert "SECURITY_SECRET_GOOGLE_KEY" in codes
    assert "SECURITY_SECRET_PEM_PRIVATE_KEY" in codes
    assert "SECURITY_SECRET_JWT" in codes
    assert "SECURITY_SECRET_BEARER_TOKEN" in codes
    assert "SECURITY_SECRET_DATABASE_URL" in codes
    assert "SECURITY_SECRET_PASSWORD" in codes
    assert "SECURITY_HIGH_ENTROPY_SECRET" in codes
    assert "SECURITY_DANGEROUS_CALL" in codes
    assert "SECURITY_SHELL_TRUE" in codes
    assert "SECURITY_UNSAFE_PICKLE" in codes
    assert "SECURITY_UNSAFE_YAML_LOAD" in codes
    assert "SECURITY_UNSAFE_TEMPFILE" in codes
    assert "SECURITY_DYNAMIC_EXECUTION" in codes
    assert "SECURITY_INSECURE_RANDOM" in codes
    assert "SECURITY_WEAK_HASH" in codes
    assert "SECURITY_TLS_VERIFICATION_DISABLED" in codes
    assert "SECURITY_SQL_FSTRING" in codes
    assert "SECURITY_DEBUG_ENABLED" in codes
    assert "SECURITY_WILDCARD_HOST" in codes
    assert "SECURITY_WILDCARD_CORS" in codes
    assert "SECURITY_TLS_DISABLED" in codes
    assert "SECURITY_DOCKER_SECRET" in codes
    assert "SECURITY_ROOT_USER" in codes
    assert "SECURITY_UNPINNED_IMAGE" in codes
    assert "SECURITY_BROAD_GITHUB_PERMISSIONS" in codes
    assert "SECURITY_PIPE_TO_SHELL" in codes
    assert "DEPENDENCY_DIRECT_REFERENCE" in codes
    assert "DEPENDENCY_TOOL_UNAVAILABLE" in codes or any(
        f.code == "DEPENDENCY_TOOL_UNAVAILABLE" for f in result.findings
    )

    raw_snapshot = json.dumps(result.serialize(), sort_keys=True, default=str)
    for secret in [
        "sk-" + "a" * 24,
        "AKIA" + "A" * 16,
        "ghp_" + "b" * 24,
        "xoxb-" + "c" * 20,
        "AIza" + "d" * 35,
        "eyJ" + "e" * 10 + "." + "f" * 10 + "." + "g" * 10,
        "Bearer " + "h" * 32,
        "postgres://user:pass@localhost/db",
        "hardcoded-password",
    ]:
        assert secret not in raw_snapshot

    first_secret_finding = next(
        f for f in result.findings if f.code == "SECURITY_SECRET_OPENAI_KEY"
    )
    assert "sk-" not in first_secret_finding.message
    assert first_secret_finding.metadata.get("sample") == "sk-***"

    command_report = next(
        artifact
        for artifact in result.artifacts
        if artifact.kind == "command_security_report"
    )
    assert "pytest" in json.dumps(
        command_report.serialize(), sort_keys=True, default=str
    )
    assert "git_diff" in json.dumps(
        command_report.serialize(), sort_keys=True, default=str
    )


def test_security_validator_serialization_masks_secrets(tmp_path: Path) -> None:
    secret = "sk-aaaaaaaaaaaaaaaaaaaaaaaa"
    _write(tmp_path / "pkg" / "module.py", f"API_KEY = '{secret}'\n")
    context = ValidationContext(
        project_root=tmp_path, changed_files=(Path("pkg/module.py"),)
    )
    impact = change_impact_step(context)
    step = security_step(context, change_impact_step=impact)
    result = SecurityValidator().validate(context, step)

    payload = json.dumps(result.serialize(), sort_keys=True, default=str)
    assert secret not in payload
    assert "API_KEY" in payload


def test_security_validator_ignores_safe_config(tmp_path: Path) -> None:
    _write(
        tmp_path / "config" / "safe.yaml",
        """
debug: false
allowed_hosts:
  - localhost
tls: true
user: app
permissions:
  contents: read
""".strip()
        + "\n",
    )
    context = ValidationContext(
        project_root=tmp_path, changed_files=(Path("config/safe.yaml"),)
    )
    impact = change_impact_step(context)
    step = security_step(context, change_impact_step=impact)
    result = SecurityValidator().validate(context, step)

    noisy_codes = {
        "SECURITY_DEBUG_ENABLED",
        "SECURITY_WILDCARD_HOST",
        "SECURITY_WILDCARD_CORS",
        "SECURITY_TLS_DISABLED",
        "SECURITY_DOCKER_SECRET",
        "SECURITY_ROOT_USER",
        "SECURITY_UNPINNED_IMAGE",
        "SECURITY_BROAD_GITHUB_PERMISSIONS",
        "SECURITY_PIPE_TO_SHELL",
    }
    assert not any(finding.code in noisy_codes for finding in result.findings)
