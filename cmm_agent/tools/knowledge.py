

from kernel.kernel import Kernel

from cmm_agent.core.paths import PROJECT_ROOT
from cmm_agent.knowledge import Knowledge
from cmm_agent.tools.base import Tool
from cmm_agent.tools.result import ToolResult


class KnowledgeTool(Tool):

    name = "knowledge"

    def __init__(self):
        self.kernel = Kernel(PROJECT_ROOT)
        self.knowledge = Knowledge(self.kernel)
from kernel.kernel import Kernel

from cmm_agent.core.paths import PROJECT_ROOT
from cmm_agent.knowledge import Knowledge
from cmm_agent.tools.base import Tool
from cmm_agent.tools.result import ToolResult


class KnowledgeTool(Tool):

    name = "knowledge"

    def __init__(self):
        self.kernel = Kernel(PROJECT_ROOT)
from kernel.kernel import Kernel

from cmm_agent.core.paths import PROJECT_ROOT
from cmm_agent.knowledge import Knowledge
from cmm_agent.tools.base import Tool
from cmm_agent.tools.result import ToolResult


class KnowledgeTool(Tool):

    name = "knowledge"

    def __init__(self):
        self.kernel = Kernel(PROJECT_ROOT)
        self.knowledge = Knowledge(self.kernel)

    def can_handle(self, goal: str) -> bool:

        goal = goal.lower()

        keywords = [
            "componentes",
            "implementados",
            "planificados",
            "registro",
            "registry",
            "listar",
            "lista",
            "existe",
        ]

        return any(k in goal for k in keywords)

    def execute(self, goal: str):

        return ToolResult(
            success=True,
            tool=self.name,
            data=self.knowledge.answer(goal),
        )
