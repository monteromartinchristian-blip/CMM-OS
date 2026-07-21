from kernel.actions.filesystem import (
    WriteFileAction,
    ReadFileAction,
    CreateDirectoryAction,
    ReplaceBlockAction,
    InsertAfterAction,
    InsertBeforeAction,
    InsertMethodAction,
    ReplaceMethodAction,
    DeleteMethodAction,
    RenameMethodAction,
    AddImportAction,
    RemoveImportAction,
    CreateClassAction,
    RenameClassAction,
    DeleteClassAction,
)

from kernel.protocol.plan import Plan


class PlanParser:

    def parse(self, data):

        actions = []

        for item in data["actions"]:

            tool = item["tool"]
            action = item["action"]

            if tool == "filesystem":

                if action == "write_file":
                    actions.append(WriteFileAction(**item))

                elif action == "read_file":
                    actions.append(ReadFileAction(**item))

                elif action == "create_directory":
                    actions.append(CreateDirectoryAction(**item))

                else:
                    raise ValueError(
                        f"Unknown filesystem action: {action}"
                    )

            elif tool == "diff":

                if action == "replace_block":
                    actions.append(
                        ReplaceBlockAction(**item)
                    )

                elif action == "insert_after":
                    actions.append(
                        InsertAfterAction(**item)
                    )

                elif action == "insert_before":
                    actions.append(
                        InsertBeforeAction(**item)
                    )

                else:
                    raise ValueError(
                        f"Unknown diff action: {action}"
                    )

            elif tool == "python":

                if action == "insert_method":

                    actions.append(
                        InsertMethodAction(**item)
                    )

                elif action == "replace_method":
                    actions.append(ReplaceMethodAction(**item))

                elif action == "delete_method":
                    actions.append(DeleteMethodAction(**item))

                elif action == "rename_method":
                    actions.append(RenameMethodAction(**item))

                elif action == "add_import":
                    actions.append(AddImportAction(**item))

                elif action == "remove_import":
                    actions.append(RemoveImportAction(**item))

                elif action == "create_class":
                    actions.append(CreateClassAction(**item))

                elif action == "rename_class":
                    actions.append(RenameClassAction(**item))

                elif action == "delete_class":
                    actions.append(DeleteClassAction(**item))

                else:
                    raise ValueError(
                        f"Unknown python action: {action}"
                    )

            else:
                raise ValueError(
                    f"Unknown tool: {tool}"
                )

        return Plan(
            version=data["version"],
            actions=actions,
        )
