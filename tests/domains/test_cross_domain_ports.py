"""Phase 10.9 – Tests for Cross-Domain Engine port protocols."""

from __future__ import annotations

import inspect

from cmm.domains.cross_domain_ports import (
    CrossDomainAgentPort,
    CrossDomainCognitivePort,
    CrossDomainEngine,
    CrossDomainKnowledgePort,
    CrossDomainOperationPort,
    CrossDomainPlannerPort,
    CrossDomainWorkflowPort,
    DomainCompositionPort,
    DomainResolutionPort,
)

ALL_PORTS = [
    DomainResolutionPort,
    DomainCompositionPort,
    CrossDomainCognitivePort,
    CrossDomainPlannerPort,
    CrossDomainAgentPort,
    CrossDomainWorkflowPort,
    CrossDomainOperationPort,
    CrossDomainKnowledgePort,
    CrossDomainEngine,
]


class TestRuntimeCheckable:
    def test_all_ports_are_runtime_checkable(self) -> None:
        for port in ALL_PORTS:
            assert getattr(port, "_is_runtime_protocol", False), port


class TestCompatibleFakes:
    def test_resolver_fake_satisfies_protocol(self) -> None:
        class FakeResolver:
            def resolve(self, request):
                return None

        assert isinstance(FakeResolver(), DomainResolutionPort)

    def test_composer_fake_satisfies_protocol(self) -> None:
        class FakeComposer:
            def compose(self, resolution):
                return None

        assert isinstance(FakeComposer(), DomainCompositionPort)

    def test_cognitive_fake_satisfies_protocol(self) -> None:
        class FakeCognitive:
            def reason(self, *, domain_id, objective, context):
                return None

        assert isinstance(FakeCognitive(), CrossDomainCognitivePort)

    def test_planner_fake_satisfies_protocol(self) -> None:
        class FakePlanner:
            def plan(self, *, composition, context):
                return None

        assert isinstance(FakePlanner(), CrossDomainPlannerPort)

    def test_agent_fake_satisfies_protocol(self) -> None:
        class FakeAgent:
            def coordinate(self, *, domain_id, plan, context):
                return None

        assert isinstance(FakeAgent(), CrossDomainAgentPort)

    def test_workflow_fake_satisfies_protocol(self) -> None:
        class FakeWorkflow:
            def coordinate(self, *, workflow_ids, context):
                return None

        assert isinstance(FakeWorkflow(), CrossDomainWorkflowPort)

    def test_operation_fake_satisfies_protocol(self) -> None:
        class FakeOperation:
            def coordinate_operations(
                self, *, operation_ids, requesting_domains, context
            ):
                return None

        assert isinstance(FakeOperation(), CrossDomainOperationPort)

    def test_knowledge_fake_satisfies_protocol(self) -> None:
        class FakeKnowledge:
            def retrieve(self, *, domains, entities, timelines, context):
                return None

        assert isinstance(FakeKnowledge(), CrossDomainKnowledgePort)

    def test_engine_fake_satisfies_protocol(self) -> None:
        class FakeEngine:
            def execute(self, request):
                return None

        assert isinstance(FakeEngine(), CrossDomainEngine)


class TestIncompatibleFakesRejected:
    def test_missing_method_rejected(self) -> None:
        class NotAResolver:
            def something_else(self) -> None:
                return None

        assert not isinstance(NotAResolver(), DomainResolutionPort)

    def test_wrong_method_name_rejected(self) -> None:
        class WrongCognitive:
            def think(self, *, domain_id, objective, context):
                return None

        assert not isinstance(WrongCognitive(), CrossDomainCognitivePort)

    def test_plain_object_rejected_by_all_ports(self) -> None:
        for port in ALL_PORTS:
            assert not isinstance(object(), port)


class TestOptionalPortsSignatures:
    def test_cognitive_reason_is_keyword_only(self) -> None:
        sig = inspect.signature(CrossDomainCognitivePort.reason)
        params = list(sig.parameters.values())[1:]  # drop self
        assert all(p.kind == inspect.Parameter.KEYWORD_ONLY for p in params)

    def test_agent_coordinate_is_keyword_only(self) -> None:
        sig = inspect.signature(CrossDomainAgentPort.coordinate)
        params = list(sig.parameters.values())[1:]
        assert all(p.kind == inspect.Parameter.KEYWORD_ONLY for p in params)

    def test_knowledge_retrieve_is_keyword_only(self) -> None:
        sig = inspect.signature(CrossDomainKnowledgePort.retrieve)
        params = list(sig.parameters.values())[1:]
        assert all(p.kind == inspect.Parameter.KEYWORD_ONLY for p in params)


class TestNoConcreteSubsystemImports:
    def test_module_does_not_import_forbidden_subsystems(self) -> None:
        import cmm.domains.cross_domain_ports as mod

        source = inspect.getsource(mod)
        for forbidden in (
            "cmm.agent_runtime",
            "cmm.cognitive",
            "cmm.execution",
            "cmm.workflows",
            "cmm.memory",
            "cmm.domains.registry",
        ):
            assert forbidden not in source, forbidden
