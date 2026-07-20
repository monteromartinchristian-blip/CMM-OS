from pathlib import Path
import ast

from kernel.services.python_locator import PythonLocator
from kernel.services.python_validator import PythonValidator
from kernel.services.python_transformer import PythonTransformer


class PythonEditor:

    def __init__(self):
        """Initialize the editor with locator, validator and transformer services.

        Args:
            None.

        Returns:
            None.

        Behavior:
            Creates the helper objects used by the public editing methods.

        Example:
            >>> editor = PythonEditor()
        """
        self.locator = PythonLocator()
        self.validator = PythonValidator()
        self.transformer = PythonTransformer()

    def _read_source(self, path):
        return Path(path).read_text(encoding="utf-8")

    def _write_source(self, path, source):
        Path(path).write_text(source, encoding="utf-8")

    def _apply_transform(self, path, transform):
        source = self._read_source(path)
        self.validator.validate(source)

        tree = ast.parse(source)
        changed = transform(tree)

        if not changed:
            return False

        self._write_source(path, ast.unparse(tree))
        return True

    def insert_method(self, path, class_name, position, code):
        """Insert a new method into a class using AST.

        Args:
            path: Path to the Python file.
            class_name: Name of the target class.
            position: Placement position for the method. Only "end" is supported.
            code: Method source code as a string.

        Returns:
            True when the file was modified, False otherwise.

        Behavior:
            If the class does not exist, the operation returns False.

        Example:
            >>> editor.insert_method("sample.py", "Calculator", "end", "def mul(self, a, b):\\n    return a * b")
            True
        """
        return self._apply_transform(
            path,
            lambda tree: self.transformer.insert_method(
                tree,
                class_name,
                position,
                code,
            ),
        )

    def create_class(self, path, class_name, base_classes=None, methods=None):
        """Create a new class at the end of the module.

        Args:
            path: Path to the Python file.
            class_name: Name for the new class.
            base_classes: Optional list of base classes.
            methods: Optional list of method definitions to include.

        Returns:
            True when the class was created, False when it already exists.

        Behavior:
            If the class name already exists, no duplicate class is created.

        Example:
            >>> editor.create_class("sample.py", "Child", base_classes=["Base"], methods=["def greet(self):\\n    return 'hi'"])
            True
        """
        return self._apply_transform(
            path,
            lambda tree: self.transformer.create_class(
                tree,
                class_name,
                base_classes=base_classes,
                methods=methods,
            ),
        )

    def replace_class(self, path, class_name, new_class):
        """Replace an existing class definition in the module.

        Args:
            path: Path to the Python file.
            class_name: Name of the class to replace.
            new_class: New class definition as a string or AST node.

        Returns:
            True when the class was replaced, False when the class does not exist.

        Behavior:
            If the target class is missing, the operation returns False.

        Example:
            >>> editor.replace_class("sample.py", "Calculator", "class Calculator:\n    pass")
            True
        """
        return self._apply_transform(
            path,
            lambda tree: self.transformer.replace_class(
                tree,
                class_name,
                new_class,
            ),
        )

    def ensure_import(self, path, module, name=None, alias=None):
        """Ensure that an import exists in the module.

        Args:
            path: Path to the Python file.
            module: Import module name, such as "os" or "pathlib".
            name: Optional imported symbol for from-import statements.
            alias: Optional alias for the import.

        Returns:
            True when an import was added, False when an equivalent import already exists.

        Behavior:
            If the import already exists, no duplicate import is created.

        Example:
            >>> editor.ensure_import("sample.py", "os")
            True
        """
        return self._apply_transform(
            path,
            lambda tree: self.transformer.ensure_import(
                tree,
                module,
                name=name,
                alias=alias,
            ),
        )

    def remove_import(self, path, module, name=None):
        """Remove an import from the module.

        Args:
            path: Path to the Python file.
            module: Import module name.
            name: Optional symbol to remove from a from-import statement.

        Returns:
            True when an import was removed, False when nothing matched.

        Behavior:
            If the import does not exist, the operation returns False.

        Example:
            >>> editor.remove_import("sample.py", "os")
            True
        """
        return self._apply_transform(
            path,
            lambda tree: self.transformer.remove_import(
                tree,
                module,
                name=name,
            ),
        )

    def has_import(self, path, module, name=None):
        """Check whether a module import exists.

        Args:
            path: Path to the Python file.
            module: Import module name.
            name: Optional symbol to match for from-import statements.

        Returns:
            True when the import exists, False otherwise.

        Behavior:
            If no matching import is found, False is returned.

        Example:
            >>> editor.has_import("sample.py", "os")
            True
        """
        source = self._read_source(path)
        tree = ast.parse(source)
        return self.transformer.has_import(tree, module, name=name)

    def replace_method(self, path, class_name, method_name, new_method):
        """Replace an existing method inside a class.

        Args:
            path: Path to the Python file.
            class_name: Name of the class containing the method.
            method_name: Name of the method to replace.
            new_method: New method definition as a string or AST node.

        Returns:
            True when the method was replaced, False when the method or class is missing.

        Behavior:
            If the target class or method does not exist, the operation returns False.

        Example:
            >>> editor.replace_method("sample.py", "Calculator", "add", "def add(self, a, b):\\n    return a + b")
            True
        """
        return self._apply_transform(
            path,
            lambda tree: self.transformer.replace_method(
                tree,
                class_name,
                method_name,
                new_method,
            ),
        )

    def delete_method(self, path, class_name, method_name):
        """Delete a method from a class.

        Args:
            path: Path to the Python file.
            class_name: Name of the class containing the method.
            method_name: Name of the method to delete.

        Returns:
            True when the method was deleted, False when the method or class is missing.

        Behavior:
            If the target class or method does not exist, the operation returns False.

        Example:
            >>> editor.delete_method("sample.py", "Calculator", "add")
            True
        """
        return self._apply_transform(
            path,
            lambda tree: self.transformer.delete_method(
                tree,
                class_name,
                method_name,
            ),
        )

    def rename_method(self, path, class_name, old_name, new_name):
        """Rename a method in a class.

        Args:
            path: Path to the Python file.
            class_name: Name of the class containing the method.
            old_name: Current method name.
            new_name: New method name.

        Returns:
            True when the method was renamed, False when the method or class is missing.

        Behavior:
            If the target class or method does not exist, the operation returns False.

        Example:
            >>> editor.rename_method("sample.py", "Calculator", "add", "sum")
            True
        """
        return self._apply_transform(
            path,
            lambda tree: self.transformer.rename_method(
                tree,
                class_name,
                old_name,
                new_name,
            ),
        )