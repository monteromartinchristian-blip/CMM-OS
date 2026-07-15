from pathlib import Path

from kernel.services.python_index import PythonIndex


class CodeContextBuilder:

    def __init__(self):

        self.indexer = PythonIndex()

    def read(self, path):

        path = Path(path)

        data = {
            "path": str(path),
            "content": path.read_text(
                encoding="utf-8"
            ),
        }

        if path.suffix == ".py":
            data["index"] = self.indexer.index(path)

        return data

    def read_many(self, paths):

        return [
            self.read(path)
            for path in paths
        ]

    def build(self, root, paths):

        root = Path(root)

        contexts = []

        for path in paths:

            full_path = root / path

            if not full_path.exists():
                continue

            contexts.append(
                self.read(full_path)
            )

        return contexts