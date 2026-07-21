from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

import cmm.__main__ as cmm_main
from cmm.development.analyzer import ProjectAnalyzer
from cmm.development.models import DevelopmentPlan, PlanValidationError
from cmm.development.providers import (
    DeterministicPlanningProvider,
    OllamaPlanningProvider,
    PlanningProviderError,
    create_planning_provider,
)
from cmm.development.service import DevelopmentService


def _plan(goal: str, operations: list[dict], files: list[str] | None = None, **extra) -> dict:
    affected = files or list(dict.fromkeys(str(item["parameters"]["path"]) for item in operations))
    return {
        "goal": goal,
        "affected_files": affected,
        "operations": operations,
        "rationale": "Apply the requested semantic change.",
        "validations": ["python_ast", "python_compile"],
        "risks": [],
        **extra,
    }


def _operation(domain: str, operation_type: str, path: str, **parameters) -> dict:
    return {
        "domain": domain,
        "type": operation_type,
        "parameters": {"path": path, **parameters},
        "reason": "Required by the test goal.",
    }


def _service(plan: dict, *, answers: list[str] | None = None, output: list[str] | None = None) -> DevelopmentService:
    responses = iter(answers or [])
    return DevelopmentService(
        DeterministicPlanningProvider(plan),
        input_fn=lambda _prompt: next(responses),
        output_fn=(output if output is not None else []).append,
    )


def test_cli_parser_recognizes_develop_and_required_options() -> None:
    args = cmm_main.build_parser().parse_args(
        [
            "develop",
            "create class User in app.py",
            "--project",
            "/tmp/project",
            "--yes",
            "--provider",
            "deterministic",
            "--dry-run",
            "--max-files",
            "7",
        ]
    )

    assert args.command == "develop"
    assert args.project == Path("/tmp/project")
    assert args.yes is True
    assert args.provider == "deterministic"
    assert args.dry_run is True
    assert args.max_files == 7


def test_cli_develop_reports_missing_project(capsys: pytest.CaptureFixture[str]) -> None:
    code = cmm_main.main(
        ["develop", "create class User in app.py", "--project", "/definitely/missing/cmm-project", "--yes"]
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "Project path does not exist" in output


def test_deterministic_provider_and_structured_plan(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("", encoding="utf-8")
    context = ProjectAnalyzer().analyze(tmp_path, "create class User in app.py")

    payload = DeterministicPlanningProvider().generate_plan("create class User in app.py", context)
    plan = DevelopmentPlan.from_mapping(payload, "create class User in app.py")
    operations = plan.to_semantic_operations()

    assert plan.affected_files == ("app.py",)
    assert operations[0].type_id == "python.create_class"


def test_ollama_is_optional_and_loaded_lazily(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    context = ProjectAnalyzer().analyze(tmp_path, "goal")

    def missing(_name: str):
        raise ModuleNotFoundError("ollama")

    monkeypatch.setattr("cmm.development.providers.importlib.import_module", missing)
    provider = OllamaPlanningProvider()

    with pytest.raises(PlanningProviderError, match="optional 'ollama'"):
        provider.generate_plan("goal", context)


def test_provider_selection_is_configurable() -> None:
    assert isinstance(create_planning_provider("deterministic"), DeterministicPlanningProvider)
    assert isinstance(create_planning_provider("ollama:custom-model"), OllamaPlanningProvider)
    with pytest.raises(PlanValidationError, match="Unknown planning provider"):
        create_planning_provider("unknown")


def test_ollama_provider_accepts_dictionary_response(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    context = ProjectAnalyzer().analyze(tmp_path, "goal")
    payload = {
        "goal": "goal",
        "affected_files": ["app.py"],
        "operations": [{"domain": "python", "type": "create_class", "parameters": {
            "path": "app.py", "class_name": "User"
        }}],
        "rationale": "Create the requested class.",
    }

    class FakeOllama:
        @staticmethod
        def chat(**_kwargs):
            return {"message": {"content": json.dumps(payload)}}

    monkeypatch.setattr("cmm.development.providers.importlib.import_module", lambda _name: FakeOllama)

    assert OllamaPlanningProvider().generate_plan("goal", context) == payload


def test_project_analysis_indexes_real_symbols_and_excludes_caches(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "service.py").write_text(
        "import os\nfrom .models import User\nclass Service:\n    def run(self):\n        return os.getcwd()\n",
        encoding="utf-8",
    )
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "ignored.py").write_text("class Ignored: pass\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("class Broken(\n", encoding="utf-8")

    context = ProjectAnalyzer().analyze(tmp_path, "Service run", max_files=5)
    by_path = {item.path: item for item in context.files}

    assert context.total_python_files == 2
    assert by_path["pkg/service.py"].module == "pkg.service"
    assert by_path["pkg/service.py"].classes[0]["name"] == "Service"
    assert by_path["pkg/service.py"].classes[0]["methods"][0]["name"] == "run"
    assert by_path["pkg/service.py"].import_targets
    assert by_path["broken.py"].syntax_error


def test_project_analysis_limits_context_by_relevance(tmp_path: Path) -> None:
    for name in ("alpha", "beta", "target"):
        (tmp_path / f"{name}.py").write_text(f"class {name.title()}:\n    pass\n", encoding="utf-8")

    context = ProjectAnalyzer().analyze(tmp_path, "Target", max_files=1)

    assert context.truncated is True
    assert context.files[0].path == "target.py"


def test_project_analysis_does_not_follow_python_symlink_outside_root(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("class Secret:\n    pass\n", encoding="utf-8")
    (project / "linked.py").symlink_to(outside)

    context = ProjectAnalyzer().analyze(project, "Secret")

    assert context.total_python_files == 0
    assert context.files == ()


def test_invalid_free_text_plan_is_rejected(tmp_path: Path) -> None:
    class InvalidProvider:
        def generate_plan(self, goal, context):
            return "edit app.py"

    result = DevelopmentService(InvalidProvider(), output_fn=lambda _line: None).develop(
        "goal", tmp_path, yes=True
    )

    assert result.success is False
    assert "plan must be a mapping" in result.errors[0]


def test_dry_run_presents_plan_and_does_not_modify(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    original = "class Existing:\n    pass\n"
    path.write_text(original, encoding="utf-8")
    goal = "create User"
    output: list[str] = []
    plan = _plan(goal, [_operation("python", "create_class", "app.py", class_name="User")])

    result = _service(plan, output=output).develop(goal, tmp_path, dry_run=True)

    assert result.success is True
    assert result.dry_run is True
    assert result.approved is False
    assert path.read_text(encoding="utf-8") == original
    assert any("python.create_class" in line for line in output)


def test_human_rejection_does_not_modify(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    original = "class Existing:\n    pass\n"
    path.write_text(original, encoding="utf-8")
    goal = "create User"
    plan = _plan(goal, [_operation("python", "create_class", "app.py", class_name="User")])

    result = _service(plan, answers=["n"]).develop(goal, tmp_path)

    assert result.success is True
    assert result.approved is False
    assert path.read_text(encoding="utf-8") == original
    assert "rejected" in result.warnings[0].lower()


def test_yes_applies_sequential_operations_validates_and_generates_diff(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    path.write_text("", encoding="utf-8")
    goal = "create User with method"
    plan = _plan(
        goal,
        [
            _operation("python", "create_class", "app.py", class_name="User"),
            _operation(
                "python",
                "insert_method",
                "app.py",
                class_name="User",
                position="end",
                code="def hello(self):\n    return 'hello'",
            ),
        ],
    )

    result = _service(plan).develop(goal, tmp_path, yes=True)

    source = path.read_text(encoding="utf-8")
    assert result.success is True
    assert result.approved is True
    assert len(result.operations_executed) == 2
    assert result.modified_files == ("app.py",)
    assert "--- a/app.py" in result.diff
    assert "+class User:" in result.diff
    assert {record.name for record in result.validations} == {"python_ast", "python_compile"}
    assert all(record.success for record in result.validations)
    assert ast.parse(source)


def test_e2e_creates_file_then_modifies_it_semantically(tmp_path: Path) -> None:
    goal = "create a Python service"
    plan = _plan(
        goal,
        [
            _operation("filesystem", "write_file", "service.py", content="# generated\n"),
            _operation("python", "create_class", "service.py", class_name="Service"),
        ],
    )

    result = _service(plan).develop(goal, tmp_path, yes=True)

    assert result.success is True
    assert (tmp_path / "service.py").is_file()
    assert "class Service" in (tmp_path / "service.py").read_text(encoding="utf-8")
    assert len(result.operations_executed) == 2
    assert result.serialize()["diff"] == result.diff


def test_intermediate_failure_stops_and_rolls_back_all_files(tmp_path: Path) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first_original = "class First:\n    pass\n"
    second_original = "class Second:\n    pass\n"
    first.write_text(first_original, encoding="utf-8")
    second.write_text(second_original, encoding="utf-8")
    goal = "change two files"
    plan = _plan(
        goal,
        [
            _operation("python", "create_class", "first.py", class_name="Added"),
            _operation(
                "python",
                "rename_class",
                "second.py",
                class_name="Missing",
                new_name="Renamed",
            ),
            _operation("python", "create_class", "second.py", class_name="NeverExecuted"),
        ],
    )

    result = _service(plan).develop(goal, tmp_path, yes=True)

    assert result.success is False
    assert result.rollback_applied is True
    assert len(result.operations_executed) == 2
    assert first.read_text(encoding="utf-8") == first_original
    assert second.read_text(encoding="utf-8") == second_original
    assert "Added" in result.diff


def test_final_validation_failure_rolls_back_created_file(tmp_path: Path) -> None:
    goal = "write invalid Python"
    plan = _plan(
        goal,
        [_operation("filesystem", "write_file", "new/generated.py", content="class Broken(\n")],
    )

    result = _service(plan).develop(goal, tmp_path, yes=True)

    assert result.success is False
    assert result.rollback_applied is True
    assert not (tmp_path / "new" / "generated.py").exists()
    assert not (tmp_path / "new").exists()
    assert result.validations[0].success is False


def test_unexpected_post_execution_error_also_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "app.py"
    original = "class Existing:\n    pass\n"
    path.write_text(original, encoding="utf-8")
    goal = "unexpected validation error"
    plan = _plan(goal, [_operation("python", "create_class", "app.py", class_name="Added")])
    service = _service(plan)

    def fail_validation(*_args, **_kwargs):
        raise OSError("validation storage unavailable")

    monkeypatch.setattr(service, "_run_validations", fail_validation)
    result = service.develop(goal, tmp_path, yes=True)

    assert result.success is False
    assert result.rollback_applied is True
    assert path.read_text(encoding="utf-8") == original
    assert "validation storage unavailable" in result.errors[0]


@pytest.mark.parametrize("unsafe_path", ["../outside.py", "/tmp/outside.py"])
def test_paths_outside_project_are_rejected(tmp_path: Path, unsafe_path: str) -> None:
    goal = "unsafe"
    plan = _plan(
        goal,
        [_operation("filesystem", "write_file", unsafe_path, content="unsafe")],
    )

    result = _service(plan).develop(goal, tmp_path, yes=True)

    assert result.success is False
    assert "not allowed" in result.errors[0]


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    (project / "linked").symlink_to(outside, target_is_directory=True)
    goal = "unsafe symlink"
    plan = _plan(
        goal,
        [_operation("filesystem", "write_file", "linked/outside.py", content="unsafe")],
    )

    result = _service(plan).develop(goal, project, yes=True)

    assert result.success is False
    assert "escapes the project" in result.errors[0]
    assert not (outside / "outside.py").exists()


def test_unknown_validation_from_provider_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("", encoding="utf-8")
    goal = "bad validation"
    plan = _plan(
        goal,
        [_operation("python", "create_class", "app.py", class_name="User")],
        validations=["run-provider-shell"],
    )

    result = _service(plan).develop(goal, tmp_path, yes=True)

    assert result.success is False
    assert "Unsupported validation" in result.errors[0]
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == ""


def test_cli_e2e_yes_and_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "app.py"
    path.write_text("", encoding="utf-8")
    plan = {
        "affected_files": ["app.py"],
        "operations": [
            _operation("python", "create_class", "app.py", class_name="User")
        ],
        "rationale": "Create a class through the official CLI.",
        "validations": ["python_ast", "python_compile"],
        "risks": [],
    }
    goal = json.dumps(plan)

    dry_code = cmm_main.main(["develop", goal, "--project", str(tmp_path), "--dry-run"])
    assert dry_code == 0
    assert path.read_text(encoding="utf-8") == ""
    capsys.readouterr()

    apply_code = cmm_main.main(["develop", goal, "--project", str(tmp_path), "--yes"])
    output = capsys.readouterr().out

    assert apply_code == 0
    assert "class User" in path.read_text(encoding="utf-8")
    assert "Result: success" in output
    assert "Diff:" in output


def test_legacy_run_command_remains_available() -> None:
    args = cmm_main.build_parser().parse_args(["run", "goal", "--project", "."])
    assert args.command == "run"


def test_official_cli_runs_in_a_real_process_and_honors_dry_run(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    path.write_text("", encoding="utf-8")
    plan = _plan(
        "create User",
        [_operation("python", "create_class", "app.py", class_name="User")],
    )
    plan.pop("goal")
    goal = json.dumps(plan)

    command = [sys.executable, "-m", "cmm", "develop", goal, "--project", str(tmp_path), "--dry-run"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)

    assert completed.returncode == 0
    assert "Result: success" in completed.stdout
    assert "Dry run: yes" in completed.stdout
    assert path.read_text(encoding="utf-8") == ""
