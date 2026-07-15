from pathlib import Path


class FileSystemService:

    def read(self, path):
        return Path(path).read_text(encoding="utf-8")

    def write(self, path, content):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def exists(self, path):
        return Path(path).exists()

    def mkdir(self, path):
        Path(path).mkdir(parents=True, exist_ok=True)
