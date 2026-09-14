from __future__ import annotations

import json

from cmm.domains.discovery_contracts import DomainCandidate, DomainSource
from cmm.domains.enums import DomainLoadStatus
from cmm.domains.loader import DeclarativeDomainLoader
from cmm.domains.loader_contracts import DomainLoaderSnapshot, DomainLoadResult
from cmm.domains.manifest_reader import JsonDomainManifestReader
from cmm.domains.registry import DomainRegistry

from ._loader_helpers import make_candidate, write_domain_dir


def test_domain_source_full_json_round_trip():
    src = DomainSource(
        source_id="s1", kind="directory", location="/x", trusted=True, priority=3
    )
    text = json.dumps(src.to_dict())
    restored = DomainSource.from_dict(json.loads(text))
    assert restored == src


def test_domain_candidate_full_json_round_trip(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    text = json.dumps(candidate.to_dict())
    restored = DomainCandidate.from_dict(json.loads(text))
    assert restored.to_dict() == candidate.to_dict()


def test_domain_load_result_full_json_round_trip(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    registry = DomainRegistry()
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=registry
    )
    result = loader.load(candidate)

    text = json.dumps(result.to_dict())
    restored = DomainLoadResult.from_dict(json.loads(text))

    assert restored.status == DomainLoadStatus.LOADED
    assert restored.to_dict() == result.to_dict()


def test_domain_loader_snapshot_full_json_round_trip(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=DomainRegistry()
    )
    loader.load(candidate)

    snapshot = loader.snapshot()
    text = json.dumps(snapshot.to_dict())
    restored = DomainLoaderSnapshot.from_dict(json.loads(text))

    assert restored.to_dict() == snapshot.to_dict()


def test_unloaded_result_serializes_without_pack_or_record(tmp_path):
    domain_dir = write_domain_dir(tmp_path, "greeter", "1.0.0")
    candidate = make_candidate(domain_dir, "greeter", "1.0.0")
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(), registry=DomainRegistry()
    )
    loader.load(candidate)
    result = loader.unload("greeter", "1.0.0")

    data = result.to_dict()
    assert data["pack"] is None
    assert data["registry_record"] is None
    restored = DomainLoadResult.from_dict(data)
    assert restored.pack is None
    assert restored.registry_record is None
