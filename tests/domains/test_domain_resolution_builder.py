"""Phase 10.6 — Tests for DomainResolutionContextBuilder."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.errors import (
    DomainResolutionContractError,
    DomainResolutionLimitExceeded,
)
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.registry_contracts import DomainRegistryRecord, DomainRegistrySnapshot
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolution_contracts import (
    DomainResolutionHistoryItem,
    DomainResolutionSignal,
)

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
        definition=defn,
        status=status,
        registered_at=_SAMPLE_DT,
        updated_at=_SAMPLE_DT,
    )


def _snapshot(*records: DomainRegistryRecord) -> DomainRegistrySnapshot:
    return DomainRegistrySnapshot(captured_at=_SAMPLE_DT, records=list(records))


class TestBuilder:
    def test_build_with_none_snapshot(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
        )
        ctx = builder.build(user_input="hello")
        assert ctx.id == "ctx-001"
        assert ctx.user_input == "hello"
        assert ctx.available_domains == ()
        assert ctx.active_domains == ()

    def test_build_with_empty_snapshot(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
        )
        snapshot = DomainRegistrySnapshot(captured_at=_SAMPLE_DT, records=[])
        ctx = builder.build(user_input="hello", registry_snapshot=snapshot)
        assert ctx.available_domains == ()
        assert ctx.active_domains == ()

    def test_available_derived(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
        )
        r1 = _make_record("a", DomainStatus.ACTIVE)
        r2 = _make_record("b", DomainStatus.DEGRADED)
        r3 = _make_record("c", DomainStatus.DISABLED)
        snapshot = _snapshot(r1, r2, r3)
        ctx = builder.build(user_input="hello", registry_snapshot=snapshot)
        available = {d.slug for d in ctx.available_domains}
        assert available == {"a", "b", "c"}

    def test_active_derived(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
        )
        r1 = _make_record("a", DomainStatus.ACTIVE)
        r2 = _make_record("b", DomainStatus.DEGRADED)
        snapshot = _snapshot(r1, r2)
        ctx = builder.build(user_input="hello", registry_snapshot=snapshot)
        active = {d.slug for d in ctx.active_domains}
        assert active == {"a"}

    def test_disabled_available_but_not_active(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
        )
        r1 = _make_record("a", DomainStatus.DISABLED)
        snapshot = _snapshot(r1)
        ctx = builder.build(user_input="hello", registry_snapshot=snapshot)
        assert len(ctx.available_domains) == 1
        assert len(ctx.active_domains) == 0

    def test_invalid_excluded(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
        )
        r1 = _make_record("a", DomainStatus.INVALID)
        r2 = _make_record("b", DomainStatus.FAILED)
        r3 = _make_record("c", DomainStatus.INCOMPATIBLE)
        r4 = _make_record("d", DomainStatus.UNLOADED)
        snapshot = _snapshot(r1, r2, r3, r4)
        ctx = builder.build(user_input="hello", registry_snapshot=snapshot)
        assert len(ctx.available_domains) == 0

    def test_duplicate_identity_deduplicated(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
        )
        r1 = _make_record("a", DomainStatus.ACTIVE, version="1.0.0")
        r2 = _make_record("a", DomainStatus.DEGRADED, version="1.1.0")
        snapshot = _snapshot(r1, r2)
        ctx = builder.build(user_input="hello", registry_snapshot=snapshot)
        available = {d.slug for d in ctx.available_domains}
        assert available == {"a"}

    def test_two_active_versions_same_domain_rejected(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
        )
        r1 = _make_record("a", DomainStatus.ACTIVE, version="1.0.0")
        r2 = _make_record("a", DomainStatus.ACTIVE, version="1.1.0")
        snapshot = _snapshot(r1, r2)
        with pytest.raises(Exception, match="Multiple ACTIVE"):
            builder.build(user_input="hello", registry_snapshot=snapshot)

    def test_no_registry_live_access(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
        )
        ctx = builder.build(user_input="hello", registry_snapshot=None)
        assert ctx.available_domains == ()

    def test_inputs_not_mutated(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
        )
        original = "Hello World"
        ctx = builder.build(user_input=original)
        assert ctx.user_input == "Hello World"
        assert original == "Hello World"

    def test_determinism(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
        )
        ctx1 = builder.build(user_input="test")
        ctx2 = builder.build(user_input="test")
        assert ctx1 == ctx2

    def test_no_random_internal(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
        )
        ctx = builder.build(user_input="test")
        assert ctx.id == "ctx-001"

    def test_no_keyword_selection(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
        )
        ctx = builder.build(user_input="greeting bot")
        assert ctx.explicit_domains == ()

    def test_limit_exceeded_input_rejected(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
            max_input_chars=10,
        )
        with pytest.raises(Exception, match="exceeds"):
            builder.build(user_input="This is a very long input that exceeds the limit")

    def test_objective_limit_enforced(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
            max_objective_chars=5,
        )
        with pytest.raises(Exception, match="exceeds"):
            builder.build(user_input="hi", objective="Too long objective")

    # ── Updated: history over limit is REJECTED, not truncated ──────────

    def test_history_over_limit_rejected(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
            max_history_items=2,
        )
        items = tuple(
            DomainResolutionHistoryItem(
                id=f"h{i}", item_type="msg", timestamp=_SAMPLE_DT
            )
            for i in range(10)
        )
        with pytest.raises(DomainResolutionLimitExceeded, match="history"):
            builder.build(user_input="hi", recent_history=items)

    def test_signals_over_limit_rejected(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
            max_signals=3,
        )
        sigs = tuple(
            DomainResolutionSignal(kind="t", source="s", value="v") for _ in range(10)
        )
        with pytest.raises(DomainResolutionLimitExceeded, match="Signals"):
            builder.build(user_input="hi", signals=sigs)

    # ── Builder config validation ───────────────────────────────────────

    @pytest.mark.parametrize(
        "bad_value,label",
        [
            (0, "zero"),
            (-1, "negative"),
            (True, "bool_true"),
            (1.5, "float"),
            ("10", "string"),
            (None, "None"),
        ],
    )
    def test_builder_limits_must_be_positive_int(self, bad_value, label) -> None:
        with pytest.raises(DomainResolutionContractError):
            DomainResolutionContextBuilder(
                clock=lambda: _SAMPLE_DT,
                id_factory=lambda: "ctx-001",
                max_history_items=bad_value,
            )

    def test_objective_limit_reports_objective(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-001",
            max_objective_chars=5,
        )
        with pytest.raises(DomainResolutionLimitExceeded, match="objective"):
            builder.build(user_input="hi", objective="Too long objective")

    # ── ID factory tests ────────────────────────────────────────────────

    def test_default_ids_are_unique_with_fixed_clock(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
        )
        ctx1 = builder.build(user_input="a")
        ctx2 = builder.build(user_input="b")
        assert ctx1.id != ctx2.id

    def test_fixed_clock_no_collision(self) -> None:
        """Clock fixed, id_factory default: two builds produce distinct IDs."""
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            # No id_factory injected → uses uuid4 default
        )
        ctx1 = builder.build(user_input="a")
        ctx2 = builder.build(user_input="b")
        assert ctx1.id != ctx2.id

    def test_invalid_id_factory_output_rejected_empty(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "",
        )
        with pytest.raises(DomainResolutionContractError, match="non-empty"):
            builder.build(user_input="hi")

    def test_invalid_id_factory_output_rejected_non_string(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: 123,  # type: ignore[arg-type,return-value]
        )
        with pytest.raises(DomainResolutionContractError, match="string"):
            builder.build(user_input="hi")

    def test_injected_id_factory_deterministic(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "custom-001",
        )
        ctx1 = builder.build(user_input="a")
        ctx2 = builder.build(user_input="b")
        assert ctx1.id == "custom-001"
        assert ctx2.id == "custom-001"
