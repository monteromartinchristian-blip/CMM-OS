from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..errors import ValidationContractError


@dataclass(frozen=True, slots=True)
class CommitAuthorization:
    authorized: bool
    actor: str
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""
    validation_result_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.actor or not self.actor.strip():
            raise ValidationContractError("CommitAuthorization.actor must not be empty")
        if self.requested_at is not None and self.requested_at.tzinfo is None:
            object.__setattr__(
                self, "requested_at", self.requested_at.replace(tzinfo=timezone.utc)
            )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "authorized": self.authorized,
            "actor": self.actor,
            "requested_at": self.requested_at.isoformat(),
            "reason": self.reason,
            "validation_result_id": self.validation_result_id,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> CommitAuthorization:
        requested_at_raw = payload.get("requested_at")
        requested_at_dt = None
        if isinstance(requested_at_raw, str):
            requested_at_dt = datetime.fromisoformat(requested_at_raw)
        elif isinstance(requested_at_raw, datetime):
            requested_at_dt = requested_at_raw

        return cls(
            authorized=bool(payload["authorized"]),
            actor=str(payload["actor"]),
            requested_at=requested_at_dt or datetime.now(timezone.utc),
            reason=str(payload.get("reason", "")),
            validation_result_id=payload.get("validation_result_id"),
            metadata=dict(payload.get("metadata", {}))
            if isinstance(payload.get("metadata"), Mapping)
            else {},
        )


__all__ = ["CommitAuthorization"]
