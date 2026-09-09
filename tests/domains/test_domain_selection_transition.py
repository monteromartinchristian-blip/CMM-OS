from datetime import datetime, timezone

import dataclasses
import json
import typing
from dataclasses import FrozenInstanceError

import pytest

from cmm.domains.errors import (
    DomainSelectionTransitionContractError,
    DomainSelectionTransitionSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_contracts import CrossDomainPermissionRequest
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionSignal,
)
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.selection import build_domain_selection_transition
from cmm.domains.selection_contracts import DomainSelectionTransition
from cmm.domains.selection_transition_contracts import (
    DomainSelectionTransitionCommandKind,
    DomainSelectionTransitionCoordinator,
    DomainSelectionTransitionRequest,
    DomainSelectionTransitionResult,
    DomainSelectionTransitionStatus,
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
            with pytest.raises(
                DomainSelectionTransitionContractError, match=field
            ):
                _transition_request(**{field: "  "})

    def test_request_rejects_foreign_target_domain(self) -> None:
        with pytest.raises(DomainSelectionTransitionContractError):
            _transition_request(target_domain=object())

    def test_request_normalizes_optional_reason(self) -> None:
        assert _transition_request(reason=None).reason is None
        assert _transition_request(reason="with evidence").reason == (
            "with evidence"
        )
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
        assert isinstance(
            self._SpyCoordinator(), DomainSelectionTransitionCoordinator
        )

    def test_protocol_apply_returns_canonical_result(self) -> None:
        hints = typing.get_type_hints(DomainSelectionTransitionCoordinator.apply)
        assert hints["return"] is DomainSelectionTransitionResult
