"""Detector contract, isolated detection pass, and approved detectors.

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

Approved detectors (Plan 3 Task 4): :class:`CodexDetector`,
:class:`ClaudeCodeDetector`, :class:`AntigravityDetector`,
:class:`QwenTokenPlanDetector`, and :class:`EnvironmentApiCredentialDetector`
(one class configured per API provider via
:func:`default_environment_detectors`). Every filesystem/environment input
is injectable: a detector constructed without inputs reports "not detected"
without touching the real ``~/.codex`` home, the real ``~/.claude`` home,
or ``os.environ`` — this module never reads any of those implicitly.
Credential checks are presence-only (a key/file exists and is non-blank);
candidate metadata carries evidence *names* (paths, key names), never
secret or URL values.

Error taxonomy: constructors raise :class:`TypeError` for wrongly typed
inputs and :class:`ValueError` for blank/empty configuration; detection
itself never raises for missing evidence — it reports ``detected=False``.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from kernel.llm.provider_candidates import CandidateRisk, ProviderCandidate


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


def _coerce_optional_dir(
    value: str | os.PathLike[str] | None, *, label: str
) -> Path | None:
    """Coerce an injectable directory input; ``None`` means "no input"."""
    if value is None:
        return None
    if isinstance(value, (str, os.PathLike)):
        text = os.fspath(value).strip()
    else:
        raise TypeError(f"{label} must be a path")
    if not text:
        raise ValueError(f"{label} cannot be empty")
    return Path(text)


def _coerce_optional_file(
    value: str | os.PathLike[str] | None, *, label: str
) -> Path | None:
    """Coerce an injectable file input; ``None`` means "no input"."""
    return _coerce_optional_dir(value, label=label)


def _snapshot_env(env: Mapping[str, str] | None) -> dict[str, str]:
    """Copy an injectable env mapping; ``None`` means "no credentials"."""
    if env is None:
        return {}
    if not isinstance(env, Mapping):
        raise TypeError("env must be a mapping")
    return dict(env)


def _present_key(env: Mapping[str, str], keys: Iterable[str]) -> str | None:
    """Return the first key with a non-blank value; presence only."""
    for key in keys:
        value = env.get(key)
        if isinstance(value, str) and value.strip():
            return key
    return None


def _config_marks_endpoint_override(text: str) -> bool:
    """Check config text for an endpoint-override URL; never returns it."""
    lowered = text.lower()
    return "http://" in lowered or "https://" in lowered


def _validate_provider_id(provider_id: str) -> str:
    """Reject blank or non-string provider ids at the detector boundary."""
    if not isinstance(provider_id, str):
        raise TypeError("provider_id must be a string")
    if not provider_id.strip():
        raise ValueError("provider_id cannot be empty")
    return provider_id


def _validate_env_keys(env_keys: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Reject empty or blank environment key declarations."""
    if isinstance(env_keys, str) or not isinstance(env_keys, (tuple, list)):
        raise TypeError("env_keys must be a tuple of strings")
    keys = tuple(env_keys)
    if not keys:
        raise ValueError("env_keys cannot be empty")
    for key in keys:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("env_keys cannot contain empty keys")
    return keys


class CodexDetector:
    """Detect a Codex subscription home from an injectable root path."""

    provider_id = "codex"

    def __init__(self, codex_home: str | os.PathLike[str] | None = None) -> None:
        """Bind an injectable Codex home; ``None`` detects nothing."""
        self._home = _coerce_optional_dir(codex_home, label="Codex home")

    def detect(self) -> ProviderCandidate:
        """Report Codex evidence; flag external endpoint overrides."""
        if self._home is None or not self._home.is_dir():
            return self._undetected()
        auth_available = (self._home / "auth.json").is_file()
        config_path = self._home / "config.toml"
        config_present = config_path.is_file()
        override_present = config_present and self._has_override(config_path)
        risks: tuple[CandidateRisk, ...] = ()
        if config_present:
            risks = (CandidateRisk.UNTRUSTED_EXTERNAL_CONFIG,)
        if override_present:
            risks = (
                CandidateRisk.EXTERNAL_ENDPOINT_OVERRIDE,
                CandidateRisk.UNTRUSTED_EXTERNAL_CONFIG,
            )
        return ProviderCandidate(
            provider_id=self.provider_id,
            source="codex-home",
            detected=auth_available or config_present,
            auth_available=auth_available,
            external_config_present=config_present,
            external_endpoint_override_present=override_present,
            risks=risks,
            metadata=(("codex_home", str(self._home)),)
            if (auth_available or config_present)
            else (),
        )

    def _undetected(self) -> ProviderCandidate:
        """Report no evidence without touching any real home."""
        return ProviderCandidate(
            provider_id=self.provider_id,
            source="codex-home",
            detected=False,
            auth_available=False,
            external_config_present=False,
            external_endpoint_override_present=False,
            risks=(),
        )

    @staticmethod
    def _has_override(config_path: Path) -> bool:
        """Check for an override URL without returning its value."""
        try:
            text = config_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        return _config_marks_endpoint_override(text)


class ClaudeCodeDetector:
    """Detect a Claude Code subscription home from an injectable path."""

    provider_id = "claude-code"
    _AUTH_MARKERS: tuple[str, ...] = (".claude.json", "credentials.json")
    _CONFIG_MARKERS: tuple[str, ...] = ("config.json", "settings.json")

    def __init__(self, claude_home: str | os.PathLike[str] | None = None) -> None:
        """Bind an injectable Claude home; ``None`` detects nothing."""
        self._home = _coerce_optional_dir(claude_home, label="Claude home")

    def detect(self) -> ProviderCandidate:
        """Report Claude evidence; presence-only, no secret values."""
        if self._home is None or not self._home.is_dir():
            return self._undetected()
        auth_available = any(
            (self._home / marker).is_file() for marker in self._AUTH_MARKERS
        )
        config_present = any(
            (self._home / marker).is_file() for marker in self._CONFIG_MARKERS
        )
        detected = auth_available or config_present
        return ProviderCandidate(
            provider_id=self.provider_id,
            source="claude-home",
            detected=detected,
            auth_available=auth_available,
            external_config_present=config_present,
            external_endpoint_override_present=False,
            risks=(CandidateRisk.UNTRUSTED_EXTERNAL_CONFIG,) if config_present else (),
            metadata=(("claude_home", str(self._home)),) if detected else (),
        )

    def _undetected(self) -> ProviderCandidate:
        """Report no evidence without touching any real home."""
        return ProviderCandidate(
            provider_id=self.provider_id,
            source="claude-home",
            detected=False,
            auth_available=False,
            external_config_present=False,
            external_endpoint_override_present=False,
            risks=(),
        )


class AntigravityDetector:
    """Detect an Antigravity subscription home from an injectable path."""

    provider_id = "antigravity"
    _AUTH_MARKERS: tuple[str, ...] = (
        "credentials.json",
        "oauth.json",
        "antigravity.json",
    )
    _CONFIG_MARKERS: tuple[str, ...] = ("config.json", "settings.json")

    def __init__(self, config_dir: str | os.PathLike[str] | None = None) -> None:
        """Bind an injectable config dir; ``None`` detects nothing."""
        self._config_dir = _coerce_optional_dir(
            config_dir, label="Antigravity config dir"
        )

    def detect(self) -> ProviderCandidate:
        """Report Antigravity evidence; presence-only, no secret values."""
        if self._config_dir is None or not self._config_dir.is_dir():
            return self._undetected()
        auth_available = any(
            (self._config_dir / marker).is_file() for marker in self._AUTH_MARKERS
        )
        config_present = any(
            (self._config_dir / marker).is_file() for marker in self._CONFIG_MARKERS
        )
        detected = auth_available or config_present
        return ProviderCandidate(
            provider_id=self.provider_id,
            source="antigravity-home",
            detected=detected,
            auth_available=auth_available,
            external_config_present=config_present,
            external_endpoint_override_present=False,
            risks=(CandidateRisk.UNTRUSTED_EXTERNAL_CONFIG,) if config_present else (),
            metadata=(("antigravity_home", str(self._config_dir)),) if detected else (),
        )

    def _undetected(self) -> ProviderCandidate:
        """Report no evidence without touching any real home."""
        return ProviderCandidate(
            provider_id=self.provider_id,
            source="antigravity-home",
            detected=False,
            auth_available=False,
            external_config_present=False,
            external_endpoint_override_present=False,
            risks=(),
        )


class QwenTokenPlanDetector:
    """Detect Qwen Token Plan evidence via token file or env presence."""

    provider_id = "qwen-token-plan"
    env_keys: tuple[str, ...] = ("QWEN_TOKEN_PLAN_API_KEY",)

    def __init__(
        self,
        token_file: str | os.PathLike[str] | None = None,
        *,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Bind an injectable token file and env mapping (presence only)."""
        self._token_file = _coerce_optional_file(token_file, label="Token file")
        self._env = _snapshot_env(env)

    def detect(self) -> ProviderCandidate:
        """Report token-plan evidence without exposing any secret value."""
        file_present = self._token_file is not None and self._token_file.is_file()
        matched_key = _present_key(self._env, self.env_keys)
        auth_available = file_present or matched_key is not None
        metadata: tuple[tuple[str, str], ...] = ()
        if file_present:
            metadata = (("evidence", "token-file"),)
        elif matched_key is not None:
            metadata = (("env_key", matched_key),)
        return ProviderCandidate(
            provider_id=self.provider_id,
            source="token-file" if file_present else "env",
            detected=auth_available,
            auth_available=auth_available,
            external_config_present=False,
            external_endpoint_override_present=False,
            risks=(),
            metadata=metadata,
        )


class EnvironmentApiCredentialDetector:
    """Detect one API provider via environment-key presence (never values)."""

    def __init__(
        self,
        provider_id: str,
        env_keys: tuple[str, ...] | list[str],
        *,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Bind a provider id, its key names, and a fake env mapping."""
        self._provider_id = _validate_provider_id(provider_id)
        self._env_keys = _validate_env_keys(env_keys)
        self._env = _snapshot_env(env)

    @property
    def provider_id(self) -> str:
        """Return the provider this detector reports evidence for."""
        return self._provider_id

    def detect(self) -> ProviderCandidate:
        """Report credential presence; metadata names the key, not its value."""
        matched_key = _present_key(self._env, self._env_keys)
        auth_available = matched_key is not None
        return ProviderCandidate(
            provider_id=self._provider_id,
            source="env",
            detected=auth_available,
            auth_available=auth_available,
            external_config_present=False,
            external_endpoint_override_present=False,
            risks=(),
            metadata=(("env_key", matched_key),) if matched_key else (),
        )


APPROVED_ENV_CREDENTIALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("commandcode", ("COMMANDCODE_API_KEY",)),
    ("qwen-cloud", ("QWEN_CLOUD_API_KEY", "DASHSCOPE_API_KEY")),
    ("deepseek", ("DEEPSEEK_API_KEY",)),
    ("kira", ("KIRA_API_KEY",)),
    ("openrouter", ("OPENROUTER_API_KEY",)),
    ("opencode-zen", ("OPENCODE_ZEN_API_KEY",)),
    ("nvidia-nim", ("NVIDIA_NIM_API_KEY", "NIM_API_KEY")),
)
"""Approved API providers and the env key names proving credential presence."""


def default_environment_detectors(
    env: Mapping[str, str] | None = None,
) -> tuple[EnvironmentApiCredentialDetector, ...]:
    """Build one env detector per approved API provider sharing one mapping."""
    snapshot = _snapshot_env(env)
    return tuple(
        EnvironmentApiCredentialDetector(
            provider_id=provider_id, env_keys=keys, env=snapshot
        )
        for provider_id, keys in APPROVED_ENV_CREDENTIALS
    )


def default_approved_detectors(
    *,
    codex_home: str | os.PathLike[str] | None = None,
    claude_home: str | os.PathLike[str] | None = None,
    antigravity_config_dir: str | os.PathLike[str] | None = None,
    qwen_token_file: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[ProviderDetector, ...]:
    """Build every approved detector from fully injectable inputs."""
    snapshot = _snapshot_env(env)
    return (
        CodexDetector(codex_home=codex_home),
        ClaudeCodeDetector(claude_home=claude_home),
        AntigravityDetector(config_dir=antigravity_config_dir),
        QwenTokenPlanDetector(token_file=qwen_token_file, env=snapshot),
        *default_environment_detectors(env=snapshot),
    )
