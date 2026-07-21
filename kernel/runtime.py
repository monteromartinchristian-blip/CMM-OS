from kernel.protocol.parser import PlanParser
from kernel.semantic import SemanticPlanResult, SemanticRuntime
from kernel.semantic_adapters import legacy_value_from_result, operation_from_legacy_action
from kernel.semantic_executors import create_default_semantic_registry


class Runtime:

    def __init__(self, runtime=None, parser=None):
        self.runtime = runtime or SemanticRuntime(create_default_semantic_registry())
        self.parser = parser or PlanParser()

    def run(self, data) -> SemanticPlanResult:
        plan = self.parser.parse(data)
        operations = [
            operation_from_legacy_action(action)
            for action in plan.actions
        ]
        return self.runtime.execute_plan(operations)

    def execute(self, data):
        """Execute a legacy plan and return legacy-compatible raw values."""
        result = self.run(data)
        if not result.success:
            raise ValueError("; ".join(result.errors))
        return [
            legacy_value_from_result(dict(item.data))
            for item in result.results
        ]
