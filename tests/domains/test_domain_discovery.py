from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmm.domains.discovery import FileSystemDomainDiscovery
from cmm.domains.discovery_contracts import DomainSource
from cmm.domains.enums import DomainSourceKind


def _write_manifest(
    directory: Path, domain_id: str, version: str, name: str = "manifest.json"
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(
        json.dumps(
            {"id": domain_id, "version": version, "author": "tester", "license": "MIT"}
        ),
        encoding="utf-8",
    )


def _source(location: Path, **overrides) -> DomainSource:
    defaults = {
        "source_id": "s1",
        "kind": DomainSourceKind.DIRECTORY,
        "location": str(location),
        "trusted": True,
    }
    defaults.update(overrides)
    return DomainSource(**defaults)


def test_disabled_source_is_ignored(tmp_path: Path):
    _write_manifest(tmp_path / "a", "a", "1.0.0")
    source = _source(tmp_path, enabled=False)
    result = FileSystemDomainDiscovery().discover((source,))
    assert result.candidates == ()
    assert result.scanned_sources == ()


def test_nonexistent_root_produces_blocking_issue(tmp_path: Path):
    source = _source(tmp_path / "does-not-exist")
    result = FileSystemDomainDiscovery().discover((source,))
    assert result.candidates == ()
    assert len(result.issues) == 1
    assert result.issues[0].blocking is True


def test_root_not_a_directory_produces_blocking_issue(tmp_path: Path):
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    source = _source(f)
    result = FileSystemDomainDiscovery().discover((source,))
    assert result.candidates == ()
    assert result.issues[0].blocking is True


def test_direct_manifest_in_root_discovered(tmp_path: Path):
    _write_manifest(tmp_path, "root-domain", "1.0.0")
    source = _source(tmp_path)
    result = FileSystemDomainDiscovery().discover((source,))
    assert len(result.candidates) == 1
    assert result.candidates[0].candidate_id == "root-domain:1.0.0"


def test_non_recursive_finds_direct_children_only(tmp_path: Path):
    _write_manifest(tmp_path / "a", "a", "1.0.0")
    _write_manifest(tmp_path / "a" / "nested", "nested", "1.0.0")
    source = _source(tmp_path, recursive=False)
    result = FileSystemDomainDiscovery().discover((source,))
    ids = {c.candidate_id for c in result.candidates}
    assert ids == {"a:1.0.0"}


def test_recursive_finds_nested_children(tmp_path: Path):
    _write_manifest(tmp_path / "a", "a", "1.0.0")
    _write_manifest(tmp_path / "a" / "nested", "nested", "1.0.0")
    source = _source(tmp_path, recursive=True)
    result = FileSystemDomainDiscovery().discover((source,))
    ids = {c.candidate_id for c in result.candidates}
    assert ids == {"a:1.0.0", "nested:1.0.0"}


def test_discovery_is_deterministic(tmp_path: Path):
    _write_manifest(tmp_path / "zeta", "zeta", "1.0.0")
    _write_manifest(tmp_path / "alpha", "alpha", "1.0.0")
    source = _source(tmp_path)
    r1 = FileSystemDomainDiscovery().discover((source,))
    r2 = FileSystemDomainDiscovery().discover((source,))
    assert [c.candidate_id for c in r1.candidates] == [
        c.candidate_id for c in r2.candidates
    ]
    assert [c.candidate_id for c in r1.candidates] == ["alpha:1.0.0", "zeta:1.0.0"]


def test_internal_symlink_is_discovered(tmp_path: Path):
    real_dir = tmp_path / "real"
    _write_manifest(real_dir, "linked", "1.0.0")
    (tmp_path / "alias").symlink_to(real_dir)
    source = _source(tmp_path)
    result = FileSystemDomainDiscovery().discover((source,))
    ids = {c.candidate_id for c in result.candidates}
    assert "linked:1.0.0" in ids


def test_symlink_escaping_root_is_rejected(tmp_path: Path):
    outside = tmp_path.parent / "outside_discovery_test"
    _write_manifest(outside, "escaped", "1.0.0")
    root = tmp_path / "root"
    root.mkdir()
    (root / "linked").symlink_to(outside)
    source = _source(root)
    result = FileSystemDomainDiscovery().discover((source,))
    assert result.candidates == ()
    assert any(i.code == "DOMAIN_PATH_ESCAPE" and i.blocking for i in result.issues)


def test_manifest_too_large_produces_blocking_issue(tmp_path: Path):
    d = tmp_path / "big"
    d.mkdir()
    huge_value = "x" * 200
    (d / "manifest.json").write_text(
        json.dumps({"id": "big", "version": "1.0.0", "padding": huge_value}),
        encoding="utf-8",
    )
    source = _source(tmp_path)
    discovery = FileSystemDomainDiscovery(max_manifest_bytes=50)
    result = discovery.discover((source,))
    assert result.candidates == ()
    assert any(i.blocking for i in result.issues)


def test_invalid_utf8_produces_blocking_issue(tmp_path: Path):
    d = tmp_path / "badenc"
    d.mkdir()
    (d / "manifest.json").write_bytes(b"\xff\xfe not utf8")
    source = _source(tmp_path)
    result = FileSystemDomainDiscovery().discover((source,))
    assert result.candidates == ()
    assert any(i.blocking for i in result.issues)


def test_invalid_json_produces_blocking_issue(tmp_path: Path):
    d = tmp_path / "badjson"
    d.mkdir()
    (d / "manifest.json").write_text("{not json", encoding="utf-8")
    source = _source(tmp_path)
    result = FileSystemDomainDiscovery().discover((source,))
    assert result.candidates == ()
    assert any(i.blocking for i in result.issues)


def test_json_root_not_mapping_produces_blocking_issue(tmp_path: Path):
    d = tmp_path / "badroot"
    d.mkdir()
    (d / "manifest.json").write_text("[1, 2, 3]", encoding="utf-8")
    source = _source(tmp_path)
    result = FileSystemDomainDiscovery().discover((source,))
    assert result.candidates == ()
    assert any(i.blocking for i in result.issues)


def test_duplicate_json_keys_rejected(tmp_path: Path):
    d = tmp_path / "dupkeys"
    d.mkdir()
    (d / "manifest.json").write_text(
        '{"id": "dup", "id": "dup2", "version": "1.0.0"}', encoding="utf-8"
    )
    source = _source(tmp_path)
    result = FileSystemDomainDiscovery().discover((source,))
    assert result.candidates == ()
    assert any(i.blocking for i in result.issues)


def test_nan_rejected(tmp_path: Path):
    d = tmp_path / "nantest"
    d.mkdir()
    (d / "manifest.json").write_text(
        '{"id": "nantest", "version": "1.0.0", "bad": NaN}', encoding="utf-8"
    )
    source = _source(tmp_path)
    result = FileSystemDomainDiscovery().discover((source,))
    assert result.candidates == ()
    assert any(i.blocking for i in result.issues)


def test_infinity_rejected(tmp_path: Path):
    d = tmp_path / "inftest"
    d.mkdir()
    (d / "manifest.json").write_text(
        '{"id": "inftest", "version": "1.0.0", "bad": Infinity}', encoding="utf-8"
    )
    source = _source(tmp_path)
    result = FileSystemDomainDiscovery().discover((source,))
    assert result.candidates == ()
    assert any(i.blocking for i in result.issues)


def test_both_manifest_names_prefers_manifest_json_with_warning(tmp_path: Path):
    d = tmp_path / "both"
    d.mkdir()
    _write_manifest(d, "both", "1.0.0", name="manifest.json")
    _write_manifest(d, "both-alt", "1.0.0", name="domain.json")
    source = _source(tmp_path)
    result = FileSystemDomainDiscovery().discover((source,))
    assert len(result.candidates) == 1
    assert result.candidates[0].candidate_id == "both:1.0.0"
    assert any(
        i.code == "ambiguous_manifest_name" and not i.blocking for i in result.issues
    )


def test_exact_duplicate_candidate_deduplicated(tmp_path: Path):
    _write_manifest(tmp_path / "a", "dup-domain", "1.0.0")
    source_a = _source(tmp_path / "a", source_id="s1")
    source_b = _source(tmp_path / "a", source_id="s1")
    result = FileSystemDomainDiscovery().discover((source_a, source_b))
    assert len(result.candidates) == 1


def test_conflicting_identity_different_checksum_is_blocking(tmp_path: Path):
    _write_manifest(tmp_path / "a", "conflict-domain", "1.0.0")
    d2 = tmp_path / "b"
    d2.mkdir()
    (d2 / "manifest.json").write_text(
        json.dumps(
            {
                "id": "conflict-domain",
                "version": "1.0.0",
                "author": "different",
                "license": "MIT",
            }
        ),
        encoding="utf-8",
    )
    source = _source(tmp_path, recursive=True)
    result = FileSystemDomainDiscovery().discover((source,))
    assert result.candidates == ()
    assert any(
        i.code == "DOMAIN_CANDIDATE_INVALID" and i.blocking for i in result.issues
    )


def test_trusted_and_untrusted_candidates(tmp_path: Path):
    _write_manifest(tmp_path / "trusted-dom", "trusted-dom", "1.0.0")
    trusted_source = _source(tmp_path / "trusted-dom", trusted=True)
    untrusted_source = _source(tmp_path / "trusted-dom", source_id="s2", trusted=False)
    result_trusted = FileSystemDomainDiscovery().discover((trusted_source,))
    result_untrusted = FileSystemDomainDiscovery().discover((untrusted_source,))
    assert result_trusted.candidates[0].trusted is True
    assert result_untrusted.candidates[0].trusted is False


def test_candidate_checksum_matches_file_bytes(tmp_path: Path):
    import hashlib

    _write_manifest(tmp_path, "checksum-domain", "1.0.0")
    source = _source(tmp_path)
    result = FileSystemDomainDiscovery().discover((source,))
    candidate = result.candidates[0]
    raw = (tmp_path / "manifest.json").read_bytes()
    expected = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    assert candidate.checksum == expected


def test_discovery_never_imports_or_executes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    d = tmp_path / "executable"
    d.mkdir()
    entrypoint = d / "entrypoint.py"
    entrypoint.write_text(
        "raise RuntimeError('should never execute')\n", encoding="utf-8"
    )
    _write_manifest(d, "executable", "1.0.0")
    source = _source(tmp_path)
    # Should not raise even though an executable-looking file exists alongside the manifest.
    result = FileSystemDomainDiscovery().discover((source,))
    assert len(result.candidates) == 1


def test_unsupported_source_kind_not_operational(tmp_path: Path):
    source = _source(tmp_path, kind=DomainSourceKind.PLUGIN)
    result = FileSystemDomainDiscovery().discover((source,))
    assert result.candidates == ()
    assert any(
        i.code == "unsupported_source_kind" and not i.blocking for i in result.issues
    )


# ── Symlink cycles / duplicate aliasing (visited_resolved_paths) ────────────


def test_symlink_back_to_root_terminates_and_is_ignored(tmp_path: Path):
    _write_manifest(tmp_path / "a", "a", "1.0.0")
    (tmp_path / "a" / "back").symlink_to(tmp_path)
    source = _source(tmp_path, recursive=True)

    result = FileSystemDomainDiscovery().discover((source,))

    ids = {c.candidate_id for c in result.candidates}
    assert ids == {"a:1.0.0"}
    assert not any(i.code == "DOMAIN_PATH_ESCAPE" for i in result.issues)


def test_symlink_back_to_ancestor_terminates_and_is_ignored(tmp_path: Path):
    _write_manifest(tmp_path / "a" / "b", "b", "1.0.0")
    (tmp_path / "a" / "b" / "back").symlink_to(tmp_path / "a")
    source = _source(tmp_path, recursive=True)

    result = FileSystemDomainDiscovery().discover((source,))

    ids = {c.candidate_id for c in result.candidates}
    assert ids == {"b:1.0.0"}
    assert not any(i.code == "DOMAIN_PATH_ESCAPE" for i in result.issues)


def test_two_aliases_to_same_directory_processed_once(tmp_path: Path):
    real_dir = tmp_path / "real"
    _write_manifest(real_dir, "aliased", "1.0.0")
    (tmp_path / "alias1").symlink_to(real_dir)
    (tmp_path / "alias2").symlink_to(real_dir)
    source = _source(tmp_path, recursive=True)

    result = FileSystemDomainDiscovery().discover((source,))

    ids = [c.candidate_id for c in result.candidates]
    assert ids == ["aliased:1.0.0"]
    assert len(result.candidates) == 1


def test_symlink_cycle_and_aliases_combined_still_terminates_and_blocks_escapes(
    tmp_path: Path,
):
    _write_manifest(tmp_path / "a" / "b", "nested", "1.0.0")
    (tmp_path / "a" / "b" / "back").symlink_to(tmp_path / "a")
    (tmp_path / "a" / "loop_to_root").symlink_to(tmp_path)
    real_dir = tmp_path / "real"
    _write_manifest(real_dir, "aliased", "2.0.0")
    (tmp_path / "alias1").symlink_to(real_dir)
    (tmp_path / "alias2").symlink_to(real_dir)
    outside = tmp_path.parent / "outside_cycle_test"
    _write_manifest(outside, "escaped", "1.0.0")
    (tmp_path / "escape_link").symlink_to(outside)
    source = _source(tmp_path, recursive=True)

    result = FileSystemDomainDiscovery().discover((source,))

    ids = {c.candidate_id for c in result.candidates}
    assert ids == {"nested:1.0.0", "aliased:2.0.0"}
    assert any(i.code == "DOMAIN_PATH_ESCAPE" and i.blocking for i in result.issues)
    # No duplicate candidates for the aliased directory.
    assert len([c for c in result.candidates if c.candidate_id == "aliased:2.0.0"]) == 1


def test_discovery_is_deterministic_with_symlink_aliases(tmp_path: Path):
    real_dir = tmp_path / "real"
    _write_manifest(real_dir, "det-aliased", "1.0.0")
    (tmp_path / "alias1").symlink_to(real_dir)
    (tmp_path / "alias2").symlink_to(real_dir)
    source = _source(tmp_path, recursive=True)

    r1 = FileSystemDomainDiscovery().discover((source,))
    r2 = FileSystemDomainDiscovery().discover((source,))

    assert [c.candidate_id for c in r1.candidates] == [
        c.candidate_id for c in r2.candidates
    ]
    assert [c.location for c in r1.candidates] == [c.location for c in r2.candidates]


# ── root.resolve() failure is isolated to its own source ────────────────────


def test_root_resolve_failure_produces_issue_and_continues_with_other_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    good_root = tmp_path / "good"
    _write_manifest(good_root, "good-domain", "1.0.0")
    bad_root = tmp_path / "bad"
    bad_root.mkdir()

    real_resolve = Path.resolve

    def flaky_resolve(self, *args, **kwargs):
        if self == bad_root:
            raise OSError("simulated resolve failure")
        return real_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", flaky_resolve)

    source_bad = _source(bad_root, source_id="bad-source")
    source_good = _source(good_root, source_id="good-source")

    result = FileSystemDomainDiscovery().discover((source_bad, source_good))

    assert any(
        i.code == "source_root_unresolvable" and i.blocking for i in result.issues
    )
    assert any(c.candidate_id == "good-domain:1.0.0" for c in result.candidates)
    assert set(result.scanned_sources) == {"bad-source", "good-source"}
