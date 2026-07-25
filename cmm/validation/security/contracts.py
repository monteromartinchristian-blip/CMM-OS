from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from cmm.validation.errors import ValidationContractError


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return (str(value),)


def _as_path_tuple(value: Any) -> tuple[Path, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        items = value
    elif isinstance(value, list):
        items = tuple(value)
    else:
        items = (value,)
    return tuple(Path(str(item)) for item in items)


def _matches_pattern(value: str, pattern: str) -> bool:
    if pattern.endswith("*"):
        return value.startswith(pattern[:-1])
    return value == pattern


def _summarize_step(step: Mapping[str, Any]) -> dict[str, Any]:
    command_source = step.get("command") or ()
    command = tuple(str(item) for item in command_source if item is not None)
    environment = step.get("environment")
    environment_keys: tuple[str, ...] = ()
    if isinstance(environment, Mapping):
        environment_keys = tuple(sorted(str(key) for key in environment.keys()))
    metadata = step.get("metadata")
    metadata_keys: tuple[str, ...] = ()
    if isinstance(metadata, Mapping):
        metadata_keys = tuple(sorted(str(key) for key in metadata.keys()))
    return {
        "name": str(step.get("name", "")),
        "step_type": str(step.get("step_type", "command")),
        "command": list(command),
        "command_length": len(command),
        "required": bool(step.get("required", True)),
        "timeout_seconds": int(step.get("timeout_seconds", 0) or 0),
        "stop_on_failure": bool(step.get("stop_on_failure", True)),
        "working_directory": step.get("working_directory"),
        "dependencies": list(step.get("dependencies", ()) or ()),
        "tags": list(step.get("tags", ()) or ()),
        "allowed_exit_codes": list(step.get("allowed_exit_codes", ()) or ()),
        "environment_keys": list(environment_keys),
        "metadata_keys": list(metadata_keys),
    }


class SecurityScope(str, Enum):
    AFFECTED = "affected"
    FULL = "full"


@dataclass(frozen=True, slots=True)
class CommandPolicy:
    allowed_executables: tuple[str, ...] = (
        "python*",
        "pytest",
        "ruff",
        "mypy",
        "vulture",
        "pyright",
        "bandit",
        "pip-audit",
        "pip_audit",
        "git",
    )
    forbidden_arguments: tuple[str, ...] = ("-c",)
    allow_shell: bool = False
    allow_network: bool = False
    allowed_working_directories: tuple[str, ...] = ()
    environment_allowlist: tuple[str, ...] = (
        "PATH",
        "HOME",
        "TMPDIR",
        "TMP",
        "TEMP",
        "LANG",
        "LC_*",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONIOENCODING",
        "PYTHONHASHSEED",
        "VIRTUAL_ENV",
        "TERM",
        "NO_COLOR",
        "CI",
        "GITHUB_*",
        "RUNNER_*",
        "USER",
        "LOGNAME",
        "SHELL",
        "SYSTEMROOT",
        "WINDIR",
        "PROGRAMDATA",
    )
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "allowed_executables", _as_tuple(self.allowed_executables)
        )
        object.__setattr__(
            self, "forbidden_arguments", _as_tuple(self.forbidden_arguments)
        )
        object.__setattr__(
            self,
            "allowed_working_directories",
            _as_tuple(self.allowed_working_directories),
        )
        object.__setattr__(
            self, "environment_allowlist", _as_tuple(self.environment_allowlist)
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def allows_executable(self, executable: str) -> bool:
        candidate = Path(executable).name
        return any(
            _matches_pattern(candidate, pattern)
            or _matches_pattern(executable, pattern)
            for pattern in self.allowed_executables
        )

    def allows_environment_key(self, key: str) -> bool:
        return any(
            _matches_pattern(key, pattern) for pattern in self.environment_allowlist
        )

    def allows_working_directory(self, cwd: Path, project_root: Path) -> bool:
        try:
            cwd.resolve(strict=False).relative_to(project_root.resolve(strict=False))
            return True
        except Exception:
            pass
        for allowed in self.allowed_working_directories:
            candidate = Path(allowed)
            if candidate.is_absolute():
                try:
                    cwd.resolve(strict=False).relative_to(
                        candidate.resolve(strict=False)
                    )
                    return True
                except Exception:
                    continue
            else:
                try:
                    cwd.resolve(strict=False).relative_to(
                        (project_root / candidate).resolve(strict=False)
                    )
                    return True
                except Exception:
                    continue
        return False

    def serialize(self) -> dict[str, Any]:
        return {
            "allowed_executables": list(self.allowed_executables),
            "forbidden_arguments": list(self.forbidden_arguments),
            "allow_shell": self.allow_shell,
            "allow_network": self.allow_network,
            "allowed_working_directories": list(self.allowed_working_directories),
            "environment_allowlist": list(self.environment_allowlist),
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CommandPolicy":
        return cls(
            allowed_executables=_as_tuple(payload.get("allowed_executables", ())),
            forbidden_arguments=_as_tuple(payload.get("forbidden_arguments", ())),
            allow_shell=bool(payload.get("allow_shell", False)),
            allow_network=bool(payload.get("allow_network", False)),
            allowed_working_directories=_as_tuple(
                payload.get("allowed_working_directories", ())
            ),
            environment_allowlist=_as_tuple(payload.get("environment_allowlist", ())),
            metadata=dict(payload.get("metadata", {}))
            if isinstance(payload.get("metadata"), Mapping)
            else {},
        )


def default_command_policy() -> CommandPolicy:
    return CommandPolicy()


@dataclass(frozen=True, slots=True)
class SecurityAnalysisPlan:
    project_root: Path
    scope: SecurityScope
    complete: bool
    reason: str
    files: tuple[Path, ...]
    change_type: str
    public_api_changed: bool
    requires_full_suite: bool
    confidence: float
    uncertainty: tuple[str, ...] = ()
    command_policy: CommandPolicy = field(default_factory=default_command_policy)
    planned_steps: tuple[Mapping[str, Any], ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "project_root", Path(self.project_root).resolve(strict=False)
        )
        object.__setattr__(self, "files", _as_path_tuple(self.files))
        object.__setattr__(self, "uncertainty", _as_tuple(self.uncertainty))
        object.__setattr__(
            self,
            "planned_steps",
            tuple(dict(step) for step in (self.planned_steps or ())),
        )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationContractError(
                "SecurityAnalysisPlan.confidence must be between 0 and 1"
            )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "scope": self.scope.value,
            "complete": self.complete,
            "reason": self.reason,
            "files": [str(path) for path in self.files],
            "change_type": self.change_type,
            "public_api_changed": self.public_api_changed,
            "requires_full_suite": self.requires_full_suite,
            "confidence": self.confidence,
            "uncertainty": list(self.uncertainty),
            "command_policy": self.command_policy.serialize(),
            "planned_steps": [_summarize_step(step) for step in self.planned_steps],
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SecurityAnalysisPlan":
        return cls(
            project_root=Path(str(payload["project_root"])),
            scope=SecurityScope(
                str(payload.get("scope", SecurityScope.AFFECTED.value))
            ),
            complete=bool(payload.get("complete", True)),
            reason=str(payload.get("reason", "")),
            files=_as_path_tuple(payload.get("files", ())),
            change_type=str(payload.get("change_type", "unknown")),
            public_api_changed=bool(payload.get("public_api_changed", False)),
            requires_full_suite=bool(payload.get("requires_full_suite", False)),
            confidence=float(payload.get("confidence", 0.0)),
            uncertainty=_as_tuple(payload.get("uncertainty", ())),
            command_policy=CommandPolicy.from_mapping(payload.get("command_policy", {}))
            if isinstance(payload.get("command_policy"), Mapping)
            else default_command_policy(),
            planned_steps=tuple(
                dict(step)
                for step in payload.get("planned_steps", ())
                if isinstance(step, Mapping)
            ),
            metadata=dict(payload.get("metadata", {}))
            if isinstance(payload.get("metadata"), Mapping)
            else {},
        )


__all__ = [
    "CommandPolicy",
    "SecurityAnalysisPlan",
    "SecurityScope",
    "default_command_policy",
]
