"""Phase 10.6 — Snapshot integration tests with DomainRegistrySnapshot."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.registry_contracts import DomainRegistryRecord, DomainRegistrySnapshot
from cmm.domains.resolution_builder import DomainResolutionContextBuilder

_SAMPLE_DT = datetime(2024, 1, 15, tzinfo=timezone.utc)


def _domain(slug: str) -> DomainId:
    return DomainId.from_str(f"domain:{slug}")


def _make_record(
    slug: str, status: DomainStatus, version: str = "1.0.0"
) -> DomainRegistryRecord:
    did = _domain(slug)
    defn = DomainDefinition(
        id=did,
        name=slug,
        display_name=slug,
        version=version,
        kind=DomainKind.CORE,
        description="test",
        manifest_id=DomainManifestId(slug=slug, version=version),
    )
    return DomainRegistryRecord(
        definition=defn, status=status, registered_at=_SAMPLE_DT, updated_at=_SAMPLE_DT
    )


def _snapshot(*records: DomainRegistryRecord) -> DomainRegistrySnapshot:
    return DomainRegistrySnapshot(captured_at=_SAMPLE_DT, records=list(records))


class TestSnapshotIntegration:
    def test_snapshot_none_creates_empty_context(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-test",
        )
        ctx = builder.build(user_input="hello", registry_snapshot=None)
        assert ctx.available_domains == ()
        assert ctx.active_domains == ()
        assert ctx.authorized_domains == ()

    def test_snapshot_empty_creates_empty_context(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-test",
        )
        snapshot = _snapshot()
        ctx = builder.build(user_input="hello", registry_snapshot=snapshot)
        assert ctx.available_domains == ()
        assert ctx.active_domains == ()

    def test_mixed_statuses_correct_available(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-test",
        )
        records = [
            _make_record("core-bot", DomainStatus.ACTIVE),
            _make_record("degraded-agent", DomainStatus.DEGRADED),
            _make_record("disabled-tool", DomainStatus.DISABLED),
            _make_record("invalid-domain", DomainStatus.INVALID),
            _make_record("failed-domain", DomainStatus.FAILED),
            _make_record("incompatible-lib", DomainStatus.INCOMPATIBLE),
            _make_record("unloaded-mod", DomainStatus.UNLOADED),
        ]
        snapshot = _snapshot(*records)
        ctx = builder.build(user_input="hello", registry_snapshot=snapshot)
        available_slugs = {d.slug for d in ctx.available_domains}
        assert available_slugs == {"core-bot", "degraded-agent", "disabled-tool"}

    def test_active_domains_only_active_status(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-test",
        )
        records = [
            _make_record("core-bot", DomainStatus.ACTIVE),
            _make_record("core-bot-legacy", DomainStatus.DEGRADED, version="0.5.0"),
            _make_record("disabled-tool", DomainStatus.DISABLED),
        ]
        snapshot = _snapshot(*records)
        ctx = builder.build(user_input="hello", registry_snapshot=snapshot)
        active_slugs = {d.slug for d in ctx.active_domains}
        assert active_slugs == {"core-bot"}
        assert "disabled-tool" in {d.slug for d in ctx.available_domains}
        assert "disabled-tool" not in active_slugs

    def test_version_evidence_in_metadata(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-test",
        )
        records = [
            _make_record("core-bot", DomainStatus.ACTIVE, version="1.0.0"),
            _make_record("core-bot", DomainStatus.DEGRADED, version="0.9.0"),
        ]
        snapshot = _snapshot(*records)
        ctx = builder.build(user_input="hello", registry_snapshot=snapshot)
        versions_meta = ctx.metadata.get("_resolution_registry_versions", {})
        assert "core-bot" in versions_meta
        assert len(versions_meta["core-bot"]) == 2

    def test_no_semver_selection_by_builder(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-test",
        )
        r_v1 = _make_record("a", DomainStatus.ACTIVE, version="1.0.0")
        r_v2 = _make_record("a", DomainStatus.DEGRADED, version="2.0.0")
        snapshot = _snapshot(r_v1, r_v2)
        ctx = builder.build(user_input="hello", registry_snapshot=snapshot)
        available = ctx.available_domains
        assert len(available) == 1
        assert available[0].slug == "a"

    def test_builder_never_consults_live_registry(self) -> None:
        import inspect

        import cmm.domains.resolution_builder as mod

        source = inspect.getsource(mod.DomainResolutionContextBuilder.build)
        assert "live" not in source.lower()
