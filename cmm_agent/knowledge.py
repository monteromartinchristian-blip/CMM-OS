from kernel.kernel import Kernel


class Knowledge:

    def __init__(self, kernel: Kernel):
        self.kernel = kernel

    def list_components(self):
        return self.kernel.registry.list()

    def implemented(self):
        return self.kernel.registry.implemented()

    def planned(self):
        return self.kernel.registry.planned()

    def find(self, component_id):
        return self.kernel.registry.find(component_id)

    def answer(self, goal: str):

        goal = goal.lower()

        if "implementados" in goal:
            return "\n".join(
                f"- {c['id']} | {c['name']}"
                for c in self.implemented()
            )

        if "planificados" in goal or "planned" in goal:
            return "\n".join(
                f"- {c['id']} | {c['name']}"
                for c in self.planned()
            )

        return "\n".join(
            f"- {c['id']} | {c['name']} | {c['status']}"
            for c in self.list_components()
        )
