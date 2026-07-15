from pathlib import Path

from kernel.services.python_validator import PythonValidator

class DiffEngine:

    def __init__(self):
        self.validator = PythonValidator()

    def replace_block(
        self,
        path,
        old,
        new,
    ):

        path = Path(path)

        text = path.read_text(
            encoding="utf-8"
        )

        if old not in text:
            raise ValueError(
                "Block not found."
            )

        text = text.replace(
            old,
            new,
            1,
        )

        if path.suffix == ".py":
            self.validator.validate(text)

        path.write_text(
            text,
            encoding="utf-8"
        )

        return path

    def insert_after(
        self,
        path,
        anchor,
        content,
    ):

        path = Path(path)

        text = path.read_text(
            encoding="utf-8"
        )

        if anchor not in text:
            raise ValueError(
                "Anchor not found."
            )

        if anchor.strip().startswith("class "):
            raise ValueError(
                "Class declarations cannot be used as anchors."
            )

        text = text.replace(
            anchor,
            anchor + content,
            1,
        )

        if path.suffix == ".py":
            self.validator.validate(text)

        path.write_text(
            text,
            encoding="utf-8"
        )

        return path

    def insert_before(
        self,
        path,
        anchor,
        content,
    ):

        path = Path(path)

        text = path.read_text(
            encoding="utf-8"
        )

        if anchor not in text:
            raise ValueError(
                "Anchor not found."
            )

        if anchor.strip().startswith("class "):
            raise ValueError(
                "Class declarations cannot be used as anchors."
            )

        text = text.replace(
            anchor,
            content + anchor,
            1,
        )

        if path.suffix == ".py":
            self.validator.validate(text)

        path.write_text(
            text,
            encoding="utf-8"
        )

        return path