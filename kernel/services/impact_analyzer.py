from pathlib import Path


class ImpactAnalyzer:

    def __init__(self, root: Path):
        self.root = Path(root)

    def analyze(self, goal: str):

        goal = goal.lower()

        candidates = []

        if "kernel" in goal:
            candidates.append("kernel/kernel.py")

        if "runtime" in goal:
            candidates.append("kernel/runtime.py")

        if "parser" in goal:
            candidates.append("kernel/protocol/parser.py")

        if "executor" in goal:
            candidates.append("kernel/executor.py")

        return candidates
