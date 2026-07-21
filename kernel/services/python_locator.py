from kernel.services.python_index import PythonIndex
import ast


class PythonLocator:

    def __init__(self):

        self.index = PythonIndex()

    def find_class(
        self,
        path,
        class_name,
    ):
        if "." in class_name:
            return self.find_qualified_class(path, class_name)

        data = self.index.index(path)

        matches = [
            cls for cls in data["classes"]
            if cls["name"] == class_name
        ]

        if len(matches) > 1:
            raise ValueError(f"Ambiguous class: {class_name}")

        return matches[0] if matches else None

    def find_qualified_class(self, path, qualified_name):
        source = open(path, encoding="utf-8").read()
        tree = ast.parse(source)
        parts = [part for part in qualified_name.split(".") if part]
        container = tree
        found = None

        for part in parts:
            matches = [
                node
                for node in getattr(container, "body", [])
                if isinstance(node, ast.ClassDef) and node.name == part
            ]
            if len(matches) > 1:
                raise ValueError(f"Ambiguous class: {part}")
            if not matches:
                return None
            found = matches[0]
            container = found

        if found is None:
            return None

        methods = [
            {
                "name": item.name,
                "docstring": ast.get_docstring(item),
                "lineno": item.lineno,
                "end_lineno": item.end_lineno,
            }
            for item in found.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        return {
            "name": found.name,
            "qualified_name": qualified_name,
            "docstring": ast.get_docstring(found),
            "lineno": found.lineno,
            "end_lineno": found.end_lineno,
            "methods": methods,
        }

    def find_method(
        self,
        path,
        class_name,
        method_name,
    ):

        cls = self.find_class(
            path,
            class_name,
        )

        if cls is None:
            return None

        matches = [
            method for method in cls["methods"]
            if method["name"] == method_name
        ]

        if len(matches) > 1:
            raise ValueError(f"Ambiguous method: {method_name}")

        return matches[0] if matches else None

    def find_last_method(
        self,
        path,
        class_name,
    ):

        cls = self.find_class(
            path,
            class_name,
        )

        if cls is None:
            return None

        methods = cls["methods"]

        if not methods:
            return None

        return methods[-1]
