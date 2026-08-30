"""Phase 10.35 — Domain SDK Scaffold Engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cmm.domains.errors import DomainContractValidationError, DomainError
from cmm.domains.identifiers import DomainId

TEMPLATES = ("basic_domain",)


class DomainScaffoldError(DomainError):
    """Raised when domain pack scaffolding fails."""


class DomainScaffolder:
    """Creates a new external Domain Pack from a predefined template."""

    def create(
        self,
        name: str,
        destination: Path | str | None = None,
        template: str = "basic_domain",
    ) -> Path:
        """Create a new domain pack scaffold at destination."""
        if template not in TEMPLATES:
            raise DomainScaffoldError(
                f"Unknown scaffold template: {template!r}. Allowed templates: {', '.join(TEMPLATES)}"
            )

        # Validate name as a valid slug via canonical DomainId
        try:
            domain_id = DomainId.from_str(f"domain:{name}")
        except DomainContractValidationError as exc:
            raise DomainScaffoldError(
                f"Invalid domain name/slug: {name!r}: {exc.message}"
            ) from exc

        slug = domain_id.slug

        if destination is None:
            dest_path = Path.cwd() / slug
        else:
            dest_path = Path(destination).resolve()

        # Protection against existing non-empty directory or file
        if dest_path.exists():
            if dest_path.is_file():
                raise DomainScaffoldError(f"Destination {dest_path} is an existing file")
            if any(dest_path.iterdir()):
                raise DomainScaffoldError(f"Destination directory {dest_path} is not empty")
        else:
            dest_path.mkdir(parents=True, exist_ok=True)

        # Generate files for basic_domain
        self._generate_basic_domain(dest_path, slug)

        return dest_path

    def _generate_basic_domain(self, dest_path: Path, slug: str) -> None:
        fixtures_dir = dest_path / "fixtures"
        tests_dir = dest_path / "tests"

        fixtures_dir.mkdir(parents=True, exist_ok=True)
        tests_dir.mkdir(parents=True, exist_ok=True)

        # 1. manifest.json (declarative manifest format)
        manifest_data: dict[str, Any] = {
            "id": slug,
            "version": "0.1.0",
            "schema_version": "1",
            "name": slug,
            "description": f"{slug} domain pack",
            "pack_kind": "internal",
            "fixtures": [
                {
                    "id": "sample",
                    "path": "fixtures/sample.json",
                }
            ],
            "tests": [
                {
                    "id": "test_domain",
                    "path": "tests/test_domain.py",
                }
            ],
        }

        manifest_path = dest_path / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest_data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        # 2. README.md
        readme_content = f"# {slug}\n\n{slug} domain pack.\n"
        (dest_path / "README.md").write_text(readme_content, encoding="utf-8")

        # 3. fixtures/sample.json
        sample_fixture = {
            "domain": slug,
            "sample_key": "sample_value",
        }
        (fixtures_dir / "sample.json").write_text(
            json.dumps(sample_fixture, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        # 4. tests/test_domain.py
        test_content = f'''"""Development tests for {slug} domain pack."""

from __future__ import annotations

from pathlib import Path
from cmm.domains.sdk import DomainFixtureLoader, DomainTestHarness


def test_domain_manifest_and_fixture() -> None:
    pack_root = Path(__file__).resolve().parent.parent
    harness = DomainTestHarness()
    result = harness.validate(pack_root)
    assert result.manifest_valid is True

    fixture_loader = DomainFixtureLoader()
    data = fixture_loader.load(pack_root, "sample.json")
    assert isinstance(data, dict)
    assert data.get("domain") == "{slug}"
'''
        (tests_dir / "test_domain.py").write_text(test_content, encoding="utf-8")
