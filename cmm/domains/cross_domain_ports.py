"""Phase 10.9 – Cross-Domain Engine Ports.

Narrow, injectable, ``@runtime_checkable`` protocols coordinated by the
Cross-Domain Engine. The engine calls these ports only — it never imports
or embeds the Agent Runtime, Cognitive Layer, Workflow Engine, Knowledge
Graph, or the Domain Registry directly.
"""

from __future__ import annotations

from collections.abc import Mapping

from typing_extensions import Protocol, runtime_checkable

from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.cross_domain_contracts import (
    CrossDomainContextSnapshot,
    CrossDomainDomainResult,
    CrossDomainKnowledgeResult,
    CrossDomainOperationResult,
    CrossDomainPlanResult,
    CrossDomainRequest,
    CrossDomainResult,
    CrossDomainWorkflowResult,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.resolver_contracts import DomainResolutionResult


@runtime_checkable
class DomainResolutionPort(Protocol):
    """Resolves a request into primary/supporting domains (reuses Phase 10.7)."""

    def resolve(self, request: CrossDomainRequest) -> DomainResolutionResult: ...


@runtime_checkable
class DomainCompositionPort(Protocol):
    """Composes a resolution into an effective domain composition (reuses Phase 10.8).

    The adapter is responsible for obtaining domain definitions externally
    (e.g. from a registry). The engine never accesses the registry itself.
    """

    def compose(self, resolution: DomainResolutionResult) -> DomainComposition: ...


@runtime_checkable
class CrossDomainCognitivePort(Protocol):
    """Invokes the Cognitive Layer for a single domain's reasoning contribution."""

    def reason(
        self,
        *,
        domain_id: DomainId,
        objective: str,
        context: CrossDomainContextSnapshot,
    ) -> CrossDomainDomainResult: ...


@runtime_checkable
class CrossDomainPlannerPort(Protocol):
    """Produces a declarative coordination plan for the composed domains."""

    def plan(
        self,
        *,
        composition: DomainComposition,
        context: CrossDomainContextSnapshot,
    ) -> CrossDomainPlanResult: ...


@runtime_checkable
class CrossDomainAgentPort(Protocol):
    """Invokes the Agent Runtime to coordinate a domain's action-oriented work."""

    def coordinate(
        self,
        *,
        domain_id: DomainId,
        plan: CrossDomainPlanResult | None,
        context: CrossDomainContextSnapshot,
    ) -> CrossDomainDomainResult: ...


@runtime_checkable
class CrossDomainWorkflowPort(Protocol):
    """Coordinates a set of declarative workflow requests through the Workflow Engine."""

    def coordinate(
        self,
        *,
        workflow_ids: tuple[str, ...],
        context: CrossDomainContextSnapshot,
    ) -> CrossDomainWorkflowResult: ...


@runtime_checkable
class CrossDomainOperationPort(Protocol):
    """Coordinates a set of declarative operation requests through the Agent Runtime.

    Kept separate from ``CrossDomainAgentPort`` (which coordinates a single
    domain's action-oriented reasoning) so that cross-domain operation
    coordination — which spans multiple requesting domains at once — has
    its own narrow contract instead of overloading the per-domain port.
    """

    def coordinate_operations(
        self,
        *,
        operation_ids: tuple[str, ...],
        requesting_domains: Mapping[str, tuple[DomainId, ...]],
        context: CrossDomainContextSnapshot,
    ) -> CrossDomainOperationResult: ...


@runtime_checkable
class CrossDomainKnowledgePort(Protocol):
    """Retrieves shared entities, timelines, and findings from the Knowledge Graph."""

    def retrieve(
        self,
        *,
        domains: tuple[DomainId, ...],
        entities: tuple[str, ...],
        timelines: tuple[str, ...],
        context: CrossDomainContextSnapshot,
    ) -> CrossDomainKnowledgeResult: ...


@runtime_checkable
class CrossDomainEngine(Protocol):
    """The public contract of the Cross-Domain Engine itself."""

    def execute(self, request: CrossDomainRequest) -> CrossDomainResult: ...


__all__ = [
    "CrossDomainAgentPort",
    "CrossDomainCognitivePort",
    "CrossDomainEngine",
    "CrossDomainKnowledgePort",
    "CrossDomainOperationPort",
    "CrossDomainPlannerPort",
    "CrossDomainWorkflowPort",
    "DomainCompositionPort",
    "DomainResolutionPort",
]
