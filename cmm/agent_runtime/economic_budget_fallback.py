"""Bridge economic decisions into the existing Phase 9.30 fallback context."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .economic_budget_contracts import EconomicBudgetDecision


def economic_budget_snapshot(decision: EconomicBudgetDecision) -> Mapping[str, Any]:
    """Return the structured mapping consumed by ``ModelFallbackContext.budget``."""
    return decision.to_snapshot()
