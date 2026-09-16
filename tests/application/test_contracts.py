"""Phase 11.3 — versioned public application contract tests.

The Phase 11.3 application contracts are transport-neutral frozen values.  These
tests lock the versioning identity, the command/query split and the bounded,
secret-free public metadata grammar.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationCommand,
    ApplicationOperation,
    ApplicationQuery,
)


def test_application_api_version_is_v1() -> None:
    assert APPLICATION_API_VERSION == "v1"


def test_command_query_types_are_distinct() -> None:
    assert ApplicationCommand is not ApplicationQuery
    assert ApplicationOperation.MESSAGE_SUBMIT.value == "messages.submit"
