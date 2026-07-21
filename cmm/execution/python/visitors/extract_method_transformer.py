"""LibCST transformer for applying a validated method extraction."""

from __future__ import annotations

import libcst as cst

from cmm.execution.python.extract_method_analysis import MethodExtractionAnalysis


class ExtractMethodTransformer(cst.CSTTransformer):
    def __init__(self, class_name: str, method_name: str, new_method_name: str, analysis: MethodExtractionAnalysis) -> None:
        self._class_name = class_name
        self._method_name = method_name
        self._new_method_name = new_method_name
        self._analysis = analysis
        self.changed = False

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.ClassDef:
        if original_node.name.value != self._class_name:
            return updated_node
        if not isinstance(updated_node.body, cst.IndentedBlock):
            return updated_node
        body = list(updated_node.body.body)
        for index, statement in enumerate(body):
            if not isinstance(statement, cst.FunctionDef) or statement.name.value != self._method_name:
                continue
            if not isinstance(statement.body, cst.IndentedBlock):
                return updated_node
            selected = tuple(statement.body.body[self._start_index():self._end_index()])
            call = self._call_statement(statement)
            original_body = statement.body.with_changes(
                body=tuple((*statement.body.body[:self._start_index()], call, *statement.body.body[self._end_index():]))
            )
            extracted = statement.with_changes(
                name=cst.Name(self._new_method_name),
                decorators=(),
                params=self._extracted_params(statement),
                body=statement.body.with_changes(
                    body=tuple(
                        (*selected, self._return_statement())
                        if self._analysis.output
                        else selected
                    )
                ),
            )
            body[index] = statement.with_changes(body=original_body)
            body.insert(index + 1, extracted)
            self.changed = True
            break
        return updated_node.with_changes(body=updated_node.body.with_changes(body=tuple(body)))

    def _start_index(self) -> int:
        return self._analysis.method.body.index(self._analysis.selected[0])

    def _end_index(self) -> int:
        return self._start_index() + len(self._analysis.selected)

    def _receiver(self, statement: cst.FunctionDef) -> str | None:
        for decorator in statement.decorators:
            if isinstance(decorator.decorator, cst.Name) and decorator.decorator.value == "staticmethod":
                return None
        params = (*statement.params.posonly_params, *statement.params.params)
        return params[0].name.value if params else None

    def _extracted_params(self, statement: cst.FunctionDef) -> cst.Parameters:
        names = set(self._analysis.inputs)
        receiver = self._receiver(statement)
        if receiver:
            names.add(receiver)
        params = tuple(
            parameter for parameter in statement.params.params
            if parameter.name.value in names
        )
        posonly = tuple(
            parameter for parameter in statement.params.posonly_params
            if parameter.name.value in names
        )
        kwonly = tuple(
            parameter for parameter in statement.params.kwonly_params
            if parameter.name.value in names
        )
        star_arg = statement.params.star_arg
        if isinstance(star_arg, cst.Param) and star_arg.name.value not in names:
            star_arg = cst.MaybeSentinel.DEFAULT
        star_kwarg = statement.params.star_kwarg
        if isinstance(star_kwarg, cst.Param) and star_kwarg.name.value not in names:
            star_kwarg = cst.MaybeSentinel.DEFAULT
        return statement.params.with_changes(
            posonly_params=posonly,
            params=params,
            kwonly_params=kwonly,
            star_arg=star_arg,
            star_kwarg=star_kwarg,
        )

    def _call_statement(self, statement: cst.FunctionDef) -> cst.BaseStatement:
        receiver = self._receiver(statement)
        if receiver:
            callee = f"{receiver}.{self._new_method_name}"
        elif any(
            isinstance(decorator.decorator, cst.Name) and decorator.decorator.value == "staticmethod"
            for decorator in statement.decorators
        ):
            callee = f"{self._class_name}.{self._new_method_name}"
        else:
            callee = self._new_method_name
        kwonly = {parameter.name.value for parameter in statement.params.kwonly_params}
        vararg = (
            statement.params.star_arg.name.value
            if isinstance(statement.params.star_arg, cst.Param)
            else None
        )
        kwarg = (
            statement.params.star_kwarg.name.value
            if isinstance(statement.params.star_kwarg, cst.Param)
            else None
        )
        args = ", ".join(
            f"**{name}" if name == kwarg else f"*{name}" if name == vararg else f"{name}={name}" if name in kwonly else name
            for name in self._analysis.inputs
        )
        call = f"{callee}({args})"
        if isinstance(statement, cst.FunctionDef) and statement.asynchronous:
            call = f"await {call}"
        if self._analysis.output:
            call = f"{self._analysis.output} = {call}"
        return cst.parse_statement(call + "\n")

    def _return_statement(self) -> cst.BaseStatement:
        return cst.parse_statement(f"return {self._analysis.output}\n")
