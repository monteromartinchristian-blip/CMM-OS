from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

AGENT_ROOT = PROJECT_ROOT / "agents" / "cmm-agent"

REGISTRY_DIR = PROJECT_ROOT / "registry" / "components"

PROMPTS_DIR = AGENT_ROOT / "prompts"

CONFIG_DIR = AGENT_ROOT / "config"

TOOLS_DIR = AGENT_ROOT / "tools"
