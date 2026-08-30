"""Phase 10.35 — Domain SDK Fixture Loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cmm.domains.errors import DomainError


class DomainFixtureError(DomainError):
    """Raised when loading a domain test fixture fails."""


class DomainFixtureLoader:
    """Safe, isolated fixture loader for Domain Pack test data."""

    def load(self, pack_root: Path | str, fixture: str = "sample.json") -> Any:
        """Load a JSON fixture from the domain pack root or fixtures subdirectory."""
        root = Path(pack_root).resolve()
        if not root.exists() or not root.is_dir():
            raise DomainFixtureError(f"Pack root directory does not exist: {pack_root}")

        fixture_str = str(fixture).strip()
        if not fixture_str:
            raise DomainFixtureError("Fixture path cannot be empty")

        # Reject path traversal patterns
        if ".." in Path(fixture_str).parts or fixture_str.startswith("/"):
            raise DomainFixtureError(f"Unsafe fixture path traversal: {fixture!r}")

        # Resolve candidate paths
        candidates: list[Path] = [
            (root / "fixtures" / fixture_str).resolve(),
            (root / fixture_str).resolve(),
        ]

        target_path: Path | None = None
        for candidate in candidates:
            try:
                candidate.relative_to(root)
            except ValueError:
                continue
            if candidate.is_file():
                target_path = candidate
                break

        if target_path is None:
            raise DomainFixtureError(
                f"Fixture {fixture!r} not found in pack at {root}"
            )

        try:
            target_path.relative_to(root)
        except ValueError as exc:
            raise DomainFixtureError(
                f"Fixture path escapes pack root: {target_path}"
            ) from exc

        try:
            content = target_path.read_text(encoding="utf-8")
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise DomainFixtureError(
                f"Malformed JSON in fixture {target_path}: {exc}"
            ) from exc
        except OSError as exc:
            raise DomainFixtureError(
                f"Failed to read fixture {target_path}: {exc}"
            ) from exc
