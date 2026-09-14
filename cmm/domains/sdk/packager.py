"""Phase 10.35 — Domain Packager."""

from __future__ import annotations

import gzip
import os
import tarfile
import tempfile
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
        try:
            root = Path(pack_root).resolve()
        except OSError as exc:
            raise DomainPackagingError(
                f"Domain pack root could not be resolved: {pack_root}"
            ) from exc
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
            out_path = Path(output).absolute()
        else:
            out_path = (root.parent / f"{root.name}.tar.gz").absolute()

        in_root_output = self._validate_destination(root, out_path)

        if not in_root_output:
            self._create_destination_parent(out_path.parent)

        try:
            with tempfile.NamedTemporaryFile(
                mode="w+b",
                prefix=f".{out_path.name}.",
                suffix=".tmp",
                dir=out_path.parent,
            ) as raw_file:
                temp_out = Path(raw_file.name)

                # 3. Collect source items deterministically, excluding output/temp.
                collected_items = self._collect_items(
                    root,
                    excluded_paths=frozenset({out_path, temp_out}),
                )

                # 4. Write deterministic tar.gz archive.
                with (
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
                            with path.open("rb") as source_file:
                                tar.addfile(tarinfo, source_file)
                        elif tarinfo.issym():
                            tarinfo.mode = 0o777
                            tar.addfile(tarinfo)

                raw_file.flush()
                os.fsync(raw_file.fileno())

                try:
                    os.link(temp_out, out_path)
                except FileExistsError as exc:
                    raise DomainPackagingError(
                        f"Package destination already exists: {out_path}"
                    ) from exc
        except DomainPackagingError:
            raise
        except OSError as exc:
            raise DomainPackagingError(
                f"Could not write or finalize package archive: {out_path}"
            ) from exc

        return out_path.resolve()

    def _validate_destination(self, root: Path, out_path: Path) -> bool:
        """Fail closed before writing to an unsafe package destination."""
        if not out_path.name.endswith(".tar.gz"):
            raise DomainPackagingError(
                f"Package destination must end in .tar.gz: {out_path}"
            )

        if out_path.is_dir():
            raise DomainPackagingError(
                f"Package destination is a directory: {out_path}"
            )

        destination_exists = os.path.lexists(out_path)
        try:
            effective_output = out_path.resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise DomainPackagingError(
                f"Package destination could not be resolved safely: {out_path}"
            ) from exc

        if destination_exists and self._is_within(effective_output, root):
            raise DomainPackagingError(
                f"Package destination aliases a domain pack source member: {out_path}"
            )

        if destination_exists:
            raise DomainPackagingError(
                f"Package destination already exists: {out_path}"
            )

        in_root_output = self._is_within(effective_output, root)
        if in_root_output and not out_path.parent.is_dir():
            raise DomainPackagingError(
                "In-root package destination parent must already exist: "
                f"{out_path.parent}"
            )
        return in_root_output

    def _create_destination_parent(self, parent: Path) -> None:
        """Create an external destination parent when needed."""
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise DomainPackagingError(
                f"Could not create package destination directory: {parent}"
            ) from exc

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True

    def _collect_items(
        self,
        root: Path,
        *,
        excluded_paths: frozenset[Path] = frozenset(),
    ) -> list[tuple[Path, str]]:
        """Collect and sort files and directories to include in the package."""
        items: list[tuple[Path, str]] = []
        excluded_lexical = frozenset(path.absolute() for path in excluded_paths)
        excluded_resolved = frozenset(
            path.resolve(strict=False) for path in excluded_paths
        )

        all_paths = sorted(
            root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()
        )

        for p in all_paths:
            if p.absolute() in excluded_lexical:
                continue

            if p.is_symlink():
                link_target = Path(p.readlink())
                if link_target.is_absolute():
                    raise DomainPackagingError(
                        f"Absolute symlink is not allowed in domain pack: {p}"
                    )
                try:
                    resolved = p.resolve(strict=True)
                except (OSError, RuntimeError) as exc:
                    raise DomainPackagingError(
                        f"Broken or ambiguous symlink in domain pack: {p}"
                    ) from exc
            else:
                try:
                    resolved = p.resolve(strict=True)
                except OSError as exc:
                    raise DomainPackagingError(
                        f"Path could not be resolved in domain pack: {p}"
                    ) from exc

            if resolved in excluded_resolved:
                continue

            try:
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
