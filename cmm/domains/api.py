"""Phase 10.36 — Domain API.

One stable public coordination facade over the existing canonical Domain
Intelligence subsystems. The facade owns coordination and public ergonomics
only; every method delegates to an existing canonical owner:

- registry / inspection  -> ``DomainRegistry``
- discovery              -> ``FileSystemDomainDiscovery`` (non-executing)
- validation             -> ``PipelineDomainValidator``
- installation           -> ``DeclarativeDomainLoader.load`` (runtime load +
  registration only; NOT durable filesystem installation, publication,
  enablement, or authorization)
- resolution             -> ``DomainResolver``
- operation execution    -> ``DefaultDomainOperationOrchestrator``
- workflow execution     -> ``InMemoryDomainWorkflowRegistry`` +
  ``DomainWorkflowExecutor``
- sessions               -> ``SharedSessionDomainAdapter`` +
  ``DomainSessionResumer`` (shared ``SessionStore`` remains authoritative)
- conflicts              -> pure ``DomainConflictResolver``
- traces                 -> ``DomainTraceAssembler`` +
  ``DefaultDomainTraceReferenceValidator`` (reference-only)

The facade retains references to injected collaborators and owns no shadow
runtime state, no caches, no stores, and no registries. Canonical subsystem
errors propagate unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from cmm.domains.conflict_resolution import DomainConflictResolver
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictCase,
    DomainConflictResolution,
    DomainConflictResolutionPolicy,
)
from cmm.domains.contracts import DomainDefinition
from cmm.domains.discovery import FileSystemDomainDiscovery
from cmm.domains.discovery_contracts import (
    DomainCandidate,
    DomainDiscoveryResult,
    DomainSource,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.loader import DeclarativeDomainLoader
from cmm.domains.loader_contracts import DomainLoadResult
from cmm.domains.operation_contracts import (
    DomainOperationRequest,
    DomainOperationResult,
)
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainQuery
from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resolver_contracts import DomainResolutionResult
from cmm.domains.session_contracts import (
    DomainSessionContext,
    DomainSessionResumeRequest,
    DomainSessionResumeResult,
)
from cmm.domains.session_persistence import SharedSessionDomainAdapter
from cmm.domains.session_resumer import DomainSessionResumer
from cmm.domains.trace_assembler import DomainTraceAssembler
from cmm.domains.trace_contracts import (
    DomainTrace,
    DomainTraceAssemblyRequest,
    DomainTraceReferenceInventory,
    DomainTraceValidationResult,
)
from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator
from cmm.domains.validation import PipelineDomainValidator
from cmm.domains.validation_contracts import (
    DomainValidationRequest,
    DomainValidationResult,
)
from cmm.domains.workflow_contracts import (
    DomainWorkflowContext,
    DomainWorkflowResult,
)
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry

if TYPE_CHECKING:
    from cmm.domains.operation_execution import DefaultDomainOperationOrchestrator


__all__ = ["DefaultDomainAPI", "DomainAPI"]


@runtime_checkable
class DomainAPI(Protocol):
    """Stable public coordination surface for Domain Intelligence."""

    def list_domains(
        self, query: DomainQuery | None = None
    ) -> tuple[DomainDefinition, ...]: ...

    def get_domain(
        self, domain_id: str, version: str | None = None
    ) -> DomainDefinition | None: ...

    def discover_domains(
        self, sources: tuple[DomainSource, ...]
    ) -> DomainDiscoveryResult: ...

    def validate_domain(
        self, request: DomainValidationRequest
    ) -> DomainValidationResult: ...

    def install_domain(
        self, candidate: DomainCandidate, *, allow_untrusted: bool = False
    ) -> DomainLoadResult: ...

    def enable_domain(
        self, domain_id: str, version: str | None = None
    ) -> DomainDefinition: ...

    def disable_domain(
        self, domain_id: str, version: str | None = None
    ) -> DomainDefinition: ...

    def resolve_domain(
        self, context: DomainResolutionContext
    ) -> DomainResolutionResult: ...

    def get_capabilities(
        self, domain_id: str, version: str | None = None
    ) -> tuple[Any, ...]: ...

    def get_resources(
        self, domain_id: str, version: str | None = None
    ) -> tuple[str, ...]: ...

    def get_rules(
        self, domain_id: str, version: str | None = None
    ) -> tuple[str, ...]: ...

    def get_operations(
        self, domain_id: str, version: str | None = None
    ) -> tuple[str, ...]: ...

    def get_workflows(
        self, domain_id: str, version: str | None = None
    ) -> tuple[str, ...]: ...

    def execute_operation(
        self, request: DomainOperationRequest
    ) -> DomainOperationResult: ...

    def start_workflow(
        self,
        workflow_id: str,
        context: DomainWorkflowContext,
        inputs: Mapping[str, Any],
    ) -> DomainWorkflowResult: ...

    def get_session(self, session_id: str) -> DomainSessionContext | None: ...

    def resume_session(
        self, request: DomainSessionResumeRequest
    ) -> DomainSessionResumeResult: ...

    def resolve_conflict(
        self,
        case: DomainConflictCase,
        *,
        policy: DomainConflictResolutionPolicy | None = None,
        primary_domain: DomainId | None = None,
        highest_risk_domain: DomainId | None = None,
        evidence_scores: Mapping[str, float] | None = None,
        reliability_scores: Mapping[str, float] | None = None,
        temporal_scores: Mapping[str, float] | None = None,
    ) -> DomainConflictResolution: ...

    def assemble_trace(self, request: DomainTraceAssemblyRequest) -> DomainTrace: ...

    def validate_trace(
        self, trace: DomainTrace, inventory: DomainTraceReferenceInventory
    ) -> DomainTraceValidationResult: ...


_REQUIRED_COLLABORATORS = (
    "domain_registry",
    "discovery",
    "validator",
    "loader",
    "resolver",
    "operation_orchestrator",
    "workflow_registry",
    "workflow_executor",
    "session_adapter",
    "session_resumer",
    "conflict_resolver",
    "trace_assembler",
    "trace_validator",
)


class DefaultDomainAPI:
    """Dependency-injected coordination facade over canonical Domain components."""

    def __init__(
        self,
        *,
        domain_registry: DomainRegistry,
        discovery: FileSystemDomainDiscovery,
        validator: PipelineDomainValidator,
        loader: DeclarativeDomainLoader,
        resolver: DefaultDomainResolver,
        operation_orchestrator: DefaultDomainOperationOrchestrator,
        workflow_registry: InMemoryDomainWorkflowRegistry,
        workflow_executor: DomainWorkflowExecutor,
        session_adapter: SharedSessionDomainAdapter,
        session_resumer: DomainSessionResumer,
        conflict_resolver: DomainConflictResolver,
        trace_assembler: DomainTraceAssembler,
        trace_validator: DefaultDomainTraceReferenceValidator,
    ) -> None:
        for name in _REQUIRED_COLLABORATORS:
            if locals()[name] is None:
                raise TypeError(
                    f"DefaultDomainAPI requires an explicit {name} collaborator"
                )
        self._domain_registry = domain_registry
        self._discovery = discovery
        self._validator = validator
        self._loader = loader
        self._resolver = resolver
        self._operation_orchestrator = operation_orchestrator
        self._workflow_registry = workflow_registry
        self._workflow_executor = workflow_executor
        self._session_adapter = session_adapter
        self._session_resumer = session_resumer
        self._conflict_resolver = conflict_resolver
        self._trace_assembler = trace_assembler
        self._trace_validator = trace_validator

    # ── Registry and inspection ──────────────────────────────────────────

    def list_domains(
        self, query: DomainQuery | None = None
    ) -> tuple[DomainDefinition, ...]:
        """Delegate to ``DomainRegistry.list``."""
        return self._domain_registry.list(query)

    def get_domain(
        self, domain_id: str, version: str | None = None
    ) -> DomainDefinition | None:
        """Delegate to the canonical registry lookup."""
        return self._domain_registry.get(domain_id, version)

    def get_capabilities(
        self, domain_id: str, version: str | None = None
    ) -> tuple[Any, ...]:
        """Return the capabilities declared by the canonical definition."""
        definition = self._domain_registry.get_required(domain_id, version)
        return definition.capabilities

    def get_resources(
        self, domain_id: str, version: str | None = None
    ) -> tuple[str, ...]:
        """Delegate to ``DomainRegistry.list_resources``."""
        return self._domain_registry.list_resources(domain_id, version)

    def get_rules(self, domain_id: str, version: str | None = None) -> tuple[str, ...]:
        """Delegate to ``DomainRegistry.list_rules``."""
        return self._domain_registry.list_rules(domain_id, version)

    def get_operations(
        self, domain_id: str, version: str | None = None
    ) -> tuple[str, ...]:
        """Delegate to ``DomainRegistry.list_operations``."""
        return self._domain_registry.list_operations(domain_id, version)

    def get_workflows(
        self, domain_id: str, version: str | None = None
    ) -> tuple[str, ...]:
        """Delegate to ``DomainRegistry.list_workflows``."""
        return self._domain_registry.list_workflows(domain_id, version)

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def discover_domains(
        self, sources: tuple[DomainSource, ...]
    ) -> DomainDiscoveryResult:
        """Delegate to canonical Domain Discovery (non-executing)."""
        return self._discovery.discover(sources)

    def validate_domain(
        self, request: DomainValidationRequest
    ) -> DomainValidationResult:
        """Delegate to canonical Domain Validation."""
        return self._validator.validate(request)

    def install_domain(
        self, candidate: DomainCandidate, *, allow_untrusted: bool = False
    ) -> DomainLoadResult:
        """Delegate to ``DeclarativeDomainLoader.load`` (runtime load only)."""
        return self._loader.load(candidate, allow_untrusted=allow_untrusted)

    def enable_domain(
        self, domain_id: str, version: str | None = None
    ) -> DomainDefinition:
        """Delegate to ``DomainRegistry.enable``."""
        return self._domain_registry.enable(domain_id, version)

    def disable_domain(
        self, domain_id: str, version: str | None = None
    ) -> DomainDefinition:
        """Delegate to ``DomainRegistry.disable``."""
        return self._domain_registry.disable(domain_id, version)

    # ── Resolution ────────────────────────────────────────────────────────

    def resolve_domain(
        self, context: DomainResolutionContext
    ) -> DomainResolutionResult:
        """Delegate to the canonical ``DomainResolver``."""
        return self._resolver.resolve(context)

    # ── Operation execution ───────────────────────────────────────────────

    def execute_operation(
        self, request: DomainOperationRequest
    ) -> DomainOperationResult:
        """Delegate to the authoritative operation orchestrator."""
        return self._operation_orchestrator.execute(request)

    # ── Workflow execution ────────────────────────────────────────────────

    def start_workflow(
        self,
        workflow_id: str,
        context: DomainWorkflowContext,
        inputs: Mapping[str, Any],
    ) -> DomainWorkflowResult:
        """Resolve through the workflow registry and execute canonically."""
        definition = self._workflow_registry.resolve_active(workflow_id)
        return self._workflow_executor.execute_result(definition, context, dict(inputs))

    # ── Sessions ──────────────────────────────────────────────────────────

    def get_session(self, session_id: str) -> DomainSessionContext | None:
        """Delegate to ``SharedSessionDomainAdapter.load_domain_session``."""
        return self._session_adapter.load_domain_session(session_id)

    def resume_session(
        self, request: DomainSessionResumeRequest
    ) -> DomainSessionResumeResult:
        """Delegate to ``DomainSessionResumer.resume``."""
        return self._session_resumer.resume(request)

    # ── Conflicts and traces ──────────────────────────────────────────────

    def resolve_conflict(
        self,
        case: DomainConflictCase,
        *,
        policy: DomainConflictResolutionPolicy | None = None,
        primary_domain: DomainId | None = None,
        highest_risk_domain: DomainId | None = None,
        evidence_scores: Mapping[str, float] | None = None,
        reliability_scores: Mapping[str, float] | None = None,
        temporal_scores: Mapping[str, float] | None = None,
    ) -> DomainConflictResolution:
        """Delegate to the pure ``DomainConflictResolver``."""
        return self._conflict_resolver.resolve(
            case,
            policy=policy,
            primary_domain=primary_domain,
            highest_risk_domain=highest_risk_domain,
            evidence_scores=evidence_scores,
            reliability_scores=reliability_scores,
            temporal_scores=temporal_scores,
        )

    def assemble_trace(self, request: DomainTraceAssemblyRequest) -> DomainTrace:
        """Delegate to ``DomainTraceAssembler.assemble`` (reference-only)."""
        return self._trace_assembler.assemble(request)

    def validate_trace(
        self, trace: DomainTrace, inventory: DomainTraceReferenceInventory
    ) -> DomainTraceValidationResult:
        """Delegate to the canonical trace reference validator."""
        return self._trace_validator.validate(trace, inventory)
