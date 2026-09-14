"""Phase 10.4 – Domain Manifest Reader.

Safe, size-bounded, strict-JSON reading of declarative manifest files.
Never executes code, never imports modules, never follows symlinks
outside an authorized root (root enforcement is the caller's
responsibility — this module only reads a single, already-resolved
file path).

Reads exactly once: the same bytes that are checksummed are the bytes
that get parsed. Callers must use ``read_document()`` (not read the file
themselves) so no TOCTOU window exists between checksum and content.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from cmm.domains.contracts import _deep_freeze, _deep_unfreeze
from cmm.domains.errors import DomainDiscoverySourceError

_DEFAULT_MAX_BYTES = 1_048_576  # 1 MiB
_BOM = b"\xef\xbb\xbf"


@dataclass(frozen=True, slots=True)
class DomainManifestDocument:
    """The exact bytes read from a manifest file, plus its parsed mapping.

    ``raw_bytes`` and ``data`` always originate from the same single read;
    checksums must be computed over ``raw_bytes``, and packs must be
    parsed from ``data`` — never re-read the file for either purpose.

    ``data`` is deep-frozen on construction (nested dicts become
    ``MappingProxyType``, nested lists become tuples), so no caller can
    mutate the parsed manifest content in place. Callers that need a
    plain, mutable structure to feed into declarative parsers must go
    through ``_deep_unfreeze(document.data)`` explicitly.
    """

    raw_bytes: bytes
    data: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.raw_bytes, bytes):
            raise DomainDiscoverySourceError(
                f"raw_bytes must be bytes, got {type(self.raw_bytes).__name__}",
                field="raw_bytes",
            )
        if not isinstance(self.data, Mapping):
            raise DomainDiscoverySourceError(
                f"data must be a mapping, got {type(self.data).__name__}",
                field="data",
            )
        object.__setattr__(self, "data", _deep_freeze(self.data))

    def to_dict(self) -> dict[str, Any]:
        """Serialize for diagnostics/logging.

        ``raw_bytes`` is represented as a base64 string (bytes are not
        directly JSON-safe); this contract is not part of any public
        registry/loader JSON snapshot, so no stricter format is required.
        """
        return {
            "raw_bytes": base64.b64encode(self.raw_bytes).decode("ascii"),
            "data": _deep_unfreeze(self.data),
        }


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise DomainDiscoverySourceError(
                f"Duplicate key in manifest JSON: {key!r}",
                field="manifest",
                details={"key": key},
            )
        seen.add(key)
        result[key] = value
    return result


def _reject_json_constant(constant: str) -> float:
    raise DomainDiscoverySourceError(
        f"Manifest JSON must not contain non-finite constant: {constant}",
        field="manifest",
        details={"constant": constant},
    )


@runtime_checkable
class DomainManifestReader(Protocol):
    """Protocol for reading a declarative manifest file exactly once."""

    def read_document(self, candidate_path: Path) -> DomainManifestDocument: ...

    def read(self, candidate_path: Path) -> Mapping[str, Any]: ...


class JsonDomainManifestReader:
    """Strict, size-bounded, single-read JSON reader for manifest files."""

    def __init__(self, *, max_bytes: int = _DEFAULT_MAX_BYTES) -> None:
        if (
            not isinstance(max_bytes, int)
            or isinstance(max_bytes, bool)
            or max_bytes <= 0
        ):
            raise DomainDiscoverySourceError(
                f"max_bytes must be a positive int, got {max_bytes!r}",
                field="max_bytes",
            )
        self._max_bytes = max_bytes

    def read_document(self, candidate_path: Path) -> DomainManifestDocument:
        path = Path(candidate_path)
        try:
            with path.open("rb") as handle:
                raw = handle.read(self._max_bytes + 1)
        except OSError as exc:
            raise DomainDiscoverySourceError(
                f"Failed to read manifest file: {path.name}",
                field="manifest_path",
                details={"error": type(exc).__name__},
            ) from exc

        if len(raw) > self._max_bytes:
            raise DomainDiscoverySourceError(
                f"Manifest file exceeds maximum size of {self._max_bytes} bytes",
                field="manifest_path",
                details={"max_bytes": self._max_bytes},
            )

        if raw.startswith(_BOM):
            raise DomainDiscoverySourceError(
                "Manifest file must not contain a UTF-8 BOM",
                field="manifest_path",
            )

        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise DomainDiscoverySourceError(
                "Manifest file is not valid UTF-8",
                field="manifest_path",
                details={"error": type(exc).__name__},
            ) from exc

        try:
            parsed = json.loads(
                text,
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_json_constant,
            )
        except DomainDiscoverySourceError:
            raise
        except json.JSONDecodeError as exc:
            raise DomainDiscoverySourceError(
                "Manifest file is not valid JSON",
                field="manifest_path",
                details={"error": type(exc).__name__},
            ) from exc

        if not isinstance(parsed, Mapping):
            raise DomainDiscoverySourceError(
                f"Manifest JSON root must be an object, got {type(parsed).__name__}",
                field="manifest_path",
            )

        return DomainManifestDocument(raw_bytes=raw, data=parsed)

    def read(self, candidate_path: Path) -> Mapping[str, Any]:
        return self.read_document(candidate_path).data


__all__ = [
    "DomainManifestDocument",
    "DomainManifestReader",
    "JsonDomainManifestReader",
]
