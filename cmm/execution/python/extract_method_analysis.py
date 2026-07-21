"""Conservative AST analysis shared by extract-method validation and execution."""

from __future__ import annotations

import ast
import keyword
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MethodExtractionAnalysis:
    method: ast.FunctionDef | ast.AsyncFunctionDef
    selected: tuple[ast.stmt, ...]
    inputs: tuple[str, ...]
    output: str | None


def analyze_method_extraction(
    path: Path,
    class_name: str,
    method_name: str,
    new_method_name: str,
    start_index: int,
    end_index: int,
) -> tuple[MethodExtractionAnalysis | None, str]:
    if not new_method_name.isidentifier() or keyword.iskeyword(new_method_name):
        return None, f"Invalid extracted method name: {new_method_name}."
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError) as error:
        return None, f"Module is not analyzable: {error}."
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name]
    if len(classes) != 1:
        return None, f"Class is missing or ambiguous: {class_name}."
    methods = [
        node for node in classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name
    ]
    if len(methods) != 1:
        return None, f"Method is missing or ambiguous: {class_name}.{method_name}."
    method = methods[0]
    if not isinstance(method.body, list):
        return None, "Only block-bodied methods are supported."
    if start_index < 0 or end_index <= start_index or end_index > len(method.body):
        return None, "Statement selector is empty or outside the method body."
    selected = tuple(method.body[start_index:end_index])
    forbidden = (
        ast.Return, ast.Yield, ast.YieldFrom, ast.Break, ast.Continue, ast.Raise,
        ast.Try, ast.With, ast.AsyncWith, ast.ListComp, ast.SetComp,
        ast.DictComp, ast.GeneratorExp, ast.Nonlocal, ast.Lambda,
        ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Match, ast.NamedExpr,
    )
    for statement in selected:
        if any(isinstance(node, forbidden) for node in ast.walk(statement)):
            return None, "Selected block contains unsupported control flow or closure."
        if not isinstance(method, ast.AsyncFunctionDef) and any(
            isinstance(node, ast.Await) for node in ast.walk(statement)
        ):
            return None, "Await requires an async source method."

    first_statement = method.body[0] if method.body else None
    if first_statement in selected and isinstance(first_statement, ast.Expr) and isinstance(
        first_statement.value, ast.Constant
    ) and isinstance(first_statement.value.value, str):
        return None, "Selecting the method docstring is unsupported."
    decorator_names = {
        node.id
        for decorator in method.decorator_list
        for node in ast.walk(decorator)
        if isinstance(node, ast.Name)
    }
    if "staticmethod" in decorator_names and any(
        isinstance(node, ast.Name) and node.id in {"self", "cls"}
        for statement in selected
        for node in ast.walk(statement)
    ):
        return None, "Static methods using self or cls are unsupported."

    args = {
        argument.arg
        for argument in (*method.args.posonlyargs, *method.args.args, *method.args.kwonlyargs)
    }
    if method.args.vararg:
        args.add(method.args.vararg.arg)
    if method.args.kwarg:
        args.add(method.args.kwarg.arg)
    receiver = {
        method.args.posonlyargs[0].arg if method.args.posonlyargs else None,
        method.args.args[0].arg if method.args.args else None,
    } - {None}
    assigned_before = {
        node.id for statement in method.body[:start_index]
        for node in ast.walk(statement)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    assigned_inside = {
        node.id for statement in selected
        for node in ast.walk(statement)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    loaded_inside = {
        node.id for statement in selected
        for node in ast.walk(statement)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    loaded_inside.update(
        node.target.id
        for statement in selected
        for node in ast.walk(statement)
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name)
    )
    loaded_after = {
        node.id for statement in method.body[end_index:]
        for node in ast.walk(statement)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    inputs = tuple(sorted((loaded_inside & (args | assigned_before)) - receiver))
    outputs = sorted(assigned_inside & loaded_after)
    if len(outputs) > 1:
        return None, "Multiple output variables are unsupported."
    return MethodExtractionAnalysis(method, selected, inputs, outputs[0] if outputs else None), "Extraction is supported."
