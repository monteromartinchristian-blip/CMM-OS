"""Phase 11.4 — frozen public CLI presentation contracts.

This module owns the public presentation values of the one canonical ``cmm``
front door: the stable schema version, the output formats, the stable process
exit codes, the presentation availability vocabulary, the safe error/result
envelopes and the static command descriptor used for help grouping and
capability binding.

It owns no business authority.  It reads no configuration, resolves no
capability, imports no canonical subsystem and executes no command: the values
here are the frozen vocabulary the CLI adapters and dispatchers speak.

A CLI result is a *presentation* envelope, never a second public application
response.  Everything it carries is frozen at construction and validated
against one bounded presentation grammar, so an opaque runtime object, binary
data, an exception, an unbounded value or a secret-shaped key can never enter a
public CLI result.  The grammar mirrors the screening philosophy of the
application boundary (``cmm.application.contracts``) rather than importing it:
presentation stays a separate, self-contained boundary.

See ``docs/reference/phase-11-cli.md``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from types import MappingProxyType
from typing import Any

from cmm.application import ApplicationErrorCode

__all__ = [
    "CLI_MAX_STRING_LENGTH",
    "CLI_MAX_VALUE_DEPTH",
    "CLI_MAX_VALUE_ITEMS",
    "CLI_SCHEMA_VERSION",
    "CLI_UNHEALTHY_DEPENDENCY_CODE",
    "CliAvailability",
    "CliCommandDescriptor",
    "CliError",
    "CliExitCode",
    "CliOutputFormat",
    "CliResult",
    "cli_exit_for_application_error",
    "cli_exit_for_error_code",
    "cli_exit_for_result",
]

#: The one supported public CLI presentation schema version.
CLI_SCHEMA_VERSION = "v1"

#: Frozen presentation bounds of one public CLI value.  The item bound is wider
#: than an application metadata mapping's because a CLI result is a whole output
#: document: one ``status`` document carries every declared capability.
CLI_MAX_VALUE_DEPTH = 6
CLI_MAX_VALUE_ITEMS = 1024
CLI_MAX_STRING_LENGTH = 16_384

#: Normalized key names that fail closed, mirroring the application boundary.
CLI_SECRET_LIKE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "credential",
        "private_key",
        "authorization",
        "cookie",
    }
)

#: Separator-free forms, so camelCase and joined spellings compare equal, e.g.
#: ``apiKey``, ``Api-Key`` and ``private_key``.
_CLI_SECRET_LIKE_FRAGMENTS = tuple(
    sorted({key.replace("_", "") for key in CLI_SECRET_LIKE_KEYS})
)

_KEY_SEPARATOR = re.compile(r"[^a-z0-9]+")


# ── Public enums ─────────────────────────────────────────────────────────────


class CliOutputFormat(str, Enum):
    """Closed set of public CLI output representations."""

    HUMAN = "human"
    JSON = "json"
    YAML = "yaml"


class CliExitCode(IntEnum):
    """Closed, stable process exit codes of the public CLI."""

    SUCCESS = 0
    USAGE = 2
    INVALID_REQUEST = 3
    NOT_FOUND = 4
    CAPABILITY_UNAVAILABLE = 5
    PERMISSION_DENIED = 6
    CONFLICT = 7
    DEPENDENCY_UNHEALTHY = 8
    CANCELLED = 9
    INTERNAL_FAILURE = 10


class CliAvailability(str, Enum):
    """Presentation-only availability of one public CLI command.

    This is a descriptive label derived from canonical capability evidence.  It
    is not a capability registry and grants no authority.
    """

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEFERRED = "deferred"


#: The frozen application-error to CLI exit-code mapping.  Every closed public
#: application error category maps to exactly one stable process exit code.
APPLICATION_ERROR_EXIT_CODES: Mapping[ApplicationErrorCode, CliExitCode] = (
    MappingProxyType(
        {
            ApplicationErrorCode.INVALID_REQUEST: CliExitCode.INVALID_REQUEST,
            ApplicationErrorCode.UNSUPPORTED_VERSION: CliExitCode.INVALID_REQUEST,
            ApplicationErrorCode.POLICY_DENIED: CliExitCode.PERMISSION_DENIED,
            ApplicationErrorCode.RESOURCE_NOT_FOUND: CliExitCode.NOT_FOUND,
            ApplicationErrorCode.CONFLICT: CliExitCode.CONFLICT,
            ApplicationErrorCode.IDEMPOTENCY_CONFLICT: CliExitCode.CONFLICT,
            ApplicationErrorCode.CONCURRENCY_CONFLICT: CliExitCode.CONFLICT,
            ApplicationErrorCode.APPROVAL_REQUIRED: CliExitCode.PERMISSION_DENIED,
            ApplicationErrorCode.CANCELLED: CliExitCode.CANCELLED,
            ApplicationErrorCode.CAPABILITY_UNAVAILABLE: (
                CliExitCode.CAPABILITY_UNAVAILABLE
            ),
            ApplicationErrorCode.INTERNAL_FAILURE: CliExitCode.INTERNAL_FAILURE,
        }
    )
)


def cli_exit_for_application_error(code: ApplicationErrorCode) -> CliExitCode:
    """Return the stable process exit code of one public application error.

    The mapping is total over the closed error enum, so a known public error
    always has a stable exit code and an unknown value is a caller defect rather
    than a silent default.
    """

    if not isinstance(code, ApplicationErrorCode):
        raise TypeError("code must be an ApplicationErrorCode")
    return APPLICATION_ERROR_EXIT_CODES[code]


#: The CLI's own stable code for a failing diagnostic run.  It is not an
#: application error: the platform was reachable and a required check failed.
CLI_UNHEALTHY_DEPENDENCY_CODE = "DEPENDENCY_UNHEALTHY"

#: Exit codes by public error-code *name*.  The application codes and the CLI's
#: own codes live in one table, so a single total rule resolves every result.
EXIT_CODES_BY_ERROR_CODE_NAME: Mapping[str, CliExitCode] = MappingProxyType(
    {
        **{
            code.value: cli_exit_for_application_error(code)
            for code in ApplicationErrorCode
        },
        CLI_UNHEALTHY_DEPENDENCY_CODE: CliExitCode.DEPENDENCY_UNHEALTHY,
    }
)


def cli_exit_for_error_code(code_name: str) -> CliExitCode:
    """Return the stable exit code of one public CLI/application error code.

    An unrecognized code is never reported as success: it fails closed as an
    internal failure, because a code the CLI does not know is a defect rather
    than a reason to exit zero.
    """

    if not isinstance(code_name, str):
        raise TypeError("code_name must be a string")
    return EXIT_CODES_BY_ERROR_CODE_NAME.get(code_name, CliExitCode.INTERNAL_FAILURE)


def cli_exit_for_result(result: CliResult) -> CliExitCode:
    """Return the stable process exit code of one public CLI result.

    A successful result is success.  A failed result takes the exit code of its
    public error code, and a failed result carrying no usable error fails closed
    as an internal failure rather than being reported as success.
    """

    if not isinstance(result, CliResult):
        raise TypeError(f"result must be a CliResult, not {type(result).__name__}")
    if result.ok:
        return CliExitCode.SUCCESS
    if result.error is None:
        return CliExitCode.INTERNAL_FAILURE
    return cli_exit_for_error_code(result.error.code)


# ── Bounded presentation grammar ─────────────────────────────────────────────


class _ValueBudget:
    """Shared, bounded item budget for one presentation value."""

    __slots__ = ("_remaining",)

    def __init__(self) -> None:
        self._remaining = CLI_MAX_VALUE_ITEMS

    def spend(self, label: str) -> None:
        """Consume one item, failing closed when the budget is exhausted."""

        self._remaining -= 1
        if self._remaining < 0:
            raise ValueError(
                f"{label} must not contain more than {CLI_MAX_VALUE_ITEMS} items"
            )


def _check_depth(depth: int, label: str) -> None:
    if depth > CLI_MAX_VALUE_DEPTH:
        raise ValueError(
            f"{label} must not nest deeper than {CLI_MAX_VALUE_DEPTH} levels"
        )


def _is_secret_like_key(key: str) -> bool:
    """Return whether *key* names secret-bearing content.

    Comparison is containment over the separator-free lowercase key, so
    ``Api-Key``, ``apiKey``, ``refreshToken`` and ``db-credential`` all fail
    closed while the check stays deterministic and case-insensitive.
    """

    fragment = _KEY_SEPARATOR.sub("", key.lower())
    return bool(fragment) and any(
        denied in fragment for denied in _CLI_SECRET_LIKE_FRAGMENTS
    )


def _freeze_value(
    value: object, *, label: str, depth: int, budget: _ValueBudget
) -> Any:
    """Return a recursively immutable, secret-free representation of *value*."""

    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label} must not contain a non-finite number")
        return value
    if isinstance(value, str):
        if len(value) > CLI_MAX_STRING_LENGTH:
            raise ValueError(
                f"{label} must not contain a string longer than "
                f"{CLI_MAX_STRING_LENGTH} characters"
            )
        return value
    if isinstance(value, bytes | bytearray | memoryview):
        raise TypeError(f"{label} must not carry binary data")
    if isinstance(value, Mapping):
        _check_depth(depth, label)
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{label} keys must be strings")
            if _is_secret_like_key(key):
                raise ValueError(
                    f"{label} key {key!r} is not permitted in a public CLI value"
                )
            budget.spend(label)
            frozen[key] = _freeze_value(
                item, label=label, depth=depth + 1, budget=budget
            )
        return MappingProxyType(frozen)
    if isinstance(value, Sequence):
        _check_depth(depth, label)
        items: list[Any] = []
        for item in value:
            budget.spend(label)
            items.append(
                _freeze_value(item, label=label, depth=depth + 1, budget=budget)
            )
        return tuple(items)

    raise TypeError(
        f"{label} must be a JSON-safe public value, not {type(value).__name__}"
    )


def _freeze_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    """Freeze one public presentation mapping against the safe grammar."""

    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")

    frozen = _freeze_value(value, label=field_name, depth=1, budget=_ValueBudget())
    assert isinstance(frozen, Mapping)
    return frozen


def _thaw(value: object) -> Any:
    """Return a fresh, plain, JSON-native representation of a frozen value."""

    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


# ── Scalar validators ────────────────────────────────────────────────────────


def _bounded_text(value: object, field_name: str, max_length: int) -> str:
    """Return bounded public text unchanged; presentation never rewrites it."""

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
    if len(value) > max_length:
        raise ValueError(f"{field_name} must not exceed {max_length} characters")
    return value


def _enum_member(value: object, enum_type: type[Enum], field_name: str) -> Any:
    """Require a real enum member; a raw string is never silently coerced."""

    if not isinstance(value, enum_type):
        raise TypeError(f"{field_name} must be a {enum_type.__name__}")
    return value


# ── Public envelopes ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CliError:
    """One safe, public CLI error.

    The code is a stable public category name and the message is a
    presentation-owned constant.  No traceback, exception repr, filesystem path,
    credential value or hidden reasoning is ever carried here.
    """

    code: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "code",
            _bounded_text(self.code, "code", CLI_MAX_STRING_LENGTH),
        )
        object.__setattr__(
            self,
            "message",
            _bounded_text(self.message, "message", CLI_MAX_STRING_LENGTH),
        )
        object.__setattr__(self, "details", _freeze_mapping(self.details, "details"))

    def to_dict(self) -> dict[str, Any]:
        """Return the deterministic public representation of this error."""

        return {
            "code": self.code,
            "message": self.message,
            "details": _thaw(self.details),
        }


@dataclass(frozen=True, slots=True)
class CliResult:
    """One safe, versioned public CLI result envelope.

    This is presentation output, not an application response: where an
    application response already owns a semantic field, that field is projected
    here rather than redefined.
    """

    command: str
    ok: bool
    status: str
    data: Mapping[str, Any] = field(default_factory=dict)
    error: CliError | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = CLI_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "command",
            _bounded_text(self.command, "command", CLI_MAX_STRING_LENGTH),
        )
        if not isinstance(self.ok, bool):
            raise TypeError("ok must be a bool")
        object.__setattr__(
            self,
            "status",
            _bounded_text(self.status, "status", CLI_MAX_STRING_LENGTH),
        )
        object.__setattr__(self, "data", _freeze_mapping(self.data, "data"))
        if self.error is not None and not isinstance(self.error, CliError):
            raise TypeError("error must be a CliError or None")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))
        if self.schema_version != CLI_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {CLI_SCHEMA_VERSION!r}")

    def to_dict(self) -> dict[str, Any]:
        """Return the deterministic public representation of this result."""

        return {
            "schema_version": self.schema_version,
            "command": self.command,
            "ok": self.ok,
            "status": self.status,
            "data": _thaw(self.data),
            "error": None if self.error is None else self.error.to_dict(),
            "metadata": _thaw(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CliCommandDescriptor:
    """Immutable static metadata of one public CLI command.

    The descriptor declares a command identity, a presentation availability
    label and help text.  It executes nothing, resolves nothing and owns no
    state: availability is a label derived from canonical evidence, never a
    replacement for it.
    """

    command_id: str
    availability: CliAvailability
    help: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "command_id",
            _bounded_text(self.command_id, "command_id", CLI_MAX_STRING_LENGTH),
        )
        object.__setattr__(
            self,
            "availability",
            _enum_member(self.availability, CliAvailability, "availability"),
        )
        object.__setattr__(
            self, "help", _bounded_text(self.help, "help", CLI_MAX_STRING_LENGTH)
        )
