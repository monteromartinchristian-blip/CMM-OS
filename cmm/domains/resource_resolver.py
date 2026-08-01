"""Phase 10.10 – Domain Resource Resolver.

Declarative validation, permission/sensitivity/temporal helpers, and the
deterministic ``DefaultDomainResourceResolver``. No adapter execution, no
registry access, no filesystem, network or persistence.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from cmm.cognitive.enums import SensitivityLevel as Sensitivity
from cmm.domains.enums import (
    DomainResourceDecisionCode,
    DomainResourceResolutionStatus,
    DomainResourceValidationOperator,
    DomainResourceValidationSeverity,
)
from cmm.domains.errors import DomainResourceResolutionError
from cmm.domains.identifiers import DomainId
from cmm.domains.resource_contracts import (
    DomainResourceBinding,
    DomainResourceContext,
    DomainResourceDecision,
    DomainResourceDefinition,
    DomainResourceRejection,
    DomainResourceResolution,
    DomainResourceValidationResult,
)

_SENSITIVITY_RANK: dict[Sensitivity, int] = {
    Sensitivity.PUBLIC: 0,
    Sensitivity.INTERNAL: 1,
    Sensitivity.PERSONAL: 2,
    Sensitivity.SENSITIVE: 3,
    Sensitivity.HIGHLY_SENSITIVE: 4,
    Sensitivity.RESTRICTED: 5,
}

# Sentinel used only when a requested domain has no applicable definition at
# all: DomainResourceRejection.definition_id is required and non-empty, but
# there is no real definition to reference.
_UNRESOLVED_DEFINITION_ID = "<unresolved>"

# Marks a permission entry as a denial of the permission that follows.
_DENY_PREFIX = "deny:"


def _max_sensitivity(*values: Sensitivity) -> Sensitivity:
    return max(values, key=lambda v: _SENSITIVITY_RANK[v])


# ── Task 7/8: Declarative validator ─────────────────────────────────────────

_CONTEXT_DIRECT_FIELDS = frozenset(
    {
        "resource_id",
        "kind",
        "provenance",
        "applicable_domains",
        "sensitivity",
        "permissions",
        "source_type",
        "entity_types",
    }
)


def _normalize_observed(value: Any) -> Any:
    if isinstance(value, Sensitivity):
        return value.value
    if isinstance(value, DomainId):
        return str(value)
    if isinstance(value, tuple):
        return [_normalize_observed(v) for v in value]
    return value


def _lookup_metadata_path(metadata: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    """Resolve a safe dotted path rooted at ``metadata`` (e.g. ``metadata.a.b``).

    Only mapping traversal is allowed: no list indexing, no attribute access,
    no dunder or ``_``-prefixed segments, no empty segments.
    """
    segments = path.split(".")
    if len(segments) < 2 or segments[0] != "metadata":
        return False, None
    for segment in segments:
        if not segment or segment.startswith("_"):
            return False, None
    current: Any = metadata
    for segment in segments[1:]:
        if not isinstance(current, Mapping):
            return False, None
        if segment not in current:
            return False, None
        current = current[segment]
    return True, current


def _lookup_field(context: DomainResourceContext, field_name: str) -> tuple[bool, Any]:
    if field_name in _CONTEXT_DIRECT_FIELDS:
        return True, _normalize_observed(getattr(context, field_name))
    if "." in field_name:
        found, value = _lookup_metadata_path(context.metadata, field_name)
        if not found:
            return False, None
        return True, _normalize_observed(value)
    if field_name in context.metadata:
        return True, _normalize_observed(context.metadata[field_name])
    return False, None


def _evaluate_operator(
    operator: DomainResourceValidationOperator,
    found: bool,
    observed: Any,
    expected: Any,
) -> bool:
    if operator == DomainResourceValidationOperator.EXISTS:
        if not found:
            return False
        if isinstance(observed, (list, str)):
            return len(observed) > 0
        return observed is not None
    if not found:
        return False
    if operator == DomainResourceValidationOperator.EQUALS:
        return observed == expected
    if operator == DomainResourceValidationOperator.NOT_EQUALS:
        return observed != expected
    if operator == DomainResourceValidationOperator.CONTAINS:
        if isinstance(observed, Mapping):
            return expected in observed
        if isinstance(observed, (list, str)):
            return expected in observed
        return False
    if operator == DomainResourceValidationOperator.IN:
        if not isinstance(expected, (list, tuple)):
            return False
        return observed in expected
    if operator == DomainResourceValidationOperator.MINIMUM:
        if not isinstance(observed, (int, float)) or isinstance(observed, bool):
            return False
        return observed >= expected
    if operator == DomainResourceValidationOperator.MAXIMUM:
        if not isinstance(observed, (int, float)) or isinstance(observed, bool):
            return False
        return observed <= expected
    return False


@runtime_checkable
class DomainResourceValidator(Protocol):
    """Protocol for declarative Domain Resource validation."""

    def validate(
        self,
        *,
        context: DomainResourceContext,
        definition: DomainResourceDefinition,
    ) -> tuple[DomainResourceValidationResult, ...]: ...


class DefaultDomainResourceValidator:
    """Evaluates a definition's declarative validation rules against a context."""

    def validate(
        self,
        *,
        context: DomainResourceContext,
        definition: DomainResourceDefinition,
    ) -> tuple[DomainResourceValidationResult, ...]:
        results: list[DomainResourceValidationResult] = []
        for rule in definition.validation_rules:
            found, observed = _lookup_field(context, rule.field)
            passed = _evaluate_operator(rule.operator, found, observed, rule.expected)
            results.append(
                DomainResourceValidationResult(
                    rule_id=rule.id,
                    passed=passed,
                    severity=rule.severity,
                    message=rule.message,
                    field=rule.field,
                    observed=observed if found else None,
                )
            )
        return tuple(results)


# ── Task 8: Permission, sensitivity and temporal helpers ───────────────────


def _split_permissions(permissions: tuple[str, ...]) -> tuple[set[str], set[str]]:
    """Split a permission tuple into (granted, denied) permission names."""
    granted: set[str] = set()
    denied: set[str] = set()
    for permission in permissions:
        if permission.startswith(_DENY_PREFIX):
            denied.add(permission[len(_DENY_PREFIX) :])
        else:
            granted.add(permission)
    return granted, denied


def _compute_effective_permissions(
    resource_permissions: tuple[str, ...],
    definition_permissions: tuple[str, ...],
    request_permissions: tuple[str, ...],
) -> tuple[str, ...]:
    """Intersect granted permissions, then remove any permission denied by
    any of the three sources. A deny removes only the specific permission
    it names; it never blocks the whole binding by itself.
    """
    resource_granted, resource_denied = _split_permissions(resource_permissions)
    definition_granted, definition_denied = _split_permissions(definition_permissions)
    request_granted, request_denied = _split_permissions(request_permissions)

    granted = resource_granted & definition_granted & request_granted
    denied = resource_denied | definition_denied | request_denied
    return tuple(sorted(granted - denied))


def _evaluate_temporal_policy(
    *,
    context: DomainResourceContext,
    definition: DomainResourceDefinition,
    now: datetime,
) -> tuple[bool, str]:
    policy = definition.temporal_policy
    scope = context.temporal_scope

    if policy.effective_date_required and scope.get("valid_from") is None:
        return False, "effective date required but valid_from is missing"

    if policy.expiration_required and scope.get("valid_until") is None:
        return False, "expiration required but valid_until is missing"

    valid_until = scope.get("valid_until")
    if valid_until is not None and valid_until < now and not policy.historical_allowed:
        return False, "historical use of an expired resource is not allowed"

    if policy.validity_window_seconds is not None:
        reference = scope.get("last_verified_at") or scope.get("observed_at")
        if reference is not None:
            age_seconds = (now - reference).total_seconds()
            if age_seconds > policy.validity_window_seconds:
                return False, "resource is stale relative to the validity window"

    return True, ""


def _order_by_source_priority(
    definitions: tuple[DomainResourceDefinition, ...],
) -> tuple[DomainResourceDefinition, ...]:
    return tuple(
        sorted(
            definitions,
            key=lambda d: (-d.source_priority, d.domain_id.slug, d.id),
        )
    )


# ── Task 9: Resolver protocol and default resolver ─────────────────────────


@runtime_checkable
class DomainResourceResolver(Protocol):
    """Protocol for resolving a resource context into domain bindings."""

    def resolve(
        self,
        *,
        context: DomainResourceContext,
        definitions: tuple[DomainResourceDefinition, ...],
        requested_domains: tuple[DomainId, ...],
        request_permissions: tuple[str, ...],
    ) -> DomainResourceResolution: ...


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_id_factory() -> str:
    return str(uuid4())


def _default_trace_id_factory() -> str:
    return str(uuid4())


class DefaultDomainResourceResolver:
    """Deterministic Domain Resource resolver. Receives definitions explicitly."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        trace_id_factory: Callable[[], str] | None = None,
        validator: DomainResourceValidator | None = None,
    ) -> None:
        clock = clock if clock is not None else _default_clock
        id_factory = id_factory if id_factory is not None else _default_id_factory
        trace_id_factory = (
            trace_id_factory
            if trace_id_factory is not None
            else _default_trace_id_factory
        )
        validator = (
            validator if validator is not None else DefaultDomainResourceValidator()
        )

        if not callable(clock):
            raise DomainResourceResolutionError("clock must be callable", field="clock")
        if not callable(id_factory):
            raise DomainResourceResolutionError(
                "id_factory must be callable", field="id_factory"
            )
        if not callable(trace_id_factory):
            raise DomainResourceResolutionError(
                "trace_id_factory must be callable", field="trace_id_factory"
            )
        if not isinstance(validator, DomainResourceValidator):
            raise DomainResourceResolutionError(
                "validator must implement DomainResourceValidator", field="validator"
            )

        self._clock = clock
        self._id_factory = id_factory
        self._trace_id_factory = trace_id_factory
        self._validator = validator

    def _next_now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise DomainResourceResolutionError(
                "clock must return a timezone-aware datetime", field="clock"
            )
        return now

    def _next_trace_id(self) -> str:
        trace_id = self._trace_id_factory()
        if not isinstance(trace_id, str) or not trace_id:
            raise DomainResourceResolutionError(
                "trace_id_factory must return a non-empty str", field="trace_id_factory"
            )
        return trace_id

    def _next_id(self) -> str:
        value = self._id_factory()
        if not isinstance(value, str) or not value:
            raise DomainResourceResolutionError(
                "id_factory must return a non-empty str", field="id_factory"
            )
        return value

    def resolve(
        self,
        *,
        context: DomainResourceContext,
        definitions: tuple[DomainResourceDefinition, ...],
        requested_domains: tuple[DomainId, ...],
        request_permissions: tuple[str, ...],
    ) -> DomainResourceResolution:
        if not isinstance(context, DomainResourceContext):
            raise DomainResourceResolutionError(
                "context must be a DomainResourceContext", field="context"
            )
        if not isinstance(definitions, tuple):
            raise DomainResourceResolutionError(
                "definitions must be a tuple", field="definitions"
            )
        for i, definition in enumerate(definitions):
            if not isinstance(definition, DomainResourceDefinition):
                raise DomainResourceResolutionError(
                    f"definitions[{i}] must be a DomainResourceDefinition",
                    field="definitions",
                )
        if not isinstance(requested_domains, tuple):
            raise DomainResourceResolutionError(
                "requested_domains must be a tuple", field="requested_domains"
            )
        seen_requested_domains: set[DomainId] = set()
        for i, domain in enumerate(requested_domains):
            if not isinstance(domain, DomainId):
                raise DomainResourceResolutionError(
                    f"requested_domains[{i}] must be a DomainId",
                    field="requested_domains",
                )
            if domain in seen_requested_domains:
                raise DomainResourceResolutionError(
                    f"requested_domains contains duplicate domain '{domain.slug}'",
                    field="requested_domains",
                )
            seen_requested_domains.add(domain)
        if not isinstance(request_permissions, tuple):
            raise DomainResourceResolutionError(
                "request_permissions must be a tuple", field="request_permissions"
            )
        seen_request_permissions: set[str] = set()
        for i, permission in enumerate(request_permissions):
            if not isinstance(permission, str) or not permission:
                raise DomainResourceResolutionError(
                    f"request_permissions[{i}] must be a non-empty str",
                    field="request_permissions",
                )
            if permission == _DENY_PREFIX:
                raise DomainResourceResolutionError(
                    f"request_permissions[{i}] must name a permission after 'deny:'",
                    field="request_permissions",
                )
            if permission in seen_request_permissions:
                raise DomainResourceResolutionError(
                    f"request_permissions contains duplicate entry '{permission}'",
                    field="request_permissions",
                )
            seen_request_permissions.add(permission)

        now = self._next_now()
        trace_id = self._next_trace_id()

        requested_order = {
            domain.slug: index for index, domain in enumerate(requested_domains)
        }

        matching_kind = [d for d in definitions if d.kind == context.kind]
        requested_set = set(requested_domains)
        candidates = [d for d in matching_kind if d.domain_id in requested_set]

        if context.applicable_domains:
            hinted = set(context.applicable_domains)
            candidates = [d for d in candidates if d.domain_id in hinted]

        candidates = _order_by_source_priority(tuple(candidates))

        bindings: list[DomainResourceBinding] = []
        rejections: list[DomainResourceRejection] = []
        permission_denials: list[DomainResourceRejection] = []
        validation_issues: list[DomainResourceValidationResult] = []
        decisions: list[DomainResourceDecision] = []

        # Phase 1: evaluate every candidate independently of the others, so
        # the outcome never depends on the input order of ``definitions``.
        accepted: list[
            tuple[
                DomainResourceDefinition,
                tuple[str, ...],
                Sensitivity,
                tuple[DomainResourceValidationResult, ...],
            ]
        ] = []

        for definition in candidates:
            effective_permissions = _compute_effective_permissions(
                context.permissions,
                definition.default_permissions,
                request_permissions,
            )
            if not effective_permissions:
                rejection = DomainResourceRejection(
                    definition_id=definition.id,
                    domain_id=definition.domain_id,
                    code=DomainResourceDecisionCode.PERMISSION_DENIED,
                    reason="effective permissions are empty or explicitly denied",
                    blocking=True,
                )
                permission_denials.append(rejection)
                rejections.append(rejection)
                decisions.append(
                    DomainResourceDecision(
                        code=DomainResourceDecisionCode.PERMISSION_DENIED,
                        resource_id=context.resource_id,
                        reason=rejection.reason,
                        blocking=True,
                        definition_id=definition.id,
                        domain_id=definition.domain_id,
                    )
                )
                continue

            effective_sensitivity = _max_sensitivity(
                context.sensitivity, definition.default_sensitivity
            )
            if (
                _SENSITIVITY_RANK[effective_sensitivity]
                > _SENSITIVITY_RANK[context.sensitivity]
            ):
                decisions.append(
                    DomainResourceDecision(
                        code=DomainResourceDecisionCode.SENSITIVITY_RESTRICTED,
                        resource_id=context.resource_id,
                        reason="definition sensitivity raises the effective "
                        "sensitivity above the context sensitivity",
                        blocking=False,
                        definition_id=definition.id,
                        domain_id=definition.domain_id,
                    )
                )

            temporal_ok, temporal_reason = _evaluate_temporal_policy(
                context=context, definition=definition, now=now
            )
            if not temporal_ok:
                rejection = DomainResourceRejection(
                    definition_id=definition.id,
                    domain_id=definition.domain_id,
                    code=DomainResourceDecisionCode.TEMPORAL_POLICY_FAILED,
                    reason=temporal_reason,
                    blocking=True,
                )
                rejections.append(rejection)
                decisions.append(
                    DomainResourceDecision(
                        code=DomainResourceDecisionCode.TEMPORAL_POLICY_FAILED,
                        resource_id=context.resource_id,
                        reason=temporal_reason,
                        blocking=True,
                        definition_id=definition.id,
                        domain_id=definition.domain_id,
                    )
                )
                continue

            rule_results = self._validator.validate(
                context=context, definition=definition
            )
            blocking_failure = any(
                not r.passed and r.severity == DomainResourceValidationSeverity.BLOCKING
                for r in rule_results
            )
            validation_issues.extend(r for r in rule_results if not r.passed)
            if blocking_failure:
                rejection = DomainResourceRejection(
                    definition_id=definition.id,
                    domain_id=definition.domain_id,
                    code=DomainResourceDecisionCode.VALIDATION_FAILED,
                    reason="a blocking validation rule failed",
                    blocking=True,
                )
                rejections.append(rejection)
                decisions.append(
                    DomainResourceDecision(
                        code=DomainResourceDecisionCode.VALIDATION_FAILED,
                        resource_id=context.resource_id,
                        reason=rejection.reason,
                        blocking=True,
                        definition_id=definition.id,
                        domain_id=definition.domain_id,
                    )
                )
                continue

            accepted.append(
                (definition, effective_permissions, effective_sensitivity, rule_results)
            )

        # Phase 2: resolve cross-domain sharing compatibility using only the
        # set of accepted candidates, independent of their input order.
        domains_with_accepted = {definition.domain_id for definition, *_ in accepted}
        sharing_blocked = len(domains_with_accepted) > 1 and any(
            not definition.shareable for definition, *_ in accepted
        )
        if sharing_blocked:
            priority_domain = min(
                domains_with_accepted, key=lambda d: requested_order[d.slug]
            )
            allowed_domains = {priority_domain}
        else:
            allowed_domains = domains_with_accepted

        final_accepted: list[
            tuple[
                DomainResourceDefinition,
                tuple[str, ...],
                Sensitivity,
                tuple[DomainResourceValidationResult, ...],
            ]
        ] = []
        for entry in accepted:
            definition = entry[0]
            if definition.domain_id in allowed_domains:
                final_accepted.append(entry)
                continue
            rejection = DomainResourceRejection(
                definition_id=definition.id,
                domain_id=definition.domain_id,
                code=DomainResourceDecisionCode.DEFINITION_SKIPPED,
                reason="definition is not shareable across the domains that "
                "qualified for this resource",
                blocking=False,
            )
            rejections.append(rejection)
            decisions.append(
                DomainResourceDecision(
                    code=DomainResourceDecisionCode.DEFINITION_SKIPPED,
                    resource_id=context.resource_id,
                    reason=rejection.reason,
                    blocking=False,
                    definition_id=definition.id,
                    domain_id=definition.domain_id,
                )
            )

        # Phase 3: SOURCE_PRIORITY_APPLIED is recorded only for domains that
        # end up with two or more accepted, allowed bindings.
        final_domain_counts: dict[DomainId, int] = {}
        for definition, *_ in final_accepted:
            final_domain_counts[definition.domain_id] = (
                final_domain_counts.get(definition.domain_id, 0) + 1
            )
        for domain_id, count in final_domain_counts.items():
            if count > 1:
                decisions.append(
                    DomainResourceDecision(
                        code=DomainResourceDecisionCode.SOURCE_PRIORITY_APPLIED,
                        resource_id=context.resource_id,
                        reason="multiple valid definitions compete for this domain; "
                        "ordered by source priority",
                        blocking=False,
                        domain_id=domain_id,
                    )
                )

        # Phase 4: construct bindings for the final accepted candidates.
        selected_domains: set[DomainId] = set()
        for (
            definition,
            effective_permissions,
            effective_sensitivity,
            rule_results,
        ) in final_accepted:
            if context.reliability is None:
                effective_reliability = definition.default_reliability
            else:
                effective_reliability = min(
                    context.reliability, definition.default_reliability
                )

            binding = DomainResourceBinding(
                id=self._next_id(),
                resource_id=context.resource_id,
                definition_id=definition.id,
                domain_id=definition.domain_id,
                adapter=definition.adapter,
                provenance=context.provenance,
                entity_types=definition.entity_types or context.entity_types,
                sensitivity=effective_sensitivity,
                permissions=effective_permissions,
                temporal_scope=context.temporal_scope,
                source_priority=definition.source_priority,
                reliability=effective_reliability,
                validation_results=rule_results,
            )
            bindings.append(binding)
            selected_domains.add(definition.domain_id)
            decisions.append(
                DomainResourceDecision(
                    code=DomainResourceDecisionCode.DEFINITION_SELECTED,
                    resource_id=context.resource_id,
                    reason="definition satisfied permission, sensitivity, temporal "
                    "and validation constraints",
                    blocking=False,
                    definition_id=definition.id,
                    domain_id=definition.domain_id,
                )
            )
            decisions.append(
                DomainResourceDecision(
                    code=DomainResourceDecisionCode.RELIABILITY_APPLIED,
                    resource_id=context.resource_id,
                    reason="effective reliability derived from context and "
                    "definition reliability",
                    blocking=False,
                    definition_id=definition.id,
                    domain_id=definition.domain_id,
                )
            )

        candidate_domains = {d.domain_id for d in candidates}
        unmatched_domains = requested_set - candidate_domains
        for domain_id in unmatched_domains:
            rejection = DomainResourceRejection(
                definition_id=_UNRESOLVED_DEFINITION_ID,
                domain_id=domain_id,
                code=DomainResourceDecisionCode.DOMAIN_NOT_APPLICABLE,
                reason="no applicable definition was found for this domain",
                blocking=False,
            )
            rejections.append(rejection)
            decisions.append(
                DomainResourceDecision(
                    code=DomainResourceDecisionCode.DOMAIN_NOT_APPLICABLE,
                    resource_id=context.resource_id,
                    reason=rejection.reason,
                    blocking=False,
                    domain_id=domain_id,
                )
            )

        shared_domains = tuple(
            sorted(selected_domains, key=lambda d: requested_order[d.slug])
        )
        if len(shared_domains) > 1:
            decisions.append(
                DomainResourceDecision(
                    code=DomainResourceDecisionCode.RESOURCE_SHARED,
                    resource_id=context.resource_id,
                    reason="resource bound across multiple domains without duplication",
                    blocking=False,
                )
            )

        rejections_sorted = tuple(
            sorted(
                rejections,
                key=lambda r: (
                    not r.blocking,
                    r.domain_id.slug,
                    r.definition_id,
                    r.code.value,
                ),
            )
        )
        permission_denials_sorted = tuple(
            sorted(
                permission_denials,
                key=lambda r: (
                    not r.blocking,
                    r.domain_id.slug,
                    r.definition_id,
                    r.code.value,
                ),
            )
        )
        validation_issues_sorted = tuple(
            sorted(
                validation_issues,
                key=lambda v: (
                    v.severity != DomainResourceValidationSeverity.BLOCKING,
                    v.rule_id,
                    v.field,
                ),
            )
        )

        def _decision_domain_order(decision: DomainResourceDecision) -> int:
            if decision.domain_id is None:
                return len(requested_order)
            return requested_order.get(decision.domain_id.slug, len(requested_order))

        decisions_sorted = tuple(
            sorted(
                decisions,
                key=lambda d: (
                    not d.blocking,
                    _decision_domain_order(d),
                    d.definition_id or "",
                    d.code.value,
                ),
            )
        )
        bindings_sorted = tuple(
            sorted(
                bindings,
                key=lambda b: (
                    requested_order[b.domain_id.slug],
                    -b.source_priority,
                    b.definition_id,
                ),
            )
        )

        has_blocking_rejection = any(r.blocking for r in rejections_sorted)
        has_blocking_issue = any(
            v.severity == DomainResourceValidationSeverity.BLOCKING
            for v in validation_issues_sorted
        )

        if has_blocking_rejection or has_blocking_issue:
            status = DomainResourceResolutionStatus.BLOCKED
        elif bindings_sorted and rejections_sorted:
            status = DomainResourceResolutionStatus.PARTIAL
        elif bindings_sorted:
            status = DomainResourceResolutionStatus.RESOLVED
        else:
            status = DomainResourceResolutionStatus.REJECTED

        return DomainResourceResolution(
            id=self._next_id(),
            resource_id=context.resource_id,
            status=status,
            trace_id=trace_id,
            resolved_at=now,
            bindings=bindings_sorted,
            rejections=rejections_sorted,
            permission_denials=permission_denials_sorted,
            validation_issues=validation_issues_sorted,
            shared_domains=shared_domains,
            decisions=decisions_sorted,
        )


__all__ = [
    "DefaultDomainResourceResolver",
    "DefaultDomainResourceValidator",
    "DomainResourceResolver",
    "DomainResourceValidator",
]
