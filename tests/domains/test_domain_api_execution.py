"""Phase 10.36 — Domain API execution tests.

Covers canonical resolution delegation, authoritative operation orchestration,
and workflow registry/executor routing.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.api import DefaultDomainAPI
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resolver import DefaultDomainResolver
from tests.domains.test_domain_api_contracts import _make_collaborators


def _api_with_resolver(resolver: DefaultDomainResolver) -> DefaultDomainAPI:
    collaborators = _make_collaborators()
    collaborators["resolver"] = resolver
    return DefaultDomainAPI(**collaborators)


def _context() -> DomainResolutionContext:
    return DomainResolutionContext(
        id="ctx-1",
        objective="test objective",
        available_domains=(DomainId(slug="general"),),
        authorized_domains=(DomainId(slug="general"),),
        active_domains=(DomainId(slug="general"),),
        created_at=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
    )


class TestResolveDomain:
    def test_delegates_to_canonical_resolver(self) -> None:
        resolver = DefaultDomainResolver(
            clock=lambda: datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
            id_factory=lambda: "res-fixed-1",
        )
        api = _api_with_resolver(resolver)
        context = _context()
        expected = resolver.resolve(context)
        actual = api.resolve_domain(context)
        assert actual == expected

    def test_preserves_canonical_blocked_status(self) -> None:
        # No available domains -> canonical fail-closed result must be
        # preserved unchanged through the facade.
        resolver = DefaultDomainResolver(
            clock=lambda: datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
            id_factory=lambda: "res-fixed-2",
        )
        api = _api_with_resolver(resolver)
        empty_context = DomainResolutionContext(
            id="ctx-empty",
            objective="nothing available",
            available_domains=(),
            created_at=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
        )
        expected = resolver.resolve(empty_context)
        actual = api.resolve_domain(empty_context)
        assert actual == expected
        assert actual.status == expected.status
        assert actual.confidence == expected.confidence
        assert actual.reasons == expected.reasons
        assert actual.rejected_domains == expected.rejected_domains
        assert actual.ambiguous_domains == expected.ambiguous_domains
