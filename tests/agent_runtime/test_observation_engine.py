"""Phase 9.4 – Observation Engine Test Suite.

Validates observation contracts, registry, engine execution, mandatory invariants,
concrete observers (Goal, Repository, Git, Validation, Memory, Health), change detection,
and cognitive resource adapter integration.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cmm.agent_runtime.enums import (
    GoalKind,
    GoalStatus,
    ObservationKind,
    ObservationStatus,
    ObservedChangeKind,
    ObserverStatus,
)
from cmm.agent_runtime.errors import (
    DuplicateObserverError,
    InvalidObservationContractError,
)
from cmm.agent_runtime.goal_contracts import Goal, GoalPriority
from cmm.agent_runtime.goal_manager import GoalManager
from cmm.agent_runtime.goal_repository import InMemoryGoalRepository
from cmm.agent_runtime.observation_cognitive_adapter import ObservationResourceAdapter
from cmm.agent_runtime.observation_contracts import (
    Observation,
    ObservationError,
    ObservationRequest,
    ObservationResult,
    ObservationSnapshot,
)
from cmm.agent_runtime.observation_diff import compare_snapshots
from cmm.agent_runtime.observation_engine import ObservationEngine
from cmm.agent_runtime.observation_observers import (
    GitObserver,
    GoalObserver,
    RepositoryObserver,
    SystemHealthObserver,
)
from cmm.agent_runtime.observer_protocol import ObserverMetadataMixin
from cmm.agent_runtime.observer_registry import ObserverRegistry

# ── Dummy Observer Helper ─────────────────────────────────────────────────────


class DummyObserver(ObserverMetadataMixin):
    def __init__(
        self,
        name: str = "DummyObserver",
        version: str = "1.0.0",
        should_fail: bool = False,
        status: ObserverStatus = ObserverStatus.AVAILABLE,
    ) -> None:
        self.name = name
        self.version = version
        self.should_fail = should_fail
        self.status = status

    def supports(self, request: ObservationRequest) -> bool:
        return True

    def observe(self, request: ObservationRequest) -> ObservationResult:
        if self.should_fail:
            return ObservationResult(
                observer_name=self.name,
                observer_version=self.version,
                status=ObserverStatus.FAILED,
                errors=(
                    ObservationError(
                        observer_name=self.name,
                        message="Simulated observer failure",
                        is_fatal=True,
                    ),
                ),
            )

        obs = Observation(
            observer=self.name,
            kind=ObservationKind.STATE,
            subject_id=f"dummy:{self.name}",
            statement=f"Dummy observation from {self.name}",
            value={"key": "val"},
        )
        return ObservationResult(
            observer_name=self.name,
            observer_version=self.version,
            status=ObserverStatus.COMPLETED,
            observations=(obs,),
        )


# ── Invariant Tests ───────────────────────────────────────────────────────────


def test_invariant_1_stable_identifier():
    """1. An observation has a stable identifier."""
    obs = Observation(
        observer="TestObserver",
        subject_id="test:1",
        statement="State observation",
    )
    assert obs.id is not None
    assert obs.id.startswith("observation:")


def test_invariant_2_confidence_bounds():
    """2. Confidence must be between 0.0 and 1.0."""
    with pytest.raises(InvalidObservationContractError, match="confidence"):
        Observation(
            observer="TestObserver",
            subject_id="test:1",
            confidence=1.5,
        )

    with pytest.raises(InvalidObservationContractError, match="confidence"):
        Observation(
            observer="TestObserver",
            subject_id="test:1",
            confidence=-0.1,
        )


def test_invariant_3_maximum_items_positive():
    """3. maximum_items must be positive (> 0)."""
    with pytest.raises(InvalidObservationContractError, match="maximum_items"):
        ObservationRequest(maximum_items=0)

    with pytest.raises(InvalidObservationContractError, match="maximum_items"):
        ObservationRequest(maximum_items=-10)


def test_invariant_4_timeout_seconds_positive():
    """4. timeout_seconds must be positive (> 0)."""
    with pytest.raises(InvalidObservationContractError, match="timeout_seconds"):
        ObservationRequest(timeout_seconds=0.0)

    with pytest.raises(InvalidObservationContractError, match="timeout_seconds"):
        ObservationRequest(timeout_seconds=-5.0)


def test_invariant_5_snapshot_timestamps_coherence():
    """5. A completed snapshot has coherent timestamps."""
    now = datetime.now(timezone.utc)
    earlier = now - timedelta(seconds=10)

    # Valid coherence
    snap = ObservationSnapshot(
        started_at=earlier,
        completed_at=now,
        duration_ms=10000.0,
    )
    assert snap.completed_at >= snap.started_at
    assert snap.duration_ms >= 0.0

    # Invalid timestamp order
    with pytest.raises(InvalidObservationContractError, match="completed_at"):
        ObservationSnapshot(
            started_at=now,
            completed_at=earlier,
        )


def test_invariant_6_unregistered_observer_cannot_run():
    """6. An unregistered observer cannot be executed."""
    registry = ObserverRegistry()
    engine = ObservationEngine(registry)
    req = ObservationRequest(observer_names=("UnregisteredObserver",))

    snapshot = engine.execute(req)
    assert snapshot.status in (ObservationStatus.DEGRADED, ObservationStatus.PARTIAL)
    assert any("not found in registry" in w for w in snapshot.warnings)


def test_invariant_7_duplicate_observer_names_rejected():
    """7. Duplicate observer names are rejected during registration."""
    registry = ObserverRegistry()
    obs1 = DummyObserver(name="SameName")
    obs2 = DummyObserver(name="SameName")

    registry.register(obs1)
    with pytest.raises(DuplicateObserverError):
        registry.register(obs2)


def test_invariant_8_disabled_observer_skipped():
    """8. A disabled observer is not executed."""
    registry = ObserverRegistry()
    obs = DummyObserver(name="DisabledObs")
    registry.register(obs)
    registry.disable("DisabledObs")

    engine = ObservationEngine(registry)
    req = ObservationRequest(observer_names=("DisabledObs",))
    snapshot = engine.execute(req)

    assert len(snapshot.observations) == 0
    assert any("disabled or unavailable" in w for w in snapshot.warnings)


def test_invariant_9_optional_failure_produces_partial_or_degraded():
    """9. Failure of an optional observer produces a degraded/partial snapshot with preserved warnings."""
    registry = ObserverRegistry()
    obs_ok = DummyObserver(name="ObsOK")
    obs_fail = DummyObserver(name="ObsFail", should_fail=True)

    registry.register(obs_ok)
    registry.register(obs_fail)

    engine = ObservationEngine(registry)
    req = ObservationRequest(observer_names=("ObsOK", "ObsFail"))
    snapshot = engine.execute(req)

    assert snapshot.status == ObservationStatus.DEGRADED
    assert len(snapshot.observations) == 1
    assert len(snapshot.errors) == 1


def test_invariant_10_required_failure_produces_failed_snapshot():
    """10. Failure of a required observer produces a failed snapshot without discarding obtained results."""
    registry = ObserverRegistry()
    obs_ok = DummyObserver(name="ObsOK")
    obs_fail = DummyObserver(name="ObsFail", should_fail=True)

    registry.register(obs_ok)
    registry.register(obs_fail)

    engine = ObservationEngine(registry)
    req = ObservationRequest(
        observer_names=("ObsOK", "ObsFail"),
        required_observers=("ObsFail",),
    )
    snapshot = engine.execute(req)

    assert snapshot.status == ObservationStatus.FAILED
    assert len(snapshot.observations) == 1  # Results from ObsOK preserved!
    assert len(snapshot.errors) >= 1


def test_invariant_11_observer_cannot_modify_goal():
    """11. GoalObserver does not modify the Goal entity."""
    repo = InMemoryGoalRepository()
    manager = GoalManager(repository=repo)
    goal = Goal(
        id="goal-1",
        title="Original Title",
        description="Test desc",
        kind=GoalKind.MAINTENANCE,
        priority=GoalPriority(score=80),
        status=GoalStatus.ACTIVE,
    )
    repo.add(goal)

    observer = GoalObserver(manager=manager)
    req = ObservationRequest(goal_id="goal-1")
    result = observer.observe(req)

    assert result.status == ObserverStatus.COMPLETED
    stored_goal = repo.get("goal-1")
    assert stored_goal.title == "Original Title"
    assert stored_goal.status == GoalStatus.ACTIVE


def test_invariant_12_observer_cannot_modify_repository(tmp_path: Path):
    """12. RepositoryObserver does not modify files in the target directory."""
    test_file = tmp_path / "sample.py"
    test_file.write_text("print('hello')\n")
    mtime_before = test_file.stat().st_mtime

    observer = RepositoryObserver(workspace_root=tmp_path)
    req = ObservationRequest()
    result = observer.observe(req)

    assert result.status == ObserverStatus.COMPLETED
    assert test_file.exists()
    assert test_file.stat().st_mtime == mtime_before


def test_invariant_13_deterministic_ordering():
    """13. Observation and change ordering in snapshot is deterministic."""
    registry = ObserverRegistry()
    obs_b = DummyObserver(name="ObserverB")
    obs_a = DummyObserver(name="ObserverA")
    registry.register(obs_b)
    registry.register(obs_a)

    engine = ObservationEngine(registry)
    req = ObservationRequest()
    snap1 = engine.execute(req)
    snap2 = engine.execute(req)

    subjects1 = [o.subject_id for o in snap1.observations]
    subjects2 = [o.subject_id for o in snap2.observations]
    assert subjects1 == subjects2


def test_invariant_14_maximum_items_respected():
    """14. maximum_items limit is enforced and produces a warning if truncated."""

    class MultiItemObserver(ObserverMetadataMixin):
        name = "MultiItem"

        def supports(self, req: ObservationRequest) -> bool:
            return True

        def observe(self, req: ObservationRequest) -> ObservationResult:
            items = [
                Observation(
                    observer=self.name, subject_id=f"item:{i}", statement=f"Item {i}"
                )
                for i in range(10)
            ]
            return ObservationResult(
                observer_name=self.name,
                observer_version="1.0.0",
                observations=tuple(items),
            )

    registry = ObserverRegistry()
    registry.register(MultiItemObserver())
    engine = ObservationEngine(registry)

    req = ObservationRequest(maximum_items=3)
    snapshot = engine.execute(req)

    assert len(snapshot.observations) == 3
    assert any("exceeded maximum_items" in w for w in snapshot.warnings)


def test_invariant_15_defensive_collection_immutability():
    """15. Dataclasses use immutable tuples for collection attributes."""
    obs = Observation(
        observer="Obs",
        subject_id="sub",
        statement="stat",
        source_ids=("id1", "id2"),
    )
    assert isinstance(obs.source_ids, tuple)
    with pytest.raises(TypeError):
        obs.source_ids[0] = "mutated"  # type: ignore


def test_invariant_16_serialization_roundtrip():
    """16. Serialization and reconstruction preserve all contract fields."""
    req = ObservationRequest(
        goal_id="goal-123",
        observer_names=("Obs1", "Obs2"),
        maximum_items=500,
        timeout_seconds=45.0,
    )
    req_dict = req.to_dict()
    req_reconstructed = ObservationRequest.from_dict(req_dict)
    assert req_reconstructed == req

    obs = Observation(
        observer="TestObs",
        kind=ObservationKind.GIT,
        subject_id="git:repo",
        statement="Clean repo",
        confidence=0.95,
    )
    obs_dict = obs.to_dict()
    obs_reconstructed = Observation.from_dict(obs_dict)
    assert obs_reconstructed.id == obs.id
    assert obs_reconstructed.confidence == obs.confidence


def test_invariant_17_unknown_enum_rejection_handling():
    """17. Unknown string enums gracefully fallback or maintain string compatibility."""
    obs = Observation(
        observer="TestObs",
        kind="custom_kind",  # Custom string kind
        subject_id="sub:1",
    )
    assert obs.kind == "custom_kind"
    assert obs.to_dict()["kind"] == "custom_kind"


def test_invariant_18_snapshot_comparison_detects_changes():
    """18. compare_snapshots detects created, deleted, and modified observations."""
    obs1 = Observation(observer="Obs", subject_id="file:a.py", value={"size": 100})
    obs2_old = Observation(observer="Obs", subject_id="file:b.py", value={"size": 200})
    obs2_new = Observation(observer="Obs", subject_id="file:b.py", value={"size": 250})
    obs3 = Observation(observer="Obs", subject_id="file:c.py", value={"size": 300})

    snap_prev = ObservationSnapshot(observations=(obs1, obs2_old))
    snap_curr = ObservationSnapshot(observations=(obs2_new, obs3))

    changes = compare_snapshots(snap_prev, snap_curr)
    kinds = {c.subject_id: c.kind for c in changes}

    assert kinds["file:a.py"] == ObservedChangeKind.DELETED
    assert kinds["file:b.py"] == ObservedChangeKind.MODIFIED
    assert kinds["file:c.py"] == ObservedChangeKind.CREATED


def test_invariant_19_cognitive_adapter_preserves_provenance():
    """19. ObservationResourceAdapter maps observations to Resources preserving provenance."""
    obs = Observation(
        observer="GitObserver",
        kind=ObservationKind.GIT,
        subject_id="git:head",
        statement="HEAD at commit abc",
        confidence=0.99,
        sensitivity="internal",
    )
    resource = ObservationResourceAdapter.from_observation(obs)

    assert resource.domain == "agent_runtime"
    assert resource.provenance.author == "GitObserver"
    assert resource.reliability.value == 0.99
    assert resource.metadata["observation_id"] == obs.id


def test_invariant_20_observation_engine_decoupled():
    """20. Observation Engine module does not import Planner, Execution Engine or LLM."""

    # Ensure no import dependencies on planner or llm in observation files
    import cmm.agent_runtime.observation_engine as eng_mod

    module_content = Path(eng_mod.__file__).read_text()
    assert "Planner" not in module_content
    assert "ExecutionEngine" not in module_content
    assert "LLM" not in module_content


# ── Concrete Observer Integration Tests ───────────────────────────────────────


def test_goal_observer_real_repository():
    repo = InMemoryGoalRepository()
    goal = Goal(
        id="goal-real",
        title="Test Real Goal",
        description="Desc",
        kind=GoalKind.MAINTENANCE,
        priority=GoalPriority(score=80),
        status=GoalStatus.ACTIVE,
    )
    repo.add(goal)

    observer = GoalObserver(repository=repo)
    result = observer.observe(ObservationRequest(goal_id="goal-real"))

    assert result.status == ObserverStatus.COMPLETED
    assert len(result.observations) == 1
    assert result.observations[0].value["goal_id"] == "goal-real"


def test_repository_observer_real_workspace(tmp_path: Path):
    (tmp_path / "main.py").write_text("print(1)")
    (tmp_path / "utils.py").write_text("def f(): pass")
    (tmp_path / "README.md").write_text("# Readme")

    observer = RepositoryObserver(workspace_root=tmp_path)
    result = observer.observe(ObservationRequest())

    assert result.status == ObserverStatus.COMPLETED
    obs = result.observations[0]
    assert obs.value["total_files"] == 3
    assert obs.value["python_files"] == 2


def test_git_observer_real_repo():
    observer = GitObserver()
    result = observer.observe(ObservationRequest())

    # Current CMM OS repo is a git repository
    assert result.status == ObserverStatus.COMPLETED
    assert len(result.observations) == 1
    assert "branch" in result.observations[0].value


def test_system_health_observer():
    observer = SystemHealthObserver()
    result = observer.observe(ObservationRequest())

    assert result.status == ObserverStatus.COMPLETED
    assert result.observations[0].value["status"] == "healthy"


# ── E2E Flow Tests ────────────────────────────────────────────────────────────


def test_e2e_complete_observation_flow():
    """E2E 1: Active Goal -> ObservationRequest -> Observers -> ObservationEngine -> ObservationSnapshot -> Resource Adapter."""
    repo = InMemoryGoalRepository()
    goal = Goal(
        id="goal-e2e",
        title="E2E Goal",
        description="Desc",
        kind=GoalKind.MAINTENANCE,
        priority=GoalPriority(score=80),
        status=GoalStatus.ACTIVE,
    )
    repo.add(goal)

    registry = ObserverRegistry()
    registry.register(GoalObserver(repository=repo))
    registry.register(SystemHealthObserver())

    engine = ObservationEngine(registry)
    req = ObservationRequest(goal_id="goal-e2e")

    snapshot = engine.execute(req)

    assert snapshot.status == ObservationStatus.COMPLETED
    assert len(snapshot.observations) >= 2

    # Convert to Cognitive Layer Resources
    resources = ObservationResourceAdapter.from_snapshot(snapshot)
    assert len(resources) >= 3  # 1 summary + 2 individual resources


def test_e2e_partial_degradation_flow():
    """E2E 2: Required observer OK + Optional observer missing -> snapshot degraded/partial."""
    registry = ObserverRegistry()
    obs_ok = DummyObserver(name="RequiredObs")
    registry.register(obs_ok)

    engine = ObservationEngine(registry)
    req = ObservationRequest(
        observer_names=("RequiredObs", "MissingOptionalObs"),
        required_observers=("RequiredObs",),
    )

    snapshot = engine.execute(req)

    assert snapshot.status in (ObservationStatus.DEGRADED, ObservationStatus.PARTIAL)
    assert len(snapshot.observations) == 1
    assert any("not found in registry" in w for w in snapshot.warnings)


def test_e2e_required_failure_flow():
    """E2E 3: Required observer fails -> snapshot failed -> structured error -> obtained results preserved."""
    registry = ObserverRegistry()
    obs_ok = DummyObserver(name="OptionalOK")
    obs_req_fail = DummyObserver(name="RequiredFail", should_fail=True)

    registry.register(obs_ok)
    registry.register(obs_req_fail)

    engine = ObservationEngine(registry)
    req = ObservationRequest(
        observer_names=("OptionalOK", "RequiredFail"),
        required_observers=("RequiredFail",),
    )

    snapshot = engine.execute(req)

    assert snapshot.status == ObservationStatus.FAILED
    assert len(snapshot.observations) == 1  # Results from OptionalOK preserved!
    assert len(snapshot.errors) >= 1
    assert snapshot.errors[0].is_fatal is True
