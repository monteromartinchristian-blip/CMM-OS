class Tool:

    name = "tool"

    def can_handle(self, goal: str) -> bool:
        raise NotImplementedError

    def execute(self, goal: str):
        raise NotImplementedError
