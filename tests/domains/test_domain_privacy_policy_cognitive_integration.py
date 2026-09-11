"""Phase 10.50 – pure projection of Domain privacy into canonical ``PrivacyMetadata``.

The projection is a thin adapter only: canonical Phase 8
``resolve_effective_privacy_metadata`` and ``evaluate_privacy_operation`` remain
the sole effective-policy authority. No authority component is mocked here.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive.contracts import Confidence
from cmm.cognitive.enums import KnowledgeKind, SensitivityLevel
from cmm.cognitive.knowledge import KnowledgeItem
from cmm.cognitive.knowledge_packages import (
    KnowledgePackageBuilder,
    KnowledgePackageRequest,
)
from cmm.cognitive.privacy import (
    PrivacyDecisionStatus,
    PrivacyMetadata,
    PrivacyOperation,
    PrivacyOperationContext,
    PrivacyPolicy,
    ProcessingLocation,
    evaluate_privacy_operation,
    privacy_from_knowledge_package,
    resolve_effective_privacy_metadata,
)
from cmm.cognitive.resources import (
    Resource,
    ResourceKind,
    ResourceProvenance,
    ResourceSourceKind,
    ResourceTemporalScope,
)
from cmm.cognitive.store_memory import InMemoryKnowledgeStore
from cmm.domains.errors import DomainPrivacyPolicyContractError
from cmm.domains.health.privacy import build_health_privacy_policy
from cmm.domains.identifiers import DomainId
from cmm.domains.privacy_policy_contracts import (
    DomainPrivacyPolicy,
    project_domain_privacy_metadata,
)
from cmm.domains.university.privacy import build_university_privacy_policy

NOW = datetime(2026, 9, 11, 9, 0, tzinfo=timezone.utc)

_LOCAL_ONLY = PrivacyMetadata(
    policy=PrivacyPolicy.LOCAL_ONLY,
    sensitivity=SensitivityLevel.SENSITIVE,
    allowed_processing_locations=(ProcessingLocation.LOCAL,),
    allow_remote=False,
    allow_premium=False,
    allow_cache=True,
    allow_export=False,
)

_REMOTE_ALLOWED = PrivacyMetadata(
    policy=PrivacyPolicy.REMOTE_ALLOWED,
    sensitivity=SensitivityLevel.INTERNAL,
    allowed_processing_locations=(
        ProcessingLocation.LOCAL,
        ProcessingLocation.REMOTE,
    ),
    allowed_providers=("provider:alpha", "provider:beta"),
    prohibited_providers=("provider:gamma",),
    allow_remote=True,
    allow_premium=False,
    allow_cache=True,
    allow_export=False,
    requires_redaction=True,
)


def _policy(privacy: PrivacyMetadata, **overrides: object) -> DomainPrivacyPolicy:
    data: dict[str, object] = {
        "schema_version": "1",
        "domain_id": DomainId(slug="health"),
        "default_privacy": privacy,
    }
    data.update(overrides)
    return DomainPrivacyPolicy(**data)  # type: ignore[arg-type]


# ── Projection semantics ──────────────────────────────────────────────────────


def test_projection_returns_default_privacy_for_local_processing() -> None:
    policy = _policy(_REMOTE_ALLOWED, require_approval_for_remote=True)

    projected = project_domain_privacy_metadata(
        policy, processing_location=ProcessingLocation.LOCAL
    )

    assert projected == _REMOTE_ALLOWED
    assert projected.requires_approval is False


def test_projection_adds_remote_approval_without_widening() -> None:
    policy = _policy(_REMOTE_ALLOWED, require_approval_for_remote=True)

    projected = project_domain_privacy_metadata(
        policy, processing_location=ProcessingLocation.REMOTE
    )

    assert projected.requires_approval is True
    assert projected.policy is PrivacyPolicy.REMOTE_ALLOWED
    assert projected.allow_remote is True
    assert projected.allow_export is False
    assert projected.prohibited_providers == ("provider:gamma",)
    assert projected.allowed_providers == ("provider:alpha", "provider:beta")
    assert projected.sensitivity is SensitivityLevel.INTERNAL


def test_projection_preserves_local_only_policy() -> None:
    policy = _policy(_LOCAL_ONLY, require_approval_for_remote=True)

    projected = project_domain_privacy_metadata(
        policy, processing_location=ProcessingLocation.REMOTE
    )

    assert projected.policy is PrivacyPolicy.LOCAL_ONLY
    assert projected.allow_remote is False
    assert projected.requires_approval is True


def test_projection_preserves_allow_remote_false() -> None:
    policy = _policy(_LOCAL_ONLY)

    projected = project_domain_privacy_metadata(
        policy, processing_location=ProcessingLocation.REMOTE
    )

    assert projected.allow_remote is False
    assert projected.allowed_processing_locations == (ProcessingLocation.LOCAL,)


def test_projection_preserves_export_cache_premium_and_redaction() -> None:
    policy = _policy(_REMOTE_ALLOWED, require_approval_for_remote=True)

    projected = project_domain_privacy_metadata(
        policy, processing_location=ProcessingLocation.REMOTE
    )

    assert projected.allow_export is False
    assert projected.allow_cache is True
    assert projected.allow_premium is False
    assert projected.requires_redaction is True


def test_projection_preserves_allowed_and_prohibited_providers() -> None:
    policy = _policy(_REMOTE_ALLOWED)

    projected = project_domain_privacy_metadata(
        policy, processing_location=ProcessingLocation.LOCAL
    )

    assert projected.allowed_providers == ("provider:alpha", "provider:beta")
    assert projected.prohibited_providers == ("provider:gamma",)


def test_projection_preserves_sensitivity() -> None:
    policy = _policy(_LOCAL_ONLY)

    projected = project_domain_privacy_metadata(
        policy, processing_location=ProcessingLocation.LOCAL
    )

    assert projected.sensitivity is SensitivityLevel.SENSITIVE


def test_projection_requires_canonical_processing_location() -> None:
    policy = _policy(_LOCAL_ONLY)

    coerced = project_domain_privacy_metadata(
        policy,
        processing_location="remote",  # type: ignore[arg-type]
    )
    assert coerced.requires_approval is False

    for invalid in (None, "somewhere", 42):
        with pytest.raises(DomainPrivacyPolicyContractError):
            project_domain_privacy_metadata(policy, processing_location=invalid)  # type: ignore[arg-type]

    with pytest.raises(DomainPrivacyPolicyContractError):
        project_domain_privacy_metadata(
            "not-a-policy", processing_location=ProcessingLocation.LOCAL
        )  # type: ignore[arg-type]


def test_projection_does_not_mutate_the_declared_metadata() -> None:
    policy = _policy(_REMOTE_ALLOWED, require_approval_for_remote=True)

    projected = project_domain_privacy_metadata(
        policy, processing_location=ProcessingLocation.REMOTE
    )

    assert projected is not policy.default_privacy
    assert policy.default_privacy.requires_approval is False


# ── Canonical Phase 8 remains authoritative ───────────────────────────────────


def test_canonical_resolver_keeps_resource_local_only_over_remote_domain() -> None:
    domain_privacy = project_domain_privacy_metadata(
        _policy(_REMOTE_ALLOWED), processing_location=ProcessingLocation.REMOTE
    )
    resource_privacy = PrivacyMetadata(
        policy=PrivacyPolicy.LOCAL_ONLY,
        sensitivity=SensitivityLevel.RESTRICTED,
        inherited_from=("resource:health-record",),
    )

    resolution = resolve_effective_privacy_metadata(resource_privacy, domain_privacy)

    assert resolution.effective.policy is PrivacyPolicy.LOCAL_ONLY
    assert resolution.effective.allow_remote is False
    assert resolution.effective.sensitivity is SensitivityLevel.RESTRICTED
    assert resolution.effective.allowed_processing_locations == (
        ProcessingLocation.LOCAL,
    )


def test_canonical_evaluator_denies_remote_when_effective_policy_is_local_only() -> (
    None
):
    effective = resolve_effective_privacy_metadata(
        PrivacyMetadata(policy=PrivacyPolicy.LOCAL_ONLY),
        project_domain_privacy_metadata(
            _policy(_REMOTE_ALLOWED), processing_location=ProcessingLocation.REMOTE
        ),
    ).effective

    decision = evaluate_privacy_operation(
        effective,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, at=NOW),
    )

    assert decision.allowed is False
    assert decision.status is PrivacyDecisionStatus.DENIED
    assert decision.reason_code == "remote_blocked_local_only"


def test_remote_approval_does_not_convert_denial_to_allow() -> None:
    local_only_policy = _policy(_LOCAL_ONLY, require_approval_for_remote=True)
    projected = project_domain_privacy_metadata(
        local_only_policy, processing_location=ProcessingLocation.REMOTE
    )
    assert projected.requires_approval is True

    decision = evaluate_privacy_operation(
        projected,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            approval_granted=True,
            at=NOW,
        ),
    )

    assert decision.allowed is False
    assert decision.status is PrivacyDecisionStatus.DENIED
    assert decision.reason_code == "remote_blocked_local_only"


def test_remote_allowed_domain_can_still_require_approval() -> None:
    projected = project_domain_privacy_metadata(
        _policy(_REMOTE_ALLOWED, require_approval_for_remote=True),
        processing_location=ProcessingLocation.REMOTE,
    )

    without_approval = evaluate_privacy_operation(
        projected,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            redaction_applied=True,
            at=NOW,
        ),
    )
    assert without_approval.allowed is False
    assert without_approval.status is PrivacyDecisionStatus.APPROVAL_REQUIRED

    with_approval = evaluate_privacy_operation(
        projected,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            redaction_applied=True,
            approval_granted=True,
            at=NOW,
        ),
    )
    assert with_approval.allowed is True


def test_cache_export_provider_and_redaction_restrictions_survive_composition() -> None:
    permissive = PrivacyMetadata(
        policy=PrivacyPolicy.PREMIUM_ALLOWED,
        sensitivity=SensitivityLevel.PUBLIC,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        allowed_providers=("provider:alpha", "provider:beta"),
        allow_remote=True,
        allow_premium=True,
        allow_cache=True,
        allow_export=True,
    )
    restrictive = PrivacyMetadata(
        policy=PrivacyPolicy.LOCAL_PREFERRED,
        sensitivity=SensitivityLevel.INTERNAL,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        allowed_providers=("provider:beta",),
        prohibited_providers=("provider:gamma",),
        allow_remote=True,
        allow_premium=False,
        allow_cache=False,
        allow_export=False,
        requires_redaction=True,
        requires_approval=True,
    )

    resolution = resolve_effective_privacy_metadata(permissive, restrictive)
    effective = resolution.effective

    assert effective.allow_cache is False
    assert effective.allow_export is False
    assert effective.requires_redaction is True
    assert effective.requires_approval is True
    assert effective.allowed_providers == ("provider:beta",)
    assert effective.prohibited_providers == ("provider:gamma",)
    assert effective.allow_premium is False
    assert effective.policy is PrivacyPolicy.LOCAL_PREFERRED
    assert effective.sensitivity is SensitivityLevel.INTERNAL

    export_decision = evaluate_privacy_operation(
        effective,
        PrivacyOperation.EXPORT,
        PrivacyOperationContext(at=NOW),
    )
    assert export_decision.allowed is False
    assert export_decision.reason_code == "export_blocked"

    prohibited_decision = evaluate_privacy_operation(
        effective,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            provider_id="provider:gamma",
            redaction_applied=True,
            approval_granted=True,
            at=NOW,
        ),
    )
    assert prohibited_decision.allowed is False
    assert prohibited_decision.reason_code == "provider_prohibited"


def test_provider_prohibition_cannot_be_re_enabled_by_domain_default() -> None:
    resource = PrivacyMetadata(
        policy=PrivacyPolicy.REMOTE_ALLOWED,
        allowed_processing_locations=(
            ProcessingLocation.LOCAL,
            ProcessingLocation.REMOTE,
        ),
        prohibited_providers=("provider:gamma",),
        allow_remote=True,
    )
    domain_default = project_domain_privacy_metadata(
        _policy(
            PrivacyMetadata(
                policy=PrivacyPolicy.REMOTE_ALLOWED,
                allowed_processing_locations=(
                    ProcessingLocation.LOCAL,
                    ProcessingLocation.REMOTE,
                ),
                allow_remote=True,
                allow_cache=True,
            )
        ),
        processing_location=ProcessingLocation.REMOTE,
    )

    effective = resolve_effective_privacy_metadata(resource, domain_default).effective

    assert effective.prohibited_providers == ("provider:gamma",)
    decision = evaluate_privacy_operation(
        effective,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            provider_id="provider:gamma",
            at=NOW,
        ),
    )
    assert decision.allowed is False
    assert decision.reason_code == "provider_prohibited"


# ── Real canonical KnowledgePackage composition ───────────────────────────────
#
# These use the real canonical Phase 8 ``KnowledgePackageBuilder`` and
# ``privacy_from_knowledge_package``. No authority component is mocked.


def _resource(
    resource_id: str = "resource:health-record",
    *,
    sensitivity: SensitivityLevel = SensitivityLevel.SENSITIVE,
) -> Resource:
    return Resource(
        id=resource_id,
        domain="domain:health",
        kind=ResourceKind.DOCUMENT,
        source=ResourceSourceKind.USER_INPUT,
        content="clinical notes",
        provenance=ResourceProvenance(
            source_type=ResourceSourceKind.USER_INPUT,
            source_id="user:1",
            retrieved_at=NOW,
        ),
        reliability=Confidence(value=0.9),
        temporal_scope=ResourceTemporalScope(ingested_at=NOW),
        sensitivity=sensitivity,
        created_at=NOW,
        updated_at=NOW,
    )


def _store(resource: Resource) -> InMemoryKnowledgeStore:
    store = InMemoryKnowledgeStore()
    store.save_item(
        KnowledgeItem(
            id="item:health-record",
            statement="Recorded blood pressure observation.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=Confidence(value=0.9),
            resource_id=resource.id,
            sensitivity=SensitivityLevel.SENSITIVE,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    return store


def _package(resource: Resource):
    return KnowledgePackageBuilder(store=_store(resource), resources=(resource,)).build(
        KnowledgePackageRequest(
            objective="health record review", domain="domain:health"
        )
    )


def test_health_package_privacy_is_local_only_and_cannot_export() -> None:
    resource = _resource()
    package = _package(resource)

    package_privacy = privacy_from_knowledge_package(package)
    domain_privacy = project_domain_privacy_metadata(
        build_health_privacy_policy(), processing_location=ProcessingLocation.REMOTE
    )

    effective = resolve_effective_privacy_metadata(
        package_privacy, domain_privacy
    ).effective

    assert effective.policy is PrivacyPolicy.LOCAL_ONLY
    assert effective.allow_remote is False
    assert effective.allow_export is False
    assert effective.sensitivity is SensitivityLevel.SENSITIVE

    export_decision = evaluate_privacy_operation(
        effective, PrivacyOperation.EXPORT, PrivacyOperationContext(at=NOW)
    )
    assert export_decision.allowed is False
    assert export_decision.reason_code == "export_blocked"

    remote_decision = evaluate_privacy_operation(
        effective,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, at=NOW),
    )
    assert remote_decision.allowed is False
    assert remote_decision.reason_code == "remote_blocked_local_only"


def test_university_remote_default_does_not_widen_local_only_package() -> None:
    resource = _resource("resource:university-notes")
    package = _package(resource)

    effective = resolve_effective_privacy_metadata(
        privacy_from_knowledge_package(package),
        project_domain_privacy_metadata(
            build_university_privacy_policy(),
            processing_location=ProcessingLocation.REMOTE,
        ),
    ).effective

    assert effective.policy is PrivacyPolicy.LOCAL_ONLY
    assert effective.allow_remote is False
    assert effective.allowed_processing_locations == (ProcessingLocation.LOCAL,)


def test_package_privacy_and_domain_privacy_raise_sensitivity_above_orientation() -> (
    None
):
    resource = _resource(
        "resource:restricted-notes", sensitivity=SensitivityLevel.RESTRICTED
    )
    package = _package(resource)

    effective = resolve_effective_privacy_metadata(
        privacy_from_knowledge_package(package),
        project_domain_privacy_metadata(
            build_university_privacy_policy(),
            processing_location=ProcessingLocation.LOCAL,
        ),
    ).effective

    assert effective.sensitivity is SensitivityLevel.RESTRICTED
    assert effective.policy is PrivacyPolicy.LOCAL_ONLY


def test_health_domain_privacy_never_mutates_the_canonical_package() -> None:
    resource = _resource()
    package = _package(resource)
    before = package.serialize()

    project_domain_privacy_metadata(
        build_health_privacy_policy(), processing_location=ProcessingLocation.REMOTE
    )
    privacy_from_knowledge_package(package)

    assert package.serialize() == before


def test_university_domain_default_alone_permits_remote_but_package_blocks_it() -> None:
    university_remote = project_domain_privacy_metadata(
        build_university_privacy_policy(),
        processing_location=ProcessingLocation.REMOTE,
    )
    domain_only = resolve_effective_privacy_metadata(university_remote).effective
    assert domain_only.policy is PrivacyPolicy.REMOTE_ALLOWED

    domain_only_remote = evaluate_privacy_operation(
        domain_only,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, at=NOW),
    )
    assert domain_only_remote.allowed is True

    resource = _resource("resource:university-notes")
    package = _package(resource)
    composed = resolve_effective_privacy_metadata(
        privacy_from_knowledge_package(package), university_remote
    ).effective

    composed_remote = evaluate_privacy_operation(
        composed,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, at=NOW),
    )
    assert composed.policy is PrivacyPolicy.LOCAL_ONLY
    assert composed_remote.allowed is False
    assert composed_remote.reason_code == "remote_blocked_local_only"
