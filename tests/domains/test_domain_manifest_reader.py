from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

from cmm.domains.errors import DomainDiscoverySourceError
from cmm.domains.manifest_reader import DomainManifestDocument, JsonDomainManifestReader


def test_reads_valid_manifest(tmp_path: Path):
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({"id": "x", "version": "1.0.0"}), encoding="utf-8")
    reader = JsonDomainManifestReader()
    result = reader.read(p)
    assert result == {"id": "x", "version": "1.0.0"}


def test_rejects_oversized_file(tmp_path: Path):
    p = tmp_path / "manifest.json"
    p.write_text(
        json.dumps({"id": "x", "version": "1.0.0", "padding": "y" * 1000}),
        encoding="utf-8",
    )
    reader = JsonDomainManifestReader(max_bytes=10)
    with pytest.raises(DomainDiscoverySourceError):
        reader.read(p)


def test_rejects_bom(tmp_path: Path):
    p = tmp_path / "manifest.json"
    p.write_bytes(
        b"\xef\xbb\xbf" + json.dumps({"id": "x", "version": "1.0.0"}).encode("utf-8")
    )
    reader = JsonDomainManifestReader()
    with pytest.raises(DomainDiscoverySourceError):
        reader.read(p)


def test_rejects_invalid_utf8(tmp_path: Path):
    p = tmp_path / "manifest.json"
    p.write_bytes(b"\xff\xfe\x00\x01")
    reader = JsonDomainManifestReader()
    with pytest.raises(DomainDiscoverySourceError):
        reader.read(p)


def test_rejects_invalid_json(tmp_path: Path):
    p = tmp_path / "manifest.json"
    p.write_text("{not valid json", encoding="utf-8")
    reader = JsonDomainManifestReader()
    with pytest.raises(DomainDiscoverySourceError):
        reader.read(p)


def test_rejects_non_mapping_root(tmp_path: Path):
    p = tmp_path / "manifest.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    reader = JsonDomainManifestReader()
    with pytest.raises(DomainDiscoverySourceError):
        reader.read(p)


def test_rejects_duplicate_keys(tmp_path: Path):
    p = tmp_path / "manifest.json"
    p.write_text('{"id": "a", "id": "b"}', encoding="utf-8")
    reader = JsonDomainManifestReader()
    with pytest.raises(DomainDiscoverySourceError):
        reader.read(p)


def test_rejects_nan(tmp_path: Path):
    p = tmp_path / "manifest.json"
    p.write_text('{"id": "a", "bad": NaN}', encoding="utf-8")
    reader = JsonDomainManifestReader()
    with pytest.raises(DomainDiscoverySourceError):
        reader.read(p)


def test_rejects_infinity(tmp_path: Path):
    p = tmp_path / "manifest.json"
    p.write_text('{"id": "a", "bad": Infinity}', encoding="utf-8")
    reader = JsonDomainManifestReader()
    with pytest.raises(DomainDiscoverySourceError):
        reader.read(p)


def test_rejects_negative_infinity(tmp_path: Path):
    p = tmp_path / "manifest.json"
    p.write_text('{"id": "a", "bad": -Infinity}', encoding="utf-8")
    reader = JsonDomainManifestReader()
    with pytest.raises(DomainDiscoverySourceError):
        reader.read(p)


def test_missing_file_raises_structured_error(tmp_path: Path):
    reader = JsonDomainManifestReader()
    with pytest.raises(DomainDiscoverySourceError):
        reader.read(tmp_path / "nope.json")


def test_max_bytes_must_be_positive_int():
    with pytest.raises(DomainDiscoverySourceError):
        JsonDomainManifestReader(max_bytes=0)
    with pytest.raises(DomainDiscoverySourceError):
        JsonDomainManifestReader(max_bytes=True)


# ── Single-read coherence ────────────────────────────────────────────────────


def test_read_document_returns_bytes_and_mapping_from_the_same_read(tmp_path: Path):
    p = tmp_path / "manifest.json"
    content = json.dumps({"id": "x", "version": "1.0.0"}).encode("utf-8")
    p.write_bytes(content)
    reader = JsonDomainManifestReader()

    document = reader.read_document(p)

    assert isinstance(document, DomainManifestDocument)
    assert document.raw_bytes == content
    assert document.data == {"id": "x", "version": "1.0.0"}


def test_read_document_checksum_matches_exact_bytes_parsed(tmp_path: Path):
    p = tmp_path / "manifest.json"
    content = json.dumps({"id": "checksum-consistency", "version": "1.0.0"}).encode(
        "utf-8"
    )
    p.write_bytes(content)
    reader = JsonDomainManifestReader()

    document = reader.read_document(p)
    checksum = f"sha256:{hashlib.sha256(document.raw_bytes).hexdigest()}"
    expected = f"sha256:{hashlib.sha256(content).hexdigest()}"

    assert checksum == expected
    assert document.data["id"] == "checksum-consistency"


def test_read_document_opens_file_exactly_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    p = tmp_path / "manifest.json"
    p.write_bytes(json.dumps({"id": "x", "version": "1.0.0"}).encode("utf-8"))

    open_calls = []
    real_open = Path.open

    def counting_open(self, *args, **kwargs):
        if self == p:
            open_calls.append(1)
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counting_open)
    reader = JsonDomainManifestReader()

    reader.read_document(p)

    assert len(open_calls) == 1


def test_read_wrapper_does_not_open_file_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    p = tmp_path / "manifest.json"
    p.write_bytes(json.dumps({"id": "x", "version": "1.0.0"}).encode("utf-8"))

    open_calls = []
    real_open = Path.open

    def counting_open(self, *args, **kwargs):
        if self == p:
            open_calls.append(1)
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counting_open)
    reader = JsonDomainManifestReader()

    reader.read(p)

    assert len(open_calls) == 1


# ── Real size bound (never loads the whole file first) ──────────────────────


def test_oversized_file_never_reads_past_the_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    p = tmp_path / "manifest.json"
    # A file drastically larger than the configured limit.
    huge_payload = json.dumps({"id": "x", "version": "1.0.0", "pad": "z" * 1_000_000})
    p.write_text(huge_payload, encoding="utf-8")

    requested_sizes: list[int] = []
    real_open = Path.open

    class _SpyHandle:
        def __init__(self, handle):
            self._handle = handle

        def read(self, size=-1):
            requested_sizes.append(size)
            return self._handle.read(size)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self._handle.close()
            return False

    def spying_open(self, *args, **kwargs):
        if self == p:
            return _SpyHandle(real_open(self, *args, **kwargs))
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", spying_open)
    reader = JsonDomainManifestReader(max_bytes=100)

    with pytest.raises(DomainDiscoverySourceError):
        reader.read_document(p)

    # The reader must request a bounded amount (max_bytes + 1), never the
    # full 1MB+ file size, proving the limit is enforced during the read
    # itself rather than after loading everything into memory.
    assert requested_sizes == [101]
    assert len(huge_payload.encode("utf-8")) > 100


def test_file_exactly_at_limit_is_accepted(tmp_path: Path):
    p = tmp_path / "manifest.json"
    content = json.dumps({"id": "x", "version": "1.0.0"}).encode("utf-8")
    p.write_bytes(content)

    reader = JsonDomainManifestReader(max_bytes=len(content))
    document = reader.read_document(p)
    assert document.raw_bytes == content


def test_file_one_byte_over_limit_is_rejected(tmp_path: Path):
    p = tmp_path / "manifest.json"
    content = json.dumps({"id": "x", "version": "1.0.0", "pad": "zz"}).encode("utf-8")
    p.write_bytes(content)
    reader = JsonDomainManifestReader(max_bytes=len(content) - 1)

    with pytest.raises(DomainDiscoverySourceError):
        reader.read_document(p)


# ── Deep immutability of DomainManifestDocument.data ────────────────────────


def test_document_data_top_level_assignment_is_rejected(tmp_path: Path):
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({"id": "x", "version": "1.0.0"}), encoding="utf-8")
    document = JsonDomainManifestReader().read_document(p)

    with pytest.raises(TypeError):
        document.data["id"] = "tampered"


def test_document_data_nested_mapping_is_immutable(tmp_path: Path):
    p = tmp_path / "manifest.json"
    p.write_text(
        json.dumps(
            {
                "id": "x",
                "version": "1.0.0",
                "compatibility": {"minimum_cmm_version": "1.0.0"},
            }
        ),
        encoding="utf-8",
    )
    document = JsonDomainManifestReader().read_document(p)

    nested = document.data["compatibility"]
    with pytest.raises(TypeError):
        nested["minimum_cmm_version"] = "tampered"


def test_document_data_nested_list_is_immutable(tmp_path: Path):
    p = tmp_path / "manifest.json"
    p.write_text(
        json.dumps({"id": "x", "version": "1.0.0", "tags": ["a", "b"]}),
        encoding="utf-8",
    )
    document = JsonDomainManifestReader().read_document(p)

    nested = document.data["tags"]
    assert isinstance(nested, tuple)
    with pytest.raises((TypeError, AttributeError)):
        nested[0] = "tampered"  # tuples have no item assignment


def test_document_is_frozen_dataclass(tmp_path: Path):
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({"id": "x", "version": "1.0.0"}), encoding="utf-8")
    document = JsonDomainManifestReader().read_document(p)

    with pytest.raises(Exception):  # noqa: B017 - dataclasses.FrozenInstanceError
        document.raw_bytes = b"tampered"


def test_document_to_dict_unfreezes_for_serialization(tmp_path: Path):
    p = tmp_path / "manifest.json"
    content = json.dumps(
        {"id": "x", "version": "1.0.0", "tags": ["a"], "meta": {"k": "v"}}
    ).encode("utf-8")
    p.write_bytes(content)
    document = JsonDomainManifestReader().read_document(p)

    result = document.to_dict()

    assert result["data"]["tags"] == ["a"]
    assert isinstance(result["data"]["tags"], list)
    assert result["data"]["meta"] == {"k": "v"}
    assert isinstance(result["data"]["meta"], dict)
    decoded_bytes = base64.b64decode(result["raw_bytes"])
    assert decoded_bytes == content
