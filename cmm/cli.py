import json
import sys
from pathlib import Path

from kernel.kernel import Kernel
from cmm_agent.agent import Agent

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def usage():
    print("CMM OS")
    print()
    print("Uso:")
    print("  cmm doctor")
    print("  cmm registry list")
    print("  cmm plan <goal>")
    print("  cmm apply")
    print("  cmm develop <goal>")


def registry_list():

    kernel = Kernel(PROJECT_ROOT)

    for component in kernel.registry.list():
        print(
            f"{component['id']:12} "
            f"{component['status']:13} "
            f"{component['name']}"
        )


def doctor():

    kernel = Kernel(PROJECT_ROOT)

    print("== CMM OS Doctor ==")
    print()
    print("Project root :", PROJECT_ROOT)
    print("Registry     : OK")
    print("Components   :", len(kernel.registry.list()))


def main():

    if len(sys.argv) < 2:
        usage()
        return

    command = sys.argv[1]

    if command == "doctor":
        doctor()
        return

    if command == "registry":

        if len(sys.argv) >= 3 and sys.argv[2] == "list":
            registry_list()
            return

        usage()
        return

    agent = Agent(PROJECT_ROOT)

    if command == "plan":

        goal = " ".join(sys.argv[2:])

        plan = agent.plan(goal)

        print(json.dumps(plan, indent=2))
        return

    if command == "apply":

        print(agent.apply())
        return

    if command == "develop":

        goal = " ".join(sys.argv[2:])

        print()
        print("=== DEVELOP ===")
        print()

        result = agent.develop(goal)

        print(result)

        return

    usage()


if __name__ == "__main__":
    main()
