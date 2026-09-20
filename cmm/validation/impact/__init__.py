from __future__ import annotations

from .analyzer import ChangeImpactAnalyzer
from .contracts import (
    ChangeImpactResult,
    ChangeSet,
    ChangeType,
    DependencyEdge,
    DependencyGraph,
    FileChange,
    FileChangeKind,
    FileVersion,
    ImportChange,
    ImportChangeKind,
    ProjectSnapshot,
    PublicAPIChange,
    PublicAPIChangeKind,
    SymbolChange,
    SymbolChangeKind,
)
from .defaults import default_impact_steps
from .diff import PythonModuleDiff, diff_python_sources
from .git import GitChangeSetAdapter, GitChangeSetError
from .graph import affected_dependents, build_dependency_graph, module_name_from_path
from .snapshots import ChangeSetBuilder, scan_project_snapshot
from .validation import ChangeImpactValidator, change_impact_step

__all__ = [
    "ChangeImpactAnalyzer",
    "ChangeImpactResult",
    "ChangeImpactValidator",
    "ChangeSet",
    "ChangeSetBuilder",
    "ChangeType",
    "DependencyEdge",
    "DependencyGraph",
    "FileChange",
    "FileChangeKind",
    "FileVersion",
    "GitChangeSetAdapter",
    "GitChangeSetError",
    "ImportChange",
    "ImportChangeKind",
    "ProjectSnapshot",
    "PublicAPIChange",
    "PublicAPIChangeKind",
    "PythonModuleDiff",
    "SymbolChange",
    "SymbolChangeKind",
    "affected_dependents",
    "build_dependency_graph",
    "change_impact_step",
    "default_impact_steps",
    "diff_python_sources",
    "module_name_from_path",
    "scan_project_snapshot",
]
