"""Phase 11.22 — durable event storage configuration.

This module answers exactly one question: *where* does the canonical durable
event repository keep its append-only evidence?

It is deliberately **not** a settings framework.  It reuses the composition
approach already used across the platform — an explicit value supplied by the
caller — rather than introducing environment parsing, a config file format, a
settings registry or a storage subsystem.

Requirements Phase 11.22 must satisfy:

* the source tree is never the default runtime storage location;
* tests inject a temporary directory;
* the runtime composition can inject the CMM OS data location;
* the resulting path is deterministic;
* parent-directory creation is bounded to the configured path;
* an invalid or unwritable location fails safely.

See ``docs/reference/phase-11-event-system.md``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

__all__ = [
    "DEFAULT_EVENT_STORE_FILENAME",
    "EVENT_STORE_DIRECTORY_NAME",
    "SOURCE_TREE_STORAGE_ERROR",
    "default_event_store_directory",
    "default_event_store_path",
    "event_store_path",
    "is_inside_source_tree",
    "resolve_data_directory",
]

#: The configured directory name for Phase 11.22 durable event evidence.
EVENT_STORE_DIRECTORY_NAME = "events"

#: The append-only evidence file name.
DEFAULT_EVENT_STORE_FILENAME = "runtime_events.jsonl"

#: Failure code used when a configured location points inside the source tree.
SOURCE_TREE_STORAGE_ERROR = "EVENT_STORAGE_INSIDE_SOURCE_TREE"

_APPLICATION_DIRECTORY_NAME = "CMM OS"


class EventStorageConfigurationError(ValueError):
    """Raised when an event storage location is refused."""

    def __init__(self, reason: str, *, code: str) -> None:
        self.reason = reason
        self.code = code
        super().__init__(f"event storage location refused: {reason}")


def _repository_root() -> Path:
    """Return the CMM OS source tree root that must never hold runtime data."""

    return Path(__file__).resolve().parents[2]


def is_inside_source_tree(path: str | os.PathLike[str]) -> bool:
    """Return whether *path* resolves inside the CMM OS source tree."""

    candidate = Path(path).expanduser()
    try:
        resolved = candidate.resolve()
    except OSError:  # pragma: no cover - defensive for exotic paths
        resolved = candidate.absolute()

    root = _repository_root()
    return resolved == root or root in resolved.parents


def resolve_data_directory(
    data_directory: str | os.PathLike[str] | None = None,
) -> Path:
    """Return the canonical CMM OS data directory.

    An explicit value always wins: composition injects the location rather than
    discovering it.  When none is supplied, a deterministic per-user location
    outside the source tree is used.
    """

    if data_directory is not None:
        if not isinstance(data_directory, (str, os.PathLike)):
            raise TypeError("data_directory must be a str, os.PathLike or None")
        normalized = str(data_directory).strip()
        if not normalized:
            raise EventStorageConfigurationError(
                "data_directory must be non-empty when provided",
                code="EVENT_STORAGE_INVALID_DIRECTORY",
            )
        return Path(normalized).expanduser()

    override = os.environ.get("CMM_OS_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser()

    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / _APPLICATION_DIRECTORY_NAME
        )
    if os.name == "nt":  # pragma: no cover - platform specific
        local = os.environ.get("LOCALAPPDATA", "").strip()
        if local:
            return Path(local) / _APPLICATION_DIRECTORY_NAME
    return Path.home() / ".local" / "share" / _APPLICATION_DIRECTORY_NAME


def default_event_store_directory(
    data_directory: str | os.PathLike[str] | None = None,
) -> Path:
    """Return the deterministic directory holding durable event evidence."""

    return resolve_data_directory(data_directory) / EVENT_STORE_DIRECTORY_NAME


def default_event_store_path(
    data_directory: str | os.PathLike[str] | None = None,
    *,
    filename: str = DEFAULT_EVENT_STORE_FILENAME,
) -> Path:
    """Return the deterministic durable event store path."""

    return event_store_path(
        data_directory=data_directory,
        filename=filename,
    )


def event_store_path(
    data_directory: str | os.PathLike[str] | None = None,
    *,
    filename: str = DEFAULT_EVENT_STORE_FILENAME,
    allow_source_tree: bool = False,
) -> Path:
    """Resolve the durable event store path, refusing the source tree by default.

    ``allow_source_tree`` exists only so a test can prove the refusal is real; it
    is never enabled by the runtime composition.
    """

    if not isinstance(filename, str) or not filename.strip():
        raise EventStorageConfigurationError(
            "filename must be a non-empty string",
            code="EVENT_STORAGE_INVALID_FILENAME",
        )

    directory = default_event_store_directory(data_directory)
    candidate = directory / filename.strip()

    if not allow_source_tree and is_inside_source_tree(candidate):
        raise EventStorageConfigurationError(
            f"'{candidate}' is inside the CMM OS source tree",
            code=SOURCE_TREE_STORAGE_ERROR,
        )

    return candidate
