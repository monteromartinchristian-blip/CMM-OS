"""Phase 10.5/10.39 – Tests for DomainFragmentationValidator."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from cmm.domains.validation_contracts import (
    DomainValidationExecutionContext,
    DomainValidationRequest,
)
from cmm.domains.validation_fragmentation import analyze_fragmentation
from cmm.domains.validation_scan import DomainValidationScanSession
from cmm.domains.validation_validators import DomainFragmentationValidator
from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepType


def _make_request(root_path, strict=True):
    return DomainValidationRequest(pack=None, root_path=str(root_path), strict=strict)


class TestDomainFragmentationValidator:
    def test_no_scan_session_returns_blocker(self) -> None:
        request = _make_request("/tmp")
        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=ValidationContext(project_root=Path("/tmp")),
        )
        validator = DomainFragmentationValidator(exec_ctx, scan_session=None)
        step = ValidationStep(
            name="domain.fragmentation",
            step_type=ValidationStepType.INTERNAL,
            required=True,
            dependencies=(),
        )
        result = validator.validate(None, step)
        assert any("No scan session" in f.message for f in result.findings)

    def test_readme_con_planner_no_bloquea(self) -> None:
        """README non-py file mentioning Planner doesn't block fragmentation."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("Uses Planner\n", encoding="utf-8")
            scan = DomainValidationScanSession(
                root=root,
                max_files=10,
                max_file_bytes=1_000_000,
                max_total_bytes=10_000_000,
                max_depth=10,
            )
            request = _make_request(td)
            exec_ctx = DomainValidationExecutionContext(
                request=request,
                validation_context=ValidationContext(project_root=root),
                scan_session=scan,
            )
            validator = DomainFragmentationValidator(exec_ctx, scan_session=scan)
            step = ValidationStep(
                name="domain.fragmentation",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            # README is not .py, so no findings
            assert len(result.findings) == 0

    def test_adapter_oficial_no_bloquea(self) -> None:
        """Official CMM adapter: extending TaskPlanner via canonical import
        must not produce fragmentation findings (Phase 10.39 fix)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "my_planner.py").write_text(
                "from cmm.planner import TaskPlanner\n"
                "class MyPlanner(TaskPlanner):\n    pass\n",
                encoding="utf-8",
            )
            scan = DomainValidationScanSession(
                root=root,
                max_files=10,
                max_file_bytes=1_000_000,
                max_total_bytes=10_000_000,
                max_depth=10,
            )
            request = _make_request(td)
            exec_ctx = DomainValidationExecutionContext(
                request=request,
                validation_context=ValidationContext(project_root=root),
                scan_session=scan,
            )
            validator = DomainFragmentationValidator(exec_ctx, scan_session=scan)
            step = ValidationStep(
                name="domain.fragmentation",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            # Phase 10.39: canonical adapters are recognized as reuse, not duplication
            fragmentation_findings = [
                f for f in result.findings if "FRAGMENTATION" in (f.code or "").upper()
            ]
            assert len(fragmentation_findings) == 0

    def test_clase_duplicada_real_bloquea(self) -> None:
        """Redefining a CMM class should block."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "dup.py").write_text(
                "class MemoryStore:\n    pass\n", encoding="utf-8"
            )
            scan = DomainValidationScanSession(
                root=root,
                max_files=10,
                max_file_bytes=1_000_000,
                max_total_bytes=10_000_000,
                max_depth=10,
            )
            request = _make_request(td)
            exec_ctx = DomainValidationExecutionContext(
                request=request,
                validation_context=ValidationContext(project_root=root),
                scan_session=scan,
            )
            validator = DomainFragmentationValidator(exec_ctx, scan_session=scan)
            step = ValidationStep(
                name="domain.fragmentation",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            block_findings = [f for f in result.findings if f.blocking]
            assert len(block_findings) >= 1

    def test_invalid_utf8_emits_finding(self) -> None:
        """Invalid UTF-8 byte sequence should emit a finding."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bad.py").write_bytes(b"print('hello')\xff\xfe\n")
            scan = DomainValidationScanSession(
                root=root,
                max_files=10,
                max_file_bytes=1_000_000,
                max_total_bytes=10_000_000,
                max_depth=10,
            )
            request = _make_request(td, strict=True)
            exec_ctx = DomainValidationExecutionContext(
                request=request,
                validation_context=ValidationContext(project_root=root),
                scan_session=scan,
            )
            validator = DomainFragmentationValidator(exec_ctx, scan_session=scan)
            step = ValidationStep(
                name="domain.fragmentation",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            utf8_findings = [f for f in result.findings if "UTF" in f.code.upper()]
            assert len(utf8_findings) >= 1
            # In strict mode, this should be blocking
            assert any(f.blocking for f in utf8_findings)


# ── Phase 10.39 – Protected core component duplications ───────────────────────


@pytest.mark.parametrize(
    ("source", "expected_code"),
    (
        (
            "class KnowledgeGraph:\n    pass\n",
            "DOMAIN_FRAGMENTATION_KNOWLEDGE_GRAPH_DUPLICATION",
        ),
        (
            "class HealthReasoningEngine:\n    pass\n",
            "DOMAIN_FRAGMENTATION_REASONING_ENGINE_DUPLICATION",
        ),
        (
            "class UniversityWorkflowEngine:\n    pass\n",
            "DOMAIN_FRAGMENTATION_WORKFLOW_ENGINE_DUPLICATION",
        ),
        (
            "class HealthPermissionSystem:\n    pass\n",
            "DOMAIN_FRAGMENTATION_PERMISSION_SYSTEM_DUPLICATION",
        ),
        (
            "class HealthSessionStore:\n    pass\n",
            "DOMAIN_FRAGMENTATION_SESSION_INFRASTRUCTURE_DUPLICATION",
        ),
        (
            "class HealthSessionContext:\n    pass\n",
            "DOMAIN_FRAGMENTATION_SESSION_INFRASTRUCTURE_DUPLICATION",
        ),
        (
            "class HealthOperationResult:\n    pass\n",
            "DOMAIN_FRAGMENTATION_OPERATION_RESULT_DUPLICATION",
        ),
    ),
)
def test_phase1039_missing_core_component_duplications_are_detected(
    source: str,
    expected_code: str,
) -> None:
    findings = analyze_fragmentation(source, "domain_component.py")
    codes = {str(item["code"]) for item in findings}
    assert expected_code in codes, f"Expected {expected_code} but found only {codes}"


# ── Phase 10.39 – Canonical adapter recognition ───────────────────────────────


def test_canonical_imported_adapter_does_not_block_fragmentation() -> None:
    """Adapters that extend a canonical imported base must not be blocked.

    Uses the real canonical ``cmm.planner.TaskPlanner`` (Phase 10.39
    remediation: replaced fictional ``BasePlanner``).
    """
    source = (
        "from cmm.planner import TaskPlanner\nclass MyPlanner(TaskPlanner):\n    pass\n"
    )
    findings = analyze_fragmentation(source, "my_planner.py")
    assert not any(
        item["code"] == "DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION" for item in findings
    )


def test_canonical_module_alias_adapter_does_not_block_fragmentation() -> None:
    """Module-alias adapters that extend a canonical base must not be blocked."""
    source = (
        "import cmm.planner as canonical_planner\n"
        "class MyPlanner(canonical_planner.TaskPlanner):\n"
        "    pass\n"
    )
    findings = analyze_fragmentation(source, "my_planner.py")
    assert not any(
        item["code"] == "DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION" for item in findings
    )


@pytest.mark.parametrize(
    ("source", "expected_code"),
    (
        (
            (
                "from cmm.planner import TaskPlanner\n"
                "TaskPlanner = object\n"
                "class EvilPlanner(TaskPlanner):\n"
                "    pass\n"
            ),
            "DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION",
        ),
        (
            (
                "from cmm.planner import TaskPlanner as CanonicalPlanner\n"
                "CanonicalPlanner = object\n"
                "class EvilPlanner(CanonicalPlanner):\n"
                "    pass\n"
            ),
            "DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION",
        ),
        (
            (
                "from cmm.workflows import WorkflowEngine\n"
                "WorkflowEngine = object\n"
                "class EvilWorkflowEngine(WorkflowEngine):\n"
                "    pass\n"
            ),
            "DOMAIN_FRAGMENTATION_WORKFLOW_ENGINE_DUPLICATION",
        ),
        (
            (
                "from cmm.cognitive import InMemoryResolutionMemoryStore\n"
                "InMemoryResolutionMemoryStore = object\n"
                "class EvilMemoryStore(InMemoryResolutionMemoryStore):\n"
                "    pass\n"
            ),
            "DOMAIN_FRAGMENTATION_MEMORY_DUPLICATION",
        ),
        (
            (
                "from cmm.planner import TaskPlanner\n"
                "TaskPlanner: object = object\n"
                "class EvilPlanner(TaskPlanner):\n"
                "    pass\n"
            ),
            "DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION",
        ),
        (
            (
                "import cmm.planner\n"
                "cmm = object\n"
                "class EvilPlanner(cmm.planner.TaskPlanner):\n"
                "    pass\n"
            ),
            "DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION",
        ),
    ),
)
def test_rebound_canonical_adapter_binding_does_not_grant_immunity(
    source: str,
    expected_code: str,
) -> None:
    """A binding must still be canonical when the protected class is declared."""
    findings = analyze_fragmentation(source, "rebound_adapter.py")
    assert expected_code in {str(item["code"]) for item in findings}


@pytest.mark.parametrize(
    ("source", "unexpected_code"),
    (
        (
            "import cmm.planner\nclass MyPlanner(cmm.planner.TaskPlanner):\n    pass\n",
            "DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION",
        ),
        (
            (
                "import cmm.workflows\n"
                "class MyWorkflowEngine(cmm.workflows.WorkflowEngine):\n"
                "    pass\n"
            ),
            "DOMAIN_FRAGMENTATION_WORKFLOW_ENGINE_DUPLICATION",
        ),
    ),
)
def test_unaliased_canonical_module_adapter_does_not_block_fragmentation(
    source: str,
    unexpected_code: str,
) -> None:
    """Equivalent unaliased canonical imports must retain adapter immunity."""
    findings = analyze_fragmentation(source, "canonical_adapter.py")
    assert unexpected_code not in {str(item["code"]) for item in findings}


def test_local_fake_base_does_not_make_duplicate_planner_an_adapter() -> None:
    """A local fake base class must NOT receive canonical-adapter immunity."""
    source = "class BasePlanner:\n    pass\nclass MyPlanner(BasePlanner):\n    pass\n"
    findings = analyze_fragmentation(source, "my_planner.py")
    assert "DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION" in {
        str(item["code"]) for item in findings
    }


# ── Phase 10.39 – Protected canonical contract redefinition ───────────────────


@pytest.mark.parametrize(
    "protected_name",
    (
        "KnowledgeItem",
        "Evidence",
        "TemporalScope",
        "Resource",
        "ResourceProvenance",
        "MemoryUpdateProposal",
    ),
)
def test_protected_canonical_contract_redefinition_is_detected(
    protected_name: str,
) -> None:
    findings = analyze_fragmentation(
        f"class {protected_name}:\n    pass\n",
        "contracts.py",
    )
    assert "DOMAIN_FRAGMENTATION_CONTRACT_REDEFINITION" in {
        str(item["code"]) for item in findings
    }


@pytest.mark.parametrize(
    ("protected_name", "expected_dedup_code"),
    (
        (
            "DomainSessionContext",
            "DOMAIN_FRAGMENTATION_SESSION_INFRASTRUCTURE_DUPLICATION",
        ),
        ("DomainOperationResult", "DOMAIN_FRAGMENTATION_OPERATION_RESULT_DUPLICATION"),
    ),
)
def test_protected_canonical_contract_deduped_by_component_duplication(
    protected_name: str,
    expected_dedup_code: str,
) -> None:
    """Names that match both contract and component rules produce the more
    specific component-duplication finding; contract redefinition is suppressed."""
    findings = analyze_fragmentation(
        f"class {protected_name}:\n    pass\n",
        "contracts.py",
    )
    codes = {str(item["code"]) for item in findings}
    assert expected_dedup_code in codes
    assert "DOMAIN_FRAGMENTATION_CONTRACT_REDEFINITION" not in codes


# ── BLOCKER-01 – Unrelated official base must NOT grant immunity ──────────────


@pytest.mark.parametrize(
    ("source", "expected_code"),
    (
        (
            (
                "from cmm.domains.pack import DomainPack\n"
                "class EvilMemoryStore(DomainPack):\n"
                "    pass\n"
            ),
            "DOMAIN_FRAGMENTATION_MEMORY_DUPLICATION",
        ),
        (
            (
                "from cmm.domains.pack import DomainPack\n"
                "class EvilPlanner(DomainPack):\n"
                "    pass\n"
            ),
            "DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION",
        ),
        (
            (
                "from cmm.domains.pack import DomainPack\n"
                "class EvilWorkflowEngine(DomainPack):\n"
                "    pass\n"
            ),
            "DOMAIN_FRAGMENTATION_WORKFLOW_ENGINE_DUPLICATION",
        ),
    ),
)
def test_unrelated_official_base_does_not_grant_protected_component_immunity(
    source: str,
    expected_code: str,
) -> None:
    """BLOCKER-01 regression: inheriting from an unrelated official CMM class
    must not grant immunity to a protected component name."""
    findings = analyze_fragmentation(source, "evil.py")
    codes = {str(item["code"]) for item in findings}
    assert expected_code in codes, (
        f"Expected {expected_code} to be blocked but found only {codes}"
    )


# ── MAJOR-01 8A – Recreated canonical global services ─────────────────────────


@pytest.mark.parametrize(
    ("source", "expected_code"),
    (
        (
            "class HealthDomainRegistry:\n    pass\n",
            "DOMAIN_FRAGMENTATION_REGISTRY_DUPLICATION",
        ),
        (
            "class HealthResourceRegistry:\n    pass\n",
            "DOMAIN_FRAGMENTATION_REGISTRY_DUPLICATION",
        ),
        (
            "class HealthWorkflowRegistry:\n    pass\n",
            "DOMAIN_FRAGMENTATION_REGISTRY_DUPLICATION",
        ),
        (
            "class HealthEventBus:\n    pass\n",
            "DOMAIN_FRAGMENTATION_EVENT_BUS_DUPLICATION",
        ),
        (
            "class HealthDomainResolver:\n    pass\n",
            "DOMAIN_FRAGMENTATION_RESOLVER_DUPLICATION",
        ),
        (
            "class HealthDomainLoader:\n    pass\n",
            "DOMAIN_FRAGMENTATION_LOADER_DUPLICATION",
        ),
        (
            "class HealthTraceStore:\n    pass\n",
            "DOMAIN_FRAGMENTATION_TRACE_STORE_DUPLICATION",
        ),
    ),
)
def test_recreated_canonical_global_service_is_blocked(
    source: str,
    expected_code: str,
) -> None:
    """MAJOR-01 8A regression: recreated canonical global services must be blocked."""
    findings = analyze_fragmentation(source, "service.py")
    codes = {str(item["code"]) for item in findings}
    assert expected_code in codes, f"Expected {expected_code} but found only {codes}"


# ── MAJOR-01 8B – Attribute and annotated policy bypass ───────────────────────


def test_attribute_policy_bypass_is_detected() -> None:
    """MAJOR-01 8B regression: dotted attribute bypass must be detected."""
    source = (
        "class Config:\n    pass\nconfig = Config()\nconfig.skip_validation = True\n"
    )
    findings = analyze_fragmentation(source, "config.py")
    codes = {str(item["code"]) for item in findings}
    assert "DOMAIN_FRAGMENTATION_POLICY_BYPASS" in codes


def test_annotated_policy_bypass_is_detected() -> None:
    """MAJOR-01 8B regression: annotated assignment bypass must be detected."""
    source = "skip_validation: bool = True\n"
    findings = analyze_fragmentation(source, "config.py")
    codes = {str(item["code"]) for item in findings}
    assert "DOMAIN_FRAGMENTATION_POLICY_BYPASS" in codes


def test_false_not_detected_as_policy_bypass() -> None:
    """False value must NOT be flagged as policy bypass."""
    source = "skip_validation = False\n"
    findings = analyze_fragmentation(source, "config.py")
    codes = {str(item["code"]) for item in findings}
    assert "DOMAIN_FRAGMENTATION_POLICY_BYPASS" not in codes


# ── MAJOR-01 8C – ImportFrom persistence bypass ───────────────────────────────


@pytest.mark.parametrize(
    "source",
    (
        "from shelve import open\n",
        "from sqlite3 import connect\n",
        "from sqlalchemy import create_engine\n",
    ),
)
def test_importfrom_persistence_is_detected(source: str) -> None:
    """MAJOR-01 8C regression: ImportFrom of protected persistence modules
    must be detected."""
    findings = analyze_fragmentation(source, "persist.py")
    codes = {str(item["code"]) for item in findings}
    assert "DOMAIN_FRAGMENTATION_DIRECT_PERSISTENCE_ACCESS" in codes


# ── MAJOR-02 9A – Arbitrary connect() must not imply persistence ──────────────


def test_arbitrary_client_connect_not_flagged() -> None:
    """MAJOR-02 9A regression: arbitrary client.connect() must not be flagged."""
    source = "def f(client):\n    return client.connect()\n"
    findings = analyze_fragmentation(source, "api.py")
    assert not any(
        f["code"] == "DOMAIN_FRAGMENTATION_DIRECT_PERSISTENCE_ACCESS" for f in findings
    )


def test_local_connect_not_flagged() -> None:
    """MAJOR-02 9A regression: locally defined connect() must not be flagged."""
    source = "def connect():\n    return True\nconnect()\n"
    findings = analyze_fragmentation(source, "api.py")
    assert not any(
        f["code"] == "DOMAIN_FRAGMENTATION_DIRECT_PERSISTENCE_ACCESS" for f in findings
    )


# ── MAJOR-02 9B – Arbitrary write_text/write_bytes must not imply FS write ────


def test_arbitrary_writer_write_text_not_flagged() -> None:
    """MAJOR-02 9B regression: writer.write_text() on non-Path must not be flagged."""
    source = "def f(writer):\n    writer.write_text('hello')\n"
    findings = analyze_fragmentation(source, "io.py")
    assert not any(f["code"] == "DOMAIN_FRAGMENTATION_DIRECT_WRITE" for f in findings)


def test_path_write_text_is_flagged() -> None:
    """MAJOR-02 9B regression: Path(...).write_text() must be flagged."""
    source = "from pathlib import Path\nPath('s.json').write_text('{}')\n"
    findings = analyze_fragmentation(source, "io.py")
    codes = {str(item["code"]) for item in findings}
    assert "DOMAIN_FRAGMENTATION_DIRECT_WRITE" in codes


def test_path_alias_write_bytes_is_flagged() -> None:
    """MAJOR-02 9B regression: aliased Path write_bytes must be flagged."""
    source = "from pathlib import Path as P\nP('s.json').write_bytes(b'x')\n"
    findings = analyze_fragmentation(source, "io.py")
    codes = {str(item["code"]) for item in findings}
    assert "DOMAIN_FRAGMENTATION_DIRECT_WRITE" in codes


@pytest.mark.parametrize(
    "source",
    (
        "import pathlib as pl\npl.Path('state.json').write_text('{}')\n",
        "import pathlib as pl\npl.Path('state.bin').write_bytes(b'x')\n",
    ),
)
def test_pathlib_module_alias_write_is_flagged(source: str) -> None:
    """An exact pathlib module alias must retain filesystem-write identity."""
    findings = analyze_fragmentation(source, "io.py")
    assert "DOMAIN_FRAGMENTATION_DIRECT_WRITE" in {
        str(item["code"]) for item in findings
    }


# ── MAJOR-02 9C – Shadowed open must not be treated as builtin ────────────────


def test_shadowed_open_not_flagged() -> None:
    """MAJOR-02 9C regression: shadowed local open() must not be flagged."""
    source = "def open(path, mode):\n    return None\nopen('x', 'w')\n"
    findings = analyze_fragmentation(source, "io.py")
    assert not any(f["code"] == "DOMAIN_FRAGMENTATION_DIRECT_WRITE" for f in findings)


def test_imported_open_not_flagged() -> None:
    """MAJOR-02 9C regression: imported non-builtin open must not be flagged."""
    source = "from some_module import open\nopen('x', 'w')\n"
    findings = analyze_fragmentation(source, "io.py")
    assert not any(f["code"] == "DOMAIN_FRAGMENTATION_DIRECT_WRITE" for f in findings)


def test_builtin_open_write_mode_is_flagged() -> None:
    """Builtin open() in write mode must remain blocked."""
    source = "open('x', 'w')\n"
    findings = analyze_fragmentation(source, "io.py")
    codes = {str(item["code"]) for item in findings}
    assert "DOMAIN_FRAGMENTATION_DIRECT_WRITE" in codes


@pytest.mark.parametrize(
    "mode",
    ("w", "a", "x", "r+"),
)
def test_builtins_open_alias_write_mode_is_flagged(mode: str) -> None:
    """Only aliases proven to be builtins.open inherit builtin write policy."""
    source = f"from builtins import open as bo\nbo('state.json', {mode!r})\n"
    findings = analyze_fragmentation(source, "io.py")
    assert "DOMAIN_FRAGMENTATION_DIRECT_WRITE" in {
        str(item["code"]) for item in findings
    }


def test_builtin_open_before_later_shadow_is_flagged() -> None:
    """A later module definition cannot shadow an earlier builtin open call."""
    source = "open('state.json', 'w')\ndef open(path, mode):\n    return None\n"
    findings = analyze_fragmentation(source, "io.py")
    assert "DOMAIN_FRAGMENTATION_DIRECT_WRITE" in {
        str(item["code"]) for item in findings
    }


# ── MAJOR-02 9D – Comments must not trigger backend-bypass regex ──────────────


def test_comment_backend_import_not_flagged() -> None:
    """MAJOR-02 9D regression: forbidden import text in a comment must not be flagged."""
    source = "# from cmm.memory.backend import Store\nx = 1\n"
    findings = analyze_fragmentation(source, "mod.py")
    assert not any(f["code"] == "DOMAIN_FRAGMENTATION_BACKEND_BYPASS" for f in findings)


def test_real_backend_import_is_flagged() -> None:
    """Real protected backend import must remain blocked."""
    source = "from cmm.memory.backend import Store\n"
    findings = analyze_fragmentation(source, "mod.py")
    codes = {str(item["code"]) for item in findings}
    assert "DOMAIN_FRAGMENTATION_BACKEND_BYPASS" in codes
