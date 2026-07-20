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

        for node in tree.body:

            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(
                    self._format_import(node)
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
                                "lineno": item.lineno,
                                "end_lineno": item.end_lineno,
                            }
                        )

                classes.append(
                    {
                        "name": node.name,
                        "docstring": ast.get_docstring(node),
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
                        "lineno": node.lineno,
                        "end_lineno": node.end_lineno,
                    }
                )

        return {
            "docstring": ast.get_docstring(tree),
            "imports": imports,
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


if __name__ == "__main__":

    index = PythonIndex()

    print(
        index.index(
            "kernel/kernel.py"
        )
    )
