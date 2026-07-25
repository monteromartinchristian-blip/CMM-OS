"""ProjectManifestValidator implementation for CMM OS custom validators catalog."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.context import ValidationContext
from cmm.validation.custom import CustomValidator
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding
from cmm.validation.steps import ValidationStepResult
from ._utils import aggregate_status, read_file_safe, safe_read_text, serialize_path

REQUIRED_DEV_TOOLS = ("pytest", "mypy", "vulture")
REQUIRED_VALIDATION_TOOLS = ("bandit", "pip-audit", "mypy", "vulture")


def _normalize_pkg_name(req_str: str) -> str:
    """Extract and normalize canonical package name from dependency specification string."""
    req = req_str.split(";")[0].strip()
    pkg = re.split(r"[><=~!;\s]", req)[0].strip()
    return pkg.lower().replace("_", "-")


class ProjectManifestValidator(CustomValidator):
    """Validates structure and required configurations in pyproject.toml."""

    name = "project_manifest"

    def validate(self, context: ValidationContext) -> ValidationStepResult:
        started_at = datetime.now(timezone.utc)
        t0 = time.monotonic()
        source_name = f"validation.custom.{self.name}"

        manifest_path = context.project_root / "pyproject.toml"
        rel_manifest_path = serialize_path(manifest_path, context.project_root)

        findings: List[ValidationFinding] = []
        project_name: str | None = None
        version: str | None = None
        requires_python: str | None = None
        scripts: Dict[str, Any] | None = None
        optional_groups: List[str] | None = None
        missing_reqs: List[str] = []
        duplicate_reqs: List[str] = []

        if not manifest_path.is_file():
            findings.append(
                ValidationFinding(
                    code="PROJECT_MANIFEST_MISSING",
                    message="pyproject.toml manifest file was not found in project root",
                    severity=ValidationSeverity.ERROR,
                    source=source_name,
                    file_path=rel_manifest_path,
                    blocking=True,
                )
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            return self._build_result(
                findings=findings,
                started_at=started_at,
                duration_ms=duration_ms,
                rel_path=rel_manifest_path,
                project_name=None,
                version=None,
                requires_python=None,
                scripts=None,
                optional_groups=None,
                missing_reqs=missing_reqs,
                duplicate_reqs=duplicate_reqs,
            )

        read_res = read_file_safe(manifest_path)
        if read_res.is_unreadable or read_res.content is None:
            findings.append(
                ValidationFinding(
                    code="PROJECT_MANIFEST_INVALID_TOML",
                    message=f"pyproject.toml could not be read ({read_res.error_type or 'read_error'})",
                    severity=ValidationSeverity.ERROR,
                    source=source_name,
                    file_path=rel_manifest_path,
                    blocking=True,
                    metadata={"error_type": read_res.error_type or "read_error"},
                )
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            return self._build_result(
                findings=findings,
                started_at=started_at,
                duration_ms=duration_ms,
                rel_path=rel_manifest_path,
                project_name=None,
                version=None,
                requires_python=None,
                scripts=None,
                optional_groups=None,
                missing_reqs=missing_reqs,
                duplicate_reqs=duplicate_reqs,
            )

        content_str = read_res.content

        try:
            doc = tomllib.loads(content_str)
        except Exception as exc:
            findings.append(
                ValidationFinding(
                    code="PROJECT_MANIFEST_INVALID_TOML",
                    message=f"pyproject.toml contains invalid TOML syntax: {exc}",
                    severity=ValidationSeverity.ERROR,
                    source=source_name,
                    file_path=rel_manifest_path,
                    blocking=True,
                )
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            return self._build_result(
                findings=findings,
                started_at=started_at,
                duration_ms=duration_ms,
                rel_path=rel_manifest_path,
                project_name=None,
                version=None,
                requires_python=None,
                scripts=None,
                optional_groups=None,
                missing_reqs=missing_reqs,
                duplicate_reqs=duplicate_reqs,
            )

        # Check [build-system]
        if "build-system" not in doc:
            findings.append(
                ValidationFinding(
                    code="PROJECT_MANIFEST_BUILD_SYSTEM_MISSING",
                    message="[build-system] section is missing in pyproject.toml",
                    severity=ValidationSeverity.ERROR,
                    source=source_name,
                    file_path=rel_manifest_path,
                    blocking=True,
                )
            )

        # Check [project]
        if "project" not in doc or not isinstance(doc["project"], dict):
            findings.append(
                ValidationFinding(
                    code="PROJECT_MANIFEST_PROJECT_SECTION_MISSING",
                    message="[project] section is missing in pyproject.toml",
                    severity=ValidationSeverity.ERROR,
                    source=source_name,
                    file_path=rel_manifest_path,
                    blocking=True,
                )
            )
        else:
            proj = doc["project"]

            # project.name
            raw_name = proj.get("name")
            if not isinstance(raw_name, str) or not raw_name.strip():
                findings.append(
                    ValidationFinding(
                        code="PROJECT_MANIFEST_NAME_MISSING",
                        message="project.name is missing or empty in pyproject.toml",
                        severity=ValidationSeverity.ERROR,
                        source=source_name,
                        file_path=rel_manifest_path,
                        blocking=True,
                    )
                )
            else:
                project_name = raw_name.strip()

            # project.version
            raw_version = proj.get("version")
            if not isinstance(raw_version, str) or not raw_version.strip():
                findings.append(
                    ValidationFinding(
                        code="PROJECT_MANIFEST_VERSION_MISSING",
                        message="project.version is missing or empty in pyproject.toml",
                        severity=ValidationSeverity.ERROR,
                        source=source_name,
                        file_path=rel_manifest_path,
                        blocking=True,
                    )
                )
            else:
                version = raw_version.strip()

            # project.requires-python
            raw_req_py = proj.get("requires-python")
            if not isinstance(raw_req_py, str) or not raw_req_py.strip():
                findings.append(
                    ValidationFinding(
                        code="PROJECT_MANIFEST_REQUIRES_PYTHON_MISSING",
                        message="project.requires-python is missing in pyproject.toml",
                        severity=ValidationSeverity.WARNING,
                        source=source_name,
                        file_path=rel_manifest_path,
                        blocking=False,
                    )
                )
            else:
                requires_python = raw_req_py.strip()

            # project.scripts / entry points
            raw_scripts = proj.get("scripts")
            if isinstance(raw_scripts, dict):
                scripts = raw_scripts
                cmm_ep = raw_scripts.get("cmm")
                if cmm_ep is None:
                    findings.append(
                        ValidationFinding(
                            code="PROJECT_MANIFEST_ENTRY_POINT_MISSING",
                            message="Entry point 'cmm' is missing under [project.scripts]",
                            severity=ValidationSeverity.ERROR,
                            source=source_name,
                            file_path=rel_manifest_path,
                            blocking=True,
                        )
                    )
                elif cmm_ep != "cmm.cli:main":
                    findings.append(
                        ValidationFinding(
                            code="PROJECT_MANIFEST_ENTRY_POINT_INVALID",
                            message=f"Entry point 'cmm' must be 'cmm.cli:main', got '{cmm_ep}'",
                            severity=ValidationSeverity.ERROR,
                            source=source_name,
                            file_path=rel_manifest_path,
                            blocking=True,
                            metadata={
                                "expected": "cmm.cli:main",
                                "actual": str(cmm_ep),
                            },
                        )
                    )
            else:
                findings.append(
                    ValidationFinding(
                        code="PROJECT_MANIFEST_ENTRY_POINT_MISSING",
                        message="[project.scripts] table is missing or invalid in pyproject.toml",
                        severity=ValidationSeverity.ERROR,
                        source=source_name,
                        file_path=rel_manifest_path,
                        blocking=True,
                    )
                )

            # optional-dependencies
            opt_deps = proj.get("optional-dependencies")
            if isinstance(opt_deps, dict):
                optional_groups = list(opt_deps.keys())

                # Check duplicates & collect tools per group
                tools_in_group: Dict[str, Set[str]] = {}
                for grp, req_list in opt_deps.items():
                    if isinstance(req_list, list):
                        seen_in_group: Set[str] = set()
                        tools_in_group[grp] = set()
                        for r in req_list:
                            if isinstance(r, str):
                                norm_pkg = _normalize_pkg_name(r)
                                tools_in_group[grp].add(norm_pkg)
                                if norm_pkg in seen_in_group:
                                    duplicate_reqs.append(f"{grp}:{norm_pkg}")
                                    findings.append(
                                        ValidationFinding(
                                            code="PROJECT_MANIFEST_DUPLICATE_DEPENDENCY",
                                            message=f"Duplicate dependency '{norm_pkg}' found in optional-dependencies group '{grp}'",
                                            severity=ValidationSeverity.WARNING,
                                            source=source_name,
                                            file_path=rel_manifest_path,
                                            blocking=False,
                                            metadata={
                                                "group": grp,
                                                "dependency": norm_pkg,
                                            },
                                        )
                                    )
                                seen_in_group.add(norm_pkg)

                # Check dev group
                dev_tools = tools_in_group.get("dev", set())
                for req_tool in REQUIRED_DEV_TOOLS:
                    if req_tool not in dev_tools:
                        missing_reqs.append(f"dev:{req_tool}")
                        findings.append(
                            ValidationFinding(
                                code="PROJECT_MANIFEST_DEV_DEPENDENCY_MISSING",
                                message=f"Required development tool '{req_tool}' is missing in project.optional-dependencies.dev",
                                severity=ValidationSeverity.WARNING,
                                source=source_name,
                                file_path=rel_manifest_path,
                                blocking=False,
                                metadata={"tool": req_tool, "group": "dev"},
                            )
                        )

                # Check validation group
                val_tools = tools_in_group.get("validation", set())
                for req_tool in REQUIRED_VALIDATION_TOOLS:
                    if req_tool not in val_tools:
                        missing_reqs.append(f"validation:{req_tool}")
                        findings.append(
                            ValidationFinding(
                                code="PROJECT_MANIFEST_VALIDATION_DEPENDENCY_MISSING",
                                message=f"Required validation tool '{req_tool}' is missing in project.optional-dependencies.validation",
                                severity=ValidationSeverity.WARNING,
                                source=source_name,
                                file_path=rel_manifest_path,
                                blocking=False,
                                metadata={"tool": req_tool, "group": "validation"},
                            )
                        )
            else:
                for req_tool in REQUIRED_DEV_TOOLS:
                    missing_reqs.append(f"dev:{req_tool}")
                    findings.append(
                        ValidationFinding(
                            code="PROJECT_MANIFEST_DEV_DEPENDENCY_MISSING",
                            message=f"Required development tool '{req_tool}' is missing in project.optional-dependencies.dev",
                            severity=ValidationSeverity.WARNING,
                            source=source_name,
                            file_path=rel_manifest_path,
                            blocking=False,
                        )
                    )

        duration_ms = int((time.monotonic() - t0) * 1000)
        return self._build_result(
            findings=findings,
            started_at=started_at,
            duration_ms=duration_ms,
            rel_path=rel_manifest_path,
            project_name=project_name,
            version=version,
            requires_python=requires_python,
            scripts=scripts,
            optional_groups=optional_groups,
            missing_reqs=missing_reqs,
            duplicate_reqs=duplicate_reqs,
        )

    def _build_result(
        self,
        findings: List[ValidationFinding],
        started_at: datetime,
        duration_ms: int,
        rel_path: str,
        project_name: str | None,
        version: str | None,
        requires_python: str | None,
        scripts: Dict[str, Any] | None,
        optional_groups: List[str] | None,
        missing_reqs: List[str],
        duplicate_reqs: List[str],
    ) -> ValidationStepResult:
        status = aggregate_status(findings)
        completed_at = datetime.now(timezone.utc)

        artifact = ValidationArtifact(
            id="project-manifest-report",
            kind="project_manifest_report",
            source=f"validation.custom.{self.name}",
            content={
                "path": rel_path,
                "project_name": project_name,
                "version": version,
                "requires_python": requires_python,
                "scripts": scripts,
                "optional_dependency_groups": optional_groups,
                "missing_requirements": missing_reqs,
                "duplicate_requirements": duplicate_reqs,
                "valid": status == ValidationStatus.PASSED,
            },
            findings=tuple(findings),
        )

        return ValidationStepResult(
            name=f"custom.{self.name}",
            status=status,
            duration_ms=duration_ms,
            findings=tuple(findings),
            artifacts=(artifact,),
            started_at=started_at,
            completed_at=completed_at,
            metadata={
                "custom_validator": True,
                "validator_name": self.name,
                "validator_category": "project_structure",
            },
        )
