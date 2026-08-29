"""Phase 10.33 — Domain Event Credential Detection Policy.

Canonical high-confidence credential signatures and detection policy for Domain Intelligence Events.
All patterns are deterministic, precompiled regular expressions with unique family names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CredentialSignature:
    """Immutable signature definition for a recognized high-confidence credential family."""

    name: str
    pattern: re.Pattern[str]


# ── Canonical High-Confidence Credential Signatures Registry ──────────────────

HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES: tuple[CredentialSignature, ...] = (
    # Prefixed API keys & generic provider patterns (OpenAI, Stripe sk_*, generic sk_*, pk_*, etc.)
    CredentialSignature(
        name="openai_or_prefixed_key",
        pattern=re.compile(
            r"\b(?:sk|pk|api[_-]?key)[-_][a-zA-Z0-9_\-]{8,}\b", re.IGNORECASE
        ),
    ),
    CredentialSignature(
        name="generic_key_pattern",
        pattern=re.compile(r"\bkey-[a-zA-Z0-9_\-]{8,}\b", re.IGNORECASE),
    ),
    # GitHub credentials
    CredentialSignature(
        name="github_classic_token",
        pattern=re.compile(
            r"\b(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{16,}\b", re.IGNORECASE
        ),
    ),
    CredentialSignature(
        name="github_fine_grained_pat",
        pattern=re.compile(r"\bgithub_pat_[a-zA-Z0-9_]{16,}\b", re.IGNORECASE),
    ),
    # AWS credentials
    CredentialSignature(
        name="aws_access_key_id",
        pattern=re.compile(r"\bAKIA[0-9A-Za-z]{16}\b"),
    ),
    # Google credentials
    CredentialSignature(
        name="google_api_key",
        pattern=re.compile(r"\bAIza[0-9A-Za-z\-_]{30,}\b"),
    ),
    # Slack credentials
    CredentialSignature(
        name="slack_token",
        pattern=re.compile(r"\bxox[bpar]-[0-9a-zA-Z\-]{10,}\b", re.IGNORECASE),
    ),
    # GitLab Personal Access Token
    CredentialSignature(
        name="gitlab_pat",
        pattern=re.compile(r"\bglpat-[a-zA-Z0-9\-_]{20,}\b"),
    ),
    # npm Access Token
    CredentialSignature(
        name="npm_token",
        pattern=re.compile(r"\bnpm_[a-zA-Z0-9]{20,}\b"),
    ),
    # Hugging Face Access Token
    CredentialSignature(
        name="huggingface_token",
        pattern=re.compile(r"\bhf_[a-zA-Z0-9]{20,}\b"),
    ),
    # SendGrid API Key
    CredentialSignature(
        name="sendgrid_api_key",
        pattern=re.compile(r"\bSG\.[a-zA-Z0-9_\-]{16,}\.[a-zA-Z0-9_\-]{16,}\b"),
    ),
    # DigitalOcean Personal Access Token
    CredentialSignature(
        name="digitalocean_pat",
        pattern=re.compile(r"\bdop_v1_[a-zA-Z0-9]{32,}\b"),
    ),
    # Stripe Secret & Restricted API Keys
    CredentialSignature(
        name="stripe_api_key",
        pattern=re.compile(r"\b(?:sk|rk)_(?:live|test)_[0-9a-zA-Z]{16,}\b"),
    ),
    # Twilio API Key
    CredentialSignature(
        name="twilio_api_key",
        pattern=re.compile(r"\bSK[0-9a-fA-F]{32}\b"),
    ),
    # PyPI API Token
    CredentialSignature(
        name="pypi_token",
        pattern=re.compile(r"\bpypi-[a-zA-Z0-9\-_]{20,}\b"),
    ),
    # Docker Hub Personal Access Token
    CredentialSignature(
        name="dockerhub_pat",
        pattern=re.compile(r"\bdckr_pat_[a-zA-Z0-9\-_]{20,}\b"),
    ),
    # Structural credential assignments & headers
    CredentialSignature(
        name="authorization_header",
        pattern=re.compile(r"authorization\s*[:=]", re.IGNORECASE),
    ),
    CredentialSignature(
        name="bearer_token",
        pattern=re.compile(r"\bbearer\s+[a-zA-Z0-9_\-\.]{8,}", re.IGNORECASE),
    ),
    CredentialSignature(
        name="bearer_assignment",
        pattern=re.compile(r"\bbearer\s*[:=]\s*\S+", re.IGNORECASE),
    ),
    CredentialSignature(
        name="credential_assignment",
        pattern=re.compile(
            r"\b(?:password|secret|credential|cookie|set[_-]?cookie|session[_-]?token|sessionid|session[_-]?id|access[_-]?token|refresh[_-]?token|auth[_-]?token|csrf[_-]?token|csrftoken)\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
    ),
)


def contains_high_confidence_credential(value: str) -> bool:
    """Return True when value contains a recognized high-confidence credential."""
    if not isinstance(value, str):
        return False
    cleaned = re.sub(r"\[REDACTED_[A-Z0-9_]+\]", " ", value, flags=re.IGNORECASE)
    for sig in HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES:
        if sig.pattern.search(cleaned):
            return True
    return False
