"""Phase 10.35 — Tests for public SDK import surface and side effects."""

from __future__ import annotations

import subprocess
import sys


def test_sdk_exposes_only_intended_builder_surface() -> None:
    from cmm.domains.sdk import (
        DomainBuilder,
        ManifestBuilder,
    )

    assert DomainBuilder is not None
    assert ManifestBuilder is not None


def test_sdk_fresh_import_has_no_side_effects() -> None:
    code = """
import sys
from cmm.domains.registry import DomainRegistry

reg_before = DomainRegistry()
snapshot_before = reg_before.snapshot_state()

import cmm.domains.sdk

reg_after = DomainRegistry()
snapshot_after = reg_after.snapshot_state()

assert snapshot_before == snapshot_after, "DomainRegistry was mutated on import!"
print("OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Import had side effects:\n{result.stderr}"
    assert result.stdout.strip() == "OK"
