"""Phase 10.1 – Tests for domain identifiers."""

from __future__ import annotations

import pytest

from cmm.domains.errors import DomainContractValidationError, DomainSerializationError
from cmm.domains.identifiers import (
    DomainId,
    DomainManifestId,
    DomainResultId,
)

# ── DomainId ──────────────────────────────────────────────────────────────────


class TestDomainId:
    """Tests for DomainId."""

    # ── Happy path ───────────────────────────────────────────────────────

    def test_valid_slug(self) -> None:
        did = DomainId(slug="my-domain")
        assert did.slug == "my-domain"
        assert str(did) == "domain:my-domain"

    def test_single_segment_slug(self) -> None:
        did = DomainId(slug="minimal")
        assert did.slug == "minimal"
        assert str(did) == "domain:minimal"

    def test_multi_segment_slug(self) -> None:
        did = DomainId(slug="a-b-c-d")
        assert did.slug == "a-b-c-d"
        assert str(did) == "domain:a-b-c-d"

    def test_numeric_segments(self) -> None:
        did = DomainId(slug="app-v2-beta3")
        assert did.slug == "app-v2-beta3"

    # ── Hash and equality ────────────────────────────────────────────────

    def test_equal_by_slug(self) -> None:
        a = DomainId(slug="test")
        b = DomainId(slug="test")
        assert a == b
        assert hash(a) == hash(b)

    def test_not_equal_different_slugs(self) -> None:
        a = DomainId(slug="test")
        b = DomainId(slug="other")
        assert a != b

    def test_equality_with_string(self) -> None:
        did = DomainId(slug="test")
        assert did == "domain:test"

    def test_equality_other_types_not_implemented(self) -> None:
        did = DomainId(slug="test")
        assert did != 42
        assert did != None

    def test_hash_consistent(self) -> None:
        did = DomainId(slug="test")
        assert hash(did) == hash(did)
        assert hash(did) == hash("test")

    def test_str_roundtrip(self) -> None:
        did = DomainId(slug="my-domain")
        parsed = DomainId.from_str(str(did))
        assert did == parsed

    # ── Invalid slugs ────────────────────────────────────────────────────

    @pytest.mark.parametrize(
        "bad_slug",
        [
            "",
            "  ",
            "UPPERCASE",
            "has_underscore",
            "has space",
            "-leading-dash",
            "trailing-dash-",
            "double--dash",
            "camelCase",
            "CamelCase",
            "with.dot",
        ],
    )
    def test_invalid_slug_raises(self, bad_slug: str) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainId(slug=bad_slug)

    # ── Serialization ────────────────────────────────────────────────────

    def test_to_dict(self) -> None:
        did = DomainId(slug="test")
        assert did.to_dict() == {"slug": "test"}

    def test_from_dict(self) -> None:
        did = DomainId.from_dict({"slug": "test"})
        assert did.slug == "test"

    def test_from_dict_missing_key(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainId.from_dict({})

    def test_from_dict_not_mapping(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainId.from_dict("not-a-mapping")  # type: ignore[arg-type]

    def test_from_str(self) -> None:
        did = DomainId.from_str("domain:my-domain")
        assert did.slug == "my-domain"

    def test_from_str_invalid_prefix(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainId.from_str("manifest:my-domain:1.0")

    def test_from_str_missing_prefix(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainId.from_str("my-domain")

    # ── Immutability ─────────────────────────────────────────────────────

    def test_frozen(self) -> None:
        did = DomainId(slug="test")
        with pytest.raises(Exception):  # noqa: B017
            did.slug = "other"  # type: ignore[misc]


# ── DomainManifestId ──────────────────────────────────────────────────────────


class TestDomainManifestId:
    """Tests for DomainManifestId."""

    # ── Happy path ───────────────────────────────────────────────────────

    def test_valid(self) -> None:
        mid = DomainManifestId(slug="my-domain", version="1.0.0")
        assert mid.slug == "my-domain"
        assert mid.version == "1.0.0"
        assert str(mid) == "manifest:my-domain:1.0.0"

    def test_version_with_hyphens(self) -> None:
        mid = DomainManifestId(slug="test", version="1.0.0-beta1")
        assert str(mid) == "manifest:test:1.0.0-beta1"

    def test_version_complex(self) -> None:
        mid = DomainManifestId(slug="core", version="2024.1.0-alpha.2+build.123")
        assert str(mid) == "manifest:core:2024.1.0-alpha.2+build.123"

    # ── Hash and equality ────────────────────────────────────────────────

    def test_equal(self) -> None:
        a = DomainManifestId(slug="test", version="1.0")
        b = DomainManifestId(slug="test", version="1.0")
        assert a == b
        assert hash(a) == hash(b)

    def test_not_equal_different_slug(self) -> None:
        a = DomainManifestId(slug="test", version="1.0")
        b = DomainManifestId(slug="other", version="1.0")
        assert a != b

    def test_not_equal_different_version(self) -> None:
        a = DomainManifestId(slug="test", version="1.0")
        b = DomainManifestId(slug="test", version="2.0")
        assert a != b

    def test_equality_with_string(self) -> None:
        mid = DomainManifestId(slug="test", version="1.0")
        assert mid == "manifest:test:1.0"

    # ── Invalid inputs ───────────────────────────────────────────────────

    def test_empty_slug(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainManifestId(slug="", version="1.0")

    def test_bad_slug(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainManifestId(slug="BAD-slug", version="1.0")

    def test_empty_version(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainManifestId(slug="test", version="")

    def test_version_with_space(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainManifestId(slug="test", version="1.0 alpha")

    def test_version_with_colon(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainManifestId(slug="test", version="1.0:alpha")

    # ── Serialization ────────────────────────────────────────────────────

    def test_to_dict(self) -> None:
        mid = DomainManifestId(slug="test", version="1.0")
        assert mid.to_dict() == {"slug": "test", "version": "1.0"}

    def test_from_dict(self) -> None:
        mid = DomainManifestId.from_dict({"slug": "test", "version": "1.0"})
        assert mid.slug == "test"
        assert mid.version == "1.0"

    def test_from_dict_missing_keys(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainManifestId.from_dict({"slug": "test"})

    def test_from_dict_not_mapping(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainManifestId.from_dict("not-a-mapping")  # type: ignore[arg-type]

    # ── Immutability ─────────────────────────────────────────────────────

    def test_frozen(self) -> None:
        mid = DomainManifestId(slug="test", version="1.0")
        with pytest.raises(Exception):  # noqa: B017
            mid.slug = "other"  # type: ignore[misc]


# ── DomainResultId ────────────────────────────────────────────────────────────


class TestDomainResultId:
    """Tests for DomainResultId."""

    # ── Happy path ───────────────────────────────────────────────────────

    def test_valid(self) -> None:
        rid = DomainResultId(opaque_id="abc123")
        assert rid.opaque_id == "abc123"
        assert str(rid) == "domain-result:abc123"

    def test_generate(self) -> None:
        rid = DomainResultId.generate()
        assert rid.opaque_id != ""
        assert ":" not in rid.opaque_id
        assert str(rid).startswith("domain-result:")

    def test_generate_unique(self) -> None:
        a = DomainResultId.generate()
        b = DomainResultId.generate()
        assert a != b

    # ── Hash and equality ────────────────────────────────────────────────

    def test_equal(self) -> None:
        a = DomainResultId(opaque_id="abc")
        b = DomainResultId(opaque_id="abc")
        assert a == b
        assert hash(a) == hash(b)

    def test_not_equal(self) -> None:
        a = DomainResultId(opaque_id="abc")
        b = DomainResultId(opaque_id="xyz")
        assert a != b

    def test_equality_with_string(self) -> None:
        rid = DomainResultId(opaque_id="abc")
        assert rid == "domain-result:abc"

    # ── Invalid inputs ───────────────────────────────────────────────────

    def test_empty_opaque_id(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainResultId(opaque_id="")

    def test_whitespace_opaque_id(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainResultId(opaque_id="   ")

    def test_colon_in_opaque_id(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainResultId(opaque_id="abc:def")

    # ── Serialization ────────────────────────────────────────────────────

    def test_to_dict(self) -> None:
        rid = DomainResultId(opaque_id="abc")
        assert rid.to_dict() == {"opaque_id": "abc"}

    def test_from_dict(self) -> None:
        rid = DomainResultId.from_dict({"opaque_id": "abc"})
        assert rid.opaque_id == "abc"

    def test_from_dict_missing_key(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainResultId.from_dict({})

    # ── Immutability ─────────────────────────────────────────────────────

    def test_frozen(self) -> None:
        rid = DomainResultId(opaque_id="abc")
        with pytest.raises(Exception):  # noqa: B017
            rid.opaque_id = "other"  # type: ignore[misc]
