from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmm.memory import (
    CorruptRepositoryError,
    IncompatibleRepositoryError,
    PersistentKnowledgeRepository,
    ProjectMismatchError,
    ProjectIndexer,
    TechnicalMemory,
    TechnicalReasoner,
)
from cmm.planner import TaskPlanner


def test_graph_persists_and_recovers_in_a_new_memory_instance(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "class User:\n    def run(self):\n        return 1\n\n",
        encoding="utf-8",
    )
    memory = TechnicalMemory.for_project(tmp_path)

    loaded = memory.load()
    reloaded = TechnicalMemory.for_project(tmp_path)
    second = reloaded.load()

    assert loaded.origin == "reconstructed"
    assert second.origin == "persisted"
    assert reloaded.find_class("User") is not None
    assert reloaded.find_method("run") is not None
    assert (tmp_path / ".cmm" / "memory.json").is_file()


def test_persistent_repository_round_trips_nodes_edges_and_metadata(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("class User:\n    pass\n", encoding="utf-8")
    graph = ProjectIndexer(tmp_path).build()
    repository = PersistentKnowledgeRepository(tmp_path / "memory.json", tmp_path)

    repository.save(graph)
    restored = repository.load()

    assert set(restored.nodes) == set(graph.nodes)
    assert restored.edges == graph.edges
    assert restored.nodes["module:app.py"].metadata["path"] == "app.py"


def test_missing_corrupt_and_incompatible_repositories_are_structured(tmp_path: Path) -> None:
    repository = PersistentKnowledgeRepository(tmp_path / "memory.json", tmp_path)
    with pytest.raises(Exception, match="does not exist"):
        repository.load()

    (tmp_path / "memory.json").write_text("{invalid", encoding="utf-8")
    with pytest.raises(CorruptRepositoryError):
        repository.load()

    (tmp_path / "memory.json").write_text(json.dumps({"schema_version": 999}), encoding="utf-8")
    with pytest.raises(IncompatibleRepositoryError):
        repository.load()


def test_corrupt_memory_rebuilds_safely_and_persists_again(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("class Rebuilt:\n    pass\n", encoding="utf-8")
    memory = TechnicalMemory.for_project(tmp_path)
    memory.load()
    memory_path = tmp_path / ".cmm" / "memory.json"
    memory_path.write_text("not json", encoding="utf-8")

    result = TechnicalMemory.for_project(tmp_path).load()

    assert result.success is True
    assert result.origin == "reconstructed"
    assert result.rebuilt is True
    assert result.warnings
    assert TechnicalMemory.for_project(tmp_path).load().origin == "persisted"


def test_repository_rejects_a_different_project(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "app.py").write_text("class First:\n    pass\n", encoding="utf-8")
    first_memory = TechnicalMemory.for_project(first)
    first_memory.load()

    with pytest.raises(ProjectMismatchError):
        TechnicalMemory(PersistentKnowledgeRepository(first / ".cmm" / "memory.json", first), second)


def test_refresh_detects_created_modified_deleted_and_renamed_files(tmp_path: Path) -> None:
    (tmp_path / "old.py").write_text("class Old:\n    pass\n", encoding="utf-8")
    (tmp_path / "changed.py").write_text("class Before:\n    pass\n", encoding="utf-8")
    memory = TechnicalMemory.for_project(tmp_path)
    memory.load()

    (tmp_path / "new.py").write_text("class Old:\n    pass\n", encoding="utf-8")
    (tmp_path / "old.py").unlink()
    (tmp_path / "changed.py").write_text("class After:\n    pass\n", encoding="utf-8")
    (tmp_path / "created.py").write_text("def added():\n    pass\n", encoding="utf-8")
    result = memory.refresh()

    assert result.success is True
    assert result.change_set.renamed == (("old.py", "new.py"),)
    assert result.change_set.modified == ("changed.py",)
    assert result.change_set.created == ("created.py",)
    assert memory.find_class("Old") is not None
    assert memory.find_class("Before") is None
    assert memory.find_function("added") is not None


def test_refresh_without_changes_is_empty_and_does_not_persist(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def stable():\n    pass\n", encoding="utf-8")
    memory = TechnicalMemory.for_project(tmp_path)
    memory.load()

    first = memory.refresh()
    second = memory.refresh()

    assert first.change_set.empty is True
    assert second.change_set.empty is True
    assert first.persisted is False
    assert second.persisted is False


def test_reasoner_and_task_planner_use_refreshed_persistent_memory(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def old_feature():\n    pass\n", encoding="utf-8")
    memory = TechnicalMemory.for_project(tmp_path)
    memory.load()
    (tmp_path / "app.py").write_text("def new_feature():\n    pass\n", encoding="utf-8")
    memory.refresh()

    reasoner = TechnicalReasoner(memory)
    planner = TaskPlanner(reasoner)
    plan = planner.create_plan("new_feature")

    assert reasoner.locate_feature("new_feature")
    assert reasoner.locate_feature("old_feature") == []
    assert [item.title for item in plan.entry_points] == ["new_feature"]
