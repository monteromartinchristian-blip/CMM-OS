"""Phase 10.32 — Domain Conflict Resolution Adversarial and Purity tests."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

from cmm.domains.conflict_resolution import DomainConflictResolver
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReasonCode,
    DomainConflictReference,
    DomainConflictResolutionPolicy,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
    DomainConflictStrategy,
)
from cmm.domains.identifiers import DomainId


def _ref(
    source_id: str,
    *,
    domain_slug: str | None = None,
    blocking: bool = False,
    authority: DomainConflictAuthority = DomainConflictAuthority.UNCLASSIFIED,
) -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id=source_id,
        domain_id=DomainId(slug=domain_slug) if domain_slug else None,
        blocking=blocking,
        severity=(
            DomainConflictSeverity.BLOCKING
            if blocking
            else DomainConflictSeverity.MATERIAL
        ),
        authority_kind=authority,
    )


def test_resolver_has_no_forbidden_imports() -> None:
    path = Path("cmm/domains/conflict_resolution.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))

    forbidden_modules = {
        "time",
        "datetime",
        "uuid",
        "random",
        "secrets",
        "socket",
        "http",
        "urllib",
        "requests",
    }
    forbidden_prefixes = (
        "cmm.agent_runtime.approval_service",
        "cmm.agent_runtime.workflow",
        "cmm.cognitive.store",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                assert root_pkg not in forbidden_modules, (
                    f"Forbidden import: {alias.name}"
                )
                for prefix in forbidden_prefixes:
                    assert not alias.name.startswith(prefix), (
                        f"Forbidden import prefix: {alias.name}"
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            root_pkg = node.module.split(".")[0]
            assert root_pkg not in forbidden_modules, (
                f"Forbidden from-import: {node.module}"
            )
            for prefix in forbidden_prefixes:
                assert not node.module.startswith(prefix), (
                    f"Forbidden from-import prefix: {node.module}"
                )


def test_resolver_is_pure_and_does_not_call_time_or_random() -> None:
    resolver = DomainConflictResolver()
    ref1 = _ref("ref-1", authority=DomainConflictAuthority.EVIDENCE)
    ref2 = _ref("ref-2", authority=DomainConflictAuthority.EVIDENCE)
    case = DomainConflictCase(
        id="case-purity",
        domains=(),
        kind=DomainConflictKind.EVIDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
        blocking=False,
    )

    def _trap(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Forbidden impure call inside resolver!")

    with (
        patch("time.time", side_effect=_trap),
        patch("uuid.uuid4", side_effect=_trap),
        patch("random.random", side_effect=_trap),
    ):
        res1 = resolver.resolve(case, evidence_scores={"ref-1": 0.8, "ref-2": 0.2})
        res2 = resolver.resolve(case, evidence_scores={"ref-1": 0.8, "ref-2": 0.2})

    assert res1 == res2
    assert res1.to_dict() == res2.to_dict()


def test_adversarial_user_preference_cannot_override_global_safety() -> None:
    resolver = DomainConflictResolver()
    ref_safety = _ref(
        "safety-1", blocking=True, authority=DomainConflictAuthority.GLOBAL_SAFETY
    )
    ref_user = _ref(
        "user-pref-1", blocking=False, authority=DomainConflictAuthority.USER
    )

    case = DomainConflictCase(
        id="case-adv-safety",
        domains=(),
        kind=DomainConflictKind.SAFETY,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_safety, ref_user),
        blocking=True,
    )

    res = resolver.resolve(case)
    assert res.winning_reference_ids == ("safety-1",)
    assert res.can_proceed is False
    assert res.requires_user_input is False
    assert DomainConflictReasonCode.SAFETY_PRECEDENCE in res.reason_codes


def test_adversarial_temporal_freshness_cannot_convert_permission_deny() -> None:
    resolver = DomainConflictResolver()
    ref_perm = _ref(
        "perm-deny", blocking=True, authority=DomainConflictAuthority.PERMISSION
    )
    ref_temp = _ref(
        "temp-fresh", blocking=False, authority=DomainConflictAuthority.TEMPORAL
    )

    case = DomainConflictCase(
        id="case-adv-perm-temp",
        domains=(),
        kind=DomainConflictKind.PERMISSION,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_perm, ref_temp),
        blocking=True,
    )

    res = resolver.resolve(
        case, temporal_scores={"perm-deny": 1.0, "temp-fresh": 9999.0}
    )
    assert "temp-fresh" not in res.winning_reference_ids
    assert res.can_proceed is False
    assert DomainConflictReasonCode.PERMISSION_PRECEDENCE in res.reason_codes


def test_adversarial_primary_domain_cannot_defeat_mandatory_rule() -> None:
    resolver = DomainConflictResolver()
    ref_mandatory = _ref(
        "mand-1",
        domain_slug="compliance",
        blocking=True,
        authority=DomainConflictAuthority.MANDATORY_RULE,
    )
    ref_primary = _ref(
        "prim-1",
        domain_slug="project",
        blocking=False,
        authority=DomainConflictAuthority.PRIMARY_DOMAIN,
    )

    case = DomainConflictCase(
        id="case-adv-mand-prim",
        domains=(DomainId(slug="compliance"), DomainId(slug="project")),
        kind=DomainConflictKind.MANDATORY_RULE,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_mandatory, ref_primary),
        blocking=True,
    )

    res = resolver.resolve(case, primary_domain=DomainId(slug="project"))
    assert "prim-1" not in res.winning_reference_ids
    assert res.can_proceed is False
    assert DomainConflictReasonCode.MANDATORY_RULE_PRECEDENCE in res.reason_codes


def test_adversarial_separate_results_forbidden_for_safety_or_permission() -> None:
    resolver = DomainConflictResolver()
    ref_perm = _ref(
        "perm-1", blocking=True, authority=DomainConflictAuthority.PERMISSION
    )
    case = DomainConflictCase(
        id="case-adv-sep-perm",
        domains=(),
        kind=DomainConflictKind.PERMISSION,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_perm,),
        blocking=True,
    )
    policy = DomainConflictResolutionPolicy(
        permission_strategy=DomainConflictStrategy.MOST_RESTRICTIVE,
        allow_separate_results=True,
    )
    res = resolver.resolve(case, policy=policy)
    assert res.strategy is not DomainConflictStrategy.SEPARATE_RESULTS
    assert res.can_proceed is False


def test_adversarial_ask_user_forbidden_for_safety_or_permission() -> None:
    resolver = DomainConflictResolver()
    ref_safety = _ref(
        "safety-1", blocking=True, authority=DomainConflictAuthority.GLOBAL_SAFETY
    )
    case = DomainConflictCase(
        id="case-adv-ask-safety",
        domains=(),
        kind=DomainConflictKind.SAFETY,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_safety,),
        blocking=True,
    )
    res = resolver.resolve(case)
    assert res.strategy is not DomainConflictStrategy.ASK_USER
    assert res.requires_user_input is False
    assert res.can_proceed is False
