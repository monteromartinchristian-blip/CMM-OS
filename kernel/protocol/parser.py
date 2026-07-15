from kernel.actions.filesystem import (
    WriteFileAction,
    ReadFileAction,
    CreateDirectoryAction,
    ReplaceBlockAction,
    InsertAfterAction,
    InsertBeforeAction,
    InsertMethodAction,
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

            elif tool == "python":

                if action == "insert_method":

                    actions.append(
                        InsertMethodAction(**item)
                    )

            else:
                raise ValueError(
                    f"Unknown tool: {tool}"
                )

        return Plan(
            version=data["version"],
            actions=actions,
        )