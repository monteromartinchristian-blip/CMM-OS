import ast
from pathlib import Path
from typing import Any, Union


class PythonIndex:
    """Build a lightweight structural index for a Python source file."""

    def index(self, path: Path) -> dict[str, Any]:

        path = Path(path)

        source = path.read_text(
            encoding="utf-8"
        )

        tree = ast.parse(source)

        classes = []
        functions = []
        imports = []
        import_targets = []

        for node in tree.body:

            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(
                    self._format_import(node)
                )
                import_targets.extend(
                    self._import_targets(node)
                )

            if isinstance(node, ast.ClassDef):

                methods = []

                for item in node.body:

                    if isinstance(
                        item,
                        (ast.FunctionDef, ast.AsyncFunctionDef),
                    ):
                        methods.append(
                            {
                                "name": item.name,
                                "docstring": ast.get_docstring(item),
                                "calls": self._calls(item),
                                "uses": self._uses(item),
                                "lineno": item.lineno,
                                "end_lineno": item.end_lineno,
                            }
                        )

                classes.append(
                    {
                        "name": node.name,
                        "docstring": ast.get_docstring(node),
                        "bases": [
                            name
                            for name in (
                                self._expr_name(base)
                                for base in node.bases
                            )
                            if name
                        ],
                        "uses": self._uses(node),
                        "lineno": node.lineno,
                        "end_lineno": node.end_lineno,
                        "methods": methods,
                    }
                )

            elif isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):

                functions.append(
                    {
                        "name": node.name,
                        "docstring": ast.get_docstring(node),
                        "calls": self._calls(node),
                        "uses": self._uses(node),
                        "lineno": node.lineno,
                        "end_lineno": node.end_lineno,
                    }
                )

        return {
            "docstring": ast.get_docstring(tree),
            "imports": imports,
            "import_targets": import_targets,
            "classes": classes,
            "functions": functions,
        }

    def _format_import(self, node: Union[ast.Import, ast.ImportFrom]) -> str:
        if isinstance(node, ast.Import):
            return "import " + ", ".join(
                self._format_alias(alias)
                for alias in node.names
            )

        module = "." * node.level
        if node.module:
            module += node.module

        return "from " + module + " import " + ", ".join(
            self._format_alias(alias)
            for alias in node.names
        )

    def _format_alias(self, alias: ast.alias) -> str:
        if alias.asname:
            return f"{alias.name} as {alias.asname}"

        return alias.name

    def _import_targets(self, node: Union[ast.Import, ast.ImportFrom]) -> list[dict[str, Any]]:
        if isinstance(node, ast.Import):
            return [
                {
                    "kind": "import",
                    "module": alias.name,
                    "name": None,
                    "asname": alias.asname,
                    "level": 0,
                }
                for alias in node.names
            ]

        return [
            {
                "kind": "from",
                "module": node.module,
                "name": alias.name,
                "asname": alias.asname,
                "level": node.level,
            }
            for alias in node.names
        ]

    def _calls(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> list[str]:
        calls = []

        for item in ast.walk(node):
            if isinstance(item, ast.Call):
                name = self._expr_name(item.func)
                if name:
                    calls.append(name)

        return calls

    def _uses(self, node: Union[ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef]) -> list[str]:
        uses = set()

        for item in ast.walk(node):
            if isinstance(item, ast.Call):
                name = self._expr_name(item.func)
                if name:
                    uses.add(name)

            if isinstance(item, ast.AnnAssign):
                self._collect_annotation_uses(item.annotation, uses)

            if isinstance(item, ast.arg) and item.annotation is not None:
                self._collect_annotation_uses(item.annotation, uses)

            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.returns is not None:
                self._collect_annotation_uses(item.returns, uses)

        return sorted(uses)

    def _collect_annotation_uses(self, node: ast.AST, uses: set[str]) -> None:
        name = self._expr_name(node)
        if name:
            uses.add(name)

        for child in ast.iter_child_nodes(node):
            self._collect_annotation_uses(child, uses)

    def _expr_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.Attribute):
            parent = self._expr_name(node.value)
            if parent:
                return f"{parent}.{node.attr}"

            return node.attr

        if isinstance(node, ast.Subscript):
            return self._expr_name(node.value)

        if isinstance(node, ast.Call):
            return self._expr_name(node.func)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                return node.value

        return ""


if __name__ == "__main__":

    index = PythonIndex()

    print(
        index.index(
            "kernel/kernel.py"
        )
    )
