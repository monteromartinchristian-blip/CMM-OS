from __future__ import annotations

import ast
import hashlib
import importlib.util
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.context import ValidationContext
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding
from cmm.validation.steps import ValidationStep, ValidationStepResult, ValidationStepType

from cmm.validation.impact.contracts import ChangeSet, ChangeType
from cmm.validation.impact.snapshots import ChangeSetBuilder

from .contracts import CommandPolicy, SecurityAnalysisPlan, SecurityScope, default_command_policy

_EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
}

_SUPPORTED_SECURITY_SUFFIXES = {
    ".py",
    ".toml",
    ".ini",
    ".cfg",
    ".yaml",
    ".yml",
    ".json",
    ".env",
    ".txt",
}

_SECRET_KEY_RE = re.compile(
    r"(?i)^(?:.*(?:API_KEY|SECRET_KEY|SECRET_ACCESS_KEY|ACCESS_KEY|ACCESS_TOKEN|AUTH_TOKEN|PRIVATE_KEY|CLIENT_SECRET|CLIENT_KEY|PASSWORD|PASSWD|TOKEN).*)$"
)
_TEXT_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)^\s*(?P<key>[A-Z0-9_]*?(?:API_KEY|SECRET_KEY|SECRET_ACCESS_KEY|ACCESS_KEY|ACCESS_TOKEN|AUTH_TOKEN|PRIVATE_KEY|CLIENT_SECRET|CLIENT_KEY|PASSWORD|PASSWD|TOKEN)[A-Z0-9_]*)\s*[:=]\s*(?P<value>.+?)\s*$"
)
_URL_RE = re.compile(r"(?i)\b(?:https?|ftp|ssh)://")
_DIRECT_DEP_RE = re.compile(r"(?i)@\s*(?:git\+|file:|https?://|ssh://)|^\s*(?:-e|--editable)\b")


def build_security_plan(
    *,
    project_root: Path,
    change_set: ChangeSet,
    command_policy: CommandPolicy | None = None,
    planned_steps: Sequence[ValidationStep] = (),
) -> SecurityAnalysisPlan:
    root = Path(project_root).resolve(strict=False)
    scope, reason = _resolve_scope(change_set)
    files = _select_files(root, change_set, scope)
    if not files:
        reason = f"{reason}:no_security_files" if reason else "no_security_files"
    safe_steps = tuple(step.serialize() for step in planned_steps)
    return SecurityAnalysisPlan(
        project_root=root,
        scope=scope,
        complete=True,
        reason=reason,
        files=tuple(files),
        change_type=change_set.change_type.value,
        public_api_changed=bool(change_set.public_api_changes),
        requires_full_suite=change_set.requires_full_suite,
        confidence=change_set.confidence,
        uncertainty=change_set.uncertainty,
        command_policy=command_policy or default_command_policy(),
        planned_steps=safe_steps,
        metadata={
            "change_set_summary": _summarize_change_set(change_set),
            "change_type": change_set.change_type.value,
            "files_selected": len(files),
            "planned_step_count": len(safe_steps),
        },
    )


def security_step(
    context: ValidationContext,
    *,
    change_impact_step: ValidationStep | None = None,
    planned_steps: Sequence[ValidationStep] = (),
    command_policy: CommandPolicy | None = None,
) -> ValidationStep:
    change_set = _load_change_set(context, change_impact_step)
    plan = build_security_plan(
        project_root=context.project_root,
        change_set=change_set,
        command_policy=command_policy or _load_command_policy(context, change_impact_step),
        planned_steps=planned_steps,
    )
    return ValidationStep(
        name="security",
        step_type=ValidationStepType.INTERNAL,
        required=True,
        timeout_seconds=120,
        stop_on_failure=True,
        dependencies=("change_impact",),
        metadata={
            "validator": "security",
            "security_plan": plan.serialize(),
            "change_set_summary": _summarize_change_set(change_set),
            "command_policy": plan.command_policy.serialize(),
        },
    )


def default_security_steps(
    context: ValidationContext,
    *,
    change_impact_step: ValidationStep | None = None,
    planned_steps: Sequence[ValidationStep] = (),
) -> tuple[ValidationStep, ...]:
    return (
        security_step(
            context,
            change_impact_step=change_impact_step,
            planned_steps=planned_steps,
        ),
    )


def bandit_step(
    context: ValidationContext,
    *,
    change_impact_step: ValidationStep | None = None,
) -> ValidationStep | None:
    if not _tool_available("bandit"):
        return None
    change_set = _load_change_set(context, change_impact_step)
    plan = build_security_plan(project_root=context.project_root, change_set=change_set)
    files = [str(path) for path in plan.files if str(path).endswith(".py")]
    command = (sys.executable, "-m", "bandit", "-f", "json", *files)
    return ValidationStep(
        name="bandit",
        step_type=ValidationStepType.COMMAND,
        command=command,
        required=False,
        timeout_seconds=300,
        stop_on_failure=False,
        allowed_exit_codes=(0, 1),
        working_directory=context.project_root,
        dependencies=("change_impact",),
        metadata={
            "result_parser": "bandit",
            "tool": "bandit",
            "security_profile": "validation",
            "command_policy": default_command_policy().serialize(),
            "scope": files or None,
            "analysis_plan": plan.serialize(),
        },
    )


def pip_audit_step(
    context: ValidationContext,
    *,
    change_impact_step: ValidationStep | None = None,
) -> ValidationStep | None:
    if not _tool_available("pip_audit"):
        return None
    change_set = _load_change_set(context, change_impact_step)
    plan = build_security_plan(project_root=context.project_root, change_set=change_set)
    dependency_files = [str(path) for path in plan.files if _is_dependency_manifest(path)]
    command = (sys.executable, "-m", "pip_audit", "-f", "json", *dependency_files)
    return ValidationStep(
        name="pip_audit",
        step_type=ValidationStepType.COMMAND,
        command=command,
        required=False,
        timeout_seconds=300,
        stop_on_failure=False,
        allowed_exit_codes=(0, 1),
        working_directory=context.project_root,
        dependencies=("change_impact",),
        metadata={
            "result_parser": "pip_audit",
            "tool": "pip-audit",
            "security_profile": "validation",
            "command_policy": default_command_policy().serialize(),
            "scope": dependency_files or None,
            "analysis_plan": plan.serialize(),
        },
    )


def evaluate_command_policy(
    *,
    command: Sequence[str],
    working_directory: Path | None,
    project_root: Path,
    environment: Mapping[str, str],
    policy: CommandPolicy,
    security_profile: str | None = None,
    step_name: str = "unknown",
) -> tuple[ValidationFinding, ...]:
    if security_profile != "validation":
        return ()

    findings: list[ValidationFinding] = []
    command_tuple = tuple(str(item) for item in command if item is not None)
    if not command_tuple:
        findings.append(
            ValidationFinding(
                code="SECURITY_EMPTY_COMMAND",
                message=f"Validation step '{step_name}' did not declare a command.",
                severity=ValidationSeverity.ERROR,
                source="validation.security",
                blocking=True,
                metadata={"step_name": step_name},
            )
        )
        return tuple(findings)

    executable = command_tuple[0]
    if not policy.allows_executable(executable):
        findings.append(
            ValidationFinding(
                code="SECURITY_EXECUTABLE_NOT_ALLOWED",
                message=f"Executable '{Path(executable).name}' is not allowed by the command policy.",
                severity=ValidationSeverity.ERROR,
                source="validation.security",
                blocking=True,
                metadata={"step_name": step_name, "executable": Path(executable).name},
            )
        )

    if any(arg in policy.forbidden_arguments for arg in command_tuple[1:]):
        forbidden = [arg for arg in command_tuple[1:] if arg in policy.forbidden_arguments]
        findings.append(
            ValidationFinding(
                code="SECURITY_FORBIDDEN_ARGUMENT",
                message=f"Validation step '{step_name}' uses forbidden argument(s).",
                severity=ValidationSeverity.ERROR,
                source="validation.security",
                blocking=True,
                metadata={"step_name": step_name, "forbidden_arguments": forbidden},
            )
        )

    shell_tokens = _shell_operator_tokens(command_tuple[1:])
    if shell_tokens:
        findings.append(
            ValidationFinding(
                code="SECURITY_SHELL_OPERATOR",
                message=f"Validation step '{step_name}' uses shell operator tokens.",
                severity=ValidationSeverity.ERROR,
                source="validation.security",
                blocking=True,
                metadata={"step_name": step_name, "operators": list(shell_tokens)},
            )
        )

    if _is_python_executable(executable):
        module_name = _python_module_name(command_tuple)
        if module_name is not None and not _matches_any(module_name, policy.allowed_executables):
            findings.append(
                ValidationFinding(
                    code="SECURITY_PYTHON_MODULE_NOT_ALLOWED",
                    message=f"Python module '{module_name}' is not allowed by the command policy.",
                    severity=ValidationSeverity.ERROR,
                    source="validation.security",
                    blocking=True,
                    metadata={"step_name": step_name, "module": module_name},
                )
            )
        elif module_name is None:
            script_argument = _python_script_argument(command_tuple)
            if script_argument is not None:
                script_path = Path(script_argument)
                if not _python_script_allowed(Path(project_root), script_path):
                    findings.append(
                        ValidationFinding(
                            code="SECURITY_SCRIPT_OUTSIDE_PROJECT",
                            message=f"Validation step '{step_name}' would execute a Python script outside the project root.",
                            severity=ValidationSeverity.ERROR,
                            source="validation.security",
                            blocking=True,
                            metadata={"step_name": step_name, "script": str(script_path)},
                        )
                    )

    if Path(executable).name == "git":
        git_subcommand = _git_subcommand(command_tuple)
        if git_subcommand not in _READ_ONLY_GIT_SUBCOMMANDS:
            findings.append(
                ValidationFinding(
                    code="SECURITY_GIT_MUTATION",
                    message=f"Validation step '{step_name}' uses forbidden git subcommand '{git_subcommand or 'unknown'}'.",
                    severity=ValidationSeverity.ERROR,
                    source="validation.security",
                    blocking=True,
                    metadata={"step_name": step_name, "subcommand": git_subcommand},
                )
            )

    if working_directory is not None:
        cwd = Path(working_directory).resolve(strict=False)
        if not _working_directory_allowed(cwd, Path(project_root).resolve(strict=False), policy):
            findings.append(
                ValidationFinding(
                    code="SECURITY_WORKING_DIRECTORY_OUTSIDE_PROJECT",
                    message=f"Validation step '{step_name}' would run outside the project root.",
                    severity=ValidationSeverity.ERROR,
                    source="validation.security",
                    blocking=True,
                    metadata={
                        "step_name": step_name,
                        "working_directory": str(cwd),
                        "project_root": str(Path(project_root).resolve(strict=False)),
                    },
                )
            )

    if not policy.allow_network and any(_URL_RE.search(arg) for arg in command_tuple[1:]):
        findings.append(
            ValidationFinding(
                code="SECURITY_NETWORK_ARGUMENT",
                message=f"Validation step '{step_name}' includes a network URL argument while network access is disabled.",
                severity=ValidationSeverity.ERROR,
                source="validation.security",
                blocking=True,
                metadata={"step_name": step_name},
            )
        )

    sensitive_env = [
        key
        for key, value in environment.items()
        if _looks_sensitive_env_key(key) and bool(str(value).strip())
    ]
    if sensitive_env:
        findings.append(
            ValidationFinding(
                code="SECURITY_SENSITIVE_ENVIRONMENT",
                message=f"Validation step '{step_name}' declares sensitive environment variables.",
                severity=ValidationSeverity.ERROR,
                source="validation.security",
                blocking=True,
                metadata={"step_name": step_name, "environment_keys": sorted(sensitive_env)},
            )
        )

    return tuple(findings)


class SecurityValidator:
    def validate(self, context: ValidationContext, step: ValidationStep) -> ValidationStepResult:
        plan = self._load_plan(context, step.metadata)
        secret_findings, secret_artifact = _scan_secret_files(plan)
        code_findings, code_artifact = _scan_code_files(plan)
        dependency_findings, dependency_artifact = _scan_dependency_security(plan)
        command_findings, command_artifact = _scan_command_policy(plan)

        findings = _dedupe_findings((*secret_findings, *code_findings, *dependency_findings, *command_findings))
        artifacts = tuple(
            artifact
            for artifact in (secret_artifact, code_artifact, dependency_artifact, command_artifact)
            if artifact is not None
        )

        if any(f.blocking for f in findings):
            status = ValidationStatus.FAILED
        elif any(f.severity == ValidationSeverity.WARNING for f in findings):
            status = ValidationStatus.WARNING
        else:
            status = ValidationStatus.PASSED

        return ValidationStepResult(
            name=step.name,
            status=status,
            duration_ms=0,
            stdout="",
            stderr="",
            findings=findings,
            artifacts=artifacts,
            metadata={
                "security_plan": plan.serialize(),
                "finding_count": len(findings),
                "blocking_count": sum(1 for finding in findings if finding.blocking),
                "warning_count": sum(1 for finding in findings if finding.severity == ValidationSeverity.WARNING),
                "source_file_count": len(plan.files),
                "planned_step_count": len(plan.planned_steps),
                "command_policy": plan.command_policy.serialize(),
            },
        )

    def _load_plan(self, context: ValidationContext, metadata: Mapping[str, Any]) -> SecurityAnalysisPlan:
        payload = metadata.get("security_plan")
        if isinstance(payload, Mapping):
            return SecurityAnalysisPlan.from_mapping(payload)
        change_set_payload = metadata.get("change_set")
        if isinstance(change_set_payload, Mapping):
            change_set = ChangeSet.from_mapping(change_set_payload)
        else:
            builder = ChangeSetBuilder()
            change_set = builder.build(project_root=context.project_root, changed_files=context.changed_files)
        policy_payload = metadata.get("command_policy")
        policy = CommandPolicy.from_mapping(policy_payload) if isinstance(policy_payload, Mapping) else default_command_policy()
        return build_security_plan(
            project_root=context.project_root,
            change_set=change_set,
            command_policy=policy,
            planned_steps=(),
        )


def _scan_command_policy(plan: SecurityAnalysisPlan) -> tuple[tuple[ValidationFinding, ...], ValidationArtifact | None]:
    findings: list[ValidationFinding] = []
    summaries: list[dict[str, Any]] = []
    for step in plan.planned_steps:
        if str(step.get("name", "")) == "security":
            continue
        if str(step.get("step_type", "command")) != ValidationStepType.COMMAND.value:
            continue
        command = tuple(str(item) for item in (step.get("command") or ()) if item is not None)
        working_directory = step.get("working_directory")
        environment = step.get("environment")
        env_map = environment if isinstance(environment, Mapping) else {}
        environment_keys = step.get("environment_keys")
        if not env_map and isinstance(environment_keys, (list, tuple)):
            env_map = {str(key): "" for key in environment_keys}
        step_findings = evaluate_command_policy(
            command=command,
            working_directory=Path(str(working_directory)) if working_directory else None,
            project_root=plan.project_root,
            environment={str(key): str(value) for key, value in env_map.items()},
            policy=plan.command_policy,
            security_profile=str(step.get("metadata", {}).get("security_profile")) if isinstance(step.get("metadata"), Mapping) else None,
            step_name=str(step.get("name", "unknown")),
        )
        findings.extend(step_findings)
        summaries.append(
            {
                "name": str(step.get("name", "")),
                "step_type": str(step.get("step_type", "")),
                "executable": Path(command[0]).name if command else None,
                "command_length": len(command),
                "working_directory": None if working_directory is None else str(working_directory),
                "violation_codes": [finding.code for finding in step_findings],
            }
        )
    artifact = ValidationArtifact(
        id="security-command-policy",
        kind="command_security_report",
        source="validation.security",
        content={
            "command_policy": plan.command_policy.serialize(),
            "planned_steps": summaries,
            "metrics": {
                "planned_command_steps": len(summaries),
                "violation_count": len(findings),
            },
        },
        findings=tuple(findings),
        metrics={
            "planned_command_steps": len(summaries),
            "violation_count": len(findings),
        },
    )
    return tuple(findings), artifact


def _scan_secret_files(plan: SecurityAnalysisPlan) -> tuple[tuple[ValidationFinding, ...], ValidationArtifact | None]:
    findings: list[ValidationFinding] = []
    files: list[str] = []
    for path in plan.files:
        resolved = plan.project_root / path if not path.is_absolute() else path
        if not resolved.exists() or not resolved.is_file() or resolved.is_symlink():
            continue
        text = resolved.read_text(encoding="utf-8", errors="replace")
        file_findings = _scan_secret_text(text, path)
        if file_findings:
            files.append(str(path))
        findings.extend(file_findings)
    artifact = ValidationArtifact(
        id="security-secret-scan",
        kind="secret_scan_report",
        source="validation.security",
        content={
            "files": files,
            "diagnostics": [finding.serialize() for finding in findings],
            "metrics": {
                "file_count": len(files),
                "finding_count": len(findings),
            },
        },
        findings=tuple(findings),
        metrics={
            "file_count": len(files),
            "finding_count": len(findings),
        },
    )
    return tuple(findings), artifact


def _scan_code_files(plan: SecurityAnalysisPlan) -> tuple[tuple[ValidationFinding, ...], ValidationArtifact | None]:
    findings: list[ValidationFinding] = []
    scanned_files: list[str] = []
    for path in plan.files:
        resolved = plan.project_root / path if not path.is_absolute() else path
        if not resolved.exists() or not resolved.is_file() or resolved.is_symlink():
            continue
        scanned_files.append(str(path))
        if resolved.suffix == ".py":
            findings.extend(_scan_python_file(path, resolved))
        else:
            findings.extend(_scan_configuration_text(path, resolved))
    artifact = ValidationArtifact(
        id="security-code-scan",
        kind="code_security_report",
        source="validation.security",
        content={
            "files": scanned_files,
            "diagnostics": [finding.serialize() for finding in findings],
            "metrics": {
                "file_count": len(scanned_files),
                "finding_count": len(findings),
            },
        },
        findings=tuple(findings),
        metrics={
            "file_count": len(scanned_files),
            "finding_count": len(findings),
        },
    )
    return tuple(findings), artifact


def _scan_dependency_security(plan: SecurityAnalysisPlan) -> tuple[tuple[ValidationFinding, ...], ValidationArtifact | None]:
    findings: list[ValidationFinding] = []
    manifests: list[str] = []
    tool_status = {
        "bandit": _tool_available("bandit"),
        "pip_audit": _tool_available("pip_audit"),
    }
    if not tool_status["pip_audit"]:
        findings.append(
            ValidationFinding(
                code="DEPENDENCY_TOOL_UNAVAILABLE",
                message="pip-audit is not available in the current environment.",
                severity=ValidationSeverity.WARNING,
                source="validation.security",
                blocking=False,
                metadata={"tool": "pip-audit"},
            )
        )
    for path in plan.files:
        if not _is_dependency_manifest(path):
            continue
        resolved = plan.project_root / path if not path.is_absolute() else path
        if not resolved.exists() or not resolved.is_file():
            continue
        manifests.append(str(path))
        text = resolved.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not _DIRECT_DEP_RE.search(line):
                continue
            findings.append(
                ValidationFinding(
                    code="DEPENDENCY_DIRECT_REFERENCE",
                    message=f"Dependency manifest '{path}' contains a direct or editable dependency reference.",
                    severity=ValidationSeverity.WARNING,
                    source="validation.security",
                    file_path=path,
                    line=line_no,
                    blocking=False,
                    metadata={"manifest": str(path), "pattern": "direct_reference"},
                )
            )
    artifact = ValidationArtifact(
        id="security-dependency-scan",
        kind="dependency_security_report",
        source="validation.security",
        content={
            "manifests": manifests,
            "tool_status": tool_status,
            "diagnostics": [finding.serialize() for finding in findings],
            "metrics": {
                "manifest_count": len(manifests),
                "finding_count": len(findings),
            },
        },
        findings=tuple(findings),
        metrics={
            "manifest_count": len(manifests),
            "finding_count": len(findings),
        },
    )
    return tuple(findings), artifact


def _scan_secret_text(text: str, relative_path: Path) -> tuple[ValidationFinding, ...]:
    findings: list[ValidationFinding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for detector in _SECRET_DETECTORS:
            for match in detector["pattern"].finditer(line):
                secret = match.group(0)
                if detector["name"] == "generic_high_entropy" and not _looks_high_entropy(secret):
                    continue
                findings.append(
                    ValidationFinding(
                        code=detector["code"],
                        message=detector["message"],
                        severity=ValidationSeverity.ERROR,
                        source="validation.security",
                        file_path=relative_path,
                        line=line_no,
                        blocking=True,
                        metadata={
                            "pattern": detector["name"],
                            "fingerprint": _fingerprint(secret),
                            "length": len(secret),
                            "sample": detector["sample"],
                        },
                    )
                )
    return tuple(_dedupe_findings(findings))


def _scan_python_file(relative_path: Path, resolved: Path) -> tuple[ValidationFinding, ...]:
    text = resolved.read_text(encoding="utf-8", errors="replace")
    findings: list[ValidationFinding] = []
    try:
        tree = ast.parse(text, filename=str(resolved))
    except SyntaxError:
        return tuple(findings)

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> Any:  # type: ignore[override]
            dotted = _dotted_name(node.func)
            if dotted in {"os.system", "os.popen"}:
                findings.append(
                    ValidationFinding(
                        code="SECURITY_DANGEROUS_CALL",
                        message=f"Python code calls '{dotted}', which is not allowed in validation code.",
                        severity=ValidationSeverity.ERROR,
                        source="validation.security",
                        file_path=relative_path,
                        line=node.lineno,
                        column=node.col_offset + 1,
                        blocking=True,
                        metadata={"call": dotted},
                    )
                )
            if dotted.startswith("subprocess.") and any(_keyword_is_true(keyword, "shell") for keyword in node.keywords):
                findings.append(
                    ValidationFinding(
                        code="SECURITY_SHELL_TRUE",
                        message="Python code invokes subprocess with shell=True.",
                        severity=ValidationSeverity.ERROR,
                        source="validation.security",
                        file_path=relative_path,
                        line=node.lineno,
                        column=node.col_offset + 1,
                        blocking=True,
                        metadata={"call": dotted},
                    )
                )
            if dotted in {"pickle.loads", "pickle.load"}:
                findings.append(
                    ValidationFinding(
                        code="SECURITY_UNSAFE_PICKLE",
                        message="Python code uses pickle loading APIs.",
                        severity=ValidationSeverity.ERROR,
                        source="validation.security",
                        file_path=relative_path,
                        line=node.lineno,
                        column=node.col_offset + 1,
                        blocking=True,
                        metadata={"call": dotted},
                    )
                )
            if dotted == "yaml.load":
                findings.append(
                    ValidationFinding(
                        code="SECURITY_UNSAFE_YAML_LOAD",
                        message="Python code uses yaml.load without a safe loader.",
                        severity=ValidationSeverity.ERROR,
                        source="validation.security",
                        file_path=relative_path,
                        line=node.lineno,
                        column=node.col_offset + 1,
                        blocking=True,
                        metadata={"call": dotted},
                    )
                )
            if dotted == "tempfile.mktemp":
                findings.append(
                    ValidationFinding(
                        code="SECURITY_UNSAFE_TEMPFILE",
                        message="Python code uses tempfile.mktemp.",
                        severity=ValidationSeverity.ERROR,
                        source="validation.security",
                        file_path=relative_path,
                        line=node.lineno,
                        column=node.col_offset + 1,
                        blocking=True,
                        metadata={"call": dotted},
                    )
                )
            if dotted in {"eval", "exec"}:
                findings.append(
                    ValidationFinding(
                        code="SECURITY_DYNAMIC_EXECUTION",
                        message=f"Python code invokes '{dotted}', which is not allowed in validation code.",
                        severity=ValidationSeverity.ERROR,
                        source="validation.security",
                        file_path=relative_path,
                        line=node.lineno,
                        column=node.col_offset + 1,
                        blocking=True,
                        metadata={"call": dotted},
                    )
                )
            if dotted == "random.random":
                findings.append(
                    ValidationFinding(
                        code="SECURITY_INSECURE_RANDOM",
                        message="Python code uses random.random in a security-sensitive context.",
                        severity=ValidationSeverity.WARNING,
                        source="validation.security",
                        file_path=relative_path,
                        line=node.lineno,
                        column=node.col_offset + 1,
                        blocking=False,
                        metadata={"call": dotted},
                    )
                )
            if dotted in {"hashlib.md5", "hashlib.sha1"}:
                findings.append(
                    ValidationFinding(
                        code="SECURITY_WEAK_HASH",
                        message=f"Python code uses weak hash function '{dotted}'.",
                        severity=ValidationSeverity.WARNING,
                        source="validation.security",
                        file_path=relative_path,
                        line=node.lineno,
                        column=node.col_offset + 1,
                        blocking=False,
                        metadata={"call": dotted},
                    )
                )
            if dotted.startswith("requests.") and any(_keyword_is_false(keyword, "verify") for keyword in node.keywords):
                findings.append(
                    ValidationFinding(
                        code="SECURITY_TLS_VERIFICATION_DISABLED",
                        message="Python code disables TLS verification for an HTTP request.",
                        severity=ValidationSeverity.WARNING,
                        source="validation.security",
                        file_path=relative_path,
                        line=node.lineno,
                        column=node.col_offset + 1,
                        blocking=False,
                        metadata={"call": dotted},
                    )
                )
            self.generic_visit(node)

        def visit_JoinedStr(self, node: ast.JoinedStr) -> Any:  # type: ignore[override]
            if _looks_sql_fstring(node):
                findings.append(
                    ValidationFinding(
                        code="SECURITY_SQL_FSTRING",
                        message="Python code builds SQL using an f-string.",
                        severity=ValidationSeverity.ERROR,
                        source="validation.security",
                        file_path=relative_path,
                        line=node.lineno,
                        column=node.col_offset + 1,
                        blocking=True,
                        metadata={"node": "JoinedStr"},
                    )
                )
            self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> Any:  # type: ignore[override]
            self._scan_secret_assignment(node.targets, node.value, node)
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:  # type: ignore[override]
            targets = [node.target] if node.target is not None else []
            self._scan_secret_assignment(targets, node.value, node)
            self.generic_visit(node)

        def _scan_secret_assignment(self, targets: Sequence[ast.AST], value: ast.AST | None, node: ast.AST) -> None:
            if value is None:
                return
            if not isinstance(value, ast.Constant) or not isinstance(value.value, (str, bytes)):
                return
            for target in targets:
                identifier = _assignment_name(target)
                if identifier is None:
                    continue
                if not _looks_sensitive_name(identifier):
                    continue
                findings.append(
                    ValidationFinding(
                        code="SECURITY_SECRET_LITERAL",
                        message=f"Python code assigns a literal to sensitive name '{identifier}'.",
                        severity=ValidationSeverity.ERROR,
                        source="validation.security",
                        file_path=relative_path,
                        line=getattr(node, "lineno", None),
                        column=getattr(node, "col_offset", None) + 1 if getattr(node, "col_offset", None) is not None else None,
                        blocking=True,
                        metadata={"name": identifier, "value_length": len(value.value) if isinstance(value.value, (str, bytes)) else None, "fingerprint": _fingerprint(value.value if isinstance(value.value, str) else str(value.value))},
                    )
                )

    Visitor().visit(tree)
    return tuple(findings)


def _scan_configuration_text(relative_path: Path, resolved: Path) -> tuple[ValidationFinding, ...]:
    text = resolved.read_text(encoding="utf-8", errors="replace")
    findings: list[ValidationFinding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        lower = line.lower()
        if _looks_debug_enabled(lower):
            findings.append(
                ValidationFinding(
                    code="SECURITY_DEBUG_ENABLED",
                    message=f"Configuration file '{relative_path}' enables debug logging.",
                    severity=ValidationSeverity.WARNING,
                    source="validation.security",
                    file_path=relative_path,
                    line=line_no,
                    blocking=False,
                    metadata={"pattern": "debug_true"},
                )
            )
        if _looks_wildcard_host(lower):
            findings.append(
                ValidationFinding(
                    code="SECURITY_WILDCARD_HOST",
                    message=f"Configuration file '{relative_path}' allows a wildcard host.",
                    severity=ValidationSeverity.ERROR,
                    source="validation.security",
                    file_path=relative_path,
                    line=line_no,
                    blocking=True,
                    metadata={"pattern": "wildcard_host"},
                )
            )
        if _looks_wildcard_cors(lower):
            findings.append(
                ValidationFinding(
                    code="SECURITY_WILDCARD_CORS",
                    message=f"Configuration file '{relative_path}' allows wildcard CORS.",
                    severity=ValidationSeverity.ERROR,
                    source="validation.security",
                    file_path=relative_path,
                    line=line_no,
                    blocking=True,
                    metadata={"pattern": "wildcard_cors"},
                )
            )
        if _looks_tls_disabled(lower):
            findings.append(
                ValidationFinding(
                    code="SECURITY_TLS_DISABLED",
                    message=f"Configuration file '{relative_path}' disables TLS verification.",
                    severity=ValidationSeverity.ERROR,
                    source="validation.security",
                    file_path=relative_path,
                    line=line_no,
                    blocking=True,
                    metadata={"pattern": "tls_disabled"},
                )
            )
        if "shell: true" in lower or "shell=true" in lower:
            findings.append(
                ValidationFinding(
                    code="SECURITY_SHELL_CONFIGURATION",
                    message=f"Configuration file '{relative_path}' enables shell execution.",
                    severity=ValidationSeverity.ERROR,
                    source="validation.security",
                    file_path=relative_path,
                    line=line_no,
                    blocking=True,
                    metadata={"pattern": "shell_true"},
                )
            )
        if _looks_docker_secret(lower):
            findings.append(
                ValidationFinding(
                    code="SECURITY_DOCKER_SECRET",
                    message=f"Configuration file '{relative_path}' references a Docker secret.",
                    severity=ValidationSeverity.WARNING,
                    source="validation.security",
                    file_path=relative_path,
                    line=line_no,
                    blocking=False,
                    metadata={"pattern": "docker_secret"},
                )
            )
        if _looks_root_user(lower):
            findings.append(
                ValidationFinding(
                    code="SECURITY_ROOT_USER",
                    message=f"Configuration file '{relative_path}' runs as root.",
                    severity=ValidationSeverity.ERROR,
                    source="validation.security",
                    file_path=relative_path,
                    line=line_no,
                    blocking=True,
                    metadata={"pattern": "root_user"},
                )
            )
        if _looks_unpinned_image(lower):
            findings.append(
                ValidationFinding(
                    code="SECURITY_UNPINNED_IMAGE",
                    message=f"Configuration file '{relative_path}' uses an unpinned image reference.",
                    severity=ValidationSeverity.WARNING,
                    source="validation.security",
                    file_path=relative_path,
                    line=line_no,
                    blocking=False,
                    metadata={"pattern": "unpinned_image"},
                )
            )
        if _looks_broad_github_permissions(lower):
            findings.append(
                ValidationFinding(
                    code="SECURITY_BROAD_GITHUB_PERMISSIONS",
                    message=f"Configuration file '{relative_path}' grants broad GitHub permissions.",
                    severity=ValidationSeverity.ERROR,
                    source="validation.security",
                    file_path=relative_path,
                    line=line_no,
                    blocking=True,
                    metadata={"pattern": "broad_permissions"},
                )
            )
        if "curl " in lower and "|" in line and (" bash" in lower or " sh" in lower):
            findings.append(
                ValidationFinding(
                    code="SECURITY_PIPE_TO_SHELL",
                    message=f"Configuration file '{relative_path}' pipes a download into a shell.",
                    severity=ValidationSeverity.ERROR,
                    source="validation.security",
                    file_path=relative_path,
                    line=line_no,
                    blocking=True,
                    metadata={"pattern": "pipe_to_shell"},
                )
            )
    return tuple(findings)


def _load_change_set(context: ValidationContext, change_impact_step: ValidationStep | None) -> ChangeSet:
    if change_impact_step is not None:
        payload = change_impact_step.metadata.get("change_set")
        if isinstance(payload, Mapping):
            return ChangeSet.from_mapping(payload)
    builder = ChangeSetBuilder()
    return builder.build(project_root=context.project_root, changed_files=context.changed_files)


def _tool_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _load_command_policy(context: ValidationContext, change_impact_step: ValidationStep | None) -> CommandPolicy:
    for candidate in (
        context.metadata.get("command_policy"),
        None if change_impact_step is None else change_impact_step.metadata.get("command_policy"),
    ):
        if isinstance(candidate, Mapping):
            return CommandPolicy.from_mapping(candidate)
    return default_command_policy()


def _summarize_change_set(change_set: ChangeSet) -> dict[str, Any]:
    return {
        "change_type": change_set.change_type.value,
        "confidence": change_set.confidence,
        "requires_full_suite": change_set.requires_full_suite,
        "public_api_changed": bool(change_set.public_api_changes),
        "file_count": len(change_set.file_changes),
        "changed_files": [str(path) for path in change_set.changed_files],
        "uncertainty": list(change_set.uncertainty),
    }


def _resolve_scope(change_set: ChangeSet) -> tuple[SecurityScope, str]:
    if change_set.change_type == ChangeType.PUBLIC_API_CHANGE or change_set.public_api_changes:
        return SecurityScope.FULL, "public_api_change"
    if change_set.requires_full_suite:
        return SecurityScope.FULL, "requires_full_suite"
    if change_set.uncertainty:
        return SecurityScope.FULL, "uncertainty"
    if change_set.confidence < 0.7:
        return SecurityScope.FULL, "low_confidence"
    return SecurityScope.AFFECTED, "affected_scope"


def _select_files(project_root: Path, change_set: ChangeSet, scope: SecurityScope) -> list[Path]:
    if scope == SecurityScope.FULL:
        return _collect_full_scope_files(project_root)

    selected: list[Path] = []
    seen: set[Path] = set()
    for file_change in change_set.file_changes:
        candidate = file_change.after_path or file_change.before_path
        if candidate is None or not _supported_security_file(candidate):
            continue
        rel_path = _normalize_relative(project_root, candidate)
        if rel_path is None:
            continue
        abs_path = project_root / rel_path
        if not abs_path.exists() or not abs_path.is_file() or abs_path.is_symlink():
            continue
        if rel_path not in seen:
            selected.append(rel_path)
            seen.add(rel_path)
    return sorted(selected, key=str)


def _collect_full_scope_files(project_root: Path) -> list[Path]:
    selected: list[Path] = []
    seen: set[Path] = set()
    for root, dirs, files in os.walk(project_root, topdown=True, followlinks=False):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d)) and d not in _EXCLUDED_DIRS]
        for name in sorted(files):
            full_path = Path(root) / name
            if full_path.is_symlink() or not full_path.is_file():
                continue
            rel_path = full_path.relative_to(project_root)
            if not _supported_security_file(rel_path) or rel_path in seen:
                continue
            seen.add(rel_path)
            selected.append(rel_path)
    return sorted(selected, key=str)


def _supported_security_file(path: Path) -> bool:
    return path.suffix.lower() in _SUPPORTED_SECURITY_SUFFIXES or path.name in {
        "pyproject.toml",
        "Pipfile",
        "Pipfile.lock",
        "poetry.lock",
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-test.txt",
        "setup.cfg",
        "tox.ini",
        ".pre-commit-config.yaml",
    }


def _normalize_relative(project_root: Path, path: Path | str) -> Path | None:
    candidate = Path(str(path))
    if candidate.is_absolute():
        try:
            return candidate.relative_to(project_root)
        except Exception:
            return None
    return candidate


def _matches_any(value: str, patterns: Sequence[str]) -> bool:
    candidate = Path(value).name
    for pattern in patterns:
        if pattern.endswith("*") and candidate.startswith(pattern[:-1]):
            return True
        if value == pattern or candidate == pattern:
            return True
    return False


def _is_python_executable(executable: str) -> bool:
    return _matches_any(executable, ("python*",))


def _python_module_name(command: Sequence[str]) -> str | None:
    for index, token in enumerate(command[1:], start=1):
        if token == "-m" and index + 1 < len(command):
            return command[index + 1]
    return None


def _python_script_argument(command: Sequence[str]) -> str | None:
    index = 1
    while index < len(command):
        token = command[index]
        if token == "-m" and index + 1 < len(command):
            return None
        if token == "-c":
            return None
        if token.startswith("-"):
            index += 1
            continue
        return token
    return None


_READ_ONLY_GIT_SUBCOMMANDS = {
    "diff",
    "status",
    "log",
    "show",
    "rev-parse",
    "ls-files",
    "describe",
    "grep",
}


def _git_subcommand(command: Sequence[str]) -> str | None:
    for token in command[1:]:
        if token.startswith("-"):
            continue
        return token
    return None


def _shell_operator_tokens(tokens: Sequence[str]) -> tuple[str, ...]:
    dangerous: list[str] = []
    for token in tokens:
        if token in {"&&", "||", "|", ";", "&", ">", "<"}:
            dangerous.append(token)
            continue
        if "$(" in token or "`" in token:
            dangerous.append(token)
    return tuple(dangerous)


def _python_script_allowed(project_root: Path, script_path: Path) -> bool:
    root = project_root.resolve(strict=False)
    if script_path.is_absolute():
        try:
            script_path.resolve(strict=False).relative_to(root)
            return True
        except Exception:
            return False
    try:
        (root / script_path).resolve(strict=False).relative_to(root)
        return True
    except Exception:
        return False


def _working_directory_allowed(cwd: Path, project_root: Path, policy: CommandPolicy) -> bool:
    try:
        cwd.relative_to(project_root)
        return True
    except Exception:
        pass
    for allowed in policy.allowed_working_directories:
        allowed_path = Path(allowed)
        if allowed_path.is_absolute():
            try:
                cwd.relative_to(allowed_path.resolve(strict=False))
                return True
            except Exception:
                continue
        else:
            candidate = (project_root / allowed_path).resolve(strict=False)
            try:
                cwd.relative_to(candidate)
                return True
            except Exception:
                continue
    return False


def _looks_sensitive_env_key(key: str) -> bool:
    return bool(_SECRET_KEY_RE.match(key)) and (key.isupper() or "_" in key)


def _looks_sensitive_name(name: str) -> bool:
    return bool(_SECRET_KEY_RE.match(name)) and (name.isupper() or "_" in name)


def _assignment_name(target: ast.AST) -> str | None:
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return None


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _keyword_is_true(keyword: ast.keyword, name: str) -> bool:
    if keyword.arg != name:
        return False
    return isinstance(keyword.value, ast.Constant) and keyword.value.value is True


def _keyword_is_false(keyword: ast.keyword, name: str) -> bool:
    if keyword.arg != name:
        return False
    return isinstance(keyword.value, ast.Constant) and keyword.value.value is False


def _dedupe_findings(findings: Sequence[ValidationFinding]) -> tuple[ValidationFinding, ...]:
    seen: set[tuple[Any, ...]] = set()
    unique: list[ValidationFinding] = []
    for finding in findings:
        key = (
            finding.code,
            finding.message,
            str(finding.file_path) if finding.file_path is not None else None,
            finding.line,
            finding.column,
            finding.severity.value,
            finding.blocking,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return tuple(unique)


def _is_dependency_manifest(path: Path) -> bool:
    name = path.name
    lower = name.lower()
    if name in {"pyproject.toml", "Pipfile", "Pipfile.lock", "poetry.lock", "tox.ini", "setup.cfg"}:
        return True
    if lower.startswith("requirements") and path.suffix.lower() == ".txt":
        return True
    return False


_SECRET_DETECTORS = (
    {
        "name": "openai_key",
        "code": "SECURITY_SECRET_OPENAI_KEY",
        "message": "Potential OpenAI API key detected.",
        "sample": "sk-***",
        "pattern": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    },
    {
        "name": "aws_key",
        "code": "SECURITY_SECRET_AWS_KEY",
        "message": "Potential AWS access key detected.",
        "sample": "AKIA***",
        "pattern": re.compile(r"AKIA[0-9A-Z]{16}"),
    },
    {
        "name": "github_token",
        "code": "SECURITY_SECRET_GITHUB_TOKEN",
        "message": "Potential GitHub token detected.",
        "sample": "ghp_***",
        "pattern": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    },
    {
        "name": "slack_token",
        "code": "SECURITY_SECRET_SLACK_TOKEN",
        "message": "Potential Slack token detected.",
        "sample": "xoxb-***",
        "pattern": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    },
    {
        "name": "google_key",
        "code": "SECURITY_SECRET_GOOGLE_KEY",
        "message": "Potential Google API key detected.",
        "sample": "AIza***",
        "pattern": re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    },
    {
        "name": "pem_private_key",
        "code": "SECURITY_SECRET_PEM_PRIVATE_KEY",
        "message": "Potential PEM private key detected.",
        "sample": "-----BEGIN PRIVATE KEY-----",
        "pattern": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    },
    {
        "name": "jwt",
        "code": "SECURITY_SECRET_JWT",
        "message": "Potential JSON Web Token detected.",
        "sample": "eyJ***.***.***",
        "pattern": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    },
    {
        "name": "bearer_token",
        "code": "SECURITY_SECRET_BEARER_TOKEN",
        "message": "Potential bearer token detected.",
        "sample": "Bearer ***",
        "pattern": re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    },
    {
        "name": "database_url",
        "code": "SECURITY_SECRET_DATABASE_URL",
        "message": "Potential database URL with embedded credentials detected.",
        "sample": "postgres://user:***@host/db",
        "pattern": re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^@\s]+@[^/\s]+"),
    },
    {
        "name": "hardcoded_password",
        "code": "SECURITY_SECRET_PASSWORD",
        "message": "Potential hardcoded password detected.",
        "sample": "password=***",
        "pattern": re.compile(r"(?i)\b(?:password|passwd|secret|token)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    },
    {
        "name": "generic_high_entropy",
        "code": "SECURITY_HIGH_ENTROPY_SECRET",
        "message": "Potential high-entropy secret detected.",
        "sample": "***",
        "pattern": re.compile(r"[A-Za-z0-9+/=_-]{32,}"),
    },
)


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _looks_high_entropy(value: str) -> bool:
    candidate = value.strip().strip("'\"")
    if len(candidate) < 32:
        return False
    if candidate.isdigit():
        return False
    unique = len(set(candidate))
    if unique < 10:
        return False
    alpha_ratio = sum(char.isalpha() for char in candidate) / len(candidate)
    digit_ratio = sum(char.isdigit() for char in candidate) / len(candidate)
    return alpha_ratio > 0.3 and digit_ratio > 0.1


def _looks_sql_fstring(node: ast.JoinedStr) -> bool:
    pieces: list[str] = []
    has_interpolation = False
    for value in node.values:
        if isinstance(value, ast.FormattedValue):
            has_interpolation = True
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            pieces.append(value.value)
    if not has_interpolation:
        return False
    text = " ".join(piece.lower() for piece in pieces)
    return any(keyword in text for keyword in ("select ", "insert ", "update ", "delete ", "drop ", "where "))


def _looks_debug_enabled(lower: str) -> bool:
    return "debug=true" in lower or "debug = true" in lower or "debug: true" in lower


def _looks_wildcard_host(lower: str) -> bool:
    return ("allowed_hosts" in lower and "*" in lower) or "host: \"*\"" in lower or "host='*'" in lower or "host = '*'" in lower or "0.0.0.0" in lower


def _looks_wildcard_cors(lower: str) -> bool:
    return ("cors" in lower and "*" in lower) or ("allow_origin" in lower and "*" in lower) or ("allow_origins" in lower and "*" in lower)


def _looks_tls_disabled(lower: str) -> bool:
    return "verify=false" in lower or "ssl: false" in lower or "tls: false" in lower or "insecure: true" in lower


def _looks_docker_secret(lower: str) -> bool:
    return "secrets:" in lower or "docker secret" in lower


def _looks_root_user(lower: str) -> bool:
    return "user root" in lower or "user: root" in lower or "runasuser: 0" in lower or "run_as_user: 0" in lower


def _looks_unpinned_image(lower: str) -> bool:
    if "image:" not in lower and not lower.startswith("from "):
        return False
    if "@sha256:" in lower:
        return False
    return ":" in lower and not lower.endswith(":latest")


def _looks_broad_github_permissions(lower: str) -> bool:
    return any(token in lower for token in ("write-all", "contents: write", "actions: write", "issues: write", "pull-requests: write"))


__all__ = [
    "bandit_step",
    "SecurityValidator",
    "build_security_plan",
    "default_security_steps",
    "evaluate_command_policy",
    "pip_audit_step",
    "security_step",
]
