"""Confidentiality test for Phase 7.11.

Verifies that secrets never appear in any file written by the persistence
layer, including:
- Execution JSON
- Log JSONL
- Artifact JSON
- Index JSON

The test constructs a context containing known secret values and then
searches for those literal strings in every file under the storage tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.observability.models import (
    CURRENT_SCHEMA_VERSION,
    ValidationExecutionRecord,
    ValidationLogEntry,
)
from cmm.validation.observability.repository import LocalValidationRepository
from cmm.validation.observability.sanitization import sanitize_validation_data

_SECRETS = [
    "super-secret-api-key",
    "Bearer secret-token-xyz",
    "hunter2",
]

_KNOWN_SENSITIVE_KEYS = {
    "API_KEY": _SECRETS[0],
    "Authorization": _SECRETS[1],
    "password": _SECRETS[2],
}


def _find_secrets_in_tree(storage_root: Path) -> list[tuple[str, Path]]:
    """Return list of (secret, file) where the secret appears verbatim."""
    hits: list[tuple[str, Path]] = []
    for fpath in storage_root.rglob("*"):
        if not fpath.is_file():
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for secret in _SECRETS:
            if secret in content:
                hits.append((secret, fpath))
    return hits


def test_secrets_never_appear_on_disk(tmp_path: Path) -> None:
    """
    Build an execution record, log entries, and an artifact that all
    contain known secrets in their metadata / environment / content,
    sanitise them, persist them, then scan the storage tree to confirm
    no secret string survives to disk.
    """
    store_root = tmp_path / "secret_validation_store"
    repo = LocalValidationRepository(store_root)
    vid = "validation-confidentiality-001"

    # --- Build and persist sanitised execution record ---
    raw_meta = dict(_KNOWN_SENSITIVE_KEYS)
    raw_meta["safe_field"] = "this-is-safe"
    sanitised_meta = sanitize_validation_data(raw_meta)

    record = ValidationExecutionRecord(
        id=vid,
        schema_version=CURRENT_SCHEMA_VERSION,
        status="passed",
        metadata=sanitised_meta,
        started_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
        completed_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
    )
    repo.save_execution(record)

    # --- Build and persist sanitised log entries ---
    for secret_key, secret_val in _KNOWN_SENSITIVE_KEYS.items():
        log_meta = sanitize_validation_data({secret_key: secret_val, "safe": "value"})
        entry = ValidationLogEntry.new(
            validation_id=vid,
            level="info",
            component="test",
            event="validation.started",
            message="Log with sanitised metadata",
            metadata=log_meta,
        )
        repo.save_log(entry)

    # --- Build and persist sanitised artifact ---
    raw_content = dict(_KNOWN_SENSITIVE_KEYS)
    raw_content["normal"] = "safe-content"
    sanitised_content = sanitize_validation_data(raw_content)

    from datetime import datetime, timezone

    artifact = ValidationArtifact(
        id="artifact-secret-test",
        kind="security_report",
        source="test",
        content=sanitised_content,
        created_at=datetime.now(timezone.utc),
    )
    repo.save_artifact(vid, artifact)

    # --- Scan storage tree for secrets ---
    hits = _find_secrets_in_tree(store_root)

    if hits:
        details = "\n".join(f"  secret={s!r} found in {p}" for s, p in hits)
        pytest.fail(
            f"Found {len(hits)} secret(s) on disk after sanitisation:\n{details}"
        )


def test_secret_not_in_index(tmp_path: Path) -> None:
    """Specifically check the index.json file."""
    store_root = tmp_path / "secret_index_store"
    repo = LocalValidationRepository(store_root)
    vid = "validation-index-secret-test"

    sanitised_meta = sanitize_validation_data(
        {"token": _SECRETS[0], "safe": "safe_value"}
    )
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    record = ValidationExecutionRecord(
        id=vid,
        schema_version=CURRENT_SCHEMA_VERSION,
        status="passed",
        metadata=sanitised_meta,
        started_at=now,
        completed_at=now,
    )
    repo.save_execution(record)

    index_path = store_root / "index.json"
    assert index_path.exists(), "Index file was not created"
    index_content = index_path.read_text(encoding="utf-8")

    for secret in _SECRETS:
        assert secret not in index_content, f"Secret {secret!r} found in index.json"
    assert "safe_value" not in index_content  # metadata not in compact index


def test_secret_not_in_logs(tmp_path: Path) -> None:
    """Specifically verify the JSONL log file."""
    store_root = tmp_path / "secret_log_store"
    repo = LocalValidationRepository(store_root)
    vid = "validation-log-secret-test"

    # Save a baseline record
    record = ValidationExecutionRecord(
        id=vid,
        schema_version=CURRENT_SCHEMA_VERSION,
        status="running",
    )
    repo.save_execution(record)

    for key, val in _KNOWN_SENSITIVE_KEYS.items():
        sanitised = sanitize_validation_data({key: val})
        entry = ValidationLogEntry.new(
            validation_id=vid,
            level="info",
            component="test",
            event="validation.step.started",
            message="Step with secret metadata",
            metadata=sanitised,
        )
        repo.save_log(entry)

    log_path = store_root / "logs" / f"{vid}.jsonl"
    assert log_path.exists(), "Log JSONL was not created"
    log_content = log_path.read_text(encoding="utf-8")

    for secret in _SECRETS:
        assert secret not in log_content, f"Secret {secret!r} found in JSONL log"


def test_secret_not_in_artifact_json(tmp_path: Path) -> None:
    """Specifically verify the artifact JSON file."""
    store_root = tmp_path / "secret_artifact_store"
    repo = LocalValidationRepository(store_root)
    vid = "validation-artifact-secret-test"

    from datetime import datetime, timezone

    sanitised_content = sanitize_validation_data(
        {"api_key": _SECRETS[0], "description": "ok"}
    )
    artifact = ValidationArtifact(
        id="art-secret",
        kind="report",
        source="test",
        content=sanitised_content,
        created_at=datetime.now(timezone.utc),
    )
    repo.save_artifact(vid, artifact)

    artifact_path = store_root / "artifacts" / vid / "art-secret.json"
    assert artifact_path.exists(), "Artifact JSON was not created"
    artifact_content = artifact_path.read_text(encoding="utf-8")

    for secret in _SECRETS:
        assert secret not in artifact_content, (
            f"Secret {secret!r} found in artifact JSON"
        )
