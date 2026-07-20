from __future__ import annotations

from cmm.memory import ProjectIndexer, RelationType


def test_project_indexer_detects_modules(tmp_path) -> None:
    (tmp_path / "package").mkdir()
    (tmp_path / "package" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "package" / "service.py").write_text("", encoding="utf-8")

    graph = ProjectIndexer(tmp_path).build()

    modules = [
        node
        for node in graph.nodes.values()
        if node.kind == "Module"
    ]

    assert {module.title for module in modules} == {"package", "package.service"}


def test_project_indexer_detects_classes_functions_methods_and_docstrings(tmp_path) -> None:
    module = tmp_path / "sample.py"
    module.write_text(
        '''"""Module docs."""

import os
from pathlib import Path


class User:
    """User docs."""

    def full_name(self):
        """Method docs."""
        return "Ada"


def build_user():
    """Function docs."""
    return User()
''',
        encoding="utf-8",
    )

    graph = ProjectIndexer(tmp_path).build()

    module_node = _only_node(graph, "Module", "sample")
    class_node = _only_node(graph, "Class", "User")
    function_node = _only_node(graph, "Function", "build_user")
    method_node = _only_node(graph, "Method", "full_name")

    assert module_node.summary == "Module docs."
    assert module_node.metadata["imports"] == ("import os", "from pathlib import Path")
    assert class_node.summary == "User docs."
    assert function_node.summary == "Function docs."
    assert method_node.summary == "Method docs."


def test_project_indexer_creates_contains_relationships(tmp_path) -> None:
    module = tmp_path / "sample.py"
    module.write_text(
        """
class User:
    def full_name(self):
        return "Ada"


def build_user():
    return User()
""",
        encoding="utf-8",
    )

    graph = ProjectIndexer(tmp_path).build()

    project = _only_node(graph, "Project", tmp_path.name)
    module_node = _only_node(graph, "Module", "sample")
    class_node = _only_node(graph, "Class", "User")
    function_node = _only_node(graph, "Function", "build_user")
    method_node = _only_node(graph, "Method", "full_name")

    assert _has_contains(graph, project.identifier, module_node.identifier)
    assert _has_contains(graph, module_node.identifier, class_node.identifier)
    assert _has_contains(graph, module_node.identifier, function_node.identifier)
    assert _has_contains(graph, class_node.identifier, method_node.identifier)


def test_project_indexer_creates_imports_relationships_for_project_modules(tmp_path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "models.py").write_text("class User:\n    pass\n", encoding="utf-8")
    (tmp_path / "app" / "service.py").write_text(
        "import os\nfrom app import models\n",
        encoding="utf-8",
    )

    graph = ProjectIndexer(tmp_path).build()

    service = _only_node(graph, "Module", "app.service")
    models = _only_node(graph, "Module", "app.models")

    assert _has_relation(graph, service.identifier, models.identifier, RelationType.IMPORTS)
    assert not any(
        edge.relation == RelationType.IMPORTS
        and graph.nodes[edge.target_id].title == "os"
        for edge in graph.edges
    )


def test_project_indexer_creates_inherits_relationships_for_project_classes(tmp_path) -> None:
    module = tmp_path / "models.py"
    module.write_text(
        """
class Base:
    pass


class User(Base):
    pass
""",
        encoding="utf-8",
    )

    graph = ProjectIndexer(tmp_path).build()

    base = _only_node(graph, "Class", "Base")
    user = _only_node(graph, "Class", "User")

    assert _has_relation(graph, user.identifier, base.identifier, RelationType.INHERITS)


def test_project_indexer_creates_calls_relationships_for_functions_and_methods(tmp_path) -> None:
    module = tmp_path / "service.py"
    module.write_text(
        """
def helper():
    return "Ada"


def build_user():
    return helper()


class UserService:
    def normalize(self):
        return helper()

    def run(self):
        return self.normalize()
""",
        encoding="utf-8",
    )

    graph = ProjectIndexer(tmp_path).build()

    helper = _only_node(graph, "Function", "helper")
    build_user = _only_node(graph, "Function", "build_user")
    normalize = _only_node(graph, "Method", "normalize")
    run = _only_node(graph, "Method", "run")

    assert _has_relation(graph, build_user.identifier, helper.identifier, RelationType.CALLS)
    assert _has_relation(graph, normalize.identifier, helper.identifier, RelationType.CALLS)
    assert _has_relation(graph, run.identifier, normalize.identifier, RelationType.CALLS)


def test_project_indexer_creates_uses_relationships_for_project_classes(tmp_path) -> None:
    module = tmp_path / "models.py"
    module.write_text(
        """
class Profile:
    pass


class User:
    profile: Profile

    def build_profile(self) -> Profile:
        self.profile = Profile()
        return self.profile
""",
        encoding="utf-8",
    )

    graph = ProjectIndexer(tmp_path).build()

    profile = _only_node(graph, "Class", "Profile")
    user = _only_node(graph, "Class", "User")

    assert _has_relation(graph, user.identifier, profile.identifier, RelationType.USES)


def _only_node(graph, kind: str, title: str):
    matches = [
        node
        for node in graph.nodes.values()
        if node.kind == kind and node.title == title
    ]

    assert len(matches) == 1
    return matches[0]


def _has_contains(graph, source_id: str, target_id: str) -> bool:
    return _has_relation(graph, source_id, target_id, RelationType.CONTAINS)


def _has_relation(graph, source_id: str, target_id: str, relation: RelationType) -> bool:
    return any(
        edge.source_id == source_id
        and edge.target_id == target_id
        and edge.relation == relation
        for edge in graph.edges
    )
