import ast
from pathlib import Path


class PythonIndex:

    def index(self, path):

        path = Path(path)

        source = path.read_text(
            encoding="utf-8"
        )

        tree = ast.parse(source)

        classes = []

        functions = []

        for node in tree.body:

            if isinstance(node, ast.ClassDef):

                methods = []

                for item in node.body:

                    if isinstance(item, ast.FunctionDef):

                        methods.append(
                            {
                                "name": item.name,
                                "lineno": item.lineno,
                                "end_lineno": item.end_lineno,
                            }
                        )

                classes.append(
                    {
                        "name": node.name,
                        "lineno": node.lineno,
                        "end_lineno": node.end_lineno,
                        "methods": methods,
                    }
                )

            elif isinstance(node, ast.FunctionDef):

                functions.append(
                    {
                        "name": node.name,
                        "lineno": node.lineno,
                        "end_lineno": node.end_lineno,
                    }
                )

        return {
            "classes": classes,
            "functions": functions,
        }


if __name__ == "__main__":

    index = PythonIndex()

    print(
        index.index(
            "kernel/kernel.py"
        )
    )