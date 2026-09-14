"""Detector contract and isolated detection pass for hybrid discovery.

Detector contract: a detector may read discovery metadata, check credential
*presence* (never secret values), call non-inference administrative
endpoints such as ``/models``, and check login/auth status. It must not
generate model output, spend quota or credit, write external configuration,
or place secret values in candidates or logs. A provider needing inference
to verify compatibility stays ``UNVERIFIED_COMPATIBILITY`` until a
user-authorized canary occurs.

Isolation: :func:`detect_all` catches each detector's exceptions into a
structured :class:`DetectorFailure` channel (via the ``on_error`` hook)
without aborting the pass, so one broken source never hides unrelated
providers. Output is sorted by ``provider_id`` for deterministic results.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from kernel.llm.provider_candidates import ProviderCandidate


@dataclass(frozen=True, slots=True)
class DetectorFailure:
    """Structured record of one detector's failure during a pass."""

    detector_name: str
    error: Exception


@runtime_checkable
class ProviderDetector(Protocol):
    """Passive discovery source for one provider; presence checks only."""

    def detect(self) -> ProviderCandidate:
        """Return this detector's candidate, or raise on source failure."""
        ...


def detect_all(
    detectors: Iterable[ProviderDetector],
    *,
    on_error: Callable[[DetectorFailure], object] | None = None,
) -> tuple[ProviderCandidate, ...]:
    """Run every detector; isolate failures, keep detections, sort output."""
    found: list[ProviderCandidate] = []
    for detector in detectors:
        try:
            candidate = detector.detect()
        except Exception as exc:  # noqa: BLE001 — isolation is the contract
            if on_error is not None:
                on_error(
                    DetectorFailure(detector_name=type(detector).__name__, error=exc)
                )
            continue
        if not isinstance(candidate, ProviderCandidate):
            if on_error is not None:
                on_error(
                    DetectorFailure(
                        detector_name=type(detector).__name__,
                        error=TypeError(
                            "detector must return ProviderCandidate, "
                            f"got {type(candidate).__name__}"
                        ),
                    )
                )
            continue
        if candidate.detected:
            found.append(candidate)
    found.sort(key=lambda item: item.provider_id)
    return tuple(found)
