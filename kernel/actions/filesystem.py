from dataclasses import dataclass

from kernel.actions.base import Action


@dataclass
class WriteFileAction(Action):

    path: str
    content: str


@dataclass
class ReadFileAction(Action):

    path: str


@dataclass
class CreateDirectoryAction(Action):

    path: str


@dataclass
class ReplaceBlockAction(Action):

    tool: str
    action: str

    path: str

    old: str

    new: str


@dataclass
class InsertAfterAction(Action):

    tool: str
    action: str

    path: str

    anchor: str

    content: str


@dataclass
class InsertBeforeAction(Action):

    tool: str
    action: str

    path: str

    anchor: str

    content: str


@dataclass
class InsertMethodAction(Action):

    tool: str
    action: str

    path: str

    class_name: str

    position: str

    code: str

    scope: str | None = None


@dataclass
class ReplaceMethodAction(Action):

    path: str
    class_name: str
    method_name: str
    code: str
    scope: str | None = None


@dataclass
class DeleteMethodAction(Action):

    path: str
    class_name: str
    method_name: str
    scope: str | None = None


@dataclass
class RenameMethodAction(Action):

    path: str
    class_name: str
    old_name: str
    new_name: str
    scope: str | None = None


@dataclass
class AddImportAction(Action):

    path: str
    module: str
    name: str | None = None
    alias: str | None = None
    level: int = 0


@dataclass
class RemoveImportAction(Action):

    path: str
    module: str
    name: str | None = None
    alias: str | None = None
    level: int = 0


@dataclass
class CreateClassAction(Action):

    path: str
    class_name: str
    scope: str | None = None
    base_classes: list[str] | None = None
    methods: list[str] | None = None


@dataclass
class RenameClassAction(Action):

    path: str
    class_name: str
    new_name: str
    scope: str | None = None


@dataclass
class DeleteClassAction(Action):

    path: str
    class_name: str
    scope: str | None = None
