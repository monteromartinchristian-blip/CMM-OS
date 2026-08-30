"""Phase 10.34 — Domain Sessions — Independent Audit V5 regressions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cmm.cognitive.contracts import Confidence
from cmm.cognitive.enums import KnowledgeKind, KnowledgeStatus, TemporalScopeKind
from cmm.cognitive.knowledge import KnowledgeItem, TemporalScope
from cmm.cognitive.store_memory import InMemoryKnowledgeStore
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.knowledge_authority import DefaultDomainKnowledgeAuthority
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.resource_authority import DefaultDomainResourceAuthority
from cmm.domains.resource_contracts import (
    DomainResourceContext,
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)
from cmm.domains.session_contracts import (
    DomainSessionCheckStatus,
    DomainSessionContext,
    DomainSessionResumeRequest,
    DomainSessionResumeStatus,
)
from cmm.domains.session_resumer import DomainSessionResumer
from tests.domains.domain_session_test_support import shared_session_adapter

NOW = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


def _resource_authority(
    resource_id: str,
    *,
    valid_until: datetime,
    historical_allowed: bool,
    last_verified_at: datetime | None = None,
    validity_window_seconds: int | None = None,
) -> DefaultDomainResourceAuthority:
    temporal_scope: dict[str, datetime] = {"valid_until": valid_until}
    if last_verified_at is not None:
        temporal_scope["last_verified_at"] = last_verified_at
    context = DomainResourceContext(
        resource_id=resource_id,
        kind="clinical-record",
        provenance=("native:clinical-system",),
        temporal_scope=temporal_scope,
    )
    definition = DomainResourceDefinition(
        id=f"definition:{resource_id}",
        kind="clinical-record",
        domain_id=DomainId("health"),
        adapter="health.clinical_record",
        temporal_policy=DomainResourceTemporalPolicy(
            validity_window_seconds=validity_window_seconds,
            expiration_required=True,
            historical_allowed=historical_allowed,
        ),
    )
    return DefaultDomainResourceAuthority(
        resources={resource_id: context},
        definitions={resource_id: definition},
    )


def _knowledge_item(
    knowledge_id: str,
    *,
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE,
    temporal_scope: TemporalScope | None = None,
) -> KnowledgeItem:
    kwargs: dict[str, object] = {}
    if status is KnowledgeStatus.INVALIDATED:
        kwargs.update(
            invalidated_at=NOW,
            invalidation_reason="native invalidation",
        )
    elif status is KnowledgeStatus.SUPERSEDED:
        kwargs["superseded_by_id"] = f"{knowledge_id}:revision"
    return KnowledgeItem(
        id=knowledge_id,
        statement=f"Canonical knowledge {knowledge_id}",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(0.95),
        status=status,
        temporal_scope=temporal_scope or TemporalScope(kind=TemporalScopeKind.TIMELESS),
        created_at=NOW,
        updated_at=NOW,
        **kwargs,
    )


def _authority_with_item(item: KnowledgeItem) -> DefaultDomainKnowledgeAuthority:
    store = InMemoryKnowledgeStore()
    store.save_item(item)
    return DefaultDomainKnowledgeAuthority(store=store)


def _registry() -> DomainRegistry:
    definition = DomainDefinition(
        id=DomainId("health"),
        name="health",
        display_name="Health",
        version="1.0.0",
        kind=DomainKind.PERSONAL,
        description="Health domain",
        manifest_id=DomainManifestId(slug="health", version="1.0.0"),
        operations=("op:health:read",),
        permissions=("perm:health:read",),
    )
    registry = DomainRegistry()
    registry.register(definition)
    registry.restore_record(
        DomainRegistryRecord(
            definition=definition,
            status=DomainStatus.ACTIVE,
            registered_at=NOW,
            updated_at=NOW,
        )
    )
    return registry


def _resumer(authority: DefaultDomainKnowledgeAuthority) -> DomainSessionResumer:
    return DomainSessionResumer(
        registry=_registry(),
        permission_evaluator=lambda _actor, permissions: permissions,
        operation_filter=lambda _permissions, operations: operations,
        knowledge_authority=authority,
        shared_session_adapter=shared_session_adapter(),
    )


def test_01_native_resource_historical_allowed_policy_is_preserved() -> None:
    verdict = _resource_authority(
        "res:historical-allowed",
        valid_until=NOW - timedelta(hours=1),
        historical_allowed=True,
    ).resolve_resource_freshness("res:historical-allowed", at=NOW)

    assert verdict.status is DomainSessionCheckStatus.PASS
    assert verdict.is_blocking is False


def test_02_native_resource_historical_disallowed_is_blocked() -> None:
    verdict = _resource_authority(
        "res:historical-blocked",
        valid_until=NOW - timedelta(hours=1),
        historical_allowed=False,
    ).resolve_resource_freshness("res:historical-blocked", at=NOW)

    assert verdict.status is DomainSessionCheckStatus.BLOCKING
    assert verdict.is_blocking is True


def test_03_valid_native_resource_passes() -> None:
    verdict = _resource_authority(
        "res:current",
        valid_until=NOW + timedelta(hours=1),
        historical_allowed=False,
    ).resolve_resource_freshness("res:current", at=NOW)

    assert verdict.status is DomainSessionCheckStatus.PASS
    assert verdict.is_blocking is False


def test_native_resource_stale_window_uses_canonical_drift() -> None:
    verdict = _resource_authority(
        "res:stale-window",
        valid_until=NOW + timedelta(hours=1),
        historical_allowed=False,
        last_verified_at=NOW - timedelta(minutes=5),
        validity_window_seconds=60,
    ).resolve_resource_freshness("res:stale-window", at=NOW)

    assert verdict.status is DomainSessionCheckStatus.DRIFT
    assert verdict.is_blocking is False


def test_04_canonical_knowledge_item_invalidated_is_blocked() -> None:
    item = _knowledge_item("know:invalidated", status=KnowledgeStatus.INVALIDATED)
    verdict = _authority_with_item(item).resolve_knowledge_freshness(item.id, at=NOW)

    assert verdict.status is DomainSessionCheckStatus.BLOCKING
    assert verdict.is_blocking is True
    assert verdict.details["status"] == KnowledgeStatus.INVALIDATED.value


def test_05_canonical_knowledge_item_superseded_is_blocked() -> None:
    item = _knowledge_item("know:superseded", status=KnowledgeStatus.SUPERSEDED)
    verdict = _authority_with_item(item).resolve_knowledge_freshness(item.id, at=NOW)

    assert verdict.status is DomainSessionCheckStatus.BLOCKING
    assert verdict.is_blocking is True
    assert verdict.details["superseded_by_id"] == "know:superseded:revision"


def test_06_canonical_knowledge_item_active_and_temporally_valid_is_current() -> None:
    item = _knowledge_item("know:active")
    verdict = _authority_with_item(item).resolve_knowledge_freshness(item.id, at=NOW)

    assert verdict.status is DomainSessionCheckStatus.PASS
    assert verdict.is_blocking is False


def test_07_canonical_knowledge_item_unverified_is_conservative() -> None:
    item = _knowledge_item("know:unverified", status=KnowledgeStatus.UNVERIFIED)
    verdict = _authority_with_item(item).resolve_knowledge_freshness(item.id, at=NOW)

    assert verdict.status is not DomainSessionCheckStatus.PASS
    assert verdict.is_blocking is True


def test_08_missing_canonical_knowledge_fails_closed() -> None:
    verdict = DefaultDomainKnowledgeAuthority(
        store=InMemoryKnowledgeStore()
    ).resolve_knowledge_freshness("know:missing", at=NOW)

    assert verdict.status is DomainSessionCheckStatus.BLOCKING
    assert verdict.is_blocking is True


def test_native_knowledge_temporal_invalidity_is_conservative() -> None:
    item = _knowledge_item(
        "know:expired",
        temporal_scope=TemporalScope(
            kind=TemporalScopeKind.INTERVAL,
            valid_from=NOW - timedelta(days=2),
            valid_until=NOW - timedelta(days=1),
        ),
    )
    verdict = _authority_with_item(item).resolve_knowledge_freshness(item.id, at=NOW)

    assert verdict.status is not DomainSessionCheckStatus.PASS
    assert verdict.is_blocking is True


def test_unknown_mapping_object_is_not_assumed_current() -> None:
    verdict = DefaultDomainKnowledgeAuthority(
        {"know:unknown": object()}
    ).resolve_knowledge_freshness("know:unknown", at=NOW)

    assert verdict.status is DomainSessionCheckStatus.BLOCKING
    assert verdict.is_blocking is True


def test_09_session_e2e_invalidated_knowledge_cannot_resume() -> None:
    item = _knowledge_item(
        "know:session-invalidated", status=KnowledgeStatus.INVALIDATED
    )
    result = _resumer(_authority_with_item(item)).resume(
        DomainSessionResumeRequest(
            session_id="audit-v5-native-invalidated",
            temporal_reference=NOW,
        ),
        DomainSessionContext(
            session_id="audit-v5-native-invalidated",
            primary_domain="domain:health",
            domain_knowledge_refs={"domain:health": (item.id,)},
            updated_at=NOW,
        ),
    )

    knowledge_check = next(
        check for check in result.checks if check.name == f"knowledge_drift_{item.id}"
    )
    assert knowledge_check.status is DomainSessionCheckStatus.BLOCKING
    assert knowledge_check.blocking is True
    assert result.status is DomainSessionResumeStatus.BLOCKED
    assert result.recorded_resumption is False
