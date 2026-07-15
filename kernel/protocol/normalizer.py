class ResponseNormalizer:

    def normalize(self, response: str) -> str:

        response = response.strip()

        if response.startswith("```json"):
            response = response[len("```json"):]

        if response.startswith("```"):
            response = response[len("```"):]

        if response.endswith("```"):
            response = response[:-3]

        return response.strip()
