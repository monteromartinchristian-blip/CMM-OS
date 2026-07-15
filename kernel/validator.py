class ValidationError(Exception):
    pass


class PlanValidator:

    REQUIRED = {
        ("filesystem", "write_file"): [
            "tool",
            "action",
            "path",
            "content",
        ],
        ("filesystem", "read_file"): [
            "tool",
            "action",
            "path",
        ],
        ("filesystem", "create_directory"): [
            "tool",
            "action",
            "path",
        ],
        ("diff", "replace_block"): [
            "tool",
            "action",
            "path",
            "old",
            "new",
        ],
        ("diff", "insert_after"): [
            "tool",
            "action",
            "path",
            "anchor",
            "content",
        ],
        ("diff", "insert_before"): [
            "tool",
            "action",
            "path",
            "anchor",
            "content",
        ],
        ("python", "insert_method"): [
            "tool",
            "action",
            "path",
            "class_name",
            "position",
            "code",
        ],
    }

    def validate(self, plan):

        if "actions" not in plan:
            raise ValidationError(
                "Plan has no actions."
            )

        for action in plan["actions"]:

            key = (
                action.get("tool"),
                action.get("action"),
            )

            if key not in self.REQUIRED:
                raise ValidationError(
                    f"Unsupported action: {key}"
                )

            for field in self.REQUIRED[key]:

                if field not in action:
                    raise ValidationError(
                        f"Missing field '{field}'"
                    )

        return True
