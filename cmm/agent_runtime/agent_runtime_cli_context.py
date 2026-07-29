"""Phase 9.22 – Agent Runtime CLI Context Builder.

Builds an ``AgentRuntimeApiContext`` from CLI arguments, a small whitelist
of environment variables, and an optional JSON config file, with a strict
precedence: CLI > environment > config > safe defaults.

Never reads the environment indiscriminately: only the five variables
listed below are consulted. Never invents an actor or permission for a
mutating operation - those must come from an explicit source.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from cmm.agent_runtime.agent_runtime_api_contracts import AgentRuntimeApiContext
from cmm.agent_runtime.agent_runtime_cli_errors import (
    AgentRuntimeCliConfigError,
    AgentRuntimeCliUsageError,
)
from cmm.agent_runtime.agent_runtime_cli_parsers import (
    parse_json_file,
    parse_permissions,
)

ENV_ACTOR_ID = "CMM_AGENT_ACTOR_ID"
ENV_PERMISSIONS = "CMM_AGENT_PERMISSIONS"
ENV_OUTPUT = "CMM_AGENT_OUTPUT"
ENV_CONFIG = "CMM_AGENT_CONFIG"
ENV_NO_COLOR = "CMM_AGENT_NO_COLOR"

ALLOWED_ENV_VARS = frozenset(
    {ENV_ACTOR_ID, ENV_PERMISSIONS, ENV_OUTPUT, ENV_CONFIG, ENV_NO_COLOR}
)

# Safe default actor used only for read-only operations when no actor was
# configured anywhere. Mutating operations never fall back to this - they
# require an explicit actor or the request is rejected as a usage error.
DEFAULT_READONLY_ACTOR = "cli"

MAX_CONFIG_BYTES = 64 * 1024

# Operations for which an implicit/default actor is never acceptable.
MUTATING_OPERATIONS = frozenset(
    {
        "goal.create",
        "goal.update",
        "goal.prioritize",
        "goal.pause",
        "goal.resume",
        "goal.cancel",
        "run.start",
        "run.pause",
        "run.resume",
        "run.cancel",
        "approval.approve",
        "approval.reject",
        "budget.reserve",
        "budget.release",
        "event.publish",
        "event.replay",
        "dead_letter.replay",
    }
)

_CONFIG_STRING_KEYS = ("actor_id", "output")
_CONFIG_BOOL_KEYS = ("no_color",)


class AgentRuntimeCliContextBuilder:
    """Resolves CLI context and cross-cutting settings from layered sources."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = env if env is not None else os.environ

    def _env_get(self, name: str) -> str | None:
        if name not in ALLOWED_ENV_VARS:
            return None
        value = self._env.get(name)
        return value if value else None

    def load_config(self, path_text: str | None) -> dict[str, Any]:
        """Load and validate the optional JSON config file.

        Returns an empty dict when no path is given. Never returns or
        leaks unknown/extra keys' values in error messages.
        """
        if not path_text:
            return {}
        try:
            raw = parse_json_file(path_text, max_bytes=MAX_CONFIG_BYTES)
        except Exception as exc:
            raise AgentRuntimeCliConfigError("config file could not be loaded") from exc
        config: dict[str, Any] = {}
        for key in _CONFIG_STRING_KEYS:
            if key in raw:
                value = raw[key]
                if not isinstance(value, str):
                    raise AgentRuntimeCliConfigError(
                        f"config field '{key}' must be a string"
                    )
                config[key] = value
        if "permissions" in raw:
            value = raw["permissions"]
            if not isinstance(value, list) or not all(
                isinstance(v, str) for v in value
            ):
                raise AgentRuntimeCliConfigError(
                    "config field 'permissions' must be a list of strings"
                )
            config["permissions"] = list(value)
        for key in _CONFIG_BOOL_KEYS:
            if key in raw:
                value = raw[key]
                if not isinstance(value, bool):
                    raise AgentRuntimeCliConfigError(
                        f"config field '{key}' must be a boolean"
                    )
                config[key] = value
        return config

    def resolve_output_format(
        self,
        *,
        cli_output: str | None,
        config: Mapping[str, Any],
    ) -> str | None:
        if cli_output:
            return cli_output
        env_value = self._env_get(ENV_OUTPUT)
        if env_value:
            return env_value
        config_value = config.get("output")
        if isinstance(config_value, str) and config_value:
            return config_value
        return None

    def resolve_no_color(
        self, *, cli_no_color: bool, config: Mapping[str, Any]
    ) -> bool:
        if cli_no_color:
            return True
        env_value = self._env_get(ENV_NO_COLOR)
        if env_value is not None:
            return env_value.strip().lower() in {"1", "true", "yes", "on"}
        config_value = config.get("no_color")
        if isinstance(config_value, bool):
            return config_value
        return False

    def build(
        self,
        *,
        operation: str,
        actor_id: str | None,
        permissions: frozenset[str] | None,
        config: Mapping[str, Any] | None = None,
    ) -> AgentRuntimeApiContext:
        """Build the immutable API context for a single operation."""
        config = config or {}

        actor = actor_id or self._env_get(ENV_ACTOR_ID) or config.get("actor_id")
        if not actor:
            if operation in MUTATING_OPERATIONS:
                raise AgentRuntimeCliUsageError(
                    "an explicit actor is required for this operation "
                    "(--actor-id, CMM_AGENT_ACTOR_ID, or config actor_id)"
                )
            actor = DEFAULT_READONLY_ACTOR

        if permissions:
            resolved_permissions = permissions
        else:
            env_permissions = self._env_get(ENV_PERMISSIONS)
            if env_permissions:
                resolved_permissions = parse_permissions(
                    [p for p in env_permissions.split(",") if p.strip()]
                )
            else:
                config_permissions = config.get("permissions")
                if config_permissions:
                    resolved_permissions = parse_permissions(list(config_permissions))
                else:
                    resolved_permissions = frozenset()

        return AgentRuntimeApiContext(actor=actor, permissions=resolved_permissions)


__all__ = [
    "ALLOWED_ENV_VARS",
    "DEFAULT_READONLY_ACTOR",
    "ENV_ACTOR_ID",
    "ENV_CONFIG",
    "ENV_NO_COLOR",
    "ENV_OUTPUT",
    "ENV_PERMISSIONS",
    "MAX_CONFIG_BYTES",
    "MUTATING_OPERATIONS",
    "AgentRuntimeCliContextBuilder",
]
