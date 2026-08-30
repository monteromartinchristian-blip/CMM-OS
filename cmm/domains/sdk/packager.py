"""Phase 10.35 — Domain Packager."""

from __future__ import annotations

import gzip
import tarfile
from pathlib import Path

from cmm.domains.enums import DomainValidationStatus
from cmm.domains.errors import DomainError
from cmm.domains.sdk.validation import validate_domain_path

EXCLUDED_DIR_NAMES = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "venv",
        ".git",
        ".tox",
        ".mypy_cache",
        ".ruff_cache",
    }
)

EXCLUDED_FILE_NAMES = frozenset(
    {
        ".DS_Store",
    }
)

EXCLUDED_EXTENSIONS = frozenset(
    {
        ".pyc",
        ".pyo",
    }
)


class DomainPackagingError(DomainError):
    """Raised when domain packaging fails or is blocked by validation."""


class DomainPackager:
    """Creates deterministic .tar.gz archives of validated Domain Packs."""

    def pack(
        self,
        pack_root: Path | str,
        output: Path | str | None = None,
    ) -> Path:
        """Validate and package a domain pack into a deterministic .tar.gz archive."""
        root = Path(pack_root).resolve()
        if not root.exists() or not root.is_dir():
            raise DomainPackagingError(
                f"Domain pack root does not exist or is not a directory: {pack_root}"
            )

        # 1. Canonical validation first — reject blocked packs
        validation_result = validate_domain_path(root)
        blocking = [
            f for f in validation_result.findings if getattr(f, "blocking", False)
        ]
        if (
            validation_result.status
            in (DomainValidationStatus.FAILED, DomainValidationStatus.ERROR)
            or blocking
        ):
            raise DomainPackagingError(
                f"Domain validation failed with status={validation_result.status.value}; packaging blocked"
            )

        # 2. Determine output archive path
        if output is not None:
            out_path = Path(output).resolve()
        else:
            out_path = (root.parent / f"{root.name}.tar.gz").resolve()

        out_path.parent.mkdir(parents=True, exist_ok=True)

        # 3. Collect source items deterministically
        collected_items = self._collect_items(root)

        # 4. Write deterministic tar.gz archive
        temp_out = out_path.with_suffix(f"{out_path.suffix}.tmp")
        try:
            with (
                temp_out.open("wb") as raw_file,
                gzip.GzipFile(
                    filename="",
                    mode="wb",
                    fileobj=raw_file,
                    mtime=0.0,
                ) as gz_file,
                tarfile.open(
                    mode="w",
                    fileobj=gz_file,
                    format=tarfile.PAX_FORMAT,
                ) as tar,
            ):
                for path, rel_posix in collected_items:
                    tarinfo = tar.gettarinfo(str(path), arcname=rel_posix)
                    tarinfo.uid = 0
                    tarinfo.gid = 0
                    tarinfo.uname = ""
                    tarinfo.gname = ""
                    tarinfo.mtime = 0

                    if tarinfo.isdir():
                        tarinfo.mode = 0o755
                        tar.addfile(tarinfo)
                    elif tarinfo.isreg():
                        tarinfo.mode = 0o644
                        with path.open("rb") as f:
                            tar.addfile(tarinfo, f)

            temp_out.replace(out_path)
        except Exception:
            if temp_out.exists():
                temp_out.unlink()
            raise

        return out_path

    def _collect_items(self, root: Path) -> list[tuple[Path, str]]:
        """Collect and sort files and directories to include in the package."""
        items: list[tuple[Path, str]] = []

        all_paths = sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix())

        for p in all_paths:
            # Check symlink escape
            try:
                resolved = p.resolve()
                resolved.relative_to(root)
            except ValueError as exc:
                raise DomainPackagingError(
                    f"Path escape detected in domain pack: {p}"
                ) from exc

            # Relative parts
            rel = p.relative_to(root)
            parts = rel.parts

            # Exclude directories and matching files
            if any(part in EXCLUDED_DIR_NAMES for part in parts):
                continue
            if p.name in EXCLUDED_FILE_NAMES:
                continue
            if p.suffix in EXCLUDED_EXTENSIONS:
                continue

            items.append((p, rel.as_posix()))

        return items
