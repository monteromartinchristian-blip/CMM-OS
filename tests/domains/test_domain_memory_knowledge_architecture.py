"""Phase 10.44 — Architecture, privacy, and anti-fragmentation boundary hardening.

Asserts:
- No prohibited owner classes (no Knowledge Graph, Store, Repository, or Engine in Domains).
- Strict reverse-import ban (cmm.cognitive and cmm.agent_runtime never import cmm.domains).
- TechnicalMemory boundary (no imports of cmm.memory or TechnicalMemory in Phase 10.44 or api.py).
- Zero Cognitive-store mutations in DefaultDomainMemoryKnowledgeIntegrator.
- Zero sensitive payload fields in dataclass fields and serialized dictionaries.
- Fail-closed deterministic diagnostics that never leak sensitive payload values.
"""

from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

import pytest

from cmm.domains.identifiers import DomainId
from cmm.domains.memory_contracts import (
    DomainMemoryReferenceInventory,
    DomainMemoryViewRequest,
)
from cmm.domains.memory_knowledge_integration import (
    DefaultDomainMemoryKnowledgeIntegrator,
)
from cmm.domains.memory_knowledge_integration_contracts import (
    FORBIDDEN_PAYLOAD_FIELDS,
    DomainMemoryKnowledgeContradictionRef,
    DomainMemoryKnowledgeInventory,
    DomainMemoryKnowledgePath,
    DomainMemoryKnowledgePathHop,
    DomainMemoryKnowledgeProjection,
    DomainMemoryKnowledgeProjectionCapability,
    DomainMemoryKnowledgeProjectionRequest,
    DomainMemoryKnowledgeRelationRef,
)
from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PHASE_10_44_FILES = (
    REPO_ROOT / "cmm" / "domains" / "memory_knowledge_integration_contracts.py",
    REPO_ROOT / "cmm" / "domains" / "memory_knowledge_integration.py",
)

PROHIBITED_OWNER_NAMES = frozenset(
    {
        "DomainKnowledgeGraph",
        "DomainGraphStore",
        "DomainGraphRepository",
        "DomainMemoryStore",
        "DomainMemoryRepository",
        "DomainTemporalEngine",
        "DomainContradictionEngine",
        "DomainRelationRepository",
        "DomainProposalRepository",
    }
)


class TestProhibitedOwnerNames:
    """Ensure Phase 10.44 introduces no duplicate Knowledge Graph, store, or engine."""

    def test_no_prohibited_owner_classes_defined(self) -> None:
        for file_path in PHASE_10_44_FILES:
            tree = ast.parse(
                file_path.read_text(encoding="utf-8"), filename=str(file_path)
            )
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    assert node.name not in PROHIBITED_OWNER_NAMES, (
                        f"Prohibited owner class {node.name} defined in {file_path.name}"
                    )
                    for suffix in ("Store", "Repository", "Engine"):
                        assert not node.name.endswith(suffix), (
                            f"Prohibited owner class {node.name} ends with {suffix} in {file_path.name}"
                        )


class TestReverseImports:
    """Ensure Cognitive layer and Agent Runtime never import Domain Intelligence."""

    def test_cognitive_never_imports_domains(self) -> None:
        cognitive_dir = REPO_ROOT / "cmm" / "cognitive"
        for py_file in cognitive_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("cmm.domains"), (
                            f"Illegal reverse import '{alias.name}' in {py_file}"
                        )
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    assert not mod.startswith("cmm.domains"), (
                        f"Illegal reverse import 'from {mod}' in {py_file}"
                    )

    def test_agent_runtime_never_imports_domains(self) -> None:
        runtime_dir = REPO_ROOT / "cmm" / "agent_runtime"
        for py_file in runtime_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("cmm.domains"), (
                            f"Illegal reverse import '{alias.name}' in {py_file}"
                        )
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    assert not mod.startswith("cmm.domains"), (
                        f"Illegal reverse import 'from {mod}' in {py_file}"
                    )


class TestTechnicalMemoryBoundary:
    """Ensure no imports from cmm.memory or TechnicalMemory in Phase 10.44 or api.py."""

    def test_no_cmm_memory_imports(self) -> None:
        files_to_check = (
            *PHASE_10_44_FILES,
            REPO_ROOT / "cmm" / "domains" / "api.py",
        )
        for file_path in files_to_check:
            tree = ast.parse(
                file_path.read_text(encoding="utf-8"), filename=str(file_path)
            )
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("cmm.memory"), (
                            f"Prohibited import {alias.name} in {file_path.name}"
                        )
                        assert "TechnicalMemory" not in alias.name, (
                            f"Prohibited TechnicalMemory in {file_path.name}"
                        )
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    assert not mod.startswith("cmm.memory"), (
                        f"Prohibited import from {mod} in {file_path.name}"
                    )
                    for alias in node.names:
                        assert "TechnicalMemory" not in alias.name, (
                            f"Prohibited TechnicalMemory in {file_path.name}"
                        )


class TestCognitiveStoreMutationProhibited:
    """Ensure DefaultDomainMemoryKnowledgeIntegrator never calls store mutation methods."""

    def test_no_store_mutation_calls(self) -> None:
        integrator_file = (
            REPO_ROOT / "cmm" / "domains" / "memory_knowledge_integration.py"
        )
        tree = ast.parse(
            integrator_file.read_text(encoding="utf-8"), filename=str(integrator_file)
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr_name = node.func.attr
                if attr_name in {
                    "update",
                    "invalidate",
                    "relate",
                    "delete",
                    "save",
                    "commit",
                }:
                    raise AssertionError(
                        f"Prohibited mutation verb '{attr_name}' called in {integrator_file.name} at line {node.lineno}"
                    )
                if attr_name == "add" and not (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id
                    in {"used_relation_ids", "unknown_set", "visited", "seen"}
                ):
                    raise AssertionError(
                        f"Prohibited store mutation 'add' called on non-local object in {integrator_file.name} at line {node.lineno}"
                    )


class TestSensitiveFieldSchema:
    """Ensure Phase 10.44 public contracts never define or serialize payload fields."""

    CONTRACT_CLASSES = (
        DomainMemoryKnowledgeRelationRef,
        DomainMemoryKnowledgeContradictionRef,
        DomainMemoryKnowledgePathHop,
        DomainMemoryKnowledgePath,
        DomainMemoryKnowledgeInventory,
        DomainMemoryKnowledgeProjectionRequest,
        DomainMemoryKnowledgeProjection,
    )

    def test_dataclass_fields_contain_no_forbidden_names(self) -> None:
        for cls in self.CONTRACT_CLASSES:
            if is_dataclass(cls):
                field_names = {f.name for f in fields(cls)}
                leak = field_names.intersection(FORBIDDEN_PAYLOAD_FIELDS)
                assert not leak, f"Forbidden fields {leak} found on {cls.__name__}"

    def test_serialized_dictionaries_contain_no_forbidden_names(self) -> None:
        hop = DomainMemoryKnowledgePathHop(
            relation_id="rel-1",
            source_reference_id="ref:a",
            target_reference_id="ref:b",
            kind="related_to",
        )
        path = DomainMemoryKnowledgePath.create((hop,))
        rel_ref = DomainMemoryKnowledgeRelationRef(
            relation_id="rel-1",
            source_reference_id="ref:a",
            target_reference_id="ref:b",
            kind="related_to",
        )
        contra_ref = DomainMemoryKnowledgeContradictionRef(
            contradiction_id="contra-1",
            reference_ids=("ref:a", "ref:b"),
            resolution_reference_id="res-1",
        )
        req = DomainMemoryKnowledgeProjectionRequest(
            request_id="req-1",
            primary_domain=DomainId("billing"),
            supporting_domains=(),
            memory_view_id="view:req-1:0123456789ab",
            memory_view_digest="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            resolution_reference_id="res-1",
            composition_reference_id="comp-1",
            permission_decision_ids=(),
            requested_capabilities=(
                DomainMemoryKnowledgeProjectionCapability.RELATIONS,
            ),
        )
        inv = DomainMemoryKnowledgeInventory()
        proj = DomainMemoryKnowledgeProjection.create(
            request_id="req-1",
            request_digest="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            memory_view_id="view:req-1:0123456789ab",
            memory_view_digest="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            selected_reference_ids=("ref:a", "ref:b"),
            shared_identity_reference_ids=(),
            relation_refs=(rel_ref,),
            contradiction_refs=(contra_ref,),
            dependency_paths=(path,),
            impact_paths=(),
            proposal_binding_ids=(),
            excluded_reference_ids=(),
        )

        def _assert_no_forbidden_keys(obj: Any) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    assert k not in FORBIDDEN_PAYLOAD_FIELDS, (
                        f"Forbidden key '{k}' found in serialized dict"
                    )
                    _assert_no_forbidden_keys(v)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    _assert_no_forbidden_keys(item)

        for instance in (hop, path, rel_ref, contra_ref, req, inv, proj):
            if hasattr(instance, "to_dict"):
                d = instance.to_dict()
                _assert_no_forbidden_keys(d)


class TestDeterministicDiagnosticsLeaking:
    """Ensure error messages never echo sensitive probe strings."""

    SENSITIVE_PROBE = "SUPER_SECRET_TOKEN_xyz_12345"

    def test_digest_error_does_not_leak_sensitive_value(self) -> None:
        with pytest.raises(Exception) as exc_info:
            DomainMemoryKnowledgeProjectionRequest(
                request_id="req-1",
                primary_domain=DomainId("billing"),
                supporting_domains=(),
                memory_view_id="view:req-1:0123456789ab",
                memory_view_digest=f"bad_digest_{self.SENSITIVE_PROBE}",
                resolution_reference_id="res-1",
                composition_reference_id="comp-1",
                permission_decision_ids=(),
                requested_capabilities=(),
            )
        err_str = str(exc_info.value)
        assert self.SENSITIVE_PROBE not in err_str

    def test_relation_ref_error_does_not_leak_sensitive_value(self) -> None:
        with pytest.raises(Exception) as exc_info:
            DomainMemoryKnowledgeRelationRef(
                relation_id="   ",
                source_reference_id=f"ref:{self.SENSITIVE_PROBE}",
                target_reference_id="ref:b",
                kind="rel",
            )
        err_str = str(exc_info.value)
        assert self.SENSITIVE_PROBE not in err_str

    def test_authorization_mismatch_error_does_not_leak_sensitive_value(self) -> None:
        integrator = DefaultDomainMemoryKnowledgeIntegrator()
        mem_req = DomainMemoryViewRequest(
            request_id="req-1", primary_domain=DomainId("analytics")
        )
        mem_inv = DomainMemoryReferenceInventory(references=())
        view = DefaultDomainMemoryViewResolver().resolve(mem_req, mem_inv)
        req = DomainMemoryKnowledgeProjectionRequest(
            request_id=f"req-{self.SENSITIVE_PROBE}",
            primary_domain=DomainId("billing"),
            supporting_domains=(),
            memory_view_id=view.view_id,
            memory_view_digest=view.content_digest,
            resolution_reference_id="res-1",
            composition_reference_id="comp-1",
            permission_decision_ids=(),
            requested_capabilities=(),
        )
        inv = DomainMemoryKnowledgeInventory()

        with pytest.raises(Exception) as exc_info:
            integrator.project(
                req,
                memory_request=mem_req,
                view=view,
                memory_inventory=mem_inv,
                inventory=inv,
            )
        err_str = str(exc_info.value)
        assert self.SENSITIVE_PROBE not in err_str
