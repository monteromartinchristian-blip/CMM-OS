from pathlib import Path

from kernel.runtime import Runtime
from kernel.services.plan_store import PlanStore
from kernel.services.registry import RegistryService
from kernel.validator import PlanValidator


class Kernel:

    def __init__(self, project_root: Path):

        self.project_root = Path(project_root)

        self.runtime = Runtime()

        self.registry = RegistryService(self.project_root)

        self.plan_store = PlanStore(self.project_root)

        self.validator = PlanValidator()

    def save_plan(self, plan):

        self.plan_store.save(plan)

    def load_plan(self):

        return self.plan_store.load()

    def apply(self):

        plan = self.load_plan()

        if plan is None:
            raise RuntimeError(
                "No plan available."
            )

        self.validator.validate(plan)

        return self.runtime.execute(plan)

    def version(self):

        return "1.0.0"

    def hello(self):
        return 'hola'
