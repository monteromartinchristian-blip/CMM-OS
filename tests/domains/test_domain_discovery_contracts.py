from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from cmm.domains.discovery_contracts import (
    DomainCandidate,
    DomainDiscoveryIssue,
    DomainDiscoveryResult,
    DomainSource,
)
from cmm.domains.enums import DomainSourceKind
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSerializationError,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
CHECKSUM = "sha256:" + "a" * 64


def _candidate(**overrides):
    defaults = {
        "candidate_id": "greeter:1.0.0",
        "source_id": "s1",
        "source_kind": DomainSourceKind.DIRECTORY,
        "location": "/roots/greeter",
        "manifest_path": "manifest.json",
        "domain_id": "domain:greeter",
        "detected_version": "1.0.0",
        "checksum": CHECKSUM,
        "trusted": True,
        "discovered_at": NOW,
    }
    defaults.update(overrides)
    return DomainCandidate(**defaults)


# ── DomainSource ─────────────────────────────────────────────────────────────


def test_domain_source_valid_construction():
    src = DomainSource(
        source_id="s1", kind=DomainSourceKind.DIRECTORY, location="/tmp/domains"
    )
    assert src.trusted is False
    assert src.priority == 0
    assert src.metadata == {}


def test_domain_source_is_frozen():
    src = DomainSource(source_id="s1", kind="directory", location="/x")
    with pytest.raises(FrozenInstanceError):
        src.priority = 5  # type: ignore[misc]


def test_domain_source_priority_rejects_bool():
    with pytest.raises(DomainContractValidationError):
        DomainSource(source_id="s1", kind="directory", location="/x", priority=True)


def test_domain_source_trusted_rejects_non_bool():
    with pytest.raises(DomainContractValidationError):
        DomainSource(source_id="s1", kind="directory", location="/x", trusted="false")


def test_domain_source_recursive_rejects_int():
    with pytest.raises(DomainContractValidationError):
        DomainSource(source_id="s1", kind="directory", location="/x", recursive=1)


def test_domain_source_metadata_accepts_boolean_values():
    src = DomainSource(
        source_id="s1", kind="directory", location="/x", metadata={"flag": True}
    )
    assert src.metadata["flag"] is True


def test_domain_source_metadata_rejects_non_json_safe():
    with pytest.raises(DomainContractValidationError):
        DomainSource(
            source_id="s1", kind="directory", location="/x", metadata={"f": object()}
        )


def test_domain_source_metadata_rejects_credentials():
    with pytest.raises(DomainContractValidationError):
        DomainSource(
            source_id="s1", kind="directory", location="/x", metadata={"password": "x"}
        )


def test_domain_source_from_dict_rejects_unknown_fields():
    with pytest.raises(DomainSerializationError):
        DomainSource.from_dict(
            {"source_id": "s1", "kind": "directory", "location": "/x", "bogus": 1}
        )


def test_domain_source_round_trip():
    src = DomainSource(
        source_id="s1",
        kind=DomainSourceKind.TEST,
        location="/tmp",
        trusted=True,
        recursive=True,
        priority=5,
        metadata={"k": "v"},
    )
    restored = DomainSource.from_dict(src.to_dict())
    assert restored == src
    assert restored.to_dict() == src.to_dict()


def test_domain_source_json_dumps():
    import json

    src = DomainSource(source_id="s1", kind="directory", location="/x")
    json.dumps(src.to_dict())


def test_domain_source_location_not_resolved_on_construction():
    # Should not raise even for a non-existent path — construction never touches disk.
    DomainSource(source_id="s1", kind="directory", location="/does/not/exist")


# ── DomainCandidate ──────────────────────────────────────────────────────────


def test_domain_candidate_valid_construction():
    c = _candidate()
    assert c.trusted is True
    assert c.checksum == CHECKSUM


def test_domain_candidate_is_frozen():
    c = _candidate()
    with pytest.raises(FrozenInstanceError):
        c.checksum = "x"  # type: ignore[misc]


def test_domain_candidate_rejects_invalid_checksum_format():
    with pytest.raises(DomainContractValidationError):
        _candidate(checksum="md5:abc")


def test_domain_candidate_rejects_naive_datetime():
    with pytest.raises(DomainContractValidationError):
        _candidate(discovered_at=datetime(2026, 1, 1))  # noqa: DTZ001


def test_domain_candidate_rejects_invalid_semver():
    with pytest.raises(DomainContractValidationError):
        _candidate(detected_version="not-a-version")


def test_domain_candidate_rejects_non_bool_trusted():
    with pytest.raises(DomainContractValidationError):
        _candidate(trusted="true")


def test_domain_candidate_domain_id_normalizes_bare_slug():
    c = _candidate(domain_id="greeter")
    assert c.domain_id == "domain:greeter"


def test_domain_candidate_domain_id_accepts_canonical_form():
    c = _candidate(domain_id="domain:greeter")
    assert c.domain_id == "domain:greeter"


def test_domain_candidate_domain_id_rejects_invalid_slug():
    with pytest.raises(DomainContractValidationError):
        _candidate(domain_id="Not Valid!")


def test_domain_candidate_domain_id_rejects_empty():
    with pytest.raises(DomainContractValidationError):
        _candidate(domain_id="")


def test_domain_candidate_metadata_accepts_bool():
    c = _candidate(metadata={"flag": False})
    assert c.metadata["flag"] is False


def test_domain_candidate_metadata_rejects_credentials():
    with pytest.raises(DomainContractValidationError):
        _candidate(metadata={"api_key": "abc"})


def test_domain_candidate_from_dict_rejects_unknown_fields():
    data = _candidate().to_dict()
    data["bogus"] = 1
    with pytest.raises(DomainSerializationError):
        DomainCandidate.from_dict(data)


def test_domain_candidate_round_trip():
    c = _candidate()
    restored = DomainCandidate.from_dict(c.to_dict())
    assert restored == c
    assert restored.to_dict() == c.to_dict()


def test_domain_candidate_json_dumps():
    import json

    json.dumps(_candidate().to_dict())


# ── DomainDiscoveryIssue ─────────────────────────────────────────────────────


def test_domain_discovery_issue_valid_construction():
    issue = DomainDiscoveryIssue(
        source_id="s1", location="/x", code="test_code", message="msg", blocking=True
    )
    assert issue.blocking is True


def test_domain_discovery_issue_rejects_non_bool_blocking():
    with pytest.raises(DomainContractValidationError):
        DomainDiscoveryIssue(
            source_id="s1", location="/x", code="c", message="m", blocking=1
        )


def test_domain_discovery_issue_rejects_overlong_message():
    with pytest.raises(DomainContractValidationError):
        DomainDiscoveryIssue(
            source_id="s1",
            location="/x",
            code="c",
            message="x" * 2001,
            blocking=False,
        )


def test_domain_discovery_issue_round_trip():
    issue = DomainDiscoveryIssue(
        source_id="s1", location="/x", code="c", message="m", blocking=False
    )
    restored = DomainDiscoveryIssue.from_dict(issue.to_dict())
    assert restored == issue


# ── DomainDiscoveryResult ────────────────────────────────────────────────────


def test_domain_discovery_result_deterministic_ordering():
    c1 = _candidate(candidate_id="b:1.0.0", source_id="s2")
    c2 = _candidate(candidate_id="a:1.0.0", source_id="s1")
    i1 = DomainDiscoveryIssue(
        source_id="s2", location="/y", code="z", message="m", blocking=False
    )
    i2 = DomainDiscoveryIssue(
        source_id="s1", location="/x", code="a", message="m", blocking=False
    )
    result = DomainDiscoveryResult(
        candidates=(c1, c2),
        issues=(i1, i2),
        scanned_sources=("s2", "s1"),
        discovered_at=NOW,
    )
    assert [c.source_id for c in result.candidates] == ["s1", "s2"]
    assert [i.source_id for i in result.issues] == ["s1", "s2"]
    assert result.scanned_sources == ("s1", "s2")


def test_domain_discovery_result_rejects_naive_datetime():
    with pytest.raises(DomainContractValidationError):
        DomainDiscoveryResult(
            candidates=(),
            issues=(),
            scanned_sources=(),
            discovered_at=datetime(2026, 1, 1),  # noqa: DTZ001
        )


def test_domain_discovery_result_round_trip():
    c = _candidate()
    issue = DomainDiscoveryIssue(
        source_id="s1", location="/x", code="c", message="m", blocking=False
    )
    result = DomainDiscoveryResult(
        candidates=(c,), issues=(issue,), scanned_sources=("s1",), discovered_at=NOW
    )
    restored = DomainDiscoveryResult.from_dict(result.to_dict())
    assert restored.to_dict() == result.to_dict()


def test_domain_discovery_result_json_dumps():
    import json

    result = DomainDiscoveryResult(
        candidates=(_candidate(),),
        issues=(),
        scanned_sources=("s1",),
        discovered_at=NOW,
    )
    json.dumps(result.to_dict())
