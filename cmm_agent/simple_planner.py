class SimplePlanner:

    def plan(self, goal: str):

        goal = goal.lower()

        if "crea archivo" in goal:

            return {
                "tool": "filesystem",
                "action": "write_file",
                "path": "planner_demo.txt",
                "content": "Creado por el Planner"
            }

        return None
