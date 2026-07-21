from pathlib import Path


class ProjectAnalyzer:

    _EXCLUDED_PARTS = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }

    def __init__(self, root: Path):
        self.root = Path(root)

    def python_files(self):
        return sorted(
            p.relative_to(self.root)
            for p in self.root.rglob("*.py")
            if not any(part in self._EXCLUDED_PARTS for part in p.relative_to(self.root).parts)
            and not p.is_symlink()
            and p.is_file()
            and self._within_root(p)
        )

    def _within_root(self, path: Path) -> bool:
        try:
            path.resolve(strict=True).relative_to(self.root.resolve(strict=True))
        except (OSError, ValueError):
            return False
        return True

    def packages(self):

        packages = set()

        for file in self.python_files():

            if len(file.parts) > 1:
                packages.add(file.parts[0])

        return sorted(packages)

    def services(self):

        services_dir = self.root / "kernel" / "services"

        if not services_dir.exists():
            return []

        return sorted(
            f.stem
            for f in services_dir.glob("*.py")
            if f.stem != "__init__"
        )

    def tools(self):

        tools_dir = self.root / "cmm_agent" / "tools"

        if not tools_dir.exists():
            return []

        return sorted(
            f.stem
            for f in tools_dir.glob("*.py")
            if f.stem not in ("__init__", "base", "result")
        )

    def summary(self):

        return {
            "python_files": len(self.python_files()),
            "packages": self.packages(),
            "services": self.services(),
            "tools": self.tools(),
        }
