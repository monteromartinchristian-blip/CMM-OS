"""Isolated subscription provider profiles (Plan 3 Task 3).

Subscription bridges must never inherit mutable third-party
configuration: :func:`create_codex_profile` copies ONLY ``auth.json``
(the artifact proven necessary by the current Codex authentication
contract) into a CMM-owned target home and never copies
``config.toml``, so external ``openai_base_url`` overrides stay
behind. Claude/Antigravity adapters scope traffic through
:class:`SubscriptionProfileDescriptor`, which carries an isolated
home plus an explicit list of PAYG environment names to strip.

Provider dispatch lives in one place:
:meth:`SubscriptionProfileManager.create_profile` builds the CMM-owned profile
for a provider id (Codex copies only ``auth.json``; Claude/Antigravity get a
CMM-owned home plus their PAYG strip policy). A provider this module does not
implement is reported as ``unsupported`` — never a silent success — so a
caller that requires isolation fails closed instead of connecting unisolated.

All filesystem inputs are injectable paths; this module never
touches the real ``~/.codex`` or ``~/.claude`` homes.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_AUTH_FILENAME = "auth.json"
_RESTRICTIVE_MODE = 0o600

CLAUDE_PAYG_STRIP_ENV: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
)

ANTIGRAVITY_PAYG_STRIP_ENV: tuple[str, ...] = (
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_GENAI_API_KEY",
)


# Outcome statuses a caller must handle; ``ok`` is the only success.
_OUTCOME_STATUSES: tuple[str, ...] = ("ok", "auth_required", "unsupported", "failed")

# Providers whose isolation profile is a CMM-owned home plus an env-strip
# policy (no credential copy happens for these).
_SCOPED_PROVIDER_IDS: tuple[str, ...] = ("claude", "claude-code", "antigravity")


class CodexAuthRequiredError(ValueError):
    """Source home carries no transferable Codex auth material."""


def _coerce_dir(value: str | os.PathLike[str], *, label: str) -> Path:
    """Coerce a path-like input to a ``Path``; reject blanks."""
    if isinstance(value, (str, os.PathLike)):
        text = os.fspath(value).strip()
    else:
        raise TypeError(f"{label} must be a path")
    if not text:
        raise ValueError(f"{label} cannot be empty")
    return Path(text)


def create_codex_profile(
    source_home: str | os.PathLike[str],
    target_home: str | os.PathLike[str],
) -> Path:
    """Copy only ``auth.json`` into a CMM-owned target home.

    ``config.toml`` is never copied, so external endpoint overrides
    stay behind. The copied ``auth.json`` gets mode ``0o600``.
    Raises :class:`CodexAuthRequiredError` when the source has no
    transferable auth material; nothing is copied in that case.
    """
    source = _coerce_dir(source_home, label="Source home")
    target = _coerce_dir(target_home, label="Target home")
    if target == source:
        raise ValueError("target home must differ from source home")
    if not source.is_dir():
        raise ValueError(f"source home is not a directory: {source}")
    auth = source / _AUTH_FILENAME
    if not auth.is_file():
        raise CodexAuthRequiredError(
            "auth_required: no transferable Codex auth material"
        )
    target.mkdir(parents=True, exist_ok=True)
    dest = target / _AUTH_FILENAME
    shutil.copyfile(auth, dest)
    os.chmod(dest, _RESTRICTIVE_MODE)
    return dest


@dataclass(frozen=True, slots=True)
class CodexProfileOutcome:
    """Structured result of a Codex profile build attempt."""

    status: str
    provider_id: str = "codex"
    target_home: Path | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        """Reject unknown statuses and non-normalized provider ids."""
        if self.status not in ("ok", "auth_required"):
            raise ValueError(f"unknown status: {self.status!r}")
        if not self.provider_id.strip():
            raise ValueError("provider id cannot be empty")


@dataclass(frozen=True, slots=True)
class SubscriptionProfileDescriptor:
    """Isolated home/path plus PAYG env names to strip."""

    provider_id: str
    home: Path
    env_strip: tuple[str, ...]

    def __post_init__(self) -> None:
        """Normalize ids and reject blank strip entries."""
        provider = self.provider_id.strip().lower()
        if not provider:
            raise ValueError("provider id cannot be empty")
        object.__setattr__(self, "provider_id", provider)
        stripped = tuple(name.strip() for name in self.env_strip)
        if not stripped or any(not name for name in stripped):
            raise ValueError("env_strip must list names to strip")
        object.__setattr__(self, "env_strip", stripped)

    def isolated_env(self, env: Mapping[str, str]) -> dict[str, str]:
        """Copy ``env`` minus every PAYG name in ``env_strip``."""
        return {key: value for key, value in env.items() if key not in self.env_strip}


@dataclass(frozen=True, slots=True)
class SubscriptionProfileOutcome:
    """Structured result of one CMM-owned isolation-profile build.

    ``status`` is the only success signal: ``ok`` means a CMM-owned
    ``target_home`` exists. ``auth_required``, ``unsupported`` and ``failed``
    all mean no usable isolation outcome was produced, so a caller that
    requires isolation must fail closed rather than connect.
    """

    status: str
    provider_id: str
    target_home: Path | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        """Reject unknown statuses, blank ids and an ``ok`` without a home."""
        if self.status not in _OUTCOME_STATUSES:
            raise ValueError(f"unknown status: {self.status!r}")
        provider = self.provider_id.strip().lower()
        if not provider:
            raise ValueError("provider id cannot be empty")
        object.__setattr__(self, "provider_id", provider)
        if self.status == "ok" and self.target_home is None:
            raise ValueError("an ok outcome requires a target home")


def _normalize_provider_id(provider_id: str) -> str:
    """Strip and lowercase a provider id; reject blank or non-string input."""
    if not isinstance(provider_id, str):
        raise TypeError("provider id must be a str")
    normalized = provider_id.strip().lower()
    if not normalized:
        raise ValueError("provider id cannot be empty")
    return normalized


class SubscriptionProfileManager:
    """Build CMM-owned isolated profiles for subscription providers."""

    def create_profile(
        self,
        provider_id: str,
        source_home: str | os.PathLike[str],
        target_home: str | os.PathLike[str],
    ) -> SubscriptionProfileOutcome:
        """Build the CMM-owned isolation profile for one provider.

        Provider dispatch lives here so onboarding has a single isolation path
        (MAJOR-03) instead of a per-provider branch. ``codex`` copies only
        ``auth.json``; ``claude``/``claude-code``/``antigravity`` get a
        CMM-owned home plus their PAYG env-strip policy. A provider this module
        does not implement returns ``unsupported`` — never a silent success —
        so an isolation-required caller fails closed.
        """
        provider = _normalize_provider_id(provider_id)
        if provider == "codex":
            return self._codex_outcome(source_home, target_home)
        if provider in _SCOPED_PROVIDER_IDS:
            return self._scoped_outcome(provider, source_home, target_home)
        return SubscriptionProfileOutcome(
            status="unsupported",
            provider_id=provider,
            detail=f"no CMM isolation profile is implemented for provider: {provider}",
        )

    def _codex_outcome(
        self,
        source_home: str | os.PathLike[str],
        target_home: str | os.PathLike[str],
    ) -> SubscriptionProfileOutcome:
        """Copy Codex auth only; missing or unusable evidence fails closed."""
        try:
            dest = create_codex_profile(source_home, target_home)
        except CodexAuthRequiredError as exc:
            return SubscriptionProfileOutcome(
                status="auth_required", provider_id="codex", detail=str(exc)
            )
        except (OSError, TypeError, ValueError) as exc:
            return SubscriptionProfileOutcome(
                status="failed", provider_id="codex", detail=str(exc)
            )
        # ``target_home`` is the CMM-owned isolation HOME, which is what a
        # connection references; the copied artifact (``dest``) lives inside it.
        # ``CodexProfileOutcome.target_home`` keeps its historical meaning of
        # "the copied auth artifact" for compatibility.
        return SubscriptionProfileOutcome(
            status="ok", provider_id="codex", target_home=dest.parent
        )

    def _scoped_outcome(
        self,
        provider: str,
        source_home: str | os.PathLike[str],
        target_home: str | os.PathLike[str],
    ) -> SubscriptionProfileOutcome:
        """Create the CMM-owned home for a descriptor-scoped provider."""
        try:
            source = _coerce_dir(source_home, label="Source home")
            target = _coerce_dir(target_home, label="Target home")
        except (TypeError, ValueError) as exc:
            return SubscriptionProfileOutcome(
                status="failed", provider_id=provider, detail=str(exc)
            )
        if not source.is_dir():
            return SubscriptionProfileOutcome(
                status="failed",
                provider_id=provider,
                detail=f"source home is not a directory: {source}",
            )
        if target == source:
            return SubscriptionProfileOutcome(
                status="failed",
                provider_id=provider,
                detail="target home must differ from source home",
            )
        descriptor = (
            self.claude_descriptor(target)
            if provider.startswith("claude")
            else self.antigravity_descriptor(target)
        )
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return SubscriptionProfileOutcome(
                status="failed",
                provider_id=provider,
                detail=f"isolated home could not be created: {exc}",
            )
        return SubscriptionProfileOutcome(
            status="ok",
            provider_id=provider,
            target_home=target,
            detail=(
                "cmm-owned isolated home; strips "
                f"{len(descriptor.env_strip)} payg env names"
            ),
        )

    def create_codex_profile(
        self,
        source_home: str | os.PathLike[str],
        target_home: str | os.PathLike[str],
    ) -> CodexProfileOutcome:
        """Copy Codex auth only; missing auth yields ``auth_required``."""
        try:
            dest = create_codex_profile(source_home, target_home)
        except CodexAuthRequiredError as exc:
            return CodexProfileOutcome(status="auth_required", detail=str(exc))
        return CodexProfileOutcome(status="ok", target_home=dest)

    def claude_descriptor(
        self, home: str | os.PathLike[str]
    ) -> SubscriptionProfileDescriptor:
        """Describe an isolated Claude profile scoped to ``home``."""
        return SubscriptionProfileDescriptor(
            provider_id="claude",
            home=_coerce_dir(home, label="Home"),
            env_strip=CLAUDE_PAYG_STRIP_ENV,
        )

    def antigravity_descriptor(
        self, home: str | os.PathLike[str]
    ) -> SubscriptionProfileDescriptor:
        """Describe an isolated Antigravity profile scoped to ``home``."""
        return SubscriptionProfileDescriptor(
            provider_id="antigravity",
            home=_coerce_dir(home, label="Home"),
            env_strip=ANTIGRAVITY_PAYG_STRIP_ENV,
        )
