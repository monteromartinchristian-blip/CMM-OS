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