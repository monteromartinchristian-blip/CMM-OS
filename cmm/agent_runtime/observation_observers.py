"""Phase 9.4 – Initial System State Observers.

Provides real, non-mutating Observers for Goals, Repository, Git, Validation,
Technical Memory, and System Health.
"""

from __future__ import annotations

import os
import platform
import sys
import time
from pathlib import Path
from typing import ClassVar

from cmm.agent_runtime.enums import (
    ObservationKind,
    ObserverStatus,
)
from cmm.agent_runtime.goal_manager import GoalManager
from cmm.agent_runtime.goal_repository import GoalRepository
from cmm.agent_runtime.observation_contracts import (
    Observation,
    ObservationError,
    ObservationRequest,
    ObservationResult,
    ObservationSourceVersion,
)
from cmm.agent_runtime.observer_protocol import ObserverMetadataMixin
from cmm.execution.services.git_service import GitService, GitServiceError
from cmm.memory.technical_memory import TechnicalMemory
from cmm.validation.observability.history import ValidationHistoryQuery
from cmm.validation.observability.service import ValidationObservabilityService


class GoalObserver(ObserverMetadataMixin):
    """Observer for Goal System state, criteria, constraints, and history."""

    name: str = "GoalObserver"
    version: str = "1.0.0"
    capabilities: tuple[str, ...] = (
        "goal_state",
        "goal_history",
        "criteria_evaluation",
    )
    scope: tuple[str, ...] = ("goal_system",)

    def __init__(
        self,
        repository: GoalRepository | None = None,
        manager: GoalManager | None = None,
    ) -> None:
        self.repository = repository
        self.manager = manager

    def supports(self, request: ObservationRequest) -> bool:
        return (
            request.goal_id is not None or "goal" in request.scope or not request.scope
        )

    def observe(self, request: ObservationRequest) -> ObservationResult:
        start = time.perf_counter()
        observations: list[Observation] = []
        warnings: list[str] = []
        errors: list[ObservationError] = []

        target_repo = self.repository
        if target_repo is None and self.manager is not None:
            target_repo = self.manager.repository

        if target_repo is None:
            warnings.append("GoalObserver: No GoalRepository or GoalManager provided.")
            return ObservationResult(
                observer_name=self.name,
                observer_version=self.version,
                status=ObserverStatus.DEGRADED,
                observations=(),
                warnings=tuple(warnings),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        goal_id = request.goal_id
        if goal_id:
            goal = target_repo.get(goal_id)
            if goal:
                history_entries = (
                    [h.to_dict() for h in target_repo.get_history(goal_id)]
                    if hasattr(target_repo, "get_history")
                    else []
                )

                obs_val = {
                    "goal_id": goal.id,
                    "title": goal.title,
                    "kind": goal.kind.value
                    if hasattr(goal.kind, "value")
                    else str(goal.kind),
                    "status": goal.status.value
                    if hasattr(goal.status, "value")
                    else str(goal.status),
                    "priority": goal.priority,
                    "urgency": goal.urgency,
                    "value": goal.value,
                    "confidence": goal.confidence,
                    "success_criteria": [sc.to_dict() for sc in goal.success_criteria],
                    "constraints": [c.to_dict() for c in goal.constraints],
                    "dependencies": [d.to_dict() for d in goal.dependencies],
                    "blocked_by": list(goal.blocked_by),
                    "parent_goal_id": goal.parent_goal_id,
                    "child_goal_ids": list(goal.child_goal_ids),
                    "history_count": len(history_entries),
                    "history": history_entries[:10],
                }
                observations.append(
                    Observation(
                        observer=self.name,
                        kind=ObservationKind.GOAL,
                        subject_id=f"goal:{goal.id}",
                        statement=(
                            f"Goal '{goal.title}' is currently "
                            f"{goal.status.value if hasattr(goal.status, 'value') else goal.status}"
                        ),
                        value=obs_val,
                        confidence=goal.confidence,
                    )
                )
            else:
                warnings.append(
                    f"GoalObserver: Goal '{goal_id}' not found in repository."
                )
        else:
            # Query all goals if no specific goal_id
            if hasattr(target_repo, "_goals"):
                all_goals = list(target_repo._goals.values())
                summary_val = {
                    "total_goals": len(all_goals),
                    "statuses": {g.id: g.status.value for g in all_goals},
                }
                observations.append(
                    Observation(
                        observer=self.name,
                        kind=ObservationKind.GOAL,
                        subject_id="goal_repository:summary",
                        statement=f"Repository contains {len(all_goals)} goals.",
                        value=summary_val,
                    )
                )

        return ObservationResult(
            observer_name=self.name,
            observer_version=self.version,
            status=ObserverStatus.COMPLETED
            if observations
            else ObserverStatus.DEGRADED,
            observations=tuple(observations),
            warnings=tuple(warnings),
            errors=tuple(errors),
            duration_ms=(time.perf_counter() - start) * 1000,
        )


class RepositoryObserver(ObserverMetadataMixin):
    """Observer for workspace file structure, file counts, and Python module footprint.

    Enforces workspace boundary and security path traversal checks.
    """

    name: str = "RepositoryObserver"
    version: str = "1.0.0"
    capabilities: tuple[str, ...] = ("filesystem_structure", "python_files_count")
    scope: tuple[str, ...] = ("repository", "filesystem")

    EXCLUDED_DIRS: ClassVar[set[str]] = {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "node_modules",
    }

    def __init__(self, workspace_root: Path | str | None = None) -> None:
        if workspace_root is None:
            workspace_root = Path.cwd()
        self.workspace_root = Path(workspace_root).resolve()

    def supports(self, request: ObservationRequest) -> bool:
        return (
            "repository" in request.scope
            or "filesystem" in request.scope
            or not request.scope
        )

    def observe(self, request: ObservationRequest) -> ObservationResult:
        start = time.perf_counter()
        observations: list[Observation] = []
        warnings: list[str] = []

        if not self.workspace_root.exists() or not self.workspace_root.is_dir():
            return ObservationResult(
                observer_name=self.name,
                observer_version=self.version,
                status=ObserverStatus.UNAVAILABLE,
                warnings=(
                    f"Workspace root directory '{self.workspace_root}' does not exist.",
                ),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        total_files = 0
        python_files = 0
        file_list: list[str] = []

        # Safe directory traversal enforcing scope and excluding cache/venv dirs
        try:
            for root, dirs, files in os.walk(self.workspace_root, followlinks=False):
                # Filter out excluded directories in-place
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in self.EXCLUDED_DIRS and not d.startswith(".")
                ]

                current_path = Path(root).resolve()
                # Security check: path traversal safeguard
                if not str(current_path).startswith(str(self.workspace_root)):
                    warnings.append(f"Skipped path outside workspace: {current_path}")
                    continue

                for f in files:
                    if f.startswith("."):
                        continue
                    total_files += 1
                    rel_path = str(Path(root, f).relative_to(self.workspace_root))
                    if f.endswith(".py"):
                        python_files += 1
                    if len(file_list) < request.maximum_items:
                        file_list.append(rel_path)
        except Exception as exc:  # noqa: BLE001
            return ObservationResult(
                observer_name=self.name,
                observer_version=self.version,
                status=ObserverStatus.FAILED,
                warnings=(f"Error traversing workspace: {exc}",),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        repo_val = {
            "workspace_root": str(self.workspace_root),
            "total_files": total_files,
            "python_files": python_files,
            "sample_files": file_list[:20],
        }

        observations.append(
            Observation(
                observer=self.name,
                kind=ObservationKind.REPOSITORY,
                subject_id=f"repository:{self.workspace_root.name}",
                statement=f"Repository contains {total_files} files ({python_files} Python files)",
                value=repo_val,
                confidence=1.0,
            )
        )

        return ObservationResult(
            observer_name=self.name,
            observer_version=self.version,
            status=ObserverStatus.COMPLETED,
            observations=tuple(observations),
            warnings=tuple(warnings),
            duration_ms=(time.perf_counter() - start) * 1000,
        )


class GitObserver(ObserverMetadataMixin):
    """Read-only observer for Git branch state, working tree, and tags using GitService."""

    name: str = "GitObserver"
    version: str = "1.0.0"
    capabilities: tuple[str, ...] = ("git_status", "git_branch", "git_tags")
    scope: tuple[str, ...] = ("git", "repository")

    def __init__(
        self,
        workspace_root: Path | str | None = None,
        git_service: GitService | None = None,
    ) -> None:
        if workspace_root is None:
            workspace_root = Path.cwd()
        self.workspace_root = Path(workspace_root).resolve()
        self.git_service = git_service or GitService()

    def supports(self, request: ObservationRequest) -> bool:
        return (
            "git" in request.scope or "repository" in request.scope or not request.scope
        )

    def observe(self, request: ObservationRequest) -> ObservationResult:
        start = time.perf_counter()
        observations: list[Observation] = []
        warnings: list[str] = []
        source_ver: ObservationSourceVersion | None = None

        try:
            branch_data = self.git_service.current_branch(self.workspace_root)
            status_data = self.git_service.status(self.workspace_root)
            current_branch = str(branch_data.get("branch", ""))
            porcelain = str(status_data.get("porcelain", ""))

            # Get recent commit for source version
            log_data = self.git_service.log(self.workspace_root, limit=1)
            raw_entries = log_data.get("entries")
            head_commit = "unknown"
            if isinstance(raw_entries, list) and raw_entries:
                first_entry = raw_entries[0]
                if isinstance(first_entry, dict):
                    commit = first_entry.get("commit")
                    if isinstance(commit, str) and commit:
                        head_commit = commit

            source_ver = ObservationSourceVersion(
                source_name="git",
                version_identifier=head_commit,
            )

            is_clean = len(porcelain.strip()) == 0
            git_val = {
                "branch": current_branch,
                "head_commit": head_commit,
                "is_clean": is_clean,
                "porcelain_status": porcelain,
            }

            observations.append(
                Observation(
                    observer=self.name,
                    kind=ObservationKind.GIT,
                    subject_id=f"git:repo:{self.workspace_root.name}",
                    statement=f"Git branch '{current_branch}' (HEAD: {head_commit[:7]}), clean: {is_clean}",
                    value=git_val,
                    confidence=1.0,
                )
            )
            obs_status = ObserverStatus.COMPLETED
        except (GitServiceError, Exception) as exc:  # noqa: BLE001
            warnings.append(f"GitObserver failed to read git status: {exc}")
            obs_status = ObserverStatus.DEGRADED

        return ObservationResult(
            observer_name=self.name,
            observer_version=self.version,
            status=obs_status,
            observations=tuple(observations),
            warnings=tuple(warnings),
            source_version=source_ver,
            duration_ms=(time.perf_counter() - start) * 1000,
        )


class ValidationObserver(ObserverMetadataMixin):
    """Observer for Phase 7 Validation execution records and test/lint findings."""

    name: str = "ValidationObserver"
    version: str = "1.0.0"
    capabilities: tuple[str, ...] = ("validation_results", "commit_gate_status")
    scope: tuple[str, ...] = ("validation",)

    def __init__(self, service: ValidationObservabilityService | None = None) -> None:
        self.service = service

    def supports(self, request: ObservationRequest) -> bool:
        return "validation" in request.scope or not request.scope

    def observe(self, request: ObservationRequest) -> ObservationResult:
        start = time.perf_counter()
        observations: list[Observation] = []
        warnings: list[str] = []

        if self.service is None:
            warnings.append(
                "ValidationObserver: ValidationObservabilityService not configured."
            )
            return ObservationResult(
                observer_name=self.name,
                observer_version=self.version,
                status=ObserverStatus.DEGRADED,
                warnings=tuple(warnings),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        try:
            history_page = self.service.list_history(ValidationHistoryQuery(limit=5))
            history = history_page.items
            if history:
                latest = history[0]
                val_data = {
                    "execution_id": latest.id,
                    "status": latest.status,
                    "total_runs": history_page.total,
                }
                observations.append(
                    Observation(
                        observer=self.name,
                        kind=ObservationKind.VALIDATION,
                        subject_id="validation:latest",
                        statement=f"Latest validation execution status is {val_data['status']}",
                        value=val_data,
                    )
                )
            else:
                warnings.append("No prior validation records found.")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"ValidationObserver error: {exc}")

        return ObservationResult(
            observer_name=self.name,
            observer_version=self.version,
            status=ObserverStatus.COMPLETED
            if observations
            else ObserverStatus.DEGRADED,
            observations=tuple(observations),
            warnings=tuple(warnings),
            duration_ms=(time.perf_counter() - start) * 1000,
        )


class MemoryObserver(ObserverMetadataMixin):
    """Observer for Technical Memory status, indexed graph statistics, and freshness."""

    name: str = "MemoryObserver"
    version: str = "1.0.0"
    capabilities: tuple[str, ...] = ("technical_memory_status", "knowledge_graph_stats")
    scope: tuple[str, ...] = ("memory", "knowledge")

    def __init__(self, memory: TechnicalMemory | None = None) -> None:
        self.memory = memory

    def supports(self, request: ObservationRequest) -> bool:
        return (
            "memory" in request.scope
            or "knowledge" in request.scope
            or not request.scope
        )

    def observe(self, request: ObservationRequest) -> ObservationResult:
        start = time.perf_counter()
        observations: list[Observation] = []
        warnings: list[str] = []

        if self.memory is None:
            warnings.append("MemoryObserver: TechnicalMemory instance not provided.")
            return ObservationResult(
                observer_name=self.name,
                observer_version=self.version,
                status=ObserverStatus.DEGRADED,
                warnings=tuple(warnings),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        try:
            graph = self.memory.graph if hasattr(self.memory, "graph") else None
            nodes_count = len(graph.nodes) if graph and hasattr(graph, "nodes") else 0
            edges_count = len(graph.edges) if graph and hasattr(graph, "edges") else 0

            mem_val = {
                "nodes_count": nodes_count,
                "edges_count": edges_count,
                "is_indexed": nodes_count > 0,
            }

            observations.append(
                Observation(
                    observer=self.name,
                    kind=ObservationKind.MEMORY,
                    subject_id="technical_memory:graph",
                    statement=f"Technical Memory contains {nodes_count} nodes and {edges_count} edges",
                    value=mem_val,
                )
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"MemoryObserver error: {exc}")

        return ObservationResult(
            observer_name=self.name,
            observer_version=self.version,
            status=ObserverStatus.COMPLETED
            if observations
            else ObserverStatus.DEGRADED,
            observations=tuple(observations),
            warnings=tuple(warnings),
            duration_ms=(time.perf_counter() - start) * 1000,
        )


class SystemHealthObserver(ObserverMetadataMixin):
    """Observer for Python runtime environment, platform, disk space, and system components."""

    name: str = "SystemHealthObserver"
    version: str = "1.0.0"
    capabilities: tuple[str, ...] = ("system_health", "environment_runtime")
    scope: tuple[str, ...] = ("health", "system")

    def supports(self, request: ObservationRequest) -> bool:
        return (
            "health" in request.scope or "system" in request.scope or not request.scope
        )

    def observe(self, request: ObservationRequest) -> ObservationResult:
        start = time.perf_counter()
        observations: list[Observation] = []

        health_val = {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "cpu_count": os.cpu_count() or 1,
            "status": "healthy",
        }

        observations.append(
            Observation(
                observer=self.name,
                kind=ObservationKind.HEALTH,
                subject_id="system:runtime_health",
                statement=f"Python {health_val['python_version']} running on {health_val['platform']}",
                value=health_val,
                confidence=1.0,
            )
        )

        return ObservationResult(
            observer_name=self.name,
            observer_version=self.version,
            status=ObserverStatus.COMPLETED,
            observations=tuple(observations),
            duration_ms=(time.perf_counter() - start) * 1000,
        )
