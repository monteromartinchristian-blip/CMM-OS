"""Tests for Phase 10.8 – Permission Composition."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from cmm.domains.composition_contracts import (
    DomainCompositionItem,
    DomainCompositionPolicy,
    PermissionComposition,
)
from cmm.domains.composition_permissions import (
    compose_permissions,
    filter_operations_by_permissions,
)
from cmm.domains.contracts import DomainDefinition, DomainManifestId
from cmm.domains.enums import DomainConflictPolicy, DomainKind
from cmm.domains.errors import DomainCompositionContractError
from cmm.domains.identifiers import DomainId


def make_definition(slug, **kwargs):
    defaults = {
        "id": DomainId.from_str(f"domain:{slug}"),
        "name": slug,
        "display_name": slug.title(),
        "version": "1.0.0",
        "kind": DomainKind.CORE,
        "description": f"Test domain {slug}",
        "manifest_id": DomainManifestId(slug=slug, version="1.0.0"),
        "enabled": True,
    }
    defaults.update(kwargs)
    return DomainDefinition(**defaults)


def test_permissions_required_accumulate():
    d1 = make_definition("a", permissions=("require:read", "require:write"))
    d2 = make_definition("b", permissions=("require:execute",))
    policy = DomainCompositionPolicy()
    perm, _, _ = compose_permissions((d1, d2), policy)
    assert set(perm.required_permissions) == {"execute", "read", "write"}


def test_permissions_granted():
    d1 = make_definition("a", permissions=("allow:access", "grant:use"))
    policy = DomainCompositionPolicy()
    perm, _, _ = compose_permissions((d1,), policy)
    assert set(perm.granted_permissions) == {"access", "use"}


def test_permissions_deny_wins_most_restrictive():
    d1 = make_definition("a", permissions=("allow:delete",))
    d2 = make_definition("b", permissions=("deny:delete",))
    policy = DomainCompositionPolicy()
    perm, _decisions, conflicts = compose_permissions((d1, d2), policy)
    assert "delete" in perm.denied_permissions
    assert "delete" not in perm.granted_permissions
    assert any(c.resolved for c in conflicts)


def test_permissions_primary_precedence():
    d1 = make_definition("primary", permissions=("allow:export",))
    d2 = make_definition("support", permissions=("deny:export",))
    policy = DomainCompositionPolicy(
        conflict_policy=DomainConflictPolicy.PRIMARY_PRECEDENCE,
    )
    perm, _decisions, conflicts = compose_permissions((d1, d2), policy)
    assert "export" in perm.granted_permissions
    assert "export" not in perm.denied_permissions
    assert any(c.resolved and "primary_precedence" == c.resolution for c in conflicts)


def test_permissions_block_on_conflict():
    d1 = make_definition("a", permissions=("allow:delete",))
    d2 = make_definition("b", permissions=("deny:delete",))
    policy = DomainCompositionPolicy(
        conflict_policy=DomainConflictPolicy.BLOCK_ON_CONFLICT,
    )
    perm, _, conflicts = compose_permissions((d1, d2), policy)
    assert any(not c.resolved and c.blocking for c in conflicts)
    assert "delete" in perm.denied_permissions


def test_permissions_opaque_no_prefix():
    d1 = make_definition("a", permissions=("some-permission",))
    policy = DomainCompositionPolicy()
    perm, _, _ = compose_permissions((d1,), policy)
    assert "some-permission" in perm.unresolved_permissions


def test_permissions_duplicate_collapse():
    d1 = make_definition("a", permissions=("require:x",))
    d2 = make_definition("b", permissions=("require:x",))
    policy = DomainCompositionPolicy()
    perm, _, _ = compose_permissions((d1, d2), policy)
    assert len(perm.required_permissions) == 1


def test_permissions_provenance():
    d1 = make_definition("a", permissions=("require:analyze",))
    d2 = make_definition("b", permissions=("allow:analyze",))
    policy = DomainCompositionPolicy()
    perm, _, _ = compose_permissions((d1, d2), policy)
    prov = dict(perm.provenance)
    assert "analyze" in prov
    assert "domain:a" in prov["analyze"]


def test_permissions_empty_prefix_rejected():
    d1 = make_definition("a", permissions=("deny:",))
    policy = DomainCompositionPolicy()
    with pytest.raises(DomainCompositionContractError):
        compose_permissions((d1,), policy)


def test_filter_operations_no_metadata_keeps_all():
    d1_id = DomainId.from_str("domain:a")
    perm = PermissionComposition()
    ops = (
        DomainCompositionItem(
            category="operations",
            identifier="op-1",
            contributing_domains=(d1_id,),
            primary_contributor=d1_id,
            precedence=0,
        ),
    )
    definitions = (make_definition("a"),)
    kept, excluded = filter_operations_by_permissions(ops, perm, definitions)
    assert len(kept) == 1
    assert len(excluded) == 0


def test_filter_operations_missing_required_excluded():
    d1_id = DomainId.from_str("domain:a")
    from cmm.domains.contracts import DomainMetadata

    d1 = make_definition(
        "a",
        metadata=DomainMetadata(
            author="test",
            license="MIT",
            metadata=MappingProxyType(
                {
                    "operation_permissions": {
                        "op-1": {"required": ["missing-perm"]},
                    }
                }
            ),
        ),
    )
    perm = PermissionComposition()
    ops = (
        DomainCompositionItem(
            category="operations",
            identifier="op-1",
            contributing_domains=(d1_id,),
            primary_contributor=d1_id,
            precedence=0,
        ),
    )
    kept, excluded = filter_operations_by_permissions(ops, perm, (d1,))
    assert len(kept) == 0
    assert len(excluded) == 1
    assert excluded[0].code == "DOMAIN_COMPOSITION_OPERATION_EXCLUDED"


def test_filter_operations_denied_active_excluded():
    d1_id = DomainId.from_str("domain:a")
    from cmm.domains.contracts import DomainMetadata

    d1 = make_definition(
        "a",
        metadata=DomainMetadata(
            author="test",
            license="MIT",
            metadata=MappingProxyType(
                {
                    "operation_permissions": {
                        "op-1": {"denied": ["blocked-perm"]},
                    }
                }
            ),
        ),
    )
    perm = PermissionComposition(denied_permissions=("blocked-perm",))
    ops = (
        DomainCompositionItem(
            category="operations",
            identifier="op-1",
            contributing_domains=(d1_id,),
            primary_contributor=d1_id,
            precedence=0,
        ),
    )
    kept, excluded = filter_operations_by_permissions(ops, perm, (d1,))
    assert len(kept) == 0
    assert len(excluded) == 1
