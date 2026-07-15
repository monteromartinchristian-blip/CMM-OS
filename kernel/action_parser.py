from kernel.actions.filesystem import (
    WriteFileAction,
    ReadFileAction,
    CreateDirectoryAction,
)


class ActionParser:

    def parse(self, data):

        tool = data["tool"]
        action = data["action"]

        if tool == "filesystem":

            if action == "write_file":
                return WriteFileAction(**data)

            if action == "read_file":
                return ReadFileAction(**data)

            if action == "create_directory":
                return CreateDirectoryAction(**data)

        raise ValueError(
            f"Unknown action: {tool}/{action}"
        )
