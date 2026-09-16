"""Phase 11.2 — canonical domain routing.

``CanonicalDomainRouter`` is an orchestration **facade** over Domain
Intelligence.  It does not resolve domains: primary and supporting domain
selection stay owned by ``cmm.domains.resolver.DefaultDomainResolver``, and
permission evidence stays owned by the canonical Domain permission layer.  This
module therefore reimplements no scoring weight, no fallback rule, no ambiguity
rule, no permission semantic and no cross-domain authority.

Two canonical sources feed the resolver:

* the canonical ``DomainRegistry`` snapshot supplies the available/active
  domains through ``DomainResolutionContextBuilder``;
* the canonical ``DomainPermissionResolver`` supplies restrictive permission
  evidence for intents that imply an action.

Everything else is request evidence the caller may only *narrow*: explicit
domain references and structured domain signals.  A caller can never widen the
domain set — ``available_domains`` and ``authorized_domains`` are taken from the
canonical registry, never from the request.

Phase 11.2 states installation-level domain availability, not a per-actor
permission grant: every action remains gated by canonical Domain permission
evidence, and the dedicated authorization owner (Phase 11.13) will narrow the
authorized set when it exists.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any, Protocol, runtime_checkable

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_contracts import DomainPermissionRequest
from cmm.domains.resolution_contracts import DomainResolutionSignal
from cmm.domains.resolver_contracts import DomainResolutionResult
from cmm.orchestration.contracts import (
    DomainRouteDecision,
    IntentKind,
    IntentResolution,
    OrchestrationRequest,
    ResolvedContext,
)
from cmm.orchestration.errors import DomainRoutingError

__all__ = [
    "CanonicalDomainRouter",
    "DomainRouter",
]

#: Caller context keys this router consumes.  Domain availability is canonical
#: and cannot be supplied or widened by the caller.
CALLER_EXPLICIT_DOMAINS_KEY = "explicit_domains"
CALLER_DOMAIN_SIGNALS_KEY = "domain_signals"

#: Canonical permission capability that an intent implies.  An intent with no
#: entry performs no action, so no permission evidence is gathered for it.
ACTION_BY_INTENT: dict[IntentKind, PermissionCapability] = {
    IntentKind.COMMAND: PermissionCapability.OPERATION_EXECUTE,
    IntentKind.GOAL: PermissionCapability.GOAL_UPDATE,
    IntentKind.WORKFLOW_REQUEST: PermissionCapability.WORKFLOW_EXECUTE,
    IntentKind.INFORMATION_UPDATE: PermissionCapability.MEMORY_WRITE,
    IntentKind.CONTINUATION: PermissionCapability.WORKFLOW_EXECUTE,
    IntentKind.CONFIGURATION_CHANGE: PermissionCapability.PERMISSION_MODIFY,
}

#: Canonical required identifier per capability, resolved from the structured
#: request input.  When it is absent, no permission evidence is gathered rather
#: than inventing an identifier.
_ACTION_CONTAINER: dict[PermissionCapability, str] = {
    PermissionCapability.OPERATION_EXECUTE: "command",
    PermissionCapability.WORKFLOW_EXECUTE: "workflow_request",
}

#: Within each container mapping, the canonical key that carries the identifier.
_ACTION_CONTAINER_KEY: dict[str, str] = {
    "command": "operation",
    "workflow_request": "workflow_id",
}

#: Fallback request key when the container carries no identifier.
_ACTION_FALLBACK_KEY: dict[PermissionCapability, str] = {
    PermissionCapability.WORKFLOW_EXECUTE: "continuation_id",
}

#: Canonical request field name per capability.
_ACTION_PARAMETER: dict[PermissionCapability, str] = {
    PermissionCapability.OPERATION_EXECUTE: "operation_id",
    PermissionCapability.WORKFLOW_EXECUTE: "workflow_id",
}

#: Deterministic evidence order for the canonical resolution objective.  The
#: first non-empty explicit request field wins.  Every intent that reaches this
#: router carries at least one of these fields, because the deterministic intent
#: resolver only classifies an intent whose structured shape is present.
_OBJECTIVE_INPUT: tuple[tuple[str, str | None], ...] = (
    ("goal", "title"),
    ("question", None),
    ("reflection", None),
    ("command", "operation"),
    ("workflow_request", "workflow_type"),
    ("information_update", "subject_ref"),
    ("configuration_change", "path"),
    ("continuation_id", None),
    ("cancel_target_id", None),
    ("approval_id", None),
)

#: Request input container/key pairs that name canonical operations.
_OPERATION_INPUT: tuple[tuple[str, str], ...] = (("command", "operation"),)


@runtime_checkable
class DomainRouter(Protocol):
    """Orchestration-facing domain routing boundary."""

    def route(
        self,
        request: OrchestrationRequest,
        intent: IntentResolution,
        context: ResolvedContext,
    ) -> DomainRouteDecision: ...


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _nested_text(payload: Mapping[str, object], container: str, key: str) -> str | None:
    nested = payload.get(container)
    if not isinstance(nested, Mapping):
        return None
    return _text(nested.get(key))


def _objective(request: OrchestrationRequest) -> str | None:
    """Return the natural-language objective carried by the request, if any."""

    for container, nested_key in _OBJECTIVE_INPUT:
        if nested_key is None:
            direct = _text(request.input.get(container))
            if direct is not None:
                return direct
        else:
            nested = _nested_text(request.input, container, nested_key)
            if nested is not None:
                return nested
    return None


def _requested_operations(request: OrchestrationRequest) -> tuple[str, ...]:
    """Return the canonical operation references the request names."""

    found: list[str] = []
    for container, key in _OPERATION_INPUT:
        reference = _nested_text(request.input, container, key)
        if reference is not None and reference not in found:
            found.append(reference)
    return tuple(found)


def _domain_references(request: OrchestrationRequest, key: str) -> tuple[DomainId, ...]:
    """Return canonical domain IDs from an allowlisted caller context key."""

    raw = request.context.get(key)
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes | bytearray)) or not isinstance(raw, (list, tuple)):
        raise DomainRoutingError(
            "Caller domain evidence must be a sequence of domain slugs",
            details={"field": key},
        )

    domains: list[DomainId] = []
    for item in raw:
        slug = _text(item)
        if slug is None:
            raise DomainRoutingError(
                "Caller domain evidence must contain non-empty domain slugs",
                details={"field": key},
            )
        domains.append(DomainId(slug=slug))
    return tuple(domains)


def _domain_signals(
    request: OrchestrationRequest,
) -> tuple[DomainResolutionSignal, ...]:
    """Return canonical domain signals from an allowlisted caller context key."""

    raw = request.context.get(CALLER_DOMAIN_SIGNALS_KEY)
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes | bytearray)) or not isinstance(raw, (list, tuple)):
        raise DomainRoutingError(
            "Caller domain signals must be a sequence of structured signals",
            details={"field": CALLER_DOMAIN_SIGNALS_KEY},
        )

    signals: list[DomainResolutionSignal] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise DomainRoutingError(
                "Caller domain signals must be structured mappings",
                details={"field": CALLER_DOMAIN_SIGNALS_KEY},
            )
        value = _text(item.get("value"))
        kind = _text(item.get("kind")) or "intent"
        if value is None:
            raise DomainRoutingError(
                "Caller domain signals require a non-empty value",
                details={"field": CALLER_DOMAIN_SIGNALS_KEY},
            )
        domains = item.get("domains", ())
        if isinstance(domains, (str, bytes | bytearray)) or not isinstance(
            domains, (list, tuple)
        ):
            raise DomainRoutingError(
                "Caller domain signals require a sequence of domain slugs",
                details={"field": CALLER_DOMAIN_SIGNALS_KEY},
            )
        domain_ids: list[DomainId] = []
        for slug in domains:
            normalized = _text(slug)
            if normalized is None:
                raise DomainRoutingError(
                    "Caller domain signal domains must be non-empty slugs",
                    details={"field": CALLER_DOMAIN_SIGNALS_KEY},
                )
            domain_ids.append(DomainId(slug=normalized))
        if not domain_ids:
            raise DomainRoutingError(
                "Caller domain signals require at least one domain",
                details={"field": CALLER_DOMAIN_SIGNALS_KEY},
            )
        confidence = item.get("confidence", 0.5)
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise DomainRoutingError(
                "Caller domain signal confidence must be numeric",
                details={"field": CALLER_DOMAIN_SIGNALS_KEY},
            )
        signals.append(
            DomainResolutionSignal(
                kind=kind,
                source="cmm.orchestration",
                value=value,
                domain_ids=tuple(domain_ids),
                confidence=float(confidence),
                provenance={"source": "cmm.orchestration"},
            )
        )
    return tuple(signals)


class CanonicalDomainRouter:
    """Orchestration facade over canonical Domain Intelligence."""

    def __init__(
        self,
        *,
        resolver: Any,
        registry: Any | None = None,
        context_builder: Any | None = None,
        profile_registry: Any | None = None,
        permission_registry: Any | None = None,
        permission_resolver: Any | None = None,
    ) -> None:
        if resolver is None:
            raise TypeError("resolver must be a canonical Domain resolver")
        if (permission_registry is None) is not (permission_resolver is None):
            raise TypeError(
                "permission_registry and permission_resolver must be provided "
                "together: canonical permission resolution requires at least one "
                "active canonical policy for the participating domains"
            )
        self._resolver = resolver
        self._registry = registry
        self._context_builder = context_builder
        self._profile_registry = profile_registry
        self._permission_registry = permission_registry
        self._permission_resolver = permission_resolver

    # ── Public API ───────────────────────────────────────────────────────────

    def route(
        self,
        request: OrchestrationRequest,
        intent: IntentResolution,
        context: ResolvedContext,
    ) -> DomainRouteDecision:
        """Return the orchestration projection of canonical domain evidence."""

        if not isinstance(request, OrchestrationRequest):
            raise TypeError(
                f"request must be an OrchestrationRequest, got {type(request).__name__}"
            )
        if not isinstance(intent, IntentResolution):
            raise TypeError(
                f"intent must be an IntentResolution, got {type(intent).__name__}"
            )
        if not isinstance(context, ResolvedContext):
            raise TypeError(
                f"context must be a ResolvedContext, got {type(context).__name__}"
            )

        canonical_context = self._build_context(request, intent)
        result = self._resolve(request, canonical_context)
        return self._project(request, intent, result)

    # ── Canonical delegation ─────────────────────────────────────────────────

    def _builder(self) -> Any:
        if self._context_builder is not None:
            return self._context_builder
        from cmm.domains.resolution_builder import DomainResolutionContextBuilder

        return DomainResolutionContextBuilder()

    def _build_context(self, request: OrchestrationRequest, intent: IntentResolution):
        builder = self._builder()
        snapshot = None if self._registry is None else self._registry.snapshot()

        base = builder.build(
            registry_snapshot=snapshot,
            objective=_objective(request),
            session_id=request.session_id,
            explicit_domains=_domain_references(request, CALLER_EXPLICIT_DOMAINS_KEY),
            requested_operations=_requested_operations(request),
            signals=_domain_signals(request),
            intent=intent.intent.value,
            actor=request.user_id,
        )
        # Canonical domain availability and the authorized set both come from
        # the canonical registry; the caller can narrow evidence but never
        # widen the selectable domain set.
        return replace(base, authorized_domains=base.available_domains)

    def _resolve(self, request: OrchestrationRequest, canonical_context: Any):
        try:
            result = self._resolver.resolve(canonical_context)
        except Exception as error:
            raise DomainRoutingError(
                "Canonical domain resolution failed",
                details={"request_id": request.request_id},
            ) from error

        if not isinstance(result, DomainResolutionResult):
            raise DomainRoutingError(
                "Domain resolver returned an unexpected result type",
                details={"request_id": request.request_id},
            )
        if result.status is DomainResolutionStatus.FAILED:
            raise DomainRoutingError(
                "Canonical domain resolution reported failure",
                details={"request_id": request.request_id},
            )
        return result

    def _project(
        self,
        request: OrchestrationRequest,
        intent: IntentResolution,
        result: DomainResolutionResult,
    ) -> DomainRouteDecision:
        needs_clarification = bool(result.requires_clarification) or (
            result.primary_domain is None
            and result.status is not DomainResolutionStatus.BLOCKED
        )

        primary = None
        supporting: tuple[str, ...] = ()
        profile_id = None
        disposition = None
        permission_refs: tuple[str, ...] = ()
        approval_refs: tuple[str, ...] = ()

        if not needs_clarification and result.primary_domain is not None:
            primary = str(result.primary_domain)
            supporting = tuple(str(domain) for domain in result.supporting_domains)
            profile_id = self._profile_reference(result.primary_domain)
            disposition, permission_refs, approval_refs = self._permission_evidence(
                request, intent, result, primary
            )

        return DomainRouteDecision(
            status=result.status.value,
            primary_domain=primary,
            supporting_domains=supporting,
            rejected_domains=tuple(str(domain) for domain in result.rejected_domains),
            ambiguous_domains=tuple(str(domain) for domain in result.ambiguous_domains),
            profile_id=profile_id,
            permission_disposition=disposition,
            permission_refs=permission_refs,
            approval_refs=approval_refs,
            trace_refs=(
                f"domain-resolution:{result.id}",
                f"domain-resolution-context:{result.context_id}",
            ),
            reason_codes=tuple(dict.fromkeys(reason.code for reason in result.reasons)),
            needs_clarification=needs_clarification,
            fallback_used=bool(result.fallback_used),
        )

    # ── Canonical collaborators ──────────────────────────────────────────────

    def _profile_reference(self, primary: DomainId) -> str | None:
        if self._profile_registry is None:
            return None
        profile = self._profile_registry.get_by_domain(primary)
        if profile is None:
            return None
        return profile.id

    def _permission_evidence(
        self,
        request: OrchestrationRequest,
        intent: IntentResolution,
        result: DomainResolutionResult,
        primary: str,
    ) -> tuple[str | None, tuple[str, ...], tuple[str, ...]]:
        """Return canonical permission evidence for an action-implying intent."""

        capability = ACTION_BY_INTENT.get(intent.intent)
        if capability is None or self._permission_resolver is None:
            return None, (), ()
        if primary is None or request.session_id is None:
            return None, (), ()

        identifiers = self._action_identifiers(request, capability)
        if identifiers is None:
            return None, (), ()

        supporting = tuple(str(domain) for domain in result.supporting_domains)
        if not self._has_canonical_policy(primary, supporting):
            # ``DomainPermissionResolver.resolve`` is defined for domains that
            # have at least one active canonical policy.  When the canonical
            # permission layer holds no policy for any participating domain
            # there is no canonical decision to project; absence of evidence is
            # not a deny, and the orchestration policy decides how to treat it.
            return None, (), ()

        domain_id = primary
        try:
            permission_request = DomainPermissionRequest(
                request_id=request.request_id,
                action=capability,
                domain_id=domain_id,
                actor_id=request.user_id,
                session_id=request.session_id,
                **identifiers,
            )
        except Exception as error:
            raise DomainRoutingError(
                "Canonical permission request could not be constructed",
                details={"request_id": request.request_id},
            ) from error

        try:
            resolution = self._permission_resolver.resolve(
                permission_request,
                supporting_domains=supporting,
            )
        except Exception as error:
            raise DomainRoutingError(
                "Canonical permission resolution failed",
                details={"request_id": request.request_id, "domain_id": domain_id},
            ) from error

        effective = resolution.effective_permissions
        permission_refs = tuple(
            f"permission:{evaluation.source_id}"
            for evaluation in effective.layer_evaluations
        )
        approval_refs = tuple(
            requirement.requirement_id
            for requirement in effective.approval_requirements
        )
        return effective.decision.value, permission_refs, approval_refs

    def _has_canonical_policy(self, primary: str, supporting: tuple[str, ...]) -> bool:
        """Return whether any participating domain has an active canonical policy."""

        registry = self._permission_registry
        if registry is None:
            return False
        participating = sorted({primary, *supporting})
        return any(
            registry.active_for_domain(domain_id) is not None
            for domain_id in participating
        )

    @staticmethod
    def _action_identifiers(
        request: OrchestrationRequest,
        capability: PermissionCapability,
    ) -> dict[str, str] | None:
        """Return the canonical identifier a capability requires, if present."""

        container = _ACTION_CONTAINER.get(capability)
        if container is None:
            return {}

        identifier = _nested_text(
            request.input, container, _ACTION_CONTAINER_KEY[container]
        )
        if identifier is None:
            fallback = _ACTION_FALLBACK_KEY.get(capability)
            if fallback is not None:
                identifier = _text(request.input.get(fallback))
        if identifier is None:
            return None

        return {_ACTION_PARAMETER[capability]: identifier}
