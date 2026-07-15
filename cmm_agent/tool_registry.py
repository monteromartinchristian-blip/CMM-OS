import importlib
import inspect
import pkgutil

from cmm_agent.tools.base import Tool
import cmm_agent.tools as tools


class ToolRegistry:

    def __init__(self):
        self.tools = []
        self._discover()

    def _discover(self):

        for _, module_name, _ in pkgutil.iter_modules(tools.__path__):

            if module_name == "base":
                continue

            module = importlib.import_module(
                f"cmm_agent.tools.{module_name}"
            )

            for _, obj in inspect.getmembers(module, inspect.isclass):

                if issubclass(obj, Tool) and obj is not Tool:
                    self.tools.append(obj())

    def resolve(self, goal):

        for tool in self.tools:
            if tool.can_handle(goal):
                return tool

        return None

    def list(self):
        return [tool.name for tool in self.tools]
