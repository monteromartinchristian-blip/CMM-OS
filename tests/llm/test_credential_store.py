"""Contract tests for the provider credential store (Plan 3 Task 2).

The normal suite uses the in-memory fake: Registry-shaped consumers
receive only ``keychain://`` refs, never secret material. Keychain
command-construction tests use a mocked runner: the real macOS
keychain is NEVER touched here.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from kernel.llm.credential_store import (
    SERVICE_NAME,
    CredentialStore,
    InMemoryCredentialStore,
    MacOSKeychainCredentialStore,
    credential_ref,
)

_SECRET = "test-secret-value-xyz-123"


@dataclass(frozen=True, slots=True)
class _RegistryEntry:
    """Registry-shaped consumer: carries only a credential ref."""

    provider_id: str
    credential_ref: str


def _completed(returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["security"], returncode=returncode, stdout="", stderr=""
    )


def test_credential_ref_format() -> None:
    assert (
        credential_ref("deepseek", "main") == "keychain://cmm/providers/deepseek/main"
    )


def test_credential_ref_normalizes_case_and_whitespace() -> None:
    assert (
        credential_ref("  DeepSeek ", " Main ")
        == "keychain://cmm/providers/deepseek/main"
    )


@pytest.mark.parametrize(
    ("provider_id", "account"),
    [("", "main"), ("   ", "main"), ("deepseek", ""), ("deepseek", "  ")],
)
def test_credential_ref_rejects_blank(provider_id: str, account: str) -> None:
    with pytest.raises(ValueError):
        credential_ref(provider_id, account)


@pytest.mark.parametrize("store_cls", [InMemoryCredentialStore])
def test_put_rejects_blank_secret(store_cls: type) -> None:
    store: CredentialStore = store_cls()
    with pytest.raises(ValueError):
        store.put("deepseek", "main", "   ")


@pytest.mark.parametrize("store_cls", [InMemoryCredentialStore])
@pytest.mark.parametrize(
    ("provider_id", "account"),
    [("", "main"), ("deepseek", ""), ("  ", "main")],
)
def test_put_rejects_blank_ids(store_cls: type, provider_id: str, account: str) -> None:
    store: CredentialStore = store_cls()
    with pytest.raises(ValueError):
        store.put(provider_id, account, _SECRET)


def test_fake_put_returns_keychain_ref() -> None:
    store = InMemoryCredentialStore()
    ref = store.put("deepseek", "main", _SECRET)
    assert ref == "keychain://cmm/providers/deepseek/main"


def test_fake_has_delete_round_trip() -> None:
    store = InMemoryCredentialStore()
    ref = store.put("deepseek", "main", _SECRET)
    assert store.has(ref) is True
    store.delete(ref)
    assert store.has(ref) is False


def test_fake_missing_ref_has_false_and_delete_noop() -> None:
    store = InMemoryCredentialStore()
    missing = "keychain://cmm/providers/deepseek/absent"
    assert store.has(missing) is False
    store.delete(missing)  # idempotent: no error


def test_fake_has_malformed_ref_is_false() -> None:
    store = InMemoryCredentialStore()
    assert store.has("not-a-ref") is False


def test_fake_delete_malformed_ref_raises() -> None:
    store = InMemoryCredentialStore()
    with pytest.raises(ValueError):
        store.delete("not-a-ref")


def test_registry_consumers_receive_only_refs() -> None:
    store = InMemoryCredentialStore()
    ref = store.put("deepseek", "main", _SECRET)
    entry = _RegistryEntry(provider_id="deepseek", credential_ref=ref)
    assert entry.credential_ref == "keychain://cmm/providers/deepseek/main"
    assert not hasattr(entry, "secret")
    assert _SECRET not in repr(entry)


def test_keychain_put_passes_secret_via_stdin_never_argv() -> None:
    runner = MagicMock(return_value=_completed(0))
    store = MacOSKeychainCredentialStore(runner=runner)
    ref = store.put("deepseek", "main", _SECRET)
    assert ref == "keychain://cmm/providers/deepseek/main"
    assert runner.call_count == 1
    argv = runner.call_args[0][0]
    kwargs = runner.call_args[1]
    assert argv[0] == "security"
    assert "add-generic-password" in argv
    assert "-w" not in argv
    assert kwargs.get("input") == _SECRET.encode("utf-8")
    assert all(_SECRET not in str(part) for part in argv)


def test_keychain_put_failure_raises() -> None:
    runner = MagicMock(return_value=_completed(returncode=1))
    store = MacOSKeychainCredentialStore(runner=runner)
    with pytest.raises(RuntimeError):
        store.put("deepseek", "main", _SECRET)


def test_keychain_has_uses_find_generic_password() -> None:
    runner = MagicMock(return_value=_completed(0))
    store = MacOSKeychainCredentialStore(runner=runner)
    ref = credential_ref("deepseek", "main")
    assert store.has(ref) is True
    argv = runner.call_args[0][0]
    assert argv[0] == "security"
    assert "find-generic-password" in argv
    assert all(_SECRET not in str(part) for part in argv)


def test_keychain_has_missing_ref_is_false() -> None:
    runner = MagicMock(return_value=_completed(returncode=44))
    store = MacOSKeychainCredentialStore(runner=runner)
    assert store.has(credential_ref("deepseek", "absent")) is False


def test_keychain_service_namespace_is_pinned() -> None:
    assert SERVICE_NAME == "CMM Provider Registry"


def test_keychain_put_uses_pinned_service_namespace() -> None:
    runner = MagicMock(return_value=_completed(0))
    store = MacOSKeychainCredentialStore(runner=runner)
    store.put("deepseek", "main", _SECRET)
    argv = runner.call_args[0][0]
    assert "-s" in argv
    assert argv[argv.index("-s") + 1] == SERVICE_NAME == "CMM Provider Registry"


def test_keychain_has_unexpected_returncode_raises_without_secret() -> None:
    runner = MagicMock(return_value=_completed(returncode=36))
    store = MacOSKeychainCredentialStore(runner=runner)
    with pytest.raises(RuntimeError) as excinfo:
        store.has(credential_ref("deepseek", "main"))
    assert _SECRET not in str(excinfo.value)


def test_keychain_has_malformed_ref_is_false() -> None:
    runner = MagicMock(return_value=_completed(0))
    store = MacOSKeychainCredentialStore(runner=runner)
    assert store.has("not-a-ref") is False
    runner.assert_not_called()


def test_keychain_delete_missing_ref_is_noop() -> None:
    runner = MagicMock(return_value=_completed(returncode=44))
    store = MacOSKeychainCredentialStore(runner=runner)
    store.delete(credential_ref("deepseek", "absent"))  # not found: no error
    argv = runner.call_args[0][0]
    assert "delete-generic-password" in argv


def test_keychain_delete_failure_raises() -> None:
    runner = MagicMock(return_value=_completed(returncode=1))
    store = MacOSKeychainCredentialStore(runner=runner)
    with pytest.raises(RuntimeError):
        store.delete(credential_ref("deepseek", "main"))


def test_keychain_rejects_blank_inputs_without_calling_runner() -> None:
    runner = MagicMock(return_value=_completed(0))
    store = MacOSKeychainCredentialStore(runner=runner)
    with pytest.raises(ValueError):
        store.put("", "main", _SECRET)
    with pytest.raises(ValueError):
        store.put("deepseek", "", _SECRET)
    with pytest.raises(ValueError):
        store.put("deepseek", "main", "  ")
    with pytest.raises(ValueError):
        store.delete("not-a-ref")
    runner.assert_not_called()


def test_keychain_never_logs_secret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner = MagicMock(return_value=_completed(0))
    store = MacOSKeychainCredentialStore(runner=runner)
    ref = credential_ref("deepseek", "main")
    with caplog.at_level(logging.DEBUG, logger="kernel.llm.credential_store"):
        store.put("deepseek", "main", _SECRET)
        store.has(ref)
        store.delete(ref)
    assert caplog.records, "expected keychain debug log records"
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert _SECRET not in logged
    for call in runner.call_args_list:
        argv = call[0][0]
        assert all(_SECRET not in str(part) for part in argv)
