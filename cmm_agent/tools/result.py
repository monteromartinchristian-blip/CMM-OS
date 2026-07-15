from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class ToolResult:
    success: bool
    tool: str
    data: Any = None
    error: Optional[str] = None
