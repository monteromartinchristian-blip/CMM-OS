from kernel.model.architecture import (
    Architecture,
    Component,
    Service,
    Tool,
)
from kernel.services.project_analyzer import ProjectAnalyzer
from kernel.services.registry import RegistryService


class ArchitectureBuilder:

    def __init__(self, project_root):
        self.project_root = project_root

    def build(self):

        registry = RegistryService(self.project_root)
        analyzer = ProjectAnalyzer(self.project_root)

        architecture = Architecture()

        for c in registry.list():

            architecture.components.append(
                Component(
                    id=c["id"],
                    name=c["name"],
                    type=c["type"],
                    status=c["status"],
                )
            )

        for service in analyzer.services():
            architecture.services.append(Service(service))

        for tool in analyzer.tools():
            architecture.tools.append(Tool(tool))

        return architecture
