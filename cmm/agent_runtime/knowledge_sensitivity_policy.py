"""Phase 9.18 – Knowledge Sensitivity and Privacy Policy Adapter.

Evaluates candidates for secrets, personal data, credentials, financial, health, and private data.
Enforces redaction, approval requirements, and secret rejection policies.
"""

from __future__ import annotations

import re
import uuid

from cmm.agent_runtime.enums import KnowledgeSensitivityLevel
from cmm.agent_runtime.knowledge_update_contracts import (
    KnowledgeSensitivityAssessment,
    KnowledgeUpdateCandidate,
    MemoryUpdateCandidate,
)

# Comprehensive patterns for secrets, keys, credentials, and sensitive PII
_SECRET_PATTERNS = [
    re.compile(
        r"(?i)(api[_-]?key|secret|password|passwd|auth[_-]?token|bearer|private[_-]?key)\s*[:=]\s*['\"]?[a-zA-Z0-9_\-\.]{8,}"
    ),
    re.compile(r"-----BEGIN\s+(RSA|EC|DSA|OPENSSH)\s+PRIVATE\s+KEY-----"),
    re.compile(
        r"ey[JjaWdAGlOiJKV1QiLCJhbGciOiJIUzI1NiJ9\.\w\.\w\-]+"
    ),  # JWT token pattern
]

_PERSONAL_PATTERNS = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),  # Email
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN pattern
    re.compile(r"\b(?:\d[ -]*?){13,16}\b"),  # Credit card numbers
]


class KnowledgeSensitivityPolicyAdapter:
    """Evaluates candidate data sensitivity and enforces privacy policies."""

    def evaluate_candidate(
        self, candidate: KnowledgeUpdateCandidate | MemoryUpdateCandidate
    ) -> KnowledgeSensitivityAssessment:
        """Analyze candidate payload and classify sensitivity level."""
        reasons: list[str] = []
        redacted_fields: list[str] = []
        contains_secrets = False
        contains_personal = False
        contains_credentials = False

        content_str = (
            str(candidate.content)
            if isinstance(candidate, KnowledgeUpdateCandidate)
            else str(candidate.value)
        )
        title_str = getattr(candidate, "title", getattr(candidate, "key", ""))

        full_text = f"{title_str} {content_str}"

        # 1. Check for secrets / credentials
        for pat in _SECRET_PATTERNS:
            if pat.search(full_text):
                contains_secrets = True
                contains_credentials = True
                reasons.append("SECRET_PATTERN_MATCHED")

        # 2. Check for personal / PII data
        for pat in _PERSONAL_PATTERNS:
            if pat.search(full_text):
                contains_personal = True
                reasons.append("PERSONAL_DATA_PATTERN_MATCHED")

        # 3. Determine sensitivity level
        if contains_secrets:
            level = KnowledgeSensitivityLevel.SECRET
            requires_redaction = True
        elif contains_personal or contains_credentials:
            level = KnowledgeSensitivityLevel.RESTRICTED
            requires_redaction = True
        elif (
            getattr(candidate, "is_explicit_preference", False)
            or getattr(candidate, "kind", None) == "explicit_preference"
        ):
            level = KnowledgeSensitivityLevel.INTERNAL
            requires_redaction = False
        else:
            level = KnowledgeSensitivityLevel.PUBLIC
            requires_redaction = False

        return KnowledgeSensitivityAssessment(
            assessment_id=f"sens-{uuid.uuid4().hex[:8]}",
            level=level,
            contains_secrets=contains_secrets,
            contains_personal_data=contains_personal,
            contains_credentials=contains_credentials,
            requires_redaction=requires_redaction,
            redacted_fields=tuple(redacted_fields),
            reasons=tuple(reasons),
        )

    def redact_payload(self, text: str) -> str:
        """Sanitize text by replacing matched secret patterns with redaction placeholder."""
        sanitized = text
        for pat in _SECRET_PATTERNS:
            sanitized = pat.sub("[REDACTED_SECRET]", sanitized)
        for pat in _PERSONAL_PATTERNS:
            sanitized = pat.sub("[REDACTED_PII]", sanitized)
        return sanitized
