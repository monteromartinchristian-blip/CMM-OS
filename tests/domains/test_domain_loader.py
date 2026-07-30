from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

import pytest

import cmm.domains.loader as loader_module
from cmm.domains.discovery_contracts import DomainCandidate
from cmm.domains.enums import DomainLoadStatus, DomainStatus
from cmm.domains.errors import (
    DomainChecksumMismatch,
    DomainLoadFailed,
    DomainRegistryNotFound,
    DomainReloadFailed,
    DomainSourceUntrusted,
    DomainUnloadFailed,
)
from cmm.domains.loader import DeclarativeDomainLoader
from cmm.domains.manifest_reader import JsonDomainManifestReader
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryRecord

from ._loader_helpers import make_candidate, write_domain_dir


def _make_loader(registry: DomainRegistry | None = None) -> DeclarativeDomainLoader:
    return DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(),
        registry=registry or DomainRegistry(),
    )


def test_load_valid_candidate(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    registry = DomainRegistry()
    loader = _make_loader(registry)

    result = loader.load(candidate)

    assert result.status == DomainLoadStatus.LOADED
    assert result.pack is not None
    assert result.registry_record is not None
    assert registry.get("greeter", "1.0.0") is not None


def test_load_untrusted_rejected(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0", trusted=False)
    loader = _make_loader()

    with pytest.raises(DomainSourceUntrusted):
        loader.load(candidate)


def test_load_allow_untrusted_succeeds(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0", trusted=False)
    loader = _make_loader()

    result = loader.load(candidate, allow_untrusted=True)

    assert result.status == DomainLoadStatus.LOADED


def test_load_checksum_mismatch_raises(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    # Tamper with the manifest after the candidate's checksum was computed.
    (domain_dir / "manifest.json").write_text(
        json.dumps(
            {
                "id": "greeter",
                "version": "1.0.0",
                "author": "x",
                "license": "MIT",
                "tags": ["x"],
            }
        ),
        encoding="utf-8",
    )
    loader = _make_loader()

    with pytest.raises(DomainChecksumMismatch):
        loader.load(candidate)


def test_load_version_mismatch_fails(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    tampered = DomainCandidate(
        candidate_id=candidate.candidate_id,
        source_id=candidate.source_id,
        source_kind=candidate.source_kind,
        location=candidate.location,
        manifest_path=candidate.manifest_path,
        domain_id=candidate.domain_id,
        detected_version="2.0.0",
        checksum=candidate.checksum,
        trusted=candidate.trusted,
        discovered_at=candidate.discovered_at,
    )
    loader = _make_loader()

    result = loader.load(tampered)

    assert result.status == DomainLoadStatus.FAILED
    assert result.errors


def test_load_invalid_manifest_fails(tmp_path):
    domain_dir = tmp_path / "bad"
    domain_dir.mkdir()
    (domain_dir / "manifest.json").write_text("{not json", encoding="utf-8")
    import hashlib
    from datetime import datetime, timezone

    raw = (domain_dir / "manifest.json").read_bytes()
    checksum = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    candidate = DomainCandidate(
        candidate_id="bad:1.0.0",
        source_id="s1",
        source_kind="directory",
        location=str(domain_dir),
        manifest_path="manifest.json",
        domain_id="domain:bad",
        detected_version="1.0.0",
        checksum=checksum,
        trusted=True,
        discovered_at=datetime.now(timezone.utc),
    )
    loader = _make_loader()

    result = loader.load(candidate)

    assert result.status == DomainLoadStatus.FAILED


def test_load_registry_conflict_returns_rejected(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    registry = DomainRegistry()
    loader = _make_loader(registry)
    loader.load(candidate)

    # Different content, same identity -> registry conflict.
    domain_dir2 = tmp_path / "greeter2"
    domain_dir2.mkdir()
    (domain_dir2 / "manifest.json").write_text(
        json.dumps(
            {"id": "greeter", "version": "1.0.0", "author": "other", "license": "MIT"}
        ),
        encoding="utf-8",
    )
    candidate2 = make_candidate(domain_dir2, "greeter", "1.0.0", source_id="s2")

    result = loader.load(candidate2)

    assert result.status == DomainLoadStatus.REJECTED
    assert result.errors


def test_load_does_not_auto_enable(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    registry = DomainRegistry()
    loader = _make_loader(registry)

    loader.load(candidate)

    definition = registry.get("greeter", "1.0.0")
    assert definition.enabled is False


def test_get_loaded_and_list_loaded(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    loader = _make_loader()
    loader.load(candidate)

    assert loader.get_loaded("greeter", "1.0.0") is not None
    assert loader.get_loaded("greeter") is not None
    assert loader.get_loaded("nonexistent") is None
    assert len(loader.list_loaded()) == 1


def test_unload_removes_registry_entry(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    registry = DomainRegistry()
    loader = _make_loader(registry)
    loader.load(candidate)

    result = loader.unload("greeter", "1.0.0")

    assert result.status == DomainLoadStatus.UNLOADED
    assert registry.get("greeter", "1.0.0") is None
    assert loader.get_loaded("greeter", "1.0.0") is None


def test_unload_nonexistent_raises(tmp_path):
    loader = _make_loader()
    with pytest.raises(DomainRegistryNotFound):
        loader.unload("nonexistent")


def test_unload_does_not_delete_files(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    loader = _make_loader()
    loader.load(candidate)

    loader.unload("greeter", "1.0.0")

    assert (domain_dir / "manifest.json").is_file()


def test_reload_valid_new_version(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate_v1 = make_candidate(domain_dir, "greeter", "1.0.0")
    registry = DomainRegistry()
    loader = _make_loader(registry)
    loader.load(candidate_v1)

    domain_dir_v2 = write_domain_dir(tmp_path, "greeter-v2", "2.0.0")
    (domain_dir_v2 / "manifest.json").write_text(
        json.dumps(
            {"id": "greeter", "version": "2.0.0", "author": "tester", "license": "MIT"}
        ),
        encoding="utf-8",
    )
    candidate_v2 = make_candidate(domain_dir_v2, "greeter", "2.0.0")

    result = loader.reload(candidate_v2)

    assert result.status == DomainLoadStatus.LOADED
    assert registry.get("greeter", "1.0.0") is None
    assert registry.get("greeter", "2.0.0") is not None


def test_reload_invalid_preserves_previous_version(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate_v1 = make_candidate(domain_dir, "greeter", "1.0.0")
    registry = DomainRegistry()
    loader = _make_loader(registry)
    loader.load(candidate_v1)

    bad_dir = tmp_path / "greeter-bad"
    bad_dir.mkdir()
    (bad_dir / "manifest.json").write_text("{not json", encoding="utf-8")
    import hashlib

    raw = (bad_dir / "manifest.json").read_bytes()
    checksum = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    bad_candidate = DomainCandidate(
        candidate_id="greeter:2.0.0",
        source_id="s1",
        source_kind="directory",
        location=str(bad_dir),
        manifest_path="manifest.json",
        domain_id="domain:greeter",
        detected_version="2.0.0",
        checksum=checksum,
        trusted=True,
        discovered_at=candidate_v1.discovered_at,
    )

    result = loader.reload(bad_candidate)

    assert result.status == DomainLoadStatus.FAILED
    assert registry.get("greeter", "1.0.0") is not None


def test_reload_checksum_mismatch_raises(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate_v1 = make_candidate(domain_dir, "greeter", "1.0.0")
    loader = _make_loader()
    loader.load(candidate_v1)

    domain_dir_v2 = tmp_path / "greeter-v2"
    domain_dir_v2.mkdir()
    (domain_dir_v2 / "manifest.json").write_text(
        json.dumps(
            {"id": "greeter", "version": "2.0.0", "author": "tester", "license": "MIT"}
        ),
        encoding="utf-8",
    )
    candidate_v2 = make_candidate(domain_dir_v2, "greeter", "2.0.0")
    (domain_dir_v2 / "manifest.json").write_text(
        json.dumps(
            {
                "id": "greeter",
                "version": "2.0.0",
                "author": "tampered",
                "license": "MIT",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(DomainChecksumMismatch):
        loader.reload(candidate_v2)


def test_load_rejects_non_candidate_type():
    loader = _make_loader()
    with pytest.raises(DomainLoadFailed):
        loader.load("not-a-candidate")  # type: ignore[arg-type]


def test_snapshot_reflects_loaded_state(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    loader = _make_loader()
    loader.load(candidate)

    snapshot = loader.snapshot()

    assert len(snapshot.load_results) == 1
    assert len(snapshot.known_candidates) == 1
    assert snapshot.snapshot_version == "10.4.0"


def test_loader_thread_safety(tmp_path):
    registry = DomainRegistry()
    loader = _make_loader(registry)
    errors: list[Exception] = []

    def _load_one(i: int) -> None:
        try:
            domain_dir = write_domain_dir(tmp_path, f"dom{i}", "1.0.0")
            candidate = make_candidate(
                domain_dir, f"dom{i}", "1.0.0", source_id=f"s{i}"
            )
            loader.load(candidate)
        except Exception as exc:  # noqa: BLE001 -- test boundary, collect for assertion
            errors.append(exc)

    threads = [threading.Thread(target=_load_one, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(loader.list_loaded()) == 8


# ── Atomicity: fault injection after registry.register() ───────────────────


class _GetRecordFailingRegistry(DomainRegistry):
    """Registry whose get_record() raises for one identity.

    The loader calls ``get_record`` exactly once after ``register`` (to
    build the LOADED result) — failing this call simulates a fault
    strictly after the registration has already happened.
    """

    def __init__(self, *, fail_for: tuple[str, str]) -> None:
        super().__init__()
        self._fail_for = fail_for

    def get_record(self, domain_id, version=None):
        slug = domain_id.removeprefix("domain:")
        if (slug, version) == self._fail_for:
            raise RuntimeError("simulated get_record failure")
        return super().get_record(domain_id, version)


class _FailingClock:
    """Clock that raises once call count reaches ``fail_at``."""

    def __init__(self, fail_at: int) -> None:
        self.calls = 0
        self.fail_at = fail_at

    def __call__(self) -> datetime:
        self.calls += 1
        if self.calls == self.fail_at:
            raise RuntimeError("simulated clock failure")
        return datetime.now(timezone.utc)


def test_load_rollback_on_get_record_failure_after_register(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    registry = _GetRecordFailingRegistry(fail_for=("greeter", "1.0.0"))
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )

    with pytest.raises(DomainLoadFailed):
        loader.load(candidate)

    assert registry.get("greeter", "1.0.0") is None
    assert loader.get_loaded("greeter", "1.0.0") is None
    assert loader.list_loaded() == ()


def test_load_rollback_on_clock_failure_after_register(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    registry = DomainRegistry()
    clock = _FailingClock(fail_at=2)
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry, clock=clock
    )

    with pytest.raises(DomainLoadFailed):
        loader.load(candidate)

    assert registry.get("greeter", "1.0.0") is None
    assert loader.get_loaded("greeter", "1.0.0") is None


def test_load_rollback_on_result_construction_failure(tmp_path, monkeypatch):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    registry = DomainRegistry()
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )

    real_result_cls = loader_module.DomainLoadResult

    def flaky_result(*args, **kwargs):
        if kwargs.get("status") == DomainLoadStatus.LOADED:
            raise RuntimeError("simulated construction failure")
        return real_result_cls(*args, **kwargs)

    monkeypatch.setattr(loader_module, "DomainLoadResult", flaky_result)

    with pytest.raises(DomainLoadFailed):
        loader.load(candidate)

    monkeypatch.setattr(loader_module, "DomainLoadResult", real_result_cls)
    assert registry.get("greeter", "1.0.0") is None
    assert loader.get_loaded("greeter", "1.0.0") is None


def test_load_rollback_does_not_remove_preexisting_idempotent_record(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    registry = DomainRegistry()
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )
    # Pre-register the identical definition directly (simulating that the
    # identity already existed with the same content before this load()).
    pack, _errors = loader._build_pack(candidate)
    registry.register(pack.definition)
    assert registry.get("greeter", "1.0.0") is not None

    clock = _FailingClock(fail_at=2)
    loader2 = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry, clock=clock
    )

    with pytest.raises(DomainLoadFailed):
        loader2.load(candidate)

    # The pre-existing record must survive rollback untouched.
    assert registry.get("greeter", "1.0.0") is not None


# ── Atomicity: fault injection after registry.unregister() (unload) ────────


class _DeletingLoaderDict(dict):
    """A dict whose __delitem__ raises once, to simulate an unload fault."""

    def __init__(self, *args, fail_once: bool = True, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._fail_once = fail_once

    def __delitem__(self, key) -> None:
        if self._fail_once:
            self._fail_once = False
            raise RuntimeError("simulated unload local-state failure")
        super().__delitem__(key)


def test_unload_rollback_on_failure_after_unregister(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    registry = DomainRegistry()
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )
    loader.load(candidate)
    loader._loaded = _DeletingLoaderDict(loader._loaded)

    with pytest.raises(DomainUnloadFailed):
        loader.unload("greeter", "1.0.0")

    # Registry record and loaded state must both be restored exactly.
    assert registry.get("greeter", "1.0.0") is not None
    assert loader.get_loaded("greeter", "1.0.0") is not None


# ── Reload: exact lifecycle restoration on rollback ─────────────────────────


def _load_v1(tmp_path, registry):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )
    loader.load(candidate)
    return loader, candidate


def _bad_candidate_v2(tmp_path) -> DomainCandidate:
    bad_dir = tmp_path / "greeter-bad-v2"
    bad_dir.mkdir()
    (bad_dir / "manifest.json").write_text("{not json", encoding="utf-8")
    import hashlib

    raw = (bad_dir / "manifest.json").read_bytes()
    checksum = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    return DomainCandidate(
        candidate_id="greeter:2.0.0",
        source_id="s1",
        source_kind="directory",
        location=str(bad_dir),
        manifest_path="manifest.json",
        domain_id="domain:greeter",
        detected_version="2.0.0",
        checksum=checksum,
        trusted=True,
        discovered_at=datetime.now(timezone.utc),
    )


def test_reload_restores_previous_registered_status(tmp_path):
    registry = DomainRegistry()
    loader, _candidate_v1 = _load_v1(tmp_path, registry)
    assert registry.get_record("greeter", "1.0.0").status == DomainStatus.REGISTERED

    result = loader.reload(_bad_candidate_v2(tmp_path))

    assert result.status == DomainLoadStatus.FAILED
    record = registry.get_record("greeter", "1.0.0")
    assert record is not None
    assert record.status == DomainStatus.REGISTERED


def test_reload_restores_previous_active_status(tmp_path):
    registry = DomainRegistry()
    loader, _candidate_v1 = _load_v1(tmp_path, registry)
    registry.enable("greeter", "1.0.0")
    assert registry.get_record("greeter", "1.0.0").status == DomainStatus.ACTIVE

    result = loader.reload(_bad_candidate_v2(tmp_path))

    assert result.status == DomainLoadStatus.FAILED
    record = registry.get_record("greeter", "1.0.0")
    assert record is not None
    assert record.status == DomainStatus.ACTIVE
    assert record.definition.enabled is True


def test_reload_restores_previous_disabled_status(tmp_path):
    registry = DomainRegistry()
    loader, _candidate_v1 = _load_v1(tmp_path, registry)
    registry.enable("greeter", "1.0.0")
    registry.disable("greeter", "1.0.0")
    assert registry.get_record("greeter", "1.0.0").status == DomainStatus.DISABLED

    result = loader.reload(_bad_candidate_v2(tmp_path))

    assert result.status == DomainLoadStatus.FAILED
    record = registry.get_record("greeter", "1.0.0")
    assert record is not None
    assert record.status == DomainStatus.DISABLED


def test_reload_restores_previous_degraded_status(tmp_path):
    registry = DomainRegistry()
    loader, _candidate_v1 = _load_v1(tmp_path, registry)
    previous_record = registry.get_record("greeter", "1.0.0")
    # DEGRADED is not reachable via the public registry lifecycle API, so
    # capture it via restore_record() (the same mechanism the loader uses
    # for rollback) to construct the scenario.
    degraded_record = DomainRegistryRecord(
        definition=previous_record.definition,
        status=DomainStatus.DEGRADED,
        registered_at=previous_record.registered_at,
        updated_at=previous_record.updated_at,
    )
    registry.restore_record(degraded_record)
    assert registry.get_record("greeter", "1.0.0").status == DomainStatus.DEGRADED

    result = loader.reload(_bad_candidate_v2(tmp_path))

    assert result.status == DomainLoadStatus.FAILED
    record = registry.get_record("greeter", "1.0.0")
    assert record is not None
    assert record.status == DomainStatus.DEGRADED


def test_reload_fault_after_new_register_restores_previous_exactly(tmp_path):
    registry = DomainRegistry()
    domain_dir_v1 = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate_v1 = make_candidate(domain_dir_v1, "greeter", "1.0.0")
    clock_calls = {"n": 0}

    def counting_clock():
        clock_calls["n"] += 1
        return datetime.now(timezone.utc)

    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(),
        registry=registry,
        clock=counting_clock,
    )
    loader.load(candidate_v1)
    registry.enable("greeter", "1.0.0")

    domain_dir_v2 = tmp_path / "greeter-v2-fault"
    domain_dir_v2.mkdir()
    (domain_dir_v2 / "manifest.json").write_text(
        json.dumps(
            {"id": "greeter", "version": "2.0.0", "author": "tester", "license": "MIT"}
        ),
        encoding="utf-8",
    )
    candidate_v2 = make_candidate(domain_dir_v2, "greeter", "2.0.0")

    # Fail the clock call used for the new LOADED result's loaded_at, which
    # happens right after the new version is registered.
    call_count = {"n": 0}

    def fault_after_register_clock():
        call_count["n"] += 1
        # First call: _build_pack's installed_at. Second call: post-register
        # result.loaded_at -- fail exactly there.
        if call_count["n"] == 2:
            raise RuntimeError("simulated post-register failure")
        return datetime.now(timezone.utc)

    loader._clock = fault_after_register_clock

    with pytest.raises(DomainReloadFailed):
        loader.reload(candidate_v2)

    # Exactly one version remains registered: the restored previous (ACTIVE) one.
    assert registry.get("greeter", "2.0.0") is None
    record = registry.get_record("greeter", "1.0.0")
    assert record is not None
    assert record.status == DomainStatus.ACTIVE
    assert loader.get_loaded("greeter", "1.0.0") is not None
    assert len(registry.versions("greeter")) == 1


def test_reload_invalid_preserves_previous_loaded_result_object(tmp_path):
    registry = DomainRegistry()
    loader, _candidate_v1 = _load_v1(tmp_path, registry)
    previous_result = loader.get_loaded("greeter", "1.0.0")

    loader.reload(_bad_candidate_v2(tmp_path))

    assert loader.get_loaded("greeter", "1.0.0") is previous_result


# ── Known-candidate identity: (source_id, candidate_id, checksum) ───────────


def test_known_candidates_from_different_sources_do_not_overwrite(tmp_path):
    domain_dir_a = write_domain_dir(tmp_path / "src_a", "greeter", "1.0.0")
    domain_dir_b = write_domain_dir(tmp_path / "src_b", "greeter", "1.0.0")
    candidate_a = make_candidate(
        domain_dir_a, "greeter", "1.0.0", source_id="source-a", trusted=False
    )
    candidate_b = make_candidate(
        domain_dir_b, "greeter", "1.0.0", source_id="source-b", trusted=False
    )
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=DomainRegistry()
    )

    # Both candidates share the same candidate_id ("greeter:1.0.0") but come
    # from different sources — recording one must not clobber the other.
    assert candidate_a.candidate_id == candidate_b.candidate_id
    try:
        loader.load(candidate_a)
    except DomainSourceUntrusted:
        pass
    try:
        loader.load(candidate_b)
    except DomainSourceUntrusted:
        pass

    snapshot = loader.snapshot()
    recorded_sources = {c.source_id for c in snapshot.known_candidates}
    assert recorded_sources == {"source-a", "source-b"}
    assert len(snapshot.known_candidates) == 2


def test_known_candidates_same_source_and_id_but_different_checksum_both_kept(
    tmp_path,
):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate_v1 = make_candidate(domain_dir, "greeter", "1.0.0", trusted=False)

    # Simulate re-discovery of the same (source_id, candidate_id) with
    # different manifest content -> different checksum.
    (domain_dir / "manifest.json").write_text(
        json.dumps(
            {
                "id": "greeter",
                "version": "1.0.0",
                "author": "tester-changed",
                "license": "MIT",
            }
        ),
        encoding="utf-8",
    )
    candidate_v2 = make_candidate(domain_dir, "greeter", "1.0.0", trusted=False)
    assert candidate_v1.checksum != candidate_v2.checksum
    assert candidate_v1.candidate_id == candidate_v2.candidate_id

    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=DomainRegistry()
    )
    for cand in (candidate_v1, candidate_v2):
        try:
            loader.load(cand)
        except DomainSourceUntrusted:
            pass

    snapshot = loader.snapshot()
    checksums = {c.checksum for c in snapshot.known_candidates}
    assert checksums == {candidate_v1.checksum, candidate_v2.checksum}
    assert len(snapshot.known_candidates) == 2


# ── Candidate domain_id coherence (not derived from candidate_id) ──────────


def test_manipulated_candidate_id_does_not_change_domain_identity(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    # candidate_id is renamed to something unrelated to the real domain_id;
    # loading must still succeed because coherence is checked against
    # candidate.domain_id, not by parsing candidate_id.
    renamed = DomainCandidate(
        candidate_id="totally-unrelated-label",
        source_id=candidate.source_id,
        source_kind=candidate.source_kind,
        location=candidate.location,
        manifest_path=candidate.manifest_path,
        domain_id=candidate.domain_id,
        detected_version=candidate.detected_version,
        checksum=candidate.checksum,
        trusted=candidate.trusted,
        discovered_at=candidate.discovered_at,
    )
    registry = DomainRegistry()
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )

    result = loader.load(renamed)

    assert result.status == DomainLoadStatus.LOADED
    assert registry.get("greeter", "1.0.0") is not None


def test_candidate_domain_id_mismatch_with_manifest_blocks_load(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    # Claim a different domain_id than what the (checksummed) manifest
    # actually declares -- must be rejected, not silently trusted.
    mismatched = DomainCandidate(
        candidate_id=candidate.candidate_id,
        source_id=candidate.source_id,
        source_kind=candidate.source_kind,
        location=candidate.location,
        manifest_path=candidate.manifest_path,
        domain_id="domain:not-greeter",
        detected_version=candidate.detected_version,
        checksum=candidate.checksum,
        trusted=candidate.trusted,
        discovered_at=candidate.discovered_at,
    )
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=DomainRegistry()
    )

    result = loader.load(mismatched)

    assert result.status == DomainLoadStatus.FAILED
    assert any("domain_id" in e.lower() for e in result.errors)


# ── Rollback failure itself must never be swallowed ─────────────────────────


class _RestoreStateFailingRegistry(DomainRegistry):
    """Registry whose restore_state() always raises, simulating a fault
    strictly within the rollback mechanism itself."""

    def restore_state(self, snapshot):
        raise RuntimeError("simulated restore_state failure")


class _GetRecordFailingRestoreFailingRegistry(_RestoreStateFailingRegistry):
    """Combines a post-register get_record() fault with a broken rollback,
    so both the original failure and the rollback failure are exercised."""

    def __init__(self, *, fail_for: tuple[str, str]) -> None:
        super().__init__()
        self._fail_for = fail_for

    def get_record(self, domain_id, version=None):
        slug = domain_id.removeprefix("domain:")
        if (slug, version) == self._fail_for:
            raise RuntimeError("simulated get_record failure")
        return super().get_record(domain_id, version)


def test_load_raises_rollback_failed_when_restore_state_fails(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    registry = _GetRecordFailingRestoreFailingRegistry(fail_for=("greeter", "1.0.0"))
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )

    with pytest.raises(loader_module.DomainLoadRollbackFailed) as exc_info:
        loader.load(candidate)

    details = exc_info.value.details
    assert details["original_error"] == "RuntimeError"
    assert details["rollback_error"] == "RuntimeError"
    # The error message must never leak str()/repr() of the underlying
    # exceptions or a traceback -- only safe type names.
    assert "RuntimeError" not in exc_info.value.message
    assert "simulated" not in exc_info.value.message


class _UnregisterOkThenRestoreFailsRegistry(_RestoreStateFailingRegistry):
    """Registry that unregisters normally but whose restore_state() (used
    for unload rollback) always fails."""


def test_unload_raises_rollback_failed_when_restore_state_fails(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    registry = _UnregisterOkThenRestoreFailsRegistry()
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )
    loader.load(candidate)
    loader._loaded = _DeletingLoaderDict(loader._loaded)

    with pytest.raises(loader_module.DomainUnloadRollbackFailed) as exc_info:
        loader.unload("greeter", "1.0.0")

    details = exc_info.value.details
    assert details["original_error"] == "RuntimeError"
    assert details["rollback_error"] == "RuntimeError"


class _RegisterOkThenRestoreFailsRegistry(_RestoreStateFailingRegistry):
    """Registry whose register() of the new version succeeds but whose
    get_record() for that new version fails, and whose restore_state()
    (used for reload rollback) always fails."""

    def __init__(self, *, fail_for: tuple[str, str]) -> None:
        super().__init__()
        self._fail_for = fail_for

    def get_record(self, domain_id, version=None):
        slug = domain_id.removeprefix("domain:")
        if (slug, version) == self._fail_for:
            raise RuntimeError("simulated get_record failure")
        return super().get_record(domain_id, version)


def test_reload_raises_rollback_failed_when_restore_state_fails(tmp_path):
    registry = _RegisterOkThenRestoreFailsRegistry(fail_for=("greeter", "2.0.0"))
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate_v1 = make_candidate(domain_dir, "greeter", "1.0.0")
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )
    loader.load(candidate_v1)

    domain_dir_v2 = tmp_path / "greeter-v2-rollback-fail"
    domain_dir_v2.mkdir()
    (domain_dir_v2 / "manifest.json").write_text(
        json.dumps(
            {"id": "greeter", "version": "2.0.0", "author": "tester", "license": "MIT"}
        ),
        encoding="utf-8",
    )
    candidate_v2 = make_candidate(domain_dir_v2, "greeter", "2.0.0")

    with pytest.raises(loader_module.DomainReloadRollbackFailed) as exc_info:
        loader.reload(candidate_v2)

    details = exc_info.value.details
    assert details["original_error"] == "RuntimeError"
    assert details["rollback_error"] == "RuntimeError"


# ── Snapshot rollback restores multiple records and indices ────────────────


def test_rollback_restores_other_unrelated_records_and_their_index_state(tmp_path):
    registry = DomainRegistry()
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )

    # An unrelated, already-active domain that must survive any rollback
    # untouched -- including its index entries (status/kind/capability).
    other_dir = write_domain_dir(tmp_path, "other", "1.0.0")
    other_candidate = make_candidate(other_dir, "other", "1.0.0")
    loader.load(other_candidate)
    registry.enable("other", "1.0.0")
    assert registry.get_record("other", "1.0.0").status == DomainStatus.ACTIVE

    # Now trigger a failing load for a *different* domain.
    greeter_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    greeter_candidate = make_candidate(greeter_dir, "greeter", "1.0.0")
    flaky_registry = _GetRecordFailingRegistry(fail_for=("greeter", "1.0.0"))
    # Re-point the flaky registry's store at the same underlying store so
    # "other" is visible through it too.
    flaky_registry._store = registry._store
    flaky_loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=flaky_registry
    )

    with pytest.raises(DomainLoadFailed):
        flaky_loader.load(greeter_candidate)

    # "other" must remain exactly as it was: registered, ACTIVE, findable
    # by status index and by direct lookup.
    assert registry.get("greeter", "1.0.0") is None
    other_record = registry.get_record("other", "1.0.0")
    assert other_record is not None
    assert other_record.status == DomainStatus.ACTIVE
    active_records = registry.list_records(
        query=None,
    )
    assert any(
        r.definition.id.slug == "other" and r.status == DomainStatus.ACTIVE
        for r in active_records
    )


def test_load_rollback_restores_loaded_dict_to_exact_prior_object(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "other", "1.0.0")
    candidate = make_candidate(domain_dir, "other", "1.0.0")
    registry = DomainRegistry()
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )
    loader.load(candidate)
    previous_result = loader.get_loaded("other", "1.0.0")

    domain_dir2 = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate2 = make_candidate(domain_dir2, "greeter", "1.0.0")
    flaky_registry = _GetRecordFailingRegistry(fail_for=("greeter", "1.0.0"))
    flaky_registry._store = registry._store
    flaky_loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=flaky_registry
    )
    flaky_loader._loaded = dict(loader._loaded)
    flaky_loader._known_candidates = dict(loader._known_candidates)

    with pytest.raises(DomainLoadFailed):
        flaky_loader.load(candidate2)

    assert flaky_loader.get_loaded("greeter", "1.0.0") is None
    # The unrelated, previously-loaded entry is exactly the same object.
    assert flaky_loader.get_loaded("other", "1.0.0") is previous_result


def test_known_candidates_policy_survives_failed_load(tmp_path):
    """Documented policy: _known_candidates records every attempted
    candidate and is never rolled back, even when the load itself fails
    or is rejected."""
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    registry = _GetRecordFailingRegistry(fail_for=("greeter", "1.0.0"))
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )

    with pytest.raises(DomainLoadFailed):
        loader.load(candidate)

    snapshot = loader.snapshot()
    assert candidate.candidate_id in {c.candidate_id for c in snapshot.known_candidates}
