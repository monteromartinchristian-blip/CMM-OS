"""Phase 9.5 – Cognitive Adapter Implementation and Service.

Translates between Agent Runtime operational contracts (Goal, AgentRun, ObservationSnapshot,
Resources, Knowledge) and the Cognitive Layer (Phase 8), returning structured operational
recommendations without executing planning, operations, or automatic memory persistence.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from cmm.agent_runtime.cognitive_adapter_contracts import (
    AgentCognitiveConfiguration,
    AgentCognitiveContext,
    AgentCognitiveRequest,
    AgentCognitiveResult,
    AgentCognitiveSessionReference,
    AgentCognitiveWarning,
    generate_cognitive_context_id,
    generate_cognitive_result_id,
)
from cmm.agent_runtime.contracts import AgentRun
from cmm.agent_runtime.enums import (
    AgentCognitiveDecision,
    AgentCognitiveStatus,
    CognitiveSessionMode,
)
from cmm.agent_runtime.errors import (
    CognitiveAdapterExecutionError,
    CognitiveProfileResolutionError,
    CognitiveResourceAccessError,
    CognitiveSessionMismatchError,
    CognitiveSessionNotFoundError,
    GoalError,
    InvalidAgentCognitiveContractError,
    ObservationEngineError,
)
from cmm.agent_runtime.goal_contracts import Goal
from cmm.agent_runtime.observation_cognitive_adapter import (
    ObservationResourceAdapter,
)
from cmm.agent_runtime.observation_contracts import ObservationSnapshot
from cmm.cognitive.contracts import (
    CognitiveFinding,
    CognitiveResult,
    CognitiveStatus,
    Confidence,
    utc_now,
)
from cmm.cognitive.enums import SensitivityLevel
from cmm.cognitive.resources import Resource


class CognitiveRuntimeAdapter(Protocol):
    """Protocol defining the Cognitive Runtime Adapter interface."""

    def analyze(self, request: AgentCognitiveRequest) -> AgentCognitiveResult:
        """Perform cognitive analysis for an agent request."""
        ...

    def resume(self, request: AgentCognitiveRequest) -> AgentCognitiveResult:
        """Resume a suspended or existing cognitive session."""
        ...

    def build_context(self, request: AgentCognitiveRequest) -> AgentCognitiveContext:
        """Construct auditable evidence context prior to cognitive analysis."""
        ...

    def translate_result(
        self,
        cognitive_result: CognitiveResult | Any,
        request: AgentCognitiveRequest,
    ) -> AgentCognitiveResult:
        """Translate Cognitive Layer output into operational AgentCognitiveResult."""
        ...

    def get_session_reference(
        self, session_id: str
    ) -> AgentCognitiveSessionReference | None:
        """Retrieve reference metadata for a cognitive session."""
        ...


class DefaultCognitiveRuntimeAdapter:
    """Default implementation of CognitiveRuntimeAdapter.

    Acts as a bridge between Agent Runtime and Cognitive Layer (Phase 8).
    """

    def __init__(
        self,
        cognitive_layer: Any | None = None,
        goal_manager: Any | None = None,
        snapshot_repository: Any | None = None,
        knowledge_store: Any | None = None,
        observation_adapter: ObservationResourceAdapter | None = None,
        profile_resolver: Callable[[str, Goal | None, AgentRun | None], str]
        | None = None,
        session_service: Any | None = None,
        configuration: AgentCognitiveConfiguration | None = None,
    ) -> None:
        self._cognitive_layer = cognitive_layer
        self._goal_manager = goal_manager
        self._snapshot_repository = snapshot_repository
        self._knowledge_store = knowledge_store
        self._observation_adapter = observation_adapter or ObservationResourceAdapter()
        self._profile_resolver = profile_resolver
        self._session_service = session_service
        self._configuration = configuration or AgentCognitiveConfiguration()
        self._sessions: dict[str, AgentCognitiveSessionReference] = {}

    def get_session_reference(
        self, session_id: str
    ) -> AgentCognitiveSessionReference | None:
        """Retrieve reference metadata for a cognitive session."""
        if not session_id or not session_id.strip():
            return None
        if self._session_service and hasattr(self._session_service, "get_session"):
            res = self._session_service.get_session(session_id)
            if isinstance(res, AgentCognitiveSessionReference):
                return res
        return self._sessions.get(session_id)

    def _resolve_profile(
        self,
        request: AgentCognitiveRequest,
        goal: Goal | None,
        agent_run: AgentRun | None,
    ) -> str:
        """Resolve cognitive reasoning profile deterministically."""
        if self._profile_resolver is not None:
            try:
                resolved = self._profile_resolver(
                    request.reasoning_profile, goal, agent_run
                )
                if resolved and resolved.strip():
                    return resolved
            except Exception as exc:
                raise CognitiveProfileResolutionError(
                    f"Profile resolver failed for '{request.reasoning_profile}': {exc}"
                ) from exc

        if request.reasoning_profile and request.reasoning_profile != "general":
            return request.reasoning_profile

        if goal and goal.metadata and "reasoning_profile" in goal.metadata:
            return str(goal.metadata["reasoning_profile"])

        if (
            agent_run
            and agent_run.metadata
            and "reasoning_profile" in agent_run.metadata
        ):
            return str(agent_run.metadata["reasoning_profile"])

        return self._configuration.default_profile

    def _deduplicate_resources(
        self, resources: Sequence[Resource]
    ) -> tuple[Resource, ...]:
        """Deduplicate resources deterministically while maintaining order."""
        seen: set[str] = set()
        deduped: list[Resource] = []

        for res in resources:
            if res.id and res.id in seen:
                continue
            key = (
                res.id
                if res.id
                else f"{res.domain}:{res.kind.value}:{res.provenance.source_id}"
            )
            if key in seen:
                continue
            seen.add(key)
            if res.id:
                seen.add(res.id)
            deduped.append(res)

        return tuple(deduped)

    def _check_resource_permissions(
        self,
        resources: Sequence[Resource],
        permissions: tuple[str, ...],
    ) -> tuple[Resource, ...]:
        """Verify sensitivity levels and permissions for resources."""
        allowed_resources: list[Resource] = []
        permission_set = set(permissions)

        for res in resources:
            # RESTRICTED resources require 'restricted_access' permission unless explicitly allowed
            if (
                res.sensitivity is SensitivityLevel.RESTRICTED
                and "restricted_access" not in permission_set
                and "admin" not in permission_set
            ):
                raise CognitiveResourceAccessError(
                    f"Access denied for RESTRICTED resource '{res.id or res.provenance.source_id}'. "
                    f"Required permission missing."
                )

            # SENSITIVE resources require 'sensitive_access', 'restricted_access', 'internal_access' or 'admin'
            if (
                res.sensitivity
                in (SensitivityLevel.SENSITIVE, SensitivityLevel.HIGHLY_SENSITIVE)
                and permission_set
                and not permission_set.intersection(
                    {
                        "sensitive_access",
                        "restricted_access",
                        "internal_access",
                        "admin",
                    }
                )
            ):
                raise CognitiveResourceAccessError(
                    f"Access denied for SENSITIVE resource '{res.id or res.provenance.source_id}'."
                )

            allowed_resources.append(res)

        return tuple(allowed_resources)

    def build_context(self, request: AgentCognitiveRequest) -> AgentCognitiveContext:
        """Prepare auditable evidence context before invoking Cognitive Layer."""
        if not isinstance(request, AgentCognitiveRequest):
            raise InvalidAgentCognitiveContractError(
                "request must be an instance of AgentCognitiveRequest"
            )

        # 1. Fetch Goal if manager available
        goal: Goal | None = None
        if self._goal_manager and hasattr(self._goal_manager, "get_goal"):
            try:
                goal = self._goal_manager.get_goal(request.goal_id)
            except (GoalError, KeyError, ValueError, RuntimeError):
                goal = None

        # 2. Fetch Snapshot if repository available
        snapshot: ObservationSnapshot | None = request.observation_snapshot
        if (
            snapshot is None
            and request.observation_snapshot_id
            and self._snapshot_repository
            and hasattr(self._snapshot_repository, "get_snapshot")
        ):
            try:
                snapshot = self._snapshot_repository.get_snapshot(
                    request.observation_snapshot_id
                )
            except (ObservationEngineError, KeyError, ValueError, RuntimeError):
                snapshot = None

        # 3. Derive resources from snapshot
        derived_resources: tuple[Resource, ...] = ()
        if snapshot:
            derived_resources = self._observation_adapter.from_snapshot(snapshot)

        # 4. Explicit resources
        explicit_resources: tuple[Resource, ...] = request.resources

        # 5. Combine and deduplicate
        all_raw_resources = list(derived_resources) + list(explicit_resources)

        # 6. Fetch resources by ID if requested & provider available
        cognitive_layer = self._cognitive_layer
        if (
            request.resource_ids
            and cognitive_layer is not None
            and hasattr(cognitive_layer, "get_resource")
        ):
            for r_id in request.resource_ids:
                try:
                    res = cognitive_layer.get_resource(r_id)
                    if isinstance(res, Resource):
                        all_raw_resources.append(res)
                except (KeyError, ValueError, AttributeError, RuntimeError):
                    continue

        # Deduplicate
        combined_resources = self._deduplicate_resources(all_raw_resources)

        # Check permissions
        combined_resources = self._check_resource_permissions(
            combined_resources, request.permissions
        )

        # Apply resource max limit
        if len(combined_resources) > self._configuration.max_resources:
            combined_resources = combined_resources[: self._configuration.max_resources]

        # 7. Resolve profile
        profile = self._resolve_profile(request, goal, None)

        # 8. Handle Session
        session_ref: AgentCognitiveSessionReference | None = None
        if request.session_mode is CognitiveSessionMode.NEW:
            s_id = f"cog-session-{uuid.uuid4().hex[:12]}"
            session_ref = AgentCognitiveSessionReference(
                session_id=s_id,
                mode=CognitiveSessionMode.NEW,
                goal_id=request.goal_id,
                created_at=utc_now(),
            )
            self._sessions[s_id] = session_ref
        elif request.session_mode is CognitiveSessionMode.RESUME:
            if not request.cognitive_session_id:
                raise InvalidAgentCognitiveContractError(
                    "cognitive_session_id is required for RESUME mode"
                )
            existing = self.get_session_reference(request.cognitive_session_id)
            if existing is None:
                raise CognitiveSessionNotFoundError(
                    f"Cognitive session '{request.cognitive_session_id}' not found."
                )
            if existing.goal_id and existing.goal_id != request.goal_id:
                raise CognitiveSessionMismatchError(
                    f"Cognitive session '{request.cognitive_session_id}' belongs to goal "
                    f"'{existing.goal_id}', not '{request.goal_id}'."
                )
            session_ref = AgentCognitiveSessionReference(
                session_id=existing.session_id,
                mode=CognitiveSessionMode.RESUME,
                parent_session_id=existing.parent_session_id,
                goal_id=request.goal_id,
                created_at=utc_now(),
            )
        elif request.session_mode is CognitiveSessionMode.FORK:
            parent_id = request.cognitive_session_id
            s_id = f"cog-session-fork-{uuid.uuid4().hex[:12]}"
            session_ref = AgentCognitiveSessionReference(
                session_id=s_id,
                mode=CognitiveSessionMode.FORK,
                parent_session_id=parent_id,
                goal_id=request.goal_id,
                created_at=utc_now(),
            )
            self._sessions[s_id] = session_ref
        elif request.session_mode is CognitiveSessionMode.STATELESS:
            session_ref = None

        return AgentCognitiveContext(
            id=generate_cognitive_context_id(),
            request_id=request.id,
            goal=goal,
            observation_snapshot=snapshot,
            derived_resources=derived_resources,
            explicit_resources=explicit_resources,
            combined_resources=combined_resources,
            knowledge_query=request.knowledge_query,
            constraints=request.constraints,
            permissions=request.permissions,
            reasoning_profile=profile,
            session_reference=session_ref,
            temporal_reference=request.temporal_reference,
            maximum_questions=request.maximum_questions,
            requested_depth=request.requested_depth,
            actor_id=request.actor_id,
            metadata=dict(request.metadata),
            created_at=utc_now(),
        )

    def translate_result(
        self,
        cognitive_result: CognitiveResult | Any,
        request: AgentCognitiveRequest,
    ) -> AgentCognitiveResult:
        """Translate Cognitive Layer result into operational AgentCognitiveResult."""
        if not isinstance(request, AgentCognitiveRequest):
            raise InvalidAgentCognitiveContractError(
                "request must be AgentCognitiveRequest"
            )

        # Extract fields from CognitiveResult or dict/object
        if isinstance(cognitive_result, CognitiveResult):
            cog_id = cognitive_result.id
            cog_status = cognitive_result.status
            cog_confidence = cognitive_result.confidence.value
            findings = cognitive_result.findings
            trace_id = cognitive_result.trace_id
            session_id = cognitive_result.session_id
            metadata = dict(cognitive_result.metadata)
        elif isinstance(cognitive_result, dict):
            cog_id = str(cognitive_result.get("id") or generate_cognitive_result_id())
            cog_status_str = cognitive_result.get("status", "completed")
            try:
                cog_status = CognitiveStatus(cog_status_str)
            except ValueError:
                cog_status = CognitiveStatus.COMPLETED
            conf_val = cognitive_result.get("confidence", 1.0)
            cog_confidence = (
                conf_val.get("value", 1.0)
                if isinstance(conf_val, dict)
                else float(conf_val)
            )
            findings = tuple(
                CognitiveFinding.from_dict(f) if isinstance(f, dict) else f
                for f in cognitive_result.get("findings", ())
            )
            trace_id = cognitive_result.get("trace_id")
            session_id = cognitive_result.get("session_id")
            metadata = cognitive_result.get("metadata", {})
        else:
            cog_id = getattr(cognitive_result, "id", f"cog-res-{uuid.uuid4().hex[:8]}")
            cog_status = getattr(cognitive_result, "status", CognitiveStatus.COMPLETED)
            conf_obj = getattr(cognitive_result, "confidence", 1.0)
            cog_confidence = (
                getattr(conf_obj, "value", float(conf_obj))
                if not isinstance(conf_obj, (int, float))
                else float(conf_obj)
            )
            findings = tuple(getattr(cognitive_result, "findings", ()))
            trace_id = getattr(cognitive_result, "trace_id", None)
            session_id = getattr(cognitive_result, "session_id", None)
            metadata = getattr(cognitive_result, "metadata", {})

        # Analyze findings for questions, gaps, contradictions, errors
        questions: list[Any] = []
        gaps: list[Any] = []
        contradictions: list[Any] = []
        warnings: list[AgentCognitiveWarning] = []
        errors: list[str] = []
        blocking_question_present = False
        blocking_resource_gap_present = False
        blocking_unresolvable_gap_present = False
        requires_user_input = False
        requires_resource = False

        # Extract structured findings if present
        for finding in findings:
            if hasattr(finding, "code"):
                code = finding.code.lower()
                msg = finding.message
                is_blocking = getattr(finding, "blocking", False)

                if "question" in code or "ask_user" in code:
                    questions.append(finding)
                    requires_user_input = True
                    if is_blocking:
                        blocking_question_present = True

                elif "gap" in code or "missing" in code or "resource" in code:
                    gaps.append(finding)
                    if "unresolvable" in code:
                        if is_blocking:
                            blocking_unresolvable_gap_present = True
                    elif (
                        "load_resource" in code
                        or "resource" in code
                        or "resolvable" in code
                    ):
                        requires_resource = True
                        if is_blocking:
                            blocking_resource_gap_present = True
                    else:
                        if is_blocking:
                            blocking_unresolvable_gap_present = True

                elif "contradiction" in code:
                    contradictions.append(finding)

                elif "error" in code or "fail" in code:
                    errors.append(f"{finding.code}: {msg}")

                if getattr(finding, "severity", None) and str(
                    finding.severity
                ).lower() in ("warning", "warn"):
                    warnings.append(
                        AgentCognitiveWarning(
                            code=finding.code,
                            message=msg,
                            source=getattr(finding, "source", "cognitive"),
                        )
                    )

        # Extract explicit custom fields from metadata if passed
        explicit_questions = metadata.get("questions")
        if explicit_questions:
            questions.extend(explicit_questions)
            requires_user_input = True
            if metadata.get("blocking_question", False):
                blocking_question_present = True

        explicit_gaps = metadata.get("information_gaps")
        if explicit_gaps:
            gaps.extend(explicit_gaps)
            if metadata.get("blocking_resource_gap", False):
                blocking_resource_gap_present = True
                requires_resource = True
            elif metadata.get("blocking_unresolvable_gap", False):
                blocking_unresolvable_gap_present = True

        explicit_contradictions = metadata.get("contradictions")
        if explicit_contradictions:
            contradictions.extend(explicit_contradictions)

        # Determine AgentCognitiveDecision & AgentCognitiveStatus deterministically
        if errors or cog_status is CognitiveStatus.FAILED:
            status = AgentCognitiveStatus.FAILED
            decision = AgentCognitiveDecision.FAIL
        elif (
            blocking_question_present or cog_status is CognitiveStatus.WAITING_FOR_USER
        ):
            status = AgentCognitiveStatus.WAITING_FOR_USER
            decision = AgentCognitiveDecision.ASK_USER
        elif (
            blocking_resource_gap_present
            or cog_status is CognitiveStatus.WAITING_FOR_RESOURCE
        ):
            status = AgentCognitiveStatus.WAITING_FOR_RESOURCE
            decision = AgentCognitiveDecision.LOAD_RESOURCE
        elif (
            blocking_unresolvable_gap_present
            or cog_status is CognitiveStatus.INSUFFICIENT_INFORMATION
        ):
            status = AgentCognitiveStatus.INSUFFICIENT_INFORMATION
            decision = AgentCognitiveDecision.INSUFFICIENT_INFORMATION
        elif metadata.get("escalate", False) or metadata.get(
            "critical_contradiction", False
        ):
            status = AgentCognitiveStatus.BLOCKED
            decision = AgentCognitiveDecision.ESCALATE
        elif metadata.get("pause", False) or cog_status is CognitiveStatus.PAUSED:
            status = AgentCognitiveStatus.BLOCKED
            decision = AgentCognitiveDecision.PAUSE
        elif metadata.get("complete_without_action", False):
            status = AgentCognitiveStatus.COMPLETED
            decision = AgentCognitiveDecision.COMPLETE_WITHOUT_ACTION
        elif metadata.get("partial", False) or cog_status is CognitiveStatus.REASONING:
            status = AgentCognitiveStatus.PARTIAL
            decision = AgentCognitiveDecision.CONTINUE_REASONING
        else:
            status = AgentCognitiveStatus.COMPLETED
            decision = AgentCognitiveDecision.PLAN

        recommendations = tuple(metadata.get("recommendations", ()))
        hypotheses = tuple(metadata.get("hypotheses", ()))
        inferences = tuple(metadata.get("inferences", ()))
        relevant_facts = tuple(metadata.get("relevant_facts", ()))
        observations = tuple(metadata.get("observations", ()))
        unknowns = tuple(metadata.get("unknowns", ()))
        source_ids = tuple(metadata.get("source_ids", ()))

        return AgentCognitiveResult(
            id=generate_cognitive_result_id(),
            request_id=request.id,
            agent_run_id=request.agent_run_id,
            goal_id=request.goal_id,
            status=status,
            recommended_decision=decision,
            reasoning_result_id=cog_id,
            reasoning_session_id=session_id or request.cognitive_session_id,
            reasoning_trace_id=trace_id,
            relevant_facts=relevant_facts,
            observations=observations,
            inferences=inferences,
            hypotheses=hypotheses,
            contradictions=tuple(contradictions),
            information_gaps=tuple(gaps),
            questions=tuple(questions),
            recommendations=recommendations,
            unknowns=unknowns,
            source_ids=source_ids,
            confidence=cog_confidence,
            blocked=(
                status in (AgentCognitiveStatus.BLOCKED, AgentCognitiveStatus.FAILED)
            ),
            requires_user_input=requires_user_input
            or (decision is AgentCognitiveDecision.ASK_USER),
            requires_resource=requires_resource
            or (decision is AgentCognitiveDecision.LOAD_RESOURCE),
            warnings=tuple(warnings),
            errors=tuple(errors),
            created_at=utc_now(),
            metadata=dict(metadata),
        )

    def analyze(self, request: AgentCognitiveRequest) -> AgentCognitiveResult:
        """Perform end-to-end cognitive analysis for request."""
        ctx = self.build_context(request)

        # Invoke cognitive layer if configured
        if self._cognitive_layer is not None:
            try:
                if hasattr(self._cognitive_layer, "analyze"):
                    cog_res = self._cognitive_layer.analyze(ctx)
                elif hasattr(self._cognitive_layer, "run_cycle"):
                    cog_res = self._cognitive_layer.run_cycle(
                        query=request.knowledge_query
                    )
                elif callable(self._cognitive_layer):
                    cog_res = self._cognitive_layer(ctx)
                else:
                    cog_res = CognitiveResult(
                        objective=request.objective,
                        status=CognitiveStatus.COMPLETED,
                        confidence=Confidence(value=1.0, source="cognitive_adapter"),
                    )
                return self.translate_result(cog_res, request)
            except Exception as exc:
                if isinstance(
                    exc,
                    (
                        InvalidAgentCognitiveContractError,
                        CognitiveSessionNotFoundError,
                        CognitiveSessionMismatchError,
                        CognitiveResourceAccessError,
                    ),
                ):
                    raise
                raise CognitiveAdapterExecutionError(
                    f"Cognitive Layer execution failed: {exc}"
                ) from exc

        # Fallback default deterministic synthesis if no cognitive engine passed
        default_cog_result = CognitiveResult(
            objective=request.objective,
            status=CognitiveStatus.COMPLETED,
            confidence=Confidence(value=1.0, source="default_cognitive_adapter"),
        )
        return self.translate_result(default_cog_result, request)

    def resume(self, request: AgentCognitiveRequest) -> AgentCognitiveResult:
        """Resume a suspended or existing cognitive session."""
        if request.session_mode is not CognitiveSessionMode.RESUME:
            raise InvalidAgentCognitiveContractError(
                "session_mode must be 'resume' to invoke resume()"
            )
        return self.analyze(request)


class AgentCognitiveService:
    """Facade service providing a unified interface for Agent Runtime cognitive operations."""

    def __init__(
        self,
        adapter: CognitiveRuntimeAdapter | None = None,
        cognitive_layer: Any | None = None,
        goal_manager: Any | None = None,
        snapshot_repository: Any | None = None,
        knowledge_store: Any | None = None,
        observation_adapter: ObservationResourceAdapter | None = None,
        profile_resolver: Any | None = None,
        session_service: Any | None = None,
        configuration: AgentCognitiveConfiguration | None = None,
    ) -> None:
        if adapter is not None:
            self._adapter = adapter
        else:
            self._adapter = DefaultCognitiveRuntimeAdapter(
                cognitive_layer=cognitive_layer,
                goal_manager=goal_manager,
                snapshot_repository=snapshot_repository,
                knowledge_store=knowledge_store,
                observation_adapter=observation_adapter,
                profile_resolver=profile_resolver,
                session_service=session_service,
                configuration=configuration,
            )

    def analyze(self, request: AgentCognitiveRequest) -> AgentCognitiveResult:
        """Perform cognitive analysis."""
        return self._adapter.analyze(request)

    def resume(self, request: AgentCognitiveRequest) -> AgentCognitiveResult:
        """Resume a cognitive session."""
        return self._adapter.resume(request)

    def cancel(self, request_id_or_session_id: str) -> bool:
        """Cancel an ongoing or pending cognitive analysis if supported."""
        if hasattr(self._adapter, "cancel"):
            return bool(self._adapter.cancel(request_id_or_session_id))
        return True

    def get_session_reference(
        self, session_id: str
    ) -> AgentCognitiveSessionReference | None:
        """Retrieve reference metadata for a cognitive session."""
        return self._adapter.get_session_reference(session_id)

    def build_context(self, request: AgentCognitiveRequest) -> AgentCognitiveContext:
        """Construct evidence context before reasoning."""
        return self._adapter.build_context(request)

    def translate_result(
        self,
        cognitive_result: CognitiveResult | Any,
        request: AgentCognitiveRequest,
    ) -> AgentCognitiveResult:
        """Translate Cognitive Layer result to AgentCognitiveResult."""
        return self._adapter.translate_result(cognitive_result, request)
