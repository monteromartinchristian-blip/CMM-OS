"""Bootstrap helpers for the planner subsystem."""

from __future__ import annotations

from kernel.llm.clients.ollama_client import OllamaClient
from kernel.llm.mock_provider import MockProvider
from kernel.llm.ollama_provider import OllamaProvider
from kernel.llm.parser import OperationPlanParser
from kernel.llm.prompt import PromptBuilder
from kernel.planner.context import PlanningContext
from kernel.planner.hybrid_planner import HybridPlanner
from kernel.planner.llm_planner import LLMPlanner
from kernel.planner.planner import RuleBasedPlanner
from kernel.planner.registry import (
    CreateClassHandler,
    EnsureImportHandler,
    ExtractFactsHandler,
    InsertMethodHandler,
    MergeKnowledgeHandler,
    OperationRegistry,
    OperationHandler,
    ReplaceMethodHandler,
)
from kernel.planner.operations import (
    CreateClassOperation,
    EnsureImportOperation,
    InsertMethodOperation,
    Operation,
    ReplaceMethodOperation,
)
from kernel.planner.read_pdf_operation import ReadPDFOperation
from kernel.planner.extract_facts_operation import ExtractFactsOperation
from kernel.planner.merge_knowledge_operation import MergeKnowledgeOperation
from kernel.planner.rules import (
    CompositeCreateClassWithMethodRule,
    CreateClassRule,
    EnsureImportRule,
    InsertMethodRule,
    ReplaceMethodRule,
)


def create_default_registry() -> OperationRegistry:
    """Create a registry with the default planner handlers."""

    registry = OperationRegistry()
    registry.register(CreateClassOperation, CreateClassHandler())
    registry.register(InsertMethodOperation, InsertMethodHandler())
    registry.register(ReplaceMethodOperation, ReplaceMethodHandler())
    registry.register(EnsureImportOperation, EnsureImportHandler())
    registry.register(ReadPDFOperation, _ReadPDFHandler())
    registry.register(ExtractFactsOperation, ExtractFactsHandler())
    registry.register(MergeKnowledgeOperation, MergeKnowledgeHandler())
    return registry


def create_default_planner() -> RuleBasedPlanner:
    """Create the default rule-based planner."""

    return RuleBasedPlanner(
        [
            CompositeCreateClassWithMethodRule(),
            CreateClassRule(),
            InsertMethodRule(),
            ReplaceMethodRule(),
            EnsureImportRule(),
        ]
    )


def create_hybrid_planner() -> HybridPlanner:
    """Create a planner that uses rules first and LLM as a fallback."""

    rule_planner = create_default_planner()
    llm_planner = LLMPlanner(
        provider=MockProvider(response='{"operations": []}'),
        prompt_builder=PromptBuilder(),
        parser=OperationPlanParser(),
    )
    return HybridPlanner(rule_planner=rule_planner, llm_planner=llm_planner)


def create_ollama_planner() -> LLMPlanner:
    """Create an LLM planner backed by an Ollama provider."""

    client = OllamaClient()
    provider = OllamaProvider(client=client)
    return LLMPlanner(
        provider=provider,
        prompt_builder=PromptBuilder(),
        parser=OperationPlanParser(),
    )


class _ReadPDFHandler(OperationHandler):
    def execute(self, operation: Operation, engine):
        return operation.execute()
