from pathlib import Path

from kernel.services.filesystem import FileSystemService
from cmm_agent.core.paths import PROJECT_ROOT
from cmm_agent.tools.base import Tool
from cmm_agent.tools.result import ToolResult


class FileSystemTool(Tool):

    name = "filesystem"

    def __init__(self):
        self.fs = FileSystemService()

    def can_handle(self, goal: str) -> bool:

        goal = goal.lower()

        keywords = [
            "crear archivo",
            "crea archivo",
            "escribe archivo",
            "write file",
        ]

        return any(k in goal for k in keywords)

    def execute(self, goal: str):

        demo = PROJECT_ROOT / "demo.txt"

        self.fs.write(
            demo,
            "Archivo creado por CMM OS\n"
        )

        return ToolResult(
            success=True,
            tool=self.name,
            data=f"Archivo creado: {demo}"
        )
