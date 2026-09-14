"""Ephemeral provider candidates from passive hybrid discovery.

Detection is evidence, not authority: a candidate records what a detector
observed (installed apps, config directories, credential *presence*,
localhost services) without authorizing use. Candidates are never routable —
they carry no credential reference, no connection id and no execution
methods — and their ``metadata`` carries only non-secret evidence pairs
(paths, source names), never secret values. Only explicit user acceptance
may promote a candidate into a durable ``ProviderConnection`` (see
``kernel.llm.provider_connections``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CandidateRisk(str, Enum):
    """Risk flags a detector may attach to a candidate."""

    EXTERNAL_ENDPOINT_OVERRIDE = "external-endpoint-override"
    UNTRUSTED_EXTERNAL_CONFIG = "untrusted-external-config"
    SHARED_AUTH_NAMESPACE = "shared-auth-namespace"
    UNVERIFIED_COMPATIBILITY = "unverified-compatibility"


# Substrings marking a metadata value as secret-shaped; checked against the
# lowercased value so a secret embedded in a longer string is still caught.
_SECRET_MARKERS: tuple[str, ...] = (
    "sk-",
    "sk_",
    "api-key",
    "apikey",
    "password=",
    "token=",
    "bearer ",
    "secret",
)


def _normalize_identifier(value: str, *, label: str) -> str:
    """Strip and lowercase an identifier; reject blank input."""
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError(f"{label} cannot be empty")
    return normalized


def _normalize_source(value: str) -> str:
    """Strip and lowercase a detector source name; reject blank input."""
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("source cannot be empty")
    return normalized


def _normalize_risks(value: tuple[CandidateRisk, ...]) -> tuple[CandidateRisk, ...]:
    """Coerce risk entries so raw strings cannot enter through replace()."""
    normalized = (value,) if isinstance(value, (str, CandidateRisk)) else tuple(value)
    coerced: list[CandidateRisk] = []
    for entry in normalized:
        try:
            coerced.append(
                entry if isinstance(entry, CandidateRisk) else CandidateRisk(entry)
            )
        except ValueError:
            raise ValueError(f"unknown risk: {entry!r}") from None
    return tuple(coerced)


def _normalize_metadata(
    value: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str], ...]:
    """Coerce metadata pairs; reject blanks and secret-shaped values."""
    pairs = [value] if isinstance(value, str) else list(value)
    normalized: list[tuple[str, str]] = []
    for pair in pairs:
        try:
            key, item = pair
        except (TypeError, ValueError):
            raise ValueError("metadata entries must be (key, value) pairs") from None
        if not isinstance(key, str) or not isinstance(item, str):
            raise TypeError("metadata entries must be (key, value) pairs")
        if not key.strip() or not item.strip():
            raise ValueError("metadata cannot contain empty keys or values")
        if any(marker in item.lower() for marker in _SECRET_MARKERS):
            raise ValueError("metadata must not carry secrets")
        normalized.append((key.strip(), item.strip()))
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class ProviderCandidate:
    """Non-routable evidence record from one detector; never executed."""

    provider_id: str
    source: str
    detected: bool
    auth_available: bool
    external_config_present: bool
    external_endpoint_override_present: bool
    risks: tuple[CandidateRisk, ...]
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        """Normalize identifiers and reject secret-carrying metadata."""
        object.__setattr__(
            self,
            "provider_id",
            _normalize_identifier(self.provider_id, label="Provider id"),
        )
        object.__setattr__(self, "source", _normalize_source(self.source))
        for name in (
            "detected",
            "auth_available",
            "external_config_present",
            "external_endpoint_override_present",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        object.__setattr__(self, "risks", _normalize_risks(self.risks))
        object.__setattr__(self, "metadata", _normalize_metadata(self.metadata))
