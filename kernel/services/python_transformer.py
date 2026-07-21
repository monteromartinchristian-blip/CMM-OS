import ast
import keyword


class PythonTransformer:

    def _split_scope(self, qualified_name, scope=None):
        if scope:
            parts = [part for part in str(scope).split(".") if part]
            parts.append(str(qualified_name))
            return parts
        return [part for part in str(qualified_name).split(".") if part]

    def _class_children(self, container):
        return [
            (index, node)
            for index, node in enumerate(container.body)
            if isinstance(node, ast.ClassDef)
        ]

    def _find_class_in_container(self, container, name):
        matches = [
            (index, node)
            for index, node in self._class_children(container)
            if node.name == name
        ]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous class: {name}")
        return matches[0] if matches else (None, None)

    def _find_class_by_parts(self, tree, parts):
        container = tree
        index = None
        node = None
        for part in parts:
            index, node = self._find_class_in_container(container, part)
            if node is None:
                return None, None, None
            container = node
        return container if node is not None else None, index, node

    def _find_qualified_class(self, tree, class_name, scope=None):
        parts = self._split_scope(class_name, scope=scope)
        if not parts:
            raise ValueError("Class name must be non-empty.")

        if len(parts) > 1 or scope:
            parent_parts = parts[:-1]
            parent = tree
            if parent_parts:
                _, _, parent_node = self._find_class_by_parts(tree, parent_parts)
                if parent_node is None:
                    return None, None, None
                parent = parent_node
            index, node = self._find_class_in_container(parent, parts[-1])
            return parent, index, node

        matches = []
        for parent in ast.walk(tree):
            if not hasattr(parent, "body"):
                continue
            for index, child in self._class_children(parent):
                if child.name == parts[0]:
                    matches.append((parent, index, child))
        if len(matches) > 1:
            raise ValueError(f"Ambiguous class: {parts[0]}")
        return matches[0] if matches else (None, None, None)

    def _find_method(self, cls, method_name):
        matches = []
        for index, node in enumerate(cls.body):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name:
                matches.append((index, node))
        if len(matches) > 1:
            raise ValueError(f"Ambiguous method: {method_name}")
        return matches[0] if matches else (None, None)

    def _normalize_method(self, method):
        if isinstance(method, str):
            parsed = ast.parse(method)
            if len(parsed.body) != 1:
                raise ValueError("Method code must contain exactly one method.")
            method = parsed.body[0]

        if isinstance(method, ast.Module):
            if len(method.body) != 1:
                raise ValueError("Replacement code must contain exactly one method.")
            method = method.body[0]

        if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise ValueError("Code is not a method.")

        return method

    def _normalize_class(self, class_node):
        if isinstance(class_node, str):
            parsed = ast.parse(class_node)
            if len(parsed.body) != 1:
                raise ValueError("Class code must contain exactly one class.")
            class_node = parsed.body[0]

        if isinstance(class_node, ast.Module):
            if len(class_node.body) != 1:
                raise ValueError("Class code must contain exactly one class.")
            class_node = class_node.body[0]

        if not isinstance(class_node, ast.ClassDef):
            raise ValueError("Code is not a class.")

        return class_node

    def _ensure_class_body(self, cls):
        if not cls.body:
            cls.body.append(ast.Pass())

    def _validate_identifier(self, name, kind):
        if not isinstance(name, str) or not name.isidentifier() or keyword.iskeyword(name):
            raise ValueError(f"Invalid {kind} name: {name}")

    def insert_method(self, tree, class_name, position, code, scope=None):
        _, _, cls = self._find_qualified_class(tree, class_name, scope=scope)
        if cls is None:
            return False
        if position != "end":
            raise ValueError(f"Unsupported position: {position}")
        method = self._normalize_method(code)
        existing_index, _ = self._find_method(cls, method.name)
        if existing_index is not None:
            raise ValueError(f"Method already exists: {method.name}")
        if len(cls.body) == 1 and isinstance(cls.body[0], ast.Pass):
            cls.body = []
        cls.body.append(method)
        return True

    def create_class(self, tree, class_name, base_classes=None, methods=None, scope=None):
        self._validate_identifier(class_name, "class")
        base_classes = base_classes or []
        methods = methods or []
        parent = tree
        if scope:
            _, _, parent_node = self._find_qualified_class(tree, scope)
            if parent_node is None:
                return False
            parent = parent_node

        index, _ = self._find_class_in_container(parent, class_name)
        if index is not None:
            return False

        bases = [
            ast.Name(id=base, ctx=ast.Load()) if isinstance(base, str) else base
            for base in base_classes
        ]
        body = [self._normalize_method(method) for method in methods]
        if not body:
            body = [ast.Pass()]
        if isinstance(parent, ast.ClassDef) and len(parent.body) == 1 and isinstance(parent.body[0], ast.Pass):
            parent.body = []
        parent.body.append(
            ast.ClassDef(
                name=class_name,
                bases=bases,
                keywords=[],
                body=body,
                decorator_list=[],
            )
        )
        return True

    def replace_class(self, tree, class_name, new_class, scope=None):
        parent, index, _ = self._find_qualified_class(tree, class_name, scope=scope)
        if parent is None:
            return False
        parent.body[index] = self._normalize_class(new_class)
        return True

    def rename_class(self, tree, class_name, new_name, scope=None):
        self._validate_identifier(new_name, "class")
        parent, _, cls = self._find_qualified_class(tree, class_name, scope=scope)
        if cls is None:
            return False
        conflict_index, _ = self._find_class_in_container(parent, new_name)
        if conflict_index is not None:
            raise ValueError(f"Class already exists: {new_name}")
        cls.name = new_name
        return True

    def delete_class(self, tree, class_name, scope=None):
        parent, index, _ = self._find_qualified_class(tree, class_name, scope=scope)
        if parent is None:
            return False
        del parent.body[index]
        if isinstance(parent, ast.ClassDef):
            self._ensure_class_body(parent)
        return True

    def _parse_import_target(self, module, level=0):
        if module is None:
            module = ""
        module = str(module)
        if module.startswith("."):
            inferred_level = len(module) - len(module.lstrip("."))
            level = inferred_level
            module = module[inferred_level:]
        return module or None, int(level or 0)

    def _normalize_import(self, module, name=None, alias=None, level=0):
        module, level = self._parse_import_target(module, level=level)
        if name is None and level == 0:
            return ast.Import(names=[ast.alias(name=module, asname=alias)])
        if name is None:
            raise ValueError("Relative imports require an imported name.")
        return ast.ImportFrom(
            module=module,
            names=[ast.alias(name=name, asname=alias)],
            level=level,
        )

    def _import_matches(self, node, module, name=None, alias=None, level=0):
        module, level = self._parse_import_target(module, level=level)
        if isinstance(node, ast.Import):
            if name is not None or level != 0:
                return False
            return any(item.name == module and (alias is None or item.asname == alias) for item in node.names)
        if isinstance(node, ast.ImportFrom):
            if node.module != module or node.level != level:
                return False
            if name is None:
                return alias is None
            return any(item.name == name and (alias is None or item.asname == alias) for item in node.names)
        return False

    def has_import(self, tree, module, name=None, alias=None, level=0):
        return any(
            self._import_matches(node, module, name=name, alias=alias, level=level)
            for node in tree.body
        )

    def ensure_import(self, tree, module, name=None, alias=None, level=0):
        if self.has_import(tree, module, name=name, alias=alias, level=level):
            return False
        tree.body.insert(0, self._normalize_import(module, name=name, alias=alias, level=level))
        return True

    def remove_import(self, tree, module, name=None, alias=None, level=0):
        module, level = self._parse_import_target(module, level=level)
        changed = False
        new_body = []

        for node in tree.body:
            if isinstance(node, ast.Import):
                if name is not None or level != 0:
                    new_body.append(node)
                    continue
                remaining = [
                    item
                    for item in node.names
                    if not (item.name == module and (alias is None or item.asname == alias))
                ]
                changed = changed or len(remaining) != len(node.names)
                if remaining:
                    node.names = remaining
                    new_body.append(node)
            elif isinstance(node, ast.ImportFrom):
                if node.module != module or node.level != level:
                    new_body.append(node)
                    continue
                if name is None:
                    changed = True
                    continue
                remaining = [
                    item
                    for item in node.names
                    if not (item.name == name and (alias is None or item.asname == alias))
                ]
                changed = changed or len(remaining) != len(node.names)
                if remaining:
                    node.names = remaining
                    new_body.append(node)
            else:
                new_body.append(node)

        tree.body = new_body
        return changed

    def rename_method(self, tree, class_name, old_name, new_name, scope=None):
        self._validate_identifier(new_name, "method")
        _, _, cls = self._find_qualified_class(tree, class_name, scope=scope)
        if cls is None:
            return False
        conflict_index, _ = self._find_method(cls, new_name)
        if conflict_index is not None:
            raise ValueError(f"Method already exists: {new_name}")
        _, method = self._find_method(cls, old_name)
        if method is None:
            return False
        method.name = new_name
        return True

    def replace_method(self, tree, class_name, method_name, new_method, scope=None):
        _, _, cls = self._find_qualified_class(tree, class_name, scope=scope)
        if cls is None:
            return False
        index, _ = self._find_method(cls, method_name)
        if index is None:
            return False
        replacement = self._normalize_method(new_method)
        cls.body[index] = replacement
        return True

    def delete_method(self, tree, class_name, method_name, scope=None):
        _, _, cls = self._find_qualified_class(tree, class_name, scope=scope)
        if cls is None:
            return False
        index, _ = self._find_method(cls, method_name)
        if index is None:
            return False
        del cls.body[index]
        self._ensure_class_body(cls)
        return True
