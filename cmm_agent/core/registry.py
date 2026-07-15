import json

from cmm_agent.core.paths import REGISTRY_DIR

def load_components():

    components = []

    if not REGISTRY_DIR.exists():
        return components

    for file in sorted(REGISTRY_DIR.glob("*.json")):
        with open(file, "r", encoding="utf-8") as f:
            components.append(json.load(f))

    return components
