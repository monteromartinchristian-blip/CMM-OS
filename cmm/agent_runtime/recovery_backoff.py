"""Phase 9.16 – Recovery Backoff Calculator.

Calculates deterministic retry delay intervals based on backoff strategy, attempt count,
caps, and optional random jitter sources without performing actual sleep calls.
"""

from __future__ import annotations

import random
from collections.abc import Callable

from cmm.agent_runtime.enums import BackoffStrategy
from cmm.agent_runtime.errors import RecoveryBackoffError
from cmm.agent_runtime.recovery_contracts import RetryPolicy


class RecoveryBackoffCalculator:
    """Calculates retry backoff delay values deterministically."""

    def __init__(
        self,
        random_source: Callable[[], float] | None = None,
    ) -> None:
        """Initialize calculator with optional custom random source function returning float in [0, 1)."""
        self._random_source = random_source or random.random

    def calculate_delay(
        self,
        policy: RetryPolicy,
        attempt_index: int,
    ) -> float:
        """Calculate the backoff delay in seconds for a given attempt index and policy."""
        if attempt_index < 1:
            raise RecoveryBackoffError(
                f"attempt_index must be >= 1, got {attempt_index}."
            )

        strategy = policy.backoff_strategy
        initial = policy.initial_delay_seconds
        maximum = policy.maximum_delay_seconds

        if initial < 0 or maximum < 0:
            raise RecoveryBackoffError(
                "Initial and maximum delay values cannot be negative."
            )
        if maximum < initial:
            raise RecoveryBackoffError(
                "Maximum delay cannot be smaller than initial delay."
            )

        if strategy == BackoffStrategy.NONE:
            return 0.0

        if strategy == BackoffStrategy.CONSTANT:
            delay = initial
        elif strategy == BackoffStrategy.LINEAR:
            delay = initial * attempt_index
        elif strategy == BackoffStrategy.EXPONENTIAL:
            delay = initial * (2.0 ** (attempt_index - 1))
        else:
            delay = initial

        if policy.jitter and delay > 0:
            # Apply deterministic jitter factor using self._random_source()
            jitter_factor = 0.5 + 0.5 * self._random_source()  # [0.5, 1.0)
            delay = delay * jitter_factor

        # Cap at maximum_delay_seconds
        capped_delay = min(delay, maximum)
        return max(0.0, round(capped_delay, 4))
