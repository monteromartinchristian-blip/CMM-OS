from kernel.services.python_index import PythonIndex


class PythonLocator:

    def __init__(self):

        self.index = PythonIndex()

    def find_class(
        self,
        path,
        class_name,
    ):

        data = self.index.index(path)

        for cls in data["classes"]:

            if cls["name"] == class_name:
                return cls

        return None

    def find_method(
        self,
        path,
        class_name,
        method_name,
    ):

        cls = self.find_class(
            path,
            class_name,
        )

        if cls is None:
            return None

        for method in cls["methods"]:

            if method["name"] == method_name:
                return method

        return None

    def find_last_method(
        self,
        path,
        class_name,
    ):

        cls = self.find_class(
            path,
            class_name,
        )

        if cls is None:
            return None

        methods = cls["methods"]

        if not methods:
            return None

        return methods[-1]