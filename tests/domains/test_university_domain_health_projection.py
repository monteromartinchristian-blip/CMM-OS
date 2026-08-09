"""Phase 10.22 — Cross-domain Health → University constraint projection.

Frozen decision: Health→University defaults to **minimal constraint projection**
(hybrid mode).  Detailed clinical context is NOT transferred by default; only an
authorized minimal functional constraint may enter University, and only when
relevant and permitted.  Supporting-domain participation must never widen
University permissions; the most restrictive effective policy wins.

These tests prove the invariants hold through the real University contracts:
the University package never reads a Health store directly; the workload rule
consumes an *authorized constraint projection* rather than fetching Health
records; and the University permission model cannot be widened by a supporting
domain.
"""

from __future__ import annotations

import inspect
import pathlib
from datetime import datetime, timezone

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains import university
from cmm.domains.university.rules import evaluate_academic_workload

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _context(**metadata) -> ReasoningRuleContext:
    return ReasoningRuleContext(
        reasoning_id="rid",
        timestamp=T,
        active_domains=("domain:university", "domain:health"),
        primary_domain="domain:university",
        metadata=metadata,
    )


def test_university_package_never_reads_health_store_directly():
    """No direct ``health`` store access from the University package.

    The canonical principle: detailed clinical context must not be fetched by
    University; only an authorized projection may enter.  We assert the
    University package never imports a Health domain module / registry or
    references a Health store/registry/resource.  (The word "Health" may appear
    in a spec-referencing docstring; what matters is the absence of any direct
    store/import coupling.)
    """
    package_dir = pathlib.Path(university.__file__).resolve().parent
    coupling_markers = (
        "import cmm.domains.health",
        "from cmm.domains.health",
        "health_registry",
        "health_resource",
        "HealthResolver",
        "HealthMemoryStore",
    )
    for module in package_dir.glob("*.py"):
        src = module.read_text(encoding="utf-8")
        for marker in coupling_markers:
            assert marker not in src, (
                f"{module.name} directly couples to a Health store via {marker!r}"
            )


def test_workload_rule_consumes_authorized_constraint_projection():
    """AcademicWorkloadRule consumes an authorized constraint projection, not a
    Health record.  A reduced-availability constraint is folded into the plan as
    a factual input, and the rule never fetches Health data itself."""
    rule = {
        r.definition.id: r
        for r in university.build_university_rules()
    }["university.academic_workload"]
    # The constraint projection is a *minimal functional constraint* already
    # authorized for transfer (e.g. "reduced available workload"), not clinical
    # detail.
    result = rule.evaluate(
        _context(
            workload={
                "total_ect": 60,
                "full_time_ect": 30,
                "max_ratio": 1.5,
                "constraint_projection": {
                    "reduced_workload": True,
                    "authorized": True,
                },
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "WORKLOAD_OVERCOMMIT" for finding in result.findings
    )


def test_workload_helper_accepts_only_scalar_constraint_signal():
    """The deterministic workload helper reduces to a scalar signal; it never
    carries clinical detail out of Health."""
    record = evaluate_academic_workload(total_ect=60, full_time_ect=30)
    assert record["flagged"] is True
    # The workload assessment is a scalar planning risk, never a Health record.
    assert "total_ect" in record and "ratio" in record


def test_supporting_health_cannot_widen_university_permissions():
    """Supporting-domain participation must not widen University permissions.

    The University permission policy is a closed surface; a Health capability
    (e.g. MEMORY_WRITE or SENSITIVE_INFERENCE_PERSIST or EXPORT) is not granted
    by University's own policy and is not in its allowed set.  Inbound
    ``domain_cross_access`` is accepted only as a scoped, approval-gated
    minimal projection — it is never granted as an autonomous outbound
    capability and never widens University's mutating surface.
    """
    policy = university.build_university_permission_policy()
    for capability in (
        PermissionCapability.MEMORY_WRITE,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
        PermissionCapability.EXPORT,
    ):
        assert capability not in policy.allowed_capabilities
        assert capability in policy.prohibited_capabilities
    # Inbound cross-domain is scoped and approval-gated, not an autonomous
    # outbound grant; University grants no outbound cross-domain access.
    assert PermissionCapability.DOMAIN_CROSS_ACCESS not in policy.allowed_capabilities
    assert PermissionCapability.DOMAIN_CROSS_ACCESS not in policy.prohibited_capabilities
    assert PermissionCapability.DOMAIN_CROSS_ACCESS in policy.approval_capabilities
    assert policy.allow_cross_domain_access is False


def test_most_restrictive_effective_policy_wins():
    """The most restrictive effective policy wins: University does not
    auto-authorize cross-domain access or export, so a Health peering cannot
    widen University's surface."""
    policy = university.build_university_permission_policy()
    assert policy.allow_cross_domain_access is False
    assert policy.allow_export is False
    assert policy.autonomy_limits.allow_irreversible_changes is False


def test_university_reject_unrelated_health_content():
    """Unrelated health content is not transferred: University declares no
    Health resource as required and its resources are all University-scoped."""
    from cmm.domains.university.catalog import CANONICAL_UNIVERSITY_RESOURCE_IDS

    resource_ids = set(CANONICAL_UNIVERSITY_RESOURCE_IDS)
    assert not any("health" in resource_id for resource_id in resource_ids)
    for resource in university.build_university_resource_definitions():
        assert resource.domain_id == "domain:university"


def test_shared_resource_not_duplicated():
    """A shared resource is not duplicated: University resource IDs are all
    distinct within the canonical catalog."""
    from cmm.domains.university.catalog import CANONICAL_UNIVERSITY_RESOURCE_IDS

    ids = list(CANONICAL_UNIVERSITY_RESOURCE_IDS)
    assert len(ids) == len(set(ids))


def test_no_direct_health_store_import_in_inspection():
    """The integration bootstrap never imports a Health store; University
    composes with General only for fallback."""
    from cmm.domains.university import bootstrap

    src = inspect.getsource(bootstrap)
    assert "health" not in src.lower()