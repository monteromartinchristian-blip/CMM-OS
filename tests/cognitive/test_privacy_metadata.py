"""Phase 8.25 – Privacy and Sensitivity Metadata tests."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from inspect import getsourcefile
from pathlib import Path

import pytest

from cmm.cognitive import (
    CognitiveCache,
    CognitiveCacheContext,
    Confidence,
    InMemoryCognitiveCacheStore,
    InvalidCognitiveCacheEntryError,
    InvalidPrivacyMetadataError,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgePackage,
    PrivacyDecisionStatus,
    PrivacyMetadata,
    PrivacyOperation,
    PrivacyOperationContext,
    PrivacyPolicy,
    PrivacyResolution,
    PrivacyResolutionError,
    ProcessingLocation,
    Resource,
    ResourceKind,
    ResourcePermission,
    ResourcePermissionOperation,
    ResourceProvenance,
    ResourceSourceKind,
    ResourceTemporalScope,
    SensitivityLevel,
    evaluate_privacy_operation,
    resolve_effective_privacy_metadata,
)
from cmm.cognitive.cognitive_cache import (
    cache_entry_from_knowledge_package,
    privacy_from_cache_entry,
)
from cmm.cognitive.privacy import (
    privacy_from_knowledge_item,
    privacy_from_knowledge_package,
    privacy_from_resource,
)

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)


def make_resource(
    resource_id: str = "resource:health",
    *,
    sensitivity: SensitivityLevel = SensitivityLevel.PERSONAL,
    permissions: tuple[ResourcePermission, ...] = (),
) -> Resource:
    return Resource(
        id=resource_id,
        domain="health",
        kind=ResourceKind.NOTE,
        source=ResourceSourceKind.USER_INPUT,
        content="patient notes",
        provenance=ResourceProvenance(
            source_type=ResourceSourceKind.USER_INPUT,
            source_id="user:1",
            retrieved_at=NOW,
        ),
        reliability=Confidence(value=0.9),
        temporal_scope=ResourceTemporalScope(ingested_at=NOW),
        sensitivity=sensitivity,
        permissions=permissions,
        created_at=NOW,
        updated_at=NOW,
    )


def make_item(item_id: str = "item:1", resource_id: str | None = None) -> KnowledgeItem:
    return KnowledgeItem(
        id=item_id,
        statement="the patient reported mild pain",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(value=0.8),
        created_at=NOW,
        updated_at=NOW,
        resource_id=resource_id,
        sensitivity=SensitivityLevel.PERSONAL,
    )


def make_package(**overrides) -> KnowledgePackage:
    defaults = {"id": "pkg:1", "objective": "summarize", "created_at": NOW}
    defaults.update(overrides)
    return KnowledgePackage(**defaults)


# ── 1-15: contract ────────────────────────────────────────────────────────


def test_minimal_valid_metadata() -> None:
    metadata = PrivacyMetadata()
    assert metadata.policy is PrivacyPolicy.LOCAL_ONLY
    assert metadata.sensitivity is SensitivityLevel.RESTRICTED
    assert metadata.allow_cache is True
    assert metadata.allow_remote is False
    assert metadata.allow_export is False
    assert metadata.allow_premium is False


def test_metadata_is_immutable() -> None:
    metadata = PrivacyMetadata()
    with pytest.raises(AttributeError):
        metadata.allow_cache = True  # type: ignore[misc]


def test_serialize_is_json_safe() -> None:
    metadata = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        sensitivity=SensitivityLevel.INTERNAL,
        allowed_processing_locations=(ProcessingLocation.LOCAL, ProcessingLocation.REMOTE),
        allow_remote=True,
    )
    payload = metadata.serialize()
    assert payload["policy"] == "remote_allowed"
    assert payload["allowed_processing_locations"] == ["local", "remote"]
    assert metadata.to_dict() == payload


def test_round_trip() -> None:
    metadata = PrivacyMetadata(
        policy=PrivacyPolicy.LOCAL_PREFERRED,
        sensitivity=SensitivityLevel.SENSITIVE,
        allowed_providers=("provider-a",),
        inherited_from=("resource:1",),
    )
    restored = PrivacyMetadata.from_mapping(metadata.serialize())
    assert restored == metadata
    assert PrivacyMetadata.from_dict(metadata.to_dict()) == metadata


def test_serialization_is_deterministic() -> None:
    metadata = PrivacyMetadata(allowed_providers=("a", "b"))
    assert metadata.serialize() == metadata.serialize()


def test_rejects_unsupported_schema_version() -> None:
    with pytest.raises(InvalidPrivacyMetadataError):
        PrivacyMetadata(schema_version=99)


def test_rejects_invalid_policy() -> None:
    with pytest.raises(InvalidPrivacyMetadataError):
        PrivacyMetadata(policy="not-a-policy")


def test_rejects_invalid_sensitivity() -> None:
    with pytest.raises(InvalidPrivacyMetadataError):
        PrivacyMetadata(sensitivity="not-a-sensitivity")


def test_rejects_invalid_processing_location() -> None:
    with pytest.raises(InvalidPrivacyMetadataError):
        PrivacyMetadata(
            policy=PrivacyPolicy.REMOTE_ALLOWED,
            allowed_processing_locations=("outer-space",),
        )


def test_rejects_duplicate_providers() -> None:
    with pytest.raises(InvalidPrivacyMetadataError):
        PrivacyMetadata(
            policy=PrivacyPolicy.REMOTE_ALLOWED,
            allowed_providers=("provider-a", "provider-a"),
        )


def test_rejects_provider_both_allowed_and_prohibited() -> None:
    with pytest.raises(InvalidPrivacyMetadataError):
        PrivacyMetadata(
            policy=PrivacyPolicy.REMOTE_ALLOWED,
            allowed_providers=("provider-a",),
            prohibited_providers=("provider-a",),
        )


def test_local_only_incoherent_with_remote() -> None:
    with pytest.raises(InvalidPrivacyMetadataError):
        PrivacyMetadata(policy=PrivacyPolicy.LOCAL_ONLY, allow_remote=True)
    with pytest.raises(InvalidPrivacyMetadataError):
        PrivacyMetadata(
            policy=PrivacyPolicy.LOCAL_ONLY,
            allowed_processing_locations=(ProcessingLocation.LOCAL, ProcessingLocation.REMOTE),
        )


def test_premium_incoherent_with_policy() -> None:
    with pytest.raises(InvalidPrivacyMetadataError):
        PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allow_remote=True, allow_premium=True)


def test_rejects_invalid_permissions() -> None:
    with pytest.raises(InvalidPrivacyMetadataError):
        PrivacyMetadata(permissions=("not-a-permission",))


def test_rejects_duplicate_inherited_from() -> None:
    with pytest.raises(InvalidPrivacyMetadataError):
        PrivacyMetadata(inherited_from=("resource:1", "resource:1"))


# ── 16-29: effective resolution ─────────────────────────────────────────────


def test_resolution_uses_most_restrictive_policy() -> None:
    permissive = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allow_remote=True)
    strict = PrivacyMetadata(policy=PrivacyPolicy.LOCAL_ONLY)
    resolution = resolve_effective_privacy_metadata(permissive, strict)
    assert resolution.effective.policy is PrivacyPolicy.LOCAL_ONLY


def test_resolution_uses_highest_sensitivity() -> None:
    low = PrivacyMetadata(sensitivity=SensitivityLevel.PUBLIC)
    high = PrivacyMetadata(sensitivity=SensitivityLevel.HIGHLY_SENSITIVE)
    resolution = resolve_effective_privacy_metadata(low, high)
    assert resolution.effective.sensitivity is SensitivityLevel.HIGHLY_SENSITIVE


def test_resolution_intersects_processing_locations() -> None:
    a = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allow_remote=True,
        allowed_processing_locations=(ProcessingLocation.LOCAL, ProcessingLocation.REMOTE),
    )
    b = PrivacyMetadata(policy=PrivacyPolicy.LOCAL_PREFERRED, allowed_processing_locations=(ProcessingLocation.LOCAL,))
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.allowed_processing_locations == (ProcessingLocation.LOCAL,)


def test_resolution_unions_prohibited_providers() -> None:
    a = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, prohibited_providers=("bad-a",))
    b = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, prohibited_providers=("bad-b",))
    resolution = resolve_effective_privacy_metadata(a, b)
    assert set(resolution.effective.prohibited_providers) == {"bad-a", "bad-b"}


def test_resolution_intersects_allowlists() -> None:
    a = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allowed_providers=("p1", "p2"))
    b = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allowed_providers=("p2", "p3"))
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.allowed_providers == ("p2",)


def test_resolution_ands_allow_remote() -> None:
    a = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allow_remote=True)
    b = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allow_remote=False)
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.allow_remote is False


def test_resolution_ands_allow_cache() -> None:
    a = PrivacyMetadata(allow_cache=True)
    b = PrivacyMetadata(allow_cache=False)
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.allow_cache is False


def test_resolution_ands_allow_export() -> None:
    a = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allow_export=True)
    b = PrivacyMetadata(allow_export=False)
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.allow_export is False


def test_resolution_ands_allow_premium() -> None:
    a = PrivacyMetadata(policy=PrivacyPolicy.PREMIUM_ALLOWED, allow_remote=True, allow_premium=True)
    b = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allow_remote=True, allow_premium=False)
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.allow_premium is False


def test_resolution_ors_requires_redaction() -> None:
    a = PrivacyMetadata(requires_redaction=False)
    b = PrivacyMetadata(requires_redaction=True)
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.requires_redaction is True


def test_resolution_ors_requires_approval() -> None:
    a = PrivacyMetadata(requires_approval=False)
    b = PrivacyMetadata(requires_approval=True)
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.requires_approval is True


def test_resolution_inheritance_is_ordered_and_deduplicated() -> None:
    a = PrivacyMetadata(inherited_from=("resource:1", "resource:2"))
    b = PrivacyMetadata(inherited_from=("resource:2", "resource:3"))
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.inherited_from == ("resource:1", "resource:2", "resource:3")


def test_resolution_reports_explicit_conflict() -> None:
    a = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allowed_providers=("p1",))
    b = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allowed_providers=("p2",))
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.allowed_providers == ()
    assert any("allowed_providers" in conflict for conflict in resolution.conflicts)


def test_resolution_is_deterministic() -> None:
    a = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allow_remote=True)
    b = PrivacyMetadata(policy=PrivacyPolicy.LOCAL_PREFERRED)
    first = resolve_effective_privacy_metadata(a, b)
    second = resolve_effective_privacy_metadata(a, b)
    assert first.effective == second.effective
    assert first.restrictions_applied == second.restrictions_applied


def test_resolution_requires_at_least_one_policy() -> None:
    with pytest.raises(PrivacyResolutionError):
        resolve_effective_privacy_metadata()


def test_resolution_result_is_structured() -> None:
    resolution = resolve_effective_privacy_metadata(PrivacyMetadata())
    assert isinstance(resolution, PrivacyResolution)
    assert resolution.source_count == 1
    assert resolution.to_dict()["source_count"] == 1


# ── 30-43: operation evaluation ─────────────────────────────────────────────


def test_process_local_allowed() -> None:
    decision = evaluate_privacy_operation(
        PrivacyMetadata(), PrivacyOperation.PROCESS_LOCAL, PrivacyOperationContext()
    )
    assert decision.allowed is True
    assert decision.status is PrivacyDecisionStatus.ALLOWED


def test_local_only_blocks_remote() -> None:
    decision = evaluate_privacy_operation(
        PrivacyMetadata(policy=PrivacyPolicy.LOCAL_ONLY),
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE),
    )
    assert decision.allowed is False
    assert decision.reason_code == "remote_blocked_local_only"


def test_local_preferred_blocks_remote_without_authorization() -> None:
    decision = evaluate_privacy_operation(
        PrivacyMetadata(policy=PrivacyPolicy.LOCAL_PREFERRED, allow_remote=False),
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE),
    )
    assert decision.allowed is False
    assert decision.reason_code == "remote_blocked_not_authorized"


def test_remote_allowed_when_authorized() -> None:
    privacy = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allow_remote=True,
        allowed_processing_locations=(ProcessingLocation.LOCAL, ProcessingLocation.REMOTE),
    )
    decision = evaluate_privacy_operation(
        privacy, PrivacyOperation.PROCESS_REMOTE, PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE)
    )
    assert decision.allowed is True


def test_cache_blocked() -> None:
    decision = evaluate_privacy_operation(
        PrivacyMetadata(allow_cache=False), PrivacyOperation.CACHE, PrivacyOperationContext()
    )
    assert decision.allowed is False
    assert decision.reason_code == "cache_blocked"


def test_export_blocked() -> None:
    decision = evaluate_privacy_operation(
        PrivacyMetadata(allow_export=False), PrivacyOperation.EXPORT, PrivacyOperationContext()
    )
    assert decision.allowed is False
    assert decision.reason_code == "export_blocked"


def test_premium_blocked() -> None:
    decision = evaluate_privacy_operation(
        PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allow_remote=True, allow_premium=False),
        PrivacyOperation.USE_PREMIUM,
        PrivacyOperationContext(),
    )
    assert decision.allowed is False
    assert decision.reason_code == "premium_blocked"


def test_provider_prohibited() -> None:
    privacy = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allow_remote=True,
        allowed_processing_locations=(ProcessingLocation.LOCAL, ProcessingLocation.REMOTE),
        prohibited_providers=("bad-provider",),
    )
    decision = evaluate_privacy_operation(
        privacy,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, provider_id="bad-provider"),
    )
    assert decision.allowed is False
    assert decision.reason_code == "provider_prohibited"
    assert decision.excluded is True


def test_provider_outside_allowlist() -> None:
    privacy = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allow_remote=True,
        allowed_processing_locations=(ProcessingLocation.LOCAL, ProcessingLocation.REMOTE),
        allowed_providers=("good-provider",),
    )
    decision = evaluate_privacy_operation(
        privacy,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, provider_id="other-provider"),
    )
    assert decision.allowed is False
    assert decision.reason_code == "provider_not_allowlisted"


def test_redaction_required_blocks_until_applied() -> None:
    privacy = PrivacyMetadata(requires_redaction=True)
    blocked = evaluate_privacy_operation(privacy, PrivacyOperation.PROCESS_LOCAL, PrivacyOperationContext())
    assert blocked.allowed is False
    assert blocked.status is PrivacyDecisionStatus.REDACTION_REQUIRED
    allowed = evaluate_privacy_operation(
        privacy, PrivacyOperation.PROCESS_LOCAL, PrivacyOperationContext(redaction_applied=True)
    )
    assert allowed.allowed is True


def test_approval_required_blocks_until_granted() -> None:
    privacy = PrivacyMetadata(requires_approval=True)
    blocked = evaluate_privacy_operation(privacy, PrivacyOperation.PROCESS_LOCAL, PrivacyOperationContext())
    assert blocked.allowed is False
    assert blocked.status is PrivacyDecisionStatus.APPROVAL_REQUIRED
    allowed = evaluate_privacy_operation(
        privacy, PrivacyOperation.PROCESS_LOCAL, PrivacyOperationContext(approval_granted=True)
    )
    assert allowed.allowed is True


def test_actor_permission_denied() -> None:
    privacy = PrivacyMetadata(
        permissions=(
            ResourcePermission(
                allowed_actor_ids=("actor:allowed",),
                allowed_operations=(ResourcePermissionOperation.INFER,),
            ),
        )
    )
    decision = evaluate_privacy_operation(
        privacy, PrivacyOperation.PROCESS_LOCAL, PrivacyOperationContext(actor_id="actor:other")
    )
    assert decision.allowed is False
    assert decision.reason_code == "permission_denied"


def test_permission_expired() -> None:
    privacy = PrivacyMetadata(
        permissions=(
            ResourcePermission(
                allowed_operations=(ResourcePermissionOperation.INFER,),
                expires_at=NOW,
            ),
        )
    )
    decision = evaluate_privacy_operation(
        privacy,
        PrivacyOperation.PROCESS_LOCAL,
        PrivacyOperationContext(at=NOW + timedelta(days=1)),
    )
    assert decision.allowed is False
    assert decision.reason_code == "permission_expired"


def test_decision_is_deterministic() -> None:
    privacy = PrivacyMetadata(allow_cache=False)
    context = PrivacyOperationContext()
    first = evaluate_privacy_operation(privacy, PrivacyOperation.CACHE, context)
    second = evaluate_privacy_operation(privacy, PrivacyOperation.CACHE, context)
    assert first == second


# ── 44-55: propagation ───────────────────────────────────────────────────────


def test_privacy_from_resource() -> None:
    resource = make_resource(sensitivity=SensitivityLevel.SENSITIVE)
    privacy = privacy_from_resource(resource)
    assert isinstance(privacy, PrivacyMetadata)
    assert privacy.sensitivity is SensitivityLevel.SENSITIVE


def test_privacy_from_resource_preserves_sensitivity() -> None:
    resource = make_resource(sensitivity=SensitivityLevel.HIGHLY_SENSITIVE)
    privacy = privacy_from_resource(resource)
    assert privacy.sensitivity is SensitivityLevel.HIGHLY_SENSITIVE


def test_privacy_from_resource_preserves_permissions() -> None:
    permission = ResourcePermission(allowed_actor_ids=("actor:1",))
    resource = make_resource(permissions=(permission,))
    privacy = privacy_from_resource(resource)
    assert privacy.permissions == (permission,)


def test_privacy_from_knowledge_item() -> None:
    item = make_item()
    privacy = privacy_from_knowledge_item(item)
    assert isinstance(privacy, PrivacyMetadata)
    assert privacy.sensitivity is SensitivityLevel.PERSONAL


def test_privacy_from_knowledge_package() -> None:
    resource = make_resource(sensitivity=SensitivityLevel.SENSITIVE)
    package = make_package(resources=(resource,))
    privacy = privacy_from_knowledge_package(package)
    assert isinstance(privacy, PrivacyMetadata)
    assert privacy.sensitivity is SensitivityLevel.SENSITIVE


def test_package_uses_most_restrictive_policy() -> None:
    local_only_resource = make_resource("resource:local", sensitivity=SensitivityLevel.PUBLIC)
    permissive_privacy = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allow_remote=True)
    package = make_package(resources=(local_only_resource,))
    privacy = privacy_from_knowledge_package(package, privacy=permissive_privacy)
    assert privacy.policy is PrivacyPolicy.LOCAL_ONLY


def test_package_historical_privacy_payload_is_compatible() -> None:
    package = make_package(privacy={"classification": "internal"})
    privacy = privacy_from_knowledge_package(package)
    assert isinstance(privacy, PrivacyMetadata)
    assert dict(package.privacy) == {"classification": "internal"}


def test_privacy_from_cache_entry() -> None:
    package = make_package()
    entry = cache_entry_from_knowledge_package(
        package, key="k1", context_signature="ctx-1"
    )
    privacy = privacy_from_cache_entry(entry)
    assert isinstance(privacy, PrivacyMetadata)


def test_allow_cache_false_blocks_put() -> None:
    package = make_package()
    entry = cache_entry_from_knowledge_package(
        package,
        key="k2",
        context_signature="ctx-2",
        privacy=PrivacyMetadata(allow_cache=False),
    )
    cache = CognitiveCache(InMemoryCognitiveCacheStore())
    with pytest.raises(InvalidCognitiveCacheEntryError):
        cache.put(entry)


def test_local_only_entry_blocked_in_remote_context() -> None:
    package = make_package()
    entry = cache_entry_from_knowledge_package(
        package, key="k3", context_signature="ctx-3"
    )
    cache = CognitiveCache(InMemoryCognitiveCacheStore())
    cache.put(entry)
    context = CognitiveCacheContext(
        context_signature="ctx-3",
        sensitivity_clearance=SensitivityLevel.RESTRICTED,
        processing_location=ProcessingLocation.REMOTE,
        at=NOW,
    )
    result = cache.get("k3", context)
    assert result.reusable is False


def test_no_downgrade_between_package_and_cache() -> None:
    strict_resource = make_resource("resource:strict", sensitivity=SensitivityLevel.RESTRICTED)
    package = make_package(resources=(strict_resource,))
    permissive_override = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allow_remote=True)
    entry = cache_entry_from_knowledge_package(
        package, key="k4", context_signature="ctx-4", privacy=permissive_override
    )
    assert entry.privacy is not None
    assert entry.privacy.policy is PrivacyPolicy.LOCAL_ONLY


def test_round_trip_of_integrated_contracts() -> None:
    package = make_package()
    entry = cache_entry_from_knowledge_package(
        package,
        key="k5",
        context_signature="ctx-5",
        privacy=PrivacyMetadata(sensitivity=SensitivityLevel.SENSITIVE),
    )
    restored = type(entry).from_mapping(entry.serialize())
    assert restored.privacy == entry.privacy


# ── 56-60: architecture ──────────────────────────────────────────────────────


def test_public_api_exports_privacy_symbols() -> None:
    from cmm import cognitive

    for name in (
        "PrivacyPolicy",
        "ProcessingLocation",
        "PrivacyMetadata",
        "PrivacyOperation",
        "PrivacyOperationContext",
        "PrivacyDecision",
        "PrivacyDecisionStatus",
        "PrivacyResolution",
        "resolve_effective_privacy_metadata",
        "evaluate_privacy_operation",
    ):
        assert hasattr(cognitive, name), f"missing public export: {name}"


def test_module_has_no_provider_or_routing_imports() -> None:
    module_path = Path(getsourcefile(PrivacyMetadata))
    tree = ast.parse(module_path.read_text())
    forbidden = ("provider", "routing", "llm", "gateway")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = getattr(node, "module", None) or ""
            names = [alias.name for alias in node.names]
            haystack = " ".join([module_name, *names]).lower()
            assert not any(term in haystack for term in forbidden), haystack


def test_does_not_duplicate_sensitivity_level() -> None:
    from cmm.cognitive import privacy as privacy_module

    assert not hasattr(privacy_module, "SensitivityLevel") or (
        privacy_module.SensitivityLevel is SensitivityLevel
    )


def test_does_not_duplicate_resource_permission() -> None:
    from cmm.cognitive import privacy as privacy_module

    assert privacy_module.ResourcePermission is ResourcePermission


def test_compatible_with_existing_cognitive_suite() -> None:
    package = make_package()
    entry = cache_entry_from_knowledge_package(package, key="k6", context_signature="ctx-6")
    cache = CognitiveCache(InMemoryCognitiveCacheStore())
    cache.put(entry)
    context = CognitiveCacheContext(
        context_signature="ctx-6",
        sensitivity_clearance=SensitivityLevel.RESTRICTED,
        at=NOW,
    )
    result = cache.get("k6", context)
    assert result.hit is True


# ── Security fix 1: allowlist absence vs. restrictive-empty allowlist ───────


def test_missing_allowlist_permits_a_non_prohibited_provider() -> None:
    privacy = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allow_remote=True,
        allowed_processing_locations=(ProcessingLocation.LOCAL, ProcessingLocation.REMOTE),
    )
    assert privacy.allowed_providers is None
    decision = evaluate_privacy_operation(
        privacy,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, provider_id="any-provider"),
    )
    assert decision.allowed is True


def test_explicit_empty_allowlist_blocks_every_provider() -> None:
    privacy = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allow_remote=True,
        allowed_processing_locations=(ProcessingLocation.LOCAL, ProcessingLocation.REMOTE),
        allowed_providers=(),
    )
    decision = evaluate_privacy_operation(
        privacy,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, provider_id="any-provider"),
    )
    assert decision.allowed is False
    assert decision.reason_code == "provider_not_allowlisted"


def test_incompatible_allowlists_resolve_to_blocking_empty_tuple() -> None:
    locations = (ProcessingLocation.LOCAL, ProcessingLocation.REMOTE)
    a = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allow_remote=True,
        allowed_processing_locations=locations,
        allowed_providers=("p1",),
    )
    b = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allow_remote=True,
        allowed_processing_locations=locations,
        allowed_providers=("p2",),
    )
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.allowed_providers == ()
    assert resolution.effective.allowed_providers is not None
    decision = evaluate_privacy_operation(
        resolution.effective,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE, provider_id="p1"
        ),
    )
    assert decision.allowed is False
    assert decision.reason_code == "provider_not_allowlisted"


def test_overlapping_allowlists_permit_only_common_providers() -> None:
    a = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allow_remote=True, allowed_providers=("p1", "p2"))
    b = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allow_remote=True, allowed_providers=("p2", "p3"))
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.allowed_providers == ("p2",)


def test_allowed_providers_none_vs_empty_round_trip() -> None:
    absent = PrivacyMetadata()
    restored_absent = PrivacyMetadata.from_mapping(absent.serialize())
    assert restored_absent.allowed_providers is None

    empty = PrivacyMetadata(policy=PrivacyPolicy.REMOTE_ALLOWED, allow_remote=True, allowed_providers=())
    restored_empty = PrivacyMetadata.from_mapping(empty.serialize())
    assert restored_empty.allowed_providers == ()
    assert restored_empty.allowed_providers is not None


# ── Security fix 2: semantic ResourcePermission intersection ───────────────


def test_permission_intersection_identical() -> None:
    permission = ResourcePermission(
        allowed_actor_ids=("actor:1",), allowed_operations=(ResourcePermissionOperation.INFER,)
    )
    a = PrivacyMetadata(permissions=(permission,))
    b = PrivacyMetadata(permissions=(permission,))
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.permissions == (permission,)
    assert resolution.effective.permissions_denied is False


def test_permission_intersection_partially_overlapping_actors() -> None:
    a = PrivacyMetadata(
        permissions=(ResourcePermission(allowed_actor_ids=("actor:1", "actor:2")),)
    )
    b = PrivacyMetadata(
        permissions=(ResourcePermission(allowed_actor_ids=("actor:2", "actor:3")),)
    )
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.permissions_denied is False
    assert len(resolution.effective.permissions) == 1
    assert resolution.effective.permissions[0].allowed_actor_ids == ("actor:2",)


def test_permission_intersection_partially_overlapping_domains() -> None:
    a = PrivacyMetadata(permissions=(ResourcePermission(allowed_domains=("health", "finance")),))
    b = PrivacyMetadata(permissions=(ResourcePermission(allowed_domains=("finance", "legal")),))
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.permissions_denied is False
    assert resolution.effective.permissions[0].allowed_domains == ("finance",)


def test_permission_intersection_partially_overlapping_operations() -> None:
    a = PrivacyMetadata(
        permissions=(
            ResourcePermission(
                allowed_operations=(ResourcePermissionOperation.READ, ResourcePermissionOperation.INFER)
            ),
        )
    )
    b = PrivacyMetadata(
        permissions=(
            ResourcePermission(
                allowed_operations=(ResourcePermissionOperation.INFER, ResourcePermissionOperation.EXPORT)
            ),
        )
    )
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.permissions_denied is False
    assert resolution.effective.permissions[0].allowed_operations == (ResourcePermissionOperation.INFER,)


def test_permission_intersection_earliest_expiry() -> None:
    earlier = NOW
    later = NOW + timedelta(days=30)
    a = PrivacyMetadata(permissions=(ResourcePermission(expires_at=later),))
    b = PrivacyMetadata(permissions=(ResourcePermission(expires_at=earlier),))
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.permissions_denied is False
    assert resolution.effective.permissions[0].expires_at == earlier


def test_permission_intersection_incompatible_actors_denies() -> None:
    a = PrivacyMetadata(permissions=(ResourcePermission(allowed_actor_ids=("actor:1",)),))
    b = PrivacyMetadata(permissions=(ResourcePermission(allowed_actor_ids=("actor:2",)),))
    resolution = resolve_effective_privacy_metadata(a, b)
    assert resolution.effective.permissions == ()
    assert resolution.effective.permissions_denied is True
    assert any("permissions" in conflict for conflict in resolution.conflicts)


def test_permission_incompatibility_never_opens_the_operation() -> None:
    a = PrivacyMetadata(permissions=(ResourcePermission(allowed_actor_ids=("actor:1",)),))
    b = PrivacyMetadata(permissions=(ResourcePermission(allowed_actor_ids=("actor:2",)),))
    resolution = resolve_effective_privacy_metadata(a, b)
    decision = evaluate_privacy_operation(
        resolution.effective,
        PrivacyOperation.PROCESS_LOCAL,
        PrivacyOperationContext(actor_id="actor:1"),
    )
    assert decision.allowed is False
    assert decision.reason_code == "permissions_denied"


def test_unrestricted_policy_does_not_remove_another_policys_restriction() -> None:
    restricted = PrivacyMetadata(permissions=(ResourcePermission(allowed_actor_ids=("actor:1",)),))
    unrestricted = PrivacyMetadata()
    resolution = resolve_effective_privacy_metadata(restricted, unrestricted)
    assert resolution.effective.permissions_denied is False
    assert resolution.effective.permissions[0].allowed_actor_ids == ("actor:1",)
    denied = evaluate_privacy_operation(
        resolution.effective,
        PrivacyOperation.PROCESS_LOCAL,
        PrivacyOperationContext(actor_id="actor:other"),
    )
    assert denied.allowed is False


# ── Security fix 3: schema_version mandatory in from_mapping ───────────────


def test_from_mapping_rejects_missing_schema_version() -> None:
    payload = PrivacyMetadata().serialize()
    del payload["schema_version"]
    with pytest.raises(InvalidPrivacyMetadataError):
        PrivacyMetadata.from_mapping(payload)


def test_from_mapping_rejects_invalid_schema_version() -> None:
    payload = PrivacyMetadata().serialize()
    payload["schema_version"] = 99
    with pytest.raises(InvalidPrivacyMetadataError):
        PrivacyMetadata.from_mapping(payload)


def test_direct_constructor_still_uses_default_schema_version() -> None:
    assert PrivacyMetadata().schema_version == 1


# ── Security fix 4: strict boolean parsing in from_mapping ─────────────────


@pytest.mark.parametrize("bad_value", ["false", "true", 0, 1, [], {}])
def test_from_mapping_rejects_non_bool_flag_values(bad_value: object) -> None:
    payload = PrivacyMetadata().serialize()
    payload["allow_remote"] = bad_value
    with pytest.raises(InvalidPrivacyMetadataError):
        PrivacyMetadata.from_mapping(payload)


@pytest.mark.parametrize(
    "field_name",
    [
        "allow_remote",
        "allow_premium",
        "allow_cache",
        "allow_export",
        "requires_redaction",
        "requires_approval",
    ],
)
def test_from_mapping_rejects_string_false_for_every_boolean_field(field_name: str) -> None:
    payload = PrivacyMetadata().serialize()
    payload[field_name] = "false"
    with pytest.raises(InvalidPrivacyMetadataError):
        PrivacyMetadata.from_mapping(payload)


def test_from_mapping_accepts_real_booleans() -> None:
    payload = PrivacyMetadata().serialize()
    payload["allow_cache"] = False
    restored = PrivacyMetadata.from_mapping(payload)
    assert restored.allow_cache is False


def test_from_mapping_uses_default_when_flag_absent() -> None:
    payload = PrivacyMetadata().serialize()
    del payload["allow_cache"]
    restored = PrivacyMetadata.from_mapping(payload)
    assert restored.allow_cache is True


# ── Compatibility: historical KnowledgePackage.privacy mapping ─────────────


def test_package_without_policy_key_still_ignored_safely() -> None:
    package = make_package(privacy={"note": "legacy, no policy key"})
    privacy = privacy_from_knowledge_package(package)
    assert isinstance(privacy, PrivacyMetadata)
