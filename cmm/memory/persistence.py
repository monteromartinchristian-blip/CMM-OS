"""Small, atomic JSON persistence boundary for technical memory."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from cmm.memory.graph import KnowledgeGraph
from cmm.memory.models import KnowledgeEdge, KnowledgeNode, RelationType
from cmm.memory.results import ProjectChangeSet


SCHEMA_VERSION = 1
_EXCLUDED_PARTS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


class RepositoryError(RuntimeError):
    """Base class for structured repository failures."""


class RepositoryNotFoundError(RepositoryError):
    pass


class CorruptRepositoryError(RepositoryError):
    pass


class IncompatibleRepositoryError(RepositoryError):
    pass


class ProjectMismatchError(RepositoryError):
    pass


@dataclass(frozen=True, slots=True)
class FileFingerprint:
    path: str
    sha256: str
    size: int
    mtime_ns: int
    parse_error: str | None = None

    def serialize(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size": self.size,
            "mtime_ns": self.mtime_ns,
            "parse_error": self.parse_error,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "FileFingerprint":
        required = {"path", "sha256", "size", "mtime_ns"}
        if not required.issubset(payload):
            raise CorruptRepositoryError("File fingerprint is missing required fields.")
        if not isinstance(payload["path"], str) or not isinstance(payload["sha256"], str):
            raise CorruptRepositoryError("File fingerprint path/hash have invalid types.")
        if not isinstance(payload["size"], int) or not isinstance(payload["mtime_ns"], int):
            raise CorruptRepositoryError("File fingerprint size/mtime have invalid types.")
        return cls(payload["path"], payload["sha256"], payload["size"], payload["mtime_ns"], payload.get("parse_error"))


@dataclass(frozen=True, slots=True)
class ProjectSnapshot:
    project_root: str
    files: Mapping[str, FileFingerprint]
    updated_at: str

    def serialize(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "updated_at": self.updated_at,
            "files": {path: item.serialize() for path, item in sorted(self.files.items())},
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ProjectSnapshot":
        files = payload.get("files")
        if not isinstance(files, Mapping) or not isinstance(payload.get("project_root"), str):
            raise CorruptRepositoryError("Project snapshot has an invalid schema.")
        return cls(
            project_root=payload["project_root"],
            files={str(path): FileFingerprint.from_mapping(item) for path, item in files.items()},
            updated_at=str(payload.get("updated_at", "")),
        )


def scan_project(project_root: Path) -> ProjectSnapshot:
    root = Path(project_root).resolve(strict=True)
    files: dict[str, FileFingerprint] = {}
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if any(part in _EXCLUDED_PARTS for part in relative.parts) or not path.is_file() or path.is_symlink():
            continue
        try:
            path.resolve(strict=True).relative_to(root)
        except (OSError, ValueError):
            continue
        content = path.read_bytes()
        parse_error = None
        try:
            import ast

            ast.parse(content.decode("utf-8"), filename=relative.as_posix())
        except (SyntaxError, UnicodeDecodeError) as error:
            parse_error = str(error)
        stat = path.stat()
        files[relative.as_posix()] = FileFingerprint(
            relative.as_posix(), hashlib.sha256(content).hexdigest(), stat.st_size, stat.st_mtime_ns, parse_error
        )
    return ProjectSnapshot(str(root), files, datetime.now(timezone.utc).isoformat())


def compare_snapshots(previous: ProjectSnapshot | None, current: ProjectSnapshot) -> ProjectChangeSet:
    if previous is None:
        return ProjectChangeSet(created=tuple(sorted(current.files)), parse_errors=tuple(sorted(
            path for path, item in current.files.items() if item.parse_error
        )))
    old_files = previous.files
    new_files = current.files
    created = set(new_files).difference(old_files)
    deleted = set(old_files).difference(new_files)
    modified = {
        path for path in set(old_files).intersection(new_files)
        if old_files[path] != new_files[path]
    }
    renamed: list[tuple[str, str]] = []
    for old_path in sorted(deleted):
        matches = [new_path for new_path in sorted(created) if old_files[old_path].sha256 == new_files[new_path].sha256]
        if len(matches) == 1:
            new_path = matches[0]
            renamed.append((old_path, new_path))
            created.remove(new_path)
            deleted.remove(old_path)
    parse_errors = tuple(sorted(path for path, item in new_files.items() if item.parse_error))
    return ProjectChangeSet(tuple(sorted(created)), tuple(sorted(modified)), tuple(sorted(deleted)), tuple(renamed), parse_errors)


class PersistentKnowledgeRepository:
    """Versioned JSON repository with atomic replacement and project binding."""

    def __init__(self, path: Path, project_root: Path | None = None) -> None:
        self.path = Path(path)
        self.project_root = (Path(project_root) if project_root is not None else self.path.parent).resolve(strict=False)

    def load(self) -> KnowledgeGraph:
        graph, _snapshot = self.load_snapshot()
        return graph

    def load_snapshot(self) -> tuple[KnowledgeGraph, ProjectSnapshot]:
        if not self.path.exists():
            raise RepositoryNotFoundError(f"Memory repository does not exist: {self.path}")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CorruptRepositoryError(f"Unable to read memory repository: {error}") from error
        if not isinstance(payload, Mapping) or payload.get("schema_version") != SCHEMA_VERSION:
            raise IncompatibleRepositoryError("Unsupported or missing memory repository schema version.")
        snapshot = ProjectSnapshot.from_mapping(payload.get("snapshot", {}))
        self._validate_project(snapshot.project_root)
        graph = self._decode_graph(payload.get("graph"))
        return graph, snapshot

    def save(self, graph: KnowledgeGraph) -> None:
        self.save_snapshot(graph, scan_project(self.project_root))

    def save_snapshot(self, graph: KnowledgeGraph, snapshot: ProjectSnapshot) -> None:
        self._validate_graph_paths(graph)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "snapshot": snapshot.serialize(),
            "graph": self._encode_graph(graph),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, prefix=f".{self.path.name}.", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(payload, handle, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except OSError as error:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise RepositoryError(f"Unable to persist memory repository: {error}") from error

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)

    def _validate_project(self, stored_root: str) -> None:
        try:
            Path(stored_root).resolve(strict=False).relative_to(self.project_root)
            self.project_root.relative_to(Path(stored_root).resolve(strict=False))
        except ValueError as error:
            raise ProjectMismatchError(
                f"Memory repository belongs to {stored_root}, not {self.project_root}."
            ) from error

    def _validate_graph_paths(self, graph: KnowledgeGraph) -> None:
        for node in graph.nodes.values():
            if node.source_path is None:
                continue
            try:
                Path(node.source_path).resolve(strict=False).relative_to(self.project_root)
            except ValueError as error:
                raise ProjectMismatchError(f"Node path escapes project: {node.source_path}") from error

    def _encode_graph(self, graph: KnowledgeGraph) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "identifier": node.identifier,
                    "title": node.title,
                    "kind": node.kind,
                    "summary": node.summary,
                    "source_path": str(node.source_path) if node.source_path is not None else None,
                    "metadata": _json_safe(node.metadata),
                }
                for node in graph.nodes.values()
            ],
            "edges": [
                {
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "relation": edge.relation.value,
                    "metadata": _json_safe(edge.metadata),
                }
                for edge in graph.edges
            ],
        }

    def _decode_graph(self, payload: Any) -> KnowledgeGraph:
        if not isinstance(payload, Mapping) or not isinstance(payload.get("nodes"), list) or not isinstance(payload.get("edges"), list):
            raise CorruptRepositoryError("Memory graph has an invalid schema.")
        graph = KnowledgeGraph()
        for item in payload["nodes"]:
            if not isinstance(item, Mapping) or not all(isinstance(item.get(key), str) for key in ("identifier", "title", "kind", "summary")):
                raise CorruptRepositoryError("Memory graph contains an invalid node.")
            source = item.get("source_path")
            source_path = Path(source) if isinstance(source, str) else None
            if source_path is not None:
                try:
                    source_path.resolve(strict=False).relative_to(self.project_root)
                except ValueError as error:
                    raise ProjectMismatchError(f"Persisted node path escapes project: {source_path}") from error
            metadata = item.get("metadata", {})
            if not isinstance(metadata, Mapping):
                raise CorruptRepositoryError("Memory node metadata must be an object.")
            graph.add_node(KnowledgeNode(item["identifier"], item["title"], item["kind"], item["summary"], source_path, metadata))
        for item in payload["edges"]:
            if not isinstance(item, Mapping) or not all(isinstance(item.get(key), str) for key in ("source_id", "target_id", "relation")):
                raise CorruptRepositoryError("Memory graph contains an invalid edge.")
            try:
                relation = RelationType(item["relation"])
            except ValueError as error:
                raise CorruptRepositoryError(f"Unknown graph relation: {item['relation']}") from error
            metadata = item.get("metadata", {})
            if not isinstance(metadata, Mapping):
                raise CorruptRepositoryError("Memory edge metadata must be an object.")
            if item["source_id"] not in graph.nodes or item["target_id"] not in graph.nodes:
                raise CorruptRepositoryError("Memory edge references an unknown node.")
            graph.add_edge(KnowledgeEdge(item["source_id"], item["target_id"], relation, metadata))
        return graph


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
