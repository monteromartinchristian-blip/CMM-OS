"""Phase 10.36 — Domain API.

One stable public coordination facade over the existing canonical Domain
Intelligence subsystems. The facade owns coordination and public ergonomics
only; every method delegates to an existing canonical owner:

- registry / inspection  -> ``DomainRegistry``
- discovery              -> ``DomainDiscovery`` protocol (non-executing)
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
  ``DomainTraceReferenceValidator`` protocol (reference-only)
- activation trust       -> pure ``evaluate_domain_trust`` (Phase 10.38):
  explicit trust boundary enforced before registry enablement

The facade retains references to injected collaborators and owns no shadow
runtime state, no caches, no stores, and no registries. Canonical subsystem
errors propagate unchanged.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from cmm.domains.conflict_resolution import DomainConflictResolver
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictCase,
    DomainConflictResolution,
    DomainConflictResolutionPolicy,
)
from cmm.domains.contracts import DomainCapability, DomainDefinition
from cmm.domains.discovery import DomainDiscovery
from cmm.domains.discovery_contracts import (
    DomainCandidate,
    DomainDiscoveryResult,
    DomainSource,
)
from cmm.domains.enums import DomainSourceKind
from cmm.domains.errors import DomainRegistryValidationError
from cmm.domains.identifiers import DomainId
from cmm.domains.loader import DeclarativeDomainLoader
from cmm.domains.loader_contracts import DomainLoadResult
from cmm.domains.memory_contracts import (
    DomainMemoryReferenceInventory,
    DomainMemoryView,
    DomainMemoryViewRequest,
)
from cmm.domains.memory_knowledge_integration import (
    DefaultDomainMemoryKnowledgeIntegrator,
)
from cmm.domains.memory_knowledge_integration_contracts import (
    DomainMemoryKnowledgeIntegrator,
    DomainMemoryKnowledgeInventory,
    DomainMemoryKnowledgeProjection,
    DomainMemoryKnowledgeProjectionRequest,
)
from cmm.domains.operation_contracts import (
    DomainOperationRequest,
    DomainOperationResult,
)
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainQuery
from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resolver import DomainResolver
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
from cmm.domains.trace_validation import DomainTraceReferenceValidator
from cmm.domains.trust_contracts import DomainTrustPolicy
from cmm.domains.trust_evaluator import (
    evaluate_domain_trust,
    is_terminal_validation_evidence,
)
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
    ) -> tuple[DomainCapability, ...]: ...

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

    def project_memory_knowledge(
        self,
        request: DomainMemoryKnowledgeProjectionRequest,
        *,
        memory_request: DomainMemoryViewRequest,
        view: DomainMemoryView,
        memory_inventory: DomainMemoryReferenceInventory,
        inventory: DomainMemoryKnowledgeInventory,
    ) -> DomainMemoryKnowledgeProjection: ...


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
        discovery: DomainDiscovery,
        validator: PipelineDomainValidator,
        loader: DeclarativeDomainLoader,
        resolver: DomainResolver,
        operation_orchestrator: DefaultDomainOperationOrchestrator,
        workflow_registry: InMemoryDomainWorkflowRegistry,
        workflow_executor: DomainWorkflowExecutor,
        session_adapter: SharedSessionDomainAdapter,
        session_resumer: DomainSessionResumer,
        conflict_resolver: DomainConflictResolver,
        trace_assembler: DomainTraceAssembler,
        trace_validator: DomainTraceReferenceValidator,
        trust_policy_lookup: Callable[[str], DomainTrustPolicy | None] | None = None,
        memory_knowledge_integrator: DomainMemoryKnowledgeIntegrator | None = None,
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
        self._trust_policy_lookup = trust_policy_lookup
        self._memory_knowledge_integrator = (
            memory_knowledge_integrator
            if memory_knowledge_integrator is not None
            else DefaultDomainMemoryKnowledgeIntegrator()
        )

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
    ) -> tuple[DomainCapability, ...]:
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
        """Explicitly enable a Domain through the canonical registry.

        Phase 10.38 trust boundary: external/non-internal candidates require
        an explicit trust policy before registry mutation. ``candidate.trusted``
        is never authority. A trusted INTERNAL candidate with no explicit
        trust policy preserves the existing Phase 10.36 activation behavior.
        """
        loaded = self._loader.get_loaded(domain_id, version)
        if loaded is None or loaded.candidate is None or loaded.pack is None:
            # Preserve canonical lifecycle error semantics for registries
            # that already own the record (e.g. DomainRegistryNotFound).
            return self._domain_registry.enable(domain_id, version)
        candidate = loaded.candidate

        trust_policy: DomainTrustPolicy | None = None
        if self._trust_policy_lookup is not None:
            trust_policy = self._trust_policy_lookup(candidate.domain_id)

        internal_trusted = (
            candidate.source_kind is DomainSourceKind.INTERNAL
            and candidate.trusted
            and trust_policy is None
        )
        if trust_policy is None and not internal_trusted:
            raise DomainRegistryValidationError(
                "External/non-internal Domain activation requires an explicit "
                "trust policy",
                field="domain_id",
                details={
                    "domain_id": candidate.domain_id,
                    "candidate_id": candidate.candidate_id,
                    "source_id": candidate.source_id,
                    "trust_level": None,
                    "reason_codes": ["trust.policy_required"],
                },
            )

        # Fresh canonical validation for the exact loaded candidate/pack.
        # Test execution is deferred by the canonical pipeline; the trust
        # boundary requires the mandatory manifest/contracts/security/limits
        # checks, not the deferred test-run step.
        validation = self._validator.validate(
            DomainValidationRequest(
                pack=loaded.pack,
                root_path=loaded.pack.root_path,
                candidate=candidate,
                strict=True,
                run_tests=False,
                excluded_steps=("domain.tests",),
            )
        )
        # V1 MAJOR-01: only terminal validation evidence may activate.  A
        # structurally coherent PENDING/RUNNING result is not a finished
        # decision and must fail closed on every activation path, including
        # the trusted-INTERNAL/no-policy compatibility path below.
        if not is_terminal_validation_evidence(validation.status):
            raise DomainRegistryValidationError(
                "Domain activation requires terminal validation evidence",
                field="domain_id",
                details={
                    "domain_id": candidate.domain_id,
                    "candidate_id": candidate.candidate_id,
                    "source_id": candidate.source_id,
                    "trust_level": None,
                    "reason_codes": ["trust.validation_failed"],
                },
            )
        if not validation.is_install_allowed:
            raise DomainRegistryValidationError(
                "Domain activation blocked by canonical validation",
                field="domain_id",
                details={
                    "domain_id": candidate.domain_id,
                    "candidate_id": candidate.candidate_id,
                    "source_id": candidate.source_id,
                    "trust_level": None,
                    "reason_codes": ["trust.validation_failed"],
                },
            )

        if trust_policy is not None:
            decision = evaluate_domain_trust(
                candidate=candidate,
                manifest=loaded.pack.manifest,
                validation=validation,
                policy=trust_policy,
                manual_enable_requested=True,
            )
            if not decision.activation_allowed:
                raise DomainRegistryValidationError(
                    "Domain activation denied by trust policy",
                    field="domain_id",
                    details={
                        "domain_id": decision.domain_id,
                        "candidate_id": decision.candidate_id,
                        "source_id": decision.source_id,
                        "trust_level": decision.trust_level.value,
                        "reason_codes": list(decision.reason_codes),
                    },
                )

        # Registry mutation happens only after a successful trust decision.
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

    # ── Memory and knowledge integration ─────────────────────────────────

    def project_memory_knowledge(
        self,
        request: DomainMemoryKnowledgeProjectionRequest,
        *,
        memory_request: DomainMemoryViewRequest,
        view: DomainMemoryView,
        memory_inventory: DomainMemoryReferenceInventory,
        inventory: DomainMemoryKnowledgeInventory,
    ) -> DomainMemoryKnowledgeProjection:
        """Delegate to the pure ``DomainMemoryKnowledgeIntegrator``."""
        return self._memory_knowledge_integrator.project(
            request,
            memory_request=memory_request,
            view=view,
            memory_inventory=memory_inventory,
            inventory=inventory,
        )
