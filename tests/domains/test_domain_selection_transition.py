import dataclasses
import itertools
import json
import typing
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.domain_permission_contracts import PermissionOutcome
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.enums import (
    DomainCompositionStatus,
    DomainResolutionStatus,
)
from cmm.domains.errors import (
    DomainCompositionContractError,
    DomainSelectionTransitionContractError,
    DomainSelectionTransitionSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_contracts import CrossDomainPermissionRequest
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionKnowledgeItem,
    DomainResolutionPolicy,
    DomainResolutionResource,
    DomainResolutionSignal,
)
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resolver_contracts import DomainScoringPolicy
from cmm.domains.selection import build_domain_selection_transition
from cmm.domains.selection_contracts import DomainSelectionTransition
from cmm.domains.selection_transition import (
    DefaultDomainSelectionTransitionCoordinator,
)
from cmm.domains.selection_transition_contracts import (
    DomainSelectionTransitionCommandKind,
    DomainSelectionTransitionCoordinator,
    DomainSelectionTransitionRequest,
    DomainSelectionTransitionResult,
    DomainSelectionTransitionStatus,
)
from cmm.domains.session_contracts import (
    DomainSessionContext,
    DomainSessionTransition,
)
from cmm.domains.session_persistence import SharedSessionDomainAdapter
from cmm.runtime.sessions import InMemorySessionStore
from tests.domains.test_domain_interface_integration import (
    _make_domain_definition,
    _mark_degraded,
    _register_inbound_policy,
    _register_outbound_policy,
)

GENERAL = DomainId.from_str("domain:general")
PROJECT = DomainId.from_str("domain:project")
HEALTH = DomainId.from_str("domain:health")
REFLECTION = DomainId.from_str("domain:reflection")

NOW = datetime(2026, 8, 27, 18, 0, tzinfo=timezone.utc)


def _resolver(result_id: str) -> DefaultDomainResolver:
    return DefaultDomainResolver(
        fallback_domain=GENERAL,
        id_factory=lambda: result_id,
        clock=lambda: NOW,
    )


def _resolved(
    *,
    result_id: str,
    context_id: str,
    primary: DomainId,
    supporting: DomainId | None = None,
):
    signals = [
        DomainResolutionSignal(
            kind="operation",
            source="test",
            value="primary-evidence",
            domain_ids=(primary,),
            confidence=1.0,
            weight=1.0,
            provenance={"source": "test_fixture"},
        )
    ]

    available = [GENERAL, primary]

    if supporting is not None:
        available.append(supporting)
        signals.append(
            DomainResolutionSignal(
                kind="intent",
                source="test",
                value="supporting-evidence",
                domain_ids=(supporting,),
                confidence=1.0,
                weight=1.0,
                provenance={"source": "test_fixture"},
            )
        )

    context = DomainResolutionContext(
        id=context_id,
        user_input="structured transition fixture",
        available_domains=tuple(available),
        authorized_domains=tuple(available),
        signals=tuple(signals),
        created_at=NOW,
    )

    result = _resolver(result_id).resolve(context)

    assert result.primary_domain == primary

    if supporting is None:
        assert result.supporting_domains == ()
    else:
        assert result.supporting_domains == (supporting,)

    return result


def test_transition_binds_exact_previous_and_new_resolution_ids():
    previous = _resolved(
        result_id="resolution-before",
        context_id="context-before",
        primary=PROJECT,
    )
    current = _resolved(
        result_id="resolution-after",
        context_id="context-after",
        primary=HEALTH,
    )

    transition = build_domain_selection_transition(previous, current)

    assert transition.previous_resolution_id == "resolution-before"
    assert transition.new_resolution_id == "resolution-after"


def test_transition_detects_primary_change():
    previous = _resolved(
        result_id="resolution-before",
        context_id="context-before",
        primary=PROJECT,
    )
    current = _resolved(
        result_id="resolution-after",
        context_id="context-after",
        primary=HEALTH,
    )

    transition = build_domain_selection_transition(previous, current)

    assert transition.previous_primary_domain == PROJECT
    assert transition.new_primary_domain == HEALTH
    assert transition.primary_changed is True
    assert transition.supporting_changed is False
    assert transition.reason_codes == (
        "DOMAIN_SELECTION_REEVALUATED",
        "DOMAIN_SELECTION_PRIMARY_CHANGED",
    )
    assert transition.requires_recomposition is True
    assert transition.requires_session_update is True


def test_transition_detects_supporting_only_change():
    previous = _resolved(
        result_id="resolution-before",
        context_id="context-before",
        primary=PROJECT,
    )
    current = _resolved(
        result_id="resolution-after",
        context_id="context-after",
        primary=PROJECT,
        supporting=REFLECTION,
    )

    transition = build_domain_selection_transition(previous, current)

    assert transition.primary_changed is False
    assert transition.supporting_changed is True
    assert transition.previous_supporting_domains == ()
    assert transition.new_supporting_domains == (REFLECTION,)
    assert transition.reason_codes == (
        "DOMAIN_SELECTION_REEVALUATED",
        "DOMAIN_SELECTION_COMPOSITION_CHANGED",
    )
    assert transition.requires_recomposition is True
    assert transition.requires_session_update is True


def test_transition_detects_primary_and_supporting_change():
    previous = _resolved(
        result_id="resolution-before",
        context_id="context-before",
        primary=PROJECT,
        supporting=REFLECTION,
    )
    current = _resolved(
        result_id="resolution-after",
        context_id="context-after",
        primary=HEALTH,
        supporting=PROJECT,
    )

    transition = build_domain_selection_transition(previous, current)

    assert transition.primary_changed is True
    assert transition.supporting_changed is True
    assert transition.reason_codes == (
        "DOMAIN_SELECTION_REEVALUATED",
        "DOMAIN_SELECTION_PRIMARY_CHANGED",
        "DOMAIN_SELECTION_COMPOSITION_CHANGED",
    )
    assert transition.requires_recomposition is True
    assert transition.requires_session_update is True


def test_unchanged_selection_has_no_transition_effects():
    previous = _resolved(
        result_id="resolution-before",
        context_id="context-before",
        primary=PROJECT,
        supporting=REFLECTION,
    )
    current = _resolved(
        result_id="resolution-after",
        context_id="context-after",
        primary=PROJECT,
        supporting=REFLECTION,
    )

    transition = build_domain_selection_transition(previous, current)

    assert transition.previous_resolution_id == "resolution-before"
    assert transition.new_resolution_id == "resolution-after"
    assert transition.primary_changed is False
    assert transition.supporting_changed is False
    assert transition.reason_codes == ()
    assert transition.requires_recomposition is False
    assert transition.requires_session_update is False


def test_transition_round_trip_preserves_identity_and_change_state():
    previous = _resolved(
        result_id="resolution-before",
        context_id="context-before",
        primary=PROJECT,
    )
    current = _resolved(
        result_id="resolution-after",
        context_id="context-after",
        primary=HEALTH,
    )

    transition = build_domain_selection_transition(previous, current)
    restored = DomainSelectionTransition.from_dict(transition.to_dict())

    assert restored.to_dict() == transition.to_dict()
    assert restored.previous_resolution_id == previous.id
    assert restored.new_resolution_id == current.id


# ─────────────────────────────────────────────────────────────────────────────
# Phase 10.45 MAJOR-03 — canonical selection transition contracts
# ─────────────────────────────────────────────────────────────────────────────


def _permission_evidence(**overrides: object) -> CrossDomainPermissionRequest:
    values: dict[str, object] = {
        "request_id": "permission-request:1",
        "source_domain": str(HEALTH),
        "target_domain": str(GENERAL),
        "reason": "supporting domain application through domain selector",
        "actor_id": "actor-user",
        "session_id": "session-user",
    }
    values.update(overrides)
    return CrossDomainPermissionRequest(**values)


def _transition_request(**overrides: object) -> DomainSelectionTransitionRequest:
    values: dict[str, object] = {
        "request_id": "transition-request:1",
        "kind": DomainSelectionTransitionCommandKind.ADD_SUPPORTING,
        "target_domain": GENERAL,
        "session_reference_id": "session:1",
        "resolution_reference_id": "resolution:1",
        "composition_reference_id": "composition:1",
        "reason": "user asked to add the general domain",
        "permission_request": _permission_evidence(),
    }
    values.update(overrides)
    return DomainSelectionTransitionRequest(**values)


def _canonical_transition() -> DomainSelectionTransition:
    return DomainSelectionTransition(
        previous_resolution_id="resolution:1",
        new_resolution_id="resolution:2",
    )


class TestDomainSelectionTransitionCommandKind:
    def test_command_kind_exposes_only_membership_delta_commands(self) -> None:
        assert [member.value for member in DomainSelectionTransitionCommandKind] == [
            "add_supporting",
            "withdraw_supporting",
        ]

    def test_command_kind_is_a_string_enum(self) -> None:
        assert isinstance(DomainSelectionTransitionCommandKind.ADD_SUPPORTING, str)
        assert (
            DomainSelectionTransitionCommandKind("add_supporting")
            is DomainSelectionTransitionCommandKind.ADD_SUPPORTING
        )


class TestDomainSelectionTransitionRequest:
    def test_request_is_frozen_and_slotted(self) -> None:
        request = _transition_request()
        assert dataclasses.is_dataclass(request)
        with pytest.raises(FrozenInstanceError):
            request.request_id = "other"  # type: ignore[misc]

    def test_request_coerces_kind_and_target_from_canonical_strings(self) -> None:
        request = _transition_request(
            kind="add_supporting",
            target_domain=str(GENERAL),
        )
        assert request.kind is DomainSelectionTransitionCommandKind.ADD_SUPPORTING
        assert request.target_domain == GENERAL

    def test_request_rejects_unknown_kind(self) -> None:
        with pytest.raises(DomainSelectionTransitionContractError):
            _transition_request(kind="explain_selection")

    def test_request_rejects_blank_identity_fields(self) -> None:
        for field in (
            "request_id",
            "session_reference_id",
            "resolution_reference_id",
            "composition_reference_id",
        ):
            with pytest.raises(DomainSelectionTransitionContractError, match=field):
                _transition_request(**{field: "  "})

    def test_request_rejects_foreign_target_domain(self) -> None:
        with pytest.raises(DomainSelectionTransitionContractError):
            _transition_request(target_domain=object())

    def test_request_normalizes_optional_reason(self) -> None:
        assert _transition_request(reason=None).reason is None
        assert _transition_request(reason="with evidence").reason == ("with evidence")
        with pytest.raises(DomainSelectionTransitionContractError):
            _transition_request(reason=" ")

    def test_add_supporting_requires_canonical_permission_evidence(self) -> None:
        with pytest.raises(DomainSelectionTransitionContractError):
            _transition_request(permission_request=None)

    def test_withdraw_supporting_rejects_permission_evidence(self) -> None:
        with pytest.raises(DomainSelectionTransitionContractError):
            _transition_request(
                kind=DomainSelectionTransitionCommandKind.WITHDRAW_SUPPORTING,
                permission_request=_permission_evidence(),
            )

    def test_request_rejects_foreign_permission_payload(self) -> None:
        with pytest.raises(DomainSelectionTransitionContractError):
            _transition_request(permission_request=object())

    def test_request_json_round_trip(self) -> None:
        request = _transition_request()
        payload = json.loads(json.dumps(request.to_dict()))
        restored = DomainSelectionTransitionRequest.from_dict(payload)
        assert restored == request
        assert payload["kind"] == "add_supporting"
        assert payload["target_domain"] == str(GENERAL)
        assert payload["permission_request"]["target_domain"] == str(GENERAL)

    def test_request_from_dict_requires_identity_fields(self) -> None:
        payload = _transition_request().to_dict()
        del payload["composition_reference_id"]
        with pytest.raises(DomainSelectionTransitionSerializationError):
            DomainSelectionTransitionRequest.from_dict(payload)


class TestDomainSelectionTransitionResult:
    def test_result_is_frozen_and_slotted(self) -> None:
        result = DomainSelectionTransitionResult(
            request_id="transition-request:1",
            kind=DomainSelectionTransitionCommandKind.ADD_SUPPORTING,
            status=DomainSelectionTransitionStatus.ACCEPTED,
            reason_code="DOMAIN_SELECTION_COMPOSITION_CHANGED",
            transition=_canonical_transition(),
        )
        assert dataclasses.is_dataclass(result)
        with pytest.raises(FrozenInstanceError):
            result.request_id = "other"  # type: ignore[misc]

    def test_result_requires_transition_when_accepted(self) -> None:
        with pytest.raises(DomainSelectionTransitionContractError):
            DomainSelectionTransitionResult(
                request_id="transition-request:1",
                kind=DomainSelectionTransitionCommandKind.ADD_SUPPORTING,
                status=DomainSelectionTransitionStatus.ACCEPTED,
                transition=None,
            )

    def test_result_forbids_transition_when_blocked_or_pending(self) -> None:
        for status in (
            DomainSelectionTransitionStatus.BLOCKED,
            DomainSelectionTransitionStatus.PENDING,
        ):
            with pytest.raises(DomainSelectionTransitionContractError):
                DomainSelectionTransitionResult(
                    request_id="transition-request:1",
                    kind=DomainSelectionTransitionCommandKind.ADD_SUPPORTING,
                    status=status,
                    reason_code="target_cross_domain_denied",
                    transition=_canonical_transition(),
                )

    def test_result_rejects_foreign_transition_payload(self) -> None:
        with pytest.raises(DomainSelectionTransitionContractError):
            DomainSelectionTransitionResult(
                request_id="transition-request:1",
                kind=DomainSelectionTransitionCommandKind.ADD_SUPPORTING,
                status=DomainSelectionTransitionStatus.ACCEPTED,
                transition=object(),
            )

    def test_result_normalizes_optional_reason_code(self) -> None:
        result = DomainSelectionTransitionResult(
            request_id="transition-request:1",
            kind=DomainSelectionTransitionCommandKind.WITHDRAW_SUPPORTING,
            status=DomainSelectionTransitionStatus.BLOCKED,
            reason_code=None,
        )
        assert result.reason_code is None
        with pytest.raises(DomainSelectionTransitionContractError):
            DomainSelectionTransitionResult(
                request_id="transition-request:1",
                kind=DomainSelectionTransitionCommandKind.WITHDRAW_SUPPORTING,
                status=DomainSelectionTransitionStatus.BLOCKED,
                reason_code=" ",
            )

    def test_result_json_round_trip_with_transition(self) -> None:
        result = DomainSelectionTransitionResult(
            request_id="transition-request:1",
            kind=DomainSelectionTransitionCommandKind.ADD_SUPPORTING,
            status=DomainSelectionTransitionStatus.ACCEPTED,
            reason_code="DOMAIN_SELECTION_COMPOSITION_CHANGED",
            transition=_canonical_transition(),
        )
        payload = json.loads(json.dumps(result.to_dict()))
        restored = DomainSelectionTransitionResult.from_dict(payload)
        assert restored == result
        assert isinstance(restored.transition, DomainSelectionTransition)
        assert restored.transition == _canonical_transition()
        assert payload["status"] == "accepted"

    def test_result_json_round_trip_without_transition(self) -> None:
        result = DomainSelectionTransitionResult(
            request_id="transition-request:1",
            kind=DomainSelectionTransitionCommandKind.ADD_SUPPORTING,
            status=DomainSelectionTransitionStatus.PENDING,
            reason_code="cross_domain_request_pending",
        )
        payload = json.loads(json.dumps(result.to_dict()))
        restored = DomainSelectionTransitionResult.from_dict(payload)
        assert restored == result
        assert restored.transition is None


class TestDomainSelectionTransitionCoordinatorProtocol:
    class _SpyCoordinator:
        def apply(self, **kwargs: object) -> DomainSelectionTransitionResult:
            return DomainSelectionTransitionResult(
                request_id="transition-request:1",
                kind=DomainSelectionTransitionCommandKind.ADD_SUPPORTING,
                status=DomainSelectionTransitionStatus.BLOCKED,
                reason_code="blocked",
            )

    def test_protocol_accepts_conforming_implementations(self) -> None:
        assert isinstance(self._SpyCoordinator(), DomainSelectionTransitionCoordinator)

    def test_protocol_apply_returns_canonical_result(self) -> None:
        hints = typing.get_type_hints(DomainSelectionTransitionCoordinator.apply)
        assert hints["return"] is DomainSelectionTransitionResult


# ─────────────────────────────────────────────────────────────────────────────
# Phase 10.45 MAJOR-03 — canonical selection transition coordinator
#
# Connected coordinator tests: real DomainRegistry + real DefaultDomainResolver
# + real DefaultDomainComposer + real DomainPermissionResolver + real
# SharedSessionDomainAdapter over the shared InMemorySessionStore, mirroring
# test_domain_interface_dp045_acceptance.py.
# ─────────────────────────────────────────────────────────────────────────────

ALPHA = DomainId("alpha")
BETA = DomainId("beta")
GAMMA = DomainId("gamma")
DELTA = DomainId("delta")

_ENV_DEFINITIONS = tuple(
    _make_domain_definition(slug) for slug in ("alpha", "beta", "gamma", "delta")
)


class _CoordinatorEnvironment:
    """Canonical connected environment for coordinator tests.

    The registry holds four enabled definitions (alpha primary, beta/gamma
    supporting, delta addable).  Scoring is calibrated deterministically:

      beta/gamma carry one resource each (resource weight 40); delta carries
      one knowledge item (weight 15) which keeps delta eligible (score floor
      10) while outside the supporting margin (60) from the explicit primary
      alpha (score 100).  Base resolution therefore selects exactly
      (beta, gamma) and a required-delta re-resolution selects
      (delta, beta, gamma).
    """

    def __init__(
        self,
        *,
        session_id: str = "session:coordinator:1",
        authorize_delta: bool = True,
        system_policy: DomainResolutionPolicy | None = None,
        outbound_targets: tuple[str, ...] = (str(DELTA),),
    ) -> None:
        self.session_id = session_id
        resolution_ids = itertools.count(1)
        composition_ids = itertools.count(1)

        self.registry = DomainRegistry()
        for definition in _ENV_DEFINITIONS:
            self.registry.register(definition)
            self.registry.enable(definition.id.slug)
        self.registry_snapshot_before: tuple[tuple[object, ...], ...] = ()

        self.resolver = DefaultDomainResolver(
            fallback_domain=GENERAL,
            scoring_policy=DomainScoringPolicy(
                max_supporting_domains=3, supporting_margin=60.0
            ),
            clock=lambda: NOW,
            id_factory=lambda: f"resolution:coordinator:{next(resolution_ids)}",
        )
        self.composer = DefaultDomainComposer(
            id_factory=lambda: f"composition:coordinator:{next(composition_ids)}",
            clock=lambda: NOW,
        )

        authorized = (ALPHA, BETA, GAMMA)
        if authorize_delta:
            authorized = (ALPHA, BETA, GAMMA, DELTA)
        self.context = DomainResolutionContext(
            id="context:coordinator:1",
            user_input="coordinator connected transition fixture",
            explicit_domains=(ALPHA,),
            available_domains=(ALPHA, BETA, GAMMA, DELTA),
            authorized_domains=authorized,
            resources=(
                DomainResolutionResource(
                    id="resource:beta",
                    resource_type="document",
                    source="user",
                    domain_ids=(BETA,),
                ),
                DomainResolutionResource(
                    id="resource:gamma",
                    resource_type="document",
                    source="user",
                    domain_ids=(GAMMA,),
                ),
            ),
            knowledge_items=(
                DomainResolutionKnowledgeItem(
                    id="knowledge:delta",
                    knowledge_type="document",
                    source="user",
                    domain_ids=(DELTA,),
                    relevance=1.0,
                ),
            ),
            system_policy=system_policy,
            created_at=NOW,
        )

        self.resolution = self.resolver.resolve(self.context)
        assert self.resolution.status is DomainResolutionStatus.RESOLVED
        assert self.resolution.primary_domain == ALPHA
        assert self.resolution.supporting_domains == (BETA, GAMMA)

        definitions_by_slug = {
            definition.id.slug: definition for definition in _ENV_DEFINITIONS
        }
        self.composition = self.composer.compose(
            self.resolution,
            tuple(definitions_by_slug[domain.slug] for domain in (ALPHA, BETA, GAMMA)),
        )
        assert self.composition.status in (
            DomainCompositionStatus.COMPOSED,
            DomainCompositionStatus.PARTIAL,
        )
        assert self.composition.resolution_id == self.resolution.id

        self.session = DomainSessionContext(
            session_id=session_id,
            primary_domain=str(ALPHA),
            supporting_domains=tuple(
                str(d) for d in self.resolution.supporting_domains
            ),
            domain_versions={str(domain): "1.0.0" for domain in (ALPHA, BETA, GAMMA)},
            composition_id=self.composition.id,
            effective_profile="default",
            last_resolution_id=self.resolution.id,
            updated_at=NOW,
        )

        self.store = InMemorySessionStore()
        self.adapter = SharedSessionDomainAdapter(store=self.store)
        self.adapter.save_domain_session(self.session)
        durable = self.adapter.load_domain_session(session_id)
        assert durable is not None
        assert durable.revision == 1

        self.permission_registry = DomainPermissionRegistry()
        _register_outbound_policy(
            self.permission_registry,
            domain_id=str(ALPHA),
            allowed_target_domains=outbound_targets,
        )
        _register_inbound_policy(self.permission_registry, domain_id=str(DELTA))
        self.permission_resolver = DomainPermissionResolver(self.permission_registry)

    def registry_snapshot(self) -> tuple[tuple[object, ...], ...]:
        return tuple(
            (
                record.domain_id,
                record.status.value,
                record.definition.enabled,
                str(record.definition.version),
            )
            for record in self.registry.list_records()
        )


def _coordinator(
    env: _CoordinatorEnvironment,
) -> DefaultDomainSelectionTransitionCoordinator:
    return DefaultDomainSelectionTransitionCoordinator(
        resolver=env.resolver,
        composer=env.composer,
        domain_registry=env.registry,
        permission_resolver=env.permission_resolver,
        session_adapter=env.adapter,
        clock=lambda: NOW,
    )


def _permission_request(
    env: _CoordinatorEnvironment,
    *,
    target_domain: DomainId = DELTA,
    requires_approval: bool = False,
) -> CrossDomainPermissionRequest:
    return CrossDomainPermissionRequest(
        request_id=f"permission:{env.session_id}:{target_domain.slug}",
        source_domain=env.session.primary_domain,
        target_domain=str(target_domain),
        reason="supporting domain application through the canonical coordinator",
        actor_id="actor:coordinator",
        session_id=env.session_id,
        requires_approval=requires_approval,
        sensitivity_level="internal",
    )


def _coordinator_request(
    env: _CoordinatorEnvironment,
    *,
    kind: DomainSelectionTransitionCommandKind = (
        DomainSelectionTransitionCommandKind.ADD_SUPPORTING
    ),
    target_domain: DomainId = DELTA,
    requires_approval: bool = False,
    request_id: str = "transition-request:coordinator:1",
    permission_target_domain: DomainId | None = None,
) -> DomainSelectionTransitionRequest:
    """Build an ADD/WITHDRAW request against the coordinator environment.

    ADD requests always carry canonical cross-domain permission evidence.
    ``permission_target_domain`` overrides the evidence target when it cannot
    equal the request target (canonical cross-domain evidence is never
    self-referential); it only probes precondition ordering, where the
    coordinator must reject the request before any permission evaluation.
    """
    permission_request: CrossDomainPermissionRequest | None = None
    if kind is DomainSelectionTransitionCommandKind.ADD_SUPPORTING:
        evidence_target = (
            target_domain
            if permission_target_domain is None
            else permission_target_domain
        )
        permission_request = _permission_request(
            env,
            target_domain=evidence_target,
            requires_approval=requires_approval,
        )
    return DomainSelectionTransitionRequest(
        request_id=request_id,
        kind=kind,
        target_domain=target_domain,
        session_reference_id=env.session_id,
        resolution_reference_id=env.resolution.id,
        composition_reference_id=env.composition.id,
        reason="user asked through the domain selector",
        permission_request=permission_request,
    )


def _apply(
    env: _CoordinatorEnvironment,
    *,
    kind: DomainSelectionTransitionCommandKind = (
        DomainSelectionTransitionCommandKind.ADD_SUPPORTING
    ),
    target_domain: DomainId = DELTA,
    requires_approval: bool = False,
    request_id: str = "transition-request:coordinator:1",
    session=None,
    resolution=None,
    composition=None,
    permission_target_domain: DomainId | None = None,
) -> DomainSelectionTransitionResult:
    return _coordinator(env).apply(
        request=_coordinator_request(
            env,
            kind=kind,
            target_domain=target_domain,
            requires_approval=requires_approval,
            request_id=request_id,
            permission_target_domain=permission_target_domain,
        ),
        session=env.session if session is None else session,
        resolution=env.resolution if resolution is None else resolution,
        composition=env.composition if composition is None else composition,
        resolution_context=env.context,
    )


class TestDomainSelectionTransitionCoordinatorAccept:
    def test_add_supporting_allow_applies_canonical_transition(self) -> None:
        env = _CoordinatorEnvironment()
        expected = env.permission_resolver.resolve_cross_domain(
            _permission_request(env)
        )
        assert expected.decision is PermissionOutcome.ALLOW
        before_registry = env.registry_snapshot()

        result = _apply(env)

        assert result.request_id == "transition-request:coordinator:1"
        assert result.kind is DomainSelectionTransitionCommandKind.ADD_SUPPORTING
        assert result.status is DomainSelectionTransitionStatus.ACCEPTED
        assert result.reason_code is None
        assert result.transition is not None
        assert result.transition.previous_resolution_id == env.resolution.id
        assert result.transition.new_resolution_id != env.resolution.id
        assert result.transition.previous_primary_domain == ALPHA
        assert result.transition.new_primary_domain == ALPHA
        assert result.transition.primary_changed is False
        assert result.transition.supporting_changed is True
        assert result.transition.previous_supporting_domains == (BETA, GAMMA)
        assert result.transition.new_supporting_domains == (DELTA, BETA, GAMMA)
        assert "DOMAIN_SELECTION_COMPOSITION_CHANGED" in (
            result.transition.reason_codes
        )
        assert result.transition.requires_recomposition is True
        assert env.registry_snapshot() == before_registry

    def test_withdraw_supporting_applies_canonical_transition(self) -> None:
        env = _CoordinatorEnvironment()
        before_registry = env.registry_snapshot()

        result = _apply(
            env,
            kind=DomainSelectionTransitionCommandKind.WITHDRAW_SUPPORTING,
            target_domain=BETA,
        )

        assert result.status is DomainSelectionTransitionStatus.ACCEPTED
        assert result.transition is not None
        assert result.transition.supporting_changed is True
        assert result.transition.previous_supporting_domains == (BETA, GAMMA)
        assert result.transition.new_supporting_domains == (GAMMA,)
        assert env.registry_snapshot() == before_registry

    def test_transition_persists_exactly_one_new_session_revision(self) -> None:
        env = _CoordinatorEnvironment()
        result = _apply(env)

        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == env.session.revision + 1 == 2
        assert durable.session_id == env.session.session_id
        assert durable.primary_domain == str(ALPHA)
        assert durable.supporting_domains == (
            str(DELTA),
            str(BETA),
            str(GAMMA),
        )
        assert durable.composition_id != env.composition.id
        assert durable.last_resolution_id == result.transition.new_resolution_id
        assert durable.domain_versions == {
            str(domain): "1.0.0" for domain in (ALPHA, DELTA, BETA, GAMMA)
        }
        assert len(durable.domain_transitions) == 1
        transition_record = durable.domain_transitions[0]
        assert isinstance(transition_record, DomainSessionTransition)
        assert transition_record.previous_primary_domain == str(ALPHA)
        assert transition_record.new_primary_domain == str(ALPHA)
        assert transition_record.previous_supporting_domains == (
            str(BETA),
            str(GAMMA),
        )
        assert transition_record.new_supporting_domains == (
            str(DELTA),
            str(BETA),
            str(GAMMA),
        )
        assert transition_record.reason_code == "ADD_SUPPORTING"
        assert transition_record.resolution_id == durable.last_resolution_id
        assert transition_record.composition_id == durable.composition_id
        assert transition_record.occurred_at == NOW
        assert durable.effective_profile == env.session.effective_profile
        assert durable.approval_refs == env.session.approval_refs
        assert durable.partial_result_refs == env.session.partial_result_refs
        assert durable.trace_refs == env.session.trace_refs
        assert durable.metadata == env.session.metadata

    def test_transition_does_not_mutate_registry(self) -> None:
        env = _CoordinatorEnvironment()
        before = env.registry_snapshot()
        _apply(env)
        assert env.registry_snapshot() == before
        _apply(
            env,
            kind=DomainSelectionTransitionCommandKind.WITHDRAW_SUPPORTING,
            target_domain=BETA,
        )
        assert env.registry_snapshot() == before
        _apply(env, target_domain=BETA)  # add already-supporting fails closed
        assert env.registry_snapshot() == before

    def test_transition_does_not_mutate_original_policy(self) -> None:
        for policy in (None, DomainResolutionPolicy()):
            env = _CoordinatorEnvironment(system_policy=policy)
            before_policy = env.context.system_policy
            before_context = env.context.to_dict()
            _apply(env)
            assert env.context.system_policy == before_policy
            assert env.context.to_dict() == before_context
            _apply(
                env,
                kind=DomainSelectionTransitionCommandKind.WITHDRAW_SUPPORTING,
                target_domain=BETA,
            )
            assert env.context.system_policy == before_policy
            assert env.context.to_dict() == before_context


class TestDomainSelectionTransitionCoordinatorPermission:
    def test_add_supporting_permission_deny_blocks(self) -> None:
        env = _CoordinatorEnvironment(outbound_targets=())
        request = _permission_request(env)
        expected = env.permission_resolver.resolve_cross_domain(request)
        assert expected.decision is PermissionOutcome.DENY
        assert expected.reasons
        before_registry = env.registry_snapshot()

        result = _apply(env)

        assert result.status is DomainSelectionTransitionStatus.BLOCKED
        assert result.transition is None
        assert result.reason_code == expected.reasons[0]
        assert env.registry_snapshot() == before_registry
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1
        assert durable.supporting_domains == (str(BETA), str(GAMMA))

    def test_add_supporting_approval_required_stays_pending(self) -> None:
        env = _CoordinatorEnvironment()
        request = _permission_request(env, requires_approval=True)
        expected = env.permission_resolver.resolve_cross_domain(request)
        assert expected.decision is PermissionOutcome.APPROVAL_REQUIRED
        assert expected.reasons
        before_registry = env.registry_snapshot()

        result = _apply(env, requires_approval=True)

        assert result.status is DomainSelectionTransitionStatus.PENDING
        assert result.transition is None
        assert result.reason_code == expected.reasons[0]
        assert env.registry_snapshot() == before_registry
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1


class TestDomainSelectionTransitionCoordinatorPreconditions:
    def test_add_supporting_target_already_supporting_blocks(self) -> None:
        env = _CoordinatorEnvironment()
        result = _apply(env, target_domain=BETA)
        assert result.status is DomainSelectionTransitionStatus.BLOCKED
        assert (
            result.reason_code
            == "domain_selection_transition_target_already_supporting"
        )
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1

    def test_add_supporting_target_is_primary_blocks(self) -> None:
        env = _CoordinatorEnvironment()
        result = _apply(
            env,
            target_domain=ALPHA,
            permission_target_domain=DELTA,
        )
        assert result.status is DomainSelectionTransitionStatus.BLOCKED
        assert result.reason_code == "domain_selection_transition_target_is_primary"
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1

    def test_add_supporting_target_disabled_blocks(self) -> None:
        env = _CoordinatorEnvironment()
        env.registry.disable("delta")
        after_disable = env.registry_snapshot()
        result = _apply(env)
        assert result.status is DomainSelectionTransitionStatus.BLOCKED
        assert result.reason_code == "domain_selection_transition_target_disabled"
        assert env.registry_snapshot() == after_disable
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1

    def test_add_supporting_target_degraded_when_policy_forbids_blocks(
        self,
    ) -> None:
        env = _CoordinatorEnvironment(
            system_policy=DomainResolutionPolicy(allow_degraded=False)
        )
        _mark_degraded(env.registry, "delta")
        after_degrade = env.registry_snapshot()
        result = _apply(env)
        assert result.status is DomainSelectionTransitionStatus.BLOCKED
        assert result.reason_code == "domain_selection_transition_target_degraded"
        assert env.registry_snapshot() == after_degrade
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1

    def test_withdraw_supporting_target_not_supporting_blocks(self) -> None:
        env = _CoordinatorEnvironment()
        result = _apply(
            env,
            kind=DomainSelectionTransitionCommandKind.WITHDRAW_SUPPORTING,
            target_domain=DELTA,
        )
        assert result.status is DomainSelectionTransitionStatus.BLOCKED
        assert result.reason_code == "domain_selection_transition_target_not_supporting"
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1

    def test_withdraw_supporting_target_is_primary_blocks(self) -> None:
        env = _CoordinatorEnvironment()
        result = _apply(
            env,
            kind=DomainSelectionTransitionCommandKind.WITHDRAW_SUPPORTING,
            target_domain=ALPHA,
        )
        assert result.status is DomainSelectionTransitionStatus.BLOCKED
        assert result.reason_code == "domain_selection_transition_target_is_primary"
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1


class TestDomainSelectionTransitionCoordinatorFailClosed:
    def test_transition_does_not_persist_on_resolution_failure(self) -> None:
        env = _CoordinatorEnvironment(authorize_delta=False)
        expected = env.permission_resolver.resolve_cross_domain(
            _permission_request(env)
        )
        assert expected.decision is PermissionOutcome.ALLOW
        before_registry = env.registry_snapshot()

        result = _apply(env)

        assert result.status is DomainSelectionTransitionStatus.BLOCKED
        assert result.transition is None
        assert result.reason_code == "DOMAIN_UNAUTHORIZED_REJECTED"
        assert env.registry_snapshot() == before_registry
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1
        assert durable.supporting_domains == (str(BETA), str(GAMMA))

    def test_transition_does_not_persist_on_composition_failure(self) -> None:
        env = _CoordinatorEnvironment()
        env.registry.disable("beta")
        after_disable = env.registry_snapshot()

        with pytest.raises(DomainCompositionContractError):
            _apply(env)

        assert env.registry_snapshot() == after_disable
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1

    def test_transition_reports_optimistic_session_revision_conflict(
        self,
    ) -> None:
        env = _CoordinatorEnvironment()
        advanced = dataclasses.replace(env.session, revision=2)
        env.adapter.save_domain_session(
            advanced, expected_previous_revision=env.session.revision
        )
        durable_before = env.adapter.load_domain_session(env.session_id)
        assert durable_before is not None
        assert durable_before.revision == 2

        result = _apply(env)

        assert result.status is DomainSelectionTransitionStatus.BLOCKED
        assert result.transition is None
        assert result.reason_code == "domain_selection_transition_session_conflict"
        durable_after = env.adapter.load_domain_session(env.session_id)
        assert durable_after is not None
        assert durable_after.revision == 2
        assert durable_after.to_dict() == durable_before.to_dict()


class _DropDeltaResolver:
    """Real-resolver delegate producing RESOLVED results without the delta."""

    def __init__(self, delegate: DefaultDomainResolver) -> None:
        self._delegate = delegate

    def resolve(self, context: DomainResolutionContext) -> object:
        result = self._delegate.resolve(context)
        if result.status is not DomainResolutionStatus.RESOLVED:
            return result
        return dataclasses.replace(
            result,
            supporting_domains=tuple(
                domain for domain in result.supporting_domains if domain != DELTA
            ),
        )


class _ShiftPrimaryResolver:
    """Real-resolver delegate fabricating a primary change on re-resolution."""

    def __init__(self, delegate: DefaultDomainResolver) -> None:
        self._delegate = delegate

    def resolve(self, context: DomainResolutionContext) -> object:
        result = self._delegate.resolve(context)
        if result.status is not DomainResolutionStatus.RESOLVED:
            return result
        return dataclasses.replace(result, primary_domain=DELTA)


class TestDomainSelectionTransitionCoordinatorVerifyGuards:
    def test_transition_blocks_when_membership_delta_not_applied(self) -> None:
        env = _CoordinatorEnvironment()
        coordinator = DefaultDomainSelectionTransitionCoordinator(
            resolver=_DropDeltaResolver(env.resolver),
            composer=env.composer,
            domain_registry=env.registry,
            permission_resolver=env.permission_resolver,
            session_adapter=env.adapter,
            clock=lambda: NOW,
        )

        result = coordinator.apply(
            request=_coordinator_request(env),
            session=env.session,
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=env.context,
        )

        assert result.status is DomainSelectionTransitionStatus.BLOCKED
        assert result.transition is None
        assert result.reason_code == "domain_selection_transition_delta_not_applied"
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1

    def test_transition_blocks_when_primary_would_change(self) -> None:
        env = _CoordinatorEnvironment()
        coordinator = DefaultDomainSelectionTransitionCoordinator(
            resolver=_ShiftPrimaryResolver(env.resolver),
            composer=env.composer,
            domain_registry=env.registry,
            permission_resolver=env.permission_resolver,
            session_adapter=env.adapter,
            clock=lambda: NOW,
        )

        result = coordinator.apply(
            request=_coordinator_request(env),
            session=env.session,
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=env.context,
        )

        assert result.status is DomainSelectionTransitionStatus.BLOCKED
        assert result.transition is None
        assert result.reason_code == "domain_selection_transition_primary_changed"
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1


class TestDomainSelectionTransitionCoordinatorAuthorityBinding:
    def test_request_reference_mismatch_raises_and_persists_nothing(
        self,
    ) -> None:
        env = _CoordinatorEnvironment()
        request = _coordinator_request(env)
        mismatched = dataclasses.replace(
            request, resolution_reference_id="resolution:coordinator:other"
        )
        with pytest.raises(DomainSelectionTransitionContractError):
            _coordinator(env).apply(
                request=mismatched,
                session=env.session,
                resolution=env.resolution,
                composition=env.composition,
                resolution_context=env.context,
            )
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1

    def test_session_resolution_mismatch_raises_and_persists_nothing(
        self,
    ) -> None:
        env = _CoordinatorEnvironment()
        mismatched_session = dataclasses.replace(
            env.session, last_resolution_id="resolution:coordinator:other"
        )
        with pytest.raises(DomainSelectionTransitionContractError):
            _coordinator(env).apply(
                request=_coordinator_request(env),
                session=mismatched_session,
                resolution=env.resolution,
                composition=env.composition,
                resolution_context=env.context,
            )
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1

    def test_composition_resolution_mismatch_raises_and_persists_nothing(
        self,
    ) -> None:
        env = _CoordinatorEnvironment()
        mismatched_composition = dataclasses.replace(
            env.composition, resolution_id="resolution:coordinator:other"
        )
        with pytest.raises(DomainSelectionTransitionContractError):
            _coordinator(env).apply(
                request=_coordinator_request(env),
                session=env.session,
                resolution=env.resolution,
                composition=mismatched_composition,
                resolution_context=env.context,
            )
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1
