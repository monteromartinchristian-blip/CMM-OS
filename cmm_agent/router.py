class IntentRouter:

    def route(self, goal: str) -> str:

        goal = goal.lower()

        knowledge_keywords = [
            "qué componentes",
            "que componentes",
            "implementados",
            "planned",
            "planificados",
            "registry",
            "registro",
            "existe",
            "listar",
            "lista",
            "componentes"
        ]

        for keyword in knowledge_keywords:
            if keyword in goal:
                return "knowledge"

        return "planner"
