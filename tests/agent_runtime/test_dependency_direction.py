from __future__ import annotations

import json
import subprocess
import sys


def test_importing_agent_runtime_does_not_load_domains() -> None:
    program = """
import json
import sys
import cmm.agent_runtime

print(json.dumps(sorted(
    name for name in sys.modules
    if name == "cmm.domains" or name.startswith("cmm.domains.")
)))
"""
    completed = subprocess.run(
        [sys.executable, "-c", program],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == []
