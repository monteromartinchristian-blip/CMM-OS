"""Phase 10.6 — Tests for resolution input limits."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.errors import (
    DomainResolutionContractError,
)
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
)

_SAMPLE_DT = datetime(2024, 1, 15, tzinfo=timezone.utc)


class TestLimits:
    def test_user_input_too_long_via_builder(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-1",
            max_input_chars=10,
        )
        with pytest.raises(Exception, match="exceeds"):
            builder.build(user_input="x" * 11)

    def test_user_input_max_boundary_ok(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-1",
            max_input_chars=10,
        )
        ctx = builder.build(user_input="x" * 10)
        assert len(ctx.user_input) == 10

    def test_objective_too_long_via_builder(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-1",
            max_objective_chars=5,
        )
        with pytest.raises(Exception, match="exceeds"):
            builder.build(user_input="hi", objective="x" * 6)

    def test_user_input_absurdly_large_rejected_directly(self) -> None:
        """Direct construction with overly large text should be rejected."""
        huge = "x" * 200_001
        with pytest.raises(Exception, match="exceeds"):
            DomainResolutionContext(id="ctx", user_input=huge, created_at=_SAMPLE_DT)

    def test_empty_string_becomes_none_optional_fields(self) -> None:
        ctx = DomainResolutionContext(
            id="ctx",
            user_input="hi",
            objective="   ",
            created_at=_SAMPLE_DT,
        )
        assert ctx.objective is None

    def test_non_string_input_builder_rejected(self) -> None:
        builder = DomainResolutionContextBuilder(
            clock=lambda: _SAMPLE_DT,
            id_factory=lambda: "ctx-1",
        )
        with pytest.raises(DomainResolutionContractError, match="string"):
            builder.build(user_input=123)  # type: ignore[arg-type]
