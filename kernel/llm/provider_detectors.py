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
providers. A throwing ``on_error`` hook is swallowed the same way — the
original detector failure is already recorded — so a broken hook cannot
abort the pass either. Output is sorted by ``provider_id`` for
deterministic results.

Failure errors: ``DetectorFailure.error`` is preserved verbatim for
debugging and must NEVER be logged verbatim — detectors must not embed
secret values in exceptions, and callers must redact before logging.
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
            _report_failure(on_error, type(detector).__name__, exc)
            continue
        if not isinstance(candidate, ProviderCandidate):
            _report_failure(
                on_error,
                type(detector).__name__,
                TypeError(
                    "detector must return ProviderCandidate, "
                    f"got {type(candidate).__name__}"
                ),
            )
            continue
        if candidate.detected:
            found.append(candidate)
    found.sort(key=lambda item: item.provider_id)
    return tuple(found)


def _report_failure(
    on_error: Callable[[DetectorFailure], object] | None,
    detector_name: str,
    error: Exception,
) -> None:
    """Deliver one failure to the hook without letting it abort the pass."""
    if on_error is None:
        return
    try:
        on_error(DetectorFailure(detector_name=detector_name, error=error))
    except Exception:  # noqa: BLE001, S110 — hook isolation is the contract
        pass
