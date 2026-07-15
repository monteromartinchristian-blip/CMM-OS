#!/usr/bin/env python3

import sys

from cmm_agent.agent import Agent


def main():

    if len(sys.argv) < 2:
        print("Uso:")
        print('python3 runtime.py "Pregunta"')
        return

    goal = " ".join(sys.argv[1:])

    result = Agent().run(goal)

    print()

    print(result)


if __name__ == "__main__":
    main()
