import ast


class PythonTransformer:

    def _find_class(
        self,
        tree,
        class_name,
    ):

        for node in tree.body:

            if (
                isinstance(node, ast.ClassDef)
                and node.name == class_name
            ):
                return node

        return None

    def _find_method(
        self,
        cls,
        method_name,
    ):

        for index, node in enumerate(cls.body):

            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):

                if node.name == method_name:

                    return index, node

        return None, None

    def _normalize_method(
        self,
        method,
    ):

        if isinstance(method, str):
            parsed = ast.parse(method)

            if len(parsed.body) != 1:
                raise ValueError(
                    "Method code must contain exactly one method."
                )

            method = parsed.body[0]

        if isinstance(method, ast.Module):

            if len(method.body) != 1:
                raise ValueError(
                    "Replacement code must contain exactly one method."
                )

            method = method.body[0]

        if not isinstance(
            method,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            raise ValueError(
                "Code is not a method."
            )

        return method

    def insert_method(
        self,
        tree,
        class_name,
        position,
        code,
    ):
        """Insert a new method into a class using AST.

        Args:
            tree: AST tree representing the Python module.
            class_name: Name of the class receiving the method.
            position: Placement position for the method. Only "end" is supported.
            code: Method source code as a string or AST node.

        Returns:
            True when the method is inserted, False when the class is missing.

        Behavior:
            If the class does not exist, the operation returns False.

        Example:
            >>> transformer.insert_method(tree, "Calculator", "end", "def mul(self, a, b):\\n    return a * b")
            True
        """
        cls = self._find_class(
            tree,
            class_name,
        )

        if cls is None:
            return False

        if position != "end":
            raise ValueError(
                f"Unsupported position: {position}"
            )

        method = self._normalize_method(code)
        cls.body.append(method)

        return True

    def create_class(
        self,
        tree,
        class_name,
        base_classes=None,
        methods=None,
    ):
        """Create a new class at the end of the module.

        Args:
            tree: AST tree representing the Python module.
            class_name: Name for the new class.
            base_classes: Optional list of base classes.
            methods: Optional list of method definitions.

        Returns:
            True when the class is created, False when it already exists.

        Behavior:
            If the class name already exists, no duplicate class is created.

        Example:
            >>> transformer.create_class(tree, "Child", base_classes=["Base"], methods=["def greet(self):\\n    return 'hi'"])
            True
        """
        if self._find_class(tree, class_name) is not None:
            return False

        if base_classes is None:
            base_classes = []

        if methods is None:
            methods = []

        bases = []

        for base in base_classes:
            if isinstance(base, str):
                bases.append(ast.Name(id=base, ctx=ast.Load()))
            else:
                bases.append(base)

        class_body = []

        for method in methods:
            method_node = self._normalize_method(method)
            class_body.append(method_node)

        new_class = ast.ClassDef(
            name=class_name,
            bases=bases,
            keywords=[],
            body=class_body,
            decorator_list=[],
        )

        tree.body.append(new_class)
        return True

    def replace_class(
        self,
        tree,
        class_name,
        new_class,
    ):
        """Replace an existing class definition in the module.

        Args:
            tree: AST tree representing the Python module.
            class_name: Name of the class to replace.
            new_class: New class definition as a string or AST node.

        Returns:
            True when the class is replaced, False when the class is missing.

        Behavior:
            If the target class does not exist, the operation returns False.

        Example:
            >>> transformer.replace_class(tree, "Calculator", "class Calculator:\n    pass")
            True
        """
        cls = self._find_class(
            tree,
            class_name,
        )

        if cls is None:
            return False

        if isinstance(new_class, str):
            parsed = ast.parse(new_class)

            if len(parsed.body) != 1:
                raise ValueError(
                    "Replacement code must contain exactly one class."
                )

            new_class = parsed.body[0]

        if isinstance(new_class, ast.Module):

            if len(new_class.body) != 1:
                raise ValueError(
                    "Replacement code must contain exactly one class."
                )

            new_class = new_class.body[0]

        if not isinstance(new_class, ast.ClassDef):
            raise ValueError(
                "Replacement code is not a class."
            )

        for index, node in enumerate(tree.body):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                tree.body[index] = new_class
                return True

        return False

    def _normalize_import(self, module, name=None, alias=None):
        if name is None and alias is None:
            return ast.Import(names=[ast.alias(name=module)])

        if alias is not None:
            return ast.Import(names=[ast.alias(name=module, asname=alias)])

        return ast.ImportFrom(
            module=module,
            names=[ast.alias(name=name)],
            level=0,
        )

    def _import_matches(self, node, module, name=None, alias=None):
        if isinstance(node, ast.Import):
            for import_alias in node.names:
                if import_alias.name != module:
                    continue

                if alias is None:
                    if name is None:
                        return import_alias.asname is None
                    return False

                return import_alias.asname == alias

            return False

        if isinstance(node, ast.ImportFrom):
            if node.module != module:
                return False

            for import_alias in node.names:
                if name is not None and import_alias.name != name:
                    continue

                if alias is None:
                    return import_alias.asname is None

                return import_alias.asname == alias

        return False

    def has_import(self, tree, module, name=None):
        """Check whether an import exists in the module.

        Args:
            tree: AST tree representing the Python module.
            module: Import module name.
            name: Optional symbol to match for from-import statements.

        Returns:
            True when the import exists, False otherwise.

        Behavior:
            If the import is missing, False is returned.

        Example:
            >>> transformer.has_import(tree, "os")
            True
        """
        for node in tree.body:
            if self._import_matches(node, module, name=name):
                return True

        return False

    def ensure_import(self, tree, module, name=None, alias=None):
        """Ensure that an import exists in the module.

        Args:
            tree: AST tree representing the Python module.
            module: Import module name.
            name: Optional imported symbol for from-import statements.
            alias: Optional alias for the import.

        Returns:
            True when an import is added, False when an equivalent import already exists.

        Behavior:
            If the import already exists, no duplicate import is created.

        Example:
            >>> transformer.ensure_import(tree, "os")
            True
        """
        for node in tree.body:
            if self._import_matches(node, module, name=name, alias=alias):
                return False

        import_node = self._normalize_import(module, name=name, alias=alias)
        tree.body.insert(0, import_node)
        return True

    def remove_import(self, tree, module, name=None):
        """Remove an import from the module.

        Args:
            tree: AST tree representing the Python module.
            module: Import module name.
            name: Optional symbol to remove from a from-import.

        Returns:
            True when an import was removed, False when nothing matched.

        Behavior:
            If the target import does not exist, the operation returns False.

        Example:
            >>> transformer.remove_import(tree, "os")
            True
        """
        changed = False
        new_body = []

        for node in tree.body:
            if isinstance(node, ast.Import):
                remaining = []
                for alias in node.names:
                    if alias.name == module and (name is None or alias.name == module):
                        changed = True
                    else:
                        remaining.append(alias)

                if remaining:
                    node.names = remaining
                    new_body.append(node)
            elif isinstance(node, ast.ImportFrom):
                if node.module == module and (name is None or any(alias.name == name for alias in node.names)):
                    changed = True
                    continue

                new_body.append(node)
            else:
                new_body.append(node)

        tree.body = new_body
        return changed

    def rename_method(
        self,
        tree,
        class_name,
        old_name,
        new_name,
    ):
        """Rename a method in a class.

        Args:
            tree: AST tree representing the Python module.
            class_name: Name of the class containing the method.
            old_name: Current method name.
            new_name: New method name.

        Returns:
            True when the method is renamed, False when the class or method is missing.

        Behavior:
            If the target class or method does not exist, the operation returns False.

        Example:
            >>> transformer.rename_method(tree, "Calculator", "add", "sum")
            True
        """
        cls = self._find_class(
            tree,
            class_name,
        )

        if cls is None:
            return False

        _, method = self._find_method(
            cls,
            old_name,
        )

        if method is None:
            return False

        method.name = new_name

        return True

    def replace_method(
        self,
        tree,
        class_name,
        method_name,
        new_method,
    ):
        """Replace an existing method inside a class.

        Args:
            tree: AST tree representing the Python module.
            class_name: Name of the class containing the method.
            method_name: Name of the method to replace.
            new_method: New method definition as a string or AST node.

        Returns:
            True when the method is replaced, False when the class or method is missing.

        Behavior:
            If the target class or method does not exist, the operation returns False.

        Example:
            >>> transformer.replace_method(tree, "Calculator", "add", "def add(self, a, b):\\n    return a + b")
            True
        """
        cls = self._find_class(
            tree,
            class_name,
        )

        if cls is None:
            return False

        index, _ = self._find_method(
            cls,
            method_name,
        )

        if index is None:
            return False

        new_method = self._normalize_method(new_method)
        cls.body[index] = new_method

        return True

    def delete_method(
        self,
        tree,
        class_name,
        method_name,
    ):
        """Delete a method from a class.

        Args:
            tree: AST tree representing the Python module.
            class_name: Name of the class containing the method.
            method_name: Name of the method to delete.

        Returns:
            True when the method is deleted, False when the class or method is missing.

        Behavior:
            If the target class or method does not exist, the operation returns False.

        Example:
            >>> transformer.delete_method(tree, "Calculator", "add")
            True
        """
        cls = self._find_class(
            tree,
            class_name,
        )

        if cls is None:
            return False

        index, _ = self._find_method(
            cls,
            method_name,
        )

        if index is None:
            return False

        del cls.body[index]

        return True