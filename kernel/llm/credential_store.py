"""Secure credential storage for provider secrets (Plan 3 Task 2).

API keys live in Keychain/platform secret storage, never in Registry
persistence: callers store secrets through a :class:`CredentialStore`
and keep only the returned provider-oriented ref such as
``keychain://cmm/providers/deepseek/main``. Refs expose no Keychain
internals (service names, account derivations).

Security rules pinned by tests:

- ``MacOSKeychainCredentialStore.put`` passes the secret via stdin
  (``input=``), never as an argv element (no ``-w`` flag);
- ``find-generic-password`` is used only inside this module;
- no logged command record ever contains secret material;
- the Keychain service namespace is the stable
  ``CMM Provider Registry`` string; account names derive from
  normalized ``provider/account`` ids.

The normal test suite uses :class:`InMemoryCredentialStore`, which
offers no secret getter by design — consumers receive only refs.
The real macOS keychain is never touched by tests.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from typing import Protocol, runtime_checkable

SERVICE_NAME = "CMM Provider Registry"
_REF_PREFIX = "keychain://cmm/providers/"
_NOT_FOUND_RETURNCODE = 44

logger = logging.getLogger(__name__)


def _normalize_part(value: str, *, label: str) -> str:
    """Strip and lowercase an id part; reject blanks and ``/``."""
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a str")
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError(f"{label} cannot be empty")
    if "/" in normalized:
        raise ValueError(f"{label} must not contain '/'")
    return normalized


def credential_ref(provider_id: str, account: str) -> str:
    """Build the provider-oriented ref for a stored credential."""
    provider = _normalize_part(provider_id, label="Provider id")
    name = _normalize_part(account, label="Account")
    return f"{_REF_PREFIX}{provider}/{name}"


def _split_ref(ref: str) -> tuple[str, str]:
    """Split a ref into ``(provider, account)``; reject malformed."""
    if not isinstance(ref, str) or not ref.startswith(_REF_PREFIX):
        raise ValueError(f"malformed credential ref: {ref!r}")
    rest = ref[len(_REF_PREFIX) :]
    parts = rest.split("/")
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise ValueError(f"malformed credential ref: {ref!r}")
    return parts[0], parts[1]


def _keychain_account(provider_id: str, account: str) -> str:
    """Derive the Keychain account name from normalized ids."""
    return f"cmm/providers/{provider_id}/{account}"


@runtime_checkable
class CredentialStore(Protocol):
    """Abstract secret storage; Registry objects keep only refs."""

    def put(self, provider_id: str, account: str, secret: str) -> str:
        """Store ``secret``; return its provider-oriented ref."""
        ...

    def has(self, ref: str) -> bool:
        """Probe for a stored credential; never raise on absence."""
        ...

    def delete(self, ref: str) -> None:
        """Remove a stored credential; missing refs are a no-op."""
        ...


class InMemoryCredentialStore:
    """In-memory fake for tests; exposes no secret getter by design."""

    def __init__(self) -> None:
        """Create an empty fake store."""
        self._secrets: dict[str, str] = {}

    def put(self, provider_id: str, account: str, secret: str) -> str:
        """Record ``secret`` under its ref; return the ref."""
        _require_secret(secret)
        ref = credential_ref(provider_id, account)
        self._secrets[ref] = secret
        return ref

    def has(self, ref: str) -> bool:
        """Return True only for a known, well-formed ref."""
        try:
            _split_ref(ref)
        except ValueError:
            return False
        return ref in self._secrets

    def delete(self, ref: str) -> None:
        """Forget ``ref``; unknown refs are a silent no-op."""
        _split_ref(ref)
        self._secrets.pop(ref, None)


def _require_secret(secret: str) -> str:
    """Reject blank or non-string secrets before any storage call."""
    if not isinstance(secret, str):
        raise TypeError("secret must be a str")
    if not secret.strip():
        raise ValueError("secret cannot be empty")
    return secret


Runner = Callable[..., subprocess.CompletedProcess[bytes]]


class MacOSKeychainCredentialStore:
    """macOS Keychain backend invoking the ``security`` CLI.

    The secret travels via stdin (``input=``); it never appears in
    argv and is never logged. ``runner`` defaults to
    :func:`subprocess.run` and exists so tests can inject a mock —
    the real keychain is never touched by the test suite.
    """

    def __init__(self, runner: Runner | None = None) -> None:
        """Create the backend; inject a mock runner for tests."""
        self._runner: Runner = runner or subprocess.run

    def put(self, provider_id: str, account: str, secret: str) -> str:
        """Upsert ``secret`` into the Keychain; return its ref."""
        _require_secret(secret)
        provider = _normalize_part(provider_id, label="Provider id")
        name = _normalize_part(account, label="Account")
        account_name = _keychain_account(provider, name)
        argv = [
            "security",
            "add-generic-password",
            "-a",
            account_name,
            "-s",
            SERVICE_NAME,
            "-U",
        ]
        logger.debug("keychain put %s", argv)
        completed = self._runner(
            argv, input=secret.encode("utf-8"), capture_output=True
        )
        if completed.returncode != 0:
            raise RuntimeError(f"keychain store failed for {provider}/{name}")
        return f"{_REF_PREFIX}{provider}/{name}"

    def has(self, ref: str) -> bool:
        """Probe the Keychain; missing or malformed refs are False."""
        try:
            provider, name = _split_ref(ref)
        except ValueError:
            return False
        argv = [
            "security",
            "find-generic-password",
            "-a",
            _keychain_account(provider, name),
            "-s",
            SERVICE_NAME,
        ]
        logger.debug("keychain has %s", argv)
        completed = self._runner(argv, capture_output=True)
        if completed.returncode == 0:
            return True
        if completed.returncode == _NOT_FOUND_RETURNCODE:
            return False
        raise RuntimeError(f"keychain probe failed for {provider}/{name}")

    def delete(self, ref: str) -> None:
        """Delete from the Keychain; not-found (44) is a no-op."""
        provider, name = _split_ref(ref)
        argv = [
            "security",
            "delete-generic-password",
            "-a",
            _keychain_account(provider, name),
            "-s",
            SERVICE_NAME,
        ]
        logger.debug("keychain delete %s", argv)
        completed = self._runner(argv, capture_output=True)
        if completed.returncode in (0, _NOT_FOUND_RETURNCODE):
            return
        raise RuntimeError(f"keychain delete failed for {ref}")
