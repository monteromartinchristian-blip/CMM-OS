"""Phase 10.11 – Domain Profile Resolver.

Orchestrates request validation, overlay relevance checking, and pure
composer invocation to produce an auditable ``DomainProfileResolution``.
The resolver performs no registry access and executes no rules.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable
from uuid import uuid4

from cmm.domains.enums import DomainProfileResolutionStatus, DomainProfileSource
from cmm.domains.errors import DomainProfileResolutionError
from cmm.domains.profile_composition import (
    DefaultDomainProfileComposer,
    DomainProfileComposer,
)
from cmm.domains.profile_contracts import (
    DomainProfileConflict,
    DomainProfileConflictSeverity,
    DomainProfileDefinition,
    DomainProfileOverlay,
    DomainProfileRejection,
    DomainProfileResolution,
    DomainProfileResolutionRequest,
    ResolvedDomainProfile,
)


@runtime_checkable
class DomainProfileResolver(Protocol):
    """Protocol for resolving a Domain Profile from explicit inputs."""

    def resolve(
        self,
        *,
        request: DomainProfileResolutionRequest,
        global_profile: DomainProfileDefinition,
        primary_profile: DomainProfileDefinition,
        supporting_profiles: tuple[DomainProfileDefinition, ...],
        overlays: tuple[DomainProfileOverlay, ...],
    ) -> DomainProfileResolution: ...


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_id_factory() -> str:
    return str(uuid4())


def _default_profile_id_factory() -> str:
    return str(uuid4())


def _default_trace_id_factory() -> str:
    return str(uuid4())


def _is_overlay_relevant(
    overlay: DomainProfileOverlay, request: DomainProfileResolutionRequest
) -> bool:
    """Deterministic overlay relevance check with no runtime identity lookup."""
    if overlay.source == DomainProfileSource.GLOBAL_POLICY:
        return True
    if overlay.source == DomainProfileSource.PRIMARY_DOMAIN:
        return overlay.source_id == request.primary_domain.slug
    if overlay.source == DomainProfileSource.SUPPORTING_DOMAIN:
        supporting_slugs = {d.slug for d in request.supporting_domains}
        return overlay.source_id in supporting_slugs
    if overlay.source == DomainProfileSource.WORKFLOW:
        return overlay.source_id in request.workflow_ids
    if overlay.source == DomainProfileSource.OPERATION:
        return overlay.source_id in request.operation_ids
    if overlay.source == DomainProfileSource.RISK:
        return overlay.source_id == request.risk_level
    if overlay.source == DomainProfileSource.AUTONOMY:
        return overlay.source_id == request.autonomy_level
    if overlay.source == DomainProfileSource.EXPLICIT_REQUEST:
        return overlay.source_id == request.id
    if overlay.source == DomainProfileSource.ACTOR:
        actor_id = request.actor_context.get("actor_id")
        if isinstance(actor_id, str) and overlay.source_id == actor_id:
            return True
        actor_ids = request.actor_context.get("actor_ids")
        return isinstance(actor_ids, (tuple, list)) and overlay.source_id in actor_ids
    return False


def _is_overlay_mandatory(overlay: DomainProfileOverlay) -> bool:
    return overlay.source in {
        DomainProfileSource.GLOBAL_POLICY,
        DomainProfileSource.PRIMARY_DOMAIN,
    }


class DefaultDomainProfileResolver:
    """Deterministic Domain Profile resolver. Receives all inputs explicitly."""

    def __init__(
        self,
        *,
        composer: DomainProfileComposer | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        profile_id_factory: Callable[[], str] | None = None,
        trace_id_factory: Callable[[], str] | None = None,
    ) -> None:
        composer = composer if composer is not None else DefaultDomainProfileComposer()
        clock = clock if clock is not None else _default_clock
        id_factory = id_factory if id_factory is not None else _default_id_factory
        profile_id_factory = (
            profile_id_factory
            if profile_id_factory is not None
            else _default_profile_id_factory
        )
        trace_id_factory = (
            trace_id_factory
            if trace_id_factory is not None
            else _default_trace_id_factory
        )

        if not isinstance(composer, DomainProfileComposer):
            raise DomainProfileResolutionError(
                "composer must implement DomainProfileComposer", field="composer"
            )
        if not callable(clock):
            raise DomainProfileResolutionError("clock must be callable", field="clock")
        if not callable(id_factory):
            raise DomainProfileResolutionError(
                "id_factory must be callable", field="id_factory"
            )
        if not callable(profile_id_factory):
            raise DomainProfileResolutionError(
                "profile_id_factory must be callable", field="profile_id_factory"
            )
        if not callable(trace_id_factory):
            raise DomainProfileResolutionError(
                "trace_id_factory must be callable", field="trace_id_factory"
            )

        self._composer = composer
        self._clock = clock
        self._id_factory = id_factory
        self._profile_id_factory = profile_id_factory
        self._trace_id_factory = trace_id_factory

    def _next_now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise DomainProfileResolutionError(
                "clock must return a timezone-aware datetime", field="clock"
            )
        return now

    def _next_id(self) -> str:
        value = self._id_factory()
        if not isinstance(value, str) or not value:
            raise DomainProfileResolutionError(
                "id_factory must return a non-empty str", field="id_factory"
            )
        return value

    def _next_profile_id(self) -> str:
        value = self._profile_id_factory()
        if not isinstance(value, str) or not value:
            raise DomainProfileResolutionError(
                "profile_id_factory must return a non-empty str",
                field="profile_id_factory",
            )
        return value

    def _next_trace_id(self) -> str:
        value = self._trace_id_factory()
        if not isinstance(value, str) or not value:
            raise DomainProfileResolutionError(
                "trace_id_factory must return a non-empty str",
                field="trace_id_factory",
            )
        return value

    def resolve(
        self,
        *,
        request: DomainProfileResolutionRequest,
        global_profile: DomainProfileDefinition,
        primary_profile: DomainProfileDefinition,
        supporting_profiles: tuple[DomainProfileDefinition, ...] = (),
        overlays: tuple[DomainProfileOverlay, ...] = (),
    ) -> DomainProfileResolution:
        if not isinstance(request, DomainProfileResolutionRequest):
            raise DomainProfileResolutionError(
                "request must be a DomainProfileResolutionRequest", field="request"
            )
        if not isinstance(global_profile, DomainProfileDefinition):
            raise DomainProfileResolutionError(
                "global_profile must be a DomainProfileDefinition",
                field="global_profile",
            )
        if (
            global_profile.domain_id.slug != "general"
            or global_profile.profile_name != "GeneralProfile"
        ):
            raise DomainProfileResolutionError(
                "global_profile must use domain:general and GeneralProfile",
                field="global_profile",
            )
        if not isinstance(primary_profile, DomainProfileDefinition):
            raise DomainProfileResolutionError(
                "primary_profile must be a DomainProfileDefinition",
                field="primary_profile",
            )
        if primary_profile.domain_id.slug != request.primary_domain.slug:
            raise DomainProfileResolutionError(
                "primary_profile.domain_id must match request.primary_domain",
                field="primary_profile",
            )
        if not isinstance(supporting_profiles, tuple):
            raise DomainProfileResolutionError(
                "supporting_profiles must be a tuple", field="supporting_profiles"
            )
        expected_supporting_slugs = tuple(d.slug for d in request.supporting_domains)
        actual_supporting_slugs = tuple(p.domain_id.slug for p in supporting_profiles)
        for i, profile in enumerate(supporting_profiles):
            if not isinstance(profile, DomainProfileDefinition):
                raise DomainProfileResolutionError(
                    f"supporting_profiles[{i}] must be a DomainProfileDefinition",
                    field="supporting_profiles",
                )
        if actual_supporting_slugs != expected_supporting_slugs:
            raise DomainProfileResolutionError(
                "supporting_profiles must align in order with request.supporting_domains",
                field="supporting_profiles",
            )
        if not isinstance(overlays, tuple):
            raise DomainProfileResolutionError(
                "overlays must be a tuple", field="overlays"
            )
        for i, overlay in enumerate(overlays):
            if not isinstance(overlay, DomainProfileOverlay):
                raise DomainProfileResolutionError(
                    f"overlays[{i}] must be a DomainProfileOverlay", field="overlays"
                )

        relevant_overlays: list[DomainProfileOverlay] = []
        extra_conflicts: list[DomainProfileConflict] = []
        extra_rejections: list[DomainProfileRejection] = []

        for overlay in overlays:
            if _is_overlay_relevant(overlay, request):
                relevant_overlays.append(overlay)
                continue
            if _is_overlay_mandatory(overlay):
                extra_conflicts.append(
                    DomainProfileConflict(
                        code="IRRELEVANT_MANDATORY_OVERLAY",
                        field="overlays",
                        severity=DomainProfileConflictSeverity.BLOCKING,
                        sources=(overlay.source,),
                        description=(
                            f"mandatory overlay {overlay.id!r} from source "
                            f"{overlay.source.value!r} is not relevant to the request"
                        ),
                        blocking=True,
                    )
                )
            else:
                extra_rejections.append(
                    DomainProfileRejection(
                        source=overlay.source,
                        source_id=overlay.source_id or overlay.id,
                        field="overlays",
                        reason="overlay is not relevant to the request context",
                        blocking=False,
                    )
                )

        composition_result = self._composer.compose(
            global_profile=global_profile,
            primary_profile=primary_profile,
            supporting_profiles=supporting_profiles,
            overlays=tuple(relevant_overlays),
            request_permissions=request.permissions,
        )

        conflicts = tuple(composition_result.conflicts) + tuple(extra_conflicts)
        rejections = tuple(composition_result.rejections) + tuple(extra_rejections)
        decisions = composition_result.decisions

        has_blocking_conflict = any(c.blocking for c in conflicts)
        trace_id = self._next_trace_id()
        resolved_at = self._next_now()

        if has_blocking_conflict or composition_result.profile is None:
            return DomainProfileResolution(
                id=self._next_id(),
                status=DomainProfileResolutionStatus.BLOCKED,
                profile=None,
                conflicts=conflicts,
                rejections=rejections,
                decisions=decisions,
                trace_id=trace_id,
                resolved_at=resolved_at,
            )

        draft = composition_result.profile
        resolved_profile = ResolvedDomainProfile(
            id=self._next_profile_id(),
            primary_domain=draft.primary_domain,
            supporting_domains=draft.supporting_domains,
            profile_names=draft.profile_names,
            required_rules=draft.required_rules,
            optional_rules=draft.optional_rules,
            prohibited_rules=draft.prohibited_rules,
            allowed_resource_kinds=draft.allowed_resource_kinds,
            priority_resource_kinds=draft.priority_resource_kinds,
            prohibited_resource_kinds=draft.prohibited_resource_kinds,
            minimum_confidence=draft.minimum_confidence,
            reasoning_depth=draft.reasoning_depth,
            allowed_inferences=draft.allowed_inferences,
            prohibited_inferences=draft.prohibited_inferences,
            maximum_questions=draft.maximum_questions,
            escalation_rules=draft.escalation_rules,
            prohibited_actions=draft.prohibited_actions,
            question_policy=draft.question_policy,
            presentation_policy=draft.presentation_policy,
            memory_policy=draft.memory_policy,
            temporal_policy=draft.temporal_policy,
            production_policy=draft.production_policy,
            permissions=draft.permissions,
            modifications=draft.modifications,
            trace_id=trace_id,
            resolved_at=resolved_at,
        )

        status = (
            DomainProfileResolutionStatus.PARTIAL
            if rejections
            else DomainProfileResolutionStatus.RESOLVED
        )

        return DomainProfileResolution(
            id=self._next_id(),
            status=status,
            profile=resolved_profile,
            conflicts=conflicts,
            rejections=rejections,
            decisions=decisions,
            trace_id=trace_id,
            resolved_at=resolved_at,
        )


__all__ = [
    "DefaultDomainProfileResolver",
    "DomainProfileResolver",
]
