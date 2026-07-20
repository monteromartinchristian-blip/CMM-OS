"""Thin CLI entry point for the CMM OS kernel."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from kernel.core.bootstrap import create_kernel
from kernel.core.kernel import AgentKernel
from kernel.llm.clients.ollama_client import OllamaClient
from kernel.llm.ollama_provider import OllamaProvider
from kernel.planner.bootstrap import create_ollama_planner, create_default_registry
from kernel.planner.context import PlanningContext
from kernel.planner.executor import Executor
from kernel.planner.validator import PlanValidator
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.bootstrap import create_ollama_planner as create_ollama_planner_bootstrap
from kernel.llm.parser import OperationPlanParser
from kernel.llm.prompt import PromptBuilder
from kernel.planner.llm_planner import LLMPlanner
from kernel.core.result import KernelResult
from kernel.planner.bootstrap import create_default_planner


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""

    parser = argparse.ArgumentParser(prog="cmm")
    parser.add_argument("prompt")
    parser.add_argument("--model", dest="model", default="qwen3:30b-a3b")
    parser.add_argument("--host", dest="host", default="http://localhost:11434")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser


def _build_kernel(model: str, host: str) -> AgentKernel:
    """Create the kernel using the existing bootstrap path."""

    planner = create_ollama_planner_bootstrap()
    planner.provider = OllamaProvider(client=OllamaClient(host=host), model=model)
    validator = PlanValidator()
    registry = create_default_registry()
    executor = Executor(engine=None, registry=registry)
    return AgentKernel(planner=planner, validator=validator, executor=executor)


def _format_plan(plan: ExecutionPlan) -> str:
    """Render a human-readable execution plan."""

    lines = ["Execution Plan"]
    for index, operation in enumerate(plan, start=1):
        lines.append(f"{index}. {operation.operation_type_value}")
        if hasattr(operation, "module") and operation.module is not None:
            lines.append(f"module={operation.module}")
        if hasattr(operation, "class_name"):
            lines.append(f"name={operation.class_name}")
        if hasattr(operation, "target_class"):
            lines.append(f"class={operation.target_class}")
        if hasattr(operation, "method_name"):
            lines.append(f"name={operation.method_name}")
        if hasattr(operation, "source_code"):
            lines.append(f"code={operation.source_code}")
        if hasattr(operation, "name") and operation.name is not None:
            lines.append(f"import={operation.name}")
    return "\n".join(lines)


def _render_result(result: KernelResult, *, json_output: bool = False) -> str:
    """Render the kernel result for the CLI user."""

    if json_output:
        return json.dumps(result.execution_plan.serialize(), indent=2)

    lines = [
        "✓ Planner utilized",
        f"✓ Model: {result.planning_context.metadata.get('model', 'unknown')}",
        f"✓ Operations: {len(result.execution_plan)}",
        "✓ Operations found",
        "✓ Execution successful" if result.success else "✗ Execution failed",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        kernel = _build_kernel(args.model, args.host)
        context = PlanningContext(intent=args.prompt, metadata={"model": args.model, "host": args.host})
        result = kernel.execute(context)
    except Exception as exc:  # pragma: no cover - thin CLI error boundary
        if args.debug:
            raise
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(_format_plan(result.execution_plan))
        return 0

    if args.json:
        print(json.dumps(result.execution_plan.serialize(), indent=2))
        return 0

    print(_render_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
