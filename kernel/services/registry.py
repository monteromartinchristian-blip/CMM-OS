import json
from pathlib import Path


class RegistryService:

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.registry_dir = self.project_root / "registry" / "components"

    def list(self):

        components = []

        if not self.registry_dir.exists():
            return components

        for file in sorted(self.registry_dir.glob("*.json")):
            with open(file, "r", encoding="utf-8") as f:
                components.append(json.load(f))

        return components

    def find(self, component_id):

        for component in self.list():
            if component["id"] == component_id:
                return component

        return None

    def implemented(self):

        return [
            c for c in self.list()
            if c["status"] == "implemented"
        ]

    def planned(self):

        return [
            c for c in self.list()
            if c["status"] == "planned"
        ]
