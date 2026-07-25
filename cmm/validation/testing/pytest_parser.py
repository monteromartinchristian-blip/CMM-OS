from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding
from cmm.validation.steps import ValidationStep, ValidationStepResult
from .artifacts import build_pytest_artifact
from .selection import TestSelection

_ALLOWED_STATUSES = {"passed", "failed", "error", "skipped", "xfailed", "xpassed"}


def _coerce_int(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _coerce_float_ms(value: Any) -> int:
    try:
        return int(float(value) * 1000)
    except Exception:
        return 0


def _parse_path(value: str | None, project_root: Path | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if project_root is not None and not path.is_absolute():
        path = project_root / path
    if project_root is not None:
        try:
            path = path.relative_to(project_root)
        except Exception:
            pass
    return path


def _extract_text(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    text = "".join(element.itertext()).strip()
    return text or None


@dataclass(frozen=True, slots=True)
class PytestTestCaseResult:
    nodeid: str
    status: str
    duration_ms: int
    file_path: Path | None
    class_name: str | None
    test_name: str
    message: str | None = None
    traceback: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.nodeid:
            raise ValueError("PytestTestCaseResult.nodeid must not be empty")
        if self.status not in _ALLOWED_STATUSES:
            raise ValueError("PytestTestCaseResult.status is invalid")
        if self.duration_ms < 0:
            raise ValueError("PytestTestCaseResult.duration_ms must be non-negative")
        if not self.test_name:
            raise ValueError("PytestTestCaseResult.test_name must not be empty")
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "nodeid": self.nodeid,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "file_path": None if self.file_path is None else str(self.file_path),
            "class_name": self.class_name,
            "test_name": self.test_name,
            "message": self.message,
            "traceback": self.traceback,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True, slots=True)
class PytestRunSummary:
    collected: int
    passed: int
    failed: int
    errors: int
    skipped: int
    xfailed: int
    xpassed: int
    duration_ms: int
    test_cases: tuple[PytestTestCaseResult, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "collected",
            "passed",
            "failed",
            "errors",
            "skipped",
            "xfailed",
            "xpassed",
            "duration_ms",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"PytestRunSummary.{field_name} must be non-negative")
        object.__setattr__(self, "test_cases", tuple(self.test_cases or ()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "collected": self.collected,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "skipped": self.skipped,
            "xfailed": self.xfailed,
            "xpassed": self.xpassed,
            "duration_ms": self.duration_ms,
            "test_cases": [case.serialize() for case in self.test_cases],
            "metadata": dict(self.metadata or {}),
        }


def _iter_testcases(root: ET.Element) -> Iterable[ET.Element]:
    if root.tag == "testcase":
        yield root
    for node in root.iter("testcase"):
        yield node


def _case_status(case: ET.Element) -> tuple[str, str | None, str | None]:
    failure = case.find("failure")
    error = case.find("error")
    skipped = case.find("skipped")
    if failure is not None:
        message = failure.attrib.get("message") or _extract_text(failure)
        if message and "xpass" in message.lower():
            return "xpassed", message, _extract_text(failure)
        return "failed", message, _extract_text(failure)
    if error is not None:
        message = error.attrib.get("message") or _extract_text(error)
        return "error", message, _extract_text(error)
    if skipped is not None:
        message = skipped.attrib.get("message") or _extract_text(skipped)
        skipped_type = (skipped.attrib.get("type") or "").lower()
        if "xfail" in skipped_type or (message and "xfail" in message.lower()):
            return "xfailed", message, _extract_text(skipped)
        return "skipped", message, _extract_text(skipped)
    return "passed", None, None


def _case_nodeid(
    case: ET.Element, fallback_classname: str | None, fallback_name: str
) -> str:
    if case.attrib.get("nodeid"):
        return str(case.attrib["nodeid"])
    file_attr = case.attrib.get("file")
    if file_attr:
        return f"{file_attr}::{fallback_name}"
    if fallback_classname:
        return f"{fallback_classname}::{fallback_name}"
    return fallback_name


def _case_file_path(case: ET.Element, project_root: Path | None) -> Path | None:
    return _parse_path(case.attrib.get("file"), project_root)


def _summary_from_cases(
    cases: list[PytestTestCaseResult], duration_ms: int, metadata: Mapping[str, Any]
) -> PytestRunSummary:
    counts = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
    }
    for case in cases:
        if case.status in counts:
            counts[case.status] += 1
    return PytestRunSummary(
        collected=len(cases),
        passed=counts["passed"],
        failed=counts["failed"],
        errors=counts["errors"],
        skipped=counts["skipped"],
        xfailed=counts["xfailed"],
        xpassed=counts["xpassed"],
        duration_ms=duration_ms,
        test_cases=tuple(cases),
        metadata=dict(metadata),
    )


def _find_related_changes(
    selection: Mapping[str, Any],
) -> Mapping[str, tuple[str, ...]]:
    related = selection.get("related_changes") if isinstance(selection, Mapping) else {}
    if not isinstance(related, Mapping):
        return {}
    return {
        str(key): tuple(str(item) for item in value) for key, value in related.items()
    }


def _selection_from_step(step: ValidationStep) -> TestSelection:
    selection = step.metadata.get("selection")
    if isinstance(selection, Mapping):
        selected = tuple(
            Path(str(item)) for item in selection.get("selected_tests", ())
        )
        related = selection.get("related_changes", {})
        if not isinstance(related, Mapping):
            related = {}
        return TestSelection(
            selected_tests=selected,
            related_changes={
                str(key): tuple(str(item) for item in value)
                for key, value in related.items()
            },
            confidence=float(selection.get("confidence", 0.0)),
            requires_full_suite=bool(selection.get("requires_full_suite", False)),
            reasons=tuple(str(item) for item in selection.get("reasons", ())),
            metadata=dict(selection.get("metadata", {}))
            if isinstance(selection.get("metadata"), Mapping)
            else {},
        )
    return TestSelection()


def _extract_report_path(
    step: ValidationStep, junit_xml: str | bytes | Path | None
) -> tuple[Path | None, Path | None]:
    report_path: Path | None = None
    temp_dir: Path | None = None
    if junit_xml is not None:
        if isinstance(junit_xml, Path):
            report_path = junit_xml
        elif isinstance(junit_xml, bytes):
            return None, None
        else:
            raw = str(junit_xml)
            if "<" not in raw and ">" not in raw:
                report_path = Path(raw)
    meta_path = step.metadata.get("pytest_junitxml")
    if report_path is None and meta_path:
        report_path = Path(str(meta_path))
    meta_temp = step.metadata.get("pytest_temp_dir")
    if meta_temp:
        temp_dir = Path(str(meta_temp))
    if report_path is not None and not report_path.is_absolute():
        project_root = step.metadata.get("project_root")
        if project_root:
            report_path = Path(str(project_root)) / report_path
    return report_path, temp_dir


def _parse_report_xml(
    xml_text: str, *, project_root: Path | None
) -> tuple[list[PytestTestCaseResult], dict[str, Any]]:
    root = ET.fromstring(xml_text)
    cases: list[PytestTestCaseResult] = []
    root_metadata = {
        "root_tag": root.tag,
        "attributes": dict(root.attrib),
    }
    for case in _iter_testcases(root):
        status, message, traceback = _case_status(case)
        classname = case.attrib.get("classname")
        test_name = case.attrib.get("name") or ""
        nodeid = _case_nodeid(case, classname, test_name)
        file_path = _case_file_path(case, project_root)
        duration_ms = _coerce_float_ms(case.attrib.get("time"))
        metadata = {
            "classname": classname,
            "line": _coerce_int(case.attrib.get("line")) or None,
            "raw_attributes": dict(case.attrib),
        }
        cases.append(
            PytestTestCaseResult(
                nodeid=nodeid,
                status=status,
                duration_ms=duration_ms,
                file_path=file_path,
                class_name=classname,
                test_name=test_name or nodeid,
                message=message,
                traceback=traceback,
                metadata=metadata,
            )
        )
    return cases, root_metadata


def parse_pytest_result(
    *,
    step: ValidationStep,
    generic_result: ValidationStepResult,
    junit_xml: str | bytes | Path | None,
) -> ValidationStepResult:
    selection = _selection_from_step(step)
    report_path, temp_dir = _extract_report_path(step, junit_xml)
    project_root = None
    project_root_meta = step.metadata.get("project_root")
    if project_root_meta:
        project_root = Path(str(project_root_meta))

    findings: list[ValidationFinding] = []
    artifacts: list[ValidationArtifact] = []
    cases: list[PytestTestCaseResult] = []
    summary: PytestRunSummary | None = None
    parse_error = False

    try:
        xml_text: str | None = None
        if isinstance(junit_xml, bytes):
            xml_text = junit_xml.decode("utf-8", errors="replace")
        elif isinstance(junit_xml, Path) and junit_xml.exists():
            xml_text = junit_xml.read_text(encoding="utf-8")
        elif isinstance(junit_xml, str):
            if "<" in junit_xml and ">" in junit_xml:
                xml_text = junit_xml
            elif report_path is not None and report_path.exists():
                xml_text = report_path.read_text(encoding="utf-8")
        elif report_path is not None and report_path.exists():
            xml_text = report_path.read_text(encoding="utf-8")

        if xml_text is not None:
            try:
                cases, root_metadata = _parse_report_xml(
                    xml_text, project_root=project_root
                )
                summary = _summary_from_cases(
                    cases, generic_result.duration_ms, root_metadata
                )
            except ET.ParseError as exc:
                parse_error = True
                findings.append(
                    ValidationFinding(
                        code="PYTEST_REPORT_PARSE_ERROR",
                        message="Pytest JUnit XML report could not be parsed.",
                        severity=ValidationSeverity.ERROR,
                        source="pytest",
                        blocking=True,
                        metadata={
                            "report_path": None
                            if report_path is None
                            else str(report_path),
                            "error": str(exc),
                        },
                    )
                )
                status = ValidationStatus.ERROR
                root_metadata = {}
        else:
            root_metadata = {}

        case_related_changes = _find_related_changes(step.metadata.get("selection", {}))
        selection_related = dict(case_related_changes)
        affected_tests = tuple(str(path) for path in selection.selected_tests)

        failed_cases = [case for case in cases if case.status == "failed"]
        error_cases = [case for case in cases if case.status == "error"]
        collection_error_cases = [
            case
            for case in error_cases
            if "collect" in case.nodeid.lower() or case.file_path is None
        ]

        def _add_case_finding(
            case: PytestTestCaseResult, code: str, message: str | None
        ) -> None:
            related = []
            if case.file_path is not None:
                related = list(selection_related.get(str(case.file_path), ()))
            findings.append(
                ValidationFinding(
                    code=code,
                    message=message
                    or case.message
                    or f"Pytest reported {case.status} for {case.nodeid}",
                    severity=ValidationSeverity.ERROR,
                    source="pytest",
                    file_path=case.file_path,
                    line=case.metadata.get("line"),
                    blocking=bool(step.required),
                    metadata={
                        "nodeid": case.nodeid,
                        "classname": case.class_name,
                        "test_name": case.test_name,
                        "duration_ms": case.duration_ms,
                        "status": case.status,
                        "related_changes": related,
                        "traceback": case.traceback,
                    },
                )
            )

        if generic_result.status == ValidationStatus.TIMED_OUT:
            findings.append(
                ValidationFinding(
                    code="PYTEST_TIMEOUT",
                    message="Pytest execution timed out.",
                    severity=ValidationSeverity.ERROR,
                    source="pytest",
                    blocking=True,
                    metadata={
                        "timeout_seconds": step.timeout_seconds,
                        "scope": step.metadata.get("pytest_scope"),
                    },
                )
            )
            status = ValidationStatus.TIMED_OUT
        elif generic_result.exit_code == 2:
            findings.append(
                ValidationFinding(
                    code="PYTEST_INTERRUPTED",
                    message="Pytest execution was interrupted.",
                    severity=ValidationSeverity.ERROR,
                    source="pytest",
                    blocking=True,
                    metadata={"scope": step.metadata.get("pytest_scope")},
                )
            )
            status = ValidationStatus.CANCELLED
        elif generic_result.exit_code == 3:
            findings.append(
                ValidationFinding(
                    code="PYTEST_INTERNAL_ERROR",
                    message="Pytest reported an internal error.",
                    severity=ValidationSeverity.ERROR,
                    source="pytest",
                    blocking=True,
                    metadata={
                        "stdout": generic_result.stdout,
                        "stderr": generic_result.stderr,
                    },
                )
            )
            status = ValidationStatus.ERROR
        elif generic_result.exit_code == 4:
            findings.append(
                ValidationFinding(
                    code="PYTEST_USAGE_ERROR",
                    message="Pytest reported a usage or configuration error.",
                    severity=ValidationSeverity.ERROR,
                    source="pytest",
                    blocking=True,
                    metadata={
                        "stdout": generic_result.stdout,
                        "stderr": generic_result.stderr,
                    },
                )
            )
            status = ValidationStatus.ERROR
        elif generic_result.exit_code == 5:
            findings.append(
                ValidationFinding(
                    code="PYTEST_NO_TESTS_COLLECTED",
                    message="Pytest did not collect any tests.",
                    severity=ValidationSeverity.WARNING,
                    source="pytest",
                    blocking=bool(step.required),
                    metadata={"scope": step.metadata.get("pytest_scope")},
                )
            )
            status = (
                ValidationStatus.FAILED if step.required else ValidationStatus.WARNING
            )
        elif report_path is not None and not report_path.exists():
            findings.append(
                ValidationFinding(
                    code="PYTEST_REPORT_MISSING",
                    message="Pytest JUnit XML report was not created.",
                    severity=ValidationSeverity.ERROR,
                    source="pytest",
                    blocking=True,
                    metadata={
                        "report_path": str(report_path),
                        "exit_code": generic_result.exit_code,
                    },
                )
            )
            status = ValidationStatus.ERROR
        elif xml_text is None:
            findings.append(
                ValidationFinding(
                    code="PYTEST_REPORT_MISSING",
                    message="Pytest JUnit XML report was not available.",
                    severity=ValidationSeverity.ERROR,
                    source="pytest",
                    blocking=True,
                    metadata={
                        "report_path": None
                        if report_path is None
                        else str(report_path),
                        "exit_code": generic_result.exit_code,
                    },
                )
            )
            status = ValidationStatus.ERROR
        else:
            for case in failed_cases:
                code = "PYTEST_TEST_FAILED"
                _add_case_finding(case, code, case.message)
            for case in error_cases:
                code = (
                    "PYTEST_COLLECTION_ERROR"
                    if case in collection_error_cases
                    else "PYTEST_TEST_ERROR"
                )
                _add_case_finding(case, code, case.message)
            if generic_result.exit_code == 1 and not findings:
                findings.append(
                    ValidationFinding(
                        code="PYTEST_REPORT_MISSING",
                        message="Pytest reported failures but no test findings could be extracted.",
                        severity=ValidationSeverity.ERROR,
                        source="pytest",
                        blocking=True,
                    )
                )
                status = ValidationStatus.ERROR
            elif (
                failed_cases
                or error_cases
                or any(case.status in {"xpassed"} for case in cases)
            ):
                status = ValidationStatus.FAILED
            elif generic_result.exit_code == 0:
                status = ValidationStatus.PASSED
            else:
                status = ValidationStatus.ERROR

        if parse_error:
            status = ValidationStatus.ERROR

        if summary is None:
            summary = PytestRunSummary(
                collected=len(cases),
                passed=sum(1 for case in cases if case.status == "passed"),
                failed=sum(1 for case in cases if case.status == "failed"),
                errors=sum(1 for case in cases if case.status == "error"),
                skipped=sum(1 for case in cases if case.status == "skipped"),
                xfailed=sum(1 for case in cases if case.status == "xfailed"),
                xpassed=sum(1 for case in cases if case.status == "xpassed"),
                duration_ms=generic_result.duration_ms,
                test_cases=tuple(cases),
                metadata={"parser": "pytest", "status": generic_result.status.value},
            )

        artifact = build_pytest_artifact(
            scope=str(step.metadata.get("pytest_scope") or "affected"),
            full_suite=bool(step.metadata.get("pytest_full_suite")),
            confidence=float(step.metadata.get("pytest_confidence", 0.0)),
            selection=selection,
            command=step.command,
            summary=summary,
            test_cases=cases,
            related_changes=selection.related_changes,
            metadata={
                "exit_code": generic_result.exit_code,
                "scope": step.metadata.get("pytest_scope"),
                "report_path": None if report_path is None else str(report_path),
            },
        )
        artifacts.append(artifact)

        metadata = dict(generic_result.metadata or {})
        metadata.update(
            {
                "parser": "pytest",
                "pytest_scope": step.metadata.get("pytest_scope"),
                "pytest_full_suite": bool(step.metadata.get("pytest_full_suite")),
                "pytest_confidence": float(step.metadata.get("pytest_confidence", 0.0)),
                "selection": selection.serialize(),
                "affected_tests": [str(path) for path in selection.selected_tests],
                "pytest_summary": summary.serialize(),
                "pytest_report_path": None if report_path is None else str(report_path),
                "pytest_test_count": len(cases),
            }
        )
        return ValidationStepResult(
            name=generic_result.name,
            status=status,
            exit_code=generic_result.exit_code,
            duration_ms=generic_result.duration_ms,
            stdout=generic_result.stdout,
            stderr=generic_result.stderr,
            findings=tuple(findings),
            artifacts=tuple(artifacts),
            started_at=generic_result.started_at,
            completed_at=generic_result.completed_at,
            metadata=metadata,
        )
    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)
