"""Phase 10.1 – Domain Identifiers.

Immutable, validated identifier contracts for the Domain Intelligence subsystem.

Canonical formats::

    domain:<slug>
    manifest:<slug>:<version>
    domain-result:<opaque-id>
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cmm.domains.errors import DomainContractValidationError, DomainSerializationError


def _reject_unknown_id_fields(
    data: Mapping[str, Any], known: frozenset[str], cls_name: str
) -> None:
    """Raise DomainSerializationError if data contains unknown fields."""
    unknown = set(data.keys()) - known
    if unknown:
        raise DomainSerializationError(
            f"{cls_name}.from_dict got unknown fields: {sorted(unknown)}",
            field="data",
            details={"unknown_fields": sorted(unknown)},
        )


# ── Slug validation ───────────────────────────────────────────────────────────

_SLUG_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def _validate_slug(value: str, field: str) -> str:
    """Validate a slug string against the canonical domain-slug rules."""
    if not value:
        raise DomainContractValidationError(f"{field} must not be empty", field=field)
    if not _SLUG_RE.match(value):
        raise DomainContractValidationError(
            f"{field} must be lowercase ASCII, hyphen-separated, "
            f"no consecutive hyphens, no leading or trailing hyphens: {value!r}",
            field=field,
            details={"value": value, "pattern": _SLUG_RE.pattern},
        )
    return value


# ── Version validation ────────────────────────────────────────────────────────


def _validate_version_segment(value: str, field: str) -> str:
    """Validate a version segment: non-empty, no spaces, no colons."""
    if not value:
        raise DomainContractValidationError(f"{field} must not be empty", field=field)
    if " " in value:
        raise DomainContractValidationError(
            f"{field} must not contain spaces: {value!r}",
            field=field,
            details={"value": value},
        )
    if ":" in value:
        raise DomainContractValidationError(
            f"{field} must not contain colon: {value!r}",
            field=field,
            details={"value": value},
        )
    return value


# ── DomainId ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DomainId:
    """Immutable identifier for a domain.

    Canonical form: ``domain:<slug>``
    """

    slug: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "slug", _validate_slug(self.slug, "slug"))

    def __str__(self) -> str:
        return f"domain:{self.slug}"

    def __hash__(self) -> int:
        return hash(self.slug)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DomainId):
            return self.slug == other.slug
        if isinstance(other, str):
            return str(self) == other
        return NotImplemented

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {"slug": self.slug}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainId:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainId.from_dict requires a mapping", field="data"
            )
        _reject_unknown_id_fields(data, frozenset({"slug"}), "DomainId")
        if "slug" not in data:
            raise DomainSerializationError(
                "DomainId.from_dict missing required field 'slug'", field="slug"
            )
        return cls(slug=str(data["slug"]))

    @classmethod
    def from_str(cls, value: str) -> DomainId:
        """Parse from canonical string ``domain:<slug>``."""
        if not value.startswith("domain:"):
            raise DomainSerializationError(
                f"DomainId must start with 'domain:': {value!r}", field="value"
            )
        slug = value[len("domain:") :]
        return cls(slug=slug)


# ── DomainManifestId ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DomainManifestId:
    """Immutable identifier for a domain manifest.

    Canonical form: ``manifest:<slug>:<version>``
    """

    slug: str
    version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "slug", _validate_slug(self.slug, "slug"))
        object.__setattr__(
            self, "version", _validate_version_segment(self.version, "version")
        )

    def __str__(self) -> str:
        return f"manifest:{self.slug}:{self.version}"

    def __hash__(self) -> int:
        return hash((self.slug, self.version))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DomainManifestId):
            return self.slug == other.slug and self.version == other.version
        if isinstance(other, str):
            return str(self) == other
        return NotImplemented

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {"slug": self.slug, "version": self.version}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainManifestId:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainManifestId.from_dict requires a mapping", field="data"
            )
        _reject_unknown_id_fields(
            data, frozenset({"slug", "version"}), "DomainManifestId"
        )
        missing = {"slug", "version"} - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainManifestId.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        return cls(slug=str(data["slug"]), version=str(data["version"]))


# ── DomainResultId ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DomainResultId:
    """Immutable identifier for a domain result.

    Canonical form: ``domain-result:<opaque-id>``
    """

    opaque_id: str

    def __post_init__(self) -> None:
        if not self.opaque_id or not self.opaque_id.strip():
            raise DomainContractValidationError(
                "opaque_id must not be empty", field="opaque_id"
            )
        if ":" in self.opaque_id:
            raise DomainContractValidationError(
                f"opaque_id must not contain colon: {self.opaque_id!r}",
                field="opaque_id",
                details={"value": self.opaque_id},
            )
        object.__setattr__(self, "opaque_id", self.opaque_id.strip())

    def __str__(self) -> str:
        return f"domain-result:{self.opaque_id}"

    def __hash__(self) -> int:
        return hash(self.opaque_id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DomainResultId):
            return self.opaque_id == other.opaque_id
        if isinstance(other, str):
            return str(self) == other
        return NotImplemented

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {"opaque_id": self.opaque_id}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainResultId:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainResultId.from_dict requires a mapping", field="data"
            )
        _reject_unknown_id_fields(data, frozenset({"opaque_id"}), "DomainResultId")
        if "opaque_id" not in data:
            raise DomainSerializationError(
                "DomainResultId.from_dict missing required field 'opaque_id'",
                field="opaque_id",
            )
        return cls(opaque_id=str(data["opaque_id"]))

    @classmethod
    def generate(cls) -> DomainResultId:
        """Generate a new unique DomainResultId."""
        return cls(opaque_id=uuid.uuid4().hex)


__all__ = [
    "DomainId",
    "DomainManifestId",
    "DomainResultId",
]
