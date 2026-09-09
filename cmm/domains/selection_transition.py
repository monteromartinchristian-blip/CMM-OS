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

from cmm.agent_runtime.domain_permission_contracts import PermissionOutcome
from cmm.domains.composer import DomainComposer
from cmm.domains.composition_contracts import (
    DomainComposition,
    EffectiveReasoningProfile,
)
from cmm.domains.enums import (
    DomainCompositionStatus,
    DomainResolutionStatus,
    DomainStatus,
)
from cmm.domains.errors import DomainSelectionTransitionContractError
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_contracts import (
    CrossDomainPermissionDecision,
    CrossDomainPermissionRequest,
)
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionPolicy,
)
from cmm.domains.resolver import DomainResolver
from cmm.domains.resolver_contracts import DomainResolutionResult
from cmm.domains.selection import build_domain_selection_transition
from cmm.domains.selection_contracts import DomainSelectionTransition
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
_REASON_PERMISSION_NON_ALLOW = "domain_selection_transition_permission_non_allow"


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


def _effective_profile_from_composition(
    composition: DomainComposition,
) -> str | None:
    """Derive the session effective profile from the canonical composition.

    Mirrors the canonical session-resumer mapping: the composition carries an
    ``EffectiveReasoningProfile`` object, while the session stores its base
    profile token. A missing composition profile yields ``None`` rather than a
    stale inherited value.
    """
    profile = composition.effective_profile
    if profile is None:
        return None
    if isinstance(profile, str):
        return profile
    if isinstance(profile, EffectiveReasoningProfile):
        return profile.base_profile
    return getattr(profile, "name", str(profile))


def _effective_rule_ids_from_composition(
    composition: DomainComposition,
) -> tuple[str, ...]:
    """Derive session rule refs from the canonical composition rules."""
    return tuple(item.identifier for item in composition.rules)


def _effective_permission_refs_from_composition(
    composition: DomainComposition,
) -> tuple[str, ...]:
    """Derive session permission refs from the canonical permission set."""
    permissions = composition.permissions
    if permissions is None:
        return ()
    return tuple(sorted(set(permissions.granted_permissions)))


def _effective_workflow_refs_from_composition(
    composition: DomainComposition,
) -> tuple[str, ...]:
    """Derive session workflow refs from the canonical composition workflows."""
    return tuple(item.identifier for item in composition.workflows)


def _effective_operation_ids_from_composition(
    composition: DomainComposition,
) -> tuple[str, ...]:
    """Derive session operation ids from the canonical composition operations."""
    return tuple(item.identifier for item in composition.operations)


def _session_matches_pending_delta(
    request: DomainSelectionTransitionRequest,
    session: DomainSessionContext,
    resolution_supporting: tuple[DomainId, ...],
) -> bool:
    """Allow the pre-delta session against a post-delta resolution authority.

    An ADD command is resolved against a rebased authority whose supporting
    set already contains the target, while the durable session still holds
    the pre-delta membership. That exact one-delta difference is the legal
    command shape — not a foreign snapshot — provided identity binding
    (session/composition/last-resolution ids) already passed. Any other
    divergence still fails closed. WITHDRAW always requires exact matching.
    """
    if request.kind is not DomainSelectionTransitionCommandKind.ADD_SUPPORTING:
        return False
    resolution_set = frozenset(str(domain) for domain in resolution_supporting)
    session_set = frozenset(session.supporting_domains)
    target = str(request.target_domain)
    return session_set == (resolution_set - {target})


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
        resolver: DomainResolver,
        composer: DomainComposer,
        domain_registry: DomainRegistry,  # noqa: F821 — canonical owner, injected
        permission_resolver: DomainPermissionResolver,  # noqa: F821 — injected
        session_adapter: SharedSessionDomainAdapter,  # noqa: F821 — injected
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Inject the canonical seams; the coordinator owns none of them.

        Seam authorities are injected, never imported: the quoted annotations
        below name the canonical owner types without importing them.
        """
        self._resolver: DomainResolver = resolver
        self._composer: DomainComposer = composer
        self._domain_registry = domain_registry
        self._permission_resolver = permission_resolver
        self._session_adapter = session_adapter
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def apply(
        self,
        request: DomainSelectionTransitionRequest,
        session: DomainSessionContext,
        resolution: DomainResolutionResult,
        composition: DomainComposition,
        resolution_context: DomainResolutionContext,
    ) -> DomainSelectionTransitionResult:
        """Apply one membership delta or fail closed with a typed result.

        Raises ``DomainSelectionTransitionContractError`` when the request is
        not bound to the same canonical authority chain (session, resolution,
        composition) — nothing is ever persisted in that case.
        """
        self._bind(request, session, resolution, composition, resolution_context)

        precondition = self._check_preconditions(request, session)
        if precondition is not None:
            return precondition

        if request.kind is DomainSelectionTransitionCommandKind.ADD_SUPPORTING:
            blocked = self._check_target_lifecycle(request, resolution_context)
            if blocked is not None:
                return blocked
            permission = self._check_permission(request, session)
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
        resolution: DomainResolutionResult,
        composition: DomainComposition,
        resolution_context: DomainResolutionContext,
    ) -> None:
        """Verify the request binds to one canonical authority chain."""
        if type(request) is not DomainSelectionTransitionRequest:
            raise DomainSelectionTransitionContractError(
                "request must be a canonical DomainSelectionTransitionRequest",
                field="request",
            )
        if type(session) is not DomainSessionContext:
            raise DomainSelectionTransitionContractError(
                "session must be a canonical DomainSessionContext",
                field="session",
            )
        if type(resolution) is not DomainResolutionResult:
            raise DomainSelectionTransitionContractError(
                "resolution must be a canonical DomainResolutionResult",
                field="resolution",
            )
        if type(composition) is not DomainComposition:
            raise DomainSelectionTransitionContractError(
                "composition must be a canonical DomainComposition",
                field="composition",
            )
        if type(resolution_context) is not DomainResolutionContext:
            raise DomainSelectionTransitionContractError(
                "resolution_context must be a canonical DomainResolutionContext",
                field="resolution_context",
            )
        if resolution.status is not DomainResolutionStatus.RESOLVED:
            raise DomainSelectionTransitionContractError(
                "resolution must be RESOLVED for a selection transition",
                field="resolution",
            )
        if composition.status not in (
            DomainCompositionStatus.COMPOSED,
            DomainCompositionStatus.PARTIAL,
        ):
            raise DomainSelectionTransitionContractError(
                "composition status must be COMPOSED or PARTIAL",
                field="composition",
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
        if session.composition_id != composition.id:
            raise DomainSelectionTransitionContractError(
                "session is not bound to the supplied composition authority",
                field="composition_id",
            )
        if resolution.primary_domain is None or session.primary_domain != str(
            resolution.primary_domain
        ):
            raise DomainSelectionTransitionContractError(
                "session primary domain diverges from the resolution authority",
                field="primary_domain",
            )
        if resolution.primary_domain is None or str(composition.primary_domain) != str(
            resolution.primary_domain
        ):
            raise DomainSelectionTransitionContractError(
                "composition primary domain diverges from the resolution authority",
                field="primary_domain",
            )
        if frozenset(session.supporting_domains) != frozenset(
            str(domain) for domain in resolution.supporting_domains
        ) and not _session_matches_pending_delta(
            request, session, resolution.supporting_domains
        ):
            raise DomainSelectionTransitionContractError(
                "session supporting domains diverge from the resolution authority",
                field="supporting_domains",
            )
        if frozenset(str(domain) for domain in composition.supporting_domains) != (
            frozenset(str(domain) for domain in resolution.supporting_domains)
        ):
            raise DomainSelectionTransitionContractError(
                "composition supporting domains diverge from the resolution authority",
                field="supporting_domains",
            )
        if resolution.context_id != resolution_context.id:
            raise DomainSelectionTransitionContractError(
                "resolution is not bound to the supplied resolution context",
                field="resolution_context",
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
        session: DomainSessionContext,
    ) -> DomainSelectionTransitionResult | None:
        """Evaluate the canonical cross-domain permission evidence.

        Only the target-specific canonical ALLOW for this command proceeds;
        DENY blocks, APPROVAL_REQUIRED pends, and any other outcome fails
        closed without persistence.
        """
        evidence = request.permission_request
        if evidence is None:
            raise DomainSelectionTransitionContractError(
                "permission evidence is required for ADD_SUPPORTING",
                field="permission_request",
            )
        if type(evidence) is not CrossDomainPermissionRequest:
            raise DomainSelectionTransitionContractError(
                "permission evidence must be a canonical CrossDomainPermissionRequest",
                field="permission_request",
            )
        if evidence.target_domain != request.target_domain.slug and (
            evidence.target_domain != str(request.target_domain)
        ):
            raise DomainSelectionTransitionContractError(
                "permission evidence does not bind to the transition target",
                field="permission_request",
            )
        if evidence.source_domain != session.primary_domain:
            raise DomainSelectionTransitionContractError(
                "permission evidence does not bind to the session primary domain",
                field="permission_request",
            )
        if evidence.session_id != session.session_id:
            raise DomainSelectionTransitionContractError(
                "permission evidence does not bind to the session authority",
                field="permission_request",
            )
        decision = self._permission_resolver.resolve_cross_domain(evidence)
        if type(decision) is not CrossDomainPermissionDecision:
            raise DomainSelectionTransitionContractError(
                "permission delegation did not return a canonical "
                "CrossDomainPermissionDecision",
                field="permission_request",
            )
        if decision.request_id != evidence.request_id:
            raise DomainSelectionTransitionContractError(
                "permission decision does not bind to the permission evidence",
                field="permission_request",
            )
        if decision.decision is PermissionOutcome.ALLOW:
            return None
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
        return _typed_result(
            request,
            DomainSelectionTransitionStatus.BLOCKED,
            _REASON_PERMISSION_NON_ALLOW,
        )

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
            if request.target_domain.slug in {
                domain.slug for domain in policy.required_domains
            }:
                return resolution_context
            derived_policy = replace(
                policy,
                required_domains=policy.required_domains + (request.target_domain,),
            )
            return replace(
                resolution_context,
                system_policy=derived_policy,
            )
        if request.target_domain.slug in {
            domain.slug for domain in policy.denied_domains
        }:
            return resolution_context
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
        resolution: DomainResolutionResult,
        new_resolution: DomainResolutionResult,
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
        previous_slugs = {domain.slug for domain in resolution.supporting_domains}
        target_slug = request.target_domain.slug
        if request.kind is DomainSelectionTransitionCommandKind.ADD_SUPPORTING:
            delta_applied = supporting_slugs == (previous_slugs | {target_slug})
        else:
            delta_applied = supporting_slugs == (previous_slugs - {target_slug})
        if not delta_applied:
            return _typed_result(
                request,
                DomainSelectionTransitionStatus.BLOCKED,
                _REASON_DELTA_NOT_APPLIED,
            )
        return None

    # ── Canonical recomposition ──────────────────────────────────────────────

    def _compose_members(
        self, new_resolution: DomainResolutionResult
    ) -> DomainComposition:
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
        new_resolution: DomainResolutionResult,
        new_composition: DomainComposition,
        transition: DomainSelectionTransition,
    ) -> DomainSessionContext:
        """Build the single next immutable session revision (revision + 1).

        Membership, version, identity and transition-history fields follow the
        new resolution/composition; composition-derived effective fields are
        rebuilt from the new composition so removed-domain refs cannot survive;
        every unrelated session field is preserved unchanged.
        """
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
            effective_profile=_effective_profile_from_composition(new_composition),
            effective_rule_ids=_effective_rule_ids_from_composition(new_composition),
            effective_permission_refs=_effective_permission_refs_from_composition(
                new_composition
            ),
            active_workflow_refs=_effective_workflow_refs_from_composition(
                new_composition
            ),
            available_operation_ids=_effective_operation_ids_from_composition(
                new_composition
            ),
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
