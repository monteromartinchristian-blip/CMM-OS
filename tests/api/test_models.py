"""Phase 11.3 — API transport model tests.

Phase 11.3 adds exactly one approved HTTP framework dependency.  These tests
lock that dependency boundary before the transport DTOs exist.
"""

from __future__ import annotations


def test_fastapi_dependency_is_available() -> None:
    import fastapi

    assert fastapi.__version__
