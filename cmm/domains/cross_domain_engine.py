"""Phase 10.9 – Cross-Domain Engine.

``DefaultCrossDomainEngine`` coordinates the Domain Resolver, Domain
Composition, Cognitive Layer, Planner, Agent Runtime, Workflow Engine,
Operation coordination, and Knowledge Graph through narrow injectable
ports. It is an orchestrator — it never reasons, never executes
operations or workflows directly, and never accesses a registry, store,
or the network itself.

Limit accounting convention (explicit, tested in
``tests/domains/test_cross_domain_engine.py``): ``resolver.resolve()`` and
``composer.compose()`` are treated as internal calls and never consume the
``external_calls``/``cost`` budget — only ``knowledge``, ``workflow``, and
``operation`` results report ``external_calls_used``/``estimated_cost``,
because only their result contracts carry those fields. Duration and
iteration/domain capacity are still checked before every port call,
including resolver/composer.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.cross_domain_aggregation import (
    derive_confidence,
    derive_cross_domain_status,
    merge_contradictions,
    merge_dependencies,
    merge_domain_results,
    merge_findings,
    merge_gaps,
    merge_recommendations,
)
from cmm.domains.cross_domain_context import CrossDomainContextBuilder
from cmm.domains.cross_domain_contracts import (
    CrossDomainContextTransfer,
    CrossDomainDecision,
    CrossDomainDomainResult,
    CrossDomainGap,
    CrossDomainKnowledgeResult,
    CrossDomainOperationResult,
    CrossDomainPlanResult,
    CrossDomainPolicy,
    CrossDomainRequest,
    CrossDomainResult,
    CrossDomainWorkflowResult,
)
from cmm.domains.cross_domain_limits import CrossDomainLimitTracker
from cmm.domains.cross_domain_ports import (
    CrossDomainAgentPort,
    CrossDomainCognitivePort,
    CrossDomainKnowledgePort,
    CrossDomainOperationPort,
    CrossDomainPlannerPort,
    CrossDomainWorkflowPort,
    DomainCompositionPort,
    DomainResolutionPort,
)
from cmm.domains.enums import (
    CrossDomainStage,
    CrossDomainStatus,
    DomainCompositionStatus,
    DomainResolutionStatus,
)
from cmm.domains.errors import (
    CrossDomainConfigurationError,
    CrossDomainContractError,
    CrossDomainPortError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.resolver_contracts import DomainResolutionResult


def _decision(
    code: str,
    stage: CrossDomainStage,
    domain_id: DomainId | None,
    action: str,
    *,
    reason: str | None = None,
    blocking: bool = False,
    iteration: int = 0,
) -> CrossDomainDecision:
    return CrossDomainDecision(
        code=code,
        stage=stage,
        domain_id=domain_id,
        action=action,
        reason=reason,
        blocking=blocking,
        iteration=iteration,
    )


def _sort_decisions(
    decisions: tuple[CrossDomainDecision, ...],
) -> tuple[CrossDomainDecision, ...]:
    """Deterministic order: blocking first, iteration, stage, domain, code, action."""
    return tuple(
        sorted(
            decisions,
            key=lambda d: (
                not d.blocking,
                d.iteration,
                d.stage.value,
                d.domain_id.slug if d.domain_id else "",
                d.code,
                d.action,
            ),
        )
    )


class DefaultCrossDomainEngine:
    """Deterministic, synchronous coordinator over injected cross-domain ports."""

    def __init__(
        self,
        *,
        resolver: DomainResolutionPort,
        composer: DomainCompositionPort,
        cognitive: CrossDomainCognitivePort | None = None,
        planner: CrossDomainPlannerPort | None = None,
        agent: CrossDomainAgentPort | None = None,
        workflow: CrossDomainWorkflowPort | None = None,
        operation: CrossDomainOperationPort | None = None,
        knowledge: CrossDomainKnowledgePort | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        trace_id_factory: Callable[[], str] | None = None,
        policy: CrossDomainPolicy | None = None,
    ) -> None:
        if not isinstance(resolver, DomainResolutionPort):
            raise CrossDomainConfigurationError(
                "resolver does not satisfy DomainResolutionPort", field="resolver"
            )
        if not isinstance(composer, DomainCompositionPort):
            raise CrossDomainConfigurationError(
                "composer does not satisfy DomainCompositionPort", field="composer"
            )
        for name, port, protocol in (
            ("cognitive", cognitive, CrossDomainCognitivePort),
            ("planner", planner, CrossDomainPlannerPort),
            ("agent", agent, CrossDomainAgentPort),
            ("workflow", workflow, CrossDomainWorkflowPort),
            ("operation", operation, CrossDomainOperationPort),
            ("knowledge", knowledge, CrossDomainKnowledgePort),
        ):
            if port is not None and not isinstance(port, protocol):
                raise CrossDomainConfigurationError(
                    f"{name} does not satisfy {protocol.__name__}", field=name
                )

        self._resolver = resolver
        self._composer = composer
        self._cognitive = cognitive
        self._planner = planner
        self._agent = agent
        self._workflow = workflow
        self._operation = operation
        self._knowledge = knowledge
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: f"cross-domain-result-{uuid.uuid4()}")
        self._trace_id_factory = trace_id_factory or (
            lambda: f"cross-domain-trace-{uuid.uuid4()}"
        )
        self._policy = policy or CrossDomainPolicy()

    # ── Factory validation ───────────────────────────────────────────────────

    def _next_id(self) -> str:
        value = self._id_factory()
        if not isinstance(value, str) or not value.strip():
            raise CrossDomainConfigurationError(
                "id_factory must return a non-empty string", field="id_factory"
            )
        return value

    def _next_trace_id(self) -> str:
        value = self._trace_id_factory()
        if not isinstance(value, str) or not value.strip():
            raise CrossDomainConfigurationError(
                "trace_id_factory must return a non-empty string",
                field="trace_id_factory",
            )
        return value

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime):
            raise CrossDomainConfigurationError(
                f"clock must return a datetime, got {type(value).__name__}",
                field="clock",
            )
        if value.tzinfo is None:
            raise CrossDomainConfigurationError(
                "clock must return a timezone-aware datetime", field="clock"
            )
        return value

    # ── Public API ───────────────────────────────────────────────────────────

    def execute(self, request: CrossDomainRequest) -> CrossDomainResult:
        """Coordinate cross-domain reasoning, planning, and action for ``request``."""
        if not isinstance(request, CrossDomainRequest):
            raise CrossDomainContractError(
                "request must be a CrossDomainRequest", field="request"
            )

        result_id = self._next_id()
        trace_id = self._next_trace_id()
        started_at = self._now()

        limits = CrossDomainLimitTracker(
            request=request, policy=self._policy, clock=self._clock
        )
        decisions: list[CrossDomainDecision] = []
        required_ports = set(self._policy.required_ports)

        # ── Resolution ───────────────────────────────────────────────────────
        if not limits.has_time_remaining():
            return self._build_early_result(
                result_id=result_id,
                trace_id=trace_id,
                request=request,
                composition_id=None,
                started_at=started_at,
                status=CrossDomainStatus.LIMIT_REACHED,
                decisions=decisions,
                limits=limits,
            )

        resolution = self._resolver.resolve(request)
        if not isinstance(resolution, DomainResolutionResult):
            raise CrossDomainPortError(
                "resolver.resolve() must return a DomainResolutionResult",
                field="resolver",
            )

        early_status = self._evaluate_resolution(resolution, decisions)
        if early_status is not None:
            return self._build_early_result(
                result_id=result_id,
                trace_id=trace_id,
                request=request,
                composition_id=None,
                started_at=started_at,
                status=early_status,
                decisions=decisions,
                limits=limits,
            )

        # ── Composition ──────────────────────────────────────────────────────
        if not limits.has_time_remaining():
            return self._build_early_result(
                result_id=result_id,
                trace_id=trace_id,
                request=request,
                composition_id=None,
                started_at=started_at,
                status=CrossDomainStatus.LIMIT_REACHED,
                decisions=decisions,
                limits=limits,
            )

        composition = self._composer.compose(resolution)
        if not isinstance(composition, DomainComposition):
            raise CrossDomainPortError(
                "composer.compose() must return a DomainComposition", field="composer"
            )

        early_status = self._evaluate_composition(composition, decisions)
        if early_status is not None:
            return self._build_early_result(
                result_id=result_id,
                trace_id=trace_id,
                request=request,
                composition_id=composition.id,
                started_at=started_at,
                status=early_status,
                decisions=decisions,
                limits=limits,
            )

        context = CrossDomainContextBuilder(
            request_id=request.id, composition_id=composition.id, clock=self._clock
        )
        for d in decisions:
            context.add_decision(d)
        active_domains = (composition.primary_domain, *composition.supporting_domains)
        context.set_active_domains(active_domains)

        # ── Knowledge retrieval ──────────────────────────────────────────────
        knowledge_stop = self._retrieve_knowledge(
            active_domains, context, limits, required_ports
        )

        # ── Planning ─────────────────────────────────────────────────────────
        if knowledge_stop:
            plan, planner_stop = None, False
        else:
            plan, planner_stop = self._build_plan(
                composition, context, limits, required_ports
            )
        effective_required_ports = required_ports | set(
            plan.required_ports if plan is not None else ()
        )
        global_stop = knowledge_stop or planner_stop

        # ── Domain order ─────────────────────────────────────────────────────
        domain_order = (
            () if global_stop else self._derive_domain_order(composition, plan)
        )

        # ── Domain execution loop ────────────────────────────────────────────
        blocked_domains: set[str] = set()
        for domain_id in domain_order:
            context.advance_iteration()
            context.mark_visited(domain_id)
            iteration = context.iteration

            if (
                not limits.has_capacity_for_domain()
                or not limits.has_capacity_for_iteration()
                or not limits.has_time_remaining()
            ):
                context.add_decision(
                    _decision(
                        "LIMIT_REACHED",
                        CrossDomainStage.DOMAIN_EXECUTION,
                        domain_id,
                        "stop domain execution: limit reached",
                        iteration=iteration,
                    )
                )
                break

            if domain_id.slug in blocked_domains:
                context.add_decision(
                    _decision(
                        "DOMAIN_SKIPPED",
                        CrossDomainStage.DOMAIN_EXECUTION,
                        domain_id,
                        "skipped: blocked by upstream dependency",
                        blocking=True,
                        iteration=iteration,
                    )
                )
                continue

            limits.record_domain()
            limits.record_iteration()
            context.add_decision(
                _decision(
                    "DOMAIN_SELECTED",
                    CrossDomainStage.DOMAIN_EXECUTION,
                    domain_id,
                    "select domain for execution",
                    iteration=iteration,
                )
            )

            self._transfer_context(
                domain_id, plan, composition, request, context, limits, iteration
            )

            domain_result = self._execute_domain(
                domain_id,
                plan,
                request,
                context,
                limits,
                effective_required_ports,
                iteration,
            )
            if domain_result is None:
                continue

            domain_result = self._clamp_questions(
                domain_result, context, limits, iteration
            )

            context.merge_domain_result(domain_result)
            context.add_decision(
                _decision(
                    "DOMAIN_RESULT_MERGED",
                    CrossDomainStage.DOMAIN_EXECUTION,
                    domain_id,
                    "merge domain result",
                    iteration=iteration,
                )
            )

            if self._domain_is_blocking(domain_result):
                context.add_decision(
                    _decision(
                        "BLOCK_PROPAGATED",
                        CrossDomainStage.DOMAIN_EXECUTION,
                        domain_id,
                        "propagate blocker to dependents",
                        blocking=True,
                        iteration=iteration,
                    )
                )
                context.add_decision(
                    _decision(
                        "PARTIAL_RESULT_RETAINED",
                        CrossDomainStage.DOMAIN_EXECUTION,
                        domain_id,
                        "retain partial result despite block",
                        iteration=iteration,
                    )
                )
                dependents = self._dependents_of(domain_id, plan)
                if self._policy.continue_independent_domains:
                    blocked_domains |= dependents
                else:
                    blocked_domains |= {d.slug for d in domain_order}

        # ── Workflow / operation coordination ───────────────────────────────
        if not global_stop:
            self._coordinate_workflows(
                composition, plan, context, limits, effective_required_ports
            )
            self._coordinate_operations(
                composition, plan, context, limits, effective_required_ports
            )

        return self._finalize(
            result_id=result_id,
            trace_id=trace_id,
            request=request,
            composition_id=composition.id,
            started_at=started_at,
            context=context,
            limits=limits,
            domain_order=domain_order,
        )

    # ── Resolution handling ──────────────────────────────────────────────────

    def _evaluate_resolution(
        self,
        resolution: DomainResolutionResult,
        decisions: list[CrossDomainDecision],
    ) -> CrossDomainStatus | None:
        """Return an early terminal status, or ``None`` if resolution is usable.

        ``INSUFFICIENT_INFORMATION`` only continues execution when the
        resolver explicitly declared the missing information non-blocking
        (``fallback_used=True`` and ``requires_clarification=False``); a gap
        is recorded either way so the missing information is never silently
        forgotten.
        """
        status = resolution.status
        if status == DomainResolutionStatus.RESOLVED:
            return None
        if status == DomainResolutionStatus.INSUFFICIENT_INFORMATION:
            if (
                resolution.primary_domain is not None
                and resolution.fallback_used
                and not resolution.requires_clarification
            ):
                decisions.append(
                    _decision(
                        "PARTIAL_RESULT_RETAINED",
                        CrossDomainStage.RESOLUTION,
                        resolution.primary_domain,
                        "continuing with declared non-blocking missing information",
                    )
                )
                return None
            decisions.append(
                _decision(
                    "HUMAN_REVIEW_REQUESTED",
                    CrossDomainStage.RESOLUTION,
                    None,
                    "insufficient information to resolve a domain",
                )
            )
            return CrossDomainStatus.REQUIRES_REVIEW
        if status == DomainResolutionStatus.AMBIGUOUS:
            decisions.append(
                _decision(
                    "HUMAN_REVIEW_REQUESTED",
                    CrossDomainStage.RESOLUTION,
                    None,
                    "resolution is ambiguous",
                )
            )
            return CrossDomainStatus.REQUIRES_REVIEW
        if status in (
            DomainResolutionStatus.UNSUPPORTED,
            DomainResolutionStatus.BLOCKED,
        ):
            decisions.append(
                _decision(
                    "BLOCK_PROPAGATED",
                    CrossDomainStage.RESOLUTION,
                    None,
                    f"resolution status is {status.value}",
                    blocking=True,
                )
            )
            return CrossDomainStatus.BLOCKED
        return CrossDomainStatus.FAILED

    # ── Composition handling ─────────────────────────────────────────────────

    def _evaluate_composition(
        self,
        composition: DomainComposition,
        decisions: list[CrossDomainDecision],
    ) -> CrossDomainStatus | None:
        """Return an early terminal status, or ``None`` if composition is usable."""
        status = composition.status
        if status == DomainCompositionStatus.COMPOSED:
            return None
        if status == DomainCompositionStatus.PARTIAL:
            decisions.append(
                _decision(
                    "PARTIAL_RESULT_RETAINED",
                    CrossDomainStage.COMPOSITION,
                    None,
                    "composition is partial",
                )
            )
            return None
        if status == DomainCompositionStatus.BLOCKED:
            decisions.append(
                _decision(
                    "BLOCK_PROPAGATED",
                    CrossDomainStage.COMPOSITION,
                    None,
                    "composition is blocked",
                    blocking=True,
                )
            )
            return CrossDomainStatus.BLOCKED
        return CrossDomainStatus.FAILED

    # ── Knowledge ────────────────────────────────────────────────────────────

    def _check_port_capacity(
        self,
        *,
        limits: CrossDomainLimitTracker,
        context: CrossDomainContextBuilder,
        stage: CrossDomainStage,
        action: str,
        domain_id: DomainId | None = None,
        iteration: int = 0,
    ) -> bool:
        """Reject a port call before invocation when any shared limit is exhausted."""
        available = True
        if not limits.has_time_remaining():
            limits.mark_reached("duration")
            available = False
        if not limits.has_capacity_for_external_calls():
            limits.mark_reached("external_calls")
            available = False
        if not limits.has_capacity_for_cost():
            limits.mark_reached("cost")
            available = False
        if not available:
            context.add_decision(
                _decision(
                    "LIMIT_REACHED",
                    stage,
                    domain_id,
                    f"skip {action}: limit reached",
                    iteration=iteration,
                )
            )
        return available

    def _accept_port_usage(
        self,
        *,
        result: object,
        limits: CrossDomainLimitTracker,
        context: CrossDomainContextBuilder,
        stage: CrossDomainStage,
        action: str,
        domain_id: DomainId | None = None,
        iteration: int = 0,
    ) -> bool:
        """Accept a complete port result only when all declared usage fits."""
        external_calls = result.external_calls_used
        estimated_cost = result.estimated_cost
        if not limits.can_accept_usage(
            external_calls=external_calls, estimated_cost=estimated_cost
        ):
            if external_calls > limits.remaining_external_calls():
                limits.mark_reached("external_calls")
            if (
                estimated_cost is not None
                and limits.remaining_cost() is not None
                and estimated_cost > limits.remaining_cost()
            ):
                limits.mark_reached("cost")
            context.add_decision(
                _decision(
                    "LIMIT_REACHED",
                    stage,
                    domain_id,
                    f"reject {action} result: declared consumption exceeds remaining budget",
                    iteration=iteration,
                )
            )
            return False
        limits.record_external_calls(external_calls)
        if estimated_cost is not None:
            limits.record_cost(estimated_cost)
        return True

    def _retrieve_knowledge(
        self,
        active_domains: tuple[DomainId, ...],
        context: CrossDomainContextBuilder,
        limits: CrossDomainLimitTracker,
        required_ports: set[str],
    ) -> bool:
        """Retrieve shared knowledge. Returns whether dependent work must stop."""
        if self._knowledge is None:
            blocking = "knowledge" in required_ports
            context.add_decision(
                _decision(
                    "PORT_UNAVAILABLE" if blocking else "PORT_SKIPPED",
                    CrossDomainStage.KNOWLEDGE,
                    None,
                    "knowledge port unavailable",
                    blocking=blocking,
                )
            )
            return blocking
        if not self._check_port_capacity(
            limits=limits,
            context=context,
            stage=CrossDomainStage.KNOWLEDGE,
            action="knowledge retrieval",
        ):
            return "knowledge" in required_ports
        result = self._knowledge.retrieve(
            domains=active_domains,
            entities=(),
            timelines=(),
            context=context.snapshot(),
        )
        if not isinstance(result, CrossDomainKnowledgeResult):
            raise CrossDomainPortError(
                "knowledge.retrieve() must return a CrossDomainKnowledgeResult",
                field="knowledge",
            )
        if not self._accept_port_usage(
            result=result,
            limits=limits,
            context=context,
            stage=CrossDomainStage.KNOWLEDGE,
            action="knowledge retrieval",
        ):
            return "knowledge" in required_ports
        context.merge_knowledge_result(result)
        context.add_decision(
            _decision(
                "KNOWLEDGE_RETRIEVED",
                CrossDomainStage.KNOWLEDGE,
                None,
                "retrieve knowledge",
            )
        )
        return False

    # ── Planning ─────────────────────────────────────────────────────────────

    def _build_plan(
        self,
        composition: DomainComposition,
        context: CrossDomainContextBuilder,
        limits: CrossDomainLimitTracker,
        required_ports: set[str],
    ) -> tuple[CrossDomainPlanResult | None, bool]:
        """Build a plan. Returns ``(plan, stop_dependent_work)``.

        A required-but-missing planner stops all dependent work rather than
        silently falling back to an implicit composition-order plan.
        """
        if self._planner is None:
            blocking = "planner" in required_ports
            context.add_decision(
                _decision(
                    "PORT_UNAVAILABLE" if blocking else "PORT_SKIPPED",
                    CrossDomainStage.PLANNING,
                    None,
                    "planner port unavailable",
                    blocking=blocking,
                )
            )
            return None, blocking

        if not self._check_port_capacity(
            limits=limits,
            context=context,
            stage=CrossDomainStage.PLANNING,
            action="planning",
        ):
            return None, "planner" in required_ports

        plan = self._planner.plan(composition=composition, context=context.snapshot())
        if not isinstance(plan, CrossDomainPlanResult):
            raise CrossDomainPortError(
                "planner.plan() must return a CrossDomainPlanResult", field="planner"
            )
        if not self._accept_port_usage(
            result=plan,
            limits=limits,
            context=context,
            stage=CrossDomainStage.PLANNING,
            action="planning",
        ):
            return None, "planner" in required_ports
        context.consume_port_usage(plan.external_calls_used, plan.estimated_cost)
        omitted_supporting = self._validate_plan(plan, composition)
        for d in plan.decisions:
            context.add_decision(d)
        context.add_decision(
            _decision("PLAN_CREATED", CrossDomainStage.PLANNING, None, "plan created")
        )
        for slug in sorted(omitted_supporting):
            context.add_decision(
                _decision(
                    "DOMAIN_OMITTED_BY_PLAN",
                    CrossDomainStage.PLANNING,
                    DomainId(slug=slug),
                    "supporting domain omitted from plan domain_order",
                )
            )
        if any(
            len(g) > self._policy.maximum_parallel_group_size
            for g in plan.parallel_groups
        ):
            limits.record_parallel_group_violation()
            context.add_decision(
                _decision(
                    "LIMIT_REACHED",
                    CrossDomainStage.PLANNING,
                    None,
                    "declarative parallel group exceeds maximum_parallel_group_size",
                )
            )
        return plan, False

    def _validate_plan(
        self, plan: CrossDomainPlanResult, composition: DomainComposition
    ) -> set[str]:
        """Validate that the plan never expands scope beyond the composition.

        Returns the set of composed supporting-domain slugs the plan omitted
        from ``domain_order`` (each becomes an explicit, non-blocking
        decision — never a silent drop).
        """
        composed_slugs = {composition.primary_domain.slug} | {
            d.slug for d in composition.supporting_domains
        }

        retrospective_ports = set(plan.required_ports) & {"knowledge", "planner"}
        if retrospective_ports:
            raise CrossDomainPortError(
                "planner cannot require completed stages: "
                f"{sorted(retrospective_ports)}",
                field="planner",
            )

        if {"agent", "cognitive"}.issubset(plan.required_ports):
            declared_domains = {str(domain_id) for domain_id in plan.domain_modes}
            planned_domains = {
                domain_id.slug for domain_id in plan.domain_order
            } or composed_slugs
            if planned_domains - declared_domains:
                raise CrossDomainPortError(
                    "planner must declare domain_modes when both agent and cognitive "
                    "ports are required",
                    field="planner",
                )

        omitted: set[str] = set()
        if plan.domain_order:
            plan_slugs = [d.slug for d in plan.domain_order]
            if len(set(plan_slugs)) != len(plan_slugs):
                raise CrossDomainPortError(
                    "planner produced duplicate domains in domain_order",
                    field="planner",
                )
            extra = set(plan_slugs) - composed_slugs
            if extra:
                raise CrossDomainPortError(
                    f"planner introduced domains not present in composition: {sorted(extra)}",
                    field="planner",
                )
            if plan.domain_order[0].slug != composition.primary_domain.slug:
                raise CrossDomainPortError(
                    "planner plan must place the primary domain first", field="planner"
                )
            omitted = composed_slugs - set(plan_slugs)

        seen_in_groups: set[str] = set()
        for group in plan.parallel_groups:
            for d in group:
                if d.slug in seen_in_groups:
                    raise CrossDomainPortError(
                        f"domain {d.slug!r} appears in more than one parallel_groups entry",
                        field="planner",
                    )
                seen_in_groups.add(d.slug)

        for dep in plan.dependencies:
            if dep.source_domain.slug not in composed_slugs:
                raise CrossDomainPortError(
                    f"planner dependency references domain not present in composition: "
                    f"{dep.source_domain.slug!r}",
                    field="planner",
                )
            if dep.target_domain.slug not in composed_slugs:
                raise CrossDomainPortError(
                    f"planner dependency references domain not present in composition: "
                    f"{dep.target_domain.slug!r}",
                    field="planner",
                )

        return omitted

    def _derive_domain_order(
        self, composition: DomainComposition, plan: CrossDomainPlanResult | None
    ) -> tuple[DomainId, ...]:
        if plan is not None and plan.domain_order:
            return plan.domain_order
        return (composition.primary_domain, *composition.supporting_domains)

    # ── Context transfer ─────────────────────────────────────────────────────

    def _denied_slugs(
        self, request: CrossDomainRequest, composition: DomainComposition
    ) -> set[str]:
        """Slugs explicitly denied by request permissions or composed permissions."""
        denied = {
            p[len("deny:") :] for p in request.permissions if p.startswith("deny:")
        }
        if composition.permissions is not None:
            denied |= {
                p[len("deny:") :]
                for p in composition.permissions.denied_permissions
                if p.startswith("deny:")
            }
        return denied

    def _transfer_context(
        self,
        domain_id: DomainId,
        plan: CrossDomainPlanResult | None,
        composition: DomainComposition,
        request: CrossDomainRequest,
        context: CrossDomainContextBuilder,
        limits: CrossDomainLimitTracker,
        iteration: int,
    ) -> None:
        """Transfer only the findings a plan/dependency justifies, with real provenance.

        Only findings actually produced by the dependency's declared source
        domain are eligible — never the whole shared pool — and each
        transfer carries the finding's own provenance, never the
        dependency's.
        """
        if plan is None:
            return
        denied_slugs = self._denied_slugs(request, composition)
        for dep in plan.dependencies:
            if dep.target_domain.slug != domain_id.slug:
                continue
            if (
                dep.source_domain.slug in denied_slugs
                or dep.target_domain.slug in denied_slugs
            ):
                context.add_decision(
                    _decision(
                        "CONTEXT_TRANSFER_BLOCKED",
                        CrossDomainStage.DOMAIN_EXECUTION,
                        domain_id,
                        "transfer blocked by explicit permission denial",
                        iteration=iteration,
                    )
                )
                continue

            snapshot = context.snapshot()
            eligible = [
                f
                for f in snapshot.shared_findings
                if dep.source_domain.slug in {d.slug for d in f.source_domains}
            ]
            for finding in eligible:
                if not limits.has_capacity_for_hop():
                    context.add_decision(
                        _decision(
                            "CONTEXT_TRANSFER_BLOCKED",
                            CrossDomainStage.DOMAIN_EXECUTION,
                            domain_id,
                            "transfer blocked: hop limit reached",
                            iteration=iteration,
                        )
                    )
                    break
                transfer = CrossDomainContextTransfer(
                    source_domain=dep.source_domain,
                    target_domain=dep.target_domain,
                    kind="finding",
                    identifier=finding.identifier,
                    value=finding.value,
                    reason=dep.description,
                    iteration=iteration,
                    provenance=finding.provenance,
                    private=finding.private,
                    transferable=finding.transferable,
                )
                accepted = context.add_transfer(transfer)
                if accepted:
                    limits.record_hop()
                    context.add_decision(
                        _decision(
                            "CONTEXT_TRANSFERRED",
                            CrossDomainStage.DOMAIN_EXECUTION,
                            domain_id,
                            f"transferred finding {finding.identifier}",
                            iteration=iteration,
                        )
                    )
                else:
                    context.add_decision(
                        _decision(
                            "CONTEXT_TRANSFER_BLOCKED",
                            CrossDomainStage.DOMAIN_EXECUTION,
                            domain_id,
                            f"transfer blocked for finding {finding.identifier}: "
                            "private or non-transferable",
                            iteration=iteration,
                        )
                    )

    # ── Domain execution ─────────────────────────────────────────────────────

    def _select_execution_port(
        self,
        domain_id: DomainId,
        plan: CrossDomainPlanResult | None,
        required_ports: set[str],
    ) -> str | None:
        """Select Cognitive or Agent for ``domain_id``.

        A plan-declared mode is authoritative and never silently falls back
        to the other port. Absent a declaration, Cognitive is the default
        when available.
        """
        declared_mode = None
        if plan is not None:
            declared_mode = plan.domain_modes.get(str(domain_id))

        if declared_mode == "agent":
            return "agent" if self._agent is not None else None
        if declared_mode == "cognitive":
            return "cognitive" if self._cognitive is not None else None

        if {"agent", "cognitive"}.issubset(required_ports):
            return None
        if "cognitive" in required_ports:
            return "cognitive" if self._cognitive is not None else None
        if "agent" in required_ports:
            return "agent" if self._agent is not None else None

        if self._cognitive is not None:
            return "cognitive"
        if self._agent is not None:
            return "agent"
        return None

    def _execute_domain(
        self,
        domain_id: DomainId,
        plan: CrossDomainPlanResult | None,
        request: CrossDomainRequest,
        context: CrossDomainContextBuilder,
        limits: CrossDomainLimitTracker,
        required_ports: set[str],
        iteration: int,
    ) -> CrossDomainDomainResult | None:
        choice = self._select_execution_port(domain_id, plan, required_ports)
        snapshot = context.snapshot()
        if choice == "agent":
            if not self._check_port_capacity(
                limits=limits,
                context=context,
                stage=CrossDomainStage.DOMAIN_EXECUTION,
                action="agent execution",
                domain_id=domain_id,
                iteration=iteration,
            ):
                return None
            domain_result = self._agent.coordinate(
                domain_id=domain_id, plan=plan, context=snapshot
            )
        elif choice == "cognitive":
            if not self._check_port_capacity(
                limits=limits,
                context=context,
                stage=CrossDomainStage.DOMAIN_EXECUTION,
                action="cognitive execution",
                domain_id=domain_id,
                iteration=iteration,
            ):
                return None
            domain_result = self._cognitive.reason(
                domain_id=domain_id, objective=request.objective, context=snapshot
            )
        else:
            declared_mode = plan.domain_modes.get(str(domain_id)) if plan else None
            required = (
                declared_mode in required_ports
                if declared_mode
                else bool({"agent", "cognitive"} & required_ports)
            )
            context.add_decision(
                _decision(
                    "PORT_UNAVAILABLE",
                    CrossDomainStage.DOMAIN_EXECUTION,
                    domain_id,
                    "no reasoning or agent port available for the declared mode",
                    blocking=bool(required),
                    iteration=iteration,
                )
            )
            return None

        if not isinstance(domain_result, CrossDomainDomainResult):
            raise CrossDomainPortError(
                "cognitive/agent port must return a CrossDomainDomainResult",
                field=choice,
            )
        if domain_result.domain_id.slug != domain_id.slug:
            raise CrossDomainPortError(
                "cognitive/agent port returned a mismatched domain_id", field=choice
            )
        if not self._accept_port_usage(
            result=domain_result,
            limits=limits,
            context=context,
            stage=CrossDomainStage.DOMAIN_EXECUTION,
            action=f"{choice} execution",
            domain_id=domain_id,
            iteration=iteration,
        ):
            return None
        return domain_result

    def _clamp_questions(
        self,
        domain_result: CrossDomainDomainResult,
        context: CrossDomainContextBuilder,
        limits: CrossDomainLimitTracker,
        iteration: int,
    ) -> CrossDomainDomainResult:
        """Accept only as many *new* distinct questions as capacity allows.

        Overflow questions are never silently merged past the limit — they
        are dropped from the result and recorded as a recoverable gap plus a
        ``LIMIT_REACHED`` decision.
        """
        if not domain_result.questions:
            return domain_result

        known = set(context.question_identity_keys())
        accepted: list = []
        dropped: list = []
        for q in domain_result.questions:
            key = q.identity_key()
            if key in known:
                accepted.append(q)
                continue
            if limits.has_capacity_for_question():
                accepted.append(q)
                known.add(key)
                limits.record_question()
            else:
                dropped.append(q)

        if not dropped:
            return domain_result

        context.add_decision(
            _decision(
                "LIMIT_REACHED",
                CrossDomainStage.DOMAIN_EXECUTION,
                domain_result.domain_id,
                f"{len(dropped)} question(s) dropped: maximum_questions reached",
                iteration=iteration,
            )
        )
        overflow_gaps = tuple(
            CrossDomainGap(
                code="QUESTION_LIMIT_EXCEEDED",
                domain_id=domain_result.domain_id,
                description=f"Question dropped due to maximum_questions limit: {q.subject}",
                blocking=False,
                recoverable=True,
                provenance=q.provenance,
            )
            for q in dropped
        )
        return CrossDomainDomainResult(
            domain_id=domain_result.domain_id,
            status=domain_result.status,
            findings=domain_result.findings,
            questions=tuple(accepted),
            dependencies=domain_result.dependencies,
            contradictions=domain_result.contradictions,
            gaps=domain_result.gaps + overflow_gaps,
            recommendations=domain_result.recommendations,
            operations=domain_result.operations,
            workflow_requests=domain_result.workflow_requests,
            entities=domain_result.entities,
            timelines=domain_result.timelines,
            confidence=domain_result.confidence,
            external_calls_used=domain_result.external_calls_used,
            estimated_cost=domain_result.estimated_cost,
            metadata=domain_result.metadata,
        )

    def _domain_is_blocking(self, domain_result: CrossDomainDomainResult) -> bool:
        return (
            domain_result.status
            in (CrossDomainStatus.BLOCKED, CrossDomainStatus.FAILED)
            or any(g.blocking for g in domain_result.gaps)
            or any(
                d.blocking
                and not d.satisfied
                and d.source_domain.slug == domain_result.domain_id.slug
                for d in domain_result.dependencies
            )
        )

    def _dependents_of(
        self, domain_id: DomainId, plan: CrossDomainPlanResult | None
    ) -> set[str]:
        dependents: set[str] = set()
        if plan is not None:
            for dep in plan.dependencies:
                if dep.source_domain.slug == domain_id.slug:
                    dependents.add(dep.target_domain.slug)
        return dependents

    # ── Workflow coordination ────────────────────────────────────────────────

    def _collect_workflow_requests(
        self,
        composition: DomainComposition,
        plan: CrossDomainPlanResult | None,
        context: CrossDomainContextBuilder,
    ) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []

        def add(value: str) -> None:
            if value not in seen:
                seen.add(value)
                ordered.append(value)

        for item in composition.workflows:
            add(item.identifier)
        if plan is not None:
            for w in plan.workflow_requests:
                add(w)
        for r in context.snapshot().partial_results:
            for w in r.workflow_requests:
                add(w)
        return tuple(ordered)

    def _coordinate_workflows(
        self,
        composition: DomainComposition,
        plan: CrossDomainPlanResult | None,
        context: CrossDomainContextBuilder,
        limits: CrossDomainLimitTracker,
        required_ports: set[str],
    ) -> None:
        workflow_ids = self._collect_workflow_requests(composition, plan, context)
        if not workflow_ids:
            if self._workflow is None and "workflow" in required_ports:
                context.add_decision(
                    _decision(
                        "PORT_UNAVAILABLE",
                        CrossDomainStage.WORKFLOW_COORDINATION,
                        None,
                        "workflow port unavailable",
                        blocking=True,
                    )
                )
            return
        if self._workflow is None:
            blocking = "workflow" in required_ports
            context.add_decision(
                _decision(
                    "PORT_UNAVAILABLE" if blocking else "PORT_SKIPPED",
                    CrossDomainStage.WORKFLOW_COORDINATION,
                    None,
                    "workflow port unavailable",
                    blocking=blocking,
                )
            )
            return
        if not self._check_port_capacity(
            limits=limits,
            context=context,
            stage=CrossDomainStage.WORKFLOW_COORDINATION,
            action="workflow coordination",
        ):
            return
        result = self._workflow.coordinate(
            workflow_ids=workflow_ids, context=context.snapshot()
        )
        if not isinstance(result, CrossDomainWorkflowResult):
            raise CrossDomainPortError(
                "workflow.coordinate() must return a CrossDomainWorkflowResult",
                field="workflow",
            )
        if not self._accept_port_usage(
            result=result,
            limits=limits,
            context=context,
            stage=CrossDomainStage.WORKFLOW_COORDINATION,
            action="workflow coordination",
        ):
            return
        context.merge_workflow_result(result)
        context.add_decision(
            _decision(
                "WORKFLOW_COORDINATED",
                CrossDomainStage.WORKFLOW_COORDINATION,
                None,
                "workflows coordinated",
            )
        )

    # ── Operation coordination ───────────────────────────────────────────────

    def _collect_operation_requests(
        self,
        composition: DomainComposition,
        plan: CrossDomainPlanResult | None,
        context: CrossDomainContextBuilder,
    ) -> tuple[tuple[str, ...], dict[str, set[str]]]:
        """Collect exact, deduplicated operation ids and their requesting domains."""
        order: list[str] = []
        requesting: dict[str, set[str]] = {}

        def add(op_id: str, domain_slugs: tuple[str, ...]) -> None:
            if op_id not in requesting:
                requesting[op_id] = set()
                order.append(op_id)
            requesting[op_id].update(domain_slugs)

        for item in composition.operations:
            add(item.identifier, tuple(d.slug for d in item.contributing_domains))
        if plan is not None:
            for op in plan.operation_requests:
                add(op, ())
        for r in context.snapshot().partial_results:
            for op in r.operations:
                add(op, (r.domain_id.slug,))
        return tuple(order), requesting

    def _coordinate_operations(
        self,
        composition: DomainComposition,
        plan: CrossDomainPlanResult | None,
        context: CrossDomainContextBuilder,
        limits: CrossDomainLimitTracker,
        required_ports: set[str],
    ) -> None:
        operation_ids, requesting = self._collect_operation_requests(
            composition, plan, context
        )
        if not operation_ids:
            if self._operation is None and "operation" in required_ports:
                context.add_decision(
                    _decision(
                        "PORT_UNAVAILABLE",
                        CrossDomainStage.OPERATION_COORDINATION,
                        None,
                        "operation port unavailable",
                        blocking=True,
                    )
                )
            return
        if self._operation is None:
            blocking = "operation" in required_ports
            context.add_decision(
                _decision(
                    "PORT_UNAVAILABLE" if blocking else "PORT_SKIPPED",
                    CrossDomainStage.OPERATION_COORDINATION,
                    None,
                    "operation port unavailable",
                    blocking=blocking,
                )
            )
            return

        remaining = limits.remaining_operations()
        if remaining <= 0:
            context.add_decision(
                _decision(
                    "LIMIT_REACHED",
                    CrossDomainStage.OPERATION_COORDINATION,
                    None,
                    "operation limit reached",
                )
            )
            return
        accepted_ids = operation_ids[:remaining]
        dropped_ids = operation_ids[remaining:]

        if not self._check_port_capacity(
            limits=limits,
            context=context,
            stage=CrossDomainStage.OPERATION_COORDINATION,
            action="operation coordination",
        ):
            return

        requesting_domains_map = {
            op_id: tuple(DomainId(slug=s) for s in sorted(requesting[op_id]))
            for op_id in accepted_ids
        }
        result = self._operation.coordinate_operations(
            operation_ids=accepted_ids,
            requesting_domains=requesting_domains_map,
            context=context.snapshot(),
        )
        if not isinstance(result, CrossDomainOperationResult):
            raise CrossDomainPortError(
                "operation.coordinate_operations() must return a CrossDomainOperationResult",
                field="operation",
            )
        if not self._accept_port_usage(
            result=result,
            limits=limits,
            context=context,
            stage=CrossDomainStage.OPERATION_COORDINATION,
            action="operation coordination",
        ):
            return
        context.merge_operation_result(result)
        limits.record_operations(len(accepted_ids))
        if dropped_ids:
            context.add_decision(
                _decision(
                    "LIMIT_REACHED",
                    CrossDomainStage.OPERATION_COORDINATION,
                    None,
                    f"{len(dropped_ids)} operation(s) dropped: maximum_operations reached",
                )
            )
        context.add_decision(
            _decision(
                "OPERATION_COORDINATED",
                CrossDomainStage.OPERATION_COORDINATION,
                None,
                "operations coordinated",
            )
        )

    # ── Result construction ──────────────────────────────────────────────────

    def _build_early_result(
        self,
        *,
        result_id: str,
        trace_id: str,
        request: CrossDomainRequest,
        composition_id: str | None,
        started_at: datetime,
        status: CrossDomainStatus,
        decisions: list[CrossDomainDecision],
        limits: CrossDomainLimitTracker,
    ) -> CrossDomainResult:
        completed_at = self._now()
        return CrossDomainResult(
            id=result_id,
            status=status,
            objective=request.objective,
            request_id=request.id,
            composition_id=composition_id,
            decisions=_sort_decisions(tuple(decisions)),
            limits=limits.snapshot(),
            confidence=None,
            trace_id=trace_id,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _finalize(
        self,
        *,
        result_id: str,
        trace_id: str,
        request: CrossDomainRequest,
        composition_id: str,
        started_at: datetime,
        context: CrossDomainContextBuilder,
        limits: CrossDomainLimitTracker,
        domain_order: tuple[DomainId, ...],
    ) -> CrossDomainResult:
        snapshot = context.snapshot()
        domain_results = merge_domain_results(snapshot.partial_results)
        shared_findings = merge_findings(
            snapshot.shared_findings, *(r.findings for r in domain_results)
        )
        recommendations = merge_recommendations(
            *(r.recommendations for r in domain_results)
        )
        dependencies = merge_dependencies(
            snapshot.dependencies, *(r.dependencies for r in domain_results)
        )
        contradictions = merge_contradictions(
            snapshot.contradictions, *(r.contradictions for r in domain_results)
        )
        gaps = merge_gaps(snapshot.gaps, *(r.gaps for r in domain_results))
        open_questions = snapshot.open_questions
        decisions_final = _sort_decisions(snapshot.decisions)

        limits_snapshot = limits.snapshot()

        any_domain_blocking = any(self._domain_is_blocking(r) for r in domain_results)
        required_port_missing_blocking = any(
            d.blocking and d.code == "PORT_UNAVAILABLE" for d in decisions_final
        )
        global_block_decision = any(
            d.blocking and d.code == "BLOCK_PROPAGATED" and d.domain_id is None
            for d in decisions_final
        )
        has_useful_output = bool(domain_results or shared_findings or recommendations)

        is_blocked = (
            required_port_missing_blocking
            or global_block_decision
            or (not self._policy.continue_independent_domains and any_domain_blocking)
            or (any_domain_blocking and not has_useful_output)
        )

        requires_review = any(
            c.requires_review and not c.resolved for c in contradictions
        ) or any(d.code == "HUMAN_REVIEW_REQUESTED" for d in decisions_final)
        if self._policy.require_review_for_high_severity:
            requires_review = requires_review or any(
                c.severity.value in ("high", "critical") and not c.resolved
                for c in contradictions
            )

        incomplete_domains = len(domain_order) - len(domain_results)
        all_domains_completed = (
            has_useful_output
            and incomplete_domains == 0
            and all(r.status == CrossDomainStatus.COMPLETED for r in domain_results)
        )

        status = derive_cross_domain_status(
            is_blocked=is_blocked,
            limit_reached=bool(limits_snapshot.reached_limits),
            requires_review=requires_review,
            has_useful_output=has_useful_output,
            all_domains_completed=all_domains_completed,
        )

        if status == CrossDomainStatus.REQUIRES_REVIEW and not any(
            d.code == "HUMAN_REVIEW_REQUESTED" for d in decisions_final
        ):
            decisions_final = _sort_decisions(
                (
                    *decisions_final,
                    _decision(
                        "HUMAN_REVIEW_REQUESTED",
                        CrossDomainStage.AGGREGATION,
                        None,
                        "unresolved high-severity contradiction requires review",
                    ),
                )
            )

        confidence = derive_confidence(
            domain_results,
            self._policy,
            unresolved_contradiction=any(not c.resolved for c in contradictions),
            unresolved_gap=bool(gaps),
            skipped_required_domain=incomplete_domains > 0,
            unavailable_required_port=required_port_missing_blocking,
            limit_reached=bool(limits_snapshot.reached_limits),
        )

        completed_at = self._now()

        return CrossDomainResult(
            id=result_id,
            status=status,
            objective=request.objective,
            request_id=request.id,
            composition_id=composition_id,
            domain_results=domain_results,
            shared_findings=shared_findings,
            contradictions=contradictions,
            dependencies=dependencies,
            cross_domain_gaps=gaps,
            recommendations=recommendations,
            open_questions=open_questions,
            decisions=decisions_final,
            limits=limits_snapshot,
            confidence=confidence,
            trace_id=trace_id,
            started_at=started_at,
            completed_at=completed_at,
        )


__all__ = ["DefaultCrossDomainEngine"]
