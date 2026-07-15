from datetime import datetime


class ExecutionLog:

    def __init__(self):

        self.entries = []

    def record(self, action, result):

        self.entries.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "action": type(action).__name__,
                "result": str(result),
            }
        )

    def all(self):

        return list(self.entries)