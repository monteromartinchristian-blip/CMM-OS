import json
from pathlib import Path


class PlanStore:

    def __init__(self, root: Path):
        self.file = root / ".cmm" / "last_plan.json"

    def save(self, plan):

        self.file.parent.mkdir(parents=True, exist_ok=True)

        self.file.write_text(
            json.dumps(plan, indent=2),
            encoding="utf-8"
        )

    def load(self):

        if not self.file.exists():
            return None

        return json.loads(
            self.file.read_text(encoding="utf-8")
        )
