import shutil
import subprocess
from pathlib import Path

import pytest

from cmm.validation.commit_gate.authorization import CommitAuthorization
from cmm.validation.commit_gate.enums import CommitGateReasonCode
from cmm.validation.commit_gate.evaluator import CommitGateEvaluator
from cmm.validation.commit_gate.service import ProvisionalCommitService
from cmm.validation.enums import ValidationStatus
from cmm.validation.policy import DEFAULT_VALIDATION_POLICIES
from cmm.validation.results import ValidationResult
from cmm.validation.steps import ValidationStepResult


def is_git_available() -> bool:
    return shutil.which("git") is not None


@pytest.mark.skipif(not is_git_available(), reason="Git executable is not available")
def test_integration_provisional_commit_flow(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Initialize Git repository
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "CMM OS Tests"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "cmm-os-tests@example.invalid"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )

    # Initial file & commit
    init_file = repo_dir / "README.md"
    init_file.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"], cwd=str(repo_dir), check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )

    # Modify validated file
    target_file = repo_dir / "src.py"
    target_file.write_text("def hello(): pass\n", encoding="utf-8")

    policy = DEFAULT_VALIDATION_POLICIES["small_change"]
    step_results = (
        ValidationStepResult(name="formatter_check", status=ValidationStatus.PASSED),
        ValidationStepResult(name="lint_check", status=ValidationStatus.PASSED),
        ValidationStepResult(name="syntax", status=ValidationStatus.PASSED),
        ValidationStepResult(name="ast", status=ValidationStatus.PASSED),
        ValidationStepResult(name="affected_tests", status=ValidationStatus.PASSED),
    )
    val_result = ValidationResult(
        id="val-integration-1",
        status=ValidationStatus.PASSED,
        policy="small_change",
        steps=step_results,
        changed_files=(Path("src.py"),),
        can_commit=True,
    )

    # Step 1: Evaluate Gate
    gate_res = CommitGateEvaluator.evaluate(val_result, policy)
    assert gate_res.allowed is True
    assert gate_res.commit_created is False

    # Step 2: Authorize
    auth = CommitAuthorization(
        authorized=True,
        actor="human:christian",
        reason="Add src.py module",
        validation_result_id="val-integration-1",
    )

    # Step 3: Create Provisional Commit
    service = ProvisionalCommitService()
    final_res = service.create_commit(
        gate_result=gate_res,
        authorization=auth,
        repository_path=repo_dir,
        files_to_commit=[Path("src.py")],
    )

    assert final_res.allowed is True
    assert final_res.commit_created is True
    assert final_res.commit_hash is not None
    assert len(final_res.commit_hash) > 0

    # Verify Git Log
    log_res = subprocess.run(
        ["git", "log", "-n", "1"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Authorized-By: human:christian" in log_res.stdout
    assert "Validation-ID: val-integration-1" in log_res.stdout
    assert "Add src.py module" in log_res.stdout


@pytest.mark.skipif(not is_git_available(), reason="Git executable is not available")
def test_integration_provisional_commit_unauthorized_staged_files(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo2"
    repo_dir.mkdir()

    # Initialize Git repository
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "CMM OS Tests"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "cmm-os-tests@example.invalid"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )

    # Initial file & commit
    init_file = repo_dir / "README.md"
    init_file.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"], cwd=str(repo_dir), check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )

    # Modify two files, but only one is authorized for validation
    val_file = repo_dir / "validated.py"
    val_file.write_text("a = 1\n", encoding="utf-8")
    unval_file = repo_dir / "unvalidated.py"
    unval_file.write_text("secret = 2\n", encoding="utf-8")

    # Pre-stage the unvalidated file manually
    subprocess.run(
        ["git", "add", "unvalidated.py"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )

    policy = DEFAULT_VALIDATION_POLICIES["small_change"]
    step_results = (
        ValidationStepResult(name="formatter_check", status=ValidationStatus.PASSED),
        ValidationStepResult(name="lint_check", status=ValidationStatus.PASSED),
        ValidationStepResult(name="syntax", status=ValidationStatus.PASSED),
        ValidationStepResult(name="ast", status=ValidationStatus.PASSED),
        ValidationStepResult(name="affected_tests", status=ValidationStatus.PASSED),
    )
    val_result = ValidationResult(
        id="val-integration-2",
        status=ValidationStatus.PASSED,
        policy="small_change",
        steps=step_results,
        changed_files=(Path("validated.py"),),
        can_commit=True,
    )

    gate_res = CommitGateEvaluator.evaluate(val_result, policy)
    auth = CommitAuthorization(
        authorized=True,
        actor="human:christian",
        validation_result_id="val-integration-2",
    )

    service = ProvisionalCommitService()
    final_res = service.create_commit(
        gate_result=gate_res,
        authorization=auth,
        repository_path=repo_dir,
        files_to_commit=[Path("validated.py")],
    )

    # Should deny commit because unvalidated.py is staged outside authorized scope!
    assert final_res.allowed is False
    assert final_res.commit_created is False
    assert any(
        r.code == CommitGateReasonCode.UNAUTHORIZED_FILES_STAGED
        for r in final_res.reasons
    )
