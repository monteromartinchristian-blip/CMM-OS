"""Phase 10.45 MAJOR-03 — Canonical Domain Selection Transition Coordinator.

Translates a permission-validated membership-delta intent (``ADD_SUPPORTING``
or ``WITHDRAW_SUPPORTING``) into exactly one canonical ``DomainSessionContext``
revision through the canonical resolution, composition, transition and session
persistence chain — or fails closed leaving every canonical object and store
untouched.

Dependency direction (mandatory, never reversed):

    interface_integration → selection_transition (this coordinator)
            ↓  dependency-injected canonical seams
    resolver / composer / domain_registry / permission_resolver / shared
    session adapter over the store owned by ``cmm.runtime.sessions``

No parallel store, registry, resolver, composer, permission engine or session
authority is created in this module, and no Phase 10.45 interface integration
module is imported here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.domain_permission_contracts import PermissionOutcome
from cmm.domains.enums import (
    DomainCompositionStatus,
    DomainResolutionStatus,
    DomainStatus,
)
from cmm.domains.errors import DomainSelectionTransitionContractError
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionPolicy,
)
from cmm.domains.selection import build_domain_selection_transition
from cmm.domains.selection_transition_contracts import (
    DomainSelectionTransitionCommandKind,
    DomainSelectionTransitionRequest,
    DomainSelectionTransitionResult,
    DomainSelectionTransitionStatus,
)
from cmm.domains.session_contracts import (
    DomainSessionContext,
    DomainSessionTransition,
)
from cmm.runtime.sessions import SessionPersistenceError

_REASON_TARGET_IS_PRIMARY = "domain_selection_transition_target_is_primary"
_REASON_TARGET_ALREADY_SUPPORTING = (
    "domain_selection_transition_target_already_supporting"
)
_REASON_TARGET_NOT_SUPPORTING = "domain_selection_transition_target_not_supporting"
_REASON_TARGET_DISABLED = "domain_selection_transition_target_disabled"
_REASON_TARGET_DEGRADED = "domain_selection_transition_target_degraded"
_REASON_DELTA_NOT_APPLIED = "domain_selection_transition_delta_not_applied"
_REASON_PRIMARY_CHANGED = "domain_selection_transition_primary_changed"
_REASON_RECOMPOSITION_BLOCKED = "domain_selection_transition_recomposition_blocked"
_REASON_SESSION_CONFLICT = "domain_selection_transition_session_conflict"
_REASON_RESOLUTION_BLOCKED = "domain_selection_transition_resolution_blocked"
_REASON_PERMISSION_DENIED = "domain_selection_transition_permission_denied"
_REASON_PERMISSION_APPROVAL_REQUIRED = "domain_selection_transition_approval_required"


def _canonical_slug(reference: DomainId | str) -> str:
    """Return the canonical slug of a domain reference."""
    return DomainId.from_str(reference).slug


def _typed_result(
    request: DomainSelectionTransitionRequest,
    status: DomainSelectionTransitionStatus,
    reason_code: str | None = None,
) -> DomainSelectionTransitionResult:
    """Build a typed non-ACCEPTED (or transitional) result for a request."""
    return DomainSelectionTransitionResult(
        request_id=request.request_id,
        kind=request.kind,
        status=status,
        reason_code=reason_code,
    )


class DefaultDomainSelectionTransitionCoordinator:
    """Canonical coordinator translating membership deltas into revisions.

    The coordinator performs no resolution, composition, permission or
    persistence algorithm itself: it composes the canonical seams (resolver,
    composer, registry, permission resolver, session adapter) with a
    request-scoped derived policy so exactly one new immutable session
    revision captures the membership delta — or nothing persists at all.
    """

    def __init__(
        self,
        *,
        resolver: Any,
        composer: Any,
        domain_registry: Any,
        permission_resolver: Any,
        session_adapter: Any,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Inject the canonical seams; the coordinator owns none of them."""
        self._resolver = resolver
        self._composer = composer
        self._domain_registry = domain_registry
        self._permission_resolver = permission_resolver
        self._session_adapter = session_adapter
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def apply(
        self,
        request: DomainSelectionTransitionRequest,
        session: DomainSessionContext,
        resolution: Any,
        composition: Any,
        resolution_context: DomainResolutionContext,
    ) -> DomainSelectionTransitionResult:
        """Apply one membership delta or fail closed with a typed result.

        Raises ``DomainSelectionTransitionContractError`` when the request is
        not bound to the same canonical authority chain (session, resolution,
        composition) — nothing is ever persisted in that case.
        """
        self._bind(request, session, resolution, composition)

        precondition = self._check_preconditions(request, session)
        if precondition is not None:
            return precondition

        if request.kind is DomainSelectionTransitionCommandKind.ADD_SUPPORTING:
            blocked = self._check_target_lifecycle(request, resolution_context)
            if blocked is not None:
                return blocked
            permission = self._check_permission(request)
            if permission is not None:
                return permission

        derived_context = self._derive_context(request, resolution_context)
        new_resolution = self._resolver.resolve(derived_context)

        blocked = self._verify_resolution(request, resolution, new_resolution)
        if blocked is not None:
            return blocked

        new_composition = self._compose_members(new_resolution)
        if new_composition.status not in (
            DomainCompositionStatus.COMPOSED,
            DomainCompositionStatus.PARTIAL,
        ):
            return _typed_result(
                request,
                DomainSelectionTransitionStatus.BLOCKED,
                _REASON_RECOMPOSITION_BLOCKED,
            )

        transition = build_domain_selection_transition(resolution, new_resolution)
        new_session = self._build_new_session(
            request, session, new_resolution, new_composition, transition
        )

        try:
            self._session_adapter.save_domain_session(
                new_session, expected_previous_revision=session.revision
            )
        except SessionPersistenceError:
            # Optimistic revision conflict: another authority already advanced
            # the session. Never retry and never overwrite the durable state.
            return _typed_result(
                request,
                DomainSelectionTransitionStatus.BLOCKED,
                _REASON_SESSION_CONFLICT,
            )

        return DomainSelectionTransitionResult(
            request_id=request.request_id,
            kind=request.kind,
            status=DomainSelectionTransitionStatus.ACCEPTED,
            transition=transition,
        )

    # ── Authority binding ─────────────────────────────────────────────────────

    def _bind(
        self,
        request: DomainSelectionTransitionRequest,
        session: DomainSessionContext,
        resolution: Any,
        composition: Any,
    ) -> None:
        """Verify the request binds to one canonical authority chain."""
        if not isinstance(request, DomainSelectionTransitionRequest):
            raise DomainSelectionTransitionContractError(
                "request must be a canonical DomainSelectionTransitionRequest",
                field="request",
            )
        if not isinstance(session, DomainSessionContext):
            raise DomainSelectionTransitionContractError(
                "session must be a canonical DomainSessionContext",
                field="session",
            )
        if resolution is None or composition is None:
            raise DomainSelectionTransitionContractError(
                "resolution and composition are required for a transition",
                field="resolution",
            )
        if request.session_reference_id != session.session_id:
            raise DomainSelectionTransitionContractError(
                "request session reference does not match the session authority",
                field="session_reference_id",
            )
        if request.resolution_reference_id != resolution.id:
            raise DomainSelectionTransitionContractError(
                "request resolution reference does not match the resolution authority",
                field="resolution_reference_id",
            )
        if session.last_resolution_id != resolution.id:
            raise DomainSelectionTransitionContractError(
                "session is not bound to the supplied resolution authority",
                field="last_resolution_id",
            )
        if request.composition_reference_id != composition.id:
            raise DomainSelectionTransitionContractError(
                "request composition reference does not match the composition authority",
                field="composition_reference_id",
            )
        if composition.resolution_id != resolution.id:
            raise DomainSelectionTransitionContractError(
                "composition is not bound to the supplied resolution authority",
                field="resolution_id",
            )

    # ── Preconditions ─────────────────────────────────────────────────────────

    def _check_preconditions(
        self,
        request: DomainSelectionTransitionRequest,
        session: DomainSessionContext,
    ) -> DomainSelectionTransitionResult | None:
        """Validate target membership preconditions against the session."""
        target_slug = request.target_domain.slug
        primary_slug = _canonical_slug(session.primary_domain)
        supporting_slugs = {
            _canonical_slug(entry) for entry in session.supporting_domains
        }

        if target_slug == primary_slug:
            return _typed_result(
                request,
                DomainSelectionTransitionStatus.BLOCKED,
                _REASON_TARGET_IS_PRIMARY,
            )

        if request.kind is DomainSelectionTransitionCommandKind.ADD_SUPPORTING:
            if target_slug in supporting_slugs:
                return _typed_result(
                    request,
                    DomainSelectionTransitionStatus.BLOCKED,
                    _REASON_TARGET_ALREADY_SUPPORTING,
                )
        elif target_slug not in supporting_slugs:
            return _typed_result(
                request,
                DomainSelectionTransitionStatus.BLOCKED,
                _REASON_TARGET_NOT_SUPPORTING,
            )
        return None

    def _check_target_lifecycle(
        self,
        request: DomainSelectionTransitionRequest,
        resolution_context: DomainResolutionContext,
    ) -> DomainSelectionTransitionResult | None:
        """Validate the target registry lifecycle for an ADD command."""
        record = self._domain_registry.get_record(request.target_domain.slug)
        if record is None:
            raise DomainSelectionTransitionContractError(
                "target domain is not registered in the canonical domain registry",
                field="target_domain",
            )
        if not record.definition.enabled:
            return _typed_result(
                request,
                DomainSelectionTransitionStatus.BLOCKED,
                _REASON_TARGET_DISABLED,
            )
        if record.status is DomainStatus.DEGRADED:
            policy = resolution_context.system_policy or DomainResolutionPolicy()
            if not policy.allow_degraded:
                return _typed_result(
                    request,
                    DomainSelectionTransitionStatus.BLOCKED,
                    _REASON_TARGET_DEGRADED,
                )
        return None

    def _check_permission(
        self,
        request: DomainSelectionTransitionRequest,
    ) -> DomainSelectionTransitionResult | None:
        """Evaluate the canonical cross-domain permission evidence."""
        if request.permission_request is None:
            raise DomainSelectionTransitionContractError(
                "permission evidence is required for ADD_SUPPORTING",
                field="permission_request",
            )
        decision = self._permission_resolver.resolve_cross_domain(
            request.permission_request
        )
        if decision.decision is PermissionOutcome.DENY:
            return _typed_result(
                request,
                DomainSelectionTransitionStatus.BLOCKED,
                decision.reasons[0] if decision.reasons else _REASON_PERMISSION_DENIED,
            )
        if decision.decision is PermissionOutcome.APPROVAL_REQUIRED:
            return _typed_result(
                request,
                DomainSelectionTransitionStatus.PENDING,
                decision.reasons[0]
                if decision.reasons
                else _REASON_PERMISSION_APPROVAL_REQUIRED,
            )
        return None

    # ── Derived policy + canonical re-resolution ─────────────────────────────

    def _derive_context(
        self,
        request: DomainSelectionTransitionRequest,
        resolution_context: DomainResolutionContext,
    ) -> DomainResolutionContext:
        """Clone the policy with the request-scoped membership delta.

        The original policy and context are never mutated; the derived context
        is a throwaway authority for the re-resolution only.
        """
        policy = resolution_context.system_policy or DomainResolutionPolicy()
        if request.kind is DomainSelectionTransitionCommandKind.ADD_SUPPORTING:
            derived_policy = replace(
                policy,
                required_domains=policy.required_domains + (request.target_domain,),
            )
            return replace(
                resolution_context,
                system_policy=derived_policy,
            )
        derived_policy = replace(
            policy,
            denied_domains=policy.denied_domains + (request.target_domain,),
        )
        # Context invariant: denied_domains and authorized_domains are disjoint.
        stripped_authorized = tuple(
            domain
            for domain in resolution_context.authorized_domains
            if domain != request.target_domain
        )
        return replace(
            resolution_context,
            system_policy=derived_policy,
            authorized_domains=stripped_authorized,
        )

    def _verify_resolution(
        self,
        request: DomainSelectionTransitionRequest,
        resolution: Any,
        new_resolution: Any,
    ) -> DomainSelectionTransitionResult | None:
        """Fail closed unless the delta was applied and the primary preserved."""
        if new_resolution.status is not DomainResolutionStatus.RESOLVED:
            reason_code = _REASON_RESOLUTION_BLOCKED
            if new_resolution.reasons:
                reason_code = new_resolution.reasons[0].code
            return _typed_result(
                request,
                DomainSelectionTransitionStatus.BLOCKED,
                reason_code,
            )

        if new_resolution.primary_domain != resolution.primary_domain:
            return _typed_result(
                request,
                DomainSelectionTransitionStatus.BLOCKED,
                _REASON_PRIMARY_CHANGED,
            )

        supporting_slugs = {domain.slug for domain in new_resolution.supporting_domains}
        target_slug = request.target_domain.slug
        if request.kind is DomainSelectionTransitionCommandKind.ADD_SUPPORTING:
            delta_applied = target_slug in supporting_slugs
        else:
            delta_applied = target_slug not in supporting_slugs
        if not delta_applied:
            return _typed_result(
                request,
                DomainSelectionTransitionStatus.BLOCKED,
                _REASON_DELTA_NOT_APPLIED,
            )
        return None

    # ── Canonical recomposition ──────────────────────────────────────────────

    def _compose_members(self, new_resolution: Any) -> Any:
        """Recompose from the canonical definitions of the resulting members.

        ``DomainCompositionContractError`` raised by the canonical composer
        propagates: it represents an unresolvable membership state, and nothing
        was persisted before this point.
        """
        members = (new_resolution.primary_domain, *new_resolution.supporting_domains)
        definitions = []
        for domain in members:
            record = self._domain_registry.get_record(domain.slug)
            if record is None:
                raise DomainSelectionTransitionContractError(
                    "resolved member is not registered in the canonical domain "
                    "registry",
                    field="target_domain",
                )
            definitions.append(record.definition)
        return self._composer.compose(new_resolution, definitions)

    # ── New session revision ──────────────────────────────────────────────────

    def _build_new_session(
        self,
        request: DomainSelectionTransitionRequest,
        session: DomainSessionContext,
        new_resolution: Any,
        new_composition: Any,
        transition: Any,
    ) -> DomainSessionContext:
        """Build the single next immutable session revision (revision + 1)."""
        now = self._clock()
        members = (new_resolution.primary_domain, *new_resolution.supporting_domains)
        domain_versions = {}
        for domain in members:
            record = self._domain_registry.get_record(domain.slug)
            if record is not None:
                domain_versions[str(domain)] = str(record.definition.version)

        return replace(
            session,
            revision=session.revision + 1,
            updated_at=now,
            primary_domain=str(new_resolution.primary_domain),
            supporting_domains=tuple(
                str(domain) for domain in new_resolution.supporting_domains
            ),
            domain_versions=domain_versions,
            composition_id=new_composition.id,
            last_resolution_id=new_resolution.id,
            domain_transitions=session.domain_transitions
            + (
                DomainSessionTransition(
                    previous_primary_domain=session.primary_domain,
                    new_primary_domain=str(new_resolution.primary_domain),
                    previous_supporting_domains=session.supporting_domains,
                    new_supporting_domains=tuple(
                        str(domain) for domain in new_resolution.supporting_domains
                    ),
                    reason_code=request.kind.value.upper(),
                    resolution_id=new_resolution.id,
                    composition_id=new_composition.id,
                    occurred_at=now,
                ),
            ),
        )


__all__ = ["DefaultDomainSelectionTransitionCoordinator"]
