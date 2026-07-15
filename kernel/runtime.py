from kernel.executor import Executor
from kernel.protocol.parser import PlanParser


class Runtime:

    def __init__(self):
        self.executor = Executor()
        self.parser = PlanParser()

    def execute(self, data):

        plan = self.parser.parse(data)

        results = []

        for action in plan.actions:
            results.append(
                self.executor.execute(action)
            )

        return results
