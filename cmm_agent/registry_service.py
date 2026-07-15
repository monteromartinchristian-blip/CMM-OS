from cmm_agent.core.registry import load_components

class RegistryService:

    def __init__(self):
        self.components = load_components()

    def all(self):
        return self.components

    def implemented(self):
        return [
            c for c in self.components
            if c["status"] == "implemented"
        ]

    def planned(self):
        return [
            c for c in self.components
            if c["status"] == "planned"
        ]

    def by_type(self, component_type):
        return [
            c for c in self.components
            if c["type"] == component_type
        ]

    def find(self, component_id):
        for c in self.components:
            if c["id"] == component_id:
                return c
        return None

    def stats(self):
        return {
            "total": len(self.components),
            "implemented": len(self.implemented()),
            "planned": len(self.planned())
        }
