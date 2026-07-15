from kernel.services.architecture_builder import ArchitectureBuilder

from cmm_agent.core.paths import PROJECT_ROOT


def build_context():

    architecture = ArchitectureBuilder(PROJECT_ROOT).build()

    lines = []

    lines.append("Components:")

    for c in architecture.components:
        lines.append(
            f"- {c.id} | {c.name} | {c.status}"
        )

    lines.append("")
    lines.append("Services:")

    for s in architecture.services:
        lines.append(f"- {s.name}")

    lines.append("")
    lines.append("Tools:")

    for t in architecture.tools:
        lines.append(f"- {t.name}")

    return "\n".join(lines)
