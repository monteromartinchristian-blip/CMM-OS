class PlanNormalizer:

    def normalize(self, plan):

        normalized = []

        seen = set()

        for action in plan.actions:

            key = repr(action)

            if key in seen:
                continue

            seen.add(key)

            normalized.append(action)

        plan.actions = normalized

        return plan