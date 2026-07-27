"""Phase 9.22 – Agent Runtime CLI Public Facade.

The single import path for the Agent Runtime CLI's public surface:
``AgentRuntimeCliRunner``, ``AgentRuntimeCliResult``,
``AgentRuntimeCliContextBuilder``, the four output formatters, and the
module-level ``run``/``main`` functions. Internal helpers (parsers,
argparse tree, per-operation payload builders) are intentionally not
re-exported here.
"""

from __future__ import annotations

from cmm.agent_runtime.agent_runtime_cli_app import AgentRuntimeCliRunner, main, run
from cmm.agent_runtime.agent_runtime_cli_context import AgentRuntimeCliContextBuilder
from cmm.agent_runtime.agent_runtime_cli_formatters import (
    HumanFormatter,
    JsonFormatter,
    JsonLinesFormatter,
    QuietFormatter,
)
from cmm.agent_runtime.agent_runtime_cli_result import AgentRuntimeCliResult

__all__ = [
    "AgentRuntimeCliContextBuilder",
    "AgentRuntimeCliResult",
    "AgentRuntimeCliRunner",
    "HumanFormatter",
    "JsonFormatter",
    "JsonLinesFormatter",
    "QuietFormatter",
    "main",
    "run",
]

if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
