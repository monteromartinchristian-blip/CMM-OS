from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.enums import DomainLoadStatus
from cmm.domains.errors import DomainContractValidationError, DomainSerializationError
from cmm.domains.loader_contracts import DomainLoaderSnapshot, DomainLoadResult

from ._loader_helpers import (
    make_candidate,
    make_pack,
    make_registry_record,
    write_domain_dir,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _candidate(tmp_path, slug="greeter", version="1.0.0"):
    domain_dir = write_domain_dir(tmp_path, slug, version)
    return make_candidate(domain_dir, slug, version)


def test_loaded_requires_pack_and_registry_record(tmp_path):
    candidate = _candidate(tmp_path)
    with pytest.raises(DomainContractValidationError):
        DomainLoadResult(
            candidate=candidate,
            status=DomainLoadStatus.LOADED,
            pack=None,
            registry_record=None,
            errors=(),
            warnings=(),
            loaded_at=NOW,
        )


def test_failed_requires_at_least_one_error(tmp_path):
    candidate = _candidate(tmp_path)
    with pytest.raises(DomainContractValidationError):
        DomainLoadResult(
            candidate=candidate,
            status=DomainLoadStatus.FAILED,
            pack=None,
            registry_record=None,
            errors=(),
            warnings=(),
            loaded_at=NOW,
        )


def test_rejected_requires_at_least_one_error(tmp_path):
    candidate = _candidate(tmp_path)
    with pytest.raises(DomainContractValidationError):
        DomainLoadResult(
            candidate=candidate,
            status=DomainLoadStatus.REJECTED,
            pack=None,
            registry_record=None,
            errors=(),
            warnings=(),
            loaded_at=NOW,
        )


def test_unloaded_must_not_carry_active_record(tmp_path):
    candidate = _candidate(tmp_path)
    pack = make_pack("greeter", "1.0.0")
    with pytest.raises(DomainContractValidationError):
        DomainLoadResult(
            candidate=candidate,
            status=DomainLoadStatus.UNLOADED,
            pack=pack,
            registry_record=None,
            errors=(),
            warnings=(),
            loaded_at=NOW,
        )


def test_valid_loaded_result(tmp_path):
    candidate = _candidate(tmp_path)
    pack = make_pack("greeter", "1.0.0")
    record = make_registry_record("greeter", "1.0.0")
    result = DomainLoadResult(
        candidate=candidate,
        status=DomainLoadStatus.LOADED,
        pack=pack,
        registry_record=record,
        errors=(),
        warnings=(),
        loaded_at=NOW,
    )
    assert result.status == DomainLoadStatus.LOADED


def test_valid_failed_result(tmp_path):
    candidate = _candidate(tmp_path)
    result = DomainLoadResult(
        candidate=candidate,
        status=DomainLoadStatus.FAILED,
        pack=None,
        registry_record=None,
        errors=("boom",),
        warnings=(),
        loaded_at=NOW,
    )
    assert result.errors == ("boom",)


def test_load_result_rejects_naive_datetime(tmp_path):
    candidate = _candidate(tmp_path)
    with pytest.raises(DomainContractValidationError):
        DomainLoadResult(
            candidate=candidate,
            status=DomainLoadStatus.UNLOADED,
            pack=None,
            registry_record=None,
            errors=(),
            warnings=(),
            loaded_at=datetime(2026, 1, 1),  # noqa: DTZ001
        )


def test_load_result_round_trip(tmp_path):
    candidate = _candidate(tmp_path)
    pack = make_pack("greeter", "1.0.0")
    record = make_registry_record("greeter", "1.0.0")
    result = DomainLoadResult(
        candidate=candidate,
        status=DomainLoadStatus.LOADED,
        pack=pack,
        registry_record=record,
        errors=(),
        warnings=("warn",),
        loaded_at=NOW,
    )
    restored = DomainLoadResult.from_dict(result.to_dict())
    assert restored.to_dict() == result.to_dict()


def test_load_result_from_dict_rejects_unknown_fields(tmp_path):
    candidate = _candidate(tmp_path)
    data = DomainLoadResult(
        candidate=candidate,
        status=DomainLoadStatus.UNLOADED,
        pack=None,
        registry_record=None,
        errors=(),
        warnings=(),
        loaded_at=NOW,
    ).to_dict()
    data["bogus"] = 1
    with pytest.raises(DomainSerializationError):
        DomainLoadResult.from_dict(data)


def test_load_result_json_dumps(tmp_path):
    import json

    candidate = _candidate(tmp_path)
    pack = make_pack("greeter", "1.0.0")
    record = make_registry_record("greeter", "1.0.0")
    result = DomainLoadResult(
        candidate=candidate,
        status=DomainLoadStatus.LOADED,
        pack=pack,
        registry_record=record,
        errors=(),
        warnings=(),
        loaded_at=NOW,
    )
    json.dumps(result.to_dict())


# ── DomainLoaderSnapshot ─────────────────────────────────────────────────────


def test_snapshot_valid_construction(tmp_path):
    candidate = _candidate(tmp_path)
    snapshot = DomainLoaderSnapshot(
        known_candidates=(candidate,), load_results=(), captured_at=NOW
    )
    assert snapshot.snapshot_version == "10.4.0"


def test_snapshot_rejects_naive_datetime(tmp_path):
    candidate = _candidate(tmp_path)
    with pytest.raises(DomainContractValidationError):
        DomainLoaderSnapshot(
            known_candidates=(candidate,),
            load_results=(),
            captured_at=datetime(2026, 1, 1),  # noqa: DTZ001
        )


def test_snapshot_round_trip(tmp_path):
    candidate = _candidate(tmp_path)
    pack = make_pack("greeter", "1.0.0")
    record = make_registry_record("greeter", "1.0.0")
    result = DomainLoadResult(
        candidate=candidate,
        status=DomainLoadStatus.LOADED,
        pack=pack,
        registry_record=record,
        errors=(),
        warnings=(),
        loaded_at=NOW,
    )
    snapshot = DomainLoaderSnapshot(
        known_candidates=(candidate,), load_results=(result,), captured_at=NOW
    )
    restored = DomainLoaderSnapshot.from_dict(snapshot.to_dict())
    assert restored.to_dict() == snapshot.to_dict()


def test_snapshot_json_dumps(tmp_path):
    import json

    candidate = _candidate(tmp_path)
    snapshot = DomainLoaderSnapshot(
        known_candidates=(candidate,), load_results=(), captured_at=NOW
    )
    json.dumps(snapshot.to_dict())
