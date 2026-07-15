import json

from kernel.protocol.normalizer import ResponseNormalizer

from cmm_agent.prompts import load_prompt


def build_prompt(goal, architecture, code_contexts):

    system = load_prompt("planner.system")

    sections = [
        system,
        "",
        "Architecture:",
        architecture,
    ]

    if code_contexts:

        sections.append("")
        sections.append("Relevant files:")

        for ctx in code_contexts:

            sections.append("")
            sections.append(f"### {ctx['path']}")

            index = ctx.get("index")

            if index:

                if index["classes"]:

                    sections.append("")
                    sections.append("Classes:")

                    for cls in index["classes"]:

                        sections.append(
                            f"- {cls['name']}"
                        )

                        for method in cls["methods"]:

                            sections.append(
                                f"  - {method}"
                            )

                if index["functions"]:

                    sections.append("")
                    sections.append("Functions:")

                    for function in index["functions"]:

                        sections.append(
                            f"- {function}"
                        )

            sections.append("")
            sections.append("Source:")
            sections.append(ctx["content"])

    sections.append("")
    sections.append("Goal:")
    sections.append(goal)

    return "\n".join(sections)


def parse_plan(response: str):

    response = ResponseNormalizer().normalize(response)

    try:
        return json.loads(response)

    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Planner returned invalid JSON:\n\n{response}"
        ) from e