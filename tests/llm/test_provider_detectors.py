"""Contract tests for the provider detector isolation contract.

One failing detector must never break unrelated providers: ``detect_all``
catches per-detector exceptions into a structured failure channel and keeps
going, returning surviving candidates in deterministic order.
"""

import inspect

from kernel.llm.provider_candidates import CandidateRisk, ProviderCandidate
from kernel.llm.provider_detectors import (
    DetectorFailure,
    ProviderDetector,
    detect_all,
)


def _candidate(provider_id: str = "deepseek") -> ProviderCandidate:
    return ProviderCandidate(
        provider_id=provider_id,
        source="env",
        detected=True,
        auth_available=True,
        external_config_present=False,
        external_endpoint_override_present=False,
        risks=(),
    )


class _ValidDetector:
    """Minimal detector stub returning a fixed candidate."""

    def __init__(self, provider_id: str = "deepseek") -> None:
        self._provider_id = provider_id

    def detect(self) -> ProviderCandidate:
        return _candidate(self._provider_id)


class _RaisingDetector:
    """Detector stub simulating a broken provider source."""

    def detect(self) -> ProviderCandidate:
        raise RuntimeError("broken source")


def test_detector_protocol_requires_single_detect_method() -> None:
    methods = {
        name
        for name, _ in inspect.getmembers(
            ProviderDetector, predicate=inspect.isfunction
        )
    }

    public = {name for name in methods if not name.startswith("_")}

    assert public == {"detect"}
    assert hasattr(_ValidDetector(), "detect")
    assert not isinstance(object(), ProviderDetector)


def test_detect_all_isolates_failing_detector() -> None:
    failures: list[DetectorFailure] = []

    candidates = detect_all(
        [_RaisingDetector(), _ValidDetector()], on_error=failures.append
    )

    assert [c.provider_id for c in candidates] == ["deepseek"]
    assert len(failures) == 1
    assert isinstance(failures[0].error, RuntimeError)
    assert "broken source" in str(failures[0].error)


def test_detect_all_without_hook_still_does_not_raise() -> None:
    candidates = detect_all([_RaisingDetector(), _ValidDetector()])

    assert [c.provider_id for c in candidates] == ["deepseek"]


def test_detect_all_empty_input_returns_empty() -> None:
    assert detect_all([]) == ()


def test_detect_all_orders_candidates_deterministically() -> None:
    candidates = detect_all([_ValidDetector("openrouter"), _ValidDetector("deepseek")])

    assert [c.provider_id for c in candidates] == ["deepseek", "openrouter"]


def test_detect_all_skips_undetected_candidates() -> None:
    class _Undetected:
        def detect(self) -> ProviderCandidate:
            return ProviderCandidate(
                provider_id="kira",
                source="config",
                detected=False,
                auth_available=False,
                external_config_present=True,
                external_endpoint_override_present=True,
                risks=(CandidateRisk.EXTERNAL_ENDPOINT_OVERRIDE,),
            )

    candidates = detect_all([_Undetected(), _ValidDetector()])

    assert [c.provider_id for c in candidates] == ["deepseek"]
