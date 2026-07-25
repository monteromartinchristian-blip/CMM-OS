"""History query and pagination contracts for Phase 7.11.

:class:`ValidationHistoryQuery`
    Immutable filter specification for querying execution history.

:class:`ValidationHistoryPage`
    Immutable paginated result set.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import ValidationExecutionRecord

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_LIMIT: int = 50
_MAX_LIMIT: int = 500


# ---------------------------------------------------------------------------
# ValidationHistoryQuery
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ValidationHistoryQuery:
    """Immutable filter specification for the execution history.

    All fields are optional; ``None`` means "no filter".

    Parameters
    ----------
    policy:
        Match only executions that used this exact policy name.
    status:
        Match only executions with this status string.
    actor:
        Match only executions triggered by this actor.
    branch:
        Match only executions on this branch.
    started_after:
        Include only executions that started at or after this timestamp.
    started_before:
        Include only executions that started at or before this timestamp.
    gate_allowed:
        When ``True``, include only gate-approved executions.
        When ``False``, include only gate-denied executions.
        ``None`` means no filter.
    has_commit:
        When ``True``, include only executions that produced a commit hash.
        When ``False``, include only those without.
        ``None`` means no filter.
    limit:
        Maximum number of results per page (1–:data:`_MAX_LIMIT`,
        default 50).
    offset:
        Zero-based starting index for pagination.
    """

    policy: str | None = None
    status: str | None = None
    actor: str | None = None
    branch: str | None = None
    started_after: datetime | None = None
    started_before: datetime | None = None
    gate_allowed: bool | None = None
    has_commit: bool | None = None
    limit: int = _DEFAULT_LIMIT
    offset: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.limit, int) or self.limit < 1:
            raise ValueError(
                f"ValidationHistoryQuery.limit must be a positive integer; "
                f"got {self.limit!r}"
            )
        if self.limit > _MAX_LIMIT:
            raise ValueError(
                f"ValidationHistoryQuery.limit cannot exceed {_MAX_LIMIT}; "
                f"got {self.limit}"
            )
        if not isinstance(self.offset, int) or self.offset < 0:
            raise ValueError(
                f"ValidationHistoryQuery.offset must be a non-negative integer; "
                f"got {self.offset!r}"
            )

    def matches(self, record: ValidationExecutionRecord) -> bool:
        """Return ``True`` if *record* satisfies all non-None filters."""
        if self.policy is not None and record.policy != self.policy:
            return False
        if self.status is not None and record.status != self.status:
            return False
        if self.actor is not None and record.actor != self.actor:
            return False
        if self.branch is not None and record.branch != self.branch:
            return False
        if (
            self.started_after is not None
            and record.started_at is not None
            and record.started_at < self.started_after
        ):
            return False
        if (
            self.started_before is not None
            and record.started_at is not None
            and record.started_at > self.started_before
        ):
            return False
        if self.gate_allowed is not None and record.gate_allowed != self.gate_allowed:
            return False
        if self.has_commit is not None:
            record_has_commit = record.commit_hash is not None
            if record_has_commit != self.has_commit:
                return False
        return True


# ---------------------------------------------------------------------------
# ValidationHistoryPage
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ValidationHistoryPage:
    """Immutable paginated slice of matching execution records.

    Parameters
    ----------
    items:
        Tuple of records in the current page (most-recent first).
    total:
        Total number of records that match the query (across all pages).
    limit:
        The page size that was requested.
    offset:
        The starting offset that was requested.
    has_more:
        ``True`` if there are more records beyond this page.
    """

    items: tuple[ValidationExecutionRecord, ...] = ()
    total: int = 0
    limit: int = _DEFAULT_LIMIT
    offset: int = 0
    has_more: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items or ()))


__all__ = ["ValidationHistoryPage", "ValidationHistoryQuery"]
