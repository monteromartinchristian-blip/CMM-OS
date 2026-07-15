from pathlib import Path
import textwrap

from kernel.services.python_locator import PythonLocator
from kernel.services.python_validator import PythonValidator


class PythonEditor:

    def __init__(self):

        self.locator = PythonLocator()

        self.validator = PythonValidator()

    def insert_method(
        self,
        path,
        class_name,
        position,
        code,
    ):

        path = Path(path)

        if position != "end":
            raise ValueError(
                f"Unsupported position: {position}"
            )

        last_method = self.locator.find_last_method(
            path,
            class_name,
        )

        if last_method is None:
            raise ValueError(
                f"Class '{class_name}' has no methods."
            )

        lines = path.read_text(
            encoding="utf-8"
        ).splitlines()

        insert_at = last_method["end_lineno"]

        code = textwrap.dedent(
            code
        ).strip()

        method_lines = []

        for line in code.splitlines():

            if line.strip():

                method_lines.append(
                    "    " + line
                )

            else:

                method_lines.append("")

        lines[insert_at:insert_at] = (
            [""]
            + method_lines
            + [""]
        )

        text = "\n".join(lines)

        self.validator.validate(text)

        path.write_text(
            text,
            encoding="utf-8",
        )

        return path