from __future__ import annotations

from cmm.memory import KnowledgeQuery, ProjectIndexer, RelationType


def test_knowledge_query_finds_nodes_by_id_type_and_name(tmp_path) -> None:
    query = _build_query(tmp_path)

    module = query.find_module("app.service")
    service = query.find_class("Service")
    build = query.find_function("build")
    run = query.find_method("run")

    assert module is not None
    assert service is not None
    assert build is not None
    assert run is not None
    assert query.find_node(module.identifier) == module
    assert query.find_nodes(node_type="Class", name="Service") == [service]
    assert query.find_nodes(name="missing") == []


def test_knowledge_query_returns_neighbors_and_edges(tmp_path) -> None:
    query = _build_query(tmp_path)

    service_module = query.find_module("app.service")
    service = query.find_class("Service")

    assert service_module is not None
    assert service is not None

    outgoing = query.outgoing(service_module)
    incoming = query.incoming(service)
    neighbors = query.neighbors(service_module)
    contains = query.relations(service_module, RelationType.CONTAINS)

    assert any(edge.relation == RelationType.CONTAINS for edge in outgoing)
    assert any(edge.source_id == service_module.identifier for edge in incoming)
    assert service in neighbors
    assert contains
    assert all(edge.relation == RelationType.CONTAINS for edge in contains)


def test_knowledge_query_navigates_contains_relationships(tmp_path) -> None:
    query = _build_query(tmp_path)

    project = query.find_nodes(node_type="Project")[0]
    service_module = query.find_module("app.service")
    service = query.find_class("Service")
    run = query.find_method("run")

    assert service_module is not None
    assert service is not None
    assert run is not None
    assert service_module in query.children(project)
    assert service in query.children(service_module)
    assert query.parents(service) == [service_module]
    assert run in query.descendants(project)
    assert project in query.ancestors(run)
    assert service in query.ancestors(run)


def test_knowledge_query_exposes_call_impact(tmp_path) -> None:
    query = _build_query(tmp_path)

    build = query.find_function("build")
    helper = query.find_function("helper")
    run = query.find_method("run")
    normalize = query.find_method("normalize")

    assert build is not None
    assert helper is not None
    assert run is not None
    assert normalize is not None
    assert helper in query.callees(build)
    assert build in query.callers(helper)
    assert normalize in query.callees(run)
    assert run in query.callers(normalize)


def test_knowledge_query_exposes_import_impact(tmp_path) -> None:
    query = _build_query(tmp_path)

    service_module = query.find_module("app.service")
    models_module = query.find_module("app.models")

    assert service_module is not None
    assert models_module is not None
    assert models_module in query.imports(service_module)
    assert service_module in query.imported_by(models_module)


def test_knowledge_query_exposes_inheritance_impact(tmp_path) -> None:
    query = _build_query(tmp_path)

    base = query.find_class("Base")
    profile = query.find_class("Profile")

    assert base is not None
    assert profile is not None
    assert base in query.inherits_from(profile)
    assert profile in query.derived_classes(base)


def test_knowledge_query_exposes_usage_impact(tmp_path) -> None:
    query = _build_query(tmp_path)

    profile = query.find_class("Profile")
    service = query.find_class("Service")

    assert profile is not None
    assert service is not None
    assert profile in query.uses(service)
    assert service in query.used_by(profile)


def _build_query(tmp_path) -> KnowledgeQuery:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "models.py").write_text(
        """
class Base:
    pass


class Profile(Base):
    pass
""",
        encoding="utf-8",
    )
    (tmp_path / "app" / "service.py").write_text(
        """
from app import models
from app.models import Profile


def helper():
    return Profile()


def build():
    return helper()


class Service:
    profile: Profile

    def normalize(self):
        return helper()

    def run(self):
        self.profile = Profile()
        return self.normalize()
""",
        encoding="utf-8",
    )

    return KnowledgeQuery(ProjectIndexer(tmp_path).build())
