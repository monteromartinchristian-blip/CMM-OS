"""Phase 10.3 – Tests for Registry Contracts."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.errors import DomainContractValidationError, DomainSerializationError
from cmm.domains.registry_contracts import (
    DomainQuery,
    DomainRegistryRecord,
    DomainRegistrySnapshot,
    DomainValidationResult,
    _is_json_safe,
    compare_versions_desc,
    parse_semver,
)


def _make_defn(
    slug: str = "test", version: str = "1.0.0", kind: DomainKind = DomainKind.CORE
) -> DomainDefinition:
    return DomainDefinition(
        id=f"domain:{slug}",
        name=slug,
        display_name=f"Test {slug}",
        version=version,
        kind=kind,
        description="Test domain",
        manifest_id=f"manifest:{slug}:{version}",
    )


def _make_record(
    slug: str = "test",
    version: str = "1.0.0",
    status: DomainStatus = DomainStatus.REGISTERED,
) -> DomainRegistryRecord:
    ts = datetime.now(timezone.utc)
    return DomainRegistryRecord(
        definition=_make_defn(slug, version),
        status=status,
        registered_at=ts,
        updated_at=ts,
    )


# ── Semantic Version ───────────────────────────────────────────────────────────


class TestSemanticVersion:
    def test_parse_canonical(self) -> None:
        sv = parse_semver("1.0.0")
        assert sv.major == 1

    def test_1_10_0_greater_than_1_9_0(self) -> None:
        assert parse_semver("1.10.0") > parse_semver("1.9.0")

    def test_prerelease_ordering(self) -> None:
        versions = [
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
            "1.0.0",
        ]
        for i in range(len(versions) - 1):
            assert parse_semver(versions[i]) < parse_semver(versions[i + 1]), (
                f"{versions[i]} < {versions[i + 1]}"
            )

    def test_compare_versions_desc(self) -> None:
        assert compare_versions_desc("2.0.0", "1.0.0") == -1
        assert compare_versions_desc("1.0.0", "2.0.0") == 1
        assert compare_versions_desc("1.0.0", "1.0.0") == 0


# ── DomainQuery ────────────────────────────────────────────────────────────────


class TestDomainQuery:
    def test_default_construction(self) -> None:
        q = DomainQuery()
        assert q.kinds == ()
        assert q.include_experimental is False

    def test_enabled_must_be_strict_bool(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainQuery(enabled=1)  # type: ignore[arg-type]

    def test_metadata_json_safe(self) -> None:
        q = DomainQuery(metadata={"name": "value", "num": 42})
        assert q.metadata["name"] == "value"

    def test_metadata_sensitive_keys_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainQuery(metadata={"api_secret": "value"})

    def test_immutable(self) -> None:
        q = DomainQuery(kinds=(DomainKind.CORE,))
        with pytest.raises(FrozenInstanceError):
            q.kinds = ()  # type: ignore[misc]

    def test_from_dict_unknown_fields_rejected(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainQuery.from_dict({"unknown_field": "value"})

    def test_json_serialization(self) -> None:
        q = DomainQuery(kinds=(DomainKind.CORE,), metadata={"k": "v"})
        js = json.dumps(q.to_dict())
        assert isinstance(js, str)
        DomainQuery.from_dict(json.loads(js))

    def test_boolean_metadata_accepted(self) -> None:
        q = DomainQuery(metadata={"enabled_feature": True})
        assert q.metadata["enabled_feature"] is True
        js = json.dumps(q.to_dict())
        assert isinstance(js, str)
        assert json.loads(js)["metadata"]["enabled_feature"] is True

    def test_boolean_metadata_does_not_leak_into_strict_bool_fields(self) -> None:
        """Booleans are JSON-safe in free-form metadata, but that must not
        weaken strict bool validation on dedicated bool fields like `enabled`."""
        with pytest.raises(DomainContractValidationError):
            DomainQuery(enabled=1)  # type: ignore[arg-type]
        q = DomainQuery(metadata={"key": True}, enabled=True)
        assert q.metadata["key"] is True
        assert q.enabled is True

    def test_empty_string_capability_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainQuery(capabilities=("",))


# ── DomainValidationResult ─────────────────────────────────────────────────────


class TestDomainValidationResult:
    def test_valid_construction(self) -> None:
        result = DomainValidationResult(domain_id="test", version="1.0.0", valid=True)
        assert result.valid is True
        assert result.checked_at.tzinfo is not None

    def test_valid_with_errors_raises(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainValidationResult(
                domain_id="test", version="1.0.0", valid=True, errors=("err",)
            )

    def test_checked_at_must_be_tz_aware(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainValidationResult(
                domain_id="test",
                version="1.0.0",
                valid=True,
                checked_at=datetime(2024, 1, 1),  # noqa: DTZ001
            )

    def test_invalid_with_all_fields(self) -> None:
        result = DomainValidationResult(
            domain_id="test",
            version="1.0.0",
            valid=False,
            errors=("bad",),
            warnings=("warn",),
            missing_dependencies=("x",),
            conflicts=("c",),
        )
        assert result.valid is False

    def test_to_dict_and_from_dict_round_trip(self) -> None:
        result = DomainValidationResult(
            domain_id="test",
            version="1.0.0",
            valid=False,
            errors=("bad",),
        )
        d = result.to_dict()
        result2 = DomainValidationResult.from_dict(d)
        assert result2.valid == result.valid

    def test_from_dict_unknown_fields(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainValidationResult.from_dict(
                {
                    "domain_id": "t",
                    "version": "1.0.0",
                    "valid": True,
                    "checked_at": "2024-01-01T00:00:00+00:00",
                    "extra": True,
                }
            )

    def test_from_dict_missing_required(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainValidationResult.from_dict({"domain_id": "test"})

    def test_from_dict_non_bool_valid(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainValidationResult.from_dict(
                {
                    "domain_id": "t",
                    "version": "1.0.0",
                    "valid": "true",
                    "checked_at": "2024-01-01T00:00:00+00:00",
                }
            )

    def test_from_dict_naive_datetime_rejected(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainValidationResult.from_dict(
                {
                    "domain_id": "t",
                    "version": "1.0.0",
                    "valid": True,
                    "checked_at": "2024-01-01T00:00:00",
                }
            )

    def test_json_serialization(self) -> None:
        result = DomainValidationResult(domain_id="test", version="1.0.0", valid=True)
        js = json.dumps(result.to_dict(), default=str)
        assert isinstance(js, str)

    def test_boolean_metadata_accepted(self) -> None:
        result = DomainValidationResult(
            domain_id="test", version="1.0.0", valid=True, metadata={"cached": False}
        )
        assert result.metadata["cached"] is False
        js = json.dumps(result.to_dict(), default=str)
        assert json.loads(js)["metadata"]["cached"] is False

    def test_valid_must_stay_strict_bool_despite_metadata_booleans(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainValidationResult.from_dict(
                {
                    "domain_id": "t",
                    "version": "1.0.0",
                    "valid": 1,
                    "checked_at": "2024-01-01T00:00:00+00:00",
                }
            )

    def test_from_dict_coercions_rejected(self) -> None:
        for bad in [123, True, False]:
            with pytest.raises(DomainSerializationError):
                DomainValidationResult.from_dict(
                    {
                        "domain_id": bad,
                        "version": "1.0.0",
                        "valid": True,
                        "checked_at": "2024-01-01T00:00:00+00:00",
                    }
                )
        for bad in [100, False, True]:
            with pytest.raises(DomainSerializationError):
                DomainValidationResult.from_dict(
                    {
                        "domain_id": "t",
                        "version": bad,
                        "valid": True,
                        "checked_at": "2024-01-01T00:00:00+00:00",
                    }
                )
        for bad in ["error", [1], [None], [{}]]:
            with pytest.raises(DomainSerializationError):
                DomainValidationResult.from_dict(
                    {
                        "domain_id": "t",
                        "version": "1.0.0",
                        "valid": False,
                        "errors": bad,
                        "checked_at": "2024-01-01T00:00:00+00:00",
                    }
                )


# ── DomainRegistryRecord ──────────────────────────────────────────────────────


class TestDomainRegistryRecord:
    def test_construction(self) -> None:
        ts = datetime.now(timezone.utc)
        rec = DomainRegistryRecord(
            definition=_make_defn("x"),
            status=DomainStatus.REGISTERED,
            registered_at=ts,
            updated_at=ts,
        )
        assert rec.status == DomainStatus.REGISTERED
        assert rec.definition.id.slug == "x"

    def test_immutable(self) -> None:
        ts = datetime.now(timezone.utc)
        rec = DomainRegistryRecord(
            definition=_make_defn("x"),
            status=DomainStatus.REGISTERED,
            registered_at=ts,
            updated_at=ts,
        )
        with pytest.raises(FrozenInstanceError):
            rec.status = DomainStatus.ACTIVE  # type: ignore[misc]

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainRegistryRecord(
                definition=_make_defn("x"),
                status=DomainStatus.REGISTERED,
                registered_at=datetime(2024, 1, 1),  # noqa: DTZ001
                updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )

    def test_updated_before_registered_rejected(self) -> None:
        ts1 = datetime(2024, 6, 1, tzinfo=timezone.utc)
        ts2 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        with pytest.raises(DomainContractValidationError):
            DomainRegistryRecord(
                definition=_make_defn("x"),
                status=DomainStatus.REGISTERED,
                registered_at=ts1,
                updated_at=ts2,
            )

    def test_to_dict_and_from_dict_round_trip(self) -> None:
        ts = datetime.now(timezone.utc)
        rec = DomainRegistryRecord(
            definition=_make_defn("y", "3.0.0"),
            status=DomainStatus.ACTIVE,
            registered_at=ts,
            updated_at=ts,
        )
        d = rec.to_dict()
        rec2 = DomainRegistryRecord.from_dict(d)
        assert rec2.status == rec.status
        assert rec2.definition.id.slug == "y"

    def test_from_dict_unknown_fields(self) -> None:
        ts = "2024-01-01T00:00:00+00:00"
        with pytest.raises(DomainSerializationError):
            DomainRegistryRecord.from_dict(
                {
                    "definition": _make_defn("x").to_dict(),
                    "status": "registered",
                    "registered_at": ts,
                    "updated_at": ts,
                    "extra": True,
                }
            )

    def test_json_serialization(self) -> None:
        ts = datetime.now(timezone.utc)
        rec = DomainRegistryRecord(
            definition=_make_defn("z"),
            status=DomainStatus.REGISTERED,
            registered_at=ts,
            updated_at=ts,
        )
        js = json.dumps(rec.to_dict(), default=str)
        assert isinstance(js, str)


# ── DomainRegistrySnapshot ─────────────────────────────────────────────────────


class TestDomainRegistrySnapshot:
    def test_construction(self) -> None:
        rec = _make_record("test-a")
        snapshot = DomainRegistrySnapshot(
            captured_at=datetime.now(timezone.utc), records=(rec,)
        )
        assert snapshot.snapshot_version == "10.3.0"
        assert len(snapshot.records) == 1
        assert snapshot.definitions[0].id.slug == "test-a"

    def test_deterministic_sort(self) -> None:
        rec_b = _make_record("b", "1.0.0")
        rec_a = _make_record("a", "1.0.0")
        snapshot = DomainRegistrySnapshot(
            captured_at=datetime.now(timezone.utc), records=(rec_b, rec_a)
        )
        assert snapshot.records[0].definition.id.slug == "a"
        assert snapshot.records[1].definition.id.slug == "b"

    def test_version_desc_sort_within_same_domain(self) -> None:
        rec_v2 = _make_record("test", "2.0.0")
        rec_v1 = _make_record("test", "1.0.0")
        snapshot = DomainRegistrySnapshot(
            captured_at=datetime.now(timezone.utc), records=(rec_v1, rec_v2)
        )
        assert snapshot.records[0].definition.version == "2.0.0"
        assert snapshot.records[1].definition.version == "1.0.0"

    def test_captured_at_tz_aware(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainRegistrySnapshot(
                captured_at=datetime(2024, 1, 1),  # noqa: DTZ001
                records=(),
            )

    def test_captured_at_normalized_utc(self) -> None:
        from datetime import timedelta

        tz_east = timezone(timedelta(hours=5))
        dt = datetime(2024, 6, 15, tzinfo=tz_east)
        snapshot = DomainRegistrySnapshot(captured_at=dt, records=())
        assert snapshot.captured_at.tzinfo == timezone.utc

    def test_immutable(self) -> None:
        snapshot = DomainRegistrySnapshot(
            captured_at=datetime.now(timezone.utc), records=()
        )
        with pytest.raises(FrozenInstanceError):
            snapshot.snapshot_version = "99"  # type: ignore[misc]

    def test_to_dict(self) -> None:
        rec = _make_record("x")
        snapshot = DomainRegistrySnapshot(
            captured_at=datetime(2024, 1, 1, tzinfo=timezone.utc), records=(rec,)
        )
        d = snapshot.to_dict()
        assert d["snapshot_version"] == "10.3.0"
        assert len(d["records"]) == 1

    def test_from_dict_round_trip(self) -> None:
        rec = _make_record("y", "3.2.1")
        snapshot = DomainRegistrySnapshot(
            captured_at=datetime(2024, 6, 1, tzinfo=timezone.utc), records=(rec,)
        )
        d = snapshot.to_dict()
        snapshot2 = DomainRegistrySnapshot.from_dict(d)
        assert snapshot2.captured_at == snapshot.captured_at
        assert len(snapshot2.records) == 1

    def test_json_serialization(self) -> None:
        rec = _make_record("z")
        snapshot = DomainRegistrySnapshot(
            captured_at=datetime.now(timezone.utc), records=(rec,)
        )
        js = json.dumps(snapshot.to_dict(), default=str)
        assert isinstance(js, str)

    def test_from_dict_naive_datetime_rejected(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainRegistrySnapshot.from_dict(
                {"captured_at": "2024-01-01T00:00:00", "records": []}
            )


# ── Regressions ────────────────────────────────────────────────────────────────


class TestRegressions:
    def test_1_10_0_not_before_1_9_0(self) -> None:
        assert parse_semver("1.10.0") > parse_semver("1.9.0")

    def test_false_not_converted_to_true(self) -> None:
        with pytest.raises((DomainContractValidationError, DomainSerializationError)):
            DomainQuery(enabled="false")  # type: ignore[arg-type]

    def test_enabled_1_rejected(self) -> None:
        with pytest.raises((DomainContractValidationError, DomainSerializationError)):
            DomainQuery(enabled=1)  # type: ignore[arg-type]

    def test_datetime_naive_rejected_in_validation_result(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainValidationResult(
                domain_id="test",
                version="1.0.0",
                valid=True,
                checked_at=datetime(2024, 1, 1),  # noqa: DTZ001
            )

    def test_datetime_naive_rejected_in_snapshot(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainRegistrySnapshot(
                captured_at=datetime(2024, 1, 1),  # noqa: DTZ001
                records=(),
            )

    def test_string_capability_not_treated_as_sequence(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainQuery(capabilities="string")  # type: ignore[arg-type]

    def test_empty_string_identifiers_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainQuery(capabilities=("",))


# ── JSON-safe metadata ──────────────────────────────────────────────────────────


class TestJsonSafeMetadata:
    """Booleans are JSON-safe values and must be accepted in free-form metadata."""

    def test_bool_is_json_safe(self) -> None:
        assert _is_json_safe(True) is True
        assert _is_json_safe(False) is True

    def test_bool_inside_containers_is_json_safe(self) -> None:
        assert _is_json_safe({"flag": True}) is True
        assert _is_json_safe([False, True]) is True

    def test_non_json_types_still_rejected(self) -> None:
        assert _is_json_safe(object()) is False
        assert _is_json_safe({1, 2, 3}) is False
