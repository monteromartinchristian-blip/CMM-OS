"""Contract tests for the provider detector isolation contract.

One failing detector must never break unrelated providers: ``detect_all``
catches per-detector exceptions into a structured failure channel and keeps
going, returning surviving candidates in deterministic order.
"""

import inspect

import pytest

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


def test_detect_all_throwing_hook_does_not_abort_pass() -> None:
    def _throwing_hook(_failure: DetectorFailure) -> None:
        raise RuntimeError("hook blew up")

    candidates = detect_all(
        [_RaisingDetector(), _ValidDetector()], on_error=_throwing_hook
    )

    assert [c.provider_id for c in candidates] == ["deepseek"]


def test_detector_failure_preserves_error_verbatim() -> None:
    failures: list[DetectorFailure] = []

    candidates = detect_all(
        [_RaisingDetector(), _ValidDetector()], on_error=failures.append
    )

    assert [c.provider_id for c in candidates] == ["deepseek"]
    assert len(failures) == 1
    assert type(failures[0].error) is RuntimeError
    assert str(failures[0].error) == "broken source"


# ---- Plan 3 Task 4: detectors for approved provider classes ----
# Imports for the new detectors are deferred into each test so this
# RED stage keeps every Task 1 test above green while the new tests
# fail with ImportError until the detectors are implemented.

_APPROVED_ENV_PROVIDERS: tuple[tuple[str, str], ...] = (
    ("commandcode", "COMMANDCODE_API_KEY"),
    ("qwen-cloud", "QWEN_CLOUD_API_KEY"),
    ("deepseek", "DEEPSEEK_API_KEY"),
    ("kira", "KIRA_API_KEY"),
    ("openrouter", "OPENROUTER_API_KEY"),
    ("opencode-zen", "OPENCODE_ZEN_API_KEY"),
    ("nvidia-nim", "NVIDIA_NIM_API_KEY"),
)

_NONCANONICAL_CODEX_CONFIG = (
    'model = "gpt-5"\nopenai_base_url = "http://127.0.0.1:17841/v1"\n'
)


def test_codex_detector_flags_external_endpoint_override(tmp_path) -> None:
    from kernel.llm.provider_detectors import CodexDetector

    (tmp_path / "auth.json").write_text('{"access_token": "x"}\n')
    (tmp_path / "config.toml").write_text(_NONCANONICAL_CODEX_CONFIG)

    candidate = CodexDetector(codex_home=tmp_path).detect()

    assert candidate.provider_id == "codex"
    assert candidate.detected is True
    assert candidate.auth_available is True
    assert candidate.external_config_present is True
    assert candidate.external_endpoint_override_present is True
    assert CandidateRisk.EXTERNAL_ENDPOINT_OVERRIDE in candidate.risks
    for _key, value in candidate.metadata:
        assert "127.0.0.1" not in value
        assert "17841" not in value


def test_codex_detector_without_config_has_no_override_risk(tmp_path) -> None:
    from kernel.llm.provider_detectors import CodexDetector

    (tmp_path / "auth.json").write_text('{"access_token": "x"}\n')

    candidate = CodexDetector(codex_home=tmp_path).detect()

    assert candidate.detected is True
    assert candidate.auth_available is True
    assert candidate.external_config_present is False
    assert candidate.external_endpoint_override_present is False
    assert CandidateRisk.EXTERNAL_ENDPOINT_OVERRIDE not in candidate.risks


def test_codex_detector_default_construction_reads_no_real_home() -> None:
    from kernel.llm.provider_detectors import CodexDetector

    candidate = CodexDetector().detect()

    assert candidate.detected is False
    assert candidate.auth_available is False


@pytest.mark.parametrize(("provider_id", "env_key"), _APPROVED_ENV_PROVIDERS)
def test_env_detector_present_key_reports_auth_without_secret(
    provider_id: str, env_key: str
) -> None:
    from kernel.llm.provider_detectors import EnvironmentApiCredentialDetector

    secret = f"test-secret-for-{provider_id}"
    detector = EnvironmentApiCredentialDetector(
        provider_id=provider_id, env_keys=(env_key,), env={env_key: secret}
    )
    candidate = detector.detect()

    assert candidate.provider_id == provider_id
    assert candidate.detected is True
    assert candidate.auth_available is True
    assert secret not in str(candidate)
    for key, value in candidate.metadata:
        assert secret not in key
        assert secret not in value


@pytest.mark.parametrize(("provider_id", "env_key"), _APPROVED_ENV_PROVIDERS)
def test_env_detector_absent_key_reports_no_auth(
    provider_id: str, env_key: str
) -> None:
    from kernel.llm.provider_detectors import EnvironmentApiCredentialDetector

    detector = EnvironmentApiCredentialDetector(
        provider_id=provider_id, env_keys=(env_key,), env={}
    )
    candidate = detector.detect()

    assert candidate.auth_available is False


def test_default_environment_detectors_cover_approved_providers() -> None:
    from kernel.llm.provider_detectors import default_environment_detectors

    detectors = default_environment_detectors(env={})

    assert {d.provider_id for d in detectors} == {
        provider_id for provider_id, _ in _APPROVED_ENV_PROVIDERS
    }


def test_claude_code_detector_detects_injected_home(tmp_path) -> None:
    from kernel.llm.provider_detectors import ClaudeCodeDetector

    (tmp_path / ".claude.json").write_text("{}\n")

    candidate = ClaudeCodeDetector(claude_home=tmp_path).detect()

    assert candidate.provider_id == "claude-code"
    assert candidate.detected is True
    assert candidate.auth_available is True


def test_claude_code_detector_default_construction_detects_nothing() -> None:
    from kernel.llm.provider_detectors import ClaudeCodeDetector

    assert ClaudeCodeDetector().detect().detected is False


def test_antigravity_detector_detects_injected_home(tmp_path) -> None:
    from kernel.llm.provider_detectors import AntigravityDetector

    (tmp_path / "credentials.json").write_text("{}\n")

    candidate = AntigravityDetector(config_dir=tmp_path).detect()

    assert candidate.provider_id == "antigravity"
    assert candidate.detected is True
    assert candidate.auth_available is True


def test_antigravity_detector_default_construction_detects_nothing() -> None:
    from kernel.llm.provider_detectors import AntigravityDetector

    assert AntigravityDetector().detect().detected is False


def test_qwen_token_plan_detector_env_presence_without_secret() -> None:
    from kernel.llm.provider_detectors import QwenTokenPlanDetector

    secret = "test-qwen-token-plan-secret"
    candidate = QwenTokenPlanDetector(env={"QWEN_TOKEN_PLAN_API_KEY": secret}).detect()

    assert candidate.provider_id == "qwen-token-plan"
    assert candidate.detected is True
    assert candidate.auth_available is True
    assert secret not in str(candidate)


def test_qwen_token_plan_detector_token_file_presence(tmp_path) -> None:
    from kernel.llm.provider_detectors import QwenTokenPlanDetector

    token_file = tmp_path / "qwen-token.json"
    token_file.write_text('{"token": "x"}\n')

    candidate = QwenTokenPlanDetector(token_file=token_file, env={}).detect()

    assert candidate.detected is True
    assert candidate.auth_available is True


def test_qwen_token_plan_detector_absent_everywhere_reports_no_auth() -> None:
    from kernel.llm.provider_detectors import QwenTokenPlanDetector

    candidate = QwenTokenPlanDetector(env={}).detect()

    assert candidate.detected is False
    assert candidate.auth_available is False


def test_new_detectors_failure_isolation(tmp_path) -> None:
    from kernel.llm.provider_detectors import (
        CodexDetector,
        EnvironmentApiCredentialDetector,
    )

    (tmp_path / "auth.json").write_text('{"access_token": "x"}\n')
    failures: list[DetectorFailure] = []
    detectors = [
        _RaisingDetector(),
        CodexDetector(codex_home=tmp_path),
        EnvironmentApiCredentialDetector(
            provider_id="deepseek",
            env_keys=("DEEPSEEK_API_KEY",),
            env={"DEEPSEEK_API_KEY": "s3cret"},
        ),
    ]

    candidates = detect_all(detectors, on_error=failures.append)

    assert [c.provider_id for c in candidates] == ["codex", "deepseek"]
    assert len(failures) == 1
