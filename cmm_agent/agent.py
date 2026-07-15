from kernel.kernel import Kernel
from kernel.services.code_context import CodeContextBuilder
from kernel.services.impact_analyzer import ImpactAnalyzer

from cmm_agent.context import build_context
from cmm_agent.planner import build_prompt, parse_plan
from cmm_agent.provider import OllamaProvider


class Agent:

    def __init__(self, project_root):
        self.kernel = Kernel(project_root)
        self.provider = OllamaProvider()

        self.impact = ImpactAnalyzer(project_root)
        self.context = CodeContextBuilder()

    def plan(self, goal):

        files = self.impact.analyze(goal)

        code_contexts = self.context.read_many(files)

        prompt = build_prompt(
            goal,
            build_context(),
            code_contexts,
        )

        response = self.provider.chat(prompt)

        plan = parse_plan(response)

        self.kernel.save_plan(plan)

        return plan

    def apply(self):

        return self.kernel.apply()

    def develop(self, goal):

        self.plan(goal)

        return self.apply()
