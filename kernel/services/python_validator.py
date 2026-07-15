import ast


class PythonValidator:

    def validate(self, code: str):

        ast.parse(code)