"""Phase 9.15 – Checkpoints and Transaction Boundaries Test Suite.

Comprehensive test suite covering contracts, repository invariants, checkpoint creation,
integrity verification, transaction boundaries, state restoration, validation integration,
concurrency, security, and runtime execution adapter integration.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from cmm.agent_runtime import (
    AgentExecutionAdapter,
    AgentOperationExecutionStatus,
    AgentOperationRequest,
    AgentValidationDecision,
    AgentValidationResult,
    AgentValidationStage,
    BackupRequiredError,
    Checkpoint,
    CheckpointAlreadyExistsError,
    CheckpointCreationError,
    CheckpointCreationRequest,
    CheckpointExpiredError,
    CheckpointIntegrityStatus,
    CheckpointIntegrityVerifier,
    CheckpointInvalidError,
    CheckpointManager,
    CheckpointNotFoundError,
    CheckpointRepositoryError,
    CheckpointRestorationManager,
    CheckpointRestorationRequest,
    CheckpointStatus,
    CompensationAction,
    InMemoryAgentOperationRegistry,
    InMemoryAgentRuntimeRepository,
    InMemoryBackupProvider,
    InMemoryCheckpointRepository,
    InMemoryGitStateProvider,
    InMemoryKnowledgeStateProvider,
    InMemoryMemoryStateProvider,
    InMemoryResourceVersionProvider,
    InMemoryStorageSnapshotProvider,
    IrreversibleOperationError,
    OperationDescriptor,
    OperationRecoveryKind,
    RestorationStatus,
    RuntimeLockManager,
    TransactionBoundaryError,
    TransactionBoundaryKind,
    TransactionBoundaryResolver,
    TransactionManager,
    TransactionOperation,
    TransactionStateError,
    TransactionStatus,
    compute_checkpoint_fingerprint,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── 1. Contracts & Immutability Tests ──────────────────────────────────────────


def test_checkpoint_contract_immutability():
    now = _now_iso()
    cp = Checkpoint(
        checkpoint_id="cp-001",
        agent_run_id="run-001",
        goal_id="goal-001",
        workflow_id="wf-001",
        iteration_id="task-001",
        name="test_checkpoint",
        status=CheckpointStatus.ACTIVE,
        transaction_boundary_id="txb-001",
        resource_versions={"file1.py": "v1"},
        git_state={"commit": "abc"},
        storage_snapshot_id="snap-1",
        memory_state_version="mem-1",
        knowledge_state_version="know-1",
        reversible_operations=("op1",),
        compensable_operations=(),
        irreversible_effects=(),
        locks=("lock-1",),
        fingerprint="fp123",
        created_at=now,
    )

    assert cp.checkpoint_id == "cp-001"
    assert cp.status == CheckpointStatus.ACTIVE.value

    with pytest.raises(FrozenInstanceError):
        cp.status = CheckpointStatus.RESTORED.value  # type: ignore[misc]

    with pytest.raises(TypeError):
        cp.resource_versions["file2.py"] = "v2"  # type: ignore[index]


def test_checkpoint_invalid_initialization():
    now = _now_iso()
    with pytest.raises(CheckpointInvalidError):
        Checkpoint(
            checkpoint_id="",
            agent_run_id="run-001",
            goal_id="goal-001",
            workflow_id="wf-001",
            iteration_id="task-001",
            name="invalid",
            status=CheckpointStatus.CREATING,
            transaction_boundary_id="txb-001",
            resource_versions={},
            git_state={},
            storage_snapshot_id=None,
            memory_state_version=None,
            knowledge_state_version=None,
            reversible_operations=(),
            compensable_operations=(),
            irreversible_effects=(),
            locks=(),
            fingerprint="fp",
            created_at=now,
        )


def test_checkpoint_to_dict_and_serialization():
    now = _now_iso()
    cp = Checkpoint(
        checkpoint_id="cp-002",
        agent_run_id="run-002",
        goal_id="goal-002",
        workflow_id="wf-002",
        iteration_id="task-002",
        name="serialize_test",
        status=CheckpointStatus.ACTIVE,
        transaction_boundary_id="txb-002",
        resource_versions={"res1": "v10"},
        git_state={"branch": "main"},
        storage_snapshot_id=None,
        memory_state_version=None,
        knowledge_state_version=None,
        reversible_operations=("op_a",),
        compensable_operations=(),
        irreversible_effects=(),
        locks=(),
        fingerprint="fp_hash",
        created_at=now,
    )
    d = cp.to_dict()
    assert d["checkpoint_id"] == "cp-002"
    assert d["status"] == CheckpointStatus.ACTIVE.value
    serialized = json.dumps(d)
    assert "cp-002" in serialized


def test_compute_checkpoint_fingerprint_deterministic():
    now = _now_iso()
    fp1 = compute_checkpoint_fingerprint(
        checkpoint_id="cp-1",
        agent_run_id="run-1",
        goal_id="g1",
        workflow_id="w1",
        iteration_id="i1",
        transaction_boundary_id="txb-1",
        resource_versions={"a": "1", "b": "2"},
        git_state={"commit": "xyz"},
        storage_snapshot_id="snap-1",
        created_at=now,
    )
    fp2 = compute_checkpoint_fingerprint(
        checkpoint_id="cp-1",
        agent_run_id="run-1",
        goal_id="g1",
        workflow_id="w1",
        iteration_id="i1",
        transaction_boundary_id="txb-1",
        resource_versions={"b": "2", "a": "1"},  # order reversed
        git_state={"commit": "xyz"},
        storage_snapshot_id="snap-1",
        created_at=now,
    )
    assert fp1 == fp2
    assert len(fp1) == 64


# ── 2. Checkpoint Repository Tests ─────────────────────────────────────────────


def test_repository_save_and_get():
    repo = InMemoryCheckpointRepository()
    now = _now_iso()
    cp = Checkpoint(
        checkpoint_id="cp-repo-1",
        agent_run_id="run-repo",
        goal_id="g",
        workflow_id="w",
        iteration_id="i",
        name="test",
        status=CheckpointStatus.ACTIVE,
        transaction_boundary_id="txb",
        resource_versions={},
        git_state={},
        storage_snapshot_id=None,
        memory_state_version=None,
        knowledge_state_version=None,
        reversible_operations=(),
        compensable_operations=(),
        irreversible_effects=(),
        locks=(),
        fingerprint="fp1",
        created_at=now,
    )
    saved = repo.save_checkpoint(cp)
    assert saved.checkpoint_id == "cp-repo-1"

    retrieved = repo.get_checkpoint("cp-repo-1")
    assert retrieved.checkpoint_id == "cp-repo-1"


def test_repository_idempotency_same_fingerprint():
    repo = InMemoryCheckpointRepository()
    now = _now_iso()
    cp = Checkpoint(
        checkpoint_id="cp-idemp-1",
        agent_run_id="run-idemp",
        goal_id="g",
        workflow_id="w",
        iteration_id="i",
        name="test",
        status=CheckpointStatus.ACTIVE,
        transaction_boundary_id="txb",
        resource_versions={},
        git_state={},
        storage_snapshot_id=None,
        memory_state_version=None,
        knowledge_state_version=None,
        reversible_operations=(),
        compensable_operations=(),
        irreversible_effects=(),
        locks=(),
        fingerprint="fp_same",
        created_at=now,
    )
    r1 = repo.save_checkpoint(cp, idempotency_key="key-123")
    r2 = repo.save_checkpoint(cp, idempotency_key="key-123")
    assert r1.checkpoint_id == r2.checkpoint_id


def test_repository_idempotency_conflicting_fingerprint():
    repo = InMemoryCheckpointRepository()
    now = _now_iso()
    cp1 = Checkpoint(
        checkpoint_id="cp-idemp-1",
        agent_run_id="run-idemp",
        goal_id="g",
        workflow_id="w",
        iteration_id="i",
        name="test1",
        status=CheckpointStatus.ACTIVE,
        transaction_boundary_id="txb",
        resource_versions={},
        git_state={},
        storage_snapshot_id=None,
        memory_state_version=None,
        knowledge_state_version=None,
        reversible_operations=(),
        compensable_operations=(),
        irreversible_effects=(),
        locks=(),
        fingerprint="fp1",
        created_at=now,
    )
    cp2 = Checkpoint(
        checkpoint_id="cp-idemp-2",
        agent_run_id="run-idemp",
        goal_id="g",
        workflow_id="w",
        iteration_id="i",
        name="test2",
        status=CheckpointStatus.ACTIVE,
        transaction_boundary_id="txb",
        resource_versions={},
        git_state={},
        storage_snapshot_id=None,
        memory_state_version=None,
        knowledge_state_version=None,
        reversible_operations=(),
        compensable_operations=(),
        irreversible_effects=(),
        locks=(),
        fingerprint="fp2",
        created_at=now,
    )
    repo.save_checkpoint(cp1, idempotency_key="key-same")
    with pytest.raises(CheckpointAlreadyExistsError):
        repo.save_checkpoint(cp2, idempotency_key="key-same")


def test_repository_not_found_raises():
    repo = InMemoryCheckpointRepository()
    with pytest.raises(CheckpointNotFoundError):
        repo.get_checkpoint("cp-nonexistent")


def test_repository_valid_status_transition():
    repo = InMemoryCheckpointRepository()
    now = _now_iso()
    cp = Checkpoint(
        checkpoint_id="cp-trans-1",
        agent_run_id="run-trans",
        goal_id="g",
        workflow_id="w",
        iteration_id="i",
        name="test",
        status=CheckpointStatus.CREATING,
        transaction_boundary_id="txb",
        resource_versions={},
        git_state={},
        storage_snapshot_id=None,
        memory_state_version=None,
        knowledge_state_version=None,
        reversible_operations=(),
        compensable_operations=(),
        irreversible_effects=(),
        locks=(),
        fingerprint="fp",
        created_at=now,
    )
    repo.save_checkpoint(cp)

    # CREATING -> ACTIVE
    active = repo.update_status("cp-trans-1", CheckpointStatus.ACTIVE)
    assert active.status == CheckpointStatus.ACTIVE.value

    # ACTIVE -> RESTORING
    restoring = repo.update_status("cp-trans-1", CheckpointStatus.RESTORING)
    assert restoring.status == CheckpointStatus.RESTORING.value

    # RESTORING -> RESTORED
    restored = repo.update_status("cp-trans-1", CheckpointStatus.RESTORED)
    assert restored.status == CheckpointStatus.RESTORED.value


def test_repository_invalid_status_transition_raises():
    repo = InMemoryCheckpointRepository()
    now = _now_iso()
    cp = Checkpoint(
        checkpoint_id="cp-final-1",
        agent_run_id="run-final",
        goal_id="g",
        workflow_id="w",
        iteration_id="i",
        name="test",
        status=CheckpointStatus.RESTORED,
        transaction_boundary_id="txb",
        resource_versions={},
        git_state={},
        storage_snapshot_id=None,
        memory_state_version=None,
        knowledge_state_version=None,
        reversible_operations=(),
        compensable_operations=(),
        irreversible_effects=(),
        locks=(),
        fingerprint="fp",
        created_at=now,
    )
    repo.save_checkpoint(cp)
    with pytest.raises(CheckpointRepositoryError):
        repo.update_status("cp-final-1", CheckpointStatus.ACTIVE)


# ── 3. Checkpoint Manager & Creation Tests ────────────────────────────────────


def test_checkpoint_manager_create_simple():
    res_provider = InMemoryResourceVersionProvider({"file1.py": "v1.0"})
    git_provider = InMemoryGitStateProvider()
    mgr = CheckpointManager(resource_provider=res_provider, git_provider=git_provider)

    req = CheckpointCreationRequest(
        agent_run_id="run-mgr-1",
        goal_id="goal-mgr",
        workflow_id="wf-mgr",
        iteration_id="task-mgr",
        name="cp_simple",
        transaction_boundary_id="txb-mgr",
        resource_keys=("file1.py",),
    )

    result = mgr.create_checkpoint(req)
    assert result.success is True
    assert result.status == CheckpointStatus.ACTIVE.value
    assert result.checkpoint is not None
    assert result.checkpoint.resource_versions["file1.py"] == "v1.0"


def test_checkpoint_manager_backup_required_missing_provider():
    mgr = CheckpointManager()  # No backup provider
    req = CheckpointCreationRequest(
        agent_run_id="run-bk",
        goal_id="g",
        workflow_id="w",
        iteration_id="i",
        name="cp_backup",
        transaction_boundary_id="txb",
        requires_backup=True,
    )

    with pytest.raises(BackupRequiredError):
        mgr.create_checkpoint(req)


def test_checkpoint_manager_backup_required_success():
    bk_provider = InMemoryBackupProvider()
    mgr = CheckpointManager(backup_provider=bk_provider)
    req = CheckpointCreationRequest(
        agent_run_id="run-bk2",
        goal_id="g",
        workflow_id="w",
        iteration_id="i",
        name="cp_backup2",
        transaction_boundary_id="txb",
        requires_backup=True,
    )
    res = mgr.create_checkpoint(req)
    assert res.success is True


# ── 4. Checkpoint Integrity Verifier Tests ─────────────────────────────────────


def test_integrity_verifier_valid():
    res_provider = InMemoryResourceVersionProvider({"f1": "v1"})
    git_provider = InMemoryGitStateProvider()
    verifier = CheckpointIntegrityVerifier(
        resource_provider=res_provider, git_provider=git_provider
    )

    now = _now_iso()
    fp = compute_checkpoint_fingerprint(
        checkpoint_id="cp-int-1",
        agent_run_id="run-1",
        goal_id="g1",
        workflow_id="w1",
        iteration_id="i1",
        transaction_boundary_id="txb-1",
        resource_versions={"f1": "v1"},
        git_state={"commit_hash": "abc1234", "branch": "main", "is_clean": True},
        storage_snapshot_id=None,
        created_at=now,
    )

    cp = Checkpoint(
        checkpoint_id="cp-int-1",
        agent_run_id="run-1",
        goal_id="g1",
        workflow_id="w1",
        iteration_id="i1",
        name="int_test",
        status=CheckpointStatus.ACTIVE,
        transaction_boundary_id="txb-1",
        resource_versions={"f1": "v1"},
        git_state={"commit_hash": "abc1234", "branch": "main", "is_clean": True},
        storage_snapshot_id=None,
        memory_state_version=None,
        knowledge_state_version=None,
        reversible_operations=(),
        compensable_operations=(),
        irreversible_effects=(),
        locks=(),
        fingerprint=fp,
        created_at=now,
    )

    integrity = verifier.verify(cp)
    assert integrity.status == CheckpointIntegrityStatus.VALID.value
    assert integrity.fingerprint_valid is True
    assert integrity.resources_valid is True


def test_integrity_verifier_corrupted_fingerprint():
    verifier = CheckpointIntegrityVerifier()
    now = _now_iso()
    cp = Checkpoint(
        checkpoint_id="cp-int-bad",
        agent_run_id="run-1",
        goal_id="g1",
        workflow_id="w1",
        iteration_id="i1",
        name="int_test",
        status=CheckpointStatus.ACTIVE,
        transaction_boundary_id="txb-1",
        resource_versions={},
        git_state={},
        storage_snapshot_id=None,
        memory_state_version=None,
        knowledge_state_version=None,
        reversible_operations=(),
        compensable_operations=(),
        irreversible_effects=(),
        locks=(),
        fingerprint="corrupted_fingerprint_hash",
        created_at=now,
    )
    integrity = verifier.verify(cp)
    assert integrity.status == CheckpointIntegrityStatus.CORRUPTED.value
    assert integrity.fingerprint_valid is False


def test_integrity_verifier_expired_checkpoint():
    verifier = CheckpointIntegrityVerifier()
    past = (datetime.now(timezone.utc) - timedelta(seconds=100)).isoformat()
    cp = Checkpoint(
        checkpoint_id="cp-int-exp",
        agent_run_id="run-1",
        goal_id="g1",
        workflow_id="w1",
        iteration_id="i1",
        name="exp_test",
        status=CheckpointStatus.ACTIVE,
        transaction_boundary_id="txb-1",
        resource_versions={},
        git_state={},
        storage_snapshot_id=None,
        memory_state_version=None,
        knowledge_state_version=None,
        reversible_operations=(),
        compensable_operations=(),
        irreversible_effects=(),
        locks=(),
        fingerprint="fp",
        created_at=past,
        expires_at=past,
    )
    integrity = verifier.verify(cp)
    assert integrity.status in (
        CheckpointIntegrityStatus.STALE.value,
        CheckpointIntegrityStatus.CORRUPTED.value,
    )


# ── 5. Transaction Boundary & Transaction Manager Tests ───────────────────────


def test_transaction_boundary_resolver_atomic():
    bnd = TransactionBoundaryResolver.resolve_boundary(
        agent_run_id="run-tx-1",
        kind=TransactionBoundaryKind.ATOMIC,
        name="tx_atomic",
    )
    assert bnd.kind == TransactionBoundaryKind.ATOMIC.value


def test_transaction_boundary_atomic_forbidden_irreversible():
    op = TransactionOperation(
        operation_id="op-1",
        transaction_boundary_id="txb-1",
        operation_name="delete_db",
        recovery_kind=OperationRecoveryKind.IRREVERSIBLE,
    )
    with pytest.raises(TransactionBoundaryError):
        TransactionBoundaryResolver.resolve_boundary(
            agent_run_id="run-tx-1",
            kind=TransactionBoundaryKind.ATOMIC,
            name="tx_atomic",
            operations=(op,),
        )


def test_transaction_boundary_irreversible_without_approval():
    op = TransactionOperation(
        operation_id="op-2",
        transaction_boundary_id="txb-2",
        operation_name="drop_table",
        recovery_kind=OperationRecoveryKind.IRREVERSIBLE,
    )
    with pytest.raises(IrreversibleOperationError):
        TransactionBoundaryResolver.resolve_boundary(
            agent_run_id="run-tx-2",
            kind=TransactionBoundaryKind.IRREVERSIBLE_WITH_APPROVAL,
            name="tx_irrev",
            has_approval=False,
            operations=(op,),
        )


def test_transaction_manager_start_and_commit():
    cp_mgr = CheckpointManager()
    tx_mgr = TransactionManager(cp_mgr)

    bnd, cp_id = tx_mgr.start_transaction(
        agent_run_id="run-tm-1",
        goal_id="g1",
        workflow_id="w1",
        iteration_id="i1",
        kind=TransactionBoundaryKind.ATOMIC,
        name="tx_test",
    )

    assert bnd.status == TransactionStatus.ACTIVE.value
    assert cp_id is not None

    committed = tx_mgr.commit(bnd.id)
    assert committed.status == TransactionStatus.COMMITTED.value


def test_transaction_manager_commit_invalid_state_raises():
    cp_mgr = CheckpointManager()
    tx_mgr = TransactionManager(cp_mgr)

    bnd, _ = tx_mgr.start_transaction(
        agent_run_id="run-tm-2",
        goal_id="g1",
        workflow_id="w1",
        iteration_id="i1",
        kind=TransactionBoundaryKind.ATOMIC,
        name="tx_test2",
    )

    tx_mgr.commit(bnd.id)
    # Double commit
    with pytest.raises(TransactionStateError):
        tx_mgr.commit(bnd.id)


# ── 6. Checkpoint Restoration Manager Tests ───────────────────────────────────


def test_restoration_manager_success():
    res_provider = InMemoryResourceVersionProvider({"res1": "v1.0"})
    git_provider = InMemoryGitStateProvider()
    cp_mgr = CheckpointManager(
        resource_provider=res_provider, git_provider=git_provider
    )

    req = CheckpointCreationRequest(
        agent_run_id="run-rest-1",
        goal_id="g1",
        workflow_id="w1",
        iteration_id="i1",
        name="restore_cp",
        transaction_boundary_id="txb-r1",
        resource_keys=("res1",),
    )
    cp_res = cp_mgr.create_checkpoint(req)

    # Mutate resource version
    res_provider.set_version("res1", "v2.0")

    rest_mgr = CheckpointRestorationManager(
        repository=cp_mgr.repository,
        resource_provider=res_provider,
        git_provider=git_provider,
    )

    rest_req = CheckpointRestorationRequest(
        checkpoint_id=cp_res.checkpoint_id,
        agent_run_id="run-rest-1",
        reason="post-execution failure",
    )

    res = rest_mgr.restore_checkpoint(rest_req, original_error="Validation failure")

    assert res.success is True
    assert res.status == RestorationStatus.RESTORED.value
    assert res.original_error == "Validation failure"
    assert res.restoration_error is None
    assert res_provider.capture_version("res1") == "v1.0"


def test_restoration_manager_expired_checkpoint_raises():
    repo = InMemoryCheckpointRepository()
    past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    cp = Checkpoint(
        checkpoint_id="cp-exp-rest",
        agent_run_id="run-exp",
        goal_id="g",
        workflow_id="w",
        iteration_id="i",
        name="exp",
        status=CheckpointStatus.EXPIRED,
        transaction_boundary_id="txb",
        resource_versions={},
        git_state={},
        storage_snapshot_id=None,
        memory_state_version=None,
        knowledge_state_version=None,
        reversible_operations=(),
        compensable_operations=(),
        irreversible_effects=(),
        locks=(),
        fingerprint="fp",
        created_at=past,
    )
    repo.save_checkpoint(cp)

    rest_mgr = CheckpointRestorationManager(repository=repo)
    rest_req = CheckpointRestorationRequest(
        checkpoint_id="cp-exp-rest", agent_run_id="run-exp"
    )

    with pytest.raises(CheckpointExpiredError):
        rest_mgr.restore_checkpoint(rest_req)


def test_restoration_manager_preserves_original_and_restoration_errors():
    class BrokenGitProvider:
        def capture_git_state(self):
            return {"commit_hash": "abc"}

        def restore_git_state(self, state):
            raise RuntimeError("Git disk I/O error during restore")

    broken_git = BrokenGitProvider()
    res_provider = InMemoryResourceVersionProvider({"res1": "v1.0"})
    cp_mgr = CheckpointManager(
        resource_provider=res_provider,
        git_provider=broken_git,  # type: ignore[arg-type]
    )
    cp_res = cp_mgr.create_checkpoint(
        CheckpointCreationRequest(
            agent_run_id="run-err-pres",
            goal_id="g",
            workflow_id="w",
            iteration_id="i",
            name="cp_err",
            transaction_boundary_id="txb",
            resource_keys=("res1",),
        )
    )

    rest_mgr = CheckpointRestorationManager(
        repository=cp_mgr.repository,
        resource_provider=res_provider,
        git_provider=broken_git,  # type: ignore[arg-type]
    )

    rest_req = CheckpointRestorationRequest(
        checkpoint_id=cp_res.checkpoint_id,
        agent_run_id="run-err-pres",
    )

    res = rest_mgr.restore_checkpoint(
        rest_req, original_error="AssertionError in unit test"
    )

    assert res.success is False
    assert res.original_error == "AssertionError in unit test"
    assert res.restoration_error is not None
    assert "Git disk I/O error" in res.restoration_error


# ── 7. Operation Execution Adapter Integration Tests ─────────────────────────


def test_operation_execution_adapter_checkpoint_creation():
    reg = InMemoryAgentOperationRegistry()
    desc = OperationDescriptor(
        name="file_write",
        version="1",
        description="Writes to a file",
        reversible=True,
    )
    reg.register(desc)

    cp_mgr = CheckpointManager()

    def dummy_exec(req):
        return {"success": True, "effects": ("file written",)}

    adapter = AgentExecutionAdapter(
        registry=reg,
        execution_delegate=dummy_exec,
        checkpoint_manager=cp_mgr,
    )

    op_req = AgentOperationRequest(
        id="op-req-1",
        agent_run_id="run-op-1",
        workflow_id="wf-1",
        task_id="task-1",
        operation_name="file_write",
        idempotency_key="key-op-1",
        metadata={"requires_checkpoint": True},
    )

    result = adapter.execute(op_req)
    assert result.success is True
    assert result.status == AgentOperationExecutionStatus.COMPLETED
    assert result.checkpoint_id is not None


def test_operation_execution_adapter_post_validation_failure_preserves_checkpoint():
    reg = InMemoryAgentOperationRegistry()
    desc = OperationDescriptor(
        name="db_update",
        version="1",
        description="Updates database",
        reversible=True,
    )
    reg.register(desc)

    cp_mgr = CheckpointManager()

    class FailingValidationAdapter:
        def validate(self, request, exec_context=None):
            if request.stage == AgentValidationStage.PRE_EXECUTION:
                return AgentValidationResult(
                    request_id="val-res-pre",
                    stage=AgentValidationStage.PRE_EXECUTION,
                    status="passed",
                    decision=AgentValidationDecision.CONTINUE,
                    run_id=request.run_id,
                    iteration_id=request.iteration_id,
                    operation_request_id=request.operation_request_id,
                )
            return AgentValidationResult(
                request_id="val-res-fail",
                stage=AgentValidationStage.POST_EXECUTION,
                status="failed",
                decision=AgentValidationDecision.ROLLBACK,
                run_id=request.run_id,
                iteration_id=request.iteration_id,
                operation_request_id=request.operation_request_id,
            )

    def dummy_exec(req):
        return {"success": True}

    adapter = AgentExecutionAdapter(
        registry=reg,
        execution_delegate=dummy_exec,
        checkpoint_manager=cp_mgr,
        validation_adapter=FailingValidationAdapter(),  # type: ignore[arg-type]
    )

    op_req = AgentOperationRequest(
        id="op-req-2",
        agent_run_id="run-op-2",
        workflow_id="wf-2",
        task_id="task-2",
        operation_name="db_update",
        idempotency_key="key-op-2",
        metadata={"requires_checkpoint": True},
    )

    result = adapter.execute(op_req)
    assert result.success is False
    assert result.status == AgentOperationExecutionStatus.VALIDATION_FAILED
    assert result.checkpoint_id is not None

    # Verify Checkpoint is preserved in ACTIVE state in repository
    cp = cp_mgr.repository.get_checkpoint(result.checkpoint_id)
    assert cp.status == CheckpointStatus.ACTIVE.value


# ── 8. Security & Boundary Rule Tests ──────────────────────────────────────────


def test_security_no_shell_or_subprocess():
    """Verify that Checkpoint ecosystem modules do not contain shell/subprocess calls."""
    import inspect

    import cmm.agent_runtime.checkpoint_integrations as ci
    import cmm.agent_runtime.checkpoint_manager as cm
    import cmm.agent_runtime.checkpoint_restoration as cr

    for module in (ci, cm, cr):
        source = inspect.getsource(module)
        assert "import subprocess" not in source
        assert "subprocess.Popen" not in source
        assert "subprocess.run" not in source
        assert "shell=True" not in source
        assert "os.system" not in source
        assert "eval(" not in source
        assert "exec(" not in source


# ── 9. Comprehensive Multi-Scenario Test Matrix ──────────────────────────────


@pytest.mark.parametrize(
    "kind",
    [
        TransactionBoundaryKind.ATOMIC,
        TransactionBoundaryKind.COMPENSABLE,
        TransactionBoundaryKind.CHECKPOINT_SEQUENCE,
        TransactionBoundaryKind.INDEPENDENT,
        TransactionBoundaryKind.IRREVERSIBLE_WITH_APPROVAL,
    ],
)
def test_all_transaction_kinds_resolution(kind):
    bnd = TransactionBoundaryResolver.resolve_boundary(
        agent_run_id="run-matrix",
        kind=kind,
        name=f"tx_{kind.value}",
        has_approval=True,
    )
    assert bnd.kind == kind.value


def test_full_transaction_checkpoint_restoration_lifecycle():
    # 1. Setup Providers
    res_provider = InMemoryResourceVersionProvider({"db.json": "v1.0"})
    git_provider = InMemoryGitStateProvider()
    cp_mgr = CheckpointManager(
        resource_provider=res_provider, git_provider=git_provider
    )
    tx_mgr = TransactionManager(cp_mgr)

    # 2. Start Transaction
    bnd, cp_id = tx_mgr.start_transaction(
        agent_run_id="run-lifecycle",
        goal_id="g1",
        workflow_id="w1",
        iteration_id="i1",
        kind=TransactionBoundaryKind.ATOMIC,
        name="full_lifecycle",
        resource_keys=("db.json",),
    )
    assert cp_id is not None

    # 3. Register Operation
    tx_mgr.register_operation(
        transaction_boundary_id=bnd.id,
        operation_name="db_json_write",
        recovery_kind=OperationRecoveryKind.REVERSIBLE,
    )

    # 4. Simulate Failure & Mutate State
    res_provider.set_version("db.json", "v2.0_corrupted")

    # 5. Mark Rollback Started
    tx_mgr.mark_rollback_started(bnd.id)

    # 6. Execute Restoration
    rest_mgr = CheckpointRestorationManager(
        repository=cp_mgr.repository,
        resource_provider=res_provider,
        git_provider=git_provider,
    )

    rest_res = rest_mgr.restore_checkpoint(
        CheckpointRestorationRequest(checkpoint_id=cp_id, agent_run_id="run-lifecycle"),
        original_error="Uncaught Exception in task worker",
    )

    assert rest_res.success is True

    # 7. Mark Rolled Back
    final_bnd = tx_mgr.mark_rolled_back(bnd.id)
    assert final_bnd.status == TransactionStatus.ROLLED_BACK.value
    assert res_provider.capture_version("db.json") == "v1.0"


# ── 10. Audit Coverage Gap Tests ───────────────────────────────────────────────


def test_checkpoint_manager_captures_storage_memory_and_knowledge():
    res_provider = InMemoryResourceVersionProvider({"res1": "v1.0"})
    git_provider = InMemoryGitStateProvider()
    storage_provider = InMemoryStorageSnapshotProvider()
    memory_provider = InMemoryMemoryStateProvider()
    knowledge_provider = InMemoryKnowledgeStateProvider()

    memory_provider.restore_memory_version("run-multi", "mem-v1")
    knowledge_provider.restore_knowledge_version("goal-multi", "know-v1")

    mgr = CheckpointManager(
        resource_provider=res_provider,
        git_provider=git_provider,
        storage_provider=storage_provider,
        memory_provider=memory_provider,
        knowledge_provider=knowledge_provider,
    )

    req = CheckpointCreationRequest(
        agent_run_id="run-multi",
        goal_id="goal-multi",
        workflow_id="wf-multi",
        iteration_id="task-multi",
        name="cp_multi_domain",
        transaction_boundary_id="txb-multi",
        resource_keys=("res1",),
    )

    result = mgr.create_checkpoint(req)
    assert result.success is True
    cp = result.checkpoint

    # Verify all 5 state domains are bound correctly
    assert cp.resource_versions["res1"] == "v1.0"
    assert "commit_hash" in cp.git_state
    assert cp.storage_snapshot_id is not None
    assert cp.memory_state_version == "mem-v1"
    assert cp.knowledge_state_version == "know-v1"

    # Verify fingerprint & integrity VALID
    verifier = CheckpointIntegrityVerifier(
        resource_provider=res_provider,
        git_provider=git_provider,
        storage_provider=storage_provider,
        memory_provider=memory_provider,
        knowledge_provider=knowledge_provider,
    )
    integrity = verifier.verify(cp)
    assert integrity.status == CheckpointIntegrityStatus.VALID.value


def test_checkpoint_manager_multidomain_capture_failure_is_not_activated():
    class FailingMemoryProvider:
        def capture_memory_version(self, agent_run_id: str) -> str:
            raise RuntimeError("Memory store connection timeout")

    lock_repo = InMemoryAgentRuntimeRepository()
    lock_mgr = RuntimeLockManager(lock_repo)
    res_provider = InMemoryResourceVersionProvider({"res1": "v1.0"})
    git_provider = InMemoryGitStateProvider()

    mgr = CheckpointManager(
        lock_manager=lock_mgr,
        resource_provider=res_provider,
        git_provider=git_provider,
        memory_provider=FailingMemoryProvider(),  # type: ignore[arg-type]
    )

    req = CheckpointCreationRequest(
        agent_run_id="run-fail-cap",
        goal_id="g1",
        workflow_id="w1",
        iteration_id="i1",
        name="cp_fail_cap",
        transaction_boundary_id="txb1",
        resource_keys=("res1",),
    )

    with pytest.raises(CheckpointCreationError) as exc_info:
        mgr.create_checkpoint(req)

    # Verify original exception cause is chained
    assert exc_info.value.__cause__ is not None
    assert "Memory store connection timeout" in str(exc_info.value.__cause__)

    # Verify NO checkpoint is in ACTIVE status in repository
    active_cps = mgr.repository.find_active("run-fail-cap")
    assert len(active_cps) == 0

    # Verify lock was released
    active_locks = lock_repo.find_active_locks(resource_key="res1")
    assert len(active_locks) == 0


def test_checkpoint_manager_lock_acquisition_failure_blocks_creation():
    lock_repo = InMemoryAgentRuntimeRepository()
    lock_mgr = RuntimeLockManager(lock_repo)
    # Acquire lock beforehand under a different run ID to cause conflict
    lock_mgr.acquire(
        "res_locked", owner_agent_run_id="run-owner-other", ttl_seconds=300
    )

    class TrackingResourceProvider:
        def __init__(self):
            self.invoked = False

        def capture_version(self, resource_uri: str) -> str:
            self.invoked = True
            return "v1.0"

        def get_version(self, resource_uri: str) -> str:
            return "v1.0"

    tracking_prov = TrackingResourceProvider()
    mgr = CheckpointManager(lock_manager=lock_mgr, resource_provider=tracking_prov)  # type: ignore[arg-type]

    req = CheckpointCreationRequest(
        agent_run_id="run-blocked",
        goal_id="g1",
        workflow_id="w1",
        iteration_id="i1",
        name="cp_blocked",
        transaction_boundary_id="txb1",
        resource_keys=("res_locked",),
    )

    with pytest.raises(CheckpointCreationError):
        mgr.create_checkpoint(req)

    # Verify no provider was invoked
    assert tracking_prov.invoked is False

    # Verify no checkpoint was persisted
    assert len(mgr.repository.find_by_agent_run("run-blocked")) == 0


def test_restoration_reverts_operations_in_reverse_order():
    execution_order: list[str] = []

    def make_handler(name: str):
        def _handler(action: CompensationAction) -> bool:
            execution_order.append(name)
            return True

        return _handler

    cp_mgr = CheckpointManager()
    cp_res = cp_mgr.create_checkpoint(
        CheckpointCreationRequest(
            agent_run_id="run-rev",
            goal_id="g",
            workflow_id="w",
            iteration_id="i",
            name="cp_rev",
            transaction_boundary_id="txb",
        )
    )

    rest_mgr = CheckpointRestorationManager(
        repository=cp_mgr.repository,
        compensation_handlers={
            "hA": make_handler("A"),
            "hB": make_handler("B"),
            "hC": make_handler("C"),
        },
    )

    comp_a = CompensationAction(
        action_id="act_A", operation_name="op_A", handler_name="hA", parameters={}
    )
    comp_b = CompensationAction(
        action_id="act_B", operation_name="op_B", handler_name="hB", parameters={}
    )
    comp_c = CompensationAction(
        action_id="act_C", operation_name="op_C", handler_name="hC", parameters={}
    )

    # Registered in chronological order A, B, C
    req = CheckpointRestorationRequest(
        checkpoint_id=cp_res.checkpoint_id, agent_run_id="run-rev"
    )
    res = rest_mgr.restore_checkpoint(req, compensations=(comp_a, comp_b, comp_c))

    assert res.success is True
    # Verify execution order is EXACTLY C, B, A
    assert execution_order == ["C", "B", "A"]


def test_restoration_reverse_order_partial_failure():
    execution_order: list[str] = []

    def handler_c(action: CompensationAction) -> bool:
        execution_order.append("C")
        return True

    def handler_b(action: CompensationAction) -> bool:
        execution_order.append("B")
        raise RuntimeError("Compensation B DB connection reset")

    def handler_a(action: CompensationAction) -> bool:
        execution_order.append("A")
        return True

    lock_repo = InMemoryAgentRuntimeRepository()
    lock_mgr = RuntimeLockManager(lock_repo)
    res_prov = InMemoryResourceVersionProvider({"res1": "v1.0"})
    cp_mgr = CheckpointManager(lock_manager=lock_mgr, resource_provider=res_prov)

    cp_res = cp_mgr.create_checkpoint(
        CheckpointCreationRequest(
            agent_run_id="run-part-fail",
            goal_id="g",
            workflow_id="w",
            iteration_id="i",
            name="cp_part",
            transaction_boundary_id="txb",
            resource_keys=("res1",),
        )
    )

    rest_mgr = CheckpointRestorationManager(
        repository=cp_mgr.repository,
        lock_manager=lock_mgr,
        resource_provider=res_prov,
        compensation_handlers={
            "hA": handler_a,
            "hB": handler_b,
            "hC": handler_c,
        },
    )

    comp_a = CompensationAction(
        action_id="act_A", operation_name="op_A", handler_name="hA", parameters={}
    )
    comp_b = CompensationAction(
        action_id="act_B", operation_name="op_B", handler_name="hB", parameters={}
    )
    comp_c = CompensationAction(
        action_id="act_C", operation_name="op_C", handler_name="hC", parameters={}
    )

    rest_req = CheckpointRestorationRequest(
        checkpoint_id=cp_res.checkpoint_id,
        agent_run_id="run-part-fail",
    )

    res = rest_mgr.restore_checkpoint(
        rest_req,
        original_error="Primary operation failed",
        compensations=(comp_a, comp_b, comp_c),
    )

    # 1. Success is False and status is PARTIALLY_RESTORED
    assert res.success is False
    assert res.status == RestorationStatus.PARTIALLY_RESTORED.value

    # 2. C was executed before failure of B; A was not reached
    assert execution_order == ["C", "B"]

    # 3. Original error separated from restoration error
    assert res.original_error == "Primary operation failed"
    assert res.restoration_error is not None
    assert "Compensation B DB connection reset" in res.restoration_error

    # 4. Differences and completed/failed operations registered
    assert "compensation:act_C" in res.restored_resources
    assert "compensation:act_B" in res.failed_resources

    # 5. Verify locks released
    assert len(lock_repo.find_active_locks(resource_key="res1")) == 0
